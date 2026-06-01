"""
Test Google Indexing API with one service account
"""
from google.oauth2 import service_account
from googleapiclient.discovery import build
import glob
import json

# Get first key file
key_files = sorted(glob.glob('./google_keys/*.json'))
if not key_files:
    print("No key files found!")
    exit()

key_file = key_files[0]
print(f"Testing with: {key_file}")

# Load email
with open(key_file) as f:
    data = json.load(f)
print(f"Service account: {data['client_email']}")

# Try to call the API
SCOPES = ["https://www.googleapis.com/auth/indexing"]
credentials = service_account.Credentials.from_service_account_file(
    key_file, scopes=SCOPES
)

service = build("indexing", "v3", credentials=credentials, cache_discovery=False)

# Test with your GitHub pages URL
body = {
    "url": "https://asimsumair.github.io",
    "type": "URL_UPDATED"
}

try:
    response = service.urlNotifications().publish(body=body).execute()
    print(f"✅ SUCCESS: {response}")
except Exception as e:
    print(f"❌ ERROR: {e}")
