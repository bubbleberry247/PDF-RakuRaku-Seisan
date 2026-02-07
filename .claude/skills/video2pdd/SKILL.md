# Video2PDD Skill

## Overview
Power Automate Desktop (PAD) Robin script → PDD (Process Design Document) Excel generator.
PAD recorder output from copy-paste → structured Japanese step descriptions → 4-sheet Excel.

## Prerequisites
- Python 3.11+
- openpyxl installed
- Power Automate Desktop (Free version is sufficient)

---

## 1. Workflow Overview

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

## 2. Robin Script Acquisition (PAD Free)

PAD Free版にはエクスポート機能がないため、コピペで取得する。

### 手順（担当者向け）

1. PADを起動し、対象フローを「編集」で開く
2. フローエディター内で `Ctrl+A`（全アクション選択）
3. `Ctrl+C`（コピー）
4. メモ帳を開いて `Ctrl+V`（貼り付け）
5. ファイル名: `〇〇業務.robin` で保存（UTF-8）
6. メール/チャットで送付

### Robin Script Format

```robin
# レコーダーを使用した自動生成アクションの開始
@@source: 'Recorder'
UIAutomation.PressButton Button: appmask['TaskBar']['Button \'Edge\'']
@@source: 'Recorder'
WebAutomation.LaunchEdge.AttachToEdgeByUrl TabUrl: 'https://example.com'
@@source: 'Recorder'
WebAutomation.Click.Click BrowserInstance: Browser Control: appmask['Web Page']['Input text \'username\''] ClickType: WebAutomation.ClickType.LeftClick
# レコーダーを使用した自動生成アクションの終了
```

Key patterns:
- `#` = Comment (skipped)
- `@@source` = Source annotation (skipped)
- `UIAutomation.*` = Desktop UI actions
- `WebAutomation.*` = Browser actions
- `MouseAndKeyboard.*` = Keyboard/mouse actions
- `WAIT N` = Wait N seconds
- `appmask['Window']['Element']` = Target selector

## 3. Pipeline Execution

### New Run

```bash
python -m tools.video2pdd.main --robin-file <path_to_robin> [--output-dir <dir>]
```

### Resume (after interruption)

```bash
python -m tools.video2pdd.main --resume <path_to_event_log.json>
```

### Stop After Specific Phase

```bash
python -m tools.video2pdd.main --robin-file <file> --stop-after phase1
# Options: phase1, phase2, phase3
```

### Output

```
output_dir/
├── event_log.json          ← SSOT (all pipeline data)
└── PDD_YYYYMMDD_HHMMSS_xxxx.xlsx  ← PDD Excel (4 sheets)
```

## 4. Pipeline Phases

| Phase | Module | Description |
|-------|--------|-------------|
| 1 | `phase1_robin.py` | Robin parse + Gap detection |
| 2-3 | `phase2_describe.py` | Normalize + Japanese description + Flow phases |
| 4 | `phase3_excel.py` | Excel generation (4 sheets) |

### Phase 1: Robin Parse
- Classifies actions: `ui_automation`, `web_automation`, `keyboard`, `wait`, etc.
- Extracts: target_window, target_element, click_type, input_value, url
- Gap detection: `ambiguous_element`, `coordinate_only_click`, `duplicate_action`, `complex_key_combo`
- Verification: `confirmed` (clean) or `provisional` (has gap flags)

### Phase 2-3: Normalize + Describe
- Element alias: `"Input submit 'ログイン'"` → `「ログイン」ボタン`
- Window alias: `"Web Page 'h...'"` → `楽楽精算Webページ`
- Key description: `"{LMenu}({Tab}{Tab})"` → `Alt + Tab × 2`
- Duplicate merge: consecutive identical actions → `duplicate_count` + `merged_into`
- Flow phases: window context grouping

### Phase 4: Excel Output
4 sheets:
1. **概要フロー**: Phase-level summary with window context
2. **詳細手順**: Step-by-step PDD (yellow = provisional, gray = merged)
3. **未解決項目**: Items needing human review
4. **実行メタデータ**: Run info, stats, phase status

