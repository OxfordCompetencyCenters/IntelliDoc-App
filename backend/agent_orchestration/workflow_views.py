# backend/agent_orchestration/workflow_views.py

from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.core.files.storage import default_storage
from asgiref.sync import sync_to_async, async_to_sync
from typing import List, Dict, Any
from types import SimpleNamespace
import logging
import mimetypes
import os
import uuid

from users.models import (
    IntelliDocProject, AgentWorkflow, AgentWorkflowStatus,
    WorkflowEvaluation, WorkflowEvaluationResult, EvaluationStatus
)
from .serializers import AgentWorkflowSerializer, AgentWorkflowCreateSerializer
from .workflow_evaluator import WorkflowEvaluator
from .conversation_orchestrator import ConversationOrchestrator

logger = logging.getLogger(__name__)

class AgentWorkflowViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing agent workflows within projects
    """
    serializer_class = AgentWorkflowSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = 'workflow_id'
    
    def get_queryset(self):
        """Filter workflows by project permissions (not just creator)"""
        project_id = self.kwargs.get('project_id')
        if project_id:
            try:
                # FIX: Get project without created_by restriction
                project = get_object_or_404(IntelliDocProject, project_id=project_id)
                
                # FIX: Check if user has access to this project using project permission system
                if not project.has_user_access(self.request.user):
                    logger.warning(f"🚫 WORKFLOW ACCESS: User {self.request.user.email} denied access to project {project.name}")
                    return AgentWorkflow.objects.none()
                
                # FIX: Return ALL workflows in the accessible project (not just created_by user)
                workflows = AgentWorkflow.objects.filter(project=project)
                logger.info(f"✅ WORKFLOW ACCESS: User {self.request.user.email} can access {workflows.count()} workflows in project {project.name}")
                return workflows
                
            except Exception as e:
                logger.error(f"❌ WORKFLOW QUERYSET: Error filtering workflows: {e}")
                return AgentWorkflow.objects.none()
        
        # FIX: For no specific project, show workflows from ALL accessible projects
        accessible_projects = []
        all_projects = IntelliDocProject.objects.all()
        
        for project in all_projects:
            if project.has_user_access(self.request.user):
                accessible_projects.append(project.id)
        
        workflows = AgentWorkflow.objects.filter(project__id__in=accessible_projects)
        logger.info(f"✅ WORKFLOW ACCESS: User {self.request.user.email} can access {workflows.count()} workflows across {len(accessible_projects)} projects")
        return workflows
    
    def get_serializer_class(self):
        """Use different serializer for creation"""
        if self.action == 'create':
            return AgentWorkflowCreateSerializer
        return AgentWorkflowSerializer
    
    def create(self, request, *args, **kwargs):
        """Create a new workflow for a specific project"""
        project_id = kwargs.get('project_id')
        project = get_object_or_404(IntelliDocProject, project_id=project_id)
        
        # FIX: Ensure user has access to the project using project permission system
        if not project.has_user_access(request.user):
            logger.warning(f"🚫 WORKFLOW CREATE: User {request.user.email} denied workflow creation access to project {project.name}")
            return Response(
                {'error': 'You do not have permission to create workflows in this project'}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # Create workflow with project and user
        workflow = serializer.save(
            project=project,
            created_by=request.user
        )
        
        logger.info(f"🆕 WORKFLOW CREATED: {workflow.workflow_id} for project {project.project_id} by {request.user.email}")
        
        response_serializer = AgentWorkflowSerializer(workflow)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)
    
    def update(self, request, *args, **kwargs):
        """Update workflow with logging"""
        workflow = self.get_object()
        
        logger.info(f"📝 WORKFLOW UPDATE: {workflow.workflow_id} by {request.user.email}")
        
        # Update the timestamp
        workflow.updated_at = timezone.now()
        
        return super().update(request, *args, **kwargs)
    
    def partial_update(self, request, *args, **kwargs):
        """Partial update workflow with logging"""
        workflow = self.get_object()

        logger.info(f"📝 WORKFLOW PARTIAL UPDATE: {workflow.workflow_id} by {request.user.email}")

        # Update the timestamp
        workflow.updated_at = timezone.now()

        response = super().partial_update(request, *args, **kwargs)

        # Cleanup orphaned URL summaries: delete rows whose URL is no longer
        # referenced in any node of any workflow in this project.
        try:
            from users.models import WebSearchUrlSummary
            all_workflows = AgentWorkflow.objects.filter(project=workflow.project)
            active_urls: set = set()
            for wf in all_workflows:
                graph = wf.graph_json or {}
                for node in (graph.get('nodes') or []):
                    data = node.get('data') or {}
                    if data.get('web_search_mode') == 'urls':
                        active_urls.update(u for u in (data.get('web_search_urls') or []) if u)
            deleted_count, _ = WebSearchUrlSummary.objects.filter(
                project=workflow.project
            ).exclude(url__in=active_urls).delete()
            if deleted_count:
                logger.info(
                    f"🗑️ URL SUMMARY CLEANUP: Deleted {deleted_count} orphaned summaries "
                    f"for project {workflow.project.project_id}"
                )
        except Exception as cleanup_err:
            logger.warning(f"⚠️ URL SUMMARY CLEANUP: {cleanup_err}")

        return response
    
    def destroy(self, request, *args, **kwargs):
        """Delete workflow with logging"""
        workflow = self.get_object()
        
        logger.info(f"🗑️ WORKFLOW DELETE: {workflow.workflow_id} by {request.user.email}")
        
        return super().destroy(request, *args, **kwargs)
    
    @action(
        detail=True,
        methods=['post'],
        url_path=r'nodes/(?P<node_id>[^/.]+)/upload-file-attachment',
        parser_classes=[MultiPartParser, FormParser],
    )
    def upload_file_attachment(self, request, project_id=None, workflow_id=None, node_id=None):
        """
        Upload a node-scoped file attachment and immediately upload it to the
        selected LLM provider's File API.
        
        This does NOT create a ProjectDocument entry. The returned file_id is
        meant to be stored in the workflow graph (nodeConfig.inline_file_attachments).
        """
        workflow = self.get_object()
        project = workflow.project

        upload = request.FILES.get('file')
        provider = (request.data.get('provider') or '').lower() or 'openai'

        if not upload:
            return Response(
                {'error': 'No file provided', 'reason': 'missing_file'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        valid_providers = {'openai', 'anthropic', 'google', 'gemini'}
        if provider not in valid_providers:
            return Response(
                {'error': f'Unsupported provider: {provider}', 'reason': 'unsupported_provider'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Map gemini alias to google for the file service
        file_service_provider = 'google' if provider == 'gemini' else provider

        # Save file to temporary storage so LLMFileUploadService can read it
        filename = upload.name
        ext = os.path.splitext(filename)[1].lower()
        mime_type = mimetypes.guess_type(filename)[0] or 'application/octet-stream'

        storage_path = default_storage.save(
            os.path.join(
                'node_attachments',
                str(project.project_id),
                str(workflow.workflow_id),
                node_id or 'unknown-node',
                f'{uuid.uuid4().hex}_{filename}',
            ),
            upload,
        )

        file_size = upload.size

        # Build a lightweight document-like object for validation/upload
        pseudo_document = SimpleNamespace(
            file_path=storage_path,
            file_size=file_size,
            file_extension=ext,
            file_type=mime_type,
            original_filename=filename,
            document_id=None,
        )

        try:
            from agent_orchestration.llm_file_service import LLMFileUploadService

            service = LLMFileUploadService(project)
            result = async_to_sync(service._upload_to_provider)(pseudo_document, file_service_provider)

            if not result.get('file_id'):
                # Clean up stored file if upload failed
                try:
                    if default_storage.exists(storage_path):
                        default_storage.delete(storage_path)
                except Exception:
                    logger.debug("Failed to delete temp node attachment after upload failure")

                return Response(
                    {
                        'error': result.get('error', 'Upload failed'),
                        'reason': result.get('reason'),
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # We can safely delete the temp file after successful provider upload
            try:
                if default_storage.exists(storage_path):
                    default_storage.delete(storage_path)
            except Exception:
                logger.debug("Failed to delete temp node attachment after successful upload")

            attachment_id = str(uuid.uuid4())
            payload = {
                'id': attachment_id,
                'filename': filename,
                'provider': provider,
                'file_id': result['file_id'],
                'size': file_size,
                'mime_type': mime_type,
                'uploaded_at': timezone.now().isoformat(),
            }

            logger.info(
                f"📎 NODE ATTACHMENT: Uploaded file for workflow {workflow.workflow_id}, "
                f"node {node_id}, provider {provider}: {filename}"
            )

            return Response(payload, status=status.HTTP_201_CREATED)

        except Exception as e:
            logger.error(f"❌ NODE ATTACHMENT: Error uploading file for workflow {workflow_id}, node {node_id}: {e}")
            import traceback
            logger.error(f"❌ NODE ATTACHMENT TRACEBACK: {traceback.format_exc()}")

            # Attempt to clean up stored file
            try:
                if default_storage.exists(storage_path):
                    default_storage.delete(storage_path)
            except Exception:
                logger.debug("Failed to delete temp node attachment after exception")

            return Response(
                {'error': 'Upload failed', 'detail': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
    
    @action(detail=True, methods=['post'])
    def execute(self, request, project_id=None, workflow_id=None):
        """
        Execute a workflow with REAL orchestration and human input support
        """
        workflow = self.get_object()
        
        logger.info(f"🚀 WORKFLOW EXECUTE: {workflow.workflow_id} by {request.user.email}")
        
        try:
            # Import here to avoid circular imports
            from .conversation_orchestrator import ConversationOrchestrator
            import asyncio
            
            # Create orchestrator and execute workflow
            orchestrator = ConversationOrchestrator()
            
            async def run_workflow():
                return await orchestrator.execute_workflow(workflow, request.user)
            
            result = asyncio.run(run_workflow())
            
            # Check if workflow is paused for human input
            if result.get('status') == 'awaiting_human_input':
                logger.info(f"⏸️ WORKFLOW PAUSED: {workflow.workflow_id} awaiting human input")
                return Response({
                    'status': 'paused',
                    'message': result.get('message'),
                    'execution_id': result.get('execution_id'),
                    'human_input_required': True,
                    'agent_name': result.get('agent_name'),
                    'agent_id': result.get('agent_id'),
                    'input_context': result.get('input_context'),
                    'conversation_history': result.get('conversation_history')
                })
            
            # Normal completion
            logger.info(f"✅ WORKFLOW COMPLETE: {workflow.workflow_id}")
            return Response({
                'status': 'success',
                'message': 'Workflow executed successfully',
                'workflow_id': str(workflow.workflow_id),
                'execution_id': result.get('execution_id'),  # CRITICAL: Include at top level for frontend monitoring
                'result': result
            })
            
        except Exception as error:
            from .docaware_handler import FileAttachmentPreparationError
            if isinstance(error, FileAttachmentPreparationError):
                user_message = f"File attachments could not be prepared: {error.message}"
                if getattr(error, 'missing_documents', None):
                    user_message += f" Missing or not uploaded for provider: {', '.join(error.missing_documents)}."
                logger.error(f"❌ WORKFLOW ERROR (file attachments): {workflow.workflow_id} - {error.message}")
                return Response({
                    'status': 'error',
                    'message': user_message,
                    'workflow_id': str(workflow.workflow_id)
                }, status=400)
            logger.error(f"❌ WORKFLOW ERROR: {workflow.workflow_id} - {error}")
            import traceback
            logger.error(f"❌ WORKFLOW TRACEBACK: {traceback.format_exc()}")
            return Response({
                'status': 'error',
                'message': f'Execution failed: {str(error)}',
                'workflow_id': str(workflow.workflow_id)
            }, status=500)
    
    @action(detail=False, methods=['post'])
    def stop(self, request, project_id=None):
        """
        Emergency stop for workflow execution
        """
        try:
            execution_id = request.data.get('execution_id')
            if not execution_id:
                return Response({
                    'status': 'error',
                    'message': 'execution_id is required'
                }, status=400)
            
            logger.info(f"🛑 STOP: Emergency stop requested for execution {execution_id}")
            
            # Import here to avoid circular imports
            from users.models import WorkflowExecutionMessage
            from .conversation_orchestrator import ConversationOrchestrator
            
            # Find the execution record
            try:
                execution_record = WorkflowExecutionMessage.objects.get(execution_id=execution_id)
                logger.info(f"🛑 STOP: Found execution record for {execution_id}")
            except WorkflowExecutionMessage.DoesNotExist:
                logger.warning(f"🛑 STOP: Execution record not found for {execution_id}")
                return Response({
                    'status': 'error',
                    'message': f'Execution {execution_id} not found'
                }, status=404)
            
            # Stop the execution by updating its status
            execution_record.status = 'stopped'
            execution_record.human_input_required = False
            execution_record.awaiting_human_input_agent = ""
            execution_record.human_input_context = {}
            execution_record.end_time = timezone.now()
            execution_record.save()
            
            logger.info(f"🛑 STOP: Execution {execution_id} marked as stopped")
            
            # Clear any pending human inputs for this execution
            from agent_orchestration.human_input_views import clear_pending_inputs_for_execution
            clear_pending_inputs_for_execution(execution_id)
            
            return Response({
                'status': 'success',
                'message': f'Execution {execution_id} stopped successfully',
                'execution_id': execution_id
            })
            
        except Exception as error:
            logger.error(f"❌ STOP: Failed to stop execution: {error}")
            return Response({
                'status': 'error',
                'message': f'Failed to stop execution: {str(error)}'
            }, status=500)
    
    @action(detail=True, methods=['get'])
    def history(self, request, project_id=None, workflow_id=None):
        """
        Get execution history for a workflow using WorkflowExecution model
        """
        from users.models import WorkflowExecution
        
        workflow = self.get_object()
        
        logger.info(f"📊 WORKFLOW HISTORY: Loading history for {workflow.workflow_id}")
        
        try:
            # Get total count first (before slicing)
            all_executions = WorkflowExecution.objects.filter(workflow=workflow)
            total_executions = all_executions.count()
            successful_executions = all_executions.filter(status='completed').count()
            
            # Get recent executions (last 20)
            recent_executions_qs = all_executions.order_by('-start_time')[:20]
            
            logger.info(f"📊 WORKFLOW HISTORY: Found {total_executions} total executions, showing recent {len(recent_executions_qs)}")
            
            # Calculate success rate
            success_rate = (successful_executions / total_executions * 100) if total_executions > 0 else 0
            
            # Build execution data
            recent_executions = []
            for execution in recent_executions_qs:
                execution_data = {
                    'execution_id': str(execution.execution_id),
                    'status': execution.status,
                    'start_time': execution.start_time,
                    'end_time': execution.end_time,
                    'duration_seconds': execution.duration_seconds,
                    'total_messages': execution.total_messages or 0,
                    'total_agents_involved': execution.total_agents_involved or 0,
                    'providers_used': execution.providers_used or [],
                    'error_message': execution.error_message,
                    'human_input_required': execution.human_input_required or False,
                    'conversation_history': execution.conversation_history or ''
                }
                recent_executions.append(execution_data)
                
            logger.info(f"✅ WORKFLOW HISTORY: Returning {len(recent_executions)} executions")
            
            return Response({
                'workflow_id': str(workflow.workflow_id),
                'total_executions': total_executions,
                'successful_executions': successful_executions,
                'success_rate': round(success_rate, 2),
                'last_executed_at': workflow.last_executed_at,
                'recent_executions': recent_executions
            })
            
        except Exception as e:
            logger.error(f"❌ WORKFLOW HISTORY: Error loading history: {e}")
            import traceback
            logger.error(f"❌ WORKFLOW HISTORY TRACEBACK: {traceback.format_exc()}")
            
            return Response({
                'error': f'Failed to load workflow history: {str(e)}',
                'workflow_id': str(workflow.workflow_id)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['get'])
    def conversation(self, request, project_id=None, workflow_id=None):
        """
        Get conversation history for a specific workflow execution
        """
        from users.models import WorkflowExecution, WorkflowExecutionMessage
        
        workflow = self.get_object()
        execution_id = request.query_params.get('execution_id')
        
        if not execution_id:
            return Response({
                'error': 'execution_id parameter is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        logger.info(f"💬 CONVERSATION: Loading conversation for execution {execution_id[:8]}")
        
        try:
            # Get the specific execution
            execution = WorkflowExecution.objects.get(
                execution_id=execution_id,
                workflow=workflow
            )
            
            # ROOT CAUSE FIX: Use ONLY messages_data as single source of truth
            # Do NOT parse conversation_history as it creates duplicates
            logger.info(f"💬 CONVERSATION: Using messages_data as single source of truth")
            
            conversation_messages = []
            messages_from_data = execution.messages_data or []
            logger.info(f"💬 ENHANCED PARSER: Found {len(messages_from_data)} messages in messages_data JSON field")
            
            # ROOT CAUSE FIX: Directly use messages_data without complex duplicate detection
            # Since we're using single source, duplicates shouldn't exist
            for message_data in messages_from_data:
                # Convert timestamp to proper format if needed
                timestamp = message_data.get('timestamp')
                if timestamp is None:
                    timestamp = timezone.now()
                elif isinstance(timestamp, str):
                    try:
                        from datetime import datetime
                        timestamp = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                    except:
                        timestamp = timezone.now()
                # If it's already a datetime, keep it as is
                
                formatted_message = {
                    'sequence': message_data.get('sequence', 0),
                    'agent_name': message_data.get('agent_name', ''),
                    'agent_type': message_data.get('agent_type', 'Unknown'),
                    'content': message_data.get('content', ''),
                    'message_type': message_data.get('message_type', 'chat'),
                    'timestamp': timestamp,
                    'response_time_ms': message_data.get('response_time_ms', 0),
                    'token_count': message_data.get('token_count'),
                    'metadata': message_data.get('metadata', {})
                }
                conversation_messages.append(formatted_message)
                logger.debug(f"💬 CLEAN SOURCE: Added message: {formatted_message['agent_name']} - {formatted_message['content'][:50]}...")
            
            logger.info(f"💬 CLEAN SOURCE: Loaded {len(conversation_messages)} messages from single source (no duplicates)")
            
            # Sort all messages chronologically by timestamp, then by sequence as secondary sort
            # Handle None timestamps explicitly to avoid comparison errors
            conversation_messages.sort(key=lambda x: (
                x.get('timestamp') or timezone.now(),  # Handle None explicitly
                x.get('sequence', 0)
            ))
            
            logger.info(f"💬 CONVERSATION: Found {len(conversation_messages)} total messages in chronological order")
            
            # Clean logging for single source approach
            agent_names = [msg.get('agent_name', 'Unknown') for msg in conversation_messages]
            unique_agent_names = set(agent_names)
            logger.info(f"💬 CLEAN SOURCE: Agent types found: {unique_agent_names}")
            
            for msg in conversation_messages:
                agent_name = msg.get('agent_name', 'Unknown')
                content_preview = msg.get('content', '')[:50] + ('...' if len(msg.get('content', '')) > 50 else '')
                logger.debug(f"💬 CLEAN SOURCE: Final message - {agent_name}: {content_preview}")
            
            # Re-sequence messages to ensure proper chronological order for frontend
            for i, msg in enumerate(conversation_messages):
                msg['sequence'] = i
            
            logger.info(f"✅ CONVERSATION: Returning {len(conversation_messages)} messages from single clean source")
            
            return Response({
                'execution_id': execution_id,
                'workflow_id': str(workflow.workflow_id),
                'execution_status': execution.status,
                'total_messages': len(conversation_messages),
                'conversation_history': execution.conversation_history,
                'messages': conversation_messages
            })
            
        except WorkflowExecution.DoesNotExist:
            logger.error(f"❌ CONVERSATION: Execution {execution_id[:8]} not found")
            return Response({
                'error': f'Execution {execution_id} not found for this workflow'
            }, status=status.HTTP_404_NOT_FOUND)
        
        except Exception as e:
            logger.error(f"❌ CONVERSATION: Error loading conversation: {e}")
            return Response({
                'error': f'Failed to load conversation: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def parse_conversation_history(self, conversation_history: str, start_time) -> List[Dict[str, Any]]:
        """
        Enhanced conversation history parser for multi-agent orchestration
        Properly captures GroupChatManager, DelegateAgent interactions, and full conversation flow
        """
        if not conversation_history or not conversation_history.strip():
            return []
        
        messages = []
        lines = conversation_history.strip().split('\n')
        sequence = 0
        
        # Calculate time intervals for realistic chronological timestamps
        from datetime import timedelta
        current_time = start_time
        message_interval = timedelta(seconds=5)
        
        logger.info(f"💬 ENHANCED PARSER: Processing {len(lines)} lines of conversation history")
        
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            
            if not line:
                i += 1
                continue
            
            # Enhanced parsing for different conversation patterns
            message_data = None
            
            # Pattern 1: Basic "Agent Name: message" format
            if ':' in line and not line.startswith('===') and not line.startswith('---'):
                parts = line.split(':', 1)
                if len(parts) == 2:
                    agent_name = parts[0].strip()
                    content = parts[1].strip()
                    
                    # Look ahead for multi-line content
                    full_content = [content]
                    j = i + 1
                    consecutive_empty_lines = 0
                    while j < len(lines):
                        next_line = lines[j].strip()
                        
                        # Stop if we hit another agent message (agent name followed by colon)
                        if ':' in next_line and any(agent_type in next_line.lower() for agent_type in ['agent', 'assistant', 'manager', 'delegate', 'start', 'end', 'proxy', 'node']):
                            break
                        
                        # Handle empty lines: allow single empty line within message, but stop on multiple consecutive empty lines
                        if not next_line:
                            consecutive_empty_lines += 1
                            if consecutive_empty_lines >= 2:  # Two consecutive empty lines indicate end of message
                                break
                            # Add empty line to preserve formatting
                            full_content.append('')
                        else:
                            consecutive_empty_lines = 0  # Reset counter when we find content
                            full_content.append(next_line)
                        
                        j += 1
                    
                    # Update the index to skip processed lines
                    i = j - 1
                    content = '\n'.join(full_content)
                    
                    agent_type = self.determine_agent_type_enhanced(agent_name, content)
                    response_time = max(1000, len(content) * 30)  # More realistic timing
                    
                    message_data = {
                        'sequence': sequence,
                        'agent_name': agent_name,
                        'agent_type': agent_type,
                        'content': content,
                        'message_type': self.determine_message_type(agent_name, content),
                        'timestamp': current_time,
                        'response_time_ms': response_time,
                        'token_count': len(content.split()) if content else None,
                        'metadata': {
                            'parsed_from_history': True,
                            'estimated_timestamp': True,
                            'multi_line_content': len(full_content) > 1
                        }
                    }
                    
            # Pattern 2: GroupChatManager Summary format
            elif 'GroupChatManager' in line and 'Summary' in line:
                # Extract GroupChatManager name and summary content
                agent_name = 'GroupChatManager'
                if '(' in line:
                    # Extract iterations info
                    iterations_info = line[line.find('('):line.find(')')+1]
                    agent_name = f"GroupChatManager {iterations_info}"
                
                # Collect the full summary including delegate details
                summary_content = [line]
                j = i + 1
                while j < len(lines) and j < i + 20:  # Limit lookahead
                    next_line = lines[j].strip()
                    if next_line and not (':' in next_line and any(keyword in next_line.lower() for keyword in ['agent', 'start', 'end'])):
                        summary_content.append(next_line)
                    else:
                        break
                    j += 1
                
                i = j - 1
                content = '\n'.join(summary_content)
                
                message_data = {
                    'sequence': sequence,
                    'agent_name': agent_name,
                    'agent_type': 'GroupChatManager',
                    'content': content,
                    'message_type': 'orchestration_summary',
                    'timestamp': current_time,
                    'response_time_ms': 2000,  # Summaries take longer
                    'token_count': len(content.split()),
                    'metadata': {
                        'parsed_from_history': True,
                        'estimated_timestamp': True,
                        'is_orchestration_summary': True
                    }
                }
                
            # Pattern 3: Delegate conversation logs (embedded in GroupChatManager output)
            elif line.startswith('[Round ') and ']' in line:
                # Extract delegate round information
                parts = line.split(']', 1)
                if len(parts) == 2:
                    round_info = parts[0] + ']'
                    delegate_content = parts[1].strip()
                    
                    # Extract delegate name if present
                    delegate_name = 'Delegate'
                    if ':' in delegate_content:
                        name_parts = delegate_content.split(':', 1)
                        delegate_name = name_parts[0].strip()
                        delegate_content = name_parts[1].strip()
                    
                    message_data = {
                        'sequence': sequence,
                        'agent_name': f"{delegate_name} {round_info}",
                        'agent_type': 'DelegateAgent',
                        'content': delegate_content,
                        'message_type': 'delegate_response',
                        'timestamp': current_time,
                        'response_time_ms': max(1000, len(delegate_content) * 40),
                        'token_count': len(delegate_content.split()),
                        'metadata': {
                            'parsed_from_history': True,
                            'estimated_timestamp': True,
                            'is_delegate_round': True,
                            'round_info': round_info
                        }
                    }
                    
            # Pattern 4: System messages and other content
            else:
                if line and not line.startswith('=') and not line.startswith('-'):
                    message_data = {
                        'sequence': sequence,
                        'agent_name': 'System',
                        'agent_type': 'system',
                        'content': line,
                        'message_type': 'system',
                        'timestamp': current_time,
                        'response_time_ms': 0,
                        'token_count': None,
                        'metadata': {
                            'parsed_from_history': True,
                            'estimated_timestamp': True,
                            'system_message': True
                        }
                    }
            
            # Add message if we created one
            if message_data:
                messages.append(message_data)
                sequence += 1
                current_time += message_interval
                
                # Log the parsed message for debugging
                logger.debug(f"💬 ENHANCED PARSER: [{sequence}] {message_data['agent_name']} ({message_data['agent_type']}): {message_data['content'][:100]}...")
            
            i += 1
        
        logger.info(f"💬 ENHANCED PARSER: Parsed {len(messages)} messages from multi-agent orchestration")
        logger.info(f"💬 ENHANCED PARSER: Agent types found: {set(msg['agent_type'] for msg in messages)}")
        
        return messages
    
    def determine_agent_type_enhanced(self, agent_name: str, content: str) -> str:
        """
        Enhanced agent type determination with content analysis
        """
        name_lower = agent_name.lower()
        content_lower = content.lower() if content else ""
        
        # Check for specific agent type indicators
        if 'start' in name_lower or 'start node' in name_lower:
            return 'StartNode'
        elif 'end' in name_lower or 'end node' in name_lower:
            return 'EndNode'
        elif 'user' in name_lower or 'proxy' in name_lower:
            return 'UserProxyAgent'
        elif 'chat manager' in name_lower or 'groupchatmanager' in name_lower or 'manager' in name_lower:
            return 'GroupChatManager'
        elif 'delegate' in name_lower or '[round' in content_lower:
            return 'DelegateAgent'
        elif 'assistant' in name_lower:
            return 'AssistantAgent'
        
        # Content-based detection
        if 'delegate' in content_lower and 'summary' in content_lower:
            return 'GroupChatManager'
        elif 'processed' in content_lower and 'iterations' in content_lower:
            return 'GroupChatManager'
        elif any(keyword in content_lower for keyword in ['round 1', 'round 2', 'round 3']):
            return 'DelegateAgent'
        
        return 'AssistantAgent'  # Default
    
    def determine_message_type(self, agent_name: str, content: str) -> str:
        """
        Determine the type of message based on agent and content
        """
        name_lower = agent_name.lower()
        content_lower = content.lower() if content else ""
        
        if 'start' in name_lower:
            return 'workflow_start'
        elif 'end' in name_lower:
            return 'workflow_end'
        elif 'summary' in content_lower and 'delegate' in content_lower:
            return 'orchestration_summary'
        elif '[round' in content_lower or 'delegate' in name_lower:
            return 'delegate_response'
        elif 'user' in name_lower or 'proxy' in name_lower:
            return 'user_input'
        else:
            return 'agent_response'
    
    @action(detail=True, methods=['post'])
    def validate(self, request, project_id=None, workflow_id=None):
        """
        Validate workflow structure and configuration
        """
        workflow = self.get_object()
        
        logger.info(f"✅ WORKFLOW VALIDATE: {workflow.workflow_id} by {request.user.email}")
        
        errors = []
        warnings = []
        
        # Basic validation
        graph_json = workflow.graph_json
        nodes = graph_json.get('nodes', [])
        edges = graph_json.get('edges', [])
        
        # Check for required nodes
        if not nodes:
            errors.append("Workflow must contain at least one node")
        
        # Check for Start Node (REQUIRED - validation error if missing)
        start_nodes = [n for n in nodes if n.get('type') == 'StartNode']
        if not start_nodes:
            errors.append("Workflow must contain at least one Start Node")
        elif len(start_nodes) > 1:
            warnings.append("Workflow should contain only one Start Node")
        
        # Check for End Node (REQUIRED - validation error if missing)
        end_nodes = [n for n in nodes if n.get('type') == 'EndNode']
        if not end_nodes:
            errors.append("Workflow must contain at least one End Node")
        
        # Check for orphaned nodes
        node_ids = set(n['id'] for n in nodes)
        connected_nodes = set()
        for edge in edges:
            connected_nodes.add(edge['source'])
            connected_nodes.add(edge['target'])
        
        orphaned_nodes = node_ids - connected_nodes
        if orphaned_nodes and len(nodes) > 1:
            warnings.append(f"Found {len(orphaned_nodes)} disconnected nodes")
        
        # Update workflow status
        if not errors:
            workflow.status = AgentWorkflowStatus.VALIDATED
            workflow.save()
        
        return Response({
            'valid': len(errors) == 0,
            'errors': errors,
            'warnings': warnings,
            'status': workflow.status,
            'validated_at': timezone.now()
        })
    
    @action(detail=True, methods=['post'], parser_classes=[MultiPartParser, FormParser])
    def evaluate(self, request, project_id=None, workflow_id=None):
        """
        POST /api/projects/{project_id}/workflows/{workflow_id}/evaluate/
        Upload CSV and start workflow evaluation
        """
        workflow = self.get_object()
        
        logger.info(f"🔍 WORKFLOW EVALUATE: {workflow.workflow_id} by {request.user.email}")
        
        if 'csv_file' not in request.FILES:
            return Response({
                'error': 'No CSV file provided',
                'detail': 'Please upload a CSV file with "input" and "expected_output" columns'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        csv_file = request.FILES['csv_file']
        
        # Validate file type
        if not csv_file.name.lower().endswith('.csv'):
            return Response({
                'error': 'Invalid file type',
                'detail': 'File must be a CSV file'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            # Import here to avoid circular imports
            import asyncio
            
            # Create orchestrator to get dependencies
            orchestrator = ConversationOrchestrator()
            
            # Create evaluator
            evaluator = WorkflowEvaluator(
                workflow_executor=orchestrator.workflow_executor,
                llm_provider_manager=orchestrator.llm_provider_manager,
                workflow_parser=orchestrator.workflow_parser
            )
            
            # Run evaluation asynchronously
            async def run_evaluation():
                return await evaluator.evaluate_workflow(
                    workflow=workflow,
                    csv_file=csv_file,
                    executed_by=request.user
                )
            
            evaluation = asyncio.run(run_evaluation())
            
            logger.info(f"✅ WORKFLOW EVALUATE: Evaluation {evaluation.evaluation_id} completed")
            
            return Response({
                'evaluation_id': str(evaluation.evaluation_id),
                'status': evaluation.status,
                'total_rows': evaluation.total_rows,
                'completed_rows': evaluation.completed_rows,
                'failed_rows': evaluation.failed_rows,
                'csv_filename': evaluation.csv_filename,
                'created_at': evaluation.created_at.isoformat()
            }, status=status.HTTP_201_CREATED)
            
        except ValueError as e:
            logger.error(f"❌ WORKFLOW EVALUATE: CSV parsing error: {e}")
            return Response({
                'error': 'CSV parsing failed',
                'detail': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"❌ WORKFLOW EVALUATE: Evaluation failed: {e}")
            import traceback
            logger.error(f"❌ WORKFLOW EVALUATE TRACEBACK: {traceback.format_exc()}")
            return Response({
                'error': 'Evaluation failed',
                'detail': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['get'])
    def evaluation_history(self, request, project_id=None, workflow_id=None):
        """
        GET /api/projects/{project_id}/workflows/{workflow_id}/evaluation_history/
        Get all evaluation runs for a workflow
        """
        workflow = self.get_object()
        
        logger.info(f"📊 WORKFLOW EVALUATION HISTORY: {workflow.workflow_id}")
        
        try:
            evaluations = WorkflowEvaluation.objects.filter(workflow=workflow).order_by('-created_at')
            
            evaluation_list = []
            for eval_obj in evaluations:
                evaluation_list.append({
                    'evaluation_id': str(eval_obj.evaluation_id),
                    'csv_filename': eval_obj.csv_filename,
                    'total_rows': eval_obj.total_rows,
                    'completed_rows': eval_obj.completed_rows,
                    'failed_rows': eval_obj.failed_rows,
                    'status': eval_obj.status,
                    'created_at': eval_obj.created_at.isoformat(),
                    'executed_by': {
                        'email': eval_obj.executed_by.email,
                        'first_name': eval_obj.executed_by.first_name
                    }
                })
            
            return Response({
                'workflow_id': str(workflow.workflow_id),
                'workflow_name': workflow.name,
                'evaluations': evaluation_list,
                'total_evaluations': len(evaluation_list)
            })
            
        except Exception as e:
            logger.error(f"❌ WORKFLOW EVALUATION HISTORY: Failed: {e}")
            return Response({
                'error': 'Failed to retrieve evaluation history',
                'detail': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['get'])
    def evaluation_results(self, request, project_id=None, workflow_id=None):
        """
        GET /api/projects/{project_id}/workflows/{workflow_id}/evaluation_results/?evaluation_id={id}
        Get detailed results for a specific evaluation run
        """
        workflow = self.get_object()
        evaluation_id = request.query_params.get('evaluation_id')
        
        if not evaluation_id:
            return Response({
                'error': 'evaluation_id parameter is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        logger.info(f"📊 WORKFLOW EVALUATION RESULTS: {workflow.workflow_id} - {evaluation_id}")
        
        try:
            evaluation = WorkflowEvaluation.objects.get(
                evaluation_id=evaluation_id,
                workflow=workflow
            )
            
            results = WorkflowEvaluationResult.objects.filter(
                evaluation=evaluation
            ).order_by('row_number')
            
            results_list = []
            for result in results:
                results_list.append({
                    'row_number': result.row_number,
                    'input_text': result.input_text,
                    'expected_output': result.expected_output,
                    'workflow_output': result.workflow_output,
                    'execution_id': result.execution_id,
                    'rouge_1_score': result.rouge_1_score,
                    'rouge_2_score': result.rouge_2_score,
                    'rouge_l_score': result.rouge_l_score,
                    'bleu_score': result.bleu_score,
                    'bert_score': result.bert_score,
                    'semantic_similarity': result.semantic_similarity,
                    'average_score': result.average_score,
                    'status': result.status,
                    'error_message': result.error_message,
                    'execution_time_seconds': result.execution_time_seconds,
                    'created_at': result.created_at.isoformat()
                })
            
            # Calculate aggregate statistics
            successful_results = [r for r in results_list if r['status'] == 'success']
            if successful_results:
                avg_scores = {
                    'rouge_1': sum(r['rouge_1_score'] or 0 for r in successful_results) / len(successful_results),
                    'rouge_2': sum(r['rouge_2_score'] or 0 for r in successful_results) / len(successful_results),
                    'rouge_l': sum(r['rouge_l_score'] or 0 for r in successful_results) / len(successful_results),
                    'bleu': sum(r['bleu_score'] or 0 for r in successful_results) / len(successful_results),
                    'bert_score': sum(r['bert_score'] or 0 for r in successful_results) / len(successful_results),
                    'semantic_similarity': sum(r['semantic_similarity'] or 0 for r in successful_results) / len(successful_results),
                    'average_score': sum(r['average_score'] or 0 for r in successful_results) / len(successful_results)
                }
            else:
                avg_scores = None
            
            return Response({
                'evaluation_id': str(evaluation.evaluation_id),
                'workflow_id': str(workflow.workflow_id),
                'workflow_name': workflow.name,
                'csv_filename': evaluation.csv_filename,
                'status': evaluation.status,
                'total_rows': evaluation.total_rows,
                'completed_rows': evaluation.completed_rows,
                'failed_rows': evaluation.failed_rows,
                'created_at': evaluation.created_at.isoformat(),
                'results': results_list,
                'aggregate_statistics': avg_scores
            })
            
        except WorkflowEvaluation.DoesNotExist:
            return Response({
                'error': 'Evaluation not found',
                'detail': f'No evaluation found with ID {evaluation_id} for this workflow'
            }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"❌ WORKFLOW EVALUATION RESULTS: Failed: {e}")
            import traceback
            logger.error(f"❌ WORKFLOW EVALUATION RESULTS TRACEBACK: {traceback.format_exc()}")
            return Response({
                'error': 'Failed to retrieve evaluation results',
                'detail': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
