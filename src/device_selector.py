from dataclasses import dataclass

try:
    import torch
except Exception:  # pragma: no cover
    torch = None


@dataclass
class DeviceConfig:
    device_preference: str = "auto"
    allow_fallback: bool = True
    startup_probe: bool = True


@dataclass
class DeviceDecision:
    device: str
    used_fallback: bool
    reason: str


def _mps_ready(startup_probe: bool = True) -> tuple[bool, str]:
    if torch is None:
        return False, "torch_not_installed"

    if not hasattr(torch, "backends") or not hasattr(torch.backends, "mps"):
        return False, "mps_backend_missing"

    if not torch.backends.mps.is_built():
        return False, "mps_not_built"

    if not torch.backends.mps.is_available():
        return False, "mps_not_available"

    if startup_probe:
        try:
            t = torch.randn((256, 256), device="mps")
            _ = (t @ t).mean().item()
        except Exception as exc:
            return False, f"mps_probe_failed:{exc}"

    return True, "mps_ok"


def resolve_device(cfg: DeviceConfig) -> DeviceDecision:
    pref = (cfg.device_preference or "auto").lower()

    if pref == "cpu":
        return DeviceDecision(device="cpu", used_fallback=False, reason="forced_cpu")

    if pref == "mps":
        ok, reason = _mps_ready(startup_probe=cfg.startup_probe)
        if ok:
            return DeviceDecision(device="mps", used_fallback=False, reason=reason)
        if cfg.allow_fallback:
            return DeviceDecision(device="cpu", used_fallback=True, reason=reason)
        raise RuntimeError(f"MPS required but unavailable: {reason}")

    ok, reason = _mps_ready(startup_probe=cfg.startup_probe)
    if ok:
        return DeviceDecision(device="mps", used_fallback=False, reason=reason)

    return DeviceDecision(device="cpu", used_fallback=True, reason=reason)
