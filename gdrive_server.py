#!/usr/bin/env python3
"""
Google Drive MCP Server
Provides full read/write access to Google Drive for Claude Desktop
"""

import os
import sys
import json
import logging
import base64
import mimetypes
import re
from pathlib import Path
from typing import Any

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent
import io

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# OAuth scopes - full Drive access
SCOPES = [
    'https://www.googleapis.com/auth/drive',
    'https://www.googleapis.com/auth/documents',
    'https://www.googleapis.com/auth/spreadsheets'
]

# Paths
HOME = Path.home()
TOKEN_PATH = HOME / '.google-drive-mcp-token.json'
CREDS_PATH = Path(os.environ.get('GOOGLE_APPLICATION_CREDENTIALS',
                                  HOME / 'Projects/google-drive-mcp/gcp-oauth.keys.json'))

def get_credentials():
    """Get valid Google credentials with OAuth flow if needed"""
    creds = None
    
    # Load existing token if available
    if TOKEN_PATH.exists():
        try:
            creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)
            logger.info("Loaded existing credentials")
        except Exception as e:
            logger.warning(f"Could not load credentials: {e}")
    
    # Refresh or get new token
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            logger.info("Refreshing expired token")
            creds.refresh(Request())
        else:
            logger.info("Starting OAuth flow...")
            flow = InstalledAppFlow.from_client_secrets_file(str(CREDS_PATH), SCOPES)
            creds = flow.run_local_server(port=0)
            logger.info("OAuth flow completed successfully")
        
        # Save token
        TOKEN_PATH.write_text(creds.to_json())
        logger.info(f"Token saved to {TOKEN_PATH}")
    
    return creds

def init_drive_service():
    """Initialize Google Drive API service"""
    creds = get_credentials()
    return build('drive', 'v3', credentials=creds)

def init_docs_service():
    """Initialize Google Docs API service"""
    creds = get_credentials()
    return build('docs', 'v1', credentials=creds)

# Initialize server
app = Server("google-drive")
drive_service = None
docs_service = None

