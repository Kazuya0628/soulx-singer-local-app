"""GUI module tests — no display required (headless-safe)."""

from datetime import datetime
from pathlib import Path
import sys
from unittest.mock import patch, MagicMock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


def _mock_tk():
    """Return a mock tkinter module so tests run without a display."""
    mock_tk = MagicMock()
    mock_tk.X = "x"
    mock_tk.Y = "y"
    mock_tk.W = "w"
    mock_tk.EW = "ew"
    mock_tk.BOTH = "both"
    mock_tk.LEFT = "left"
    mock_tk.RIGHT = "right"
    mock_tk.END = "end"
    mock_tk.NORMAL = "normal"
    mock_tk.DISABLED = "disabled"
    mock_tk.VERTICAL = "vertical"
    mock_tk.WORD = "word"
    mock_tk.StringVar.return_value = MagicMock(get=MagicMock(return_value=""), set=MagicMock())
    mock_tk.IntVar.return_value = MagicMock(get=MagicMock(return_value=12), set=MagicMock())
    return mock_tk


def test_gui_module_imports():
    """gui.py can be imported without a display by mocking tkinter."""
    mock_tk = _mock_tk()
    with patch.dict(sys.modules, {"tkinter": mock_tk, "tkinter.filedialog": MagicMock(), "tkinter.ttk": MagicMock()}):
        # Re-import to pick up mocked tkinter
        if "gui" in sys.modules:
            del sys.modules["gui"]
        import gui  # noqa: F811
        assert hasattr(gui, "SoulXApp")
        assert hasattr(gui, "launch_gui")


def test_browse_audio_accepts_m4a_extension():
    mock_tk = _mock_tk()
    with patch.dict(sys.modules, {"tkinter": mock_tk, "tkinter.filedialog": MagicMock(), "tkinter.ttk": MagicMock()}):
        if "gui" in sys.modules:
            del sys.modules["gui"]
        import gui

        app = gui.SoulXApp.__new__(gui.SoulXApp)
        var = MagicMock()
        with patch.object(gui.filedialog, "askopenfilename", return_value="/tmp/input.m4a") as mock_open:
            gui.SoulXApp._browse_audio(app, var, "Select audio")

        kwargs = mock_open.call_args.kwargs
        assert "*.m4a" in kwargs["filetypes"][0][1]
        var.set.assert_called_once_with("/tmp/input.m4a")


def test_text_handler_emits_to_widget():
    """TextHandler appends formatted log messages to a Text widget."""
    mock_tk = _mock_tk()
    with patch.dict(sys.modules, {"tkinter": mock_tk, "tkinter.filedialog": MagicMock(), "tkinter.ttk": MagicMock()}):
        if "gui" in sys.modules:
            del sys.modules["gui"]
        import gui
        import logging

        mock_widget = MagicMock()
        handler = gui.TextHandler(mock_widget)
        handler.setFormatter(logging.Formatter("%(message)s"))

        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="", lineno=0,
            msg="hello", args=(), exc_info=None,
        )
        handler.emit(record)
        mock_widget.insert.assert_not_called()
        handler.flush_to_widget()
        mock_widget.insert.assert_called_once_with(mock_tk.END, "hello\n")


def test_main_gui_flag_calls_launch_gui(tmp_path):
    """--gui flag triggers launch_gui instead of CLI flow."""
    cfg = tmp_path / "settings.yaml"
    cfg.write_text(
        "app:\n  device_preference: cpu\n  allow_fallback: true\n  startup_probe: false\n"
        "inference:\n  segment_seconds: 12\n"
        "soulx:\n  command_template: echo {input} {output} {model} {device}\n"
        "  output_suffix: .wav\n  skip_output_check: true\n",
        encoding="utf-8",
    )

    with patch("sys.argv", ["main.py", "--config", str(cfg), "--gui"]):
        mock_launch = MagicMock()
        with patch.dict(sys.modules, {"gui": MagicMock(launch_gui=mock_launch)}):
            if "main" in sys.modules:
                del sys.modules["main"]
            import main
            result = main.main()
            assert result == 0
            mock_launch.assert_called_once_with(settings_path=str(cfg))


