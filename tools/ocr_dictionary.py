# -*- coding: utf-8 -*-
"""
OCR誤認識補正辞書

OCRで頻出する誤認識パターンを補正するための辞書
- 会社名の誤認識補正
- CJK互換漢字の正規化
- 数字・記号の正規化

Usage:
    from ocr_dictionary import correct_ocr_text, correct_numeric_string

    text = correct_ocr_text(raw_text)
    amount_str = correct_numeric_string(amount_str)

Created: 2026-01-14
"""

# 会社名の誤認識補正
OCR_CORRECTIONS = {
    # 漢字の誤認識
    '三井不勧産': '三井不動産',
    '三井不勤産': '三井不動産',
    '三菱不動産': '三井不動産',  # 三菱→三井の誤認識
    '三菱UFJ銀': '三菱UFJ銀行',
    '三井住友銀': '三井住友銀行',
    'みずほ銀': 'みずほ銀行',

    # カタカナ・英字の誤認識
    'ソニービズネッワークス': 'ソニービズネットワークス',
    'ソニービズネツトワークス': 'ソニービズネットワークス',
    'エヌ・ティ・ティ': 'NTT',
    'エヌ・ティー・ティー': 'NTT',
    'リアルテイ': 'リアルティ',
    'リアルティー': 'リアルティ',

    # 店舗名の誤認識
    'セリァ': 'セリア',
    'ニトリ一': 'ニトリ',
    'ダイソ一': 'ダイソー',

    # 駐車場関連
    '三井のリパーク': '三井不動産リアルティ株式会社',
    'リパーク': '三井不動産リアルティ株式会社',

    # 公共機関
    '刈谷h': '刈谷市',
    '刈谷巾': '刈谷市',
}

# CJK互換漢字の正規化
CJK_NORMALIZATIONS = {
    '⽇': '日',
    '⽉': '月',
    '⾦': '金',
    '⽕': '火',
    '⽔': '水',
    '⽊': '木',
    '⼟': '土',
    '⽜': '牛',
    '⾁': '肉',
    '⽌': '止',
    '⺟': '母',
    '⺟': '母',
    '\u2F46': '日',  # ⽇
    '\u2F51': '日',  # 別のコードポイント
    '\u2F49': '月',  # ⽉
}

# 数字の誤認識（金額内のみ適用）
NUMERIC_CORRECTIONS = {
    'O': '0',  # オー → ゼロ
    'o': '0',
    'l': '1',  # エル → イチ
    'I': '1',  # アイ → イチ
    'i': '1',
    '|': '1',  # パイプ → イチ
}

# 記号の正規化
SYMBOL_CORRECTIONS = {
    '￥': '¥',  # 全角 → 半角
    '＼': '¥',  # バックスラッシュ → 円記号
    '，': ',',  # 全角カンマ → 半角
    '．': '.',  # 全角ピリオド → 半角
    '：': ':',  # 全角コロン → 半角
    '‐': '-',  # ハイフン類似文字
    '−': '-',  # マイナス記号
    '―': '-',  # ダッシュ
}

# 年号の誤認識補正（2026年のみ有効）
# OCRで2026年が誤認識される典型的なパターン
YEAR_CORRECTIONS = {
    '2006年': '2026年',  # 2が消える / 0が重複
    '2016年': '2026年',  # 2が1に誤認識
    '2O26年': '2026年',  # Oがゼロに誤認識（逆パターン）
    '2Oz6年': '2026年',  # zが誤認識
    '20z6年': '2026年',  # zが誤認識
}


def correct_ocr_text(text: str) -> str:
    """
    OCR誤認識の補正

    Args:
        text: OCRで抽出した生テキスト

    Returns:
        補正後のテキスト
    """
    if not text:
        return text

    # 1. 記号の正規化
    for wrong, correct in SYMBOL_CORRECTIONS.items():
        text = text.replace(wrong, correct)

    # 2. CJK互換漢字の正規化
    for wrong, correct in CJK_NORMALIZATIONS.items():
        text = text.replace(wrong, correct)

    # 3. 年号の誤認識補正（2026年以降のみ有効）
    for wrong, correct in YEAR_CORRECTIONS.items():
        text = text.replace(wrong, correct)

    # 4. 会社名の誤認識補正
    for wrong, correct in OCR_CORRECTIONS.items():
        text = text.replace(wrong, correct)

    return text


def correct_numeric_string(s: str) -> str:
    """
    数字文字列内の誤認識補正

    金額や登録番号など、数字のみで構成されるべき文字列の補正

    Args:
        s: 数字を含む文字列

    Returns:
        補正後の文字列
    """
    if not s:
        return s

    for wrong, correct in NUMERIC_CORRECTIONS.items():
        s = s.replace(wrong, correct)

    return s


def normalize_amount_string(s: str) -> str:
    """
    金額文字列の正規化

    スペース区切りの数字を連結、誤認識を補正

    Args:
        s: 金額を含む文字列

    Returns:
        正規化後の文字列
    """
    if not s:
        return s

    # 記号の正規化
    for wrong, correct in SYMBOL_CORRECTIONS.items():
        s = s.replace(wrong, correct)

    # 数字内の誤認識を補正
    s = correct_numeric_string(s)

    # スペース区切りの数字を連結（¥1 1 0 → ¥110）
    import re
    s = re.sub(r'(\d)\s+(\d)', r'\1\2', s)

    return s


# テスト用
if __name__ == "__main__":
    test_cases = [
        ("三井不勧産株式会社", "三井不動産株式会社"),
        ("¥1 1 0", "¥110"),
        ("2026⽇12⽉25⾦", "2026日12月25金"),
        ("金額：￥１，０００", "金額:¥1,000"),
    ]

    print("=== OCR誤認識補正テスト ===")
    for original, expected in test_cases:
        corrected = correct_ocr_text(original)
        status = "OK" if expected in corrected or corrected == expected else "NG"
        print(f"[{status}] '{original}' → '{corrected}'")
