from pathlib import Path
from typing import Any

import yaml

from device_selector import DeviceConfig


def load_settings(path: str | Path) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    data.setdefault("app", {})
    data.setdefault("inference", {})
    data.setdefault("fallback_policy", {})
    return data


def load_device_config(settings: dict[str, Any]) -> DeviceConfig:
    app = settings.get("app", {})
    return DeviceConfig(
        device_preference=str(app.get("device_preference", "auto")).lower(),
        allow_fallback=bool(app.get("allow_fallback", True)),
        startup_probe=bool(app.get("startup_probe", True)),
    )