def _new_headless_app(gui_module, save_dir: Path, target_audio: str = "target.wav", mode: str = "svc"):
    app = gui_module.SoulXApp.__new__(gui_module.SoulXApp)
    app.save_dir_var = MagicMock(get=MagicMock(return_value=str(save_dir)))
    app.target_wav_var = MagicMock(get=MagicMock(return_value=target_audio))
    app.mode_var = MagicMock(get=MagicMock(return_value=mode))
    return app


def test_finalize_output_file_renames_generated(tmp_path):
    mock_tk = _mock_tk()
    with patch.dict(sys.modules, {"tkinter": mock_tk, "tkinter.filedialog": MagicMock(), "tkinter.ttk": MagicMock()}):
        if "gui" in sys.modules:
            del sys.modules["gui"]
        import gui

        save_dir = tmp_path / "output"
        save_dir.mkdir()
        generated = save_dir / "generated.wav"
        generated.write_bytes(b"wav")

        app = _new_headless_app(gui, save_dir)
        with patch.object(gui, "datetime") as mock_datetime:
            mock_datetime.now.return_value = datetime(2026, 4, 11, 13, 30, 45)
            output = gui.SoulXApp._finalize_output_file(
                app,
                save_dir=str(save_dir),
                target_wav="target.wav",
                mode="svc",
            )

        expected = save_dir / "target_svc_20260411_133045.wav"
        assert output == str(expected)
        assert expected.exists()
        assert not generated.exists()


def test_finalize_output_file_adds_index_when_name_conflicts(tmp_path):
    mock_tk = _mock_tk()
    with patch.dict(sys.modules, {"tkinter": mock_tk, "tkinter.filedialog": MagicMock(), "tkinter.ttk": MagicMock()}):
        if "gui" in sys.modules:
            del sys.modules["gui"]
        import gui

        save_dir = tmp_path / "output"
        save_dir.mkdir()
        (save_dir / "generated.wav").write_bytes(b"wav")
        (save_dir / "target_svc_20260411_133045.wav").write_bytes(b"existing")

        app = _new_headless_app(gui, save_dir)
        with patch.object(gui, "datetime") as mock_datetime:
            mock_datetime.now.return_value = datetime(2026, 4, 11, 13, 30, 45)
            output = gui.SoulXApp._finalize_output_file(
                app,
                save_dir=str(save_dir),
                target_wav="target.wav",
                mode="svc",
            )

        expected = save_dir / "target_svc_20260411_133045_1.wav"
        assert output == str(expected)
        assert expected.exists()


def test_finalize_output_file_returns_none_when_generated_missing(tmp_path):
    mock_tk = _mock_tk()
    with patch.dict(sys.modules, {"tkinter": mock_tk, "tkinter.filedialog": MagicMock(), "tkinter.ttk": MagicMock()}):
        if "gui" in sys.modules:
            del sys.modules["gui"]
        import gui

        save_dir = tmp_path / "output"
        save_dir.mkdir()
        app = _new_headless_app(gui, save_dir)

        output = gui.SoulXApp._finalize_output_file(
            app,
            save_dir=str(save_dir),
            target_wav="target.wav",
            mode="svc",
        )
        assert output is None


def test_build_svc_command_keeps_paths_with_spaces(tmp_path):
    mock_tk = _mock_tk()
    with patch.dict(sys.modules, {"tkinter": mock_tk, "tkinter.filedialog": MagicMock(), "tkinter.ttk": MagicMock()}):
        if "gui" in sys.modules:
            del sys.modules["gui"]
        import gui

        app = gui.SoulXApp.__new__(gui.SoulXApp)
        app.settings = {
            "soulx": {
                "svc_model": "model with space/model.pt",
                "svc_command_template": (
                    "python -m cli.inference_svc --device {device} --model_path {model} "
                    "--prompt_wav_path {prompt_wav} --target_wav_path {target_wav} "
                    "--save_dir {save_dir} --pitch_shift {pitch_shift}"
                ),
            }
        }
        app.prompt_wav_var = MagicMock(get=MagicMock(return_value="/tmp/prompt file.wav"))
        app.target_wav_var = MagicMock(get=MagicMock(return_value="/tmp/target file.wav"))
        app.save_dir_var = MagicMock(get=MagicMock(return_value="/tmp/output dir"))
        app.pitch_shift_var = MagicMock(get=MagicMock(return_value=0))

        cmd = gui.SoulXApp._build_svc_command(app, "cpu")
        assert "/tmp/prompt file.wav" in cmd
        assert "/tmp/target file.wav" in cmd
        assert "/tmp/output dir" in cmd
        assert "model with space/model.pt" in cmd


