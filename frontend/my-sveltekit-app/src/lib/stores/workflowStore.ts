/**
 * Frontend Workflow Store - Memory-based workflow management
 * 
 * This store manages workflows entirely in memory without any backend calls
 * Perfect for rapid prototyping and testing workflow designs
 */

import { writable, derived } from 'svelte/store';

export interface WorkflowNode {
  id: string;
  type: string;
  position: { x: number; y: number };
  data: {
    label: string;
    description?: string;
    config?: any;
  };
}

export interface WorkflowEdge {
  id: string;
  source: string;
  target: string;
  type?: string;
  data?: any;
}

export interface WorkflowGraph {
  nodes: WorkflowNode[];
  edges: WorkflowEdge[];
}

export interface FrontendWorkflow {
  workflow_id: string;
  name: string;
  description: string;
  graph_json: WorkflowGraph;
  created_at: string;
  updated_at: string;
  status: 'draft' | 'active' | 'completed' | 'error';
  execution_count?: number;
  last_executed?: string;
}

// Create the main workflow store
function createWorkflowStore() {
  const { subscribe, set, update } = writable<FrontendWorkflow[]>([]);

  return {
    subscribe,
    
    // Initialize store (memory-only as per requirements)
    initialize: () => {
      console.log('🏪 WORKFLOW STORE: Initializing frontend workflow store');
      set([]);
    },
    
    // Add a new workflow
    addWorkflow: (workflow: FrontendWorkflow) => {
      update(workflows => {
        console.log(`🆕 WORKFLOW STORE: Adding workflow ${workflow.workflow_id}`);
        return [...workflows, workflow];
      });
    },
    
    // Update existing workflow
    updateWorkflow: (workflowId: string, updates: Partial<FrontendWorkflow>) => {
      update(workflows => {
        const index = workflows.findIndex(w => w.workflow_id === workflowId);
        if (index >= 0) {
          const updatedWorkflow = {
            ...workflows[index],
            ...updates,
            updated_at: new Date().toISOString()
          };
          workflows[index] = updatedWorkflow;
          console.log(`📝 WORKFLOW STORE: Updated workflow ${workflowId}`);
          return [...workflows];
        }
        console.warn(`⚠️ WORKFLOW STORE: Workflow ${workflowId} not found for update`);
        return workflows;
      });
    },
    
    // Remove workflow
    removeWorkflow: (workflowId: string) => {
      update(workflows => {
        console.log(`🗑️ WORKFLOW STORE: Removing workflow ${workflowId}`);
        return workflows.filter(w => w.workflow_id !== workflowId);
      });
    },
    
    // Get workflow by ID
    getWorkflow: (workflowId: string): FrontendWorkflow | undefined => {
      let found: FrontendWorkflow | undefined;
      subscribe(workflows => {
        found = workflows.find(w => w.workflow_id === workflowId);
      })();
      return found;
    },
    
    // Clear all workflows
    clear: () => {
      console.log('🧹 WORKFLOW STORE: Clearing all workflows');
      set([]);
    },
    
    // Create a new workflow with BLANK structure (no default nodes)
    createDefaultWorkflow: (name?: string): FrontendWorkflow => {
      const timestamp = new Date().toISOString();
      const workflowId = `frontend_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
      
      const defaultWorkflow: FrontendWorkflow = {
        workflow_id: workflowId,
        name: name || `Frontend Workflow ${Date.now()}`,
        description: '🌟 New infinite canvas agent workflow (Frontend Only)',
        graph_json: {
          nodes: [], // BLANK CANVAS - No default nodes
          edges: []
        },
        created_at: timestamp,
        updated_at: timestamp,
        status: 'draft',
        execution_count: 0
      };
      
      console.log(`🏭 WORKFLOW STORE: Created BLANK workflow ${workflowId}`);
      return defaultWorkflow;
    },
    
    // Execute workflow (simulation)
    executeWorkflow: (workflowId: string) => {
      update(workflows => {
        const index = workflows.findIndex(w => w.workflow_id === workflowId);
        if (index >= 0) {
          const workflow = workflows[index];
          const updatedWorkflow = {
            ...workflow,
            execution_count: (workflow.execution_count || 0) + 1,
            last_executed: new Date().toISOString(),
            status: 'active' as const,
            updated_at: new Date().toISOString()
          };
          workflows[index] = updatedWorkflow;
          console.log(`🚀 WORKFLOW STORE: Executed workflow ${workflowId} (count: ${updatedWorkflow.execution_count})`);
          
          // Simulate execution completion after 2 seconds
          setTimeout(() => {
            update(wfs => {
              const idx = wfs.findIndex(w => w.workflow_id === workflowId);
              if (idx >= 0) {
                wfs[idx] = {
                  ...wfs[idx],
                  status: 'completed',
                  updated_at: new Date().toISOString()
                };
                console.log(`✅ WORKFLOW STORE: Workflow ${workflowId} execution completed`);
                return [...wfs];
              }
              return wfs;
            });
          }, 2000);
          
          return [...workflows];
        }
        console.warn(`⚠️ WORKFLOW STORE: Workflow ${workflowId} not found for execution`);
        return workflows;
      });
    }
  };
}

// Export the store instance
export const frontendWorkflowStore = createWorkflowStore();

// Derived stores for convenience
export const activeWorkflows = derived(
  frontendWorkflowStore, 
  $workflows => $workflows.filter(w => w.status === 'active')
);

export const draftWorkflows = derived(
  frontendWorkflowStore, 
  $workflows => $workflows.filter(w => w.status === 'draft')
);

export const completedWorkflows = derived(
  frontendWorkflowStore, 
  $workflows => $workflows.filter(w => w.status === 'completed')
);

export const workflowCount = derived(
  frontendWorkflowStore,
  $workflows => $workflows.length
);

// Utility functions
export function generateWorkflowId(): string {
  return `frontend_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
}

export function validateWorkflowGraph(graph: WorkflowGraph): { valid: boolean; errors: string[] } {
  const errors: string[] = [];
  
  // Allow empty workflows - no validation errors for empty canvas
  if (!graph.nodes || graph.nodes.length === 0) {
    return { valid: true, errors: [] };
  }
  
  // Only validate if workflow has nodes
  if (graph.nodes.length > 0) {
    // Check for required Start Node
    if (!graph.nodes.some(node => node.type === 'StartNode')) {
      errors.push('Workflow must contain at least one Start Node');
    }
    
    // Check for required End Node
    if (!graph.nodes.some(node => node.type === 'EndNode')) {
      errors.push('Workflow must contain at least one End Node');
    }
  }
  
  // Check for duplicate node IDs
  const nodeIds = graph.nodes.map(n => n.id);
  const duplicateIds = nodeIds.filter((id, index) => nodeIds.indexOf(id) !== index);
  if (duplicateIds.length > 0) {
    errors.push(`Duplicate node IDs found: ${duplicateIds.join(', ')}`);
  }
  
  // Validate edges
  graph.edges.forEach(edge => {
    const sourceExists = graph.nodes.some(n => n.id === edge.source);
    const targetExists = graph.nodes.some(n => n.id === edge.target);
    
    if (!sourceExists) {
      errors.push(`Edge references non-existent source node: ${edge.source}`);
    }
    if (!targetExists) {
      errors.push(`Edge references non-existent target node: ${edge.target}`);
    }
  });

  // Validate reflection connection limits - each agent can have only 1 outgoing reflection connection
  const reflectionConnectionCounts: Record<string, number> = {};
  
  graph.edges.forEach(edge => {
    if (edge.type === 'reflection') {
      const sourceId = edge.source;
      reflectionConnectionCounts[sourceId] = (reflectionConnectionCounts[sourceId] || 0) + 1;
      
      if (reflectionConnectionCounts[sourceId] > 1) {
        const sourceNode = graph.nodes.find(n => n.id === sourceId);
        const nodeName = sourceNode?.data?.name || sourceId;
        errors.push(`Agent "${nodeName}" can have only 1 outgoing reflection connection, but has ${reflectionConnectionCounts[sourceId]}`);
      }
    }
  });

  // ROOT CAUSE FIX: Validate reflection edge constraints for ALL agents
  // If any agent has reflection edges as input, it must have NO outgoing edges
  // This applies to: AssistantAgent, UserProxyAgent, GroupChatManager, DelegateAgent, etc.
  graph.nodes.forEach(node => {
    // Skip StartNode and EndNode as they have special roles
    if (node.type === 'StartNode' || node.type === 'EndNode') {
      return;
    }
    
    const nodeId = node.id;
    const nodeName = node.data?.name || nodeId;
    const nodeType = node.type;
    
    // Check if this agent has reflection edges as input
    const reflectionInputEdges = graph.edges.filter(
      edge => edge.target === nodeId && edge.type === 'reflection'
    );
    
    if (reflectionInputEdges.length > 0) {
      // Check for outgoing edges
      const outgoingEdges = graph.edges.filter(edge => edge.source === nodeId);
      
      if (outgoingEdges.length > 0) {
        const reflectionSources = reflectionInputEdges.map(edge => {
          const sourceNode = graph.nodes.find(n => n.id === edge.source);
          return sourceNode?.data?.name || edge.source;
        }).join(', ');
        
        errors.push(
          `${nodeType} "${nodeName}" is connected to its preceding agent(s) (${reflectionSources}) with Reflection edge(s), but has ${outgoingEdges.length} outgoing edge(s). ` +
          `Agents with reflection input must have NO outgoing edges, as reflection is a feedback loop where the workflow continues from the reflection source position.`
        );
      }
    }
  });
  
  return {
    valid: errors.length === 0,
    errors
  };
}

console.log('🏪 WORKFLOW STORE: Frontend workflow store module loaded');
