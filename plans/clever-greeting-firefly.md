# 郵送PDF処理 他部署対応拡張プラン

## 背景

### 現状
- `eisei_pdf_processor.py` は営繕営業部（L列117-124行）のみ対応
- 他部署（管理部等）のPDFも処理対象だが未対応

### 調査結果：Excelの構造
| エリア | 電話番号列 | 金額書込列 | 行範囲 |
|-------|-----------|-----------|-------|
| 一般部署 | B列(2) | R列(18) | 5-53 |
| 営繕営業部 | L列(12) | R列(18) | 117-124 |

**重要**: 両エリアとも **R列に金額を書き込む**（共通）

---

## 設計方針

### アプローチ: 統合スキャン方式
PDFから抽出した電話番号を、Excel内の全電話番号（B列+L列）と照合し、マッチした行のR列に書き込む。

**利点**:
- 部署を自動判定（引数不要）
- 1つのPDFで複数部署の電話番号があっても対応可能
- コード変更が最小限

---

## 実装計画

### 変更ファイル
- `C:\ProgramData\RK10\Robots\51&52ソフトバンク部門集計楽楽精算申請\tools\eisei_pdf_processor.py`

### 変更内容

#### 1. クラス定数の追加
```python
# Excel構造定義（複数エリア対応）
PHONE_AREAS = [
    {
        'name': '一般部署',
        'phone_col': 2,    # B列
        'amount_col': 18,  # R列
        'start_row': 5,
        'end_row': 53,
    },
    {
        'name': '営繕営業部',
        'phone_col': 12,   # L列
        'amount_col': 18,  # R列
        'start_row': 117,
        'end_row': 124,
    },
]
```

#### 2. `get_excel_phone_mapping()` の修正
現在: L列117-125行のみスキャン
変更後: 全エリア（B列5-53行 + L列117-124行）をスキャン

```python
def get_excel_phone_mapping(self, sheet_name: str) -> Dict[str, dict]:
    """ExcelからすべてのエリアのB列・L列電話番号マッピングを取得

    Returns:
        {
            '080-7933-0294': {'row': 117, 'phone_col': 12, 'amount_col': 18, 'area': '営繕営業部'},
            '070-1249-8994': {'row': 5, 'phone_col': 2, 'amount_col': 18, 'area': '一般部署'},
            ...
        }
    """
    mapping = {}
    for area in self.PHONE_AREAS:
        for row in range(area['start_row'], area['end_row'] + 1):
            phone = ws.cell(row=row, column=area['phone_col']).value
            if phone:
                mapping[normalize_phone(phone)] = {
                    'row': row,
                    'phone_col': area['phone_col'],
                    'amount_col': area['amount_col'],
                    'area': area['name'],
                }
    return mapping
```

#### 3. `write_to_excel()` の修正
現在: 固定のAMOUNT_COL（R列）に書き込み
変更後: マッピング情報のamount_col（常にR列だが将来拡張可能）を使用

---

## 検証計画

### テストケース
1. **営繕営業部PDF（46167）**: L列117-124行にマッチ → R列書き込み
2. **管理部/他部署PDF（213278）**: B列5-53行にマッチ → R列書き込み
3. **混合PDF（仮）**: 両エリアにマッチ → 両方のR列に書き込み

### 検証コマンド
```bash
# ドライランで確認
python eisei_pdf_processor.py --pdf <PDF> --month 2025-12 --dry-run

# 期待出力
# - 一般部署: 070-1249-8994 → Row 5, R列
# - 営繕営業部: 080-7933-0294 → Row 117, R列
```

---

## リスク・注意点

1. **電話番号正規化**: ハイフンの有無で不一致にならないよう注意
2. **重複電話番号**: 同一番号が複数行にあった場合の挙動（最初にマッチした行優先）
3. **シート作成**: 2025.12シートが未作成の場合のエラーハンドリング

---

## 作業順序

1. `PHONE_AREAS` 定数を追加
2. `get_excel_phone_mapping()` を修正（全エリアスキャン）
3. `write_to_excel()` を修正（マッピング情報活用）
4. ドライランテスト
5. 実PDF（可能なら）で検証
