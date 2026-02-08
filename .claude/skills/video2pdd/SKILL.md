# Video2PDD Skill

## Overview
Video or PAD Robin script → PDD (Process Design Document) Excel + Python automation code.

Two pipelines:
- **v3 (Video)**: Video file → Gemini multimodal analysis → PDD Excel + Python automation code
- **v2 (Robin)**: PAD Robin script copy-paste → rule-based parsing → PDD Excel

## Prerequisites
- Python 3.11+
- openpyxl installed
- **Video pipeline**: `pip install google-genai` (v1.62.0+) + `GEMINI_API_KEY` env var
- **Robin pipeline**: Power Automate Desktop (Free version is sufficient)

## Status
- **v3 (Video pipeline)**: E2E tested and verified (2026-02-07)
- **v2 (Robin pipeline)**: Production-ready
- **Known issues**: None (FAILED_PRECONDITION bug fixed)

---

## 1. Pipeline Selection

| Input | CLI Flag | Pipeline | Output |
|-------|----------|----------|--------|
| Video file (MP4/AVI/MKV/WEBM/MOV) | `--video` | v3 | PDD Excel + Python code |
| PAD Robin script (.robin) | `--robin-file` | v2 | PDD Excel |
| Existing event_log.json | `--resume` | Auto-detect | Continue from checkpoint |

---

## 2. Video Pipeline (v3)

### 2.1 Workflow

```
担当者（現場）                    開発者（こちら側）
─────────────────────            ─────────────────────
1. 画面操作を録画（OBS等）
2. 動画ファイル(MP4等)を送付 ──→ 3. パイプライン実行
                                  4. Excel + Python確認・調整
                                  5. PDD + 自動化コード納品
```

### 2.2 Execution

```bash
# Basic run
python -m tools.video2pdd.main --video <video_file.mp4>

# With audio analysis
python -m tools.video2pdd.main --video <video_file.mp4> --with-audio

# Skip Python code generation (PDD Excel only)
python -m tools.video2pdd.main --video <video_file.mp4> --skip-codegen

# Stop after Phase 1 (for testing)
python -m tools.video2pdd.main --video <video_file.mp4> --stop-after phase1
```

### 2.3 Pipeline Phases (Video)

| Phase | Module | Description |
|-------|--------|-------------|
| 1 | `phase1_video.py` | Gemini video analysis → structured JSON |
| 2-3 | `phase2_describe.py` | Normalize + Japanese description + Flow phases |
| 3 (Excel) | `phase3_excel.py` | PDD Excel generation (4 sheets) |
| 4 | `phase4_codegen.py` | Python automation code (Playwright + pywinauto) |

### 2.4 Phase 1: Gemini Video Analysis
- Uploads video to Gemini Files API → waits for ACTIVE state → multimodal prompting
- Model: `gemini-2.5-flash`
- Output: structured JSON with `steps`, `flow_phases`, `ambiguities`
- Gap detection: `low_confidence`, `ambiguous_selector`, `duplicate_action`
- Confidence scoring per step (0.0-1.0)
- Auth: `GEMINI_API_KEY` env var (permanent: `setx GEMINI_API_KEY <key>`)

### 2.5 Phase 4: Python Code Generation
- Web steps → async Playwright code (`await page.locator(...).click()`)
- Desktop steps → pywinauto code (`window["target"].click_input()`)
- Grouped by flow_phases into separate functions
- Every step has `# TODO: VERIFY SELECTOR` comment
- Low confidence steps get `# TODO: WARNING: LOW CONFIDENCE` comment
- Output: `automation_{run_id}.py`

### 2.6 Video Output

```
output_dir/
├── event_log.json              ← SSOT (all pipeline data)
├── PDD_YYYYMMDD_HHMMSS_xxxx.xlsx  ← PDD Excel (4 sheets)
└── automation_{run_id}.py      ← Python automation code
```

### 2.7 Gemini Prompt Structure

