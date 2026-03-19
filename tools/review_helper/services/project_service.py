"""Project master service: load project_master.xlsx, provide autocomplete."""
from __future__ import annotations

import logging
import re
from pathlib import Path
from unicodedata import normalize as unic_normalize

from ..schemas import ProjectEntry


def _nfkc(s: str) -> str:
    return unic_normalize("NFKC", s or "")

_FLEX_STRIP_RE = re.compile('[\\s\u3000\u30fb\uff65]')  # 半角/全角スペース・中点

def _normalize_flex(s: str) -> str:
    """NFKC + lowercase + スペース・中点除去（柔軟マッチング用）。"""
    return _FLEX_STRIP_RE.sub('', unic_normalize("NFKC", s or "").lower())

logger = logging.getLogger(__name__)


class ProjectService:
    def __init__(self, project_master_path: Path):
        self._path = project_master_path
        self._entries: list[ProjectEntry] = []
        self._load()

    def _load(self):
        # Try importing from batch script first (it's on sys.path)
        try:
            from outlook_save_pdf_and_batch_print import _load_project_master

            raw_entries = _load_project_master(self._path)
            self._entries = [
                ProjectEntry(
                    kojiban=str(getattr(e, "kojiban", "") or ""),
                    kojimei=str(getattr(e, "kojimei", "") or ""),
                    busho=str(getattr(e, "busho", "") or ""),
                    keywords=list(getattr(e, "keywords", []) or []),
                    route_subdir=getattr(e, "route_subdir", None),
                )
                for e in raw_entries
            ]
            logger.info("Loaded %d projects via batch script import", len(self._entries))
            self._normalize_route_subdir()
            return
        except Exception:
            logger.warning("Failed to import _load_project_master, falling back to openpyxl")

        # Fallback: read Excel directly
        try:
            import openpyxl

            wb = openpyxl.load_workbook(self._path, read_only=True, data_only=True)
            ws = wb.active
            if ws is None:
                return
            rows = list(ws.iter_rows(min_row=2, values_only=True))
            for row in rows:
                if not row or not row[0]:
                    continue
                # col0=工事番号, col1=工事名称, col2=キーワード, col3=部署, col4=status
                keywords_raw = str(row[2] or "") if len(row) > 2 else ""
                keywords = [k.strip() for k in keywords_raw.split(",") if k.strip()] if keywords_raw else []
                status = str(row[4] or "active") if len(row) > 4 else "active"
                self._entries.append(
                    ProjectEntry(
                        kojiban=str(row[0] or ""),
                        kojimei=str(row[1] or "") if len(row) > 1 else "",
                        busho=str(row[3] or "") if len(row) > 3 else "",
                        keywords=keywords,
                        status=status,
                    )
                )
            wb.close()
            logger.info("Loaded %d projects via openpyxl", len(self._entries))
            self._normalize_route_subdir()
        except Exception:
            logger.exception("Failed to load project master")

    def _normalize_route_subdir(self):
        """バッチスクリプトと同じ route_subdir ルールを適用する。
        busho == '修繕' → '営繕'、それ以外 → '{kojiban}_{kojimei}' (未設定の場合のみ)。
        """
        for e in self._entries:
            if e.route_subdir:
                continue  # 明示的に設定済みならそのまま
            if e.busho == "修繕":
                e.route_subdir = "営繕"
            else:
                folder = f"{e.kojiban}_{e.kojimei}".strip("_")
                if folder:
                    e.route_subdir = folder

    def search(self, query: str, limit: int = 10) -> list[ProjectEntry]:
        if not query:
            # 空クエリ時は active のみ返す
            active = [e for e in self._entries if e.status == "active"]
            return active[:limit]
        q = _nfkc(query).lower()
        scored: list[tuple[int, ProjectEntry]] = []
        for e in self._entries:
            score = 0
            if q in _nfkc(e.kojimei).lower():
                score += 10
            if q in _nfkc(e.kojiban).lower():
                score += 5
            for kw in e.keywords:
                if q in _nfkc(kw).lower():
                    score += 3
            if score > 0:
                # active を inactive より優先（+100 ボーナス）
                if e.status == "active":
                    score += 100
                scored.append((score, e))
        scored.sort(key=lambda x: -x[0])
        return [e for _, e in scored[:limit]]

    def get_by_number(self, kojiban: str) -> ProjectEntry | None:
        for e in self._entries:
            if e.kojiban == kojiban:
                return e
        return None

    def match_subject(self, subject: str, limit: int = 3, body_snippet: str = "") -> list[ProjectEntry]:
        """件名・本文スニペットにkojimei/keywordsが含まれているエントリを逆方向マッチで返す。
        スペース・中点を除去したフレキシブルマッチも併用（半角スペース混在に対応）。
        body_snippet を渡すと件名＋本文の結合テキストでマッチする。
        """
        combined = f"{subject} {body_snippet}".strip() if body_snippet else subject
        if not combined:
            return []
        text = _nfkc(combined).lower()
        text_flex = _normalize_flex(combined)
        scored: dict[str, tuple[int, ProjectEntry]] = {}
        for e in self._entries:
            score = 0
            nm = _nfkc(e.kojimei).lower()
            nm_flex = _normalize_flex(e.kojimei)
            # 厳密マッチ（スペースそのまま）
            if nm and nm in text:
                score += len(nm) * 3
            # フレキシブルマッチ（スペース・中点を除去して比較）
            elif nm_flex and len(nm_flex) >= 4 and nm_flex in text_flex:
                score += len(nm_flex) * 2
            # キーワードマッチ
            for kw in e.keywords:
                nkw = _nfkc(kw).lower()
                if nkw and nkw in text:
                    score += len(nkw)
                elif _normalize_flex(kw) and _normalize_flex(kw) in text_flex:
                    score += len(_normalize_flex(kw))
            if score > 0:
                # active を inactive より優先（+100 ボーナス）
                if e.status == "active":
                    score += 100
                scored[e.kojiban] = (score, e)
        results = sorted(scored.values(), key=lambda x: -x[0])
        return [e for _, e in results[:limit]]
