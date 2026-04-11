# SoulX-Singer Local App

Mac mini M4向けのローカル実行アプリ最小構成です。現行構成ではMPS実行で未実装演算に当たるケースがあるため、デフォルトはCPU固定で運用します。

## Setup

### 前提

- macOS（Mac mini M4 推奨）
- Miniconda/Anaconda
- Git
- Python 3.11+

### 1. このアプリの依存をインストール

```bash
python -m pip install -r requirements.txt
```

### 2. SoulX-Singer本体とモデルをダウンロード（macOS）

Hugging Face から約 4GB のモデルをダウンロードします（初回のみ、時間がかかります）。

```bash
chmod +x scripts/setup_soulx.sh
./scripts/setup_soulx.sh
```

このスクリプトは以下を行います:

- `SoulX-Singer/` ディレクトリに [GitHubリポジトリ](https://github.com/Soul-AILab/SoulX-Singer) をクローン
- `soulxsinger` という conda 環境を作成（Python 3.10）
- 依存パッケージをインストール
- Hugging Face から `Soul-AILab/SoulX-Singer` と `Soul-AILab/SoulX-Singer-Preprocess` モデルをダウンロード

### 3. `config/settings.yaml` の `work_dir` を設定

セットアップ後、`soulx.work_dir` に SoulX-Singer のクローン先パスを記入します。

```yaml
soulx:
  work_dir: /absolute/path/to/SoulX-Singer
```

### 4. conda 環境のアクティベート

SoulX-Singer 本体は conda 環境 `soulxsinger` でのみ動作します。アプリ実行前に有効化してください。

```bash
conda activate soulxsinger
```

## Run

### GUI モード（推奨）

```bash
python src/main.py --gui
```

設定ファイルを指定する場合:

```bash
python src/main.py --gui --config config/settings.yaml
```

GUI では以下の操作ができます:

- **Mode**: SVC（声質変換）または SVS（歌声合成）を選択
- **Prompt audio**: 参照音声（声質のソース）
- **Target audio**: 変換対象の音声
- **Output dir**: 出力先ディレクトリ
- **Device**: auto / mps / cpu
- **Pitch shift**: -12 ～ +12 半音
- **Prompt vocal separation**: promptに伴奏が含まれる場合のみ有効化
- **Target vocal separation**: チェックを外すとボーカル分離をスキップ
- **SVS Options**（SVSモード時のみ）: prompt / target の JSON メタデータファイル

入力音声は `wav/mp3/m4a/flac/ogg` を選択できます。
ただし、SVCの直接実行では環境依存で `m4a/mp3` 読み込みエラーになることがあるため、
`m4a` のボーカル差し替えは下記の `scripts/run_svc_swap.sh` 手順を推奨します。
変換が成功すると、出力先に作られる `generated.wav` は
`<target_stem>_<mode>_YYYYMMDD_HHMMSS.wav` 形式へ自動リネームされ、上書きを防止します。
`Target vocal separation` を有効化している場合は、抽出された伴奏（`preprocess/target/acc.wav`）と
推論結果を自動でミックスした音源を優先して保存します。
このとき、残留しやすいターゲット原音ボーカルは `preprocess/target/vocal.wav` を参照した
抑制処理（サイドチェイン圧縮）を追加で適用してからミックスします。
既定では `soulx.strict_target_vocal_removal: true` のため、抑制処理や伴奏抽出が失敗した場合は
ボーカルのみ出力へフォールバックせず、エラー終了します。

## m4aでボーカル差し替え（おすすめ）

やりたいこと:

- `prompt`: 録音した m4a（声質・テンションの参照）
- `target`: 差し替えたい歌（フルミックス可）

1コマンドで前処理（F0抽出）からSVC変換まで実行できます。

```bash
chmod +x scripts/run_svc_swap.sh
./scripts/run_svc_swap.sh /path/to/prompt.m4a /path/to/target_song.m4a /path/to/output Japanese
```

出力:

- 変換結果: `/path/to/output/<target_stem>_svc_YYYYMMDD_HHMMSS.wav`
- 中間ファイル: `/path/to/output/preprocess/...`
- `target` がフルミックスの場合、伴奏抽出結果: `/path/to/output/preprocess/target/acc.wav`
- `target` がフルミックスの場合、抽出伴奏に対して原音ボーカル抑制をかけてから再ミックスします

補足:

- `target` がすでにボーカル単体なら `TARGET_VOCAL_SEP=False` を付けて実行してください。

```bash
TARGET_VOCAL_SEP=False ./scripts/run_svc_swap.sh /path/to/prompt.m4a /path/to/target_vocal.m4a /path/to/output Japanese
```

### CLI モード

設定とデバイス判定のみ確認する場合:

```bash
python src/main.py --config config/settings.yaml
```

音声を指定して実行する場合:

```bash
python src/main.py --config config/settings.yaml --audio /path/to/input.wav --model /path/to/soulx-singer.pth
```

実行前にコマンド展開だけ確認する場合（dry-run）:

```bash
python src/main.py --config config/settings.yaml --audio /path/to/input.wav --model /path/to/soulx-singer.pth --dry-run
```

## Mac同期前に進められる確認

1. 設定検証とコマンド展開確認

```bash
python src/main.py --config config/settings.yaml --audio sample.wav --model model.pth --dry-run
```

1. テスト実行

```bash
pytest tests -q
```

1. 期待結果

- `dry_run_command=...` が表示される
- テストがすべて成功する

## SoulX-Singer実体の接続

GUIモードでは `config/settings.yaml` の `soulx.svc_command_template` / `soulx.svs_command_template` を使用します。
CLIモードでは後方互換として `soulx.command_template` を使用します。

SVCテンプレートの主なプレースホルダー:

- `{prompt_wav}`: 参照音声
- `{target_wav}`: 変換対象音声
- `{save_dir}`: 出力先ディレクトリ
- `{device}`: 解決済みデバイス（mps or cpu）
- `{model}`: モデルパス
- `{pitch_shift}`: キー変更

CLI互換テンプレート例:

```yaml
soulx:
  command_template: python infer.py --input {input} --output {output} --model {model} --device {device} --segment {segment_seconds}
  output_suffix: .sung.wav
  skip_output_check: false
  work_dir: /Users/yourname/SoulX-Singer
```

`work_dir` は SoulX-Singer の実行ディレクトリです。

## 実データ向けCPUプリセット

実運用向けの設定テンプレートを追加しています。

- プリセット: `config/settings.realdata.cpu.yaml`
- 特徴: CPU固定、startup probe無効、長尺で安定しやすい `segment_seconds: 8`
- 利用前に `soulx.work_dir` を自分の環境パスに合わせてください

実行例:

```bash
python src/main.py --gui --config config/settings.realdata.cpu.yaml
```

既定設定を上書きしたい場合:

```bash
cp config/settings.realdata.cpu.yaml config/settings.yaml
```

## Notes for Mac mini M4

- `config/settings.yaml` の既定値は `device_preference: cpu` です。
- MPSを試す場合は `device_preference: mps` に変更できますが、PyTorch MPS未実装演算で失敗する場合があります。
- 長尺入力で失敗する場合は `segment_seconds` を小さくしてください。

## Test

```bash
pytest tests -q
```

## Build macOS app and DMG

この手順はmacOS端末で実行してください。

1. 実行権限を付与

```bash
chmod +x scripts/build_macos_app.sh scripts/make_dmg.sh
```

1. .app を作成

```bash
./scripts/build_macos_app.sh
```

1. 配布用 DMG を作成

```bash
./scripts/make_dmg.sh 0.1.0
```

1. 生成物

- `.app`: `dist/SoulXSingerLocal.app`
- `.dmg`: `dist/SoulXSingerLocal-0.1.0.dmg`

### 配布のポイント

- 配布先Macで初回起動時にGatekeeper警告が出る場合があります。
- 開発用配布では「右クリック -> 開く」で起動可能です。
- 社内配布を安定化するなら、Apple Developer IDで署名とnotarizationを追加してください。
