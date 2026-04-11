#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 3 || $# -gt 4 ]]; then
  echo "Usage: $0 <prompt_audio.(m4a|mp3|wav|flac|ogg)> <target_audio.(m4a|mp3|wav|flac|ogg)> <output_dir> [language]"
  echo "Example: $0 ~/Desktop/prompt.m4a ~/Desktop/song.m4a ~/Desktop/soulx_out Japanese"
  exit 1
fi

PROMPT_AUDIO="$1"
TARGET_AUDIO="$2"
OUTPUT_DIR="$3"
LANGUAGE="${4:-Japanese}"

# If target is already a clean vocal track, set TARGET_VOCAL_SEP=False.
TARGET_VOCAL_SEP="${TARGET_VOCAL_SEP:-True}"

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
SOULX_DIR="$ROOT_DIR/SoulX-Singer"

CONDA_BIN="${CONDA_BIN:-/opt/homebrew/bin/conda}"
if [[ ! -x "$CONDA_BIN" ]]; then
  CONDA_BIN="$(command -v conda || true)"
fi

if [[ -z "$CONDA_BIN" ]]; then
  echo "conda command not found. Install Miniconda or set CONDA_BIN." >&2
  exit 1
fi

if [[ ! -d "$SOULX_DIR" ]]; then
  echo "SoulX-Singer directory not found: $SOULX_DIR" >&2
  exit 1
fi

if [[ ! -f "$PROMPT_AUDIO" ]]; then
  echo "Prompt audio not found: $PROMPT_AUDIO" >&2
  exit 1
fi

if [[ ! -f "$TARGET_AUDIO" ]]; then
  echo "Target audio not found: $TARGET_AUDIO" >&2
  exit 1
fi

PROMPT_AUDIO="$(cd "$(dirname "$PROMPT_AUDIO")" && pwd)/$(basename "$PROMPT_AUDIO")"
TARGET_AUDIO="$(cd "$(dirname "$TARGET_AUDIO")" && pwd)/$(basename "$TARGET_AUDIO")"
mkdir -p "$OUTPUT_DIR"
OUTPUT_DIR="$(cd "$OUTPUT_DIR" && pwd)"

PREPROCESS_DIR="$OUTPUT_DIR/preprocess"
PROMPT_PRE_DIR="$PREPROCESS_DIR/prompt"
TARGET_PRE_DIR="$PREPROCESS_DIR/target"
mkdir -p "$PROMPT_PRE_DIR" "$TARGET_PRE_DIR"

echo "[1/3] Preprocess prompt audio -> vocal.wav + vocal_f0.npy"
pushd "$SOULX_DIR" >/dev/null
"$CONDA_BIN" run -n soulxsinger python -m preprocess.pipeline \
  --audio_path "$PROMPT_AUDIO" \
  --save_dir "$PROMPT_PRE_DIR" \
  --language "$LANGUAGE" \
  --device cpu \
  --vocal_sep False \
  --midi_transcribe False

echo "[2/3] Preprocess target audio -> vocal.wav + vocal_f0.npy"
"$CONDA_BIN" run -n soulxsinger python -m preprocess.pipeline \
  --audio_path "$TARGET_AUDIO" \
  --save_dir "$TARGET_PRE_DIR" \
  --language "$LANGUAGE" \
  --device cpu \
  --vocal_sep "$TARGET_VOCAL_SEP" \
  --midi_transcribe False

PROMPT_WAV="$PROMPT_PRE_DIR/vocal.wav"
PROMPT_F0="$PROMPT_PRE_DIR/vocal_f0.npy"
TARGET_WAV="$TARGET_PRE_DIR/vocal.wav"
TARGET_F0="$TARGET_PRE_DIR/vocal_f0.npy"

for f in "$PROMPT_WAV" "$PROMPT_F0" "$TARGET_WAV" "$TARGET_F0"; do
  if [[ ! -f "$f" ]]; then
    echo "Preprocess output not found: $f" >&2
    popd >/dev/null
    exit 1
  fi
done

echo "[3/3] Run SVC voice replacement"
"$CONDA_BIN" run -n soulxsinger python -m cli.inference_svc \
  --device cpu \
  --model_path pretrained_models/SoulX-Singer/model-svc.pt \
  --config soulxsinger/config/soulxsinger.yaml \
  --prompt_wav_path "$PROMPT_WAV" \
  --target_wav_path "$TARGET_WAV" \
  --prompt_f0_path "$PROMPT_F0" \
  --target_f0_path "$TARGET_F0" \
  --save_dir "$OUTPUT_DIR" \
  --auto_shift \
  --pitch_shift 0

