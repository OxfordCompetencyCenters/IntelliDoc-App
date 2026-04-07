<!-- ConnectionPropertiesPanel.svelte - Connection Configuration Panel -->
<script lang="ts">
  import { createEventDispatcher } from 'svelte';
  
  export let connection: any;
  export let nodes: any[] = [];
  
  const dispatch = createEventDispatcher();
  
  // Connection configuration
  let connectionType = connection?.type || 'sequential';
  let connectionLabel = connection?.label || '';
  let connectionDescription = connection?.description || '';
  let connectionCondition = connection?.condition || '';
  let connectionPriority = connection?.priority || 1;
  let connectionRetryCount = connection?.retryCount || 0;
  let connectionTimeout = connection?.timeout || 30;
  
  // 🤖 CONNECTION TYPES: Only Sequential and Reflection options
  const connectionTypes = [
    { 
      id: 'sequential', 
      name: 'Sequential', 
      description: 'Standard AutoGen agent-to-agent conversation flow',
      color: '#002147',
      icon: 'fa-arrow-right',
      workflow_pattern: 'agent_to_agent',
      configurable: ['label', 'description', 'timeout', 'request_reply'],
      help_text: 'Creates a direct conversation between two agents with optional reply request'
    },
    { 
      id: 'reflection', 
      name: 'Reflection', 
      description: 'Agent self-review and iteration cycles',
      color: '#ef4444',
      icon: 'fa-redo',
      workflow_pattern: 'reflection_loop',
      configurable: ['label', 'description', 'max_iterations', 'reflection_prompt', 'timeout'],
      help_text: 'Enables agents to review and improve their responses through iteration'
    }
  ];
  
  $: selectedConnectionType = connectionTypes.find(t => t.id === connectionType) || connectionTypes[0];
  $: sourceAgent = nodes.find(n => n.id === connection?.source);
  $: targetAgent = nodes.find(n => n.id === connection?.target);
  
  function saveConnectionProperties() {
    const updatedConnection = {
      ...connection,
      type: connectionType,
      label: connectionLabel,
      description: connectionDescription,
      condition: connectionCondition,
      priority: connectionPriority,
      retryCount: connectionRetryCount,
      timeout: connectionTimeout,
      data: {
        ...connection.data,
        connectionType,
        customLabel: connectionLabel,
        description: connectionDescription,
        condition: connectionCondition,
        priority: connectionPriority,
        retryCount: connectionRetryCount,
        timeout: connectionTimeout
      },
      // 🌟 INFINITE CANVAS: Enhanced connection update context
      canvasUpdate: {
        preservePath: true,
        updateType: 'properties',
        timestamp: Date.now(),
        triggerPathRedraw: true
      }
    };
    
    dispatch('connectionUpdate', updatedConnection);
    console.log('✅ CONNECTION PROPERTIES: Infinite canvas connection updated', connection.id, updatedConnection);
  }
  
  function deleteConnection() {
    if (confirm(`Delete connection from ${sourceAgent?.data?.name} to ${targetAgent?.data?.name}?`)) {
      // 🌟 INFINITE CANVAS: Enhanced delete with canvas context
      dispatch('connectionDelete', {
        ...connection,
        canvasUpdate: {
          updateType: 'delete',
          timestamp: Date.now(),
          triggerCanvasRedraw: true
        }
      });
      console.log('🗑️ CONNECTION PROPERTIES: Deleted infinite canvas connection', connection.id);
    }
  }
  
  function closePanel() {
    dispatch('close');
  }
  
  function getAgentIcon(agentType: string): string {
    switch (agentType) {
      case 'StartNode': return 'fa-play';
      case 'UserProxyAgent': return 'fa-user';
      case 'AssistantAgent': return 'fa-robot';
      case 'GroupChatManager': return 'fa-users';
      default: return 'fa-cog';
    }
  }
  
  function getAgentColor(agentType: string): string {
    switch (agentType) {
      case 'StartNode': return '#10b981';
      case 'UserProxyAgent': return '#3b82f6';
      case 'AssistantAgent': return '#002147';
      case 'GroupChatManager': return '#8b5cf6';
      default: return '#6b7280';
    }
  }
