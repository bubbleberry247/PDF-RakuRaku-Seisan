"""Method 4: Tile-based OCR (3x3 grid with overlap).

Split PDF page into 3x3 tiles with 10% overlap, OCR each tile independently,
merge results and deduplicate overlapping text, then extract fields.

This approach improves small-text recognition by giving EasyOCR
higher-resolution sub-images.
"""
import os, sys, re, hashlib, unicodedata, cv2, numpy as np
import fitz  # PyMuPDF

# ── EasyOCR singleton ──────────────────────────────────────────────────

_easyocr_reader = None

def _get_reader():
    global _easyocr_reader
    if _easyocr_reader is None:
        import easyocr
        _easyocr_reader = easyocr.Reader(['ja', 'en'], gpu=False, verbose=False)
    return _easyocr_reader


# ── PDF → image ────────────────────────────────────────────────────────

SCRATCHPAD = os.path.dirname(os.path.abspath(__file__))

def pdf_to_cv2(pdf_path, dpi=300):
    """PDF first page → OpenCV BGR numpy array."""
    doc = fitz.open(pdf_path)
    page = doc[0]
    mat = fitz.Matrix(dpi / 72, dpi / 72)
    pix = page.get_pixmap(matrix=mat)
    data = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.h, pix.w, pix.n)
    doc.close()
    if pix.n == 4:
        data = cv2.cvtColor(data, cv2.COLOR_RGBA2BGR)
    elif pix.n == 3:
        data = cv2.cvtColor(data, cv2.COLOR_RGB2BGR)
    return data


def _save_temp(img, tag, pdf_path):
    h = hashlib.md5(pdf_path.encode()).hexdigest()[:12]
    path = os.path.join(SCRATCHPAD, f"_m4_{tag}_{h}.png")
    cv2.imwrite(path, img)
    return path


# ── Tile splitting ─────────────────────────────────────────────────────

def split_tiles(img, rows=3, cols=3, overlap=0.10):
    """Split image into grid tiles with overlap.
    Returns list of (tile_img, x_offset, y_offset)."""
    h, w = img.shape[:2]
    tile_h = h // rows
    tile_w = w // cols
    overlap_h = int(tile_h * overlap)
    overlap_w = int(tile_w * overlap)

    tiles = []
    for r in range(rows):
        for c in range(cols):
            y1 = max(0, r * tile_h - overlap_h)
            y2 = min(h, (r + 1) * tile_h + overlap_h)
            x1 = max(0, c * tile_w - overlap_w)
            x2 = min(w, (c + 1) * tile_w + overlap_w)
            tile = img[y1:y2, x1:x2].copy()
            tiles.append((tile, x1, y1))

    return tiles


# ── OCR on tiles ───────────────────────────────────────────────────────

def ocr_tile(tile_img, x_offset, y_offset, pdf_path, tile_idx):
    """Run EasyOCR on a tile, adjust bbox coordinates to global space."""
    img_path = _save_temp(tile_img, f"t{tile_idx}", pdf_path)
    try:
        reader = _get_reader()
        results = reader.readtext(str(img_path))
    finally:
        try:
            os.remove(img_path)
        except OSError:
            pass

    # Adjust coordinates to global image space
    adjusted = []
    for bbox, text, conf in results:
        # bbox is [[x1,y1],[x2,y2],[x3,y3],[x4,y4]]
        adj_bbox = [[pt[0] + x_offset, pt[1] + y_offset] for pt in bbox]
        adjusted.append((adj_bbox, text, conf))

    return adjusted


def merge_detections(all_detections):
    """Merge detections from all tiles, removing duplicates from overlap regions.

    Dedup strategy: if two detections have similar center positions (within 20px)
    and similar text, keep the one with higher confidence.
    """
    if not all_detections:
        return []

    def center(bbox):
        xs = [pt[0] for pt in bbox]
        ys = [pt[1] for pt in bbox]
        return (sum(xs) / len(xs), sum(ys) / len(ys))

    # Sort by Y then X for consistent ordering
    all_detections.sort(key=lambda d: (center(d[0])[1], center(d[0])[0]))

    merged = []
    used = set()

    for i, (bbox_i, text_i, conf_i) in enumerate(all_detections):
        if i in used:
            continue
        cx_i, cy_i = center(bbox_i)
        best_idx = i

        # Check for duplicates
        for j in range(i + 1, len(all_detections)):
            if j in used:
                continue
            bbox_j, text_j, conf_j = all_detections[j]
            cx_j, cy_j = center(bbox_j)

            # Within 20px distance and similar text
            if abs(cx_i - cx_j) < 20 and abs(cy_i - cy_j) < 20:
                # Keep higher confidence
                if conf_j > all_detections[best_idx][2]:
                    used.add(best_idx)
                    best_idx = j
                else:
                    used.add(j)

        merged.append(all_detections[best_idx])
        used.add(best_idx)

    return merged


# ── Field extraction ───────────────────────────────────────────────────

TOOLS_DIR = r"C:\ProgramData\RK10\Robots\44PDF一般経費楽楽精算申請\tools"
if TOOLS_DIR not in sys.path:
    sys.path.insert(0, TOOLS_DIR)


