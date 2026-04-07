# backend/project_api_keys/services.py

import logging
import asyncio
from typing import Dict, Optional, List, Tuple
from django.core.exceptions import ObjectDoesNotExist
from django.utils import timezone
from asgiref.sync import sync_to_async

from users.models import IntelliDocProject, ProjectAPIKey, ProjectAPIKeyProvider
from .encryption import encryption_service
from .validators import APIKeyValidator

logger = logging.getLogger(__name__)

class ProjectAPIKeyService:
    """Service for managing project-specific API keys"""
    
    def __init__(self):
        self.encryption_service = encryption_service
        self.validator = APIKeyValidator()
        logger.info("🔑 PROJECT API KEY SERVICE: Initialized")
    
    def get_project_api_key(self, project: IntelliDocProject, provider_type: str) -> Optional[str]:
        """
        Get decrypted API key for a project and provider (sync version)
        
        Args:
            project: IntelliDocProject instance
            provider_type: Provider type (openai, google, anthropic)
            
        Returns:
            Decrypted API key or None if not found/inactive
        """
        # Type validation to prevent passing wrong object types
        if not isinstance(project, IntelliDocProject):
            error_msg = f"❌ Invalid project type: expected IntelliDocProject, got {type(project).__name__}"
            logger.error(error_msg)
            raise TypeError(error_msg)
        
        try:
            api_key_obj = ProjectAPIKey.objects.get(
                project=project,
                provider_type=provider_type,
                is_active=True
            )
            
            # Decrypt the key
            decrypted_key = self.encryption_service.decrypt_api_key(
                str(project.project_id),
                api_key_obj.encrypted_api_key
            )
            
            # Update usage tracking
            api_key_obj.usage_count += 1
            api_key_obj.last_used_at = timezone.now()
            api_key_obj.save(update_fields=['usage_count', 'last_used_at'])
            
            logger.info(f"🔑 Retrieved API key for project {project.name} - {provider_type}")
            return decrypted_key
            
        except ObjectDoesNotExist:
            logger.warning(f"⚠️ No active API key found for project {project.name} - {provider_type}")
            return None
        except TypeError:
            # Re-raise TypeError (type validation errors)
            raise
        except Exception as e:
            # Safe error logging - project is validated above, but be defensive
            project_name = getattr(project, 'name', f'<{type(project).__name__}>')
            logger.error(f"❌ Failed to retrieve API key for project {project_name} - {provider_type}: {e}")
            return None

    async def get_project_api_key_async(self, project: IntelliDocProject, provider_type: str) -> Optional[str]:
        """
        Get decrypted API key for a project and provider (async version)
        
        Args:
            project: IntelliDocProject instance
            provider_type: Provider type (openai, google, anthropic)
            
        Returns:
            Decrypted API key or None if not found/inactive
        """
        try:
            # Use sync_to_async to handle database operations in async context
            api_key_obj = await sync_to_async(ProjectAPIKey.objects.get)(
                project=project,
                provider_type=provider_type,
                is_active=True
            )
            
            # Decrypt the key
            decrypted_key = self.encryption_service.decrypt_api_key(
                str(project.project_id),
                api_key_obj.encrypted_api_key
            )
            
            # Update usage tracking
            api_key_obj.usage_count += 1
            api_key_obj.last_used_at = timezone.now()
            await sync_to_async(api_key_obj.save)(update_fields=['usage_count', 'last_used_at'])
            
            logger.info(f"🔑 Retrieved API key for project {project.name} - {provider_type}")
            return decrypted_key
            
        except ObjectDoesNotExist:
            logger.warning(f"⚠️ No active API key found for project {project.name} - {provider_type}")
            return None
        except Exception as e:
            logger.error(f"❌ Failed to retrieve API key for project {project.name} - {provider_type}: {e}")
            return None
    
    def set_project_api_key(
        self, 
        project: IntelliDocProject, 
        provider_type: str, 
        api_key: str,
        user,
        key_name: str = "",
        validate_key: bool = True
    ) -> Tuple[ProjectAPIKey, bool]:
        """
        Set or update API key for a project and provider
        
        Args:
            project: IntelliDocProject instance
            provider_type: Provider type (openai, google, anthropic)
            api_key: Plaintext API key
            user: User setting the key
            key_name: Optional descriptive name
            validate_key: Whether to validate the key with the provider
            
        Returns:
            Tuple of (ProjectAPIKey instance, created_boolean)
        """
        try:
            # Validate provider type
            if provider_type not in [choice[0] for choice in ProjectAPIKeyProvider.choices]:
                raise ValueError(f"Invalid provider type: {provider_type}")
            
            # Encrypt the API key
            encrypted_key = self.encryption_service.encrypt_api_key(
                str(project.project_id),
                api_key
            )
            
            # Get or create the API key record
            api_key_obj, created = ProjectAPIKey.objects.get_or_create(
                project=project,
                provider_type=provider_type,
                defaults={
                    'encrypted_api_key': encrypted_key,
                    'key_name': key_name,
                    'created_by': user,
                    'is_active': True,
                    'is_validated': False
                }
            )
            
            # Update existing key
            if not created:
                api_key_obj.encrypted_api_key = encrypted_key
                api_key_obj.key_name = key_name
                api_key_obj.is_active = True
                api_key_obj.is_validated = False
                api_key_obj.validation_error = ""
                api_key_obj.save()
                logger.info(f"🔄 Updated API key for project {project.name} - {provider_type}")
            else:
                logger.info(f"➕ Created new API key for project {project.name} - {provider_type}")
            
            # Validate the key if requested
            if validate_key:
                validation_result = self.validate_api_key(api_key_obj, api_key)
                if validation_result['is_valid']:
                    api_key_obj.is_validated = True
                    api_key_obj.last_validated_at = timezone.now()
                else:
                    api_key_obj.validation_error = validation_result['error']
                api_key_obj.save()
            
            return api_key_obj, created
            
        except Exception as e:
            logger.error(f"❌ Failed to set API key for project {project.name} - {provider_type}: {e}")
            raise ValueError(f"Failed to set API key: {e}")
    
    def validate_api_key(self, api_key_obj: ProjectAPIKey, plaintext_key: str = None) -> Dict:
        """Validate an API key with its provider"""
        try:
            if not plaintext_key:
                plaintext_key = self.encryption_service.decrypt_api_key(
                    str(api_key_obj.project.project_id),
                    api_key_obj.encrypted_api_key
                )
            
            logger.info(f"🔍 Validating {api_key_obj.provider_type} API key for project {api_key_obj.project.name}")
            
            # Use the validator to check the key
            is_valid, error_message = self.validator.validate_key(
                api_key_obj.provider_type,
                plaintext_key
            )
            
            result = {
                'is_valid': is_valid,
                'error': error_message or '',
                'validated_at': timezone.now().isoformat()
            }
            
            if is_valid:
                logger.info(f"✅ API key validation successful for {api_key_obj.provider_type}")
            else:
                logger.warning(f"❌ API key validation failed for {api_key_obj.provider_type}: {error_message}")
            
            return result
            
        except Exception as e:
            logger.error(f"❌ Error validating API key: {e}")
            return {
                'is_valid': False,
                'error': f"Validation error: {str(e)}",
                'validated_at': timezone.now().isoformat()
            }
    
    def get_project_api_keys(self, project: IntelliDocProject) -> Dict[str, ProjectAPIKey]:
        """Get all API keys for a project"""
        try:
            api_keys = ProjectAPIKey.objects.filter(
                project=project,
                is_active=True
            ).select_related('created_by')
            
            return {
                key.provider_type: key for key in api_keys
            }
            
        except Exception as e:
            logger.error(f"❌ Failed to get API keys for project {project.name}: {e}")
            return {}
    
    def delete_project_api_key(self, project: IntelliDocProject, provider_type: str) -> bool:
        """Delete API key for a project and provider"""
        try:
            ProjectAPIKey.objects.filter(
                project=project,
                provider_type=provider_type
            ).delete()
            
            logger.info(f"🗑️ Deleted API key for project {project.name} - {provider_type}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to delete API key for project {project.name} - {provider_type}: {e}")
            return False
    
    def get_available_providers(self) -> List[Dict]:
        """Get list of available API providers with their information"""
        providers = []
        
        for provider_code, provider_name in ProjectAPIKeyProvider.choices:
            # Get display info from the model method
            dummy_key = ProjectAPIKey(provider_type=provider_code)
            display_info = dummy_key.get_provider_display_info()
            
            providers.append({
                'code': provider_code,
                'name': provider_name,
                'display_name': display_info['name'],
                'description': display_info['description'],
                'icon': display_info['icon'],
                'color': display_info['color']
            })
        
        return providers
    
    def get_project_api_keys_status(self, project: IntelliDocProject) -> Dict:
        """Get comprehensive status of all API keys for a project"""
        try:
            api_keys = self.get_project_api_keys(project)
            available_providers = self.get_available_providers()
            
            status = {
                'project_id': str(project.project_id),
                'project_name': project.name,
                'providers': []
            }
            
            for provider in available_providers:
                provider_code = provider['code']
                api_key_obj = api_keys.get(provider_code)
                
                provider_status = {
                    **provider,
                    'has_key': api_key_obj is not None,
                    'is_active': api_key_obj.is_active if api_key_obj else False,
                    'is_validated': api_key_obj.is_validated if api_key_obj else False,
                    'validation_error': api_key_obj.validation_error if api_key_obj else '',
                    'last_validated_at': api_key_obj.last_validated_at.isoformat() if api_key_obj and api_key_obj.last_validated_at else None,
                    'usage_count': api_key_obj.usage_count if api_key_obj else 0,
                    'last_used_at': api_key_obj.last_used_at.isoformat() if api_key_obj and api_key_obj.last_used_at else None,
                    'masked_key': api_key_obj.masked_key if api_key_obj else None,
                    'status_display': api_key_obj.status_display if api_key_obj else 'Not Set'
                }
                
                status['providers'].append(provider_status)
            
            return status
            
        except Exception as e:
            logger.error(f"❌ Failed to get API keys status for project {project.name}: {e}")
            return {
                'project_id': str(project.project_id),
                'project_name': project.name,
                'providers': [],
                'error': str(e)
            }


# Service instance
_service_instance = None

def get_project_api_key_service() -> ProjectAPIKeyService:
    """Get singleton service instance"""
    global _service_instance
    if _service_instance is None:
        _service_instance = ProjectAPIKeyService()
    return _service_instance
