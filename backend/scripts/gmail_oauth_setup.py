"""Run this script once to authorise the Gmail account and save a token.

Steps:
1. Go to console.cloud.google.com
2. Create (or select) a project
3. APIs & Services → Enable APIs → search "Gmail API" → Enable
4. APIs & Services → Credentials → Create credentials → OAuth 2.0 Client ID
   - Application type: Desktop app
   - Download the JSON and save it as:  backend/data/gmail_credentials.json
5. Run:  python backend/scripts/gmail_oauth_setup.py
   A browser window opens. Log in as celonisdashboard@gmail.com and grant access.
   The token is saved to  backend/data/gmail_token.json  and used automatically.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]
DATA_DIR = Path(__file__).parents[1] / "data"
CREDENTIALS_FILE = DATA_DIR / "gmail_credentials.json"
TOKEN_FILE = DATA_DIR / "gmail_token.json"

if not CREDENTIALS_FILE.exists():
    print(f"\nCredentials file not found at: {CREDENTIALS_FILE}")
    print("\nTo create it:")
    print("  1. Go to https://console.cloud.google.com")
    print("  2. Create a project and enable the Gmail API")
    print("  3. Create OAuth 2.0 credentials (Desktop app type)")
    print(f"  4. Download the JSON and save it to: {CREDENTIALS_FILE}")
    sys.exit(1)

DATA_DIR.mkdir(parents=True, exist_ok=True)

flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_FILE), SCOPES)
creds = flow.run_local_server(port=0)

TOKEN_FILE.write_text(creds.to_json())
print(f"\nToken saved to: {TOKEN_FILE}")
print("The newsletter node will now use this token automatically.")
