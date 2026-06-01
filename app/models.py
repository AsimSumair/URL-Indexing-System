import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, Text, DateTime, ForeignKey, Boolean
from sqlalchemy.dialects.postgresql import UUID
from app.database import Base


class URL(Base):
    __tablename__ = "urls"

    id              = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    url             = Column(Text, unique=True, nullable=False)
    client_id       = Column(String, default="default")        # which client owns this URL
    status          = Column(String, default="queued")         # queued | crawling | indexed | failed
    pages_found     = Column(Integer, default=0)
    depth           = Column(Integer, default=0)
    retries         = Column(Integer, default=0)
    error_msg       = Column(Text, nullable=True)
    last_crawled_at = Column(DateTime(timezone=True), nullable=True)
    created_at      = Column(DateTime(timezone=True), default=datetime.utcnow)

    # Indexing tracking
    indexnow_submitted  = Column(Boolean, default=False)
    google_submitted    = Column(Boolean, default=False)
    sitemap_included    = Column(Boolean, default=False)


class CrawledPage(Base):
    __tablename__ = "crawled_pages"

    id           = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    url_id       = Column(UUID(as_uuid=True), ForeignKey("urls.id"))
    page_url     = Column(Text)
    title        = Column(Text)
    body_text    = Column(Text)
    content_hash = Column(String)
    crawled_at   = Column(DateTime(timezone=True), default=datetime.utcnow)


class GoogleAccount(Base):
    """
    Tracks each service account and how many URLs it has submitted today.
    Reset daily_used to 0 each midnight.
    """
    __tablename__ = "google_accounts"

    id          = Column(Integer, primary_key=True, autoincrement=True)
    key_file    = Column(String, unique=True, nullable=False)  # path to JSON key
    email       = Column(String)                               # service account email
    daily_used  = Column(Integer, default=0)                   # resets each day
    total_used  = Column(Integer, default=0)
    last_used   = Column(DateTime(timezone=True), nullable=True)
    last_reset  = Column(DateTime(timezone=True), default=datetime.utcnow)
    is_active   = Column(Boolean, default=True)


class IndexingLog(Base):
    """Audit log — every submission to every layer is recorded here."""
    __tablename__ = "indexing_logs"

    id         = Column(Integer, primary_key=True, autoincrement=True)
    url_id     = Column(UUID(as_uuid=True), ForeignKey("urls.id"))
    layer      = Column(String)      # indexnow | google | sitemap
    status     = Column(String)      # submitted | failed
    detail     = Column(Text)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)