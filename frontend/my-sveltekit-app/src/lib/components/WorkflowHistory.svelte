<!-- WorkflowHistory.svelte - PHASE 4: Real-Time Workflow Execution History -->
<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import { cleanUniversalApi } from '$lib/services/cleanUniversalApi';
  import { toasts } from '$lib/stores/toast';
  import { workflowWebSocket, type AgentMessage, type ExecutionStatus } from '$lib/services/workflowWebSocket';
  
  export let project: any;
  export let projectId: string;
  export let workflows: any[];
  
  // State
  let simulationRuns: any[] = [];
  let selectedRun: any = null;
  let runMessages: any[] = [];
  let loading = true;
  let loadingMessages = false;
  
  // PHASE 4: Real-time workflow state
  let liveMessages: AgentMessage[] = [];
  let executionStatus: ExecutionStatus = {
    status: 'idle',
    message: 'Disconnected',
    progress: 0,
    timestamp: new Date().toISOString()
  };
  let connectionStatus: 'disconnected' | 'connecting' | 'connected' | 'error' = 'disconnected';
  let workflowCapabilities: any = null;
  
  // Filters
  let statusFilter = 'all';
  let workflowFilter = 'all';
  
  // Expandable delegate conversations state
  let expandedMessages = new Set();
  
  console.log(`📊 WORKFLOW HISTORY (PHASE 4): Initializing for project ${projectId}`);
  
  onMount(() => {
    loadSimulationHistory();
    setupWorkflowConnection();
  });
  
  onDestroy(() => {
    workflowWebSocket.disconnect();
  });
  
  async function setupWorkflowConnection() {
    try {
      console.log('🤖 WORKFLOW HISTORY: Workflow WebSocket temporarily disabled');
      
      // 🔧 TEMPORARILY DISABLED: WebSocket connections until Django Channels is set up
      // This prevents the connection refused errors you're seeing
      
      // Set default states
      executionStatus = {
        status: 'idle',
        message: 'Real-time streaming disabled (using polling instead)',
        progress: 0,
        timestamp: new Date().toISOString()
      };
      connectionStatus = 'disconnected';
      
      console.log('✅ WORKFLOW HISTORY: Using polling mode instead of WebSocket');
      
      // Workflow history is loaded on demand via API (getSimulationRuns). Real-time
      // WebSocket updates are not implemented; history is fetched when the panel loads.
      
    } catch (error) {
      console.error('❌ WORKFLOW HISTORY: Workflow connection failed:', error);
    }
  }
  
  async function loadSimulationHistory() {
    try {
      loading = true;
      console.log('📋 WORKFLOW HISTORY: Loading simulation runs');
      
      const result = await cleanUniversalApi.getSimulationRuns(projectId);
      simulationRuns = result.simulation_runs || [];
      
      console.log(`✅ WORKFLOW HISTORY: Loaded ${simulationRuns.length} simulation runs`);
      
    } catch (error) {
      console.error('❌ WORKFLOW HISTORY: Failed to load runs:', error);
      toasts.error('Failed to load execution history');
    } finally {
      loading = false;
    }
  }
  
  async function loadRunMessages(run: any) {
    if (loadingMessages) return;
    
    try {
      loadingMessages = true;
      selectedRun = run;
      
      console.log(`📨 WORKFLOW HISTORY: Loading messages for run ${run.run_id}`);
      
      const result = await cleanUniversalApi.getSimulationRun(projectId, run.run_id);
      runMessages = result.messages || [];
      
      console.log(`✅ WORKFLOW HISTORY: Loaded ${runMessages.length} messages`);
      
      // Scroll to bottom of messages
      setTimeout(() => {
        scrollToBottom();
      }, 100);
      
    } catch (error) {
      console.error('❌ WORKFLOW HISTORY: Failed to load messages:', error);
      toasts.error('Failed to load run messages');
    } finally {
      loadingMessages = false;
    }
  }
  
  function setupRealtimeConnection() {
    // PHASE 4: Now handled by Workflow WebSocket service
    console.log('🔌 WORKFLOW HISTORY: Real-time connection handled by Workflow WebSocket');
  }
  
  function scrollToBottom() {
    const messagesContainer = document.querySelector('.messages-container');
    if (messagesContainer) {
      messagesContainer.scrollTop = messagesContainer.scrollHeight;
    }
  }
  
  function getStatusColor(status: string) {
    switch (status) {
      case 'completed': return 'text-green-600 bg-green-50';
      case 'running': return 'text-blue-600 bg-blue-50';
      case 'failed': return 'text-red-600 bg-red-50';
      case 'stopped': return 'text-yellow-600 bg-yellow-50';
      default: return 'text-gray-600 bg-gray-50';
    }
  }
  
  function getStatusIcon(status: string) {
    switch (status) {
      case 'completed': return 'fa-check-circle';
      case 'running': return 'fa-spinner fa-spin';
      case 'failed': return 'fa-times-circle';
      case 'stopped': return 'fa-stop-circle';
      default: return 'fa-clock';
    }
  }
  
  function formatDuration(seconds: number | null) {
    if (!seconds) return 'N/A';
    
    if (seconds < 60) {
      return `${seconds.toFixed(1)}s`;
    } else if (seconds < 3600) {
      const minutes = Math.floor(seconds / 60);
      const remainingSeconds = seconds % 60;
      return `${minutes}m ${remainingSeconds.toFixed(0)}s`;
    } else {
      const hours = Math.floor(seconds / 3600);
      const minutes = Math.floor((seconds % 3600) / 60);
      return `${hours}h ${minutes}m`;
    }
  }
  
  function formatTimestamp(timestamp: string) {
    return new Date(timestamp).toLocaleString();
  }
  
  function getMessageTypeIcon(messageType: string) {
    switch (messageType) {
      case 'user_input': return 'fa-user';
      case 'function_call': return 'fa-cog';
      case 'function_result': return 'fa-check';
      case 'error': return 'fa-exclamation-triangle';
      case 'system': return 'fa-server';
      case 'group_chat_summary': return 'fa-users';
      case 'reflection_feedback': return 'fa-eye';
      case 'reflection_revision': return 'fa-edit';
      case 'reflection_final': return 'fa-check-double';
      case 'reflection_iteration': return 'fa-redo';
      case 'tool_plan': return 'fa-clipboard-list';
      case 'tool_notebook': return 'fa-book';
      default: return 'fa-comment';
    }
  }
  
  function getMessageTypeColor(messageType: string) {
    switch (messageType) {
      case 'user_input': return 'bg-blue-100 text-blue-800';
      case 'function_call': return 'bg-purple-100 text-purple-800';
      case 'function_result': return 'bg-green-100 text-green-800';
      case 'error': return 'bg-red-100 text-red-800';
      case 'system': return 'bg-gray-100 text-gray-800';
      case 'group_chat_summary': return 'bg-amber-100 text-amber-800';
      case 'reflection_feedback': return 'bg-cyan-100 text-cyan-800';
      case 'reflection_revision': return 'bg-indigo-100 text-indigo-800';
      case 'reflection_final': return 'bg-emerald-100 text-emerald-800';
      case 'reflection_iteration': return 'bg-pink-100 text-pink-800';
      case 'tool_plan': return 'bg-slate-100 text-slate-800';
      case 'tool_notebook': return 'bg-teal-100 text-teal-800';
      default: return 'bg-oxford-blue text-white';
    }
  }
  
  async function stopSimulation(run: any) {
    try {
      console.log(`⏹️ WORKFLOW HISTORY: Stopping simulation ${run.run_id}`);
      
      await cleanUniversalApi.stopSimulation(projectId, run.run_id);
      
      toasts.success('Simulation stopped successfully');
      
      // Reload history
      await loadSimulationHistory();
      
    } catch (error) {
      console.error('❌ WORKFLOW HISTORY: Stop failed:', error);
      toasts.error(`Failed to stop simulation: ${error.message}`);
    }
  }
  
  // Filter functions
  $: filteredRuns = simulationRuns.filter(run => {
    const statusMatch = statusFilter === 'all' || run.status === statusFilter;
    const workflowMatch = workflowFilter === 'all' || run.workflow?.workflow_id === workflowFilter;
    return statusMatch && workflowMatch;
  });
  
  // Toggle delegate conversation expansion
  function toggleDelegateExpansion(messageIndex: number) {
    const newExpanded = new Set(expandedMessages);
    if (newExpanded.has(messageIndex)) {
      newExpanded.delete(messageIndex);
    } else {
      newExpanded.add(messageIndex);
    }
    expandedMessages = newExpanded;
  }
