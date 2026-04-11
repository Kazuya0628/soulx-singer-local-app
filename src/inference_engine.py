from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import shlex
import subprocess


@dataclass
class InferenceResult:
    ok: bool
    output_path: str
    device: str


class SoulXSingerEngine:
    def __init__(
        self,
        model_path: str | Path,
        command_template: str = "python infer.py --input {input} --output {output} --model {model} --device {device}",
        output_suffix: str = ".sung.wav",
        skip_output_check: bool = False,
        work_dir: str | None = None,
    ) -> None:
        self.model_path = str(model_path)
        self.command_template = command_template
        self.output_suffix = output_suffix
        self.skip_output_check = skip_output_check
        self.work_dir = work_dir

    def build_output_path(self, audio: str) -> str:
        return str(Path(audio).with_suffix(self.output_suffix))

    def build_command(self, audio: str, output: str, segment_seconds: int, device: str) -> list[str]:
        rendered = self.command_template.format(
            input=shlex.quote(audio),
            output=shlex.quote(output),
            model=shlex.quote(self.model_path),
            device=shlex.quote(device),
            segment_seconds=segment_seconds,
        )
        return shlex.split(rendered)

    def infer(self, audio: str, segment_seconds: int, device: str) -> InferenceResult:
        output = self.build_output_path(audio)
        expected_output = Path(output)
        if not expected_output.is_absolute() and self.work_dir:
            expected_output = Path(self.work_dir) / expected_output
        pre_output_stat = expected_output.stat() if expected_output.exists() else None

        cmd = self.build_command(
            audio=audio,
            output=output,
            segment_seconds=segment_seconds,
            device=device,
        )

        proc = subprocess.run(
            cmd,
            cwd=self.work_dir,
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode != 0:
            raise RuntimeError(
                "SoulX-Singer command failed: "
                f"code={proc.returncode} stdout={proc.stdout.strip()} stderr={proc.stderr.strip()}"
            )

        if not self.skip_output_check:
            if not expected_output.exists():
                raise RuntimeError(f"Expected output file not found: {expected_output}")

            if pre_output_stat is not None:
                post_output_stat = expected_output.stat()
                if (
                    post_output_stat.st_mtime_ns == pre_output_stat.st_mtime_ns
                    and post_output_stat.st_size == pre_output_stat.st_size
                ):
                    raise RuntimeError(f"Expected output file not updated: {expected_output}")

        return InferenceResult(ok=True, output_path=output, device=device)
