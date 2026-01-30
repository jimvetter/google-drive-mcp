# Google Drive MCP Server Setup

**Conversation ID:** 5acc3a01-8e0e-4f09-9f18-6df2d6831034
**Date:** 2026-01
**Related to:** Mac Studio recovery and file access

---

## Summary

Set up Google Drive MCP server for accessing files stored in Google Drive through Claude and Cursor.

## Key Topics

- Python MCP server setup
- Google OAuth2 configuration
- Claude Desktop integration

## Configuration

### Server Location
```
/Users/jvm3ultra/Projects/mcp_servers/google-drive-mcp/
```

### MCP Config Entry
```json
{
  "gdrive": {
    "command": "/Users/jvm3ultra/Projects/mcp_servers/google-drive-mcp/venv/bin/python3",
    "args": ["/Users/jvm3ultra/Projects/mcp_servers/google-drive-mcp/gdrive_server.py"],
    "env": {
      "GOOGLE_APPLICATION_CREDENTIALS": "/Users/jvm3ultra/Projects/mcp_servers/google-drive-mcp/gcp-oauth.keys.json"
    }
  }
}
```

## Files

| File | Purpose |
|------|---------|
| `gdrive_server.py` | Main MCP server |
| `gcp-oauth.keys.json` | OAuth credentials |
| `venv/` | Python virtual environment |

---
*Extracted from Cursor History MCP*