@app.list_tools()
async def list_tools() -> list[Tool]:
    """List available Google Drive tools"""
    return [
        Tool(
            name="list_files",
            description="List files in Google Drive. Can filter by folder, name, or type.",
            inputSchema={
                "type": "object",
                "properties": {
                    "folder_id": {"type": "string", "description": "Optional folder ID to list files from"},
                    "query": {"type": "string", "description": "Optional search query"},
                    "max_results": {"type": "number", "default": 100}
                }
            }
        ),
        Tool(
            name="read_file",
            description="Read contents of a text file from Google Drive",
            inputSchema={
                "type": "object",
                "properties": {
                    "file_id": {"type": "string", "description": "ID of the file to read"}
                },
                "required": ["file_id"]
            }
        ),
        Tool(
            name="create_file",
            description="Create a new text file in Google Drive",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Name of the file"},
                    "content": {"type": "string", "description": "Content of the file"},
                    "folder_id": {"type": "string", "description": "Optional folder ID"}
                },
                "required": ["name", "content"]
            }
        ),
        Tool(
            name="update_file",
            description="Update contents of an existing file",
            inputSchema={
                "type": "object",
                "properties": {
                    "file_id": {"type": "string", "description": "ID of the file to update"},
                    "content": {"type": "string", "description": "New content"}
                },
                "required": ["file_id", "content"]
            }
        ),
        Tool(
            name="delete_file",
            description="Delete a file from Google Drive",
            inputSchema={
                "type": "object",
                "properties": {
                    "file_id": {"type": "string", "description": "ID of the file to delete"}
                },
                "required": ["file_id"]
            }
        ),
        Tool(
            name="create_folder",
            description="Create a new folder in Google Drive",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Name of the folder"},
                    "parent_id": {"type": "string", "description": "Optional parent folder ID"}
                },
                "required": ["name"]
            }
        ),
        Tool(
            name="search_files",
            description="Search for files in Google Drive",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query (file name, content, etc.)"},
                    "max_results": {"type": "number", "default": 20}
                },
                "required": ["query"]
            }
        ),
        Tool(
            name="create_google_doc",
            description="Create a new Google Doc with the specified title and content",
            inputSchema={
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "Title of the new Google Doc"},
                    "content": {"type": "string", "description": "Initial text content for the document"}
                },
                "required": ["title", "content"]
            }
        ),
        Tool(
            name="append_to_google_doc",
            description="Append text to the end of an existing Google Doc",
            inputSchema={
                "type": "object",
                "properties": {
                    "doc_id": {"type": "string", "description": "ID of the Google Doc"},
                    "text": {"type": "string", "description": "Text to append to the document"}
                },
                "required": ["doc_id", "text"]
            }
        ),
        Tool(
            name="replace_google_doc_content",
            description="Replace all content in a Google Doc with new text",
            inputSchema={
                "type": "object",
                "properties": {
                    "doc_id": {"type": "string", "description": "ID of the Google Doc"},
                    "new_content": {"type": "string", "description": "New text content to replace existing content"}
                },
                "required": ["doc_id", "new_content"]
            }
        ),
        Tool(
            name="read_google_doc",
            description="Read the full text content of a Google Doc",
            inputSchema={
                "type": "object",
                "properties": {
                    "doc_id": {"type": "string", "description": "ID of the Google Doc"}
                },
                "required": ["doc_id"]
            }
        ),
        Tool(
            name="move_file",
            description="Move a file to a different folder in Google Drive",
            inputSchema={
                "type": "object",
                "properties": {
                    "file_id": {"type": "string", "description": "ID of the file to move"},
                    "new_folder_id": {"type": "string", "description": "ID of the destination folder"}
                },
                "required": ["file_id", "new_folder_id"]
            }
        ),
        Tool(
            name="copy_file",
            description="Create a copy of a file in Google Drive",
            inputSchema={
                "type": "object",
                "properties": {
                    "file_id": {"type": "string", "description": "ID of the file to copy"},
                    "new_name": {"type": "string", "description": "Name for the copied file (optional, defaults to 'Copy of [original]')"},
                    "folder_id": {"type": "string", "description": "Optional folder ID for the copy"}
                },
                "required": ["file_id"]
            }
        ),
        Tool(
            name="upload_binary_file",
            description="Upload a binary file (image, PDF, etc.) from a local path or base64 content to Google Drive",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Name for the file in Google Drive"},
                    "local_path": {"type": "string", "description": "Local file path to upload (use this OR base64_content)"},
                    "base64_content": {"type": "string", "description": "Base64-encoded file content (use this OR local_path)"},
                    "mime_type": {"type": "string", "description": "MIME type (e.g., 'image/png', 'application/pdf'). Auto-detected if local_path provided."},
                    "folder_id": {"type": "string", "description": "Optional folder ID to upload into"}
                },
                "required": ["name"]
            }
        ),
        Tool(
            name="format_google_doc_text",
            description="Apply formatting (bold, italic, underline, font size, color) to text in a Google Doc",
            inputSchema={
                "type": "object",
                "properties": {
                    "doc_id": {"type": "string", "description": "ID of the Google Doc"},
                    "start_index": {"type": "number", "description": "Starting character index (1-based)"},
                    "end_index": {"type": "number", "description": "Ending character index"},
                    "bold": {"type": "boolean", "description": "Apply bold formatting"},
                    "italic": {"type": "boolean", "description": "Apply italic formatting"},
                    "underline": {"type": "boolean", "description": "Apply underline formatting"},
                    "font_size": {"type": "number", "description": "Font size in points (e.g., 12, 14, 18)"},
                    "color_hex": {"type": "string", "description": "Text color as hex (e.g., '#FF0000' for red)"}
                },
                "required": ["doc_id", "start_index", "end_index"]
            }
        ),
        Tool(
            name="insert_heading",
            description="Insert a heading (H1-H6) into a Google Doc at a specific position",
            inputSchema={
                "type": "object",
                "properties": {
                    "doc_id": {"type": "string", "description": "ID of the Google Doc"},
                    "text": {"type": "string", "description": "The heading text"},
                    "heading_level": {"type": "number", "description": "Heading level (1-6)"},
                    "index": {"type": "number", "description": "Position to insert (1 for beginning, or use 'end')"},
                    "at_end": {"type": "boolean", "description": "If true, insert at end of document"}
                },
                "required": ["doc_id", "text", "heading_level"]
            }
        ),
        Tool(
            name="insert_bullet_list",
            description="Insert a bullet or numbered list into a Google Doc",
            inputSchema={
                "type": "object",
                "properties": {
                    "doc_id": {"type": "string", "description": "ID of the Google Doc"},
                    "items": {"type": "array", "items": {"type": "string"}, "description": "List items to insert"},
                    "numbered": {"type": "boolean", "description": "If true, create numbered list; if false, bullet list"},
                    "index": {"type": "number", "description": "Position to insert (1 for beginning)"},
                    "at_end": {"type": "boolean", "description": "If true, insert at end of document"}
                },
                "required": ["doc_id", "items"]
            }
        ),
        Tool(
            name="markdown_to_google_doc",
            description="Convert markdown content to a formatted Google Doc with headings, bold, italic, lists, and links",
            inputSchema={
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "Title for the new Google Doc"},
                    "markdown": {"type": "string", "description": "Markdown content to convert"},
                    "folder_id": {"type": "string", "description": "Optional folder ID to create the doc in"}
                },
                "required": ["title", "markdown"]
            }
        )
    ]

def refresh_services_if_needed():
    """Check if credentials are expired and refresh services if needed"""
    global drive_service, docs_service

    creds = get_credentials()  # This will refresh if expired

    # Reinitialize services with fresh credentials
    drive_service = build('drive', 'v3', credentials=creds)
    docs_service = build('docs', 'v1', credentials=creds)

    return True

