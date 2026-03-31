# Universal OCR Skill — GPT-5.4 Vision主体設計

## Purpose
日本語帳票（請求書・領収書・建設業許可証・決算書）からフィールド値を抽出する汎用OCRスキル。
GPT-5.4 Visionをメインエンジンとし、決定論的検証で業務品質100%を担保する。

## Scope
- 対象: 日本語PDF帳票（スキャン画像 + テキスト層PDF）
- 月100枚程度、速度は問題なし
- 本番: CPU（API経由）、開発: GPU

## Non-goals
- ローカルモデルの学習・ファインチューニング
- リアルタイム処理（バッチ処理前提）
- 手書き文字認識（将来検討）

## 3層品質モデル（核心）

```
Layer 1: GPT-5.4 Vision → 候補値（raw_ja + evidence）を出す
Layer 2: 決定論的検証   → jp_norm正規化 + クロスフィールドチェック + マスタ照合
Layer 3: 人手確認      → Layer 1+2で確定できないものだけ人が見る

目標: Layer 3（人手確認）の件数を最小化する
```

## 4段階パイプライン

```
[Stage 1] PDF分類+抽出 → テキスト層判定、サンプリング検証
[Stage 2] GPT-5.4 Vision API → raw出力のみ（正規化しない）
[Stage 3] 決定論的正規化+検証 → jp_norm、クロスフィールド、マスタ照合
[Stage 4] 品質ゲート → auto_accept / quick_review / human_review
```

## Config Schema

```yaml
# scenarios/{name}/fields.yaml
scenario: receipt
fields:
  - name: vendor_name
    type: company
    required: true
  - name: issue_date
    type: date
    required: true
  - name: total_amount
    type: amount
    required: true
    critical: true
validations:
  - rule: "issue_date <= today"
    severity: WARN
```

## Key Files
| File | Purpose |
|------|---------|
| `src/ocr_universal/contracts.py` | PageContext, ValidationResult, RoutingDecision |
| `src/ocr_universal/pipeline.py` | 4段階オーケストレーター |
| `src/ocr_universal/gpt54_extractor.py` | GPT-5.4 Vision API呼び出し |
| `src/ocr_universal/jp_norm.py` | 日本語正規化（唯一の正規化パス） |
| `src/ocr_universal/cross_field_validator.py` | クロスフィールド検証 |
| `src/ocr_universal/quality_gate.py` | ルーティング判定 |
| `templates/prompt.system.txt` | GPT-5.4システムプロンプト |

## Usage

```python
from ocr_universal.pipeline import UniversalOCRPipeline

pipeline = UniversalOCRPipeline(scenario="receipt")
result = pipeline.process("path/to/receipt.pdf")

# result.routing = "auto_accept" | "quick_review" | "human_review"
# result.fields = {"vendor_name": "株式会社イシハラ", "total_amount": 12345, ...}
# result.validations = [{"field": "total_amount", "status": "PASS"}, ...]
```
