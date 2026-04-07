# backend/agent_orchestration/simple_workflow_views.py

from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from django.utils import timezone
from asgiref.sync import async_to_sync
import logging
import uuid

from users.models import IntelliDocProject, AgentWorkflow
from .conversation_orchestrator import ConversationOrchestrator

logger = logging.getLogger(__name__)

class SimpleAgentWorkflowViewSet(viewsets.ViewSet):
    """
    Simplified ViewSet for managing agent workflows within projects (REAL ORCHESTRATION)
    """
    permission_classes = [IsAuthenticated]
    
    def list(self, request, project_id=None):
        """List workflows for a project"""
        try:
            logger.info(f"🔍 SIMPLE: Listing workflows for project {project_id}")
            
            # Get project
            project = get_object_or_404(IntelliDocProject, project_id=project_id)
            
            # FIX: Check if user has access to this project using project permission system
            if not project.has_user_access(request.user):
                logger.warning(f"🚫 SIMPLE: User {request.user.email} denied access to project {project.name}")
                return Response({
                    'error': 'You do not have permission to access workflows in this project'
                }, status=status.HTTP_403_FORBIDDEN)
            
            # FIX: Get ALL workflows for this project (not just created_by user)
            workflows = AgentWorkflow.objects.filter(project=project).order_by('-updated_at')
            
            # Build simple response data
            workflow_data = []
            for workflow in workflows:
                try:
                    workflow_item = {
                        'workflow_id': str(workflow.workflow_id),
                        'name': workflow.name,
                        'description': workflow.description,
                        'status': workflow.status,
                        'created_at': workflow.created_at.isoformat() if workflow.created_at else None,
                        'updated_at': workflow.updated_at.isoformat() if workflow.updated_at else None,
                        'graph_json': workflow.graph_json or {'nodes': [], 'edges': []},
                        'node_count': len(workflow.graph_json.get('nodes', [])) if workflow.graph_json else 0,
                        'edge_count': len(workflow.graph_json.get('edges', [])) if workflow.graph_json else 0
                    }
                    workflow_data.append(workflow_item)
                except Exception as e:
                    logger.error(f"❌ SIMPLE: Error processing workflow {workflow.workflow_id}: {e}")
            
            logger.info(f"✅ SIMPLE: Found {len(workflow_data)} workflows")
            
            return Response({
                'data': workflow_data,
                'count': len(workflow_data),
                'project_id': str(project_id)
            })
            
        except Exception as e:
            logger.error(f"❌ SIMPLE: Error listing workflows: {e}")
            return Response({
                'error': 'Failed to list workflows',
                'detail': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def create(self, request, project_id=None):
        """Create a new workflow"""
        try:
            logger.info(f"🆕 SIMPLE: Creating workflow for project {project_id}")
            
            # Get project
            project = get_object_or_404(IntelliDocProject, project_id=project_id)
            
            # FIX: Ensure user has access using project permission system
            if not project.has_user_access(request.user):
                logger.warning(f"🚫 SIMPLE CREATE: User {request.user.email} denied workflow creation access to project {project.name}")
                return Response({
                    'error': 'You do not have permission to create workflows in this project'
                }, status=status.HTTP_403_FORBIDDEN)
            
            # Get data from request
            data = request.data
            name = data.get('name', f'Workflow {timezone.now().strftime("%Y%m%d_%H%M%S")}')
            description = data.get('description', 'New agent orchestration workflow')
            graph_json = data.get('graph_json', {'nodes': [], 'edges': []})
            
            # Create workflow
            workflow = AgentWorkflow.objects.create(
                project=project,
                created_by=request.user,
                name=name,
                description=description,
                graph_json=graph_json,
                status='draft'
            )
            
            logger.info(f"✅ SIMPLE: Created workflow {workflow.workflow_id}")
            
            return Response({
                'workflow_id': str(workflow.workflow_id),
                'name': workflow.name,
                'description': workflow.description,
                'status': workflow.status,
                'created_at': workflow.created_at.isoformat(),
                'graph_json': workflow.graph_json,
                'message': 'Workflow created successfully'
            }, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            logger.error(f"❌ SIMPLE: Error creating workflow: {e}")
            return Response({
                'error': 'Failed to create workflow',
                'detail': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def retrieve(self, request, project_id=None, workflow_id=None):
        """Get a specific workflow"""
        try:
            logger.info(f"📄 SIMPLE: Retrieving workflow {workflow_id}")
            
            # Get project and workflow
            project = get_object_or_404(IntelliDocProject, project_id=project_id)
            
            # FIX: Check if user has access to this project using project permission system
            if not project.has_user_access(request.user):
                logger.warning(f"🚫 SIMPLE: User {request.user.email} denied access to workflow in project {project.name}")
                return Response({
                    'error': 'You do not have permission to access workflows in this project'
                }, status=status.HTTP_403_FORBIDDEN)
            
            workflow = get_object_or_404(
                AgentWorkflow, 
                workflow_id=workflow_id, 
                project=project
            )
            
            return Response({
                'workflow_id': str(workflow.workflow_id),
                'name': workflow.name,
                'description': workflow.description,
                'status': workflow.status,
                'created_at': workflow.created_at.isoformat(),
                'updated_at': workflow.updated_at.isoformat(),
                'graph_json': workflow.graph_json
            })
            
        except Exception as e:
            logger.error(f"❌ SIMPLE: Error retrieving workflow: {e}")
            return Response({
                'error': 'Failed to retrieve workflow',
                'detail': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def partial_update(self, request, project_id=None, workflow_id=None):
        """Update a workflow"""
        try:
            logger.info(f"📝 SIMPLE: Updating workflow {workflow_id}")
            
            # Get project and workflow
            project = get_object_or_404(IntelliDocProject, project_id=project_id)
            
            # FIX: Check if user has access to this project using project permission system
            if not project.has_user_access(request.user):
                logger.warning(f"🚫 SIMPLE: User {request.user.email} denied access to workflow in project {project.name}")
                return Response({
                    'error': 'You do not have permission to access workflows in this project'
                }, status=status.HTTP_403_FORBIDDEN)
            
            workflow = get_object_or_404(
                AgentWorkflow, 
                workflow_id=workflow_id, 
                project=project
            )
            
            # Update fields
            data = request.data
            if 'name' in data:
                workflow.name = data['name']
            if 'description' in data:
                workflow.description = data['description']
            if 'graph_json' in data:
                workflow.graph_json = data['graph_json']
            if 'status' in data:
                workflow.status = data['status']
            
            workflow.updated_at = timezone.now()
            workflow.save()
            
            logger.info(f"✅ SIMPLE: Updated workflow {workflow.workflow_id}")
            
            return Response({
                'workflow_id': str(workflow.workflow_id),
                'name': workflow.name,
                'description': workflow.description,
                'status': workflow.status,
                'updated_at': workflow.updated_at.isoformat(),
                'graph_json': workflow.graph_json,
                'message': 'Workflow updated successfully'
            })
            
        except Exception as e:
            logger.error(f"❌ SIMPLE: Error updating workflow: {e}")
            return Response({
                'error': 'Failed to update workflow',
                'detail': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def update(self, request, project_id=None, workflow_id=None):
        """Full update of a workflow (PUT method)"""
        return self.partial_update(request, project_id, workflow_id)
    
    def destroy(self, request, project_id=None, workflow_id=None):
        """Delete a workflow"""
        try:
            logger.info(f"🗝 SIMPLE: Deleting workflow {workflow_id}")
            
            # Get project and workflow
            project = get_object_or_404(IntelliDocProject, project_id=project_id)
            
            # FIX: Check if user has access to this project using project permission system
            if not project.has_user_access(request.user):
                logger.warning(f"🚫 SIMPLE: User {request.user.email} denied access to workflow in project {project.name}")
                return Response({
                    'error': 'You do not have permission to access workflows in this project'
                }, status=status.HTTP_403_FORBIDDEN)
            
            workflow = get_object_or_404(
                AgentWorkflow, 
                workflow_id=workflow_id, 
                project=project
            )
            
            workflow_name = workflow.name
            workflow.delete()
            
            logger.info(f"✅ SIMPLE: Deleted workflow {workflow_id}")
            
            return Response({
                'message': f'Workflow "{workflow_name}" deleted successfully',
                'workflow_id': str(workflow_id)
            }, status=status.HTTP_204_NO_CONTENT)
            
        except Exception as e:
            logger.error(f"❌ SIMPLE: Error deleting workflow: {e}")
            return Response({
                'error': 'Failed to delete workflow',
                'detail': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def execute(self, request, project_id=None, workflow_id=None):
        """
        Execute a workflow with REAL conversation orchestration
        """
        try:
            logger.info(f"🚀 SIMPLE: Executing REAL workflow {workflow_id} for project {project_id}")
            
            # Get project and workflow
            project = get_object_or_404(IntelliDocProject, project_id=project_id)
            
            # FIX: Check if user has access to this project using project permission system
            if not project.has_user_access(request.user):
                logger.warning(f"🚫 SIMPLE: User {request.user.email} denied access to workflow in project {project.name}")
                return Response({
                    'error': 'You do not have permission to access workflows in this project'
                }, status=status.HTTP_403_FORBIDDEN)
            
            workflow = get_object_or_404(
                AgentWorkflow, 
                workflow_id=workflow_id, 
                project=project
            )
            
            # Validate workflow has nodes
            if not workflow.graph_json.get('nodes'):
                return Response({
                    'error': 'Workflow has no nodes to execute',
                    'detail': 'Please add agents to your workflow before executing'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            logger.info(f"🤖 SIMPLE: Starting REAL conversation orchestration for {workflow_id}")
            
            # Execute workflow using REAL conversation orchestrator
            try:
                # Create orchestrator instance
                orchestrator = ConversationOrchestrator()
                
                # Use async_to_sync to properly handle the async call from sync context  
                async def execute_async():
                    return await orchestrator.execute_workflow(workflow, request.user)
                
                execution_result = async_to_sync(execute_async)()
                
                logger.info(f"✅ SIMPLE: REAL workflow execution completed for {workflow_id}")
                
                # Check if execution was successful
                if execution_result.get('status') == 'failed':
                    return Response({
                        'status': 'error',
                        'message': f'Workflow "{workflow.name}" execution failed',
                        'workflow_id': str(workflow.workflow_id),
                        'execution_id': execution_result.get('execution_id', 'unknown'),
                        'error_message': execution_result.get('error_message', 'Unknown error'),
                        'execution_mode': 'real_conversation_orchestration'
                    }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
                
                return Response({
                    'status': 'success',
                    'message': f'Workflow "{workflow.name}" executed successfully with REAL agent conversations',
                    'workflow_id': str(workflow.workflow_id),
                    'execution_id': execution_result.get('execution_id', 'unknown'),
                    'executed_at': execution_result.get('start_time', ''),
                    'execution_mode': 'real_conversation_orchestration',
                    'execution_summary': {
                        'total_messages': execution_result.get('total_messages', 0),
                        'agents_involved': execution_result.get('total_agents_involved', 0),
                        'average_response_time_ms': execution_result.get('average_response_time_ms', 0),
                        'duration_seconds': execution_result.get('duration_seconds', 0),
                        'providers_used': execution_result.get('providers_used', []),
                        'status': execution_result.get('status', 'unknown')
                    },
                    'conversation_history': execution_result.get('conversation_history', ''),
                    'messages': execution_result.get('messages', []),
                    'graph_data': {
                        'nodes': len(workflow.graph_json.get('nodes', [])),
                        'edges': len(workflow.graph_json.get('edges', []))
                    }
                })
                
            except Exception as execution_error:
                logger.error(f"❌ SIMPLE: REAL workflow execution failed: {execution_error}")
                return Response({
                    'status': 'error',
                    'error': 'Workflow execution failed',
                    'detail': str(execution_error),
                    'execution_mode': 'real_conversation_orchestration',
                    'workflow_id': str(workflow.workflow_id)
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
        except Exception as e:
            logger.error(f"❌ SIMPLE: Error executing workflow: {e}")
            return Response({
                'error': 'Failed to execute workflow',
                'detail': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def history(self, request, project_id=None, workflow_id=None):
        """
        Get execution history for a workflow (simplified for real orchestration)
        """
        try:
            logger.info(f"📊 SIMPLE: Getting history for workflow {workflow_id}")
            
            # Get project and workflow
            project = get_object_or_404(IntelliDocProject, project_id=project_id)
            
            # FIX: Check if user has access to this project using project permission system
            if not project.has_user_access(request.user):
                logger.warning(f"🚫 SIMPLE: User {request.user.email} denied access to workflow in project {project.name}")
                return Response({
                    'error': 'You do not have permission to access workflows in this project'
                }, status=status.HTTP_403_FORBIDDEN)
            
            workflow = get_object_or_404(
                AgentWorkflow, 
                workflow_id=workflow_id, 
                project=project
            )
            
            # Get execution summary using conversation orchestrator
            orchestrator = ConversationOrchestrator()
            # For now, return basic execution summary - will be enhanced later
            execution_summary = {
                'workflow_id': str(workflow.workflow_id),
                'workflow_name': workflow.name,
                'total_executions': 0,
                'successful_executions': 0,
                'success_rate': 0,
                'recent_executions': [],
                'last_executed_at': workflow.last_executed_at.isoformat() if workflow.last_executed_at else None
            }
            
            logger.info(f"✅ SIMPLE: Retrieved execution history for {workflow_id}")
            
            return Response(execution_summary)
            
        except Exception as e:
            logger.error(f"❌ SIMPLE: Error getting workflow history: {e}")
            return Response({
                'error': 'Failed to get workflow history',
                'detail': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def validate(self, request, project_id=None, workflow_id=None):
        """
        Validate workflow structure and configuration
        """
        try:
            logger.info(f"✅ SIMPLE: Validating workflow {workflow_id}")
            
            # Get project and workflow
            project = get_object_or_404(IntelliDocProject, project_id=project_id)
            
            # FIX: Check if user has access to this project using project permission system
            if not project.has_user_access(request.user):
                logger.warning(f"🚫 SIMPLE: User {request.user.email} denied access to workflow in project {project.name}")
                return Response({
                    'error': 'You do not have permission to access workflows in this project'
                }, status=status.HTTP_403_FORBIDDEN)
            
            workflow = get_object_or_404(
                AgentWorkflow, 
                workflow_id=workflow_id, 
                project=project
            )
            
            errors = []
            warnings = []
            
            # Basic validation
            graph_json = workflow.graph_json or {'nodes': [], 'edges': []}
            nodes = graph_json.get('nodes', [])
            edges = graph_json.get('edges', [])
            
            # Allow empty workflows - no validation errors for blank canvas
            if not nodes:
                return Response({
                    'valid': True,
                    'errors': [],
                    'warnings': ['Workflow is empty - add nodes to begin building'],
                    'status': 'draft',
                    'validated_at': timezone.now().isoformat(),
                    'node_count': 0,
                    'edge_count': 0
                })
            
            # Only validate if workflow has nodes
            
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
            if len(nodes) > 1:
                node_ids = set(n['id'] for n in nodes)
                connected_nodes = set()
                for edge in edges:
                    connected_nodes.add(edge['source'])
                    connected_nodes.add(edge['target'])
                
                orphaned_nodes = node_ids - connected_nodes
                if orphaned_nodes:
                    warnings.append(f"Found {len(orphaned_nodes)} disconnected nodes")
            
            # Update workflow status if valid
            if not errors:
                workflow.status = 'validated'
                workflow.save()
            
            return Response({
                'valid': len(errors) == 0,
                'errors': errors,
                'warnings': warnings,
                'status': workflow.status,
                'validated_at': timezone.now().isoformat(),
                'node_count': len(nodes),
                'edge_count': len(edges)
            })
            
        except Exception as e:
            logger.error(f"❌ SIMPLE: Error validating workflow: {e}")
            return Response({
                'error': 'Failed to validate workflow',
                'detail': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def conversation(self, request, project_id=None, workflow_id=None):
        """
        Get detailed execution messages for a specific execution
        """
        try:
            execution_id = request.GET.get('execution_id')
            if not execution_id:
                return Response({
                    'error': 'execution_id parameter is required',
                    'detail': 'Provide execution_id to retrieve conversation history'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            logger.info(f"💬 SIMPLE: Getting conversation for execution {execution_id}")
            
            # Get project and workflow
            project = get_object_or_404(IntelliDocProject, project_id=project_id)
            
            # FIX: Check if user has access to this project using project permission system
            if not project.has_user_access(request.user):
                logger.warning(f"🚫 SIMPLE: User {request.user.email} denied access to workflow in project {project.name}")
                return Response({
                    'error': 'You do not have permission to access workflows in this project'
                }, status=status.HTTP_403_FORBIDDEN)
            
            workflow = get_object_or_404(
                AgentWorkflow, 
                workflow_id=workflow_id, 
                project=project
            )
            
            # Get the specific execution
            from users.models import WorkflowExecution, WorkflowExecutionMessage
            
            try:
                execution = WorkflowExecution.objects.get(
                    workflow=workflow,
                    execution_id=execution_id
                )
            except WorkflowExecution.DoesNotExist:
                return Response({
                    'error': 'Execution not found',
                    'detail': f'No execution found with ID {execution_id}'
                }, status=status.HTTP_404_NOT_FOUND)
            
            # Get messages for this execution
            messages = WorkflowExecutionMessage.objects.filter(
                execution=execution
            ).order_by('sequence')
            
            # Format messages
            formatted_messages = []
            for msg in messages:
                formatted_messages.append({
                    'sequence': msg.sequence,
                    'agent_name': msg.agent_name,
                    'agent_type': msg.agent_type,
                    'content': msg.content,
                    'message_type': msg.message_type,
                    'timestamp': msg.timestamp.isoformat(),
                    'response_time_ms': msg.response_time_ms,
                    'token_count': msg.token_count,
                    'metadata': msg.metadata
                })
            
            return Response({
                'workflow_id': str(workflow.workflow_id),
                'workflow_name': workflow.name,
                'execution_id': execution_id,
                'execution_status': execution.status,
                'start_time': execution.start_time.isoformat(),
                'end_time': execution.end_time.isoformat() if execution.end_time else None,
                'total_messages': execution.total_messages,
                'messages': formatted_messages,
                'conversation_summary': execution.result_summary
            })
            
        except Exception as e:
            logger.error(f"❌ SIMPLE: Error getting conversation: {e}")
            return Response({
                'error': 'Failed to get conversation history',
                'detail': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
