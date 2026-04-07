"""
Message Converter Utility

Converts conversation_history string format to structured messages array
for LLM providers (OpenAI, Claude, Gemini native formats).
"""

import logging
from typing import List, Dict, Any, Optional, Tuple

logger = logging.getLogger(__name__)


def validate_messages_format(messages: List[Dict[str, Any]]) -> Tuple[bool, Optional[str]]:
    """
    Validate messages array format.
    
    Args:
        messages: List of message dicts to validate
        
    Returns:
        Tuple of (is_valid, error_message)
        - is_valid: True if messages are valid, False otherwise
        - error_message: Error description if invalid, None if valid
    
    Note:
        Supports both string content and array content (for file attachments).
        Array content is used by LLM providers for multi-modal inputs:
        - OpenAI: [{"type": "text", "text": "..."}, {"type": "file", ...}]
        - Claude: [{"type": "text", "text": "..."}, {"type": "document", ...}]
        - Gemini: [{"type": "text", "text": "..."}, {"type": "file_data", ...}]
    """
    if not isinstance(messages, list):
        return False, "Messages must be a list"
    
    if len(messages) == 0:
        return False, "Messages array cannot be empty"
    
    valid_roles = {'user', 'assistant', 'system', 'tool', 'function', 'model'}
    
    for i, msg in enumerate(messages):
        if not isinstance(msg, dict):
            return False, f"Message at index {i} must be a dictionary"
        
        if 'role' not in msg:
            return False, f"Message at index {i} missing required 'role' field"
        
        # tool/function result messages and assistant tool-call messages may
        # use 'parts', 'tool_call_id', or 'tool_calls' instead of 'content'
        role = msg.get('role')
        if 'content' not in msg and role not in ('tool', 'function', 'model'):
            if 'parts' not in msg and 'tool_calls' not in msg:
                return False, f"Message at index {i} missing required 'content' field"
        
        if not isinstance(role, str):
            return False, f"Message at index {i} has invalid 'role' type (must be string)"
        
        if role not in valid_roles:
            return False, f"Message at index {i} has invalid role '{role}'. Must be one of: {valid_roles}"
        
        content = msg.get('content')
        
        # Tool / function / model messages may carry data in 'parts',
        # 'tool_call_id', or 'tool_calls' instead of standard content.
        # Skip detailed content validation for these provider-specific roles.
        if role in ('tool', 'function', 'model'):
            continue
        
        # Assistant messages with tool_calls may have None content
        if content is None and role == 'assistant' and 'tool_calls' in msg:
            continue
        
        # Support both string and array content formats
        if isinstance(content, str):
            if len(content.strip()) == 0:
                logger.warning(f"⚠️ MESSAGE CONVERTER: Message at index {i} has empty content")
        elif isinstance(content, list):
            if len(content) == 0:
                return False, f"Message at index {i} has empty content array"
            
            for j, item in enumerate(content):
                if not isinstance(item, dict):
                    return False, f"Message at index {i}, content item {j} must be a dictionary"
                
                if 'type' not in item:
                    return False, f"Message at index {i}, content item {j} missing 'type' field"
                
                item_type = item.get('type')
                
                if item_type == 'text':
                    if 'text' not in item:
                        return False, f"Message at index {i}, content item {j} of type 'text' missing 'text' field"
                elif item_type in ('file', 'file_data', 'document', 'image', 'image_url', 'tool_use', 'tool_result'):
                    pass
                else:
                    logger.debug(f"ℹ️ MESSAGE CONVERTER: Unknown content type '{item_type}' at index {i}, item {j}")
        else:
            return False, f"Message at index {i} has invalid 'content' type (must be string or array)"
    
    return True, None


