"""
In-App Chatbot API -- chat with project workflows.
User messages are processed through the workflow's agent orchestration pipeline.
Conversation history is persisted in the database.
"""
import json
import logging
import uuid
import time
from django.http import JsonResponse
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from asgiref.sync import async_to_sync, sync_to_async
from users.models import IntelliDocProject

logger = logging.getLogger(__name__)


@api_view(['GET'])
@permission_classes([AllowAny])
def chatbot_sessions(request, project_id):
    """List all chatbot sessions for a project."""
    from .models import ChatbotSession
    sessions = ChatbotSession.objects.filter(
        project__project_id=project_id
    ).order_by('-updated_at')

    return Response({
        'sessions': [{
            'id': str(s.session_id),
            'label': s.label,
            'workflow_id': str(s.workflow_id) if s.workflow_id else None,
            'message_count': s.message_count,
            'preview': s.preview,
            'created_at': s.created_at.isoformat(),
            'updated_at': s.updated_at.isoformat(),
        } for s in sessions],
        'count': sessions.count(),
    })


@api_view(['POST'])
@permission_classes([AllowAny])
def chatbot_create_session(request, project_id):
    """Create a new chatbot session."""
    from .models import ChatbotSession
    project = IntelliDocProject.objects.get(project_id=project_id)
    workflow_id = request.data.get('workflow_id')
    label = request.data.get('label', 'New Conversation')

    session = ChatbotSession.objects.create(
        project=project,
        workflow_id=workflow_id,
        label=label,
        conversation_history=[],
    )

    return Response({
        'id': str(session.session_id),
        'label': session.label,
        'workflow_id': str(session.workflow_id) if session.workflow_id else None,
        'message_count': 0,
        'created_at': session.created_at.isoformat(),
    }, status=201)


@api_view(['DELETE'])
@permission_classes([AllowAny])
def chatbot_delete_session(request, project_id, session_id):
    """Delete a chatbot session."""
    from .models import ChatbotSession
    ChatbotSession.objects.filter(
        project__project_id=project_id,
        session_id=session_id,
    ).delete()
    return Response({'status': 'deleted'})


@api_view(['PATCH'])
@permission_classes([AllowAny])
def chatbot_rename_session(request, project_id, session_id):
    """Rename a chatbot session."""
    from .models import ChatbotSession
    label = request.data.get('label', '').strip()
    if not label:
        return Response({'error': 'label is required'}, status=400)

    ChatbotSession.objects.filter(
        project__project_id=project_id,
        session_id=session_id,
    ).update(label=label, updated_at=timezone.now())
    return Response({'status': 'renamed', 'label': label})


@api_view(['GET'])
@permission_classes([AllowAny])
def chatbot_messages(request, project_id, session_id):
    """Get conversation history for a session."""
    from .models import ChatbotSession
    try:
        session = ChatbotSession.objects.get(
            project__project_id=project_id,
            session_id=session_id,
        )
        return Response({
            'session_id': str(session.session_id),
            'messages': session.conversation_history or [],
            'message_count': session.message_count,
        })
    except ChatbotSession.DoesNotExist:
        return Response({'messages': [], 'message_count': 0})


