# Custom Agent Workflow JSON Schema Validator
# backend/schemas/workflow_validator.py

import json
import logging
from typing import Dict, Any, Tuple, List, Optional

try:
    import jsonschema
    from jsonschema import validate, ValidationError, Draft7Validator
    JSONSCHEMA_AVAILABLE = True
except ImportError:
    JSONSCHEMA_AVAILABLE = False
    print("⚠️ jsonschema package not installed. Run: pip install jsonschema>=4.0.0")

logger = logging.getLogger(__name__)

class AgentWorkflowValidator:
    """
    Custom JSON Schema Validator for Agent Workflows
    Replaces AutoGen with our own validation system
    """
    
    def __init__(self):
        self.schema_version = "1.0.0"
        self.available = JSONSCHEMA_AVAILABLE
        
        if not self.available:
            logger.warning("🚨 jsonschema not available - validation will be disabled")
            return
            
        # Define our custom agent workflow schema
        self.workflow_schema = {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "title": "AICC Agent Workflow Schema",
            "description": "Custom JSON schema for validating agent workflows (AutoGen replacement)",
            "type": "object",
            "required": ["nodes", "edges", "metadata"],
            "properties": {
                "metadata": {
                    "type": "object",
                    "required": ["name", "version", "agent_system"],
                    "properties": {
                        "name": {"type": "string", "minLength": 1},
                        "version": {"type": "string", "pattern": "^\\d+\\.\\d+\\.\\d+$"},
                        "agent_system": {"enum": ["custom_aicc_schema"]},
                        "description": {"type": "string"},
                        "created_by": {"type": "string"},
                        "created_at": {"type": "string", "format": "date-time"}
                    }
                },
                "nodes": {
                    "type": "array",
                    "minItems": 1,
                    "items": {
                        "type": "object",
                        "required": ["id", "type", "name", "agent_config"],
                        "properties": {
                            "id": {"type": "string", "minLength": 1},
                            "type": {
                                "enum": [
                                    "DocumentAnalyzerAgent",
                                    "HierarchicalProcessorAgent", 
                                    "CategoryClassifierAgent",
                                    "ContentReconstructorAgent",
                                    "ResearchAgent",
                                    "UserProxyAgent",
                                    "CoordinatorAgent",
                                    "ValidationAgent",
                                    "SummaryAgent",
                                    "CustomAgent"
                                ]
                            },
                            "name": {"type": "string", "minLength": 1},
                            "description": {"type": "string"},
                            "agent_config": {
                                "type": "object",
                                "required": ["llm_provider", "model"],
                                "properties": {
                                    "llm_provider": {"enum": ["openai", "google", "anthropic"]},
                                    "model": {"type": "string", "minLength": 1},
                                    "temperature": {"type": "number", "minimum": 0, "maximum": 2},
                                    "max_tokens": {"type": "integer", "minimum": 1},
                                    "system_message": {"type": "string"},
                                    "tools": {"type": "array", "items": {"type": "string"}},
                                    "supports_rag": {"type": "boolean"},
                                    "vector_collections": {"type": "array", "items": {"type": "string"}}
                                }
                            },
                            "position": {
                                "type": "object",
                                "required": ["x", "y"],
                                "properties": {
                                    "x": {"type": "number"},
                                    "y": {"type": "number"}
                                }
                            }
                        }
                    }
                },
                "edges": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "required": ["id", "source", "target"],
                        "properties": {
                            "id": {"type": "string", "minLength": 1},
                            "source": {"type": "string", "minLength": 1},
                            "target": {"type": "string", "minLength": 1},
                            "condition": {"type": "string"},
                            "message_template": {"type": "string"},
                            "priority": {"type": "integer", "minimum": 1}
                        }
                    }
                },
                "execution_config": {
                    "type": "object",
                    "properties": {
                        "max_iterations": {"type": "integer", "minimum": 1, "maximum": 100},
                        "timeout_seconds": {"type": "integer", "minimum": 10},
                        "parallel_execution": {"type": "boolean"},
                        "error_handling": {"enum": ["stop", "continue", "retry"]},
                        "retry_count": {"type": "integer", "minimum": 0, "maximum": 5}
                    }
                }
            }
        }
        
        logger.info(f"✅ Custom Agent Workflow Validator initialized (schema v{self.schema_version})")
    
    def validate_workflow(self, workflow_data: Dict[str, Any]) -> Tuple[bool, List[str], Dict[str, Any]]:
        """
        Validate agent workflow against our custom JSON schema
        Returns: (is_valid, validation_errors, analysis_summary)
        """
        if not self.available:
            logger.warning("🚨 Validation skipped - jsonschema not available")
            return True, [], {"status": "validation_disabled", "reason": "jsonschema_not_installed"}
        
        try:
            # Validate against schema
            validator = Draft7Validator(self.workflow_schema)
            errors = sorted(validator.iter_errors(workflow_data), key=lambda e: e.path)
            
            validation_errors = []
            for error in errors:
                error_path = " -> ".join([str(p) for p in error.path]) if error.path else "root"
                validation_errors.append(f"{error_path}: {error.message}")
            
            is_valid = len(validation_errors) == 0
            
            # Generate analysis summary
            analysis = self._analyze_workflow(workflow_data, is_valid)
            
            if is_valid:
                logger.info(f"✅ Workflow validation passed: {analysis.get('agent_count', 0)} agents, {analysis.get('edge_count', 0)} connections")
            else:
                logger.warning(f"❌ Workflow validation failed: {len(validation_errors)} errors")
                for error in validation_errors:
                    logger.warning(f"   - {error}")
            
            return is_valid, validation_errors, analysis
            
        except Exception as e:
            logger.error(f"❌ Validation error: {e}")
            return False, [f"Validation exception: {str(e)}"], {"status": "error", "exception": str(e)}
    
    def _analyze_workflow(self, workflow_data: Dict[str, Any], is_valid: bool) -> Dict[str, Any]:
        """Analyze workflow structure and provide insights"""
        analysis = {
            "schema_version": self.schema_version,
            "validation_status": "valid" if is_valid else "invalid",
            "analyzed_at": "2025-07-29T19:50:00Z",  # Would use timezone.now() in production
            "agent_system": "custom_aicc_schema"
        }
        
        try:
            # Count nodes and edges
            nodes = workflow_data.get("nodes", [])
            edges = workflow_data.get("edges", [])
            
            analysis.update({
                "agent_count": len(nodes),
                "edge_count": len(edges),
                "complexity_score": len(nodes) + len(edges) * 0.5,
                "agent_types": list(set(node.get("type", "unknown") for node in nodes)),
                "rag_enabled_agents": len([n for n in nodes if n.get("agent_config", {}).get("supports_rag", False)]),
                "llm_providers": list(set(node.get("agent_config", {}).get("llm_provider", "unknown") for node in nodes))
            })
            
            # Analyze workflow structure
            if nodes:
                analysis["has_start_node"] = any(not any(e.get("target") == n.get("id") for e in edges) for n in nodes)
                analysis["has_end_node"] = any(not any(e.get("source") == n.get("id") for e in edges) for n in nodes)
                analysis["is_cyclic"] = self._detect_cycles(nodes, edges)
            
            # Execution estimates
            if "execution_config" in workflow_data:
                config = workflow_data["execution_config"]
                analysis["estimated_max_runtime"] = config.get("timeout_seconds", 300)
                analysis["supports_parallel"] = config.get("parallel_execution", False)
            
        except Exception as e:
            analysis["analysis_error"] = str(e)
            logger.warning(f"⚠️ Workflow analysis partial failure: {e}")
        
        return analysis
    
    def _detect_cycles(self, nodes: List[Dict], edges: List[Dict]) -> bool:
        """Simple cycle detection using DFS"""
        try:
            # Build adjacency list
            graph = {node["id"]: [] for node in nodes}
            for edge in edges:
                if edge["source"] in graph:
                    graph[edge["source"]].append(edge["target"])
            
            # DFS cycle detection
            visited = set()
            rec_stack = set()
            
            def has_cycle(node):
                if node in rec_stack:
                    return True
                if node in visited:
                    return False
                
                visited.add(node)
                rec_stack.add(node)
                
                for neighbor in graph.get(node, []):
                    if has_cycle(neighbor):
                        return True
                
                rec_stack.remove(node)
                return False
            
            for node_id in graph:
                if node_id not in visited:
                    if has_cycle(node_id):
                        return True
            
            return False
        except:
            return False  # Default to no cycles if analysis fails
    
    def get_schema(self) -> Dict[str, Any]:
        """Return the complete JSON schema for external use"""
        if not self.available:
            return {"error": "jsonschema not available"}
        return self.workflow_schema
    
    def validate_agent_config(self, agent_config: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """Validate individual agent configuration"""
        if not self.available:
            return True, []
        
        agent_schema = self.workflow_schema["properties"]["nodes"]["items"]["properties"]["agent_config"]
        
        try:
            validate(agent_config, agent_schema)
            return True, []
        except ValidationError as e:
            return False, [e.message]
