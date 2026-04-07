<!-- Clean Universal Project Interface - Template Independent -->
<script lang="ts">
  import { page } from '$app/stores';
  import { onMount } from 'svelte';
  import { get } from 'svelte/store';
  import { goto } from '$app/navigation';
  import { toasts } from '$lib/stores/toast';
  import { cleanUniversalApi } from '$lib/services/cleanUniversalApi';
  import ApiManagement from '$lib/components/project/ApiManagement.svelte';
  import AdminDeleteButton from '$lib/components/AdminDeleteButton.svelte';
  import authStore, { isAdmin } from '$lib/stores/auth';
  import { llmModelsService, type LLMModel, type BulkModelData } from '$lib/stores/llmModelsStore';
  import { frontendWorkflowStore } from '$lib/stores/workflowStore';
  import OllamaModelManager from '$lib/components/OllamaModelManager.svelte';
  
  // Get project ID from URL
  $: projectId = $page.params.id;
  
  // Track previous project ID to detect project switches (security: prevent cross-project data leakage)
  let previousProjectId: string | null = null;
  
  // SECURITY FIX: Clear ALL stale data and reload when projectId changes
  // This prevents data from one project appearing when viewing another project
  $: if (projectId && projectId !== previousProjectId) {
    console.log(`🔄 PROJECT SWITCH: Clearing ALL stale data (${previousProjectId} -> ${projectId})`);
    
    // 1. Stop any active polling first to prevent cross-project polling
    if (statusPollingInterval) {
      console.log('⏹️ PROJECT SWITCH: Stopping status polling');
      clearInterval(statusPollingInterval);
      statusPollingInterval = null;
    }
    
    // 2. Clear core project data
    uploadedDocuments = [];
    project = null;
    processingStatus = null;
    apiKeyStatus = { hasValidKeys: false, missingProviders: [], checking: true };
    preserveOriginalFolderStructure = false;
    documentsViewMode = 'list';
    hierarchicalPaths = [];
    folderBrowsePath = '';
    loadingHierarchicalPaths = false;
    hierarchicalPathsError = '';
    
    // 3. Clear search state (prevents search results from previous project)
    searchQuery = '';
    searchResults = [];
    
    // 4. Clear LLM configuration (reset to defaults)
    llmConfig = { provider: 'openai', model: 'gpt-5.3-chat-latest', enableSummary: true };
    bulkModelData = null;
    availableProviders = [];
    providerModels = [];
    
    // 5. Clear navigation state
    currentPage = 1;
    hasNavigation = false;
    navigationPages = [];
    projectCapabilities = {};
    
    // 6. Reset processing state
    processing = false;
    pollingAttempts = 0;
    statusRequestInFlight = false;
    
    // 7. Clear workflow store so stale workflow list from previous project is not retained
    frontendWorkflowStore.initialize();
    
    // 8. Reset loading states
    loading = true;
    modelsLoading = false;
    
    // Update tracking variable
    previousProjectId = projectId;
    
    // Reload project data for the new project
    loadProject();
    loadLLMModels(false);
  }
  
  // State variables
  let project: any = null;
  let loading = true;
  let uploadedDocuments: any[] = [];
  let uploading = false;
  
  // Processing state
  let processing = false;
  let processingStatus: any = null;
  let statusPollingInterval: ReturnType<typeof setInterval> | null = null;
  let statusRequestInFlight = false;

  // vector_count maps to processing_progress.completed on the backend:
  // the count of ProjectDocument rows with DocumentVectorStatus.status=COMPLETED.
  // This is not the raw Milvus chunk count.
  $: processedCount = Number(processingStatus?.vector_status?.vector_count) || 0;
  $: totalDocumentsCount = processingStatus?.vector_status?.total_documents ?? 0;
  $: rawProcessingStatus = processingStatus?.vector_status?.processing_status || processingStatus?.vector_status?.collection_status || 'not_created';
  $: isTerminalProcessingStatus = ['completed', 'failed', 'error'].includes(rawProcessingStatus);
  $: isCountComplete = totalDocumentsCount > 0 && processedCount >= totalDocumentsCount;
  $: serverIsProcessing = processingStatus?.vector_status?.is_processing === true;
  $: effectiveProcessingStatus = isTerminalProcessingStatus
    ? rawProcessingStatus
    : (serverIsProcessing ? 'processing' : rawProcessingStatus);
  
  // Navigation state (capability-based, not template-based)
  let currentPage = 1;
  let hasNavigation = false;
  let navigationPages: any[] = [];
  let sidebarCollapsed = false;

  // Capability-based UI state
  let projectCapabilities: any = {};
  
  // API Management modal state
  let showApiManagement = false;

  // Document AI summary modal (long/short from ProjectDocumentSummary)
  let summaryModalOpen = false;
  let summaryLoading = false;
  let summaryError = '';
  let summaryModalTitle = '';
  let summaryData: {
    long_summary: string;
    short_summary: string;
    has_summary: boolean;
    message: string;
    generated_at: string | null;
    updated_at: string | null;
    llm_provider: string;
    llm_model: string;
  } | null = null;
  
  // API Key status state
  let apiKeyStatus: {
    hasValidKeys: boolean;
    missingProviders: string[];
    checking: boolean;
  } = {
    hasValidKeys: false,
    missingProviders: [],
    checking: true
  };
  
  // LLM Configuration state for document processing
  let llmConfig = {
    provider: 'openai',
    model: 'gpt-5.3-chat-latest',
    enableSummary: true
  };
  let bulkModelData: BulkModelData | null = null;
  let modelsLoading = false;
  let availableProviders: string[] = [];
  let providerModels: LLMModel[] = [];
  
  // Folder structure preservation setting
  let preserveOriginalFolderStructure = false;
  let updatingFolderStructureSetting = false;

  // Document view mode: list (default grid) vs folder (hierarchical browser)
  let documentsViewMode: 'list' | 'folder' = 'list';
  let hierarchicalPaths: any[] = [];
  let folderBrowsePath = '';
  let loadingHierarchicalPaths = false;
  let hierarchicalPathsError = '';

  // Document multi-select state
  let selectedDocumentIds: Set<string> = new Set();
  let isSelectionMode = false;
  let bulkDeleting = false;

  function toggleDocumentSelection(docId: string) {
    if (selectedDocumentIds.has(docId)) {
      selectedDocumentIds.delete(docId);
    } else {
      selectedDocumentIds.add(docId);
    }
    selectedDocumentIds = new Set(selectedDocumentIds); // trigger reactivity
  }

  function selectAllDocuments() {
    selectedDocumentIds = new Set(uploadedDocuments.map((d: any) => d.document_id || d.id));
  }

  function deselectAllDocuments() {
    selectedDocumentIds = new Set();
  }

  function exitSelectionMode() {
    isSelectionMode = false;
    selectedDocumentIds = new Set();
  }

  async function bulkDeleteSelected() {
    if (selectedDocumentIds.size === 0) return;
    const count = selectedDocumentIds.size;
    if (!confirm(`Delete ${count} document(s)? This will also remove their vector data, summaries, and workflow references. This cannot be undone.`)) return;

    bulkDeleting = true;
    try {
      const result = await cleanUniversalApi.bulkDeleteDocuments(projectId, Array.from(selectedDocumentIds));
      toasts.success(`Deleted ${result.total_deleted} document(s)${result.workflows_cleaned ? ` (${result.workflows_cleaned} workflow(s) cleaned)` : ''}`);
      if (result.total_failed > 0) {
        toasts.warning(`${result.total_failed} document(s) failed to delete`);
      }
      exitSelectionMode();
      await Promise.all([loadDocuments(), loadHierarchicalPaths()]);
    } catch (error: any) {
      console.error('Bulk delete failed:', error);
      toasts.error(error.message || 'Bulk delete failed');
    } finally {
      bulkDeleting = false;
    }
  }

  const featureKeyToLabel: Record<string, string> = {
    document_management: 'Manage documents',
    upload_interface: 'Upload files',
    processing_status: 'Track processing',
    visual_workflow_designer: 'Workflow designer',
    agent_management: 'Agent management',
    real_time_execution: 'Live execution',
    workflow_history: 'Execution history',
    workflow_evaluation: 'Run evaluations',
    csv_upload: 'CSV datasets',
    metrics_comparison: 'Compare metrics',
    batch_testing: 'Batch testing',
  };

  function navSubLabel(navPage: any): string {
    if (navPage.description) return navPage.description;
    if (!navPage.features?.length) return '';
    const mapped = navPage.features
      .slice(0, 2)
      .map((k: string) => featureKeyToLabel[k])
      .filter(Boolean);
    return mapped.length > 0 ? mapped.join(' · ') : '';
  }

  console.log(`🎯 UNIVERSAL: Initializing universal project interface for project ${projectId}`);
  
  // Helper function to format processing status
  function formatProcessingStatus(status: string | undefined | null): string {
    const labels: Record<string, string> = {
      'not_created': 'Not Started',
      'pending':     'Pending',
      'processing':  'Processing',
      'completed':   'Completed',
      'failed':      'Failed',
      'error':       'Error',
      'unknown':     'Unknown',
    };
    if (!status) return 'Not Started';
    return labels[status] ?? (status.charAt(0).toUpperCase() + status.slice(1).replace(/_/g, ' '));
  }
  
  // Toggle sidebar function
  function toggleSidebar() {
    sidebarCollapsed = !sidebarCollapsed;
  }
  
  onMount(() => {
    // NOTE: loadProject() and loadLLMModels() are now called reactively when projectId changes
    // This ensures they run on both initial load AND when navigating between projects
    // See the reactive statement above: $: if (projectId && projectId !== previousProjectId)

    // Return cleanup function for onDestroy behavior
    return () => {
      if (statusPollingInterval) {
        console.log('⏹️ CLEANUP: Stopping status polling on component destroy');
        clearInterval(statusPollingInterval);
        statusPollingInterval = null;
      }
    };
  });

  async function loadLLMModels(forceRefresh = false) {
    try {
      modelsLoading = true;
      console.log('📋 DOCUMENTS: Loading LLM models for document processing configuration', { projectId, forceRefresh });
      
      // Force refresh if requested (e.g., after setting API keys)
      const data = await llmModelsService.loadBulkModels(projectId, forceRefresh);
      bulkModelData = data;
      
      // Debug: Log provider statuses
      console.log('📊 DOCUMENTS: Provider statuses:', data.provider_statuses);
      
      // Get available providers (those with API keys set, even if validation failed)
      // We allow providers with keys set but validation failed, as validation might fail due to network issues
      availableProviders = Object.keys(data.provider_statuses || {}).filter(provider =>
        data.provider_statuses[provider]?.has_api_key === true || provider === 'ollama'
      );
      
      // Debug: Log which providers have keys but are invalid
      const providersWithKeys = Object.keys(data.provider_statuses || {}).filter(provider => 
        data.provider_statuses[provider]?.has_api_key
      );
      const invalidProviders = providersWithKeys.filter(provider => 
        !data.provider_statuses[provider]?.api_key_valid
      );
      
      if (invalidProviders.length > 0) {
        console.warn('⚠️ DOCUMENTS: Providers with API keys but validation failed:', invalidProviders.map(p => ({
          provider: p,
          status: data.provider_statuses[p],
          message: data.provider_statuses[p]?.message
        })));
      }
      
      // Set default provider to first available, or OpenAI if available
      if (availableProviders.length > 0) {
        llmConfig.provider = availableProviders.includes('openai') ? 'openai' : availableProviders[0];
        updateProviderModels();
      } else {
        console.warn('⚠️ DOCUMENTS: No providers with API keys found. Provider statuses:', data.provider_statuses);
        
        // Log detailed status for debugging
        if (data.provider_statuses) {
          Object.keys(data.provider_statuses).forEach(provider => {
            const status = data.provider_statuses[provider];
            console.log(`  - ${provider}: has_api_key=${status?.has_api_key}, api_key_valid=${status?.api_key_valid}, message=${status?.message}`);
          });
        }
      }
      
      console.log('✅ DOCUMENTS: LLM models loaded', { 
        providers: availableProviders,
        selectedProvider: llmConfig.provider,
        totalProviders: Object.keys(data.provider_statuses || {}).length
      });
    } catch (error) {
      console.error('❌ DOCUMENTS: Failed to load LLM models:', error);
      // Continue with defaults
    } finally {
      modelsLoading = false;
    }
  }
  
  function updateProviderModels() {
    if (bulkModelData) {
      providerModels = bulkModelData.provider_models[llmConfig.provider] || [];
      // Auto-select first model if current model not available
      if (providerModels.length > 0 && !providerModels.find(m => m.id === llmConfig.model)) {
        llmConfig.model = providerModels[0].id;
      }
    }
  }
  
  $: if (llmConfig.provider && bulkModelData) {
    updateProviderModels();
  }
  
  async function loadProject() {
    try {
      loading = true;
      console.log(`📄 UNIVERSAL: Loading project ${projectId}`);
      
      // Load project using universal API (works for ALL projects regardless of template)
      project = await cleanUniversalApi.getProject(projectId);
      
      // Extract capabilities from cloned project data (not template files)
      projectCapabilities = project.processing_capabilities || {};
      hasNavigation = project.has_navigation || false;
      navigationPages = (project.navigation_pages || []).sort((a: any, b: any) => (a.page_number ?? 99) - (b.page_number ?? 99));
      
      // Load folder structure preservation setting
      preserveOriginalFolderStructure = project.preserve_original_folder_structure || false;
      
      // Set up navigation based on cloned project data
      if (hasNavigation && project.total_pages > 1) {
        currentPage = 1;
      }
      
      console.log('✅ UNIVERSAL: Project loaded successfully', {
        name: project.name,
        template_type: project.template_type,
        has_navigation: hasNavigation,
        total_pages: project.total_pages,
        preserve_original_folder_structure: preserveOriginalFolderStructure,
        capabilities: Object.keys(projectCapabilities)
      });
      
      // Load documents, status, folder hierarchy, and check API keys
      await Promise.all([
        loadDocuments(),
        loadProcessingStatus(),
        checkApiKeyStatus(),
        loadHierarchicalPaths()
      ]);
      
    } catch (error) {
      console.error('❌ UNIVERSAL: Failed to load project:', error);
      toasts.error('Failed to load project');
      goto('/features/intellidoc');
    } finally {
      loading = false;
    }
  }
  
  /**
   * Check API key status for the project
   * This proactively warns users if API keys are missing
   */
  async function checkApiKeyStatus() {
    try {
      apiKeyStatus.checking = true;
      console.log(`🔑 UNIVERSAL: Checking API key status for project ${projectId}`);

      // Check if Ollama has downloaded models (local AI = no cloud keys needed)
      try {
        const ollamaResp = await fetch('/api/ollama/models/');
        if (ollamaResp.ok) {
          const ollamaData = await ollamaResp.json();
          if ((ollamaData.models?.length || 0) > 0) {
            console.log('✅ UNIVERSAL: Ollama available with local models — no cloud keys required');
            apiKeyStatus = { hasValidKeys: true, missingProviders: [], checking: false };
            return;
          }
        }
      } catch { /* Ollama not available, check cloud keys */ }

      // Get all API keys for this project
      const apiKeys = await cleanUniversalApi.getProjectApiKeys(projectId);

      const activeKeys = apiKeys.filter((key: any) => key.is_active && key.is_validated);
      const activeProviders = activeKeys.map((key: any) => key.provider_type);

      // Only warn about missing keys if NO provider is available at all
      const cloudProviders = ['openai', 'anthropic', 'google'];
      const missingProviders = cloudProviders.filter(
        provider => !activeProviders.includes(provider)
      );

      apiKeyStatus = {
        hasValidKeys: activeProviders.length > 0,
        missingProviders: activeProviders.length > 0 ? [] : missingProviders,
        checking: false
      };

    } catch (error) {
      console.error('❌ UNIVERSAL: Failed to check API key status:', error);
      apiKeyStatus.checking = false;
      apiKeyStatus.hasValidKeys = false;
      apiKeyStatus.missingProviders = ['openai', 'anthropic', 'google'];
    }
  }
  
  /**
   * Update the folder structure preservation setting
   */
  async function updateFolderStructureSetting(newValue: boolean) {
    try {
      updatingFolderStructureSetting = true;
      console.log(`📁 UNIVERSAL: Updating folder structure setting to ${newValue} for project ${projectId}`);
      
      // Get auth token from the authStore (not from localStorage directly)
      const auth = get(authStore);
      const token = auth?.token || '';
      
      if (!token) {
        throw new Error('Not authenticated. Please log in again.');
      }
      
      const response = await fetch(`/api/projects/${projectId}/folder-structure-setting/`, {
        method: 'PATCH',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({
          preserve_original_folder_structure: newValue
        })
      });
      
      if (!response.ok) {
        throw new Error(`Failed to update setting: ${response.statusText}`);
      }
      
      const result = await response.json();
      preserveOriginalFolderStructure = result.preserve_original_folder_structure;
      
      toasts.success(result.message || 'Folder structure setting updated successfully');
      console.log('✅ UNIVERSAL: Folder structure setting updated:', result);
      
    } catch (error: any) {
      console.error('❌ UNIVERSAL: Failed to update folder structure setting:', error);
      toasts.error(`Failed to update setting: ${error.message}`);
      // Revert the toggle on error
      preserveOriginalFolderStructure = !newValue;
    } finally {
      updatingFolderStructureSetting = false;
    }
  }
  
  async function loadDocuments() {
    try {
      console.log(`📄 UNIVERSAL: Loading documents for project ${projectId}`);
      const documents = await cleanUniversalApi.getDocuments(projectId);
      uploadedDocuments = documents;
      
      console.log(`✅ UNIVERSAL: Loaded ${documents.length} documents`);
    } catch (error) {
      console.error('❌ UNIVERSAL: Failed to load documents:', error);
      toasts.error('Failed to load documents');
    }
  }

  async function loadHierarchicalPaths() {
    try {
      loadingHierarchicalPaths = true;
      hierarchicalPathsError = '';
      const data = await cleanUniversalApi.getUploadedHierarchicalPaths(projectId);
      hierarchicalPaths = data.hierarchical_paths || [];
    } catch (error: any) {
      console.error('❌ UNIVERSAL: Failed to load hierarchical paths:', error);
      hierarchicalPathsError = error.message || 'Failed to load folder structure';
    } finally {
      loadingHierarchicalPaths = false;
    }
  }
  
  async function loadProcessingStatus() {
    if (statusRequestInFlight) {
      return;
    }

    const requestProjectId = projectId;

    try {
      statusRequestInFlight = true;
      console.log(`📊 UNIVERSAL: Loading processing status for project ${projectId}`);
      const nextStatus = await cleanUniversalApi.getProcessingStatus(projectId);

      // Ignore stale responses from previous project context
      if (requestProjectId !== projectId) {
        console.log('⏭️ UNIVERSAL: Ignoring stale processing status response');
        return;
      }

      processingStatus = nextStatus;
      console.log('✅ UNIVERSAL: Processing status loaded', processingStatus?.vector_status);
      
      // Auto-start polling if processing is already in progress (e.g., page refresh during processing)
      const isProcessing = processingStatus?.vector_status?.is_processing;
      if (isProcessing && !statusPollingInterval) {
        console.log('🔄 UNIVERSAL: Processing already in progress, starting status polling');
        startStatusPolling();
      }
    } catch (error) {
      console.error('❌ UNIVERSAL: Failed to load processing status:', error);
    } finally {
      statusRequestInFlight = false;
    }
  }
  
  // Polling helpers for background processing
  let pollingAttempts = 0;
  const MAX_POLLING_ATTEMPTS = 200; // ~10 minutes max polling
  
  function startStatusPolling() {
    if (statusPollingInterval) return; // Already polling
    pollingAttempts = 0;
    console.log('🔄 POLLING: Starting status polling every 3 seconds');
    statusPollingInterval = setInterval(async () => {
      pollingAttempts++;
      await loadProcessingStatus();

      // Derive directly from processingStatus to avoid stale $: reactive reads after async update
      const raw = processingStatus?.vector_status?.processing_status
                || processingStatus?.vector_status?.collection_status
                || 'not_created';
      const stillProcessing = processingStatus?.vector_status?.is_processing === true;
      const vectorCount = processingStatus?.vector_status?.vector_count || 0;
      const isTerminalRaw = ['completed', 'failed', 'error'].includes(raw);

      console.log(`🔄 POLLING: Attempt ${pollingAttempts} - raw=${raw}, serverIsProcessing=${stillProcessing}, vectors=${vectorCount}`);

      // Continue polling while:
      //  - server says still processing, OR
      //  - raw status is not terminal AND we are in startup grace period or an active state
      const shouldContinuePolling = stillProcessing ||
        (!isTerminalRaw && (
          ['processing', 'pending', 'not_created'].includes(raw) ||
          pollingAttempts <= 3
        ));

      if (!shouldContinuePolling || pollingAttempts >= MAX_POLLING_ATTEMPTS) {
        stopStatusPolling();
        loadHierarchicalPaths();
        if (raw === 'completed') {
          toasts.success('Document processing completed!');
        } else if (raw === 'failed' || raw === 'error') {
          toasts.error('Document processing failed. Check logs for details.');
        } else if (pollingAttempts >= MAX_POLLING_ATTEMPTS) {
          toasts.info('Processing is taking longer than expected. Check status manually.');
        }
      }
    }, 3000);
  }
  
  function stopStatusPolling() {
    if (statusPollingInterval) {
      console.log('⏹️ POLLING: Stopping status polling');
      clearInterval(statusPollingInterval);
      statusPollingInterval = null;
    }
  }
  
  // Electron native file picker handlers
  async function handleSelectFiles() {
    if (!window.electronAPI) {
      toasts.error('File selection requires the desktop app');
      return;
    }
    try {
      const filePaths = await window.electronAPI.selectFiles({
        filters: [{ name: 'Documents', extensions: ['pdf', 'doc', 'docx', 'txt', 'md', 'rtf'] }]
      });
      if (filePaths && filePaths.length > 0) {
        uploading = true;
        try {
          const result = await cleanUniversalApi.registerLocalFiles(projectId, filePaths);
          const count = result.registered_documents?.length || filePaths.length;
          toasts.success(`${count} file(s) registered successfully`);
          await Promise.all([loadDocuments(), loadHierarchicalPaths()]);
        } catch (error: any) {
          toasts.error(`Failed to register files: ${error.message || 'Unknown error'}`);
        } finally {
          uploading = false;
        }
      }
    } catch (error: any) {
      toasts.error(`File dialog error: ${error.message || 'Unknown error'}`);
    }
  }

  async function handleSelectDirectory() {
    if (!window.electronAPI) {
      toasts.error('Folder selection requires the desktop app');
      return;
    }
    try {
      const dirPath = await window.electronAPI.selectDirectory();
      if (dirPath) {
        uploading = true;
        try {
          const result = await cleanUniversalApi.registerLocalDirectory(projectId, dirPath);
          const count = result.registered_documents?.length || 0;
          toasts.success(`${count} file(s) registered from folder`);
          await Promise.all([loadDocuments(), loadHierarchicalPaths()]);
        } catch (error: any) {
          toasts.error(`Failed to register folder: ${error.message || 'Unknown error'}`);
        } finally {
          uploading = false;
        }
      }
    } catch (error: any) {
      toasts.error(`Folder dialog error: ${error.message || 'Unknown error'}`);
    }
  }
  
  async function deleteDocument(documentId: string, documentName: string) {
    try {
      console.log(`🗑️ UNIVERSAL: Deleting document ${documentId} from project ${projectId}`);
      await cleanUniversalApi.deleteDocument(projectId, documentId);
      
      console.log('✅ UNIVERSAL: Document deleted successfully');
      toasts.success(`Deleted "${documentName}" successfully`);
      
      // Reload documents and folder hierarchy
      await Promise.all([loadDocuments(), loadHierarchicalPaths()]);
      
    } catch (error) {
      console.error('❌ UNIVERSAL: Document deletion failed:', error);
      toasts.error(`Failed to delete document: ${error.message}`);
    }
  }
  
  function getDocAuthHeaders(): Record<string, string> {
    try {
      const raw = localStorage.getItem('auth');
      if (raw) {
        const parsed = JSON.parse(raw);
        if (parsed?.token) return { 'Authorization': `Bearer ${parsed.token}` };
      }
    } catch (_e) { /* ignore */ }
    return {};
  }

  function closeSummaryModal() {
    summaryModalOpen = false;
    summaryLoading = false;
    summaryError = '';
    summaryData = null;
    summaryModalTitle = '';
  }

  async function openDocumentSummary(doc: any) {
    const did = doc.document_id || doc.id;
    if (!did || !projectId) return;
    summaryModalTitle = doc.original_filename || doc.filename || 'Document';
    summaryModalOpen = true;
    summaryLoading = true;
    summaryError = '';
    summaryData = null;
    try {
      summaryData = await cleanUniversalApi.getDocumentSummary(projectId, String(did));
    } catch (e: any) {
      summaryError = e?.message || 'Failed to load summary';
      toasts.error(summaryError);
    } finally {
      summaryLoading = false;
    }
  }

  function handleSummaryModalKeydown(e: KeyboardEvent) {
    if (!summaryModalOpen) return;
    if (e.key === 'Escape') {
      e.preventDefault();
      closeSummaryModal();
    }
  }

  async function viewDocument(doc: any) {
    const downloadUrl = doc.download_url || `/api/projects/${projectId}/documents/${doc.document_id || doc.id}/download/`;
    const previewableExtensions = ['.pdf', '.png', '.jpg', '.jpeg', '.gif', '.webp', '.txt'];
    const extension = (doc.file_extension || '').toLowerCase();

    if (!previewableExtensions.includes(extension)) {
      downloadDocument(doc);
      return;
    }

    try {
      const resp = await fetch(downloadUrl, { headers: getDocAuthHeaders() });
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const blob = await resp.blob();
      const blobUrl = URL.createObjectURL(blob);
      window.open(blobUrl, '_blank');
      setTimeout(() => URL.revokeObjectURL(blobUrl), 60_000);
      console.log(`👁️ UNIVERSAL: Opening document preview: ${doc.original_filename || doc.filename}`);
    } catch (err: any) {
      console.error('❌ UNIVERSAL: Failed to preview document:', err);
      toasts.error(`Failed to preview document: ${err.message}`);
    }
  }

  async function downloadDocument(doc: any) {
    const downloadUrl = doc.download_url || `/api/projects/${projectId}/documents/${doc.document_id || doc.id}/download/`;
    const filename = doc.original_filename || doc.filename || 'document';

    try {
      const resp = await fetch(downloadUrl, { headers: getDocAuthHeaders() });
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const blob = await resp.blob();
      const blobUrl = URL.createObjectURL(blob);

      const link = document.createElement('a');
      link.href = blobUrl;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      setTimeout(() => URL.revokeObjectURL(blobUrl), 10_000);

      console.log(`📥 UNIVERSAL: Downloading document: ${filename}`);
      toasts.success(`Downloading "${filename}"`);
    } catch (err: any) {
      console.error('❌ UNIVERSAL: Failed to download document:', err);
      toasts.error(`Failed to download document: ${err.message}`);
    }
  }
  
  async function processDocuments() {
    if (processing) return;
    
    // Validate LLM configuration
    if (!llmConfig.provider || !llmConfig.model) {
      toasts.error('Please select an LLM provider and model');
      return;
    }
    
    try {
      processing = true;
      console.log(`🚀 UNIVERSAL: Starting document processing for project ${projectId}`, {
        llm_provider: llmConfig.provider,
        llm_model: llmConfig.model,
        enable_summary: llmConfig.enableSummary
      });
      
      const result = await cleanUniversalApi.processDocuments(projectId, {
        llm_provider: llmConfig.provider,
        llm_model: llmConfig.model,
        enable_summary: llmConfig.enableSummary
      });
      
      console.log('✅ UNIVERSAL: Document processing started', result);
      
      // Handle response status
      if (result.status === 'already_running') {
        toasts.info('Processing is already running for this project');
        await loadProcessingStatus();
        startStatusPolling();
      } else if (result.status === 'all_already_processed') {
        toasts.info('All documents are already processed. Upload new files to process them.');
        await loadProcessingStatus(); // refresh status display with current counts
      } else {
        toasts.success('Document processing started in background');
        await loadProcessingStatus();
        startStatusPolling();
      }

    } catch (error: any) {
      console.error('❌ UNIVERSAL: Document processing failed:', error);
      toasts.error(`Processing failed: ${error.message}`);
    } finally {
      processing = false;
    }
  }
  
  // Search functionality
  let searchQuery = '';
  let searchResults: any[] = [];
  let searching = false;
  
  async function searchDocuments() {
    if (!searchQuery.trim() || searching) return;
    
    try {
      searching = true;
      console.log(`🔍 UNIVERSAL: Searching documents in project ${projectId}: "${searchQuery}"`);
      
      const results = await cleanUniversalApi.searchDocuments(projectId, searchQuery.trim());
      searchResults = results.results || [];
      
      console.log(`✅ UNIVERSAL: Search completed, ${searchResults.length} results found`);
      
      if (searchResults.length === 0) {
        toasts.info('No results found for your search');
      }
      
    } catch (error) {
      console.error('❌ UNIVERSAL: Search failed:', error);
      toasts.error(`Search failed: ${error.message}`);
      searchResults = [];
    } finally {
      searching = false;
    }
  }
  
  // Navigation functions (capability-based)
  function goToNextPage() {
    if (hasNavigation && currentPage < project.total_pages) {
      currentPage++;
    }
  }

  function goToPreviousPage() {
    if (hasNavigation && currentPage > 1) {
      currentPage--;
    }
  }

  function goToPage(page: number) {
    if (hasNavigation && page >= 1 && page <= navigationPages.length) {
      currentPage = page;
    }
  }
