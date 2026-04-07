# backend/project_api_keys/integrations.py

"""
Service integrations for project-specific API keys.
This module provides helper functions to update existing services to use project-specific API keys.
"""

import logging
from typing import Optional, Dict, Any
from users.models import IntelliDocProject
from .services import get_project_api_key_service

logger = logging.getLogger(__name__)

class ProjectAPIKeyIntegration:
    """Integration helpers for using project-specific API keys in existing services"""
    
    def __init__(self):
        self.api_key_service = get_project_api_key_service()
        logger.info("🔧 PROJECT API KEY INTEGRATION: Initialized")
    
    def get_openai_client_for_project(self, project: IntelliDocProject):
        """
        Get configured OpenAI client for a project
        
        Args:
            project: IntelliDocProject instance
            
        Returns:
            OpenAI client instance or None if no key is configured
        """
        # Type validation to prevent passing wrong object types
        if not isinstance(project, IntelliDocProject):
            error_msg = f"❌ Invalid project type: expected IntelliDocProject, got {type(project).__name__}"
            logger.error(error_msg)
            raise TypeError(error_msg)
        
        try:
            api_key = self.api_key_service.get_project_api_key(project, 'openai')
            if not api_key:
                logger.warning(f"⚠️ No OpenAI API key configured for project {project.name}")
                return None
            
            # Import OpenAI here to avoid circular imports
            import openai
            
            client = openai.OpenAI(api_key=api_key)
            logger.info(f"✅ OpenAI client configured for project {project.name}")
            return client
            
        except TypeError:
            # Re-raise TypeError (type validation errors)
            raise
        except Exception as e:
            # Safe error logging - check if project has name attribute
            project_name = getattr(project, 'name', f'<{type(project).__name__}>')
            logger.error(f"❌ Failed to create OpenAI client for project {project_name}: {e}")
            return None
    
    def get_google_client_config_for_project(self, project: IntelliDocProject) -> Optional[Dict[str, Any]]:
        """
        Get Google/Gemini API configuration for a project
        
        Args:
            project: IntelliDocProject instance
            
        Returns:
            Dictionary with API configuration or None if no key is configured
        """
        try:
            api_key = self.api_key_service.get_project_api_key(project, 'google')
            if not api_key:
                logger.warning(f"⚠️ No Google API key configured for project {project.name}")
                return None
            
            config = {
                'api_key': api_key,
                'base_url': 'https://generativelanguage.googleapis.com',
                'model': 'gemini-1.5-flash'
            }
            
            logger.info(f"✅ Google API config prepared for project {project.name}")
            return config
            
        except Exception as e:
            logger.error(f"❌ Failed to get Google API config for project {project.name}: {e}")
            return None
    
    def get_anthropic_client_config_for_project(self, project: IntelliDocProject) -> Optional[Dict[str, Any]]:
        """
        Get Anthropic/Claude API configuration for a project
        
        Args:
            project: IntelliDocProject instance
            
        Returns:
            Dictionary with API configuration or None if no key is configured
        """
        try:
            api_key = self.api_key_service.get_project_api_key(project, 'anthropic')
            if not api_key:
                logger.warning(f"⚠️ No Anthropic API key configured for project {project.name}")
                return None
            
            config = {
                'api_key': api_key,
                'base_url': 'https://api.anthropic.com',
                'model': 'claude-3-haiku-20240307'
            }
            
            logger.info(f"✅ Anthropic API config prepared for project {project.name}")
            return config
            
        except Exception as e:
            logger.error(f"❌ Failed to get Anthropic API config for project {project.name}: {e}")
            return None
    
    def get_available_providers_for_project(self, project: IntelliDocProject) -> Dict[str, bool]:
        """
        Get list of available API providers for a project
        
        Args:
            project: IntelliDocProject instance
            
        Returns:
            Dictionary mapping provider names to availability status
        """
        try:
            project_keys = self.api_key_service.get_project_api_keys(project)
            
            availability = {
                'openai': 'openai' in project_keys and project_keys['openai'].is_active,
                'google': 'google' in project_keys and project_keys['google'].is_active,
                'anthropic': 'anthropic' in project_keys and project_keys['anthropic'].is_active
            }
            
            logger.info(f"🔍 Provider availability for project {project.name}: {availability}")
            return availability
            
        except Exception as e:
            logger.error(f"❌ Failed to get provider availability for project {project.name}: {e}")
            return {'openai': False, 'google': False, 'anthropic': False}
    
    def validate_project_has_provider(self, project: IntelliDocProject, provider_type: str) -> bool:
        """
        Check if a project has a specific provider configured
        
        Args:
            project: IntelliDocProject instance
            provider_type: Provider to check (openai, google, anthropic)
            
        Returns:
            True if provider is configured and active, False otherwise
        """
        try:
            api_key = self.api_key_service.get_project_api_key(project, provider_type)
            has_provider = api_key is not None
            
            if has_provider:
                logger.info(f"✅ Project {project.name} has {provider_type} configured")
            else:
                logger.warning(f"⚠️ Project {project.name} does not have {provider_type} configured")
            
            return has_provider
            
        except Exception as e:
            logger.error(f"❌ Error checking {provider_type} for project {project.name}: {e}")
            return False
    
    def get_fallback_message(self, project: IntelliDocProject, provider_type: str) -> str:
        """
        Get appropriate fallback message when API key is not configured
        
        Args:
            project: IntelliDocProject instance
            provider_type: Provider that's missing
            
        Returns:
            User-friendly error message
        """
        provider_names = {
            'openai': 'OpenAI',
            'google': 'Google (Gemini)',
            'anthropic': 'Anthropic (Claude)'
        }
        
        provider_name = provider_names.get(provider_type, provider_type)
        
        return (
            f"❌ {provider_name} API key not configured for project '{project.name}'. "
            f"Please add your {provider_name} API key in the project's API Management settings to use this feature."
        )


# Singleton instance
_integration_instance = None

def get_project_api_key_integration() -> ProjectAPIKeyIntegration:
    """Get singleton integration instance"""
    global _integration_instance
    if _integration_instance is None:
        _integration_instance = ProjectAPIKeyIntegration()
    return _integration_instance
