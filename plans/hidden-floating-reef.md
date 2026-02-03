# Plan: 教師データ活用による OCR精度向上

## Current（現状）
- TXTファイル84件（PDF73件とペア72件、TXTのみ12件、PDFのみ1件）
- 各TXTに正解値: vendor（支払先）、date（支払予定日）、amount（合計金額）
- 現テスト `test_regression_v2.py` は **amountのみ** 判定。vendor/dateは未評価
- 最新結果: OK=59, NG=13, SKIP=1（amount一致率 82%）

## Problem（困りごと）
1. vendor/dateの正解率が不明（測定していない）
2. NGの根本原因が分類できていない（OCR読取失敗 vs パース失敗 vs テスト期待値問題）
3. 修正のたびに全73件OCR再実行（約30分）が必要

## Target（狙う状態）
- 3項目（vendor/date/amount）すべての正解率を定量測定
- NG件のみ再実行で高速に検証
- NG原因の自動分類で対策の優先順位付け

---

## 実装計画

### Step 1: テストスクリプト v3 作成
**ファイル**: `scratchpad/test_regression_v3.py`

#### 1a. TXTパーサー改善
- エンコーディング: utf-8-sig → utf-8 → cp932 のフォールバック
- 正解値フィールド追加:
  - `vendor`: 支払先タブ区切り値
  - `date`: 支払予定日 → YYYYMMDD
  - `amount`: 「合計」の次行

#### 1b. 3項目評価ロジック
| 項目 | 照合方法 | 理由 |
|------|---------|------|
| amount | 完全一致 | 金額は1円の差も許容不可 |
| date | 完全一致（YYYYMMDD） | 日付も完全一致が必須 |
| vendor | **ファジー一致** | TXT=`NTTビジネスソリューションズ㈱`、OCR=`NTTビジネスソリューションズ株式会社` を同一と判定 |

**vendor照合ルール（優先順）**:
1. 完全一致
2. 法人格正規化後に一致（㈱→株式会社、㈲→有限会社、(株)→株式会社、全角⇔半角）
3. 法人格除去後に一致（「株式会社」「有限会社」「合同会社」等を除去して比較）
4. 片方が他方を含む（部分一致、短い方が3文字以上）

#### 1c. 出力形式
```
[OK]   filename.pdf  amount=OK  date=OK  vendor=OK
[NG]   filename.pdf  amount=NG(ocr=22286,exp=40000)  date=OK  vendor=PARTIAL(ocr=名古屋電気学園,exp=名古屋電気学園愛名会 事務局長 土橋繁樹)
[SKIP] filename.pdf  (TXTなし)
```

**サマリ出力**:
```
=== RESULT ===
Total: 72 (SKIP: 1)
         OK    NG    Rate
amount   59    13    82%
date     65     7    90%
vendor   55    17    76%
ALL-3    50    22    69%

=== NG BREAKDOWN ===
amount_ng: [list]
date_ng: [list]
vendor_ng: [list]
```

#### 1d. OCR結果キャッシュ（JSON）
- 初回: 全件OCR実行 → `scratchpad/ocr_cache.json` に保存
  ```json
  {
    "filename.pdf": {
      "vendor_name": "...",
      "issue_date": "YYYYMMDD",
      "amount": 12345,
      "confidence": 0.85,
      "raw_text": "...",
      "timestamp": "2026-01-29T..."
    }
  }
  ```
- 2回目以降: `--use-cache` でキャッシュ利用
- NG件のみ再実行: `--rerun-ng` で前回NGのみOCR再実行

#### 1e. NG原因自動分類
各NG項目に原因タグを付与:

**amount NG原因**:
| タグ | 条件 | 対策方向 |
|------|------|---------|
| `OCR_ZERO` | OCR amount=0 | OCR精度/パターン追加 |
| `TAX_DIFF` | OCR ≈ expected×0.909 or ×1.1 | 税抜/税込の仕様問題 |
| `FILENAME_OVERRIDE` | OCR金額≠filename金額=最終値 | ファイル名パースの問題 |
| `MULTI_PDF` | TXT「請求書N」にN≥2 | テスト期待値問題（合算） |
| `DOT_MATRIX` | confidence < 0.35 | ドットマトリクス/低品質 |
| `OTHER` | 上記に該当しない | 個別調査 |

**date NG原因**:
| タグ | 条件 | 対策方向 |
|------|------|---------|
| `EMPTY` | OCR date='' | 日付パターン追加 |
| `INVOICE_VS_DUE` | OCR=請求日, TXT=支払予定日 | 優先ロジック見直し |
| `WRONG_DATE` | 完全に別の日付 | パース誤り調査 |

**vendor NG原因**:
| タグ | 条件 | 対策方向 |
|------|------|---------|
| `EMPTY` | OCR vendor='' | vendor抽出パターン追加 |
| `LEGAL_ENTITY_DIFF` | 法人格除去後一致 | 許容レベル（実質OK） |
| `PARTIAL_MATCH` | 部分一致のみ | 抽出範囲の問題 |
| `WRONG` | 完全不一致 | 誤抽出 |

### Step 2: 初回ベースライン測定
- v3テストを全件実行し、3項目のベースライン正解率を記録
- `scratchpad/ocr_cache.json` にキャッシュ保存
- NG原因分類をサマリ出力

### Step 3: NG原因別の対策優先度決定
ベースライン結果を見て、以下の順で改善:
1. **即対応可能**（コード修正で直る）: パターン追加、パース修正
2. **仕様判断が必要**: 税抜/税込、支払予定日vs請求日
3. **テスト期待値の問題**: 合算PDF、個人分切り出し
4. **難度高**: OCR自体が読めない（DPI/エンジン問題）

### Step 4: 改善→再測定サイクル
```
改善実施 → --rerun-ng で該当件のみ再実行 → 正解率変化を確認
                                          ↓ 改善確認後
                                    全件実行でリグレッション確認
```

---

## 対象ファイル
| ファイル | 操作 |
|---------|------|
| `scratchpad/test_regression_v3.py` | **新規作成** |
| `scratchpad/ocr_cache.json` | **新規作成**（自動生成） |
| `C:\ProgramData\RK10\Robots\44PDF一般経費楽楽精算申請\tools\pdf_ocr_easyocr.py` | 改善時に修正 |

## 検証方法
1. v3テスト初回実行（全件OCR + キャッシュ生成）→ 3項目のベースライン正解率を測定
2. `--use-cache` でキャッシュからの照合のみ実行（OCRスキップ）→ 数秒で完了確認
3. `--rerun-ng` でNG件のみ再実行 → 該当件のみOCR処理確認
4. NG原因自動分類の出力が妥当か確認

## 運用制約
- OCR処理: GPU無し環境で1件約20-30秒
- `--rerun-ng` で13件なら約5-7分
- `--use-cache` なら照合のみで数秒
