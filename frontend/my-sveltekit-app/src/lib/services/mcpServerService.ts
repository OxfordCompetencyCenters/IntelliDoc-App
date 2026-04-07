// frontend/my-sveltekit-app/src/lib/services/mcpServerService.ts

const API_BASE = '/api';

export interface MCPServerType {
  code: string;
  name: string;
  display_name: string;
  description: string;
  icon: string;
  color: string;
}

export interface MCPServerCredential {
  server_type: string;
  credential_name?: string;
  is_active: boolean;
  is_validated: boolean;
  validation_error?: string;
  last_validated_at?: string;
  usage_count: number;
  last_used_at?: string;
  status_display: string;
}

export interface MCPServerTool {
  name: string;
  description: string;
  parameters: {
    type: string;
    properties?: Record<string, any>;
    required?: string[];
  };
}

export interface MCPServerStatus {
  project_id: string;
  project_name: string;
  servers: Array<MCPServerType & {
    has_credentials: boolean;
    is_active: boolean;
    is_validated: boolean;
    validation_error?: string;
    last_validated_at?: string;
    usage_count: number;
    last_used_at?: string;
    status_display: string;
  }>;
}

/**
 * Get available MCP server types
 */
export async function getMCPServerTypes(): Promise<MCPServerType[]> {
  const response = await fetch(`${API_BASE}/mcp-servers/types/`, {
    method: 'GET',
    headers: {
      'Content-Type': 'application/json',
    },
    credentials: 'include',
  });

  if (!response.ok) {
    throw new Error(`Failed to get MCP server types: ${response.statusText}`);
  }

  return response.json();
}

/**
 * Get MCP server credentials status for a project
 */
export async function getMCPServerStatus(projectId: string): Promise<MCPServerStatus> {
  const response = await fetch(`${API_BASE}/mcp-servers/projects/${projectId}/credentials/`, {
    method: 'GET',
    headers: {
      'Content-Type': 'application/json',
    },
    credentials: 'include',
  });

  if (!response.ok) {
    throw new Error(`Failed to get MCP server status: ${response.statusText}`);
  }

  return response.json();
}

/**
 * Get MCP server credentials for a project and server type
 */
export async function getMCPServerCredentials(
  projectId: string,
  serverType: string
): Promise<MCPServerCredential | null> {
  const response = await fetch(
    `${API_BASE}/mcp-servers/projects/${projectId}/credentials/${serverType}/`,
    {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
      },
      credentials: 'include',
    }
  );

  if (response.status === 404) {
    return null;
  }

  if (!response.ok) {
    throw new Error(`Failed to get MCP server credentials: ${response.statusText}`);
  }

  return response.json();
}

/**
 * Set MCP server credentials for a project and server type
 */
export async function setMCPServerCredentials(
  projectId: string,
  serverType: string,
  credentials: Record<string, any>,
  credentialName?: string,
  serverConfig?: Record<string, any>
): Promise<MCPServerCredential> {
  const response = await fetch(
    `${API_BASE}/mcp-servers/projects/${projectId}/credentials/${serverType}/`,
    {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      credentials: 'include',
      body: JSON.stringify({
        credentials,
        credential_name: credentialName,
        server_config: serverConfig || {},
      }),
    }
  );

  if (!response.ok) {
    const error = await response.json().catch(() => ({ error: response.statusText }));
    throw new Error(error.error || `Failed to set MCP server credentials: ${response.statusText}`);
  }

  return response.json();
}

/**
 * Test MCP server connection
 */
export async function testMCPServerConnection(
  projectId: string,
  serverType: string
): Promise<{ success: boolean; message?: string; error?: string; tools_count?: number }> {
  const response = await fetch(
    `${API_BASE}/mcp-servers/projects/${projectId}/credentials/${serverType}/test/`,
    {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      credentials: 'include',
    }
  );

  if (!response.ok) {
    const error = await response.json().catch(() => ({ error: response.statusText }));
    throw new Error(error.error || `Failed to test MCP server connection: ${response.statusText}`);
  }

  return response.json();
}

/**
 * Get available tools from MCP server
 */
export async function getMCPServerTools(
  projectId: string,
  serverType: string
): Promise<MCPServerTool[]> {
  const response = await fetch(
    `${API_BASE}/mcp-servers/projects/${projectId}/credentials/${serverType}/tools/`,
    {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
      },
      credentials: 'include',
    }
  );

  if (!response.ok) {
    throw new Error(`Failed to get MCP server tools: ${response.statusText}`);
  }

  return response.json();
}

/**
 * Delete MCP server credentials
 */
export async function deleteMCPServerCredentials(
  projectId: string,
  serverType: string
): Promise<void> {
  const response = await fetch(
    `${API_BASE}/mcp-servers/projects/${projectId}/credentials/${serverType}/`,
    {
      method: 'DELETE',
      headers: {
        'Content-Type': 'application/json',
      },
      credentials: 'include',
    }
  );

  if (!response.ok) {
    throw new Error(`Failed to delete MCP server credentials: ${response.statusText}`);
  }
}

