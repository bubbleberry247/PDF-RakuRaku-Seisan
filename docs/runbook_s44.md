# Runbook: Scenario 44（PDF OCR → 楽楽精算登録）

**最終更新**: 2026-01-17
**ステータス**: ドラフト

---

## 0. 参照ドキュメント

| ドキュメント | パス |
|--------------|------|
| Operating Model | `docs/operating_model.md` |
| Manual Queue SOP | `docs/manual_queue_sop.md` |
| Logging Policy | `docs/logging_policy.md` |
| Regression Criteria | `docs/regression_criteria.md` |
| 技術詳細 | `docs/44_OCR_technical.md` |

---

## 1. 目的 / 成功条件

### 1.1 目的
FAXで受信した請求書/領収書PDFを自動でOCR処理し、楽楽精算に登録する。

### 1.2 成功条件
- [ ] 自動登録が完了（失敗はmanual_queueへ退避）
- [ ] 二重登録が発生しない（冪等性保証）
- [ ] 監査可能（誰が何を処理したか追跡可能）
- [ ] SLA内に処理完了

---

## 2. 入出力

### 2.1 入力

| 環境 | パス |
|------|------|
| PROD | `\\192.168.1.251\TIC-mainSV\【個人使用フォルダ】\管理部\・瀬戸\スキャン・FAX\` |
| LOCAL | `C:\ProgramData\RK10\Robots\44PDF一般経費楽楽精算申請\data\MOCK_FAX\` |

### 2.2 出力

| 種別 | パス | 内容 |
|------|------|------|
| 処理済み | `work/processed/` | 正常完了PDF |
| 手動キュー | `work/manual_queue/` | 低信頼度/例外/失敗 |
| ログ | `logs/` | 処理ログ |
| 一時 | `work/output/` | OCR中間データ |

### 2.3 抽出項目

| 項目 | 形式 | 例 |
|------|------|-----|
| 領収書区分 | 領収書 / 請求書 | 領収書 |
| 取引日 | YYYYMMDD | 20260109 |
| 事業者登録番号 | T + 13桁 | T1234567890123 |
| 取引先名 | テキスト | 株式会社○○ |
| 金額 | 整数（円） | 1500 |

---

## 3. 実行手順

### 3.1 通常実行（一括処理）

```bash
cd "C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan\tools"

# 前処理のみ（OCRなし、回転補正・傾き補正）
python main_44_rk10.py --pre

# 一括登録（前処理 + OCR + 楽楽精算登録）
python main_44_rk10.py --run-all
```

### 3.2 dry-run（確定なしで検証）

```bash
# dry-runモード（登録せずにOCR結果を確認）
python main_44_rk10.py --run-all --dry-run
```

**確認項目**:
- OCR抽出結果の妥当性
- 信頼度スコア
- エラー/例外の有無

### 3.3 pause（確定前に停止し人が判断）

```bash
# pauseモード（各件で確認プロンプト）
python main_44_rk10.py --run-all --pause
```

### 3.4 個別ファイル処理

```bash
# 特定ファイルのみ処理
python main_44_rk10.py --file "path/to/specific.pdf"
```

---

## 4. 監視

### 4.1 収集メトリクス

| 指標 | 説明 | 閾値（暫定） |
|------|------|-------------|
| 入力件数 | 処理対象PDF数 | - |
| 成功件数 | 自動登録完了 | - |
| 手動件数 | manual_queueへ退避 | - |
| 失敗件数 | エラー終了 | - |
| 例外率 | (手動+失敗) / 入力 | > 20% でアラート |
| 処理時間 | 1件あたり秒数 | > 60秒 で調査 |

### 4.2 アラート条件

| 条件 | 対応 |
|------|------|
| 例外率 > 20% | Maintainerへ調査依頼 |
| manual_queue滞留 > 5件 | Ownerへ報告 |
| 処理時間 > 60秒/件 | パフォーマンス調査 |
| システムエラー（例外終了） | 即時Maintainer対応 |

---

## 5. 障害対応

### 5.1 一次対応（Operator）

1. **ログ確認**
   ```bash
   # 最新ログ確認
   type logs\latest.log
   ```

2. **状態確認**
   ```bash
   # 処理キュー状態
   type data\ocr_queue.json

   # manual_queue件数
   dir /b work\manual_queue\ | find /c /v ""
   ```

3. **判断**
   - 一時的なエラー → 再実行
   - 特定ファイルの問題 → manual_queueへ退避
   - システム的な問題 → 二次対応（Maintainer）へエスカレーション

### 5.2 二次対応（Maintainer）

1. **原因分析**
   - ログ解析
   - 問題ファイルの調査
   - OCRエンジンの動作確認

2. **修正**
   - コード修正
   - 設定調整
   - パターン追加

3. **回帰テスト**
   - `docs/regression_criteria.md` に従う

4. **リリース**
   - 変更をコミット
   - 本番環境への反映

---

## 6. 再実行（冪等性）

### 6.1 原則

再実行しても二重登録しないためのガードが必要。

### 6.2 二重登録防止策

| 方法 | 説明 |
|------|------|
| 処理済みファイル移動 | `processed/` へ移動済みは対象外 |
| 状態管理（queue.json） | 処理状態をJSONで管理 |
| 楽楽精算側チェック | 登録前に重複確認（TBD） |

### 6.3 再実行手順

1. **状態確認**
   ```bash
   # 処理済み/未処理の確認
   dir work\processed\
   dir work\manual_queue\
   type data\ocr_queue.json
   ```

2. **dry-run**
   ```bash
   python main_44_rk10.py --run-all --dry-run
   ```

3. **本実行**
   ```bash
   python main_44_rk10.py --run-all
   ```

---

## 7. 定期メンテナンス

### 7.1 日次

- [ ] manual_queueの処理（SOP参照）
- [ ] ログ確認（エラー/警告）

### 7.2 週次

- [ ] 処理済みファイルのアーカイブ/削除
- [ ] ログローテーション
- [ ] 精度メトリクスの確認

### 7.3 月次

- [ ] 設定ファイルのバックアップ
- [ ] 依存パッケージの更新確認
- [ ] 改善施策の検討

---

## 変更履歴

| 日付 | バージョン | 変更内容 |
|------|-----------|----------|
| 2026-01-17 | v0.1 | 初版作成 |
