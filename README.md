# Google Drive MCP Server

A Model Context Protocol (MCP) server that provides full read/write access to Google Drive and Google Docs for Claude Desktop and Claude Code.

## Features

### File Operations
- **list_files** - List files in Google Drive with optional folder/query filters
- **search_files** - Search for files by name
- **read_file** - Read contents of text files (exports Google Docs as text, Sheets as CSV)
- **create_file** - Create new text files
- **update_file** - Update existing file contents
- **delete_file** - Delete files
- **create_folder** - Create new folders
- **move_file** - Move files between folders
- **copy_file** - Create copies of files
- **upload_binary_file** - Upload images, PDFs, and other binary files

### Google Docs Operations
- **create_google_doc** - Create new Google Docs with content
- **read_google_doc** - Read full text content of a Google Doc
- **append_to_google_doc** - Append text to end of a document
- **replace_google_doc_content** - Replace all content in a document

### Rich Text Formatting
- **format_google_doc_text** - Apply bold, italic, underline, font size, and color
- **insert_heading** - Insert H1-H6 headings
- **insert_bullet_list** - Insert bullet or numbered lists
- **markdown_to_google_doc** - Convert markdown to a fully formatted Google Doc

## Setup

### 1. Google Cloud Console Setup

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select an existing one
3. Enable the following APIs:
   - Google Drive API
   - Google Docs API
   - Google Sheets API
4. Go to "Credentials" → "Create Credentials" → "OAuth client ID"
5. Select "Desktop app" as the application type
6. Download the JSON credentials file
7. Save it as `gcp-oauth.keys.json` in this directory

### 2. Install Dependencies

```bash
python3 -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows
pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib mcp
```

### 3. Authenticate

Run the server once to complete OAuth:

```bash
./venv/bin/python3 -c "from gdrive_server import get_credentials; get_credentials()"
```

A browser window will open for Google sign-in. After authorization, the token is saved to `~/.google-drive-mcp-token.json`.

### 4. Configure Claude Desktop

Add to your `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "gdrive": {
      "command": "/path/to/google-drive-mcp/venv/bin/python3",
      "args": ["/path/to/google-drive-mcp/gdrive_server.py"],
      "env": {
        "GOOGLE_APPLICATION_CREDENTIALS": "/path/to/google-drive-mcp/gcp-oauth.keys.json"
      }
    }
  }
}
```

### 5. Restart Claude Desktop

Quit and reopen Claude Desktop to load the new MCP server.

## Usage Examples

Once configured, you can ask Claude:

- "List files in my Google Drive"
- "Create a new Google Doc called 'Meeting Notes' with today's date"
- "Upload ~/Desktop/photo.jpg to my Drive"
- "Convert this markdown to a Google Doc: # My Report..."
- "Move file ABC123 to folder XYZ789"
- "Make the title bold in document ABC123"

## Security Notes

- OAuth credentials (`gcp-oauth.keys.json`) are excluded from git
- Tokens are stored in your home directory (`~/.google-drive-mcp-token.json`)
- All file/folder IDs are validated before API calls
- Query strings are sanitized to prevent injection

## License

MIT
