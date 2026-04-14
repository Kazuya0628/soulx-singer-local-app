# SoulX-Singer Local App Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** MPS優先・CPUフォールバックでSoulX-Singer推論を実行できるローカルアプリの最小実装を作る。

**Architecture:** 設定ロード、デバイス判定、推論実行、フォールバック再試行を責務分離し、UIを後付け可能な構成にする。初版はCLIで動作検証し、Tkinter UIを差し替え可能な設計にする。

**Tech Stack:** Python 3.11+, PyTorch, PyYAML, pytest

---

### Task 1: プロジェクト骨格作成

**Files:**
- Create: `soulx-singer-local-app/README.md`
- Create: `soulx-singer-local-app/requirements.txt`
- Create: `soulx-singer-local-app/src/__init__.py`
- Create: `soulx-singer-local-app/src/main.py`

- [ ] **Step 1: 最小READMEを作成する**
- [ ] **Step 2: 依存ライブラリをrequirementsに記載する**
- [ ] **Step 3: CLI起動の骨格を追加する**
- [ ] **Step 4: `python src/main.py --help` で起動確認する**

### Task 2: 設定とデバイス判定を実装

**Files:**
- Create: `soulx-singer-local-app/config/settings.yaml`
- Create: `soulx-singer-local-app/src/config_loader.py`
- Create: `soulx-singer-local-app/src/device_selector.py`
- Create: `soulx-singer-local-app/tests/test_device_selector.py`

- [ ] **Step 1: デバイス設定モデルと設定読み込みを実装する**
- [ ] **Step 2: MPS可用性チェックとプローブを実装する**
- [ ] **Step 3: auto/mps/cpu判定ロジックを実装する**
- [ ] **Step 4: 判定ロジックのテストを追加して実行する**

### Task 3: 推論実行とCPUフォールバック

**Files:**
- Create: `soulx-singer-local-app/src/inference_engine.py`
- Create: `soulx-singer-local-app/src/job_runner.py`
- Create: `soulx-singer-local-app/tests/test_job_runner.py`

- [ ] **Step 1: SoulX-Singer呼び出し用のエンジンインターフェースを作る**
- [ ] **Step 2: 推論失敗時の再試行と軽量化ロジックを実装する**
- [ ] **Step 3: MPS失敗時CPUフォールバックを実装する**
- [ ] **Step 4: フォールバック挙動のテストを実行する**

### Task 4: 実行導線とドキュメント

**Files:**
- Modify: `soulx-singer-local-app/src/main.py`
- Modify: `soulx-singer-local-app/README.md`

- [ ] **Step 1: 引数から設定を読み込んでジョブ実行する導線を作る**
- [ ] **Step 2: ログ出力を追加する**
- [ ] **Step 3: Mac mini M4向け実行手順と注意点をREADMEに追記する**
- [ ] **Step 4: テストと起動コマンドを再実行して検証する**
