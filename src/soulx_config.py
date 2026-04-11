from __future__ import annotations

from typing import Any


REQUIRED_TOKENS = ["{input}", "{output}", "{model}", "{device}"]


def validate_soulx_config(soulx_cfg: dict[str, Any]) -> tuple[bool, str]:
    template = str(soulx_cfg.get("command_template", "")).strip()
    if not template:
        return False, "command_template is required"

    missing = [token for token in REQUIRED_TOKENS if token not in template]
    if missing:
        return False, f"command_template missing required tokens: {', '.join(missing)}"

    return True, "ok"


def render_preview_command(
    soulx_cfg: dict[str, Any],
    input_audio: str,
    output_audio: str,
    model: str,
    device: str,
    segment_seconds: int,
) -> str:
    template = str(soulx_cfg.get("command_template", ""))
    return template.format(
        input=input_audio,
        output=output_audio,
        model=model,
        device=device,
        segment_seconds=segment_seconds,
    )