def test_on_run_checks_svs_metadata_file_exists(tmp_path):
    mock_tk = _mock_tk()
    with patch.dict(sys.modules, {"tkinter": mock_tk, "tkinter.filedialog": MagicMock(), "tkinter.ttk": MagicMock()}):
        if "gui" in sys.modules:
            del sys.modules["gui"]
        import gui

        prompt = tmp_path / "prompt.wav"
        target = tmp_path / "target.wav"
        prompt.write_bytes(b"dummy")
        target.write_bytes(b"dummy")

        app = gui.SoulXApp.__new__(gui.SoulXApp)
        app.prompt_wav_var = MagicMock(get=MagicMock(return_value=str(prompt)))
        app.target_wav_var = MagicMock(get=MagicMock(return_value=str(target)))
        app.save_dir_var = MagicMock(get=MagicMock(return_value=str(tmp_path / "output")))
        app.mode_var = MagicMock(get=MagicMock(return_value="svs"))
        app.prompt_meta_var = MagicMock(get=MagicMock(return_value=str(tmp_path / "missing_prompt.json")))
        app.target_meta_var = MagicMock(get=MagicMock(return_value=str(tmp_path / "missing_target.json")))
        app.logger = MagicMock()
        app.settings = {"soulx": {"work_dir": str(tmp_path)}}
        app._set_running = MagicMock()

        gui.SoulXApp._on_run(app)

        app.logger.error.assert_called_with("Prompt metadata not found: %s", str(tmp_path / "missing_prompt.json"))
        app._set_running.assert_not_called()


def test_run_inference_sets_error_when_output_is_missing(tmp_path):
    mock_tk = _mock_tk()
    with patch.dict(sys.modules, {"tkinter": mock_tk, "tkinter.filedialog": MagicMock(), "tkinter.ttk": MagicMock()}):
        if "gui" in sys.modules:
            del sys.modules["gui"]
        import gui

        app = gui.SoulXApp.__new__(gui.SoulXApp)
        app.logger = MagicMock()
        app.device_var = MagicMock(get=MagicMock(return_value="cpu"))
        app.mode_var = MagicMock(get=MagicMock(return_value="svc"))
        app.save_dir_var = MagicMock(get=MagicMock(return_value=str(tmp_path / "output")))
        app.settings = {
            "app": {"allow_fallback": True, "startup_probe": False},
            "soulx": {"work_dir": str(tmp_path)},
        }
        app._running = True
        app.root = MagicMock()
        app.status_var = MagicMock(set=MagicMock())
        app._set_running = MagicMock()
        app._enqueue_ui = MagicMock(side_effect=lambda callback, *args: callback(*args))
        app._build_svc_command_from_values = MagicMock(return_value=["/bin/echo", "ok"])
        app._finalize_output_file = MagicMock(return_value=None)
        app._convert_to_wav = MagicMock(side_effect=lambda p, d: p)
        app._run_preprocess = MagicMock(return_value=("vocal.wav", "vocal_f0.npy"))

        fake_process = MagicMock()
        fake_process.stdout = []
        fake_process.returncode = 0
        fake_process.wait = MagicMock()

        run_context = {
            "device_pref": "cpu",
            "mode": "svc",
            "work_dir": str(tmp_path),
            "save_dir": str(tmp_path / "output"),
            "prompt_wav": str(tmp_path / "prompt.wav"),
            "target_wav": str(tmp_path / "target.wav"),
            "prompt_meta": "",
            "target_meta": "",
            "pitch_shift": 0,
        }

        decision = MagicMock(device="cpu", used_fallback=False, reason="forced_cpu")
        with patch.object(gui, "resolve_device", return_value=decision):
            with patch.object(gui.subprocess, "Popen", return_value=fake_process):
                gui.SoulXApp._run_inference(app, run_context)

        assert any("generated.wav not found" in str(call) for call in app.logger.error.call_args_list)
        app.status_var.set.assert_any_call("Status: Error")


