<!-- src/lib/components/Toast.svelte -->
<script lang="ts">
  import { onMount } from 'svelte';
  import { fade, fly } from 'svelte/transition';
  
  export let type: 'success' | 'error' | 'info' | 'warning' = 'info';
  export let message: string;
  export let duration: number = 5000; // Duration in milliseconds
  export let onClose: () => void;
  
  let timeoutId: NodeJS.Timeout;
  
  const typeStyles = {
    success: {
      bg: 'bg-green-50 dark:bg-green-900/20',
      border: 'border-green-200 dark:border-green-700',
      text: 'text-green-800 dark:text-green-100',
      icon: 'text-green-400 dark:text-green-300'
    },
    error: {
      bg: 'bg-red-50 dark:bg-red-900/20',
      border: 'border-red-200 dark:border-red-700',
      text: 'text-red-800 dark:text-red-100',
      icon: 'text-red-400 dark:text-red-300'
    },
    warning: {
      bg: 'bg-yellow-50 dark:bg-yellow-900/20',
      border: 'border-yellow-200 dark:border-yellow-700',
      text: 'text-yellow-800 dark:text-yellow-100',
      icon: 'text-yellow-400 dark:text-yellow-300'
    },
    info: {
      bg: 'bg-blue-50 dark:bg-blue-900/20',
      border: 'border-blue-200 dark:border-blue-700',
      text: 'text-blue-800 dark:text-blue-100',
      icon: 'text-blue-400 dark:text-blue-300'
    }
  };
  
  // Determine if this toast is persistent (won't auto-dismiss)
  const isPersistent = duration === Infinity;
  
  onMount(() => {
    // Only set up auto-dismiss for non-persistent toasts
    if (!isPersistent) {
      timeoutId = setTimeout(() => {
        onClose();
      }, duration);
      
      return () => {
        clearTimeout(timeoutId);
      };
    }
  });
  
  function handleClose() {
    clearTimeout(timeoutId);
    onClose();
  }
</script>

<style>
  /* Style for persistent toasts */
  .persistent-toast {
    border-width: 2px;
    box-shadow: 0 8px 16px rgba(0, 0, 0, 0.1);
  }
</style>

<div 
  class="{typeStyles[type].bg} border {typeStyles[type].border} rounded-md p-4 shadow-lg max-w-sm {duration === Infinity ? 'persistent-toast' : ''}"
  transition:fly={{ y: 24, duration: 300 }}
  role="alert"
>
  <div class="flex">
    <div class="flex-shrink-0">
      {#if type === 'success'}
        <svg class="h-5 w-5 {typeStyles[type].icon}" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor">
          <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clip-rule="evenodd" />
        </svg>
      {:else if type === 'error'}
        <svg class="h-5 w-5 {typeStyles[type].icon}" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor">
          <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clip-rule="evenodd" />
        </svg>
      {:else if type === 'warning'}
        <svg class="h-5 w-5 {typeStyles[type].icon}" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor">
          <path fill-rule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clip-rule="evenodd" />
        </svg>
      {:else}
        <svg class="h-5 w-5 {typeStyles[type].icon}" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor">
          <path fill-rule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clip-rule="evenodd" />
        </svg>
      {/if}
    </div>
    <div class="ml-3 flex-1">
      <p class="text-sm {typeStyles[type].text}">
        {message}
      </p>
    </div>
    <div class="ml-auto pl-3">
      <div class="-mx-1.5 -my-1.5">
        <button
          on:click={handleClose}
          class="inline-flex {typeStyles[type].bg} rounded-md p-1.5 {typeStyles[type].text} hover:bg-opacity-80 focus:outline-none"
        >
          <span class="sr-only">Dismiss</span>
          <svg class="h-5 w-5" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor">
            <path fill-rule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clip-rule="evenodd" />
          </svg>
        </button>
      </div>
    </div>
  </div>
</div>

<!-- Visual indicator for persistent toasts -->
{#if isPersistent}
  <div class="persistent-indicator mt-1 text-xs flex justify-end">
    <span class="{typeStyles[type].text} opacity-75 flex items-center">
      <svg class="h-3 w-3 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path>
      </svg>
      Click to dismiss
    </span>
  </div>
{/if}
