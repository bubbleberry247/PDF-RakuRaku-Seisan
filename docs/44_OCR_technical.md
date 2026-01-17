# 44PDF一般経費楽楽精算申請 - 技術ドキュメント

**最終更新**: 2026-01-17
**ステータス**: 開発中（OCR精度86.5%達成）

---

## 1. 概要

### 1.1 目的
FAXで受信した請求書/領収書PDFを自動でOCR処理し、楽楽精算に登録するRPAシナリオ。

### 1.2 フォルダパス
| 環境 | パス |
|------|------|
| PROD | `\\192.168.1.251\TIC-mainSV\【個人使用フォルダ】\管理部\・瀬戸\スキャン・FAX\` |
| LOCAL | `C:\ProgramData\RK10\Robots\44PDF一般経費楽楽精算申請\data\MOCK_FAX\` |

### 1.3 抽出目標項目
| 項目 | 例 | 備考 |
|------|-----|------|
| 領収書区分 | 領収書 / 請求書 | ラジオボタン選択 |
| 取引日 | 20260109 | YYYYMMDD形式 |
| 事業者登録番号 | T1234567890123 | T + 13桁数字 |
| 取引先名 | 株式会社○○ | ベンダー名 |
| 金額 | 1500 | 整数（円） |

---

## 2. 現在の精度

### 2.1 テスト結果（74件サンプル）
| 指標 | 数値 |
|------|------|
| 成功件数 | 64件 |
| 失敗件数 | 10件 |
| **精度** | **86.5%** |

### 2.2 エンジン別内訳
| OCRエンジン | 成功率 | 備考 |
|------------|--------|------|
| YomiToku単独成功 | 約60% | 高品質画像で高精度 |
| Adobe PDF Services（フォールバック） | 約25% | YomiToku失敗時に補完 |
| 両方失敗 | 約14% | 手動対応必要 |

### 2.3 失敗パターン
| 失敗原因 | 件数 | 対策案 |
|---------|------|--------|
| 手書き金額 | 3件 | 手書きOCR強化または手動入力 |
| 極端な傾き（>30度） | 2件 | 2回前処理で対応済み |
| 低画質・かすれ | 2件 | 画像強調パラメータ調整 |
| 特殊レイアウト | 2件 | パターン追加 |
| 180度反転検出失敗 | 1件 | スコア閾値調整 |

---

## 3. 前処理フロー

```
入力PDF
    │
    ▼
[ステップ1] 回転検出・補正
    │  ├─ Tesseract OSD（向き検出）
    │  ├─ スコアベース検出（4方向評価）
    │  └─ 横長PDF判定（90°/270°選択）
    │
    ▼
[ステップ2] 傾き検出・補正
    │  ├─ Hough変換（直線検出）
    │  └─ PCA（主成分分析）
    │
    ▼
[ステップ3] 画質改善（条件付き）
    │  ├─ 影除去
    │  ├─ コントラスト強調
    │  └─ アップスケール
    │
    ▼
[ステップ4] OCR実行
    │  ├─ YomiToku（ローカルOCR、優先）
    │  └─ Adobe PDF Services（フォールバック）
    │
    ▼
[ステップ5] 後処理
    │  ├─ OCR誤認識補正（辞書ベース）
    │  └─ データ抽出（正規表現パターン）
    │
    ▼
抽出結果
```

---

## 4. 回転検出・補正

### 4.1 検出手法

**手法A: Tesseract OSD**
```python
osd = pytesseract.image_to_osd(gray, output_type=pytesseract.Output.DICT)
rotate = osd.get('rotate', 0)  # 0, 90, 180, 270
confidence = osd.get('orientation_conf', 0.0)
```
- 信頼度閾値: `confidence >= 5.0` で採用

**手法B: スコアベース検出**
```
total_score = edge_ratio × 0.3
            + position_score × 0.2
            + projection_score × 0.3
            + hough_score × 0.2
```

### 4.2 組み合わせ判定ロジック
```python
if osd_conf >= 5.0:
    return osd_angle  # OSD優先
else:
    if max(scores) - scores[0] < 0.05:
        return 0  # 差が小さいので回転しない
    return score_best_angle
```

---

## 5. 傾き検出・補正

### 5.1 検出手法
- **Hough変換**: 直線検出ベース
- **PCA**: 主成分分析ベース
- 両手法の差が5度未満なら平均、それ以外はHough優先

### 5.2 極端傾き対応
```python
if abs(skew_angle) > 30:
    # 補正後に再度前処理を実行（2回前処理）
    result = preprocess(preprocessed_image)
