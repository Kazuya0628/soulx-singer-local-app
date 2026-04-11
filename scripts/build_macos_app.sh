#!/usr/bin/env bash
set -euo pipefail

APP_NAME="SoulXSingerLocal"
ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-$ROOT_DIR/.venv/bin/python}"

if [[ ! -x "$PYTHON_BIN" ]]; then
  PYTHON_BIN="python3"
fi

cd "$ROOT_DIR"

"$PYTHON_BIN" -m pip install --upgrade pip
"$PYTHON_BIN" -m pip install -r requirements-dev.txt

# Build a macOS .app bundle with GUI (windowed mode).
"$PYTHON_BIN" -m PyInstaller \
  --noconfirm \
  --clean \
  --name "$APP_NAME" \
  --windowed \
  --add-data "config:config" \
  src/main.py

# Create a launcher script that starts in GUI mode
LAUNCHER="dist/$APP_NAME.app/Contents/MacOS/launch_gui.sh"
cat > "$LAUNCHER" <<'INNEREOF'
#!/bin/bash
DIR="$(cd "$(dirname "$0")" && pwd)"
exec "$DIR/SoulXSingerLocal" --gui "$@"
INNEREOF
chmod +x "$LAUNCHER"

echo "Built app: $ROOT_DIR/dist/$APP_NAME.app"
