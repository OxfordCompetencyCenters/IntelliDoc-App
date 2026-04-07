"""
Delegation Message Protocol - Robust Message Passing Between GCM and Delegates

Defines structured message formats and protocol for communication between
Group Chat Manager and Delegate agents.
"""

import logging
import json
import uuid
from typing import Dict, List, Any, Optional
from datetime import datetime
from enum import Enum

logger = logging.getLogger('agent_orchestration.message_protocol')


class MessageType(Enum):
    """Message types in the delegation protocol"""
    DELEGATION = 'delegation'
    RESPONSE = 'response'
    ACKNOWLEDGMENT = 'acknowledgment'
    ERROR = 'error'


class DelegationStatus(Enum):
    """Status values for delegation messages"""
    ACCEPTED = 'accepted'
    REJECTED = 'rejected'
    REQUIRES_CLARIFICATION = 'requires_clarification'
    IN_PROGRESS = 'in_progress'
    COMPLETED = 'completed'
    ERROR = 'error'


class DelegationMessageProtocol:
    """
    Protocol handler for delegation messages between GCM and Delegates
    """
    
    @staticmethod
    def create_delegation_message(
        subquery: str,
        subquery_id: str,
        priority: str = 'medium',
        original_input: str = '',
        related_subqueries: Optional[List[str]] = None,
        iteration: int = 1,
        delegation_confidence: float = 1.0
    ) -> Dict[str, Any]:
        """
        Create a structured delegation message
        
        Args:
            subquery: The subquery to delegate
            subquery_id: Unique identifier for this subquery
            priority: Priority level (high/medium/low)
            original_input: Original input that generated this subquery
            related_subqueries: List of related subquery IDs
            iteration: Current iteration number
            delegation_confidence: Confidence score for this delegation
            
        Returns:
            Structured delegation message dictionary
        """
        message = {
            'type': MessageType.DELEGATION.value,
            'subquery_id': subquery_id,
            'subquery': subquery,
            'priority': priority,
            'context': {
                'original_input': original_input,
                'related_subqueries': related_subqueries or [],
                'iteration': iteration
            },
            'metadata': {
                'timestamp': datetime.now().isoformat(),
                'delegation_confidence': delegation_confidence,
                'message_id': str(uuid.uuid4())
            }
        }
        
        logger.debug(f"📨 MESSAGE PROTOCOL: Created delegation message for subquery {subquery_id[:8]}")
        return message
    
    @staticmethod
    def create_acknowledgment_message(
        subquery_id: str,
        delegate_name: str,
        status: str,
        message: str = ''
    ) -> Dict[str, Any]:
        """
        Create an acknowledgment message from delegate
        
        Args:
            subquery_id: The subquery ID being acknowledged
            delegate_name: Name of the delegate
            status: Acknowledgment status (accepted/rejected/requires_clarification)
            message: Optional message from delegate
            
        Returns:
            Structured acknowledgment message dictionary
        """
        ack_message = {
            'type': MessageType.ACKNOWLEDGMENT.value,
            'subquery_id': subquery_id,
            'delegate_name': delegate_name,
            'status': status,
            'message': message,
            'metadata': {
                'timestamp': datetime.now().isoformat(),
                'message_id': str(uuid.uuid4())
            }
        }
        
        logger.debug(f"📨 MESSAGE PROTOCOL: Created acknowledgment from {delegate_name} for {subquery_id[:8]}")
        return ack_message
    
    @staticmethod
    def create_response_message(
        subquery_id: str,
        delegate_name: str,
        response: str,
        status: str = 'completed',
        confidence: float = 1.0,
        tokens_used: Optional[int] = None,
        response_time_ms: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Create a response message from delegate
        
        Args:
            subquery_id: The subquery ID being responded to
            delegate_name: Name of the delegate
            response: The response text
            status: Response status (completed/in_progress/error)
            confidence: Confidence score for the response
            tokens_used: Number of tokens used
            response_time_ms: Response time in milliseconds
            
        Returns:
            Structured response message dictionary
        """
        response_message = {
            'type': MessageType.RESPONSE.value,
            'subquery_id': subquery_id,
            'delegate_name': delegate_name,
            'response': response,
            'status': status,
            'confidence': confidence,
            'metadata': {
                'tokens_used': tokens_used,
                'response_time_ms': response_time_ms,
                'timestamp': datetime.now().isoformat(),
                'message_id': str(uuid.uuid4())
            }
        }
        
        logger.debug(f"📨 MESSAGE PROTOCOL: Created response from {delegate_name} for {subquery_id[:8]}")
        return response_message
    
    @staticmethod
    def create_error_message(
        subquery_id: str,
        delegate_name: str,
        error_type: str,
        error_message: str,
        retryable: bool = False
    ) -> Dict[str, Any]:
        """
        Create an error message
        
        Args:
            subquery_id: The subquery ID that caused the error
            delegate_name: Name of the delegate (if applicable)
            error_type: Type of error
            error_message: Error message
            retryable: Whether the error is retryable
            
        Returns:
            Structured error message dictionary
        """
        error_msg = {
            'type': MessageType.ERROR.value,
            'subquery_id': subquery_id,
            'delegate_name': delegate_name,
            'error_type': error_type,
            'error_message': error_message,
            'retryable': retryable,
            'metadata': {
                'timestamp': datetime.now().isoformat(),
                'message_id': str(uuid.uuid4())
            }
        }
        
        logger.debug(f"📨 MESSAGE PROTOCOL: Created error message for {subquery_id[:8]}: {error_type}")
        return error_msg
    
    @staticmethod
    def validate_message(message: Dict[str, Any]) -> tuple[bool, Optional[str]]:
        """
        Validate a message structure
        
        Args:
            message: Message dictionary to validate
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        if not isinstance(message, dict):
            return False, "Message must be a dictionary"
        
        # Check required fields based on message type
        msg_type = message.get('type')
        if not msg_type:
            return False, "Message missing 'type' field"
        
        if msg_type == MessageType.DELEGATION.value:
            required_fields = ['subquery_id', 'subquery', 'priority', 'context', 'metadata']
            for field in required_fields:
                if field not in message:
                    return False, f"Delegation message missing required field: {field}"
            
            # Validate priority
            if message['priority'] not in ['high', 'medium', 'low']:
                return False, f"Invalid priority: {message['priority']}"
        
        elif msg_type == MessageType.ACKNOWLEDGMENT.value:
            required_fields = ['subquery_id', 'delegate_name', 'status']
            for field in required_fields:
                if field not in message:
                    return False, f"Acknowledgment message missing required field: {field}"
            
            # Validate status
            valid_statuses = ['accepted', 'rejected', 'requires_clarification']
            if message['status'] not in valid_statuses:
                return False, f"Invalid acknowledgment status: {message['status']}"
        
        elif msg_type == MessageType.RESPONSE.value:
            required_fields = ['subquery_id', 'delegate_name', 'response', 'status']
            for field in required_fields:
                if field not in message:
                    return False, f"Response message missing required field: {field}"
            
            # Validate status
            valid_statuses = ['completed', 'in_progress', 'error']
            if message['status'] not in valid_statuses:
                return False, f"Invalid response status: {message['status']}"
        
        elif msg_type == MessageType.ERROR.value:
            required_fields = ['subquery_id', 'error_type', 'error_message']
            for field in required_fields:
                if field not in message:
                    return False, f"Error message missing required field: {field}"
        
        else:
            return False, f"Unknown message type: {msg_type}"
        
        return True, None
    
    @staticmethod
    def parse_delegate_response(response_text: str) -> Optional[Dict[str, Any]]:
        """
        Parse a delegate response text to extract structured message
        
        Args:
            response_text: Raw response text from delegate
            
        Returns:
            Parsed message dictionary or None if parsing fails
        """
        if not response_text or not response_text.strip():
            return None
        
        # Try to extract JSON from response
        try:
            # Look for JSON in the response
            response_text = response_text.strip()
            
            # Try to find JSON object or array
            json_start = response_text.find('{')
            json_end = response_text.rfind('}')
            
            if json_start != -1 and json_end != -1:
                json_text = response_text[json_start:json_end + 1]
                parsed = json.loads(json_text)
                if isinstance(parsed, dict) and 'type' in parsed:
                    return parsed
            
            # If no structured message found, treat as plain response
            return {
                'type': MessageType.RESPONSE.value,
                'response': response_text,
                'status': 'completed',
                'parsed_from_text': True
            }
            
        except json.JSONDecodeError:
            # Not JSON, treat as plain response
            return {
                'type': MessageType.RESPONSE.value,
                'response': response_text,
                'status': 'completed',
                'parsed_from_text': True
            }
        except Exception as e:
            logger.error(f"❌ MESSAGE PROTOCOL: Error parsing delegate response: {e}")
            return None
    
    @staticmethod
    def format_message_for_delegate(message: Dict[str, Any]) -> str:
        """
        Format a message for sending to a delegate (human-readable format)
        
        Args:
            message: Message dictionary
            
        Returns:
            Formatted string for delegate
        """
        if message.get('type') == MessageType.DELEGATION.value:
            formatted = f"""=== DELEGATION REQUEST ===

Subquery ID: {message['subquery_id']}
Priority: {message['priority'].upper()}

Task:
{message['subquery']}

Context:
- Original Input: {message['context'].get('original_input', 'N/A')}
- Related Subqueries: {len(message['context'].get('related_subqueries', []))} related
- Iteration: {message['context'].get('iteration', 1)}

Please process this subquery and provide your response.
"""
            return formatted
        
        # For other message types, return JSON representation
        return json.dumps(message, indent=2)
    
    @staticmethod
    def handle_message_error(message: Dict[str, Any], error: Exception) -> Dict[str, Any]:
        """
        Handle message processing errors
        
        Args:
            message: The message that caused the error
            error: The exception that occurred
            
        Returns:
            Error message dictionary
        """
        subquery_id = message.get('subquery_id', 'unknown')
        error_type = type(error).__name__
        error_message = str(error)
        
        # Determine if error is retryable
        retryable = isinstance(error, (TimeoutError, ConnectionError))
        
        logger.error(f"❌ MESSAGE PROTOCOL: Error processing message {subquery_id[:8]}: {error_type}: {error_message}")
        
        return DelegationMessageProtocol.create_error_message(
            subquery_id=subquery_id,
            delegate_name=message.get('delegate_name', 'unknown'),
            error_type=error_type,
            error_message=error_message,
            retryable=retryable
        )

