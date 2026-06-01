from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, update
from datetime import datetime, date
from typing import Optional
from app.models import URL, GoogleAccount, IndexingLog, CrawledPage


# ── URL operations ─────────────────────────────────────────────────────────────

async def get_url_by_url(db: AsyncSession, url: str):
    result = await db.execute(select(URL).where(URL.url == url))
    return result.scalar_one_or_none()


async def create_url(db: AsyncSession, url: str, client_id: str = "default"):
    row = URL(url=url, client_id=client_id)
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


async def get_all_urls(db: AsyncSession, client_id: Optional[str] = None):
    q = select(URL).order_by(URL.created_at.desc())
    if client_id:
        q = q.where(URL.client_id == client_id)
    result = await db.execute(q)
    return result.scalars().all()


async def get_url_by_id(db: AsyncSession, url_id):
    result = await db.execute(select(URL).where(URL.id == url_id))
    return result.scalar_one_or_none()


async def update_url_status(db: AsyncSession, row: URL, status: str):
    row.status = status
    await db.commit()
    await db.refresh(row)
    return row


async def mark_indexnow_submitted(db: AsyncSession, url_ids: list):
    await db.execute(
        update(URL).where(URL.id.in_(url_ids)).values(indexnow_submitted=True)
    )
    await db.commit()


async def mark_google_submitted(db: AsyncSession, url_id):
    await db.execute(
        update(URL).where(URL.id == url_id).values(google_submitted=True)
    )
    await db.commit()


async def get_stats(db: AsyncSession, client_id: Optional[str] = None):
    q = select(URL.status, func.count().label("count")).group_by(URL.status)
    if client_id:
        q = q.where(URL.client_id == client_id)
    result = await db.execute(q)
    stats = {row.status: row.count for row in result}

    in_q = select(func.count()).where(URL.indexnow_submitted == True)
    goog = select(func.count()).where(URL.google_submitted == True)
    if client_id:
        in_q = in_q.where(URL.client_id == client_id)
        goog = goog.where(URL.client_id == client_id)

    inow = (await db.execute(in_q)).scalar()
    gsub = (await db.execute(goog)).scalar()

    total = sum(stats.values())
    return {
        "total":              total,
        "indexed":            stats.get("indexed", 0),
        "queued":             stats.get("queued", 0),
        "crawling":           stats.get("crawling", 0),
        "failed":             stats.get("failed", 0),
        "indexnow_submitted": inow,
        "google_submitted":   gsub,
    }


# ── Google account rotation ────────────────────────────────────────────────────

DAILY_QUOTA = 200


async def get_next_google_account(db: AsyncSession) -> Optional[GoogleAccount]:
    """Return the active account with the most remaining daily quota."""
    today = date.today()
    result = await db.execute(
        select(GoogleAccount)
        .where(GoogleAccount.is_active == True)
        .where(GoogleAccount.daily_used < DAILY_QUOTA)
        .order_by(GoogleAccount.daily_used.asc())
    )
    accounts = result.scalars().all()

    for acc in accounts:
        # Reset counter if last reset was a different day
        if acc.last_reset is None or acc.last_reset.date() < today:
            acc.daily_used = 0
            acc.last_reset = datetime.utcnow()
            await db.commit()

    result2 = await db.execute(
        select(GoogleAccount)
        .where(GoogleAccount.is_active == True)
        .where(GoogleAccount.daily_used < DAILY_QUOTA)
        .order_by(GoogleAccount.daily_used.asc())
        .limit(1)
    )
    return result2.scalar_one_or_none()


async def increment_account_usage(db: AsyncSession, account: GoogleAccount):
    account.daily_used += 1
    account.total_used += 1
    account.last_used = datetime.utcnow()
    await db.commit()


async def get_all_accounts(db: AsyncSession):
    result = await db.execute(
        select(GoogleAccount).order_by(GoogleAccount.daily_used.desc())
    )
    return result.scalars().all()


async def add_google_account(db: AsyncSession, key_file: str, email: str):
    acc = GoogleAccount(key_file=key_file, email=email)
    db.add(acc)
    await db.commit()
    await db.refresh(acc)
    return acc


# ── Indexing log ───────────────────────────────────────────────────────────────

async def log_indexing(db: AsyncSession, url_id, layer: str, status: str, detail: str = ""):
    entry = IndexingLog(url_id=url_id, layer=layer, status=status, detail=detail)
    db.add(entry)
    await db.commit()