@app.call_tool()
async def call_tool(name: str, arguments: Any) -> list[TextContent]:
    """Handle tool calls"""
    global drive_service, docs_service

    # Always ensure we have fresh credentials before each call
    try:
        refresh_services_if_needed()
    except Exception as e:
        error_msg = str(e)
        if 'invalid_grant' in error_msg.lower() or 'token' in error_msg.lower():
            logger.error(f"TOKEN EXPIRED OR INVALID: {e}")
            return [TextContent(
                type="text",
                text=f"⚠️ AUTHENTICATION ERROR: Google OAuth token is expired or invalid.\n\n"
                     f"To fix this, run the following command in Terminal:\n"
                     f"  cd ~/Projects/google-drive-mcp && ./venv/bin/python3 -c \"from gdrive_server import get_credentials; get_credentials()\"\n\n"
                     f"Then restart Claude Desktop."
            )]
        else:
            logger.error(f"Failed to initialize Google services: {e}", exc_info=True)
            return [TextContent(type="text", text=f"Failed to connect to Google Drive: {str(e)}")]

    try:
        if name == "list_files":
            return await list_files_impl(arguments)
        elif name == "read_file":
            return await read_file_impl(arguments)
        elif name == "create_file":
            return await create_file_impl(arguments)
        elif name == "update_file":
            return await update_file_impl(arguments)
        elif name == "delete_file":
            return await delete_file_impl(arguments)
        elif name == "create_folder":
            return await create_folder_impl(arguments)
        elif name == "search_files":
            return await search_files_impl(arguments)
        elif name == "create_google_doc":
            return await create_google_doc_impl(arguments)
        elif name == "append_to_google_doc":
            return await append_to_google_doc_impl(arguments)
        elif name == "replace_google_doc_content":
            return await replace_google_doc_content_impl(arguments)
        elif name == "read_google_doc":
            return await read_google_doc_impl(arguments)
        elif name == "move_file":
            return await move_file_impl(arguments)
        elif name == "copy_file":
            return await copy_file_impl(arguments)
        elif name == "upload_binary_file":
            return await upload_binary_file_impl(arguments)
        elif name == "format_google_doc_text":
            return await format_google_doc_text_impl(arguments)
        elif name == "insert_heading":
            return await insert_heading_impl(arguments)
        elif name == "insert_bullet_list":
            return await insert_bullet_list_impl(arguments)
        elif name == "markdown_to_google_doc":
            return await markdown_to_google_doc_impl(arguments)
        else:
            return [TextContent(type="text", text=f"Unknown tool: {name}")]
    except Exception as e:
        error_msg = str(e)
        # Check for auth-related errors in API calls
        if 'invalid_grant' in error_msg.lower() or 'unauthorized' in error_msg.lower() or 'token' in error_msg.lower() or '401' in error_msg:
            logger.error(f"AUTH ERROR during API call: {e}")
            return [TextContent(
                type="text",
                text=f"⚠️ AUTHENTICATION ERROR: Google API returned an auth error.\n\n"
                     f"The OAuth token may have been revoked or expired.\n"
                     f"To fix: Delete ~/.google-drive-mcp-token.json and restart Claude Desktop to re-authenticate."
            )]
        logger.error(f"Error calling tool {name}: {e}", exc_info=True)
        return [TextContent(type="text", text=f"Error: {str(e)}")]

async def list_files_impl(args: dict) -> list[TextContent]:
    """List files in Drive"""
    query_parts = []

    if args.get("folder_id"):
        folder_id = args['folder_id']
        if not validate_google_id(folder_id):
            return [TextContent(type="text", text="Error: Invalid folder ID format")]
        query_parts.append(f"'{sanitize_query_string(folder_id)}' in parents")
    if args.get("query"):
        # Sanitize user-provided query to prevent injection
        sanitized_query = sanitize_query_string(args["query"])
        query_parts.append(f"name contains '{sanitized_query}'")

    query = " and ".join(query_parts) if query_parts else None

    # Bound max_results to reasonable limits
    max_results = min(args.get("max_results", 100), 500)

    results = drive_service.files().list(
        q=query,
        pageSize=max_results,
        fields="files(id, name, mimeType, modifiedTime, size)"
    ).execute()
    
    files = results.get('files', [])
    
    if not files:
        return [TextContent(type="text", text="No files found")]
    
    output = "Files:\n\n"
    for f in files:
        size = f.get('size', 'N/A')
        output += f"- {f['name']} (ID: {f['id']})\n"
        output += f"  Type: {f['mimeType']}\n"
        output += f"  Modified: {f.get('modifiedTime', 'N/A')}\n"
        output += f"  Size: {size} bytes\n\n"
    
    return [TextContent(type="text", text=output)]