The prompt (`prompts/video_analysis.txt`) instructs Gemini to output JSON:
```json
{
  "steps": [{
    "num": 1, "timestamp": "MM:SS", "application": "Window title",
    "app_type": "web|desktop", "action": "Click|Input|...",
    "target": "UI element in Japanese", "value": "typed text",
    "result": "screen change", "confidence": 0.95,
    "selector_hint": "CSS selector or control name"
  }],
  "flow_phases": [{ "phase_name": "...", "step_range": [1, 5], "summary": "..." }],
  "ambiguities": [{ "step_num": 3, "description": "..." }]
}
```

Supported actions: Click, DoubleClick, RightClick, Input, Select, Navigate, Scroll, Wait, KeyShortcut, FileOpen, FileSave, DragDrop, SwitchWindow

---

## 3. Robin Pipeline (v2)

### 3.1 Workflow

```
担当者（現場）                    開発者（こちら側）
─────────────────────            ─────────────────────
1. PADで業務を録画
2. フロー編集画面で
   Ctrl+A → Ctrl+C
3. メモ帳に貼り付け
   「〇〇業務.robin」で保存
4. ファイルを送付 ──────────────→ 5. パイプライン実行
                                  6. Excel確認・調整
                                  7. PDD納品
```

### 3.2 Robin Script Acquisition (PAD Free)

PAD Free版にはエクスポート機能がないため、コピペで取得する。

1. PADを起動し、対象フローを「編集」で開く
2. `Ctrl+A`（全アクション選択）→ `Ctrl+C`
3. メモ帳に貼り付け → `〇〇業務.robin` で保存（UTF-8）

### 3.3 Execution

```bash
python -m tools.video2pdd.main --robin-file <path_to_robin> [--output-dir <dir>]
```

### 3.4 Pipeline Phases (Robin)

| Phase | Module | Description |
|-------|--------|-------------|
| 1 | `phase1_robin.py` | Robin parse + Gap detection |
| 2-3 | `phase2_describe.py` | Normalize + Japanese description + Flow phases |
| 4 | `phase3_excel.py` | Excel generation (4 sheets) |

### 3.5 Phase 1: Robin Parse
- Classifies: `ui_automation`, `web_automation`, `keyboard`, `wait`, etc.
- Extracts: target_window, target_element, click_type, input_value, url
- Gap flags: `ambiguous_element`, `coordinate_only_click`, `duplicate_action`, `complex_key_combo`
- Verification: `confirmed` (clean) or `provisional` (has gap flags)

### 3.6 Phase 2-3: Normalize + Describe
- Element alias: `"Input submit 'ログイン'"` → `「ログイン」ボタン`
- Window alias: `"Web Page 'h...'"` → `楽楽精算Webページ`
- Key description: `"{LMenu}({Tab}{Tab})"` → `Alt + Tab × 2`
- Duplicate merge: consecutive identical → `duplicate_count` + `merged_into`

---

## 4. Common Features

### 4.1 Resume Support

```bash
python -m tools.video2pdd.main --resume <path_to_event_log.json>
```

Auto-detects pipeline type (video/robin) and resumes from last completed phase.

### 4.2 Excel Output (4 Sheets)

1. **概要フロー**: Phase-level summary with window context
2. **詳細手順**: Step-by-step PDD table
   - Yellow highlight = provisional/pending review
   - Red highlight = low confidence (video pipeline, < 0.7)
   - Gray text = merged duplicate
   - Video: includes timestamp and confidence columns
3. **未解決項目**: Items needing human review
4. **実行メタデータ**: Run info, stats, phase status

### 4.3 SSOT

| Decision | Detail |
|----------|--------|
| SSOT | event_log.json (LLM output is never SSOT) |
| Japanese text | Rule-based templates = SSOT |
| Quality | Existing business replacement = 100% required |

---

## 5. Template Dictionary Extension

### Adding Video Action Types

Edit `phase2_describe.py` → `VIDEO_ACTION_JA`:

