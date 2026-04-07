# Phase 2: Human Input API Views
# UserProxyAgent Human-in-the-Loop API Endpoints

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.utils import timezone
from asgiref.sync import sync_to_async
import asyncio
import logging

from users.models import WorkflowExecution, WorkflowExecutionStatus, HumanInputInteraction
from .conversation_orchestrator import ConversationOrchestrator

# Enhanced logging setup for human input API operations
logger = logging.getLogger('human_input_views')

# Add detailed formatter for API operations
class HumanInputAPIFormatter(logging.Formatter):
    def format(self, record):
        # Add timestamp and request info
        formatted = super().format(record)
        if hasattr(record, 'request_id'):
            formatted = f"[REQ:{record.request_id}] {formatted}"
        if hasattr(record, 'interaction_id'):
            formatted = f"[INT:{record.interaction_id}] {formatted}"
        return formatted

# Set up specialized handler for API tracing
if not any(isinstance(handler, logging.StreamHandler) for handler in logger.handlers):
    handler = logging.StreamHandler()
    handler.setFormatter(HumanInputAPIFormatter(
        '%(asctime)s - 🌐 HUMAN_INPUT_API - %(levelname)s - %(message)s'
    ))
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_pending_human_inputs(request):
    """
    Get all workflows awaiting human input for current user
    """
    logger.info(f"📋 PENDING_INPUTS: Starting request for user {request.user.email}")
    logger.debug(f"📋 PENDING_INPUTS: Request method={request.method}, path={request.path}")
    
    try:
        # 🔧 PREVENTIVE CLEANUP: Clean up stale executions older than 1 hour
        from django.utils import timezone
        from datetime import timedelta
        
        one_hour_ago = timezone.now() - timedelta(hours=1)
        stale_executions = WorkflowExecution.objects.filter(
            executed_by=request.user,
            human_input_required=True,
            status=WorkflowExecutionStatus.RUNNING,
            human_input_requested_at__lt=one_hour_ago
        )
        
        if stale_executions.exists():
            stale_count = stale_executions.count()
            logger.info(f"🧹 CLEANUP: Found {stale_count} stale executions older than 1 hour")
            
            # Clean up stale executions
            stale_executions.update(
                human_input_required=False,
                status=WorkflowExecutionStatus.COMPLETED,
                awaiting_human_input_agent='',
                result_summary='Auto-completed due to stale human input timeout'
            )
            logger.info(f"✅ CLEANUP: Cleaned up {stale_count} stale executions")
        
        pending_executions = WorkflowExecution.objects.filter(
            executed_by=request.user,
            human_input_required=True,
            status=WorkflowExecutionStatus.RUNNING
        ).order_by('-human_input_requested_at')
        
        logger.info(f"📊 PENDING_INPUTS: Found {len(pending_executions)} pending workflows")
        
        if pending_executions:
            logger.debug(
                f"📋 PENDING_INPUTS: Execution IDs: {[ex.execution_id[:8] for ex in pending_executions]}"
            )
        
        # Filter out deployment executions with user input mode (these should only show in client UI)
        from .models import DeploymentSession
        pending_inputs_data = []
        for execution in pending_executions:
            # Check if this execution is in deployment context with user input mode
            human_input_context = execution.human_input_context or {}
            input_mode = human_input_context.get('input_mode', 'user')
            is_deployment = human_input_context.get('is_deployment', False)
            
            # Also check DeploymentSession to be sure
            deployment_session_exists = DeploymentSession.objects.filter(
                paused_execution_id=execution.execution_id
            ).exists()
            
            # Skip if it's user input mode in deployment context (should only show in client UI)
            if (input_mode == 'user' and (is_deployment or deployment_session_exists)):
                logger.debug(
                    f"⏭️ PENDING_INPUTS: Skipping execution {execution.execution_id[:8]} - "
                    f"user input mode in deployment context (input_mode={input_mode}, is_deployment={is_deployment}, session_exists={deployment_session_exists})"
                )
                continue
            logger.debug(
                f"📝 PENDING_INPUTS: Processing execution {execution.execution_id[:8]} - "
                f"workflow={execution.workflow.name}, agent={execution.awaiting_human_input_agent}"
            )
            
            pending_inputs_data.append({
                'execution_id': execution.execution_id,
                'workflow_name': execution.workflow.name,
                'agent_name': execution.awaiting_human_input_agent,
                'agent_id': execution.human_input_agent_id,
                'requested_at': execution.human_input_requested_at,
                'context': execution.human_input_context,
                'conversation_history': execution.conversation_history
            })
            
            logger.debug(
                f"🕰️ PENDING_INPUTS: {execution.execution_id[:8]} requested at {execution.human_input_requested_at}"
            )
        
        logger.info(f"✅ PENDING_INPUTS: Returning {len(pending_inputs_data)} pending inputs to user")
        
        return Response({
            'status': 'success',
            'pending_inputs': pending_inputs_data
        })
        
    except Exception as e:
        logger.error(f"❌ PENDING_INPUTS: Error getting pending inputs: {e}")
        import traceback
        logger.error(f"🔍 PENDING_INPUTS: Traceback: {traceback.format_exc()}")
        return Response({
            'status': 'error',
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def submit_human_input(request):
    """
    Submit human input to resume workflow
    """
    execution_id = request.data.get('execution_id')
    human_input = request.data.get('human_input', '').strip()
    action = request.data.get('action', 'submit')
    
    logger.info(f"📝 SUBMIT_INPUT: Starting submission for execution {execution_id[:8] if execution_id else 'None'}")
    logger.debug(f"📝 SUBMIT_INPUT: Request user={request.user.email}, method={request.method}")
    logger.info(f"📝 SUBMIT_INPUT: Human input length: {len(human_input)} chars, action: {action}")
    logger.debug(f"📝 SUBMIT_INPUT: Input preview: '{human_input[:100]}...'")
    
    if not execution_id:
        logger.warning("⚠️ SUBMIT_INPUT: Missing execution_id in request")
        return Response({
            'status': 'error',
            'error': 'execution_id is required'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    if not human_input:
        logger.warning(
            f"⚠️ SUBMIT_INPUT: Empty human input for execution {execution_id[:8]}"
        )
        return Response({
            'status': 'error', 
            'error': 'human_input is required'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        # Verify the execution exists and belongs to the user
        logger.debug(
            f"🔍 SUBMIT_INPUT: Looking up execution {execution_id[:8]} for user {request.user.email}"
        )
        
        execution = WorkflowExecution.objects.get(
            execution_id=execution_id,
            executed_by=request.user,
            human_input_required=True
        )
        
        logger.info(
            f"✅ SUBMIT_INPUT: Found execution {execution.execution_id[:8]} - "
            f"workflow={execution.workflow.name}, agent={execution.awaiting_human_input_agent}"
        )
        
        logger.info(
            f"🔄 SUBMIT_INPUT: Resuming workflow for execution {execution_id[:8]}"
        )
        
        # Get orchestrator and resume workflow (using asyncio to run async function)
        logger.debug(
            f"🤖 SUBMIT_INPUT: Creating ConversationOrchestrator for {execution_id[:8]}"
        )
        orchestrator = ConversationOrchestrator()
        
        async def resume_workflow():
            # Check if this is a reflection iteration scenario
            if action == 'iterate':
                logger.info(f"🔄 SUBMIT_INPUT: Processing reflection iteration for {execution_id[:8]}")
                # Check if this is a reflection scenario by looking at human_input_context
                reflection_context = execution.human_input_context
                if reflection_context and reflection_context.get('reflection_source'):
                    logger.info(f"✅ SUBMIT_INPUT: Confirmed reflection scenario - source: {reflection_context.get('reflection_source')}")
                    return await orchestrator.human_input_handler.reflection_handler.iterate_reflection_workflow(
                        execution, human_input
                    )
                else:
                    logger.warning(f"⚠️ SUBMIT_INPUT: Iteration action without reflection context for {execution_id[:8]}")
                    # Fall back to regular resume
                    return await orchestrator.resume_workflow_with_human_input(
                        execution_id, human_input, request.user
                    )
            else:
                logger.debug(
                    f"⚡ SUBMIT_INPUT: Calling orchestrator.resume_workflow_with_human_input for {execution_id[:8]}"
                )
                return await orchestrator.resume_workflow_with_human_input(
                    execution_id, human_input, request.user
                )
        
        logger.debug(f"🔄 SUBMIT_INPUT: Running async resume_workflow for {execution_id[:8]} with action: {action}")
        result = asyncio.run(resume_workflow())
        logger.debug(f"✅ SUBMIT_INPUT: Async operation completed for {execution_id[:8]}")
        
        # Handle special iteration response
        if action == 'iterate' and isinstance(result, tuple) and len(result) == 2:
            iteration_response, updated_conversation = result
            if iteration_response == 'AWAITING_REFLECTION_INPUT':
                logger.info(f"🔄 SUBMIT_INPUT: Iteration created new reflection pause for {execution_id[:8]}")
                return Response({
                    'status': 'success',
                    'message': 'Iteration submitted - workflow paused for next feedback cycle',
                    'execution_id': execution_id,
                    'action': 'iterate',
                    'awaiting_input': True
                })
            else:
                logger.info(f"🎉 SUBMIT_INPUT: Iteration completed for {execution_id[:8]}")
                return Response({
                    'status': 'success',
                    'message': 'Iteration completed successfully',
                    'execution_id': execution_id,
                    'action': 'iterate',
                    'result': iteration_response
                })
        
        logger.info(
            f"🎉 SUBMIT_INPUT: Workflow {execution_id[:8]} resumed successfully"
        )
        logger.debug(
            f"📋 SUBMIT_INPUT: Result type: {type(result)}, keys: {list(result.keys()) if isinstance(result, dict) else 'N/A'}"
        )
        
        return Response({
            'status': 'success',
            'message': 'Workflow resumed successfully',
            'execution_id': execution_id,
            'result': result
        })
        
    except WorkflowExecution.DoesNotExist:
        logger.error(
            f"❌ SUBMIT_INPUT: Execution {execution_id[:8] if execution_id else 'None'} not found or not waiting for input"
        )
        logger.debug(
            f"🔍 SUBMIT_INPUT: User {request.user.email} tried to access non-existent or non-pending execution"
        )
        return Response({
            'status': 'error',
            'error': 'Execution not found or not awaiting human input'
        }, status=status.HTTP_404_NOT_FOUND)
        
    except Exception as e:
        logger.error(
            f"❌ SUBMIT_INPUT: Failed to resume workflow {execution_id[:8] if execution_id else 'None'}: {e}"
        )
        import traceback
        logger.error(
            f"🔍 SUBMIT_INPUT: Traceback: {traceback.format_exc()}"
        )
        return Response({
            'status': 'error',
            'error': f'Failed to resume workflow: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_human_input_history(request):
    """
    Get human input interaction history for current user
    """
    logger.info(f"📋 HISTORY: Getting interaction history for user {request.user.email}")
    logger.debug(f"📋 HISTORY: Request method={request.method}, path={request.path}")
    
    try:
        # Get recent human input interactions
        interactions = HumanInputInteraction.objects.filter(
            execution__executed_by=request.user
        ).order_by('-created_at')[:50]  # Last 50 interactions
        
        history_data = []
        logger.info(f"📊 HISTORY: Processing {len(interactions)} interactions")
        
        for interaction in interactions:
            logger.debug(
                f"📝 HISTORY: Processing interaction {interaction.id} - "
                f"execution={interaction.execution.execution_id[:8]}, agent={interaction.agent_name}"
            )
            
            history_data.append({
                'id': interaction.id,
                'execution_id': interaction.execution.execution_id,
                'workflow_name': interaction.execution.workflow.name,
                'agent_name': interaction.agent_name,
                'human_response': interaction.human_response,
                'response_time': interaction.formatted_response_time,
                'input_context_summary': interaction.input_context_summary,
                'requested_at': interaction.requested_at,
                'created_at': interaction.created_at,
                'workflow_resumed': interaction.workflow_resumed,
                'processed_successfully': interaction.processed_successfully
            })
        
        logger.info(f"✅ HISTORY: Returning {len(history_data)} interaction records to user")
        
        return Response({
            'status': 'success',
            'interactions': history_data,
            'count': len(history_data)
        })
        
    except Exception as e:
        logger.error(f"❌ HISTORY: Error getting interaction history: {e}")
        import traceback
        logger.error(f"🔍 HISTORY: Traceback: {traceback.format_exc()}")
        return Response({
            'status': 'error',
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


def clear_pending_inputs_for_execution(execution_id: str):
    """
    Clear all pending human inputs for a specific execution
    """
    try:
        logger.info(f"🧹 CLEANUP: Clearing pending inputs for execution {execution_id}")
        
        # Clear from WorkflowExecution model
        WorkflowExecution.objects.filter(execution_id=execution_id).update(
            status=WorkflowExecutionStatus.STOPPED,
            human_input_required=False,
            awaiting_human_input_agent="",
            human_input_context={},
            end_time=timezone.now()
        )
        
        # Clear from HumanInputInteraction model  
        HumanInputInteraction.objects.filter(
            execution_id=execution_id,
            response_submitted_at__isnull=True
        ).update(
            status='cancelled',
            workflow_resumed=False,
            processed_successfully=False
        )
        
        logger.info(f"🧹 CLEANUP: Successfully cleared pending inputs for execution {execution_id}")
        
    except Exception as e:
        logger.error(f"❌ CLEANUP: Error clearing pending inputs for execution {execution_id}: {e}")
        import traceback
        logger.error(f"🔍 CLEANUP: Traceback: {traceback.format_exc()}")
