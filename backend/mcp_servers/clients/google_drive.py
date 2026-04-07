# backend/mcp_servers/clients/google_drive.py

import logging
from typing import Dict, List, Any, Optional
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from ..mcp_client import MCPClientBase

logger = logging.getLogger(__name__)

# Google Drive API scopes
SCOPES = ['https://www.googleapis.com/auth/drive.readonly', 'https://www.googleapis.com/auth/drive.file']


class GoogleDriveMCPClient(MCPClientBase):
    """
    MCP client for Google Drive integration
    Supports listing, reading, searching, and uploading files
    """
    
    def __init__(self, credentials: Dict[str, Any], config: Optional[Dict[str, Any]] = None):
        super().__init__(credentials, config)
        self.service = None
        self._creds: Optional[Credentials] = None
    
    async def connect(self) -> bool:
        """Connect to Google Drive API"""
        try:
            # Extract credentials
            client_id = self.credentials.get('client_id')
            client_secret = self.credentials.get('client_secret')
            refresh_token = self.credentials.get('refresh_token')
            
            if not all([client_id, client_secret, refresh_token]):
                logger.error("Missing required Google Drive credentials")
                return False
            
            # Create credentials object
            creds = Credentials(
                token=None,
                refresh_token=refresh_token,
                token_uri='https://oauth2.googleapis.com/token',
                client_id=client_id,
                client_secret=client_secret,
                scopes=SCOPES
            )
            
            # Refresh token if needed
            if creds.expired:
                creds.refresh(Request())
            
            # Build Drive service
            self.service = build('drive', 'v3', credentials=creds)
            self._creds = creds
            self.connected = True
            
            logger.info("✅ Connected to Google Drive API")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to connect to Google Drive: {e}")
            self.connected = False
            return False
    
    async def disconnect(self):
        """Disconnect from Google Drive"""
        self.service = None
        self._creds = None
        self.connected = False
    
    async def list_tools(self) -> List[Dict[str, Any]]:
        """List available Google Drive tools"""
        return [
            {
                'name': 'list_files',
                'description': 'List files and folders in Google Drive',
                'parameters': {
                    'type': 'object',
                    'properties': {
                        'query': {
                            'type': 'string',
                            'description': 'Search query (optional)'
                        },
                        'folder_id': {
                            'type': 'string',
                            'description': 'Folder ID to list files from (optional)'
                        },
                        'max_results': {
                            'type': 'integer',
                            'description': 'Maximum number of results',
                            'default': 10
                        }
                    }
                }
            },
            {
                'name': 'read_file',
                'description': 'Read content of a Google Drive file',
                'parameters': {
                    'type': 'object',
                    'properties': {
                        'file_id': {
                            'type': 'string',
                            'description': 'Google Drive file ID',
                            'required': True
                        },
                        'mime_type': {
                            'type': 'string',
                            'description': 'MIME type for export (e.g., text/plain, application/pdf)',
                            'default': 'text/plain'
                        }
                    },
                    'required': ['file_id']
                }
            },
            {
                'name': 'search_files',
                'description': 'Search for files in Google Drive',
                'parameters': {
                    'type': 'object',
                    'properties': {
                        'query': {
                            'type': 'string',
                            'description': 'Search query',
                            'required': True
                        },
                        'max_results': {
                            'type': 'integer',
                            'description': 'Maximum number of results',
                            'default': 10
                        }
                    },
                    'required': ['query']
                }
            },
            {
                'name': 'upload_file',
                'description': 'Upload a file to Google Drive',
                'parameters': {
                    'type': 'object',
                    'properties': {
                        'file_name': {
                            'type': 'string',
                            'description': 'Name of the file',
                            'required': True
                        },
                        'content': {
                            'type': 'string',
                            'description': 'File content',
                            'required': True
                        },
                        'mime_type': {
                            'type': 'string',
                            'description': 'MIME type of the file',
                            'default': 'text/plain'
                        },
                        'folder_id': {
                            'type': 'string',
                            'description': 'Folder ID to upload to (optional)'
                        }
                    },
                    'required': ['file_name', 'content']
                }
            }
        ]
    
    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a Google Drive tool"""
        if not self.connected or not self.service:
            return {
                'success': False,
                'error': 'Not connected to Google Drive'
            }
        
        try:
            if tool_name == 'list_files':
                return await self._list_files(arguments)
            elif tool_name == 'read_file':
                return await self._read_file(arguments)
            elif tool_name == 'search_files':
                return await self._search_files(arguments)
            elif tool_name == 'upload_file':
                return await self._upload_file(arguments)
            else:
                return {
                    'success': False,
                    'error': f'Unknown tool: {tool_name}'
                }
        except Exception as e:
            logger.error(f"❌ Error executing tool {tool_name}: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    async def _list_files(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """List files in Google Drive"""
        try:
            query_parts = []
            
            # Folder filter
            if 'folder_id' in arguments:
                query_parts.append(f"'{arguments['folder_id']}' in parents")
            
            # Search query
            if 'query' in arguments:
                query_parts.append(f"name contains '{arguments['query']}'")
            
            query = ' and '.join(query_parts) if query_parts else None
            max_results = arguments.get('max_results', 10)
            
            results = self.service.files().list(
                q=query,
                pageSize=max_results,
                fields='files(id, name, mimeType, modifiedTime, size)'
            ).execute()
            
            files = results.get('files', [])
            
            return {
                'success': True,
                'result': {
                    'files': files,
                    'count': len(files)
                }
            }
        except HttpError as e:
            return {
                'success': False,
                'error': f'Google Drive API error: {e}'
            }
    
    async def _read_file(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Read file content from Google Drive"""
        try:
            file_id = arguments['file_id']
            mime_type = arguments.get('mime_type', 'text/plain')
            
            # Get file metadata
            file_metadata = self.service.files().get(fileId=file_id).execute()
            
            # Export or download file
            if 'exportLinks' in file_metadata and mime_type in file_metadata['exportLinks']:
                # Use export link
                import requests
                response = requests.get(
                    file_metadata['exportLinks'][mime_type],
                    headers={'Authorization': f'Bearer {self._creds.token}'}
                )
                content = response.text
            else:
                # Download file
                request = self.service.files().get_media(fileId=file_id)
                content = request.execute()
                if isinstance(content, bytes):
                    content = content.decode('utf-8')
            
            return {
                'success': True,
                'result': {
                    'file_id': file_id,
                    'file_name': file_metadata.get('name'),
                    'content': content,
                    'mime_type': file_metadata.get('mimeType')
                }
            }
        except HttpError as e:
            return {
                'success': False,
                'error': f'Google Drive API error: {e}'
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    async def _search_files(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Search files in Google Drive"""
        try:
            query = arguments['query']
            max_results = arguments.get('max_results', 10)
            
            results = self.service.files().list(
                q=f"name contains '{query}' or fullText contains '{query}'",
                pageSize=max_results,
                fields='files(id, name, mimeType, modifiedTime, size)'
            ).execute()
            
            files = results.get('files', [])
            
            return {
                'success': True,
                'result': {
                    'files': files,
                    'count': len(files),
                    'query': query
                }
            }
        except HttpError as e:
            return {
                'success': False,
                'error': f'Google Drive API error: {e}'
            }
    
    async def _upload_file(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Upload file to Google Drive"""
        try:
            from googleapiclient.http import MediaIoBaseUpload
            import io
            
            file_name = arguments['file_name']
            content = arguments['content']
            mime_type = arguments.get('mime_type', 'text/plain')
            folder_id = arguments.get('folder_id')
            
            # Create file metadata
            file_metadata = {'name': file_name}
            if folder_id:
                file_metadata['parents'] = [folder_id]
            
            # Create media upload
            media = MediaIoBaseUpload(
                io.BytesIO(content.encode('utf-8')),
                mimetype=mime_type,
                resumable=True
            )
            
            # Upload file
            file = self.service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id, name, mimeType'
            ).execute()
            
            return {
                'success': True,
                'result': {
                    'file_id': file.get('id'),
                    'file_name': file.get('name'),
                    'mime_type': file.get('mimeType')
                }
            }
        except HttpError as e:
            return {
                'success': False,
                'error': f'Google Drive API error: {e}'
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }

