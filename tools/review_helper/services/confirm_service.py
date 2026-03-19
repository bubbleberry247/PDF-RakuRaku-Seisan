"""Confirm service: rename, copy to live folder, update manifest (atomic copy-then-delete)."""
from __future__ import annotations

import hashlib
import json
import logging
import msvcrt
import shutil
from datetime import datetime
from pathlib import Path
from unicodedata import normalize as unic_normalize

from ..schemas import ConfirmRequest, QueueItem

logger = logging.getLogger(__name__)


def _vendor_short_fallback(vendor: str) -> str:
    """Strip corporate suffixes. Fallback if batch script import fails."""
    for suffix in ("株式会社", "有限会社", "合同会社", "合資会社"):
        vendor = vendor.replace(suffix, "")
    return vendor.strip()


def _sanitize_fallback(name: str) -> str:
    """Basic filename sanitization."""
    for ch in r'\/:*?"<>|':
        name = name.replace(ch, "_")
    return name.strip()[:200]


def _processed_attachment_key_fallback(
    entry_id: str, attachment_name: str, sha256: str
) -> str:
    """Replicate batch script's _processed_attachment_key without importing it."""
    raw = "\n".join(
        [
            str(entry_id or "").strip(),
            unic_normalize("NFKC", str(attachment_name or "").strip()),
            str(sha256 or "").strip(),
        ]
    )
    return hashlib.sha1(raw.encode("utf-8", errors="ignore")).hexdigest()


class ConfirmService:
    def __init__(self, save_dir: Path, payment_month: str, manifest_path: Path):
        self._save_dir = save_dir
        self._payment_month = payment_month
        self._manifest_path = manifest_path
        self._vendor_short = _vendor_short_fallback
        self._sanitize = _sanitize_fallback
        self._compute_key = _processed_attachment_key_fallback
        self._init_batch_imports()

    def _init_batch_imports(self):
        """Try to import helper functions from the batch script."""
        try:
            from outlook_save_pdf_and_batch_print import (
                _processed_attachment_key,
                _sanitize_filename,
                _vendor_short,
            )
            self._vendor_short = _vendor_short
            self._sanitize = _sanitize_filename
            self._compute_key = _processed_attachment_key
        except ImportError:
            logger.warning("Batch script import failed, using fallback helpers")

    def _validate_route_subdir(self, route_subdir: str) -> str:
        """NFKC 正規化を先に行い、パストラバーサルを防止する。正規化済み値を返す。"""
        from pathlib import PurePosixPath, PureWindowsPath

        # 正規化を先に実施（全角ピリオド ．． → .. 等の変換後に検証するため）
        norm = unic_normalize("NFKC", route_subdir)
        for cls in (PurePosixPath, PureWindowsPath):
            p = cls(norm)
            if p.is_absolute() or ".." in p.parts:
                raise ValueError(f"Invalid route_subdir: {route_subdir!r}")
        resolved = (self._save_dir / self._payment_month / norm).resolve()
        base = (self._save_dir / self._payment_month).resolve()
        try:
            resolved.relative_to(base)
        except ValueError:
            raise ValueError(f"route_subdir escapes save_dir: {route_subdir!r}")
        return norm

    def _unique_path(self, path: Path) -> Path:
        if not path.exists():
            return path
        stem = path.stem
        suffix = path.suffix
        parent = path.parent
        for i in range(1, 1000):
            candidate = parent / f"{stem}_{i}{suffix}"
            if not candidate.exists():
                return candidate
        return parent / f"{stem}_{datetime.now().strftime('%H%M%S')}{suffix}"

    def _build_filename(self, vendor: str, project: str) -> str:
        vs = self._sanitize(self._vendor_short(unic_normalize("NFKC", vendor)))
        ps = self._sanitize(unic_normalize("NFKC", project))
        return f"{ps}_{vs}.pdf"

    def confirm(self, item: QueueItem, req: ConfirmRequest) -> str:
        # 1. パストラバーサル検証（NFKC 正規化済みの値を返す）
        route_subdir_norm = self._validate_route_subdir(req.route_subdir)

        src = Path(item.pdf_path)
        if not src.exists():
            raise FileNotFoundError(f"Source PDF not found: {src}")

        # 2. 移動先パス構築
        filename = self._build_filename(req.vendor, req.project)
        dest_dir = self._save_dir / self._payment_month / route_subdir_norm
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = self._unique_path(dest_dir / filename)

        # 3. copy-then-delete パターン（原子性確保）
        #    copy が成功した時点で src は残る。manifest 書き込み失敗時は dest を削除。
        shutil.copy2(str(src), str(dest))
        logger.info("Copied %s -> %s", src, dest)

        try:
            self._append_manifest(item=item, req=req, new_path=dest)
        except Exception:
            dest.unlink(missing_ok=True)  # ロールバック
            logger.error("Manifest append failed; rolled back dest %s", dest)
            raise

        # 4. コピー元削除（失敗しても manifest は正しい）
        try:
            src.unlink()
        except OSError:
            logger.warning("Failed to delete source %s (manifest already updated)", src)

        return str(dest)

    def _append_manifest(self, item: QueueItem, req: ConfirmRequest, new_path: Path):
        """manifest JSONL に human resolve レコードを追記（排他ロック付き）。"""
        # dedupe key を再現（バッチスクリプトの _load_processed_attachment_index が読める形式）
        key = self._compute_key(
            item.message_entry_id or "",
            item.attachment_name or "",
            item.sha256,
        )
        record = {
            "key": key,
            "message_entry_id": item.message_entry_id,
            "attachment_name": item.attachment_name,
            "sha256": item.sha256,
            "saved_path": str(new_path),
            "vendor": req.vendor,
            "issue_date": req.issue_date,
            "amount": req.amount,
            "invoice_no": req.invoice_no,
            "project": req.project,
            "route_subdir": req.route_subdir,
            "sender": item.sender,
            "subject": item.subject,
            "routing_state": "auto_final",
            "review_reason": None,
            "resolved_by": "human",
            "resolved_at": datetime.now().isoformat(),
        }
        self._manifest_path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(record, ensure_ascii=False) + "\n"
        with self._manifest_path.open("a", encoding="utf-8") as f:
            # Windows 排他ロック（1バイト単位 — JSONL append には十分）
            try:
                msvcrt.locking(f.fileno(), msvcrt.LK_LOCK, 1)
            except OSError as e:
                raise OSError(f"Manifest file lock failed: {self._manifest_path}") from e
            try:
                f.write(line)
                f.flush()
            finally:
                try:
                    msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
                except OSError:
                    pass
