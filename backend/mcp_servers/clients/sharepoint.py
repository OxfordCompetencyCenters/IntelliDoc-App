# backend/mcp_servers/clients/sharepoint.py

import logging
from typing import Dict, List, Any, Optional
from msal import ConfidentialClientApplication
import requests

from ..mcp_client import MCPClientBase

logger = logging.getLogger(__name__)


class SharePointMCPClient(MCPClientBase):
    """
    MCP client for SharePoint integration
    Supports listing, reading, searching, and uploading documents
    """
    
    def __init__(self, credentials: Dict[str, Any], config: Optional[Dict[str, Any]] = None):
        super().__init__(credentials, config)
        self.access_token: Optional[str] = None
        self.site_url = config.get('site_url', '') if config else ''
        self.graph_endpoint = 'https://graph.microsoft.com/v1.0'
    
    async def connect(self) -> bool:
        """Connect to SharePoint via Microsoft Graph API"""
        try:
            # Extract credentials
            tenant_id = self.credentials.get('tenant_id')
            client_id = self.credentials.get('client_id')
            client_secret = self.credentials.get('client_secret')
            
            if not all([tenant_id, client_id, client_secret]):
                logger.error("Missing required SharePoint credentials")
                return False
            
            # Create MSAL app
            authority = f"https://login.microsoftonline.com/{tenant_id}"
            app = ConfidentialClientApplication(
                client_id=client_id,
                client_credential=client_secret,
                authority=authority
            )
            
            # Get access token
            scopes = ['https://graph.microsoft.com/.default']
            result = app.acquire_token_for_client(scopes=scopes)
            
            if 'access_token' in result:
                self.access_token = result['access_token']
                self.connected = True
                logger.info("✅ Connected to SharePoint via Microsoft Graph API")
                return True
            else:
                error = result.get('error_description', result.get('error', 'Unknown error'))
                logger.error(f"❌ Failed to get SharePoint access token: {error}")
                self.connected = False
                return False
                
        except Exception as e:
            logger.error(f"❌ Failed to connect to SharePoint: {e}")
            self.connected = False
            return False
    
    async def disconnect(self):
        """Disconnect from SharePoint"""
        self.access_token = None
        self.connected = False
    
    def _get_site_id(self) -> Optional[str]:
        """Get SharePoint site ID from site URL"""
        if not self.site_url:
            return None
        
        try:
            # Extract site path from URL
            # Example: https://contoso.sharepoint.com/sites/MySite -> /sites/MySite
            from urllib.parse import urlparse
            parsed = urlparse(self.site_url)
            site_path = parsed.path
            
            # Get site by path
            url = f"{self.graph_endpoint}/sites/{parsed.netloc}:{site_path}"
            headers = {'Authorization': f'Bearer {self.access_token}'}
            response = requests.get(url, headers=headers)
            
            if response.status_code == 200:
                return response.json().get('id')
            else:
                logger.warning(f"Failed to get site ID: {response.status_code}")
                return None
        except Exception as e:
            logger.error(f"Error getting site ID: {e}")
            return None
    
    async def list_tools(self) -> List[Dict[str, Any]]:
        """List available SharePoint tools"""
        return [
            {
                'name': 'list_documents',
                'description': 'List documents in SharePoint site',
                'parameters': {
                    'type': 'object',
                    'properties': {
                        'folder_path': {
                            'type': 'string',
                            'description': 'Folder path within site (optional)'
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
                'name': 'read_document',
                'description': 'Read content of a SharePoint document',
                'parameters': {
                    'type': 'object',
                    'properties': {
                        'file_id': {
                            'type': 'string',
                            'description': 'SharePoint file ID',
                            'required': True
                        }
                    },
                    'required': ['file_id']
                }
            },
            {
                'name': 'search_documents',
                'description': 'Search for documents in SharePoint',
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
                'name': 'upload_document',
                'description': 'Upload a document to SharePoint',
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
                        'folder_path': {
                            'type': 'string',
                            'description': 'Folder path within site (optional)'
                        }
                    },
                    'required': ['file_name', 'content']
                }
            }
        ]
    
    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a SharePoint tool"""
        if not self.connected or not self.access_token:
            return {
                'success': False,
                'error': 'Not connected to SharePoint'
            }
        
        try:
            if tool_name == 'list_documents':
                return await self._list_documents(arguments)
            elif tool_name == 'read_document':
                return await self._read_document(arguments)
            elif tool_name == 'search_documents':
                return await self._search_documents(arguments)
            elif tool_name == 'upload_document':
                return await self._upload_document(arguments)
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
    
    async def _list_documents(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """List documents in SharePoint"""
        try:
            site_id = self._get_site_id()
            if not site_id:
                return {
                    'success': False,
                    'error': 'Could not determine SharePoint site ID'
                }
            
            folder_path = arguments.get('folder_path', '')
            max_results = arguments.get('max_results', 10)
            
            # Build drive item path
            if folder_path:
                # Get drive and folder
                url = f"{self.graph_endpoint}/sites/{site_id}/drive/root:/{folder_path}:/children"
            else:
                url = f"{self.graph_endpoint}/sites/{site_id}/drive/root/children"
            
            headers = {
                'Authorization': f'Bearer {self.access_token}',
                'Accept': 'application/json'
            }
            
            params = {'$top': max_results}
            response = requests.get(url, headers=headers, params=params)
            
            if response.status_code == 200:
                data = response.json()
                files = data.get('value', [])
                return {
                    'success': True,
                    'result': {
                        'files': files,
                        'count': len(files)
                    }
                }
            else:
                return {
                    'success': False,
                    'error': f'SharePoint API error: {response.status_code} - {response.text}'
                }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    async def _read_document(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Read document content from SharePoint"""
        try:
            file_id = arguments['file_id']
            
            # Get file content
            url = f"{self.graph_endpoint}/sites/{file_id}/content"
            headers = {
                'Authorization': f'Bearer {self.access_token}',
                'Accept': 'text/plain'
            }
            
            response = requests.get(url, headers=headers)
            
            if response.status_code == 200:
                # Get file metadata
                metadata_url = f"{self.graph_endpoint}/sites/{file_id}"
                metadata_response = requests.get(
                    metadata_url,
                    headers={'Authorization': f'Bearer {self.access_token}'}
                )
                
                metadata = metadata_response.json() if metadata_response.status_code == 200 else {}
                
                content = response.text
                return {
                    'success': True,
                    'result': {
                        'file_id': file_id,
                        'file_name': metadata.get('name', ''),
                        'content': content,
                        'mime_type': metadata.get('file', {}).get('mimeType', '')
                    }
                }
            else:
                return {
                    'success': False,
                    'error': f'SharePoint API error: {response.status_code} - {response.text}'
                }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    async def _search_documents(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Search documents in SharePoint"""
        try:
            site_id = self._get_site_id()
            if not site_id:
                return {
                    'success': False,
                    'error': 'Could not determine SharePoint site ID'
                }
            
            query = arguments['query']
            max_results = arguments.get('max_results', 10)
            
            # Search using Microsoft Graph search API
            url = f"{self.graph_endpoint}/sites/{site_id}/drive/root/search(q='{query}')"
            headers = {
                'Authorization': f'Bearer {self.access_token}',
                'Accept': 'application/json'
            }
            
            params = {'$top': max_results}
            response = requests.get(url, headers=headers, params=params)
            
            if response.status_code == 200:
                data = response.json()
                files = data.get('value', [])
                return {
                    'success': True,
                    'result': {
                        'files': files,
                        'count': len(files),
                        'query': query
                    }
                }
            else:
                return {
                    'success': False,
                    'error': f'SharePoint API error: {response.status_code} - {response.text}'
                }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    async def _upload_document(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Upload document to SharePoint"""
        try:
            site_id = self._get_site_id()
            if not site_id:
                return {
                    'success': False,
                    'error': 'Could not determine SharePoint site ID'
                }
            
            file_name = arguments['file_name']
            content = arguments['content']
            folder_path = arguments.get('folder_path', '')
            
            # Build upload URL
            if folder_path:
                upload_url = f"{self.graph_endpoint}/sites/{site_id}/drive/root:/{folder_path}/{file_name}:/content"
            else:
                upload_url = f"{self.graph_endpoint}/sites/{site_id}/drive/root:/{file_name}:/content"
            
            headers = {
                'Authorization': f'Bearer {self.access_token}',
                'Content-Type': 'text/plain'
            }
            
            response = requests.put(upload_url, headers=headers, data=content.encode('utf-8'))
            
            if response.status_code in [200, 201]:
                file_data = response.json()
                return {
                    'success': True,
                    'result': {
                        'file_id': file_data.get('id'),
                        'file_name': file_data.get('name'),
                        'mime_type': file_data.get('file', {}).get('mimeType', '')
                    }
                }
            else:
                return {
                    'success': False,
                    'error': f'SharePoint API error: {response.status_code} - {response.text}'
                }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }

