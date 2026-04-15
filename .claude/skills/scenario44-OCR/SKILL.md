---
name: scenario44-OCR
description: Use when improving OCR accuracy for シナリオ44 PDF expense reports — preprocessing config, YomiToku table recognition, regression testing, confidence threshold tuning
---

# scenario44-OCR — シナリオ44 PDF OCR 精度向上版

## 目的
シナリオ44（PDF一般経費楽楽精算申請）のOCR抽出精度を上げるために、実装へ反映すべき設定・改善手順・検証手順を統一する。

このスキルは「説明だけ」で終わらせず、既存テンプレートコードへ実際に反映する前提で使う。

## 先に確認すること（必須）
1. スキルファイルが存在すること
`C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan\.claude\skills\scenario44-OCR\SKILL.md`
2. テンプレート実装が存在すること  
`C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan\external-repos\my-claude-skills\pdf-ocr\templates\pdf_preprocess.py`  
`C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan\external-repos\my-claude-skills\pdf-ocr\templates\pdf_ocr.py`

## シナリオ44 高精度プロファイル
### 前処理設定（A/Bテスト結果ベース）
- `do_deskew=True`
- `do_enhance=False`
- `do_shadow_removal=True`
- `force_4way_rotation=True`
- `skew_threshold=1.0`

補足:
- YomiToku系では「全部ON」より、最小限の前処理の方が精度が安定しやすい。
- 特に `do_enhance` は誤認識を増やすケースがあるため、初期値は `False` を維持する。

### 実装スニペット
```python
from pdf_preprocess import PDFPreprocessor

preprocessor = PDFPreprocessor(dpi=200)
result = preprocessor.preprocess(
    pdf_path=pdf_path,
    output_dir=output_dir,
    do_deskew=True,
    do_enhance=False,
    do_shadow_removal=True,
    skew_threshold=1.0,
    force_4way_rotation=True,
)
```

## 精度向上の実装手順
### 1. まずテンプレートを基準にする
- `external-repos/my-claude-skills/pdf-ocr/templates` 配下を基準実装として確認する。
- 同等機能を新規に書き直さず、既存関数へ追記・拡張する。

### 2. 抽出失敗時の診断ログを強化する
vendor/amount失敗時に最低限以下を出力する:
- `raw_text_length`
- `line_count`
- `line_info`（上部行の抜粋）
- `image_height`

目的:
- 「OCR認識不足」か「抽出ロジック不足」かを切り分ける。

### 3. 抽出ロジックを強化する
実装時は以下を優先する:
1. 金額パターンを改行・ノイズ文字混在に対応させる。
2. vendorキーワードを実データに合わせて追加する。
3. 日付は段階的フォールバックで抽出する。  
明示ラベル -> 和暦/西暦 -> `YYYY/MM/DD` -> `R7/1/9` など

### 4. カスケードOCRを導入する
1. 1段目: 軽量モードで実行
2. 2段目: 必要時のみ詳細モードで再実行

再実行条件の目安:
- `vendor_name` が空
- `amount == 0`
- `raw_text_length < 100`

### 5. ファイル名フォールバックを維持する
OCR未抽出時のみ、ファイル名から `date/amount/vendor` を補完する。  
ただしOCR値を無条件に上書きしない。差分が大きい場合はログで可視化する。

## 検証手順（シナリオ44）
### dry-run
```bash
cd "C:\ProgramData\RK10\Robots\44PDF一般経費楽楽精算申請\tools"
python main_44_rk10.py --run-all --dry-run
```

### 前処理のみ
```bash
cd "C:\ProgramData\RK10\Robots\44PDF一般経費楽楽精算申請\tools"
python main_44_rk10.py --pre
```

### 検証観点
- vendor抽出成功率
- amount抽出成功率
- 日付抽出成功率
- 失敗ケースのログ分類（認識不足/ロジック不足）

## 受け入れ基準（最低ライン）
- 失敗PDFで原因分類ログが必ず出ること
- 同一サンプル再実行で結果が再現すること
- `--dry-run` で致命エラーなく完走すること

## 一次ソース
- `C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan\docs\KNOWLEDGE_OCR_PREPROCESSING.md`
- `C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan\docs\44_OCR_technical.md`
- `C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan\plans\decisions\projects\pdf-ocr.md`
- `C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan\external-repos\my-claude-skills\pdf-ocr\templates\pdf_preprocess.py`
- `C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan\external-repos\my-claude-skills\pdf-ocr\templates\pdf_ocr.py`

---

## Gotchas
- `do_enhance=True` は逆効果のケースあり。初期値 `False` を維持すること
- 信頼度閾値でスキップ → 他ファイルで金額欠損リグレッション実績あり（Fix 5事件）— 閾値採用禁止
- bbox座標アプローチ → -5件の金額リグレッション実績あり（アプローチ自体を採用禁止）
- OCRパターン変更後は必ず全テストケース（ALL-N）のスコアを変更前後で比較すること
- スコアが1件でも悪化したら「他は改善した」で押し通さない — 原因特定してから適用