def extract_fields(raw_text, pdf_path):
    """Extract fields using parse_expense_data or inline fallback."""
    try:
        from pdf_ocr_easyocr import EasyOCRProcessor
        proc = EasyOCRProcessor.__new__(EasyOCRProcessor)
        proc.raw_text = raw_text
        result = proc.parse_expense_data(raw_text)
        return result
    except Exception:
        pass

    # Inline fallback
    amount = 0
    issue_date = ""
    vendor_name = ""

    amt_patterns = [
        r'(?:合\s*計|請求金額|ご請求金額|税込合計)[^\d]*?([\d,]+)',
        r'(?:税込|総合計)[^\d]*?([\d,]+)',
        r'¥\s*([\d,]+)',
    ]
    for pat in amt_patterns:
        m = re.search(pat, raw_text)
        if m:
            try:
                amount = int(m.group(1).replace(',', ''))
                break
            except ValueError:
                pass

    date_patterns = [
        (r'(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日', lambda m: f"{m.group(1)}{int(m.group(2)):02d}{int(m.group(3)):02d}"),
        (r'令和\s*(\d{1,2})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日', lambda m: f"{2018+int(m.group(1))}{int(m.group(2)):02d}{int(m.group(3)):02d}"),
        (r'(\d{4})/(\d{1,2})/(\d{1,2})', lambda m: f"{m.group(1)}{int(m.group(2)):02d}{int(m.group(3)):02d}"),
    ]
    for pat, fmt in date_patterns:
        m = re.search(pat, raw_text)
        if m:
            issue_date = fmt(m)
            break

    vendor_pat = re.compile(r'(?:株式会社|有限会社|合同会社|合資会社).{1,20}|.{1,20}(?:株式会社|有限会社|合同会社)')
    vm = vendor_pat.search(raw_text)
    if vm:
        vendor_name = vm.group(0).strip()

    return {
        "amount": amount,
        "issue_date": issue_date,
        "vendor_name": vendor_name,
        "raw_text": raw_text,
    }


# ── Main entry point ───────────────────────────────────────────────────

def process_pdf(pdf_path):
    """Process a single PDF using tile-based OCR."""
    img = pdf_to_cv2(pdf_path, dpi=300)
    tiles = split_tiles(img, rows=3, cols=3, overlap=0.10)

    # Also run full-page OCR for comparison
    full_img_path = _save_temp(img, "full", pdf_path)
    try:
        reader = _get_reader()
        full_results = reader.readtext(str(full_img_path))
    finally:
        try:
            os.remove(full_img_path)
        except OSError:
            pass

    # Run OCR on each tile
    all_tile_detections = []
    for idx, (tile_img, x_off, y_off) in enumerate(tiles):
        dets = ocr_tile(tile_img, x_off, y_off, pdf_path, idx)
        all_tile_detections.extend(dets)

    # Merge and deduplicate
    merged = merge_detections(all_tile_detections)

    # Build raw text (sorted by Y position)
    def get_y(det):
        return min(pt[1] for pt in det[0])

    merged.sort(key=get_y)
    tile_raw_text = "\n".join(det[1] for det in merged)
    tile_confs = [det[2] for det in merged]
    tile_avg_conf = sum(tile_confs) / len(tile_confs) if tile_confs else 0.0

    # Full-page results
    full_raw_text = "\n".join(r[1] for r in full_results)
    full_confs = [r[2] for r in full_results]
    full_avg_conf = sum(full_confs) / len(full_confs) if full_confs else 0.0

    # Extract fields from both
    tile_fields = extract_fields(tile_raw_text, pdf_path)
    full_fields = extract_fields(full_raw_text, pdf_path)

    # Score both and pick best
    def _score(fields, avg_conf, raw_text):
        text_len = len(raw_text.replace('\n', '').replace(' ', ''))
        text_score = min(text_len / 500, 1.0)
        field_score = 0.0
        if fields.get("amount", 0) > 0:
            field_score += 0.33
        if fields.get("issue_date", ""):
            field_score += 0.33
        if fields.get("vendor_name", ""):
            field_score += 0.34
        return (avg_conf * 0.3) + (text_score * 0.3) + (field_score * 0.4)

    tile_score = _score(tile_fields, tile_avg_conf, tile_raw_text)
    full_score = _score(full_fields, full_avg_conf, full_raw_text)

    if tile_score >= full_score:
        result = tile_fields
        result["confidence"] = tile_avg_conf
        result["mode"] = "tile"
        result["tile_score"] = round(tile_score, 4)
        result["full_score"] = round(full_score, 4)
        result["tile_chars"] = len(tile_raw_text)
        result["full_chars"] = len(full_raw_text)
    else:
        result = full_fields
        result["confidence"] = full_avg_conf
        result["mode"] = "full"
        result["tile_score"] = round(tile_score, 4)
        result["full_score"] = round(full_score, 4)
        result["tile_chars"] = len(tile_raw_text)
        result["full_chars"] = len(full_raw_text)

    # Filename fallback
    fname = os.path.basename(pdf_path)
    if not result.get("issue_date"):
        m = re.match(r'.*?_(\d{8})', fname)
        if m:
            result["issue_date"] = m.group(1)
    if not result.get("vendor_name"):
        m = re.match(r'^(.+?)_\d{8}', fname)
        if m:
            result["vendor_name"] = m.group(1)

    return result


# ── CLI ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("pdf", help="PDF file to process")
    args = parser.parse_args()

    result = process_pdf(args.pdf)
    print(f"Mode:   {result.get('mode', '?')}")
    print(f"Amount: {result.get('amount', 0)}")
    print(f"Date:   {result.get('issue_date', '')}")
    print(f"Vendor: {result.get('vendor_name', '')}")
    print(f"Conf:   {result.get('confidence', 0):.3f}")
    print(f"Tile score: {result.get('tile_score', 0):.4f}")
    print(f"Full score: {result.get('full_score', 0):.4f}")
    print(f"Tile chars: {result.get('tile_chars', 0)}")
    print(f"Full chars: {result.get('full_chars', 0)}")
