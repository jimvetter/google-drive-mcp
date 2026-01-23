#!/bin/bash

# Test the Google Drive MCP Server OAuth flow

echo "Testing Google Drive MCP Server OAuth flow..."
echo ""
echo "This will:"
echo "1. Start the MCP server"
echo "2. Trigger OAuth flow (browser will open)"
echo "3. Save the token"
echo ""
echo "Press Ctrl+C after authentication completes"
echo ""

cd ~/Projects/google-drive-mcp
source venv/bin/activate
export GOOGLE_APPLICATION_CREDENTIALS="$HOME/Projects/google-drive-mcp/gcp-oauth.keys.json"
python3 gdrive_server.py