```

---

## 6. OCR実行

### 6.1 エンジン構成
| エンジン | 種別 | 特徴 |
|---------|------|------|
| YomiToku | ローカル | 日本語特化、縦書き対応 |
| Adobe PDF Services | クラウド | 高精度、有料API |

### 6.2 フォールバック戦略
```python
CONFIDENCE_THRESHOLD = 0.40

result = yomitoku.process_pdf(pdf_path)
if evaluate_confidence(result) < CONFIDENCE_THRESHOLD:
    result = adobe_ocr.process_pdf(pdf_path)
```

### 6.3 信頼度計算
| 項目 | スコア |
|------|--------|
| 金額取得 | +0.30〜0.45 |
| 日付妥当 | +0.20 |
| 取引先名取得 | +0.20 |
| 事業者登録番号 | +0.15 |

---

## 7. 後処理

### 7.1 OCR誤認識補正辞書
```python
YEAR_CORRECTIONS = {'2006年': '2026年', '2016年': '2026年'}
OCR_CORRECTIONS = {'三井不勧産': '三井不動産', 'セリァ': 'セリア'}
CJK_NORMALIZATIONS = {'⽇': '日', '⽉': '月'}
```

### 7.2 金額抽出パターン（優先度付き）
```python
amount_patterns_priority = [
    (r'(?:合計金額|ご請求金額)[:\s：]*[¥\\￥]?\s*([\d,]+)', 10),
    (r'合計[:\s：]*[¥\\￥]?\s*([\d,]+)', 8),
    (r'駐車料金[:\s：]*\s*([\d,]+)', 7),
    (r'[¥\\￥]\s*([\d,]+)', 5),
]
```

---

## 8. ファイル構成

### 8.1 主要ファイル
| ファイル | 役割 |
|---------|------|
| `tools/main_44_rk10.py` | RK10連携CLI |
| `tools/pdf_preprocess.py` | PDF前処理 |
| `tools/pdf_rotation_detect.py` | 回転方向検出 |
| `tools/pdf_ocr_smart.py` | スマートOCR処理 |
| `tools/pdf_ocr_yomitoku.py` | YomiToku OCR |
| `tools/pdf_ocr.py` | Adobe PDF Services OCR |
| `tools/rakuraku_upload.py` | 楽楽精算アップロード |

### 8.2 設定ファイル
| ファイル | 内容 |
|---------|------|
| `config/RK10_config_LOCAL.xlsx` | 楽楽精算URL・認証情報 |

### 8.3 データフォルダ
| フォルダ | 内容 |
|---------|------|
| `data/MOCK_FAX/` | テスト用PDF |
| `data/ocr_queue.json` | OCR処理キュー |

---

## 9. 実行コマンド

### 9.1 OCR前処理
```bash
cd "C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan\tools"
python main_44_rk10.py --pre
```

### 9.2 楽楽精算一括登録
```bash
python main_44_rk10.py --run-all
```

### 9.3 個別テスト
```bash
python pdf_ocr_yomitoku.py "path/to/file.pdf" --lite
python pdf_rotation_detect.py
```

---

## 10. 楽楽精算関連

### 10.1 URL
```
https://rsatonality.rakurakuseisan.jp/rHqny3DOsIa/
```

### 10.2 セレクタ修正履歴
- 確定ボタン: `button.kakuteiEbook` → `button.accesskeyOk`
- ダイアログOK: `page.get_by_role("button", name="OK")`

---

## 11. 既知の課題

### 11.1 改善が必要な点
- **手書き対応**: 手書き金額・但し書きの認識精度
- **処理速度**: GPU活用による高速化（現在1件30秒）
- **極端傾き**: 45度付近の傾きと回転の区別

### 11.2 推奨される改善方向
1. 深層学習モデルの活用（向き検出、レイアウト解析）
2. 前処理の適応的実行（品質に応じた処理選択）
3. フィードバックループ（OCR結果を前処理パラメータに反映）

---

## 12. 依存パッケージ

```
PyMuPDF (fitz) - PDF処理
OpenCV (cv2) - 画像処理
NumPy - 数値計算
Pillow - 画像フォーマット変換
pytesseract - Tesseract OSD
YomiToku - 日本語ローカルOCR
```
