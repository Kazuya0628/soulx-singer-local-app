from __future__ import annotations

from datetime import datetime
import logging
import queue
import shlex
import shutil
import subprocess
import tempfile
import threading
import uuid
import tkinter as tk
from tkinter import filedialog, ttk
from pathlib import Path
from typing import Any

_WAV_EXTENSIONS = {".wav"}
_CONVERTIBLE_EXTENSIONS = {".m4a", ".mp3", ".flac", ".ogg", ".aac", ".wma"}

from config_loader import load_device_config, load_settings
from device_selector import DeviceConfig, resolve_device


class TextHandler(logging.Handler):
    """Logging handler that writes to a tkinter Text widget."""

    def __init__(self, text_widget: tk.Text) -> None:
        super().__init__()
        self.text_widget = text_widget
        self._pending: "queue.Queue[str]" = queue.Queue()

    def emit(self, record: logging.LogRecord) -> None:
        msg = self.format(record) + "\n"
        self._pending.put(msg)

    def flush_to_widget(self) -> None:
        while True:
            try:
                msg = self._pending.get_nowait()
            except queue.Empty:
                break
            self._append(msg)

    def _append(self, msg: str) -> None:
        self.text_widget.configure(state=tk.NORMAL)
        self.text_widget.insert(tk.END, msg)
        self.text_widget.see(tk.END)
        self.text_widget.configure(state=tk.DISABLED)


