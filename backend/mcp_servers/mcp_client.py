# backend/mcp_servers/mcp_client.py

from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional
import logging

logger = logging.getLogger(__name__)


class MCPClientBase(ABC):
    """
    Abstract base class for MCP (Model Context Protocol) client implementations.
    Provides interface for connecting to MCP servers and executing tools.
    """
    
    def __init__(self, credentials: Dict[str, Any], config: Optional[Dict[str, Any]] = None):
        """
        Initialize MCP client with credentials and configuration
        
        Args:
            credentials: Dictionary containing authentication credentials
            config: Optional server configuration (site URLs, folder paths, etc.)
        """
        self.credentials = credentials
        self.config = config or {}
        self.connected = False
        self._tools_cache: Optional[List[Dict]] = None
    
    @abstractmethod
    async def connect(self) -> bool:
        """
        Connect to the MCP server and authenticate
        
        Returns:
            True if connection successful, False otherwise
        """
        pass
    
    @abstractmethod
    async def disconnect(self):
        """Disconnect from the MCP server"""
        pass
    
    @abstractmethod
    async def list_tools(self) -> List[Dict[str, Any]]:
        """
        List available tools from the MCP server
        
        Returns:
            List of tool definitions, each containing:
            - name: Tool name
            - description: Tool description
            - parameters: JSON schema for tool parameters
        """
        pass
    
    @abstractmethod
    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Call a tool on the MCP server
        
        Args:
            tool_name: Name of the tool to call
            arguments: Dictionary of tool arguments
            
        Returns:
            Tool execution result containing:
            - success: Boolean indicating success
            - result: Tool result data
            - error: Error message if failed
        """
        pass
    
    async def list_resources(self) -> List[Dict[str, Any]]:
        """
        List available resources from the MCP server (optional)
        
        Returns:
            List of resource definitions
        """
        return []
    
    async def read_resource(self, resource_uri: str) -> Dict[str, Any]:
        """
        Read a resource from the MCP server (optional)
        
        Args:
            resource_uri: URI of the resource to read
            
        Returns:
            Resource content
        """
        raise NotImplementedError("Resource reading not implemented for this client")
    
    def is_connected(self) -> bool:
        """Check if client is connected"""
        return self.connected
    
    async def get_tool_schema(self, tool_name: str) -> Optional[Dict[str, Any]]:
        """
        Get schema for a specific tool
        
        Args:
            tool_name: Name of the tool
            
        Returns:
            Tool schema or None if not found
        """
        tools = await self.list_tools()
        for tool in tools:
            if tool.get('name') == tool_name:
                return tool
        return None
    
    def validate_tool_arguments(self, tool_name: str, arguments: Dict[str, Any]) -> tuple[bool, Optional[str]]:
        """
        Validate tool arguments against tool schema (basic validation)
        
        Args:
            tool_name: Name of the tool
            arguments: Arguments to validate
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        # Basic validation - can be extended by subclasses
        if not isinstance(arguments, dict):
            return False, "Arguments must be a dictionary"
        return True, None

