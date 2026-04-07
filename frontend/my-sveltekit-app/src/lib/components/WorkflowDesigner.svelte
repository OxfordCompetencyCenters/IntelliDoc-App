<!-- WorkflowDesigner.svelte - PowerPoint-style Visual Workflow Designer -->
<script lang="ts">
  import { createEventDispatcher, onMount, onDestroy } from 'svelte';
  import { toasts } from '$lib/stores/toast';
  import { saveWorkflowOrchestration, loadWorkflowOrchestration } from '$lib/services/api';
  import { v4 as uuidv4 } from 'uuid';
  import type { BulkModelData } from '$lib/stores/llmModelsStore';
  import { workflowStatus } from '$lib/stores/workflowStatus';
  import type { PendingHumanInput } from '$lib/services/humanInputService';
  import NodePropertiesPanel from './NodePropertiesPanel.svelte';
  
  export let project: any;
  export let projectId: string;
  export let workflow: any;
  export let capabilities: any;
  export let bulkModelData: BulkModelData | null = null;
  export let modelsLoaded: boolean = false;
  export let hierarchicalPaths: any[] = []; // Hierarchical paths for Content Filter
  export let hierarchicalPathsLoaded: boolean = false; // Whether hierarchical paths are loaded
  export let uploadedDocumentPaths: any[] = []; // Uploaded-file tree for node File Attachments picker
  export let uploadedDocumentPathsLoaded: boolean = false;
  export let documentsInfo: any = null; // Document and processing status info
  export let documentLlmStatus: Record<string, Record<string, { status: string; reason?: string }>> = {}; // Per-document LLM upload status
  export let designerMode: boolean = false; // Full-screen designer mode
  
  const dispatch = createEventDispatcher();
  
  // 🌟 ZOOM STABILITY: Throttle mechanism to prevent flicker
  let zoomUpdateTimeout: number | null = null;
  let pendingZoomUpdate = false;
  
  function throttledConnectionUpdate() {
    if (!pendingZoomUpdate) {
      pendingZoomUpdate = true;
      requestAnimationFrame(() => {
        connectionUpdateTrigger += 1;
        pendingZoomUpdate = false;
      });
    }
  }
  
  // Canvas state
  let nodes: any[] = [];
  let edges: any[] = [];
  let selectedNode: any | null = null;
  let selectedEdge: any | null = null;
  let showConnectionProperties = false;
  
  // 🔥 FIXED: Simplified reactive monitoring without potential loops
  $: nodesCount = nodes.length;
  $: edgesCount = edges.length;
  $: if (nodesCount >= 0 && edgesCount >= 0) {
    // Simple monitoring without creating complex triggers
    // Debounced logging to prevent excessive updates
    const now = Date.now();
    if (!window.lastLogTime || now - window.lastLogTime > 1000) {
      console.log('🔄 CANVAS STATE:', { nodes: nodesCount, edges: edgesCount });
      window.lastLogTime = now;
    }
  }
  
  // Force connection path updates when nodes change
  let connectionUpdateTrigger = 0;
  
  // Canvas interaction state
  let canvasElement: HTMLDivElement;
  let canvasRect: DOMRect;
  let isConnecting = false;
  let sourceNode: any = null;
  let mousePosition = { x: 0, y: 0 };
  let tempConnection: any = null;
  let isMouseOverCanvas = false;
  
  // Zoom and pan state
  let zoomLevel = 1;
  let panOffset = { x: 0, y: 0 };
  let isPanning = false;
  let isCanvasDragging = false; // 🌟 NEW: Left-click canvas dragging state
  let dragStartPos = { x: 0, y: 0 };
  let dragStartPan = { x: 0, y: 0 };
  const MIN_ZOOM = 0.1;    // Allow much more zoom out
  const MAX_ZOOM = 5;      // Allow much more zoom in
  const ZOOM_STEP = 0.1;

  // 🌟 INFINITE CANVAS: Enhanced canvas dimensions
  const CANVAS_WIDTH = 20000;   // Much larger canvas
  const CANVAS_HEIGHT = 20000;  // Much larger canvas
  const CANVAS_CENTER_X = CANVAS_WIDTH / 2;
  const CANVAS_CENTER_Y = CANVAS_HEIGHT / 2;
  
  // UI state
  let showPalette = true;
  let showProperties = false;
  let saving = false;
  let showInstructions = true; // State for dismissable instructions overlay
  let isPanelMaximized = false; // Whether the properties panel is maximized as modal
  
  // Designer Mode - exit handler
  function exitDesignerMode() {
    dispatch('exitDesignerMode');
    console.log('🖼️ WORKFLOW DESIGNER: Exiting Designer Mode');
  }
  
  // Handle Escape key to exit Designer Mode
  function handleDesignerModeKeydown(event: KeyboardEvent) {
    if (event.key === 'Escape' && designerMode && !isPanelMaximized && !showExpandedTextarea) {
      event.preventDefault();
      event.stopPropagation();
      exitDesignerMode();
    }
  }
  
  // Track if any expanded textarea is open (to not exit designer mode on Escape)
  let showExpandedTextarea = false;
  
  // Drag and drop state
  let draggedNodeType: string | null = null;
  let isDraggingNode = false;
  let dragOffset = { x: 0, y: 0 };
  let hasDraggedSignificantly = false;
  const DRAG_THRESHOLD = 5; // pixels
  
  // ============================================================================
  // PHASE 3: HUMAN INPUT VISUAL FEEDBACK STATE
  // ============================================================================
  let pendingInputs: PendingHumanInput[] = [];
  let agentsRequiringInput = new Set<string>();
  
  console.log('👤 WORKFLOW DESIGNER: Initializing human input visual feedback system');
  
  // Subscribe to workflow status for human input visual feedback
  const unsubscribeWorkflowStatus = workflowStatus.subscribe(status => {
    pendingInputs = status.pendingInputs;
    
    console.log('👤 WORKFLOW DESIGNER: Human input status update', {
      pendingCount: pendingInputs.length,
      workflowId: workflow?.workflow_id,
      pendingAgents: pendingInputs.map(p => ({ agent: p.agent_name, id: p.agent_id })),
      timestamp: new Date().toISOString()
    });
    
    // Track which agent nodes are requiring input
    const newRequiringInput = new Set(
      pendingInputs
        .filter(input => {
          // Only show for current workflow
          const isCurrentWorkflow = workflow && 
            (input.execution_id.includes(workflow.workflow_id) || 
             input.workflow_name === workflow.name);
          console.log('🔍 WORKFLOW DESIGNER: Checking input for current workflow', {
            inputExecutionId: input.execution_id.slice(-8),
            inputWorkflowName: input.workflow_name,
            currentWorkflowId: workflow?.workflow_id?.slice(-8),
            currentWorkflowName: workflow?.name,
            isCurrentWorkflow
          });
          return isCurrentWorkflow;
        })
        .map(input => input.agent_id)
        .filter(Boolean)
    );
    
    if (newRequiringInput.size !== agentsRequiringInput.size || 
        ![...newRequiringInput].every(id => agentsRequiringInput.has(id))) {
      
      console.log('🎯 WORKFLOW DESIGNER: Visual feedback update', {
        previouslyRequiring: Array.from(agentsRequiringInput),
        nowRequiring: Array.from(newRequiringInput),
        changed: true
      });
      
      agentsRequiringInput = newRequiringInput;
      
      // Force visual update if needed
      if (agentsRequiringInput.size > 0) {
        console.log('🟠 WORKFLOW DESIGNER: Highlighting nodes requiring input:', Array.from(agentsRequiringInput));
      } else {
        console.log('✅ WORKFLOW DESIGNER: No nodes requiring input');
      }
    }
  });
  
  // Connection types for visual workflow connections
  const connectionTypes = [
    { 
      id: 'sequential', 
      name: 'Sequential', 
      description: 'Standard sequential flow between agents',
      color: '#002147', 
      strokeWidth: 3,
      icon: 'fa-arrow-right'
    },
    { 
      id: 'conditional', 
      name: 'Conditional', 
      description: 'Conditional routing based on conditions',
      color: '#f59e0b', 
      strokeWidth: 3,
      icon: 'fa-code-branch'
    },
    { 
      id: 'parallel', 
      name: 'Parallel', 
      description: 'Parallel execution paths',
      color: '#10b981', 
      strokeWidth: 3,
      icon: 'fa-code-fork'
    },
    { 
      id: 'delegate', 
      name: 'Delegate Connection', 
      description: 'Connection from GroupChatManager to Delegate agent',
      color: '#f59e0b', 
      strokeWidth: 4,
      icon: 'fa-handshake'
    },
    { 
      id: 'delegate_return', 
      name: 'Delegate Return', 
      description: 'Return connection from Delegate agent to GroupChatManager',
      color: '#f97316', 
      strokeWidth: 4,
      icon: 'fa-reply'
    }
  ];
  
  // Agent type definitions with comprehensive descriptions
  const agentTypes = {
    'StartNode': {
      name: 'Start Node',
      description: 'Workflow entry point that initializes the agent conversation and sets the initial prompt or task',
      icon: 'fa-play',
      color: '#10b981',
      category: 'System',
      functionality: 'Defines starting conditions, initial prompts, and workflow parameters. Every workflow must begin with a Start Node.',
      useCases: ['Workflow initialization', 'Setting initial context', 'Defining task parameters']
    },
    'UserProxyAgent': {
      name: 'User Proxy Agent',
      description: 'Human-in-the-loop agent that facilitates user interaction, code execution, and human oversight',
      icon: 'fa-user',
      color: '#3b82f6',
      category: 'Interactive',
      functionality: 'Bridges human input with AI agents, executes code safely, requires human feedback when needed, and provides manual intervention capabilities.',
      useCases: ['Code execution', 'Human approval gates', 'Manual intervention', 'User input collection']
    },
    'AssistantAgent': {
      name: 'AI Assistant Agent',
      description: 'Core AI-powered agent that handles reasoning, analysis, and intelligent task completion',
      icon: 'fa-robot',
      color: '#002147',
      category: 'AI Core',
      functionality: 'Performs AI reasoning, natural language processing, problem-solving, and generates intelligent responses using large language models.',
      useCases: ['Text analysis', 'Problem solving', 'Content generation', 'Data interpretation', 'Decision making']
    },
    'GroupChatManager': {
      name: 'Group Chat Manager',
      description: 'Enhanced multi-agent coordinator with delegate management and multiple connection points',
      icon: 'fa-users',
      color: '#8b5cf6',
      category: 'Coordination',
      functionality: 'Manages group conversations with input/output/delegate endpoints, controls speaker selection, handles iteration limits and termination conditions.',
      useCases: ['Multi-agent coordination', 'Delegate management', 'Iterative conversations', 'Complex workflow orchestration']
    },
    'DelegateAgent': {
      name: 'Delegate Agent',
      description: 'Specialized agent invoked by GroupChatManager via tool calls based on its description',
      icon: 'fa-handshake',
      color: '#f59e0b',
      category: 'Delegation',
      functionality: 'Provides specialized capabilities to GroupChatManager. The manager dispatches tasks to delegates via tool calls. Delegates can use doc_tool_calling to access project documents. Can only connect to GroupChatManager.',
      useCases: ['Specialized task delegation', 'Iterative problem solving', 'Feedback loops', 'Expert consultation']
    },
    'EndNode': {
      name: 'End Node',
      description: 'Workflow termination point that collects results, processes final outputs, and concludes the agent conversation',
      icon: 'fa-stop',
      color: '#ef4444',
      category: 'System',
      functionality: 'Terminates workflow execution, collects and processes final results, generates output summaries, and handles cleanup operations.',
      useCases: ['Workflow completion', 'Result collection', 'Output processing', 'Final summaries']
    },
    'MCPServer': {
      name: 'MCP Server',
      description: 'Model Context Protocol server integration for external services like Google Drive and SharePoint',
      icon: 'fa-server',
      color: '#8b5cf6',
      category: 'Integration',
      functionality: 'Connects to MCP servers to access external services, execute tools, and retrieve resources. Supports Google Drive, SharePoint, and other MCP-compatible services.',
      useCases: ['Google Drive integration', 'SharePoint integration', 'External service access', 'Document retrieval', 'File operations']
    }
  };
  
  // Hover tooltip state
  let hoveredAgent = null;
  let tooltipPosition = { x: 0, y: 0 };
  
  // Initialize state
  console.log(`🎨 WORKFLOW DESIGNER: Initializing canvas for workflow ${workflow?.workflow_id}`);
  
  // 🐛 DEBUG: Log all props received
  console.log('🔍 WORKFLOW DESIGNER DEBUG:');
  console.log('  - project:', project);
  console.log('  - projectId:', projectId);
  console.log('  - workflow:', workflow);
  console.log('  - workflow.workflow_id:', workflow?.workflow_id);
  console.log('  - workflow.graph_json:', workflow?.graph_json);
  console.log('  - capabilities:', capabilities);
  
  // Simplified reactive monitoring for debug info
  $: if (capabilities && capabilities.supported_agent_types) {
    console.log('🔍 PALETTE: Agent types available:', capabilities.supported_agent_types.length, capabilities.supported_agent_types);
    
    // Debug: Check if DelegateAgent is being included
    const supportedTypes = capabilities.supported_agent_types || ['UserProxyAgent', 'AssistantAgent', 'GroupChatManager', 'DelegateAgent'];
    const coreAgentTypes = [...new Set([...supportedTypes, 'DelegateAgent'])].filter(type => type !== 'StartNode' && type !== 'EndNode' && agentTypes[type]);
    const fullAgentList = ['StartNode', ...coreAgentTypes, 'EndNode'];
    console.log('🎨 PALETTE: Full agent list that will be rendered:', fullAgentList);
    console.log('🤝 PALETTE: DelegateAgent included?', fullAgentList.includes('DelegateAgent'));
    console.log('📋 PALETTE: agentTypes has DelegateAgent?', !!agentTypes['DelegateAgent']);
  }
  
  // Monitor selected elements for debugging
  $: if (selectedEdge) {
    console.log('🎯 DEBUG: Selected edge:', selectedEdge.id.slice(-8));
  }
  
  onMount(async () => {
    updateCanvasRect();
    window.addEventListener('resize', updateCanvasRect);
    window.addEventListener('keydown', handleDesignerModeKeydown);
    
    console.log('🔄 MOUNT: Initializing WorkflowDesigner with workflow:', workflow?.workflow_id);
    console.log('🔄 MOUNT: Workflow has graph_json:', !!workflow?.graph_json);
    console.log('🔄 MOUNT: Workflow graph nodes count:', workflow?.graph_json?.nodes?.length || 0);
    
    // 🔥 CRITICAL FIX: Initialize from workflow prop first
    if (workflow && workflow.graph_json) {
      console.log('📊 MOUNT: Loading graph from workflow prop');
      loadWorkflowGraph();
    } else {
      console.log('📊 MOUNT: No graph data in workflow prop, setting empty canvas');
      nodes = [];
      edges = [];
    }
    
    // 💾 OPTIONAL: Try to load enhanced data from database (but don't override blank canvas)
    console.log('🔄 MOUNT: Attempting to load additional data from database...');
    try {
      const hasExistingNodes = nodes.length > 0;
      await loadWorkflowFromDatabase();
      
      // If we loaded nodes from database but started with empty, keep the database version
      // If we started with nodes but database returned empty, keep the original
      if (!hasExistingNodes && nodes.length === 0) {
        console.log('🎨 MOUNT: Both prop and database are empty - perfect blank canvas!');
      }
    } catch (error) {
      console.log('⚠️ MOUNT: Database load failed, continuing with prop data:', error.message);
    }
    
    // 🌟 INFINITE CANVAS: Auto-center on new workflow
    if (nodes.length === 0) {
      // Small delay to ensure canvas is rendered
      setTimeout(() => {
        centerView();
        console.log('🎯 INFINITE CANVAS: Auto-centered on empty workflow');
      }, 100);
    }
    
    return () => {
      window.removeEventListener('resize', updateCanvasRect);
    };
  });
  
  onDestroy(() => {
    // Clean up human input subscription
    unsubscribeWorkflowStatus();
    // Clean up keyboard listener
    window.removeEventListener('keydown', handleDesignerModeKeydown);
    console.log('🧹 WORKFLOW DESIGNER: Cleaned up human input subscription and keyboard listeners');
  });
  
  // Track current workflow ID to detect changes
  let currentWorkflowId = workflow?.workflow_id;
  
  // 🔥 FIXED: Use controlled workflow changes instead of reactive statement
  $: {
    if (workflow && workflow.workflow_id && workflow.workflow_id !== currentWorkflowId) {
      console.log('🔄 WORKFLOW CHANGED: Detected workflow change!', {
        oldId: currentWorkflowId?.slice(-8),
        newId: workflow.workflow_id?.slice(-8),
        newWorkflowName: workflow.name,
        hasNodes: workflow.graph_json?.nodes?.length || 0
      });
      
      currentWorkflowId = workflow.workflow_id;
      
      // Force immediate re-initialization for new workflow
      if (workflow.graph_json) {
        console.log('📊 WORKFLOW CHANGE: Loading graph from new workflow');
        loadWorkflowGraph();
      } else {
        console.log('📊 WORKFLOW CHANGE: No graph data, clearing canvas');
        nodes = [];
        edges = [];
      }
      
      // Auto-center if it's a new empty workflow
      if (!workflow.graph_json?.nodes || workflow.graph_json.nodes.length === 0) {
        setTimeout(() => {
          centerView();
          console.log('🎯 WORKFLOW CHANGE: Auto-centered on new empty workflow');
        }, 50);
      }
    }
  }
  
  function updateCanvasRect() {
    if (canvasElement) {
      canvasRect = canvasElement.getBoundingClientRect();
    }
  }
  
  function loadWorkflowGraph() {
    try {
      console.log('🔄 LOADING WORKFLOW GRAPH:', workflow?.workflow_id, workflow?.graph_json);
      const graphData = workflow.graph_json || { nodes: [], edges: [] };
      
      nodes = graphData.nodes.map((node: any) => ({
        id: node.id,
        type: node.type,
        position: node.position || getAutoPosition(node.id),
        data: {
          ...node.data,
          label: node.data?.name || node.type
        }
      }));
      
      edges = graphData.edges.map((edge: any) => ({
        id: edge.id || `${edge.source}-${edge.target}`,
        source: edge.source,
        target: edge.target,
        type: edge.type || 'default',
        label: edge.label || '',
        description: edge.description || '',
        condition: edge.condition || '',
        priority: edge.priority || 1,
        retryCount: edge.retryCount || 0,
        timeout: edge.timeout || 30
      }));
      
      console.log(`✅ WORKFLOW DESIGNER: Loaded ${nodes.length} nodes, ${edges.length} edges`);
      
      // Auto-center view on loaded nodes
      if (nodes.length > 0) {
        // Small delay to ensure canvas is rendered and nodes are positioned
        setTimeout(() => {
          centerView();
          console.log('🎯 WORKFLOW DESIGNER: Auto-centered view on loaded nodes');
        }, 150);
      }
      
    } catch (error) {
      console.error('❌ WORKFLOW DESIGNER: Failed to load graph:', error);
      if (toasts && toasts.error) {
        toasts.error('Failed to load workflow graph');
      }
    }
  }
  
  // Load workflow from database
  async function loadWorkflowFromDatabase() {
    if (!projectId || !workflow?.workflow_id) {
      console.log('💾 DATABASE LOAD: No project/workflow ID, skipping database load');
      return;
    }
    
    try {
      console.log('💾 DATABASE LOAD: Loading workflow from database', {
        projectId,
        workflowId: workflow.workflow_id
      });
      
      const loadedWorkflow = await loadWorkflowOrchestration(projectId, workflow.workflow_id);
      
      if (loadedWorkflow && loadedWorkflow.graph_json && loadedWorkflow.graph_json.nodes && loadedWorkflow.graph_json.nodes.length > 0) {
        console.log('💾 DATABASE LOAD: Found existing orchestration data with nodes');
        
        // Update workflow data with database content
        workflow = {
          ...workflow,
          ...loadedWorkflow
        };
        
        // Load the graph data
        loadWorkflowGraph();
        
        console.log('✅ DATABASE LOAD: Workflow loaded successfully from database');
        
        if (toasts && toasts.success) {
          toasts.success('💾 Workflow loaded from database');
        }
      } else {
        console.log('🔴 DATABASE LOAD: No saved orchestration found or empty - keeping current state');
        // Don't call loadWorkflowGraph() if there's no data to avoid overriding blank canvas
      }
      
    } catch (error) {
      console.error('❌ DATABASE LOAD: Failed to load from database:', error);
      console.log('🔴 DATABASE LOAD: Keeping current workflow state due to error');
      // Don't call loadWorkflowGraph() on error to avoid overriding current state
    }
  }
  
  function getAutoPosition(nodeId: string): { x: number; y: number } {
    const index = nodes.length;
    const cols = Math.ceil(Math.sqrt(nodes.length + 1));
    const row = Math.floor(index / cols);
    const col = index % cols;
    
    // 🌟 CENTER NODES: Start from origin (will be offset by CANVAS_CENTER in rendering)
    const autoPos = {
      x: -600 + col * 300, // Center horizontally with spread
      y: -300 + row * 180  // Center vertically with spread
    };
    
    console.log('🎯 AUTO POSITION:', {
      nodeIndex: index,
      gridPos: { row, col },
      autoPos,
      finalCanvasPos: {
        x: autoPos.x + CANVAS_CENTER_X,
        y: autoPos.y + CANVAS_CENTER_Y
      }
    });
    
    return autoPos;
  }
  
  // Save workflow functionality with database persistence
  async function saveWorkflowToDatabase(showToast = true) {
    if (saving) return;
    
    try {
      saving = true;
      
      const graphData = {
        nodes: nodes.map(node => ({
          id: node.id,
          type: node.type,
          position: node.position,
          data: node.data
        })),
        edges: edges.map(edge => ({
          id: edge.id,
          source: edge.source,
          target: edge.target,
          type: edge.type,
          label: edge.label,
          description: edge.description || '',
          condition: edge.condition || '',
          priority: edge.priority || 1,
          retryCount: edge.retryCount || 0,
          timeout: edge.timeout || 30
        }))
      };
      
      console.log('💾 SAVE TO DATABASE: Starting save process', {
        projectId: projectId,
        workflowId: workflow.workflow_id,
        hasNodes: nodes.length > 0,
        hasEdges: edges.length > 0,
        graphDataSize: JSON.stringify(graphData).length
      });
      
      // Save to database via API
      const orchestrationData = {
        graph_json: graphData,
        name: workflow.name || 'Unnamed Workflow',
        description: workflow.description || 'Agent orchestration workflow'
      };
      
      const savedWorkflow = await saveWorkflowOrchestration(
        projectId, 
        workflow.workflow_id, 
        orchestrationData
      );
      
      console.log('🎆 DATABASE SAVE: Workflow saved successfully', savedWorkflow);
      
      if (showToast && toasts && toasts.success) {
        toasts.success('🎆 Workflow saved to database successfully!');
      }
      
      // Dispatch update event
      const updatedWorkflow = {
        ...workflow,
        graph_json: graphData,
        updated_at: new Date().toISOString(),
        status: 'saved'
      };
      
      dispatch('workflowUpdate', updatedWorkflow);
      
    } catch (error) {
      console.error('❌ DATABASE SAVE: Failed to save to database:', error);
      if (toasts && toasts.error) {
        toasts.error(`Database save failed: ${error.message}`);
      }
    } finally {
      saving = false;
    }
  }
  
  // Agent palette drag handlers
  function handleDragStart(nodeType: string) {
    draggedNodeType = nodeType;
    console.log('🖱️ CANVAS: Started dragging agent type:', nodeType);
  }
  
  function handleCanvasDrop(event: DragEvent) {
    event.preventDefault();
    
    if (!draggedNodeType || !canvasElement) return;
    
    const rect = canvasElement.getBoundingClientRect();
    
    // 🌟 FIXED DROP POSITIONING: Account for new coordinate system
    const canvasX = (event.clientX - rect.left - panOffset.x) / zoomLevel;
    const canvasY = (event.clientY - rect.top - panOffset.y) / zoomLevel;
    
    // Convert to node coordinate space (relative to CANVAS_CENTER)
    const position = {
      x: canvasX - CANVAS_CENTER_X - 125, // Center the node (250px width / 2)
      y: canvasY - CANVAS_CENTER_Y - 40   // Center the node (80px height / 2)
    };
    
    console.log('🎯 DROP DEBUG:', {
      screenPos: { x: event.clientX, y: event.clientY },
      canvasPos: { x: canvasX, y: canvasY },
      finalPos: position,
      panOffset,
      zoomLevel
    });
    
    addNodeToCanvas(draggedNodeType, position);
    draggedNodeType = null;
  }
  
  function handleCanvasDragOver(event: DragEvent) {
    event.preventDefault();
  }
  
  function handleCanvasMouseMove(event: MouseEvent) {
    // 🌟 ENHANCED CONNECTION TRACKING: Update mouse position for connection creation
    if (isConnecting && canvasElement) {
      const rect = canvasElement.getBoundingClientRect();
      
      // 🌟 PRECISION FIX: Account for zoom and pan with proper coordinate transformation
      const rawX = (event.clientX - rect.left - panOffset.x) / zoomLevel;
      const rawY = (event.clientY - rect.top - panOffset.y) / zoomLevel;
      
      // 🌟 INFINITE CANVAS: Mouse position relative to content
      mousePosition = {
        x: rawX,
        y: rawY
      };
      
      // Force reactivity update to redraw temporary connection smoothly
      mousePosition = { ...mousePosition };
      
      console.log('📍 PRECISE CONNECTION: Mouse at', {
        screenX: event.clientX,
        screenY: event.clientY,
        canvasX: rawX,
        canvasY: rawY,
        adjustedX: mousePosition.x,
        adjustedY: mousePosition.y
      });
    }
    
    // 🌟 Update cursor during canvas navigation
    if (!isPanning && !isCanvasDragging && !isConnecting && !isDraggingNode) {
      const target = event.target as HTMLElement;
      const isCanvasBackground = target === canvasElement || 
                                 target.classList.contains('canvas-background') ||
                                 target.tagName === 'svg' ||
                                 (target.closest('.workflow-canvas') && !target.closest('.agent-node'));
      
      if (canvasElement && isCanvasBackground) {
        canvasElement.style.cursor = 'grab';
      }
    }
  }
  
  
  
  // Zoom functions
  function handleZoomIn() {
    const newZoom = Math.min(MAX_ZOOM, zoomLevel + ZOOM_STEP);
    if (newZoom !== zoomLevel) {
      setZoomLevel(newZoom);
    }
  }
  
  function handleZoomOut() {
    const newZoom = Math.max(MIN_ZOOM, zoomLevel - ZOOM_STEP);
    if (newZoom !== zoomLevel) {
      setZoomLevel(newZoom);
    }
  }
  
  function resetZoom() {
    if (zoomLevel !== 1 || panOffset.x !== 0 || panOffset.y !== 0) {
      zoomLevel = 1;
      panOffset = { x: 0, y: 0 };
      throttledConnectionUpdate();
      console.log('🔄 STABLE ZOOM: Reset to 100%');
    }
  }
  
  function setZoomLevel(newZoom: number) {
    if (newZoom !== zoomLevel) {
      zoomLevel = newZoom;
      // 🌟 PREVENT FLICKER: Throttled batch update
      throttledConnectionUpdate();
      console.log('🔍 STABLE ZOOM: Set zoom level to', Math.round(zoomLevel * 100) + '%');
    }
  }
  
  function handleWheel(event: WheelEvent) {
    if (event.ctrlKey || event.metaKey) {
      event.preventDefault();
      
      // 🌟 STABLE ZOOM: Prevent flickering with smooth zoom implementation
      const rect = canvasElement?.getBoundingClientRect();
      if (!rect) return;
      
      // Get mouse position relative to canvas
      const mouseX = event.clientX - rect.left;
      const mouseY = event.clientY - rect.top;
      
      // Calculate zoom delta
      const delta = event.deltaY > 0 ? -ZOOM_STEP : ZOOM_STEP;
      const newZoom = Math.max(MIN_ZOOM, Math.min(MAX_ZOOM, zoomLevel + delta));
      
      if (newZoom !== zoomLevel) {
        // 🌟 SMOOTH ZOOM: Calculate pan adjustment to zoom toward mouse position
        const zoomRatio = newZoom / zoomLevel;
        
        // Adjust pan offset to zoom toward mouse cursor
        panOffset = {
          x: mouseX - (mouseX - panOffset.x) * zoomRatio,
          y: mouseY - (mouseY - panOffset.y) * zoomRatio
        };
        
        // Apply new zoom level
        zoomLevel = newZoom;
        
        // 🌟 PREVENT FLICKER: Throttled batch update to prevent multiple renders
        throttledConnectionUpdate();
        
        console.log('🔍 STABLE ZOOM: Zoomed to', Math.round(zoomLevel * 100) + '% at mouse position', { mouseX, mouseY });
      }
    }
  }

  // 🌟 ENHANCED PAN FUNCTIONALITY: Left-click canvas drag + Middle mouse button
  function handleCanvasMouseDown(event: MouseEvent) {
    const target = event.target as HTMLElement;
    
    console.log('🖱️ CANVAS CLICK DEBUG:', {
      button: event.button,
      target: target.tagName,
      targetClass: target.className,
      isConnecting,
      isDraggingNode,
      clientX: event.clientX,
      clientY: event.clientY
    });
    
    // Middle mouse or Ctrl+Right-click (existing functionality)
    if (event.button === 1 || (event.button === 2 && event.ctrlKey)) {
      console.log('🖱️ CANVAS: Middle-click pan triggered');
      event.preventDefault();
      startPanning(event, 'middle');
      return;
    }
    
    // 🌟 NEW: Left-click canvas dragging
    if (event.button === 0) { // Left mouse button
      // Only start canvas dragging if clicking on canvas background, not on nodes or other elements
      const isClickingNode = target.closest('.agent-node') || target.classList.contains('agent-node');
      const isClickingConnectionHandle = target.closest('.connection-handle') || target.classList.contains('connection-handle');
      const isClickingConnectionPath = target.closest('.connection-group');
      const isClickingUI = target.closest('.instructions-overlay') || target.closest('button');
      
      console.log('🖱️ CANVAS CLICK ANALYSIS:', {
        isClickingNode,
        isClickingConnectionHandle,
        isClickingConnectionPath,
        isClickingUI,
        canStartDrag: !isClickingNode && !isClickingConnectionHandle && !isClickingConnectionPath && !isClickingUI && !isConnecting && !isDraggingNode
      });
      
      if (!isClickingNode && !isClickingConnectionHandle && !isClickingConnectionPath && !isClickingUI && !isConnecting && !isDraggingNode) {
        console.log('✅ CANVAS DRAG: Starting left-click canvas navigation');
        event.preventDefault();
        startPanning(event, 'left');
      } else {
        console.log('❌ CANVAS DRAG: Blocked - clicking on interactive element');
      }
    }
  }
  
  function startPanning(event: MouseEvent, type: 'left' | 'middle') {
    if (type === 'left') {
      isCanvasDragging = true;
    } else {
      isPanning = true;
    }
    
    dragStartPos = { x: event.clientX, y: event.clientY };
    dragStartPan = { ...panOffset };
    
    console.log(`✅ PANNING: Started ${type}-click canvas navigation`, {
      startPos: dragStartPos,
      startPan: dragStartPan,
      isCanvasDragging,
      isPanning
    });
    
    function handleMouseMove(e: MouseEvent) {
      if (!isPanning && !isCanvasDragging) {
        console.log('⚠️ PANNING: Mouse move ignored - not in panning state');
        return;
      }
      
      const deltaX = e.clientX - dragStartPos.x;
      const deltaY = e.clientY - dragStartPos.y;
      
      panOffset = {
        x: dragStartPan.x + deltaX,
        y: dragStartPan.y + deltaY
      };
      
      console.log('🖱️ PANNING: Mouse move', { deltaX, deltaY, newPanOffset: panOffset });
      
      // Update cursor to show we're dragging
      if (canvasElement) {
        canvasElement.style.cursor = 'grabbing';
        // 🌟 Optional: Add visual feedback for canvas navigation
        document.body.style.userSelect = 'none'; // Prevent text selection during drag
      }
    }
    
    function handleMouseUp() {
      console.log('✅ PANNING: Ended canvas navigation');
      isPanning = false;
      isCanvasDragging = false;
      
      // Reset cursor and body styles
      if (canvasElement) {
        canvasElement.style.cursor = 'grab';
      }
      document.body.style.userSelect = ''; // Re-enable text selection
      
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
    }
    
    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseup', handleMouseUp);
  }

  // Center view function
  function centerView() {
    // Ensure canvas rect is updated
    updateCanvasRect();
    
    if (nodes.length === 0) {
      // 🌟 INFINITE CANVAS: Center on canvas center if no nodes
      console.log('🎯 CENTERING: No nodes, centering on canvas center');
      panOffset = {
        x: (canvasRect?.width || 800) / 2 - CANVAS_CENTER_X,
        y: (canvasRect?.height || 600) / 2 - CANVAS_CENTER_Y
      };
      console.log('🎯 CENTERED: New panOffset =', panOffset);
    } else {
      // Center on nodes
      const minX = Math.min(...nodes.map(n => n.position.x + CANVAS_CENTER_X));
      const maxX = Math.max(...nodes.map(n => n.position.x + CANVAS_CENTER_X + 250));
      const minY = Math.min(...nodes.map(n => n.position.y + CANVAS_CENTER_Y));
      const maxY = Math.max(...nodes.map(n => n.position.y + CANVAS_CENTER_Y + 80));
      
      console.log('🎯 CENTERING: On nodes, bounds =', { minX, maxX, minY, maxY });
      
      const centerX = (minX + maxX) / 2;
      const centerY = (minY + maxY) / 2;
      
      panOffset = {
        x: (canvasRect?.width || 800) / 2 - centerX,
        y: (canvasRect?.height || 600) / 2 - centerY
      };
    }
    
    console.log('🎯 CANVAS: Centered view');
  }
  
  function addNodeToCanvas(nodeType: string, position: { x: number; y: number }) {
    const nodeId = uuidv4();
    const nodeData = getDefaultNodeData(nodeType);
    
    // 🔥 CRITICAL FIX: Ensure each node gets completely isolated data
    const newNode = {
      id: nodeId,
      type: nodeType,
      position: { ...position }, // Clone position
      data: {
        // Deep clone to prevent shared references
        ...JSON.parse(JSON.stringify(nodeData)),
        label: nodeData.name // Ensure label matches name
      }
    };
    
    console.log('➕ NODE CREATE DEBUG:', {
      nodeType,
      nodeId: nodeId.slice(-4),
      position,
      nodeData: JSON.stringify(newNode.data),
      finalCanvasPos: {
        x: position.x + CANVAS_CENTER_X,
        y: position.y + CANVAS_CENTER_Y
      },
      dataMemoryCheck: {
        originalDataRef: nodeData,
        newDataRef: newNode.data,
        isSameReference: nodeData === newNode.data
      }
    });
    
    nodes = [...nodes, newNode];
    selectedNode = newNode;
    showProperties = true;
    
    console.log('➕ WORKFLOW DESIGNER: Added node:', nodeType, nodeId.slice(-4), 'at position', position);
    saveWorkflowToDatabase(false); // Silent auto-save
  }
  
  function getDefaultNodeData(nodeType: string) {
    const count = nodes.filter(n => n.type === nodeType).length + 1;
    
    switch (nodeType) {
      case 'StartNode':
        return {
          name: `Start ${count}`,
          prompt: 'Enter your initial prompt here...',
          description: 'Starting point of the workflow'
        };
      case 'UserProxyAgent':
        return {
          name: `User Proxy ${count}`,
          description: 'USER INPUT REQUIRED',
          require_human_input: true,
          input_mode: 'user'
        };
      case 'AssistantAgent':
        return {
          name: `AI Assistant ${count}`,
          system_message: 'You are a helpful AI assistant.',
          description: 'AI assistant for task completion',
          llm_config: 'gpt-4',
          doc_tool_calling: false,
          doc_tool_calling_documents: []
        };
      case 'GroupChatManager':
        return {
          name: `Chat Manager ${count}`,
          description: 'Manages group conversation flow with delegates',
          system_message: 'You are a Group Chat Manager responsible for coordinating multiple specialized agents and synthesizing their contributions into comprehensive solutions.',
          delegate_connections: [],
        };
      case 'DelegateAgent':
        return {
          name: `Delegate ${count}`,
          description: 'Specialized delegate for Chat Manager',
          system_message: 'You are a specialized delegate agent.',
          llm_config: 'gpt-4',
          doc_tool_calling: false,
          doc_tool_calling_documents: [],
          can_only_connect_to: 'GroupChatManager'
        };
      case 'EndNode':
        return {
          name: `End ${count}`,
          description: 'Workflow termination and result collection',
          output_format: 'summary',
          collect_results: true
        };
      case 'MCPServer':
        return {
          name: `MCP Server ${count}`,
          description: 'MCP server integration for external services',
          server_type: 'google_drive',
          server_config: {},
          selected_tools: [],
          parameters: {}
        };
      default:
        return {
          name: `${nodeType} ${count}`,
          description: `${nodeType} agent`
        };
    }
  }
  
  // Node interaction handlers
  function handleNodeClick(node: any, event: MouseEvent) {
    // Don't handle click if we just finished a significant drag
    if (hasDraggedSignificantly) {
      hasDraggedSignificantly = false;
      return;
    }
    
    if (isConnecting) {
      handleConnectionTarget(node);
      return;
    }
    
    selectedNode = node;
    selectedEdge = null;
    showProperties = true;
    showConnectionProperties = false;
    
    console.log('🎯 WORKFLOW DESIGNER: Node clicked (not dragged):', node.id);
  }
  
  function handleNodeMouseDown(event: MouseEvent, node: any) {
    if (event.button !== 0) return; // Only left mouse button
    
    // CRITICAL FIX: Don't handle if clicking connection handle
    const target = event.target as HTMLElement;
    if (target.classList.contains('connection-handle') || target.closest('.connection-handle')) {
      // Let the connection handle deal with this
      console.log('🎯 NODE DRAG: Ignoring - clicked on connection handle');
      return;
    }
    
    // Start node dragging
    event.preventDefault();
    event.stopPropagation(); // 🌟 PREVENT canvas dragging when clicking nodes
    
    console.log('🖱️ NODE DRAG: Starting drag for node', node.data.name);
    
    isDraggingNode = true;
    hasDraggedSignificantly = false;
    selectedNode = node;
    selectedEdge = null;
    
    const startMousePos = { x: event.clientX, y: event.clientY };
    const startNodePos = { ...node.position };
    
    function handleMouseMove(e: MouseEvent) {
      if (!isDraggingNode) return;
      
      const deltaX = e.clientX - startMousePos.x;
      const deltaY = e.clientY - startMousePos.y;
      
      // Check if we've dragged significantly
      const dragDistance = Math.sqrt(deltaX * deltaX + deltaY * deltaY);
      if (dragDistance > DRAG_THRESHOLD) {
        hasDraggedSignificantly = true;
        console.log('🔄 NODE DRAG: Significant drag detected, distance =', dragDistance);
      }
      
      const newPosition = {
        x: startNodePos.x + deltaX / zoomLevel, // 🌟 INFINITE CANVAS: Allow negative coordinates
        y: startNodePos.y + deltaY / zoomLevel  // 🌟 INFINITE CANVAS: Allow negative coordinates
      };
      
      // Update position in real-time during dragging
      updateNodePosition(node.id, newPosition);
    }
    
    function handleMouseUp() {
      console.log('🖱️ NODE DRAG: Drag ended, hasDraggedSignificantly =', hasDraggedSignificantly);
      isDraggingNode = false;
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
      if (hasDraggedSignificantly) {
        saveWorkflowToDatabase(false); // Silent auto-save
      }
    }
    
    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseup', handleMouseUp);
  }
  
  function updateNodePosition(nodeId: string, position: { x: number; y: number }) {
    const nodeIndex = nodes.findIndex(n => n.id === nodeId);
    if (nodeIndex >= 0) {
      // 🌟 INFINITE CANVAS: Allow negative coordinates for true infinite canvas
      const newPosition = {
        x: position.x, // Remove Math.max(0, ...) to allow negative coordinates
        y: position.y  // Remove Math.max(0, ...) to allow negative coordinates
      };
      
      // Update the node position
      nodes[nodeIndex] = {
        ...nodes[nodeIndex],
        position: { ...newPosition } // Ensure new object reference
      };
      
      // Force Svelte reactivity by creating new array
      nodes = [...nodes];
      
      // Trigger connection path recalculation
      connectionUpdateTrigger += 1;
      
      // Update selected node if it's the one being moved
      if (selectedNode?.id === nodeId) {
        selectedNode = nodes[nodeIndex];
      }
      
      console.log('🔄 INFINITE CANVAS: Updated node', nodeId.slice(-4), 'to position', newPosition, 'trigger =', connectionUpdateTrigger);
    }
  }
  
  // Connection creation handlers

  function handleConnectionStart(event: MouseEvent, node: any) {
    console.log('🟦 CONNECTION START: Event triggered on node', node.data.name);
    event.preventDefault();
    event.stopPropagation();
    
    if (isConnecting) {
      console.log('⚠️ CONNECTION START: Already connecting, canceling previous');
      // Reset any previous connection state
      isConnecting = false;
      sourceNode = null;
      tempConnection = null;
    }
    
    isConnecting = true;
    sourceNode = node;
    
    console.log('🎆 CONNECTION START: Set isConnecting=true, sourceNode=', sourceNode.data.name);
    
    // 🌟 PRECISE CONNECTION: Initialize mouse position immediately with proper coordinates
    if (canvasElement) {
      const rect = canvasElement.getBoundingClientRect();
      const rawX = (event.clientX - rect.left - panOffset.x) / zoomLevel;
      const rawY = (event.clientY - rect.top - panOffset.y) / zoomLevel;
      
      mousePosition = {
        x: rawX,
        y: rawY
      };
    }
    
    console.log('🔗 CANVAS: Starting connection from', node.data.name, 'at position', mousePosition);
    
    // 🌟 ENHANCED GLOBAL TRACKING: Add global mouse move listener for smooth tracking
    function handleGlobalMouseMove(e: MouseEvent) {
      if (isConnecting && canvasElement) {
        const rect = canvasElement.getBoundingClientRect();
        const rawX = (e.clientX - rect.left - panOffset.x) / zoomLevel;
        const rawY = (e.clientY - rect.top - panOffset.y) / zoomLevel;
        
        mousePosition = {
          x: rawX,
          y: rawY
        };
        // Force reactivity for smooth connection line following
        mousePosition = { ...mousePosition };
      }
    }
    
    function handleGlobalMouseUp(e: MouseEvent) {
      console.log('🔗 CONNECTION END: Mouse up detected, checking for target');
      
      if (isConnecting) {
        // Check if we're over a valid target
        const targetElement = document.elementFromPoint(e.clientX, e.clientY);
        const targetNodeElement = targetElement?.closest('[data-node-id]');
        const targetNodeId = targetNodeElement?.getAttribute('data-node-id');
        
        console.log('🎯 CONNECTION TARGET: Found element', targetElement, 'nodeId', targetNodeId);
        
        if (targetNodeId && targetNodeId !== sourceNode?.id) {
          const targetNode = nodes.find(n => n.id === targetNodeId);
          if (targetNode) {
            console.log('✅ CONNECTION: Creating connection to', targetNode.data.name);
            createConnection(sourceNode, targetNode);
          }
        } else {
          console.log('❌ CONNECTION: No valid target found');
        }
        
        // Reset connection state
        isConnecting = false;
        sourceNode = null;
        tempConnection = null;
        mousePosition = { x: 0, y: 0 }; // Reset mouse position
      }
      
      // Remove both listeners
      document.removeEventListener('mousemove', handleGlobalMouseMove);
      document.removeEventListener('mouseup', handleGlobalMouseUp);
    }
    
    // Add both listeners
    document.addEventListener('mousemove', handleGlobalMouseMove);
    document.addEventListener('mouseup', handleGlobalMouseUp);
  }
  
  function handleConnectionTarget(targetNode: any) {
    if (!sourceNode || sourceNode.id === targetNode.id) {
      isConnecting = false;
      sourceNode = null;
      return;
    }
    
    createConnection(sourceNode, targetNode);
    
    // Reset connection state
    isConnecting = false;
    sourceNode = null;
  }
  
  function createConnection(source: any, target: any) {
    // Check for duplicate
    const existingConnection = edges.find(edge => 
      edge.source === source.id && edge.target === target.id
    );
    
    if (existingConnection) {
      console.log('⚠️ CANVAS: Connection already exists');
      if (toasts && toasts.warning) {
        toasts.warning('Connection already exists between these agents');
      }
      return;
    }
    
    // ✅ END NODE VALIDATION: Only one incoming edge allowed
    if (target.type === 'EndNode') {
      const incomingToEnd = edges.filter(edge => edge.target === target.id);
      if (incomingToEnd.length >= 1) {
        console.log('❌ CANVAS: End node already has an incoming connection');
        if (toasts && toasts.error) {
          toasts.error('End node can only receive input from a single agent');
        }
        return;
      }
    }
    
    // ✅ DELEGATE CONNECTION VALIDATION
    if (source.type === 'DelegateAgent' && target.type !== 'GroupChatManager') {
      console.log('❌ CANVAS: Delegate agents can only connect to GroupChatManager');
      if (toasts && toasts.error) {
        toasts.error('Delegate agents can only connect to Group Chat Manager');
      }
      return;
    }
    
    // Validate connection to DelegateAgent (only GroupChatManager can connect to delegates)
    if (target.type === 'DelegateAgent' && source.type !== 'GroupChatManager') {
      console.log('❌ CANVAS: Only GroupChatManager can connect to Delegate agents');
      if (toasts && toasts.error) {
        toasts.error('Only Group Chat Manager can connect to Delegate agents');
      }
      return;
    }
    
    // Determine connection type based on agent types
    let connectionType = 'sequential';
    
    // Special handling for GroupChatManager-DelegateAgent connections
    // These should use 'delegate' type to maintain proper connection visualization
    if ((source.type === 'GroupChatManager' && target.type === 'DelegateAgent') ||
        (source.type === 'DelegateAgent' && target.type === 'GroupChatManager')) {
      connectionType = 'delegate';
    }
    
    const newConnection = {
      id: `${source.id}-${target.id}`,
      source: source.id,
      target: target.id,
      type: connectionType,
      label: '',
      description: '',
      condition: '',
      priority: 1,
      retryCount: 0,
      timeout: 30
    };
    
    edges = [...edges, newConnection];
    
    console.log('✅ CANVAS: Connection created:', newConnection);
    if (toasts && toasts.success) {
      toasts.success(`Connected ${source.data.name} to ${target.data.name}`);
    }
    
    // Trigger Group Chat Manager prompt regeneration if delegate connection was created
    if (connectionType === 'delegate' && source.type === 'GroupChatManager') {
      console.log('🔧 GROUP CHAT MANAGER: Delegate connection created, will trigger prompt regeneration');
      // The reactive statement in NodePropertiesPanel will handle this
      // Force update selectedNode if it's the Group Chat Manager
      if (selectedNode && selectedNode.id === source.id) {
        selectedNode = { ...selectedNode }; // Trigger reactivity
      }
    }
    
    saveWorkflowToDatabase(false); // Silent auto-save
  }
  
  // Connection rendering helpers
  function getConnectionPath(sourceId: string, targetId: string): string {
    const sourceNode = nodes.find(n => n.id === sourceId);
    const targetNode = nodes.find(n => n.id === targetId);
    
    if (!sourceNode || !targetNode) {
      console.log('⚠️ CONNECTION PATH: Missing nodes for connection', sourceId, '->', targetId);
      return '';
    }
    
    // Determine connection type
    const connection = edges.find(e => e.source === sourceId && e.target === targetId);
    const connectionType = connection?.type || 'sequential';
    
    // 🌟 ENHANCED CONNECTION POSITIONING: Handle different node types and connection points
    let sourcePos, targetPos;
    
    // Calculate source position based on node type and connection type
    if (sourceNode.type === 'GroupChatManager') {
      const sourceWidth = 300;
      const sourceHeight = 120;
      
      if (connectionType === 'delegate') {
        // Delegate connection from bottom of GroupChatManager
        sourcePos = {
          x: sourceNode.position.x + CANVAS_CENTER_X + sourceWidth / 2, // Bottom center
          y: sourceNode.position.y + CANVAS_CENTER_Y + sourceHeight     // Bottom edge
        };
      } else {
        // Regular workflow connection from right side
        sourcePos = {
          x: sourceNode.position.x + CANVAS_CENTER_X + sourceWidth,     // Right edge
          y: sourceNode.position.y + CANVAS_CENTER_Y + sourceHeight / 3  // Top third (output handle)
        };
      }
    } else {
      // Standard node positioning
      const sourceWidth = 250;
      const sourceHeight = 80;
      sourcePos = {
        x: sourceNode.position.x + CANVAS_CENTER_X + sourceWidth, // Right edge
        y: sourceNode.position.y + CANVAS_CENTER_Y + sourceHeight / 2  // Center height
      };
    }
    
    // Calculate target position based on node type and connection type
    if (targetNode.type === 'GroupChatManager') {
      const targetHeight = 120;
      
      if (connectionType === 'delegate' || connectionType === 'delegate_return') {
        // Delegate connection to bottom of GroupChatManager
        targetPos = {
          x: targetNode.position.x + CANVAS_CENTER_X + 150,          // Center horizontally
          y: targetNode.position.y + CANVAS_CENTER_Y + targetHeight  // Bottom edge
        };
      } else {
        // Regular workflow connection to left side
        targetPos = {
          x: targetNode.position.x + CANVAS_CENTER_X,                // Left edge
          y: targetNode.position.y + CANVAS_CENTER_Y + targetHeight / 3  // Top third (input handle)
        };
      }
    } else if (targetNode.type === 'DelegateAgent') {
      // Connection to delegate agent (from GroupChatManager)
      const targetHeight = 80;
      targetPos = {
        x: targetNode.position.x + CANVAS_CENTER_X,              // Left edge
        y: targetNode.position.y + CANVAS_CENTER_Y + targetHeight / 2  // Center height
      };
    } else {
      // Standard node positioning
      const targetHeight = 80;
      targetPos = {
        x: targetNode.position.x + CANVAS_CENTER_X,              // Left edge
        y: targetNode.position.y + CANVAS_CENTER_Y + targetHeight / 2  // Center height
      };
    }
    
    // Create path based on connection type
    let path;
    if (connectionType === 'delegate') {
      // Special curved path for delegate connections (from bottom to side)
      const deltaY = Math.abs(targetPos.y - sourcePos.y);
      const controlOffset = Math.max(50, deltaY * 0.3);
      
      path = `M ${sourcePos.x} ${sourcePos.y} C ${sourcePos.x} ${sourcePos.y + controlOffset}, ${targetPos.x - controlOffset} ${targetPos.y}, ${targetPos.x} ${targetPos.y}`;
    } else {
      // Standard curved path for regular connections
      const deltaX = Math.abs(targetPos.x - sourcePos.x);
      const controlOffset = Math.max(50, deltaX * 0.5);
      
      path = `M ${sourcePos.x} ${sourcePos.y} C ${sourcePos.x + controlOffset} ${sourcePos.y}, ${targetPos.x - controlOffset} ${targetPos.y}, ${targetPos.x} ${targetPos.y}`;
    }
    
    // Debug log for path updates
    console.log('📏 ENHANCED CONNECTION:', {
      connection: `${sourceId.slice(-4)} -> ${targetId.slice(-4)}`,
      type: connectionType,
      sourceType: sourceNode.type,
      targetType: targetNode.type,
      sourcePos,
      targetPos
    });
    
    return path;
  }
  
  function getTempConnectionPath(): string {
    if (!sourceNode || !isConnecting) {
      console.log('⚠️ TEMP CONNECTION: Missing sourceNode or not connecting');
      return '';
    }
    
    // 🌟 ENHANCED TEMP CONNECTION: Handle different source node types
    let sourcePos;
    
    if (sourceNode.type === 'GroupChatManager') {
      const sourceWidth = 300;
      const sourceHeight = 120;
      
      // For GroupChatManager, start from the appropriate handle based on mouse position
      const nodeCenter = {
        x: sourceNode.position.x + CANVAS_CENTER_X + sourceWidth / 2,
        y: sourceNode.position.y + CANVAS_CENTER_Y + sourceHeight / 2
      };
      
      // Determine if we're connecting from bottom (delegate) or right (output)
      const isBottomConnection = mousePosition.y > nodeCenter.y;
      
      if (isBottomConnection) {
        // Delegate connection from bottom
        sourcePos = {
          x: sourceNode.position.x + CANVAS_CENTER_X + sourceWidth / 2,
          y: sourceNode.position.y + CANVAS_CENTER_Y + sourceHeight
        };
      } else {
        // Regular connection from right
        sourcePos = {
          x: sourceNode.position.x + CANVAS_CENTER_X + sourceWidth,
          y: sourceNode.position.y + CANVAS_CENTER_Y + sourceHeight / 3
        };
      }
    } else {
      // Standard node positioning
      const sourceWidth = sourceNode.type === 'DelegateAgent' ? 250 : 250;
      const sourceHeight = 80;
      sourcePos = {
        x: sourceNode.position.x + CANVAS_CENTER_X + sourceWidth,
        y: sourceNode.position.y + CANVAS_CENTER_Y + sourceHeight / 2
      };
    }
    
    // Create a smooth curve for the temporary connection
    const deltaX = mousePosition.x - sourcePos.x;
    const deltaY = mousePosition.y - sourcePos.y;
    
    let path;
    // Special handling for delegate connections (vertical component)
    if (sourceNode.type === 'GroupChatManager' && mousePosition.y > sourcePos.y) {
      const controlOffset = Math.max(50, Math.abs(deltaY) * 0.3);
      path = `M ${sourcePos.x} ${sourcePos.y} C ${sourcePos.x} ${sourcePos.y + controlOffset}, ${mousePosition.x - Math.abs(deltaX) * 0.3} ${mousePosition.y}, ${mousePosition.x} ${mousePosition.y}`;
    } else if (Math.abs(deltaX) > 50) {
      const controlOffset = Math.abs(deltaX) * 0.3;
      path = `M ${sourcePos.x} ${sourcePos.y} C ${sourcePos.x + controlOffset} ${sourcePos.y}, ${mousePosition.x - controlOffset} ${mousePosition.y}, ${mousePosition.x} ${mousePosition.y}`;
    } else {
      path = `M ${sourcePos.x} ${sourcePos.y} L ${mousePosition.x} ${mousePosition.y}`;
    }
    
    console.log('📍 ENHANCED TEMP CONNECTION:', {
      sourceType: sourceNode.type,
      sourcePos,
      mousePos: mousePosition,
      path: path.substring(0, 50) + '...'
    });
    return path;
  }
  
  // Delete functions
  function deleteSelectedNode() {
    if (!selectedNode) return;
    
    if (confirm(`Delete agent "${selectedNode.data.name}"?`)) {
      nodes = nodes.filter(n => n.id !== selectedNode.id);
      edges = edges.filter(e => e.source !== selectedNode.id && e.target !== selectedNode.id);
      
      selectedNode = null;
      showProperties = false;
      
      console.log('🗑️ CANVAS: Node deleted');
      saveWorkflowToDatabase(false); // Silent auto-save
    }
  }
  
  function deleteConnection(connection: any) {
    if (confirm('Delete this connection?')) {
      // Check if this is a delegate connection to a Group Chat Manager
      const sourceNode = nodes.find(n => n.id === connection.source);
      const isDelegateConnection = connection.type === 'delegate' && 
                                  sourceNode && 
                                  sourceNode.type === 'GroupChatManager';
      
      // Remove the connection
      edges = edges.filter(e => e.id !== connection.id);
      
      if (selectedEdge?.id === connection.id) {
        selectedEdge = null;
        showConnectionProperties = false;
      }
      
      console.log('✅ CANVAS: Connection deleted:', connection);
      
      // Trigger Group Chat Manager prompt regeneration if delegate connection was deleted
      if (isDelegateConnection) {
        console.log('🔧 GROUP CHAT MANAGER: Delegate connection deleted, will trigger prompt regeneration');
        // The reactive statement in NodePropertiesPanel will handle this
        // Force update selectedNode if it's the Group Chat Manager
        if (selectedNode && selectedNode.id === sourceNode.id) {
          selectedNode = { ...selectedNode }; // Trigger reactivity
        }
      }
      
      saveWorkflowToDatabase(false); // Silent auto-save
    }
  }
  
  function handleConnectionUpdate(event: CustomEvent) {
    const updatedConnection = event.detail;
    const connectionIndex = edges.findIndex(e => e.id === updatedConnection.id);
    if (connectionIndex >= 0) {
      edges[connectionIndex] = updatedConnection;
      edges = [...edges];
      selectedEdge = updatedConnection;
      
      console.log('✅ CANVAS: Connection updated:', updatedConnection);
      saveWorkflowToDatabase(false); // Silent auto-save
    }
  }
  
  function handleConnectionDelete(event: CustomEvent) {
    const connection = event.detail;
    deleteConnection(connection);
    showConnectionProperties = false;
  }
  
  function handleConnectionClick(connection: any) {
    console.log('🔧 Opening connection properties for:', connection.id.slice(-8));
    
    // Find source and target nodes
    const sourceNode = nodes.find(n => n.id === connection.source);
    const targetNode = nodes.find(n => n.id === connection.target);
    
    // Don't show properties for GroupChatManager <-> DelegateAgent connections
    if ((sourceNode?.type === 'GroupChatManager' && targetNode?.type === 'DelegateAgent') ||
        (sourceNode?.type === 'DelegateAgent' && targetNode?.type === 'GroupChatManager')) {
      console.log('🔧 Connection properties disabled for GroupChatManager-DelegateAgent connection');
      if (toasts && toasts.info) {
        toasts.info('Connection properties are not configurable for GroupChatManager-DelegateAgent connections. They default to Sequential.');
      }
      return; // Don't show properties panel
    }
    
    // Clear any selected node
    selectedNode = null;
    showProperties = false;
    
    // Set connection as selected
    selectedEdge = connection;
    showConnectionProperties = true;
    
    // Force reactivity update
    connectionUpdateTrigger += 1;
    
    console.log('✅ Connection properties panel opened');
  }
  
  // Helper functions
  function getAgentIcon(agentType: string): string {
    const agentConfig = agentTypes[agentType];
    if (agentConfig) {
      return agentConfig.icon;
    }
    
    switch (agentType) {
      case 'StartNode': return 'fa-play';
      case 'UserProxyAgent': return 'fa-user';
      case 'AssistantAgent': return 'fa-robot';
      case 'GroupChatManager': return 'fa-users';
      case 'DelegateAgent': return 'fa-handshake';
      case 'EndNode': return 'fa-stop';
      case 'MCPServer': return 'fa-server';
      default: return 'fa-cog';
    }
  }
  
  function getAgentColor(agentType: string): string {
    const agentConfig = agentTypes[agentType];
    if (agentConfig) {
      return agentConfig.color;
    }
    
    switch (agentType) {
      case 'StartNode': return '#10b981';
      case 'UserProxyAgent': return '#3b82f6';
      case 'AssistantAgent': return '#002147';
      case 'GroupChatManager': return '#8b5cf6';
      case 'DelegateAgent': return '#f59e0b';
      case 'EndNode': return '#ef4444';
      case 'MCPServer': return '#8b5cf6';
      default: return '#6b7280';
    }
  }
  
  function getDisplayName(agentType: string): string {
    switch (agentType) {
      case 'UserProxyAgent': return 'User Proxy Agent';
      case 'AssistantAgent': return 'AI Assistant Agent';
      case 'GroupChatManager': return 'Group Chat Manager';
      case 'DelegateAgent': return 'Delegate Agent';
      case 'StartNode': return 'Start Node';
      case 'EndNode': return 'End Node';
      case 'MCPServer': return 'MCP Server';
      default: return agentType;
    }
  }
  
  function getShortDescription(agentType: string): string {
    switch (agentType) {
      case 'UserProxyAgent': return 'Human-in-the-loop agent';
      case 'AssistantAgent': return 'AI-powered assistant';
      case 'GroupChatManager': return 'Multi-agent coordinator';
      case 'DelegateAgent': return 'Specialized delegate';
      case 'StartNode': return 'Workflow entry point';
      case 'EndNode': return 'Workflow termination';
      case 'MCPServer': return 'External service integration';
      default: return 'Custom agent type';
    }
  }
  
  // Tooltip functions
  function handleAgentHover(event: MouseEvent, agentType: string) {
    const agentConfig = agentTypes[agentType];
    if (agentConfig) {
      hoveredAgent = agentConfig;
      tooltipPosition = {
        x: event.clientX + 10,
        y: event.clientY - 10
      };
    }
  }
  
  function handleAgentLeave() {
    hoveredAgent = null;
  }
  
  function getConnectionStyle(connection: any) {
    const type = connectionTypes.find(t => t.id === connection.type) || connectionTypes[0];
    return {
      stroke: type.color,
      strokeWidth: selectedEdge?.id === connection.id ? type.strokeWidth + 1 : type.strokeWidth,
      strokeDasharray: connection.type === 'conditional' ? '8,4' : 
                      connection.type === 'parallel' ? '4,4' : 
                      connection.type === 'feedback' ? '12,4,4,4' : 'none'
    };
  }

