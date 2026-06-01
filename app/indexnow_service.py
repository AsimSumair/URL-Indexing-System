"""
IndexNow Layer — submits URLs to Bing and Yandex instantly.
One API key, up to 10,000 URLs per call, completely free.

Setup:
  1. Set INDEXNOW_KEY in .env (any UUID works)
  2. Create a file at https://yourdomain.com/{INDEXNOW_KEY}.txt
     containing just the key on one line
  3. Set INDEXNOW_HOST in .env to your domain
"""
import os
import httpx
from typing import List

INDEXNOW_KEY  = os.getenv("INDEXNOW_KEY", "")
INDEXNOW_HOST = os.getenv("INDEXNOW_HOST", "https://example.com")
ENDPOINT      = "https://api.indexnow.org/indexnow"


async def submit_indexnow(urls: List[str]) -> dict:
    """
    Submit a batch of URLs (up to 10,000) to IndexNow.
    Returns {"success": True/False, "submitted": N, "error": "..."}
    """
    if not INDEXNOW_KEY:
        return {"success": False, "submitted": 0, "error": "INDEXNOW_KEY not set in .env"}

    # Split into batches of 10,000
    results = {"success": True, "submitted": 0, "error": ""}
    for i in range(0, len(urls), 10_000):
        batch = urls[i : i + 10_000]
        payload = {
            "host":        INDEXNOW_HOST.replace("https://", "").replace("http://", ""),
            "key":         INDEXNOW_KEY,
            "keyLocation": f"{INDEXNOW_HOST}/{INDEXNOW_KEY}.txt",
            "urlList":     batch,
        }
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(ENDPOINT, json=payload)
                if resp.status_code in (200, 202):
                    results["submitted"] += len(batch)
                else:
                    results["success"] = False
                    results["error"] = f"HTTP {resp.status_code}: {resp.text[:200]}"
        except Exception as e:
            results["success"] = False
            results["error"] = str(e)

    return results