import subprocess
import os
import time

BILLING_ACCOUNT  = "01A266-FBBB77-E30C85"
PROJECTS         = 5
ACCOUNTS_EACH    = 50
KEYS_DIR         = "./google_keys"
os.makedirs(KEYS_DIR, exist_ok=True)

def run(cmd):
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  ERROR: {result.stderr.strip()}")
    return result.stdout.strip()

for p in range(1, PROJECTS + 1):
    project_id = f"url-indexer-{p:02d}"
    print(f"\n{'='*50}")
    print(f"Setting up project {project_id}...")

    run(f"gcloud projects create {project_id} --name='URL Indexer {p:02d}'")
    time.sleep(3)
    run(f"gcloud billing projects link {project_id} --billing-account={BILLING_ACCOUNT}")
    run(f"gcloud services enable indexing.googleapis.com --project={project_id}")
    time.sleep(2)

    for a in range(1, ACCOUNTS_EACH + 1):
        sa_name  = f"indexer-sa-{a:02d}"
        sa_email = f"{sa_name}@{project_id}.iam.gserviceaccount.com"
        key_path = f"{KEYS_DIR}/{project_id}-sa{a:02d}.json"

        if os.path.exists(key_path):
            print(f"  [{a:02d}] Already exists, skipping.")
            continue

        print(f"  [{a:02d}] Creating {sa_email}...")
        run(f"gcloud iam service-accounts create {sa_name} "
            f"--display-name='Indexer {a:02d}' --project={project_id}")
        run(f"gcloud iam service-accounts keys create {key_path} "
            f"--iam-account={sa_email} --project={project_id}")
        print(f"       ✅ Key saved: {key_path}")
        time.sleep(1)

print("\n✅ Done! All 250 service accounts created across 5 projects.")
print("\nNext step: Add each service account email to Google Search Console as Owner.")
print("\nRun this to get all emails:")
print("python -c \"import glob,json; [print(json.load(open(f))['client_email']) for f in sorted(glob.glob('./google_keys/*.json'))]\"")
