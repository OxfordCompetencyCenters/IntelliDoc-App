# backend/agent_orchestration/debug_views.py

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
import logging

logger = logging.getLogger(__name__)

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def debug_workflows(request, project_id=None):
    """Debug endpoint for workflow operations"""
    try:
        logger.info(f"🔧 DEBUG: Workflow request for project {project_id}")
        logger.info(f"🔧 DEBUG: Method {request.method}")
        logger.info(f"🔧 DEBUG: User {request.user}")
        
        # Check if we can import the models
        try:
            from users.models import IntelliDocProject, AgentWorkflow
            logger.info("✅ DEBUG: Models imported successfully")
        except Exception as e:
            logger.error(f"❌ DEBUG: Failed to import models: {e}")
            return Response({
                'error': 'Model import failed',
                'detail': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        # Check if project exists
        try:
            project = get_object_or_404(IntelliDocProject, project_id=project_id)
            logger.info(f"✅ DEBUG: Project found: {project.name}")
        except Exception as e:
            logger.error(f"❌ DEBUG: Failed to get project: {e}")
            return Response({
                'error': 'Project not found',
                'detail': str(e)
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Check if we can query workflows
        try:
            workflows = AgentWorkflow.objects.filter(
                project=project, 
                created_by=request.user
            )
            workflow_count = workflows.count()
            logger.info(f"✅ DEBUG: Found {workflow_count} workflows")
            
            if request.method == 'GET':
                # Return simple workflow list
                workflow_data = []
                for workflow in workflows[:5]:  # Limit to 5 for debugging
                    workflow_data.append({
                        'workflow_id': str(workflow.workflow_id),
                        'name': workflow.name,
                        'status': workflow.status,
                        'created_at': workflow.created_at.isoformat() if workflow.created_at else None,
                        'node_count': len(workflow.graph_json.get('nodes', [])) if workflow.graph_json else 0
                    })
                
                return Response({
                    'debug': True,
                    'project_id': str(project_id),
                    'project_name': project.name,
                    'workflow_count': workflow_count,
                    'workflows': workflow_data,
                    'user': request.user.email
                })
            
            elif request.method == 'POST':
                # Create a simple test workflow
                try:
                    test_workflow = AgentWorkflow.objects.create(
                        project=project,
                        created_by=request.user,
                        name=f"Debug Workflow {workflow_count + 1}",
                        description="Debug test workflow",
                        graph_json={
                            'nodes': [
                                {
                                    'id': 'start_debug',
                                    'type': 'StartNode',
                                    'position': {'x': 0, 'y': 0},
                                    'data': {'name': 'Debug Start', 'prompt': 'Debug workflow'}
                                }
                            ],
                            'edges': []
                        }
                    )
                    
                    logger.info(f"✅ DEBUG: Created test workflow {test_workflow.workflow_id}")
                    
                    return Response({
                        'debug': True,
                        'created': True,
                        'workflow_id': str(test_workflow.workflow_id),
                        'name': test_workflow.name,
                        'message': 'Debug workflow created successfully'
                    })
                    
                except Exception as e:
                    logger.error(f"❌ DEBUG: Failed to create workflow: {e}")
                    return Response({
                        'error': 'Workflow creation failed',
                        'detail': str(e)
                    }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        except Exception as e:
            logger.error(f"❌ DEBUG: Failed to query workflows: {e}")
            return Response({
                'error': 'Workflow query failed',
                'detail': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
    except Exception as e:
        logger.error(f"❌ DEBUG: Unexpected error: {e}")
        return Response({
            'error': 'Unexpected error',
            'detail': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
