"""
XML Sitemap Layer — generates one sitemap per client and pings Google.

Sitemaps are the passive backup layer. Google crawls them on its own
schedule, so no API quota is needed. Each client gets their own sitemap
file at /sitemaps/{client_id}.xml served by FastAPI.
"""
from datetime import datetime
from typing import List


def generate_sitemap(urls: List[str], last_modified: datetime = None) -> str:
    """
    Generate a valid XML sitemap string for a list of URLs.
    Compliant with https://www.sitemaps.org/protocol.html
    """
    lm = (last_modified or datetime.utcnow()).strftime("%Y-%m-%d")
    entries = "\n".join(
        f"""  <url>
    <loc>{url}</loc>
    <lastmod>{lm}</lastmod>
    <changefreq>weekly</changefreq>
    <priority>0.8</priority>
  </url>"""
        for url in urls
    )
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
{entries}
</urlset>"""


async def ping_google_sitemap(sitemap_url: str) -> dict:
    """
    Ping Google to re-crawl the sitemap.
    Returns {"success": True/False, "status": int}
    """
    import httpx
    ping_url = f"https://www.google.com/ping?sitemap={sitemap_url}"
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(ping_url)
            return {"success": resp.status_code == 200, "status": resp.status_code}
    except Exception as e:
        return {"success": False, "status": 0, "error": str(e)}