# Plan: Video2Auto — 動画から業務フロー書き起こし＋Python自動化

## 改善タスクの標準フォーマット

- **Current（現状）**: Video2PDD v2は Robin script→PDD Excel のみ対応。動画ファイル直接入力とPython自動化コード生成は未実装
- **Problem（困りごと）**: 画面録画済みの業務フローを手動で書き起こし→手動でPython自動化コード作成している。時間がかかりミスしやすい
- **Target（狙う状態）**: MP4動画を入力 → PDD Excel + Python自動化コード（Playwright+pywinauto）を自動生成
- **Change（今回"変える"こと）**: Gemini multimodal動画解析 + テンプレートベースPythonコード生成を追加
- **Verification（検証）**: テスト動画（rakuraku_login相当）でE2E実行、PDD Excelが既存フォーマットと一致、生成コードが構文エラーなし
- **Safety（安全）**: event_log.json がSSOT。Phase間でResume可能。API失敗時リトライ。低confidenceステップは自動フラグ
- **Next（失敗時の次の一手）**: Gemini精度不足 → フレーム抽出 + 個別画像解析にフォールバック

---

## アーキテクチャ

```
Video (MP4)
    |
Phase 1: Gemini動画解析
    | (構造化JSON: steps + flow_phases)
    v
Phase 2: event_log正規化 + Gap検出
    | (event_log.json - SSOT)
    v
Phase 3: PDD Excel生成（既存phase3_excel.py再利用）
    | (PDD Excel 4シート)
    v
Phase 4: Python自動化コード生成（NEW）
    | (automation_YYYYMMDD.py)
    v
Output: PDD Excel + Python script
```

### 品質分類
**新規ツール（PoC→段階的品質向上）** — 初版60%精度で価値あり。PDD Excel出力は既存100%品質フォーマットを再利用。

---

## 実装ステップ

### Step 1: event_log.py v3 拡張（~50行追加）

**変更内容**: 動画入力対応のスキーマ拡張

追加フィールド（steps）:
- `timestamp`: "MM:SS" — 動画内タイムスタンプ
- `app_type`: "web|desktop" — アプリ種別（Playwright/pywinauto振り分け用）
- `confidence`: 0.95 — Gemini解析の信頼度
- `selector_hint`: "..." — 自動化用セレクタヒント

追加フィールド（run_metadata.input_files）:
- `video_file`: "path/to/video.mp4"
- `video_file_sha256`: "..."

追加フェーズ:
- `PHASE_VIDEO_ANALYSIS = "phase1_video_analysis"`
- `PHASE_CODE_GEN = "phase5_code_generation"`

**既存互換性**: Robin入力のv2フォーマットはそのまま動作。新フィールドはOptional。

### Step 2: Geminiプロンプト設計（新規ファイル）

**ファイル**: `tools/video2pdd/prompts/video_analysis.txt`

既存 `tools/prompts/pdd_extraction.txt` をベースに拡張:
- **出力形式**: Markdown table → JSON配列（パース可能）
- **追加カラム**: `app_type`, `confidence`, `selector_hint`
- **Web/Desktop判定ルール**: ブラウザクロム検出 → web、それ以外 → desktop
- **セレクタヒント**: ボタンテキスト、input type、URL パス等

Gemini出力JSON例:
```json
{
  "steps": [
    {
      "num": 1,
      "timestamp": "00:05",
      "application": "Edge - 楽楽精算",
      "app_type": "web",
      "action": "Navigate",
      "target": "楽楽精算ログインページ",
      "value": "https://app.rakurakuseisan.jp/login",
      "result": "ログインページが表示された",
      "confidence": 0.95,
      "selector_hint": "URL: /login",
      "notes": ""
    }
  ],
  "flow_phases": [
    {
      "phase_name": "ログイン",
      "step_range": [1, 5],
      "summary": "楽楽精算へのログイン操作",
      "window_context": "Edge - 楽楽精算"
    }
  ],
  "ambiguities": [
    {
      "step_num": 3,
      "description": "パスワード入力の具体値が画面上マスクされている"
    }
  ]
}
```

音声付き用: `tools/video2pdd/prompts/video_analysis_audio.txt`

### Step 3: Phase 1 — Gemini動画解析（新規モジュール）

**ファイル**: `tools/video2pdd/phase1_video.py` (~200行)

```
def analyze_video(video_path, prompt_path) -> dict:
    1. 動画ファイルサイズ/形式チェック（ポカヨケ）
    2. Gemini CLI呼び出し（gemini -p "..." < video.mp4）
    3. JSON出力パース + バリデーション
    4. confidence < 0.7 のステップに gap_flag 付与
    5. 重複ステップ検出（GAP_DUPLICATE_ACTION）
    6. リトライ（API失敗時、最大3回）
```

Gemini呼び出し:
```bash
gemini -p "$(cat prompts/video_analysis.txt)" < video.mp4 2>/dev/null
```

### Step 4: Phase 2 — event_log正規化（既存拡張）

**ファイル**: `tools/video2pdd/phase2_describe.py` に追加 (~100行)

- `normalize_video_steps()`: Gemini JSON → event_log.steps マッピング
- `detect_app_type()`: application名からweb/desktop自動判定
- 既存の `alias_element()`, `alias_window()`, `build_flow_phases()` を再利用

