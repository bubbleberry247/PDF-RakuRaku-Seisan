"""Method 2: bbox座標ベースフィールド抽出

EasyOCRのreadtext()が返す(bbox, text, conf)を活用し、
ラベル（「合計」「請求金額」「発行日」等）のbbox位置から
右隣・下方向の値を空間的に取得する。

Usage:
    from method2_bbox_extract import process_pdf
    result = process_pdf("receipt.pdf")
"""
import os, sys, re, unicodedata, math
from pathlib import Path

# EasyOCR + 既存ツール
TOOLS_DIR = r"C:\ProgramData\RK10\Robots\44PDF一般経費楽楽精算申請\tools"
sys.path.insert(0, TOOLS_DIR)

import fitz  # PyMuPDF for PDF→image


# ── bbox helpers ──────────────────────────────────────────────────────

def bbox_center(bbox):
    """4点bbox [[x1,y1],[x2,y2],[x3,y3],[x4,y4]] の中心座標を返す。"""
    xs = [p[0] for p in bbox]
    ys = [p[1] for p in bbox]
    return (sum(xs) / len(xs), sum(ys) / len(ys))


def bbox_rect(bbox):
    """4点bbox → (x_min, y_min, x_max, y_max) の矩形に変換。"""
    xs = [p[0] for p in bbox]
    ys = [p[1] for p in bbox]
    return (min(xs), min(ys), max(xs), max(ys))


def is_right_of(label_rect, candidate_rect, tolerance_y=30, max_gap_x=400):
    """candidate が label の右方向にあるか。"""
    lx1, ly1, lx2, ly2 = label_rect
    cx1, cy1, cx2, cy2 = candidate_rect
    # Y軸が重なっている（許容範囲内）
    y_overlap = (cy1 <= ly2 + tolerance_y) and (cy2 >= ly1 - tolerance_y)
    # X方向で右にある
    x_right = cx1 >= lx2 - 10  # 少し重なりも許容
    # 距離が近い
    x_gap = cx1 - lx2
    return y_overlap and x_right and (x_gap <= max_gap_x)


def is_below(label_rect, candidate_rect, tolerance_x=50, max_gap_y=80):
    """candidate が label の直下にあるか。"""
    lx1, ly1, lx2, ly2 = label_rect
    cx1, cy1, cx2, cy2 = candidate_rect
    # X軸がある程度重なっている
    x_overlap = (cx1 <= lx2 + tolerance_x) and (cx2 >= lx1 - tolerance_x)
    # Y方向で下にある
    y_below = cy1 >= ly2 - 5
    # 距離が近い
    y_gap = cy1 - ly2
    return x_overlap and y_below and (y_gap <= max_gap_y)


def distance_between(rect_a, rect_b):
    """2つの矩形の中心間距離。"""
    ax = (rect_a[0] + rect_a[2]) / 2
    ay = (rect_a[1] + rect_a[3]) / 2
    bx = (rect_b[0] + rect_b[2]) / 2
    by = (rect_b[1] + rect_b[3]) / 2
    return math.sqrt((ax - bx) ** 2 + (ay - by) ** 2)


# ── ラベル辞書 ────────────────────────────────────────────────────────

AMOUNT_LABELS = [
    r'合\s*計',
    r'請求金額',
    r'ご請求金額',
    r'お支払金額',
    r'お支払い金額',
    r'税込合計',
    r'税込金額',
    r'合計金額',
    r'総合計',
    r'差引請求額',
    r'小計',
]

DATE_LABELS = [
    r'請求日',
    r'発行日',
    r'請求書日付',
    r'日\s*付',
    r'御請求日',
    r'ご利用日',
    r'作成日',
]

VENDOR_LABELS = [
    r'(?:株式|有限|合同|一般社団|一般財団|社会福祉|医療)(?:会社|法人)',
    r'㈱',
    r'㈲',
]


# ── 値抽出パターン ─────────────────────────────────────────────────────

def extract_amount_from_text(text):
    """テキストから金額数値を抽出。"""
    text = unicodedata.normalize('NFKC', text)
    text = text.replace('\\', '').replace('¥', '').replace('￥', '')
    text = text.strip()
    # カンマ付き数値
    m = re.search(r'(\d{1,3}(?:,\d{3})+)', text)
    if m:
        return int(m.group(1).replace(',', ''))
    # 整数
    m = re.search(r'(\d{3,})', text)
    if m:
        return int(m.group(1))
    return 0


def extract_date_from_text(text):
    """テキストから日付をYYYYMMDD形式で抽出。"""
    text = unicodedata.normalize('NFKC', text)

    # 西暦 YYYY年MM月DD日
    m = re.search(r'(20\d{2})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日', text)
    if m:
        return f"{m.group(1)}{int(m.group(2)):02d}{int(m.group(3)):02d}"

    # 令和
    m = re.search(r'令和\s*(\d{1,2})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日', text)
    if m:
        year = 2018 + int(m.group(1))
        return f"{year}{int(m.group(2)):02d}{int(m.group(3)):02d}"

    # YYYY/MM/DD or YYYY-MM-DD
    m = re.search(r'(20\d{2})[/\-.](\d{1,2})[/\-.](\d{1,2})', text)
    if m:
        return f"{m.group(1)}{int(m.group(2)):02d}{int(m.group(3)):02d}"

    return ""


