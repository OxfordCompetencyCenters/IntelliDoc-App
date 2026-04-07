<!-- HumanInputModal.svelte - Phase 3 Human-in-the-Loop Modal Component -->
<script lang="ts">
  import { createEventDispatcher, onMount, onDestroy } from 'svelte';
  import { toasts } from '$lib/stores/toast';
  import { workflowStatus } from '$lib/stores/workflowStatus';
  import type { PendingHumanInput, InputSource } from '$lib/services/humanInputService';
  
  // Props
  export let executionId: string;
  export let agentName: string;
  export let inputContext: any;
  export let conversationHistory: string = '';
  export let isVisible: boolean = false;
  
  // Event dispatcher
  const dispatch = createEventDispatcher();
  
  // Component state
  let humanInput = '';
  let submitting = false;
  let showFullContext = false;
  let showConversationHistory = false;
  
  // Reflection iteration state
  let isIterating = false;
  
  // Modal element for focus management
  let modalElement: HTMLDivElement;
  let textareaElement: HTMLTextAreaElement;
  
  console.log('👤 HUMAN_INPUT_MODAL: Component initialized', {
    executionId: executionId?.slice(-8),
    agentName,
    inputCount: inputContext?.input_count || 0,
    hasConversationHistory: !!conversationHistory,
    isVisible,
    timestamp: new Date().toISOString()
  });
  
  // Focus management
  onMount(() => {
    console.log('🔄 HUMAN_INPUT_MODAL: Component mounted');
    console.log('📋 HUMAN_INPUT_MODAL: Mount state:', {
      isVisible,
      hasTextarea: !!textareaElement,
      executionId: executionId?.slice(-8),
      agentName
    });
    
    if (isVisible && textareaElement) {
      // Small delay to ensure modal is fully rendered
      setTimeout(() => {
        console.log('🎯 HUMAN_INPUT_MODAL: Focusing textarea');
        textareaElement?.focus();
      }, 100);
    }
    
    // Add escape key handler
    const handleKeydown = (event: KeyboardEvent) => {
      if (event.key === 'Escape' && isVisible && !submitting) {
        console.log('⌨️ HUMAN_INPUT_MODAL: Escape key pressed, closing modal');
        closeModal();
      }
    };
    
    document.addEventListener('keydown', handleKeydown);
    console.log('⌨️ HUMAN_INPUT_MODAL: Keyboard event listener added');
    
    return () => {
      console.log('🧹 HUMAN_INPUT_MODAL: Cleanup - removing keyboard listener');
      document.removeEventListener('keydown', handleKeydown);
    };
  });
  
  // Auto-resize textarea
  function autoResizeTextarea() {
    if (textareaElement) {
      const oldHeight = textareaElement.style.height;
      textareaElement.style.height = 'auto';
      const newHeight = Math.min(textareaElement.scrollHeight, 200) + 'px';
      textareaElement.style.height = newHeight;
      
      if (oldHeight !== newHeight) {
        console.log('📏 HUMAN_INPUT_MODAL: Textarea resized:', {
          oldHeight,
          newHeight,
          contentLength: humanInput.length
        });
      }
    }
  }
  
  // Handle input changes
  function handleInputChange() {
    console.log('📝 HUMAN_INPUT_MODAL: Input changed:', {
      length: humanInput.length,
      isValid: humanInput.trim().length > 0,
      preview: humanInput.slice(0, 50) + (humanInput.length > 50 ? '...' : '')
    });
    autoResizeTextarea();
  }
  
  // Check if this is a reflection scenario
  $: isReflectionScenario = inputContext?.reflection_source || inputContext?.input_method === 'reflection_feedback';
  $: reflectionSource = inputContext?.reflection_source || '';
  $: reflectionIteration = inputContext?.iteration || 1;
  $: reflectionMaxIterations = inputContext?.max_iterations || 1;
  
  // Iterate function for reflection
  async function iterateReflection() {
    console.log('🔄 HUMAN_INPUT_MODAL: Starting reflection iteration');
    console.log('📋 HUMAN_INPUT_MODAL: Iteration details:', {
      executionId: executionId?.slice(-8),
      agentName,
      reflectionSource,
      currentIteration: reflectionIteration,
      maxIterations: reflectionMaxIterations,
      hasInput: !!humanInput.trim()
    });
    
    if (!humanInput.trim()) {
      console.warn('⚠️ HUMAN_INPUT_MODAL: Empty input for iteration');
      toasts.error('Please enter your feedback before iterating');
      return;
    }
    
    if (!executionId) {
      console.error('❌ HUMAN_INPUT_MODAL: Missing execution ID for iteration');
      toasts.error('Missing execution ID - cannot iterate');
      return;
    }
    
    try {
      isIterating = true;
      console.log('⚡ HUMAN_INPUT_MODAL: Setting isIterating=true');
      
      console.log('🔄 HUMAN INPUT MODAL: Submitting iteration request', {
        executionId: executionId.slice(-8),
        inputLength: humanInput.length,
        agentName,
        action: 'iterate',
        timestamp: new Date().toISOString()
      });
      
      // Submit iteration via workflow status store with special action flag
      console.log('🌐 HUMAN_INPUT_MODAL: Calling workflowStatus.submitInput with iteration flag...');
      await workflowStatus.submitInput(executionId, humanInput.trim(), { action: 'iterate' });
      console.log('✅ HUMAN_INPUT_MODAL: Iteration request completed');
      
      // Show iteration message
      const iterationMessage = `🔄 Iteration requested! Sending feedback back to ${reflectionSource} for revision...`;
      console.log('🎉 HUMAN_INPUT_MODAL: Showing iteration toast:', iterationMessage);
      toasts.success(iterationMessage);
      
      console.log('✅ HUMAN INPUT MODAL: Iteration submitted successfully');
      
      // CRITICAL: Dispatch event with iteration flag
      const eventData = { 
        executionId, 
        humanInput: humanInput.trim(),
        agentName,
        action: 'iterate',
        reflectionSource,
        iteration: reflectionIteration
      };
      console.log('📡 HUMAN_INPUT_MODAL: Dispatching iteration event:', eventData);
      dispatch('inputSubmitted', eventData);
      
      // Close modal after successful iteration
      console.log('🚪 HUMAN_INPUT_MODAL: Closing modal after iteration');
      closeModal();
      
    } catch (error) {
      console.error('❌ HUMAN INPUT MODAL: Iteration failed:', error);
      console.error('❌ HUMAN_INPUT_MODAL: Iteration error details:', {
        message: error?.message,
        stack: error?.stack,
        executionId: executionId?.slice(-8),
        agentName,
        reflectionSource,
        inputLength: humanInput.length,
        timestamp: new Date().toISOString()
      });
      toasts.error(`Failed to submit iteration: ${error.message || 'Unknown error'}`);
    } finally {
      console.log('🏁 HUMAN_INPUT_MODAL: Setting isIterating=false');
      isIterating = false;
    }
  }

  // Submit human input
  async function submitInput() {
    console.log('📤 HUMAN_INPUT_MODAL: Starting submission process');
    console.log('📋 HUMAN_INPUT_MODAL: Submission details:', {
      executionId: executionId?.slice(-8),
      agentName,
      inputLength: humanInput.length,
      inputTrimmed: humanInput.trim().length,
      isValid: !!humanInput.trim(),
      hasExecutionId: !!executionId
    });
    
    if (!humanInput.trim()) {
      console.warn('⚠️ HUMAN_INPUT_MODAL: Empty input detected');
      toasts.error('Please enter your response');
      return;
    }
    
    if (!executionId) {
      console.error('❌ HUMAN_INPUT_MODAL: Missing execution ID');
      toasts.error('Missing execution ID - cannot submit input');
      return;
    }
    
    try {
      submitting = true;
      console.log('⚡ HUMAN_INPUT_MODAL: Setting submitting=true');
      
      console.log('📝 HUMAN INPUT MODAL: Submitting input', {
        executionId: executionId.slice(-8),
        inputLength: humanInput.length,
        agentName,
        timestamp: new Date().toISOString()
      });
      
      // Submit via workflow status store (handles API call and state updates)
      console.log('🌐 HUMAN_INPUT_MODAL: Calling workflowStatus.submitInput...');
      await workflowStatus.submitInput(executionId, humanInput.trim());
      console.log('✅ HUMAN_INPUT_MODAL: workflowStatus.submitInput completed');
      
      // Show success message
      const successMessage = `✅ Input submitted! ${agentName} workflow resuming...`;
      console.log('🎉 HUMAN_INPUT_MODAL: Showing success toast:', successMessage);
      toasts.success(successMessage);
      
      console.log('✅ HUMAN INPUT MODAL: Input submitted successfully');
      
      // CRITICAL FIX: Dispatch event with the input data BEFORE closing
      const eventData = { 
        executionId, 
        humanInput: humanInput.trim(),
        agentName
      };
      console.log('📡 HUMAN_INPUT_MODAL: Dispatching inputSubmitted event:', eventData);
      dispatch('inputSubmitted', eventData);
      
      // Close modal AFTER dispatching event
      console.log('🚪 HUMAN_INPUT_MODAL: Closing modal after successful submission');
      closeModal();
      
    } catch (error) {
      console.error('❌ HUMAN INPUT MODAL: Submission failed:', error);
      console.error('❌ HUMAN_INPUT_MODAL: Error details:', {
        message: error?.message,
        stack: error?.stack,
        executionId: executionId?.slice(-8),
        agentName,
        inputLength: humanInput.length,
        timestamp: new Date().toISOString()
      });
      toasts.error(`Failed to submit input: ${error.message || 'Unknown error'}`);
    } finally {
      console.log('🏁 HUMAN_INPUT_MODAL: Setting submitting=false');
      submitting = false;
    }
  }
  
  // Close modal
  function closeModal() {
    if (submitting) {
      console.warn('⚠️ HUMAN_INPUT_MODAL: Cannot close modal while submitting');
      return; // Don't close while submitting
    }
    
    console.log('❌ HUMAN INPUT MODAL: Closing modal');
    console.log('🧹 HUMAN_INPUT_MODAL: Cleaning up modal state:', {
      hadInput: humanInput.length > 0,
      showingFullContext: showFullContext,
      showingConversationHistory: showConversationHistory,
      executionId: executionId?.slice(-8)
    });
    
    // Clear input
    humanInput = '';
    showFullContext = false;
    showConversationHistory = false;
    
    // CRITICAL FIX: Dispatch close event immediately to prevent null reference issues
    console.log('📡 HUMAN_INPUT_MODAL: Dispatching close event');
    dispatch('close');
    
    console.log('✅ HUMAN_INPUT_MODAL: Modal closed successfully');
  }
  
  // Format timestamp for display
  function formatTimestamp(timestamp: string): string {
    try {
      return new Date(timestamp).toLocaleTimeString();
    } catch {
      return 'Unknown time';
    }
  }
  
  // Format date for display
  function formatDate(timestamp: string): string {
    try {
      return new Date(timestamp).toLocaleDateString();
    } catch {
      return 'Unknown date';
    }
  }
  
  // Get input sources with proper typing
  $: inputSources = (inputContext?.input_sources || []) as InputSource[];
  $: primaryInput = inputContext?.primary_input || '';
  $: inputCount = inputContext?.input_count || 0;
  
  // Handle click outside modal
  function handleBackdropClick(event: MouseEvent) {
    console.log('🖱️ HUMAN_INPUT_MODAL: Backdrop clicked');
    if (event.target === event.currentTarget && !submitting) {
      console.log('🚪 HUMAN_INPUT_MODAL: Valid backdrop click, closing modal');
      closeModal();
    } else if (submitting) {
      console.log('⚠️ HUMAN_INPUT_MODAL: Backdrop click ignored - submitting in progress');
    }
  }
  
  // Character count for textarea
  $: characterCount = humanInput.length;
  $: isInputValid = humanInput.trim().length > 0;
