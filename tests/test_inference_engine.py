from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from inference_engine import SoulXSingerEngine  # noqa: E402


def test_build_command_replaces_placeholders():
    engine = SoulXSingerEngine(
        model_path="models/soulx.pth",
        command_template=(
            "python infer.py --input {input} --output {output} "
            "--model {model} --device {device} --segment {segment_seconds}"
        ),
    )

    cmd = engine.build_command(
        audio="input.wav",
        output="out.wav",
        segment_seconds=10,
        device="mps",
    )

    assert cmd[:3] == ["python", "infer.py", "--input"]
    assert "input.wav" in cmd
    assert "out.wav" in cmd
    assert "models/soulx.pth" in cmd
    assert "mps" in cmd
    assert "10" in cmd


def test_build_command_supports_paths_with_spaces():
    engine = SoulXSingerEngine(
        model_path="models/model with space.pth",
        command_template=(
            "python infer.py --input {input} --output {output} "
            "--model {model} --device {device} --segment {segment_seconds}"
        ),
    )

    cmd = engine.build_command(
        audio="/tmp/input file.wav",
        output="/tmp/output file.wav",
        segment_seconds=12,
        device="cpu",
    )

    assert "/tmp/input file.wav" in cmd
    assert "/tmp/output file.wav" in cmd
    assert "models/model with space.pth" in cmd


def test_infer_raises_when_output_missing_with_skip_disabled(tmp_path):
    engine = SoulXSingerEngine(
        model_path="models/soulx.pth",
        command_template=f"\"{sys.executable}\" -c \"print('ok')\"",
        skip_output_check=False,
    )

    input_audio = tmp_path / "input.wav"
    input_audio.write_bytes(b"dummy")

    try:
        engine.infer(audio=str(input_audio), segment_seconds=12, device="cpu")
        assert False, "expected RuntimeError"
    except RuntimeError as exc:
        assert "Expected output file not found" in str(exc)


def test_infer_succeeds_when_skip_output_check_enabled(tmp_path):
    engine = SoulXSingerEngine(
        model_path="models/soulx.pth",
        command_template=f"\"{sys.executable}\" -c \"print('ok')\"",
        skip_output_check=True,
    )

    input_audio = tmp_path / "input.wav"
    input_audio.write_bytes(b"dummy")

    result = engine.infer(audio=str(input_audio), segment_seconds=12, device="cpu")

    assert result.ok is True
    assert result.device == "cpu"
    assert result.output_path.endswith(".sung.wav")


def test_infer_checks_relative_output_inside_work_dir(tmp_path):
    engine = SoulXSingerEngine(
        model_path="models/soulx.pth",
        command_template=f"\"{sys.executable}\" -c \"open('input.sung.wav', 'wb').write(b'ok')\"",
        skip_output_check=False,
        work_dir=str(tmp_path),
    )

    input_audio = tmp_path / "input.wav"
    input_audio.write_bytes(b"dummy")

    result = engine.infer(audio="input.wav", segment_seconds=12, device="cpu")

    assert result.ok is True
    assert (tmp_path / "input.sung.wav").exists()


def test_infer_raises_when_preexisting_output_is_not_updated(tmp_path):
    engine = SoulXSingerEngine(
        model_path="models/soulx.pth",
        command_template=f"\"{sys.executable}\" -c \"print('ok')\"",
        skip_output_check=False,
        work_dir=str(tmp_path),
    )

    input_audio = tmp_path / "input.wav"
    input_audio.write_bytes(b"dummy")

    stale_output = tmp_path / "input.sung.wav"
    stale_output.write_bytes(b"old")

    try:
        engine.infer(audio="input.wav", segment_seconds=12, device="cpu")
        assert False, "expected RuntimeError"
    except RuntimeError as exc:
        assert "Expected output file not updated" in str(exc)
