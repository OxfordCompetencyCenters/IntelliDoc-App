# backend/mcp_servers/apps.py

from django.apps import AppConfig


class MCPServersConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'mcp_servers'
    verbose_name = 'MCP Servers'

    def ready(self):
        import mcp_servers.signals  # noqa