popd >/dev/null

# ── Post-process: suppress target vocal bleed and remix with accompaniment ──
GENERATED="$OUTPUT_DIR/generated.wav"
if [[ ! -f "$GENERATED" ]]; then
  echo "Warning: generated.wav not found in $OUTPUT_DIR" >&2
  exit 1
fi

OUTPUT_SOURCE="$GENERATED"
if [[ "${TARGET_VOCAL_SEP,,}" == "true" ]]; then
  ACC_PATH="$TARGET_PRE_DIR/acc.wav"
  TARGET_VOCAL_PATH="$TARGET_PRE_DIR/vocal.wav"
  FFMPEG_BIN="${FFMPEG_BIN:-$(command -v ffmpeg || true)}"

  if [[ ! -f "$ACC_PATH" ]]; then
    echo "Accompaniment not found at $ACC_PATH. Cannot remove target vocal reliably." >&2
    exit 1
  fi
  if [[ -z "$FFMPEG_BIN" ]]; then
    echo "ffmpeg not found. Install with: brew install ffmpeg" >&2
    exit 1
  fi

  ACC_FOR_MIX="$ACC_PATH"
  if [[ -f "$TARGET_VOCAL_PATH" ]]; then
    SUPPRESSED_ACC="$OUTPUT_DIR/generated_acc_suppressed.wav"
    echo "[post] Suppressing residual target vocal from accompaniment..."
    "$FFMPEG_BIN" -y -i "$ACC_PATH" -i "$TARGET_VOCAL_PATH" \
      -filter_complex "[0:a]aresample=44100,aformat=channel_layouts=stereo,highpass=f=120,lowpass=f=11000[acc];[1:a]aresample=44100,aformat=channel_layouts=stereo,highpass=f=120,lowpass=f=6000,volume=2.0[key];[acc][key]sidechaincompress=threshold=0.003:ratio=20:attack=5:release=250:makeup=1[duck]" \
      -map "[duck]" "$SUPPRESSED_ACC"
    ACC_FOR_MIX="$SUPPRESSED_ACC"
  fi

  MIXED_PATH="$OUTPUT_DIR/generated_mix.wav"
  echo "[post] Mixing generated vocal with accompaniment..."
  "$FFMPEG_BIN" -y -i "$GENERATED" -i "$ACC_FOR_MIX" \
    -filter_complex "[0:a]aresample=44100,pan=stereo|c0=c0|c1=c0,volume=1.0[v];[1:a]aresample=44100,aformat=channel_layouts=stereo,volume=0.9[a];[v][a]amix=inputs=2:normalize=0,alimiter=limit=0.98[out]" \
    -map "[out]" "$MIXED_PATH"
  OUTPUT_SOURCE="$MIXED_PATH"
fi

# ── Rename output file to timestamped name ──
if [[ -f "$OUTPUT_SOURCE" ]]; then
  TARGET_STEM="$(basename "${TARGET_AUDIO%.*}")"
  # sanitize: keep only alphanumeric, hyphen, underscore
  TARGET_STEM="$(echo "$TARGET_STEM" | sed 's/[^a-zA-Z0-9_-]/_/g')"
  TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
  FINAL_NAME="${TARGET_STEM}_svc_${TIMESTAMP}.wav"
  FINAL_PATH="$OUTPUT_DIR/$FINAL_NAME"

  # avoid overwrite if name already exists
  if [[ -f "$FINAL_PATH" ]]; then
    INDEX=1
    while [[ -f "${FINAL_PATH%.wav}_${INDEX}.wav" ]]; do
      INDEX=$((INDEX + 1))
    done
    FINAL_PATH="${FINAL_PATH%.wav}_${INDEX}.wav"
  fi

  mv "$OUTPUT_SOURCE" "$FINAL_PATH"
  echo "Output: $FINAL_PATH"
  if [[ -f "$TARGET_PRE_DIR/acc.wav" ]]; then
    echo "Accompaniment (for remix): $TARGET_PRE_DIR/acc.wav"
  fi
else
  echo "Expected output not found: $OUTPUT_SOURCE" >&2
  exit 1
fi
