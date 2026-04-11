from __future__ import annotations

from typing import Any


def run_inference_with_fallback(
    engine: Any,
    audio: str,
    settings: dict[str, Any],
    device: str,
) -> Any:
    policy = settings.get("fallback_policy", {})
    inf = settings.get("inference", {})

    retries = int(policy.get("retry_count", 0))
    reduce_segment = bool(policy.get("on_oom_reduce_segment_seconds", True))
    min_segment = int(policy.get("min_segment_seconds", 4))
    segment = int(inf.get("segment_seconds", 12))

    attempts = retries + 1
    for _ in range(attempts):
        try:
            return engine.infer(audio=audio, segment_seconds=segment, device=device)
        except RuntimeError as exc:
            msg = str(exc).lower()
            retryable = "out of memory" in msg or "mps" in msg
            if not retryable:
                raise

            if reduce_segment:
                segment = max(min_segment, segment - 2)

    raise RuntimeError("inference_failed_after_retries")