</script>

<!-- Designer Mode Header Bar (fixed at top when active) -->
{#if designerMode}
  <div class="fixed top-0 left-0 right-0 z-[10000] flex items-center justify-between px-4 py-2 shadow-lg" style="background-color: #002147;">
    <div class="flex items-center space-x-3">
      <div class="w-8 h-8 rounded-lg flex items-center justify-center" style="background-color: rgba(255,255,255,0.2);">
        <i class="fas fa-expand-arrows-alt" style="color: white;"></i>
      </div>
      <div>
        <h2 class="font-semibold" style="color: white;">Designer Mode</h2>
        <p class="text-xs" style="color: rgba(255,255,255,0.8);">{workflow?.name || 'Workflow'} - Press ESC to exit</p>
      </div>
    </div>
    
    <div class="flex items-center space-x-3">
      <!-- Workflow info -->
      <div class="text-sm px-3 py-1.5 rounded-lg" style="color: white; background-color: rgba(255,255,255,0.15);">
        {nodes.length} agents • {edges.length} connections
      </div>
      
      <!-- Exit Designer Mode Button -->
      <button
        class="flex items-center space-x-2 px-4 py-2 bg-white rounded-lg hover:bg-gray-100 transition-all font-medium shadow-md"
        style="color: #002147;"
        on:click={exitDesignerMode}
        title="Exit Designer Mode (ESC)"
      >
        <i class="fas fa-compress-arrows-alt"></i>
        <span>Exit Designer Mode</span>
      </button>
    </div>
  </div>
{/if}

<!-- Main Workflow Designer (becomes fullscreen when in designer mode) -->
<div 
  class="workflow-designer flex bg-white w-full {designerMode ? 'fixed inset-0 z-[9999] pt-12' : 'h-full'}"
  class:designer-mode-active={designerMode}
  role={designerMode ? 'dialog' : undefined}
  aria-modal={designerMode ? 'true' : undefined}
  aria-label={designerMode ? 'Designer Mode - Full Screen Workflow Editor' : undefined}
>
  <!-- Agent Palette (Left Sidebar) -->
  {#if showPalette}
    <div class="w-64 border-r border-gray-200 bg-gray-50 flex flex-col">
      <div class="p-4 border-b border-gray-200 bg-white">
        <div class="flex items-center justify-between">
          <h3 class="font-semibold text-gray-900">Agent Components</h3>
          <button
            class="p-1 rounded hover:bg-gray-100 transition-colors"
            on:click={() => showPalette = false}
            title="Hide Palette"
          >
            <i class="fas fa-chevron-left text-gray-500"></i>
          </button>
        </div>
        <p class="text-xs text-gray-600 mt-1">Drag components to the canvas</p>
      </div>
      
      <div class="p-4 space-y-3 flex-1 overflow-y-auto">
        <!-- All Agent Types (ensuring DelegateAgent is always included) -->
        {#each ['StartNode', 'UserProxyAgent', 'AssistantAgent', 'GroupChatManager', 'DelegateAgent', 'MCPServer', 'EndNode'].filter(type => agentTypes[type]) as agentType}
          <div
            class="agent-component p-3 border border-gray-200 rounded-lg bg-white hover:border-oxford-blue hover:shadow-sm transition-all cursor-move select-none"
            draggable="true"
            on:dragstart={() => handleDragStart(agentType)}
            on:mouseenter={(e) => handleAgentHover(e, agentType)}
            on:mouseleave={handleAgentLeave}
          >
            <div class="flex items-center space-x-3">
              <div 
                class="w-8 h-8 text-white rounded-lg flex items-center justify-center text-sm"
                style="background-color: {getAgentColor(agentType)};"
              >
                <i class="fas {getAgentIcon(agentType)}"></i>
              </div>
              <div class="flex-1 min-w-0">
                <div class="font-medium text-sm text-gray-900">
                  {agentTypes[agentType]?.name || getDisplayName(agentType)}
                </div>
                <div class="text-xs text-gray-600 truncate">
                  {agentTypes[agentType]?.description || getShortDescription(agentType)}
                </div>
              </div>
            </div>
          </div>
        {/each}
      </div>
    </div>
  {:else}
    <!-- Collapsed Palette Toggle -->
    <div class="w-12 border-r border-gray-200 bg-gray-50 flex flex-col items-center py-4">
      <button
        class="p-2 rounded hover:bg-gray-100 transition-colors"
        on:click={() => showPalette = true}
        title="Show Palette"
      >
        <i class="fas fa-chevron-right text-gray-500"></i>
      </button>
    </div>
  {/if}

  
  <!-- Main Canvas Area -->
  <div class="flex-1 flex flex-col">
    <!-- Canvas Toolbar -->
    <div class="bg-white border-b border-gray-200 px-4 py-3">
      <div class="flex items-center justify-between">
        <div class="flex items-center space-x-4">
          <h3 class="font-semibold text-gray-900">{workflow.name}</h3>
          
          <div class="text-sm text-gray-600">
            {nodes.length} agents • {edges.length} connections
            {#if isConnecting}
              • <span class="text-blue-600 font-medium">Creating connection...</span>
            {/if}
            {#if showConnectionProperties && selectedEdge}
              • <span class="text-green-600 font-medium">📋 Connection Properties: {selectedEdge.id}</span>
            {/if}
          </div>

        </div>
        
        <div class="flex items-center space-x-2">
          <!-- Zoom Controls -->
          <div class="flex items-center space-x-1 bg-gray-100 rounded-lg p-1">
            <button
              class="p-1.5 hover:bg-white rounded text-sm transition-colors" 
              on:click={handleZoomOut}
              disabled={zoomLevel <= MIN_ZOOM}
              title="Zoom Out (Ctrl + Scroll)"
            >
              <i class="fas fa-search-minus"></i>
            </button>
            <span class="text-xs font-medium px-2 py-1 bg-white rounded min-w-[50px] text-center">
              {Math.round(zoomLevel * 100)}%
            </span>
            <button
              class="p-1.5 hover:bg-white rounded text-sm transition-colors"
              on:click={handleZoomIn}
              disabled={zoomLevel >= MAX_ZOOM}
              title="Zoom In (Ctrl + Scroll)"
            >
              <i class="fas fa-search-plus"></i>
            </button>
            <button
              class="p-1.5 hover:bg-white rounded text-sm transition-colors"
              on:click={resetZoom}
              title="Reset Zoom (100%)"
            >
              <i class="fas fa-expand-arrows-alt"></i>
            </button>
            <!-- Center View button -->
            <button
              class="p-1.5 hover:bg-white rounded text-sm transition-colors"
              on:click={centerView}
              title="Center View"
            >
              <i class="fas fa-crosshairs"></i>
            </button>

          </div>
          
          <!-- Delete buttons -->
          {#if selectedNode}
            <button
              class="px-3 py-1.5 text-red-600 hover:bg-red-50 rounded text-sm font-medium transition-colors"
              on:click={deleteSelectedNode}
            >
              <i class="fas fa-trash mr-1"></i>
              Delete Agent
            </button>
          {/if}
          
          {#if selectedEdge}
            <button
              class="px-3 py-1.5 text-red-600 hover:bg-red-50 rounded text-sm font-medium transition-colors"
              on:click={() => deleteConnection(selectedEdge)}
            >
              <i class="fas fa-unlink mr-1"></i>
              Delete Connection
            </button>
          {/if}
          
          <!-- Save button -->
          <button
            class="px-4 py-1.5 bg-oxford-blue text-white rounded hover:bg-blue-700 text-sm font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            on:click={() => {
              console.log('🔄 SAVE BUTTON: Clicked! Current state:', {
                projectId: projectId,
                workflowId: workflow?.workflow_id,
                workflowName: workflow?.name,
                nodesCount: nodes.length,
                edgesCount: edges.length,
                saving,
                toastsAvailable: !!toasts
              });
              saveWorkflowToDatabase(true);
            }}
            disabled={saving}
          >
            {#if saving}
              <i class="fas fa-spinner fa-spin mr-1"></i>
              Saving...
            {:else}
              <i class="fas fa-save mr-1"></i>
              Save Workflow
            {/if}
          </button>
          

        </div>
      </div>
    </div>
    
    <!-- Canvas -->
    <div class="flex-1 relative bg-gray-50 overflow-hidden">
      <div 
        bind:this={canvasElement}
        class="absolute inset-0 w-full h-full cursor-grab canvas-background"
        style="cursor: {isPanning || isCanvasDragging ? 'grabbing' : 'grab'};"
        on:drop={handleCanvasDrop}
        on:dragover={handleCanvasDragOver}
        on:mousemove={handleCanvasMouseMove}
        on:mousedown={handleCanvasMouseDown}
        on:contextmenu={(e) => e.preventDefault()}
        on:mouseenter={() => isMouseOverCanvas = true}
        on:mouseleave={() => isMouseOverCanvas = false}
        on:wheel={handleWheel}
      >
        <!-- Instructions Overlay - Dismissable - MOVED OUTSIDE ZOOMABLE CONTAINER -->
        {#if showInstructions}
          <div class="instructions-overlay absolute top-4 left-4 bg-white rounded-lg shadow-lg p-3 border border-gray-200 max-w-sm" style="z-index: 1000;">
            <div class="flex items-center justify-between text-sm mb-2">
              <div class="flex items-center space-x-2">
                <i class="fas fa-info-circle text-blue-500"></i>
                <span class="font-medium text-gray-900">Canvas Controls</span>
              </div>
              <button
                class="p-1 hover:bg-gray-100 rounded text-gray-500 hover:text-gray-700 transition-colors"
                on:click|stopPropagation={() => {
                  console.log('🔧 CANVAS: Dismissing instructions overlay');
                  showInstructions = false;
                }}
                title="Dismiss instructions"
                style="cursor: pointer; z-index: 1001;"
              >
                <i class="fas fa-times text-xs"></i>
              </button>
            </div>
            <div class="text-xs text-gray-600 space-y-1">
              <div>• <strong>Drag canvas</strong> to navigate around infinite workspace</div>
              <div>• <strong>Drag agents</strong> from palette to canvas</div>
              <div>• <strong>Drag nodes</strong> to reposition (connections follow)</div>
              <div>• <strong>Drag blue handle</strong> to connect agents</div>
              <div>• <strong>Ctrl + Scroll</strong> to zoom in/out (10%-500%)</div>
              <div>• <strong>Click crosshairs</strong> to center view on nodes</div>
              <div>• <strong>Click connections</strong> to configure properties</div>
              <div>• <strong>Click agents</strong> to configure settings</div>
            </div>
            {#if isConnecting}
              <div class="mt-2 p-2 bg-blue-50 border border-blue-200 rounded text-xs text-blue-700">
                <strong>Connecting mode:</strong> Drop on target agent to connect
              </div>
            {/if}
            {#if zoomLevel !== 1}
              <div class="mt-2 p-2 bg-green-50 border border-green-200 rounded text-xs text-green-700">
                <strong>Zoom:</strong> {Math.round(zoomLevel * 100)}% • Click reset to return to 100%
              </div>
            {/if}
          </div>
        {/if}
        
        <!-- Zoomable and Pannable Content Container - Fixed Viewport -->
        <div 
          class="absolute"
          style="
            transform: translate3d({panOffset.x}px, {panOffset.y}px, 0) scale({zoomLevel}); 
            transform-origin: 0 0;
            will-change: transform;
            left: 0px;
            top: 0px;
            width: {CANVAS_WIDTH + 20000}px; 
            height: {CANVAS_HEIGHT + 20000}px;
          "
        >

        <!-- Background Grid for Infinite Canvas - Properly Centered -->
        <div 
          class="absolute"
          style="
            left: 0px; 
            top: 0px; 
            width: {CANVAS_WIDTH + 20000}px; 
            height: {CANVAS_HEIGHT + 20000}px;
            background-image: 
              linear-gradient(to right, rgba(0,0,0,0.1) 1px, transparent 1px),
              linear-gradient(to bottom, rgba(0,0,0,0.1) 1px, transparent 1px);
            background-size: 50px 50px;
            background-position: {CANVAS_CENTER_X % 50}px {CANVAS_CENTER_Y % 50}px;
            opacity: 0.3;
            pointer-events: none;
          "
        ></div>
        
        <!-- Node Layer -->
        <div class="absolute inset-0" style="z-index: 40; pointer-events: none;">
          {#each nodes as node}
            {@const isValidTarget = isConnecting && sourceNode && node.id !== sourceNode.id}
            {@const isCurrentSource = isConnecting && sourceNode && node.id === sourceNode.id}
            {@const isRequiringInput = agentsRequiringInput.has(node.id)}
            {@const nodeWidth = node.type === 'GroupChatManager' ? 300 : 250}
            {@const nodeHeight = node.type === 'GroupChatManager' ? 120 : 80}
            <div 
              class="agent-node absolute bg-white border-2 rounded-xl shadow-lg transition-all duration-200 hover:shadow-xl cursor-pointer select-none {selectedNode?.id === node.id ? 'border-oxford-blue ring-2 ring-oxford-blue ring-opacity-20' : isRequiringInput ? 'border-orange-400 ring-2 ring-orange-400 ring-opacity-30 animate-pulse human-input-node' : isValidTarget ? 'border-green-400 ring-2 ring-green-400 ring-opacity-30' : isCurrentSource ? 'border-blue-500 ring-2 ring-blue-500 ring-opacity-30' : 'border-gray-300 hover:border-oxford-blue'}"
              style="left: {node.position.x + CANVAS_CENTER_X}px; top: {node.position.y + CANVAS_CENTER_Y}px; width: {nodeWidth}px; height: {nodeHeight}px; pointer-events: auto;"
              data-node-id={node.id}
              on:click={(e) => handleNodeClick(node, e)}
              on:mousedown={(e) => {
                // Only handle node dragging if not clicking on connection handle
                const target = e.target as HTMLElement;
                if (!target.classList.contains('connection-handle') && !target.closest('.connection-handle')) {
                  handleNodeMouseDown(e, node);
                }
              }}
            >
              <!-- Node Content -->
              {#if node.type === 'GroupChatManager'}
                <!-- Enhanced GroupChatManager Layout -->
                <div class="h-full flex flex-col p-3">
                  <!-- Header Section -->
                  <div class="flex items-center space-x-3 mb-2">
                    <div 
                      class="w-10 h-10 rounded-lg flex items-center justify-center text-white shadow-md"
                      style="background-color: {getAgentColor(node.type)};"
                    >
                      <i class="fas {getAgentIcon(node.type)} text-sm"></i>
                    </div>
                    <div class="flex-1 min-w-0">
                      <div class="font-semibold text-gray-900 truncate text-sm">
                        {node.data?.name || node.data?.label || node.type}
                      </div>
                      <div class="text-xs text-gray-600">
                        Enhanced Chat Manager
                      </div>
                    </div>
                  </div>
                  
                  <!-- Connection Stats -->
                  <div class="flex justify-between text-xs text-gray-500">
                    <div class="flex items-center">
                      <i class="fas fa-arrow-left mr-1 text-blue-500"></i>
                      {edges.filter(e => e.target === node.id && e.type !== 'delegate').length} input
                    </div>
                    <div class="flex items-center">
                      <i class="fas fa-arrow-right mr-1 text-green-500"></i>
                      {edges.filter(e => e.source === node.id && e.type !== 'delegate').length} output
                    </div>
                    <div class="flex items-center">
                      <i class="fas fa-handshake mr-1 text-orange-500"></i>
                      {edges.filter(e => (e.source === node.id || e.target === node.id) && e.type === 'delegate').length} delegates
                    </div>
                  </div>
                  
                  <!-- Delegate Management Info -->
                  {#if node.data?.delegate_connections && node.data.delegate_connections.length > 0}
                    <div class="mt-2 p-1 bg-orange-50 rounded text-xs text-orange-700">
                      <i class="fas fa-users mr-1"></i>
                      {node.data.delegate_connections.length} active delegates
                    </div>
                  {/if}
                </div>
              {:else}
                <!-- Standard Agent Layout -->
                <div class="h-full flex items-center p-3 space-x-3">
                  <!-- Agent Icon -->
                  <div 
                    class="w-12 h-12 rounded-lg flex items-center justify-center text-white shadow-md"
                    style="background-color: {getAgentColor(node.type)};"
                  >
                    <i class="fas {getAgentIcon(node.type)} text-lg"></i>
                  </div>
                  
                  <!-- Agent Info -->
                  <div class="flex-1 min-w-0">
                    <div class="font-semibold text-gray-900 truncate text-sm">
                      {node.data?.name || node.data?.label || node.type}
                    </div>
                    <div class="text-xs text-gray-600 truncate">
                      {node.type === 'DelegateAgent' ? 'Specialized Agent' : node.type}
                    </div>
                    <div class="text-xs text-gray-500 mt-1">
                      <i class="fas fa-arrow-right mr-1"></i>
                      {edges.filter(e => e.source === node.id).length} out •
                      <i class="fas fa-arrow-left mr-1"></i>
                      {edges.filter(e => e.target === node.id).length} in
                    </div>
                  </div>
                </div>
              {/if}
              
              <!-- Human Input Required Badge - Visual Feedback Enhancement -->
              {#if isRequiringInput}
                <div 
                  class="absolute -top-2 -right-2 w-6 h-6 bg-orange-500 text-white rounded-full flex items-center justify-center text-xs font-bold shadow-lg animate-pulse z-50"
                  title="Human input required"
                  style="border: 2px solid white;"
                >
                  <i class="fas fa-user text-xs"></i>
                </div>
                <!-- Pulsing ring animation -->
                <div 
                  class="absolute -top-2 -right-2 w-6 h-6 border-2 border-orange-400 rounded-full animate-ping z-40"
                  style="opacity: 0.5;"
                ></div>
              {/if}
              
              <!-- Connection Handles - Enhanced for GroupChatManager -->
              {#if node.type === 'GroupChatManager'}
                <!-- Input Handle (Left side) - for incoming workflow -->
                <div 
                  class="absolute left-0 top-1/3 w-4 h-4 rounded-full border-2 border-white shadow-md transition-all {isValidTarget ? 'bg-green-500 scale-110 animate-pulse' : 'bg-blue-400'}"
                  style="transform: translate(-50%, -50%); z-index: 50;"
                  title="Workflow Input"
                ></div>
                
                <!-- Output Handle (Right side) - for outgoing workflow -->
                <div 
                  class="connection-handle absolute right-0 top-1/3 w-4 h-4 rounded-full border-2 border-white shadow-lg cursor-crosshair hover:scale-110 transition-all duration-200 {isCurrentSource ? 'bg-blue-500' : 'bg-green-500'}"
                  style="transform: translate(50%, -50%); z-index: 100;"
                  title="Workflow Output - Click and drag to connect"
                  on:mousedown|stopPropagation={(e) => {
                    console.log('🟦 OUTPUT HANDLE: Workflow output clicked for', node.data.name);
                    handleConnectionStart(e, node);
                  }}
                >
                  <div class="absolute inset-0 rounded-full opacity-30 {isCurrentSource ? 'bg-blue-400 animate-pulse' : 'bg-green-400'}"></div>
                </div>
                
                <!-- Delegate Handle (Bottom center) - for delegate connections -->
                <div 
                  class="connection-handle absolute left-1/2 bottom-0 w-5 h-5 rounded-full border-2 border-white shadow-lg cursor-crosshair hover:scale-110 transition-all duration-200 {isCurrentSource ? 'bg-blue-500' : 'bg-orange-500'}"
                  style="transform: translate(-50%, 50%); z-index: 100;"
                  title="Delegate Connection - Click and drag to connect delegates"
                  on:mousedown|stopPropagation={(e) => {
                    console.log('🤝 DELEGATE HANDLE: Delegate connection clicked for', node.data.name);
                    handleConnectionStart(e, node);
                  }}
                >
                  <div class="absolute inset-0 rounded-full opacity-30 {isCurrentSource ? 'bg-blue-400 animate-pulse' : 'bg-orange-400'}"></div>
                  <i class="fas fa-handshake text-xs text-white absolute inset-0 flex items-center justify-center"></i>
                </div>
              {:else if node.type === 'DelegateAgent'}
                <!-- Delegate Agent - Special connection to GroupChatManager only -->
                <div 
                  class="connection-handle absolute right-0 top-1/2 w-4 h-4 rounded-full border-2 border-white shadow-lg cursor-crosshair hover:scale-110 transition-all duration-200 {isCurrentSource ? 'bg-blue-500' : 'bg-orange-500'}"
                  style="transform: translate(50%, -50%); z-index: 100;"
                  title="Connect to Group Chat Manager only"
                  on:mousedown|stopPropagation={(e) => {
                    console.log('🤝 DELEGATE HANDLE: Delegate connection clicked for', node.data.name);
                    handleConnectionStart(e, node);
                  }}
                >
                  <div class="absolute inset-0 rounded-full opacity-30 {isCurrentSource ? 'bg-blue-400 animate-pulse' : 'bg-orange-400'}"></div>
                </div>
                
                <!-- Input Handle (Left side) -->
                <div 
                  class="absolute left-0 top-1/2 w-4 h-4 rounded-full border-2 border-white shadow-md transition-all {isValidTarget ? 'bg-green-500 scale-110 animate-pulse' : 'bg-orange-400'}"
                  style="transform: translate(-50%, -50%); z-index: 50;"
                  title="Connection from Group Chat Manager"
                ></div>
              {:else}
                <!-- Standard Agent Connection Handles -->
                <div 
                  class="connection-handle absolute right-0 top-1/2 w-4 h-4 rounded-full border-2 border-white shadow-lg cursor-crosshair hover:scale-110 transition-all duration-200 {isCurrentSource ? 'bg-blue-500' : 'bg-oxford-blue'}"
                  style="transform: translate(50%, -50%); z-index: 100;"
                  title="Click and drag to create connection"
                  on:mousedown|stopPropagation={(e) => {
                    console.log('🟦 HANDLE CLICK: Connection handle clicked for', node.data.name);
                    handleConnectionStart(e, node);
                  }}
                >
                  <div class="absolute inset-0 rounded-full opacity-30 {isCurrentSource ? 'bg-blue-400 animate-pulse' : 'bg-oxford-blue'}"></div>
                </div>
                
                <!-- Input Handle (Left side) -->
                <div 
                  class="absolute left-0 top-1/2 w-4 h-4 rounded-full border-2 border-white shadow-md transition-all {isValidTarget ? 'bg-green-500 scale-110 animate-pulse' : 'bg-gray-400'}"
                  style="transform: translate(-50%, -50%); z-index: 50;"
                  title="Connection input"
                ></div>
              {/if}
            </div>
          {/each}
        </div>
        
        <!-- Background Grid Pattern -->
        <div 
          class="absolute inset-0 w-full h-full canvas-background"
          style="
            background-image: radial-gradient(circle, #e5e7eb 1px, transparent 1px);
            background-size: 50px 50px;
            background-position: {panOffset.x % 50}px {panOffset.y % 50}px;
            opacity: 0.3;
            pointer-events: none;
          "
        ></div>
        
        <!-- SVG Layer for Connections - Fixed Viewport -->
        <svg 
          class="absolute workflow-canvas" 
          style="
            left: 0px;
            top: 0px;
            width: {CANVAS_WIDTH + 20000}px;
            height: {CANVAS_HEIGHT + 20000}px;
            z-index: 30; 
            isolation: isolate;
          " 
          key="svg-{connectionUpdateTrigger}"
        >
          
          
          <defs>
            <!-- Arrow markers -->
            {#each connectionTypes as type}
              <marker 
                id="arrow-{type.id}" 
                viewBox="0 0 10 10" 
                refX="9" 
                refY="3" 
                markerWidth="6" 
                markerHeight="6" 
                orient="auto"
                fill={type.color}
              >
                <path d="M0,0 L0,6 L9,3 z"></path>
              </marker>
            {/each}
          </defs>
          
          <!-- Render connections with dynamic paths -->
          {#each edges as connection (connection.id)}
            {@const style = getConnectionStyle(connection)}
            <!-- Force path recalculation by including connectionUpdateTrigger -->
            {@const path = connectionUpdateTrigger >= 0 ? getConnectionPath(connection.source, connection.target) : ''}
            
            <!-- Render connection path -->
            
            {#if path}
              <g class="connection-group">
                <!-- Wide invisible clickable path -->
                <path 
                  d={path}
                  stroke="transparent"
                  stroke-width="20"
                  fill="none"
                  style="pointer-events: stroke; cursor: pointer;"
                  on:click={(e) => {
                    e.stopPropagation();
                    console.log('✅ PATH CLICKED: Wide path clicked!', connection.id.slice(-8));
                    handleConnectionClick(connection);
                  }}
                />
                
                <!-- Visible connection path -->
                <path 
                  d={path}
                  stroke={style.stroke}
                  stroke-width={style.strokeWidth}
                  stroke-dasharray={style.strokeDasharray}
                  fill="none"
                  marker-end="url(#arrow-{connection.type || 'default'})"
                  class="transition-all duration-200"
                  style="pointer-events: visibleStroke; cursor: pointer;"
                  on:click={(e) => {
                    e.stopPropagation();
                    console.log('✅ PATH CLICKED: Visible path clicked!', connection.id.slice(-8));
                    handleConnectionClick(connection);
                  }}
                />
                
                
                
                <!-- Delete button for selected connection -->
                {#if selectedEdge?.id === connection.id}
                  {@const sourceNode = nodes.find(n => n.id === connection.source)}
                  {@const targetNode = nodes.find(n => n.id === connection.target)}
                  {#if sourceNode && targetNode}
                    {@const midX = (sourceNode.position.x + CANVAS_CENTER_X + 250 + targetNode.position.x + CANVAS_CENTER_X) / 2}
                    {@const midY = (sourceNode.position.y + CANVAS_CENTER_Y + 40 + targetNode.position.y + CANVAS_CENTER_Y + 40) / 2}
                    
                    <circle 
                      cx={midX} 
                      cy={midY} 
                      r="12" 
                      fill="white" 
                      stroke="#ef4444" 
                      stroke-width="2"
                      class="cursor-pointer"
                      on:click|stopPropagation={() => deleteConnection(connection)}
                    />
                    <text 
                      x={midX} 
                      y={midY + 4} 
                      text-anchor="middle" 
                      class="text-sm fill-red-600 font-bold cursor-pointer"
                      style="user-select: none;"
                      on:click|stopPropagation={() => deleteConnection(connection)}
                    >
                      ×
                    </text>
                  {/if}
                {/if}
              </g>
            {/if}
          {/each}
          
          <!-- Temporary connection line while creating connection -->
          {#if isConnecting && sourceNode && mousePosition}
            {#key `${mousePosition.x}-${mousePosition.y}`}
              <g class="temp-connection">
                <!-- Temporary path with enhanced visibility -->
                <path 
                  d={getTempConnectionPath()}
                  stroke="#002147"
                  stroke-width="3"
                  stroke-dasharray="8,4"
                  opacity="0.8"
                  fill="none"
                  class="animate-pulse"
                />
                
                <!-- Connection endpoint indicator -->
                <circle 
                  cx={mousePosition.x} 
                  cy={mousePosition.y} 
                  r="6" 
                  fill="#002147" 
                  opacity="0.6"
                  class="animate-pulse"
                />
              </g>
            {/key}
          {/if}
        </svg>
        
        <!-- Empty State -->
        {#if nodes.length === 0}
          <div 
            class="absolute flex items-center justify-center"
            style="
              left: {CANVAS_CENTER_X - 200}px; 
              top: {CANVAS_CENTER_Y - 100}px; 
              width: 400px; 
              height: 200px;
            "
          >
            <div class="text-center">
              <div class="w-20 h-20 bg-gray-200 text-gray-400 rounded-xl flex items-center justify-center mx-auto mb-4">
                <i class="fas fa-project-diagram text-3xl"></i>
              </div>
              <h3 class="text-lg font-medium text-gray-700 mb-2">Visual Workflow Canvas</h3>
              <p class="text-gray-500 mb-4">Drag agents to design your workflow</p>
              <div class="text-sm text-gray-400">
                <i class="fas fa-info-circle mr-1"></i>
                Drag canvas to pan • Ctrl + scroll to zoom
              </div>
            </div>
          </div>
        {/if}
        
        </div> <!-- Close zoomable container -->
      </div>
    </div>
  </div>
  

  
  <!-- Node Properties Panel (Right Sidebar or Modal) -->
  {#if showProperties && selectedNode}
    {#if isPanelMaximized}
      <!-- Maximized Modal View -->
      <div 
        class="fixed inset-0 bg-black bg-opacity-50 z-50 flex items-center justify-center p-4"
        on:click|self={() => isPanelMaximized = false}
        role="dialog"
        aria-modal="true"
        aria-label="Agent Properties Modal"
      >
        <div class="bg-white rounded-xl shadow-2xl w-[85vw] h-[90vh] overflow-hidden flex flex-col">
          <NodePropertiesPanel
            node={selectedNode}
            {capabilities}
            {projectId}
            workflowData={{ nodes, edges, workflow }}
            {bulkModelData}
            {modelsLoaded}
            {hierarchicalPaths}
            {hierarchicalPathsLoaded}
            {uploadedDocumentPaths}
            {uploadedDocumentPathsLoaded}
            documentsInfo={documentsInfo}
            {documentLlmStatus}
            isMaximized={true}
            on:nodeUpdate={(e) => {
              const updatedNode = e.detail;
              const nodeIndex = nodes.findIndex(n => n.id === updatedNode.id);

              console.log('🔄 WORKFLOW: Node update received for', updatedNode.id.slice(-4));

              if (nodeIndex >= 0) {
                const newNode = {
                  id: updatedNode.id,
                  type: updatedNode.type,
                  position: { ...updatedNode.position },
                  data: {
                    ...JSON.parse(JSON.stringify(updatedNode.data))
                  }
                };

                nodes = nodes.map((n, idx) => idx === nodeIndex ? newNode : n);

                if (selectedNode && selectedNode.id === newNode.id) {
                  selectedNode = newNode;
                }

                saveWorkflowToDatabase(false);
              }
            }}
            on:toggleMaximize={() => isPanelMaximized = false}
            on:close={() => {
              showProperties = false;
              selectedNode = null;
              isPanelMaximized = false;
            }}
          />
        </div>
      </div>
    {:else}
      <!-- Normal Sidebar View -->
      <div class="w-80 border-l border-gray-200 bg-white">
        <NodePropertiesPanel
          node={selectedNode}
          {capabilities}
          {projectId}
          workflowData={{ nodes, edges, workflow }}
          {bulkModelData}
          {modelsLoaded}
          {hierarchicalPaths}
          {hierarchicalPathsLoaded}
          {uploadedDocumentPaths}
          {uploadedDocumentPathsLoaded}
          documentsInfo={documentsInfo}
          {documentLlmStatus}
          isMaximized={false}
          on:nodeUpdate={(e) => {
            const updatedNode = e.detail;
            const nodeIndex = nodes.findIndex(n => n.id === updatedNode.id);

            console.log('🔄 WORKFLOW: Node update received for', updatedNode.id.slice(-4));

            if (nodeIndex >= 0) {
              const newNode = {
                id: updatedNode.id,
                type: updatedNode.type,
                position: { ...updatedNode.position },
                data: {
                  ...JSON.parse(JSON.stringify(updatedNode.data))
                }
              };

              console.log('🔄 WORKFLOW: Node update details', {
                nodeId: updatedNode.id.slice(-4),
                oldName: nodes[nodeIndex].data?.name || nodes[nodeIndex].data?.label,
                newName: newNode.data?.name || newNode.data?.label,
                oldDesc: (nodes[nodeIndex].data?.description || '').substring(0, 50),
                newDesc: (newNode.data?.description || '').substring(0, 50),
                oldData: nodes[nodeIndex].data,
                newData: newNode.data
              });

              nodes = nodes.map((n, idx) => idx === nodeIndex ? newNode : n);

              if (selectedNode && selectedNode.id === newNode.id) {
                selectedNode = newNode;
              }

              console.log('✅ WORKFLOW: Node updated successfully - name:', newNode.data?.name || newNode.data?.label, 'description:', (newNode.data?.description || '').substring(0, 50));
              saveWorkflowToDatabase(false);
            } else {
              console.error('❌ WORKFLOW: Node not found in array!', updatedNode.id);
            }
          }}
          on:toggleMaximize={() => isPanelMaximized = true}
          on:close={() => {
            showProperties = false;
            selectedNode = null;
          }}
        />
      </div>
    {/if}
  {/if}
  
  <!-- Connection Properties Panel (Right Sidebar) -->
  <!-- DEBUG: Connection panel visibility check -->
  <!-- Total connections: {edges.length} -->
  {#if showConnectionProperties && selectedEdge}
    <div class="w-80 border-l border-gray-200 bg-white">

      
      {#await import('./ConnectionPropertiesPanel.svelte')}
        <div class="p-4 flex items-center justify-center">
          <div class="animate-spin rounded-full h-6 w-6 border-b-2 border-oxford-blue"></div>
          <span class="ml-2 text-sm">Loading connection properties...</span>
        </div>
      {:then ConnectionPropertiesPanelModule}
        <svelte:component 
          this={ConnectionPropertiesPanelModule.default}
          connection={selectedEdge}
          nodes={nodes}
          on:connectionUpdate={handleConnectionUpdate}
          on:connectionDelete={handleConnectionDelete}
          on:close={() => {
            showConnectionProperties = false;
            selectedEdge = null;
          }}
        />
      {:catch error}
        <div class="p-4">
          <div class="text-red-600">Failed to load connection properties panel</div>
          <div class="text-sm text-gray-600 mt-2">Error: {error.message}</div>
        </div>
      {/await}
    </div>

  {/if}
</div>

<!-- Enhanced Tooltip -->
{#if hoveredAgent}
  <div 
    class="fixed z-[9999] bg-white rounded-lg shadow-xl border border-gray-200 p-4 max-w-sm pointer-events-none"
    style="left: {tooltipPosition.x}px; top: {tooltipPosition.y}px;"
  >
    <div class="flex items-center space-x-3 mb-3">
      <div 
        class="w-10 h-10 rounded-lg flex items-center justify-center text-white shadow-sm"
        style="background-color: {hoveredAgent.color};"
      >
        <i class="fas {hoveredAgent.icon} text-lg"></i>
      </div>
      <div class="flex-1">
        <div class="font-semibold text-gray-900">{hoveredAgent.name}</div>
        <div class="text-xs text-gray-500 font-medium">{hoveredAgent.category}</div>
      </div>
    </div>
    
    <div class="space-y-2 text-sm">
      <div class="text-gray-700">
        <strong>Description:</strong>
        <p class="mt-1">{hoveredAgent.description}</p>
      </div>
      
      <div class="text-gray-700">
        <strong>Functionality:</strong>
        <p class="mt-1">{hoveredAgent.functionality}</p>
      </div>
      
      <div class="text-gray-700">
        <strong>Use Cases:</strong>
        <ul class="mt-1 ml-4 space-y-0.5">
          {#each hoveredAgent.useCases as useCase}
            <li class="text-xs text-gray-600">• {useCase}</li>
          {/each}
        </ul>
      </div>
    </div>
  </div>
{/if}

<style>
  .agent-component:hover {
    transform: translateY(-1px);
  }
  
  .connection-group:hover path {
    stroke-width: 4 !important;
  }
  
  .workflow-designer {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', sans-serif;
  }
  
  :global(.oxford-blue) {
    color: #002147;
  }
  
  :global(.bg-oxford-blue) {
    background-color: #002147;
  }
  
  :global(.border-oxford-blue) {
    border-color: #002147;
  }
  
  /* 🌟 ANTI-FLICKER: GPU acceleration and stable transforms */
  .workflow-designer .absolute {
    backface-visibility: hidden;
    transform-style: preserve-3d;
    isolation: isolate;
  }
  
  /* 🌟 SMOOTH ZOOM: Prevent flickering during zoom operations */
  .workflow-designer [style*="transform"] {
    will-change: transform;
    backface-visibility: hidden;
    transform-style: preserve-3d;
  }
  
  /* 🌟 NODE STABILITY: Prevent node flickering */
  .agent-node {
    will-change: transform;
    backface-visibility: hidden;
    transform: translateZ(0);
  }
  
  /* Connection Handle Styling */
  .connection-handle {
    user-select: none;
    pointer-events: auto !important;
    will-change: transform;
  }
  
  .connection-handle:hover {
    box-shadow: 0 0 0 3px rgba(0, 33, 71, 0.3);
  }
  
  /* Instructions overlay z-index fix */
  .workflow-designer .instructions-overlay {
    z-index: 1000 !important;
    pointer-events: auto !important;
  }
  
  .workflow-designer .instructions-overlay button {
    z-index: 1001 !important;
    pointer-events: auto !important;
    cursor: pointer !important;
  }
  
  /* Enhanced agent component hover effects */
  .agent-component {
    transition: all 0.2s ease;
  }
  
  .agent-component:hover {
    transform: translateY(-1px);
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
  }
  
  /* 🌟 SVG STABILITY: Prevent SVG flickering during zoom */
  svg.workflow-canvas {
    will-change: transform;
    backface-visibility: hidden;
    transform: translateZ(0);
  }
  
  /* Tooltip animations */
  .fixed {
    animation: fadeIn 0.2s ease-out;
  }
  
  @keyframes fadeIn {
    from {
      opacity: 0;
      transform: translateY(-5px);
    }
    to {
      opacity: 1;
      transform: translateY(0);
    }
  }
  
  /* 🖼️ DESIGNER MODE: Full-screen immersive editing */
  .designer-mode-active {
    animation: designerModeEnter 0.3s ease-out;
  }
  
  @keyframes designerModeEnter {
    from {
      opacity: 0;
      transform: scale(0.98);
    }
    to {
      opacity: 1;
      transform: scale(1);
    }
  }
  
  /* Designer Mode header bar styling */
  .designer-mode-active .workflow-designer {
    border-radius: 0;
  }
</style>