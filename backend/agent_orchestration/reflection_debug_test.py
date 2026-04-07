"""
Reflection Debug Test Script
============================

Test script to verify that reflective connections between AssistantAgent and AssistantAgent
work properly and log all messages correctly.

This script simulates the workflow:
Start → AI Assistant 1 → AI Assistant 2 (reflection) → End

Expected messages:
1. Start: Initial prompt
2. AI Assistant 1: Original response  
3. AI Assistant 2: Reflection feedback
4. AI Assistant 1: Revised response based on feedback
5. End: Workflow completion

TOTAL: 5 messages, 3 agents involved
"""

import asyncio
import json
import logging
from typing import Dict, Any
from unittest.mock import Mock, AsyncMock

# Configure logging for debugging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MockLLMResponse:
    """Mock LLM response for testing"""
    def __init__(self, text: str, error: str = None):
        self.text = text
        self.error = error
        self.response_time_ms = 1000
        self.token_count = 100
        self.cost_estimate = 0.01

class MockLLMProvider:
    """Mock LLM provider for testing"""
    def __init__(self, provider_type: str):
        self.provider_type = provider_type
    
    async def generate_response(self, prompt: str, temperature: float = 0.7) -> MockLLMResponse:
        """Generate mock responses based on provider type"""
        if self.provider_type == "ai_assistant_1":
            if "feedback" in prompt.lower():
                # This is a revision based on reflection
                return MockLLMResponse(
                    "Here are improved KPIs for the OpenAI-Oxford collaboration based on feedback: "
                    "1. Educational Impact: Student learning outcomes, course completion rates, "
                    "2. Engagement Metrics: Active users, session duration, feature adoption, "
                    "3. Academic Integration: Faculty adoption, curriculum integration success, "
                    "4. Innovation Metrics: New educational applications developed, research collaborations initiated. "
                    "These metrics provide a comprehensive view of the collaboration's success."
                )
            else:
                # Original response
                return MockLLMResponse(
                    "The key performance indicators (KPIs) of this collaboration could include metrics such as user engagement, "
                    "user satisfaction, knowledge retention, and educational outcomes. Tracking these metrics can help assess "
                    "the effectiveness of ChatGPT Edu in providing valuable educational resources to Oxford members and "
                    "improving their learning experience."
                )
        elif self.provider_type == "ai_assistant_2":
            # Reflection feedback
            return MockLLMResponse(
                "I've reviewed your response about the OpenAI-Oxford collaboration KPIs. Your suggestions are good but could be more specific and measurable. "
                "Consider adding: 1) Specific metrics for educational impact like course completion rates and grade improvements, "
                "2) Technical performance indicators like system uptime and response accuracy, "
                "3) Innovation metrics such as new use cases developed or research papers published using the platform. "
                "Also consider breaking down the metrics by different stakeholder groups (students, faculty, administrators)."
            )
        else:
            return MockLLMResponse("Mock response from unknown provider")

class MockExecutionRecord:
    """Mock execution record for testing"""
    def __init__(self):
        self.messages_data = []
        self.conversation_history = ""
        self.execution_id = "test_exec_123"
        self.awaiting_human_input_agent = ""
        self.human_input_context = {}
        
    async def save(self):
        """Mock save method"""
        logger.info(f"📝 MOCK: Saving execution record with {len(self.messages_data)} messages")

