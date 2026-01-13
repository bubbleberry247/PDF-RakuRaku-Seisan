# -*- coding: utf-8 -*-
"""
PDF OCR抽出 ABテスト

問題: 電話番号が日付として誤認識される / 令和形式・異体字への対応不足
原因:
  - TEL：0566-63-5593 が日付パターンにマッチ
  - CJK互換漢字（⽇⽉年）が正規表現にマッチしない
  - 令和形式の西暦変換ロジックが不正確
  - ラベルと日付が別行にある場合に対応できない

改善案:
A案: 日付パターンの優先順位変更（「請求日」「発行日」ラベル付きを優先）
B案: 電話番号パターンを除外してから日付抽出
C案: 日付の妥当性検証（年が1900-2100の範囲内か）
D案: A+B+C 複合
E案: CJK互換漢字の正規化 + 令和変換 + 複数行対応
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
sys.stdout.reconfigure(encoding='utf-8')

import fitz
from common.logger import setup_logger, get_logger

# テスト対象PDF
TEST_PDFS = [
    r"C:\ProgramData\RK10\Robots\44PDF一般経費楽楽精算申請\data\MOCK_DOCS\2022 6月分キャリアント請求書.pdf",
    r"C:\ProgramData\RK10\Robots\44PDF一般経費楽楽精算申請\data\MOCK_DOCS\城山請求書（23年5月請求分）.pdf",
    r"C:\ProgramData\RK10\Robots\44PDF一般経費楽楽精算申請\data\MOCK_DOCS\給与計算_請求書（10月分）.pdf",
]

# 期待値
EXPECTED = {
    "2022 6月分キャリアント請求書.pdf": {"date": "20220711", "vendor": "株式会社 キャリアント"},
    "城山請求書（23年5月請求分）.pdf": {"date": "20230515", "vendor": "株式会社しごとラボ"},  # 請求日: 令和5年5月15日
    "給与計算_請求書（10月分）.pdf": {"date": "20221101", "vendor": "株式会社ホームズパレット"},  # 請求日: 令和4年11月1日
}


def extract_text(pdf_path: str) -> str:
    """PDFからテキスト抽出"""
    doc = fitz.open(pdf_path)
    text = ""
    for page in doc:
        text += page.get_text()
    doc.close()
    return text


def normalize_cjk(text: str) -> str:
    """CJK互換漢字を通常の漢字に正規化"""
    # CJK互換漢字 → 通常漢字 のマッピング
    replacements = {
        '\u2F46': '日',  # ⽇ → 日
        '\u2F51': '日',  # ⽇ → 日 (別のコードポイント)
        '\u2F49': '月',  # ⽉ → 月
        '\u2F4B': '年',  # ⽛ → 年 (念のため)
        '⽇': '日',
        '⽉': '月',
        '⾦': '金',
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text


def reiwa_to_seireki(reiwa_year: int) -> int:
    """令和年を西暦に変換 (令和1年 = 2019年)"""
    return 2018 + reiwa_year


# === 現行パターン（ベースライン） ===
def extract_date_baseline(text: str) -> str:
    """現行の日付抽出"""
    date_patterns = [
        r'(\d{4})[年/\-](\d{1,2})[月/\-](\d{1,2})[日]?',
        r'[令和R]?\s*(\d{1,2})[年\.](\d{1,2})[月\.](\d{1,2})[日]?',
        r'発行日[:\s：]*(\d{4})[/\-]?(\d{2})[/\-]?(\d{2})',
        r'請求日[:\s：]*(\d{4})[/\-]?(\d{2})[/\-]?(\d{2})',
    ]
    for pattern in date_patterns:
        match = re.search(pattern, text)
        if match:
            groups = match.groups()
            if len(groups) == 3:
                year, month, day = groups
                if int(year) < 100:
                    year = str(2018 + int(year))
                return f"{int(year):04d}{int(month):02d}{int(day):02d}"
    return ""


# === A案: ラベル付き日付を優先 ===
def extract_date_pattern_a(text: str) -> str:
    """A案: 「請求日」「発行日」ラベル付きを優先"""
    # 優先度1: ラベル付き日付
    labeled_patterns = [
        r'請求[日⽇][:\s：]*(\d{4})[年/\-]?(\d{1,2})[月/\-]?(\d{1,2})[日⽇]?',
        r'発行[日⽇][:\s：]*(\d{4})[年/\-]?(\d{1,2})[月/\-]?(\d{1,2})[日⽇]?',
        r'日付[:\s：]*(\d{4})[年/\-]?(\d{1,2})[月/\-]?(\d{1,2})[日⽇]?',
    ]
    for pattern in labeled_patterns:
        match = re.search(pattern, text)
        if match:
            year, month, day = match.groups()
            return f"{int(year):04d}{int(month):02d}{int(day):02d}"

    # 優先度2: 一般的な日付パターン
    general_patterns = [
        r'(\d{4})[年](\d{1,2})[月](\d{1,2})[日⽇]',  # 2022年7月11日
    ]
    for pattern in general_patterns:
        match = re.search(pattern, text)
        if match:
            year, month, day = match.groups()
            return f"{int(year):04d}{int(month):02d}{int(day):02d}"

    return ""


# === B案: 電話番号を除外してから抽出 ===
def extract_date_pattern_b(text: str) -> str:
    """B案: TEL/FAX行を除外してから日付抽出"""
    # 電話番号・FAX行を除外
    lines = text.split('\n')
    filtered_lines = []
    for line in lines:
        if re.search(r'TEL|FAX|電話|ファックス', line, re.IGNORECASE):
            continue
        filtered_lines.append(line)
    filtered_text = '\n'.join(filtered_lines)

    # 日付抽出
    date_patterns = [
        r'(\d{4})[年](\d{1,2})[月](\d{1,2})[日⽇]',
        r'(\d{4})[/\-](\d{1,2})[/\-](\d{1,2})',
    ]
    for pattern in date_patterns:
        match = re.search(pattern, filtered_text)
        if match:
            year, month, day = match.groups()
            return f"{int(year):04d}{int(month):02d}{int(day):02d}"
    return ""


# === C案: 日付の妥当性検証 ===
def extract_date_pattern_c(text: str) -> str:
    """C案: 抽出後に妥当性検証"""
    date_patterns = [
        r'(\d{4})[年/\-](\d{1,2})[月/\-](\d{1,2})[日⽇]?',
    ]
    candidates = []
    for pattern in date_patterns:
        for match in re.finditer(pattern, text):
            year, month, day = match.groups()
            year = int(year)
            month = int(month)
            day = int(day)
            # 妥当性検証
            if 1900 <= year <= 2100 and 1 <= month <= 12 and 1 <= day <= 31:
                candidates.append((year, month, day, match.start()))

    if candidates:
        # 最も後ろにある日付を採用（請求日は後半にあることが多い）
        candidates.sort(key=lambda x: x[3], reverse=True)
        year, month, day, _ = candidates[0]
        return f"{year:04d}{month:02d}{day:02d}"
    return ""


# === D案: A+B+C 複合 ===
def extract_date_pattern_d(text: str) -> str:
    """D案: ラベル優先 + 電話除外 + 妥当性検証"""
    # 電話番号行を除外
    lines = text.split('\n')
    filtered_lines = [l for l in lines if not re.search(r'TEL|FAX|電話', l, re.IGNORECASE)]
    filtered_text = '\n'.join(filtered_lines)

    # 優先度1: ラベル付き日付
    labeled_patterns = [
        r'請求[日⽇][:\s：]*(\d{4})[年/\-]?(\d{1,2})[月/\-]?(\d{1,2})[日⽇]?',
        r'発行[日⽇][:\s：]*(\d{4})[年/\-]?(\d{1,2})[月/\-]?(\d{1,2})[日⽇]?',
    ]
    for pattern in labeled_patterns:
        match = re.search(pattern, filtered_text)
        if match:
            year, month, day = match.groups()
            y, m, d = int(year), int(month), int(day)
            if 1900 <= y <= 2100 and 1 <= m <= 12 and 1 <= d <= 31:
                return f"{y:04d}{m:02d}{d:02d}"

    # 優先度2: 年月日形式
    for match in re.finditer(r'(\d{4})[年](\d{1,2})[月](\d{1,2})[日⽇]', filtered_text):
        year, month, day = match.groups()
        y, m, d = int(year), int(month), int(day)
        if 1900 <= y <= 2100 and 1 <= m <= 12 and 1 <= d <= 31:
            return f"{y:04d}{m:02d}{d:02d}"

    return ""


# === E案: CJK正規化 + 令和変換 + 複数行対応（推奨） ===
def extract_date_pattern_e(text: str) -> str:
    """E案: CJK正規化 + 令和変換 + 複数行対応 + TEL除外"""
    # Step 1: CJK互換漢字を正規化
    normalized = normalize_cjk(text)

    # Step 2: 電話番号行を除外
    lines = normalized.split('\n')
    filtered_lines = [l for l in lines if not re.search(r'TEL|FAX|電話', l, re.IGNORECASE)]
    filtered_text = '\n'.join(filtered_lines)

    # Step 3: 「請求日」ラベルの近くにある日付を探す（複数行対応）
    # 「請求日」の後、数行以内に日付がある場合を考慮
    lines = filtered_text.split('\n')
    for i, line in enumerate(lines):
        if '請求日' in line or '発行日' in line:
            # 同じ行に日付があるか
            # 令和形式
            match = re.search(r'令和\s*(\d{1,2})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日', line)
            if match:
                year = reiwa_to_seireki(int(match.group(1)))
                month, day = int(match.group(2)), int(match.group(3))
                return f"{year:04d}{month:02d}{day:02d}"

            # 西暦形式
            match = re.search(r'(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日', line)
            if match:
                year, month, day = int(match.group(1)), int(match.group(2)), int(match.group(3))
                return f"{year:04d}{month:02d}{day:02d}"

            # 次の行に日付があるか確認（ラベルと日付が別行の場合）
            for j in range(i+1, min(i+3, len(lines))):
                next_line = lines[j].strip()
                # 令和形式
                match = re.search(r'令和\s*(\d{1,2})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日', next_line)
                if match:
                    year = reiwa_to_seireki(int(match.group(1)))
                    month, day = int(match.group(2)), int(match.group(3))
                    return f"{year:04d}{month:02d}{day:02d}"

                # 西暦形式
                match = re.search(r'(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日', next_line)
                if match:
                    year, month, day = int(match.group(1)), int(match.group(2)), int(match.group(3))
                    return f"{year:04d}{month:02d}{day:02d}"

    # Step 4: ラベルなしでも西暦年月日形式を探す
    for match in re.finditer(r'(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日', filtered_text):
        year, month, day = int(match.group(1)), int(match.group(2)), int(match.group(3))
        if 2000 <= year <= 2100 and 1 <= month <= 12 and 1 <= day <= 31:
            return f"{year:04d}{month:02d}{day:02d}"

    return ""


def run_ab_test():
    """ABテスト実行"""
    setup_logger("ab_test")

    patterns = {
        "Baseline": extract_date_baseline,
        "A案(ラベル優先)": extract_date_pattern_a,
        "B案(TEL除外)": extract_date_pattern_b,
        "C案(妥当性検証)": extract_date_pattern_c,
        "D案(複合)": extract_date_pattern_d,
        "E案(CJK正規化+令和)": extract_date_pattern_e,
    }

    print("=" * 80)
    print("PDF日付抽出 ABテスト")
    print("=" * 80)

    results = {name: {"success": 0, "fail": 0} for name in patterns}

    for pdf_path in TEST_PDFS:
        pdf_name = Path(pdf_path).name
        expected = EXPECTED.get(pdf_name, {}).get("date", "")

        text = extract_text(pdf_path)

        print(f"\n--- {pdf_name} ---")
        print(f"期待値: {expected}")

        for name, func in patterns.items():
            extracted = func(text)
            is_correct = extracted == expected
            status = "OK" if is_correct else "NG"

            if is_correct:
                results[name]["success"] += 1
            else:
                results[name]["fail"] += 1

            print(f"  {name}: {extracted} [{status}]")

    # サマリー
    print("\n" + "=" * 80)
    print("テスト結果サマリー")
    print("=" * 80)
    total = len(TEST_PDFS)
    for name, res in results.items():
        rate = res["success"] / total * 100
        print(f"  {name}: {res['success']}/{total} ({rate:.0f}%)")


if __name__ == "__main__":
    run_ab_test()
