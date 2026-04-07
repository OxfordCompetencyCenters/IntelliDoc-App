<!-- EnhancedTextArea.svelte - Enhanced text area with line numbers, syntax highlighting, and expand functionality -->
<script lang="ts">
  import { createEventDispatcher, onMount, onDestroy } from 'svelte';
  
  export let value: string = '';
  export let placeholder: string = '';
  export let label: string = '';
  export let rows: number = 6;
  export let enableLineNumbers: boolean = true;
  export let enableSyntaxHighlight: boolean = true;
  export let syntaxLanguage: 'markdown' | 'json' | 'plain' = 'markdown';
  export let disabled: boolean = false;
  export let maxLength: number | null = null;
  export let showCharCount: boolean = false;
  export let helperText: string = '';
  
  const dispatch = createEventDispatcher();
  
  let showExpandedEditor = false;
  let textareaElement: HTMLTextAreaElement;
  let expandedTextareaElement: HTMLTextAreaElement;
  let lineNumbersElement: HTMLDivElement;
  const textareaId = 'enhanced-textarea-' + Math.random().toString(36).slice(2, 11);
  
  // Calculate line count for line numbers
  $: lineCount = value ? value.split('\n').length : 1;
  $: lines = Array.from({ length: Math.max(lineCount, rows) }, (_, i) => i + 1);
  
  // Character count
  $: charCount = value?.length || 0;
  
  // Sync scroll between textarea and line numbers
  function handleScroll(event: Event) {
    const target = event.target as HTMLTextAreaElement;
    if (lineNumbersElement) {
      lineNumbersElement.scrollTop = target.scrollTop;
    }
  }
  
  function handleInput(event: Event) {
    const target = event.target as HTMLTextAreaElement;
    value = target.value;
    dispatch('input', { value });
  }
  
  function handleExpandedInput(event: Event) {
    const target = event.target as HTMLTextAreaElement;
    value = target.value;
    dispatch('input', { value });
  }
  
  function openExpandedEditor() {
    showExpandedEditor = true;
    // Focus the expanded textarea after it renders
    setTimeout(() => {
      if (expandedTextareaElement) {
        expandedTextareaElement.focus();
        // Move cursor to end
        expandedTextareaElement.selectionStart = expandedTextareaElement.value.length;
        expandedTextareaElement.selectionEnd = expandedTextareaElement.value.length;
      }
    }, 50);
  }
  
  function closeExpandedEditor() {
    showExpandedEditor = false;
    // Refocus the main textarea
    setTimeout(() => {
      if (textareaElement) {
        textareaElement.focus();
      }
    }, 50);
  }
  
  function handleKeydown(event: KeyboardEvent) {
    // Close expanded editor on Escape
    if (event.key === 'Escape' && showExpandedEditor) {
      event.preventDefault();
      event.stopPropagation();
      closeExpandedEditor();
    }
  }
  
  // Add keyboard listener only when expanded editor is open
  function addKeyboardListener() {
    window.addEventListener('keydown', handleKeydown);
  }
  
  function removeKeyboardListener() {
    window.removeEventListener('keydown', handleKeydown);
  }
  
  // Watch for showExpandedEditor changes to manage keyboard listener
  $: if (showExpandedEditor) {
    addKeyboardListener();
  } else {
    removeKeyboardListener();
  }
  
  // Clean up on component destroy
  onDestroy(() => {
    removeKeyboardListener();
  });
  
  // Apply basic syntax highlighting for preview
  function highlightSyntax(text: string): string {
    if (!enableSyntaxHighlight || !text) return escapeHtml(text);
    
    if (syntaxLanguage === 'markdown') {
      return highlightMarkdown(text);
    } else if (syntaxLanguage === 'json') {
      return highlightJson(text);
    }
    return escapeHtml(text);
  }
  
  function escapeHtml(text: string): string {
    return text
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }
  
  function highlightMarkdown(text: string): string {
    let escaped = escapeHtml(text);
    
    // Headers (# Header)
    escaped = escaped.replace(/^(#{1,6})\s(.+)$/gm, '<span class="text-blue-600 font-semibold">$1 $2</span>');
    
    // Bold (**text** or __text__)
    escaped = escaped.replace(/\*\*(.+?)\*\*/g, '<span class="font-bold text-gray-900">**$1**</span>');
    escaped = escaped.replace(/__(.+?)__/g, '<span class="font-bold text-gray-900">__$1__</span>');
    
    // Italic (*text* or _text_)
    escaped = escaped.replace(/(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)/g, '<span class="italic text-gray-700">*$1*</span>');
    
    // Code blocks (```code```)
    escaped = escaped.replace(/```([\s\S]*?)```/g, '<span class="bg-gray-100 text-pink-600 font-mono">```$1```</span>');
    
    // Inline code (`code`)
    escaped = escaped.replace(/`([^`]+)`/g, '<span class="bg-gray-100 text-pink-600 font-mono px-1 rounded">`$1`</span>');
    
    // Lists (- item or * item or 1. item)
    escaped = escaped.replace(/^(\s*[-*+]|\s*\d+\.)\s/gm, '<span class="text-green-600">$1 </span>');
    
    // Links [text](url)
    escaped = escaped.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<span class="text-blue-500 underline">[$1]($2)</span>');
    
    return escaped;
  }
  
  function highlightJson(text: string): string {
    let escaped = escapeHtml(text);
    
    // Keys
    escaped = escaped.replace(/"([^"]+)":/g, '<span class="text-purple-600">"$1"</span>:');
    
    // String values
    escaped = escaped.replace(/:\s*"([^"]*)"/g, ': <span class="text-green-600">"$1"</span>');
    
    // Numbers
    escaped = escaped.replace(/:\s*(\d+\.?\d*)/g, ': <span class="text-blue-600">$1</span>');
    
    // Booleans and null
    escaped = escaped.replace(/:\s*(true|false|null)/g, ': <span class="text-orange-600">$1</span>');
    
    return escaped;
  }
</script>

<div class="enhanced-textarea-wrapper">
  <!-- Label and controls -->
  {#if label}
    <div class="flex items-center justify-between mb-2">
      <label for={textareaId} class="block text-sm font-medium text-gray-700">{label}</label>
      <button
        type="button"
        aria-label="Expand editor"
        on:click={openExpandedEditor}
        class="p-1.5 text-gray-500 hover:text-oxford-blue hover:bg-gray-100 rounded transition-colors"
        title="Expand editor"
      >
        <i class="fas fa-expand-alt text-sm" aria-hidden="true"></i>
      </button>
    </div>
  {/if}
  
  <!-- Main textarea with optional line numbers -->
  <div class="relative flex border border-gray-300 rounded-lg overflow-hidden focus-within:border-oxford-blue focus-within:ring-2 focus-within:ring-oxford-blue focus-within:ring-opacity-20 transition-all bg-white">
    <!-- Line numbers -->
    {#if enableLineNumbers}
      <div 
        bind:this={lineNumbersElement}
        class="line-numbers select-none text-gray-400 text-xs font-mono text-right py-2 px-2 bg-gray-50 border-r border-gray-200 overflow-hidden"
        style="min-width: 2.5rem;"
      >
        {#each lines as lineNum}
          <div class="leading-5">{lineNum}</div>
        {/each}
      </div>
    {/if}
    
    <!-- Textarea -->
    <textarea
      id={textareaId}
      bind:this={textareaElement}
      bind:value
      on:input={handleInput}
      on:scroll={handleScroll}
      {placeholder}
      {disabled}
      maxlength={maxLength}
      rows={rows}
      class="flex-1 px-3 py-2 text-sm leading-5 font-mono resize-y focus:outline-none disabled:bg-gray-100 disabled:cursor-not-allowed"
      class:bg-gray-50={disabled}
      style="min-height: {rows * 1.25}rem;"
    ></textarea>
  </div>
  
  <!-- Helper text and character count -->
  <div class="flex items-center justify-between mt-1">
    {#if helperText}
      <p class="text-xs text-gray-500">{helperText}</p>
    {:else}
      <span></span>
    {/if}
    
    {#if showCharCount}
      <p class="text-xs text-gray-500">
        {charCount}{#if maxLength}/{maxLength}{/if} characters
      </p>
    {/if}
  </div>
</div>

<!-- Expanded Editor Modal -->
{#if showExpandedEditor}
  <div 
    class="fixed inset-0 bg-black bg-opacity-50 z-[100] flex items-center justify-center p-4"
    role="dialog"
    aria-modal="true"
    aria-labelledby="expanded-editor-title"
    tabindex="-1"
    on:click|self={closeExpandedEditor}
    on:keydown={(e) => e.key === 'Escape' && closeExpandedEditor()}
  >
    <div class="bg-white rounded-xl shadow-2xl w-full max-w-4xl h-[85vh] flex flex-col overflow-hidden">
      <!-- Modal Header -->
      <div class="flex items-center justify-between px-4 py-3 border-b border-gray-200 bg-gray-50">
        <div class="flex items-center space-x-2">
          <i class="fas fa-edit text-oxford-blue"></i>
          <h3 id="expanded-editor-title" class="font-semibold text-gray-900">
            {label || 'Text Editor'}
          </h3>
        </div>
        <div class="flex items-center space-x-2">
          {#if showCharCount}
            <span class="text-sm text-gray-500">
              {charCount}{#if maxLength}/{maxLength}{/if} chars
            </span>
          {/if}
          <button
            type="button"
            aria-label="Close"
            on:click={closeExpandedEditor}
            class="p-2 text-gray-500 hover:text-gray-700 hover:bg-gray-200 rounded-lg transition-colors"
            title="Close (Esc)"
          >
            <i class="fas fa-times" aria-hidden="true"></i>
          </button>
        </div>
      </div>
      
      <!-- Modal Body - Editor with line numbers -->
      <div class="flex-1 flex overflow-hidden">
        <!-- Line numbers for expanded view -->
        {#if enableLineNumbers}
          <div class="line-numbers-expanded select-none text-gray-400 text-sm font-mono text-right py-4 px-3 bg-gray-50 border-r border-gray-200 overflow-y-auto">
            {#each lines as lineNum}
              <div class="leading-6">{lineNum}</div>
            {/each}
          </div>
        {/if}
        
        <!-- Expanded textarea -->
        <textarea
          bind:this={expandedTextareaElement}
          bind:value
          on:input={handleExpandedInput}
          {placeholder}
          {disabled}
          maxlength={maxLength}
          class="flex-1 px-4 py-4 text-sm leading-6 font-mono resize-none focus:outline-none overflow-y-auto"
          style="min-height: 100%;"
        ></textarea>
        
        <!-- Optional: Syntax highlighted preview -->
        {#if enableSyntaxHighlight && syntaxLanguage !== 'plain'}
          <div class="w-1/3 border-l border-gray-200 bg-gray-50 overflow-y-auto">
            <div class="px-3 py-2 border-b border-gray-200 bg-gray-100">
              <span class="text-xs font-medium text-gray-600">Preview</span>
            </div>
            <div class="p-4 text-sm leading-6 font-mono whitespace-pre-wrap">
              {@html highlightSyntax(value)}
            </div>
          </div>
        {/if}
      </div>
      
      <!-- Modal Footer -->
      <div class="flex items-center justify-between px-4 py-3 border-t border-gray-200 bg-gray-50">
        <div class="text-xs text-gray-500">
          <span class="mr-4"><kbd class="px-1.5 py-0.5 bg-gray-200 rounded text-xs">Esc</kbd> to close</span>
          {#if enableLineNumbers}
            <span>Lines: {lineCount}</span>
          {/if}
        </div>
        <button
          type="button"
          on:click={closeExpandedEditor}
          class="px-4 py-2 bg-oxford-blue text-white rounded-lg hover:bg-blue-700 transition-colors text-sm font-medium"
        >
          Done
        </button>
      </div>
    </div>
  </div>
{/if}

<style>
  .enhanced-textarea-wrapper {
    width: 100%;
  }
  
  /* Sync line numbers height with textarea */
  .line-numbers {
    max-height: 200px;
    overflow-y: hidden;
  }
  
  .line-numbers-expanded {
    min-width: 3rem;
  }
  
  /* Custom scrollbar for textarea */
  textarea::-webkit-scrollbar {
    width: 8px;
  }
  
  textarea::-webkit-scrollbar-track {
    background: #f1f1f1;
    border-radius: 4px;
  }
  
  textarea::-webkit-scrollbar-thumb {
    background: #c1c1c1;
    border-radius: 4px;
  }
  
  textarea::-webkit-scrollbar-thumb:hover {
    background: #a1a1a1;
  }
  
  /* Highlight styles from the highlightSyntax function are applied inline via @html */
</style>