def agent_type_to_role(agent_type: str, agent_name: str = "", content: str = "") -> str:
    """
    Map agent type to LLM role (user, assistant, system)
    
    Args:
        agent_type: The agent type (e.g., 'UserProxyAgent', 'AssistantAgent')
        agent_name: Optional agent name for additional context
        content: Optional message content to detect instructions
        
    Returns:
        LLM role: 'user', 'assistant', or 'system'
    """
    agent_type_lower = agent_type.lower() if agent_type else ""
    agent_name_lower = agent_name.lower() if agent_name else ""
    content_lower = content.lower() if content else ""
    
    # UserProxyAgent maps to 'user' role
    if 'user' in agent_type_lower or 'proxy' in agent_type_lower:
        return 'user'
    
    # StartNode content is USER INPUT, not system message
    # Start nodes contain the user's initial prompt/input
    if 'start' in agent_type_lower or 'start' in agent_name_lower:
        return 'user'  # Changed from 'system' - Start node content is user input
    
    # End nodes are typically system-level, but their content might be user-facing
    # For now, keep as system, but could be adjusted based on content
    if 'end' in agent_type_lower or 'end' in agent_name_lower:
        return 'system'
    
    # Check if content is an instruction TO the assistant (should be user role)
    instruction_keywords = [
        'please provide your response',
        'please respond',
        'please analyze',
        'please process',
        'please answer',
        'please generate',
        'based on the conversation',
        'based on the above',
        'based on the history'
    ]
    if any(keyword in content_lower for keyword in instruction_keywords):
        return 'user'  # Instructions to the assistant are user messages
    
    # All other agents (AssistantAgent, DelegateAgent, GroupChatManager) map to 'assistant'
    return 'assistant'


def parse_conversation_history_to_messages(
    conversation_history: str,
    system_message: Optional[str] = None,
    include_system: bool = True
) -> List[Dict[str, str]]:
    """
    Parse conversation_history string to structured messages array for LLM providers.
    
    Converts format: "AgentName: message\nAgentName2: message"
    To format: [{"role": "user|assistant|system", "content": "message"}, ...]
    
    Args:
        conversation_history: Plain text conversation history string
        system_message: Optional system message to prepend
        include_system: Whether to include system message in output
        
    Returns:
        List of message dicts with 'role' and 'content' keys
    """
    if not conversation_history or not conversation_history.strip():
        messages = []
        if include_system and system_message:
            messages.append({"role": "system", "content": system_message})
        return messages
    
    messages = []
    
    # Add system message first if provided
    if include_system and system_message:
        messages.append({"role": "system", "content": system_message})
        
        # Debug logging for system message verification
        system_msg_length = len(system_message)
        has_documents = "RELEVANT DOCUMENTS" in system_message or "=== RELEVANT DOCUMENTS ===" in system_message
        system_msg_preview = system_message[:300] if len(system_message) > 300 else system_message
        
        logger.info(f"📚 MESSAGE CONVERTER DEBUG: System message length: {system_msg_length} chars")
        logger.info(f"📚 MESSAGE CONVERTER DEBUG: Contains document context marker: {has_documents}")
        if has_documents:
            logger.info(f"📚 MESSAGE CONVERTER DEBUG: System message preview (first 300 chars): {system_msg_preview}...")
        else:
            # This is expected when DocAware is disabled or all documents have failed extraction
            logger.debug(f"ℹ️ MESSAGE CONVERTER DEBUG: No document context markers - DocAware may be disabled or all documents filtered")
    
    # Parse conversation history
    lines = conversation_history.strip().split('\n')
    i = 0
    
    while i < len(lines):
        line = lines[i].strip()
        
        if not line:
            i += 1
            continue
        
        # Skip section markers
        if line.startswith('===') or line.startswith('---'):
            i += 1
            continue
        
        # Pattern: "AgentName: message content"
        if ':' in line:
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
                    
                    # Stop if we hit another agent message
                    if ':' in next_line and not next_line.startswith('===') and not next_line.startswith('---'):
                        # Check if it looks like an agent name (not just a colon in content)
                        potential_agent = next_line.split(':', 1)[0].strip()
                        if any(keyword in potential_agent.lower() for keyword in 
                               ['agent', 'assistant', 'manager', 'delegate', 'start', 'end', 'proxy', 'user']):
                            break
                    
                    # Handle empty lines
                    if not next_line:
                        consecutive_empty_lines += 1
                        if consecutive_empty_lines >= 2:
                            break
                        full_content.append('')
                    else:
                        consecutive_empty_lines = 0
                        full_content.append(next_line)
                    
                    j += 1
                
                i = j - 1
                content = '\n'.join(full_content)
                
                # Determine agent type from name
                agent_type = determine_agent_type(agent_name, content)
                
                # Map to LLM role (pass content to detect instructions)
                role = agent_type_to_role(agent_type, agent_name, content)
                
                # Only add non-empty messages
                if content.strip():
                    messages.append({
                        "role": role,
                        "content": content.strip()
                    })
        
        i += 1
    
    # Safety check: ensure at least one message exists
    if len(messages) == 0:
        logger.warning(f"⚠️ MESSAGE CONVERTER: All messages were filtered, adding default user message")
        default_message = {
            "role": "user",
            "content": "Please provide your response."
        }
        if include_system and system_message:
            # If we have system message, use it
            messages.append({"role": "system", "content": system_message})
        messages.append(default_message)
    
    # Validate messages format
    is_valid, error_msg = validate_messages_format(messages)
    if not is_valid:
        logger.error(f"❌ MESSAGE CONVERTER: Invalid messages format: {error_msg}")
        # Return minimal valid messages array
        return [{"role": "user", "content": "Please provide your response."}]
    
    logger.debug(f"📝 MESSAGE CONVERTER: Parsed {len(messages)} messages from conversation history")
    return messages


