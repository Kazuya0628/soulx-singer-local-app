from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from device_selector import DeviceConfig, resolve_device  # noqa: E402


class _BackendMps:
    def __init__(self, built=True, available=True):
        self._built = built
        self._available = available

    def is_built(self):
        return self._built

    def is_available(self):
        return self._available


class _TorchStub:
    def __init__(self, built=True, available=True, fail_probe=False):
        class Backends:
            pass

        self.backends = Backends()
        self.backends.mps = _BackendMps(built=built, available=available)
        self._fail_probe = fail_probe

    def randn(self, *args, **kwargs):
        if self._fail_probe:
            raise RuntimeError("probe failed")
        return self

    def __matmul__(self, _other):
        return self

    def mean(self):
        return self

    def item(self):
        return 1.0


def test_auto_uses_mps_when_available(monkeypatch):
    import device_selector

    monkeypatch.setattr(device_selector, "torch", _TorchStub())
    decision = resolve_device(DeviceConfig(device_preference="auto"))
    assert decision.device == "mps"
    assert decision.used_fallback is False


def test_auto_falls_back_to_cpu_when_mps_unavailable(monkeypatch):
    import device_selector

    monkeypatch.setattr(device_selector, "torch", _TorchStub(available=False))
    decision = resolve_device(DeviceConfig(device_preference="auto"))
    assert decision.device == "cpu"
    assert decision.used_fallback is True


def test_mps_forced_without_fallback_raises(monkeypatch):
    import device_selector

    monkeypatch.setattr(device_selector, "torch", _TorchStub(available=False))
    cfg = DeviceConfig(device_preference="mps", allow_fallback=False)

    try:
        resolve_device(cfg)
        assert False, "expected RuntimeError"
    except RuntimeError as exc:
        assert "MPS required" in str(exc)


def test_probe_failure_falls_back_to_cpu(monkeypatch):
    import device_selector

    monkeypatch.setattr(device_selector, "torch", _TorchStub(fail_probe=True))
    decision = resolve_device(DeviceConfig(device_preference="auto", startup_probe=True))
    assert decision.device == "cpu"
    assert decision.used_fallback is True
