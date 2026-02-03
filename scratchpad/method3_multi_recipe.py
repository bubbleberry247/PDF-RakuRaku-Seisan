"""Method 3: Multi-recipe preprocessing + best-score selection.

For each PDF, generate multiple preprocessed image variants,
run EasyOCR on each, and pick the result with highest quality score.

Recipes:
  0. Original (no preprocessing)
  1. Sauvola binarization (adaptive local thresholding)
  2. Adaptive Otsu (global + local)
  3. Denoise (fastNlMeansDenoising)
  4. Dilate (thicken thin/faded characters)
  5. CLAHE contrast enhancement
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
    if pix.n == 4:  # RGBA
        data = cv2.cvtColor(data, cv2.COLOR_RGBA2BGR)
    elif pix.n == 3:  # RGB
        data = cv2.cvtColor(data, cv2.COLOR_RGB2BGR)
    return data


def _save_temp(img, tag, pdf_path):
    """Save image to scratchpad with hash-based name (avoids Japanese path issues)."""
    h = hashlib.md5(pdf_path.encode()).hexdigest()[:12]
    path = os.path.join(SCRATCHPAD, f"_m3_{tag}_{h}.png")
    cv2.imwrite(path, img)
    return path


# ── Preprocessing recipes ──────────────────────────────────────────────

def recipe_original(img):
    """Recipe 0: No preprocessing."""
    return img

def recipe_sauvola(img, window_size=25, k=0.2):
    """Recipe 1: Sauvola adaptive binarization."""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if len(img.shape) == 3 else img
    mean = cv2.blur(gray, (window_size, window_size)).astype(np.float64)
    sq_mean = cv2.blur(gray.astype(np.float64) ** 2, (window_size, window_size))
    std = np.sqrt(np.maximum(sq_mean - mean ** 2, 0))
    threshold = mean * (1 + k * (std / 128 - 1))
    binary = ((gray > threshold) * 255).astype(np.uint8)
    return cv2.cvtColor(binary, cv2.COLOR_GRAY2BGR)

def recipe_otsu(img):
    """Recipe 2: Adaptive Otsu binarization."""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if len(img.shape) == 3 else img
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return cv2.cvtColor(binary, cv2.COLOR_GRAY2BGR)

def recipe_denoise(img):
    """Recipe 3: Non-local means denoising."""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if len(img.shape) == 3 else img
    denoised = cv2.fastNlMeansDenoising(gray, h=10, templateWindowSize=7, searchWindowSize=21)
    return cv2.cvtColor(denoised, cv2.COLOR_GRAY2BGR)

def recipe_dilate(img):
    """Recipe 4: Dilate to thicken thin characters."""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if len(img.shape) == 3 else img
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    # Invert so text is white, dilate, invert back
    inv = cv2.bitwise_not(binary)
    kernel = np.ones((2, 2), np.uint8)
    dilated = cv2.dilate(inv, kernel, iterations=1)
    result = cv2.bitwise_not(dilated)
    return cv2.cvtColor(result, cv2.COLOR_GRAY2BGR)

def recipe_clahe(img):
    """Recipe 5: CLAHE contrast enhancement."""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if len(img.shape) == 3 else img
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(gray)
    return cv2.cvtColor(enhanced, cv2.COLOR_GRAY2BGR)


RECIPES = [
    ("original", recipe_original),
    ("sauvola", recipe_sauvola),
    ("otsu", recipe_otsu),
    ("denoise", recipe_denoise),
    ("dilate", recipe_dilate),
    ("clahe", recipe_clahe),
]


# ── OCR + field extraction ─────────────────────────────────────────────

# Add parent tools dir to path for parse_expense_data
TOOLS_DIR = r"C:\ProgramData\RK10\Robots\44PDF一般経費楽楽精算申請\tools"
if TOOLS_DIR not in sys.path:
    sys.path.insert(0, TOOLS_DIR)

def run_ocr_on_image(img_path):
    """Run EasyOCR on image, return (raw_text, avg_confidence, detections)."""
    reader = _get_reader()
    results = reader.readtext(str(img_path))
    if not results:
        return "", 0.0, []
    texts = [r[1] for r in results]
    confs = [r[2] for r in results]
    raw_text = "\n".join(texts)
    avg_conf = sum(confs) / len(confs) if confs else 0.0
    return raw_text, avg_conf, results


def extract_fields(raw_text, avg_conf, pdf_path):
    """Extract amount/date/vendor from raw text using parse_expense_data."""
    try:
        from pdf_ocr_easyocr import EasyOCRProcessor
        proc = EasyOCRProcessor.__new__(EasyOCRProcessor)
        proc.raw_text = raw_text
        result = proc.parse_expense_data(raw_text)
        return result
    except Exception:
        pass

    # Fallback: minimal inline extraction
    return _inline_extract(raw_text, pdf_path)


def _inline_extract(raw_text, pdf_path):
    """Minimal inline field extraction (fallback)."""
    amount = 0
    issue_date = ""
    vendor_name = ""

    # Amount patterns (simplified from parse_expense_data)
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

    # Date patterns
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

    # Vendor: look for legal entity patterns
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


# ── Scoring ────────────────────────────────────────────────────────────

def score_result(raw_text, avg_conf, fields):
    """Score an OCR result. Higher = better.

    Components:
    - OCR confidence (0-1)
    - Text richness (log of char count, normalized)
    - Field extraction bonus (each detected field adds 0.2)
    """
    text_len = len(raw_text.replace('\n', '').replace(' ', ''))
    text_score = min(text_len / 500, 1.0)  # normalize: 500+ chars = 1.0

    field_score = 0.0
    if fields.get("amount", 0) > 0:
        field_score += 0.33
    if fields.get("issue_date", ""):
        field_score += 0.33
    if fields.get("vendor_name", ""):
        field_score += 0.34

    # Weighted combination
    score = (avg_conf * 0.3) + (text_score * 0.3) + (field_score * 0.4)
    return score


# ── Main entry point ───────────────────────────────────────────────────

def process_pdf(pdf_path):
    """Process a single PDF through all recipes, return best result."""
    img = pdf_to_cv2(pdf_path)

    best_score = -1
    best_result = None
    best_recipe = ""

    for name, recipe_fn in RECIPES:
        try:
            processed = recipe_fn(img.copy())
        except Exception as e:
            continue

        img_path = _save_temp(processed, name, pdf_path)

        try:
            raw_text, avg_conf, detections = run_ocr_on_image(img_path)
            fields = extract_fields(raw_text, avg_conf, pdf_path)
            score = score_result(raw_text, avg_conf, fields)

            if score > best_score:
                best_score = score
                best_result = fields
                best_result["raw_text"] = raw_text
                best_result["confidence"] = avg_conf
                best_result["recipe"] = name
                best_result["score"] = round(score, 4)
                best_recipe = name
        except Exception as e:
            continue
        finally:
            # Cleanup temp image
            try:
                os.remove(img_path)
            except OSError:
                pass

    if best_result is None:
        return {
            "amount": 0,
            "issue_date": "",
            "vendor_name": "",
            "raw_text": "",
            "confidence": 0.0,
            "recipe": "none",
            "score": 0.0,
        }

    # Filename fallback
    fname = os.path.basename(pdf_path)
    if not best_result.get("issue_date"):
        m = re.match(r'.*?_(\d{8})', fname)
        if m:
            best_result["issue_date"] = m.group(1)
    if not best_result.get("vendor_name"):
        m = re.match(r'^(.+?)_\d{8}', fname)
        if m:
            best_result["vendor_name"] = m.group(1)

    return best_result


# ── CLI ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("pdf", help="PDF file to process")
    parser.add_argument("--all-scores", action="store_true", help="Show all recipe scores")
    args = parser.parse_args()

    if args.all_scores:
        img = pdf_to_cv2(args.pdf)
        print(f"Processing: {os.path.basename(args.pdf)}")
        print(f"{'Recipe':<12} {'Conf':>6} {'Chars':>6} {'Amt':>8} {'Date':>10} {'Score':>6}")
        print("-" * 55)
        for name, recipe_fn in RECIPES:
            processed = recipe_fn(img.copy())
            img_path = _save_temp(processed, name, args.pdf)
            raw_text, avg_conf, _ = run_ocr_on_image(img_path)
            fields = extract_fields(raw_text, avg_conf, args.pdf)
            score = score_result(raw_text, avg_conf, fields)
            text_len = len(raw_text.replace('\n', '').replace(' ', ''))
            print(f"{name:<12} {avg_conf:>6.3f} {text_len:>6} {fields.get('amount',0):>8} {fields.get('issue_date',''):>10} {score:>6.3f}")
            try:
                os.remove(img_path)
            except OSError:
                pass
    else:
        result = process_pdf(args.pdf)
        print(f"Recipe: {result.get('recipe', '?')}")
        print(f"Score:  {result.get('score', 0):.4f}")
        print(f"Amount: {result.get('amount', 0)}")
        print(f"Date:   {result.get('issue_date', '')}")
        print(f"Vendor: {result.get('vendor_name', '')}")
        print(f"Conf:   {result.get('confidence', 0):.3f}")
