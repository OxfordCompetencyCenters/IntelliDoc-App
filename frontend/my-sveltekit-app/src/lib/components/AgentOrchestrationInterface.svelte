<!-- AgentOrchestrationInterface.svelte - Database-Only Agent Orchestration -->
<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import { toasts } from '$lib/stores/toast';
  import api from '$lib/services/api';
  import { llmModelsService, ensureModelsLoaded, type BulkModelData } from '$lib/stores/llmModelsStore';
  import { workflowStatus, pendingInputsCount, isWorkflowStatusActive } from '$lib/stores/workflowStatus';
  import { validateWorkflowGraph } from '$lib/stores/workflowStore';
  import type { PendingHumanInput } from '$lib/services/humanInputService';
  
  // CRITICAL DEBUG: Test if component is loading at all
  console.log('🚨 COMPONENT TEST: AgentOrchestrationInterface.svelte is being parsed!');
  console.log('🚨 COMPONENT TEST: Current timestamp:', new Date().toISOString());
  
  export let project: any;
  export let projectId: string;
  
  // Main interface state
  let activeTab: 'designer' | 'history' = 'designer';
  let allWorkflows: any[] = [];
  let selectedWorkflow: any = null;
  let isExecuting = false;
  let currentExecutionId: string | null = null;
  let loading = true;
  let creatingWorkflow = false;
  
  // Designer Mode state - full-screen workflow designer
  let designerMode = false;
  
  // LLM Models pre-loading state
  let modelsLoading = false;
  let modelsLoaded = false;
  let modelsError: string | null = null;
  let bulkModelData: BulkModelData | null = null;
  let preloadProgress = { stage: 'idle', percentage: 0 };
  
  // Content Filter hierarchical paths state
  let hierarchicalPaths: any[] = [];
  let hierarchicalPathsLoading = false;
  let hierarchicalPathsLoaded = false; // Track if loading is complete (regardless of whether paths exist)
  let hierarchicalPathsError: string | null = null;
  let documentsInfo: any = null; // Store document and processing status info
  // Per-document LLM upload status, keyed by original filename, then provider.
  // Example shape:
  // {
  //   "paper.pdf": {
  //     openai:   { status: 'ready' | 'not_uploaded' | 'file_too_large' | 'unsupported_type' | 'missing_api_key', reason?: string },
  //     anthropic:{ ... },
  //     google:   { ... }
  //   }
  // }
  let documentLlmStatus: Record<string, Record<string, { status: string; reason?: string }>> = {};

  // Uploaded-document tree for node-level File Attachments picker.
  // Unlike `hierarchicalPaths`, this does NOT depend on Start Processing / Milvus.
  let uploadedDocumentPaths: any[] = [];
  let uploadedDocumentPathsLoading = false;
  let uploadedDocumentPathsLoaded = false;
  let uploadedDocumentPathsError: string | null = null;
  let uploadedDocumentPollInterval: number | null = null;
  let uploadedDocumentPollInFlight = false;
  let isMounted = false; // Guard against orphaned async continuations after onDestroy
  
  // Conversation history state
  let selectedRunId: string | null = null;
  let conversationHistory: any[] | null = null;
  let loadingConversation = false;
  
  // Agent capabilities (from project)
  let agentCapabilities: any = {};
  
  // ============================================================================
  // CITATION CHIP RENDERING
  // ============================================================================
  let activeCitationRef: number | null = null;
  let citationTooltipEl: HTMLElement | null = null;

  function renderContentWithCitations(content: string, citations?: any[]): string {
    if (!content) return '';
    const escaped = content
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/\n/g, '<br>');
    if (!citations || citations.length === 0) return escaped;
    return escaped.replace(/\[(\d+)\]/g, (match, num) => {
      const ref = parseInt(num, 10);
      const cit = citations.find((c: any) => Number(c.ref) === ref);
      if (!cit) return match;
      const title = (cit.document_title || '').replace(/"/g, '&quot;');
      const quote = (cit.quoted_text || '').slice(0, 200).replace(/"/g, '&quot;');
      let loc = '';
      if (cit.page) loc += `p.${cit.page}`;
      if (cit.section) loc += (loc ? ', ' : '') + cit.section;
      return `<span class="cite-chip" data-ref="${ref}" title="${title}${loc ? ' — ' + loc : ''}">${ref}</span>`;
    });
  }

  function handleCitationClick(event: MouseEvent, citations?: any[]) {
    const target = event.target as HTMLElement;
    if (!target.classList.contains('cite-chip')) {
      if (citationTooltipEl) { citationTooltipEl.remove(); citationTooltipEl = null; activeCitationRef = null; }
      return;
    }
    const ref = parseInt(target.dataset.ref || '0', 10);
    if (!citations || !ref) return;
    if (activeCitationRef === ref && citationTooltipEl) {
      citationTooltipEl.remove(); citationTooltipEl = null; activeCitationRef = null;
      return;
    }
    if (citationTooltipEl) { citationTooltipEl.remove(); citationTooltipEl = null; }
    const cit = citations.find((c: any) => Number(c.ref) === ref);
    if (!cit) return;
    activeCitationRef = ref;
    const tooltip = document.createElement('div');
    tooltip.className = 'cite-tooltip';
    let loc = '';
    if (cit.page) loc += `p.${cit.page}`;
    if (cit.section) loc += (loc ? ', ' : '') + cit.section;
    tooltip.innerHTML = `<div class="cite-tooltip-title">${cit.document_title || 'Document'}${loc ? ' — ' + loc : ''}</div><div class="cite-tooltip-quote">"${(cit.quoted_text || '').slice(0, 300)}"</div>`;
    const rect = target.getBoundingClientRect();
    tooltip.style.position = 'fixed';
    tooltip.style.left = `${rect.left}px`;
    tooltip.style.top = `${rect.bottom + 6}px`;
    tooltip.style.zIndex = '9999';
    document.body.appendChild(tooltip);
    citationTooltipEl = tooltip;
  }

  // ============================================================================
  // PHASE 3: HUMAN INPUT STATE MANAGEMENT
  // ============================================================================
  let showHumanInputModal = false;
  let currentHumanInputData: PendingHumanInput | null = null;
  let pendingInputs: PendingHumanInput[] = [];
  
  // Track recently closed execution IDs to prevent immediate re-opening
  let recentlyClosedExecutionIds = new Set();
  
  // Clear recently closed IDs after 5 seconds
  function clearRecentlyClosedId(executionId) {
    setTimeout(() => {
      recentlyClosedExecutionIds.delete(executionId);
      console.log('🧹 AGENT ORCHESTRATION: Cleared recently closed execution ID:', executionId.slice(-8));
    }, 5000);
  }
  
  // Subscribe to workflow status for human input management
  const unsubscribeWorkflowStatus = workflowStatus.subscribe(status => {
    pendingInputs = status.pendingInputs;
    
    // Auto-show modal for new human input requests
    // CRITICAL FIX: Only show modal if we don't already have one open AND there are pending inputs
    if (pendingInputs.length > 0 && !showHumanInputModal && !currentHumanInputData) {
      // Additional check: make sure this isn't just a stale pending input
      const newPendingInput = pendingInputs[0];
      if (newPendingInput && newPendingInput.execution_id && newPendingInput.agent_name) {
        // ADDITIONAL FIX: Don't show modal for recently closed executions
        if (!recentlyClosedExecutionIds.has(newPendingInput.execution_id)) {
          currentHumanInputData = newPendingInput;
          showHumanInputModal = true;
          console.log('👤 AGENT ORCHESTRATION: Auto-showing human input modal for', currentHumanInputData.agent_name);
        } else {
          console.log('🚀 AGENT ORCHESTRATION: Skipping recently closed execution:', newPendingInput.execution_id.slice(-8));
        }
      }
    } else if (pendingInputs.length === 0 && showHumanInputModal) {
      // CRITICAL FIX: If no pending inputs and modal is open, close it
      console.log('🧹 AGENT ORCHESTRATION: No pending inputs detected, closing modal');
      showHumanInputModal = false;
      currentHumanInputData = null;
    }
  });
  
  console.log(`🤖 AGENT ORCHESTRATION: Initializing for project ${projectId}`);
  
  onMount(() => {
    isMounted = true;
    console.log(`🤖 AGENT ORCHESTRATION: Component mounted`);
    initializeInterfaceWithPreloading();
    
    // ============================================================================
    // PHASE 3: START HUMAN INPUT POLLING
    // ============================================================================
    workflowStatus.startPolling(3000); // Poll every 3 seconds
    console.log('🔄 AGENT ORCHESTRATION: Started human input polling');
  });
  
  onDestroy(() => {
    isMounted = false;
    // Cleanup subscriptions and polling
    unsubscribeWorkflowStatus();
    workflowStatus.stopPolling();
    
    // Cleanup execution monitoring
    if (executionMonitoringInterval) {
      clearInterval(executionMonitoringInterval);
      executionMonitoringInterval = null;
    }

    if (uploadedDocumentPollInterval) {
      clearInterval(uploadedDocumentPollInterval);
      uploadedDocumentPollInterval = null;
    }
    
    if (citationTooltipEl) { citationTooltipEl.remove(); citationTooltipEl = null; }
    console.log('🛑 AGENT ORCHESTRATION: Cleaned up human input polling, execution monitoring, and subscriptions');
  });
  
  async function initializeInterfaceWithPreloading() {
    try {
      loading = true;
      
      console.log('🚀 AGENT ORCHESTRATION: Starting initialization');
      
      // Start all initialization tasks in parallel
      const [workflowsResult, modelsResult, pathsResult, uploadedPathsResult] = await Promise.allSettled([
        loadWorkflowsFromDatabase(),
        preLoadLLMModels(),
        loadHierarchicalPaths(),
        loadUploadedDocumentPaths(true, true)
      ]);
      
      // Handle results
      if (workflowsResult.status === 'rejected') {
        console.error('❌ AGENT ORCHESTRATION: Workflows loading failed:', workflowsResult.reason);
        if (toasts?.error) toasts.error('Failed to load workflows');
      }
      
      if (modelsResult.status === 'rejected') {
        console.error('❌ AGENT ORCHESTRATION: Models loading failed:', modelsResult.reason);
        modelsError = modelsResult.reason?.message || 'Failed to load models';
      }
      
      if (pathsResult.status === 'rejected') {
        console.error('❌ AGENT ORCHESTRATION: Hierarchical paths loading failed:', pathsResult.reason);
        hierarchicalPathsError = pathsResult.reason?.message || 'Failed to load content filter data';
      }

      if (uploadedPathsResult.status === 'rejected') {
        console.error('❌ AGENT ORCHESTRATION: Uploaded document paths loading failed:', uploadedPathsResult.reason);
        uploadedDocumentPathsError = uploadedPathsResult.reason?.message || 'Failed to load uploaded file attachment data';
        uploadedDocumentPaths = [];
        uploadedDocumentPathsLoaded = true;
      }
      
      // Set agent capabilities
      agentCapabilities = project.processing_capabilities || {
        supports_agent_orchestration: true,
        max_agents_per_workflow: 10,
        supported_agent_types: ['UserProxyAgent', 'AssistantAgent', 'GroupChatManager', 'DelegateAgent', 'MCPServer']
      };
      
      if (agentCapabilities.supported_agent_types && !agentCapabilities.supported_agent_types.includes('DelegateAgent')) {
        agentCapabilities.supported_agent_types.push('DelegateAgent');
      }
      
      console.log('✅ AGENT ORCHESTRATION: Initialization complete', {
        workflows: allWorkflows.length,
        models: bulkModelData?.statistics.total_models || 0,
        contentFilterPaths: hierarchicalPaths.length
      });

      // Poll for live updates to uploaded docs in the node attachment picker.
      // Only start if still mounted — prevents orphaned interval if user navigated away
      // during the async initialization above.
      if (isMounted) {
        startUploadedDocumentPolling();
      }
      
    } catch (error) {
      console.error('❌ AGENT ORCHESTRATION: Initialization failed:', error);
      if (toasts?.error) toasts.error('Failed to initialize agent orchestration');
    } finally {
      loading = false;
    }
  }
  
  async function preLoadLLMModels() {
    try {
      modelsLoading = true;
      modelsError = null;
      preloadProgress = { stage: 'Starting model pre-loading...', percentage: 10 };
      
      console.log('📚 AGENT ORCHESTRATION: Pre-loading LLM models for efficient agent configuration');
      console.log(`🔑 AGENT ORCHESTRATION: Using project ${projectId} for API key context`);
      
      // Pre-load all models with project ID to use project-specific API keys
      bulkModelData = await ensureModelsLoaded(false, projectId);
      
      modelsLoaded = true;
      preloadProgress = { stage: 'Models ready', percentage: 100 };
      
      console.log(
        `✅ AGENT ORCHESTRATION: Pre-loaded ${bulkModelData.statistics.total_models} models ` +
        `from ${bulkModelData.statistics.available_providers} providers ` +
        `(source: ${bulkModelData.source})`
      );
      
      // Show success message if models were freshly loaded
      if (bulkModelData.source !== 'cache' && toasts && toasts.success) {
        toasts.success(
          `🤖 Loaded ${bulkModelData.statistics.total_models} LLM models ` +
          `from ${bulkModelData.statistics.available_providers} providers`
        );
      }
      
    } catch (error) {
      console.error('❌ AGENT ORCHESTRATION: LLM models pre-loading failed:', error);
      modelsError = error.message || 'Failed to load LLM models';
      preloadProgress = { stage: 'Error loading models', percentage: 0 };
      
      // Don't fail the entire interface if models fail to load
      console.warn('⚠️ AGENT ORCHESTRATION: Continuing without pre-loaded models');
      
    } finally {
      modelsLoading = false;
    }
  }
  
  async function refreshLLMModels() {
    try {
      console.log('🔄 AGENT ORCHESTRATION: Refreshing LLM models');
      
      modelsLoading = true;
      modelsError = null;
      
      bulkModelData = await ensureModelsLoaded(true); // Force refresh
      
      modelsLoaded = true;
      
      if (toasts && toasts.success) {
        toasts.success(
          `🔄 Refreshed ${bulkModelData.statistics.total_models} LLM models`
        );
      }
      
    } catch (error) {
      console.error('❌ AGENT ORCHESTRATION: Models refresh failed:', error);
      modelsError = error.message || 'Failed to refresh models';
      
      if (toasts && toasts.error) {
        toasts.error('Failed to refresh LLM models');
      }
    } finally {
      modelsLoading = false;
    }
  }
  
  async function loadHierarchicalPaths() {
    try {
      hierarchicalPathsLoading = true;
      hierarchicalPathsLoaded = false; // Reset loaded state
      hierarchicalPathsError = null;

      console.log('📚 AGENT ORCHESTRATION: Loading hierarchical paths for multi-select content filtering');

      const response = await api.get(`/agent-orchestration/docaware/hierarchical_paths/?project_id=${projectId}&include_files=true`);

      // Extract hierarchical paths from response
      const pathsData = response.data || response;
      const rawPaths = pathsData.hierarchical_paths || [];

      // Keep both folders and files (no chunked entries)
      hierarchicalPaths = rawPaths.filter(path => {
        if (!path?.id || !path?.displayName) return false;
        // Keep: folders and complete files, Remove: individual chunks
        return !path.path?.includes('#chunk_');
      });

      console.log(`✅ AGENT ORCHESTRATION: Loaded ${hierarchicalPaths.length} content filter options`,
        `(${pathsData.folders_count || 0} folders, ${pathsData.files_count || 0} files)`);

      // Store document info for better user feedback
      documentsInfo = pathsData.documents_info || null;

      // Store per-document LLM upload status
      documentLlmStatus = pathsData.document_llm_status || {};

      // Mark as loaded regardless of whether paths exist
      hierarchicalPathsLoaded = true;

    } catch (error) {
      console.error('❌ AGENT ORCHESTRATION: Failed to load hierarchical paths:', error);
      hierarchicalPathsError = error.message || 'Failed to load content filter data';
      hierarchicalPaths = [];
      // Still mark as loaded so UI doesn't show loading forever
      hierarchicalPathsLoaded = true;
    } finally {
      hierarchicalPathsLoading = false;
    }
  }

  async function loadUploadedDocumentPaths(include_llm_status: boolean = true, resetLoadedState: boolean = true) {
    try {
      // For polling, avoid flicker: keep `uploadedDocumentPathsLoaded` as-is
      uploadedDocumentPathsLoading = resetLoadedState;
      if (resetLoadedState) uploadedDocumentPathsLoaded = false;
      uploadedDocumentPathsError = null;

      console.log('📎 AGENT ORCHESTRATION: Loading uploaded document paths for node file attachments');

      const response = await api.get(
        `/agent-orchestration/docaware/uploaded_hierarchical_paths/?project_id=${projectId}&include_files=true&include_llm_status=${include_llm_status}`
      );

      const pathsData = response.data || response;
      const rawPaths = pathsData.hierarchical_paths || [];

      // Keep only folders + files (no chunked entries exist here, but keep defensive filter)
      uploadedDocumentPaths = rawPaths.filter((p) => {
        if (!p?.id || !p?.displayName) return false;
        return !p.path?.includes('#chunk_');
      });

      console.log(
        `✅ AGENT ORCHESTRATION: Loaded ${uploadedDocumentPaths.length} uploaded attachment options`,
        `(${pathsData.folders_count || 0} folders, ${pathsData.files_count || 0} files)`
      );

      // Also refresh per-document provider upload status map if backend returns it.
      // For polling, we typically call with `include_llm_status=false` to keep it lightweight.
      if (include_llm_status && pathsData.document_llm_status) {
        documentLlmStatus = pathsData.document_llm_status;
      }

      uploadedDocumentPathsLoaded = true;
    } catch (error) {
      console.error('❌ AGENT ORCHESTRATION: Failed to load uploaded document paths:', error);
      uploadedDocumentPathsError = error.message || 'Failed to load uploaded file attachment data';
      uploadedDocumentPaths = [];
      uploadedDocumentPathsLoaded = true; // allow UI to stop showing spinner
    } finally {
      uploadedDocumentPathsLoading = false;
    }
  }

  function startUploadedDocumentPolling() {
    if (uploadedDocumentPollInterval) {
      clearInterval(uploadedDocumentPollInterval);
      uploadedDocumentPollInterval = null;
    }

    // Polling is only meaningful in designer mode where node configuration is edited.
    if (!projectId) return;

    const intervalMs = 8000; // lightweight refresh interval
    uploadedDocumentPollInterval = window.setInterval(async () => {
      if (uploadedDocumentPollInFlight) return;
      if (activeTab !== 'designer') return;

      uploadedDocumentPollInFlight = true;
      try {
        // Lightweight polling: refresh the folder/file tree only.
        // We keep existing `documentLlmStatus` to avoid repeatedly checking provider support.
        await loadUploadedDocumentPaths(false, false);
      } finally {
        uploadedDocumentPollInFlight = false;
      }
    }, intervalMs);
  }
  
  async function loadWorkflowHistory(workflowId: string) {
    try {
      console.log(`📊 AGENT ORCHESTRATION: Loading history for workflow ${workflowId}`);
      
      const response = await api.get(`/projects/${projectId}/workflows/${workflowId}/history/`);
      
      // Handle response properly
      let historyData;
      if (response.data) {
        historyData = response.data;
      } else {
        historyData = response;
      }
      
      console.log('✅ AGENT ORCHESTRATION: History data loaded:', historyData);
      console.log('   Total executions:', historyData.total_executions);
      console.log('   Recent executions count:', historyData.recent_executions?.length);
      
      // Debug: Check the structure of recent_executions
      if (historyData.recent_executions && historyData.recent_executions.length > 0) {
        console.log('   First execution sample:', historyData.recent_executions[0]);
      }
      
      return historyData;
      
    } catch (error) {
      console.error('❌ AGENT ORCHESTRATION: Failed to load workflow history:', error);
      throw error;
    }
  }
  
  async function loadConversationHistory(executionId: string) {
    if (selectedRunId === executionId && conversationHistory) {
      // Toggle off if already selected
      selectedRunId = null;
      conversationHistory = null;
      return;
    }
    
    try {
      loadingConversation = true;
      selectedRunId = executionId;
      
      console.log(`💬 AGENT ORCHESTRATION: Loading conversation for execution ${executionId}`);
      
      const response = await api.get(`/projects/${projectId}/workflows/${selectedWorkflow.workflow_id}/conversation/?execution_id=${executionId}`);
      
      let conversationData;
      if (response.data) {
        conversationData = response.data;
      } else {
        conversationData = response;
      }
      
      // The conversation history comes from the execution messages
      conversationHistory = conversationData.messages || [];
      
      console.log(`✅ AGENT ORCHESTRATION: Loaded ${conversationHistory.length} conversation messages`);
      console.log('   Sample message:', conversationHistory[0] || 'No messages');
      
    } catch (error) {
      console.error('❌ AGENT ORCHESTRATION: Failed to load conversation:', error);
      if (toasts && toasts.error) {
        toasts.error('Failed to load conversation history');
      }
      selectedRunId = null;
      conversationHistory = null;
    } finally {
      loadingConversation = false;
    }
  }
  
  async function initializeInterface() {
    try {
      loading = true;
      
      // Extract agent capabilities from project data
      agentCapabilities = project.processing_capabilities || {
        supports_agent_orchestration: true,
        max_agents_per_workflow: 10,
        supported_agent_types: ['UserProxyAgent', 'AssistantAgent', 'GroupChatManager', 'DelegateAgent', 'MCPServer']
      };
      
      // Ensure DelegateAgent is always included for enhanced Chat Manager functionality
      if (agentCapabilities.supported_agent_types && !agentCapabilities.supported_agent_types.includes('DelegateAgent')) {
        agentCapabilities.supported_agent_types.push('DelegateAgent');
      }
      
      console.log('🔧 AGENT ORCHESTRATION: Database capabilities loaded:', {
        supports_agent_orchestration: agentCapabilities.supports_agent_orchestration,
        max_agents_per_workflow: agentCapabilities.max_agents_per_workflow,
        supported_agent_types: agentCapabilities.supported_agent_types
      });
      
      // Load existing workflows from database
      await loadWorkflowsFromDatabase();
      
    } catch (error) {
      console.error('❌ AGENT ORCHESTRATION: Initialization failed:', error);
      if (toasts && toasts.error) {
        toasts.error('Failed to initialize agent orchestration');
      }
    } finally {
      loading = false;
    }
  }
  
  async function loadWorkflowsFromDatabase() {
    try {
      console.log('💾 LOADING WORKFLOWS: From database for project', projectId);
      
      const response = await api.get(`/projects/${projectId}/workflows/`);
      
      // Handle response properly - check if response has data property
      let workflowsData;
      if (response.data) {
        workflowsData = response.data;
      } else {
        // If response doesn't have data property, use response directly
        workflowsData = response;
      }
      
      // Extract workflows array from response
      if (Array.isArray(workflowsData)) {
        allWorkflows = workflowsData;
      } else if (workflowsData && workflowsData.data && Array.isArray(workflowsData.data)) {
        allWorkflows = workflowsData.data;
      } else {
        console.warn('⚠️ LOADING WORKFLOWS: Unexpected response format:', workflowsData);
        allWorkflows = [];
      }
      
      // Ensure allWorkflows is always an array
      if (!Array.isArray(allWorkflows)) {
        console.warn('⚠️ LOADING WORKFLOWS: allWorkflows is not an array, resetting to empty array');
        allWorkflows = [];
      }
      
      // Select first workflow if available
      if (allWorkflows.length > 0 && !selectedWorkflow) {
        selectedWorkflow = allWorkflows[0];
      }
      
      console.log(`✅ WORKFLOWS LOADED: ${allWorkflows.length} workflows from database`);
      
    } catch (error) {
      console.error('❌ LOADING WORKFLOWS: Failed to load from database:', error);
      allWorkflows = [];
    }
  }

  // Execution completion monitoring
  let executionMonitoringInterval: number | null = null;
  
  function startExecutionCompletionMonitoring(executionId: string) {
    console.log('🔍 EXECUTION MONITORING: Starting completion monitoring for', executionId.slice(-8));
    
    // Clear any existing monitoring
    if (executionMonitoringInterval) {
      clearInterval(executionMonitoringInterval);
    }
    
    let checkCount = 0;
    const maxChecks = 100; // Stop after 5 minutes (100 * 3 seconds)
    
    executionMonitoringInterval = setInterval(async () => {
      checkCount++;
      
      try {
        // Check execution status by reloading workflow history
        const response = await api.get(`/projects/${projectId}/workflows/${selectedWorkflow.workflow_id}/history/`);
        const historyData = response.data || response;
        
        if (historyData.recent_executions && historyData.recent_executions.length > 0) {
          // Find the execution we're monitoring
          const targetExecution = historyData.recent_executions.find((exec: any) => 
            exec.execution_id === executionId
          );
          
          if (targetExecution) {
            console.log('📊 EXECUTION MONITORING: Status check', checkCount, '-', targetExecution.status);
            
            // Check if execution is completed (success, failed, or stopped)
            if (['completed', 'failed', 'stopped'].includes(targetExecution.status)) {
              console.log('✅ EXECUTION MONITORING: Execution completed with status:', targetExecution.status);
              
              // Stop monitoring
              if (executionMonitoringInterval) {
                clearInterval(executionMonitoringInterval);
                executionMonitoringInterval = null;
              }
              
              // Switch to history tab now that execution is complete
              activeTab = 'history';
              console.log('📊 EXECUTION MONITORING: Switched to history tab after completion');
              
              // Show completion notification
              if (toasts) {
                if (targetExecution.status === 'completed') {
                  toasts.success(`🎉 Workflow execution completed successfully!`);
                } else if (targetExecution.status === 'failed') {
                  toasts.error(`❌ Workflow execution failed`);
                } else if (targetExecution.status === 'stopped') {
                  toasts.warning(`⏹️ Workflow execution was stopped`);
                }
              }
              
              // Reset execution tracking
              isExecuting = false;
              currentExecutionId = null;
              
              return;
            }
          }
        }
        
        // Stop monitoring after max attempts to prevent infinite polling
        if (checkCount >= maxChecks) {
          console.log('⚠️ EXECUTION MONITORING: Stopped after', maxChecks, 'checks - execution may still be running');
          if (executionMonitoringInterval) {
            clearInterval(executionMonitoringInterval);
            executionMonitoringInterval = null;
          }
        }
        
      } catch (error) {
        console.error('❌ EXECUTION MONITORING: Error checking status:', error);
      }
    }, 3000); // Check every 3 seconds
  }
  
  async function createNewWorkflow() {
    if (creatingWorkflow) return;
    
    try {
      creatingWorkflow = true;
      
      console.log('🆕 CREATING WORKFLOW: New database workflow for project', projectId);
      
      const workflowData = {
        name: `Workflow ${allWorkflows.length + 1}`,
        description: '🎯 New agent orchestration workflow',
        graph_json: {
          nodes: [],
          edges: []
        },
        status: 'draft'
      };
      
      const response = await api.post(`/projects/${projectId}/workflows/`, workflowData);
      
      // Handle response properly - check if response has data property
      let newWorkflow;
      if (response.data) {
        newWorkflow = response.data;
      } else {
        // If response doesn't have data property, use response directly
        newWorkflow = response;
      }
      
      console.log('✅ WORKFLOW CREATED: New database workflow created', newWorkflow.workflow_id || newWorkflow.id);
      
      // 🐛 DEBUG: Deep inspection of created workflow
      console.log('🔍 DEBUG WORKFLOW DATA:');
      console.log('  - newWorkflow object:', newWorkflow);
      console.log('  - newWorkflow keys:', Object.keys(newWorkflow || {}));
      console.log('  - newWorkflow.graph_json:', newWorkflow.graph_json);
        console.log('  - typeof newWorkflow:', typeof newWorkflow);
        console.log('  - newWorkflow has workflow_id:', !!newWorkflow.workflow_id);
        
        // Validate newWorkflow before adding to array
        if (newWorkflow && typeof newWorkflow === 'object') {
          // Add to workflows list and select it
          allWorkflows = [...(allWorkflows || []), newWorkflow];
          selectedWorkflow = newWorkflow;
          
          console.log('📋 DEBUG: After setting selectedWorkflow:');
          console.log('  - allWorkflows.length:', allWorkflows.length);
          console.log('  - selectedWorkflow.workflow_id:', selectedWorkflow.workflow_id);
          console.log('  - selectedWorkflow.graph_json:', selectedWorkflow.graph_json);
        
        // CRITICAL FIX: Ensure we're on the designer tab to show the blank canvas
        activeTab = 'designer';
        
        console.log('🎨 WORKFLOW CREATED: Switched to designer tab');
        console.log('🎨 selectedWorkflow:', selectedWorkflow);
        console.log('🎨 selectedWorkflow.graph_json:', selectedWorkflow.graph_json);
        console.log('🎨 activeTab:', activeTab);
        
        if (toasts && toasts.success) {
          toasts.success('🎯 New database workflow created!');
        }
      } else {
        console.error('❌ CREATING WORKFLOW: Invalid workflow data received:', newWorkflow);
        throw new Error('Invalid workflow data received from server');
      }
      
    } catch (error) {
      console.error('❌ CREATING WORKFLOW: Failed to create database workflow:', error);
      if (toasts && toasts.error) {
        toasts.error(`Failed to create workflow: ${error.message || 'Unknown error'}`);
      }
    } finally {
      creatingWorkflow = false;
    }
  }
  
  async function executeWorkflow(workflow: any) {
    if (isExecuting) return;
    
    try {
      isExecuting = true;
      
      // Validate workflow before execution
      if (workflow.graph_json) {
        const validation = validateWorkflowGraph(workflow.graph_json);
        if (!validation.valid) {
          toasts.error(`Cannot execute workflow: ${validation.errors.join(', ')}`);
          isExecuting = false;
          return;
        }
      }
      
      console.log(`🚀 EXECUTING WORKFLOW: Starting real execution for ${workflow.workflow_id}`);
      
      // REAL IMPLEMENTATION: Call the actual backend execute endpoint
      const response = await api.post(`/projects/${projectId}/workflows/${workflow.workflow_id}/execute/`);
      
      // Handle response data structure (may be response.data or response directly)
      const responseData = response.data || response;
      console.log('✅ WORKFLOW EXECUTION: Response received:', responseData);
      
      // Capture execution ID for stop functionality and monitoring
      // Check both top-level and nested in result object
      const executionId = responseData.execution_id || responseData.result?.execution_id;
      if (executionId) {
        currentExecutionId = executionId;
        console.log(`📝 EXECUTION: Tracking execution ID: ${currentExecutionId}`);
      } else {
        console.warn('⚠️ EXECUTION: No execution_id found in response - completion monitoring will not work');
      }
      
      if (toasts && toasts.success) {
        toasts.success(`🚀 Workflow "${workflow.name}" execution started successfully!`);
      }
      
      // CRITICAL FIX: Don't switch to history tab immediately
      // Only switch when workflow execution is complete, not when it starts
      console.log('📊 WORKFLOW EXECUTION: Started - staying on designer tab until completion');
      
      // Start monitoring for execution completion
      if (currentExecutionId) {
        startExecutionCompletionMonitoring(currentExecutionId);
      }
      
      // Reload workflows to get updated execution status
      await loadWorkflowsFromDatabase();
      
      // CRITICAL FIX: Restart polling after workflow execution to catch any new human input requests
      console.log('🔄 EXECUTING WORKFLOW: Restarting human input polling after workflow execution');
      workflowStatus.restartPolling(3000);
      
    } catch (error) {
      console.error('❌ EXECUTING WORKFLOW: Execution failed:', error);
      
      let errorMessage = 'Unknown error occurred';
      if (error.response && error.response.data) {
        if (typeof error.response.data === 'string') {
          errorMessage = error.response.data;
        } else if (error.response.data.error) {
          errorMessage = error.response.data.error;
        } else if (error.response.data.message) {
          errorMessage = error.response.data.message;
        }
      } else if (error.message) {
        errorMessage = error.message;
      }
      
      if (toasts && toasts.error) {
        toasts.error(`❌ Workflow execution failed: ${errorMessage}`);
      }
    } finally {
      isExecuting = false;
      currentExecutionId = null;
    }
  }

  async function stopWorkflowExecution() {
    if (!currentExecutionId) {
      console.warn('⚠️ STOP: No current execution ID to stop');
      return;
    }

    try {
      console.log(`🛑 STOP: Stopping workflow execution ${currentExecutionId}`);
      
      // Call backend to stop the execution
      const response = await api.post(`/projects/${projectId}/workflows/stop/`, {
        execution_id: currentExecutionId
      });
      
      console.log('✅ STOP: Workflow execution stopped successfully', response.data);
      
      if (toasts && toasts.success) {
        toasts.success('🛑 Workflow execution stopped successfully');
      }
      
      // Reset execution state
      isExecuting = false;
      currentExecutionId = null;
      
      // Close any human input modals
      showHumanInputModal = false;
      currentHumanInputData = null;
      
      // Reload workflows to get updated status
      await loadWorkflowsFromDatabase();
      
    } catch (error) {
      console.error('❌ STOP: Failed to stop workflow execution:', error);
      
      let errorMessage = 'Failed to stop workflow execution';
      if (error.response?.data?.error) {
        errorMessage = error.response.data.error;
      } else if (error.message) {
        errorMessage = error.message;
      }
      
      if (toasts && toasts.error) {
        toasts.error(`❌ ${errorMessage}`);
      }
      
      // Reset state even if stop request failed
      isExecuting = false;
      currentExecutionId = null;
    }
  }
  
  // ============================================================================
  // PHASE 3: HUMAN INPUT HANDLERS
  // ============================================================================
  
  function handleHumanInputSubmitted(event: CustomEvent) {
    const { executionId, humanInput, agentName } = event.detail;
    console.log('✅ AGENT ORCHESTRATION: Human input submitted', {
      executionId: executionId.slice(-8),
      inputLength: humanInput.length,
      agentName
    });
    
    // CRITICAL FIX: Track this execution as recently closed
    recentlyClosedExecutionIds.add(executionId);
    clearRecentlyClosedId(executionId);
    console.log('📋 AGENT ORCHESTRATION: Marked execution as recently closed:', executionId.slice(-8));
    
    // CRITICAL FIX: Close modal immediately to prevent null reference errors
    showHumanInputModal = false;
    currentHumanInputData = null;
    
    // Refresh workflow history to show updated execution status
    loadWorkflowsFromDatabase();
    
    // Show success feedback
    if (toasts && toasts.success) {
      toasts.success(`🎯 Workflow resumed! ${agentName} received your input.`);
    }
  }
  
  function handleHumanInputClosed() {
    console.log('❌ AGENT ORCHESTRATION: Human input modal closed');
    showHumanInputModal = false;
    currentHumanInputData = null;
  }
  
  function openPendingInputModal(pendingInput?: PendingHumanInput) {
    const inputToShow = pendingInput || pendingInputs[0];
    
    if (inputToShow) {
      currentHumanInputData = inputToShow;
      showHumanInputModal = true;
      console.log('👤 AGENT ORCHESTRATION: Manually opened input modal for', inputToShow.agent_name);
    } else {
      console.warn('⚠️ AGENT ORCHESTRATION: No pending input to show');
      if (toasts && toasts.warning) {
        toasts.warning('No pending human inputs available');
      }
    }
  }
  
  function handleWorkflowUpdate(updatedWorkflow: any) {
    // Update workflow in the list
    const index = allWorkflows.findIndex(w => w.workflow_id === updatedWorkflow.workflow_id);
    if (index >= 0) {
      allWorkflows[index] = updatedWorkflow;
      allWorkflows = [...allWorkflows];
    }
    
    // Update selected workflow
    if (selectedWorkflow?.workflow_id === updatedWorkflow.workflow_id) {
      selectedWorkflow = updatedWorkflow;
    }
  }
  
  function handleTabSwitch(tab: 'designer' | 'history') {
    activeTab = tab;
    console.log(`🔄 AGENT ORCHESTRATION: Switched to ${tab} tab`);
  }
</script>

<svelte:head>
  <title>Agent Orchestration - {project?.name || 'Project'}</title>
</svelte:head>

<div class="agent-orchestration-interface h-full flex flex-col bg-gray-50 w-full">
  <!-- Header -->
  <div class="bg-white border-b border-gray-200 px-6 py-4">
    <div class="flex items-center justify-between">
      <div class="flex items-center space-x-4">
        <div class="w-10 h-10 bg-oxford-blue text-white rounded-lg flex items-center justify-center shadow-lg">
          <i class="fas fa-sitemap text-lg"></i>
        </div>
        <div>
          <h1 class="text-2xl font-bold text-gray-900">Agent Orchestration</h1>
          <p class="text-sm text-gray-600">
            Design and manage multi-agent workflows with visual interface
          </p>
        </div>
      </div>
      
      <div class="flex items-center space-x-3">
        <!-- Human Input Status Indicator (Phase 3) -->
        {#if $pendingInputsCount > 0}
          <div class="flex items-center px-3 py-2 bg-orange-50 border border-orange-200 rounded-lg text-sm cursor-pointer hover:bg-orange-100 transition-colors"
               on:click={() => openPendingInputModal()}
               title="Click to open human input modal">
            <div class="w-2 h-2 bg-orange-500 rounded-full animate-pulse mr-2"></div>
            <span class="text-orange-700 font-medium">
              {$pendingInputsCount} workflow{$pendingInputsCount > 1 ? 's' : ''} awaiting input
            </span>
            <button 
              class="ml-2 text-orange-600 hover:text-orange-800 transition-colors p-1 rounded hover:bg-orange-200"
              on:click|stopPropagation={() => openPendingInputModal()}
              title="Show pending input"
            >
              <i class="fas fa-eye text-xs"></i>
            </button>
          </div>
        {:else if $isWorkflowStatusActive}
          <div class="flex items-center px-3 py-2 bg-green-50 border border-green-200 rounded-lg text-sm">
            <div class="w-2 h-2 bg-green-500 rounded-full mr-2"></div>
            <span class="text-green-700 font-medium">Monitoring workflows</span>
          </div>
        {/if}
        
        <!-- LLM Models Status Indicator -->
        <div class="flex items-center space-x-2">
          {#if modelsLoading}
            <div class="flex items-center px-3 py-2 bg-blue-50 border border-blue-200 rounded-lg text-sm">
              <div class="animate-spin rounded-full h-4 w-4 border-b-2 border-blue-600 mr-2"></div>
              <span class="text-blue-700 font-medium">{preloadProgress.stage}</span>
              <span class="text-blue-600 ml-2 text-xs">{preloadProgress.percentage}%</span>
            </div>
          {:else if modelsLoaded && bulkModelData}
            <div class="flex items-center px-3 py-2 bg-green-50 border border-green-200 rounded-lg text-sm">
              <i class="fas fa-check-circle text-green-600 mr-2"></i>
              <span class="text-green-700 font-medium">
                {bulkModelData.statistics.total_models} models from {bulkModelData.statistics.available_providers} providers
              </span>
              <button 
                class="ml-2 text-green-600 hover:text-green-800 transition-colors"
                on:click={refreshLLMModels}
                title="Refresh models"
              >
                <i class="fas fa-sync-alt text-xs"></i>
              </button>
            </div>
          {:else if modelsError}
            <div class="flex items-center px-3 py-2 bg-red-50 border border-red-200 rounded-lg text-sm">
              <i class="fas fa-exclamation-triangle text-red-600 mr-2"></i>
              <span class="text-red-700 font-medium">Models failed to load</span>
              <button 
                class="ml-2 text-red-600 hover:text-red-800 transition-colors"
                on:click={refreshLLMModels}
                title="Retry loading models"
              >
                <i class="fas fa-retry text-xs"></i>
              </button>
            </div>
          {:else}
            <div class="flex items-center px-3 py-2 bg-gray-50 border border-gray-200 rounded-lg text-sm">
              <i class="fas fa-robot text-gray-600 mr-2"></i>
              <span class="text-gray-700 font-medium">Models not loaded</span>
            </div>
          {/if}
        </div>
        
        <!-- Designer Mode Button -->
        {#if selectedWorkflow}
          <button
            class="px-4 py-2 bg-oxford-blue text-white rounded-lg hover:bg-blue-900 transition-all text-sm font-medium shadow-lg hover:shadow-xl disabled:opacity-50 disabled:cursor-not-allowed"
            on:click={() => designerMode = true}
            title="Enter Designer Mode - full-screen workflow editor"
          >
            <i class="fas fa-expand-arrows-alt mr-2"></i>
            Designer Mode
          </button>
        {/if}
        
        <!-- Workflow Selector -->
        {#if allWorkflows.length > 0}
          <select 
            bind:value={selectedWorkflow}
            class="px-3 py-2 border border-gray-300 rounded-lg text-sm font-medium bg-white text-gray-700 hover:border-oxford-blue focus:border-oxford-blue focus:ring-2 focus:ring-oxford-blue focus:ring-opacity-20 transition-all"
          >
            {#each allWorkflows as workflow}
              <option value={workflow}>
                {workflow.name}
              </option>
            {/each}
          </select>
        {/if}
        
        <!-- Create New Workflow Button -->
        <button
          class="px-4 py-2 bg-white border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 hover:border-oxford-blue transition-all text-sm font-medium"
          on:click={createNewWorkflow}
          disabled={creatingWorkflow}
        >
          {#if creatingWorkflow}
            <i class="fas fa-spinner fa-spin mr-2"></i>
            Creating...
          {:else}
            <i class="fas fa-plus mr-2"></i>
            New Workflow
          {/if}
        </button>
        
        <!-- Execute Button -->
        {#if selectedWorkflow}
          <button
            class="px-4 py-2 bg-oxford-blue text-white rounded-lg hover:bg-blue-700 transition-all text-sm font-medium shadow-lg hover:shadow-xl disabled:opacity-50 disabled:cursor-not-allowed"
            on:click={() => executeWorkflow(selectedWorkflow)}
            disabled={isExecuting || !selectedWorkflow?.graph_json?.nodes?.length}
          >
            {#if isExecuting}
              <i class="fas fa-spinner fa-spin mr-2"></i>
              Executing...
            {:else}
              <i class="fas fa-play mr-2"></i>
              Execute
            {/if}
          </button>
          
          <!-- Stop Button -->
          {#if isExecuting}
            <button
              class="px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 transition-all text-sm font-medium shadow-lg hover:shadow-xl"
              on:click={() => stopWorkflowExecution()}
            >
              <i class="fas fa-stop mr-2"></i>
              Stop
            </button>
          {/if}
        {/if}
      </div>
    </div>
    
    <!-- Tab Navigation -->
    <div class="mt-4 border-b border-gray-200">
      <nav class="flex space-x-8">
        <button
          class="pb-2 px-1 border-b-2 font-medium text-sm transition-all {activeTab === 'designer' 
            ? 'border-oxford-blue text-oxford-blue' 
            : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'}"
          on:click={() => handleTabSwitch('designer')}
        >
          <i class="fas fa-project-diagram mr-2"></i>
          Workflow Designer
        </button>
        <button
          class="pb-2 px-1 border-b-2 font-medium text-sm transition-all {activeTab === 'history' 
            ? 'border-oxford-blue text-oxford-blue' 
            : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'}"
          on:click={() => handleTabSwitch('history')}
        >
          <i class="fas fa-history mr-2"></i>
          Execution History
        </button>
      </nav>
    </div>
  </div>
  
  <!-- Main Content Area -->
  <div class="flex-1 flex min-h-0">
    {#if loading}
      <!-- Loading State -->
      <div class="flex-1 flex items-center justify-center">
        <div class="text-center">
          <div class="animate-spin rounded-full h-12 w-12 border-b-2 border-oxford-blue mx-auto mb-4"></div>
          <p class="text-gray-600">Loading agent orchestration interface...</p>
        </div>
      </div>
    {:else if activeTab === 'designer'}
      <!-- 🌟 Infinite Canvas Workflow Designer -->
      <div class="flex-1 flex">
        <!-- 🐛 DEBUG: Add debugging info -->
        <div class="hidden">
          Debug: selectedWorkflow={selectedWorkflow ? 'EXISTS' : 'NULL'}
          Debug: activeTab={activeTab}
          Debug: selectedWorkflow.workflow_id={selectedWorkflow?.workflow_id || 'N/A'}
          Debug: creatingWorkflow={creatingWorkflow}
        </div>
        
        {#if selectedWorkflow}
          <!-- Show loading state while creating new workflow -->
          {#if creatingWorkflow}
            <div class="flex-1 flex items-center justify-center">
              <div class="text-center">
                <div class="animate-spin rounded-full h-12 w-12 border-b-2 border-oxford-blue mx-auto mb-4"></div>
                <p class="text-gray-600">Creating new workflow...</p>
                <p class="text-sm text-gray-500 mt-2">Setting up blank canvas</p>
              </div>
            </div>
          {:else}
            {#await import('./WorkflowDesigner.svelte')}
            <div class="flex-1 flex items-center justify-center">
              <div class="text-center">
                <div class="animate-spin rounded-full h-8 w-8 border-b-2 border-oxford-blue mx-auto mb-4"></div>
                <p class="text-gray-600">Loading visual workflow designer...</p>
              </div>
            </div>
          {:then WorkflowDesignerModule}
            <svelte:component 
              this={WorkflowDesignerModule.default}
              {project}
              {projectId}
              workflow={selectedWorkflow}
              capabilities={agentCapabilities}
              bulkModelData={bulkModelData}
              modelsLoaded={modelsLoaded}
              hierarchicalPaths={hierarchicalPaths}
              hierarchicalPathsLoaded={hierarchicalPathsLoaded}
              uploadedDocumentPaths={uploadedDocumentPaths}
              uploadedDocumentPathsLoaded={uploadedDocumentPathsLoaded}
              documentsInfo={documentsInfo}
              documentLlmStatus={documentLlmStatus}
              {designerMode}
              on:workflowUpdate={(e) => handleWorkflowUpdate(e.detail)}
              on:exitDesignerMode={() => designerMode = false}
            />
          {:catch error}
            <div class="flex-1 flex items-center justify-center">
              <div class="text-center">
                <div class="w-16 h-16 bg-red-100 text-red-600 rounded-xl flex items-center justify-center mx-auto mb-4">
                  <i class="fas fa-exclamation-triangle text-2xl"></i>
                </div>
                <p class="text-red-600">Failed to load visual workflow designer</p>
                <p class="text-sm text-gray-500 mt-2">Database connection may be required</p>
              </div>
            </div>
            {/await}
          {/if}
        {:else}
          <!-- No Workflow Selected -->
          <div class="flex-1 flex items-center justify-center">
            <div class="text-center max-w-md mx-auto">
              <div class="w-20 h-20 bg-gray-100 text-gray-400 rounded-xl flex items-center justify-center mx-auto mb-6">
                <i class="fas fa-sitemap text-3xl"></i>
              </div>
              <h3 class="text-xl font-semibold text-gray-900 mb-2">No Workflows Found</h3>
              <p class="text-gray-600 mb-6">Create your first agent orchestration workflow to get started with multi-agent automation.</p>
              
              <button
                class="px-6 py-3 bg-oxford-blue text-white rounded-lg hover:bg-blue-700 transition-all font-medium shadow-lg hover:shadow-xl"
                on:click={createNewWorkflow}
                disabled={creatingWorkflow}
              >
                {#if creatingWorkflow}
                  <i class="fas fa-spinner fa-spin mr-2"></i>
                  Creating Workflow...
                {:else}
                  <i class="fas fa-plus mr-2"></i>
                  Create Workflow
                {/if}
              </button>
              
              <div class="mt-6 p-4 bg-green-50 rounded-lg border border-green-200">
                <div class="flex items-start text-left">
                  <i class="fas fa-database text-green-500 mt-1 mr-3 flex-shrink-0"></i>
                  <div class="text-sm text-green-700">
                    <p class="font-medium mb-1">💾 Database Workflow Features:</p>
                    <ul class="list-disc list-inside space-y-1 text-xs">
                      <li><strong>Persistent Storage:</strong> Workflows saved to database</li>
                      <li><strong>Cross-Session Access:</strong> Resume work from any device</li>
                      <li><strong>Team Collaboration:</strong> Share workflows with team members</li>
                      <li><strong>Version History:</strong> Track changes over time</li>
                      <li><strong>Production Ready:</strong> Deploy and execute workflows</li>
                      <li><strong>Real-time Sync:</strong> Changes saved automatically</li>
                      <li>🎯 Perfect state restoration across sessions</li>
                      <li>🚀 20K×20K infinite canvas with zoom & pan</li>
                    </ul>
                  </div>
                </div>
              </div>
            </div>
          </div>
        {/if}
      </div>
    {:else if activeTab === 'history'}
      <!-- Execution History -->
      <div class="flex-1 p-6">
        <div class="bg-white rounded-lg border border-gray-200 h-full">
          <div class="p-6">
            <div class="flex items-center justify-between mb-6">
              <h2 class="text-xl font-bold text-gray-900">Execution History</h2>
              <span class="px-3 py-1 text-sm font-medium bg-green-100 text-green-800 rounded-full">
                Database Storage
              </span>
            </div>
            
            {#if selectedWorkflow}
              {#await loadWorkflowHistory(selectedWorkflow.workflow_id)}
                <div class="text-center py-12">
                  <div class="animate-spin rounded-full h-8 w-8 border-b-2 border-oxford-blue mx-auto mb-4"></div>
                  <p class="text-gray-600">Loading execution history...</p>
                </div>
              {:then historyData}
                {#if historyData && historyData.recent_executions && historyData.recent_executions.length > 0}
                  <div class="space-y-4">
                    <div class="grid grid-cols-3 gap-4 mb-6">
                      <div class="bg-blue-50 p-4 rounded-lg">
                        <div class="text-2xl font-bold text-blue-600">{historyData.total_executions || 0}</div>
                        <div class="text-sm text-blue-600">Total Executions</div>
                      </div>
                      <div class="bg-green-50 p-4 rounded-lg">
                        <div class="text-2xl font-bold text-green-600">
                          {historyData.successful_executions || 0}
                        </div>
                        <div class="text-sm text-green-600">Successful</div>
                      </div>
                      <div class="bg-purple-50 p-4 rounded-lg">
                        <div class="text-2xl font-bold text-purple-600">
                          {historyData.success_rate ? Math.round(historyData.success_rate) : 0}%
                        </div>
                        <div class="text-sm text-purple-600">Success Rate</div>
                      </div>
                    </div>
                    
                    <h3 class="text-lg font-semibold text-gray-900 mb-4">Recent Executions</h3>
                    <div class="space-y-3">
                      {#each historyData.recent_executions as execution}
                        <div class="border border-gray-200 rounded-lg p-4 hover:bg-gray-50 transition-colors cursor-pointer"
                             on:click={() => loadConversationHistory(execution.execution_id)}>
                          <div class="flex items-center justify-between">
                            <div class="flex items-center space-x-3">
                              <div class="w-3 h-3 rounded-full {execution.status === 'completed' ? 'bg-green-500' : execution.status === 'running' ? 'bg-blue-500' : execution.status === 'failed' ? 'bg-red-500' : 'bg-gray-500'}"></div>
                              <div>
                                <div class="font-medium text-gray-900">Execution {execution.execution_id.slice(-8)}</div>
                                <div class="text-sm text-gray-500">
                                  {execution.start_time ? new Date(execution.start_time).toLocaleString() : 'Unknown time'}
                                </div>
                                {#if execution.total_messages > 0}
                                  <div class="text-xs text-blue-600 mt-1">
                                    {execution.total_messages} messages • {execution.total_agents_involved} agents
                                  </div>
                                {/if}
                              </div>
                            </div>
                            <div class="text-right">
                              <div class="text-sm font-medium text-gray-900 capitalize">{execution.status}</div>
                              <div class="text-sm text-gray-500">{execution.duration_seconds ? `${execution.duration_seconds.toFixed(1)}s` : 'N/A'}</div>
                              {#if execution.error_message}
                                <div class="text-xs text-red-600 mt-1">Error</div>
                              {/if}
                            </div>
                          </div>
                          
                          {#if selectedRunId === execution.execution_id}
                            <div class="mt-4 pt-4 border-t border-gray-200">
                              {#if loadingConversation}
                                <div class="text-center py-4">
                                  <div class="animate-spin rounded-full h-6 w-6 border-b-2 border-oxford-blue mx-auto mb-2"></div>
                                  <p class="text-sm text-gray-600">Loading conversation...</p>
                                </div>
                              {:else if conversationHistory && conversationHistory.length > 0}
                                <h4 class="font-medium text-gray-900 mb-3">Conversation History</h4>
                                <div class="space-y-3">
                                  {#each conversationHistory as message}
                                    <div class="flex items-start space-x-3 p-3 rounded-lg {message.agent_type === 'StartNode' ? 'bg-blue-50' : message.agent_type === 'EndNode' ? 'bg-green-50' : 'bg-gray-50'}">
                                      <div class="flex-shrink-0">
                                        <div class="w-8 h-8 rounded-full flex items-center justify-center text-white text-sm font-medium
                                             {message.agent_type === 'StartNode' ? 'bg-blue-500' : 
                                              message.agent_type === 'EndNode' ? 'bg-green-500' : 
                                              message.agent_type === 'AssistantAgent' ? 'bg-purple-500' : 'bg-gray-500'}">
                                          {message.agent_name.charAt(0)}
                                        </div>
                                      </div>
                                      <div class="flex-1 min-w-0">
                                        <div class="flex items-center justify-between">
                                          <div class="font-medium text-gray-900">{message.agent_name}</div>
                                          <div class="text-xs text-gray-500">
                                            {new Date(message.timestamp).toLocaleTimeString()}
                                            {#if message.response_time_ms}
                                              • {message.response_time_ms}ms
                                            {/if}
                                          </div>
                                        </div>
                                        {#if message.message_type === 'tool_plan'}
                                          <div class="mt-1 text-sm">
                                            <div class="font-medium text-slate-600 mb-1 flex items-center">
                                              <i class="fas fa-clipboard-list mr-1.5 text-xs"></i>
                                              Agent Plan
                                            </div>
                                            <div class="text-gray-700 whitespace-pre-wrap bg-slate-50 p-2.5 rounded-md border-l-4 border-slate-400 text-sm">{message.content}</div>
                                          </div>
                                        {:else if message.message_type === 'tool_notebook'}
                                          {@const entry = (() => { try { return JSON.parse(message.content); } catch { return null; } })()}
                                          <div class="mt-1 text-sm">
                                            <div class="font-medium text-teal-600 mb-1 flex items-center">
                                              <i class="fas fa-book mr-1.5 text-xs"></i>
                                              Notebook
                                              {#if entry?.step}
                                                <span class="ml-1.5 text-xs bg-teal-100 text-teal-600 px-1.5 py-0.5 rounded">Step {entry.step}</span>
                                              {/if}
                                              {#if entry?.status === 'completed'}
                                                <i class="fas fa-check-circle ml-1.5 text-green-500 text-xs"></i>
                                              {/if}
                                            </div>
                                            {#if entry}
                                              <div class="bg-teal-50 p-2.5 rounded-md border-l-4 border-teal-300 space-y-1.5">
                                                <div class="text-xs text-teal-600 font-medium">{entry.tool_name}</div>
                                                <div class="text-xs text-gray-500"><span class="font-medium">Query:</span> {entry.query}</div>
                                                <div class="text-gray-700 whitespace-pre-wrap text-sm">{entry.result}</div>
                                                {#if entry.source_passages?.length}
                                                  <div class="mt-1.5 pt-1.5 border-t border-teal-200">
                                                    <div class="text-xs font-medium text-teal-700 mb-1 flex items-center">
                                                      <i class="fas fa-quote-left mr-1 text-teal-400" style="font-size: 0.6rem;"></i>
                                                      Citations ({entry.source_passages.length})
                                                    </div>
                                                    {#each entry.source_passages.slice(0, 3) as passage}
                                                      <div class="text-xs bg-white/60 rounded px-2 py-1 mb-1 border-l-2 border-teal-400">
                                                        <span class="text-gray-600 italic">"{passage.quoted_text?.slice(0, 150)}{passage.quoted_text?.length > 150 ? '...' : ''}"</span>
                                                        {#if passage.page || passage.section}
                                                          <span class="text-teal-500 ml-1 not-italic">
                                                            {#if passage.page}p.{passage.page}{/if}{#if passage.page && passage.section}, {/if}{#if passage.section}{passage.section}{/if}
                                                          </span>
                                                        {/if}
                                                      </div>
                                                    {/each}
                                                  </div>
                                                {/if}
                                              </div>
                                            {:else}
                                              <div class="text-gray-700 whitespace-pre-wrap bg-teal-50 p-2.5 rounded-md border-l-4 border-teal-300">{message.content}</div>
                                            {/if}
                                          </div>
                                        {:else}
                                          {#if message.metadata?.citations?.length}
                                            <!-- svelte-ignore a11y-click-events-have-key-events -->
                                            <!-- svelte-ignore a11y-no-static-element-interactions -->
                                            <div class="mt-1 text-sm text-gray-700 citation-content" on:click={(e) => handleCitationClick(e, message.metadata.citations)}>
                                              {@html renderContentWithCitations(message.content, message.metadata.citations)}
                                            </div>
                                          {:else}
                                            <div class="mt-1 text-sm text-gray-700 whitespace-pre-wrap">{message.content}</div>
                                          {/if}
                                        {/if}
                                        {#if message.metadata && message.metadata.llm_provider}
                                          <div class="mt-2 flex items-center space-x-2 text-xs text-gray-500">
                                            <span class="px-2 py-1 bg-gray-200 rounded">{message.metadata.llm_provider}</span>
                                            <span class="px-2 py-1 bg-gray-200 rounded">{message.metadata.llm_model}</span>
                                            {#if message.token_count}
                                              <span class="px-2 py-1 bg-gray-200 rounded">{message.token_count} tokens</span>
                                            {/if}
                                          </div>
                                        {/if}
                                      </div>
                                    </div>
                                  {/each}
                                </div>
                              {:else}
                                <div class="text-center py-4">
                                  <p class="text-sm text-gray-600">No conversation history available</p>
                                </div>
                              {/if}
                            </div>
                          {/if}
                        </div>
                      {/each}
                    </div>
                  </div>
                {:else}
                  <div class="text-center py-12">
                    <div class="w-16 h-16 bg-gray-100 text-gray-400 rounded-xl flex items-center justify-center mx-auto mb-4">
                      <i class="fas fa-history text-2xl"></i>
                    </div>
                    <h3 class="text-lg font-semibold text-gray-900 mb-2">No Execution History</h3>
                    <p class="text-gray-600">Execute this workflow to see its history here</p>
                  </div>
                {/if}
              {:catch error}
                <div class="text-center py-12">
                  <div class="w-16 h-16 bg-red-100 text-red-600 rounded-xl flex items-center justify-center mx-auto mb-4">
                    <i class="fas fa-exclamation-triangle text-2xl"></i>
                  </div>
                  <h3 class="text-lg font-semibold text-gray-900 mb-2">Failed to Load History</h3>
                  <p class="text-gray-600">Error: {error.message}</p>
                </div>
              {/await}
            {:else}
              <div class="text-center py-12">
                <div class="w-16 h-16 bg-gray-100 text-gray-400 rounded-xl flex items-center justify-center mx-auto mb-4">
                  <i class="fas fa-info-circle text-2xl"></i>
                </div>
                <h3 class="text-lg font-semibold text-gray-900 mb-2">No Workflow Selected</h3>
                <p class="text-gray-600">Select a workflow to view its execution history</p>
              </div>
            {/if}
          </div>
        </div>
      </div>
    {/if}
  </div>
</div>

<!-- Human Input Modal (Phase 3) -->
{#if showHumanInputModal && currentHumanInputData}
  {#await import('./HumanInputModal.svelte')}
    <!-- Loading modal placeholder -->
    <div class="fixed inset-0 bg-black bg-opacity-60 flex items-center justify-center z-50">
      <div class="bg-white rounded-xl p-6 max-w-md">
        <div class="flex items-center justify-center">
          <div class="animate-spin rounded-full h-8 w-8 border-b-2 border-oxford-blue mr-4"></div>
          <span class="text-gray-700">Loading human input interface...</span>
        </div>
      </div>
    </div>
  {:then HumanInputModalModule}
    <!-- CRITICAL FIX: Add null checks to prevent reactive errors -->
    {#if currentHumanInputData && currentHumanInputData.execution_id && currentHumanInputData.agent_name}
      <svelte:component
        this={HumanInputModalModule.default}
        executionId={currentHumanInputData.execution_id}
        agentName={currentHumanInputData.agent_name}
        inputContext={currentHumanInputData.context || {}}
        conversationHistory={currentHumanInputData.conversation_history || ''}
        isVisible={showHumanInputModal}
        on:inputSubmitted={handleHumanInputSubmitted}
        on:close={handleHumanInputClosed}
      />
    {/if}
  {:catch error}
    <!-- Error loading modal -->
    <div class="fixed inset-0 bg-black bg-opacity-60 flex items-center justify-center z-50">
      <div class="bg-white rounded-xl p-6 max-w-md">
        <div class="text-center">
          <div class="w-12 h-12 bg-red-100 text-red-600 rounded-xl flex items-center justify-center mx-auto mb-4">
            <i class="fas fa-exclamation-triangle text-xl"></i>
          </div>
          <h3 class="text-lg font-semibold text-gray-900 mb-2">Failed to Load Modal</h3>
          <p class="text-sm text-gray-600 mb-4">Error: {error.message}</p>
          <button
            class="px-4 py-2 bg-oxford-blue text-white rounded-lg hover:bg-blue-700 transition-colors"
            on:click={handleHumanInputClosed}
          >
            Close
          </button>
        </div>
      </div>
    </div>
  {/await}
{/if}

<style>
  .agent-orchestration-interface {
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
  
  :global(.hover\:border-oxford-blue:hover) {
    border-color: #002147;
  }
  
  :global(.focus\:border-oxford-blue:focus) {
    border-color: #002147;
  }
  
  :global(.focus\:ring-oxford-blue:focus) {
    --tw-ring-color: #002147;
  }

  :global(.cite-chip) {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    min-width: 18px;
    height: 18px;
    padding: 0 4px;
    border-radius: 4px;
    background: #0ea5e9;
    color: white;
    font-size: 11px;
    font-weight: 600;
    cursor: pointer;
    vertical-align: super;
    margin: 0 1px;
    line-height: 1;
    transition: background 0.15s;
  }
  :global(.cite-chip:hover) {
    background: #0284c7;
  }

  .citation-content {
    line-height: 1.7;
  }

  :global(.cite-tooltip) {
    max-width: 380px;
    background: #1e293b;
    color: #e2e8f0;
    border-radius: 8px;
    padding: 10px 14px;
    font-size: 13px;
    box-shadow: 0 8px 24px rgba(0,0,0,0.25);
    animation: citeTooltipIn 0.15s ease-out;
  }
  :global(.cite-tooltip-title) {
    font-weight: 600;
    color: #38bdf8;
    margin-bottom: 6px;
    font-size: 12px;
  }
  :global(.cite-tooltip-quote) {
    font-style: italic;
    color: #cbd5e1;
    font-size: 12px;
    line-height: 1.5;
  }

  @keyframes citeTooltipIn {
    from { opacity: 0; transform: translateY(-4px); }
    to { opacity: 1; transform: translateY(0); }
  }
</style>