@api_view(['POST'])
@permission_classes([AllowAny])
def chatbot_send_message(request, project_id, session_id):
    """Send a message and get a response from the workflow.

    The user's message is processed through the project's workflow.
    The full conversation history is passed so agents have context.
    """
    from .models import ChatbotSession, AgentWorkflow

    user_message = request.data.get('message', '').strip()
    if not user_message:
        return Response({'error': 'message is required'}, status=400)

    try:
        project = IntelliDocProject.objects.get(project_id=project_id)
        session = ChatbotSession.objects.get(
            project=project,
            session_id=session_id,
        )

        # Get the workflow
        workflow_id = session.workflow_id
        if not workflow_id:
            return Response({'error': 'No workflow selected for this session'}, status=400)

        workflow = AgentWorkflow.objects.get(workflow_id=workflow_id, project=project)

        # Add user message to history
        user_entry = {
            'role': 'user',
            'content': user_message,
            'timestamp': timezone.now().isoformat(),
        }
        history = session.conversation_history or []
        history.append(user_entry)

        # Build full conversation history string (same format as deployment executor)
        full_conversation = '\n'.join([
            f"{'User' if m['role'] == 'user' else 'Assistant'}: {m['content']}"
            for m in history[-20:]  # Last 20 turns for context window
        ])

        # Execute workflow using the same pattern as the deployment executor:
        # 1. Deep copy graph
        # 2. Set Start Node prompt = full conversation history
        # 3. Pass deployment_context with current_user_query
        # 4. Extract response from End Node's predecessor agent
        import copy
        graph = copy.deepcopy(workflow.graph_json or {})

        # Set Start Node prompt to full conversation history
        for node in graph.get('nodes', []):
            if node.get('type') == 'StartNode':
                node.setdefault('data', {})['prompt'] = full_conversation
                break

        original_graph = workflow.graph_json
        workflow.graph_json = graph

        deployment_context = {
            'is_deployment': True,
            'current_user_query': user_message,
            'session_id': str(session.session_id),
        }

        start_time = time.time()
        try:
            from .conversation_orchestrator import ConversationOrchestrator
            from core.desktop_auth_middleware import get_desktop_user

            orchestrator = ConversationOrchestrator()
            user = get_desktop_user()

            async def _execute():
                return await orchestrator.execute_workflow(
                    workflow, user, deployment_context=deployment_context
                )

            result = async_to_sync(_execute)()
            workflow.graph_json = original_graph

            # Extract response using conversation_history (same as deployment_executor)
            # The conversation_history string contains the FULL execution output
            # including tool results and synthesis, while messages[] only has 3-4 entries
            assistant_response = ''
            if isinstance(result, dict):
                # Primary: parse conversation_history string
                # Format: "Start Node: query\nAgentName: response text"
                conv_hist = result.get('conversation_history', '')
                if conv_hist:
                    # Find the End Node's predecessor agent name
                    graph_nodes = graph.get('nodes', [])
                    graph_edges = graph.get('edges', [])
                    end_nodes = [n for n in graph_nodes if n.get('type') == 'EndNode']
                    pred_name = None
                    if end_nodes:
                        end_id = end_nodes[0].get('id')
                        pred_ids = [e['source'] for e in graph_edges if e.get('target') == end_id]
                        if pred_ids:
                            for n in graph_nodes:
                                if n.get('id') == pred_ids[0]:
                                    pred_name = n.get('data', {}).get('name', '')
                                    break

                    if pred_name:
                        # Extract the LAST occurrence of "AgentName: ..." from conversation_history
                        marker = f"{pred_name}: "
                        last_idx = conv_hist.rfind(marker)
                        if last_idx >= 0:
                            assistant_response = conv_hist[last_idx + len(marker):].strip()

                    # Fallback: get everything after the last agent line (not Start Node)
                    if not assistant_response:
                        lines = conv_hist.split('\n')
                        for line in reversed(lines):
                            if line.startswith('Start Node:'):
                                continue
                            if ':' in line:
                                assistant_response = line.split(':', 1)[1].strip()
                                break

                # Fallback: direct result fields
                if not assistant_response:
                    assistant_response = (
                        result.get('final_response', '') or
                        result.get('response', '') or
                        result.get('text', '') or
                        'I was unable to generate a response.'
                    )

            elif isinstance(result, str):
                assistant_response = result

            if not assistant_response:
                assistant_response = 'I was unable to generate a response. Please try again.'

            # Clean ALL citation block variants from the response
            import re
            # Catch all variants: ---CITATIONS---, **CITATIONS---, ### CITATIONS---, etc.
            # Pattern: anything containing CITATIONS as a header, through END_CITATIONS
            assistant_response = re.sub(
                r'[\-\*#\s]*CITATIONS[\-\*#\s]*\n?\[.*?END_CITATIONS[\-\*#\s]*',
                '', assistant_response, flags=re.DOTALL
            )
            # Fallback: catch ---CITATIONS--- ... ---END_CITATIONS--- (strict)
            assistant_response = re.sub(
                r'---\s*CITATIONS\s*---.*?---\s*END_CITATIONS\s*---',
                '', assistant_response, flags=re.DOTALL
            )
            # Remove "=== Grounded source references..."
            assistant_response = re.sub(
                r'===\s*Grounded source references.*$',
                '', assistant_response, flags=re.DOTALL
            )
            # Remove any trailing ---  or *** separators
            assistant_response = re.sub(r'\n---+\s*$', '', assistant_response)
            assistant_response = re.sub(r'\n\*\*\*+\s*$', '', assistant_response)
            assistant_response = assistant_response.rstrip()

            # Extract citations from multiple sources
            citations_list = []
            if isinstance(result, dict):
                # Source 1: message metadata
                for msg in result.get('messages', []):
                    msg_meta = msg.get('metadata', {})
                    if isinstance(msg_meta, dict) and msg_meta.get('citations'):
                        citations_list.extend(msg_meta['citations'])

                # Source 2: direct result field
                if not citations_list and result.get('citations'):
                    citations_list = result['citations']

                # Source 3: parse from conversation_history's grounded references block
                if not citations_list:
                    conv_hist = result.get('conversation_history', '')
                    grounded_idx = conv_hist.find('=== Grounded source references')
                    if grounded_idx >= 0:
                        grounded_block = conv_hist[grounded_idx:]
                        import re as _re
                        # Pattern: [N] DocTitle (location): "quoted text"
                        for match in _re.finditer(r'\[(\d+)\]\s+(.+?)(?:\s*\(([^)]*)\))?\s*:\s*"([^"]*)"', grounded_block):
                            citations_list.append({
                                'ref': int(match.group(1)),
                                'document_title': match.group(2).strip(),
                                'section': match.group(3) or '',
                                'quoted_text': match.group(4).strip(),
                            })

            elapsed_ms = int((time.time() - start_time) * 1000)

        except Exception as exec_err:
            workflow.graph_json = original_graph  # Restore on error
            logger.error(f"❌ CHATBOT: Workflow execution failed: {exec_err}")
            import traceback
            logger.error(traceback.format_exc())
            assistant_response = f'Error executing workflow: {str(exec_err)}'
            elapsed_ms = int((time.time() - start_time) * 1000)

        # Add assistant response to history
        assistant_entry = {
            'role': 'assistant',
            'content': assistant_response,
            'timestamp': timezone.now().isoformat(),
            'elapsed_ms': elapsed_ms,
        }
        if citations_list:
            assistant_entry['citations'] = citations_list
        history.append(assistant_entry)

        # Persist — use first user message as session label
        session.conversation_history = history
        session.message_count = len([m for m in history if m['role'] == 'user'])
        session.preview = user_message[:80]
        if session.message_count == 1 or session.label.startswith('Chat '):
            session.label = user_message[:50]
        session.updated_at = timezone.now()
        session.save(update_fields=['conversation_history', 'message_count', 'preview', 'label', 'updated_at'])

        return Response({
            'response': assistant_response,
            'elapsed_ms': elapsed_ms,
            'message_count': session.message_count,
            'citations': citations_list,
        })

    except IntelliDocProject.DoesNotExist:
        return Response({'error': 'Project not found'}, status=404)
    except ChatbotSession.DoesNotExist:
        return Response({'error': 'Session not found'}, status=404)
    except AgentWorkflow.DoesNotExist:
        return Response({'error': 'Workflow not found'}, status=404)
    except Exception as e:
        logger.error(f"CHATBOT: Error: {e}")
        return Response({'error': str(e)}, status=500)