class SoulXApp:
    def __init__(self, settings_path: str = "config/settings.yaml") -> None:
        self.settings = load_settings(settings_path)
        self.settings_path = settings_path
        self._running = False
        self._process: subprocess.Popen | None = None
        self._thread: threading.Thread | None = None
        self._ui_queue: "queue.Queue[tuple[Any, tuple[Any, ...]]]" = queue.Queue()

        self.root = tk.Tk()
        self.root.title("SoulX-Singer Local")
        self.root.minsize(560, 560)
        self._build_ui()
        self._setup_logging()
        self._load_defaults()
        self._on_mode_change()
        self._start_ui_pumps()

    # ── UI construction ──────────────────────────────────────────

    def _build_ui(self) -> None:
        pad = {"padx": 8, "pady": 4}

        # Mode selection
        mode_frame = ttk.LabelFrame(self.root, text="Mode")
        mode_frame.pack(fill=tk.X, **pad)

        self.mode_var = tk.StringVar(value="svc")
        ttk.Radiobutton(mode_frame, text="SVC (Voice Conversion)", variable=self.mode_var, value="svc", command=self._on_mode_change).pack(side=tk.LEFT, padx=8, pady=4)
        ttk.Radiobutton(mode_frame, text="SVS (Voice Synthesis)", variable=self.mode_var, value="svs", command=self._on_mode_change).pack(side=tk.LEFT, padx=8, pady=4)

        # File selection frame
        file_frame = ttk.LabelFrame(self.root, text="Files")
        file_frame.pack(fill=tk.X, **pad)

        self.prompt_wav_var = tk.StringVar()
        self.target_wav_var = tk.StringVar()
        self.save_dir_var = tk.StringVar()

        self._file_row(file_frame, "Prompt audio:", self.prompt_wav_var, self._browse_prompt_wav, 0)
        self._file_row(file_frame, "Target audio:", self.target_wav_var, self._browse_target_wav, 1)
        self._file_row(file_frame, "Output dir:", self.save_dir_var, self._browse_save_dir, 2)

        # SVS-specific fields (hidden by default)
        self.svs_frame = ttk.LabelFrame(self.root, text="SVS Options")
        self.prompt_meta_var = tk.StringVar()
        self.target_meta_var = tk.StringVar()
        self._file_row(self.svs_frame, "Prompt metadata:", self.prompt_meta_var, self._browse_prompt_meta, 0)
        self._file_row(self.svs_frame, "Target metadata:", self.target_meta_var, self._browse_target_meta, 1)

        # Settings frame
        settings_frame = ttk.LabelFrame(self.root, text="Settings")
        settings_frame.pack(fill=tk.X, **pad)

        ttk.Label(settings_frame, text="Device:").grid(row=0, column=0, sticky=tk.W, padx=4, pady=2)
        self.device_var = tk.StringVar(value="auto")
        ttk.Combobox(
            settings_frame, textvariable=self.device_var,
            values=["auto", "mps", "cpu"], state="readonly", width=12,
        ).grid(row=0, column=1, sticky=tk.W, padx=4, pady=2)

        ttk.Label(settings_frame, text="Pitch shift:").grid(row=1, column=0, sticky=tk.W, padx=4, pady=2)
        self.pitch_shift_var = tk.IntVar(value=0)
        ttk.Spinbox(
            settings_frame, textvariable=self.pitch_shift_var,
            from_=-12, to=12, width=6,
        ).grid(row=1, column=1, sticky=tk.W, padx=4, pady=2)

        self.target_vocal_sep_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            settings_frame,
            text="Target vocal separation (uncheck if target is already vocal-only)",
            variable=self.target_vocal_sep_var,
        ).grid(row=2, column=0, columnspan=2, sticky=tk.W, padx=4, pady=2)

        self.prompt_vocal_sep_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            settings_frame,
            text="Prompt vocal separation (enable if prompt contains BGM)",
            variable=self.prompt_vocal_sep_var,
        ).grid(row=3, column=0, columnspan=2, sticky=tk.W, padx=4, pady=2)

        # Control frame
        ctrl_frame = ttk.Frame(self.root)
        ctrl_frame.pack(fill=tk.X, **pad)

        self.run_btn = ttk.Button(ctrl_frame, text="\u25b6 Run", command=self._on_run)
        self.run_btn.pack(side=tk.LEFT, padx=4)

        self.stop_btn = ttk.Button(ctrl_frame, text="\u25a0 Stop", command=self._on_stop, state=tk.DISABLED)
        self.stop_btn.pack(side=tk.LEFT, padx=4)

        self.status_var = tk.StringVar(value="Status: Idle")
        ttk.Label(ctrl_frame, textvariable=self.status_var).pack(side=tk.LEFT, padx=12)

        # Log frame
        log_frame = ttk.LabelFrame(self.root, text="Log")
        log_frame.pack(fill=tk.BOTH, expand=True, **pad)

        self.log_text = tk.Text(log_frame, height=12, state=tk.DISABLED, wrap=tk.WORD)
        scrollbar = ttk.Scrollbar(log_frame, orient=tk.VERTICAL, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=scrollbar.set)
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    def _file_row(
        self, parent: ttk.Widget, label: str,
        var: tk.StringVar, command: Any, row: int,
    ) -> None:
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky=tk.W, padx=4, pady=2)
        ttk.Entry(parent, textvariable=var, width=40).grid(row=row, column=1, sticky=tk.EW, padx=4, pady=2)
        ttk.Button(parent, text="Browse", command=command).grid(row=row, column=2, padx=4, pady=2)
        parent.columnconfigure(1, weight=1)

    def _on_mode_change(self) -> None:
        soulx_cfg = self.settings.get("soulx", {})
        if self.mode_var.get() == "svs":
            self.svs_frame.pack(fill=tk.X, padx=8, pady=4, after=self.root.winfo_children()[1])
        else:
            self.svs_frame.pack_forget()

    # ── Browse dialogs ───────────────────────────────────────────

    def _browse_audio(self, var: tk.StringVar, title: str) -> None:
        path = filedialog.askopenfilename(
            title=title,
            filetypes=[("Audio files", "*.wav *.mp3 *.m4a *.flac *.ogg"), ("All files", "*.*")],
        )
        if path:
            var.set(path)

    def _browse_prompt_wav(self) -> None:
        self._browse_audio(self.prompt_wav_var, "Select prompt audio (reference voice)")

    def _browse_target_wav(self) -> None:
        self._browse_audio(self.target_wav_var, "Select target audio (music to convert)")

    def _browse_save_dir(self) -> None:
        path = filedialog.askdirectory(title="Select output directory")
        if path:
            self.save_dir_var.set(path)

    def _browse_json(self, var: tk.StringVar, title: str) -> None:
        path = filedialog.askopenfilename(
            title=title,
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
        )
        if path:
            var.set(path)

    def _browse_prompt_meta(self) -> None:
        self._browse_json(self.prompt_meta_var, "Select prompt metadata JSON")

    def _browse_target_meta(self) -> None:
        self._browse_json(self.target_meta_var, "Select target metadata JSON")

    # ── Logging setup ────────────────────────────────────────────

    def _setup_logging(self) -> None:
        self._log_handler = TextHandler(self.log_text)
        self._log_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S"))
        logger = logging.getLogger("soulx-local")
        logger.addHandler(self._log_handler)
        logger.setLevel(logging.INFO)
        self.logger = logger

    def _start_ui_pumps(self) -> None:
        self.root.after(50, self._process_ui_queue)
        self.root.after(50, self._flush_log_queue)

    def _enqueue_ui(self, callback: Any, *args: Any) -> None:
        self._ui_queue.put((callback, args))

    def _process_ui_queue(self) -> None:
        try:
            while True:
                try:
                    callback, args = self._ui_queue.get_nowait()
                except queue.Empty:
                    break

                try:
                    callback(*args)
                except tk.TclError:
                    continue
                except Exception:
                    self.logger.exception("UI callback failed")
                    continue
        except tk.TclError:
            return
        finally:
            try:
                self.root.after(50, self._process_ui_queue)
            except tk.TclError:
                return

    def _flush_log_queue(self) -> None:
        try:
            self._log_handler.flush_to_widget()
        except tk.TclError:
            return
        finally:
            try:
                self.root.after(50, self._flush_log_queue)
            except tk.TclError:
                return

    # ── Load defaults from settings.yaml ─────────────────────────

    def _load_defaults(self) -> None:
        app = self.settings.get("app", {})
        soulx_cfg = self.settings.get("soulx", {})

        self.device_var.set(str(app.get("device_preference", "auto")).lower())
        self.pitch_shift_var.set(int(soulx_cfg.get("pitch_shift", 0)))
        self.mode_var.set(str(soulx_cfg.get("mode", "svc")))

        work_dir = soulx_cfg.get("work_dir")
        if work_dir:
            self.save_dir_var.set(str(Path(work_dir) / "output"))

    # ── Build command ────────────────────────────────────────────

    def _build_svc_command(self, device: str) -> list[str]:
        soulx_cfg = self.settings.get("soulx", {})
        template = soulx_cfg.get("svc_command_template", "")
        model = soulx_cfg.get("svc_model", "pretrained_models/SoulX-Singer/model-svc.pt")

        prompt_wav = self.prompt_wav_var.get().strip()
        target_wav = self.target_wav_var.get().strip()
        save_dir = self.save_dir_var.get().strip()
        pitch_shift = self.pitch_shift_var.get()

        return self._build_svc_command_from_values(
            template=template,
            model=model,
            device=device,
            prompt_wav=prompt_wav,
            target_wav=target_wav,
            save_dir=save_dir,
            pitch_shift=pitch_shift,
        )

    def _build_svc_command_from_values(
        self,
        *,
        template: str,
        model: str,
        device: str,
        prompt_wav: str,
        target_wav: str,
        save_dir: str,
        pitch_shift: int,
        prompt_f0: str = "",
        target_f0: str = "",
    ) -> list[str]:

        rendered = template.format(
            device=shlex.quote(device),
            model=shlex.quote(model),
            config=shlex.quote("soulxsinger/config/soulxsinger.yaml"),
            prompt_wav=shlex.quote(prompt_wav),
            target_wav=shlex.quote(target_wav),
            save_dir=shlex.quote(save_dir),
            pitch_shift=pitch_shift,
        )
        parts = shlex.split(rendered)
        if prompt_f0:
            parts.extend(["--prompt_f0_path", prompt_f0])
        if target_f0:
            parts.extend(["--target_f0_path", target_f0])
        return parts

    def _build_svs_command(self, device: str) -> list[str]:
        soulx_cfg = self.settings.get("soulx", {})
        template = soulx_cfg.get("svs_command_template", "")
        model = soulx_cfg.get("svs_model", "pretrained_models/SoulX-Singer/model.pt")

        prompt_wav = self.prompt_wav_var.get().strip()
        prompt_meta = self.prompt_meta_var.get().strip()
        target_meta = self.target_meta_var.get().strip()
        save_dir = self.save_dir_var.get().strip()
        pitch_shift = self.pitch_shift_var.get()

        return self._build_svs_command_from_values(
            template=template,
            model=model,
            device=device,
            prompt_wav=prompt_wav,
            prompt_meta=prompt_meta,
            target_meta=target_meta,
            save_dir=save_dir,
            pitch_shift=pitch_shift,
        )

    def _build_svs_command_from_values(
        self,
        *,
        template: str,
        model: str,
        device: str,
        prompt_wav: str,
        prompt_meta: str,
        target_meta: str,
        save_dir: str,
        pitch_shift: int,
    ) -> list[str]:

        rendered = template.format(
            device=shlex.quote(device),
            model=shlex.quote(model),
            config=shlex.quote("soulxsinger/config/soulxsinger.yaml"),
            prompt_wav=shlex.quote(prompt_wav),
            prompt_meta=shlex.quote(prompt_meta),
            target_meta=shlex.quote(target_meta),
            save_dir=shlex.quote(save_dir),
            pitch_shift=pitch_shift,
        )
        return shlex.split(rendered)

    def _safe_stem(self, path_value: str) -> str:
        stem = Path(path_value).stem.strip() or "output"
        return "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in stem)

    def _next_available_output_path(self, save_dir: Path, base_name: str) -> Path:
        candidate = save_dir / f"{base_name}.wav"
        if not candidate.exists():
            return candidate

        index = 1
        while True:
            candidate = save_dir / f"{base_name}_{index}.wav"
            if not candidate.exists():
                return candidate
            index += 1

    def _finalize_output_file(
        self,
        save_dir: str,
        target_wav: str,
        mode: str,
        source_filename: str = "generated.wav",
    ) -> str | None:
        save_dir_path = Path(save_dir)
        source_path = save_dir_path / source_filename
        if not source_path.exists():
            return None

        target_stem = self._safe_stem(target_wav)
        mode_name = mode.strip() or "svc"
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        base_name = f"{target_stem}_{mode_name}_{timestamp}"
        final_path = self._next_available_output_path(save_dir_path, base_name)
        source_path.replace(final_path)
        return str(final_path)

    def _mix_with_accompaniment(self, vocal_wav: str, acc_wav: str, output_wav: str) -> None:
        ffmpeg = shutil.which("ffmpeg")
        if ffmpeg is None:
            raise RuntimeError("ffmpeg not found. Install with: brew install ffmpeg")

        cmd = [
            ffmpeg,
            "-y",
            "-i",
            vocal_wav,
            "-i",
            acc_wav,
            "-filter_complex",
            "[0:a]aresample=44100,pan=stereo|c0=c0|c1=c0,volume=1.0[v];"
            "[1:a]aresample=44100,aformat=channel_layouts=stereo,volume=0.9[a];"
            "[v][a]amix=inputs=2:normalize=0,alimiter=limit=0.98[out]",
            "-map",
            "[out]",
            output_wav,
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if proc.returncode != 0:
            raise RuntimeError(f"ffmpeg mix failed: {proc.stderr.strip()}")

    def _suppress_target_vocal_from_accompaniment(
        self,
        acc_wav: str,
        target_vocal_wav: str,
        output_wav: str,
    ) -> None:
        ffmpeg = shutil.which("ffmpeg")
        if ffmpeg is None:
            raise RuntimeError("ffmpeg not found. Install with: brew install ffmpeg")

        cmd = [
            ffmpeg,
            "-y",
            "-i",
            acc_wav,
            "-i",
            target_vocal_wav,
            "-filter_complex",
            "[0:a]aresample=44100,aformat=channel_layouts=stereo,highpass=f=120,lowpass=f=11000[acc];"
            "[1:a]aresample=44100,aformat=channel_layouts=stereo,highpass=f=120,lowpass=f=6000,volume=2.0[key];"
            "[acc][key]sidechaincompress=threshold=0.003:ratio=20:attack=5:release=250:makeup=1[duck]",
            "-map",
            "[duck]",
            output_wav,
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if proc.returncode != 0:
            raise RuntimeError(f"ffmpeg vocal suppression failed: {proc.stderr.strip()}")

    # ── Audio pre-processing ────────────────────────────────────

    def _run_preprocess(
        self, audio_wav: str, pre_dir: str, device: str, work_dir: str, label: str,
        vocal_sep: bool = False,
    ) -> tuple[str, str]:
        """Run F0 extraction pipeline. Returns (vocal_wav_path, vocal_f0_path)."""
        Path(pre_dir).mkdir(parents=True, exist_ok=True)

        conda_bin = self.settings.get("soulx", {}).get(
            "conda_bin", "/opt/homebrew/bin/conda"
        )
        conda_env = str(self.settings.get("soulx", {}).get("conda_env", "soulxsinger"))
        if not shutil.which(conda_bin):
            conda_bin = shutil.which("conda") or conda_bin

        cmd = [
            conda_bin, "run", "-n", conda_env,
            "python", "-m", "preprocess.pipeline",
            "--audio_path", audio_wav,
            "--save_dir", pre_dir,
            "--language", "Japanese",
            "--device", device,
            "--vocal_sep", str(vocal_sep),
            "--midi_transcribe", "False",
        ]

        self.logger.info("[Preprocess %s] %s", label, " ".join(cmd))
        proc = subprocess.Popen(
            cmd, cwd=work_dir,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
        )
        self._process = proc
        try:
            for line in proc.stdout:
                self.logger.info(line.rstrip())
                if not self._running:
                    proc.kill()
                    raise RuntimeError("Cancelled during preprocessing")
            proc.wait()
            if proc.returncode != 0:
                raise RuntimeError(f"Preprocess ({label}) failed with exit code {proc.returncode}")
        finally:
            if self._process is proc:
                self._process = None

        vocal_wav = str(Path(pre_dir) / "vocal.wav")
        vocal_f0 = str(Path(pre_dir) / "vocal_f0.npy")
        if not Path(vocal_wav).exists() or not Path(vocal_f0).exists():
            raise RuntimeError(f"Preprocess ({label}) did not produce vocal.wav / vocal_f0.npy")

        return vocal_wav, vocal_f0

    def _convert_to_wav(self, audio_path: str, tmp_dir: str) -> str:
        """Convert non-wav audio to wav using ffmpeg. Returns path to wav file."""
        src = Path(audio_path)
        if src.suffix.lower() in _WAV_EXTENSIONS:
            return audio_path

        if src.suffix.lower() not in _CONVERTIBLE_EXTENSIONS:
            self.logger.warning("Unknown audio format %s, passing as-is", src.suffix)
            return audio_path

        ffmpeg = shutil.which("ffmpeg")
        if ffmpeg is None:
            raise RuntimeError(
                "ffmpeg not found. Install with: brew install ffmpeg"
            )

        unique_name = f"{src.stem}_{uuid.uuid4().hex[:8]}.wav"
        dest = Path(tmp_dir) / unique_name
        self.logger.info("Converting %s → wav ...", src.name)
        proc = subprocess.run(
            [ffmpeg, "-y", "-i", str(src), "-ar", "44100", "-ac", "1", str(dest)],
            capture_output=True, text=True, check=False,
        )
        if proc.returncode != 0:
            raise RuntimeError(f"ffmpeg conversion failed: {proc.stderr.strip()}")

        self.logger.info("Converted: %s", dest.name)
        return str(dest)

    # ── Run / Stop ───────────────────────────────────────────────

    def _on_run(self) -> None:
        prompt = self.prompt_wav_var.get().strip()
        target = self.target_wav_var.get().strip()
        save_dir = self.save_dir_var.get().strip()

        if not prompt:
            self.logger.error("No prompt audio selected.")
            return
        if not Path(prompt).is_file():
            self.logger.error("Prompt audio not found: %s", prompt)
            return
        if not target:
            self.logger.error("No target audio selected.")
            return
        if not Path(target).is_file():
            self.logger.error("Target audio not found: %s", target)
            return
        if not save_dir:
            self.logger.error("No output directory selected.")
            return

        mode = self.mode_var.get().strip()
        prompt_meta = ""
        target_meta = ""
        if mode == "svs":
            prompt_meta = self.prompt_meta_var.get().strip()
            target_meta = self.target_meta_var.get().strip()
            if not prompt_meta:
                self.logger.error("SVS mode requires prompt metadata.")
                return
            if not target_meta:
                self.logger.error("SVS mode requires target metadata.")
                return
            if not Path(prompt_meta).is_file():
                self.logger.error("Prompt metadata not found: %s", prompt_meta)
                return
            if not Path(target_meta).is_file():
                self.logger.error("Target metadata not found: %s", target_meta)
                return

        work_dir = self.settings.get("soulx", {}).get("work_dir")
        if not work_dir or not Path(work_dir).is_dir():
            self.logger.error(
                "SoulX-Singer work_dir not configured or not found. "
                "Run scripts/setup_soulx.sh first, then set work_dir in settings.yaml."
            )
            return

        run_context = {
            "device_pref": self.device_var.get().strip(),
            "mode": mode,
            "work_dir": str(work_dir),
            "save_dir": save_dir,
            "prompt_wav": prompt,
            "target_wav": target,
            "prompt_meta": prompt_meta,
            "target_meta": target_meta,
            "pitch_shift": int(self.pitch_shift_var.get()),
            "prompt_vocal_sep": bool(self.prompt_vocal_sep_var.get()),
            "target_vocal_sep": bool(self.target_vocal_sep_var.get()),
        }

        self._set_running(True)
        self._thread = threading.Thread(target=self._run_inference, args=(run_context,), daemon=True)
        self._thread.start()

    def _on_stop(self) -> None:
        self._running = False
        if self._process and self._process.poll() is None:
            self._process.terminate()
            self.logger.info("Process terminated.")
        self._set_running(False)

    def _set_running(self, running: bool) -> None:
        self._running = running
        if running:
            self.run_btn.configure(state=tk.DISABLED)
            self.stop_btn.configure(state=tk.NORMAL)
            self.status_var.set("Status: Running...")
        else:
            self.run_btn.configure(state=tk.NORMAL)
            self.stop_btn.configure(state=tk.DISABLED)
            self.status_var.set("Status: Idle")

    def _run_inference(self, run_context: dict[str, Any]) -> None:
        tmp_dir = tempfile.mkdtemp(prefix="soulx_conv_")
        try:
            # Convert non-wav audio files to wav
            mode = str(run_context["mode"])
            self.logger.info("Checking audio formats...")
            prompt_wav = self._convert_to_wav(str(run_context["prompt_wav"]), tmp_dir)
            target_wav = str(run_context["target_wav"])
            if mode == "svc":
                target_wav = self._convert_to_wav(target_wav, tmp_dir)

            self.logger.info("Resolving device...")
            device_pref = str(run_context["device_pref"])
            dev_cfg = DeviceConfig(
                device_preference=device_pref,
                allow_fallback=bool(self.settings.get("app", {}).get("allow_fallback", True)),
                startup_probe=bool(self.settings.get("app", {}).get("startup_probe", True)),
            )
            decision = resolve_device(dev_cfg)
            self.logger.info(
                "Device: %s (fallback=%s, reason=%s)",
                decision.device, decision.used_fallback, decision.reason,
            )

            if not self._running:
                return

            save_dir = str(run_context["save_dir"])
            work_dir = str(run_context["work_dir"])

            soulx_cfg = self.settings.get("soulx", {})
            strict_target_vocal_removal = bool(soulx_cfg.get("strict_target_vocal_removal", True))
            if mode == "svc":
                # Run F0 extraction preprocessing
                preprocess_dir = str(Path(save_dir) / "preprocess")
                prompt_vocal_sep = bool(run_context.get("prompt_vocal_sep", False))
                self.logger.info(
                    "[1/3] Preprocessing prompt audio (F0 extraction, vocal_sep=%s)...",
                    prompt_vocal_sep,
                )
                prompt_vocal, prompt_f0 = self._run_preprocess(
                    audio_wav=prompt_wav,
                    pre_dir=str(Path(preprocess_dir) / "prompt"),
                    device=decision.device,
                    work_dir=work_dir,
                    label="prompt",
                    vocal_sep=prompt_vocal_sep,
                )
                if not self._running:
                    return

                target_vocal_sep = bool(run_context.get("target_vocal_sep", True))
                self.logger.info(
                    "[2/3] Preprocessing target audio (F0 extraction, vocal_sep=%s)...",
                    target_vocal_sep,
                )
                target_vocal, target_f0 = self._run_preprocess(
                    audio_wav=target_wav,
                    pre_dir=str(Path(preprocess_dir) / "target"),
                    device=decision.device,
                    work_dir=work_dir,
                    label="target",
                    vocal_sep=target_vocal_sep,
                )
                if not self._running:
                    return

                self.logger.info("[3/3] Running SVC inference...")
                cmd = self._build_svc_command_from_values(
                    template=soulx_cfg.get("svc_command_template", ""),
                    model=soulx_cfg.get("svc_model", "pretrained_models/SoulX-Singer/model-svc.pt"),
                    device=decision.device,
                    prompt_wav=prompt_vocal,
                    target_wav=target_vocal,
                    save_dir=save_dir,
                    pitch_shift=int(run_context["pitch_shift"]),
                    prompt_f0=prompt_f0,
                    target_f0=target_f0,
                )
            else:
                cmd = self._build_svs_command_from_values(
                    template=soulx_cfg.get("svs_command_template", ""),
                    model=soulx_cfg.get("svs_model", "pretrained_models/SoulX-Singer/model.pt"),
                    device=decision.device,
                    prompt_wav=prompt_wav,
                    prompt_meta=str(run_context["prompt_meta"]),
                    target_meta=str(run_context["target_meta"]),
                    save_dir=save_dir,
                    pitch_shift=int(run_context["pitch_shift"]),
                )

            Path(save_dir).mkdir(parents=True, exist_ok=True)
            generated_path = Path(save_dir) / "generated.wav"
            pre_generated_stat = generated_path.stat() if generated_path.exists() else None

            self.logger.info("Running: %s", " ".join(cmd))
            self._process = subprocess.Popen(
                cmd,
                cwd=work_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )

            for line in self._process.stdout:
                self.logger.info(line.rstrip())
                if not self._running:
                    break

            self._process.wait()
            if self._process.returncode == 0:
                generated_path = Path(save_dir) / "generated.wav"
                if not generated_path.exists():
                    self.logger.error("Inference finished but generated.wav not found: %s", generated_path)
                    self._enqueue_ui(self.status_var.set, "Status: Error")
                    return

                if pre_generated_stat is not None:
                    post_generated_stat = generated_path.stat()
                    if (
                        post_generated_stat.st_mtime_ns == pre_generated_stat.st_mtime_ns
                        and post_generated_stat.st_size == pre_generated_stat.st_size
                    ):
                        self.logger.error("Inference finished but generated.wav was not updated: %s", generated_path)
                        self._enqueue_ui(self.status_var.set, "Status: Error")
                        return

                output_source_path = generated_path
                if mode == "svc" and bool(run_context.get("target_vocal_sep", True)):
                    acc_path = Path(save_dir) / "preprocess" / "target" / "acc.wav"
                    if acc_path.exists():
                        mixed_path = Path(save_dir) / "generated_mix.wav"
                        target_vocal_path = Path(target_vocal)
                        acc_for_mix = acc_path
                        try:
                            if target_vocal_path.exists():
                                self.logger.info("Suppressing residual target vocal from accompaniment...")
                                suppressed_acc_path = Path(save_dir) / "generated_acc_suppressed.wav"
                                self._suppress_target_vocal_from_accompaniment(
                                    acc_wav=str(acc_path),
                                    target_vocal_wav=str(target_vocal_path),
                                    output_wav=str(suppressed_acc_path),
                                )
                                acc_for_mix = suppressed_acc_path

                            self.logger.info("Mixing generated vocal with accompaniment...")
                            self._mix_with_accompaniment(
                                vocal_wav=str(generated_path),
                                acc_wav=str(acc_for_mix),
                                output_wav=str(mixed_path),
                            )
                            output_source_path = mixed_path
                        except Exception as exc:
                            if strict_target_vocal_removal:
                                self.logger.error("Target vocal suppression failed: %s", exc)
                                self._enqueue_ui(self.status_var.set, "Status: Error")
                                return
                            self.logger.warning("Mixdown skipped, using vocal-only output: %s", exc)
                    else:
                        if strict_target_vocal_removal:
                            self.logger.error("Accompaniment not found; cannot remove target vocal reliably.")
                            self._enqueue_ui(self.status_var.set, "Status: Error")
                            return
                        self.logger.info("Accompaniment not found, exporting vocal-only output.")

                final_output = None
                try:
                    final_output = self._finalize_output_file(
                        save_dir=save_dir,
                        target_wav=str(run_context["target_wav"]),
                        mode=mode,
                        source_filename=output_source_path.name,
                    )
                except OSError as exc:
                    self.logger.warning("Auto-rename skipped: %s", exc)

                output_path = Path(final_output) if final_output else output_source_path
                if not output_path.exists():
                    self.logger.error("Inference finished but output file not found: %s", output_path)
                    self._enqueue_ui(self.status_var.set, "Status: Error")
                    return

                self.logger.info("Output saved to %s", output_path)

                self.logger.info("Inference completed successfully.")
                self._enqueue_ui(self.status_var.set, "Status: Complete")
            else:
                self.logger.error("Inference failed (exit code %d)", self._process.returncode)
                self._enqueue_ui(self.status_var.set, "Status: Error")

        except Exception as exc:
            self.logger.error("Inference failed: %s", exc)
            self._enqueue_ui(self.status_var.set, "Status: Error")
        finally:
            self._process = None
            self._enqueue_ui(self._set_running, False)
            shutil.rmtree(tmp_dir, ignore_errors=True)

    # ── Main loop ────────────────────────────────────────────────

    def run(self) -> None:
        self.root.mainloop()


def launch_gui(settings_path: str = "config/settings.yaml") -> None:
    app = SoulXApp(settings_path=settings_path)
    app.run()
