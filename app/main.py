"""
FastAPI application — all routes + serves the frontend HTML.

Endpoints:
  GET  /                        → serves index.html
  GET  /sitemaps/{client_id}    → XML sitemap for that client
  POST /api/urls                → submit a single URL
  POST /api/urls/bulk           → submit up to 10,000 URLs at once
  GET  /api/urls                → list all URLs (optional ?client_id=)
  POST /api/urls/{id}/retry     → retry a failed URL
  GET  /api/stats               → counts by status
  POST /api/indexnow/submit     → manually trigger IndexNow for all pending
  GET  /api/accounts            → list Google service accounts
  POST /api/accounts/scan       → auto-scan ./google_keys/ and register new accounts
  GET  /api/logs/{url_id}       → indexing log for a URL
"""
from fastapi import FastAPI, Depends, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import UUID
import os
import pathlib

from app.database import get_db, engine, Base
from app.schemas import URLCreate, URLResponse, BulkURLCreate, BulkURLResponse, AccountResponse
from app import crud
from app.worker import crawl_url
from app.indexnow_service import submit_indexnow
from app.sitemap_service import generate_sitemap, ping_google_sitemap
from app.google_service import scan_key_files
from app.models import URL, IndexingLog

app = FastAPI(title="URL Indexing System", version="2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

FRONTEND_PATH = pathlib.Path(__file__).parent.parent / "index.html"

@app.get("/googleeca36eae2be9e165.html")
async def google_verify():
    return Response(
        content="google-site-verification: googleeca36eae2be9e165.html",
        media_type="text/html"
    )

# ── Startup: create tables ──────────────────────────────────────────────────

@app.on_event("startup")
async def startup():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


# ── Frontend ────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def serve_frontend():
    if FRONTEND_PATH.exists():
        return FRONTEND_PATH.read_text()
    return "<h1>Frontend not found — place index.html in the project root</h1>"


# ── Sitemap ─────────────────────────────────────────────────────────────────

@app.get("/sitemaps/{client_id}")
async def get_sitemap(client_id: str, db: AsyncSession = Depends(get_db)):
    rows = await crud.get_all_urls(db, client_id=client_id)
    urls = [r.url for r in rows if r.status == "indexed"]
    xml = generate_sitemap(urls)
    return Response(content=xml, media_type="application/xml")


# ── URL submission ───────────────────────────────────────────────────────────

@app.post("/api/urls", response_model=URLResponse)
async def submit_url(payload: URLCreate, db: AsyncSession = Depends(get_db)):
    existing = await crud.get_url_by_url(db, str(payload.url))
    if existing:
        raise HTTPException(status_code=409, detail="URL already exists")

    row = await crud.create_url(db, str(payload.url), payload.client_id)
    crawl_url.delay(str(row.id))
    return row


@app.post("/api/urls/bulk", response_model=BulkURLResponse)
async def submit_bulk(payload: BulkURLCreate, db: AsyncSession = Depends(get_db)):
    submitted = 0
    duplicates = 0
    errors = 0

    for url in payload.urls:
        try:
            existing = await crud.get_url_by_url(db, str(url))
            if existing:
                duplicates += 1
                continue
            row = await crud.create_url(db, str(url), payload.client_id)
            crawl_url.delay(str(row.id))
            submitted += 1
        except Exception:
            errors += 1

    # After bulk insert, trigger IndexNow for all newly submitted URLs
    if submitted > 0:
        new_rows = await crud.get_all_urls(db, client_id=payload.client_id)
        pending = [r.url for r in new_rows if not r.indexnow_submitted]
        if pending:
            result = await submit_indexnow(pending)
            if result["success"]:
                ids = [r.id for r in new_rows if not r.indexnow_submitted]
                await crud.mark_indexnow_submitted(db, ids)

    return {"submitted": submitted, "duplicates": duplicates, "errors": errors}


@app.get("/api/urls", response_model=list[URLResponse])
async def list_urls(client_id: str = None, db: AsyncSession = Depends(get_db)):
    return await crud.get_all_urls(db, client_id=client_id)


@app.post("/api/urls/{url_id}/retry", response_model=URLResponse)
async def retry_url(url_id: UUID, db: AsyncSession = Depends(get_db)):
    row = await crud.get_url_by_id(db, url_id)
    if not row:
        raise HTTPException(status_code=404, detail="Not found")

    row.retries += 1
    row = await crud.update_url_status(db, row, "queued")
    crawl_url.delay(str(url_id))
    return row


# ── Stats ────────────────────────────────────────────────────────────────────

@app.get("/api/stats")
async def get_stats(client_id: str = None, db: AsyncSession = Depends(get_db)):
    return await crud.get_stats(db, client_id=client_id)


# ── Manual IndexNow trigger ──────────────────────────────────────────────────

@app.post("/api/indexnow/submit")
async def trigger_indexnow(db: AsyncSession = Depends(get_db)):
    """Submit all pending (not yet IndexNow-submitted) URLs."""
    rows = await crud.get_all_urls(db)
    pending = [r for r in rows if not r.indexnow_submitted]
    if not pending:
        return {"message": "No pending URLs", "submitted": 0}

    urls = [r.url for r in pending]
    result = await submit_indexnow(urls)

    if result["success"]:
        ids = [r.id for r in pending]
        await crud.mark_indexnow_submitted(db, ids)

    return result


# ── Google accounts ──────────────────────────────────────────────────────────

@app.get("/api/accounts", response_model=list[AccountResponse])
async def list_accounts(db: AsyncSession = Depends(get_db)):
    return await crud.get_all_accounts(db)


@app.post("/api/accounts/scan")
async def scan_accounts(db: AsyncSession = Depends(get_db)):
    """
    Scan ./google_keys/ folder and register any new JSON key files
    as Google service accounts in the database.
    """
    found = scan_key_files()
    added = 0
    for item in found:
        from app.models import GoogleAccount
        from sqlalchemy import select
        result = await db.execute(
            select(GoogleAccount).where(GoogleAccount.key_file == item["key_file"])
        )
        existing = result.scalar_one_or_none()
        if not existing:
            await crud.add_google_account(db, item["key_file"], item["email"])
            added += 1

    return {"found": len(found), "newly_registered": added}


# ── Indexing log ─────────────────────────────────────────────────────────────

@app.get("/api/logs/{url_id}")
async def get_logs(url_id: UUID, db: AsyncSession = Depends(get_db)):
    from sqlalchemy import select
    result = await db.execute(
        select(IndexingLog)
        .where(IndexingLog.url_id == url_id)
        .order_by(IndexingLog.created_at.desc())
    )
    logs = result.scalars().all()
    return [
        {
            "layer":      l.layer,
            "status":     l.status,
            "detail":     l.detail,
            "created_at": l.created_at,
        }
        for l in logs
    ]