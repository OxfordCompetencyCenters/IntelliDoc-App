<!-- NodePropertiesPanel.svelte - Enhanced Agent Node Configuration Panel with API Key Based Models -->
<script lang="ts">
  import { createEventDispatcher, onMount, onDestroy } from 'svelte';
  import { toasts } from '$lib/stores/toast';
  import EnhancedTextArea from './EnhancedTextArea.svelte';
  import { dynamicModelsService, type ModelInfo, type ProviderStatus } from '$lib/services/dynamicModelsService';
  import { docAwareService, type SearchMethod, type SearchMethodParameter } from '$lib/services/docAwareService';
  import type { BulkModelData } from '$lib/stores/llmModelsStore';
  import { 
    getMCPServerCredentials, 
    setMCPServerCredentials, 
    testMCPServerConnection, 
    getMCPServerTools 
  } from '$lib/services/mcpServerService';
  import { 
    generateSystemPrompt, 
    previewGeneratedPrompt,
    type PromptGenerationRequest,
    type PromptGenerationResponse 
  } from '$lib/services/promptGenerationService';
  import api from '$lib/services/api';
  
  export let node: any;
  /** Passed by parent (e.g. AgentOrchestrationInterface); kept for API compatibility. */
  export let capabilities: any;
  $: void capabilities; // no-op use to satisfy unused-prop check
  export let projectId: string = ''; // Add projectId prop for DocAware functionality
  export let workflowData: any = null; // Add workflow data to get StartNode input
  export let bulkModelData: BulkModelData | null = null; // Pre-loaded model data
  export let modelsLoaded: boolean = false; // Whether models are loaded
  export let hierarchicalPaths: any[] = []; // Hierarchical paths for Content Filter
  export let hierarchicalPathsLoaded: boolean = false; // Whether hierarchical paths are loaded
  export let uploadedDocumentPaths: any[] = []; // Uploaded-file tree for node File Attachments picker
  export let uploadedDocumentPathsLoaded: boolean = false;
  export let documentsInfo: any = null; // Document and processing status info
  // Per-document LLM upload status from backend/docaware_views.hierarchical_paths
  // Shape: documentLlmStatus[filename][provider] = { status: string, reason?: string }
  export let documentLlmStatus: Record<string, Record<string, { status: string; reason?: string }>> = {};
  export let isMaximized: boolean = false; // Whether the panel is maximized as modal
  
  const dispatch = createEventDispatcher();
  
  // Track the current node ID to detect changes
  let currentNodeId = node.id;
  
  // Editable node data - Initialize from current node
  let nodeName = node.data.name || node.data.label || node.type;
  let nodeDescription = node.data.description || '';
  let nodeConfig = { ...node.data };
  
  // API Key based models state
  let availableModels: ModelInfo[] = [];
  let loadingModels = false;
  let modelsError: string | null = null;
  let lastProviderChange = '';
  let providerStatus: ProviderStatus | null = null;
  let hasValidApiKeys = false;
  
  // Request cancellation tracking to prevent stale updates
  let currentLoadRequestId = 0;
  
  // 📚 DocAware state
  let availableSearchMethods: SearchMethod[] = [];
  let loadingSearchMethods = false;
  let searchMethodsError: string | null = null;
  let selectedSearchMethod: SearchMethod | null = null;
  let searchParameters: Record<string, any> = {};
  let testingSearch = false;
  let testSearchResults: any = null;
  let testSearchQuery = ''; // Custom test search query entered by user
  let expandedResults: Set<number> = new Set(); // Track which results are expanded
  
  // 🔧 MCP Server state
  let mcpGoogleDriveCredentials = {
    client_id: '',
    client_secret: '',
    refresh_token: ''
  };
  let mcpSharePointCredentials = {
    tenant_id: '',
    client_id: '',
    client_secret: '',
    site_url: ''
  };
  let mcpCredentialName = '';
  let loadingMCPCredentials = false;
  let savingMCPCredentials = false;
  let testingMCPConnection = false;
  let mcpConnectionTestResult: any = null;
  let mcpAvailableTools: any[] = [];
  let loadingMCPTools = false;
  let mcpCredentialStatus: any = null;
  
  // 🤖 Prompt Generation state
  let generatingPrompt = false;
  let generatedPromptPreview: string | null = null;
  let promptGenerationError: string | null = null;
  let showPromptPreview = false;
  let autoGenerateEnabled = false;
  let descriptionDebounceTimer: ReturnType<typeof setTimeout> | null = null;
  let promptGenerationMetadata: any = null;

  // Clear web cache state
  let clearingWebCache = false;
  let webCacheCleared = false;

  async function doClearWebCache() {
    if (!projectId || clearingWebCache) return;
    clearingWebCache = true;
    webCacheCleared = false;
    try {
      await api.post(`/agent-orchestration/projects/${projectId}/clear-websearch-cache/`, {});
      webCacheCleared = true;
      setTimeout(() => { webCacheCleared = false; }, 3000);
    } catch (err: any) {
      console.warn('Clear web cache failed:', err);
    } finally {
      clearingWebCache = false;
    }
  }

  // Web search URL indexing state
  let syncingWebIndex = false;
  let webIndexStatus: string | null = null;
  let webIndexDebounceTimer: ReturnType<typeof setTimeout> | null = null;

  function debouncedSyncWebIndex(urls: string[]) {
    if (webIndexDebounceTimer) clearTimeout(webIndexDebounceTimer);
    webIndexDebounceTimer = setTimeout(() => {
      doSyncWebIndex(urls);
    }, 2000); // 2s debounce — user stops typing
  }

  async function doSyncWebIndex(urls: string[]) {
    if (!projectId || syncingWebIndex) return;
    const validUrls = urls.filter(u => u.startsWith('http://') || u.startsWith('https://'));
    if (validUrls.length === 0) return;
    syncingWebIndex = true;
    webIndexStatus = null;
    try {
      const cacheTtl = nodeConfig.web_search_cache_ttl ?? 2592000;
      const res = await api.post(`/agent-orchestration/projects/${projectId}/sync-websearch-index/`, {
        urls: validUrls,
        cache_ttl: cacheTtl,
      });
      const d = res.data;
      if (d.indexed > 0 || d.removed > 0) {
        webIndexStatus = `Indexed ${d.indexed} new, removed ${d.removed} stale` + (d.failed > 0 ? `, ${d.failed} failed` : '');
      } else {
        webIndexStatus = `All ${d.already_indexed} URLs up to date`;
      }
      setTimeout(() => { webIndexStatus = null; }, 5000);
    } catch (err: any) {
      console.warn('Sync web index failed:', err);
      webIndexStatus = null;
    } finally {
      syncingWebIndex = false;
    }
  }

  // Initialize defaults for new nodes
  function initializeNodeDefaults() {
    // Initialize default LLM configuration if not present
    if (['AssistantAgent', 'DelegateAgent', 'GroupChatManager'].includes(node.type)) {
      if (!nodeConfig.llm_provider) {
        // Set defaults based on agent type - will be updated once we check API keys
        if (node.type === 'AssistantAgent') {
          nodeConfig.llm_provider = 'openai';
          nodeConfig.llm_model = 'gpt-4-turbo';
        } else if (node.type === 'DelegateAgent') {
          nodeConfig.llm_provider = 'anthropic';
          nodeConfig.llm_model = 'claude-3-5-haiku-20241022';
        } else if (node.type === 'GroupChatManager') {
          nodeConfig.llm_provider = 'anthropic';
          nodeConfig.llm_model = 'claude-3-5-sonnet-20241022';
        }
        console.log('🤖 LLM CONFIG: Initialized default config for', node.type, nodeConfig.llm_provider, nodeConfig.llm_model);
      }
      
      // GroupChatManager uses tool-based delegation — no round-robin/intelligent config needed
    } else if (node.type === 'UserProxyAgent') {
      // UserProxyAgent only gets LLM configuration if DocAware is enabled
      if (nodeConfig.doc_aware && !nodeConfig.llm_provider) {
        nodeConfig.llm_provider = 'openai';
        nodeConfig.llm_model = 'gpt-3.5-turbo';
        console.log('🤖 LLM CONFIG: Initialized DocAware LLM config for UserProxyAgent');
      }
      
      // Initialize system message if not present for agents that need it
      if (['AssistantAgent', 'DelegateAgent', 'GroupChatManager'].includes(node.type)) {
        if (!nodeConfig.system_message) {
          if (node.type === 'AssistantAgent') {
            nodeConfig.system_message = 'You are a helpful AI assistant.';
          } else if (node.type === 'DelegateAgent') {
            nodeConfig.system_message = 'You are a specialized delegate agent.';
          } else if (node.type === 'GroupChatManager') {
            nodeConfig.system_message = 'You are a Group Chat Manager responsible for coordinating multiple specialized agents and synthesizing their contributions into comprehensive solutions.';
          }
          console.log('💬 SYSTEM MESSAGE: Initialized default system message for', node.type);
        }
      }

      // Initialize default RAG configuration if not present
      if (['AssistantAgent', 'UserProxyAgent', 'DelegateAgent'].includes(node.type) && !nodeConfig.hasOwnProperty('doc_aware')) {
        nodeConfig.doc_aware = false;
        nodeConfig.vector_collections = [];
        nodeConfig.rag_search_limit = 5;
        nodeConfig.rag_relevance_threshold = 0.7;
        nodeConfig.query_refinement_enabled = false;
        console.log('📚 RAG CONFIG: Initialized default RAG config for', node.type);
      }

      // Initialize Document Tool Calling default
      if (['AssistantAgent', 'DelegateAgent'].includes(node.type) && !nodeConfig.hasOwnProperty('doc_tool_calling')) {
        nodeConfig.doc_tool_calling = false;
      }
      // Initialize plan_mode default (enabled = planning LLM call runs before tool execution)
      if (['AssistantAgent', 'DelegateAgent'].includes(node.type) && !nodeConfig.hasOwnProperty('plan_mode')) {
        nodeConfig.plan_mode = true;
      }
      // Initialize doc_tool_calling_documents only for new nodes (not for existing nodes that
      // already have doc_tool_calling enabled but no selection — those fall back to all docs)
      if (['AssistantAgent', 'DelegateAgent'].includes(node.type)
          && !nodeConfig.hasOwnProperty('doc_tool_calling_documents')
          && !nodeConfig.doc_tool_calling) {
        nodeConfig.doc_tool_calling_documents = [];
      }
      
      // Initialize query_refinement_enabled if not present (for existing nodes)
      if (['AssistantAgent', 'UserProxyAgent', 'DelegateAgent'].includes(node.type) && !nodeConfig.hasOwnProperty('query_refinement_enabled')) {
        nodeConfig.query_refinement_enabled = false;
      }
      
      // Initialize input_mode for UserProxyAgent (default to 'user' for backward compatibility)
      if (node.type === 'UserProxyAgent' && !nodeConfig.hasOwnProperty('input_mode')) {
        nodeConfig.input_mode = 'user';
        console.log('👤 INPUT MODE: Initialized default input_mode for UserProxyAgent');
      }

      // Initialize content_filters as array if not present
      if (['AssistantAgent', 'UserProxyAgent', 'DelegateAgent'].includes(node.type)) {
        if (!nodeConfig.content_filters || !Array.isArray(nodeConfig.content_filters)) {
          nodeConfig.content_filters = [];
          console.log('📚 CONTENT FILTER: Initialized content_filters as empty array');
        }
      }

      // Initialize file attachment settings if not present
      if (['AssistantAgent', 'UserProxyAgent', 'DelegateAgent'].includes(node.type)) {
        if (!nodeConfig.hasOwnProperty('file_attachments_enabled')) {
          nodeConfig.file_attachments_enabled = false;
        }
        if (!nodeConfig.file_attachment_documents || !Array.isArray(nodeConfig.file_attachment_documents)) {
          nodeConfig.file_attachment_documents = [];
        }
        if (!nodeConfig.inline_file_attachments || !Array.isArray(nodeConfig.inline_file_attachments)) {
          nodeConfig.inline_file_attachments = [];
        }
      }
    }
  }
  
  // 📚 DocAware Methods
  async function loadSearchMethods() {
    if (loadingSearchMethods) return;
    
    try {
      loadingSearchMethods = true;
      searchMethodsError = null;
      
      console.log('📚 DOCAWARE: Loading search methods');
      console.log('📚 DOCAWARE: Making API call to:', '/agent-orchestration/docaware/search_methods/');
      
      const response = await docAwareService.getSearchMethods();
      
      if (!response || !response.methods) {
        throw new Error('Invalid response structure: missing methods array');
      }
      
      availableSearchMethods = response.methods;
      console.log('✅ DOCAWARE: Successfully loaded', availableSearchMethods.length, 'search methods');
      console.log('📚 DOCAWARE: Method IDs:', availableSearchMethods.map(m => m.id));
      
      // Handle existing configuration after methods load
      if (nodeConfig.search_method && !selectedSearchMethod) {
        await handleSearchMethodChange();
      }
      
    } catch (error) {
      console.error('❌ DOCAWARE: Failed to load search methods:', error);
      console.error('❌ DOCAWARE: Error details:', {
        name: error.name,
        message: error.message,
        stack: error.stack,
        response: error.response,
        status: error.response?.status,
        statusText: error.response?.statusText,
        data: error.response?.data
      });
      
      // Provide actionable error messages
      if (error.response?.status === 404) {
        searchMethodsError = 'DocAware API endpoints not found. Check backend URL configuration.';
      } else if (error.response?.status === 403) {
        searchMethodsError = 'Access denied. Check authentication and permissions.';
      } else if (error.response?.status >= 500) {
        searchMethodsError = 'Server error. Check backend service and database connectivity.';
      } else {
        searchMethodsError = `Failed to load search methods: ${error.response?.status || ''} ${error.message}`;
      }
      
      availableSearchMethods = [];
    } finally {
      loadingSearchMethods = false;
    }
  }
  
  async function handleSearchMethodChange() {
    const methodId = nodeConfig.search_method;
    
    if (!methodId) {
      selectedSearchMethod = null;
      searchParameters = {};
      updateNodeData();
      return;
    }
    
    // Ensure search methods are loaded before proceeding
    if (availableSearchMethods.length === 0 && !loadingSearchMethods) {
      console.log('📚 DOCAWARE: Search methods not loaded, loading now...');
      await loadSearchMethods();
    }
    
    selectedSearchMethod = availableSearchMethods.find(m => m.id === methodId) || null;
    
    if (selectedSearchMethod) {
      // Get defaults for the method
      const defaults = docAwareService.getDefaultParameters(selectedSearchMethod);
      
      // Merge: existing values take precedence over defaults
      const existingParams = nodeConfig.search_parameters || {};
      searchParameters = { ...defaults, ...existingParams };
      nodeConfig.search_parameters = { ...searchParameters };
      
      console.log('📚 DOCAWARE: Selected method:', selectedSearchMethod.name);
      console.log('📚 DOCAWARE: Default parameters:', defaults);
      console.log('📚 DOCAWARE: Existing parameters:', existingParams);
      console.log('📚 DOCAWARE: Merged parameters:', searchParameters);
      
      updateNodeData();
    } else if (availableSearchMethods.length > 0) {
      console.error('📚 DOCAWARE: Method not found:', methodId, 'Available:', availableSearchMethods.map(m => m.id));
    }
  }
  
  function handleSearchParameterChange(paramKey: string, value: any) {
    searchParameters[paramKey] = value;
    nodeConfig.search_parameters = { ...searchParameters };
    
    console.log(`📚 DOCAWARE: Updated parameter ${paramKey}:`, value);
    updateNodeData();
  }
  
  async function testSearch() {
    if (!selectedSearchMethod || !projectId || testingSearch) return;
    
    try {
      testingSearch = true;
      testSearchResults = null;
      expandedResults = new Set(); // Reset expanded state for new search
      
      console.log('📚 DOCAWARE: Testing search with method:', selectedSearchMethod.id);
      
      let actualQuery = '';
      let inputSource = 'no input available';
      
      // Priority: Use custom test query if provided by user
      if (testSearchQuery && testSearchQuery.trim().length > 0) {
        actualQuery = testSearchQuery.trim();
        inputSource = 'custom test query';
        console.log('📚 DOCAWARE: Using custom test query:', actualQuery);
      } else {
        // Fallback: Use aggregated input from directly connected nodes
        if (workflowData && workflowData.nodes && workflowData.edges) {
          // Find all nodes that connect TO this current node (input sources)
          const currentNodeId = node.id;
          const inputEdges = workflowData.edges.filter(edge => edge.target === currentNodeId);
          
          console.log('📚 DOCAWARE: Found', inputEdges.length, 'input connections to current node');
          
          if (inputEdges.length > 0) {
            const inputContents = [];
            
            for (const edge of inputEdges) {
              const sourceNode = workflowData.nodes.find(n => n.id === edge.source);
              if (sourceNode) {
                console.log('📚 DOCAWARE: Processing connected node:', sourceNode.type, sourceNode.data.name);
                
                if (sourceNode.type === 'StartNode' && sourceNode.data.prompt) {
                  inputContents.push(sourceNode.data.prompt);
                  console.log('📚 DOCAWARE: Added StartNode prompt:', sourceNode.data.prompt);
                } else if (sourceNode.data.system_message) {
                  inputContents.push(sourceNode.data.system_message);
                  console.log('📚 DOCAWARE: Added system message from:', sourceNode.data.name || sourceNode.type);
                }
              }
            }
            
            if (inputContents.length > 0) {
              actualQuery = inputContents.join('; ');
              inputSource = `aggregated input from ${inputEdges.length} connected nodes`;
              console.log('📚 DOCAWARE: Using aggregated input:', actualQuery);
            }
          }
        }
      }
      
      // If no valid query found (neither custom nor from connected nodes), show error
      if (!actualQuery || actualQuery.trim().length === 0) {
        console.error('📚 DOCAWARE: No valid input found');
        testSearchResults = {
          success: false,
          error: 'No test query provided. Please enter a custom test query or connect this DocAware agent to other agents that provide input (StartNode, AssistantAgent, etc.).',
          query: '',
          method: selectedSearchMethod.id
        };
        toasts?.error('No test query provided. Enter a custom query or connect agents with input.');
        return;
      }
      
      console.log('📚 DOCAWARE: Final test query:', actualQuery);
      console.log('📚 DOCAWARE: Input source:', inputSource);
      console.log('📚 DOCAWARE: Content filters (array):', nodeConfig.content_filters);

      const result = await docAwareService.testSearch(
        projectId,
        selectedSearchMethod.id,
        searchParameters,
        actualQuery,
        nodeConfig.content_filters || []  // Pass array instead of string
      );
      
      testSearchResults = result;
      
      if (result.success) {
        toasts?.success(`Search test successful! Found ${result.results_count} results using ${inputSource}.`);
      } else {
        toasts?.error(`Search test failed: ${result.error}`);
      }
      
    } catch (error) {
      console.error('❌ DOCAWARE: Search test failed:', error);
      toasts?.error('Search test failed');
    } finally {
      testingSearch = false;
    }
  }
  
  // Check if we have any valid API keys from bulk data
  function checkApiKeyAvailability() {
    if (!bulkModelData || !modelsLoaded) {
      hasValidApiKeys = false;
      modelsError = 'Models not loaded yet. Please wait...';
      return;
    }
    
    // Check bulk data for valid providers
    const validProviders = Object.values(bulkModelData.provider_statuses)
      .filter(status => status.api_key_valid);
    
    hasValidApiKeys = validProviders.length > 0;
    
    console.log('🔑 BULK API KEY CHECK: Has valid API keys:', hasValidApiKeys, 'Valid providers:', validProviders.length);
    
    if (!hasValidApiKeys) {
      modelsError = 'No LLM provider API keys are configured. Please configure API keys in settings.';
      availableModels = [];
      return;
    }
    
    // If current provider doesn't have valid API key, switch to first valid provider
    if (nodeConfig.llm_provider) {
      const currentProviderStatus = bulkModelData.provider_statuses[nodeConfig.llm_provider];
      if (!currentProviderStatus?.api_key_valid) {
        const firstValidProvider = validProviders[0];
        if (firstValidProvider) {
          const providerId = Object.keys(bulkModelData.provider_statuses)
            .find(id => bulkModelData.provider_statuses[id] === firstValidProvider);
          
          if (providerId) {
            console.log(`⚠️ BULK API KEY: Current provider ${nodeConfig.llm_provider} not valid, switching to ${providerId}`);
            nodeConfig.llm_provider = providerId;
            nodeConfig.llm_model = ''; // Will be set when models load
            updateNodeData();
          }
        }
      }
    }
  }
  
  // Load models for the current provider from bulk data
  function loadModelsForProvider(providerId: string, forceRefresh = false) {
    // CRITICAL FIX: Request cancellation mechanism to prevent stale updates
    // Increment request ID to cancel any previous pending requests
    currentLoadRequestId++;
    const requestId = currentLoadRequestId;
    
    // CRITICAL FIX: Ensure we're updating models for the correct node
    // Store the node ID at the time of the call to prevent cross-instance updates
    const currentNodeIdAtCall = node?.id;
    
    if (!providerId) {
      // Only update if this is still the current node and request is still valid
      if (node?.id === currentNodeIdAtCall && requestId === currentLoadRequestId) {
        availableModels = [];
        modelsError = 'No provider selected';
      }
      return;
    }
    
    if (!bulkModelData || !modelsLoaded) {
      // Only update if this is still the current node and request is still valid
      if (node?.id === currentNodeIdAtCall && requestId === currentLoadRequestId) {
        availableModels = [];
        modelsError = 'Models not loaded yet. Please wait...';
        loadingModels = false;
      }
      return;
    }
    
    console.log(`🚀 BULK MODELS: Loading models for provider ${providerId} from bulk data (node: ${currentNodeIdAtCall?.slice(-4)}, requestId: ${requestId})`);
    
    // Get provider status from bulk data
    providerStatus = bulkModelData.provider_statuses[providerId];
    
    if (!providerStatus?.api_key_valid) {
      // Only update if this is still the current node and request is still valid
      if (node?.id === currentNodeIdAtCall && requestId === currentLoadRequestId) {
        availableModels = [];
        modelsError = providerStatus?.message || 'No valid API key for this provider';
      }
      console.log(`❌ BULK MODELS: Provider ${providerId} has no valid API key`);
      return;
    }
    
    // Get models from bulk data - INSTANT!
    const models = bulkModelData.provider_models[providerId] || [];
    
    // CRITICAL FIX: Only update availableModels if this is still the current node and request is still valid
    // This prevents models from appearing in the wrong agent's property panel
    if (node?.id === currentNodeIdAtCall && requestId === currentLoadRequestId) {
      availableModels = models;
      modelsError = null;
      
      console.log(`✅ BULK MODELS: Loaded ${models.length} models for ${providerId} instantly! (node: ${currentNodeIdAtCall?.slice(-4)}, requestId: ${requestId})`, models.map(m => m.id));
      
      // If no models available
      if (models.length === 0) {
        modelsError = `No models available for ${providerId.toUpperCase()}. Please check your API key configuration.`;
        return;
      }
      
      // If current model is not in the list, reset to first available model
      // CRITICAL: Re-verify node and request ID before updating nodeConfig
      if (models.length > 0 && node?.id === currentNodeIdAtCall && requestId === currentLoadRequestId) {
        const currentModel = nodeConfig.llm_model;
        const modelExists = models.some(model => model.id === currentModel);
        
        if (!modelExists) {
          // Final verification before updating nodeConfig
          if (node?.id === currentNodeIdAtCall && requestId === currentLoadRequestId) {
            console.log(`⚠️ BULK MODELS: Current model ${currentModel} not found, switching to ${models[0].id} (node: ${currentNodeIdAtCall?.slice(-4)}, requestId: ${requestId})`);
            nodeConfig.llm_model = models[0].id;
            // Only update node data if node is still valid
            if (node?.id === currentNodeIdAtCall && requestId === currentLoadRequestId) {
              updateNodeData();
            }
          }
        }
      }
    } else {
      console.log(`⏭️ BULK MODELS: Skipping update - node changed from ${currentNodeIdAtCall?.slice(-4)} to ${node?.id?.slice(-4)} or request cancelled (requestId: ${requestId}, current: ${currentLoadRequestId})`);
    }
  }
  
  // Get status object for a document & current provider
  function getDocStatus(filename: string): { status: string; reason?: string } | null {
    const provider = (nodeConfig.llm_provider || 'openai').toLowerCase();

    // Ollama is local — no file upload needed, always ready
    if (provider === 'ollama') {
      return { status: 'ready' };
    }

    const entry = documentLlmStatus[filename];
    if (!entry) {
      // Desktop app: no File API status tracking — documents are processed locally
      // and uploaded on-the-fly when needed. Treat as ready.
      return { status: 'ready' };
    }

    const key = provider === 'gemini' ? 'google' : provider;
    const statusObj = entry[key];
    if (!statusObj) {
      // Provider not tracked yet — will be uploaded on first use
      return { status: 'ready' };
    }
    return statusObj;
  }

  // Convenience: whether the document is fully ready for current provider
  function isDocReady(filename: string): boolean {
    const statusObj = getDocStatus(filename);
    return !!statusObj && statusObj.status === 'ready';
  }

  // Human-readable label for status
  function getDocStatusLabel(filename: string): string {
    const statusObj = getDocStatus(filename);
    if (!statusObj) return 'PENDING';
    switch (statusObj.status) {
      case 'ready':
        return 'Ready';
      case 'not_uploaded':
        return 'Not uploaded yet (will upload when used)';
      case 'file_too_large':
        return 'Too large for this provider (will fail)';
      case 'unsupported_type':
      case 'unsupported':
        return 'Unsupported file type for this provider (will fail)';
      case 'missing_api_key':
        return 'Missing API key for this provider (will fail)';
      default:
        return statusObj.reason || 'PENDING';
    }
  }

  // --- Node-level file attachment helpers ---

  let isUploadingInlineAttachment = false;

  /** Display name for node attachment: strip leading unicode symbols (e.g. checkmark) if present */
  function inlineAttachmentDisplayName(att: { filename?: string }) {
    const raw = (att?.filename || '').trim();
    return raw.replace(/^[\s\u2705\u26A0\uFE0F]+/, '').trim() || raw;
  }

  /** True if any node attachment was uploaded for a different provider than current (google/gemini treated as same) */
  function hasInlineAttachmentProviderMismatch(): boolean {
    const current = (nodeConfig.llm_provider || 'openai').toLowerCase();
    const currentNorm = current === 'gemini' ? 'google' : current;
    const list = nodeConfig.inline_file_attachments || [];
    return list.some((att: { provider?: string }) => {
      const p = (att?.provider || '').toLowerCase();
      const pNorm = p === 'gemini' ? 'google' : p;
      return pNorm && pNorm !== currentNorm;
    });
  }

  /** HTML accept attribute for node file upload by provider (matches backend SUPPORTED_FILE_TYPES) */
  const INLINE_ATTACHMENT_ACCEPT_BY_PROVIDER: Record<string, string> = {
    openai: '.pdf,.txt,.doc,.docx,.md,.rtf',
    anthropic: '.pdf,.txt,.png,.jpg,.jpeg,.gif,.webp',
    google: '.pdf,.txt,.doc,.docx,.md,.rtf,.png,.jpg,.jpeg,.gif,.webp,.mp3,.wav,.mp4',
    gemini: '.pdf,.txt,.doc,.docx,.md,.rtf,.png,.jpg,.jpeg,.gif,.webp,.mp3,.wav,.mp4',
  };
  const INLINE_ATTACHMENT_EXTENSIONS_BY_PROVIDER: Record<string, string[]> = {
    openai: ['pdf', 'txt', 'doc', 'docx', 'md', 'rtf'],
    anthropic: ['pdf', 'txt', 'png', 'jpg', 'jpeg', 'gif', 'webp'],
    google: ['pdf', 'txt', 'doc', 'docx', 'md', 'rtf', 'png', 'jpg', 'jpeg', 'gif', 'webp', 'mp3', 'wav', 'mp4'],
    gemini: ['pdf', 'txt', 'doc', 'docx', 'md', 'rtf', 'png', 'jpg', 'jpeg', 'gif', 'webp', 'mp3', 'wav', 'mp4'],
  };
  function inlineAttachmentAccept(): string {
    const p = (nodeConfig.llm_provider || 'openai').toLowerCase();
    return INLINE_ATTACHMENT_ACCEPT_BY_PROVIDER[p] || INLINE_ATTACHMENT_ACCEPT_BY_PROVIDER.openai;
  }
  function getAllowedExtensionsForCurrentProvider(): string[] {
    const p = (nodeConfig.llm_provider || 'openai').toLowerCase();
    return INLINE_ATTACHMENT_EXTENSIONS_BY_PROVIDER[p] || INLINE_ATTACHMENT_EXTENSIONS_BY_PROVIDER.openai;
  }

  function removeInlineAttachment(index: number) {
    if (!Array.isArray(nodeConfig.inline_file_attachments) || index < 0 || index >= nodeConfig.inline_file_attachments.length) return;
    nodeConfig.inline_file_attachments = [
      ...nodeConfig.inline_file_attachments.slice(0, index),
      ...nodeConfig.inline_file_attachments.slice(index + 1),
    ];
    nodeConfig = { ...nodeConfig };
    updateNodeData();
  }

  // --- Uploaded Project Document Attachment Picker (pre-processing support) ---
  // `uploadedDocumentPaths` comes from backend `uploaded_hierarchical_paths` and
  // is based on *uploaded* ProjectDocument.original_filename (not Milvus).
  $: uploadedFileItems = (uploadedDocumentPaths || []).filter((p) => p?.type === 'file');
  $: uploadedFolderItems = (uploadedDocumentPaths || []).filter((p) => p?.type === 'folder');
  $: uploadedAttachmentItemsForRender = (() => {
    const items = [
      ...(uploadedFolderItems || []),
      ...(uploadedFileItems || [])
    ];

    items.sort((a: any, b: any) => {
      const da = uploadedPathDepth(a?.path || '');
      const db = uploadedPathDepth(b?.path || '');
      if (da !== db) return da - db;

      // Keep folders before files at the same depth
      if (a?.type !== b?.type) return a?.type === 'folder' ? -1 : 1;

      return (a?.displayName || '').localeCompare(b?.displayName || '');
    });

    return items;
  })();

  function uploadedPathDepth(path: string): number {
    if (!path) return 0;
    return path.split('/').filter(Boolean).length;
  }

  function filesUnderUploadedFolder(folderPath: string): string[] {
    const fp = folderPath || '';
    if (!fp) return [];

    const prefix = `${fp}/`;
    return uploadedFileItems
      .filter((f) => {
        const fPath = f?.path || '';
        return fPath === fp || fPath.startsWith(prefix);
      })
      .map((f) => f?.name)
      .filter(Boolean);
  }

  function isFileSelected(fileName: string): boolean {
    return (nodeConfig.file_attachment_documents || []).includes(fileName);
  }

  function isFolderFullySelected(folderPath: string): boolean {
    const files = filesUnderUploadedFolder(folderPath);
    if (files.length === 0) return false;
    const selected = new Set(nodeConfig.file_attachment_documents || []);
    return files.every((n) => selected.has(n));
  }

  function toggleFileSelection(fileName: string, checked: boolean) {
    const selected = new Set(nodeConfig.file_attachment_documents || []);
    if (checked) selected.add(fileName);
    else selected.delete(fileName);
    nodeConfig.file_attachment_documents = Array.from(selected);
    nodeConfig = { ...nodeConfig };
    updateNodeData();
  }

  function toggleFolderSelection(folderPath: string, checked: boolean) {
    const descendants = filesUnderUploadedFolder(folderPath);
    const selected = new Set(nodeConfig.file_attachment_documents || []);

    if (checked) {
      for (const name of descendants) selected.add(name);
    } else {
      for (const name of descendants) selected.delete(name);
    }

    nodeConfig.file_attachment_documents = Array.from(selected);
    nodeConfig = { ...nodeConfig };
    updateNodeData();
  }

  // ── Document Tool Calling document selection helpers ──────────────
  function isDocToolFileSelected(fileName: string): boolean {
    return (nodeConfig.doc_tool_calling_documents || []).includes(fileName);
  }

  function isDocToolFolderFullySelected(folderPath: string): boolean {
    const files = filesUnderUploadedFolder(folderPath);
    if (files.length === 0) return false;
    const selected = new Set(nodeConfig.doc_tool_calling_documents || []);
    return files.every((n) => selected.has(n));
  }

  function toggleDocToolFileSelection(fileName: string, checked: boolean) {
    const selected = new Set(nodeConfig.doc_tool_calling_documents || []);
    if (checked) selected.add(fileName);
    else selected.delete(fileName);
    nodeConfig.doc_tool_calling_documents = Array.from(selected);
    nodeConfig = { ...nodeConfig };
    updateNodeData();
  }

  function toggleDocToolFolderSelection(folderPath: string, checked: boolean) {
    const descendants = filesUnderUploadedFolder(folderPath);
    const selected = new Set(nodeConfig.doc_tool_calling_documents || []);

    if (checked) {
      for (const name of descendants) selected.add(name);
    } else {
      for (const name of descendants) selected.delete(name);
    }

    nodeConfig.doc_tool_calling_documents = Array.from(selected);
    nodeConfig = { ...nodeConfig };
    updateNodeData();
  }

  async function handleInlineFileAttachmentUpload(event: Event) {
    const target = event.currentTarget as HTMLInputElement | null;
    if (!target || !target.files || target.files.length === 0) return;

    const allFiles = Array.from(target.files);
    target.value = '';

    const allowedExts = getAllowedExtensionsForCurrentProvider();
    const files = allFiles.filter((file: File) => {
      const ext = (file.name.split('.').pop() || '').toLowerCase();
      return allowedExts.includes(ext);
    });
    if (files.length < allFiles.length) {
      const skipped = allFiles.length - files.length;
      toasts.error?.(`${skipped} file(s) skipped: type not supported for ${nodeConfig.llm_provider || 'openai'}. Allowed: ${allowedExts.join(', ')}`);
    }
    if (files.length === 0) return;

    if (!projectId || !workflowData || !workflowData.workflow || !workflowData.workflow.workflow_id) {
      console.error('❌ INLINE ATTACHMENT: Missing projectId or workflowData.workflow.workflow_id');
      toasts.error?.('Cannot upload attachment: missing workflow context.');
      return;
    }

    const provider = (nodeConfig.llm_provider || 'openai').toLowerCase();
    const workflowId = workflowData.workflow.workflow_id;
    const uploaded: string[] = [];
    let failed = 0;

    try {
      isUploadingInlineAttachment = true;
      for (const file of files) {
        const formData = new FormData();
        formData.append('file', file);
        formData.append('provider', provider);

        try {
          const response = await api.post(
            `/projects/${projectId}/workflows/${workflowId}/nodes/${node.id}/upload-file-attachment/`,
            formData,
            { headers: { 'Content-Type': 'multipart/form-data' } }
          );

          const data = (response as any).data || response;
          if (!data || !data.file_id) {
            console.error('❌ INLINE ATTACHMENT: Invalid response from upload endpoint', data);
            failed += 1;
            continue;
          }

          if (!Array.isArray(nodeConfig.inline_file_attachments)) {
            nodeConfig.inline_file_attachments = [];
          }
          nodeConfig.inline_file_attachments = [
            ...nodeConfig.inline_file_attachments,
            { ...data, filename: (data.filename || file.name || '').replace(/^[\s\u2705\u26A0\uFE0F]+/, '').trim() || file.name }
          ];
          uploaded.push(data.filename || file.name);
          nodeConfig = { ...nodeConfig };
          updateNodeData();
        } catch (err: any) {
          console.error('❌ INLINE ATTACHMENT: Upload failed for', file.name, err);
          failed += 1;
        }
      }

      nodeConfig = { ...nodeConfig };
      updateNodeData();

      if (uploaded.length > 0) {
        toasts.success?.(uploaded.length === 1
          ? `Attached file "${uploaded[0]}" for this node.`
          : `${uploaded.length} files attached for this node.`);
      }
      if (failed > 0) {
        toasts.error?.(`${failed} file(s) failed to upload.`);
      }
    } catch (error: any) {
      console.error('❌ INLINE ATTACHMENT: Upload failed', error);
      const message =
        error?.response?.data?.error ||
        error?.message ||
        'Attachment upload failed. Please try again.';
      toasts.error?.(message);
    } finally {
      isUploadingInlineAttachment = false;
    }
  }

  // Count how many selected file attachment docs are NOT uploaded to the current provider
  function countMissingUploads(): number {
    if (!nodeConfig.file_attachments_enabled || !nodeConfig.file_attachment_documents?.length) return 0;
    return nodeConfig.file_attachment_documents.filter((name: string) => !isDocReady(name)).length;
  }

  // Handle provider change
  function handleProviderChange() {
    const newProvider = nodeConfig.llm_provider;
    
    if (newProvider !== lastProviderChange) {
      console.log(`🔄 PROVIDER CHANGE: From ${lastProviderChange} to ${newProvider}`);
      lastProviderChange = newProvider;
      
      // Reset model - will be set when models load
      nodeConfig.llm_model = '';
      
      // Load models for the new provider from bulk data
      loadModelsForProvider(newProvider, false);
      
      updateNodeData();
    }
  }
  
  // Use controlled updates instead of reactive statements
  let isUpdatingFromNode = false; // Flag to prevent update loops
  let isUserEditing = false; // Flag to prevent reactive sync while user is typing
  let userEditingTimer: ReturnType<typeof setTimeout> | null = null;
  
  function updateLocalStateFromNode() {
    if (!node || !node.id || isUpdatingFromNode) return;
    
    // Extract current values from the node
    const currentName = node.data.name || node.data.label || node.type;
    const currentDesc = node.data.description || '';
    const currentConfig = { ...node.data };
    
    // Check if this is a different node OR if the data has changed
    const isDifferentNode = node.id !== currentNodeId;
    const hasNameChanged = nodeName !== currentName;
    const hasDescChanged = nodeDescription !== currentDesc;
    const hasConfigChanged = JSON.stringify(nodeConfig) !== JSON.stringify(currentConfig);
    
    // CRITICAL FIX: Always update when node changes, regardless of focus state
    // This prevents stale data from previous nodes appearing in the current node's property panel
    if (isDifferentNode) {
      // Force immediate update for different nodes - don't check focus state
      console.log('🔄 NODE SYNC: Different node detected, forcing immediate state update', {
        from: currentNodeId?.slice(-4),
        to: node.id.slice(-4),
        oldName: nodeName,
        newName: currentName,
        oldDesc: nodeDescription.substring(0, 50),
        newDesc: currentDesc.substring(0, 50)
      });
      
      // Clear prompt generation state when node changes
      generatedPromptPreview = null;
      showPromptPreview = false;
      promptGenerationError = null;
      promptGenerationMetadata = null;
      
      // Update current node ID
      currentNodeId = node.id;
      
      // CRITICAL: Force update nodeName and nodeDescription immediately
      // This prevents the previous node's name from appearing in the new node's property panel
      nodeName = currentName;
      nodeDescription = currentDesc;
      nodeConfig = { ...currentConfig }; // Deep clone to prevent reference issues
      
      console.log('✅ NODE SYNC: State forcefully updated for new node', {
        nodeName,
        nodeDescription: nodeDescription.substring(0, 50),
        nodeId: node.id.slice(-4),
        nodeDataName: node.data?.name,
        nodeDataDesc: (node.data?.description || '').substring(0, 50)
      });
    } else if (!isUserEditing && !isUploadingInlineAttachment && (hasNameChanged || hasDescChanged || (hasConfigChanged && !document.activeElement?.closest('.node-properties-panel')))) {
      // Update if name/description changed OR if config changed and user is not actively editing
      // Skip entirely if user is actively typing or bulk-uploading attachments to prevent overriding their input
      console.log('🔄 NODE SYNC: Node data changed, updating local state', {
        hasNameChanged,
        hasDescChanged,
        hasConfigChanged,
        isUserEditing,
        oldName: nodeName,
        newName: currentName,
        oldDesc: nodeDescription.substring(0, 50),
        newDesc: currentDesc.substring(0, 50)
      });
      
      // Update current node ID if it changed (shouldn't happen, but safety check)
      if (node.id !== currentNodeId) {
        currentNodeId = node.id;
      }
      
      // Update local state to match node data
      if (hasNameChanged) {
        nodeName = currentName;
      }
      if (hasDescChanged) {
        nodeDescription = currentDesc;
      }
      if (hasConfigChanged && !document.activeElement?.closest('.node-properties-panel')) {
        // Only update config if user is not actively editing
        nodeConfig = { ...currentConfig }; // Deep clone to prevent reference issues
      }
      
      console.log('✅ NODE SYNC: Local state updated', {
        nodeName,
        nodeDescription: nodeDescription.substring(0, 50),
        nodeId: node.id.slice(-4),
        nodeDataName: node.data?.name,
        nodeDataDesc: (node.data?.description || '').substring(0, 50)
      });
    }
  }
  
  // Initialize on mount and when node changes
  // 🔧 MCP Server Methods
  async function loadMCPCredentials() {
    if (!projectId || !nodeConfig.server_type || loadingMCPCredentials) return;
    
    try {
      loadingMCPCredentials = true;
      const creds = await getMCPServerCredentials(projectId, nodeConfig.server_type);
      
      if (creds) {
        mcpCredentialStatus = creds;
        mcpCredentialName = creds.credential_name || '';
        // Note: We can't decrypt credentials on frontend for security
        // User will need to re-enter them if they want to update
      } else {
        mcpCredentialStatus = null;
        mcpCredentialName = '';
      }
      
      // Load available tools if credentials exist
      if (creds?.is_validated) {
        await loadMCPTools();
      }
    } catch (error: any) {
      console.error('Error loading MCP credentials:', error);
      mcpCredentialStatus = null;
    } finally {
      loadingMCPCredentials = false;
    }
  }
  
  async function loadMCPTools() {
    if (!projectId || !nodeConfig.server_type || loadingMCPTools) return;
    
    try {
      loadingMCPTools = true;
      mcpAvailableTools = await getMCPServerTools(projectId, nodeConfig.server_type);
    } catch (error: any) {
      console.error('Error loading MCP tools:', error);
      mcpAvailableTools = [];
    } finally {
      loadingMCPTools = false;
    }
  }
  
  async function saveMCPCredentials() {
    if (!projectId || !nodeConfig.server_type || savingMCPCredentials) return;
    
    // Validate required fields
    if (nodeConfig.server_type === 'google_drive') {
      if (!mcpGoogleDriveCredentials.client_id || !mcpGoogleDriveCredentials.client_secret || !mcpGoogleDriveCredentials.refresh_token) {
        toasts?.error('Please fill in all required Google Drive credentials');
        return;
      }
    } else if (nodeConfig.server_type === 'sharepoint') {
      if (!mcpSharePointCredentials.tenant_id || !mcpSharePointCredentials.client_id || !mcpSharePointCredentials.client_secret) {
        toasts?.error('Please fill in all required SharePoint credentials');
        return;
      }
      // Store site_url in server_config
      if (!nodeConfig.server_config) nodeConfig.server_config = {};
      nodeConfig.server_config.site_url = mcpSharePointCredentials.site_url;
      updateNodeData();
    }
    
    try {
      savingMCPCredentials = true;
      const credentials = nodeConfig.server_type === 'google_drive' 
        ? mcpGoogleDriveCredentials 
        : mcpSharePointCredentials;
      
      await setMCPServerCredentials(
        projectId,
        nodeConfig.server_type,
        credentials,
        mcpCredentialName,
        nodeConfig.server_config || {}
      );
      
      toasts?.success('MCP server credentials saved successfully');
      await loadMCPCredentials();
      mcpConnectionTestResult = null;
    } catch (error: any) {
      toasts?.error(`Failed to save credentials: ${error.message}`);
    } finally {
      savingMCPCredentials = false;
    }
  }
  
  async function testMCPConnection() {
    if (!projectId || !nodeConfig.server_type || testingMCPConnection) return;
    
    // Save credentials first if not already saved
    if (!mcpCredentialStatus) {
      await saveMCPCredentials();
    }
    
    try {
      testingMCPConnection = true;
      mcpConnectionTestResult = null;
      
      const result = await testMCPServerConnection(projectId, nodeConfig.server_type);
      mcpConnectionTestResult = result;
      
      if (result.success) {
        toasts?.success(`Connection successful! Found ${result.tools_count || 0} tools.`);
        await loadMCPTools();
      } else {
        toasts?.error(`Connection failed: ${result.error || 'Unknown error'}`);
      }
    } catch (error: any) {
      toasts?.error(`Connection test failed: ${error.message}`);
      mcpConnectionTestResult = { success: false, error: error.message };
    } finally {
      testingMCPConnection = false;
    }
  }
  
  function handleServerTypeChange() {
    // Reset credentials when server type changes
    mcpGoogleDriveCredentials = { client_id: '', client_secret: '', refresh_token: '' };
    mcpSharePointCredentials = { tenant_id: '', client_id: '', client_secret: '', site_url: '' };
    mcpCredentialName = '';
    mcpConnectionTestResult = null;
    mcpAvailableTools = [];
    mcpCredentialStatus = null;
    
    // Load credentials for new server type
    if (nodeConfig.server_type) {
      loadMCPCredentials();
    }
    
    updateNodeData();
  }
  
  onMount(async () => {
    // Load MCP credentials if this is an MCPServer node
    if (node.type === 'MCPServer' && projectId && nodeConfig.server_type) {
      await loadMCPCredentials();
    }
    initializeNodeDefaults();
    console.log('🔧 NODE PROPERTIES: Opening panel for node:', node.id, node.type);
    
    // Check API key availability from bulk data
    checkApiKeyAvailability();
    
    // Load models for the current provider from bulk data
    if (nodeConfig.llm_provider && hasValidApiKeys && bulkModelData && modelsLoaded) {
      lastProviderChange = nodeConfig.llm_provider;
      loadModelsForProvider(nodeConfig.llm_provider, false);
    }
    
    // 📚 DOCAWARE: Load search methods if DocAware is supported
    if (['AssistantAgent', 'UserProxyAgent', 'DelegateAgent'].includes(node.type)) {
      await loadSearchMethods();
    }
    
    // Auto-generate Group Chat Manager prompt if delegates are connected
    if (node.type === 'GroupChatManager') {
      // Delay slightly to ensure workflowData is available
      setTimeout(async () => {
        const delegates = findConnectedDelegates();
        if (delegates.length > 0 && (!nodeConfig.system_message || nodeConfig.system_message.trim().length === 0)) {
          console.log('🔧 GROUP CHAT MANAGER: Auto-generating prompt on mount from', delegates.length, 'delegates');
          await autoGenerateGroupChatManagerPrompt();
        }
      }, 500);
    }

  });

  // Cleanup on component destroy
  onDestroy(() => {
    // Clear user editing timer to prevent memory leaks
    if (userEditingTimer) {
      clearTimeout(userEditingTimer);
      userEditingTimer = null;
    }
    // Clear description debounce timer
    if (descriptionDebounceTimer) {
      clearTimeout(descriptionDebounceTimer);
      descriptionDebounceTimer = null;
    }
  });
  
  // Call update function when node changes
  $: if (node && node.id) {
    // Check if this is a different node OR if the node data has changed
    const isDifferentNode = node.id !== currentNodeId;
    const currentName = node.data.name || node.data.label || node.type;
    const currentDesc = node.data.description || '';
    const hasNameChanged = nodeName !== currentName;
    const hasDescChanged = nodeDescription !== currentDesc;
    
    // Clear prompt generation state when switching to a different node
    if (isDifferentNode) {
      const previousNodeId = currentNodeId;
      currentNodeId = node.id;
      
      // CRITICAL FIX: Immediately clear and reset all state when switching nodes
      // This prevents name/description/system_message from one node appearing in another node's property panel
      generatedPromptPreview = null;
      showPromptPreview = false;
      promptGenerationError = null;
      promptGenerationMetadata = null;
      
      // Clear description debounce timer
      if (descriptionDebounceTimer) {
        clearTimeout(descriptionDebounceTimer);
        descriptionDebounceTimer = null;
      }
      
      // Immediately reset nodeName and nodeDescription from the new node's data
      // This ensures the UI reflects the correct node's data, not stale data from the previous node
      const previousName = nodeName;
      const previousDesc = nodeDescription;
      
      // CRITICAL: Always update, even if values appear the same, to ensure reactivity
      nodeName = currentName;
      nodeDescription = currentDesc;
      
      console.log(`🔄 NODE PROPERTIES: Node changed (${previousNodeId?.slice(-4)} → ${node.id.slice(-4)})`, {
        nameChange: previousName !== currentName ? `${previousName} → ${currentName}` : 'no change',
        descChange: previousDesc !== currentDesc ? `${previousDesc.substring(0, 50)}... → ${currentDesc.substring(0, 50)}...` : 'no change'
      });
      
      // CRITICAL FIX: Immediately reset nodeConfig (including system_message) from the new node's data
      // This prevents system_message and other config values from the previous node appearing in the new node's property panel
      const previousSystemMessage = nodeConfig.system_message;
      nodeConfig = { ...node.data }; // Deep clone to prevent reference issues
      const newSystemMessage = nodeConfig.system_message;
      
      if (previousSystemMessage !== newSystemMessage) {
        console.log(`🔄 NODE PROPERTIES: Node changed, reset system_message from "${previousSystemMessage?.substring(0, 50) || 'empty'}..." to "${newSystemMessage?.substring(0, 50) || 'empty'}..."`);
      }
      
      // CRITICAL: Immediately reset model-related state to prevent models from slipping between panels
      availableModels = [];
      modelsError = null;
      loadingModels = false;
      lastProviderChange = '';
      // Cancel any pending model load requests
      currentLoadRequestId++;
      
      // Reset DocAware state
      selectedSearchMethod = null;
      searchParameters = {};
      testSearchResults = null;
      testSearchQuery = ''; // Clear custom test query when switching nodes
      expandedResults = new Set(); // Clear expanded results when switching nodes
      
      // Reset MCP state
      mcpGoogleDriveCredentials = { client_id: '', client_secret: '', refresh_token: '' };
      mcpSharePointCredentials = { tenant_id: '', client_id: '', client_secret: '', site_url: '' };
      mcpCredentialName = '';
      mcpConnectionTestResult = null;
      mcpAvailableTools = [];
      
      console.log('🔄 NODE PROPERTIES: Node changed, cleared all state and reset name/description/system_message/models');
    } else if ((hasNameChanged || hasDescChanged) && !isUserEditing) {
      // Same node but name/description changed externally (e.g., from another component or after save)
      // Skip if user is actively editing to prevent overriding their input
      console.log('🔄 NODE PROPERTIES: Same node but name/description changed externally', {
        hasNameChanged,
        hasDescChanged,
        oldName: nodeName,
        newName: currentName,
        oldDesc: nodeDescription.substring(0, 50),
        newDesc: currentDesc.substring(0, 50),
        isUserEditing
      });
      
      // Update local state to match node data (only if not actively editing)
      if (hasNameChanged) {
        nodeName = currentName;
      }
      if (hasDescChanged) {
        nodeDescription = currentDesc;
      }
    }
    
    // Always call updateLocalStateFromNode to ensure full sync
    updateLocalStateFromNode();
  }
  
  // Handle delayed search method loading for DocAware
  $: if (nodeConfig.doc_aware && !selectedSearchMethod && nodeConfig.search_method && availableSearchMethods.length > 0) {
    console.log('📚 DOCAWARE: Reactive - Setting up search method after delayed loading');
    handleSearchMethodChange();
  }
  
  // Deep clone to prevent shared references
  function updateNodeData() {
    // Preserve spaces in names and descriptions - don't trim during editing
    const saveName = nodeName;
    const saveDesc = nodeDescription;
    
    console.log('🔥 UPDATE NODE DATA: Starting update for node', node.id.slice(-4));
    console.log('🔥 UPDATE NODE DATA: Name change:', (node.data.name || 'undefined') + ' → ' + saveName);
    console.log('🔥 UPDATE NODE DATA: Description change:', (node.data.description || 'undefined').substring(0, 50) + ' → ' + saveDesc.substring(0, 50));
    console.log('🔥 NODE CONFIG CHECK:', JSON.stringify(nodeConfig));
    console.log('📚 DOC AWARE STATUS:', nodeConfig.doc_aware);
    
    // Set flag to prevent updateLocalStateFromNode from running
    isUpdatingFromNode = true;
    
    // Create completely new objects to prevent shared references
    const baseData = JSON.parse(JSON.stringify(node.data));
    const configData = JSON.parse(JSON.stringify(nodeConfig));
    
    // Create data object with explicit order to ensure our values take precedence
    const updatedData = {
      ...baseData,
      ...configData,
      // These MUST come last to override any conflicts - preserve spaces
      name: saveName,
      label: saveName,
      description: saveDesc
    };
    
    const updatedNode = {
      id: node.id, // Keep original ID
      type: node.type, // Keep original type
      position: { ...node.position }, // Clone position
      data: updatedData
    };
    
    console.log('🔥 UPDATE NODE DATA DEBUG:', {
      nodeId: node.id.slice(-4),
      originalName: node.data.name || node.data.label,
      newName: saveName,
      originalDesc: (node.data.description || '').substring(0, 50),
      newDesc: saveDesc.substring(0, 50),
      updatedData: JSON.stringify(updatedNode.data),
      docAwareValue: updatedNode.data.doc_aware,
      dataMemoryCheck: {
        originalRef: node.data,
        newRef: updatedNode.data,
        isSameReference: node.data === updatedNode.data
      }
    });
    
    // Enhanced dispatch with position preservation
    dispatch('nodeUpdate', {
      ...updatedNode,
      canvasUpdate: {
        preservePosition: true,
        updateType: 'properties',
        timestamp: Date.now()
      }
    });
    
    // Reset flag after a short delay
    setTimeout(() => {
      isUpdatingFromNode = false;
    }, 100);
    
    console.log('✅ NODE PROPERTIES: Update dispatched for node', node.id.slice(-4), 'new name:', saveName, 'new desc:', saveDesc.substring(0, 50), 'doc_aware:', updatedNode.data.doc_aware);
  }
  
  function handleNameChange(event: Event | null) {
    const target = event?.target as HTMLInputElement | null;
    const newName = target?.value ?? nodeName;
    const currentName = node.data.name || node.data.label || node.type;
    
    console.log('📝 HANDLE NAME CHANGE: Called with newName=', JSON.stringify(newName), 'currentName=', JSON.stringify(currentName));
    console.log('📝 BINDING CHECK: nodeName variable=', JSON.stringify(nodeName), 'input value=', JSON.stringify(newName));
    
    // Set user editing flag to prevent reactive sync from overriding user input
    isUserEditing = true;
    if (userEditingTimer) clearTimeout(userEditingTimer);
    userEditingTimer = setTimeout(() => {
      isUserEditing = false;
    }, 500); // Reset after 500ms of no input
    
    // Always update nodeName to match input (bind:value should handle this, but ensure it)
    nodeName = newName;
    
    // Compare raw values to allow spaces
    if (newName !== currentName) {
      console.log('📝 NAME CHANGE DEBUG:', {
        from: currentName,
        to: newName,
        nodeId: node.id.slice(-4),
        currentNodeData: node.data
      });
      
      // Update node data immediately
      updateNodeData();
    } else {
      console.log('⚠️ NAME CHANGE: No change detected, not updating');
    }
  }
  
  function handleDescriptionChange(event: Event | null) {
    const target = event?.target as HTMLTextAreaElement | null;
    const newDesc = target?.value ?? nodeDescription;
    const currentDesc = node.data.description || '';
    
    console.log('📝 HANDLE DESC CHANGE: Called with newDesc=', JSON.stringify(newDesc.substring(0, 50)), 'currentDesc=', JSON.stringify(currentDesc.substring(0, 50)));
    
    // Set user editing flag to prevent reactive sync from overriding user input
    isUserEditing = true;
    if (userEditingTimer) clearTimeout(userEditingTimer);
    userEditingTimer = setTimeout(() => {
      isUserEditing = false;
    }, 500); // Reset after 500ms of no input
    
    // Always update nodeDescription to match input (bind:value should handle this, but ensure it)
    nodeDescription = newDesc;
    
    // Compare raw values to allow spaces
    if (newDesc !== currentDesc) {
      console.log('📝 DESC CHANGE DEBUG:', {
        from: currentDesc.substring(0, 50),
        to: newDesc.substring(0, 50),
        nodeId: node.id.slice(-4),
        currentNodeData: node.data
      });
      
      // Update node data immediately
      updateNodeData();
      
      // Auto-generate prompt if enabled and agent type supports it
      if (autoGenerateEnabled && ['AssistantAgent', 'DelegateAgent', 'GroupChatManager'].includes(node.type)) {
        // Clear existing timer
        if (descriptionDebounceTimer) {
          clearTimeout(descriptionDebounceTimer);
        }
        
        // Debounce auto-generation (2 seconds)
        descriptionDebounceTimer = setTimeout(() => {
          if (nodeDescription.trim().length >= 10) {
            generatePromptFromDescription();
          }
        }, 2000);
      }
    } else {
      console.log('⚠️ DESC CHANGE: No change detected, not updating');
    }
  }
  
  // Find connected delegate agents for Group Chat Manager
  function findConnectedDelegates(): Array<{ name: string; description: string }> {
    if (node.type !== 'GroupChatManager' || !workflowData || !workflowData.nodes || !workflowData.edges) {
      return [];
    }
    
    const currentNodeId = node.id;
    const delegates: Array<{ name: string; description: string }> = [];
    
    // Find all edges where this Group Chat Manager is the source and target is a DelegateAgent
    const delegateEdges = workflowData.edges.filter(edge => 
      edge.source === currentNodeId && 
      edge.type === 'delegate'
    );
    
    console.log('🔍 GROUP CHAT MANAGER: Found', delegateEdges.length, 'delegate connections');
    
    for (const edge of delegateEdges) {
      const delegateNode = workflowData.nodes.find(n => n.id === edge.target && n.type === 'DelegateAgent');
      if (delegateNode) {
        const delegateName = delegateNode.data.name || 'Delegate';
        const delegateDescription = delegateNode.data.description || 
                                   delegateNode.data.system_message || 
                                   `${delegateName} is a specialized delegate agent.`;
        
        delegates.push({
          name: delegateName,
          description: delegateDescription
        });
        
        console.log('🔍 GROUP CHAT MANAGER: Found delegate:', delegateName, '-', delegateDescription.substring(0, 50));
      }
    }
    
    return delegates;
  }
  
  // Auto-generate Group Chat Manager prompt from connected delegates
  async function autoGenerateGroupChatManagerPrompt() {
    if (node.type !== 'GroupChatManager') {
      return;
    }
    
    const delegates = findConnectedDelegates();
    
    if (delegates.length === 0) {
      console.log('⚠️ GROUP CHAT MANAGER: No connected delegates found, skipping auto-generation');
      return;
    }
    
    try {
      generatingPrompt = true;
      promptGenerationError = null;
      
      // Build description from delegate capabilities
      const delegateDescriptions = delegates.map(d => 
        `${d.name}: ${d.description}`
      ).join('; ');
      
      // Include Group Chat Manager's own description if available
      const managerDescription = nodeDescription.trim() || node.data.description || '';
      let description = '';
      
      if (managerDescription) {
        description = `Group Chat Manager: ${managerDescription}. This manager coordinates ${delegates.length} specialized delegate agents: ${delegateDescriptions}. The manager should intelligently route tasks to appropriate delegates based on their capabilities and synthesize their responses into comprehensive solutions.`;
      } else {
        description = `Group Chat Manager coordinating ${delegates.length} specialized delegate agents: ${delegateDescriptions}. The manager should intelligently route tasks to appropriate delegates based on their capabilities and synthesize their responses into comprehensive solutions.`;
      }
      
      console.log('🔧 GROUP CHAT MANAGER PROMPT GEN: Auto-generating from', delegates.length, 'delegates');
      console.log('🔧 GROUP CHAT MANAGER PROMPT GEN: Description:', description.substring(0, 100));
      
      const request: PromptGenerationRequest = {
        description: description,
        agent_type: 'GroupChatManager',
        doc_aware: nodeConfig.doc_aware || false,
        project_id: projectId || undefined,
        llm_provider: nodeConfig.llm_provider || 'openai',
        llm_model: nodeConfig.llm_model || 'gpt-4'
      };
      
      const response: PromptGenerationResponse = await generateSystemPrompt(request);
      
      if (response.success && response.generated_prompt) {
        // Auto-apply the generated prompt to system_message
        nodeConfig.system_message = response.generated_prompt;
        updateNodeData();
        
        console.log('✅ GROUP CHAT MANAGER PROMPT GEN: Auto-generated and applied prompt');
        toasts.success(`Auto-generated prompt from ${delegates.length} connected delegate${delegates.length > 1 ? 's' : ''}`);
      } else {
        promptGenerationError = response.error || 'Failed to generate prompt';
        console.error('❌ GROUP CHAT MANAGER PROMPT GEN: Generation failed:', promptGenerationError);
      }
    } catch (error) {
      promptGenerationError = error instanceof Error ? error.message : 'Unknown error';
      console.error('❌ GROUP CHAT MANAGER PROMPT GEN: Exception:', error);
    } finally {
      generatingPrompt = false;
    }
  }
  
  async function generatePromptFromDescription() {
    // Only generate for agents that support system messages
    if (!['AssistantAgent', 'DelegateAgent', 'GroupChatManager'].includes(node.type)) {
      return;
    }
    
    if (!nodeDescription || nodeDescription.trim().length < 10) {
      toasts.warning('Please provide a description (at least 10 characters)');
      return;
    }
    
    try {
      generatingPrompt = true;
      promptGenerationError = null;
      generatedPromptPreview = null;
      
      const request: PromptGenerationRequest = {
        description: nodeDescription.trim(),
        agent_type: node.type,
        doc_aware: nodeConfig.doc_aware || false,
        project_id: projectId || undefined,
        llm_provider: nodeConfig.llm_provider || 'openai',
        llm_model: nodeConfig.llm_model || 'gpt-4'
      };
      
      console.log('🔧 PROMPT GEN: Generating prompt for', node.type, 'with description:', nodeDescription.substring(0, 50));
      
      const response: PromptGenerationResponse = await generateSystemPrompt(request);
      
      if (response.success && response.generated_prompt) {
        generatedPromptPreview = response.generated_prompt;
        promptGenerationMetadata = response.metadata;
        showPromptPreview = true;
        toasts.success('Prompt generated successfully!');
        console.log('✅ PROMPT GEN: Generated prompt:', response.generated_prompt.substring(0, 100));
      } else {
        promptGenerationError = response.error || 'Failed to generate prompt';
        toasts.error(promptGenerationError);
        console.error('❌ PROMPT GEN: Generation failed:', promptGenerationError);
      }
    } catch (error) {
      promptGenerationError = error instanceof Error ? error.message : 'Unknown error';
      toasts.error('Failed to generate prompt: ' + promptGenerationError);
      console.error('❌ PROMPT GEN: Exception:', error);
    } finally {
      generatingPrompt = false;
    }
  }
  
  function applyGeneratedPrompt() {
    if (generatedPromptPreview) {
      nodeConfig.system_message = generatedPromptPreview;
      updateNodeData();
      toasts.success('Generated prompt applied to system message');
      showPromptPreview = false;
    }
  }
  
  function dismissPromptPreview() {
    showPromptPreview = false;
    generatedPromptPreview = null;
    promptGenerationError = null;
  }
  
  function saveNodeChanges() {
    try {
      const updatedNode = {
        ...node,
        data: {
          ...node.data,
          name: nodeName,
          description: nodeDescription,
          label: nodeName, // Ensure label is synchronized
          ...nodeConfig
        }
      };
      
      // Enhanced save with canvas context
      dispatch('nodeUpdate', {
        ...updatedNode,
        canvasUpdate: {
          preservePosition: true,
          updateType: 'save',
          timestamp: Date.now(),
          triggerCanvasRedraw: true
        }
      });
      toasts.success('Node updated successfully');
      
      console.log('✅ NODE PROPERTIES: Node updated:', node.id);
      
    } catch (error) {
      console.error('❌ NODE PROPERTIES: Update failed:', error);
      toasts.error('Failed to update node');
    }
  }
  
  function closePanel() {
    dispatch('close');
  }
  
  function toggleMaximize() {
    dispatch('toggleMaximize');
  }
  
  function getNodeIcon(nodeType: string) {
    switch (nodeType) {
      case 'StartNode': return 'fa-play';
      case 'UserProxyAgent': return 'fa-user';
      case 'AssistantAgent': return 'fa-robot';
      case 'GroupChatManager': return 'fa-users';
      case 'DelegateAgent': return 'fa-handshake';
      case 'EndNode': return 'fa-stop';
      default: return 'fa-cog';
    }
  }
  
  function getNodeTypeColor(nodeType: string) {
    switch (nodeType) {
      case 'StartNode': return 'bg-green-600';
      case 'UserProxyAgent': return 'bg-blue-600';
      case 'AssistantAgent': return 'bg-oxford-blue';
      case 'GroupChatManager': return 'bg-purple-600';
      case 'DelegateAgent': return 'bg-orange-600';
      case 'EndNode': return 'bg-red-600';
      default: return 'bg-gray-600';
    }
  }
  
  // Refresh models function - now uses bulk data
  function refreshModels() {
    if (nodeConfig.llm_provider && bulkModelData && modelsLoaded) {
      console.log('🔄 REFRESH: Refreshing models from bulk data');
      loadModelsForProvider(nodeConfig.llm_provider, false);
    } else {
      console.log('⚠️ REFRESH: Cannot refresh - bulk data not available');
      modelsError = 'Bulk model data not available. Please wait for models to load.';
    }
  }
