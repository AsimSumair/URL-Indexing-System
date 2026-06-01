from pydantic import BaseModel, HttpUrl, field_validator
from datetime import datetime
from uuid import UUID
from typing import Optional, List


class URLCreate(BaseModel):
    url: HttpUrl
    client_id: Optional[str] = "default"

    @field_validator('url', mode='after')
    @classmethod
    def clean_url(cls, v):
        return str(v).rstrip(',')


class URLResponse(BaseModel):
    id:                 UUID
    url:                str
    client_id:          str
    status:             str
    pages_found:        int
    retries:            int
    depth:              int
    error_msg:          Optional[str]
    last_crawled_at:    Optional[datetime]
    created_at:         datetime
    indexnow_submitted: bool
    google_submitted:   bool
    sitemap_included:   bool

    class Config:
        from_attributes = True


class BulkURLCreate(BaseModel):
    urls: List[HttpUrl]
    client_id: Optional[str] = "default"

    @field_validator('urls', mode='after')
    @classmethod
    def clean_urls(cls, v):
        return [str(u).rstrip(',') for u in v]


class BulkURLResponse(BaseModel):
    submitted: int
    duplicates: int
    errors: int


class StatsResponse(BaseModel):
    total: int
    indexed: int
    queued: int
    crawling: int
    failed: int
    indexnow_submitted: int
    google_submitted: int


class AccountResponse(BaseModel):
    id:         int
    email:      str
    daily_used: int
    total_used: int
    is_active:  bool
    last_used:  Optional[datetime]

    class Config:
        from_attributes = True