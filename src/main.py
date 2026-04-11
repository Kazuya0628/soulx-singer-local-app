import argparse
import logging
from pathlib import Path
import sys

from config_loader import load_device_config, load_settings
from device_selector import resolve_device
from inference_engine import SoulXSingerEngine
from job_runner import run_inference_with_fallback
from soulx_config import render_preview_command, validate_soulx_config


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="SoulX-Singer local runner")
    parser.add_argument("--config", default="config/settings.yaml", help="settings yaml path")
    parser.add_argument("--audio", required=False, help="input audio file")
    parser.add_argument("--model", default="models/soulx-singer.pth", help="model path")
    parser.add_argument("--dry-run", action="store_true", help="show resolved SoulX command and exit")
    parser.add_argument("--gui", action="store_true", help="launch GUI mode")
    return parser


def main() -> int:
    args = build_parser().parse_args()

    # For packaged macOS app, launch GUI by default when no CLI action is requested.
    if args.gui or (getattr(sys, "frozen", False) and not args.audio and not args.dry_run):
        from gui import launch_gui
        launch_gui(settings_path=args.config)
        return 0

    settings = load_settings(args.config)

    log_level = settings.get("app", {}).get("log_level", "INFO")
    logging.basicConfig(level=getattr(logging, str(log_level).upper(), logging.INFO))
    logger = logging.getLogger("soulx-local")

    dev_cfg = load_device_config(settings)
    decision = resolve_device(dev_cfg)
    logger.info(
        "device_selected=%s fallback=%s reason=%s",
        decision.device,
        decision.used_fallback,
        decision.reason,
    )

    soulx_cfg = settings.get("soulx", {})
    valid, message = validate_soulx_config(soulx_cfg)
    if not valid:
        logger.error("Invalid soulx config: %s", message)
        return 1

    engine = SoulXSingerEngine(
        model_path=args.model,
        command_template=soulx_cfg.get(
            "command_template",
            "python infer.py --input {input} --output {output} --model {model} --device {device}",
        ),
        output_suffix=soulx_cfg.get("output_suffix", ".sung.wav"),
        skip_output_check=bool(soulx_cfg.get("skip_output_check", False)),
        work_dir=soulx_cfg.get("work_dir"),
    )

    if args.dry_run:
        input_for_preview = args.audio or "input.wav"
        output_for_preview = engine.build_output_path(input_for_preview)
        segment_seconds = int(settings.get("inference", {}).get("segment_seconds", 12))
        preview = render_preview_command(
            soulx_cfg=soulx_cfg,
            input_audio=input_for_preview,
            output_audio=output_for_preview,
            model=args.model,
            device=decision.device,
            segment_seconds=segment_seconds,
        )
        print(f"dry_run_command={preview}")
        return 0

    if not args.audio:
        logger.info("No --audio provided. Device probe finished.")
        return 0

    if not Path(args.audio).exists():
        logger.error("Audio file not found: %s", args.audio)
        return 1
    result = run_inference_with_fallback(
        engine=engine,
        audio=args.audio,
        settings=settings,
        device=decision.device,
    )
    logger.info("inference_done=%s", result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
