# backend/mcp_servers/manager.py

import logging
from typing import Dict, Optional, List, Any
from asgiref.sync import sync_to_async

from users.models import IntelliDocProject
from .services import get_mcp_server_credential_service
from .clients.google_drive import GoogleDriveMCPClient
from .clients.sharepoint import SharePointMCPClient
from .mcp_client import MCPClientBase

logger = logging.getLogger(__name__)


class MCPServerManager:
    """
    Manages MCP server client instances, connection pooling, and tool execution
    """
    
    def __init__(self):
        self._clients: Dict[str, MCPClientBase] = {}  # Cache of connected clients
        self.credential_service = get_mcp_server_credential_service()
        logger.info("🔧 MCP SERVER MANAGER: Initialized")
    
    async def get_server_client(
        self,
        project: IntelliDocProject,
        server_type: str,
        force_reconnect: bool = False
    ) -> Optional[MCPClientBase]:
        """
        Get or create MCP server client for a project
        
        Args:
            project: IntelliDocProject instance
            server_type: MCP server type (google_drive, sharepoint)
            force_reconnect: Force reconnection even if client exists
            
        Returns:
            MCPClientBase instance or None if failed
        """
        # Create cache key
        cache_key = f"{project.project_id}:{server_type}"
        
        # Return cached client if exists and not forcing reconnect
        if not force_reconnect and cache_key in self._clients:
            client = self._clients[cache_key]
            if client.is_connected():
                return client
            else:
                # Remove disconnected client from cache
                del self._clients[cache_key]
        
        try:
            # Get credentials
            credentials = await self.credential_service.get_credentials_async(project, server_type)
            if not credentials:
                logger.warning(f"⚠️ No credentials found for project {project.name} - {server_type}")
                return None
            
            # Get server config
            credential_obj = await sync_to_async(
                lambda: self.credential_service.get_project_credentials(project).get(server_type)
            )()
            server_config = credential_obj.server_config if credential_obj else {}
            
            # Create client based on server type
            if server_type == 'google_drive':
                client = GoogleDriveMCPClient(credentials, server_config)
            elif server_type == 'sharepoint':
                client = SharePointMCPClient(credentials, server_config)
            else:
                logger.error(f"❌ Unknown server type: {server_type}")
                return None
            
            # Connect
            connected = await client.connect()
            if not connected:
                logger.error(f"❌ Failed to connect to {server_type} for project {project.name}")
                return None
            
            # Cache client
            self._clients[cache_key] = client
            logger.info(f"✅ Connected to {server_type} for project {project.name}")
            return client
            
        except Exception as e:
            logger.error(f"❌ Error getting MCP client for {server_type}: {e}")
            return None
    
    async def get_available_tools(
        self,
        project: IntelliDocProject,
        server_type: str
    ) -> List[Dict[str, Any]]:
        """
        Get list of available tools from MCP server
        
        Args:
            project: IntelliDocProject instance
            server_type: MCP server type
            
        Returns:
            List of tool definitions
        """
        client = await self.get_server_client(project, server_type)
        if not client:
            return []
        
        try:
            tools = await client.list_tools()
            return tools
        except Exception as e:
            logger.error(f"❌ Error getting tools from {server_type}: {e}")
            return []
    
    async def execute_tool(
        self,
        project: IntelliDocProject,
        server_type: str,
        tool_name: str,
        arguments: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Execute a tool on an MCP server
        
        Args:
            project: IntelliDocProject instance
            server_type: MCP server type
            tool_name: Name of the tool to execute
            arguments: Tool arguments
            
        Returns:
            Tool execution result
        """
        client = await self.get_server_client(project, server_type)
        if not client:
            return {
                'success': False,
                'error': f'Could not connect to {server_type} server'
            }
        
        try:
            # Validate tool exists
            tool_schema = await client.get_tool_schema(tool_name)
            if not tool_schema:
                return {
                    'success': False,
                    'error': f'Tool {tool_name} not found on {server_type} server'
                }
            
            # Validate arguments
            is_valid, error_msg = client.validate_tool_arguments(tool_name, arguments)
            if not is_valid:
                return {
                    'success': False,
                    'error': f'Invalid tool arguments: {error_msg}'
                }
            
            # Execute tool
            result = await client.call_tool(tool_name, arguments)
            logger.info(f"✅ Executed tool {tool_name} on {server_type} for project {project.name}")
            return result
            
        except Exception as e:
            logger.error(f"❌ Error executing tool {tool_name} on {server_type}: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    async def test_connection(
        self,
        project: IntelliDocProject,
        server_type: str
    ) -> Dict[str, Any]:
        """
        Test connection to MCP server
        
        Args:
            project: IntelliDocProject instance
            server_type: MCP server type
            
        Returns:
            Connection test result
        """
        client = await self.get_server_client(project, server_type, force_reconnect=True)
        if not client:
            return {
                'success': False,
                'error': f'Could not connect to {server_type} server'
            }
        
        try:
            # Try to list tools as a connection test
            tools = await client.list_tools()
            return {
                'success': True,
                'message': f'Successfully connected to {server_type}',
                'tools_count': len(tools)
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def clear_cache(self, project_id: Optional[str] = None, server_type: Optional[str] = None):
        """
        Clear client cache
        
        Args:
            project_id: Optional project ID to clear (if None, clears all)
            server_type: Optional server type to clear (if None, clears all)
        """
        if project_id and server_type:
            cache_key = f"{project_id}:{server_type}"
            if cache_key in self._clients:
                client = self._clients[cache_key]
                # Disconnect before removing
                try:
                    import asyncio
                    if asyncio.iscoroutinefunction(client.disconnect):
                        asyncio.create_task(client.disconnect())
                    else:
                        client.disconnect()
                except:
                    pass
                del self._clients[cache_key]
        else:
            # Clear all
            for client in self._clients.values():
                try:
                    import asyncio
                    if asyncio.iscoroutinefunction(client.disconnect):
                        asyncio.create_task(client.disconnect())
                    else:
                        client.disconnect()
                except:
                    pass
            self._clients.clear()


# Global instance
_manager_instance = None

def get_mcp_server_manager() -> MCPServerManager:
    """Get singleton manager instance"""
    global _manager_instance
    if _manager_instance is None:
        _manager_instance = MCPServerManager()
    return _manager_instance

