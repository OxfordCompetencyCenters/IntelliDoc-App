<!-- AgentConnector.svelte - Visual Agent Connection Component -->
<script lang="ts">
  import { createEventDispatcher } from 'svelte';
  
  export let sourceAgent: any;
  export let targetAgent: any;
  export let connection: any;
  export let isSelected = false;
  export let canDelete = true;
  
  const dispatch = createEventDispatcher();
  
  // Connection types and their visual properties
  const connectionTypes = {
    'default': { color: '#002147', style: 'solid', label: 'Flow' },
    'conditional': { color: '#f59e0b', style: 'dashed', label: 'Conditional' },
    'parallel': { color: '#10b981', style: 'dotted', label: 'Parallel' },
    'feedback': { color: '#ef4444', style: 'solid', label: 'Feedback' },
    'data': { color: '#8b5cf6', style: 'solid', label: 'Data' }
  };
  
  $: connectionType = connectionTypes[connection.type] || connectionTypes.default;
  $: connectionLabel = connection.label || connectionType.label;
  
  function handleConnectionClick() {
    dispatch('connectionSelect', connection);
  }
  
  function handleDeleteConnection(event: Event) {
    event.stopPropagation();
    dispatch('connectionDelete', connection);
  }
  
  function handleConfigureConnection(event: Event) {
    event.stopPropagation();
    dispatch('connectionConfigure', connection);
  }
</script>

<div 
  class="agent-connector flex items-center justify-between p-3 border rounded-lg transition-all cursor-pointer {isSelected ? 'border-oxford-blue bg-blue-50 shadow-md' : 'border-gray-200 hover:border-gray-300 hover:shadow-sm'}"
  on:click={handleConnectionClick}
  role="button"
  tabindex="0"
  on:keydown={(e) => e.key === 'Enter' && handleConnectionClick()}
>
  <!-- Connection Visualization -->
  <div class="flex items-center space-x-3 flex-1">
    <!-- Source Agent -->
    <div class="flex items-center space-x-2">
      <div class="w-8 h-8 bg-oxford-blue text-white rounded-lg flex items-center justify-center text-sm">
        <i class="fas {sourceAgent.icon || 'fa-robot'}"></i>
      </div>
      <span class="text-sm font-medium text-gray-900 truncate max-w-20">{sourceAgent.name}</span>
    </div>
    
    <!-- Connection Arrow with Type -->
    <div class="flex items-center space-x-2">
      <!-- Connection Line -->
      <div class="relative flex items-center">
        <div 
          class="h-0.5 w-12 transition-colors"
          style="background-color: {connectionType.color}; border-style: {connectionType.style};"
        ></div>
        
        <!-- Arrow -->
        <div 
          class="w-0 h-0 border-l-4 border-t-2 border-b-2 border-transparent transition-colors"
          style="border-left-color: {connectionType.color};"
        ></div>
      </div>
      
      <!-- Connection Type Badge -->
      {#if connection.type && connection.type !== 'default'}
        <span 
          class="inline-block px-2 py-0.5 rounded-full text-xs font-medium"
          style="background-color: {connectionType.color}20; color: {connectionType.color};"
        >
          {connectionLabel}
        </span>
      {/if}
    </div>
    
    <!-- Target Agent -->
    <div class="flex items-center space-x-2">
      <div class="w-8 h-8 bg-oxford-blue text-white rounded-lg flex items-center justify-center text-sm">
        <i class="fas {targetAgent.icon || 'fa-robot'}"></i>
      </div>
      <span class="text-sm font-medium text-gray-900 truncate max-w-20">{targetAgent.name}</span>
    </div>
  </div>
  
  <!-- Connection Actions -->
  <div class="flex items-center space-x-1 ml-3">
    <!-- Configure Connection -->
    <button
      class="p-1.5 text-gray-400 hover:text-oxford-blue transition-colors opacity-0 group-hover:opacity-100"
      on:click={handleConfigureConnection}
      title="Configure Connection"
    >
      <i class="fas fa-cog text-xs"></i>
    </button>
    
    <!-- Delete Connection -->
    {#if canDelete}
      <button
        class="p-1.5 text-gray-400 hover:text-red-600 transition-colors opacity-0 group-hover:opacity-100"
        on:click={handleDeleteConnection}
        title="Delete Connection"
      >
        <i class="fas fa-trash text-xs"></i>
      </button>
    {/if}
  </div>
</div>

<style>
  .agent-connector:hover .group-hover\:opacity-100 {
    opacity: 1;
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
</style>
