"""
Prompt Generation Service - LLM-Based Automatic System Prompt Generation

Generates detailed, context-aware system prompts from simple user-provided agent descriptions
using the agent's configured LLM provider.
"""

import logging
import hashlib
import json
from typing import Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
from asgiref.sync import sync_to_async

from users.models import IntelliDocProject
from .llm_provider_manager import LLMProviderManager

logger = logging.getLogger('agent_orchestration.prompt_generation')

# Simple in-memory cache (can be upgraded to Redis later)
_prompt_cache: Dict[str, Dict[str, Any]] = {}
CACHE_DURATION_HOURS = 24


class PromptGenerationService:
    """
    Service for generating detailed system prompts from simple agent descriptions
    """
    
    def __init__(self):
        self.llm_provider_manager = LLMProviderManager()
        logger.info("🔧 PROMPT GENERATION SERVICE: Initialized")
    
    async def generate_prompt_from_description(
        self,
        description: str,
        agent_type: str,
        doc_aware: bool,
        project: Optional[IntelliDocProject],
        llm_provider: str = 'openai',
        llm_model: str = 'gpt-4',
        project_capabilities: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Generate a detailed system prompt from a simple agent description
        
        Args:
            description: Simple user-provided description of the agent
            agent_type: Type of agent (AssistantAgent, DocumentAnalyzerAgent, etc.)
            doc_aware: Whether DocAware capabilities are enabled
            project: Project instance for API keys and context
            llm_provider: LLM provider to use for generation
            llm_model: LLM model to use
            project_capabilities: Project capabilities dict
            
        Returns:
            Dict with 'generated_prompt', 'success', 'error', 'metadata'
        """
        if not description or not description.strip():
            return {
                'success': False,
                'error': 'Description cannot be empty',
                'generated_prompt': None
            }
        
        description = description.strip()
        
        # Check cache first
        cache_key = self._generate_cache_key(description, agent_type, doc_aware)
        cached_result = self._get_from_cache(cache_key)
        if cached_result:
            logger.info(f"✅ PROMPT GEN: Using cached prompt for {agent_type}")
            return cached_result
        
        try:
            logger.info(f"🔧 PROMPT GEN: Generating prompt for {agent_type} with description: {description[:50]}...")
            
            # Build generation context
            generation_prompt = self._build_generation_prompt(
                description,
                agent_type,
                doc_aware,
                project_capabilities or {}
            )
            
            # Get LLM provider
            agent_config = {
                'llm_provider': llm_provider,
                'llm_model': llm_model
            }
            
            llm_provider_instance = await self.llm_provider_manager.get_llm_provider(
                agent_config,
                project
            )
            
            if not llm_provider_instance:
                logger.warning(f"⚠️ PROMPT GEN: No LLM provider available, falling back to template")
                return self._fallback_to_template(agent_type, doc_aware, description)
            
            # Generate prompt using LLM
            logger.info(f"🤖 PROMPT GEN: Calling LLM ({llm_provider}/{llm_model}) for prompt generation")
            
            # Use higher max_tokens to ensure comprehensive prompts (minimum 1500 tokens for 300-500 words)
            logger.info(f"🤖 PROMPT GEN: Calling LLM ({llm_provider}/{llm_model}) for prompt generation with max_tokens=1500")
            llm_response = await llm_provider_instance.generate_response(
                prompt=generation_prompt,
                max_tokens=1500,  # Increased from 800 to allow for comprehensive prompts
                temperature=0.7
            )
            
            if not llm_response or llm_response.error:
                error_msg = llm_response.error if llm_response else 'No response from LLM'
                logger.error(f"❌ PROMPT GEN: LLM generation failed: {error_msg}")
                return self._fallback_to_template(agent_type, doc_aware, description)
            
            generated_prompt = llm_response.text.strip() if llm_response.text else ''
            
            if not generated_prompt:
                logger.warning(f"⚠️ PROMPT GEN: Empty response from LLM, using fallback")
                return self._fallback_to_template(agent_type, doc_aware, description)
            
            # Log prompt length for debugging
            word_count = len(generated_prompt.split())
            char_count = len(generated_prompt)
            logger.info(f"📏 PROMPT GEN: Generated prompt length - {word_count} words, {char_count} characters")
            
            # Check if prompt is too short (less than 100 words suggests it's a one-liner)
            if word_count < 100:
                logger.warning(f"⚠️ PROMPT GEN: Generated prompt is too short ({word_count} words), expected at least 200 words. Regenerating with more explicit instructions...")
                # Try regenerating with even more explicit instructions
                enhanced_prompt = generation_prompt + "\n\nCRITICAL: The previous response was too short. Generate a MUCH MORE DETAILED prompt with at least 300 words. Expand extensively on every aspect of the agent's role, capabilities, and responsibilities. Include specific examples, detailed instructions, and comprehensive guidelines."
                retry_response = await llm_provider_instance.generate_response(
                    prompt=enhanced_prompt,
                    temperature=0.7,
                    max_tokens=2000  # Even higher for retry
                )
                if retry_response and retry_response.text and len(retry_response.text.strip().split()) >= 100:
                    generated_prompt = retry_response.text.strip()
                    word_count = len(generated_prompt.split())
                    logger.info(f"✅ PROMPT GEN: Retry generated {word_count} words")
            
            # Validate generated prompt
            validation_result = self._validate_generated_prompt(generated_prompt)
            if not validation_result['valid']:
                logger.warning(f"⚠️ PROMPT GEN: Validation failed: {validation_result['error']}, using fallback")
                return self._fallback_to_template(agent_type, doc_aware, description)
            
            # Enhance with DocAware instructions if needed
            if doc_aware:
                generated_prompt = self._enhance_with_docaware_instructions(generated_prompt)
            
            # Prepare result
            result = {
                'success': True,
                'generated_prompt': generated_prompt,
                'metadata': {
                    'generated_at': datetime.now().isoformat(),
                    'llm_provider': llm_provider,
                    'llm_model': llm_model,
                    'agent_type': agent_type,
                    'doc_aware': doc_aware,
                    'description_length': len(description),
                    'prompt_length': len(generated_prompt),
                    'tokens_used': llm_response.token_count or 0,
                    'response_time_ms': llm_response.response_time_ms or 0
                },
                'error': None
            }
            
            # Cache the result
            self._save_to_cache(cache_key, result)
            
            logger.info(f"✅ PROMPT GEN: Successfully generated prompt ({len(generated_prompt)} chars) for {agent_type}")
            return result
            
        except Exception as e:
            logger.error(f"❌ PROMPT GEN: Exception during generation: {e}")
            import traceback
            logger.error(f"❌ PROMPT GEN: Traceback: {traceback.format_exc()}")
            return self._fallback_to_template(agent_type, doc_aware, description)
    
    def _build_generation_prompt(
        self,
        description: str,
        agent_type: str,
        doc_aware: bool,
        project_capabilities: Dict[str, Any]
    ) -> str:
        """
        Build the prompt that will be sent to LLM to generate the system prompt
        """
        agent_type_context = self._get_agent_type_context(agent_type)
        project_context = self._get_project_context(project_capabilities)
        
        generation_prompt = f"""You are a system prompt generator for AI agents. Given a simple agent description, generate a comprehensive, detailed system prompt that:

1. Clearly defines the agent's role and responsibilities
2. Outlines specific capabilities and functions
3. Provides clear instructions for behavior
4. Includes best practices for the agent type
5. Is structured, actionable, and professional
6. Is MINIMUM 200 words, ideally 300-500 words - DO NOT create short one-liner prompts

IMPORTANT: The generated prompt must be DETAILED and COMPREHENSIVE. Expand significantly on the user's description. Include:
- Specific role definition
- Detailed capabilities and responsibilities
- Clear behavioral guidelines
- Examples of tasks the agent should handle
- Best practices for the agent type
- Any relevant context from the agent type

Agent Type: {agent_type}
Agent Type Context: {agent_type_context}

User Description: "{description}"

DocAware Enabled: {doc_aware}
Project Context: {project_context}

Generate a detailed, comprehensive system prompt that significantly expands on the user's description while maintaining focus and clarity. The prompt should be written in second person (e.g., "You are...", "Your responsibilities include...") and should be ready to use as a system message for the AI agent.

The prompt MUST be at least 200 words. Aim for 300-500 words for a comprehensive prompt that fully defines the agent's role and capabilities.

Return ONLY the generated system prompt, without any additional explanation or formatting."""
        
        return generation_prompt
    
    def _get_agent_type_context(self, agent_type: str) -> str:
        """Get context information about the agent type"""
        context_map = {
            'DocumentAnalyzerAgent': """This agent specializes in comprehensive document analysis. It should focus on:
- Analyzing document structure and organization
- Extracting key sections and important content
- Identifying document types and classifying content
- Assessing content complexity and processing requirements
- Providing detailed analysis reports""",
            
            'HierarchicalProcessorAgent': """This agent specializes in organizing and structuring document content. It should focus on:
- Creating logical document hierarchies
- Organizing content into meaningful levels
- Establishing relationships between sections
- Generating navigation structures
- Maintaining content integrity during organization""",
            
            'CategoryClassifierAgent': """This agent specializes in intelligent document categorization and tagging. It should focus on:
- Classifying documents into appropriate categories
- Assigning relevant content tags
- Determining subject areas and domains
- Assessing document importance and priority
- Supporting multi-label classification""",
            
            'ContentReconstructorAgent': """This agent specializes in rebuilding and organizing fragmented content. It should focus on:
- Reconstructing complete documents from chunks
- Merging related content sections
- Preserving original formatting and structure
- Maintaining content integrity and flow
- Generating coherent, complete documents""",
            
            'AssistantAgent': """This is a general-purpose AI assistant. It should be:
- Helpful, accurate, and context-aware
- Capable of handling various tasks and questions
- Clear and concise in communication
- Focused on providing actionable insights""",
            
            'UserProxyAgent': """This agent handles human interaction and code execution. It should focus on:
- Facilitating human-in-the-loop interactions
- Executing code when needed
- Requesting user input when required
- Managing code execution safely""",
            
            'GroupChatManager': """This agent coordinates multi-agent conversations. It should focus on:
- Facilitating smooth conversation flow between agents
- Ensuring all agents contribute their expertise
- Guiding the team toward task completion
- Summarizing results and insights
- Managing conversation context"""
        }
        
        return context_map.get(agent_type, "This is a general AI agent that should be helpful, accurate, and context-aware.")
    
    def _get_project_context(self, project_capabilities: Dict[str, Any]) -> str:
        """Get project-specific context"""
        context_parts = []
        
        if project_capabilities.get('supports_rag_agents'):
            context_parts.append("Project supports RAG (Retrieval-Augmented Generation) capabilities")
        
        if project_capabilities.get('supports_hierarchical_processing'):
            context_parts.append("Project supports hierarchical document processing")
        
        if project_capabilities.get('supports_agent_orchestration'):
            context_parts.append("Project supports multi-agent orchestration")
        
        if not context_parts:
            return "Standard project configuration"
        
        return "; ".join(context_parts)
    
    def _enhance_with_docaware_instructions(self, generated_prompt: str) -> str:
        """No-op: document access instructions are injected at runtime by the
        IntelliDoc platform prompt only when documents are actually available.
        Kept for backwards compatibility with callers."""
        return generated_prompt
    
    def _validate_generated_prompt(self, prompt: str) -> Dict[str, Any]:
        """Validate that the generated prompt is acceptable"""
        if not prompt or len(prompt.strip()) < 50:
            return {
                'valid': False,
                'error': 'Generated prompt is too short (minimum 50 characters)'
            }
        
        if len(prompt) > 2000:
            return {
                'valid': False,
                'error': 'Generated prompt is too long (maximum 2000 characters)'
            }
        
        # Check for basic structure (should contain "You are" or similar)
        prompt_lower = prompt.lower()
        if not any(phrase in prompt_lower for phrase in ['you are', 'your', 'this agent', 'the agent']):
            return {
                'valid': False,
                'error': 'Generated prompt does not appear to be a valid system prompt'
            }
        
        return {'valid': True, 'error': None}
    
    def _fallback_to_template(
        self,
        agent_type: str,
        doc_aware: bool,
        description: str
    ) -> Dict[str, Any]:
        """Fallback to template-based generation when LLM generation fails
        Creates a more comprehensive template-based prompt"""
        logger.info(f"🔄 PROMPT GEN: Using template fallback for {agent_type}")
        
        # Build comprehensive template-based prompt
        prompt_parts = []
        
        # Role definition
        if agent_type == 'DelegateAgent':
            prompt_parts.append(f"You are a specialized delegate agent.")
        elif agent_type == 'AssistantAgent':
            prompt_parts.append(f"You are a helpful AI assistant.")
        elif agent_type == 'GroupChatManager':
            prompt_parts.append(f"You are a Group Chat Manager responsible for coordinating multiple specialized agents.")
        else:
            prompt_parts.append(f"You are a {agent_type}.")
        
        # Add user description with expansion
        if description:
            prompt_parts.append(f"\n\nYour primary role and responsibilities:\n{description}")
            prompt_parts.append("\n\nYou should approach tasks with expertise and attention to detail, ensuring high-quality results.")
            prompt_parts.append("Be thorough and comprehensive in your analysis and responses.")
        else:
            prompt_parts.append("\n\nYou should be helpful, accurate, and context-aware in all your interactions.")
        
        # Add capabilities based on agent type
        if agent_type == 'DelegateAgent':
            prompt_parts.append("\n\nAs a delegate agent, you work under the coordination of a Group Chat Manager.")
            prompt_parts.append("You receive specific subqueries or tasks assigned to you based on your capabilities.")
            prompt_parts.append("Focus on providing detailed, specialized analysis for the tasks assigned to you.")
            prompt_parts.append("Be thorough and comprehensive in your responses, ensuring you address all aspects of the assigned task.")
        
        # DocAware note: capability instructions are injected at runtime by
        # the IntelliDoc platform prompt only when documents are actually
        # available.  No static "you have access to document search" here.
        
        # Add behavioral guidelines
        prompt_parts.append("\n\nGuidelines for your behavior:")
        prompt_parts.append("- Be clear, concise, and professional in your communication")
        prompt_parts.append("- Provide actionable insights and recommendations")
        prompt_parts.append("- If you need clarification, ask for it")
        prompt_parts.append("- Always prioritize accuracy and completeness")
        prompt_parts.append("- Structure your responses logically and comprehensively")
        
        base_prompt = "".join(prompt_parts)
        
        # Enhance with DocAware if needed (this adds more content)
        if doc_aware:
            base_prompt = self._enhance_with_docaware_instructions(base_prompt)
        
        word_count = len(base_prompt.split())
        logger.info(f"📏 PROMPT GEN: Template fallback generated {word_count} words")
        
        return {
            'success': True,
            'generated_prompt': base_prompt,
            'metadata': {
                'generated_at': datetime.now().isoformat(),
                'llm_provider': 'template_fallback',
                'llm_model': 'template',
                'agent_type': agent_type,
                'doc_aware': doc_aware,
                'fallback_used': True
            },
            'error': None
        }
    
    def _generate_cache_key(self, description: str, agent_type: str, doc_aware: bool) -> str:
        """Generate a cache key for the prompt generation request"""
        key_string = f"{description}|{agent_type}|{doc_aware}"
        return hashlib.md5(key_string.encode()).hexdigest()
    
    def _get_from_cache(self, cache_key: str) -> Optional[Dict[str, Any]]:
        """Get cached prompt generation result"""
        if cache_key not in _prompt_cache:
            return None
        
        cached = _prompt_cache[cache_key]
        cached_time = datetime.fromisoformat(cached['metadata']['generated_at'])
        
        if datetime.now() - cached_time > timedelta(hours=CACHE_DURATION_HOURS):
            # Cache expired
            del _prompt_cache[cache_key]
            return None
        
        logger.debug(f"💾 PROMPT GEN: Cache hit for key {cache_key[:8]}...")
        return cached
    
    def _save_to_cache(self, cache_key: str, result: Dict[str, Any]):
        """Save prompt generation result to cache"""
        _prompt_cache[cache_key] = result
        logger.debug(f"💾 PROMPT GEN: Cached result for key {cache_key[:8]}...")


# Singleton instance
_prompt_generation_service_instance: Optional[PromptGenerationService] = None

def get_prompt_generation_service() -> PromptGenerationService:
    """Get singleton prompt generation service instance"""
    global _prompt_generation_service_instance
    if _prompt_generation_service_instance is None:
        _prompt_generation_service_instance = PromptGenerationService()
    return _prompt_generation_service_instance