async def read_file_impl(args: dict) -> list[TextContent]:
    """Read file contents"""
    file_id = args["file_id"]

    if not validate_google_id(file_id):
        return [TextContent(type="text", text="Error: Invalid file ID format")]

    # Get file metadata
    file = drive_service.files().get(fileId=file_id).execute()
    mime_type = file.get('mimeType', '')
    
    # Download content
    if 'google-apps' in mime_type:
        # Export Google Docs/Sheets/Slides
        if 'document' in mime_type:
            request = drive_service.files().export_media(fileId=file_id, mimeType='text/plain')
        elif 'spreadsheet' in mime_type:
            request = drive_service.files().export_media(fileId=file_id, mimeType='text/csv')
        else:
            return [TextContent(type="text", text=f"Cannot read file type: {mime_type}")]
    else:
        request = drive_service.files().get_media(fileId=file_id)
    
    fh = io.BytesIO()
    downloader = MediaIoBaseDownload(fh, request)
    done = False
    while not done:
        _, done = downloader.next_chunk()
    
    try:
        content = fh.getvalue().decode('utf-8')
    except UnicodeDecodeError:
        return [TextContent(type="text", text=f"Error: File '{file['name']}' appears to be binary and cannot be displayed as text")]

    return [TextContent(type="text", text=f"File: {file['name']}\n\n{content}")]

async def create_file_impl(args: dict) -> list[TextContent]:
    """Create a new file"""
    if args.get('folder_id') and not validate_google_id(args['folder_id']):
        return [TextContent(type="text", text="Error: Invalid folder ID format")]

    file_metadata = {'name': args['name']}

    if args.get('folder_id'):
        file_metadata['parents'] = [args['folder_id']]
    
    media = MediaFileUpload(
        io.BytesIO(args['content'].encode('utf-8')),
        mimetype='text/plain',
        resumable=True
    )
    
    file = drive_service.files().create(
        body=file_metadata,
        media_body=media,
        fields='id, name, webViewLink'
    ).execute()
    
    return [TextContent(
        type="text",
        text=f"Created file: {file['name']}\nID: {file['id']}\nLink: {file.get('webViewLink', 'N/A')}"
    )]

async def update_file_impl(args: dict) -> list[TextContent]:
    """Update file contents"""
    if not validate_google_id(args['file_id']):
        return [TextContent(type="text", text="Error: Invalid file ID format")]

    media = MediaFileUpload(
        io.BytesIO(args['content'].encode('utf-8')),
        mimetype='text/plain',
        resumable=True
    )
    
    file = drive_service.files().update(
        fileId=args['file_id'],
        media_body=media
    ).execute()
    
    return [TextContent(type="text", text=f"Updated file ID: {file['id']}")]

async def delete_file_impl(args: dict) -> list[TextContent]:
    """Delete a file"""
    file_id = args['file_id']
    if not validate_google_id(file_id):
        return [TextContent(type="text", text="Error: Invalid file ID format")]

    drive_service.files().delete(fileId=file_id).execute()
    return [TextContent(type="text", text=f"Deleted file ID: {file_id}")]

async def create_folder_impl(args: dict) -> list[TextContent]:
    """Create a folder"""
    if args.get('parent_id') and not validate_google_id(args['parent_id']):
        return [TextContent(type="text", text="Error: Invalid parent folder ID format")]

    file_metadata = {
        'name': args['name'],
        'mimeType': 'application/vnd.google-apps.folder'
    }

    if args.get('parent_id'):
        file_metadata['parents'] = [args['parent_id']]
    
    folder = drive_service.files().create(
        body=file_metadata,
        fields='id, name'
    ).execute()
    
    return [TextContent(type="text", text=f"Created folder: {folder['name']}\nID: {folder['id']}")]

def sanitize_query_string(value: str) -> str:
    """Escape single quotes in query strings to prevent injection"""
    if not value:
        return value
    # Escape single quotes by doubling them (Google Drive query syntax)
    return value.replace("'", "\\'")

def validate_google_id(id_str: str) -> bool:
    """Validate that a string looks like a Google Drive/Docs ID"""
    if not id_str or not isinstance(id_str, str):
        return False
    # Google IDs are alphanumeric with underscores and hyphens, typically 20-60 chars
    import re
    return bool(re.match(r'^[a-zA-Z0-9_-]{10,100}$', id_str))

async def search_files_impl(args: dict) -> list[TextContent]:
    """Search for files"""
    search_term = sanitize_query_string(args['query'])
    query = f"name contains '{search_term}'"

    # Bound max_results to reasonable limits
    max_results = min(args.get('max_results', 20), 100)

    results = drive_service.files().list(
        q=query,
        pageSize=max_results,
        fields="files(id, name, mimeType)"
    ).execute()
    
    files = results.get('files', [])
    
    if not files:
        return [TextContent(type="text", text="No files found matching your search")]
    
    output = f"Found {len(files)} file(s):\n\n"
    for f in files:
        output += f"- {f['name']} (ID: {f['id']})\n"
    
    return [TextContent(type="text", text=output)]

