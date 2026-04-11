from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from soulx_config import validate_soulx_config, render_preview_command  # noqa: E402


def test_validate_requires_minimum_placeholders():
    bad = {
        "command_template": "python infer.py --input {input} --output {output}",
    }
    ok, msg = validate_soulx_config(bad)
    assert ok is False
    assert "{model}" in msg


def test_validate_accepts_required_placeholders():
    good = {
        "command_template": "python infer.py --input {input} --output {output} --model {model} --device {device}",
    }
    ok, msg = validate_soulx_config(good)
    assert ok is True
    assert msg == "ok"


def test_render_preview_command_replaces_tokens():
    cfg = {
        "command_template": "python infer.py --input {input} --output {output} --model {model} --device {device} --segment {segment_seconds}",
    }
    cmd = render_preview_command(
        soulx_cfg=cfg,
        input_audio="in.wav",
        output_audio="out.wav",
        model="m.pth",
        device="cpu",
        segment_seconds=12,
    )
    assert "in.wav" in cmd
    assert "out.wav" in cmd
    assert "m.pth" in cmd
    assert "cpu" in cmd
    assert "12" in cmd
