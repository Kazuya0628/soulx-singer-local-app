from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from job_runner import run_inference_with_fallback  # noqa: E402


class FakeEngine:
    def __init__(self, fail_times=0, error_message="out of memory"):
        self.fail_times = fail_times
        self.error_message = error_message
        self.calls = []

    def infer(self, audio, segment_seconds, device):
        self.calls.append((audio, segment_seconds, device))
        if len(self.calls) <= self.fail_times:
            raise RuntimeError(self.error_message)
        return {"ok": True, "segment_seconds": segment_seconds, "device": device}


def _settings():
    return {
        "inference": {"segment_seconds": 12},
        "fallback_policy": {
            "retry_count": 2,
            "on_oom_reduce_segment_seconds": True,
            "min_segment_seconds": 4,
        },
    }


def test_retry_reduces_segment_and_succeeds():
    engine = FakeEngine(fail_times=1)
    result = run_inference_with_fallback(
        engine=engine,
        audio="input.wav",
        settings=_settings(),
        device="mps",
    )

    assert result["ok"] is True
    assert len(engine.calls) == 2
    assert engine.calls[0][1] == 12
    assert engine.calls[1][1] == 10


def test_non_retryable_error_is_raised():
    engine = FakeEngine(fail_times=1, error_message="unexpected parse error")

    try:
        run_inference_with_fallback(
            engine=engine,
            audio="input.wav",
            settings=_settings(),
            device="mps",
        )
        assert False, "expected RuntimeError"
    except RuntimeError as exc:
        assert "unexpected parse error" in str(exc)