</script>

<!-- Modal Backdrop -->
{#if isVisible}
  <!-- svelte-ignore a11y-click-events-have-key-events -->
  <!-- svelte-ignore a11y-no-static-element-interactions -->
  <div 
    class="fixed inset-0 bg-black bg-opacity-60 flex items-center justify-center z-50 p-4"
    on:click={handleBackdropClick}
  >
    <!-- Modal Container -->
    <div 
      bind:this={modalElement}
      class="bg-white rounded-xl shadow-2xl max-w-6xl w-full max-h-[90vh] overflow-hidden flex flex-col"
      on:click|stopPropagation
    >
      <!-- Modal Header -->
      <div class="bg-white border-b border-gray-200 p-6 flex-shrink-0">
        <div class="flex items-center justify-between">
          <div class="flex items-center space-x-4">
            <!-- Professional Icon -->
            <div class="w-12 h-12 bg-oxford-blue text-white rounded-lg flex items-center justify-center">
              <i class="fas fa-user text-lg"></i>
            </div>
            
            <!-- Header Text -->
            <div>
              <h2 class="text-xl font-semibold text-gray-900">
                {isReflectionScenario ? 'Reflection Feedback Required' : 'Human Input Required'}
              </h2>
              <p class="text-gray-600 mt-1">
                {#if isReflectionScenario}
                  <span class="font-medium">{agentName}</span> needs feedback on response from <span class="font-medium text-orange-600">{reflectionSource}</span>
                {:else}
                  <span class="font-medium">{agentName}</span> needs your response to continue
                {/if}
              </p>
              {#if isReflectionScenario}
                <div class="mt-2 flex items-center text-sm">
                  <div class="flex items-center text-orange-600 bg-orange-50 px-2 py-1 rounded">
                    <i class="fas fa-redo mr-1"></i>
                    Iteration {reflectionIteration} of {reflectionMaxIterations}
                  </div>
                </div>
              {/if}
            </div>
          </div>
          
          <!-- Close Button -->
          <button
            class="text-gray-400 hover:text-gray-600 p-2 rounded-lg transition-colors hover:bg-gray-100"
            on:click={closeModal}
            disabled={submitting}
            title="Close (Esc)"
          >
            <i class="fas fa-times text-lg"></i>
          </button>
        </div>
        
        <!-- Status Bar -->
        <div class="mt-4 flex items-center justify-between text-sm">
          <div class="flex items-center space-x-4 text-gray-600">
            <div class="flex items-center">
              <i class="fas fa-clock mr-2"></i>
              Execution: {executionId.slice(-8)}
            </div>
            <div class="flex items-center">
              <i class="fas fa-project-diagram mr-2"></i>
              {inputCount} input source{inputCount !== 1 ? 's' : ''}
            </div>
          </div>
          
          {#if submitting}
            <div class="flex items-center text-oxford-blue">
              <i class="fas fa-spinner fa-spin mr-2"></i>
              Processing...
            </div>
          {/if}
        </div>
      </div>
      
      <!-- Modal Body -->
      <div class="flex flex-1 min-h-0 overflow-hidden">
        <!-- Left Panel: Input Context -->
        <div class="w-1/2 border-r border-gray-200 flex flex-col bg-gray-50">
          <div class="p-6 border-b border-gray-200 bg-white">
            <h3 class="text-lg font-semibold text-gray-900 mb-2">
              Input from Connected Agents
            </h3>
            <p class="text-sm text-gray-600">
              Review the information from {inputCount} connected agent{inputCount !== 1 ? 's' : ''} that led to this request
            </p>
          </div>
          
          <div class="flex-1 overflow-y-auto p-6">
            {#if inputSources && inputSources.length > 0}
              <div class="space-y-4">
                {#each inputSources as input, index}
                  <div class="bg-white border border-gray-200 rounded-lg p-4 shadow-sm">
                    <!-- Input Header -->
                    <div class="flex items-center justify-between mb-3">
                      <div class="flex items-center space-x-3">
                        <div class="w-8 h-8 rounded-lg flex items-center justify-center text-white text-sm font-medium shadow-sm
                                   {input.type === 'StartNode' ? 'bg-green-500' : 
                                    input.type === 'AssistantAgent' ? 'bg-blue-500' : 
                                    input.type === 'GroupChatManager' ? 'bg-purple-500' : 
                                    'bg-gray-500'}">
                          {input.name ? input.name.charAt(0).toUpperCase() : '?'}
                        </div>
                        <div>
                          <div class="font-medium text-gray-900">{input.name}</div>
                          <div class="text-xs text-gray-500">{input.type}</div>
                        </div>
                      </div>
                      
                      <div class="text-xs text-gray-400 bg-gray-100 px-2 py-1 rounded">
                        Priority {input.priority || 1}
                      </div>
                    </div>
                    
                    <!-- Input Content -->
                    <div class="bg-gray-50 rounded-lg p-3">
                      <div class="text-sm text-gray-800 whitespace-pre-wrap leading-relaxed">
                        {input.content || 'No content provided'}
                      </div>
                    </div>
                    
                    {#if input.content && input.content.length > 200}
                      <div class="mt-2 text-xs text-gray-500">
                        {input.content.length} characters
                      </div>
                    {/if}
                  </div>
                {/each}
              </div>
            {:else}
              <!-- No Input Sources -->
              <div class="text-center py-12">
                <div class="w-16 h-16 bg-gray-200 text-gray-400 rounded-xl flex items-center justify-center mx-auto mb-4">
                  <i class="fas fa-info-circle text-2xl"></i>
                </div>
                <h4 class="text-gray-900 font-medium mb-2">No Input Sources</h4>
                <p class="text-sm text-gray-600">
                  This UserProxyAgent was triggered without connected input sources.
                </p>
              </div>
            {/if}
            
            <!-- Conversation History Toggle -->
            {#if conversationHistory && conversationHistory.trim()}
              <div class="mt-6 pt-6 border-t border-gray-200">
                <button
                  class="w-full text-sm text-oxford-blue hover:text-oxford-700 font-medium py-2 px-4 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors"
                  on:click={() => showConversationHistory = !showConversationHistory}
                >
                  <i class="fas fa-{showConversationHistory ? 'chevron-up' : 'chevron-down'} mr-2"></i>
                  {showConversationHistory ? 'Hide' : 'Show'} Full Conversation History
                </button>
                
                {#if showConversationHistory}
                  <div class="mt-4 bg-white border border-gray-200 rounded-lg p-4 max-h-60 overflow-y-auto">
                    <div class="text-sm text-gray-700 whitespace-pre-wrap leading-relaxed">
                      {conversationHistory}
                    </div>
                  </div>
                {/if}
              </div>
            {/if}
          </div>
        </div>
        
        <!-- Right Panel: Human Response -->
        <div class="w-1/2 flex flex-col">
          <!-- Response Header -->
          <div class="p-6 border-b border-gray-200 bg-white">
            <h3 class="text-lg font-semibold text-gray-900 mb-2">Your Response</h3>
            <p class="text-sm text-gray-600">
              Provide feedback, corrections, approval, or additional instructions
            </p>
          </div>
          
          <!-- Response Input Area -->
          <div class="flex-1 p-6 flex flex-col">
            <!-- Textarea -->
            <div class="flex-1 flex flex-col">
              <textarea
                bind:this={textareaElement}
                bind:value={humanInput}
                on:input={handleInputChange}
                placeholder="Enter your response here...

Examples:
• Approve the analysis and proceed
• This looks good, but please also consider...
• I need you to revise the approach by...
• Add more detail about...
• The information is incorrect, please fix..."
                class="flex-1 min-h-[200px] w-full p-4 border border-gray-300 rounded-lg focus:border-oxford-blue focus:ring-1 focus:ring-oxford-blue resize-none text-sm leading-relaxed"
                disabled={submitting}
                style="min-height: 200px; max-height: 400px;"
              ></textarea>
              
              <!-- Character Counter -->
              <div class="mt-2 flex justify-between items-center text-xs text-gray-500">
                <div>
                  {characterCount} characters
                  {#if characterCount > 1000}
                    <span class="text-amber-600">(detailed response)</span>
                  {:else if characterCount > 100}
                    <span class="text-green-600">(good length)</span>
                  {/if}
                </div>
                <div class="text-gray-500">
                  <i class="fas fa-info-circle mr-1"></i>
                  Tip: Be specific for best results
                </div>
              </div>
            </div>
            
            <!-- Input Guidelines -->
            <div class="mt-4 p-4 bg-gray-50 border border-gray-200 rounded-lg">
              <h4 class="text-sm font-medium text-gray-900 mb-2">
                <i class="fas fa-lightbulb mr-1"></i>
                Response Guidelines
              </h4>
              <ul class="text-xs text-gray-700 space-y-1">
                <li>• <strong>Be specific:</strong> Clear instructions help agents perform better</li>
                <li>• <strong>Provide context:</strong> Explain your reasoning when making changes</li>
                <li>• <strong>Ask questions:</strong> Request clarification if needed</li>
                <li>• <strong>Give feedback:</strong> Let agents know what worked well</li>
                <li>• <strong>Set constraints:</strong> Specify any limitations or requirements</li>
              </ul>
            </div>
          </div>
          
          <!-- Action Buttons -->
          <div class="p-6 border-t border-gray-200 bg-gray-50">
            <div class="flex justify-end space-x-4">
              <!-- Cancel Button -->
              <button
                class="px-6 py-3 text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 hover:border-gray-400 transition-colors font-medium"
                on:click={closeModal}
                disabled={submitting || isIterating}
              >
                <i class="fas fa-times mr-2"></i>
                Cancel
              </button>
              
              <!-- Iterate Button (only for reflection scenarios) -->
              {#if isReflectionScenario}
                <button
                  class="px-6 py-3 bg-orange-500 text-white rounded-lg hover:bg-orange-600 transition-colors font-medium disabled:opacity-50 disabled:cursor-not-allowed"
                  on:click={iterateReflection}
                  disabled={submitting || isIterating || !isInputValid}
                  class:animate-pulse={isIterating}
                  title="Send feedback back to {reflectionSource} for another iteration"
                >
                  {#if isIterating}
                    <i class="fas fa-spinner fa-spin mr-2"></i>
                    Iterating...
                  {:else}
                    <i class="fas fa-redo mr-2"></i>
                    Iterate
                  {/if}
                </button>
              {/if}
              
              <!-- Submit Button -->
              <button
                class="px-8 py-3 bg-oxford-blue text-white rounded-lg hover:bg-oxford-700 transition-colors font-medium disabled:opacity-50 disabled:cursor-not-allowed"
                on:click={submitInput}
                disabled={submitting || isIterating || !isInputValid}
                class:animate-pulse={submitting}
              >
                {#if submitting}
                  <i class="fas fa-spinner fa-spin mr-2"></i>
                  Submitting...
                {:else}
                  <i class="fas fa-paper-plane mr-2"></i>
                  {isReflectionScenario ? 'Submit Final Response' : 'Submit Response'}
                {/if}
              </button>
            </div>
            
            <!-- Submit Helper -->
            {#if !isInputValid && humanInput.length === 0}
              <div class="mt-2 text-xs text-gray-500 text-right">
                Enter your response to enable submission
              </div>
            {:else if isInputValid}
              <div class="mt-2 text-xs text-green-600 text-right">
                <i class="fas fa-check mr-1"></i>
                {#if isReflectionScenario}
                  Ready to iterate or submit final response
                {:else}
                  Ready to submit
                {/if}
              </div>
            {/if}
            
            <!-- Reflection Helper -->
            {#if isReflectionScenario && isInputValid}
              <div class="mt-2 p-3 bg-orange-50 border border-orange-200 rounded-lg">
                <div class="text-xs text-orange-800">
                  <i class="fas fa-info-circle mr-1"></i>
                  <strong>Reflection Mode:</strong> 
                  <span class="ml-1">Click "Iterate" to send feedback back to {reflectionSource} for revision, or "Submit Final Response" to continue the workflow.</span>
                </div>
              </div>
            {/if}
          </div>
        </div>
      </div>
    </div>
  </div>
{/if}

<style>
  :global(.bg-oxford-blue) {
    background-color: #002147;
  }
  
  :global(.text-oxford-blue) {
    color: #002147;
  }
  
  :global(.border-oxford-blue) {
    border-color: #002147;
  }
  
  :global(.focus\:border-oxford-blue:focus) {
    border-color: #002147;
  }
  
  :global(.focus\:ring-oxford-blue:focus) {
    --tw-ring-color: #002147;
  }
  
  /* Modal animation */
  .fixed {
    animation: modalFadeIn 0.3s ease-out;
  }
  
  @keyframes modalFadeIn {
    from {
      opacity: 0;
    }
    to {
      opacity: 1;
    }
  }
  
  /* Modal content animation */
  .bg-white.rounded-xl {
    animation: modalSlideIn 0.3s ease-out;
  }
  
  @keyframes modalSlideIn {
    from {
      transform: translateY(-20px) scale(0.95);
      opacity: 0;
    }
    to {
      transform: translateY(0) scale(1);
      opacity: 1;
    }
  }
  
  /* Auto-resize textarea styling */
  textarea {
    resize: none;
    overflow-y: auto;
  }
  
  /* Scrollbar styling for better UX */
  .overflow-y-auto::-webkit-scrollbar {
    width: 6px;
  }
  
  .overflow-y-auto::-webkit-scrollbar-track {
    background: #f1f5f9;
  }
  
  .overflow-y-auto::-webkit-scrollbar-thumb {
    background: #cbd5e1;
    border-radius: 3px;
  }
  
  .overflow-y-auto::-webkit-scrollbar-thumb:hover {
    background: #94a3b8;
  }
</style>
