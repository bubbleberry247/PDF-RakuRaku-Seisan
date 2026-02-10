# PDF OCR Decisions

## 2026-02-08

### [CODE] Gemini マルチモーダルOCR検証レイヤー追加

**背景**: OCR精度86.5%（74サンプル）。ボトルネックは取引先名抽出（65-75%）。
LayerXの記事（2026/01/14）で、OCRテキスト+元画像→LLMで80%→95%改善を報告。

**アーキテクチャ**: LLM-as-Validator（条件付き検証）
- 高信頼度(≥0.40) → regexのみ（コスト0）
- 低信頼度 → Gemini multimodal検証 → 差分照合

**実装**:
- `tools/pdf_ocr_gemini.py` — GeminiOCRValidator（API key + Vertex AI両対応）
- `tools/prompts/ocr_multimodal_extract.txt` — マルチモーダル抽出プロンプト
- `tools/prompts/ocr_reconcile.txt` — 差分照合プロンプト
- `tools/pdf_ocr_smart.py` L570-611 — LLM検証をAdobe fallbackの前に挿入

**認証**:
- Option 1: GEMINI_API_KEY env var → Generative Language API
- Option 2: gcloud ADC → Vertex AI endpoint (robotic-catwalk-464100-m3)
- Generative Language APIはOAuth非対応（APIキーのみ）。Gemini CLIは内部endpoint使用。

**テスト結果（10件、画像のみ、OCRテキストなし）**:
| フィールド | Gemini結果 | 現行regex参考値 |
|-----------|-----------|----------------|
| vendor_name | 9/10 (90%) | ~65-75% |
| issue_date | 9/10 (90%) | ~90%+ |
| amount | 8/10 (80%) | ~95%+ |
| avg latency | 7.4s | 3-6s |

**エラー分析**:
- モノタロウ: Geminiが正式英語名「MonotaRO」返却（vendor_nameはfill-emptyで補完可能）
- 安城印刷: 税抜8,250 vs 税込13,750（プロンプト改善余地あり）
- アマゾン: 発送日vs請求日の曖昧性

**結論**: fill-empty戦略が正解。Geminiはvendor補完に特化、amountはregex維持。

**GCP API有効化**:
- `generativelanguage.googleapis.com` — Enabled
- `aiplatform.googleapis.com` — Enabled (Vertex AI)
- Project: robotic-catwalk-464100-m3

**次のステップ**:
- 74件フル回帰テスト（regex-only vs Gemini-only vs 統合）
- OCRテキスト併用テスト（画像+OCRテキストで精度向上確認）
- プロンプトチューニング（税込金額の優先、vendor正式名称指示）

### [PROCESS] 客先PCではGemini API不使用（API課金作業禁止）

**制約**: 客先PCではGemini等の外部API課金が発生する処理を実行しない。
**開発環境**: 検証・ベンチマーク目的でのGemini使用はOK。

**本番パイプラインへの影響**:
- `pdf_ocr_smart.py`: `LLM_ENABLED = False`（客先では常にOFF）
- `pdf_ocr_gemini.py`: 開発環境専用（客先にはデプロイしない）
- プロンプトファイル: 開発資産として保持

**Gemini不要で本番採用する部分**:
- インボイス番号誤読補正ロジック（`T+13桁`バリデーション + `7→T`等の補正）
- fill-empty マージ戦略（regexが空の場合のみ別ソースで補完するパターン）
