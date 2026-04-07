"""
Query Analysis Service - Intelligent Query Splitting and Delegate Matching

Analyzes input queries, splits them into meaningful subqueries, and matches
subqueries to appropriate delegate agents based on their capabilities.
"""

import logging
import json
import uuid
from typing import Dict, List, Any, Optional
from datetime import datetime

from .llm_provider_manager import LLMProviderManager
from users.models import IntelliDocProject

logger = logging.getLogger('agent_orchestration.query_analysis')


class QueryAnalysisService:
    """
    Service for analyzing queries and matching them to delegate agents
    """
    
    def __init__(self, llm_provider_manager: LLMProviderManager):
        self.llm_provider_manager = llm_provider_manager
        logger.info("🔧 QUERY ANALYSIS SERVICE: Initialized")
    
    async def analyze_and_split_query(
        self,
        input_text: str,
        delegate_descriptions: Dict[str, str],
        llm_provider,
        project: Optional[IntelliDocProject] = None,
        max_subqueries: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Analyze input query and split into meaningful subqueries
        
        Args:
            input_text: The input query to analyze
            delegate_descriptions: Dict mapping delegate names to their descriptions
            llm_provider: LLM provider instance for analysis
            project: Optional project for context
            
        Returns:
            List of subquery dictionaries with metadata
        """
        if not input_text or not input_text.strip():
            logger.warning("⚠️ QUERY ANALYSIS: Empty input text provided")
            return []
        
        if not delegate_descriptions:
            logger.warning("⚠️ QUERY ANALYSIS: No delegate descriptions provided")
            return []
        
        try:
            logger.info(f"🔍 QUERY ANALYSIS: Analyzing input ({len(input_text)} chars) with {len(delegate_descriptions)} delegates")
            
            # Build delegate descriptions string
            delegate_info = []
            for name, desc in delegate_descriptions.items():
                delegate_info.append(f"- {name}: {desc}")
            delegate_info_str = "\n".join(delegate_info)
            
            # Create query splitting prompt
            splitting_prompt = f"""You are a task analysis system. Given an input query and available delegate agents, 
analyze the query and split it into meaningful, actionable subqueries.

Input Query: {input_text}

Available Delegates:
{delegate_info_str}

Instructions:
1. Identify distinct, actionable subqueries within the input
2. Each subquery should be specific and assignable to a delegate
3. Maintain context and relationships between subqueries
4. Prioritize subqueries (high/medium/low) based on importance
5. Identify dependencies between subqueries if any
6. Suggest which delegate(s) might handle each subquery based on their descriptions

Return a JSON array of subqueries. Each subquery should have:
- query: The subquery text (string)
- priority: Priority level - "high", "medium", or "low" (string)
- dependencies: List of other subquery indices this depends on (array of integers, empty if none)
- suggested_delegates: List of delegate names that might handle this (array of strings)

Example format:
[
  {{
    "query": "Analyze the financial data for Q4",
    "priority": "high",
    "dependencies": [],
    "suggested_delegates": ["Financial Analyst"]
  }},
  {{
    "query": "Create a summary report based on the analysis",
    "priority": "medium",
    "dependencies": [0],
    "suggested_delegates": ["Report Writer"]
  }}
]

Return ONLY the JSON array, no additional text or explanation."""
            
            logger.info(f"🤖 QUERY ANALYSIS: Calling LLM for query splitting")
            
            # Call LLM for query splitting
            llm_response = await llm_provider.generate_response(
                prompt=splitting_prompt,
                max_tokens=2000,
                temperature=0.3  # Lower temperature for more consistent parsing
            )
            
            if llm_response.error:
                logger.error(f"❌ QUERY ANALYSIS: LLM error during splitting: {llm_response.error}")
                # Fallback: return single subquery
                return [{
                    'query': input_text,
                    'priority': 'medium',
                    'dependencies': [],
                    'suggested_delegates': list(delegate_descriptions.keys())
                }]
            
            response_text = llm_response.text.strip()
            
            # Try to extract JSON from response
            try:
                # Remove markdown code blocks if present
                if response_text.startswith('```'):
                    # Extract JSON from code block
                    lines = response_text.split('\n')
                    json_start = None
                    json_end = None
                    for i, line in enumerate(lines):
                        if line.strip().startswith('```json') or (line.strip() == '```' and json_start is None):
                            json_start = i + 1
                        elif line.strip() == '```' and json_start is not None:
                            json_end = i
                            break
                    
                    if json_start is not None and json_end is not None:
                        response_text = '\n'.join(lines[json_start:json_end])
                    elif json_start is not None:
                        response_text = '\n'.join(lines[json_start:])
                    else:
                        # Try to find JSON array directly
                        start_idx = response_text.find('[')
                        end_idx = response_text.rfind(']')
                        if start_idx != -1 and end_idx != -1:
                            response_text = response_text[start_idx:end_idx + 1]
                
                # Parse JSON
                subqueries = json.loads(response_text)
                
                if not isinstance(subqueries, list):
                    raise ValueError("Response is not a JSON array")
                
                # Validate and enrich subqueries
                validated_subqueries = []
                for idx, sq in enumerate(subqueries):
                    if not isinstance(sq, dict):
                        continue
                    
                    validated_sq = {
                        'subquery_id': str(uuid.uuid4()),
                        'query': sq.get('query', '').strip(),
                        'priority': sq.get('priority', 'medium').lower(),
                        'dependencies': sq.get('dependencies', []),
                        'suggested_delegates': sq.get('suggested_delegates', []),
                        'index': idx,
                        'created_at': datetime.now().isoformat()
                    }
                    
                    # Validate query is not empty
                    if validated_sq['query']:
                        validated_subqueries.append(validated_sq)
                
                # Apply max_subqueries limit if specified
                if max_subqueries is not None and max_subqueries > 0:
                    original_count = len(validated_subqueries)
                    if original_count > max_subqueries:
                        # Sort by priority (high > medium > low) and take top N
                        priority_order = {'high': 3, 'medium': 2, 'low': 1}
                        validated_subqueries.sort(
                            key=lambda sq: priority_order.get(sq.get('priority', 'medium'), 2),
                            reverse=True
                        )
                        validated_subqueries = validated_subqueries[:max_subqueries]
                        logger.info(f"📊 QUERY ANALYSIS: Limited subqueries from {original_count} to {len(validated_subqueries)} (max_subqueries={max_subqueries})")
                    else:
                        logger.info(f"✅ QUERY ANALYSIS: {len(validated_subqueries)} subqueries within limit (max_subqueries={max_subqueries})")
                else:
                    logger.info(f"✅ QUERY ANALYSIS: Successfully split into {len(validated_subqueries)} subqueries")
                
                return validated_subqueries
                
            except json.JSONDecodeError as e:
                logger.error(f"❌ QUERY ANALYSIS: Failed to parse JSON response: {e}")
                logger.error(f"❌ QUERY ANALYSIS: Response text: {response_text[:500]}")
                # Fallback: return single subquery
                return [{
                    'subquery_id': str(uuid.uuid4()),
                    'query': input_text,
                    'priority': 'medium',
                    'dependencies': [],
                    'suggested_delegates': list(delegate_descriptions.keys()),
                    'index': 0,
                    'created_at': datetime.now().isoformat()
                }]
            except Exception as e:
                logger.error(f"❌ QUERY ANALYSIS: Error processing response: {e}")
                import traceback
                logger.error(f"❌ QUERY ANALYSIS: Traceback: {traceback.format_exc()}")
                # Fallback: return single subquery
                return [{
                    'subquery_id': str(uuid.uuid4()),
                    'query': input_text,
                    'priority': 'medium',
                    'dependencies': [],
                    'suggested_delegates': list(delegate_descriptions.keys()),
                    'index': 0,
                    'created_at': datetime.now().isoformat()
                }]
                
        except Exception as e:
            logger.error(f"❌ QUERY ANALYSIS: Exception during query splitting: {e}")
            import traceback
            logger.error(f"❌ QUERY ANALYSIS: Traceback: {traceback.format_exc()}")
            # Fallback: return single subquery
            return [{
                'subquery_id': str(uuid.uuid4()),
                'query': input_text,
                'priority': 'medium',
                'dependencies': [],
                'suggested_delegates': list(delegate_descriptions.keys()),
                'index': 0,
                'created_at': datetime.now().isoformat()
            }]
    
    async def match_subquery_to_delegate(
        self,
        subquery: str,
        delegate_descriptions: Dict[str, str],
        llm_provider,
        confidence_threshold: float = 0.7,
        project: Optional[IntelliDocProject] = None
    ) -> Dict[str, Any]:
        """
        Match a subquery to the most appropriate delegate agent(s)
        
        Args:
            subquery: The subquery to match
            delegate_descriptions: Dict mapping delegate names to their descriptions
            llm_provider: LLM provider instance for matching
            confidence_threshold: Minimum confidence score for assignment
            project: Optional project for context
            
        Returns:
            Dict with assigned_delegates, confidence, and reasoning
        """
        if not subquery or not subquery.strip():
            logger.warning("⚠️ QUERY ANALYSIS: Empty subquery provided for matching")
            return {
                'assigned_delegates': [],
                'confidence': 0.0,
                'reasoning': 'Empty subquery provided'
            }
        
        if not delegate_descriptions:
            logger.warning("⚠️ QUERY ANALYSIS: No delegate descriptions provided for matching")
            return {
                'assigned_delegates': [],
                'confidence': 0.0,
                'reasoning': 'No delegates available'
            }
        
        try:
            logger.info(f"🎯 QUERY ANALYSIS: Matching subquery to delegates: {subquery[:100]}...")
            
            # Build delegate descriptions string
            delegate_info = []
            for name, desc in delegate_descriptions.items():
                delegate_info.append(f"- {name}: {desc}")
            delegate_info_str = "\n".join(delegate_info)
            
            # Create matching prompt
            matching_prompt = f"""You are a task routing system. Given a subquery and available delegate agents, 
determine which delegate(s) should handle this subquery.

Subquery: {subquery}

Available Delegates:
{delegate_info_str}

Instructions:
1. Analyze the subquery requirements and capabilities needed
2. Match against delegate capabilities (from their descriptions)
3. Assign to the best matching delegate(s) - can assign to multiple if collaboration is beneficial
4. Provide confidence score (0.0-1.0) indicating how well the delegate matches
5. Provide brief reasoning for the assignment

Return JSON with:
- assigned_delegates: List of delegate names (array of strings)
- confidence: Confidence score between 0.0 and 1.0 (float)
- reasoning: Brief explanation of why these delegates were chosen (string)

Example format:
{{
  "assigned_delegates": ["Financial Analyst"],
  "confidence": 0.9,
  "reasoning": "The subquery requires financial analysis, which matches the Financial Analyst delegate's expertise in financial data analysis."
}}

Return ONLY the JSON object, no additional text or explanation."""
            
            logger.info(f"🤖 QUERY ANALYSIS: Calling LLM for delegate matching")
            
            # Call LLM for matching
            llm_response = await llm_provider.generate_response(
                prompt=matching_prompt,
                max_tokens=500,
                temperature=0.2  # Very low temperature for consistent matching
            )
            
            if llm_response.error:
                logger.error(f"❌ QUERY ANALYSIS: LLM error during matching: {llm_response.error}")
                # Fallback: assign to all delegates
                return {
                    'assigned_delegates': list(delegate_descriptions.keys()),
                    'confidence': 0.5,
                    'reasoning': 'LLM matching failed, broadcasting to all delegates'
                }
            
            response_text = llm_response.text.strip()
            
            # Try to extract JSON from response
            try:
                # Remove markdown code blocks if present
                if response_text.startswith('```'):
                    lines = response_text.split('\n')
                    json_start = None
                    json_end = None
                    for i, line in enumerate(lines):
                        if line.strip().startswith('```json') or (line.strip() == '```' and json_start is None):
                            json_start = i + 1
                        elif line.strip() == '```' and json_start is not None:
                            json_end = i
                            break
                    
                    if json_start is not None and json_end is not None:
                        response_text = '\n'.join(lines[json_start:json_end])
                    else:
                        # Try to find JSON object directly
                        start_idx = response_text.find('{')
                        end_idx = response_text.rfind('}')
                        if start_idx != -1 and end_idx != -1:
                            response_text = response_text[start_idx:end_idx + 1]
                
                # Parse JSON
                match_result = json.loads(response_text)
                
                if not isinstance(match_result, dict):
                    raise ValueError("Response is not a JSON object")
                
                # Validate and normalize result
                assigned_delegates = match_result.get('assigned_delegates', [])
                if not isinstance(assigned_delegates, list):
                    assigned_delegates = []
                
                # Filter to only include valid delegate names
                valid_delegates = [d for d in assigned_delegates if d in delegate_descriptions]
                
                confidence = float(match_result.get('confidence', 0.5))
                confidence = max(0.0, min(1.0, confidence))  # Clamp to [0, 1]
                
                reasoning = match_result.get('reasoning', 'No reasoning provided')
                
                # If no valid delegates or confidence too low, fallback to all delegates
                if not valid_delegates or confidence < confidence_threshold:
                    logger.warning(f"⚠️ QUERY ANALYSIS: Low confidence ({confidence}) or no valid delegates, broadcasting to all")
                    return {
                        'assigned_delegates': list(delegate_descriptions.keys()),
                        'confidence': confidence,
                        'reasoning': f'Confidence below threshold or no valid matches. Original reasoning: {reasoning}'
                    }
                
                logger.info(f"✅ QUERY ANALYSIS: Matched to {len(valid_delegates)} delegate(s) with confidence {confidence:.2f}")
                return {
                    'assigned_delegates': valid_delegates,
                    'confidence': confidence,
                    'reasoning': reasoning
                }
                
            except (json.JSONDecodeError, ValueError, KeyError) as e:
                logger.error(f"❌ QUERY ANALYSIS: Failed to parse matching response: {e}")
                logger.error(f"❌ QUERY ANALYSIS: Response text: {response_text[:500]}")
                # Fallback: assign to all delegates
                return {
                    'assigned_delegates': list(delegate_descriptions.keys()),
                    'confidence': 0.5,
                    'reasoning': 'Failed to parse matching response, broadcasting to all delegates'
                }
            except Exception as e:
                logger.error(f"❌ QUERY ANALYSIS: Error processing matching response: {e}")
                import traceback
                logger.error(f"❌ QUERY ANALYSIS: Traceback: {traceback.format_exc()}")
                # Fallback: assign to all delegates
                return {
                    'assigned_delegates': list(delegate_descriptions.keys()),
                    'confidence': 0.5,
                    'reasoning': 'Error processing matching response, broadcasting to all delegates'
                }
                
        except Exception as e:
            logger.error(f"❌ QUERY ANALYSIS: Exception during delegate matching: {e}")
            import traceback
            logger.error(f"❌ QUERY ANALYSIS: Traceback: {traceback.format_exc()}")
            # Fallback: assign to all delegates
            return {
                'assigned_delegates': list(delegate_descriptions.keys()),
                'confidence': 0.5,
                'reasoning': 'Exception during matching, broadcasting to all delegates'
            }


# Singleton instance
_query_analysis_service_instance: Optional[QueryAnalysisService] = None

def get_query_analysis_service(llm_provider_manager: LLMProviderManager) -> QueryAnalysisService:
    """Get singleton query analysis service instance"""
    global _query_analysis_service_instance
    if _query_analysis_service_instance is None:
        _query_analysis_service_instance = QueryAnalysisService(llm_provider_manager)
    return _query_analysis_service_instance

