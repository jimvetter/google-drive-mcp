#!/usr/bin/env python3
"""
Manual OAuth flow for Google Drive
Generates the authorization URL for you to open manually
"""

import json
from pathlib import Path
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = [
    'https://www.googleapis.com/auth/drive',
    'https://www.googleapis.com/auth/documents',
    'https://www.googleapis.com/auth/spreadsheets'
]

CREDS_PATH = Path.home() / 'Projects/google-drive-mcp/gcp-oauth.keys.json'
TOKEN_PATH = Path.home() / '.google-drive-mcp-token.json'

print("=" * 70)
print("Google Drive MCP - Manual OAuth Setup")
print("=" * 70)
print()

# Load credentials
with open(CREDS_PATH) as f:
    creds_data = json.load(f)
    
print(f"✓ Loaded credentials from: {CREDS_PATH}")
print()

# Create flow
flow = InstalledAppFlow.from_client_secrets_file(
    str(CREDS_PATH),
    SCOPES,
    redirect_uri='http://localhost:8080/'
)

# Generate authorization URL
auth_url, _ = flow.authorization_url(
    access_type='offline',
    include_granted_scopes='true',
    prompt='consent'
)

print("MANUAL SETUP REQUIRED:")
print("-" * 70)
print()
print("1. COPY this URL and paste it into your browser:")
print()
print(auth_url)
print()
print("2. Sign in to Google and authorize the application")
print()
print("3. After authorization, you'll be redirected to a URL like:")
print("   http://localhost:8080/?code=XXXXX&scope=...")
print()
print("4. COPY the entire URL from your browser's address bar")
print()
print("5. Come back here and paste it when prompted")
print()
print("-" * 70)
print()

# Get the authorization response
auth_response = input("Paste the full redirect URL here: ").strip()

# Exchange the authorization code for credentials
flow.fetch_token(authorization_response=auth_response)

# Save the credentials
TOKEN_PATH.write_text(flow.credentials.to_json())

print()
print("=" * 70)
print("✓ SUCCESS! Token saved to:", TOKEN_PATH)
print("=" * 70)
print()
print("Next steps:")
print("1. Quit Claude Desktop (Cmd+Q)")
print("2. Reopen Claude Desktop")
print("3. Ask: 'List files in my Google Drive'")
print()




