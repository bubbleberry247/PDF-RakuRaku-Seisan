"""Queue management: scan review directories, join with manifest, track state."""
from __future__ import annotations

import base64
import hashlib
import json
from datetime import datetime
from pathlib import Path

from ..schemas import QueueItem, StatsResponse


class QueueService:
    def __init__(self, queue_base_dir: Path, manifest_path: Path):
        self._queue_base_dir = queue_base_dir
        self._manifest_path = manifest_path
        self._state_path = queue_base_dir / "_review_state.json"
        self._state: dict[str, dict] = {}
        self._items: dict[str, QueueItem] = {}
        self._load_state()
        self.refresh()

    # --- State persistence ---

    def _load_state(self):
        if self._state_path.exists():
            try:
                self._state = json.loads(self._state_path.read_text("utf-8"))
            except (json.JSONDecodeError, OSError):
                self._state = {}

    def _save_state(self):
        self._state_path.parent.mkdir(parents=True, exist_ok=True)
        self._state_path.write_text(
            json.dumps(self._state, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    # --- Helpers ---

    @staticmethod
    def _sha256_file(path: Path) -> str:
        h = hashlib.sha256()
        with path.open("rb") as f:
            while chunk := f.read(65536):
                h.update(chunk)
        return h.hexdigest()

    @staticmethod
    def _make_item_id(sha256_hex: str, filename: str) -> str:
        """sha256 + filename で一意 ID を生成。同一内容 PDF でもファイル名が異なれば別 ID。"""
        raw = f"{sha256_hex}:{filename}"
        return base64.urlsafe_b64encode(
            hashlib.sha256(raw.encode()).digest()
        ).decode()[:16]

    def _load_manifest_index(self) -> dict[str, dict]:
        """Load manifest JSONL, build {sha256: record} index. Last row wins."""
        index: dict[str, dict] = {}
        if not self._manifest_path.exists():
            return index
        with self._manifest_path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                sha = rec.get("sha256", "")
                if sha:
                    index[sha] = rec
        return index

    # --- Public API ---

    def refresh(self):
        """Rescan queue directories and rebuild item list."""
        manifest = self._load_manifest_index()
        items: dict[str, QueueItem] = {}

        for subdir_name in ("review_required", "unresolved"):
            scan_dir = self._queue_base_dir / subdir_name
            if not scan_dir.is_dir():
                continue
            for pdf in scan_dir.glob("*.pdf"):
                sha = self._sha256_file(pdf)
                item_id = self._make_item_id(sha, pdf.name)
                rec = manifest.get(sha, {})
                st = self._state.get(item_id, {})
                state = st.get("status", "pending")

                items[item_id] = QueueItem(
                    id=item_id,
                    sha256=sha,
                    filename=pdf.name,
                    pdf_path=str(pdf),
                    source_dir=subdir_name,
                    vendor=rec.get("vendor"),
                    issue_date=rec.get("issue_date"),
                    amount=str(rec["amount"]) if rec.get("amount") is not None else None,
                    invoice_no=rec.get("invoice_no"),
                    project=rec.get("project"),
                    route_subdir=rec.get("route_subdir"),
                    route_reason=rec.get("route_reason"),
                    sender=rec.get("sender"),
                    subject=rec.get("subject"),
                    body_snippet=rec.get("body_snippet"),
                    routing_state=rec.get("routing_state"),
                    review_reason=rec.get("review_reason"),
                    message_entry_id=rec.get("message_entry_id"),
                    attachment_name=rec.get("attachment_name"),
                    manifest_key=rec.get("key"),
                    state=state,
                )
        self._items = items

    def list_items(self, status_filter: str | None = None) -> list[QueueItem]:
        if status_filter and status_filter != "all":
            return [it for it in self._items.values() if it.state == status_filter]
        return list(self._items.values())

    def get_item(self, item_id: str) -> QueueItem | None:
        return self._items.get(item_id)

    def set_state(self, item_id: str, status: str, reason: str = ""):
        self._state[item_id] = {
            "status": status,
            "reason": reason,
            "updated_at": datetime.now().isoformat(),
        }
        self._save_state()
        if item_id in self._items:
            self._items[item_id] = self._items[item_id].model_copy(update={"state": status})

    def remove_item(self, item_id: str):
        self._items.pop(item_id, None)
        self._state.pop(item_id, None)
        self._save_state()

    def stats(self) -> StatsResponse:
        items = list(self._items.values())
        return StatsResponse(
            total=len(items),
            pending=sum(1 for i in items if i.state == "pending"),
            confirmed=sum(1 for i in items if i.state == "confirmed"),
            skipped=sum(1 for i in items if i.state == "skipped"),
            excluded=sum(1 for i in items if i.state == "excluded"),
        )
