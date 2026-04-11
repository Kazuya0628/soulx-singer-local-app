from pathlib import Path
import subprocess
import sys


def test_main_dry_run_prints_command(tmp_path):
    root = Path(__file__).resolve().parents[1]
    src = root / "src"

    cfg = tmp_path / "settings.yaml"
    cfg.write_text(
        """
app:
  device_preference: cpu
  allow_fallback: true
  startup_probe: false
  log_level: INFO

inference:
  segment_seconds: 12

fallback_policy:
  retry_count: 0

soulx:
  command_template: python infer.py --input {input} --output {output} --model {model} --device {device}
  output_suffix: .sung.wav
  skip_output_check: true
  work_dir: null
""".strip(),
        encoding="utf-8",
    )

    input_audio = tmp_path / "in.wav"
    input_audio.write_bytes(b"dummy")

    cmd = [
        sys.executable,
        str(src / "main.py"),
        "--config",
        str(cfg),
        "--audio",
        str(input_audio),
        "--model",
        "model.pth",
        "--dry-run",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, cwd=str(root))

    assert proc.returncode == 0
    assert "dry_run_command=" in proc.stdout
    assert "model.pth" in proc.stdout
    assert "--device cpu" in proc.stdout
