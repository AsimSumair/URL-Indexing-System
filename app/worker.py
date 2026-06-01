"""
Celery Workers — two tasks:
  1. crawl_url     — fetch page, extract content, store in DB
  2. submit_to_google — submit a URL to Google via a service account

Run with:
  celery -A app.worker worker --loglevel=info --concurrency=2
"""
import os
import time
import hashlib
import httpx
from bs4 import BeautifulSoup
from celery import Celery
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

celery = Celery(
    "indexer",
    broker=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
    backend=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
)

celery.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    beat_schedule={
        "reset-google-quotas": {
            "task": "app.worker.reset_daily_quotas",
            "schedule": 86400,
        }
    },
)

_last_request: dict = {}


def rate_limit(domain: str, delay: float = 1.0):
    """1 request per second per domain to be polite."""
    last = _last_request.get(domain, 0)
    wait = delay - (time.time() - last)
    if wait > 0:
        time.sleep(wait)
    _last_request[domain] = time.time()


def make_engine():
    """Shared engine factory with connection limits."""
    from sqlalchemy import create_engine
    return create_engine(
        os.getenv("SYNC_DATABASE_URL"),
        pool_pre_ping=True,
        pool_size=2,
        max_overflow=0,
    )


# ── Task 1: Crawl a URL ────────────────────────────────────────────────────────

@celery.task(bind=True, max_retries=3, default_retry_delay=10)
def crawl_url(self, url_id: str):
    from sqlalchemy.orm import sessionmaker
    from app.models import URL, CrawledPage

    engine = make_engine()
    Session = sessionmaker(engine)

    with Session() as db:
        row = db.get(URL, url_id)
        if not row:
            return {"error": "URL not found"}

        row.status = "crawling"
        db.commit()

        try:
            from urllib.parse import urlparse
            domain = urlparse(row.url).netloc
            rate_limit(domain)

            with httpx.Client(
                timeout=15,
                follow_redirects=True,
                verify=False,
                headers={"User-Agent": "IndexerBot/1.0 (+https://your-domain.com)"},
            ) as client:
                resp = client.get(row.url)
                resp.raise_for_status()

            soup         = BeautifulSoup(resp.text, "lxml")
            title        = soup.title.get_text(strip=True) if soup.title else ""
            body_text    = soup.get_text(separator=" ", strip=True)
            content_hash = hashlib.sha256(body_text.encode()).hexdigest()

            # Check for duplicate content
            existing = db.query(CrawledPage).filter_by(content_hash=content_hash).first()
            if not existing:
                page = CrawledPage(
                    url_id=url_id,
                    page_url=row.url,
                    title=title,
                    body_text=body_text[:50_000],
                    content_hash=content_hash,
                    crawled_at=datetime.utcnow(),
                )
                db.add(page)

            links               = soup.find_all("a", href=True)
            row.status          = "indexed"
            row.pages_found     = len(links)
            row.depth           = 1
            row.last_crawled_at = datetime.utcnow()
            db.commit()

            # Chain: after crawl succeeds, submit to Google indexing API
            submit_to_google.delay(url_id)

        except Exception as exc:
            row.status    = "failed"
            row.error_msg = str(exc)[:500]
            db.commit()
            raise self.retry(exc=exc)


# ── Task 2: Submit to Google Indexing API ─────────────────────────────────────

@celery.task(bind=True, max_retries=2, default_retry_delay=30)
def submit_to_google(self, url_id: str):
    from sqlalchemy.orm import sessionmaker
    from app.models import URL, GoogleAccount, IndexingLog
    from app.google_service import submit_url_to_google
    from datetime import date

    engine = make_engine()
    Session = sessionmaker(engine)

    with Session() as db:
        row = db.get(URL, url_id)
        if not row or row.google_submitted:
            return

        today = date.today()
        accounts = (
            db.query(GoogleAccount)
            .filter(GoogleAccount.is_active == True)
            .filter(GoogleAccount.daily_used < 200)
            .order_by(GoogleAccount.daily_used.asc())
            .all()
        )

        # Reset counters if it is a new day
        for acc in accounts:
            if acc.last_reset and acc.last_reset.date() < today:
                acc.daily_used = 0
                acc.last_reset = datetime.utcnow()
        db.commit()

        # Re-query after reset
        account = (
            db.query(GoogleAccount)
            .filter(GoogleAccount.is_active == True)
            .filter(GoogleAccount.daily_used < 200)
            .order_by(GoogleAccount.daily_used.asc())
            .first()
        )

        if not account:
            log = IndexingLog(
                url_id=url_id,
                layer="google",
                status="skipped",
                detail="No Google accounts with remaining quota",
            )
            db.add(log)
            db.commit()
            return

        result = submit_url_to_google(account.key_file, row.url)

        log = IndexingLog(
            url_id=url_id,
            layer="google",
            status="submitted" if result["success"] else "failed",
            detail=result.get("error") or result.get("response") or "",
        )
        db.add(log)

        if result["success"]:
            row.google_submitted = True
            account.daily_used  += 1
            account.total_used  += 1
            account.last_used    = datetime.utcnow()

        db.commit()


# ── Task 3: Reset daily quotas (runs via Celery Beat) ─────────────────────────

@celery.task
def reset_daily_quotas():
    from sqlalchemy.orm import sessionmaker
    from app.models import GoogleAccount

    engine = make_engine()
    Session = sessionmaker(engine)

    with Session() as db:
        db.query(GoogleAccount).update({
            "daily_used": 0,
            "last_reset": datetime.utcnow(),
        })
        db.commit()

    return "Daily quotas reset"