</script>

<svelte:head>
  <title>{project?.name || 'Project'} - AI Catalogue</title>
</svelte:head>

{#if loading}
  <div class="flex items-center justify-center min-h-96">
    <div class="text-center">
      <div class="animate-spin rounded-full h-12 w-12 border-b-2 border-oxford-blue mx-auto mb-4"></div>
      <p class="text-oxford-blue">Loading project...</p>
    </div>
  </div>
{:else if project}
  <div class="min-h-screen bg-gray-50 flex w-full">
    <!-- Left Sidebar Navigation (if supported by project capabilities) -->
    {#if hasNavigation && navigationPages.length > 0}
      <div class="{sidebarCollapsed ? 'w-16' : 'w-64'} bg-white border-r border-gray-200 transition-all duration-300 flex flex-col shadow-lg">
        <!-- Sidebar Header -->
        <div class="p-4 border-b border-gray-200">
          <div class="flex items-center {sidebarCollapsed ? 'justify-center' : 'justify-between'}">
            {#if !sidebarCollapsed}
              <h3 class="text-lg font-bold text-gray-900">Navigation</h3>
            {/if}
            <button
              class="p-2 rounded-lg hover:bg-gray-100 transition-colors"
              on:click={toggleSidebar}
              title={sidebarCollapsed ? 'Expand Sidebar' : 'Collapse Sidebar'}
            >
              <i class="fas {sidebarCollapsed ? 'fa-chevron-right' : 'fa-chevron-left'} text-gray-600"></i>
            </button>
          </div>
        </div>
        
        <!-- Navigation Items -->
        <nav class="flex-1 p-4" aria-label="Project pages">
          <div class="space-y-2">
            {#each navigationPages as navPage, index}
              <button
                class="w-full flex items-center {sidebarCollapsed ? 'justify-center p-3' : 'p-4'} rounded-xl font-medium transition-all duration-200 {currentPage === index + 1 
                  ? 'bg-oxford-blue shadow-lg' 
                  : 'text-gray-600 hover:text-oxford-blue hover:bg-blue-50 hover:shadow-md'}"
                on:click={() => goToPage(index + 1)}
                title={sidebarCollapsed ? navPage.name : ''}
                aria-current={currentPage === index + 1 ? 'page' : undefined}
              >
                <div class="flex-shrink-0">
                  <i class="fas {navPage.icon} text-lg {currentPage === index + 1 ? '!text-white' : 'text-gray-600'}"></i>
                </div>
                {#if !sidebarCollapsed}
                  <div class="ml-4 text-left flex-1">
                    <div class="font-semibold text-sm {currentPage === index + 1 ? '!text-white' : 'text-gray-600'}">{navPage.name}</div>
                    {#if navPage.features && navPage.features.length > 0}
                      <div class="text-xs opacity-75 mt-1 {currentPage === index + 1 ? '!text-white' : 'text-gray-500'}">
                        {navPage.features.slice(0, 2).join(' · ')}
                      </div>
                    {/if}
                  </div>
                  {#if currentPage === index + 1}
                    <div class="flex-shrink-0">
                      <i class="fas fa-check text-sm bg-white bg-opacity-20 rounded-full p-1 !text-white"></i>
                    </div>
                  {/if}
                {/if}
              </button>
            {/each}
          </div>
        </nav>
      </div>
    {/if}
    
    <!-- Main Content Area -->
    <div class="flex-1 flex flex-col">
      <!-- API Key Warning Banner -->
      {#if !apiKeyStatus.checking && !apiKeyStatus.hasValidKeys && apiKeyStatus.missingProviders.length > 0}
        <div class="bg-yellow-50 border-l-4 border-yellow-400 p-4 sticky top-0 z-20 shadow-md">
          <div class="flex items-start">
            <div class="flex-shrink-0">
              <i class="fas fa-exclamation-triangle text-yellow-600 text-xl"></i>
            </div>
            <div class="ml-3 flex-1">
              <h3 class="text-sm font-medium text-yellow-800">
                API Keys Required for Agent Workflows
              </h3>
              <div class="mt-2 text-sm text-yellow-700">
                <p>
                  This project is missing API keys for: <strong>{apiKeyStatus.missingProviders.map(p => p.charAt(0).toUpperCase() + p.slice(1)).join(', ')}</strong>.
                  Agent workflows will fail without valid API keys configured.
                </p>
                <p class="mt-2">
                  <button
                    class="font-medium text-yellow-800 underline hover:text-yellow-900"
                    on:click={() => showApiManagement = true}
                  >
                    Configure API keys now →
                  </button>
                </p>
              </div>
            </div>
            <div class="ml-4 flex-shrink-0">
              <button
                class="text-yellow-600 hover:text-yellow-800"
                on:click={() => apiKeyStatus.hasValidKeys = true}
                title="Dismiss warning"
              >
                <i class="fas fa-times"></i>
              </button>
            </div>
          </div>
        </div>
      {/if}
      
      <!-- Project Header -->
        <div class="bg-white border-b border-gray-200 sticky top-0 z-10">
          <div class="w-full px-6">
            <div class="flex items-center justify-between py-6">
              <div class="flex items-center space-x-4">
                <div class="w-12 h-12 bg-oxford-blue text-white rounded-xl flex items-center justify-center shadow-lg">
                  <i class="fas {project.icon_class} text-lg"></i>
                </div>
                <div>
                  <h1 class="text-3xl font-bold text-gray-900">{project.name}</h1>
                  <p class="text-lg text-gray-600">{project.description}</p>
                  <div class="flex items-center space-x-6 mt-2 text-sm text-gray-500">
                    <span class="flex items-center">
                      <i class="fas fa-layer-group mr-2"></i>
                      Template: {project.template_name}
                    </span>
                    <span class="flex items-center">
                      <i class="fas fa-calendar mr-2"></i>
                      Created: {new Date(project.created_at).toLocaleDateString()}
                    </span>
                    {#if uploadedDocuments.length > 0}
                      <span class="flex items-center">
                        <i class="fas fa-files mr-2"></i>
                        {uploadedDocuments.length} documents
                      </span>
                    {/if}
                  </div>
                </div>
              </div>

              <div class="flex items-center space-x-4">
                <button
                  class="inline-flex items-center px-4 py-2 bg-white border-2 border-oxford-blue text-oxford-blue rounded-lg hover:bg-oxford-blue hover:text-white transition-all duration-200 shadow-lg hover:shadow-xl transform hover:-translate-y-0.5"
                  on:click={() => showApiManagement = true}
                  title="Manage project-specific API keys"
                >
                  <i class="fas fa-key mr-2"></i>
                  API Management
                </button>
                {#if processingStatus}
                  <details class="relative">
                    <summary class="cursor-pointer inline-flex items-center px-3 py-2 rounded-lg text-sm font-medium bg-gray-50 text-gray-700 border border-gray-200 hover:bg-gray-100 transition-colors">
                      <i class="fas fa-tasks mr-2 text-oxford-blue"></i>
                      {formatProcessingStatus(effectiveProcessingStatus)}
                      {#if totalDocumentsCount > 0}
                        <span class="ml-2 text-xs text-gray-400">{processedCount}/{totalDocumentsCount}</span>
                      {/if}
                    </summary>
                    <div class="absolute right-0 top-full mt-2 bg-white border border-gray-200 rounded-lg p-3 min-w-[220px] shadow-lg z-20">
                      <div class="flex items-center justify-between text-sm mb-2">
                        <span class="font-medium text-gray-700">Processing Status:</span>
                        <span class="text-oxford-blue font-semibold">
                          {formatProcessingStatus(effectiveProcessingStatus)}
                        </span>
                      </div>
                      {#if totalDocumentsCount > 0}
                        <div class="w-full bg-gray-200 rounded-full h-2">
                          <div
                            class="bg-oxford-blue h-2 rounded-full transition-all duration-300"
                            style="width: {Math.min(100, (processedCount / totalDocumentsCount) * 100)}%"
                          ></div>
                        </div>
                        <div class="text-xs text-gray-500 mt-1">
                          {processedCount}/{totalDocumentsCount} vectorized
                        </div>
                        {@const summariesCount = processingStatus?.vector_status?.summaries_generated ?? 0}
                        {#if summariesCount > 0 || effectiveProcessingStatus === 'processing'}
                          <div class="text-xs text-gray-500 mt-1">
                            {summariesCount}/{totalDocumentsCount} summaries
                          </div>
                        {/if}
                        {#if processingStatus.status_timestamp}
                          <div class="text-[11px] text-gray-400 mt-1">
                            Updated at {new Date(processingStatus.status_timestamp).toLocaleTimeString()}
                          </div>
                        {/if}
                      {/if}
                    </div>
                  </details>
                {/if}
              </div>
            </div>
          </div>
        </div>
    
    <!-- Page Content (Capability-Based) - Full Width Layout -->
    <div class="flex-1 w-full px-6 py-8">
      {#if !hasNavigation || currentPage === 1}
        <!-- Page 1: Document Management (Enhanced Full Width Layout) -->
        <div class="grid grid-cols-1 xl:grid-cols-12 gap-8">
          <!-- Left Section: Upload & Documents (8 columns) -->
          <div class="xl:col-span-8 space-y-6">
            <!-- Document Selection (Electron Native) -->
            <div class="bg-white rounded-2xl shadow-lg border border-gray-200 overflow-hidden">
              <div class="bg-gray-50 border-b border-gray-200 px-6 py-4">
                <h3 class="text-lg font-bold text-gray-900 flex items-center">
                  <i class="fas fa-folder-open mr-3 text-oxford-blue"></i>
                  Select Documents
                </h3>
                <p class="text-gray-500 text-sm mt-1">Choose files or folders from your local system</p>
              </div>

              <div class="p-6">
                {#if uploading}
                  <div class="flex items-center justify-center py-8">
                    <div class="animate-spin rounded-full h-8 w-8 border-b-2 border-oxford-blue mr-3"></div>
                    <span class="text-gray-600">Registering documents...</span>
                  </div>
                {:else}
                  <div class="flex flex-col sm:flex-row gap-4">
                    <button
                      on:click={handleSelectFiles}
                      class="flex-1 flex items-center justify-center gap-3 px-6 py-4 bg-blue-600 text-white rounded-xl hover:bg-blue-700 transition-all duration-200 shadow-md hover:shadow-lg"
                    >
                      <i class="fas fa-file-alt text-lg"></i>
                      <div class="text-left">
                        <div class="font-semibold">Select Files</div>
                        <div class="text-xs text-blue-100">PDF, DOC, TXT, MD, RTF</div>
                      </div>
                    </button>

                    <button
                      on:click={handleSelectDirectory}
                      class="flex-1 flex items-center justify-center gap-3 px-6 py-4 bg-white text-gray-800 border-2 border-gray-300 rounded-xl hover:bg-gray-50 hover:border-blue-400 transition-all duration-200 shadow-md hover:shadow-lg"
                    >
                      <i class="fas fa-folder text-lg text-blue-600"></i>
                      <div class="text-left">
                        <div class="font-semibold">Select Folder</div>
                        <div class="text-xs text-gray-500">Include all subfolders</div>
                      </div>
                    </button>
                  </div>
                {/if}
              </div>
            </div>
            
            <!-- Documents List / Folder Browser -->
            <div class="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
              <div class="px-6 py-4 bg-gray-50 border-b border-gray-200">
                <div class="flex items-center justify-between">
                  <h2 class="text-xl font-bold text-gray-900 flex items-center">
                    <i class="fas fa-file-alt mr-3 text-oxford-blue"></i>
                    Documents
                    <span class="ml-2 bg-oxford-blue text-white text-sm px-2 py-1 rounded-full">{uploadedDocuments.length}</span>
                  </h2>
                  <div class="flex items-center gap-3">
                    {#if uploadedDocuments.length > 0}
                      <span class="text-sm text-gray-500">
                        Total: {uploadedDocuments.reduce((total, doc) => total + (doc.file_size || 0), 0) > 1024 * 1024
                          ? Math.round(uploadedDocuments.reduce((total, doc) => total + (doc.file_size || 0), 0) / (1024 * 1024)) + ' MB'
                          : Math.round(uploadedDocuments.reduce((total, doc) => total + (doc.file_size || 0), 0) / 1024) + ' KB'}
                      </span>
                    {/if}
                    <!-- View mode segmented control -->
                    <div class="inline-flex rounded-lg border border-gray-300 bg-white overflow-hidden text-sm">
                      <button
                        class="px-3 py-1.5 flex items-center gap-1.5 transition-colors {documentsViewMode === 'list' ? 'bg-oxford-blue text-white' : 'text-gray-600 hover:bg-gray-100'}"
                        on:click={() => documentsViewMode = 'list'}
                      >
                        <i class="fas fa-list text-xs"></i> List
                      </button>
                      <button
                        class="px-3 py-1.5 flex items-center gap-1.5 transition-colors border-l border-gray-300 {documentsViewMode === 'folder' ? 'bg-oxford-blue text-white' : 'text-gray-600 hover:bg-gray-100'}"
                        on:click={() => { documentsViewMode = 'folder'; folderBrowsePath = ''; }}
                      >
                        <i class="fas fa-folder-tree text-xs"></i> Folders
                      </button>
                    </div>
                  </div>
                </div>
              </div>
              
              <div class="p-6">
                <!-- Bulk action toolbar -->
                {#if uploadedDocuments.length > 0 && documentsViewMode === 'list'}
                  <div class="flex items-center justify-between mb-4">
                    {#if isSelectionMode}
                      <div class="flex items-center space-x-3">
                        <button
                          class="text-sm px-3 py-1.5 rounded-lg border border-gray-300 hover:bg-gray-50 transition-colors"
                          on:click={() => selectedDocumentIds.size === uploadedDocuments.length ? deselectAllDocuments() : selectAllDocuments()}
                        >
                          {selectedDocumentIds.size === uploadedDocuments.length ? 'Deselect All' : 'Select All'}
                        </button>
                        <span class="text-sm text-gray-600">
                          {selectedDocumentIds.size} of {uploadedDocuments.length} selected
                        </span>
                      </div>
                      <div class="flex items-center space-x-2">
                        {#if selectedDocumentIds.size > 0}
                          <button
                            class="text-sm px-3 py-1.5 bg-red-600 text-white rounded-lg hover:bg-red-700 transition-colors disabled:opacity-50"
                            disabled={bulkDeleting}
                            on:click={bulkDeleteSelected}
                          >
                            {#if bulkDeleting}
                              <i class="fas fa-spinner fa-spin mr-1"></i> Deleting...
                            {:else}
                              <i class="fas fa-trash mr-1"></i> Delete {selectedDocumentIds.size} Selected
                            {/if}
                          </button>
                        {/if}
                        <button
                          class="text-sm px-3 py-1.5 rounded-lg border border-gray-300 hover:bg-gray-50 transition-colors"
                          on:click={exitSelectionMode}
                        >
                          Cancel
                        </button>
                      </div>
                    {:else}
                      <div></div>
                      <button
                        class="text-sm px-3 py-1.5 rounded-lg border border-gray-300 hover:bg-gray-50 transition-colors text-gray-600"
                        on:click={() => isSelectionMode = true}
                      >
                        <i class="fas fa-check-square mr-1"></i> Select
                      </button>
                    {/if}
                  </div>
                {/if}

                {#if documentsViewMode === 'list'}
                  <!-- LIST VIEW (original grid) -->
                  {#if uploadedDocuments.length === 0}
                    <div class="text-center py-12">
                      <i class="fas fa-folder-open text-5xl text-gray-300 mb-4"></i>
                      <h3 class="text-lg font-medium text-gray-700 mb-2">No documents uploaded yet</h3>
                      <p class="text-gray-500">Upload documents to get started with AI analysis</p>
                    </div>
                  {:else}
                    <div class="grid grid-cols-1 lg:grid-cols-2 gap-4">
                      {#each uploadedDocuments as doc}
                        <div
                          class="flex items-start p-4 border rounded-lg hover:shadow-md transition-all duration-200 group cursor-pointer {isSelectionMode && selectedDocumentIds.has(doc.document_id || doc.id) ? 'border-blue-500 bg-blue-50' : 'border-gray-200 hover:border-oxford-blue'}"
                          role="button"
                          tabindex="0"
                          on:click={() => {
                            if (isSelectionMode) {
                              toggleDocumentSelection(doc.document_id || doc.id);
                            } else {
                              openDocumentSummary(doc);
                            }
                          }}
                          on:keydown={(e) => {
                            if (e.key === 'Enter' || e.key === ' ') {
                              e.preventDefault();
                              if (isSelectionMode) {
                                toggleDocumentSelection(doc.document_id || doc.id);
                              } else {
                                openDocumentSummary(doc);
                              }
                            }
                          }}
                        >
                          {#if isSelectionMode}
                            <div class="flex-shrink-0 w-6 h-6 mr-3 mt-1" on:click|stopPropagation={() => toggleDocumentSelection(doc.document_id || doc.id)}>
                              <input
                                type="checkbox"
                                checked={selectedDocumentIds.has(doc.document_id || doc.id)}
                                class="w-5 h-5 rounded border-gray-300 text-oxford-blue focus:ring-oxford-blue cursor-pointer"
                                on:change={() => toggleDocumentSelection(doc.document_id || doc.id)}
                              />
                            </div>
                          {/if}
                          <div class="flex-shrink-0 w-10 h-10 bg-gradient-to-br from-oxford-blue to-blue-600 text-white rounded-lg flex items-center justify-center mr-4">
                            <i class="fas fa-file text-sm"></i>
                          </div>
                          <div class="flex-1 min-w-0">
                            <p class="font-medium text-gray-900 truncate">{doc.original_filename || doc.filename}</p>
                            <div class="flex items-center text-sm text-gray-500 mt-1 space-x-4">
                              <span class="flex items-center">
                                <i class="fas fa-weight-hanging mr-1"></i>
                                {doc.file_size_formatted || 'Unknown size'}
                              </span>
                              <span class="flex items-center">
                                <i class="fas fa-circle mr-1 {doc.upload_status === 'ready' ? 'text-green-500' : 'text-yellow-500'}"></i>
                                {doc.upload_status || 'ready'}
                              </span>
                            </div>
                            <p class="text-xs text-oxford-blue mt-1">Click to view AI summary</p>
                          </div>
                          <div
                            class="opacity-0 group-hover:opacity-100 transition-all duration-200 ml-2 flex items-center space-x-2"
                            on:click|stopPropagation
                            on:keydown|stopPropagation
                          >
                            {#if doc.download_url || doc.document_id}
                              <button
                                class="p-2 text-blue-600 hover:bg-blue-50 rounded-lg transition-colors"
                                title="View document"
                                on:click={() => viewDocument(doc)}
                              >
                                <i class="fas fa-eye text-sm"></i>
                              </button>
                              <button
                                class="p-2 text-green-600 hover:bg-green-50 rounded-lg transition-colors"
                                title="Download document"
                                on:click={() => downloadDocument(doc)}
                              >
                                <i class="fas fa-download text-sm"></i>
                              </button>
                            {/if}
                            <AdminDeleteButton
                              size="small"
                              itemName={doc.original_filename || doc.filename}
                              on:delete={() => deleteDocument(doc.document_id || doc.id, doc.original_filename || doc.filename)}
                            />
                          </div>
                        </div>
                      {/each}
                    </div>
                  {/if}
                {:else}
                  <!-- FOLDER VIEW -->
                  {#if loadingHierarchicalPaths}
                    <div class="flex items-center justify-center py-12">
                      <div class="animate-spin rounded-full h-8 w-8 border-b-2 border-oxford-blue mr-3"></div>
                      <span class="text-gray-500">Loading folder structure...</span>
                    </div>
                  {:else if hierarchicalPathsError}
                    <div class="text-center py-12">
                      <i class="fas fa-exclamation-triangle text-4xl text-red-300 mb-4"></i>
                      <h3 class="text-lg font-medium text-gray-700 mb-2">Failed to load folders</h3>
                      <p class="text-gray-500 mb-4">{hierarchicalPathsError}</p>
                      <button
                        class="px-4 py-2 bg-oxford-blue text-white rounded-lg hover:bg-blue-700 transition-colors text-sm"
                        on:click={loadHierarchicalPaths}
                      >
                        <i class="fas fa-redo mr-2"></i>Retry
                      </button>
                    </div>
                  {:else if hierarchicalPaths.length === 0}
                    <div class="text-center py-12">
                      <i class="fas fa-folder-open text-5xl text-gray-300 mb-4"></i>
                      <h3 class="text-lg font-medium text-gray-700 mb-2">No folder structure yet</h3>
                      <p class="text-gray-500">
                        {#if preserveOriginalFolderStructure}
                          Run <strong>Start Processing</strong> to generate AI-based folder classification.
                        {:else}
                          Upload documents to see folder structure.
                        {/if}
                      </p>
                    </div>
                  {:else}
                    <!-- Breadcrumb -->
                    <nav class="flex items-center text-sm mb-4 flex-wrap gap-1">
                      <button
                        class="hover:text-oxford-blue transition-colors {folderBrowsePath === '' ? 'text-oxford-blue font-semibold' : 'text-gray-500'}"
                        on:click={() => folderBrowsePath = ''}
                      >
                        <i class="fas fa-home mr-1"></i>Root
                      </button>
                      {#each folderBrowsePath.split('/').filter(Boolean) as segment, i}
                        <span class="text-gray-400">/</span>
                        <button
                          class="hover:text-oxford-blue transition-colors {i === folderBrowsePath.split('/').filter(Boolean).length - 1 ? 'text-oxford-blue font-semibold' : 'text-gray-500'}"
                          on:click={() => folderBrowsePath = folderBrowsePath.split('/').filter(Boolean).slice(0, i + 1).join('/')}
                        >
                          {segment}
                        </button>
                      {/each}
                    </nav>

                    <!-- Back button when inside a folder -->
                    {#if folderBrowsePath !== ''}
                      <button
                        class="flex items-center gap-2 text-sm text-gray-500 hover:text-oxford-blue mb-3 transition-colors"
                        on:click={() => {
                          const parts = folderBrowsePath.split('/').filter(Boolean);
                          parts.pop();
                          folderBrowsePath = parts.join('/');
                        }}
                      >
                        <i class="fas fa-arrow-left"></i> Back
                      </button>
                    {/if}

                    {@const currentFolders = hierarchicalPaths.filter(item =>
                      item.type === 'folder' && (() => {
                        const itemPath = item.path || '';
                        if (folderBrowsePath === '') {
                          return itemPath !== '' && !itemPath.includes('/');
                        }
                        return itemPath.startsWith(folderBrowsePath + '/') && !itemPath.slice(folderBrowsePath.length + 1).includes('/');
                      })()
                    )}
                    {@const currentFiles = hierarchicalPaths.filter(item =>
                      item.type === 'file' && (item.path || '') === folderBrowsePath
                    )}

                    {#if currentFolders.length === 0 && currentFiles.length === 0}
                      <div class="text-center py-8 text-gray-400">
                        <i class="fas fa-folder-open text-3xl mb-2"></i>
                        <p class="text-sm">This folder is empty</p>
                      </div>
                    {:else}
                      <div class="space-y-2">
                        <!-- Folders -->
                        {#each currentFolders as folder}
                          {@const fp = folder.path || ''}
                          {@const childFolderCount = hierarchicalPaths.filter(f => f.type === 'folder' && (() => {
                            const p = f.path || '';
                            return p.startsWith(fp + '/') && !p.slice(fp.length + 1).includes('/');
                          })()).length}
                          {@const directFileCount = hierarchicalPaths.filter(f => f.type === 'file' && (f.path || '') === fp).length}
                          {@const subtreeFileCount = hierarchicalPaths.filter(f => f.type === 'file' && ((f.path || '') === fp || (f.path || '').startsWith(fp + '/'))).length}
                          <button
                            class="w-full flex items-center p-3 border border-gray-200 rounded-lg hover:border-oxford-blue hover:bg-blue-50/40 transition-all duration-200 text-left group"
                            on:dblclick={() => folderBrowsePath = folder.path}
                            on:click={() => folderBrowsePath = folder.path}
                          >
                            <div class="flex-shrink-0 w-10 h-10 bg-amber-100 text-amber-600 rounded-lg flex items-center justify-center mr-4">
                              <i class="fas fa-folder text-lg"></i>
                            </div>
                            <div class="flex-1 min-w-0">
                              <p class="font-medium text-gray-900">{folder.displayName?.split('/').pop() || folder.name}</p>
                              <p class="text-xs text-gray-400 mt-0.5">
                                {#if childFolderCount > 0 && subtreeFileCount > 0}
                                  {childFolderCount} {childFolderCount === 1 ? 'subfolder' : 'subfolders'} · {subtreeFileCount} {subtreeFileCount === 1 ? 'file' : 'files'}{directFileCount > 0 && directFileCount < subtreeFileCount ? ` (${directFileCount} here)` : ''}
                                {:else if childFolderCount > 0}
                                  {childFolderCount} {childFolderCount === 1 ? 'subfolder' : 'subfolders'}
                                {:else if subtreeFileCount > 0}
                                  {subtreeFileCount} {subtreeFileCount === 1 ? 'file' : 'files'}
                                {:else}
                                  Empty
                                {/if}
                              </p>
                            </div>
                            <i class="fas fa-chevron-right text-gray-300 group-hover:text-oxford-blue transition-colors"></i>
                          </button>
                        {/each}

                        <!-- Files -->
                        {#each currentFiles as file}
                          {@const matchedDoc = uploadedDocuments.find(d => String(d.document_id) === file.document_id || d.original_filename === file.name)}
                          <div
                            class="flex items-center p-3 border border-gray-200 rounded-lg hover:border-oxford-blue hover:shadow-md transition-all duration-200 group cursor-pointer"
                            role="button"
                            tabindex="0"
                            on:click={() => matchedDoc && openDocumentSummary(matchedDoc)}
                            on:keydown={(e) => {
                              if (matchedDoc && (e.key === 'Enter' || e.key === ' ')) {
                                e.preventDefault();
                                openDocumentSummary(matchedDoc);
                              }
                            }}
                          >
                            <div class="flex-shrink-0 w-10 h-10 bg-gradient-to-br from-oxford-blue to-blue-600 text-white rounded-lg flex items-center justify-center mr-4">
                              <i class="fas fa-file text-sm"></i>
                            </div>
                            <div class="flex-1 min-w-0">
                              <p class="font-medium text-gray-900 truncate">{file.displayName?.split('/').pop() || file.name}</p>
                              {#if matchedDoc}
                                <div class="flex items-center text-sm text-gray-500 mt-0.5 space-x-4">
                                  <span class="flex items-center">
                                    <i class="fas fa-weight-hanging mr-1"></i>
                                    {matchedDoc.file_size_formatted || 'Unknown size'}
                                  </span>
                                  <span class="flex items-center">
                                    <i class="fas fa-circle mr-1 {matchedDoc.upload_status === 'ready' ? 'text-green-500' : 'text-yellow-500'}"></i>
                                    {matchedDoc.upload_status || 'ready'}
                                  </span>
                                </div>
                                <p class="text-xs text-oxford-blue mt-0.5">Click to view AI summary</p>
                              {/if}
                            </div>
                            <div
                              class="opacity-0 group-hover:opacity-100 transition-all duration-200 ml-2 flex items-center space-x-2"
                              on:click|stopPropagation
                              on:keydown|stopPropagation
                            >
                              {#if matchedDoc && (matchedDoc.download_url || matchedDoc.document_id)}
                                <button
                                  class="p-2 text-blue-600 hover:bg-blue-50 rounded-lg transition-colors"
                                  title="View document"
                                  on:click={() => viewDocument(matchedDoc)}
                                >
                                  <i class="fas fa-eye text-sm"></i>
                                </button>
                                <button
                                  class="p-2 text-green-600 hover:bg-green-50 rounded-lg transition-colors"
                                  title="Download document"
                                  on:click={() => downloadDocument(matchedDoc)}
                                >
                                  <i class="fas fa-download text-sm"></i>
                                </button>
                              {/if}
                              {#if matchedDoc}
                                <AdminDeleteButton
                                  size="small"
                                  itemName={matchedDoc.original_filename || matchedDoc.filename}
                                  on:delete={() => deleteDocument(matchedDoc.document_id || matchedDoc.id, matchedDoc.original_filename || matchedDoc.filename)}
                                />
                              {/if}
                            </div>
                          </div>
                        {/each}
                      </div>
                    {/if}
                  {/if}
                {/if}
              </div>
            </div>
          </div>
          
          <!-- Right Section: Processing & Stats (4 columns) -->
          <div class="xl:col-span-4 space-y-6">
            <!-- Quick Stats -->
            <div class="bg-oxford-blue text-white rounded-xl p-6">
              <h3 class="text-lg font-semibold mb-4 !text-white">Project Overview</h3>
              <div class="grid grid-cols-2 gap-4">
                <div class="text-center">
                  <div class="text-2xl font-bold !text-white">{uploadedDocuments.length}</div>
                  <div class="text-sm !text-white opacity-80">Documents</div>
                </div>
                <div class="text-center">
                  <div class="text-2xl font-bold !text-white">{processedCount}</div>
                  <div class="text-sm !text-white opacity-80">Processed</div>
                </div>
                <div class="text-center">
                  <div class="text-2xl font-bold !text-white">{project.total_pages}</div>
                  <div class="text-sm !text-white opacity-80">Pages</div>
                </div>
                <div class="text-center">
                  <div class="text-2xl font-bold !text-white">{hasNavigation ? 'Multi' : 'Single'}</div>
                  <div class="text-sm !text-white opacity-80">Page Mode</div>
                </div>
              </div>
            </div>
            
            <!-- Processing Section -->
            <div class="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
              <div class="px-6 py-4 bg-gray-50 border-b border-gray-200">
                <h2 class="text-lg font-bold text-gray-900 flex items-center">
                  <i class="fas fa-cogs mr-3 text-oxford-blue"></i>
                  Document Processing
                </h2>
              </div>
              
              <div class="p-6">
                {#if processingStatus}
                  <div class="mb-6">
                    <div class="flex items-center justify-between text-sm mb-3">
                      <span class="font-medium text-gray-700">Status:</span>
                      <span class="font-semibold text-oxford-blue">
                        {formatProcessingStatus(effectiveProcessingStatus)}
                      </span>
                    </div>
                    
                    {#if totalDocumentsCount > 0}
                      <div class="w-full bg-gray-200 rounded-full h-3 mb-2">
                        <div 
                          class="bg-oxford-blue h-3 rounded-full transition-all duration-500"
                          style="width: {Math.min(100, (processedCount / totalDocumentsCount) * 100)}%"
                        ></div>
                      </div>
                      <div class="flex justify-between text-xs text-gray-500">
                        <span>{processedCount} processed</span>
                        <span>{totalDocumentsCount} total</span>
                      </div>
                    {/if}
                  </div>
                {/if}
                
                <!-- LLM Configuration Section -->
                {#if uploadedDocuments.length > 0}
                  <div class="mb-6 p-4 bg-gray-50 rounded-lg border border-gray-200">
                    <h3 class="text-sm font-semibold text-gray-900 mb-4 flex items-center">
                      <i class="fas fa-brain mr-2 text-oxford-blue"></i>
                      Processing Configuration
                    </h3>
                    
                    <!-- LLM Provider Selection -->
                    <div class="mb-4">
                      <label class="block text-sm font-medium text-gray-700 mb-2">
                        LLM Provider
                        <span class="text-red-500">*</span>
                      </label>
                      {#if modelsLoading}
                        <div class="text-xs text-gray-500">Loading providers...</div>
                      {:else if availableProviders.length === 0}
                        <div class="text-xs text-amber-600 bg-amber-50 p-2 rounded">
                          <i class="fas fa-exclamation-triangle mr-1"></i>
                          No LLM providers available. Please configure API keys in API Management.
                        </div>
                      {:else}
                        {#if availableProviders.some(p => bulkModelData?.provider_statuses[p]?.has_api_key && !bulkModelData?.provider_statuses[p]?.api_key_valid)}
                          <div class="text-xs text-amber-600 bg-amber-50 p-2 rounded mb-2">
                            <i class="fas fa-exclamation-triangle mr-1"></i>
                            Some API keys could not be validated. They may still work for processing.
                          </div>
                        {/if}
                        <select 
                          bind:value={llmConfig.provider}
                          on:change={() => updateProviderModels()}
                          class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:border-oxford-blue focus:ring-2 focus:ring-oxford-blue/20 transition-all text-sm"
                        >
                          {#each availableProviders as provider}
                            {@const status = bulkModelData?.provider_statuses[provider]}
                            <option value={provider}>
                              {provider.charAt(0).toUpperCase() + provider.slice(1)}
                              {#if status?.has_api_key && !status?.api_key_valid}
                                (Validation Failed)
                              {/if}
                            </option>
                          {/each}
                        </select>
                      {/if}
                    </div>
                    
                    <!-- LLM Model Selection -->
                    {#if llmConfig.provider && providerModels.length > 0}
                      <div class="mb-4">
                        <label class="block text-sm font-medium text-gray-700 mb-2">
                          LLM Model
                          <span class="text-red-500">*</span>
                        </label>
                        <select 
                          bind:value={llmConfig.model}
                          class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:border-oxford-blue focus:ring-2 focus:ring-oxford-blue/20 transition-all text-sm"
                        >
                          {#each providerModels as model}
                            <option value={model.id}>
                              {model.display_name || model.name}
                              {#if model.cost_per_1k_tokens}
                                (${model.cost_per_1k_tokens}/1K tokens)
                              {/if}
                            </option>
                          {/each}
                        </select>
                      </div>
                    {/if}

                    <!-- Ollama Model Manager (shown when Ollama provider selected) -->
                    {#if llmConfig.provider === 'ollama'}
                      <OllamaModelManager />
                    {/if}

                    <!-- Enable Summary Toggle -->
                    <div class="flex items-center justify-between p-3 bg-white rounded-lg border border-gray-200">
                      <div class="flex-1">
                        <label class="text-sm font-medium text-gray-900 cursor-pointer" for="enable-summary-toggle">
                          Enable Summary
                        </label>
                        <p class="text-xs text-gray-500 mt-1">
                          Generate AI summaries for document chunks during processing
                        </p>
                      </div>
                      <label class="relative inline-flex items-center cursor-pointer">
                        <input 
                          type="checkbox" 
                          id="enable-summary-toggle"
                          bind:checked={llmConfig.enableSummary}
                          class="sr-only peer"
                        />
                        <div class="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-oxford-blue/20 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-oxford-blue"></div>
                      </label>
                    </div>
                    
                    <!-- Folder classification is always LLM-based (after summarization) -->
                  </div>
                {/if}
                
                <button
                  class="w-full flex items-center justify-center px-6 py-3 bg-oxford-blue text-white rounded-lg hover:bg-blue-700 transition-all duration-200 shadow-lg hover:shadow-xl transform hover:-translate-y-0.5 disabled:opacity-50 disabled:cursor-not-allowed disabled:transform-none disabled:shadow-lg"
                  on:click={processDocuments}
                  disabled={processing || uploadedDocuments.length === 0 || availableProviders.length === 0}
                >
                  {#if processing}
                    <div class="animate-spin rounded-full h-5 w-5 border-b-2 border-white mr-3"></div>
                    Processing...
                  {:else}
                    <i class="fas fa-play mr-3"></i>
                    {uploadedDocuments.length === 0 ? 'Upload documents first' : 'Start Processing'}
                  {/if}
                </button>
                
                {#if uploadedDocuments.length > 0}
                  <div class="mt-4 p-3 bg-blue-50 rounded-lg border border-blue-200">
                    <div class="flex items-start">
                      <i class="fas fa-info-circle text-blue-500 mt-0.5 mr-2"></i>
                      <div class="text-xs text-blue-700">
                        <p class="font-medium">Processing will:</p>
                        <ul class="mt-1 space-y-1">
                          <li>• Analyze document content with AI</li>
                          <li>• Create searchable embeddings</li>
                          <li>• Enable advanced features</li>
                        </ul>
                      </div>
                    </div>
                  </div>
                {/if}
              </div>
            </div>
            
            <!-- Template Info -->
            <div class="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
              <div class="px-6 py-4 bg-gray-50 border-b border-gray-200">
                <h2 class="text-lg font-bold text-gray-900 flex items-center">
                  <i class="fas fa-info-circle mr-3 text-oxford-blue"></i>
                  Template Info
                </h2>
              </div>
              
              <div class="p-6 space-y-4">
                <div class="flex justify-between items-center text-sm">
                  <span class="text-gray-600">Template Type</span>
                  <span class="font-medium text-gray-900">{project.template_type}</span>
                </div>
                <div class="flex justify-between items-center text-sm">
                  <span class="text-gray-600">Architecture</span>
                  <span class="font-medium text-green-600">Independent</span>
                </div>
                <div class="flex justify-between items-center text-sm">
                  <span class="text-gray-600">Interface Version</span>
                  <span class="font-medium text-gray-900">Universal v1.0</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      {/if}
    
    {#if hasNavigation && currentPage === 2}
      <!-- Page 2: Agent Orchestration (Capability-Based Rendering) -->
      {#if project.processing_capabilities?.supports_agent_orchestration}
        <div class="agent-orchestration-page h-full flex-1 w-full">
          <!-- SECURITY: key={projectId} forces full component remount on project switch -->
          {#key projectId}
            {#await import('$lib/components/AgentOrchestrationInterface.svelte')}
              <div class="flex items-center justify-center min-h-96">
                <div class="text-center">
                  <div class="animate-spin rounded-full h-12 w-12 border-b-2 border-oxford-blue mx-auto mb-4"></div>
                  <p class="text-oxford-blue">Loading Agent Orchestration...</p>
                </div>
              </div>
            {:then AgentOrchestrationModule}
              <svelte:component this={AgentOrchestrationModule.default} {project} {projectId} />
            {:catch error}
            <div class="flex items-center justify-center min-h-96">
              <div class="text-center">
                <div class="w-16 h-16 bg-red-100 text-red-600 rounded-xl flex items-center justify-center mx-auto mb-4 shadow-lg">
                  <i class="fas fa-exclamation-triangle text-2xl"></i>
                </div>
                <h2 class="text-xl font-bold text-gray-900 mb-2">Loading Error</h2>
                <p class="text-gray-600">Failed to load agent orchestration interface.</p>
                <button 
                  class="mt-4 px-4 py-2 bg-oxford-blue text-white rounded-md hover:bg-oxford-blue-dark transition-colors"
                  on:click={() => window.location.reload()}
                >
                  <i class="fas fa-refresh mr-2"></i>
                  Retry
                </button>
              </div>
            </div>
            {/await}
          {/key}
        </div>
      {:else}
        <div class="flex items-center justify-center min-h-96">
          <div class="text-center">
            <div class="w-16 h-16 bg-oxford-blue text-white rounded-xl flex items-center justify-center mx-auto mb-4 shadow-lg">
              <i class="fas fa-robot text-2xl"></i>
            </div>
            <h2 class="text-xl font-bold text-gray-900 mb-2">Agent Orchestration</h2>
            <p class="text-gray-600 mb-4">This project template does not support agent orchestration.</p>
            <div class="mt-4 p-4 bg-blue-50 rounded-lg border border-blue-200">
              <div class="flex items-start">
                <i class="fas fa-info-circle text-blue-500 mt-0.5 mr-2"></i>
                <div class="text-sm text-blue-700">
                  <p class="font-medium">To use agent orchestration:</p>
                  <p class="mt-1">Create a new project using the AICC-IntelliDoc v2 template</p>
                </div>
              </div>
            </div>
          </div>
        </div>
      {/if}
    {/if}
    
    {#if hasNavigation && currentPage === 3}
      <!-- Page 3: Evaluation -->
      <div class="evaluation-page h-full flex-1 w-full">
        <!-- SECURITY: key={projectId} forces full component remount on project switch -->
        {#key projectId}
          {#await import('$lib/components/WorkflowEvaluation.svelte')}
            <div class="flex items-center justify-center min-h-96">
              <div class="text-center">
                <div class="animate-spin rounded-full h-12 w-12 border-b-2 border-oxford-blue mx-auto mb-4"></div>
                <p class="text-oxford-blue">Loading Evaluation...</p>
              </div>
            </div>
          {:then WorkflowEvaluationModule}
            <svelte:component this={WorkflowEvaluationModule.default} {project} {projectId} />
          {:catch error}
          <div class="flex items-center justify-center min-h-96">
            <div class="text-center">
              <div class="w-16 h-16 bg-red-100 text-red-600 rounded-xl flex items-center justify-center mx-auto mb-4 shadow-lg">
                <i class="fas fa-exclamation-triangle text-2xl"></i>
              </div>
              <h2 class="text-xl font-bold text-gray-900 mb-2">Loading Error</h2>
              <p class="text-gray-600">Failed to load evaluation interface.</p>
              <button 
                class="mt-4 px-4 py-2 bg-oxford-blue text-white rounded-md hover:bg-oxford-blue-dark transition-colors"
                on:click={() => window.location.reload()}
              >
                <i class="fas fa-refresh mr-2"></i>
                Retry
              </button>
            </div>
          </div>
          {/await}
        {/key}
      </div>
    {/if}

    {#if hasNavigation && currentPage === 4}
      <!-- Page 4: Chatbot -->
      <div class="chatbot-page h-full flex-1 w-full">
        {#key projectId}
          {#await import('$lib/components/WorkflowChatbot.svelte')}
            <div class="flex items-center justify-center min-h-96">
              <div class="text-center">
                <div class="animate-spin rounded-full h-12 w-12 border-b-2 border-oxford-blue mx-auto mb-4"></div>
                <p class="text-oxford-blue">Loading Chatbot...</p>
              </div>
            </div>
          {:then ChatbotModule}
            <svelte:component this={ChatbotModule.default} {project} {projectId} />
          {:catch error}
            <div class="flex items-center justify-center min-h-96">
              <div class="text-center">
                <div class="w-16 h-16 bg-red-100 text-red-600 rounded-xl flex items-center justify-center mx-auto mb-4 shadow-lg">
                  <i class="fas fa-exclamation-triangle text-2xl"></i>
                </div>
                <h2 class="text-xl font-bold text-gray-900 mb-2">Loading Error</h2>
                <p class="text-gray-600">Failed to load chatbot interface.</p>
                <button
                  class="mt-4 px-4 py-2 bg-oxford-blue text-white rounded-md hover:bg-oxford-blue-dark transition-colors"
                  on:click={() => window.location.reload()}
                >
                  <i class="fas fa-refresh mr-2"></i> Retry
                </button>
              </div>
            </div>
          {/await}
        {/key}
      </div>
    {/if}
    
      </div>
    </div>
  </div>
{:else}
  <div class="flex items-center justify-center min-h-96">
    <div class="text-center">
      <i class="fas fa-exclamation-triangle text-4xl text-red-400 mb-4"></i>
      <h2 class="text-xl font-bold text-gray-900 mb-2">Project not found</h2>
      <p class="text-gray-600">The project you're looking for doesn't exist or you don't have access to it.</p>
      <button
        class="mt-4 px-4 py-2 bg-oxford-blue text-white rounded-md hover:bg-oxford-blue-dark transition-colors"
        on:click={() => goto('/features/intellidoc')}
      >
        <i class="fas fa-arrow-left mr-2"></i>
        Back to Projects
      </button>
    </div>
  </div>
{/if}

<style>
  :global(.oxford-blue) {
    color: #002147;
  }
  :global(.bg-oxford-blue) {
    background-color: #002147;
  }
  :global(.border-oxford-blue) {
    border-color: #002147;
  }
  :global(.bg-oxford-blue-dark) {
    background-color: #001122;
  }
  :global(.line-clamp-3) {
    display: -webkit-box;
    -webkit-line-clamp: 3;
    -webkit-box-orient: vertical;
    overflow: hidden;
  }
</style>

<svelte:window on:keydown={handleSummaryModalKeydown} />

<!-- Document AI summary modal -->
{#if summaryModalOpen}
  <div
    class="fixed inset-0 z-[10000] flex items-center justify-center p-4"
    role="dialog"
    aria-modal="true"
    aria-labelledby="doc-summary-modal-title"
  >
    <button
      type="button"
      class="absolute inset-0 bg-black/50 cursor-default border-0 w-full h-full"
      aria-label="Close summary"
      on:click={closeSummaryModal}
    ></button>
    <div
      class="relative bg-white rounded-xl shadow-2xl max-w-3xl w-full max-h-[85vh] flex flex-col border border-gray-200 z-10"
    >
      <div class="flex items-center justify-between px-5 py-4 border-b border-gray-200 bg-gray-50 rounded-t-xl">
        <h2 id="doc-summary-modal-title" class="text-lg font-semibold text-gray-900 truncate pr-4">
          AI summary — {summaryModalTitle}
        </h2>
        <button
          type="button"
          class="p-2 text-gray-500 hover:text-gray-800 hover:bg-gray-200 rounded-lg transition-colors"
          aria-label="Close"
          on:click={closeSummaryModal}
        >
          <i class="fas fa-times text-lg"></i>
        </button>
      </div>
      <div class="overflow-y-auto flex-1 px-5 py-4 text-sm text-gray-800">
        {#if summaryLoading}
          <div class="flex flex-col items-center justify-center py-16 text-gray-500">
            <div class="animate-spin rounded-full h-10 w-10 border-b-2 border-oxford-blue mb-3"></div>
            <p>Loading summary…</p>
          </div>
        {:else if summaryError}
          <p class="text-red-600">{summaryError}</p>
        {:else if summaryData}
          {#if summaryData.has_summary}
            {#if summaryData.short_summary && summaryData.long_summary}
              <div class="mb-6">
                <h3 class="text-xs font-semibold uppercase tracking-wide text-gray-500 mb-2">Short overview</h3>
                <p class="whitespace-pre-wrap text-gray-700 border border-gray-100 rounded-lg p-3 bg-gray-50/80">
                  {summaryData.short_summary}
                </p>
              </div>
              <div>
                <h3 class="text-xs font-semibold uppercase tracking-wide text-gray-500 mb-2">Full summary</h3>
                <div class="whitespace-pre-wrap text-gray-800 leading-relaxed border border-gray-100 rounded-lg p-3 bg-white">
                  {summaryData.long_summary}
                </div>
              </div>
            {:else if summaryData.long_summary}
              <div class="whitespace-pre-wrap text-gray-800 leading-relaxed">
                {summaryData.long_summary}
              </div>
            {:else if summaryData.short_summary}
              <p class="text-gray-600 mb-2">No long summary stored yet. Showing short summary:</p>
              <div class="whitespace-pre-wrap text-gray-800 leading-relaxed border border-gray-100 rounded-lg p-3 bg-gray-50/80">
                {summaryData.short_summary}
              </div>
            {/if}
            {#if summaryData.generated_at || summaryData.llm_provider}
              <p class="mt-6 text-xs text-gray-400 border-t border-gray-100 pt-3">
                {#if summaryData.generated_at}
                  Generated: {new Date(summaryData.generated_at).toLocaleString()}
                {/if}
                {#if summaryData.llm_provider}
                  <span class="ml-2">
                    · {summaryData.llm_provider}{summaryData.llm_model ? ` / ${summaryData.llm_model}` : ''}
                  </span>
                {/if}
              </p>
            {/if}
          {:else}
            <p class="text-gray-600">{summaryData.message || 'No AI summary available for this document yet.'}</p>
          {/if}
        {/if}
      </div>
    </div>
  </div>
{/if}

<!-- API Management Modal -->
<ApiManagement 
  {projectId}
  projectName={project?.name || ''}
  bind:showModal={showApiManagement}
  on:close={() => {
    showApiManagement = false;
    // Re-check API key status after closing the modal
    checkApiKeyStatus();
    // Force reload LLM models to pick up newly configured API keys
    loadLLMModels(true);
  }}
/>