## 5. Template Dictionary Extension

### Adding Element Types

Edit `phase2_describe.py` → `ELEMENT_TYPE_JA`:

```python
ELEMENT_TYPE_JA: dict[str, tuple[str, str]] = {
    # (ja_label, template_with_{name})
    "Button": ("ボタン", "「{name}」ボタン"),
    "Input submit": ("ボタン", "「{name}」ボタン"),
    "Input text": ("テキスト入力欄", "「{name}」テキスト入力欄"),
    "Div": ("エリア", "{name}エリア"),
    # Add new types here:
    "TreeItem": ("ツリー項目", "「{name}」ツリー項目"),
}
```

### Adding Action Types

Edit `phase1_robin.py` → `_classify_action()`:

```python
if cmd.startswith("UIAutomation."):
    if "PressButton" in cmd:
        return ACT_UI, "press_button"
    if "Click" in cmd:
        return ACT_UI, "click"
    # Add new action types here:
    if "ExpandCollapse" in cmd:
        return ACT_UI, "expand_collapse"
```

Then add description template in `phase2_describe.py` → `_build_description()`.

### Adding Key Mappings

Edit `phase2_describe.py` → `KEY_DISPLAY`:

```python
KEY_DISPLAY: dict[str, str] = {
    "{lmenu}": "Alt",
    "{tab}": "Tab",
    # Add new keys here:
    "{numlock}": "NumLock",
}
```

## 6. Design Decisions (SSOT)

| Decision | Detail |
|----------|--------|
| SSOT | event_log.json (LLM output is never SSOT) |
| Japanese text | Rule-based templates = SSOT |
| Screenshots | Not required for delivery (work reference only) |
| OBS video | Not needed (Robin has no timestamps for sync) |
| ControlRepository | Not needed (PAD Free has no export) |
| Quality | Existing business replacement = 100% required |

## 7. Verification Status

| Status | Meaning | Excel Display |
|--------|---------|---------------|
| `confirmed` | All data extracted cleanly | Normal row |
| `provisional` | Has gap flags, needs review | Yellow highlight |

### Gap Flags

| Flag | Meaning | Action |
|------|---------|--------|
| `ambiguous_element` | Generic element (Div, Group, etc.) | Human review: what element is this? |
| `coordinate_only_click` | Click uses pixel coordinates on generic element | Fragile: will break on layout change |
| `duplicate_action` | Same as previous action | Likely recorder artifact, may be removable |
| `complex_key_combo` | Modifier + key combination | Human review: describe shortcut purpose |

## 8. Key Files

| File | Purpose | Lines |
|------|---------|-------|
| `tools/video2pdd/main.py` | CLI entry point + pipeline | ~270 |
| `tools/video2pdd/event_log.py` | SSOT schema (v2) | ~285 |
| `tools/video2pdd/phase1_robin.py` | Robin parser + Gap detection | ~310 |
| `tools/video2pdd/phase2_describe.py` | Normalize + Japanese templates | ~310 |
| `tools/video2pdd/phase3_excel.py` | Excel output (4 sheets) | ~280 |
| `tools/video2pdd/test_data/rakuraku_login.robin` | Test data (login flow) | 32 |

## 9. Troubleshooting

### No action lines detected
**Cause**: Robin file has only comments/annotations
**Fix**: Ensure the file contains actual action lines (not just `#` and `@@source`)

### Too many provisional steps
**Cause**: PAD recorder captures generic elements (Div, Group) instead of specific ones
**Fix**: Have user re-record with more precise clicks, or manually resolve in Excel

### Duplicate actions
**Cause**: PAD recorder sometimes records multiple clicks for one user action
**Fix**: `duplicate_count` and `merged_into` fields identify these; gray rows in Excel

### Unicode encoding issues
**Cause**: Robin file not saved as UTF-8
**Fix**: Ensure Notepad saves with UTF-8 encoding (File → Save As → Encoding: UTF-8)

### Resume fails with validation error
**Cause**: event_log.json was manually edited or corrupted
**Fix**: Re-run from scratch with `--robin-file` instead of `--resume`
