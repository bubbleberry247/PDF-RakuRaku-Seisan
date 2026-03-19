"""FastAPI application factory for review_helper."""
from __future__ import annotations

import sys
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .config import load_config
from .schemas import ConfirmRequest, OcrResult, QueueItem, StatsResponse


def create_app() -> FastAPI:
    cfg = load_config()

    # Add tools_dir to sys.path so we can lazy-import batch script functions
    tools_str = str(cfg.tools_dir)
    if tools_str not in sys.path:
        sys.path.insert(0, tools_str)

    app = FastAPI(title="review_helper", version="0.1.0")

    # CORS for localhost dev
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:8021", "http://127.0.0.1:8021"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Static files
    static_dir = Path(__file__).resolve().parent / "static"
    if static_dir.is_dir():
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    # --- Initialize services ---
    from .services.queue_service import QueueService
    from .services.ocr_service import OcrService
    from .services.project_service import ProjectService
    from .services.confirm_service import ConfirmService

    queue_svc = QueueService(
        queue_base_dir=cfg.queue_base_dir,
        manifest_path=cfg.manifest_path,
    )
    ocr_svc = OcrService(cache_dir=cfg.ocr_cache_dir)
    project_svc = ProjectService(project_master_path=cfg.project_master_path)
    confirm_svc = ConfirmService(
        save_dir=cfg.save_dir,
        payment_month=cfg.payment_month,
        manifest_path=cfg.manifest_path,
    )

    app.state.cfg = cfg
    app.state.queue_svc = queue_svc
    app.state.ocr_svc = ocr_svc
    app.state.project_svc = project_svc
    app.state.confirm_svc = confirm_svc

    # --- Routes ---

    @app.get("/")
    async def index():
        index_html = static_dir / "index.html"
        if index_html.exists():
            return FileResponse(str(index_html))
        raise HTTPException(404, "index.html not found")

    @app.get("/healthz")
    async def healthz():
        return {"status": "ok"}

    @app.get("/api/v1/queue", response_model=list[QueueItem])
    async def list_queue():
        queue_svc.refresh()
        items = queue_svc.list_items()
        enriched = []
        for item in items:
            candidates = project_svc.match_subject(
                item.subject or "",
                limit=3,
                body_snippet=item.body_snippet or "",
            )
            enriched.append(item.model_copy(update={
                "subject_project_candidates": [c.model_dump() for c in candidates]
            }))
        return enriched

    @app.get("/api/v1/queue/{item_id}", response_model=QueueItem)
    async def get_queue_item(item_id: str):
        item = queue_svc.get_item(item_id)
        if item is None:
            raise HTTPException(404, f"Item not found: {item_id}")
        return item

    @app.get("/api/v1/queue/{item_id}/pdf")
    async def get_pdf(item_id: str):
        item = queue_svc.get_item(item_id)
        if item is None:
            raise HTTPException(404, f"Item not found: {item_id}")
        pdf_path = Path(item.pdf_path)
        if not pdf_path.exists():
            raise HTTPException(404, f"PDF file not found: {pdf_path}")
        return FileResponse(str(pdf_path), media_type="application/pdf")

    @app.post("/api/v1/queue/{item_id}/ocr", response_model=OcrResult)
    async def run_ocr(item_id: str):
        item = queue_svc.get_item(item_id)
        if item is None:
            raise HTTPException(404, f"Item not found: {item_id}")
        return ocr_svc.extract(
            pdf_path=Path(item.pdf_path),
            sha256=item.sha256,
            sender_hint=item.sender,
            subject_hint=item.subject,
        )

    @app.post("/api/v1/queue/{item_id}/confirm", response_model=QueueItem)
    async def confirm_item(item_id: str, req: ConfirmRequest):
        item = queue_svc.get_item(item_id)
        if item is None:
            raise HTTPException(404, f"Item not found: {item_id}")
        if item.state == "confirmed":
            raise HTTPException(409, f"Already confirmed: {item_id}")
        try:
            confirm_svc.confirm(item=item, req=req)
        except (ValueError, FileNotFoundError) as e:
            raise HTTPException(400, str(e))
        queue_svc.set_state(item_id, "confirmed")
        return queue_svc.get_item(item_id)

    @app.post("/api/v1/queue/{item_id}/skip", response_model=QueueItem)
    async def skip_item(item_id: str):
        item = queue_svc.get_item(item_id)
        if item is None:
            raise HTTPException(404, f"Item not found: {item_id}")
        queue_svc.set_state(item_id, "skipped")
        return queue_svc.get_item(item_id)

    @app.post("/api/v1/queue/{item_id}/exclude", response_model=QueueItem)
    async def exclude_item(item_id: str):
        item = queue_svc.get_item(item_id)
        if item is None:
            raise HTTPException(404, f"Item not found: {item_id}")
        queue_svc.set_state(item_id, "excluded")
        return queue_svc.get_item(item_id)

    @app.get("/api/v1/projects", response_model=list)
    async def list_projects(q: str = ""):
        return project_svc.search(q)

    @app.get("/api/v1/stats", response_model=StatsResponse)
    async def get_stats():
        return queue_svc.stats()

    return app
