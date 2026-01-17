# -*- coding: utf-8 -*-
"""
OCR正解データ（Ground Truth）

手動で確認した正解データを保存
精度評価・改善のベースラインとして使用
"""

# 正解データ
GROUND_TRUTH = {
    "doc06591420260109181028.pdf": {
        "vendor_name": "刈谷市会計管理者",
        "issue_date": "20260109",  # 令和8年1月9日
        "amount": 3400,
        "invoice_number": "T5000020232106",
        "note": "愛知県証紙代金として",
    },
    "鶴舞クリニック消防打合せ駐車場代.pdf": {
        "vendor_name": "三井不動産リアルティ株式会社",
        "issue_date": "20260109",  # 2026年1月9日
        "amount": 1500,
        "invoice_number": "T8010001140514",
        "note": "三井のリパーク リパーク栄第28 クレジットカード払い",
    },
}


def get_ground_truth(filename: str) -> dict:
    """正解データを取得"""
    return GROUND_TRUTH.get(filename, {})


def has_ground_truth(filename: str) -> bool:
    """正解データがあるか確認"""
    return filename in GROUND_TRUTH
