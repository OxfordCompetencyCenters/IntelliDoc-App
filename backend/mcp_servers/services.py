# backend/mcp_servers/services.py

import logging
import json
from typing import Dict, Optional, List, Tuple
from django.core.exceptions import ObjectDoesNotExist
from django.utils import timezone
from asgiref.sync import sync_to_async

from users.models import IntelliDocProject, MCPServerCredential, MCPServerType
from project_api_keys.encryption import encryption_service

logger = logging.getLogger(__name__)


class MCPServerCredentialService:
    """Service for managing project-specific MCP server credentials"""
    
    def __init__(self):
        self.encryption_service = encryption_service
        logger.info("🔐 MCP SERVER CREDENTIAL SERVICE: Initialized")
    
    def get_credentials(self, project: IntelliDocProject, server_type: str) -> Optional[Dict]:
        """
        Get decrypted credentials for a project and MCP server type (sync version)
        
        Args:
            project: IntelliDocProject instance
            server_type: MCP server type (google_drive, sharepoint)
            
        Returns:
            Decrypted credentials dict or None if not found/inactive
        """
        if not isinstance(project, IntelliDocProject):
            error_msg = f"❌ Invalid project type: expected IntelliDocProject, got {type(project).__name__}"
            logger.error(error_msg)
            raise TypeError(error_msg)
        
        try:
            credential_obj = MCPServerCredential.objects.get(
                project=project,
                server_type=server_type,
                is_active=True
            )
            
            # Decrypt the credentials
            decrypted_creds = self.encryption_service.decrypt_mcp_credentials(
                str(project.project_id),
                credential_obj.encrypted_credentials
            )
            
            # Update usage tracking
            credential_obj.usage_count += 1
            credential_obj.last_used_at = timezone.now()
            credential_obj.save(update_fields=['usage_count', 'last_used_at'])
            
            logger.info(f"🔐 Retrieved MCP credentials for project {project.name} - {server_type}")
            return decrypted_creds
            
        except ObjectDoesNotExist:
            logger.warning(f"⚠️ No active MCP credentials found for project {project.name} - {server_type}")
            return None
        except TypeError:
            raise
        except Exception as e:
            project_name = getattr(project, 'name', f'<{type(project).__name__}>')
            logger.error(f"❌ Failed to retrieve MCP credentials for project {project_name} - {server_type}: {e}")
            return None
    
    async def get_credentials_async(self, project: IntelliDocProject, server_type: str) -> Optional[Dict]:
        """
        Get decrypted credentials for a project and MCP server type (async version)
        
        Args:
            project: IntelliDocProject instance
            server_type: MCP server type (google_drive, sharepoint)
            
        Returns:
            Decrypted credentials dict or None if not found/inactive
        """
        try:
            credential_obj = await sync_to_async(MCPServerCredential.objects.get)(
                project=project,
                server_type=server_type,
                is_active=True
            )
            
            # Decrypt the credentials
            decrypted_creds = self.encryption_service.decrypt_mcp_credentials(
                str(project.project_id),
                credential_obj.encrypted_credentials
            )
            
            # Update usage tracking
            credential_obj.usage_count += 1
            credential_obj.last_used_at = timezone.now()
            await sync_to_async(credential_obj.save)(update_fields=['usage_count', 'last_used_at'])
            
            logger.info(f"🔐 Retrieved MCP credentials for project {project.name} - {server_type}")
            return decrypted_creds
            
        except ObjectDoesNotExist:
            logger.warning(f"⚠️ No active MCP credentials found for project {project.name} - {server_type}")
            return None
        except Exception as e:
            logger.error(f"❌ Failed to retrieve MCP credentials for project {project.name} - {server_type}: {e}")
            return None
    
    def set_credentials(
        self,
        project: IntelliDocProject,
        server_type: str,
        credentials: Dict,
        user,
        credential_name: str = "",
        server_config: Optional[Dict] = None,
        validate_credentials: bool = True
    ) -> Tuple[MCPServerCredential, bool]:
        """
        Set or update MCP server credentials for a project
        
        Args:
            project: IntelliDocProject instance
            server_type: MCP server type (google_drive, sharepoint)
            credentials: Dictionary containing credentials (OAuth tokens, client IDs, etc.)
            user: User setting the credentials
            credential_name: Optional descriptive name
            server_config: Optional server configuration (site URLs, folder paths, etc.)
            validate_credentials: Whether to validate the credentials with the server
            
        Returns:
            Tuple of (MCPServerCredential instance, created_boolean)
        """
        try:
            # Validate server type
            if server_type not in [choice[0] for choice in MCPServerType.choices]:
                raise ValueError(f"Invalid server type: {server_type}")
            
            # Encrypt the credentials
            encrypted_creds = self.encryption_service.encrypt_mcp_credentials(
                str(project.project_id),
                credentials
            )
            
            # Get or create the credential record
            credential_obj, created = MCPServerCredential.objects.get_or_create(
                project=project,
                server_type=server_type,
                defaults={
                    'encrypted_credentials': encrypted_creds,
                    'credential_name': credential_name,
                    'server_config': server_config or {},
                    'created_by': user,
                    'is_active': True,
                    'is_validated': False
                }
            )
            
            # Update existing credentials
            if not created:
                credential_obj.encrypted_credentials = encrypted_creds
                credential_obj.credential_name = credential_name
                if server_config is not None:
                    credential_obj.server_config = server_config
                credential_obj.is_active = True
                credential_obj.is_validated = False
                credential_obj.validation_error = ""
                credential_obj.save()
                logger.info(f"🔄 Updated MCP credentials for project {project.name} - {server_type}")
            else:
                logger.info(f"➕ Created new MCP credentials for project {project.name} - {server_type}")
            
            # Validate the credentials if requested
            if validate_credentials:
                validation_result = self.validate_credentials(credential_obj, credentials)
                if validation_result['is_valid']:
                    credential_obj.is_validated = True
                    credential_obj.last_validated_at = timezone.now()
                else:
                    credential_obj.validation_error = validation_result['error']
                credential_obj.save()
            
            return credential_obj, created
            
        except Exception as e:
            logger.error(f"❌ Failed to set MCP credentials for project {project.name} - {server_type}: {e}")
            raise ValueError(f"Failed to set MCP credentials: {e}")
    
    def validate_credentials(self, credential_obj: MCPServerCredential, plaintext_credentials: Dict = None) -> Dict:
        """
        Validate MCP server credentials by attempting to connect
        
        Args:
            credential_obj: MCPServerCredential instance
            plaintext_credentials: Optional plaintext credentials dict (if not provided, will decrypt)
            
        Returns:
            Dict with 'is_valid', 'error', 'validated_at'
        """
        try:
            if not plaintext_credentials:
                plaintext_credentials = self.encryption_service.decrypt_mcp_credentials(
                    str(credential_obj.project.project_id),
                    credential_obj.encrypted_credentials
                )
            
            logger.info(f"🔍 Validating {credential_obj.server_type} credentials for project {credential_obj.project.name}")
            
            # Basic validation - check required fields based on server type
            required_fields = self._get_required_fields(credential_obj.server_type)
            missing_fields = [field for field in required_fields if field not in plaintext_credentials or not plaintext_credentials[field]]
            
            if missing_fields:
                error_msg = f"Missing required fields: {', '.join(missing_fields)}"
                logger.warning(f"❌ MCP credential validation failed for {credential_obj.server_type}: {error_msg}")
                return {
                    'is_valid': False,
                    'error': error_msg,
                    'validated_at': timezone.now().isoformat()
                }
            
            # TODO: Add actual connection test when MCP clients are implemented
            # For now, just validate structure
            logger.info(f"✅ MCP credential validation successful for {credential_obj.server_type}")
            return {
                'is_valid': True,
                'error': '',
                'validated_at': timezone.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"❌ Error validating MCP credentials: {e}")
            return {
                'is_valid': False,
                'error': f"Validation error: {str(e)}",
                'validated_at': timezone.now().isoformat()
            }
    
    def _get_required_fields(self, server_type: str) -> List[str]:
        """Get required credential fields for a server type"""
        field_map = {
            'google_drive': ['client_id', 'client_secret', 'refresh_token'],
            'sharepoint': ['tenant_id', 'client_id', 'client_secret', 'site_url']
        }
        return field_map.get(server_type, [])
    
    def get_project_credentials(self, project: IntelliDocProject) -> Dict[str, MCPServerCredential]:
        """Get all MCP server credentials for a project"""
        try:
            credentials = MCPServerCredential.objects.filter(
                project=project,
                is_active=True
            ).select_related('created_by')
            
            return {
                cred.server_type: cred for cred in credentials
            }
            
        except Exception as e:
            logger.error(f"❌ Failed to get MCP credentials for project {project.name}: {e}")
            return {}
    
    def delete_credentials(self, project: IntelliDocProject, server_type: str) -> bool:
        """Delete MCP server credentials for a project and server type"""
        try:
            MCPServerCredential.objects.filter(
                project=project,
                server_type=server_type
            ).delete()
            
            logger.info(f"🗑️ Deleted MCP credentials for project {project.name} - {server_type}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to delete MCP credentials for project {project.name} - {server_type}: {e}")
            return False
    
    def get_available_server_types(self) -> List[Dict]:
        """Get list of available MCP server types with their information"""
        server_types = []
        
        for server_code, server_name in MCPServerType.choices:
            # Get display info from a dummy credential
            dummy_cred = MCPServerCredential(server_type=server_code)
            display_info = dummy_cred.get_server_display_info()
            
            server_types.append({
                'code': server_code,
                'name': server_name,
                'display_name': display_info['name'],
                'description': display_info['description'],
                'icon': display_info['icon'],
                'color': display_info['color']
            })
        
        return server_types
    
    def get_project_credentials_status(self, project: IntelliDocProject) -> Dict:
        """Get comprehensive status of all MCP server credentials for a project"""
        try:
            credentials = self.get_project_credentials(project)
            available_servers = self.get_available_server_types()
            
            status = {
                'project_id': str(project.project_id),
                'project_name': project.name,
                'servers': []
            }
            
            for server in available_servers:
                server_code = server['code']
                credential_obj = credentials.get(server_code)
                
                server_status = {
                    **server,
                    'has_credentials': credential_obj is not None,
                    'is_active': credential_obj.is_active if credential_obj else False,
                    'is_validated': credential_obj.is_validated if credential_obj else False,
                    'validation_error': credential_obj.validation_error if credential_obj else '',
                    'last_validated_at': credential_obj.last_validated_at.isoformat() if credential_obj and credential_obj.last_validated_at else None,
                    'usage_count': credential_obj.usage_count if credential_obj else 0,
                    'last_used_at': credential_obj.last_used_at.isoformat() if credential_obj and credential_obj.last_used_at else None,
                    'status_display': credential_obj.status_display if credential_obj else 'Not Set'
                }
                
                status['servers'].append(server_status)
            
            return status
            
        except Exception as e:
            logger.error(f"❌ Failed to get MCP credentials status for project {project.name}: {e}")
            return {
                'project_id': str(project.project_id),
                'project_name': project.name,
                'servers': [],
                'error': str(e)
            }


# Service instance
_service_instance = None

def get_mcp_server_credential_service() -> MCPServerCredentialService:
    """Get singleton service instance"""
    global _service_instance
    if _service_instance is None:
        _service_instance = MCPServerCredentialService()
    return _service_instance