async def create_google_doc_impl(args: dict) -> list[TextContent]:
    """Create a new Google Doc with content"""
    title = args['title']
    content = args['content']
    
    # Create empty doc
    doc = docs_service.documents().create(body={'title': title}).execute()
    doc_id = doc['documentId']
    
    # Insert content if provided
    if content:
        requests = [
            {
                'insertText': {
                    'location': {'index': 1},
                    'text': content
                }
            }
        ]
        docs_service.documents().batchUpdate(
            documentId=doc_id,
            body={'requests': requests}
        ).execute()
    
    return [TextContent(
        type="text",
        text=f"Created Google Doc: {title}\nID: {doc_id}\nLink: https://docs.google.com/document/d/{doc_id}/edit"
    )]

async def append_to_google_doc_impl(args: dict) -> list[TextContent]:
    """Append text to end of a Google Doc"""
    doc_id = args['doc_id']
    if not validate_google_id(doc_id):
        return [TextContent(type="text", text="Error: Invalid document ID format")]

    text = args['text']

    # Get current document to find end index
    doc = docs_service.documents().get(documentId=doc_id).execute()
    end_index = doc['body']['content'][-1]['endIndex'] - 1
    
    # Insert text at the end
    requests = [
        {
            'insertText': {
                'location': {'index': end_index},
                'text': text
            }
        }
    ]
    
    docs_service.documents().batchUpdate(
        documentId=doc_id,
        body={'requests': requests}
    ).execute()
    
    return [TextContent(type="text", text=f"Appended text to document {doc_id}")]

async def replace_google_doc_content_impl(args: dict) -> list[TextContent]:
    """Replace all content in a Google Doc"""
    doc_id = args['doc_id']
    if not validate_google_id(doc_id):
        return [TextContent(type="text", text="Error: Invalid document ID format")]

    new_content = args['new_content']

    # Get current document
    doc = docs_service.documents().get(documentId=doc_id).execute()
    
    # Find the range of existing content (skip the trailing newline)
    content = doc['body']['content']
    if len(content) > 1:
        start_index = 1
        end_index = content[-1]['endIndex'] - 1
        
        requests = []
        
        # Delete existing content if there is any
        if end_index > start_index:
            requests.append({
                'deleteContentRange': {
                    'range': {
                        'startIndex': start_index,
                        'endIndex': end_index
                    }
                }
            })
        
        # Insert new content
        requests.append({
            'insertText': {
                'location': {'index': 1},
                'text': new_content
            }
        })
        
        docs_service.documents().batchUpdate(
            documentId=doc_id,
            body={'requests': requests}
        ).execute()
    else:
        # Empty doc, just insert
        requests = [
            {
                'insertText': {
                    'location': {'index': 1},
                    'text': new_content
                }
            }
        ]
        docs_service.documents().batchUpdate(
            documentId=doc_id,
            body={'requests': requests}
        ).execute()
    
    return [TextContent(type="text", text=f"Replaced content in document {doc_id}")]

async def read_google_doc_impl(args: dict) -> list[TextContent]:
    """Read full text content of a Google Doc"""
    doc_id = args['doc_id']
    if not validate_google_id(doc_id):
        return [TextContent(type="text", text="Error: Invalid document ID format")]

    doc = docs_service.documents().get(documentId=doc_id).execute()
    title = doc.get('title', 'Untitled')
    
    # Extract text from document
    text_content = []
    for element in doc['body']['content']:
        if 'paragraph' in element:
            for para_element in element['paragraph']['elements']:
                if 'textRun' in para_element:
                    text_content.append(para_element['textRun']['content'])
    
    full_text = ''.join(text_content)
    
    return [TextContent(type="text", text=f"Document: {title}\n\n{full_text}")]

async def move_file_impl(args: dict) -> list[TextContent]:
    """Move a file to a different folder"""
    file_id = args['file_id']
    new_folder_id = args['new_folder_id']

    if not validate_google_id(file_id):
        return [TextContent(type="text", text="Error: Invalid file ID format")]
    if not validate_google_id(new_folder_id):
        return [TextContent(type="text", text="Error: Invalid folder ID format")]

    # Get current parents
    file = drive_service.files().get(fileId=file_id, fields='parents, name').execute()
    previous_parents = ",".join(file.get('parents', []))

    # Move the file
    file = drive_service.files().update(
        fileId=file_id,
        addParents=new_folder_id,
        removeParents=previous_parents,
        fields='id, name, parents'
    ).execute()

    return [TextContent(type="text", text=f"Moved '{file['name']}' to folder {new_folder_id}")]


