"""
Google Indexing API Layer — submits URLs directly to Google.

Setup:
  1. Create a Google Cloud project and enable the Indexing API.
  2. Create a Service Account, download the JSON key.
  3. Add the service account email as an Owner in Google Search Console
     for every property you want to index.
  4. Place all JSON key files inside ./google_keys/
  5. Run POST /api/accounts/scan to register them in the DB.

Quota: 200 URLs per service account per day (Google hard limit).
       Add more accounts to scale horizontally.
"""
import os
import json
import glob
from typing import List

GOOGLE_KEYS_DIR = os.getenv("GOOGLE_KEYS_DIR", "./google_keys")


def scan_key_files() -> List[dict]:
    """
    Scan GOOGLE_KEYS_DIR for *.json service-account key files.
    Returns a list of {"key_file": path, "email": service_account_email}.
    """
    pattern = os.path.join(GOOGLE_KEYS_DIR, "*.json")
    found = []
    for path in glob.glob(pattern):
        try:
            with open(path) as f:
                data = json.load(f)
            email = data.get("client_email", "unknown")
            found.append({"key_file": path, "email": email})
        except Exception:
            pass  
    return found


def submit_url_to_google(key_file: str, url: str) -> dict:
    """
    Submit a single URL to the Google Indexing API using a service account.
    Returns {"success": True/False, "response": "...", "error": "..."}

    Requires:
      pip install google-auth google-auth-httplib2 google-api-python-client
    """
    try:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build

        SCOPES = ["https://www.googleapis.com/auth/indexing"]
        credentials = service_account.Credentials.from_service_account_file(
            key_file, scopes=SCOPES
        )
        service = build("indexing", "v3", credentials=credentials, cache_discovery=False)

        body = {
            "url": url,
            "type": "URL_UPDATED",
        }
        response = service.urlNotifications().publish(body=body).execute()
        return {"success": True, "response": str(response), "error": ""}

    except ImportError:
        return {
            "success": False,
            "response": "",
            "error": (
                "Google API libraries not installed. "
                "Run: pip install google-auth google-auth-httplib2 google-api-python-client"
            ),
        }
    except Exception as e:
        return {"success": False, "response": "", "error": str(e)}