def test_run_inference_sets_error_when_generated_is_stale(tmp_path):
    mock_tk = _mock_tk()
    with patch.dict(sys.modules, {"tkinter": mock_tk, "tkinter.filedialog": MagicMock(), "tkinter.ttk": MagicMock()}):
        if "gui" in sys.modules:
            del sys.modules["gui"]
        import gui

        save_dir = tmp_path / "output"
        save_dir.mkdir()
        (save_dir / "generated.wav").write_bytes(b"old")

        app = gui.SoulXApp.__new__(gui.SoulXApp)
        app.logger = MagicMock()
        app.device_var = MagicMock(get=MagicMock(return_value="cpu"))
        app.mode_var = MagicMock(get=MagicMock(return_value="svc"))
        app.save_dir_var = MagicMock(get=MagicMock(return_value=str(save_dir)))
        app.settings = {
            "app": {"allow_fallback": True, "startup_probe": False},
            "soulx": {"work_dir": str(tmp_path)},
        }
        app._running = True
        app.root = MagicMock()
        app.status_var = MagicMock(set=MagicMock())
        app._set_running = MagicMock()
        app._enqueue_ui = MagicMock(side_effect=lambda callback, *args: callback(*args))
        app._build_svc_command_from_values = MagicMock(return_value=["/bin/echo", "ok"])
        app._finalize_output_file = MagicMock(return_value=None)
        app._convert_to_wav = MagicMock(side_effect=lambda p, d: p)
        app._run_preprocess = MagicMock(return_value=("vocal.wav", "vocal_f0.npy"))

        fake_process = MagicMock()
        fake_process.stdout = []
        fake_process.returncode = 0
        fake_process.wait = MagicMock()

        run_context = {
            "device_pref": "cpu",
            "mode": "svc",
            "work_dir": str(tmp_path),
            "save_dir": str(save_dir),
            "prompt_wav": str(tmp_path / "prompt.wav"),
            "target_wav": str(tmp_path / "target.wav"),
            "prompt_meta": "",
            "target_meta": "",
            "pitch_shift": 0,
        }

        decision = MagicMock(device="cpu", used_fallback=False, reason="forced_cpu")
        with patch.object(gui, "resolve_device", return_value=decision):
            with patch.object(gui.subprocess, "Popen", return_value=fake_process):
                gui.SoulXApp._run_inference(app, run_context)

        assert any("was not updated" in str(call) for call in app.logger.error.call_args_list)
        app._finalize_output_file.assert_not_called()
        app.status_var.set.assert_any_call("Status: Error")


def test_on_run_rejects_directory_as_audio_input(tmp_path):
    mock_tk = _mock_tk()
    with patch.dict(sys.modules, {"tkinter": mock_tk, "tkinter.filedialog": MagicMock(), "tkinter.ttk": MagicMock()}):
        if "gui" in sys.modules:
            del sys.modules["gui"]
        import gui

        prompt_dir = tmp_path / "prompt_dir"
        prompt_dir.mkdir()
        target_wav = tmp_path / "target.wav"
        target_wav.write_bytes(b"dummy")

        app = gui.SoulXApp.__new__(gui.SoulXApp)
        app.prompt_wav_var = MagicMock(get=MagicMock(return_value=str(prompt_dir)))
        app.target_wav_var = MagicMock(get=MagicMock(return_value=str(target_wav)))
        app.save_dir_var = MagicMock(get=MagicMock(return_value=str(tmp_path / "output")))
        app.mode_var = MagicMock(get=MagicMock(return_value="svc"))
        app.logger = MagicMock()
        app.settings = {"soulx": {"work_dir": str(tmp_path)}}
        app._set_running = MagicMock()

        gui.SoulXApp._on_run(app)

        app.logger.error.assert_called_with("Prompt audio not found: %s", str(prompt_dir))
        app._set_running.assert_not_called()