</script>

<div class="workflow-history h-full flex bg-gray-50">
  <!-- History Sidebar -->
  <div class="w-80 border-r border-gray-200 bg-white flex flex-col">
    <!-- History Header -->
    <div class="p-4 border-b border-gray-200">
      <h3 class="font-semibold text-gray-900 mb-3">Execution History</h3>
      
      <!-- Filters -->
      <div class="space-y-2">
        <select
          bind:value={statusFilter}
          class="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:border-oxford-blue focus:ring-2 focus:ring-oxford-blue focus:ring-opacity-20"
        >
          <option value="all">All Statuses</option>
          <option value="pending">Pending</option>
          <option value="running">Running</option>
          <option value="completed">Completed</option>
          <option value="failed">Failed</option>
          <option value="stopped">Stopped</option>
        </select>
        
        <select
          bind:value={workflowFilter}
          class="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:border-oxford-blue focus:ring-2 focus:ring-oxford-blue focus:ring-opacity-20"
        >
          <option value="all">All Workflows</option>
          {#each workflows as workflow}
            <option value={workflow.workflow_id}>{workflow.name}</option>
          {/each}
        </select>
      </div>
    </div>
    
    <!-- History List -->
    <div class="flex-1 overflow-y-auto">
      {#if loading}
        <div class="p-4 flex items-center justify-center">
          <div class="text-center">
            <div class="animate-spin rounded-full h-8 w-8 border-b-2 border-oxford-blue mx-auto mb-2"></div>
            <p class="text-sm text-gray-600">Loading history...</p>
          </div>
        </div>
      {:else if filteredRuns.length === 0}
        <div class="p-4 text-center">
          <div class="w-12 h-12 bg-gray-100 text-gray-400 rounded-lg flex items-center justify-center mx-auto mb-3">
            <i class="fas fa-history text-xl"></i>
          </div>
          <p class="text-sm text-gray-600">No execution history found</p>
          <p class="text-xs text-gray-500 mt-1">Execute a workflow to see results here</p>
        </div>
      {:else}
        <div class="p-4 space-y-3">
          {#each filteredRuns as run}
            <div
              class="run-item p-3 border border-gray-200 rounded-lg hover:border-oxford-blue transition-all cursor-pointer {selectedRun?.run_id === run.run_id ? 'border-oxford-blue bg-blue-50' : 'bg-white hover:bg-gray-50'}"
              on:click={() => loadRunMessages(run)}
            >
              <div class="flex items-center justify-between mb-2">
                <div class="text-sm font-medium text-gray-900 truncate">
                  {run.workflow?.name || 'Unknown Workflow'}
                </div>
                <div class="flex items-center space-x-2">
                  <div class="px-2 py-1 rounded-full text-xs font-medium flex items-center space-x-1 {getStatusColor(run.status)}">
                    <i class="fas {getStatusIcon(run.status)}"></i>
                    <span>{run.status}</span>
                  </div>
                  {#if run.status === 'running'}
                    <button
                      class="p-1 text-red-600 hover:bg-red-50 rounded transition-colors"
                      on:click|stopPropagation={() => stopSimulation(run)}
                      title="Stop Simulation"
                    >
                      <i class="fas fa-stop text-xs"></i>
                    </button>
                  {/if}
                </div>
              </div>
              
              <div class="text-xs text-gray-600 space-y-1">
                <div>Started: {formatTimestamp(run.start_time)}</div>
                {#if run.duration_seconds}
                  <div>Duration: {formatDuration(run.duration_seconds)}</div>
                {/if}
                {#if run.total_messages > 0}
                  <div>{run.total_messages} messages</div>
                {/if}
              </div>
            </div>
          {/each}
        </div>
      {/if}
    </div>
  </div>
  
  <!-- Messages Panel -->
  <div class="flex-1 flex flex-col">
    {#if selectedRun}
      <!-- Messages Header -->
      <div class="p-4 border-b border-gray-200 bg-white">
        <div class="flex items-center justify-between">
          <div>
            <h3 class="font-semibold text-gray-900">{selectedRun.workflow?.name}</h3>
            <div class="text-sm text-gray-600 flex items-center space-x-4 mt-1">
              <span>Run ID: {selectedRun.run_id.substring(0, 8)}...</span>
              <span class="flex items-center space-x-1 px-2 py-1 rounded-full text-xs font-medium {getStatusColor(selectedRun.status)}">
                <i class="fas {getStatusIcon(selectedRun.status)}"></i>
                <span>{selectedRun.status}</span>
              </span>
              {#if connectionStatus === 'connected'}
                <span class="flex items-center space-x-1 text-green-600">
                  <div class="w-2 h-2 bg-green-600 rounded-full animate-pulse"></div>
                  <span>Workflow Live</span>
                </span>
              {:else if connectionStatus === 'connecting'}
                <span class="flex items-center space-x-1 text-yellow-600">
                  <div class="w-2 h-2 bg-yellow-600 rounded-full animate-pulse"></div>
                  <span>Connecting...</span>
                </span>
              {:else if connectionStatus === 'error'}
                <span class="flex items-center space-x-1 text-red-600">
                  <div class="w-2 h-2 bg-red-600 rounded-full"></div>
                  <span>Error</span>
                </span>
              {:else}
                <span class="flex items-center space-x-1 text-gray-500">
                  <div class="w-2 h-2 bg-gray-500 rounded-full"></div>
                  <span>Offline</span>
                </span>
              {/if}
            </div>
          </div>
          
          <div class="text-sm text-gray-600">
            {runMessages.length} messages
          </div>
        </div>
      </div>
      
      <!-- Messages Container -->
      <div class="flex-1 overflow-y-auto messages-container bg-gray-50 p-4">
        {#if loadingMessages}
          <div class="flex items-center justify-center h-full">
            <div class="text-center">
              <div class="animate-spin rounded-full h-8 w-8 border-b-2 border-oxford-blue mx-auto mb-2"></div>
              <p class="text-sm text-gray-600">Loading messages...</p>
            </div>
          </div>
        {:else if runMessages.length === 0}
          <div class="flex items-center justify-center h-full">
            <div class="text-center">
              <div class="w-12 h-12 bg-gray-100 text-gray-400 rounded-lg flex items-center justify-center mx-auto mb-3">
                <i class="fas fa-comments text-xl"></i>
              </div>
              <p class="text-sm text-gray-600">No messages yet</p>
              <p class="text-xs text-gray-500 mt-1">Messages will appear here during execution</p>
            </div>
          </div>
        {:else}
          <div class="space-y-4 max-w-4xl mx-auto">
            {#each runMessages as message, index}
              <div class="message-item flex items-start space-x-3">
                <!-- Agent Avatar -->
                <div class="w-8 h-8 bg-oxford-blue text-white rounded-lg flex items-center justify-center text-sm flex-shrink-0">
                  <i class="fas {getMessageTypeIcon(message.message_type)}"></i>
                </div>
                
                <!-- Message Content -->
                <div class="flex-1 min-w-0">
                  <div class="flex items-center space-x-2 mb-1">
                    <span class="font-medium text-sm text-gray-900">{message.agent_name}</span>
                    <span class="px-2 py-1 text-xs font-medium rounded-full {getMessageTypeColor(message.message_type)}">
                      {message.message_type}
                    </span>
                    <span class="text-xs text-gray-500">{formatTimestamp(message.timestamp)}</span>
                  </div>
                  
                  <div class="bg-white rounded-lg p-3 border border-gray-200 shadow-sm">
                    {#if message.message_type === 'function_call'}
                      <div class="text-sm">
                        <div class="font-medium text-purple-600 mb-2">
                          <i class="fas fa-cog mr-1"></i>
                          Function Call: {message.function_name}
                        </div>
                        {#if message.function_arguments}
                          <pre class="text-xs bg-gray-50 p-2 rounded overflow-x-auto">{JSON.stringify(message.function_arguments, null, 2)}</pre>
                        {/if}
                      </div>
                    {:else if message.message_type === 'function_result'}
                      <div class="text-sm">
                        <div class="font-medium text-green-600 mb-2">
                          <i class="fas fa-check mr-1"></i>
                          Function Result
                        </div>
                        {#if message.function_result}
                          <pre class="text-xs bg-gray-50 p-2 rounded overflow-x-auto">{JSON.stringify(message.function_result, null, 2)}</pre>
                        {/if}
                      </div>
                    {:else if message.message_type === 'error'}
                      <div class="text-sm text-red-600">
                        <i class="fas fa-exclamation-triangle mr-1"></i>
                        {message.content}
                      </div>
                    {:else if message.message_type === 'group_chat_summary'}
                      <!-- GroupChatManager with expandable delegate conversations -->
                      <div class="text-sm">
                        <div class="text-gray-700 whitespace-pre-wrap mb-3">{message.content}</div>
                        
                        {#if message.metadata?.expandable && message.metadata?.delegate_conversations?.length > 0}
                          <div class="border-t border-gray-200 pt-3">
                            <button
                              class="flex items-center space-x-2 text-sm font-medium text-oxford-blue hover:text-oxford-blue-dark transition-colors"
                              on:click={() => toggleDelegateExpansion(index)}
                            >
                              <i class="fas {expandedMessages.has(index) ? 'fa-chevron-down' : 'fa-chevron-right'}"></i>
                              <span>{expandedMessages.has(index) ? 'Hide' : 'Show'} Delegate Conversations</span>
                              <span class="px-2 py-1 bg-gray-100 text-gray-600 rounded-full text-xs">
                                {message.metadata.delegate_count} delegates, {message.metadata.total_iterations} iterations
                              </span>
                            </button>
                            
                            {#if expandedMessages.has(index)}
                              <div class="mt-3 space-y-2 bg-gray-50 rounded-lg p-3 border-l-4 border-oxford-blue">
                                <div class="text-xs font-medium text-gray-600 uppercase tracking-wider mb-2">
                                  Delegate Conversation Log
                                </div>
                                {#each message.metadata.delegate_conversations as delegateMsg, delegateIndex}
                                  <div class="delegate-message text-sm">
                                    <div class="flex items-start space-x-2">
                                      <div class="w-6 h-6 bg-blue-100 text-blue-600 rounded-full flex items-center justify-center text-xs flex-shrink-0 mt-0.5">
                                        <i class="fas fa-user-tie"></i>
                                      </div>
                                      <div class="flex-1 min-w-0">
                                        <div class="bg-white rounded-lg p-2 border border-gray-200 shadow-sm">
                                          <div class="text-gray-700 whitespace-pre-wrap">{delegateMsg}</div>
                                        </div>
                                      </div>
                                    </div>
                                  </div>
                                {/each}
                                
                                {#if message.metadata.delegate_status}
                                  <div class="mt-3 pt-2 border-t border-gray-300">
                                    <div class="text-xs font-medium text-gray-600 uppercase tracking-wider mb-2">
                                      Execution Summary
                                    </div>
                                    <div class="grid grid-cols-2 gap-2 text-xs">
                                      {#each Object.entries(message.metadata.delegate_status) as [delegateName, status]}
                                        <div class="bg-white rounded p-2 border border-gray-200">
                                          <div class="font-medium text-gray-700">{delegateName}</div>
                                          <div class="text-gray-500">
                                            {status.iterations}/{status.max_iterations} iterations
                                            <span class="ml-2 px-1.5 py-0.5 rounded text-xs {status.completed ? 'bg-green-100 text-green-700' : 'bg-yellow-100 text-yellow-700'}">
                                              {status.completed ? 'Completed' : 'In Progress'}
                                            </span>
                                          </div>
                                        </div>
                                      {/each}
                                    </div>
                                  </div>
                                {/if}
                              </div>
                            {/if}
                          </div>
                        {/if}
                      </div>
                    {:else if message.message_type === 'reflection_feedback'}
                      <div class="text-sm">
                        <div class="font-medium text-cyan-700 mb-2 flex items-center">
                          <i class="fas fa-eye mr-2"></i>
                          Reflection Feedback
                          {#if message.metadata?.reflection_source}
                            <span class="ml-2 text-xs bg-cyan-100 text-cyan-600 px-2 py-1 rounded">
                              from {message.metadata.reflection_source}
                            </span>
                          {/if}
                        </div>
                        <div class="text-gray-700 whitespace-pre-wrap bg-cyan-50 p-3 rounded-md border-l-4 border-cyan-300">
                          {message.content}
                        </div>
                      </div>
                    {:else if message.message_type === 'reflection_revision'}
                      <div class="text-sm">
                        <div class="font-medium text-indigo-700 mb-2 flex items-center">
                          <i class="fas fa-edit mr-2"></i>
                          Revised Response
                          {#if message.metadata?.iteration}
                            <span class="ml-2 text-xs bg-indigo-100 text-indigo-600 px-2 py-1 rounded">
                              iteration {message.metadata.iteration}
                            </span>
                          {/if}
                        </div>
                        <div class="text-gray-700 whitespace-pre-wrap bg-indigo-50 p-3 rounded-md border-l-4 border-indigo-300">
                          {message.content}
                        </div>
                      </div>
                    {:else if message.message_type === 'reflection_final'}
                      <div class="text-sm">
                        <div class="font-medium text-emerald-700 mb-2 flex items-center">
                          <i class="fas fa-check-double mr-2"></i>
                          Final Reflection Response
                        </div>
                        <div class="text-gray-700 whitespace-pre-wrap bg-emerald-50 p-3 rounded-md border-l-4 border-emerald-400">
                          {message.content}
                        </div>
                      </div>
                    {:else if message.message_type === 'reflection_iteration'}
                      <div class="text-sm">
                        <div class="font-medium text-pink-700 mb-2 flex items-center">
                          <i class="fas fa-redo mr-2"></i>
                          Reflection Iteration
                          {#if message.metadata?.iteration}
                            <span class="ml-2 text-xs bg-pink-100 text-pink-600 px-2 py-1 rounded">
                              #{message.metadata.iteration}
                            </span>
                          {/if}
                        </div>
                        <div class="text-gray-700 whitespace-pre-wrap bg-pink-50 p-3 rounded-md border-l-4 border-pink-300">
                          {message.content}
                        </div>
                      </div>
                    {:else if message.message_type === 'tool_plan'}
                      <div class="text-sm">
                        <div class="font-medium text-slate-700 mb-2 flex items-center">
                          <i class="fas fa-clipboard-list mr-2"></i>
                          Agent Plan
                        </div>
                        <div class="text-gray-700 whitespace-pre-wrap bg-slate-50 p-3 rounded-md border-l-4 border-slate-400">
                          {message.content}
                        </div>
                      </div>
                    {:else if message.message_type === 'tool_notebook'}
                      {@const entry = (() => { try { return JSON.parse(message.content); } catch { return null; } })()}
                      <div class="text-sm">
                        <div class="font-medium text-teal-700 mb-2 flex items-center">
                          <i class="fas fa-book mr-2"></i>
                          Notebook Entry
                          {#if entry?.step}
                            <span class="ml-2 text-xs bg-teal-100 text-teal-600 px-2 py-1 rounded">
                              Step {entry.step}
                            </span>
                          {/if}
                          {#if entry?.status === 'completed'}
                            <i class="fas fa-check-circle ml-2 text-green-500"></i>
                          {/if}
                        </div>
                        {#if entry}
                          <div class="bg-teal-50 p-3 rounded-md border-l-4 border-teal-300 space-y-2">
                            <div class="flex items-center text-xs text-teal-600">
                              <i class="fas fa-file-alt mr-1"></i>
                              <span class="font-medium">{entry.tool_name}</span>
                            </div>
                            <div class="text-xs text-gray-500">
                              <span class="font-medium">Query:</span> {entry.query}
                            </div>
                            <div class="text-gray-700 whitespace-pre-wrap text-sm">
                              {entry.result}
                            </div>
                            {#if entry.source_passages?.length}
                              <div class="mt-2 pt-2 border-t border-teal-200">
                                <div class="text-xs font-medium text-teal-700 mb-1.5 flex items-center">
                                  <i class="fas fa-quote-left mr-1.5 text-teal-400" style="font-size: 0.6rem;"></i>
                                  Citations ({entry.source_passages.length})
                                </div>
                                {#each entry.source_passages.slice(0, 3) as passage}
                                  <div class="text-xs bg-white/60 rounded px-2 py-1.5 mb-1 border-l-2 border-teal-400">
                                    <span class="text-gray-600 italic">"{passage.quoted_text?.slice(0, 200)}{passage.quoted_text?.length > 200 ? '...' : ''}"</span>
                                    {#if passage.page || passage.section}
                                      <span class="text-teal-500 ml-1 not-italic text-xs">
                                        {#if passage.page}p.{passage.page}{/if}{#if passage.page && passage.section}, {/if}{#if passage.section}{passage.section}{/if}
                                      </span>
                                    {/if}
                                  </div>
                                {/each}
                              </div>
                            {/if}
                          </div>
                        {:else}
                          <div class="text-gray-700 whitespace-pre-wrap bg-teal-50 p-3 rounded-md border-l-4 border-teal-300">
                            {message.content}
                          </div>
                        {/if}
                      </div>
                    {:else}
                      <div class="text-sm text-gray-700 whitespace-pre-wrap">{message.content}</div>
                    {/if}
                    
                    {#if message.response_time_ms}
                      <div class="text-xs text-gray-500 mt-2 flex items-center space-x-2">
                        <i class="fas fa-clock"></i>
                        <span>{message.response_time_ms}ms</span>
                        {#if message.token_count}
                          <span>• {message.token_count} tokens</span>
                        {/if}
                      </div>
                    {/if}
                  </div>
                </div>
              </div>
            {/each}
          </div>
        {/if}
      </div>
    {:else}
      <!-- No Run Selected -->
      <div class="flex-1 flex items-center justify-center bg-white">
        <div class="text-center">
          <div class="w-16 h-16 bg-gray-100 text-gray-400 rounded-xl flex items-center justify-center mx-auto mb-4">
            <i class="fas fa-comments text-2xl"></i>
          </div>
          <h3 class="text-lg font-medium text-gray-900 mb-2">Select an Execution</h3>
          <p class="text-gray-600">Choose an execution from the history to view its conversation log</p>
        </div>
      </div>
    {/if}
  </div>
</div>

<style>
  .workflow-history {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', sans-serif;
  }
  
  .messages-container {
    scroll-behavior: smooth;
  }
  
  .run-item:hover {
    transform: translateY(-1px);
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  }
  
  .message-item {
    animation: fadeInUp 0.3s ease-out;
  }
  
  @keyframes fadeInUp {
    from {
      opacity: 0;
      transform: translateY(10px);
    }
    to {
      opacity: 1;
      transform: translateY(0);
    }
  }
  
  :global(.focus\:border-oxford-blue:focus) {
    border-color: #002147;
  }
  
  :global(.focus\:ring-oxford-blue:focus) {
    --tw-ring-color: #002147;
  }
  
  :global(.bg-oxford-blue) {
    background-color: #002147;
  }
</style>