def is_amount_text(text):
    """テキストが金額っぽいか判定。"""
    text = unicodedata.normalize('NFKC', text)
    text = text.replace('\\', '').replace('¥', '').replace('￥', '').strip()
    # カンマ付き数値 or 3桁以上の整数 + オプションで「円」
    return bool(re.match(r'^[\d,]+\s*円?$', text) and extract_amount_from_text(text) > 0)


def is_date_text(text):
    """テキストが日付っぽいか判定。"""
    return bool(extract_date_from_text(text))


# ── メイン処理 ─────────────────────────────────────────────────────────

def pdf_to_image(pdf_path, dpi=200):
    """PDF→画像ファイルパス（1ページ目）。"""
    doc = fitz.open(pdf_path)
    page = doc[0]
    mat = fitz.Matrix(dpi / 72, dpi / 72)
    pix = page.get_pixmap(matrix=mat)
    # 日本語パスだとOpenCVが読めないためscratchpadに保存
    import hashlib
    hash_name = hashlib.md5(pdf_path.encode()).hexdigest()[:12]
    scratchpad_dir = os.path.dirname(os.path.abspath(__file__))
    img_path = os.path.join(scratchpad_dir, f"_m2_temp_{hash_name}.png")
    pix.save(img_path)
    doc.close()
    return img_path


_easyocr_reader = None

def run_easyocr(image_path):
    """EasyOCRでbbox付きOCR実行。結果: [(bbox, text, conf), ...]"""
    global _easyocr_reader
    if _easyocr_reader is None:
        import easyocr
        _easyocr_reader = easyocr.Reader(['ja', 'en'], gpu=False, verbose=False)
    results = _easyocr_reader.readtext(str(image_path))
    return results


def find_label_matches(detections, label_patterns):
    """ラベルパターンに一致するdetection要素を返す。"""
    matches = []
    for bbox, text, conf in detections:
        text_norm = unicodedata.normalize('NFKC', text).strip()
        for pat in label_patterns:
            if re.search(pat, text_norm):
                matches.append((bbox, text_norm, conf))
                break
    return matches


def find_nearest_value(label_bbox, detections, value_check_fn, extract_fn):
    """ラベルbboxの右方向・下方向で最も近い値を取得。

    Returns: (extracted_value, distance) or (None, inf)
    """
    label_rect = bbox_rect(label_bbox)
    candidates = []

    for bbox, text, conf in detections:
        text_norm = unicodedata.normalize('NFKC', text).strip()
        if not value_check_fn(text_norm):
            continue
        cand_rect = bbox_rect(bbox)

        # 右方向チェック
        if is_right_of(label_rect, cand_rect):
            dist = distance_between(label_rect, cand_rect)
            val = extract_fn(text_norm)
            if val:
                candidates.append((val, dist, 'right', conf))

        # 下方向チェック
        if is_below(label_rect, cand_rect):
            dist = distance_between(label_rect, cand_rect)
            val = extract_fn(text_norm)
            if val:
                candidates.append((val, dist, 'below', conf))

    if not candidates:
        return None, float('inf')

    # 距離が最も近いものを採用（同距離ならconfが高い方）
    candidates.sort(key=lambda x: (x[1], -x[3]))
    return candidates[0][0], candidates[0][1]


def extract_vendor_from_detections(detections):
    """detection一覧からvendor名を抽出。法人格キーワードを含むテキストを探す。"""
    legal_patterns = [
        r'株式会社', r'有限会社', r'合同会社',
        r'一般社団法人', r'一般財団法人', r'社会福祉法人', r'医療法人',
        r'社会保険労務士法人',
        r'㈱', r'㈲',
    ]

    candidates = []
    for bbox, text, conf in detections:
        text_norm = unicodedata.normalize('NFKC', text).strip()
        for pat in legal_patterns:
            if pat in text_norm:
                # 「御中」「殿」「様」を除去
                cleaned = re.sub(r'[　\s]*(御中|殿|様)\s*$', '', text_norm)
                cleaned = re.sub(r'^(〒\d{3}-\d{4}|電話|TEL|FAX).*', '', cleaned)
                if len(cleaned) >= 3:
                    rect = bbox_rect(bbox)
                    # 上部にあるほど優先（請求書の差出人は上部にある傾向）
                    candidates.append((cleaned, rect[1], conf))
                break

    if not candidates:
        return ""

    # Y座標が小さい（上部にある）ものを優先
    candidates.sort(key=lambda x: x[1])
    return candidates[0][0]


