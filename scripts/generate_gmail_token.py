#!/usr/bin/env python3
"""Generate Gmail API token.pickle file.

Run this script locally (not in Docker) to authorize the Gmail API.
You need credentials.json from Google Cloud Console first.

Steps:
1. Go to https://console.cloud.google.com/apis/credentials
2. Create OAuth 2.0 Client ID (Desktop app type)
3. Download JSON and save as credentials.json in project root
4. Run: python scripts/generate_gmail_token.py
5. A browser will open - authorize with your Gmail account
6. token.pickle will be created
"""

import pickle
from pathlib import Path

from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/gmail.send",
]

def main():
    creds_path = Path("credentials.json")
    token_path = Path("token.pickle")

    if not creds_path.exists():
        print("ERROR: credentials.json not found!")
        print("\nTo get credentials:")
        print("1. Go to https://console.cloud.google.com/apis/credentials")
        print("2. Create OAuth 2.0 Client ID (Desktop app type)")
        print("3. Download JSON and save as credentials.json")
        return

    print("Starting OAuth flow...")
    print("A browser window will open. Please authorize access to Gmail.\n")

    flow = InstalledAppFlow.from_client_secrets_file(str(creds_path), SCOPES)
    creds = flow.run_local_server(port=0)

    with open(token_path, "wb") as token:
        pickle.dump(creds, token)

    print(f"\nSuccess! Token saved to {token_path}")
    print("You can now restart the agent container.")


if __name__ == "__main__":
    main()