</script>

<div class="connection-properties-panel w-80 h-full bg-white border-l border-gray-200 flex flex-col">
  <!-- Panel Header -->
  <div class="flex-shrink-0 px-4 py-4 border-b border-gray-200 bg-gray-50">
    <div class="flex items-center justify-between">
      <div class="flex items-center space-x-3">
        <div 
          class="w-8 h-8 rounded-lg flex items-center justify-center text-white"
          style="background-color: {selectedConnectionType.color};"
        >
          <i class="fas {selectedConnectionType.icon} text-sm"></i>
        </div>
        <div>
          <h3 class="text-lg font-semibold text-gray-900">Connection Properties</h3>
          <p class="text-xs text-gray-600">🌟 Configure infinite canvas connection behavior</p>
        </div>
      </div>
      <button
        class="p-1.5 rounded hover:bg-gray-200 transition-colors"
        on:click={closePanel}
        title="Close Properties"
      >
        <i class="fas fa-times text-gray-500"></i>
      </button>
    </div>
  </div>
  
  
  
  <!-- Configuration Form -->
  <div class="flex-1 overflow-y-auto px-4 py-4 space-y-6">
    <!-- Connection Type -->
    <div>
      <label class="block text-sm font-medium text-gray-700 mb-2">Connection Type</label>
      <select
        bind:value={connectionType}
        class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-oxford-blue focus:border-oxford-blue text-sm"
        on:change={saveConnectionProperties}
      >
        {#each connectionTypes as type}
          <option value={type.id}>{type.name}</option>
        {/each}
      </select>
      <p class="text-xs text-gray-600 mt-1">{selectedConnectionType.description}</p>
    </div>
    
    <!-- Connection Label -->
    {#if selectedConnectionType.configurable.includes('label')}
      <div>
        <label class="block text-sm font-medium text-gray-700 mb-2">Display Label</label>
        <input
          type="text"
          bind:value={connectionLabel}
          placeholder="Custom connection label..."
          class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-oxford-blue focus:border-oxford-blue text-sm"
          on:blur={saveConnectionProperties}
        />
        <p class="text-xs text-gray-600 mt-1">Optional label shown on the connection</p>
      </div>
    {/if}
    
    <!-- Connection Description -->
    {#if selectedConnectionType.configurable.includes('description')}
      <div>
        <label class="block text-sm font-medium text-gray-700 mb-2">Description</label>
        <textarea
          bind:value={connectionDescription}
          placeholder="Describe this connection's purpose..."
          rows="3"
          class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-oxford-blue focus:border-oxford-blue text-sm resize-none"
          on:blur={saveConnectionProperties}
        ></textarea>
        <p class="text-xs text-gray-600 mt-1">Optional description for documentation</p>
      </div>
    {/if}
    
    <!-- Conditional Logic -->
    {#if selectedConnectionType.configurable.includes('condition')}
      <div>
        <label class="block text-sm font-medium text-gray-700 mb-2">Execution Condition</label>
        <textarea
          bind:value={connectionCondition}
          placeholder="Enter condition logic (e.g., result.success == true)..."
          rows="2"
          class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-oxford-blue focus:border-oxford-blue text-sm resize-none font-mono"
          on:blur={saveConnectionProperties}
        ></textarea>
        <p class="text-xs text-gray-600 mt-1">Python expression that must be true to execute</p>
      </div>
    {/if}
    
    <!-- Priority Setting -->
    {#if selectedConnectionType.configurable.includes('priority')}
      <div>
        <label class="block text-sm font-medium text-gray-700 mb-2">Execution Priority</label>
        <select
          bind:value={connectionPriority}
          class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-oxford-blue focus:border-oxford-blue text-sm"
          on:change={saveConnectionProperties}
        >
          <option value={1}>High Priority (1)</option>
          <option value={2}>Normal Priority (2)</option>
          <option value={3}>Low Priority (3)</option>
        </select>
        <p class="text-xs text-gray-600 mt-1">Lower numbers execute first in parallel flows</p>
      </div>
    {/if}
    
    <!-- Retry Count -->
    {#if selectedConnectionType.configurable.includes('retryCount')}
      <div>
        <label class="block text-sm font-medium text-gray-700 mb-2">Retry Count</label>
        <input
          type="number"
          bind:value={connectionRetryCount}
          min="0"
          max="10"
          class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-oxford-blue focus:border-oxford-blue text-sm"
          on:blur={saveConnectionProperties}
        />
        <p class="text-xs text-gray-600 mt-1">Number of times to retry failed feedback loops</p>
      </div>
    {/if}
    
    <!-- Timeout Setting -->
    {#if selectedConnectionType.configurable.includes('timeout')}
      <div>
        <label class="block text-sm font-medium text-gray-700 mb-2">Timeout (seconds)</label>
        <input
          type="number"
          bind:value={connectionTimeout}
          min="1"
          max="300"
          class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-oxford-blue focus:border-oxford-blue text-sm"
          on:blur={saveConnectionProperties}
        />
        <p class="text-xs text-gray-600 mt-1">Maximum execution time before timeout</p>
      </div>
    {/if}
    
    <!-- Connection Stats -->
    <div class="p-3 bg-gray-50 rounded-lg border border-gray-200">
      <h4 class="text-sm font-medium text-gray-900 mb-2">🌟 Infinite Canvas Connection</h4>
      <div class="grid grid-cols-2 gap-3 text-xs">
        <div>
          <div class="text-gray-500">Created</div>
          <div class="font-medium text-gray-900">Just now</div>
        </div>
        <div>
          <div class="text-gray-500">Canvas Type</div>
          <div class="font-medium text-blue-700">Dynamic Path</div>
        </div>
        <div>
          <div class="text-gray-500">Executions</div>
          <div class="font-medium text-gray-900">0</div>
        </div>
        <div>
          <div class="text-gray-500">Success Rate</div>
          <div class="font-medium text-gray-900">N/A</div>
        </div>
      </div>
      <div class="mt-2 pt-2 border-t border-gray-200 text-xs text-blue-600">
        <i class="fas fa-info-circle mr-1"></i>
        Path automatically adjusts to node positions on infinite canvas
      </div>
    </div>
  </div>
  
  <!-- Panel Actions -->
  <div class="flex-shrink-0 px-4 py-4 border-t border-gray-200 bg-gray-50">
    <div class="flex items-center justify-between">
      <button
        class="px-3 py-1.5 text-red-600 hover:bg-red-50 rounded text-sm font-medium transition-colors"
        on:click={deleteConnection}
      >
        <i class="fas fa-trash mr-1"></i>
        Delete Connection
      </button>
      
      <div class="flex items-center space-x-2">
        <button
          class="px-3 py-1.5 text-gray-600 hover:text-gray-800 text-sm font-medium transition-colors"
          on:click={closePanel}
        >
          Cancel
        </button>
        <button
          class="px-3 py-1.5 bg-oxford-blue text-white rounded hover:bg-blue-700 text-sm font-medium transition-colors"
          on:click={saveConnectionProperties}
        >
          <i class="fas fa-save mr-1"></i>
          Save to Canvas
        </button>
      </div>
    </div>
  </div>
</div>

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
  
  :global(.focus\:ring-oxford-blue:focus) {
    --tw-ring-color: #002147;
  }
  
  :global(.focus\:border-oxford-blue:focus) {
    border-color: #002147;
  }
</style>