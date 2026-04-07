"""
Workflow Parser
==============

Handles workflow graph parsing and multiple input processing for conversation orchestration.
"""

import logging
from typing import Dict, List, Any, Optional

from .executed_nodes_codec import (
    plain_executed_output,
    citations_from_executed_output,
    format_upstream_citations_block,
)

logger = logging.getLogger('conversation_orchestrator')


class WorkflowParser:
    """
    Parses workflow graphs and handles multiple input aggregation
    """
    
    def parse_workflow_graph(self, graph_json: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Parse workflow graph into linear execution sequence using TOPOLOGICAL SORT
        This respects the visual flow by processing nodes in dependency order.
        It excludes nodes that are only targets of reflection edges from the main sequence.
        """
        nodes = graph_json.get('nodes', [])
        edges = graph_json.get('edges', [])

        if not nodes:
            logger.warning("⚠️ ORCHESTRATOR: No nodes found in workflow graph")
            return []

        logger.info(f"🔗 ORCHESTRATOR: Parsing workflow with {len(nodes)} nodes and {len(edges)} edges")

        # Identify nodes that should be excluded from main execution sequence:
        # 1. Nodes that are exclusively targets of reflection edges (except UserProxyAgent with human input)
        # 2. Nodes that are exclusively targets of delegate edges (DelegateAgent nodes)
        excluded_targets = set()
        all_targets = {edge['target'] for edge in edges}
        for target_id in all_targets:
            incoming_edges = [edge for edge in edges if edge['target'] == target_id]
            if incoming_edges:
                # Get target node to check its type
                target_node = next((n for n in nodes if n['id'] == target_id), None)
                if not target_node:
                    continue
                    
                target_name = target_node.get('data', {}).get('name', target_id)
                target_type = target_node.get('type', 'Unknown')
                target_data = target_node.get('data', {})
                edge_types = [edge.get('type', 'sequential') for edge in incoming_edges]
                
                # Check if ALL incoming edges are delegate type
                all_delegate = all(edge.get('type') == 'delegate' for edge in incoming_edges)
                
                # Check if ALL incoming edges are reflection type
                all_reflection = all(edge.get('type') == 'reflection' for edge in incoming_edges)
                
                # CRITICAL: DelegateAgent nodes connected via delegate edges should be excluded
                # They are discovered and executed internally by GroupChatManager
                if all_delegate and target_type == 'DelegateAgent':
                    logger.info(f"🔍 DELEGATE CHECK: Node {target_name} ({target_type}) has {len(incoming_edges)} delegate-only edges: {edge_types} - EXCLUDING from main sequence (will be handled by GroupChatManager)")
                    excluded_targets.add(target_id)
                # CRITICAL FIX: UserProxyAgent nodes that require human input should be included
                # even if they only have reflection edges, because they pause the workflow
                elif all_reflection and not (target_type == 'UserProxyAgent' and target_data.get('require_human_input', True)):
                    # This is a reflection-only target that doesn't require human input - exclude it
                    logger.info(f"🔍 REFLECTION CHECK: Node {target_name} ({target_type}) has {len(incoming_edges)} reflection-only edges: {edge_types} - EXCLUDING from main sequence")
                    excluded_targets.add(target_id)
                elif all_reflection and target_type == 'UserProxyAgent' and target_data.get('require_human_input', True):
                    # This is a UserProxyAgent with reflection edges that requires human input - INCLUDE it
                    logger.info(f"✅ INCLUDE USERPROXY: Node {target_name} ({target_type}) has reflection edges but requires human input - INCLUDING in main sequence")
                else:
                    # Node has mixed edge types - include it in main sequence
                    logger.info(f"✅ INCLUDE NODE: Node {target_name} ({target_type}) has mixed edge types: {edge_types} - including in main sequence")

        if excluded_targets:
            logger.info(f"🔗 ORCHESTRATOR: Excluding delegate/reflection-only target nodes from topological sort: {excluded_targets}")

        # Filter out nodes that are exclusively delegate or reflection targets
        nodes_for_sorting = [node for node in nodes if node['id'] not in excluded_targets]
        
        # Create node lookup for fast access
        node_map = {node['id']: node for node in nodes_for_sorting}
        
        # Build adjacency list and calculate in-degrees
        adjacency = {node['id']: [] for node in nodes_for_sorting}
        in_degree = {node['id']: 0 for node in nodes_for_sorting}
        
        # CRITICAL FIX: Track reflection dependencies for UserProxyAgent nodes
        # This ensures they execute AFTER their dependencies, even if they only have reflection edges
        reflection_dependencies = {}  # Maps node_id to list of source node_ids that have reflection edges to it
        
        # Process edges to build graph structure
        for edge in edges:
            source = edge['source']
            target = edge['target']
            edge_type = edge.get('type', 'sequential')
            
            # Skip delegate edges - they don't create dependencies in the main execution sequence
            # Delegate agents are handled internally by GroupChatManager
            if edge_type == 'delegate':
                continue
            
            # Only process edges where both nodes are in the main execution sequence
            if source not in node_map or target not in node_map:
                continue
            
            # CRITICAL FIX: For UserProxyAgent nodes, include reflection edges in adjacency
            # This ensures they're queued when their dependencies are processed
            target_node = node_map.get(target)
            is_user_proxy_target = (target_node and 
                                   target_node.get('type') == 'UserProxyAgent' and
                                   target_node.get('data', {}).get('require_human_input', True))
            
            if edge_type == 'reflection':
                if is_user_proxy_target:
                    # For UserProxyAgent nodes, add reflection edges to adjacency
                    # This ensures they execute after their reflection source
                    adjacency[source].append(target)
                    in_degree[target] += 1
                    logger.info(f"🔗 REFLECTION EDGE: Added reflection edge from {node_map[source].get('data', {}).get('name', source)} to {node_map[target].get('data', {}).get('name', target)} (UserProxyAgent)")
                else:
                    # Track reflection dependencies for non-UserProxyAgent nodes (if any)
                    if target not in reflection_dependencies:
                        reflection_dependencies[target] = []
                    reflection_dependencies[target].append(source)
                continue  # Don't add reflection edges to adjacency for non-UserProxyAgent targets
            
            # Add sequential edges to adjacency and in-degree
            adjacency[source].append(target)
            in_degree[target] += 1
        
        # KAHN'S ALGORITHM for Topological Sort
        execution_sequence = []
        queue = []
        
        # Find all nodes with in-degree 0 (start nodes)
        for node_id, degree in in_degree.items():
            if degree == 0:
                queue.append(node_id)
                logger.info(f"🚀 ORCHESTRATOR: Found start node: {node_map[node_id].get('data', {}).get('name', node_id)}")
        
        # If no start nodes found, look specifically for StartNode type
        if not queue:
            start_nodes = [n for n in nodes_for_sorting if n.get('type') == 'StartNode']
            if start_nodes:
                queue = [start_nodes[0]['id']]
                logger.warning("⚠️ ORCHESTRATOR: No zero in-degree nodes, using StartNode")
            elif nodes_for_sorting:
                queue = [nodes_for_sorting[0]['id']]
                logger.warning("⚠️ ORCHESTRATOR: No StartNode found, using first node")
        
        # Process nodes in topological order
        processed_count = 0
        # CRITICAL FIX: Create node order map for deterministic sorting
        # This ensures nodes execute in consistent order when multiple are ready
        node_order_map = {node['id']: idx for idx, node in enumerate(nodes_for_sorting)}
        
        while queue:
            # CRITICAL FIX: Sort by original node order, not alphabetically
            # This ensures deterministic execution order when multiple nodes have in-degree 0
            queue.sort(key=lambda node_id: node_order_map.get(node_id, 999999))
            current_node_id = queue.pop(0)
            
            if current_node_id not in node_map:
                logger.error(f"❌ ORCHESTRATOR: Node {current_node_id} not found in node_map")
                continue
            
            current_node = node_map[current_node_id]
            execution_sequence.append(current_node)
            processed_count += 1
            
            node_name = current_node.get('data', {}).get('name', current_node_id)
            node_type = current_node.get('type', 'Unknown')
            logger.info(f"🎯 ORCHESTRATOR: [{processed_count}] Added to sequence: {node_name} (type: {node_type})")
            
            # Process all neighbors of the current node
            if current_node_id in adjacency:
                for neighbor_id in adjacency[current_node_id]:
                    if neighbor_id in in_degree:
                        in_degree[neighbor_id] -= 1
                        if in_degree[neighbor_id] == 0:
                            queue.append(neighbor_id)
                            neighbor_name = node_map[neighbor_id].get('data', {}).get('name', neighbor_id)
                            logger.info(f"🔗 ORCHESTRATOR: Queued next node: {neighbor_name}")
        
        # ROBUST FIX: Ensure ALL nodes are processed (handle any remaining unprocessed nodes)
        # This catches terminal nodes, isolated nodes, or any edge cases
        unprocessed_ids = set(node_map.keys()) - {node['id'] for node in execution_sequence}
        if unprocessed_ids:
            unprocessed_names = [node_map[uid].get('data', {}).get('name', uid) for uid in unprocessed_ids]
            logger.info(f"🔍 ORCHESTRATOR: Found {len(unprocessed_ids)} unprocessed nodes: {unprocessed_names}")
            
            # For each unprocessed node, find its dependencies and insert it after the last dependency
            for node_id in unprocessed_ids:
                node = node_map[node_id]
                node_name = node.get('data', {}).get('name', node_id)
                node_type = node.get('type', 'Unknown')
                node_data = node.get('data', {})
                is_user_proxy_with_input = (node_type == 'UserProxyAgent' and 
                                          node_data.get('require_human_input', True))
                
                # CRITICAL FIX: Find ALL dependencies (both in execution_sequence and not yet processed)
                # This ensures UserProxyAgent nodes are placed correctly even if their dependencies haven't been processed yet
                dependency_node_ids = set()
                for edge in edges:
                    if edge['target'] == node_id:
                        edge_type = edge.get('type', 'sequential')
                        source_id = edge['source']
                        
                        # For UserProxyAgent with human input, include reflection edges
                        # For other nodes, only check non-reflection edges
                        if edge_type != 'reflection' or is_user_proxy_with_input:
                            if source_id in node_map:  # Only consider sources that are in the execution sequence
                                dependency_node_ids.add(source_id)
                
                # Find positions of dependency nodes that are already in execution_sequence
                dependency_positions = []
                for i, executed_node in enumerate(execution_sequence):
                    if executed_node['id'] in dependency_node_ids:
                        dependency_positions.append(i)
                        dep_name = executed_node.get('data', {}).get('name', executed_node['id'])
                        logger.info(f"🔗 DEPENDENCY: Node {node_name} depends on {dep_name} (already in sequence at position {i+1})")
                
                # Check if there are dependencies that haven't been processed yet
                unprocessed_dependencies = dependency_node_ids - {n['id'] for n in execution_sequence}
                if unprocessed_dependencies:
                    unprocessed_dep_names = [node_map[dep_id].get('data', {}).get('name', dep_id) for dep_id in unprocessed_dependencies]
                    logger.info(f"⏳ DEPENDENCY: Node {node_name} depends on unprocessed nodes: {unprocessed_dep_names} - will insert after they're processed")
                
                # Insert after the latest dependency, or at the end if dependencies haven't been processed yet
                if dependency_positions:
                    insert_position = max(dependency_positions) + 1
                    logger.info(f"✅ ORCHESTRATOR: Adding unprocessed node {node_name} after dependency at position {insert_position + 1}")
                elif unprocessed_dependencies:
                    # Dependencies exist but haven't been processed yet - insert at end for now
                    # They will be reordered when dependencies are processed
                    insert_position = len(execution_sequence)
                    logger.info(f"⏳ ORCHESTRATOR: Adding unprocessed node {node_name} at end (dependencies not yet processed)")
                else:
                    # No dependencies found - this might be an isolated node
                    # Check if it has any incoming edges (including reflection)
                    has_incoming = any(edge['target'] == node_id for edge in edges)
                    if not has_incoming:
                        # Truly isolated - but UserProxyAgent nodes should not be here if they have reflection dependencies
                        insert_position = len(execution_sequence)
                        logger.warning(f"⚠️ ORCHESTRATOR: Node {node_name} has no dependencies - adding at end (position {insert_position + 1})")
                    else:
                        insert_position = len(execution_sequence)
                        logger.info(f"✅ ORCHESTRATOR: Adding unprocessed node {node_name} at end (position {insert_position + 1})")
                
                execution_sequence.insert(insert_position, node)
                processed_count += 1
        
        # CRITICAL FIX: Move End nodes to the end of execution sequence
        # This ensures End nodes execute after all other nodes, including UserProxy inputs
        end_nodes = []
        non_end_nodes = []
        
        for node in execution_sequence:
            if node.get('type') == 'EndNode':
                end_nodes.append(node)
            else:
                non_end_nodes.append(node)
        
        # Reconstruct sequence with End nodes at the end
        execution_sequence = non_end_nodes + end_nodes
        
        if end_nodes:
            end_node_names = [node.get('data', {}).get('name', 'Unknown') for node in end_nodes]
            logger.info(f"🔚 ORCHESTRATOR: Moved {len(end_nodes)} End nodes to end of sequence: {', '.join(end_node_names)}")
        
        sequence_names = [f"{node.get('data', {}).get('name', 'Unknown')} ({node.get('type')})" for node in execution_sequence]
        logger.info(f"🔗 ORCHESTRATOR: FINAL execution sequence: {' → '.join(sequence_names)}")
        
        logger.info(f"✅ ORCHESTRATOR: Parsed {len(execution_sequence)} nodes using topological sort with End nodes last")
        return execution_sequence
    
    def find_multiple_inputs_to_node(self, target_node_id: str, graph_json: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Find all nodes that feed into the target node (multiple inputs support)
        Returns list of input node data with metadata
        """
        input_nodes = []
        edges = graph_json.get('edges', [])
        node_map = {node['id']: node for node in graph_json.get('nodes', [])}
        
        logger.info(f"🔍 MULTI-INPUT: Finding input sources for node {target_node_id}")
        
        for edge in edges:
            if edge.get('target') == target_node_id:
                source_id = edge.get('source')
                if source_id in node_map:
                    source_node = node_map[source_id]
                    input_nodes.append({
                        'node': source_node,
                        'edge': edge,
                        'source_id': source_id,
                        'name': source_node.get('data', {}).get('name', source_id),
                        'type': source_node.get('type', 'Unknown')
                    })
                    logger.info(f"🔗 MULTI-INPUT: Found input source: {source_node.get('data', {}).get('name', source_id)} (type: {source_node.get('type')})")
        
        logger.info(f"✅ MULTI-INPUT: Found {len(input_nodes)} input sources for {target_node_id}")
        return input_nodes
    
    def find_outgoing_edges_from_node(self, source_node_id: str, graph_json: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Find all nodes that receive input from the source node (outgoing edges)
        Returns list of target node data with metadata
        
        CRITICAL: This is used to determine which agents should receive input from a UserProxyAgent
        If a UserProxyAgent has no outgoing edges, its input should NOT be routed to any agent
        """
        target_nodes = []
        edges = graph_json.get('edges', [])
        node_map = {node['id']: node for node in graph_json.get('nodes', [])}
        
        logger.info(f"🔍 OUTGOING: Finding target nodes for source node {source_node_id}")
        
        for edge in edges:
            if edge.get('source') == source_node_id:
                target_id = edge.get('target')
                edge_type = edge.get('type', 'sequential')
                if target_id in node_map:
                    target_node = node_map[target_id]
                    target_nodes.append({
                        'node': target_node,
                        'edge': edge,
                        'target_id': target_id,
                        'name': target_node.get('data', {}).get('name', target_id),
                        'type': target_node.get('type', 'Unknown'),
                        'edge_type': edge_type
                    })
                    logger.info(f"🔗 OUTGOING: Found target: {target_node.get('data', {}).get('name', target_id)} (type: {target_node.get('type')}, edge_type: {edge_type})")
        
        logger.info(f"✅ OUTGOING: Found {len(target_nodes)} target nodes for source node {source_node_id}")
        return target_nodes
    
    def aggregate_multiple_inputs(self, input_sources: List[Dict[str, Any]], executed_nodes: Dict[str, Any]) -> Dict[str, Any]:
        """
        Aggregate multiple input sources into structured context
        
        Args:
            input_sources: List of input node metadata
            executed_nodes: Dict mapping node_id to their output/response (str or packed dict with text+citations)
        
        Returns:
            Dict with aggregated context information
        """
        logger.info(f"🔄 MULTI-INPUT: Aggregating {len(input_sources)} input sources")
        
        aggregated_context = {
            'primary_input': '',
            'primary_plain': '',
            'secondary_inputs': [],
            'input_summary': '',
            'all_inputs': [],
            'input_count': len(input_sources)
        }
        
        # Sort inputs by type priority (StartNode first, then others)
        sorted_inputs = sorted(input_sources, key=lambda x: (
            0 if x['type'] == 'StartNode' else
            1 if x['type'] in ['AssistantAgent', 'UserProxyAgent'] else
            2
        ))
        
        input_contexts = []
        
        for i, input_source in enumerate(sorted_inputs):
            input_id = input_source['source_id']
            input_name = input_source['name']
            input_type = input_source['type']
            
            # Get the output/response from this input node (may be str or {text, citations})
            raw_output = executed_nodes.get(input_id, f"[No output from {input_name}]")
            content_plain = plain_executed_output(raw_output)
            upstream_cites = citations_from_executed_output(raw_output)
            display_content = content_plain
            if upstream_cites:
                display_content = content_plain + format_upstream_citations_block(input_name, upstream_cites)
            
            # DEBUG: Log if content is missing or truncated
            if input_id not in executed_nodes:
                logger.warning(f"⚠️ MULTI-INPUT: Node {input_id} ({input_name}) not found in executed_nodes. Available keys: {list(executed_nodes.keys())}")
            elif len(content_plain) < 50 and input_id in executed_nodes:
                logger.warning(f"⚠️ MULTI-INPUT: Node {input_id} ({input_name}) has suspiciously short content ({len(content_plain)} chars): {content_plain[:100]}")
            
            input_context = {
                'name': input_name,
                'type': input_type,
                'content': display_content,
                'content_plain': content_plain,
                'citations': upstream_cites,
                'priority': i + 1
            }
            
            input_contexts.append(input_context)
            aggregated_context['all_inputs'].append(input_context)
            
            logger.info(f"📥 MULTI-INPUT: Processed input {i+1}: {input_name} ({input_type}) - {len(str(display_content))} chars (node_id: {input_id})")
        
        # Set primary input (first/highest priority)
        if input_contexts:
            aggregated_context['primary_input'] = input_contexts[0]['content']
            aggregated_context['primary_plain'] = input_contexts[0].get('content_plain', input_contexts[0]['content'])
            aggregated_context['secondary_inputs'] = input_contexts[1:] if len(input_contexts) > 1 else []
        
        # Create formatted summary
        summary_parts = []
        for ctx in input_contexts:
            summary_parts.append(f"Input {ctx['priority']} ({ctx['type']} - {ctx['name']}): {ctx['content'][:100]}{'...' if len(str(ctx['content'])) > 100 else ''}")
        
        aggregated_context['input_summary'] = "\n".join(summary_parts)
        
        logger.info(f"✅ MULTI-INPUT: Aggregation complete - Primary: {len(str(aggregated_context['primary_input']))} chars, Secondary: {len(aggregated_context['secondary_inputs'])} inputs")
        
        return aggregated_context
    
    def format_multiple_inputs_prompt(self, aggregated_context: Dict[str, Any]) -> str:
        """
        Format multiple inputs into a structured prompt section
        
        Args:
            aggregated_context: Output from aggregate_multiple_inputs
        
        Returns:
            Formatted string for inclusion in prompts
        """
        if aggregated_context['input_count'] <= 1:
            return aggregated_context['primary_input']
        
        prompt_parts = []
        prompt_parts.append(f"Multiple Input Sources ({aggregated_context['input_count']} total):")
        prompt_parts.append("")
        
        # Add primary input
        prompt_parts.append("PRIMARY INPUT:")
        prompt_parts.append(aggregated_context['primary_input'])
        prompt_parts.append("")
        
        # Add secondary inputs
        if aggregated_context['secondary_inputs']:
            prompt_parts.append("ADDITIONAL INPUTS:")
            for i, secondary in enumerate(aggregated_context['secondary_inputs']):
                prompt_parts.append(f"Input {i + 2} ({secondary['type']} - {secondary['name']}):")
                prompt_parts.append(secondary['content'])
                prompt_parts.append("")
        
        return "\n".join(prompt_parts)