```python
VIDEO_ACTION_JA: dict[str, str] = {
    "Click": "{target}を{click_ja}する",
    "Input": "{target}に「{value}」と入力する",
    # Add new types:
    "NewAction": "{target}に対して新操作する",
}
```

### Adding Robin Element Types

Edit `phase2_describe.py` → `ELEMENT_TYPE_JA`:

```python
ELEMENT_TYPE_JA: dict[str, tuple[str, str]] = {
    "Button": ("ボタン", "「{name}」ボタン"),
    # Add new types:
    "TreeItem": ("ツリー項目", "「{name}」ツリー項目"),
}
```

### Adding Robin Action Types

Edit `phase1_robin.py` → `_classify_action()`, then `phase2_describe.py` → `_build_description()`.

---

## 6. Verification Status & Gap Flags

| Status | Meaning | Excel Display |
|--------|---------|---------------|
| `confirmed` | All data extracted cleanly | Normal row |
| `provisional` | Has gap flags, needs review | Yellow highlight |
| `pending_review` | Video pipeline: not yet reviewed | Yellow highlight |

### Robin Gap Flags

| Flag | Meaning |
|------|---------|
| `ambiguous_element` | Generic element (Div, Group) |
| `coordinate_only_click` | Pixel coordinates on generic element |
| `duplicate_action` | Same as previous action |
| `complex_key_combo` | Modifier + key combination |

### Video Gap Flags

| Flag | Meaning |
|------|---------|
| `low_confidence` | Confidence < 0.7 |
| `ambiguous_selector` | No selector_hint or unknown |
| `duplicate_action` | Consecutive identical action |

---

## 7. Key Files

| File | Purpose |
|------|---------|
| `tools/video2pdd/main.py` | CLI entry point + both pipelines |
| `tools/video2pdd/event_log.py` | SSOT schema (v3) |
| `tools/video2pdd/phase1_robin.py` | Robin parser + Gap detection |
| `tools/video2pdd/phase1_video.py` | Gemini video analysis |
| `tools/video2pdd/phase2_describe.py` | Normalize + Japanese templates |
| `tools/video2pdd/phase3_excel.py` | Excel output (4 sheets) |
| `tools/video2pdd/phase4_codegen.py` | Python code generation |
| `tools/video2pdd/prompts/video_analysis.txt` | Gemini prompt |
| `tools/video2pdd/prompts/video_analysis_audio.txt` | Gemini prompt (audio) |

---

## 8. Troubleshooting

### GEMINI_API_KEY not found
**Cause**: Set with `set` (temporary) instead of `setx` (permanent)
**Fix**: `setx GEMINI_API_KEY your_key_here` (new terminal required)

### FAILED_PRECONDITION: File not in ACTIVE state
**Cause**: (Fixed in v1.62.0+) Old wait logic didn't match SDK enum representation
**Fix**: Already fixed in phase1_video.py — waits until `"ACTIVE" in str(state).upper()`
**Context**: This bug was discovered and fixed during E2E testing (2026-02-07). The SDK's state enum representation required string-based matching instead of direct enum comparison.

### Gemini returns empty response
**Cause**: Video too long/complex, or API quota exceeded
**Fix**: Retry automatically (3 attempts). Check API key and quota.

### No action lines detected (Robin)
**Cause**: Robin file has only comments/annotations
**Fix**: Ensure the file contains actual action lines

### Too many provisional steps (Robin)
**Cause**: PAD recorder captures generic elements
**Fix**: Re-record with precise clicks, or manually resolve in Excel

### Duplicate actions
**Cause**: Recorder artifact (both pipelines)
**Fix**: `duplicate_count` + `merged_into` fields; gray rows in Excel

### Unicode encoding issues (Robin)
**Cause**: Robin file not saved as UTF-8
**Fix**: Save with UTF-8 encoding

### Resume fails with validation error
**Cause**: event_log.json was manually edited or corrupted
**Fix**: Re-run from scratch