async def copy_file_impl(args: dict) -> list[TextContent]:
    """Copy a file"""
    file_id = args['file_id']
    new_name = args.get('new_name')
    folder_id = args.get('folder_id')

    if not validate_google_id(file_id):
        return [TextContent(type="text", text="Error: Invalid file ID format")]
    if folder_id and not validate_google_id(folder_id):
        return [TextContent(type="text", text="Error: Invalid folder ID format")]

    # Get original file name if no new name provided
    if not new_name:
        original = drive_service.files().get(fileId=file_id, fields='name').execute()
        new_name = f"Copy of {original['name']}"

    body = {'name': new_name}
    if folder_id:
        body['parents'] = [folder_id]

    copied_file = drive_service.files().copy(
        fileId=file_id,
        body=body,
        fields='id, name, webViewLink'
    ).execute()

    return [TextContent(
        type="text",
        text=f"Copied file as: {copied_file['name']}\nID: {copied_file['id']}\nLink: {copied_file.get('webViewLink', 'N/A')}"
    )]


async def upload_binary_file_impl(args: dict) -> list[TextContent]:
    """Upload a binary file from local path or base64 content"""
    name = args['name']
    local_path = args.get('local_path')
    base64_content = args.get('base64_content')
    mime_type = args.get('mime_type')
    folder_id = args.get('folder_id')

    if folder_id and not validate_google_id(folder_id):
        return [TextContent(type="text", text="Error: Invalid folder ID format")]

    if not local_path and not base64_content:
        return [TextContent(type="text", text="Error: Must provide either local_path or base64_content")]

    if local_path:
        # Upload from local file
        path = Path(local_path).expanduser()
        if not path.exists():
            return [TextContent(type="text", text=f"Error: File not found: {local_path}")]

        # Auto-detect mime type if not provided
        if not mime_type:
            mime_type, _ = mimetypes.guess_type(str(path))
            if not mime_type:
                mime_type = 'application/octet-stream'

        media = MediaFileUpload(str(path), mimetype=mime_type, resumable=True)
    else:
        # Upload from base64 content
        if not mime_type:
            return [TextContent(type="text", text="Error: mime_type is required when using base64_content")]

        try:
            file_content = base64.b64decode(base64_content)
        except Exception as e:
            return [TextContent(type="text", text=f"Error: Invalid base64 content: {str(e)}")]

        media = MediaFileUpload(
            io.BytesIO(file_content),
            mimetype=mime_type,
            resumable=True
        )

    file_metadata = {'name': name}
    if folder_id:
        file_metadata['parents'] = [folder_id]

    file = drive_service.files().create(
        body=file_metadata,
        media_body=media,
        fields='id, name, webViewLink, mimeType'
    ).execute()

    return [TextContent(
        type="text",
        text=f"Uploaded: {file['name']}\nID: {file['id']}\nType: {file['mimeType']}\nLink: {file.get('webViewLink', 'N/A')}"
    )]


async def format_google_doc_text_impl(args: dict) -> list[TextContent]:
    """Apply formatting to text in a Google Doc"""
    doc_id = args['doc_id']
    start_index = args['start_index']
    end_index = args['end_index']

    if not validate_google_id(doc_id):
        return [TextContent(type="text", text="Error: Invalid document ID format")]

    # Build the text style
    text_style = {}
    fields_to_update = []

    if args.get('bold') is not None:
        text_style['bold'] = args['bold']
        fields_to_update.append('bold')

    if args.get('italic') is not None:
        text_style['italic'] = args['italic']
        fields_to_update.append('italic')

    if args.get('underline') is not None:
        text_style['underline'] = args['underline']
        fields_to_update.append('underline')

    if args.get('font_size') is not None:
        text_style['fontSize'] = {
            'magnitude': args['font_size'],
            'unit': 'PT'
        }
        fields_to_update.append('fontSize')

    if args.get('color_hex'):
        hex_color = args['color_hex'].lstrip('#')
        r = int(hex_color[0:2], 16) / 255.0
        g = int(hex_color[2:4], 16) / 255.0
        b = int(hex_color[4:6], 16) / 255.0
        text_style['foregroundColor'] = {
            'color': {'rgbColor': {'red': r, 'green': g, 'blue': b}}
        }
        fields_to_update.append('foregroundColor')

    if not fields_to_update:
        return [TextContent(type="text", text="Error: No formatting options specified")]

    requests = [{
        'updateTextStyle': {
            'range': {
                'startIndex': start_index,
                'endIndex': end_index
            },
            'textStyle': text_style,
            'fields': ','.join(fields_to_update)
        }
    }]

    docs_service.documents().batchUpdate(
        documentId=doc_id,
        body={'requests': requests}
    ).execute()

    return [TextContent(type="text", text=f"Applied formatting to characters {start_index}-{end_index} in document {doc_id}")]


