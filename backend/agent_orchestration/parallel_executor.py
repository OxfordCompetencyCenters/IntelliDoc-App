"""
Parallel Execution Support for Agent Orchestration
==================================================

Detects and executes nodes in parallel when they have the same dependencies
and no dependencies on each other.
"""

import logging
import asyncio
from typing import Dict, List, Any, Set, Tuple
from collections import defaultdict

logger = logging.getLogger('conversation_orchestrator')


class ParallelExecutionDetector:
    """
    Detects which nodes can be executed in parallel based on their dependencies
    """
    
    @staticmethod
    def identify_parallel_groups(execution_sequence: List[Dict[str, Any]], graph_json: Dict[str, Any]) -> List[List[Dict[str, Any]]]:
        """
        Identify groups of nodes that can execute in parallel
        
        Args:
            execution_sequence: Linear execution sequence from topological sort
            graph_json: Full workflow graph
            
        Returns:
            List of groups, where each group contains nodes that can execute in parallel
        """
        edges = graph_json.get('edges', [])
        
        # Build dependency map: node_id -> set of source node_ids it depends on
        dependency_map = defaultdict(set)
        for edge in edges:
            if edge.get('type') == 'sequential':  # Only sequential edges create dependencies
                source_id = edge.get('source')
                target_id = edge.get('target')
                dependency_map[target_id].add(source_id)
        
        # Group nodes by their dependency sets
        # Nodes with the same dependencies can execute in parallel
        dependency_groups = defaultdict(list)
        for node in execution_sequence:
            node_id = node.get('id')
            node_type = node.get('type')
            
            # Skip StartNode and EndNode from parallel grouping
            if node_type in ['StartNode', 'EndNode']:
                continue
            
            # Get dependencies for this node
            dependencies = frozenset(dependency_map.get(node_id, set()))
            
            # Check if this node has any dependencies on other nodes in the same group
            # If yes, it can't be in the same parallel group
            can_parallelize = True
            for existing_node in dependency_groups[dependencies]:
                existing_node_id = existing_node.get('id')
                # Check if this node depends on existing node or vice versa
                if node_id in dependency_map.get(existing_node_id, set()) or \
                   existing_node_id in dependency_map.get(node_id, set()):
                    can_parallelize = False
                    break
            
            if can_parallelize:
                dependency_groups[dependencies].append(node)
        
        # Convert to list of groups, filtering out single-node groups
        parallel_groups = []
        for deps, nodes in dependency_groups.items():
            if len(nodes) > 1:
                parallel_groups.append(nodes)
                node_names = [n.get('data', {}).get('name', n.get('id')) for n in nodes]
                logger.info(f"🔀 PARALLEL: Identified parallel group: {', '.join(node_names)} (dependencies: {list(deps)})")
        
        return parallel_groups
    
    @staticmethod
    def find_ready_nodes(execution_sequence: List[Dict[str, Any]], executed_nodes: Dict[str, str], 
                        current_index: int) -> List[Tuple[int, Dict[str, Any]]]:
        """
        Find all nodes that are ready to execute (all dependencies satisfied)
        
        Args:
            execution_sequence: Full execution sequence
            executed_nodes: Dictionary of executed node outputs
            current_index: Current position in execution sequence
            
        Returns:
            List of (index, node) tuples for nodes ready to execute
        """
        ready_nodes = []
        edges = execution_sequence[0].get('_graph_edges', []) if execution_sequence else []
        
        # Build dependency map
        dependency_map = defaultdict(set)
        for edge in edges:
            if edge.get('type') == 'sequential':
                source_id = edge.get('source')
                target_id = edge.get('target')
                dependency_map[target_id].add(source_id)
        
        # Check nodes from current_index onwards
        for i in range(current_index, len(execution_sequence)):
            node = execution_sequence[i]
            node_id = node.get('id')
            node_type = node.get('type')
            
            # Skip if already executed
            if node_id in executed_nodes:
                continue
            
            # Skip StartNode and EndNode (handled separately)
            if node_type in ['StartNode', 'EndNode']:
                continue
            
            # Check if all dependencies are satisfied
            dependencies = dependency_map.get(node_id, set())
            all_dependencies_satisfied = all(dep_id in executed_nodes for dep_id in dependencies)
            
            if all_dependencies_satisfied:
                ready_nodes.append((i, node))
        
        return ready_nodes

