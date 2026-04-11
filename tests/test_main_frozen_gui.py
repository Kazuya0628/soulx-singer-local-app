from pathlib import Path
import sys
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


def test_frozen_app_without_args_launches_gui(tmp_path):
    cfg = tmp_path / "settings.yaml"
    cfg.write_text(
        "app:\n"
        "  device_preference: cpu\n"
        "  allow_fallback: true\n"
        "  startup_probe: false\n"
        "inference:\n"
        "  segment_seconds: 12\n"
        "soulx:\n"
        "  command_template: echo {input} {output} {model} {device}\n"
        "  output_suffix: .wav\n"
        "  skip_output_check: true\n",
        encoding="utf-8",
    )

    mock_launch = MagicMock()

    with patch("sys.argv", ["main.py", "--config", str(cfg)]):
        with patch.dict(sys.modules, {"gui": MagicMock(launch_gui=mock_launch)}):
            if "main" in sys.modules:
                del sys.modules["main"]
            import main

            with patch.object(main.sys, "frozen", True, create=True):
                result = main.main()

    assert result == 0
    mock_launch.assert_called_once_with(settings_path=str(cfg))
