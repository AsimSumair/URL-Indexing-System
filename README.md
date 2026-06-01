# URL-Indexing-System

A zero-cost, three-layer URL indexing system that submits 50,000+ URLs per day to Google, Bing, and Yandex — without paying for any third-party tool.

---

## The Problem

Every free indexing tool on the market caps you at 100 to 500 URLs per day. The reason is simple — they are all middlemen. They call the same free Google and Bing APIs that anyone can access, wrap them in a UI, and charge you for it. On top of that your URL data lives on their servers and you have zero control over retry logic, crawl depth, or client segmentation.

This system removes that middleman entirely.

---

## How It Works

Three layers run simultaneously. If one fails the others keep going.

### Layer 1 — IndexNow
Submits URLs directly to Bing and Yandex in real time. One API call handles up to 10,000 URLs and they get indexed within minutes. Completely free, no quota, no expiry.

### Layer 2 — Google Indexing API
Uses rotating Google service accounts to submit URLs directly to Google. Each service account gets 200 URL submissions per day. With 250 accounts that is 50,000 URLs per day from Google alone. Service accounts are free to create on Google Cloud.

### Layer 3 — XML Sitemaps
Auto-generated per client. Google crawls these on its own schedule with no API quota and no daily limits. This layer runs passively in the background 24/7 as a safety net — even when the other layers are down.

**Combined capacity: 100,000+ URLs per day at essentially zero running cost.**

---

## Tech Stack

| Layer | Tools |
|-------|-------|
| API | FastAPI + Uvicorn |
| Workers | Celery + Redis |
| Database | PostgreSQL + SQLAlchemy Async + Alembic |
| Crawling | httpx + BeautifulSoup4 |
| Google API | google-auth + google-api-python-client |
| IndexNow | httpx (single POST call, no SDK needed) |

---

## Features

- Submit single URLs or bulk up to 10,000 at once
- Automatic Celery task chaining — crawl then Google submit with no manual trigger
- Smart account rotation — always picks the account with lowest daily usage
- Automatic quota reset every midnight via Celery Beat
- Per-client sitemap segmentation at `/sitemaps/{client_id}`
- Full audit trail — every submission across all three layers is logged
- Duplicate content detection using SHA-256 hashing
- Retry logic with exponential backoff on failures
- Multi-tenant support with client_id partitioning

---

## Project Structure

```
Crawler Dashboard/
├── app/
│   ├── __init__.py
│   ├── database.py          # Database connection and session
│   ├── models.py            # SQLAlchemy models
│   ├── schemas.py           # Pydantic request/response schemas
│   ├── crud.py              # Database operations
│   ├── worker.py            # Celery tasks
│   ├── main.py              # FastAPI routes
│   ├── google_service.py    # Google Indexing API integration
│   ├── indexnow_service.py  # IndexNow integration
│   └── sitemap_service.py   # XML sitemap generation
├── google_keys/             # Google service account JSON keys (not in repo)
├── index.html               # Frontend dashboard
├── requirements.txt
└── .env                     # Environment variables (not in repo)
```

---

## Database Schema

**urls** — Core table. Tracks every URL, its status, which client owns it, and three flags that prevent double submission across retries.

**crawled_pages** — Stores extracted content from each page including title, body text capped at 50,000 characters, and a SHA-256 content hash for duplicate detection.

**google_accounts** — Tracks each service account with a daily usage counter that resets every midnight automatically.

**indexing_logs** — Full audit log. Every API call across all three layers is recorded here with status, timestamp, layer, and error reason.

---

## Setup

**Step 1 — Install dependencies**
```bash
pip install -r requirements.txt
```

**Step 2 — Create your .env file**
```
DATABASE_URL=postgresql+asyncpg://user:password@localhost/dbname
SYNC_DATABASE_URL=postgresql://user:password@localhost/dbname
REDIS_URL=redis://localhost:6379/0
INDEXNOW_KEY=your-uuid-here
INDEXNOW_HOST=https://yourdomain.com
GOOGLE_KEYS_DIR=./google_keys
```

**Step 3 — Create database tables**
```bash
alembic upgrade head
```

**Step 4 — Start the API server**
```bash
uvicorn app.main:app --reload
```

**Step 5 — Start the Celery worker**
```bash
celery -A app.worker worker --loglevel=info --concurrency=2
```

---

## Google Service Account Setup

1. Go to Google Cloud Console and create a new project
2. Enable the Indexing API for that project
3. Create a Service Account and download the JSON key
4. Add the service account email as Owner in Google Search Console
5. Drop the JSON file into the `google_keys/` folder
6. Hit `POST /api/accounts/scan` to register it in the database

Repeat for as many accounts as you need. Each account adds 200 URLs per day to your capacity.

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/urls` | Submit a single URL |
| POST | `/api/urls/bulk` | Submit up to 10,000 URLs |
| GET | `/api/urls` | List all URLs |
| POST | `/api/urls/{id}/retry` | Retry a failed URL |
| GET | `/api/stats` | Get counts by status |
| POST | `/api/indexnow/submit` | Manually trigger IndexNow |
| GET | `/api/accounts` | List Google service accounts |
| POST | `/api/accounts/scan` | Scan and register new key files |
| GET | `/api/logs/{url_id}` | Get indexing log for a URL |
| GET | `/sitemaps/{client_id}` | Get XML sitemap for a client |

---

## Scaling

Adding capacity costs nothing. Every new Google Cloud service account adds 200 more URLs per day.

| Accounts | Google URLs/day |
|----------|----------------|
| 10 | 2,000 |
| 50 | 10,000 |
| 250 | 50,000 |
| 1,000 | 200,000 |

Plus IndexNow adds another 50,000+ on top. Total theoretical ceiling with 1,000 accounts is 250,000+ URLs per day at zero running cost.

---

## Environment Variables

| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | Async PostgreSQL URL for FastAPI |
| `SYNC_DATABASE_URL` | Sync PostgreSQL URL for Celery |
| `REDIS_URL` | Redis URL for Celery broker and backend |
| `INDEXNOW_KEY` | Any UUID — your IndexNow key |
| `INDEXNOW_HOST` | Your domain eg https://yourdomain.com |
| `GOOGLE_KEYS_DIR` | Path to folder containing service account JSON files |

---

## Important Notes

- Never commit your `.env` file or `google_keys/` folder to a public repository
- Google service account JSON keys are sensitive — store them in a private repo only
- Start with `--concurrency=2` for Celery workers to avoid hitting PostgreSQL connection limits
- The system degrades gracefully — if Google API is down, IndexNow and Sitemaps keep working

---

## License

MIT
