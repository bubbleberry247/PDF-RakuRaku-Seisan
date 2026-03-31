---
name: ocr
description: PDFファイルからOCRでデータ抽出する。「OCRして」「/ocr PDFパス」「このPDFを読んで」で使用。領収書・請求書・建設業許可証・決算書に対応。GPT-4o Vision + jp_norm後処理で高精度抽出。
---

# ocr-universal — 汎用OCR（GPT-4o Vision主体）

## 基本コマンド

```bash
# APIキーをファイルから読み込んで実行
OPENAI_API_KEY=$(cat "C:/ProgramData/RK10/credentials/openai_api_key.txt" | tr -d '\r\n') \
python "C:/ProgramData/RK10/Tools/ocr-best/cli.py" --pdf "<PDFパス>"
```

### オプション

| オプション | 説明 |
|---|---|
| `--pdf <パス>` | **必須**。対象PDFのフルパス |
| `--out-json <パス>` | 結果をJSONファイルに書き出す |
| `--scenario <名前>` | シナリオ名（default: receipt）。receipt/invoice/permit |
| `--model <モデル>` | Vision model（default: gpt-4o） |
| `--offline` | オフラインモード（YomiTokuフォールバック） |

### シナリオ別

```bash
# 領収書（シナリオ44）
--scenario receipt

# 請求書（シナリオ12&13）
--scenario invoice

# 建設業許可証
--scenario permit
```

## 出力形式

```json
{
  "vendor_name": "ニトリ",
  "issue_date": "20260108",
  "amount": 32980,
  "invoice_number": "2339903686515",
  "confidence": 1.0,
  "success": true,
  "requires_manual": false,
  "missing_fields": [],
  "source_pdf": "C:\\path\\to\\receipt.pdf",
  "routing": "auto_accept",
  "api_cost_usd": 0.022,
  "engine": "ocr-universal"
}
```

## 精度実績

| シナリオ | 精度 | 金額抽出率 | コスト |
|---------|------|----------|--------|
| 領収書（44） | **90%** | **100%** | $0.025/枚 |
| 許可証 | **100%** | - | $0.030/枚 |
| 請求書（12&13） | 40-80% | **100%** | $0.050/枚 |

## 前提条件

| 条件 | 内容 |
|------|------|
| APIキー | `OPENAI_API_KEY` 環境変数 or `C:\ProgramData\RK10\credentials\openai_api_key.txt` |
| Python | `pip install openai pymupdf pyyaml` |
| ネット | 必須（オフライン時は `--offline` でYomiTokuフォールバック） |

## 3層品質モデル

```
Layer 1: GPT-4o Vision → 候補値（raw_ja）を出す
Layer 2: jp_norm + 検証 → 正規化 + クロスフィールドチェック
Layer 3: 品質ゲート → auto_accept / quick_review / human_review
```

## jp_norm 対応パターン

| 入力 | 正規化後 |
|------|---------|
| `令和7年3月15日` | `2025-03-15` |
| `25年12月24日` | `2025-12-24` |
| `2025年12月ご請求分` | `2025-12-01` |
| `￥108,278-` | `108278` |
| `壱万二千三百円` | `12300` |
| `㈱イシハラ` | `株式会社イシハラ` |

## 新シナリオ追加

`scenarios/{name}/fields.yaml` を1つ作るだけ:

```yaml
scenario: new_doc
fields:
  - name: vendor_name
    type: company
    required: true
  - name: total_amount
    type: amount
    required: true
    critical: true
```

## Key Files

| File | Path |
|------|------|
| CLI | `C:\ProgramData\RK10\Tools\ocr-best\cli.py` |
| パイプライン | `.claude/skills/ocr-universal/src/ocr_universal/pipeline.py` |
| 正規化 | `.claude/skills/ocr-universal/src/ocr_universal/jp_norm.py` |
| 品質ゲート | `.claude/skills/ocr-universal/src/ocr_universal/quality_gate.py` |
| プロンプト | `.claude/skills/ocr-universal/templates/prompt.system.txt` |
| シナリオ設定 | `.claude/skills/ocr-universal/scenarios/` |
