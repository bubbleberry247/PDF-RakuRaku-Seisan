from __future__ import annotations

import csv
import re
from collections import OrderedDict
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
IMAGE_EXTS = {".png"}


def pick_manifest() -> Path:
    candidates = sorted(
        (
            BASE_DIR / name
            for name in [
                "figures_manifest_kw_20260214_224222.csv",
                "figures_manifest_kw_*.csv",
                "figures_manifest_all_*.csv",
                "figures_manifest.csv",
            ]
        ),
        key=lambda p: p.name,
    )
    existing = []
    for pattern in candidates:
        if pattern.is_file():
            existing.append(pattern)
        elif any(char in pattern.name for char in "*?[]"):
            existing.extend(sorted(BASE_DIR.glob(pattern.name)))

    if not existing:
        raise FileNotFoundError("No manifest file found under docs/assets/doboku-14w/figures")
    return existing[-1]


def read_manifest(manifest_path: Path):
    rows = []
    with manifest_path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames:
            reader.fieldnames = [name.lstrip("\ufeff") if name else name for name in reader.fieldnames]
        for row in reader:
            if row is None:
                continue
            qid = row.get("qId") or ""
            if not qid:
                base = Path(row.get("outFile") or row.get("fileName") or row.get("image") or "").stem
                if not base:
                    continue
                qid = base

            filename = row.get("fileName") or row.get("outFile") or row.get("image")
            if not filename:
                continue

            # Keep only basename for local relative linking.
            filename = Path(filename).name
            if Path(filename).suffix.lower() not in IMAGE_EXTS:
                continue

            rows.append((qid, filename))
    return rows


def scan_choice_files(base_stem: str) -> list[str]:
    pattern = re.compile(rf"^{re.escape(base_stem)}_選択肢")
    choices = []
    for p in sorted(BASE_DIR.glob("*.png")):
        if pattern.search(p.stem):
            choices.append(p.name)
    return choices


def build_pairs_html(entries: list[tuple[str, str]]) -> str:
    rows_html = []
    for qid, filename in entries:
        image_path = BASE_DIR / filename
        if not image_path.exists():
            continue

        base_stem = image_path.stem
        choices = scan_choice_files(base_stem)
        choice_html = "\n".join(
            [
                '      <div class="item">'
                f'<div class="caption">{choice}</div>'
                f'<img loading="lazy" src="{choice}" alt="{qid} choice" />'
                "</div>"
                for choice in choices
            ]
        )
        if not choice_html:
            choice_html = '      <div class="note">この問題の「選択肢切り取り画像」は見つかりませんでした。</div>'

        rows_html.append(
            "<section class=\"pair\">"
            f"<h2>{qid}</h2>"
            f"<div class=\"file\">{filename}</div>"
            '<div class="compare">'
            "<div class=\"cell\">"
            f"<div class=\"caption\">問題画像</div>"
            f'<img loading=\"lazy\" src=\"{filename}\" alt=\"{qid} image\" />'
            "</div>"
            '<div class="cell">'
            "<div class=\"caption\">関連画像</div>"
            '<div class="subgrid">'
            f"{choice_html}"
            "</div>"
            "</div>"
            "</div>"
            "</section>"
        )

    return f"""<!doctype html>
<html lang="ja">
<head>
  <meta charset="utf-8" />
  <title>図表説明用画像一覧（QID別）</title>
  <style>
    :root {{ --line: #e2e8f0; --bg: #0f172a; }}
    body {{ font-family: Arial, sans-serif; padding: 16px; background:#f5f5f7; color:#0f172a; }}
    h1 {{ margin: 0 0 12px; }}
    .meta {{ color:#334155; margin-bottom: 14px; font-size: 14px; }}
    .pair {{ border: 1px solid var(--line); border-radius: 10px; padding: 12px; margin-bottom: 16px; background: #fff; }}
    .file {{ color:#475569; font-size: 12px; margin: 2px 0 10px; word-break: break-all; }}
    .compare {{ display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }}
    .cell {{ border: 1px solid #dbe2ea; border-radius: 8px; padding: 8px; background:#f8fafc; }}
    .caption {{ font-size: 12px; color:#334155; margin-bottom: 6px; }}
    img {{ width: 100%; max-width: 620px; height: auto; display:block; border: 1px solid #cbd5e1; }}
    .subgrid {{ display:grid; grid-template-columns: repeat(auto-fill,minmax(150px,1fr)); gap: 8px; }}
    .subgrid .item {{ border: 1px solid #dbe2ea; border-radius: 8px; padding: 8px; background:#fff; }}
    .subgrid .note {{ font-size: 12px; color:#64748b; }}
    .subgrid img {{ max-width: 100%; }}
    @media (max-width: 900px) {{ .compare {{ grid-template-columns: 1fr; }} }}
  </style>
</head>
<body>
  <h1>図表説明用画像をアップロード済み一覧</h1>
  <div class="meta">説明文脈で利用する画像をQID単位で整理しています。全{len(entries)}件（画像名ベース）</div>
  {'\n'.join(rows_html)}
</body>
</html>
"""


def build_all_full_html(entries: list[tuple[str, str]]) -> str:
    cards = []
    for qid, filename in entries:
        p = BASE_DIR / filename
        if not p.exists():
            continue
        cards.append(
            f'<div class="item"><a href="{filename}" target="_blank" rel="noreferrer">'
            f'<img loading="lazy" src="{filename}" alt="{qid}" /></a>'
            f'<div class="name">{qid} / {filename}</div>'
            "</div>"
        )

    return f"""<!doctype html>
<html lang=\"ja\">
<head>
<meta charset=\"utf-8\" />
<title>図表説明用画像（全件）</title>
<style>
  body{{font-family:system-ui,Arial,sans-serif;padding:16px;background:#fff;}}
  .grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(240px,1fr));gap:14px;}}
  .item{{border:1px solid #ddd;padding:8px;border-radius:8px;}}
  img{{max-width:220px;width:100%;height:auto;border:1px solid #ccc;}}
  .name{{font-size:12px;color:#333;word-break:break-all;margin-top:4px;}}
</style>
</head>
<body>
<h1>図表説明用画像（全件）</h1>
<div class="grid">
{chr(10).join(cards)}
</div>
</body>
</html>
"""


def main() -> None:
    manifest_path = pick_manifest()
    entries = read_manifest(manifest_path)
    if not entries:
        raise RuntimeError(f"No valid rows in manifest: {manifest_path}")

    # Remove duplicate entries while keeping original order.
    dedup = OrderedDict()
    for qid, fname in entries:
        if fname not in dedup:
            dedup[fname] = qid

    ordered = [(qid, fname) for fname, qid in dedup.items()]

    gallery_pairs = BASE_DIR / "gallery_pairs.html"
    gallery_all_full = BASE_DIR / "gallery_all_full.html"

    gallery_pairs.write_text(build_pairs_html(ordered), encoding="utf-8")
    gallery_all_full.write_text(build_all_full_html(ordered), encoding="utf-8")

    print(f"Generated: {gallery_pairs}")
    print(f"Generated: {gallery_all_full}")
    print(f"Source manifest: {manifest_path.name}")


if __name__ == "__main__":
    main()