### Step 5: Phase 3 — PDD Excel（既存微調整）

**変更最小限**:
- `timestamp` カラム表示（Sheet 2: 詳細手順に列追加）
- `confidence` による色分け（<0.7 → 赤背景、0.7-0.9 → 黄背景）

### Step 6: Phase 4 — Python自動化コード生成（新規モジュール）

**ファイル**: `tools/video2pdd/phase4_codegen.py` (~350行)

**テンプレートベース（LLM不使用 → 決定論的、再現可能）**

Web操作テンプレート（Playwright）:
```python
WEB_TEMPLATES = {
    "Navigate": 'await page.goto("{value}")',
    "Click":    'await page.locator("{selector_hint}").click()',
    "Input":    'await page.locator("{selector_hint}").fill("{value}")',
    "Select":   'await page.locator("{selector_hint}").select_option("{value}")',
    "Wait":     'await page.wait_for_timeout({value})',
    "KeyShortcut": 'await page.keyboard.press("{value}")',
}
```

Desktop操作テンプレート（pywinauto）:
```python
DESKTOP_TEMPLATES = {
    "Click":    'window["{target}"].click_input()',
    "Input":    'window["{target}"].type_keys("{value}", with_spaces=True)',
    "Select":   'window["{target}"].select("{value}")',
    "Wait":     'time.sleep({value})',
    "KeyShortcut": 'keyboard.send_keys("{value}")',
}
```

出力コード構造:
- ヘッダ: imports, source info, WARNING
- Phase別関数: `async def phase_N_xxx():` (web) / `def phase_N_xxx():` (desktop)
- main関数: Phase関数を順次呼び出し
- 全セレクタに `# TODO: VERIFY SELECTOR (confidence: X.XX)` コメント
- 全ステップに `# Source: video timestamp MM:SS` コメント（動画で確認可能）

### Step 7: main.py 拡張（CLI統合）

**変更内容**: `--video` モード追加

```bash
# 動画入力（NEW）
python -m tools.video2pdd.main --video recording.mp4

# 動画入力 + 音声あり
python -m tools.video2pdd.main --video recording.mp4 --with-audio

# Robin入力（既存、変更なし）
python -m tools.video2pdd.main --robin-file flow.robin

# 共通オプション
  --output-dir DIR        # 出力先
  --stop-after phaseN     # 途中停止
  --resume EVENT_LOG      # 再開
  --skip-codegen          # コード生成スキップ（PDD Excelのみ）
```

---

## ファイル変更一覧

| ファイル | 操作 | 行数目安 |
|---------|------|---------|
| `tools/video2pdd/event_log.py` | 編集 | +50 |
| `tools/video2pdd/prompts/video_analysis.txt` | 新規 | ~80 |
| `tools/video2pdd/prompts/video_analysis_audio.txt` | 新規 | ~90 |
| `tools/video2pdd/phase1_video.py` | 新規 | ~200 |
| `tools/video2pdd/phase2_describe.py` | 編集 | +100 |
| `tools/video2pdd/phase3_excel.py` | 編集 | +30 |
| `tools/video2pdd/phase4_codegen.py` | 新規 | ~350 |
| `tools/video2pdd/main.py` | 編集 | +80 |
| **合計** | | **~980行** |

---

## TPS設計

| TPS原則 | 実装 |
|---------|------|
| ポカヨケ | 動画形式チェック（MP4/AVI/MKV）、Gemini JSONバリデーション、confidence閾値フラグ |
| アンドン | 低confidenceステップ数をCLI出力、未解決項目シート（Excel Sheet 3）、コード内TODOコメント |
| 自働化 | API失敗時リトライ（3回）、Phase間Resume、event_log.jsonによるSSOT保証 |

## 性弱説対策

| 弱点 | 対策 |
|------|------|
| 1.忘れる | 生成コードに `# TODO: VERIFY` を強制挿入。実行時に未検証数を表示 |
| 2.見ない | PDD Excelの低confidence行を赤/黄色で視覚的に目立たせる |
| 3.後回し | `--skip-codegen` でPDD優先。コード生成は後から追加実行可能 |
| 4.飛ばす | Phase 3（PDD確認）完了前にPhase 4（コード生成）を実行不可 |

---

## 実装順序

1. Step 1: event_log.py v3拡張（基盤）
2. Step 2: Geminiプロンプト設計
3. Step 3: Phase 1 動画解析モジュール
4. Step 4: Phase 2 正規化拡張
5. Step 5: Phase 3 Excel微調整
6. Step 6: Phase 4 コード生成モジュール
7. Step 7: main.py CLI統合
8. 検証: テスト動画でE2E実行

## リスクと対策

| リスク | 影響 | 対策 |
|--------|------|------|
| Gemini動画解析の精度不足 | ステップ抜け、誤認識 | フレーム抽出+個別画像解析にフォールバック |
| セレクタの信頼性 | 生成コードが動かない | テンプレート+TODOコメント（人間が修正前提） |
| 動画が長すぎる | API制限、コスト | 分割処理+警告表示 |
| Gemini CLI未インストール | Phase 1実行不可 | 起動時チェック+インストール手順表示 |
