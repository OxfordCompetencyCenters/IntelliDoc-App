# templates/template_definitions/aicc-intellidoc-v2/workflow_validator.py

import logging
from typing import Dict, List, Any, Tuple
from datetime import datetime

logger = logging.getLogger(__name__)

class WorkflowValidator:
    """Enhanced workflow validation for AICC-IntelliDoc-v2 agent orchestration"""
    
    def __init__(self):
        self.template_type = 'aicc-intellidoc-v2'
        self.supported_agent_types = [
            'StartNode', 'UserProxyAgent', 'AssistantAgent', 
            'GroupChatManager', 'EndNode', 'MCPServer'
        ]
        self.required_connection_types = ['sequential', 'conditional', 'parallel']
        
    def validate_workflow(self, workflow_data: Dict[str, Any]) -> Tuple[bool, List[str], List[str]]:
        """
        Comprehensive workflow validation for AICC-IntelliDoc-v2
        
        Returns:
            Tuple[bool, List[str], List[str]]: (is_valid, errors, warnings)
        """
        errors = []
        warnings = []
        
        try:
            logger.info(f"🔍 VALIDATION: Starting workflow validation for {self.template_type}")
            
            graph_json = workflow_data.get('graph_json', {})
            nodes = graph_json.get('nodes', [])
            edges = graph_json.get('edges', [])
            
            # Core structure validation
            structure_errors, structure_warnings = self._validate_structure(nodes, edges)
            errors.extend(structure_errors)
            warnings.extend(structure_warnings)
            
            # Node validation
            node_errors, node_warnings = self._validate_nodes(nodes)
            errors.extend(node_errors)
            warnings.extend(node_warnings)
            
            # Connection validation
            connection_errors, connection_warnings = self._validate_connections(nodes, edges)
            errors.extend(connection_errors)
            warnings.extend(connection_warnings)
            
            # Custom agent orchestration validation
            orchestration_errors, orchestration_warnings = self._validate_orchestration_compatibility(nodes, edges)
            errors.extend(orchestration_errors)
            warnings.extend(orchestration_warnings)
            
            # RAG integration validation (for document-aware agents)
            rag_errors, rag_warnings = self._validate_rag_integration(workflow_data)
            errors.extend(rag_errors)
            warnings.extend(rag_warnings)
            
            is_valid = len(errors) == 0
            
            logger.info(f"✅ VALIDATION: Completed - Valid: {is_valid}, Errors: {len(errors)}, Warnings: {len(warnings)}")
            
            return is_valid, errors, warnings
            
        except Exception as e:
            logger.error(f"❌ VALIDATION: Unexpected error during validation: {str(e)}")
            return False, [f"Validation failed: {str(e)}"], []
    
    def _has_complex_cycles(self, nodes: List[Dict], edges: List[Dict]) -> bool:
        """Enhanced cycle detection for complex workflows"""
        if not edges or len(nodes) <= 3:
            return False
        
        # Build adjacency list
        graph = {}
        for node in nodes:
            graph[node['id']] = []
        
        for edge in edges:
            source = edge.get('source')
            target = edge.get('target')
            if source and target and source in graph:
                graph[source].append(target)
        
        # Count strongly connected components
        visited = set()
        
        def dfs_count(node_id, path):
            if node_id in path:
                return len(path) > 3  # Complex cycle if more than 3 nodes
            if node_id in visited:
                return False
            
            visited.add(node_id)
            new_path = path + [node_id]
            
            for neighbor in graph.get(node_id, []):
                if dfs_count(neighbor, new_path):
                    return True
            
            return False
        
        for node_id in graph:
            if node_id not in visited:
                if dfs_count(node_id, []):
                    return True
        
        return False
    
    def _validate_structure(self, nodes: List[Dict], edges: List[Dict]) -> Tuple[List[str], List[str]]:
        """Validate basic workflow structure"""
        errors = []
        warnings = []
        
        # Check for empty workflow
        if not nodes:
            errors.append("Workflow must contain at least one node")
            return errors, warnings
        
        # Check for Start Node
        start_nodes = [n for n in nodes if n.get('type') == 'StartNode']
        if not start_nodes:
            warnings.append("Workflow should contain a Start Node for proper initialization")
        elif len(start_nodes) > 1:
            warnings.append("Multiple Start Nodes detected - only one should be used")
        
        # Check for End Node
        end_nodes = [n for n in nodes if n.get('type') == 'EndNode']
        if not end_nodes:
            warnings.append("Workflow should contain an End Node for proper termination")
        elif len(end_nodes) > 1:
            warnings.append("Multiple End Nodes detected - consider consolidating")
        
        # Check for orphaned nodes
        if edges:
            node_ids = set(n['id'] for n in nodes)
            connected_nodes = set()
            for edge in edges:
                connected_nodes.add(edge['source'])
                connected_nodes.add(edge['target'])
            
            orphaned_nodes = node_ids - connected_nodes
            if orphaned_nodes and len(nodes) > 1:
                warnings.append(f"Found {len(orphaned_nodes)} disconnected nodes")
        
        return errors, warnings
    
    def _validate_nodes(self, nodes: List[Dict]) -> Tuple[List[str], List[str]]:
        """Validate individual nodes"""
        errors = []
        warnings = []
        
        for node in nodes:
            node_id = node.get('id', 'unknown')
            node_type = node.get('type', 'unknown')
            node_data = node.get('data', {})
            
            # Check node type support
            if node_type not in self.supported_agent_types:
                errors.append(f"Unsupported agent type '{node_type}' in node {node_id[:8]}")
                continue
            
            # Validate node-specific requirements
            node_errors, node_warnings = self._validate_node_specific(node_type, node_data, node_id)
            errors.extend(node_errors)
            warnings.extend(node_warnings)
        
        return errors, warnings
    
    def _validate_node_specific(self, node_type: str, node_data: Dict, node_id: str) -> Tuple[List[str], List[str]]:
        """Validate specific node type requirements"""
        errors = []
        warnings = []
        node_short_id = node_id[:8]
        
        if node_type == 'StartNode':
            if not node_data.get('prompt', '').strip():
                warnings.append(f"Start Node {node_short_id} should have an initial prompt")
        
        elif node_type == 'AssistantAgent':
            if not node_data.get('system_message', '').strip():
                warnings.append(f"Assistant Agent {node_short_id} should have a system message")
            if not node_data.get('llm_config'):
                warnings.append(f"Assistant Agent {node_short_id} should specify LLM configuration")
        
        elif node_type == 'UserProxyAgent':
            if node_data.get('require_human_input') is None:
                warnings.append(f"User Proxy Agent {node_short_id} should specify human input requirements")
        
        elif node_type == 'GroupChatManager':
            if not node_data.get('speaker_selection'):
                warnings.append(f"Group Chat Manager {node_short_id} should specify speaker selection method")
        
        elif node_type == 'MCPServer':
            if not node_data.get('server_type'):
                errors.append(f"MCP Server {node_short_id} must specify a server type")
            if node_data.get('server_type') and node_data.get('server_type') not in ['google_drive', 'sharepoint']:
                errors.append(f"MCP Server {node_short_id} has invalid server type: {node_data.get('server_type')}")
        
        # Check for required name field
        if not node_data.get('name', '').strip():
            warnings.append(f"Node {node_short_id} should have a descriptive name")
        
        return errors, warnings
    
    def _validate_connections(self, nodes: List[Dict], edges: List[Dict]) -> Tuple[List[str], List[str]]:
        """Validate workflow connections"""
        errors = []
        warnings = []
        
        node_ids = set(n['id'] for n in nodes)
        
        for edge in edges:
            edge_id = edge.get('id', 'unknown')
            source_id = edge.get('source')
            target_id = edge.get('target')
            
            # Check for valid node references
            if source_id not in node_ids:
                errors.append(f"Connection {edge_id[:8]} references non-existent source node")
            if target_id not in node_ids:
                errors.append(f"Connection {edge_id[:8]} references non-existent target node")
            
            # Check for self-connections
            if source_id == target_id:
                errors.append(f"Connection {edge_id[:8]} creates a self-loop (not recommended)")
            
            # Validate connection properties
            if edge.get('type') == 'conditional' and not edge.get('condition'):
                warnings.append(f"Conditional connection {edge_id[:8]} should specify a condition")
        
        # Check for cycles (basic detection)
        if self._has_cycles(nodes, edges):
            warnings.append("Workflow contains cycles - ensure proper termination conditions")
        
        return errors, warnings
    
    def _validate_orchestration_compatibility(self, nodes: List[Dict], edges: List[Dict]) -> Tuple[List[str], List[str]]:
        """Validate custom agent orchestration framework compatibility"""
        errors = []
        warnings = []
        
        # Check agent limits
        agent_nodes = [n for n in nodes if n.get('type') not in ['StartNode', 'EndNode']]
        if len(agent_nodes) > 10:  # Default max agents from template
            warnings.append(f"Workflow has {len(agent_nodes)} agents - consider breaking into smaller workflows")
        
        # Check for GroupChatManager requirements
        group_managers = [n for n in nodes if n.get('type') == 'GroupChatManager']
        if len(group_managers) > 1:
            warnings.append("Multiple Group Chat Managers detected - this may cause coordination issues")
        
        # Check for proper agent flow
        user_proxies = [n for n in nodes if n.get('type') == 'UserProxyAgent']
        assistants = [n for n in nodes if n.get('type') == 'AssistantAgent']
        
        if not user_proxies and not group_managers:
            warnings.append("Workflow should include a User Proxy Agent or Group Chat Manager for execution")
        
        if not assistants:
            warnings.append("Workflow should include at least one Assistant Agent for AI capabilities")
        
        # Check for circular dependencies in complex workflows
        if len(agent_nodes) > 5 and self._has_complex_cycles(nodes, edges):
            warnings.append("Complex workflow detected with potential circular dependencies")
        
        return errors, warnings
    
    def _validate_rag_integration(self, workflow_data: Dict[str, Any]) -> Tuple[List[str], List[str]]:
        """Validate RAG (Retrieval Augmented Generation) integration"""
        errors = []
        warnings = []
        
        # Check if workflow uses document-aware agents
        nodes = workflow_data.get('graph_json', {}).get('nodes', [])
        doc_aware_nodes = [n for n in nodes if n.get('data', {}).get('doc_aware', False)]
        
        if doc_aware_nodes:
            # Validate that project has processed documents
            supports_rag = workflow_data.get('supports_rag', False)
            if not supports_rag:
                warnings.append("Document-aware agents detected but RAG support not enabled")
            
            # Check vector collections
            vector_collections = workflow_data.get('vector_collections', [])
            if not vector_collections:
                warnings.append("Document-aware agents require vector collections for document retrieval")
        
        return errors, warnings
    
    def _has_cycles(self, nodes: List[Dict], edges: List[Dict]) -> bool:
        """Simple cycle detection using DFS"""
        if not edges:
            return False
        
        # Build adjacency list
        graph = {}
        for node in nodes:
            graph[node['id']] = []
        
        for edge in edges:
            source = edge.get('source')
            target = edge.get('target')
            if source and target and source in graph:
                graph[source].append(target)
        
        # DFS cycle detection
        visited = set()
        rec_stack = set()
        
        def dfs(node_id):
            if node_id in rec_stack:
                return True
            if node_id in visited:
                return False
            
            visited.add(node_id)
            rec_stack.add(node_id)
            
            for neighbor in graph.get(node_id, []):
                if dfs(neighbor):
                    return True
            
            rec_stack.remove(node_id)
            return False
        
        for node_id in graph:
            if node_id not in visited:
                if dfs(node_id):
                    return True
        
        return False
    
    def get_validation_report(self, workflow_data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate comprehensive validation report"""
        is_valid, errors, warnings = self.validate_workflow(workflow_data)
        
        graph_json = workflow_data.get('graph_json', {})
        nodes = graph_json.get('nodes', [])
        edges = graph_json.get('edges', [])
        
        # Generate statistics
        node_type_counts = {}
        for node in nodes:
            node_type = node.get('type', 'unknown')
            node_type_counts[node_type] = node_type_counts.get(node_type, 0) + 1
        
        return {
            'validation_timestamp': datetime.now().isoformat(),
            'template_type': self.template_type,
            'is_valid': is_valid,
            'errors': errors,
            'warnings': warnings,
            'statistics': {
                'total_nodes': len(nodes),
                'total_edges': len(edges),
                'node_type_distribution': node_type_counts,
                'complexity_score': self._calculate_complexity_score(nodes, edges),
                'orchestration_compatibility': len(errors) == 0
            },
            'recommendations': self._generate_recommendations(is_valid, errors, warnings, nodes, edges)
        }
    
    def _calculate_complexity_score(self, nodes: List[Dict], edges: List[Dict]) -> str:
        """Calculate workflow complexity"""
        total_elements = len(nodes) + len(edges)
        
        if total_elements <= 3:
            return 'simple'
        elif total_elements <= 8:
            return 'moderate'
        elif total_elements <= 15:
            return 'complex'
        else:
            return 'very_complex'
    
    def _generate_recommendations(self, is_valid: bool, errors: List[str], warnings: List[str], 
                                nodes: List[Dict], edges: List[Dict]) -> List[str]:
        """Generate actionable recommendations"""
        recommendations = []
        
        if not is_valid:
            recommendations.append("Fix validation errors before executing workflow")
        
        if len(warnings) > 0:
            recommendations.append("Review warnings to improve workflow reliability")
        
        # Structure recommendations
        start_nodes = [n for n in nodes if n.get('type') == 'StartNode']
        end_nodes = [n for n in nodes if n.get('type') == 'EndNode']
        
        if not start_nodes:
            recommendations.append("Add a Start Node to define initial conditions")
        
        if not end_nodes:
            recommendations.append("Add an End Node to properly terminate workflow")
        
        # Performance recommendations
        if len(nodes) > 8:
            recommendations.append("Consider breaking complex workflow into smaller, manageable units")
        
        if len(edges) == 0 and len(nodes) > 1:
            recommendations.append("Connect agents with proper relationships for execution flow")
        
        # Custom orchestration-specific recommendations
        agent_nodes = [n for n in nodes if n.get('type') not in ['StartNode', 'EndNode']]
        if len(agent_nodes) > 5:
            recommendations.append("Test workflow with fewer agents first, then scale up gradually")
        
        return recommendations