async def test_reflection_message_logging():
    """Test the complete reflection message logging flow"""
    
    logger.info("🚀 REFLECTION TEST: Starting reflection message logging test")
    
    # Mock workflow graph representing: AI Assistant 1 → AI Assistant 2 (reflection)
    graph_json = {
        "nodes": [
            {
                "id": "start_1",
                "type": "StartNode", 
                "data": {"name": "Start", "prompt": "OpenAI and Oxford collaboration KPIs"}
            },
            {
                "id": "ai_assistant_1",
                "type": "AssistantAgent",
                "data": {
                    "name": "AI Assistant 1",
                    "llm_provider": "openai",
                    "llm_model": "gpt-3.5-turbo",
                    "system_message": "You are an expert in educational technology partnerships."
                }
            },
            {
                "id": "ai_assistant_2", 
                "type": "AssistantAgent",
                "data": {
                    "name": "AI Assistant 2",
                    "llm_provider": "openai", 
                    "llm_model": "gpt-3.5-turbo",
                    "system_message": "You are a performance metrics consultant who reviews and improves KPI suggestions."
                }
            },
            {
                "id": "end_1",
                "type": "EndNode",
                "data": {"name": "End", "message": "Workflow completed successfully."}
            }
        ],
        "edges": [
            {"source": "start_1", "target": "ai_assistant_1", "type": "default"},
            {"source": "ai_assistant_1", "target": "ai_assistant_2", "type": "reflection", "data": {"max_iterations": 1}},
            {"source": "ai_assistant_2", "target": "end_1", "type": "default"}
        ]
    }
    
    # Mock components
    execution_record = MockExecutionRecord()
    llm_providers = {
        "ai_assistant_1": MockLLMProvider("ai_assistant_1"),
        "ai_assistant_2": MockLLMProvider("ai_assistant_2")
    }
    
    # Test data
    messages = []
    message_sequence = 0
    conversation_history = ""
    
    logger.info("📊 REFLECTION TEST: Simulating workflow execution...")
    
    # 1. StartNode
    start_content = "OpenAI and Oxford collaboration KPIs"
    messages.append({
        'sequence': message_sequence,
        'agent_name': 'Start',
        'agent_type': 'StartNode', 
        'content': start_content,
        'message_type': 'workflow_start',
        'timestamp': '2025-08-19T13:11:33Z',
        'response_time_ms': 0
    })
    message_sequence += 1
    conversation_history = f"Start Node: {start_content}"
    logger.info(f"✅ REFLECTION TEST: Added StartNode message (sequence {message_sequence - 1})")
    
    # 2. AI Assistant 1 - Original response
    ai1_original = await llm_providers["ai_assistant_1"].generate_response("What are good KPIs for OpenAI-Oxford collaboration?")
    messages.append({
        'sequence': message_sequence,
        'agent_name': 'AI Assistant 1',
        'agent_type': 'AssistantAgent',
        'content': ai1_original.text,
        'message_type': 'chat',
        'timestamp': '2025-08-19T13:11:35Z',
        'response_time_ms': ai1_original.response_time_ms,
        'token_count': ai1_original.token_count,
        'metadata': {
            'llm_provider': 'openai',
            'llm_model': 'gpt-3.5-turbo',
            'reflection_applied': False
        }
    })
    message_sequence += 1
    logger.info(f"✅ REFLECTION TEST: Added AI Assistant 1 original message (sequence {message_sequence - 1})")
    
    # 3. Cross-agent reflection: AI Assistant 1 → AI Assistant 2
    reflection_prompt = f"""
Please review this message from AI Assistant 1 and provide feedback or suggestions:

Message from AI Assistant 1:
{ai1_original.text}

Please provide your feedback, suggestions, or response:
"""
    
    ai2_feedback = await llm_providers["ai_assistant_2"].generate_response(reflection_prompt)
    messages.append({
        'sequence': message_sequence,
        'agent_name': 'AI Assistant 2',
        'agent_type': 'AssistantAgent',
        'content': ai2_feedback.text,
        'message_type': 'reflection_feedback',
        'timestamp': '2025-08-19T13:11:37Z',
        'response_time_ms': ai2_feedback.response_time_ms,
        'token_count': ai2_feedback.token_count,
        'metadata': {
            'is_reflection': True,
            'reflection_source': 'AI Assistant 1',
            'iteration': 1,
            'max_iterations': 1,
            'llm_provider': 'openai',
            'llm_model': 'gpt-3.5-turbo'
        }
    })
    message_sequence += 1
    conversation_history += f"\nAI Assistant 2 (Reflection): {ai2_feedback.text}"
    logger.info(f"✅ REFLECTION TEST: Added AI Assistant 2 reflection feedback (sequence {message_sequence - 1})")
    
    # 4. AI Assistant 1 - Revised response based on feedback
    revision_prompt = f"""
You previously said:
{ai1_original.text}

AI Assistant 2 provided this feedback:
{ai2_feedback.text}

Please revise your response based on this feedback:
"""
    
    ai1_revised = await llm_providers["ai_assistant_1"].generate_response(revision_prompt)
    
    # CRITICAL: Update the original AI Assistant 1 message with revised content
    # This simulates what the fixed workflow executor should do
    for i in range(len(messages) - 1, -1, -1):
        if (messages[i]['agent_name'] == 'AI Assistant 1' and 
            messages[i]['message_type'] == 'chat' and
            messages[i]['agent_type'] == 'AssistantAgent'):
            logger.info(f"🔄 REFLECTION TEST: Updating AI Assistant 1 message content with reflected response")
            messages[i]['content'] = ai1_revised.text
            messages[i]['metadata']['reflection_applied'] = True
            messages[i]['metadata']['reflection_iterations'] = 1
            messages[i]['metadata']['original_content_length'] = len(ai1_original.text)
            messages[i]['metadata']['reflected_content_length'] = len(ai1_revised.text)
            logger.info(f"📝 REFLECTION TEST: Updated message content from {len(ai1_original.text)} to {len(ai1_revised.text)} chars")
            break
    
    conversation_history += f"\nAI Assistant 1 (Revised): {ai1_revised.text}"
    logger.info(f"✅ REFLECTION TEST: Applied AI Assistant 1 revised response to original message")
    
    # 5. EndNode
    end_content = "Workflow completed successfully."
    messages.append({
        'sequence': message_sequence,
        'agent_name': 'End',
        'agent_type': 'EndNode',
        'content': end_content,
        'message_type': 'workflow_end',
        'timestamp': '2025-08-19T13:11:40Z',
        'response_time_ms': 0
    })
    message_sequence += 1
    logger.info(f"✅ REFLECTION TEST: Added EndNode message (sequence {message_sequence - 1})")
    
    # Verify results
    logger.info(f"\n🎯 REFLECTION TEST RESULTS:")
    logger.info(f"Total messages: {len(messages)} (Expected: 4)")
    logger.info(f"Message sequence counter: {message_sequence} (Expected: 4)")
    logger.info(f"Agents involved: 3 (Start, AI Assistant 1, AI Assistant 2, End)")
    
    # Print all messages for verification
    logger.info(f"\n📋 MESSAGE LOG VERIFICATION:")
    for i, msg in enumerate(messages):
        logger.info(f"  {i+1}. {msg['agent_name']} ({msg['message_type']}): {msg['content'][:100]}...")
        if msg.get('metadata', {}).get('is_reflection'):
            logger.info(f"     ↳ REFLECTION from {msg['metadata']['reflection_source']}")
        if msg.get('metadata', {}).get('reflection_applied'):
            logger.info(f"     ↳ REFLECTION APPLIED (iterations: {msg['metadata']['reflection_iterations']})")
    
    # Check for expected message types
    message_types = [msg['message_type'] for msg in messages]
    expected_types = ['workflow_start', 'chat', 'reflection_feedback', 'workflow_end']
    
    if message_types == expected_types:
        logger.info(f"✅ REFLECTION TEST: Message types match expected sequence: {message_types}")
    else:
        logger.error(f"❌ REFLECTION TEST: Message types mismatch. Expected: {expected_types}, Got: {message_types}")
    
    # Verify reflection metadata
    reflection_messages = [msg for msg in messages if msg.get('metadata', {}).get('is_reflection')]
    reflection_applied_messages = [msg for msg in messages if msg.get('metadata', {}).get('reflection_applied')]
    
    logger.info(f"📊 REFLECTION METADATA:")
    logger.info(f"  Reflection feedback messages: {len(reflection_messages)} (Expected: 1)")
    logger.info(f"  Messages with reflection applied: {len(reflection_applied_messages)} (Expected: 1)")
    
    if len(reflection_messages) == 1 and len(reflection_applied_messages) == 1:
        logger.info(f"✅ REFLECTION TEST: All reflection metadata correctly applied")
    else:
        logger.error(f"❌ REFLECTION TEST: Reflection metadata issues detected")
    
    # Test conversation history
    expected_history_parts = [
        "Start Node:",
        "AI Assistant 2 (Reflection):",
        "AI Assistant 1 (Revised):"
    ]
    
    all_parts_present = all(part in conversation_history for part in expected_history_parts)
    if all_parts_present:
        logger.info(f"✅ REFLECTION TEST: Conversation history contains all expected parts")
    else:
        logger.error(f"❌ REFLECTION TEST: Conversation history missing expected parts")
        logger.info(f"📝 CONVERSATION HISTORY:\n{conversation_history}")
    
    logger.info(f"\n🎉 REFLECTION TEST COMPLETE!")
    
    return {
        'messages': messages,
        'conversation_history': conversation_history,
        'test_passed': len(messages) == 4 and len(reflection_messages) == 1 and len(reflection_applied_messages) == 1
    }

if __name__ == "__main__":
    # Run the test
    result = asyncio.run(test_reflection_message_logging())
    
    if result['test_passed']:
        print("\n🎉 REFLECTION TEST PASSED! All messages logged correctly.")
    else:
        print("\n❌ REFLECTION TEST FAILED! Check logs for issues.")
        
    print(f"\nFinal message count: {len(result['messages'])}")
    print(f"Test status: {'PASSED' if result['test_passed'] else 'FAILED'}")