def test_convert_to_wav_uses_unique_temp_names_for_same_stem(tmp_path):
    mock_tk = _mock_tk()
    with patch.dict(sys.modules, {"tkinter": mock_tk, "tkinter.filedialog": MagicMock(), "tkinter.ttk": MagicMock()}):
        if "gui" in sys.modules:
            del sys.modules["gui"]
        import gui

        app = gui.SoulXApp.__new__(gui.SoulXApp)
        app.logger = MagicMock()

        fake_run = MagicMock(return_value=MagicMock(returncode=0, stderr=""))
        with patch.object(gui.shutil, "which", return_value="/usr/bin/ffmpeg"):
            with patch.object(gui.subprocess, "run", fake_run):
                out1 = gui.SoulXApp._convert_to_wav(app, "/tmp/song.mp3", str(tmp_path))
                out2 = gui.SoulXApp._convert_to_wav(app, "/var/tmp/song.mp3", str(tmp_path))

        assert out1 != out2
        assert Path(out1).name.startswith("song_")
        assert Path(out2).name.startswith("song_")


def test_run_preprocess_uses_configured_conda_env(tmp_path):
    mock_tk = _mock_tk()
    with patch.dict(sys.modules, {"tkinter": mock_tk, "tkinter.filedialog": MagicMock(), "tkinter.ttk": MagicMock()}):
        if "gui" in sys.modules:
            del sys.modules["gui"]
        import gui

        pre_dir = tmp_path / "pre"
        pre_dir.mkdir(parents=True)
        (pre_dir / "vocal.wav").write_bytes(b"wav")
        (pre_dir / "vocal_f0.npy").write_bytes(b"npy")

        app = gui.SoulXApp.__new__(gui.SoulXApp)
        app.logger = MagicMock()
        app.settings = {"soulx": {"conda_bin": "/opt/homebrew/bin/conda", "conda_env": "customenv"}}
        app._running = True

        fake_proc = MagicMock()
        fake_proc.stdout = []
        fake_proc.returncode = 0
        fake_proc.wait = MagicMock()

        with patch.object(gui.shutil, "which", return_value="/opt/homebrew/bin/conda"):
            with patch.object(gui.subprocess, "Popen", return_value=fake_proc) as mock_popen:
                gui.SoulXApp._run_preprocess(
                    app,
                    audio_wav="/tmp/in.wav",
                    pre_dir=str(pre_dir),
                    device="cpu",
                    work_dir="/tmp",
                    label="prompt",
                    vocal_sep=False,
                )

        cmd = mock_popen.call_args[0][0]
        assert cmd[0] == "/opt/homebrew/bin/conda"
        assert cmd[1:4] == ["run", "-n", "customenv"]


def test_mix_with_accompaniment_uses_stereo_pipeline():
    mock_tk = _mock_tk()
    with patch.dict(sys.modules, {"tkinter": mock_tk, "tkinter.filedialog": MagicMock(), "tkinter.ttk": MagicMock()}):
        if "gui" in sys.modules:
            del sys.modules["gui"]
        import gui

        app = gui.SoulXApp.__new__(gui.SoulXApp)

        with patch.object(gui.shutil, "which", return_value="/usr/bin/ffmpeg"):
            with patch.object(gui.subprocess, "run", return_value=MagicMock(returncode=0, stderr="")) as mock_run:
                gui.SoulXApp._mix_with_accompaniment(
                    app,
                    vocal_wav="/tmp/vocal.wav",
                    acc_wav="/tmp/acc.wav",
                    output_wav="/tmp/out.wav",
                )

        cmd = mock_run.call_args[0][0]
        filter_value = cmd[cmd.index("-filter_complex") + 1]
        assert "pan=stereo" in filter_value
        assert "amix=inputs=2" in filter_value
        assert "alimiter" in filter_value


