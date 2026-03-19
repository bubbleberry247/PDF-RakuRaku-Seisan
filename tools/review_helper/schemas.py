"""Pydantic models for review_helper API."""
from __future__ import annotations

from pydantic import BaseModel


class QueueItem(BaseModel):
    id: str
    sha256: str
    filename: str
    pdf_path: str
    source_dir: str  # "review_required" | "unresolved"
    vendor: str | None = None
    issue_date: str | None = None
    amount: str | None = None
    invoice_no: str | None = None
    project: str | None = None
    route_subdir: str | None = None
    route_reason: str | None = None
    sender: str | None = None
    subject: str | None = None
    routing_state: str | None = None
    review_reason: str | None = None
    message_entry_id: str | None = None
    attachment_name: str | None = None
    manifest_key: str | None = None  # _processed_attachment_key の値
    state: str = "pending"  # "pending" | "skipped" | "excluded" | "confirmed"
    body_snippet: str | None = None
    subject_project_candidates: list[dict] = []


class OcrResult(BaseModel):
    vendor: str | None = None
    issue_date: str | None = None
    amount: str | None = None
    amount_subtotal: str | None = None
    amount_tax: str | None = None
    amount_total: str | None = None
    amount_due: str | None = None
    invoice_no: str | None = None
    project_hint: str | None = None  # PDF内から抽出した工事名ヒント
    provider: str | None = None
    confidence: str | None = None
    error: str | None = None
    cached: bool = False


class ConfirmRequest(BaseModel):
    vendor: str
    project: str
    route_subdir: str
    issue_date: str | None = None
    amount: str | None = None
    invoice_no: str | None = None


class ProjectEntry(BaseModel):
    kojiban: str
    kojimei: str
    busho: str
    keywords: list[str] = []
    route_subdir: str | None = None
    status: str = "active"  # "active" | "inactive"


class StatsResponse(BaseModel):
    total: int = 0
    pending: int = 0
    confirmed: int = 0
    skipped: int = 0
    excluded: int = 0