</script>

<div class="node-properties-panel h-full flex flex-col bg-white">
  <!-- Panel Header -->
  <div class="p-4 border-b border-gray-200">
    <div class="flex items-center justify-between">
      <div class="flex items-center space-x-3">
        <div class="w-10 h-10 {getNodeTypeColor(node.type)} text-white rounded-lg flex items-center justify-center">
          <i class="fas {getNodeIcon(node.type)} text-lg"></i>
        </div>
        <div>
          <h3 class="font-semibold text-gray-900">Agent Properties</h3>
          <p class="text-sm text-gray-600">{node.type}</p>
        </div>
      </div>
      <div class="flex items-center space-x-1">
        <!-- Maximize/Restore Button -->
        <button
          class="p-1.5 rounded hover:bg-gray-100 transition-colors"
          on:click={toggleMaximize}
          title={isMaximized ? "Restore to sidebar" : "Maximize panel"}
        >
          <i class="fas {isMaximized ? 'fa-compress' : 'fa-expand'} text-gray-500"></i>
        </button>
        <!-- Close Button -->
        <button
          class="p-1.5 rounded hover:bg-gray-100 transition-colors"
          on:click={closePanel}
          title="Close Panel"
        >
          <i class="fas fa-times text-gray-500"></i>
        </button>
      </div>
    </div>
  </div>
  
  <!-- Properties Form - Enhanced with API Key Based Models -->
  <div class="flex-1 overflow-y-auto p-4 space-y-4">
    
    <!-- API Key Status Warning -->
    {#if !hasValidApiKeys}
      <div class="p-3 bg-red-50 border border-red-200 rounded-lg">
        <div class="flex items-center">
          <i class="fas fa-exclamation-triangle text-red-500 mr-2"></i>
          <div class="text-red-700">
            <div class="font-medium">No LLM API Keys Configured</div>
            <div class="text-sm mt-1">Please configure API keys for OpenAI, Anthropic, or Google AI to use LLM models.</div>
          </div>
        </div>
      </div>
    {/if}
    
    <!-- AGENT NAME -->
    <div>
      <label class="block text-sm font-medium text-gray-700 mb-2">Agent Name</label>
      <input
        type="text"
        bind:value={nodeName}
        on:input={(e) => {
          nodeName = e.target.value;
          handleNameChange(e);
        }}
        on:blur={(e) => {
          nodeName = e.target.value;
          handleNameChange(e);
        }}
        class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:border-oxford-blue focus:ring-2 focus:ring-oxford-blue focus:ring-opacity-20 transition-all"
        placeholder="Enter agent name..."
      />
    </div>
    
    <!-- DESCRIPTION -->
    {#if ['AssistantAgent', 'DelegateAgent', 'GroupChatManager'].includes(node.type)}
      <div>
        <div class="flex items-center justify-between mb-2">
          <label class="block text-sm font-medium text-gray-700">
            Description
            {#if node.type === 'DelegateAgent'}
              <i class="fas fa-info-circle ml-1 text-gray-400" title="Describe this delegate's capabilities and expertise. This helps the Group Chat Manager route queries intelligently."></i>
            {/if}
          </label>
          <div class="flex items-center space-x-2">
            <label class="flex items-center space-x-1 text-xs text-gray-600">
              <input
                type="checkbox"
                bind:checked={autoGenerateEnabled}
                class="form-checkbox h-3 w-3 text-oxford-blue rounded"
              />
              <span>Auto-generate</span>
            </label>
            <button
              on:click={generatePromptFromDescription}
              disabled={generatingPrompt || !nodeDescription || nodeDescription.trim().length < 10}
              class="px-3 py-1 text-xs bg-oxford-blue rounded-md hover:bg-blue-700 transition-colors disabled:bg-gray-300 disabled:cursor-not-allowed flex items-center space-x-1"
              style="color: white;"
            >
              {#if generatingPrompt}
                <i class="fas fa-spinner fa-spin" style="color: white;"></i>
                <span style="color: white;">Generating...</span>
              {:else}
                <i class="fas fa-magic" style="color: white;"></i>
                <span style="color: white;">Generate Prompt</span>
              {/if}
            </button>
          </div>
        </div>
        <EnhancedTextArea
          bind:value={nodeDescription}
          on:input={(e) => {
            nodeDescription = e.detail.value;
            handleDescriptionChange({ target: { value: e.detail.value } });
          }}
          rows={4}
          enableLineNumbers={false}
          enableSyntaxHighlight={false}
          placeholder={node.type === 'DelegateAgent' 
            ? "Describe this delegate's capabilities and expertise (e.g., 'Financial analyst specializing in quarterly reports and budget analysis')..."
            : "Describe what this agent does (e.g., 'A research assistant that helps users find information in documents')..."}
          showCharCount={true}
          maxLength={10000}
          helperText={node.type === 'DelegateAgent' && nodeDescription.length >= 100 && nodeDescription.length <= 300 
            ? "Good length for capability matching" 
            : node.type === 'DelegateAgent' && nodeDescription.length > 0 && nodeDescription.length < 100 
            ? "Consider adding more detail (100-300 chars recommended)" 
            : nodeDescription.length < 10 && nodeDescription.length > 0 
            ? "Minimum 10 characters required" 
            : ""}
        />
        
        <!-- Generated Prompt Preview -->
        {#if showPromptPreview && generatedPromptPreview}
          <div class="mt-3 p-3 bg-blue-50 border border-blue-200 rounded-lg">
            <div class="flex items-center justify-between mb-2">
              <h4 class="text-sm font-semibold text-blue-900">Generated Prompt Preview</h4>
              <button
                on:click={dismissPromptPreview}
                class="text-blue-600 hover:text-blue-800 text-xs"
              >
                <i class="fas fa-times"></i>
              </button>
            </div>
            <div class="text-sm text-gray-700 bg-white p-2 rounded border border-blue-100 max-h-48 overflow-y-auto mb-2">
              {generatedPromptPreview}
            </div>
            {#if promptGenerationMetadata}
              <div class="text-xs text-gray-600 mb-2">
                Generated using {promptGenerationMetadata.llm_provider} ({promptGenerationMetadata.llm_model})
                {#if promptGenerationMetadata.fallback_used}
                  <span class="text-yellow-600"> (template fallback)</span>
                {/if}
              </div>
            {/if}
            <div class="flex space-x-2">
              <button
                on:click={applyGeneratedPrompt}
                class="px-3 py-1 text-xs bg-green-600 text-white rounded-md hover:bg-green-700 transition-colors"
              >
                <i class="fas fa-check mr-1"></i> Apply to System Message
              </button>
              <button
                on:click={generatePromptFromDescription}
                disabled={generatingPrompt}
                class="px-3 py-1 text-xs bg-blue-600 text-white rounded-md hover:bg-blue-700 transition-colors disabled:bg-gray-300"
              >
                <i class="fas fa-redo mr-1"></i> Regenerate
              </button>
            </div>
          </div>
        {/if}
        
        {#if promptGenerationError}
          <div class="mt-2 p-2 bg-red-50 border border-red-200 rounded text-xs text-red-700">
            <i class="fas fa-exclamation-circle mr-1"></i>
            {promptGenerationError}
          </div>
        {/if}
      </div>
    {:else}
      <div>
        <EnhancedTextArea
          label="Description"
          bind:value={nodeDescription}
          on:input={(e) => {
            nodeDescription = e.detail.value;
            handleDescriptionChange({ target: { value: e.detail.value } });
          }}
          rows={4}
          enableLineNumbers={false}
          enableSyntaxHighlight={false}
          placeholder="Describe what this agent does..."
        />
      </div>
    {/if}
    
    <!-- SYSTEM MESSAGE - For AI Assistant, Delegate, GroupChatManager, and Start Node -->
    {#if node.type === 'AssistantAgent' || node.type === 'DelegateAgent' || node.type === 'GroupChatManager'}
      <div>
        <div class="flex items-center justify-between mb-2">
          <label class="block text-sm font-medium text-gray-700">System Message</label>
          {#if node.type === 'GroupChatManager'}
            <button
              on:click={autoGenerateGroupChatManagerPrompt}
              disabled={generatingPrompt || !workflowData || findConnectedDelegates().length === 0}
              class="px-2 py-1 text-xs bg-blue-600 text-white rounded-md hover:bg-blue-700 transition-colors disabled:bg-gray-300 disabled:cursor-not-allowed flex items-center space-x-1"
              title="Auto-generate prompt from connected delegates"
            >
              {#if generatingPrompt}
                <i class="fas fa-spinner fa-spin"></i>
                <span>Generating...</span>
              {:else}
                <i class="fas fa-magic"></i>
                <span>Auto-Generate from Delegates</span>
              {/if}
            </button>
          {/if}
        </div>
        <EnhancedTextArea
          bind:value={nodeConfig.system_message}
          on:input={() => updateNodeData()}
          rows={6}
          enableLineNumbers={true}
          enableSyntaxHighlight={true}
          syntaxLanguage="markdown"
          placeholder={node.type === 'AssistantAgent' 
            ? "You are a helpful AI assistant specialized in..." 
            : node.type === 'GroupChatManager'
            ? "You are a Group Chat Manager responsible for coordinating multiple specialized agents..."
            : "You are a specialized delegate agent that works with the Group Chat Manager..."}
        />
        {#if node.type === 'GroupChatManager' && findConnectedDelegates().length > 0}
          <p class="text-xs text-gray-500 mt-1">
            <i class="fas fa-info-circle mr-1"></i>
            Connected to {findConnectedDelegates().length} delegate{findConnectedDelegates().length > 1 ? 's' : ''}. 
            Click "Auto-Generate from Delegates" to create a prompt based on their capabilities.
          </p>
        {/if}
      </div>
    {:else if node.type === 'StartNode'}
      <div>
        <EnhancedTextArea
          label="Initial Prompt"
          bind:value={nodeConfig.prompt}
          on:input={() => updateNodeData()}
          rows={6}
          enableLineNumbers={true}
          enableSyntaxHighlight={true}
          syntaxLanguage="markdown"
          placeholder="Enter the initial prompt to start the workflow..."
        />
      </div>
    {/if}
    
    <!-- LLM PROVIDER - For AI agents (excluding UserProxyAgent which has special handling) -->
    {#if ['AssistantAgent', 'DelegateAgent', 'GroupChatManager'].includes(node.type)}
      <div>
        <label class="block text-sm font-medium text-gray-700 mb-2">LLM Provider</label>
        {#if hasValidApiKeys}
          <select
            bind:value={nodeConfig.llm_provider}
            on:change={handleProviderChange}
            class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:border-oxford-blue focus:ring-2 focus:ring-oxford-blue focus:ring-opacity-20 bg-white"
          >
            <option value="openai">OpenAI</option>
            <option value="anthropic">Anthropic</option>
            <option value="google">Google AI</option>
            <option value="ollama">Ollama (Local)</option>
          </select>
        {:else}
          <select disabled class="w-full px-3 py-2 border border-gray-300 rounded-lg bg-gray-100 text-gray-500">
            <option>No API keys configured</option>
          </select>
        {/if}
        
        <!-- Provider Status Display -->
        {#if providerStatus}
          <div class="mt-2 text-xs">
            {#if providerStatus.api_key_valid}
              <div class="text-green-600 flex items-center">
                <i class="fas fa-check-circle mr-1"></i>
                {providerStatus.name} API key configured and valid
              </div>
            {:else}
              <div class="text-red-600 flex items-center">
                <i class="fas fa-exclamation-circle mr-1"></i>
                {providerStatus.message}
              </div>
            {/if}
          </div>
        {/if}
      </div>
      
      <!-- LLM MODEL - Enhanced with API Key Based Loading -->
      <div>
        <div class="flex items-center justify-between mb-2">
          <label class="text-sm font-medium text-gray-700">LLM Model</label>
          {#if nodeConfig.llm_provider && hasValidApiKeys}
            <button
              class="text-xs text-oxford-blue hover:text-blue-700 transition-colors flex items-center"
              on:click={refreshModels}
              disabled={loadingModels}
              title="Refresh models list"
            >
              <i class="fas {loadingModels ? 'fa-spinner fa-spin' : 'fa-sync-alt'} mr-1"></i>
              Refresh
            </button>
          {/if}
        </div>
        
        {#if !hasValidApiKeys}
          <select disabled class="w-full px-3 py-2 border border-gray-300 rounded-lg bg-gray-100 text-gray-500">
            <option>Configure API keys to see models</option>
          </select>
        {:else if loadingModels}
          <div class="w-full px-3 py-2 border border-gray-300 rounded-lg bg-gray-50 flex items-center justify-center">
            <i class="fas fa-spinner fa-spin mr-2 text-oxford-blue"></i>
            <span class="text-sm text-gray-600">Loading models...</span>
          </div>
        {:else if modelsError}
          <div class="w-full px-3 py-2 border border-red-300 rounded-lg bg-red-50 text-red-700 text-sm">
            <i class="fas fa-exclamation-triangle mr-2"></i>
            {modelsError}
          </div>
        {:else if availableModels.length === 0}
          <select disabled class="w-full px-3 py-2 border border-gray-300 rounded-lg bg-gray-100 text-gray-500">
            {#if nodeConfig.llm_model}
              <option value={nodeConfig.llm_model} selected>{nodeConfig.llm_model}</option>
              <option disabled>---</option>
            {/if}
            <option>{dynamicModelsService.getNoApiKeyMessage(nodeConfig.llm_provider)}</option>
          </select>
        {:else}
          <select
            bind:value={nodeConfig.llm_model}
            on:change={updateNodeData}
            class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:border-oxford-blue focus:ring-2 focus:ring-oxford-blue focus:ring-opacity-20 bg-white"
          >
            {#each availableModels as model}
              <option value={model.id} title={model.capabilities ? model.capabilities.join(', ') : ''}>
                {model.display_name || model.name}
                {#if model.cost_per_1k_tokens}
                  (${model.cost_per_1k_tokens}/1k tokens)
                {/if}
              </option>
            {/each}
          </select>
        {/if}
        
        <!-- Model Info Display -->
        {#if availableModels.length > 0 && nodeConfig.llm_model}
          {@const selectedModel = availableModels.find(m => m.id === nodeConfig.llm_model)}
          {#if selectedModel}
            <div class="mt-2 p-2 bg-blue-50 rounded-lg border border-blue-200">
              <div class="text-xs text-blue-700">
                <div class="flex items-center justify-between">
                  <span class="font-medium">{selectedModel.display_name}</span>
                  {#if selectedModel.cost_per_1k_tokens}
                    <span class="bg-blue-100 px-2 py-1 rounded">${selectedModel.cost_per_1k_tokens}/1k tokens</span>
                  {/if}
                </div>
                {#if selectedModel.context_length}
                  <div class="mt-1">Context: {selectedModel.context_length.toLocaleString()} tokens</div>
                {/if}
                {#if selectedModel.capabilities && selectedModel.capabilities.length > 0}
                  <div class="mt-1">Capabilities: {selectedModel.capabilities.join(', ')}</div>
                {/if}
                {#if selectedModel.recommended_for && selectedModel.recommended_for.includes(node.type)}
                  <div class="mt-1 text-green-700">
                    <i class="fas fa-check-circle mr-1"></i>
                    Recommended for {node.type}
                  </div>
                {/if}
              </div>
            </div>
          {/if}
        {/if}
      </div>
      
      <!-- TEMPERATURE AND MAX TOKENS/MAX ROUNDS - Different layout for GroupChatManager -->
      {#if node.type === 'GroupChatManager'}
        <!-- Delegation uses tool-based routing (no user-facing config needed) -->
        <div class="p-3 bg-indigo-50 border border-indigo-200 rounded-lg">
          <p class="text-xs text-indigo-700">
            <i class="fas fa-magic mr-1"></i>
            Delegation uses tool-based routing: the manager creates a plan, then
            dispatches tasks to delegates via tool calls based on their descriptions.
          </p>
        </div>
      {/if}
    {/if}
    
    <!-- USERPROXY AGENT SPECIFIC CONFIGURATION -->
    {#if node.type === 'UserProxyAgent'}
      <!-- DocAware Toggle -->
      <div>
        <div class="flex items-center justify-between">
          <label class="text-sm font-medium text-gray-700">DocAware</label>
          <label class="relative inline-flex items-center cursor-pointer">
            <input
              type="checkbox"
              checked={nodeConfig.doc_aware}
              on:change={(e) => {
                nodeConfig.doc_aware = e.target.checked;
                
                if (e.target.checked) {
                  nodeConfig.search_method = 'hybrid_search';
                  if (!nodeConfig.vector_collections || nodeConfig.vector_collections.length === 0) {
                    nodeConfig.vector_collections = ['project_documents'];
                  }
                  if (!nodeConfig.llm_provider) {
                    nodeConfig.llm_provider = 'openai';
                    nodeConfig.llm_model = 'gpt-3.5-turbo';
                  }
                } else {
                  nodeConfig.search_method = '';
                  nodeConfig.llm_provider = '';
                  nodeConfig.llm_model = '';
                  nodeConfig.system_message = '';
                }
                
                nodeConfig = { ...nodeConfig };
                updateNodeData();
              }}
              class="sr-only peer"
            />
            <div class="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-blue-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-blue-600"></div>
          </label>
        </div>
        <p class="text-xs text-gray-500 mt-1">Enable document-aware RAG capabilities for this agent</p>
      </div>

      <!-- FILE ATTACHMENTS - Standalone section for UserProxyAgent -->
      <div>
        <div class="flex items-center justify-between">
          <label class="text-sm font-medium text-gray-700">File Attachments</label>
          <label class="relative inline-flex items-center cursor-pointer">
            <input
              type="checkbox"
              checked={nodeConfig.file_attachments_enabled}
              on:change={(e) => {
                nodeConfig.file_attachments_enabled = e.target.checked;
                if (!e.target.checked) {
                  nodeConfig.file_attachment_documents = [];
                }
                nodeConfig = { ...nodeConfig };
                updateNodeData();
              }}
              class="sr-only peer"
            />
            <div class="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-blue-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-blue-600"></div>
          </label>
        </div>
        <p class="text-xs text-gray-500 mt-1">Send entire documents directly to the LLM via the provider's File API</p>
      </div>

      {#if nodeConfig.file_attachments_enabled}
        <div class="border border-gray-200 rounded-lg p-4 bg-gray-50">
          <div class="flex items-center mb-3">
            <i class="fas fa-paperclip text-gray-600 mr-2"></i>
            <h4 class="font-medium text-gray-900">File Attachments</h4>
          </div>

          <div class="mb-3">
            <label class="block text-xs font-medium text-gray-700 mb-1">Select Documents to Attach</label>
            {#if !uploadedDocumentPathsLoaded}
              <div class="w-full px-3 py-2 border border-blue-300 rounded-lg bg-blue-50 flex items-center justify-center">
                <i class="fas fa-spinner fa-spin mr-2 text-blue-600"></i>
                <span class="text-sm text-blue-700">Loading uploaded documents...</span>
              </div>
            {:else if uploadedFileItems.length === 0}
              <div class="text-xs text-yellow-600 p-2 bg-yellow-50 rounded">
                No uploaded project documents available yet. Upload files in the Project Documents tab first.
              </div>
            {:else}
              <div class="max-h-56 overflow-y-auto pr-1 space-y-1">
                {#each uploadedAttachmentItemsForRender as item (item.id)}
                  {#if item.type === 'folder'}
                    {@const depth = uploadedPathDepth(item.path || '')}
                    {@const fileCount = filesUnderUploadedFolder(item.path || '').length}
                    <label
                      class="flex items-center gap-2 text-xs px-2 py-1 rounded hover:bg-gray-100 cursor-pointer"
                      style={`padding-left: ${depth * 12}px;`}
                    >
                      <input
                        type="checkbox"
                        checked={isFolderFullySelected(item.path || '')}
                        on:change={(e) => toggleFolderSelection(item.path || '', e.currentTarget.checked)}
                      />
                      <span class="truncate flex-1">📁 {item.displayName}</span>
                      <span class="ml-auto text-[10px] px-2 py-0.5 rounded bg-gray-100 text-gray-600">
                        {fileCount}
                      </span>
                    </label>
                  {:else}
                    {@const depth = uploadedPathDepth(item.path || '') + 1}
                    <label
                      class="flex items-center gap-2 text-xs px-2 py-1 rounded hover:bg-gray-100 cursor-pointer"
                      style={`padding-left: ${depth * 12}px;`}
                    >
                      <input
                        type="checkbox"
                        checked={isFileSelected(item.name)}
                        on:change={(e) => toggleFileSelection(item.name, e.currentTarget.checked)}
                      />
                      <span class="truncate flex-1">📄 {item.displayName}</span>
                      <span class="ml-auto text-[10px] uppercase tracking-wide bg-gray-200 text-gray-800 px-1.5 py-0.5 rounded">
                        {isDocReady(item.name) ? 'Ready' : 'Pending'}
                      </span>
                    </label>
                  {/if}
                {/each}
              </div>
              <p class="text-xs text-gray-500 mt-1">
                Checking a folder includes all descendant files (recursive).
              </p>
            {/if}
          </div>

          <!-- Node-scoped attachments upload (single or bulk) -->
          <div class="mb-3 border-t border-gray-200 pt-3 mt-3">
            <label class="block text-xs font-medium text-gray-700 mb-1">Upload New Attachment For This Node</label>
            <p class="text-xs text-gray-500 mb-2">
              This uploads the file(s) directly to the configured LLM provider as node-specific attachments.
              It will not appear in Project Documents. You can select multiple files at once.
            </p>
            <label class="inline-flex items-center px-3 py-1.5 bg-white border border-gray-300 rounded-md shadow-sm text-xs font-medium text-gray-700 hover:bg-gray-50 cursor-pointer">
              <input
                type="file"
                multiple
                class="hidden"
                accept={inlineAttachmentAccept()}
                on:change={handleInlineFileAttachmentUpload}
                disabled={isUploadingInlineAttachment}
              />
              <i class="fas fa-upload mr-2"></i>
              <span>{isUploadingInlineAttachment ? 'Uploading…' : 'Upload file(s) for this node'}</span>
            </label>

            {#if hasInlineAttachmentProviderMismatch()}
              <div class="mt-3 text-xs text-amber-700 p-2 bg-amber-50 border border-amber-200 rounded flex items-start">
                <i class="fas fa-exclamation-triangle mr-1 mt-0.5 flex-shrink-0"></i>
                <span>
                  Some attachments were uploaded for a different LLM provider than the one currently selected.
                  They will not be sent with this agent. Re-upload files after selecting the desired provider, or switch back to the provider they were uploaded for.
                </span>
              </div>
            {/if}
            {#if nodeConfig.inline_file_attachments && nodeConfig.inline_file_attachments.length > 0}
              <div class="mt-3 space-y-1">
                <label class="block text-xs font-medium text-gray-700">Node-specific attachments</label>
                {#each nodeConfig.inline_file_attachments as att, idx}
                  <div class="flex items-center text-xs px-2 py-1 rounded bg-gray-100 text-gray-700">
                    <i class="fas fa-check text-gray-600 mr-2"></i>
                    <span class="truncate flex-1">{inlineAttachmentDisplayName(att)}</span>
                    <span class="ml-2 text-[10px] uppercase tracking-wide bg-gray-200 text-gray-800 px-1.5 py-0.5 rounded">
                      {att.provider}
                    </span>
                    <button
                      type="button"
                      class="ml-2 p-0.5 text-gray-500 hover:text-red-600 hover:bg-gray-200 rounded focus:outline-none focus:ring-1 focus:ring-gray-400"
                      title="Remove attachment"
                      on:click|stopPropagation={() => removeInlineAttachment(idx)}
                    >
                      <i class="fas fa-trash-alt text-[10px]"></i>
                    </button>
                  </div>
                {/each}
              </div>
            {/if}
          </div>

          {#if nodeConfig.file_attachment_documents?.length > 0}
            <div class="mb-3 space-y-1">
              <label class="block text-xs font-medium text-gray-700">Upload Status ({nodeConfig.llm_provider || 'openai'})</label>
              {#each nodeConfig.file_attachment_documents as docName}
                <div class="flex items-center text-xs px-2 py-1 rounded {isDocReady(docName) ? 'bg-gray-100 text-gray-700' : 'bg-yellow-50 text-yellow-700'}">
                  <span class="mr-1">{isDocReady(docName) ? '✓' : '⚠'}</span>
                  <span class="truncate flex-1">{docName}</span>
                  <span class="ml-2 font-medium">{getDocStatusLabel(docName)}</span>
                </div>
              {/each}
            </div>
          {/if}

          {#if countMissingUploads() > 0}
            <div class="text-xs text-amber-700 p-2 bg-amber-50 border border-amber-200 rounded flex items-start mb-3">
              <i class="fas fa-exclamation-triangle mr-1 mt-0.5"></i>
              <span>
                {countMissingUploads()} document(s) not yet uploaded to <strong>{nodeConfig.llm_provider || 'openai'}</strong>.
                They will be uploaded automatically when the workflow runs.
              </span>
            </div>
          {/if}

          <div class="text-xs text-gray-700 p-2 bg-gray-100 rounded flex items-start">
            <i class="fas fa-info-circle mr-1 mt-0.5"></i>
            <span>
              Files are sent via the LLM provider's File API. Max sizes: OpenAI (512MB), Claude (500MB), Gemini (2GB). 
              Documents are uploaded lazily at execution time if not already uploaded. This works independently of DocAware.
            </span>
          </div>
        </div>
      {/if}
      
      <!-- User Proxy Specific Settings -->
      <div class="space-y-3">
        <div>
          <label class="flex items-center space-x-2">
            <input
              type="checkbox"
              bind:checked={nodeConfig.require_human_input}
              on:change={updateNodeData}
              class="w-4 h-4 text-oxford-blue border-gray-300 rounded focus:ring-oxford-blue"
            />
            <span class="text-sm font-medium text-gray-700">Require Human Input</span>
          </label>
        </div>
        
        <!-- Input Mode Selection -->
        {#if nodeConfig.require_human_input}
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-2">Input Mode</label>
            <div class="space-y-2">
              <label class="flex items-center space-x-2 cursor-pointer">
                <input
                  type="radio"
                  name="input_mode_{node.id}"
                  value="user"
                  checked={nodeConfig.input_mode === 'user' || !nodeConfig.input_mode}
                  on:change={() => {
                    nodeConfig.input_mode = 'user';
                    updateNodeData();
                  }}
                  class="w-4 h-4 text-oxford-blue border-gray-300 focus:ring-oxford-blue"
                />
                <span class="text-sm text-gray-700">User Input</span>
                <span class="text-xs text-gray-500 ml-2">(Collect input from end users in deployment)</span>
              </label>
              <label class="flex items-center space-x-2 cursor-pointer">
                <input
                  type="radio"
                  name="input_mode_{node.id}"
                  value="admin"
                  checked={nodeConfig.input_mode === 'admin'}
                  on:change={() => {
                    nodeConfig.input_mode = 'admin';
                    updateNodeData();
                  }}
                  class="w-4 h-4 text-oxford-blue border-gray-300 focus:ring-oxford-blue"
                />
                <span class="text-sm text-gray-700">Admin Input</span>
                <span class="text-xs text-gray-500 ml-2">(Collect input from admin in admin UI)</span>
              </label>
            </div>
          </div>
        {/if}
        
        <div>
          <label class="flex items-center space-x-2">
            <input
              type="checkbox"
              bind:checked={nodeConfig.code_execution_enabled}
              on:change={updateNodeData}
              class="w-4 h-4 text-oxford-blue border-gray-300 rounded focus:ring-oxford-blue"
            />
            <span class="text-sm font-medium text-gray-700">Enable Code Execution</span>
          </label>
        </div>
      </div>
      
      <!-- LLM PROVIDER - Only visible when DocAware is enabled -->
      {#if nodeConfig.doc_aware}
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-2">LLM Provider</label>
          {#if hasValidApiKeys}
            <select
              bind:value={nodeConfig.llm_provider}
              on:change={handleProviderChange}
              class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:border-oxford-blue focus:ring-2 focus:ring-oxford-blue focus:ring-opacity-20 bg-white"
            >
              <option value="openai">OpenAI</option>
              <option value="anthropic">Anthropic</option>
              <option value="google">Google AI</option>
              <option value="ollama">Ollama (Local)</option>
            </select>
          {:else}
            <select disabled class="w-full px-3 py-2 border border-gray-300 rounded-lg bg-gray-100 text-gray-500">
              <option>No API keys configured</option>
            </select>
          {/if}
          
          <!-- Provider Status Display -->
          {#if providerStatus}
            <div class="mt-2 text-xs">
              {#if providerStatus.api_key_valid}
                <div class="text-green-600 flex items-center">
                  <i class="fas fa-check-circle mr-1"></i>
                  {providerStatus.name} API key configured and valid
                </div>
              {:else}
                <div class="text-red-600 flex items-center">
                  <i class="fas fa-exclamation-circle mr-1"></i>
                  {providerStatus.message}
                </div>
              {/if}
            </div>
          {/if}
        </div>
        
        <!-- LLM MODEL - Only visible when DocAware is enabled -->
        <div>
          <div class="flex items-center justify-between mb-2">
            <label class="text-sm font-medium text-gray-700">LLM Model</label>
            {#if nodeConfig.llm_provider && hasValidApiKeys}
              <button
                class="text-xs text-oxford-blue hover:text-blue-700 transition-colors flex items-center"
                on:click={refreshModels}
                disabled={loadingModels}
                title="Refresh models list"
              >
                <i class="fas {loadingModels ? 'fa-spinner fa-spin' : 'fa-sync-alt'} mr-1"></i>
                Refresh
              </button>
            {/if}
          </div>
          
          {#if !hasValidApiKeys}
            <select disabled class="w-full px-3 py-2 border border-gray-300 rounded-lg bg-gray-100 text-gray-500">
              <option>Configure API keys to see models</option>
            </select>
          {:else if loadingModels}
            <div class="w-full px-3 py-2 border border-gray-300 rounded-lg bg-gray-50 flex items-center justify-center">
              <i class="fas fa-spinner fa-spin mr-2 text-oxford-blue"></i>
              <span class="text-sm text-gray-600">Loading models...</span>
            </div>
          {:else if modelsError}
            <div class="w-full px-3 py-2 border border-red-300 rounded-lg bg-red-50 text-red-700 text-sm">
              <i class="fas fa-exclamation-triangle mr-2"></i>
              {modelsError}
            </div>
          {:else if availableModels.length === 0}
            <select disabled class="w-full px-3 py-2 border border-gray-300 rounded-lg bg-gray-100 text-gray-500">
              {#if nodeConfig.llm_model}
                <option value={nodeConfig.llm_model} selected>{nodeConfig.llm_model}</option>
                <option disabled>---</option>
              {/if}
              <option>{dynamicModelsService.getNoApiKeyMessage(nodeConfig.llm_provider)}</option>
            </select>
          {:else}
            <select
              bind:value={nodeConfig.llm_model}
              on:change={updateNodeData}
              class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:border-oxford-blue focus:ring-2 focus:ring-oxford-blue focus:ring-opacity-20 bg-white"
            >
              {#each availableModels as model}
                <option value={model.id} title={model.capabilities ? model.capabilities.join(', ') : ''}>
                  {model.display_name || model.name}
                  {#if model.cost_per_1k_tokens}
                    (${model.cost_per_1k_tokens}/1k tokens)
                  {/if}
                </option>
              {/each}
            </select>
          {/if}
          
          <!-- Model Info Display -->
          {#if availableModels.length > 0 && nodeConfig.llm_model}
            {@const selectedModel = availableModels.find(m => m.id === nodeConfig.llm_model)}
            {#if selectedModel}
              <div class="mt-2 p-2 bg-blue-50 rounded-lg border border-blue-200">
                <div class="text-xs text-blue-700">
                  <div class="flex items-center justify-between">
                    <span class="font-medium">{selectedModel.display_name}</span>
                    {#if selectedModel.cost_per_1k_tokens}
                      <span class="bg-blue-100 px-2 py-1 rounded">${selectedModel.cost_per_1k_tokens}/1k tokens</span>
                    {/if}
                  </div>
                  {#if selectedModel.context_length}
                    <div class="mt-1">Context: {selectedModel.context_length.toLocaleString()} tokens</div>
                  {/if}
                  {#if selectedModel.capabilities && selectedModel.capabilities.length > 0}
                    <div class="mt-1">Capabilities: {selectedModel.capabilities.join(', ')}</div>
                  {/if}
                  {#if selectedModel.recommended_for && selectedModel.recommended_for.includes(node.type)}
                    <div class="mt-1 text-green-700">
                      <i class="fas fa-check-circle mr-1"></i>
                      Recommended for {node.type}
                    </div>
                  {/if}
                </div>
              </div>
            {/if}
          {/if}
        </div>
        
        <!-- SYSTEM MESSAGE - Only visible when DocAware is enabled -->
        <div>
          <EnhancedTextArea
            label="System Message"
            bind:value={nodeConfig.system_message}
            on:input={() => updateNodeData()}
            rows={6}
            enableLineNumbers={true}
            enableSyntaxHighlight={true}
            syntaxLanguage="markdown"
            placeholder="You are a helpful assistant that uses retrieved documents to answer user questions..."
          />
        </div>
      {/if}
      
      <!-- WEBSEARCH TOGGLE - For UserProxyAgent -->
      <div>
        <div class="flex items-center justify-between">
          <label class="text-sm font-medium text-gray-700">WebSearch</label>
          <label class="relative inline-flex items-center cursor-pointer">
            <input
              type="checkbox"
              checked={nodeConfig.web_search_enabled}
              on:change={(e) => {
                nodeConfig.web_search_enabled = e.target.checked;
                
                if (e.target.checked) {
                  // Set default values when enabling WebSearch
                  if (!nodeConfig.web_search_mode) {
                    nodeConfig.web_search_mode = 'general';
                  }
                  if (!nodeConfig.web_search_cache_ttl) {
                    nodeConfig.web_search_cache_ttl = 2592000; // 30 days default
                  }
                  if (!nodeConfig.web_search_max_results) {
                    nodeConfig.web_search_max_results = 5;
                  }
                  if (!nodeConfig.web_search_urls) {
                    nodeConfig.web_search_urls = [];
                  }
                  if (!nodeConfig.web_search_domains) {
                    nodeConfig.web_search_domains = [];
                  }
                } else {
                  // Clear configuration when disabling WebSearch
                  nodeConfig.web_search_mode = '';
                  nodeConfig.web_search_urls = [];
                  nodeConfig.web_search_domains = [];
                }
                
                nodeConfig = { ...nodeConfig };
                updateNodeData();
              }}
              class="sr-only peer"
            />
            <div class="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-green-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-green-600"></div>
          </label>
        </div>
        <p class="text-xs text-gray-500 mt-1">Enable web search capabilities to retrieve real-time information from the internet</p>
      </div>
      
      <!-- WEBSEARCH CONFIGURATION - Show when WebSearch is enabled (UserProxyAgent) -->
      {#if nodeConfig.web_search_enabled}
        <div class="border border-green-200 rounded-lg p-4 bg-green-50">
          <div class="flex items-center mb-3">
            <i class="fas fa-globe text-green-600 mr-2"></i>
            <h4 class="font-medium text-green-900">Web Search Configuration</h4>
          </div>
          
          <!-- Search Mode Selection -->
          <div class="mb-4">
            <label class="block text-sm font-medium text-gray-700 mb-2">Search Mode</label>
            <select
              bind:value={nodeConfig.web_search_mode}
              on:change={updateNodeData}
              class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:border-green-600 focus:ring-2 focus:ring-green-600 focus:ring-opacity-20 bg-white"
            >
              <option value="general">General Web Search</option>
              <option value="domains">Search Specific Domains</option>
              <option value="urls">Fetch Specific URLs</option>
            </select>
            <p class="text-xs text-gray-500 mt-1">
              {#if nodeConfig.web_search_mode === 'general'}
                Search the entire web using DuckDuckGo
              {:else if nodeConfig.web_search_mode === 'domains'}
                Restrict search to specific domains/websites
              {:else if nodeConfig.web_search_mode === 'urls'}
                Fetch content from specific URLs directly
              {:else}
                Select a search mode to configure web search
              {/if}
            </p>
          </div>
          
          <!-- Domain List (for 'domains' mode) -->
          {#if nodeConfig.web_search_mode === 'domains'}
            <div class="mb-4">
              <label class="block text-sm font-medium text-gray-700 mb-2">
                Search Domains
                <span class="text-xs text-gray-500 ml-1">(one per line)</span>
              </label>
              <textarea
                value={(nodeConfig.web_search_domains || []).join('\n')}
                on:input={(e) => {
                  const domains = e.target.value.split('\n').filter(d => d.trim());
                  nodeConfig.web_search_domains = domains;
                  updateNodeData();
                }}
                rows="3"
                class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:border-green-600 focus:ring-2 focus:ring-green-600 focus:ring-opacity-20"
                placeholder="wikipedia.org&#10;docs.python.org&#10;developer.mozilla.org"
              ></textarea>
              <p class="text-xs text-gray-500 mt-1">Enter domain names (without https://) to restrict search results</p>
            </div>
          {/if}
          
          <!-- URL List (for 'urls' mode) -->
          {#if nodeConfig.web_search_mode === 'urls'}
            <div class="mb-4">
              <label class="block text-sm font-medium text-gray-700 mb-2">
                URLs to Fetch
                <span class="text-xs text-gray-500 ml-1">(one per line)</span>
              </label>
              <textarea
                value={(nodeConfig.web_search_urls || []).join('\n')}
                on:input={(e) => {
                  const urls = e.target.value.split('\n').filter(u => u.trim());
                  nodeConfig.web_search_urls = urls;
                  updateNodeData();
                  debouncedSyncWebIndex(urls);
                }}
                rows="4"
                class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:border-green-600 focus:ring-2 focus:ring-green-600 focus:ring-opacity-20"
                placeholder="https://example.com/page1&#10;https://docs.example.com/api&#10;https://wiki.example.org/article"
              ></textarea>
              <div class="flex items-center gap-2 mt-1">
                <p class="text-xs text-gray-500">Enter full URLs (with https://) to fetch content from specific pages</p>
                {#if syncingWebIndex}
                  <span class="text-xs text-blue-600"><i class="fas fa-spinner fa-spin mr-1"></i>Indexing...</span>
                {/if}
                {#if webIndexStatus}
                  <span class="text-xs text-green-600"><i class="fas fa-check mr-1"></i>{webIndexStatus}</span>
                {/if}
              </div>
              <!-- Relevant Excerpts (RAG top-K) -->
              <div class="mt-3">
                <label class="block text-sm font-medium text-gray-700 mb-2">Relevant Excerpts</label>
                <input
                  type="number"
                  value={nodeConfig.web_search_top_k ?? 5}
                  on:change={(e) => {
                    nodeConfig.web_search_top_k = Math.max(1, Math.min(20, parseInt(e.target.value) || 5));
                    e.target.value = nodeConfig.web_search_top_k;
                    updateNodeData();
                  }}
                  min="1"
                  max="20"
                  class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:border-green-600 focus:ring-2 focus:ring-green-600 focus:ring-opacity-20"
                />
                <p class="text-xs text-gray-500 mt-1">Number of most relevant text excerpts to send to the LLM (1-20). Lower = faster and cheaper.</p>
              </div>
            </div>
          {/if}
          
          <!-- Max Results (for 'general' and 'domains' modes) -->
          {#if nodeConfig.web_search_mode === 'general' || nodeConfig.web_search_mode === 'domains'}
            <div class="mb-4">
              <label class="block text-sm font-medium text-gray-700 mb-2">Max Results</label>
              <input
                type="number"
                bind:value={nodeConfig.web_search_max_results}
                on:input={updateNodeData}
                min="1"
                max="20"
                class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:border-green-600 focus:ring-2 focus:ring-green-600 focus:ring-opacity-20"
              />
              <p class="text-xs text-gray-500 mt-1">Maximum number of search results to retrieve (1-20)</p>
            </div>
          {/if}
          
          <!-- Cache TTL (input in days, stored as seconds) -->
          <div class="mb-4">
            <label class="block text-sm font-medium text-gray-700 mb-2">Cache Duration (days)</label>
            <input
              type="number"
              value={Math.round((nodeConfig.web_search_cache_ttl ?? 2592000) / 86400)}
              on:change={(e) => {
                const days = Math.max(0, Math.min(365, parseInt(e.target.value) || 0));
                nodeConfig.web_search_cache_ttl = days * 86400;
                e.target.value = days;
                updateNodeData();
              }}
              min="0"
              max="365"
              step="1"
              class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:border-green-600 focus:ring-2 focus:ring-green-600 focus:ring-opacity-20"
            />
            <p class="text-xs text-gray-500 mt-1">
              How long to cache fetched page content. 0 = no caching, 30 = 30 days (recommended)
            </p>
          </div>
          
          <!-- Current Configuration Summary -->
          <div class="mt-3 p-2 bg-green-100 border border-green-200 rounded text-xs text-green-700">
            <i class="fas fa-info-circle mr-1"></i>
            <strong>Mode:</strong> {nodeConfig.web_search_mode || 'Not set'} |
            {#if nodeConfig.web_search_mode === 'urls'}
              <strong>URLs:</strong> {(nodeConfig.web_search_urls || []).length} configured
            {:else if nodeConfig.web_search_mode === 'domains'}
              <strong>Domains:</strong> {(nodeConfig.web_search_domains || []).length} configured
            {:else}
              <strong>Max Results:</strong> {nodeConfig.web_search_max_results || 5}
            {/if}
            | <strong>Cache:</strong> {Math.round((nodeConfig.web_search_cache_ttl || 2592000) / 86400)} day(s)
          </div>

          <!-- Clear Web Cache -->
          <div class="mt-2 flex items-center gap-2">
            <button
              on:click={doClearWebCache}
              disabled={clearingWebCache}
              class="flex items-center gap-1 px-3 py-1.5 text-xs font-medium rounded border border-red-300 text-red-600 bg-white hover:bg-red-50 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              <i class="fas {clearingWebCache ? 'fa-spinner fa-spin' : 'fa-trash-alt'}"></i>
              {clearingWebCache ? 'Clearing…' : 'Clear Web Cache'}
            </button>
            {#if webCacheCleared}
              <span class="text-xs text-green-600"><i class="fas fa-check mr-1"></i>Cache cleared — pages will be re-fetched on next run</span>
            {/if}
          </div>
        </div>
      {/if}

    {/if}

    <!-- FILE ATTACHMENTS - Standalone section for sending entire files via LLM File API -->
    {#if ['AssistantAgent', 'DelegateAgent'].includes(node.type)}
      <div>
        <div class="flex items-center justify-between">
          <label class="text-sm font-medium text-gray-700">File Attachments</label>
          <label class="relative inline-flex items-center cursor-pointer">
            <input
              type="checkbox"
              checked={nodeConfig.file_attachments_enabled}
              on:change={(e) => {
                nodeConfig.file_attachments_enabled = e.target.checked;
                if (!e.target.checked) {
                  nodeConfig.file_attachment_documents = [];
                }
                nodeConfig = { ...nodeConfig };
                updateNodeData();
              }}
              class="sr-only peer"
            />
            <div class="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-blue-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-blue-600"></div>
          </label>
        </div>
        <p class="text-xs text-gray-500 mt-1">Send entire documents directly to the LLM via the provider's File API</p>
      </div>

      {#if nodeConfig.file_attachments_enabled}
        <div class="border border-gray-200 rounded-lg p-4 bg-gray-50">
          <div class="flex items-center mb-3">
            <i class="fas fa-paperclip text-gray-600 mr-2"></i>
            <h4 class="font-medium text-gray-900">File Attachments</h4>
          </div>

          <div class="mb-3">
            <label class="block text-xs font-medium text-gray-700 mb-1">Select Documents to Attach</label>
            {#if !uploadedDocumentPathsLoaded}
              <div class="w-full px-3 py-2 border border-blue-300 rounded-lg bg-blue-50 flex items-center justify-center">
                <i class="fas fa-spinner fa-spin mr-2 text-blue-600"></i>
                <span class="text-sm text-blue-700">Loading uploaded documents...</span>
              </div>
            {:else if uploadedFileItems.length === 0}
              <div class="text-xs text-yellow-600 p-2 bg-yellow-50 rounded">
                No uploaded project documents available yet. Upload files in the Project Documents tab first.
              </div>
            {:else}
              <div class="max-h-56 overflow-y-auto pr-1 space-y-1">
                {#each uploadedAttachmentItemsForRender as item (item.id)}
                  {#if item.type === 'folder'}
                    {@const depth = uploadedPathDepth(item.path || '')}
                    {@const fileCount = filesUnderUploadedFolder(item.path || '').length}
                    <label
                      class="flex items-center gap-2 text-xs px-2 py-1 rounded hover:bg-gray-100 cursor-pointer"
                      style={`padding-left: ${depth * 12}px;`}
                    >
                      <input
                        type="checkbox"
                        checked={isFolderFullySelected(item.path || '')}
                        on:change={(e) => toggleFolderSelection(item.path || '', e.currentTarget.checked)}
                      />
                      <span class="truncate flex-1">📁 {item.displayName}</span>
                      <span class="ml-auto text-[10px] px-2 py-0.5 rounded bg-gray-100 text-gray-600">
                        {fileCount}
                      </span>
                    </label>
                  {:else}
                    {@const depth = uploadedPathDepth(item.path || '') + 1}
                    <label
                      class="flex items-center gap-2 text-xs px-2 py-1 rounded hover:bg-gray-100 cursor-pointer"
                      style={`padding-left: ${depth * 12}px;`}
                    >
                      <input
                        type="checkbox"
                        checked={isFileSelected(item.name)}
                        on:change={(e) => toggleFileSelection(item.name, e.currentTarget.checked)}
                      />
                      <span class="truncate flex-1">📄 {item.displayName}</span>
                      <span class="ml-auto text-[10px] uppercase tracking-wide bg-gray-200 text-gray-800 px-1.5 py-0.5 rounded">
                        {isDocReady(item.name) ? 'Ready' : 'Pending'}
                      </span>
                    </label>
                  {/if}
                {/each}
              </div>
              <p class="text-xs text-gray-500 mt-1">
                Checking a folder includes all descendant files (recursive).
              </p>
            {/if}
          </div>

          <!-- Node-scoped attachments upload (single or bulk) -->
          <div class="mb-3 border-t border-gray-200 pt-3 mt-3">
            <label class="block text-xs font-medium text-gray-700 mb-1">Upload New Attachment For This Node</label>
            <p class="text-xs text-gray-500 mb-2">
              This uploads the file(s) directly to the configured LLM provider as node-specific attachments.
              It will not appear in Project Documents. You can select multiple files at once.
            </p>
            <label class="inline-flex items-center px-3 py-1.5 bg-white border border-gray-300 rounded-md shadow-sm text-xs font-medium text-gray-700 hover:bg-gray-50 cursor-pointer">
              <input
                type="file"
                multiple
                class="hidden"
                accept={inlineAttachmentAccept()}
                on:change={handleInlineFileAttachmentUpload}
                disabled={isUploadingInlineAttachment}
              />
              <i class="fas fa-upload mr-2"></i>
              <span>{isUploadingInlineAttachment ? 'Uploading…' : 'Upload file(s) for this node'}</span>
            </label>

            {#if hasInlineAttachmentProviderMismatch()}
              <div class="mt-3 text-xs text-amber-700 p-2 bg-amber-50 border border-amber-200 rounded flex items-start">
                <i class="fas fa-exclamation-triangle mr-1 mt-0.5 flex-shrink-0"></i>
                <span>
                  Some attachments were uploaded for a different LLM provider than the one currently selected.
                  They will not be sent with this agent. Re-upload files after selecting the desired provider, or switch back to the provider they were uploaded for.
                </span>
              </div>
            {/if}
            {#if nodeConfig.inline_file_attachments && nodeConfig.inline_file_attachments.length > 0}
              <div class="mt-3 space-y-1">
                <label class="block text-xs font-medium text-gray-700">Node-specific attachments</label>
                {#each nodeConfig.inline_file_attachments as att, idx}
                  <div class="flex items-center text-xs px-2 py-1 rounded bg-gray-100 text-gray-700">
                    <i class="fas fa-check text-gray-600 mr-2"></i>
                    <span class="truncate flex-1">{inlineAttachmentDisplayName(att)}</span>
                    <span class="ml-2 text-[10px] uppercase tracking-wide bg-gray-200 text-gray-800 px-1.5 py-0.5 rounded">
                      {att.provider}
                    </span>
                    <button
                      type="button"
                      class="ml-2 p-0.5 text-gray-500 hover:text-red-600 hover:bg-gray-200 rounded focus:outline-none focus:ring-1 focus:ring-gray-400"
                      title="Remove attachment"
                      on:click|stopPropagation={() => removeInlineAttachment(idx)}
                    >
                      <i class="fas fa-trash-alt text-[10px]"></i>
                    </button>
                  </div>
                {/each}
              </div>
            {/if}
          </div>

          {#if nodeConfig.file_attachment_documents?.length > 0}
            <div class="mb-3 space-y-1">
              <label class="block text-xs font-medium text-gray-700">Upload Status ({nodeConfig.llm_provider || 'openai'})</label>
              {#each nodeConfig.file_attachment_documents as docName}
                <div class="flex items-center text-xs px-2 py-1 rounded {isDocReady(docName) ? 'bg-gray-100 text-gray-700' : 'bg-yellow-50 text-yellow-700'}">
                  <span class="mr-1">{isDocReady(docName) ? '✓' : '⚠'}</span>
                  <span class="truncate flex-1">{docName}</span>
                  <span class="ml-2 font-medium">{getDocStatusLabel(docName)}</span>
                </div>
              {/each}
            </div>
          {/if}

          {#if countMissingUploads() > 0}
            <div class="text-xs text-amber-700 p-2 bg-amber-50 border border-amber-200 rounded flex items-start mb-3">
              <i class="fas fa-exclamation-triangle mr-1 mt-0.5"></i>
              <span>
                {countMissingUploads()} document(s) not yet uploaded to <strong>{nodeConfig.llm_provider || 'openai'}</strong>.
                They will be uploaded automatically when the workflow runs.
              </span>
            </div>
          {/if}

          <div class="text-xs text-gray-700 p-2 bg-gray-100 rounded flex items-start">
            <i class="fas fa-info-circle mr-1 mt-0.5"></i>
            <span>
              Files are sent via the LLM provider's File API. Max sizes: OpenAI (512MB), Claude (500MB), Gemini (2GB). 
              Documents are uploaded lazily at execution time if not already uploaded. This works independently of DocAware.
            </span>
          </div>
        </div>
      {/if}
    {/if}

    <!-- DOCUMENT TOOL CALLING TOGGLE -->
    {#if ['AssistantAgent', 'DelegateAgent'].includes(node.type)}
      <div>
        <div class="flex items-center justify-between">
          <label class="text-sm font-medium text-gray-700">Document Tool Calling</label>
          <label class="relative inline-flex items-center cursor-pointer">
            <input
              type="checkbox"
              checked={nodeConfig.doc_tool_calling}
              on:change={(e) => {
                nodeConfig.doc_tool_calling = e.target.checked;
                if (!e.target.checked) {
                  nodeConfig.doc_tool_calling_documents = [];
                  nodeConfig.doc_aware = false;
                  nodeConfig.search_method = '';
                  nodeConfig.web_search_enabled = false;
                  nodeConfig.web_search_mode = '';
                  nodeConfig.web_search_urls = [];
                  nodeConfig.web_search_domains = [];
                }
                nodeConfig = { ...nodeConfig };
                updateNodeData();
              }}
              class="sr-only peer"
            />
            <div class="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-blue-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-purple-600"></div>
          </label>
        </div>
        <p class="text-xs text-gray-500 mt-1">Agent analyzes project documents using tool calls with a plan-and-execute approach</p>

        {#if nodeConfig.doc_tool_calling}
          <!-- Plan Mode toggle -->
          <div class="mt-3 flex items-center gap-3 px-1">
            <label class="relative inline-flex items-center cursor-pointer">
              <input
                type="checkbox"
                bind:checked={nodeConfig.plan_mode}
                class="sr-only peer"
              />
              <div class="w-9 h-5 bg-gray-200 peer-focus:outline-none peer-focus:ring-2 peer-focus:ring-blue-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-blue-600"></div>
            </label>
            <div>
              <span class="text-sm font-medium text-gray-700">Plan Mode</span>
              <p class="text-xs text-gray-500">{nodeConfig.plan_mode ? 'Agent plans which documents to consult before executing' : 'Disabled — agent executes tools directly (faster, saves 1 LLM call)'}</p>
            </div>
          </div>

          <div class="mt-3 border border-purple-200 rounded-lg p-3 bg-purple-50/30">
            <label class="text-xs font-medium text-gray-700 mb-2 block">Select Documents for Tool Calling</label>
            {#if !uploadedDocumentPathsLoaded}
              <div class="flex items-center gap-2 text-xs text-gray-500 py-2">
                <svg class="animate-spin h-4 w-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                  <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                  <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"></path>
                </svg>
                Loading uploaded documents...
              </div>
            {:else if uploadedAttachmentItemsForRender.length === 0}
              <p class="text-xs text-gray-500 italic py-2">No documents uploaded. Upload files in the Project Documents tab first.</p>
            {:else}
              <div class="max-h-56 overflow-y-auto pr-1 space-y-1">
                {#each uploadedAttachmentItemsForRender as item (item.id)}
                  {#if item.type === 'folder'}
                    {@const depth = uploadedPathDepth(item.path || '')}
                    {@const fileCount = filesUnderUploadedFolder(item.path || '').length}
                    <label
                      class="flex items-center gap-2 text-xs px-2 py-1 rounded hover:bg-purple-100 cursor-pointer"
                      style={`padding-left: ${depth * 12}px;`}
                    >
                      <input
                        type="checkbox"
                        checked={isDocToolFolderFullySelected(item.path || '')}
                        on:change={(e) => toggleDocToolFolderSelection(item.path || '', e.currentTarget.checked)}
                      />
                      <span class="truncate flex-1">📁 {item.displayName}</span>
                      <span class="ml-auto text-[10px] px-2 py-0.5 rounded bg-purple-100 text-purple-600">
                        {fileCount}
                      </span>
                    </label>
                  {:else}
                    {@const depth = uploadedPathDepth(item.path || '') + 1}
                    <label
                      class="flex items-center gap-2 text-xs px-2 py-1 rounded hover:bg-purple-100 cursor-pointer"
                      style={`padding-left: ${depth * 12}px;`}
                    >
                      <input
                        type="checkbox"
                        checked={isDocToolFileSelected(item.name)}
                        on:change={(e) => toggleDocToolFileSelection(item.name, e.currentTarget.checked)}
                      />
                      <span class="truncate flex-1">📄 {item.displayName}</span>
                      <span class="ml-auto text-[10px] uppercase tracking-wide bg-purple-200 text-purple-800 px-1.5 py-0.5 rounded">
                        {isDocReady(item.name) ? 'Ready' : 'Pending'}
                      </span>
                    </label>
                  {/if}
                {/each}
              </div>
              <p class="text-xs text-gray-500 mt-1">
                Checking a folder includes all descendant files (recursive).
              </p>
            {/if}
            {#if nodeConfig.doc_tool_calling && (nodeConfig.doc_tool_calling_documents || []).length === 0 && uploadedDocumentPathsLoaded && uploadedAttachmentItemsForRender.length > 0}
              <div class="mt-2 flex items-start gap-2 text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded-md px-3 py-2">
                <svg class="w-4 h-4 mt-0.5 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
                  <path fill-rule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clip-rule="evenodd" />
                </svg>
                <span>No documents selected — <strong>{nodeConfig.name || 'this agent'}</strong> will have no document tool access.</span>
              </div>
            {/if}
          </div>
        {/if}
      </div>
    {/if}

    <!-- DOCAWARE TOGGLE - For other applicable agents (excluding UserProxyAgent) -->
    {#if ['AssistantAgent', 'DelegateAgent'].includes(node.type)}
      <div class:opacity-50={!nodeConfig.doc_tool_calling}>
        <div class="flex items-center justify-between">
          <label class="text-sm font-medium text-gray-700">DocAware</label>
          <label
            class="relative inline-flex items-center {nodeConfig.doc_tool_calling ? 'cursor-pointer' : 'cursor-not-allowed'}"
          >
            <input
              type="checkbox"
              checked={nodeConfig.doc_aware}
              disabled={!nodeConfig.doc_tool_calling}
              on:change={(e) => {
                nodeConfig.doc_aware = e.target.checked;
                
                if (e.target.checked) {
                  nodeConfig.search_method = 'hybrid_search';
                  if (!nodeConfig.vector_collections || nodeConfig.vector_collections.length === 0) {
                    nodeConfig.vector_collections = ['project_documents'];
                  }
                } else {
                  nodeConfig.search_method = '';
                }
                
                nodeConfig = { ...nodeConfig };
                updateNodeData();
              }}
              class="sr-only peer"
            />
            <div class="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-blue-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-blue-600 peer-disabled:opacity-60"></div>
          </label>
        </div>
        <p class="text-xs text-gray-500 mt-1">Enable document-aware RAG capabilities for this agent</p>
        {#if !nodeConfig.doc_tool_calling}
          <p class="text-xs text-gray-400 mt-1">Enable Document Tool Calling to use this.</p>
        {/if}
      </div>
      
      <!-- WEBSEARCH TOGGLE - For AssistantAgent, DelegateAgent -->
      <div class:opacity-50={!nodeConfig.doc_tool_calling}>
        <div class="flex items-center justify-between">
          <label class="text-sm font-medium text-gray-700">WebSearch</label>
          <label
            class="relative inline-flex items-center {nodeConfig.doc_tool_calling ? 'cursor-pointer' : 'cursor-not-allowed'}"
          >
            <input
              type="checkbox"
              checked={nodeConfig.web_search_enabled}
              disabled={!nodeConfig.doc_tool_calling}
              on:change={(e) => {
                nodeConfig.web_search_enabled = e.target.checked;
                
                if (e.target.checked) {
                  // Set default values when enabling WebSearch
                  if (!nodeConfig.web_search_mode) {
                    nodeConfig.web_search_mode = 'general';
                  }
                  if (!nodeConfig.web_search_cache_ttl) {
                    nodeConfig.web_search_cache_ttl = 2592000; // 30 days default
                  }
                  if (!nodeConfig.web_search_max_results) {
                    nodeConfig.web_search_max_results = 5;
                  }
                  if (!nodeConfig.web_search_urls) {
                    nodeConfig.web_search_urls = [];
                  }
                  if (!nodeConfig.web_search_domains) {
                    nodeConfig.web_search_domains = [];
                  }
                } else {
                  // Clear configuration when disabling WebSearch
                  nodeConfig.web_search_mode = '';
                  nodeConfig.web_search_urls = [];
                  nodeConfig.web_search_domains = [];
                }
                
                nodeConfig = { ...nodeConfig };
                updateNodeData();
              }}
              class="sr-only peer"
            />
            <div class="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-green-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-green-600 peer-disabled:opacity-60"></div>
          </label>
        </div>
        <p class="text-xs text-gray-500 mt-1">Enable web search capabilities to retrieve real-time information from the internet</p>
        {#if !nodeConfig.doc_tool_calling}
          <p class="text-xs text-gray-400 mt-1">Enable Document Tool Calling to use this.</p>
        {/if}
      </div>
      
      <!-- WEBSEARCH CONFIGURATION - Show when WebSearch is enabled -->
      {#if nodeConfig.doc_tool_calling && nodeConfig.web_search_enabled}
        <div class="border border-green-200 rounded-lg p-4 bg-green-50">
          <div class="flex items-center mb-3">
            <i class="fas fa-globe text-green-600 mr-2"></i>
            <h4 class="font-medium text-green-900">Web Search Configuration</h4>
          </div>
          
          <!-- Search Mode Selection -->
          <div class="mb-4">
            <label class="block text-sm font-medium text-gray-700 mb-2">Search Mode</label>
            <select
              bind:value={nodeConfig.web_search_mode}
              on:change={updateNodeData}
              class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:border-green-600 focus:ring-2 focus:ring-green-600 focus:ring-opacity-20 bg-white"
            >
              <option value="general">General Web Search</option>
              <option value="domains">Search Specific Domains</option>
              <option value="urls">Fetch Specific URLs</option>
            </select>
            <p class="text-xs text-gray-500 mt-1">
              {#if nodeConfig.web_search_mode === 'general'}
                Search the entire web using DuckDuckGo
              {:else if nodeConfig.web_search_mode === 'domains'}
                Restrict search to specific domains/websites
              {:else if nodeConfig.web_search_mode === 'urls'}
                Fetch content from specific URLs directly
              {:else}
                Select a search mode to configure web search
              {/if}
            </p>
          </div>
          
          <!-- Domain List (for 'domains' mode) -->
          {#if nodeConfig.web_search_mode === 'domains'}
            <div class="mb-4">
              <label class="block text-sm font-medium text-gray-700 mb-2">
                Search Domains
                <span class="text-xs text-gray-500 ml-1">(one per line)</span>
              </label>
              <textarea
                value={(nodeConfig.web_search_domains || []).join('\n')}
                on:input={(e) => {
                  const domains = e.target.value.split('\n').filter(d => d.trim());
                  nodeConfig.web_search_domains = domains;
                  updateNodeData();
                }}
                rows="3"
                class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:border-green-600 focus:ring-2 focus:ring-green-600 focus:ring-opacity-20"
                placeholder="wikipedia.org&#10;docs.python.org&#10;developer.mozilla.org"
              ></textarea>
              <p class="text-xs text-gray-500 mt-1">Enter domain names (without https://) to restrict search results</p>
            </div>
          {/if}
          
          <!-- URL List (for 'urls' mode) -->
          {#if nodeConfig.web_search_mode === 'urls'}
            <div class="mb-4">
              <label class="block text-sm font-medium text-gray-700 mb-2">
                URLs to Fetch
                <span class="text-xs text-gray-500 ml-1">(one per line)</span>
              </label>
              <textarea
                value={(nodeConfig.web_search_urls || []).join('\n')}
                on:input={(e) => {
                  const urls = e.target.value.split('\n').filter(u => u.trim());
                  nodeConfig.web_search_urls = urls;
                  updateNodeData();
                  debouncedSyncWebIndex(urls);
                }}
                rows="4"
                class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:border-green-600 focus:ring-2 focus:ring-green-600 focus:ring-opacity-20"
                placeholder="https://example.com/page1&#10;https://docs.example.com/api&#10;https://wiki.example.org/article"
              ></textarea>
              <div class="flex items-center gap-2 mt-1">
                <p class="text-xs text-gray-500">Enter full URLs (with https://) to fetch content from specific pages</p>
                {#if syncingWebIndex}
                  <span class="text-xs text-blue-600"><i class="fas fa-spinner fa-spin mr-1"></i>Indexing...</span>
                {/if}
                {#if webIndexStatus}
                  <span class="text-xs text-green-600"><i class="fas fa-check mr-1"></i>{webIndexStatus}</span>
                {/if}
              </div>
              <!-- Relevant Excerpts (RAG top-K) -->
              <div class="mt-3">
                <label class="block text-sm font-medium text-gray-700 mb-2">Relevant Excerpts</label>
                <input
                  type="number"
                  value={nodeConfig.web_search_top_k ?? 5}
                  on:change={(e) => {
                    nodeConfig.web_search_top_k = Math.max(1, Math.min(20, parseInt(e.target.value) || 5));
                    e.target.value = nodeConfig.web_search_top_k;
                    updateNodeData();
                  }}
                  min="1"
                  max="20"
                  class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:border-green-600 focus:ring-2 focus:ring-green-600 focus:ring-opacity-20"
                />
                <p class="text-xs text-gray-500 mt-1">Number of most relevant text excerpts to send to the LLM (1-20). Lower = faster and cheaper.</p>
              </div>
            </div>
          {/if}
          
          <!-- Max Results (for 'general' and 'domains' modes) -->
          {#if nodeConfig.web_search_mode === 'general' || nodeConfig.web_search_mode === 'domains'}
            <div class="mb-4">
              <label class="block text-sm font-medium text-gray-700 mb-2">Max Results</label>
              <input
                type="number"
                bind:value={nodeConfig.web_search_max_results}
                on:input={updateNodeData}
                min="1"
                max="20"
                class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:border-green-600 focus:ring-2 focus:ring-green-600 focus:ring-opacity-20"
              />
              <p class="text-xs text-gray-500 mt-1">Maximum number of search results to retrieve (1-20)</p>
            </div>
          {/if}
          
          <!-- Cache TTL (input in days, stored as seconds) -->
          <div class="mb-4">
            <label class="block text-sm font-medium text-gray-700 mb-2">Cache Duration (days)</label>
            <input
              type="number"
              value={Math.round((nodeConfig.web_search_cache_ttl ?? 2592000) / 86400)}
              on:change={(e) => {
                const days = Math.max(0, Math.min(365, parseInt(e.target.value) || 0));
                nodeConfig.web_search_cache_ttl = days * 86400;
                e.target.value = days;
                updateNodeData();
              }}
              min="0"
              max="365"
              step="1"
              class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:border-green-600 focus:ring-2 focus:ring-green-600 focus:ring-opacity-20"
            />
            <p class="text-xs text-gray-500 mt-1">
              How long to cache fetched page content. 0 = no caching, 30 = 30 days (recommended)
            </p>
          </div>
          
          <!-- Current Configuration Summary -->
          <div class="mt-3 p-2 bg-green-100 border border-green-200 rounded text-xs text-green-700">
            <i class="fas fa-info-circle mr-1"></i>
            <strong>Mode:</strong> {nodeConfig.web_search_mode || 'Not set'} |
            {#if nodeConfig.web_search_mode === 'urls'}
              <strong>URLs:</strong> {(nodeConfig.web_search_urls || []).length} configured
            {:else if nodeConfig.web_search_mode === 'domains'}
              <strong>Domains:</strong> {(nodeConfig.web_search_domains || []).length} configured
            {:else}
              <strong>Max Results:</strong> {nodeConfig.web_search_max_results || 5}
            {/if}
            | <strong>Cache:</strong> {Math.round((nodeConfig.web_search_cache_ttl || 2592000) / 86400)} day(s)
          </div>

          <!-- Clear Web Cache -->
          <div class="mt-2 flex items-center gap-2">
            <button
              on:click={doClearWebCache}
              disabled={clearingWebCache}
              class="flex items-center gap-1 px-3 py-1.5 text-xs font-medium rounded border border-red-300 text-red-600 bg-white hover:bg-red-50 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              <i class="fas {clearingWebCache ? 'fa-spinner fa-spin' : 'fa-trash-alt'}"></i>
              {clearingWebCache ? 'Clearing…' : 'Clear Web Cache'}
            </button>
            {#if webCacheCleared}
              <span class="text-xs text-green-600"><i class="fas fa-check mr-1"></i>Cache cleared — pages will be re-fetched on next run</span>
            {/if}
          </div>
        </div>
      {/if}
    {/if}

    <!-- DELEGATE-SPECIFIC FIELDS -->
    {#if node.type === 'DelegateAgent'}
      <div class="p-3 bg-orange-50 border border-orange-200 rounded-lg">
        <p class="text-xs text-orange-700">
          <i class="fas fa-info-circle mr-1"></i>
          This delegate is invoked by its parent Group Chat Manager via tool calls.
          Make sure the <strong>Description</strong> field above clearly describes
          this delegate's expertise so the manager can route tasks correctly.
        </p>
      </div>
    {/if}
    
    <!-- MCP SERVER CONFIGURATION -->
    {#if node.type === 'MCPServer'}
      <div class="space-y-4 border-t border-gray-200 pt-4 mt-4">
        <h3 class="text-sm font-semibold text-gray-800">MCP Server Configuration</h3>
        
        <!-- Server Type Selection -->
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-2">Server Type</label>
          <select
            bind:value={nodeConfig.server_type}
            on:change={handleServerTypeChange}
            class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:border-oxford-blue focus:ring-2 focus:ring-oxford-blue focus:ring-opacity-20 bg-white"
          >
            <option value="google_drive">Google Drive</option>
            <option value="sharepoint">SharePoint</option>
          </select>
          <p class="text-xs text-gray-500 mt-1">Select the MCP server type to connect to</p>
        </div>
        
        <!-- Credential Status -->
        {#if mcpCredentialStatus}
          <div class="bg-green-50 border border-green-200 rounded-lg p-3">
            <div class="flex items-center justify-between">
              <div class="flex items-center">
                <i class="fas fa-check-circle text-green-600 mr-2"></i>
                <div>
                  <p class="text-sm text-green-800 font-medium">Credentials Configured</p>
                  <p class="text-xs text-green-700">
                    {mcpCredentialStatus.is_validated ? 'Validated' : 'Not validated'}
                    {#if mcpCredentialName}
                      - {mcpCredentialName}
                    {/if}
                  </p>
                </div>
              </div>
            </div>
          </div>
        {/if}
        
        <!-- Credential Name -->
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-2">Credential Name (Optional)</label>
          <input
            type="text"
            bind:value={mcpCredentialName}
            placeholder="e.g., Production Credentials"
            class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:border-oxford-blue focus:ring-2 focus:ring-oxford-blue focus:ring-opacity-20"
          />
        </div>
        
        <!-- Google Drive Credentials -->
        {#if nodeConfig.server_type === 'google_drive'}
          <div class="space-y-3 border border-gray-200 rounded-lg p-4 bg-gray-50">
            <h4 class="text-sm font-semibold text-gray-800 mb-3">Google Drive Credentials</h4>
            
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-2">OAuth Client ID</label>
              <input
                type="text"
                bind:value={mcpGoogleDriveCredentials.client_id}
                placeholder="Enter Google OAuth Client ID"
                class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:border-oxford-blue focus:ring-2 focus:ring-oxford-blue focus:ring-opacity-20"
              />
            </div>
            
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-2">OAuth Client Secret</label>
              <input
                type="password"
                bind:value={mcpGoogleDriveCredentials.client_secret}
                placeholder="Enter Google OAuth Client Secret"
                class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:border-oxford-blue focus:ring-2 focus:ring-oxford-blue focus:ring-opacity-20"
              />
            </div>
            
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-2">Refresh Token</label>
              <input
                type="password"
                bind:value={mcpGoogleDriveCredentials.refresh_token}
                placeholder="Enter OAuth Refresh Token"
                class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:border-oxford-blue focus:ring-2 focus:ring-oxford-blue focus:ring-opacity-20"
              />
              <p class="text-xs text-gray-500 mt-1">
                Obtain these from Google Cloud Console after setting up OAuth 2.0 credentials
              </p>
            </div>
          </div>
        {/if}
        
        <!-- SharePoint Credentials -->
        {#if nodeConfig.server_type === 'sharepoint'}
          <div class="space-y-3 border border-gray-200 rounded-lg p-4 bg-gray-50">
            <h4 class="text-sm font-semibold text-gray-800 mb-3">SharePoint Credentials</h4>
            
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-2">Tenant ID</label>
              <input
                type="text"
                bind:value={mcpSharePointCredentials.tenant_id}
                placeholder="Enter Azure AD Tenant ID"
                class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:border-oxford-blue focus:ring-2 focus:ring-oxford-blue focus:ring-opacity-20"
              />
            </div>
            
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-2">Client ID (Application ID)</label>
              <input
                type="text"
                bind:value={mcpSharePointCredentials.client_id}
                placeholder="Enter Azure AD Application (Client) ID"
                class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:border-oxford-blue focus:ring-2 focus:ring-oxford-blue focus:ring-opacity-20"
              />
            </div>
            
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-2">Client Secret</label>
              <input
                type="password"
                bind:value={mcpSharePointCredentials.client_secret}
                placeholder="Enter Azure AD Client Secret"
                class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:border-oxford-blue focus:ring-2 focus:ring-oxford-blue focus:ring-opacity-20"
              />
            </div>
            
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-2">SharePoint Site URL</label>
              <input
                type="text"
                bind:value={mcpSharePointCredentials.site_url}
                placeholder="https://contoso.sharepoint.com/sites/MySite"
                class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:border-oxford-blue focus:ring-2 focus:ring-oxford-blue focus:ring-opacity-20"
              />
              <p class="text-xs text-gray-500 mt-1">
                Full URL of the SharePoint site you want to access
              </p>
            </div>
          </div>
        {/if}
        
        <!-- Security Notice -->
        <div class="bg-blue-50 border border-blue-200 rounded-lg p-3">
          <div class="flex items-start">
            <i class="fas fa-shield-alt text-blue-600 mt-0.5 mr-2"></i>
            <div class="text-sm text-blue-800">
              <p class="font-medium mb-1">Secure Storage</p>
              <p class="text-xs">
                All credentials are encrypted using project-specific keys and stored securely. 
                Credentials are isolated per project and cannot be accessed by other users.
              </p>
            </div>
          </div>
        </div>
        
        <!-- Connection Test Result -->
        {#if mcpConnectionTestResult}
          <div class="p-3 rounded-lg {mcpConnectionTestResult.success ? 'bg-green-50 border border-green-200' : 'bg-red-50 border border-red-200'}">
            <div class="flex items-center">
              <i class="fas {mcpConnectionTestResult.success ? 'fa-check-circle' : 'fa-times-circle'} text-{mcpConnectionTestResult.success ? 'green' : 'red'}-600 mr-2"></i>
              <div>
                <p class="font-medium text-{mcpConnectionTestResult.success ? 'green' : 'red'}-800 text-sm">
                  {mcpConnectionTestResult.success ? 'Connection Successful' : 'Connection Failed'}
                </p>
                {#if mcpConnectionTestResult.success}
                  <p class="text-xs text-green-700 mt-1">
                    Found {mcpConnectionTestResult.tools_count || 0} available tools
                  </p>
                {:else}
                  <p class="text-xs text-red-700 mt-1">
                    {mcpConnectionTestResult.error || 'Unknown error'}
                  </p>
                {/if}
              </div>
            </div>
          </div>
        {/if}
        
        <!-- Credential Actions -->
        <div class="flex space-x-2">
          <button
            type="button"
            on:click={saveMCPCredentials}
            disabled={savingMCPCredentials}
            class="flex-1 px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed text-sm font-medium"
          >
            {#if savingMCPCredentials}
              <i class="fas fa-spinner fa-spin mr-2"></i>
              Saving...
            {:else}
              <i class="fas fa-save mr-2"></i>
              Save Credentials
            {/if}
          </button>
          
          <button
            type="button"
            on:click={testMCPConnection}
            disabled={testingMCPConnection || savingMCPCredentials}
            class="flex-1 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed text-sm font-medium"
          >
            {#if testingMCPConnection}
              <i class="fas fa-spinner fa-spin mr-2"></i>
              Testing...
            {:else}
              <i class="fas fa-plug mr-2"></i>
              Test Connection
            {/if}
          </button>
        </div>
        
        <!-- Server Configuration (for SharePoint site URL, etc.) -->
        {#if nodeConfig.server_type === 'sharepoint'}
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-2">SharePoint Site URL</label>
            <input
              type="text"
              bind:value={nodeConfig.server_config.site_url}
              on:input={updateNodeData}
              class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:border-oxford-blue focus:ring-2 focus:ring-oxford-blue focus:ring-opacity-20"
              placeholder="https://contoso.sharepoint.com/sites/MySite"
            />
            <p class="text-xs text-gray-500 mt-1">Full URL of the SharePoint site</p>
          </div>
        {/if}
        
        <!-- Available Tools -->
        <div>
          <span class="block text-sm font-medium text-gray-700 mb-2" role="heading" aria-level="3">Available Tools</span>
          {#if loadingMCPTools}
            <div class="text-xs text-gray-500 italic">
              <i class="fas fa-spinner fa-spin mr-1"></i>
              Loading tools...
            </div>
          {:else if mcpAvailableTools.length > 0}
            <div class="max-h-48 overflow-y-auto border border-gray-200 rounded-lg p-2 space-y-2">
              {#each mcpAvailableTools as tool}
                <div class="bg-white border border-gray-200 rounded p-2">
                  <div class="flex items-center justify-between">
                    <div class="flex-1">
                      <p class="text-sm font-medium text-gray-800">{tool.name}</p>
                      <p class="text-xs text-gray-600 mt-1">{tool.description}</p>
                    </div>
                    <label class="flex items-center ml-2">
                      <input
                        type="checkbox"
                        checked={nodeConfig.selected_tools?.includes(tool.name) || false}
                        on:change={(e) => {
                          if (!nodeConfig.selected_tools) nodeConfig.selected_tools = [];
                          if (e.target.checked) {
                            if (!nodeConfig.selected_tools.includes(tool.name)) {
                              nodeConfig.selected_tools = [...nodeConfig.selected_tools, tool.name];
                            }
                          } else {
                            nodeConfig.selected_tools = nodeConfig.selected_tools.filter(t => t !== tool.name);
                          }
                          updateNodeData();
                        }}
                        class="w-4 h-4 text-purple-600 border-gray-300 rounded focus:ring-purple-600"
                      />
                    </label>
                  </div>
                </div>
              {/each}
            </div>
            <p class="text-xs text-gray-500 mt-2">
              Check the tools you want this node to expose (leave all unchecked to expose all tools)
            </p>
          {:else if mcpCredentialStatus?.is_validated}
            <div class="text-xs text-gray-500 italic">
              No tools available. Try testing the connection again.
            </div>
          {:else}
            <div class="text-xs text-gray-500 italic">
              Tools will be loaded after credentials are configured and connection is tested
            </div>
          {/if}
        </div>
        
        <!-- Selected Tools Summary -->
        {#if nodeConfig.selected_tools && nodeConfig.selected_tools.length > 0}
          <div>
            <span class="block text-sm font-medium text-gray-700 mb-2" role="heading" aria-level="3">Selected Tools ({nodeConfig.selected_tools.length})</span>
            <div class="flex flex-wrap gap-2">
              {#each nodeConfig.selected_tools as tool}
                <span class="inline-flex items-center px-2 py-1 rounded-full text-xs bg-purple-100 text-purple-800">
                  {tool}
                  <button
                    type="button"
                    aria-label="Remove {tool}"
                    on:click={() => {
                      nodeConfig.selected_tools = nodeConfig.selected_tools.filter(t => t !== tool);
                      updateNodeData();
                    }}
                    class="ml-1 text-purple-600 hover:text-purple-800"
                  >
                    <i class="fas fa-times" aria-hidden="true"></i>
                  </button>
                </span>
              {/each}
            </div>
          </div>
        {/if}
      </div>
    {/if}
    
  </div>
  
  <!-- Panel Footer -->
  <div class="p-4 border-t border-gray-200 bg-gray-50">
    <div class="flex justify-end space-x-2">
      <button
        class="px-4 py-2 text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors text-sm font-medium"
        on:click={closePanel}
      >
        Cancel
      </button>
      <button
        class="px-4 py-2 bg-oxford-blue text-white rounded-lg hover:bg-blue-700 transition-colors text-sm font-medium"
        on:click={saveNodeChanges}
      >
        <i class="fas fa-save mr-1"></i>
        Save Changes
      </button>
    </div>
  </div>
</div>

<style>
  .node-properties-panel {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', sans-serif;
  }
  
  :global(.focus\\:border-oxford-blue:focus) {
    border-color: #002147;
  }
  
  :global(.focus\\:ring-oxford-blue:focus) {
    --tw-ring-color: #002147;
  }
  
  :global(.text-oxford-blue) {
    color: #002147;
  }
  
  :global(.bg-oxford-blue) {
    background-color: #002147;
  }
</style>

