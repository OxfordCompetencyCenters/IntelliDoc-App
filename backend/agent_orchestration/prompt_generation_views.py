"""
Prompt Generation API Views

REST API endpoints for generating system prompts from agent descriptions
"""

import logging
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from asgiref.sync import sync_to_async, async_to_sync

from users.models import IntelliDocProject
from .prompt_generation_service import get_prompt_generation_service

logger = logging.getLogger('agent_orchestration.prompt_generation')


class PromptGenerationViewSet(viewsets.ViewSet):
    """
    API endpoints for generating system prompts from agent descriptions
    """
    permission_classes = [IsAuthenticated]
    
    @action(detail=False, methods=['post'], url_path='generate')
    def generate(self, request):
        """
        Generate a system prompt from an agent description
        
        Request body:
        {
            "description": "A research assistant that helps users find information in documents",
            "agent_type": "AssistantAgent",
            "doc_aware": false,
            "project_id": "uuid-string",
            "llm_provider": "openai",
            "llm_model": "gpt-4"
        }
        
        Response:
        {
            "success": true,
            "generated_prompt": "...",
            "metadata": {...},
            "error": null
        }
        """
        try:
            # Extract request data
            description = request.data.get('description', '').strip()
            agent_type = request.data.get('agent_type', 'AssistantAgent')
            doc_aware = request.data.get('doc_aware', False)
            project_id = request.data.get('project_id')
            llm_provider = request.data.get('llm_provider', 'openai')
            llm_model = request.data.get('llm_model', 'gpt-4')
            
            # Validate required fields
            if not description:
                return Response(
                    {'success': False, 'error': 'Description is required'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            if len(description) < 10:
                return Response(
                    {'success': False, 'error': 'Description must be at least 10 characters'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            if len(description) > 10000:
                return Response(
                    {'success': False, 'error': 'Description must be less than 10,000 characters'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Get project if provided
            project = None
            project_capabilities = {}
            if project_id:
                try:
                    project = get_object_or_404(IntelliDocProject, project_id=project_id)
                    
                    # Check user access
                    if not project.has_user_access(request.user):
                        return Response(
                            {'success': False, 'error': 'You do not have access to this project'},
                            status=status.HTTP_403_FORBIDDEN
                        )
                    
                    # Get project capabilities
                    project_capabilities = project.processing_capabilities or {}
                    logger.info(f"📊 PROMPT GEN API: Using project {project.name} capabilities")
                except Exception as e:
                    logger.warning(f"⚠️ PROMPT GEN API: Could not load project {project_id}: {e}")
                    # Continue without project context
            
            # Get prompt generation service
            service = get_prompt_generation_service()
            
            # Generate prompt (async call wrapped in sync_to_async)
            logger.info(f"🔧 PROMPT GEN API: Generating prompt for {agent_type} (user: {request.user.email})")
            result = async_to_sync(service.generate_prompt_from_description)(
                description=description,
                agent_type=agent_type,
                doc_aware=doc_aware,
                project=project,
                llm_provider=llm_provider,
                llm_model=llm_model,
                project_capabilities=project_capabilities
            )
            
            if result['success']:
                return Response(result, status=status.HTTP_200_OK)
            else:
                return Response(result, status=status.HTTP_400_BAD_REQUEST)
                
        except Exception as e:
            logger.error(f"❌ PROMPT GEN API: Error generating prompt: {e}")
            import traceback
            logger.error(f"❌ PROMPT GEN API: Traceback: {traceback.format_exc()}")
            return Response(
                {
                    'success': False,
                    'error': f'Failed to generate prompt: {str(e)}',
                    'generated_prompt': None
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