def determine_agent_type(agent_name: str, content: str = "") -> str:
    """
    Determine agent type from agent name and content.
    
    Args:
        agent_name: Name of the agent
        content: Optional message content for context
        
    Returns:
        Agent type string
    """
    name_lower = agent_name.lower()
    content_lower = content.lower() if content else ""
    
    # Check for specific agent types
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
    
    # Default to AssistantAgent
    return 'AssistantAgent'


def convert_messages_data_to_llm_format(
    messages_data: List[Dict[str, Any]],
    system_message: Optional[str] = None,
    include_system: bool = True
) -> List[Dict[str, str]]:
    """
    Convert messages_data array to LLM provider format.
    
    Args:
        messages_data: Array of message dicts with agent_name, agent_type, content
        system_message: Optional system message to prepend
        include_system: Whether to include system message
        
    Returns:
        List of message dicts with 'role' and 'content' keys
    """
    messages = []
    
    # Add system message first if provided
    if include_system and system_message:
        messages.append({"role": "system", "content": system_message})
    
    # Convert each message
    for msg in messages_data:
        agent_type = msg.get('agent_type', 'AssistantAgent')
        agent_name = msg.get('agent_name', '')
        content = msg.get('content', '')
        
        if not content or not content.strip():
            continue
        
        # Map agent type to role (pass content to detect instructions)
        role = agent_type_to_role(agent_type, agent_name, content)
        
        messages.append({
            "role": role,
            "content": content.strip()
        })
    
    # Safety check: ensure at least one message exists
    if len(messages) == 0:
        logger.warning(f"⚠️ MESSAGE CONVERTER: All messages were filtered, adding default user message")
        default_message = {
            "role": "user",
            "content": "Please provide your response."
        }
        if include_system and system_message:
            messages.append({"role": "system", "content": system_message})
        messages.append(default_message)
    
    # Validate messages format
    is_valid, error_msg = validate_messages_format(messages)
    if not is_valid:
        logger.error(f"❌ MESSAGE CONVERTER: Invalid messages format: {error_msg}")
        # Return minimal valid messages array
        return [{"role": "user", "content": "Please provide your response."}]
    
    logger.debug(f"📝 MESSAGE CONVERTER: Converted {len(messages)} messages from messages_data")
    return messages