async def insert_heading_impl(args: dict) -> list[TextContent]:
    """Insert a heading into a Google Doc"""
    doc_id = args['doc_id']
    text = args['text']
    heading_level = args['heading_level']
    index = args.get('index', 1)
    at_end = args.get('at_end', False)

    if not validate_google_id(doc_id):
        return [TextContent(type="text", text="Error: Invalid document ID format")]

    if heading_level < 1 or heading_level > 6:
        return [TextContent(type="text", text="Error: heading_level must be between 1 and 6")]

    # Map heading level to Google Docs named style
    heading_styles = {
        1: 'HEADING_1',
        2: 'HEADING_2',
        3: 'HEADING_3',
        4: 'HEADING_4',
        5: 'HEADING_5',
        6: 'HEADING_6'
    }

    # If at_end, get current document to find end index
    if at_end:
        doc = docs_service.documents().get(documentId=doc_id).execute()
        index = doc['body']['content'][-1]['endIndex'] - 1

    # Insert text with newline
    text_with_newline = text + '\n'
    end_index = index + len(text_with_newline)

    requests = [
        {
            'insertText': {
                'location': {'index': index},
                'text': text_with_newline
            }
        },
        {
            'updateParagraphStyle': {
                'range': {
                    'startIndex': index,
                    'endIndex': end_index
                },
                'paragraphStyle': {
                    'namedStyleType': heading_styles[heading_level]
                },
                'fields': 'namedStyleType'
            }
        }
    ]

    docs_service.documents().batchUpdate(
        documentId=doc_id,
        body={'requests': requests}
    ).execute()

    return [TextContent(type="text", text=f"Inserted H{heading_level} heading in document {doc_id}")]


async def insert_bullet_list_impl(args: dict) -> list[TextContent]:
    """Insert a bullet or numbered list into a Google Doc"""
    doc_id = args['doc_id']
    items = args['items']
    numbered = args.get('numbered', False)
    index = args.get('index', 1)
    at_end = args.get('at_end', False)

    if not validate_google_id(doc_id):
        return [TextContent(type="text", text="Error: Invalid document ID format")]

    if not items:
        return [TextContent(type="text", text="Error: No items provided")]

    # If at_end, get current document to find end index
    if at_end:
        doc = docs_service.documents().get(documentId=doc_id).execute()
        index = doc['body']['content'][-1]['endIndex'] - 1

    # Build the list text
    list_text = '\n'.join(items) + '\n'
    end_index = index + len(list_text)

    requests = [
        {
            'insertText': {
                'location': {'index': index},
                'text': list_text
            }
        },
        {
            'createParagraphBullets': {
                'range': {
                    'startIndex': index,
                    'endIndex': end_index
                },
                'bulletPreset': 'NUMBERED_DECIMAL_ALPHA_ROMAN' if numbered else 'BULLET_DISC_CIRCLE_SQUARE'
            }
        }
    ]

    docs_service.documents().batchUpdate(
        documentId=doc_id,
        body={'requests': requests}
    ).execute()

    list_type = "numbered" if numbered else "bullet"
    return [TextContent(type="text", text=f"Inserted {list_type} list with {len(items)} items in document {doc_id}")]


def parse_markdown_to_doc_requests(markdown: str) -> tuple[str, list[dict]]:
    """
    Parse markdown and return plain text plus formatting requests.
    Returns (plain_text, list_of_format_requests)
    """
    # This will hold all the formatting requests to apply after text insertion
    format_requests = []

    # Track current position in output text
    plain_text = ""
    current_index = 1  # Google Docs is 1-indexed

    lines = markdown.split('\n')
    i = 0

    while i < len(lines):
        line = lines[i]

        # Check for headings (# Heading)
        heading_match = re.match(r'^(#{1,6})\s+(.+)$', line)
        if heading_match:
            level = len(heading_match.group(1))
            heading_text = heading_match.group(2) + '\n'
            start = current_index
            end = start + len(heading_text)

            plain_text += heading_text
            format_requests.append({
                'updateParagraphStyle': {
                    'range': {'startIndex': start, 'endIndex': end},
                    'paragraphStyle': {'namedStyleType': f'HEADING_{level}'},
                    'fields': 'namedStyleType'
                }
            })
            current_index = end
            i += 1
            continue

        # Check for bullet list items (- item or * item)
        if re.match(r'^[\-\*]\s+', line):
            # Collect consecutive list items
            list_start = current_index
            list_items = []
            while i < len(lines) and re.match(r'^[\-\*]\s+', lines[i]):
                item_text = re.sub(r'^[\-\*]\s+', '', lines[i])
                list_items.append(item_text)
                i += 1

            list_text = '\n'.join(list_items) + '\n'
            list_end = list_start + len(list_text)

            plain_text += list_text
            format_requests.append({
                'createParagraphBullets': {
                    'range': {'startIndex': list_start, 'endIndex': list_end},
                    'bulletPreset': 'BULLET_DISC_CIRCLE_SQUARE'
                }
            })
            current_index = list_end
            continue

        # Check for numbered list items (1. item)
        if re.match(r'^\d+\.\s+', line):
            list_start = current_index
            list_items = []
            while i < len(lines) and re.match(r'^\d+\.\s+', lines[i]):
                item_text = re.sub(r'^\d+\.\s+', '', lines[i])
                list_items.append(item_text)
                i += 1

            list_text = '\n'.join(list_items) + '\n'
            list_end = list_start + len(list_text)

            plain_text += list_text
            format_requests.append({
                'createParagraphBullets': {
                    'range': {'startIndex': list_start, 'endIndex': list_end},
                    'bulletPreset': 'NUMBERED_DECIMAL_ALPHA_ROMAN'
                }
            })
            current_index = list_end
            continue

        # Regular paragraph - handle inline formatting
        processed_line, inline_formats = process_inline_markdown(line, current_index)
        if processed_line or line == '':
            plain_text += processed_line + '\n'
            format_requests.extend(inline_formats)
            current_index += len(processed_line) + 1

        i += 1

    return plain_text, format_requests


