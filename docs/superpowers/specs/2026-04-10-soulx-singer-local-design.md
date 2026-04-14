# SoulX-Singer Local App Design

## Goal
Mac mini M4 24GB環境で、録音または音声ファイル入力から歌声生成を行うローカルアプリを構築する。モデルはSoulX-Singerを使用し、クラウドAPIは使用しない。

## Scope
- ローカル実行のデスクトップアプリ
- 入力: 音声ファイル、マイク録音
- 推論: SoulX-Singer
- 出力: WAV保存、ログ保存
- 実行デバイス: MPS優先、CPUフォールバック

## Out of Scope
- 同意取得フローの実装
- クラウド連携
- マルチユーザー管理

## Architecture
- UI層: TkinterベースのローカルUI
- 設定層: YAML設定のロードとバリデーション
- 推論層: SoulX-Singer推論エンジンラッパー
- 実行制御層: デバイス判定、再試行、フォールバック
- I/O層: 入力音声読み込み、出力保存、ログ

## Device Policy
- device_preference: auto|mps|cpu
- autoはMPS可用性と実演算プローブで判定
- MPS失敗時はCPUへフォールバック
- すべてログに理由を記録

## Error Handling
- 入力形式エラーは即時通知
- 推論失敗時は設定を軽量化して再試行
- OOMまたはMPS失敗時はCPU再実行
- 最終失敗時はログを保存して終了

## Testing Strategy
- MPS検出ロジックのユニットテスト
- デバイス選択ロジックのユニットテスト
- フォールバック再試行ロジックのユニットテスト

## Deliverables
- 実行可能なCLIエントリ
- 設定ファイルテンプレート
- ユニットテスト
- README（Macセットアップと実行方法）
