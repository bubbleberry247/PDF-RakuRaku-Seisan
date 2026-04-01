"""sarashina_ocr.py — Sarashina2.2-OCR ローカル推論ラッパー（WSL Linux経由、開発環境専用）。

Usage (Windows → WSL):
    wsl -d Ubuntu-24.04 -u root -- /opt/vllm-env/bin/python \
        /mnt/c/.../sarashina_ocr.py <pdf_path> [--max-pixels 1003520]

Usage (direct):
    python sarashina_ocr.py invoice.pdf --max-pixels 1003520
"""
from __future__ import annotations

import io
import json
import sys
import time
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import PIL.Image

# max_pixels=1280*28*28=1003520 で入力トークン半減、速度2.3x改善（精度検証済み）
DEFAULT_MAX_PIXELS = 1280 * 28 * 28


class SarashinaOCR:
    """Sarashina2.2-OCR の推論ラッパー。初回実行時にモデル (~8GB) をダウンロードする。"""

    def __init__(
        self,
        model_id: str = "sbintuitions/sarashina2.2-ocr",
        device: str = "cuda",
        max_pixels: int = DEFAULT_MAX_PIXELS,
    ) -> None:
        try:
            import torch
            from transformers import AutoModelForCausalLM, AutoProcessor
        except ImportError as e:
            raise RuntimeError(
                "transformers / torch が未インストール。pip install transformers torch"
            ) from e
        try:
            self.processor = AutoProcessor.from_pretrained(
                model_id, trust_remote_code=True, max_pixels=max_pixels,
            )
            self.model = AutoModelForCausalLM.from_pretrained(
                model_id, trust_remote_code=True,
                dtype=torch.bfloat16, device_map=device,
                attn_implementation="sdpa",
            )
        except Exception as e:
            raise RuntimeError(
                f"モデルロード失敗 ({model_id}): {e}\n"
                "GPU メモリ不足なら device='cpu' を試してください。"
            ) from e
        self._device = device
        self._max_pixels = max_pixels

    def ocr_page(self, image: PIL.Image.Image) -> str:
        """PIL 画像を受け取り OCR 結果の Markdown テキストを返す。"""
        import torch

        messages = [{"role": "user", "content": [
            {"type": "image", "image": image},
            {"type": "text", "text": "Read the text in the image."},
        ]}]
        inputs = self.processor.apply_chat_template(
            messages, add_generation_prompt=True,
            tokenize=True, return_dict=True, return_tensors="pt",
        ).to(self.model.device)

        with torch.no_grad():
            output_ids = self.model.generate(
                **inputs, max_new_tokens=4096,
                repetition_penalty=1.3,  # 1.2だとループ発生。1.3でBoC-F1が0.623→0.727に改善
            )
        generated_ids = output_ids[:, inputs["input_ids"].shape[1]:]
        result: str = self.processor.batch_decode(generated_ids, skip_special_tokens=True)[0]
        return result

    def ocr_pdf(self, pdf_path: str, dpi: int = 150) -> list[dict[str, str | float]]:
        """PDF の各ページを OCR し、ページごとの結果リストを返す。"""
        try:
            import fitz  # PyMuPDF
        except ImportError as e:
            raise RuntimeError("PyMuPDF 未インストール。pip install pymupdf") from e
        from PIL import Image

        path = Path(pdf_path)
        if not path.exists():
            raise FileNotFoundError(f"PDF が見つかりません: {pdf_path}")

        doc = fitz.open(str(path))
        results: list[dict[str, str | float]] = []
        for i, page in enumerate(doc):
            pix = page.get_pixmap(dpi=dpi)
            image = Image.open(io.BytesIO(pix.tobytes("png"))).convert("RGB")
            t0 = time.time()
            text = self.ocr_page(image)
            elapsed = time.time() - t0
            results.append({
                "page": i + 1,
                "text": text,
                "elapsed_sec": round(elapsed, 1),
                "image_size": f"{image.size[0]}x{image.size[1]}",
            })
        doc.close()
        return results


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Sarashina2.2-OCR PDF → Markdown")
    parser.add_argument("pdf_path", help="対象 PDF ファイルパス")
    parser.add_argument("--model", default="sbintuitions/sarashina2.2-ocr")
    parser.add_argument("--device", default="cuda", help="cuda / cpu")
    parser.add_argument("--dpi", type=int, default=150)
    parser.add_argument("--max-pixels", type=int, default=DEFAULT_MAX_PIXELS)
    parser.add_argument("--json", action="store_true", help="JSON出力")
    args = parser.parse_args()

    ocr = SarashinaOCR(model_id=args.model, device=args.device, max_pixels=args.max_pixels)
    results = ocr.ocr_pdf(args.pdf_path, dpi=args.dpi)

    if args.json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
    else:
        for r in results:
            print("--- Page {} ({}, {:.1f}s) ---".format(r["page"], r["image_size"], r["elapsed_sec"]))
            print(r["text"])
