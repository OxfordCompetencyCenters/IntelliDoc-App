"""
Agent Orchestration WebSocket Consumer - Template Independent Real-time Updates

Provides real-time streaming of agent messages during workflow execution
PHASE 4: Enhanced with real workflow execution support, human input handling,
and execution status tracking.
"""

import json
import logging
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth.models import AnonymousUser

logger = logging.getLogger('agent_orchestration.websocket')

class AgentOrchestrationConsumer(AsyncWebsocketConsumer):
    """
    PHASE 4: Enhanced WebSocket consumer for real-time workflow execution
    
    Features:
    - Real-time agent message streaming
    - Human input request/response handling
    - Execution status updates
    - Error reporting and recovery
    """
    
    async def connect(self):
        """Handle WebSocket connection with enhanced Phase 4 features"""
        self.project_id = self.scope['url_route']['kwargs']['project_id']
        self.room_group_name = f'agent_orchestration_{self.project_id}'
        self.user = self.scope['user']
        
        # Check authentication
        if isinstance(self.user, AnonymousUser):
            logger.warning(f"🔒 WEBSOCKET: Anonymous user attempted to connect to project {self.project_id}")
            await self.close()
            return
        
        # Verify user has access to this project
        has_access = await self.check_project_access()
        if not has_access:
            logger.warning(f"🔒 WEBSOCKET: User {self.user.email} denied access to project {self.project_id}")
            await self.close()
            return
        
        # Join room group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        
        await self.accept()
        
        logger.info(f"🔌 WEBSOCKET: User {self.user.email} connected to project {self.project_id}")
        
        # Send connection confirmation with Phase 4 capabilities
        await self.send(text_data=json.dumps({
            'type': 'workflow_connected',
            'project_id': self.project_id,
            'timestamp': 'now',
            'message': 'Connected to real-time workflow execution',
            'capabilities': {
                'real_time_messaging': True,
                'human_input_support': True,
                'code_execution': True,
                'multi_provider_llm': True,
                'execution_status': True,
                'error_recovery': True
            }
        }))
    
    async def disconnect(self, close_code):
        """Handle WebSocket disconnection"""
        # Leave room group
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )
        
        logger.info(f"🔌 WEBSOCKET: User {self.user.email if self.user else 'Unknown'} disconnected from project {self.project_id}")
    
    async def receive(self, text_data):
        """Handle messages from WebSocket (Phase 4 enhanced bi-directional communication)"""
        try:
            data = json.loads(text_data)
            message_type = data.get('type')
            
            if message_type == 'ping':
                # Respond to ping with pong
                await self.send(text_data=json.dumps({
                    'type': 'pong',
                    'timestamp': data.get('timestamp')
                }))
                
            elif message_type == 'human_input_response':
                # Handle human input response for UserProxyAgent
                await self.handle_human_input_response(data)
                
            elif message_type == 'execution_control':
                # Handle execution control commands (pause, resume, stop)
                await self.handle_execution_control(data)
                
            else:
                logger.warning(f"⚠️ WEBSOCKET: Unknown message type: {message_type}")
                
        except json.JSONDecodeError:
            logger.error("❌ WEBSOCKET: Invalid JSON received")
        except Exception as e:
            logger.error(f"❌ WEBSOCKET: Error processing message: {e}")
    
    async def agent_message(self, event):
        """Send agent message to WebSocket"""
        await self.send(text_data=json.dumps({
            'type': 'agent_message',
            'agent_name': event['agent_name'],
            'agent_type': event['agent_type'],
            'content': event['content'],
            'message_type': event['message_type'],
            'sequence_number': event['sequence_number'],
            'timestamp': event['timestamp'],
            'response_time_ms': event.get('response_time_ms'),
            'token_count': event.get('token_count')
        }))
    
    async def execution_status(self, event):
        """Send execution status update to WebSocket (Phase 4)"""
        await self.send(text_data=json.dumps({
            'type': 'execution_status',
            'status': event['status'],
            'message': event['message'],
            'progress': event.get('progress', 0),
            'timestamp': event['timestamp']
        }))
    
    async def human_input_request(self, event):
        """Request human input from connected user"""
        await self.send(text_data=json.dumps({
            'type': 'human_input_request',
            'agent_name': event['agent_name'],
            'prompt': event['prompt'],
            'run_id': event['run_id'],
            'timeout_seconds': event.get('timeout_seconds', 300),
            'timestamp': event['timestamp']
        }))
    
    async def handle_human_input_response(self, data):
        """
        Handle human input response (Phase 4).
        Human input for deployed workflows is delivered via the HTTP submit-input API
        (POST /api/workflow-deploy/<project_id>/submit-input/), not via WebSocket.
        This handler acknowledges receipt only; workflow resume uses the HTTP API.
        """
        run_id = data.get('run_id')
        request_id = data.get('request_id')
        user_input = data.get('input', '')
        
        if request_id and user_input:
            logger.info(f"👤 WEBSOCKET: Human input received for request {request_id}: {user_input[:50]}...")
            
            # Acknowledge receipt (deployed chat uses HTTP submit-input for actual resume)
            await self.send(text_data=json.dumps({
                'type': 'human_input_acknowledged',
                'request_id': request_id,
                'message': 'Input received (use HTTP submit-input API for deployment resume)',
                'timestamp': 'now'
            }))
    
    async def handle_execution_control(self, data):
        """
        Handle execution control commands (Phase 4).
        Pause/resume/stop are not implemented over WebSocket; deployment uses
        HTTP chat and submit-input only. This handler acknowledges receipt only.
        """
        command = data.get('command')
        run_id = data.get('run_id')
        
        logger.info(f"🎮 WEBSOCKET: Execution control received: {command} for run {run_id}")
        
        # Acknowledge command (execution control not implemented over WebSocket)
        await self.send(text_data=json.dumps({
            'type': 'execution_control_acknowledged',
            'command': command,
            'run_id': run_id,
            'message': f'Command {command} received',
            'timestamp': 'now'
        }))
    
    @database_sync_to_async
    def check_project_access(self):
        """Check if user has access to the project using proper permission system"""
        try:
            from users.models import IntelliDocProject
            
            project = IntelliDocProject.objects.get(project_id=self.project_id)
            # Use proper permission system that handles admin, shared projects, and group permissions
            return project.has_user_access(self.user)
            
        except IntelliDocProject.DoesNotExist:
            return False
        except Exception as e:
            logger.error(f"❌ WEBSOCKET: Error checking project access: {e}")
            return False

# ============================================================================
# WebSocket URL Routing (to be added to routing.py)
# ============================================================================

# from django.urls import re_path
# from . import consumers

# websocket_urlpatterns = [
#     re_path(r'ws/agent_orchestration/(?P<project_id>[^/]+)/$', consumers.AgentOrchestrationConsumer.as_asgi()),
# ]