def process_inline_markdown(text: str, base_index: int) -> tuple[str, list[dict]]:
    """
    Process inline markdown (bold, italic, links) and return plain text plus format requests.
    """
    format_requests = []
    result = ""
    current_pos = 0
    offset = base_index

    # Pattern for **bold**, *italic*, __bold__, _italic_, [link](url)
    patterns = [
        (r'\*\*(.+?)\*\*', 'bold'),
        (r'__(.+?)__', 'bold'),
        (r'\*(.+?)\*', 'italic'),
        (r'_(.+?)_', 'italic'),
        (r'\[([^\]]+)\]\(([^)]+)\)', 'link'),
    ]

    # Process text character by character, finding and handling markdown
    i = 0
    while i < len(text):
        matched = False

        for pattern, format_type in patterns:
            match = re.match(pattern, text[i:])
            if match:
                matched = True
                if format_type == 'link':
                    link_text = match.group(1)
                    link_url = match.group(2)
                    start = offset + len(result)
                    end = start + len(link_text)

                    result += link_text
                    format_requests.append({
                        'updateTextStyle': {
                            'range': {'startIndex': start, 'endIndex': end},
                            'textStyle': {
                                'link': {'url': link_url},
                                'foregroundColor': {'color': {'rgbColor': {'red': 0.06, 'green': 0.46, 'blue': 0.88}}}
                            },
                            'fields': 'link,foregroundColor'
                        }
                    })
                else:
                    inner_text = match.group(1)
                    start = offset + len(result)
                    end = start + len(inner_text)

                    result += inner_text
                    format_requests.append({
                        'updateTextStyle': {
                            'range': {'startIndex': start, 'endIndex': end},
                            'textStyle': {format_type: True},
                            'fields': format_type
                        }
                    })

                i += len(match.group(0))
                break

        if not matched:
            result += text[i]
            i += 1

    return result, format_requests


async def markdown_to_google_doc_impl(args: dict) -> list[TextContent]:
    """Convert markdown content to a formatted Google Doc"""
    title = args['title']
    markdown = args['markdown']
    folder_id = args.get('folder_id')

    if folder_id and not validate_google_id(folder_id):
        return [TextContent(type="text", text="Error: Invalid folder ID format")]

    # Create the document
    doc = docs_service.documents().create(body={'title': title}).execute()
    doc_id = doc['documentId']

    # If folder_id specified, move the doc there
    if folder_id:
        file = drive_service.files().get(fileId=doc_id, fields='parents').execute()
        previous_parents = ",".join(file.get('parents', []))
        drive_service.files().update(
            fileId=doc_id,
            addParents=folder_id,
            removeParents=previous_parents,
            fields='id, parents'
        ).execute()

    # Parse markdown to plain text and formatting requests
    plain_text, format_requests = parse_markdown_to_doc_requests(markdown)

    if plain_text:
        # First insert all the plain text
        insert_requests = [{
            'insertText': {
                'location': {'index': 1},
                'text': plain_text
            }
        }]

        docs_service.documents().batchUpdate(
            documentId=doc_id,
            body={'requests': insert_requests}
        ).execute()

        # Then apply all formatting
        if format_requests:
            docs_service.documents().batchUpdate(
                documentId=doc_id,
                body={'requests': format_requests}
            ).execute()

    return [TextContent(
        type="text",
        text=f"Created formatted Google Doc: {title}\nID: {doc_id}\nLink: https://docs.google.com/document/d/{doc_id}/edit"
    )]


async def main():
    """Run the MCP server"""
    logger.info("Starting Google Drive MCP Server...")
    
    # Verify credentials file exists
    if not CREDS_PATH.exists():
        logger.error(f"Credentials file not found at {CREDS_PATH}")
        sys.exit(1)
    
    logger.info(f"Using credentials from: {CREDS_PATH}")
    logger.info(f"Token will be saved to: {TOKEN_PATH}")
    
    # Run server
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())