def process_pdf(pdf_path: str) -> dict:
    """Method 2: bbox座標ベースフィールド抽出。

    Returns:
        dict with keys: amount, issue_date, vendor_name, raw_text, confidence,
                        labels_found
    """
    pdf_path = str(pdf_path)

    # PDF→画像→EasyOCR
    img_path = pdf_to_image(pdf_path)
    try:
        detections = run_easyocr(img_path)
    finally:
        if os.path.exists(img_path):
            os.remove(img_path)

    # raw_text結合
    raw_text = "\n".join([d[1] for d in detections])
    raw_text = unicodedata.normalize('NFKC', raw_text)

    result = {
        "amount": 0,
        "issue_date": "",
        "vendor_name": "",
        "raw_text": raw_text,
        "confidence": 0.0,
        "labels_found": [],
    }

    if not detections:
        return result

    # ── Amount抽出（ラベル近接） ──
    amount_labels = find_label_matches(detections, AMOUNT_LABELS)
    best_amount = 0
    best_amount_dist = float('inf')

    for label_bbox, label_text, label_conf in amount_labels:
        val, dist = find_nearest_value(
            label_bbox, detections,
            is_amount_text, extract_amount_from_text
        )
        if val and val > best_amount:
            # 最大金額を優先（合計 > 小計の傾向）
            best_amount = val
            best_amount_dist = dist
            result["labels_found"].append(f"amount:{label_text}")

    if best_amount > 0:
        result["amount"] = best_amount

    # ── Date抽出（ラベル近接 + 全文スキャン） ──
    date_labels = find_label_matches(detections, DATE_LABELS)
    best_date = ""
    best_date_dist = float('inf')

    for label_bbox, label_text, label_conf in date_labels:
        val, dist = find_nearest_value(
            label_bbox, detections,
            is_date_text, extract_date_from_text
        )
        if val and dist < best_date_dist:
            best_date = val
            best_date_dist = dist
            result["labels_found"].append(f"date:{label_text}")

    if best_date:
        result["issue_date"] = best_date
    else:
        # フォールバック: 全テキストから日付を探す
        for bbox, text, conf in detections:
            d = extract_date_from_text(text)
            if d:
                result["issue_date"] = d
                break

    # ── Vendor抽出（法人格キーワード） ──
    vendor = extract_vendor_from_detections(detections)
    if vendor:
        result["vendor_name"] = vendor

    # ── ファイル名からの補完（method1と同じロジック） ──
    stem = Path(pdf_path).stem
    if stem.startswith('【') and '】' in stem:
        stem = stem.split('】', 1)[1]
    stem_clean = re.sub(r'【.*?】', '', stem)
    parts = stem_clean.split('_')

    # vendor from filename
    if len(parts) >= 1 and parts[0]:
        filename_vendor = parts[0]
        exclude_prefixes = ['東海インプル建設', '御請求書']
        is_numeric_start = re.match(r'^\d{4,}', filename_vendor)
        if (not filename_vendor.isdigit() and
            not is_numeric_start and
            not any(ep in filename_vendor for ep in exclude_prefixes)):
            legal_entities = ['株式会社', '有限会社', '合同会社', '一般社団法人', '一般財団法人',
                              '社会福祉法人', '医療法人', '社会保険労務士法人']
            ocr_has_legal = result["vendor_name"] and any(le in result["vendor_name"] for le in legal_entities)
            ocr_contains_filename = result["vendor_name"] and filename_vendor in result["vendor_name"]
            if ocr_has_legal and ocr_contains_filename:
                pass  # Keep OCR vendor (has legal entity)
            elif result["vendor_name"] and result["vendor_name"] != filename_vendor:
                result["vendor_name"] = filename_vendor
            elif not result["vendor_name"]:
                result["vendor_name"] = filename_vendor

    # amount from filename
    if len(parts) >= 3:
        amount_part = parts[2].strip()
        if not re.match(r'^\d{8}$', amount_part):
            amount_part_clean = amount_part.replace(',', '')
            amount_match = re.match(r'^(\d+)', amount_part_clean)
            if amount_match:
                filename_amount = int(amount_match.group(1))
                if filename_amount > 0:
                    if result["amount"] > 0 and result["amount"] != filename_amount:
                        ratio = result["amount"] / filename_amount
                        is_tax_inclusive = (abs(ratio - 1.10) < 0.015 or abs(ratio - 1.08) < 0.015)
                        if not is_tax_inclusive:
                            result["amount"] = filename_amount
                    elif result["amount"] == 0:
                        result["amount"] = filename_amount

    # Confidence
    confs = [d[2] for d in detections]
    avg_conf = sum(confs) / len(confs) if confs else 0.0
    filled = sum([
        bool(result["amount"] > 0),
        bool(result["issue_date"]),
        bool(result["vendor_name"]),
    ])
    result["confidence"] = round(avg_conf * (filled / 3.0), 3)

    return result


# ── CLI test ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse, json

    parser = argparse.ArgumentParser(description="Method 2: bbox-based field extraction")
    parser.add_argument("pdf", help="PDF file to process")
    args = parser.parse_args()

    result = process_pdf(args.pdf)
    # Remove raw_text for readability
    display = {k: v for k, v in result.items() if k != "raw_text"}
    display["raw_text_length"] = len(result.get("raw_text", ""))
    print(json.dumps(display, ensure_ascii=False, indent=2))
