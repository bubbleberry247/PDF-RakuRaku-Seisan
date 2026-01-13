# -*- coding: utf-8 -*-
"""
検証用PDF作成スクリプト

動画書き起こしで確認した11件のPDFサンプルを作成する
"""
import os
from pathlib import Path
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.units import mm

# 日本語フォント登録
FONT_PATH = r"C:\Windows\Fonts\msgothic.ttc"
if os.path.exists(FONT_PATH):
    pdfmetrics.registerFont(TTFont("Gothic", FONT_PATH))
    FONT_NAME = "Gothic"
else:
    FONT_NAME = "Helvetica"

# 出力先
OUTPUT_DIR = Path(r"C:\ProgramData\RK10\Robots\44PDF一般経費楽楽精算申請\data\MOCK_FAX")

# テストデータ（動画書き起こしより）
TEST_DATA = [
    {
        "filename": "20251117183719001.pdf",
        "vendor": "ソニービズネットワークス株式会社",
        "date": "2024年11月7日",
        "amount": "22,803",
        "invoice_no": "T1010701026820",
        "doc_type": "請求書"
    },
    {
        "filename": "20251117183719002.pdf",
        "vendor": "株式会社三菱UFJ銀行",
        "date": "2024年11月15日",
        "amount": "7,612",
        "invoice_no": "T8010001008346",
        "doc_type": "領収書"
    },
    {
        "filename": "20251117183719003.pdf",
        "vendor": "エヌ・ティ・ティ・スマートコネクト株式会社",
        "date": "2024年11月10日",
        "amount": "26,400",
        "invoice_no": "",
        "doc_type": "請求書"
    },
    {
        "filename": "20251117183719004.pdf",
        "vendor": "ラディックス株式会社",
        "date": "2024年11月8日",
        "amount": "4,045",
        "invoice_no": "T5010001089333",
        "doc_type": "請求書"
    },
    {
        "filename": "20251117183719005.pdf",
        "vendor": "税理士法人TFC",
        "date": "2024年11月20日",
        "amount": "104,500",
        "invoice_no": "T3180005006900",
        "doc_type": "請求書"
    },
    {
        "filename": "20251117183719006.pdf",
        "vendor": "東海スマート企業グループ株式会社",
        "date": "2024年11月5日",
        "amount": "2,970",
        "invoice_no": "T8180301014312",
        "doc_type": "請求書"
    },
    {
        "filename": "20251117183719007.pdf",
        "vendor": "東海スマート企業グループ株式会社",
        "date": "2024年11月12日",
        "amount": "2,488,420",
        "invoice_no": "T8180301014312",
        "doc_type": "請求書"
    },
    {
        "filename": "20251117183719008.pdf",
        "vendor": "東海スマート企業グループ株式会社",
        "date": "2024年11月18日",
        "amount": "28,432",
        "invoice_no": "T8180301014312",
        "doc_type": "請求書"
    },
    {
        "filename": "20251117183719009.pdf",
        "vendor": "刈谷税務署",
        "date": "2024年11月25日",
        "amount": "14,600",
        "invoice_no": "",
        "doc_type": "領収書"
    },
    {
        "filename": "20251117183719010.pdf",
        "vendor": "楽天市場(マンツウオンラインショップ)",
        "date": "2024年11月3日",
        "amount": "10,768",
        "invoice_no": "",
        "doc_type": "領収書"
    },
    {
        "filename": "20251117183719011.pdf",
        "vendor": "楽天市場(花の専門店 行きつけのお花屋さん)",
        "date": "2024年11月22日",
        "amount": "3,998",
        "invoice_no": "T6013201013227",
        "doc_type": "領収書"
    },
]


def create_invoice_pdf(filepath: Path, data: dict):
    """請求書/領収書PDFを作成"""
    c = canvas.Canvas(str(filepath), pagesize=A4)
    width, height = A4

    # タイトル
    c.setFont(FONT_NAME, 24)
    c.drawCentredString(width / 2, height - 50 * mm, data["doc_type"])

    # 宛先
    c.setFont(FONT_NAME, 12)
    c.drawString(30 * mm, height - 80 * mm, "株式会社トナリティ 御中")

    # 発行元（長い会社名はフォントサイズを小さくして全体を表示）
    vendor = data["vendor"]
    font_size = 14 if len(vendor) < 20 else 10
    c.setFont(FONT_NAME, font_size)
    c.drawString(30 * mm, height - 100 * mm, vendor)

    # 登録番号
    if data["invoice_no"]:
        c.setFont(FONT_NAME, 10)
        c.drawString(120 * mm, height - 110 * mm, f"登録番号: {data['invoice_no']}")

    # 発行日
    c.setFont(FONT_NAME, 12)
    c.drawString(120 * mm, height - 125 * mm, f"発行日: {data['date']}")

    # 金額
    c.setFont(FONT_NAME, 18)
    c.drawString(30 * mm, height - 150 * mm, f"合計金額: ¥{data['amount']}")

    # 明細
    c.setFont(FONT_NAME, 10)
    c.drawString(30 * mm, height - 180 * mm, "品目: サービス利用料")
    c.drawString(30 * mm, height - 190 * mm, f"金額: ¥{data['amount']}")

    # 振込先
    c.setFont(FONT_NAME, 9)
    c.drawString(30 * mm, height - 220 * mm, "お振込先: ○○銀行 △△支店 普通 1234567")

    c.save()
    print(f"作成: {filepath.name}")


def main():
    """メイン処理"""
    # 出力フォルダ作成
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print("=" * 50)
    print("検証用PDF作成")
    print("=" * 50)
    print(f"出力先: {OUTPUT_DIR}")
    print(f"作成数: {len(TEST_DATA)}件")
    print("-" * 50)

    for data in TEST_DATA:
        filepath = OUTPUT_DIR / data["filename"]
        create_invoice_pdf(filepath, data)

    print("-" * 50)
    print(f"完了: {len(TEST_DATA)}件のPDFを作成しました")


if __name__ == "__main__":
    main()
