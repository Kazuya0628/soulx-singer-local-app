#!/usr/bin/env bash
set -euo pipefail

# ── SoulX-Singer setup script for Mac ──
# This script:
#   1. Clones the SoulX-Singer repository
#   2. Creates a conda environment (Python 3.10)
#   3. Installs dependencies
#   4. Downloads pretrained models from Hugging Face

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
SOULX_DIR="${SOULX_DIR:-$ROOT_DIR/SoulX-Singer}"

echo "=== SoulX-Singer Setup ==="
echo "Install directory: $SOULX_DIR"

# ── 1. Clone repository ──
if [[ -d "$SOULX_DIR/.git" ]]; then
    echo "[1/4] Repository already cloned, pulling latest..."
    git -C "$SOULX_DIR" pull
else
    echo "[1/4] Cloning SoulX-Singer..."
    git clone https://github.com/Soul-AILab/SoulX-Singer.git "$SOULX_DIR"
fi

# ── 2. Conda environment ──
echo "[2/4] Setting up conda environment..."
if conda info --envs 2>/dev/null | grep -q soulxsinger; then
    echo "  Environment 'soulxsinger' already exists, skipping creation."
else
    conda create -n soulxsinger -y python=3.10
fi

echo "  Activating environment..."
eval "$(conda shell.bash hook)"
conda activate soulxsinger

# ── 3. Install dependencies ──
echo "[3/4] Installing dependencies..."
pip install -r "$SOULX_DIR/requirements.txt"
pip install -U "huggingface_hub<1.0"

# ── 4. Download models ──
echo "[4/4] Downloading pretrained models..."
MODELS_DIR="$SOULX_DIR/pretrained_models"
mkdir -p "$MODELS_DIR"

if [[ -d "$MODELS_DIR/SoulX-Singer" && -f "$MODELS_DIR/SoulX-Singer/model-svc.pt" ]]; then
    echo "  SoulX-Singer model already downloaded."
else
    echo "  Downloading SoulX-Singer model..."
    hf download Soul-AILab/SoulX-Singer --local-dir "$MODELS_DIR/SoulX-Singer"
fi

if [[ -d "$MODELS_DIR/SoulX-Singer-Preprocess" ]]; then
    echo "  SoulX-Singer-Preprocess model already downloaded."
else
    echo "  Downloading SoulX-Singer-Preprocess model..."
    hf download Soul-AILab/SoulX-Singer-Preprocess --local-dir "$MODELS_DIR/SoulX-Singer-Preprocess"
fi

echo ""
echo "=== Setup complete ==="
echo "SoulX-Singer directory: $SOULX_DIR"
echo "Model path (SVC):      $MODELS_DIR/SoulX-Singer/model-svc.pt"
echo "Model path (SVS):      $MODELS_DIR/SoulX-Singer/model.pt"
echo ""
echo "Next steps:"
echo "  1. Update config/settings.yaml with the correct work_dir:"
echo "     work_dir: $SOULX_DIR"
echo "  2. Run the app:"
echo "     python src/main.py --gui"