def test_suppress_target_vocal_uses_sidechaincompress():
    mock_tk = _mock_tk()
    with patch.dict(sys.modules, {"tkinter": mock_tk, "tkinter.filedialog": MagicMock(), "tkinter.ttk": MagicMock()}):
        if "gui" in sys.modules:
            del sys.modules["gui"]
        import gui

        app = gui.SoulXApp.__new__(gui.SoulXApp)

        with patch.object(gui.shutil, "which", return_value="/usr/bin/ffmpeg"):
            with patch.object(gui.subprocess, "run", return_value=MagicMock(returncode=0, stderr="")) as mock_run:
                gui.SoulXApp._suppress_target_vocal_from_accompaniment(
                    app,
                    acc_wav="/tmp/acc.wav",
                    target_vocal_wav="/tmp/target_vocal.wav",
                    output_wav="/tmp/acc_suppressed.wav",
                )

        cmd = mock_run.call_args[0][0]
        filter_value = cmd[cmd.index("-filter_complex") + 1]
        assert "sidechaincompress" in filter_value
        assert "threshold=0.003" in filter_value


def test_run_inference_strict_removal_errors_when_acc_missing(tmp_path):
    mock_tk = _mock_tk()
    with patch.dict(sys.modules, {"tkinter": mock_tk, "tkinter.filedialog": MagicMock(), "tkinter.ttk": MagicMock()}):
        if "gui" in sys.modules:
            del sys.modules["gui"]
        import gui

        save_dir = tmp_path / "output"
        save_dir.mkdir()

        app = gui.SoulXApp.__new__(gui.SoulXApp)
        app.logger = MagicMock()
        app.device_var = MagicMock(get=MagicMock(return_value="cpu"))
        app.mode_var = MagicMock(get=MagicMock(return_value="svc"))
        app.save_dir_var = MagicMock(get=MagicMock(return_value=str(save_dir)))
        app.settings = {
            "app": {"allow_fallback": True, "startup_probe": False},
            "soulx": {"work_dir": str(tmp_path), "strict_target_vocal_removal": True},
        }
        app._running = True
        app.root = MagicMock()
        app.status_var = MagicMock(set=MagicMock())
        app._set_running = MagicMock()
        app._enqueue_ui = MagicMock(side_effect=lambda callback, *args: callback(*args))
        app._build_svc_command_from_values = MagicMock(return_value=["/bin/echo", "ok"])
        app._convert_to_wav = MagicMock(side_effect=lambda p, d: p)
        app._run_preprocess = MagicMock(
            side_effect=[
                (str(tmp_path / "prompt_vocal.wav"), str(tmp_path / "prompt_f0.npy")),
                (str(tmp_path / "target_vocal.wav"), str(tmp_path / "target_f0.npy")),
            ]
        )

        fake_process = MagicMock()
        fake_process.stdout = []
        fake_process.returncode = 0

        def _wait_and_write_generated():
            (save_dir / "generated.wav").write_bytes(b"wav")
            return 0

        fake_process.wait = MagicMock(side_effect=_wait_and_write_generated)

        run_context = {
            "device_pref": "cpu",
            "mode": "svc",
            "work_dir": str(tmp_path),
            "save_dir": str(save_dir),
            "prompt_wav": str(tmp_path / "prompt.wav"),
            "target_wav": str(tmp_path / "target.wav"),
            "prompt_meta": "",
            "target_meta": "",
            "pitch_shift": 0,
            "target_vocal_sep": True,
        }

        decision = MagicMock(device="cpu", used_fallback=False, reason="forced_cpu")
        with patch.object(gui, "resolve_device", return_value=decision):
            with patch.object(gui.subprocess, "Popen", return_value=fake_process):
                gui.SoulXApp._run_inference(app, run_context)

        assert any(
            "Accompaniment not found; cannot remove target vocal reliably." in str(call)
            for call in app.logger.error.call_args_list
        )
        app.status_var.set.assert_any_call("Status: Error")
