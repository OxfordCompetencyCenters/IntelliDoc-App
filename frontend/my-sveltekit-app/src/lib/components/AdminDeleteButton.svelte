<!-- Admin-Only Delete Button Component -->
<!-- src/lib/components/AdminDeleteButton.svelte -->
<script lang="ts">
  import { isAdmin } from '$lib/stores/auth';
  import { createEventDispatcher } from 'svelte';
  
  export let title: string = 'Delete (Admin only)';
  export let confirmMessage: string = 'Are you sure you want to delete this item?';
  export let size: 'small' | 'medium' | 'large' = 'medium';
  export let variant: 'danger' | 'warning' = 'danger';
  export let disabled: boolean = false;
  export let requireConfirmation: boolean = true;
  export let itemName: string = ''; // For more specific confirmation messages
  
  const dispatch = createEventDispatcher();
  
  function handleDelete() {
    if (disabled) return;
    
    const message = itemName 
      ? `Are you sure you want to delete "${itemName}"?`
      : confirmMessage;
    
    if (!requireConfirmation || confirm(message)) {
      dispatch('delete');
    }
  }
  
  $: buttonClass = `admin-delete-button ${variant} ${size} ${disabled ? 'disabled' : ''}`;
</script>

{#if $isAdmin}
  <button 
    class={buttonClass}
    on:click={handleDelete}
    {title}
    {disabled}
  >
    <i class="fas fa-trash"></i>
    <slot>Delete</slot>
  </button>
{/if}

<style>
  .admin-delete-button {
    display: inline-flex;
    align-items: center;
    gap: 0.375rem;
    border: none;
    border-radius: 0.375rem;
    font-weight: 500;
    cursor: pointer;
    transition: all 0.2s ease-in-out;
    font-family: inherit;
  }
  
  /* Sizes */
  .admin-delete-button.small {
    padding: 0.25rem 0.5rem;
    font-size: 0.75rem;
  }
  
  .admin-delete-button.medium {
    padding: 0.5rem 0.75rem;
    font-size: 0.875rem;
  }
  
  .admin-delete-button.large {
    padding: 0.75rem 1rem;
    font-size: 1rem;
  }
  
  /* Variants */
  .admin-delete-button.danger {
    background-color: #fee2e2;
    color: #dc2626;
    border: 1px solid #fecaca;
  }
  
  .admin-delete-button.danger:hover:not(.disabled) {
    background-color: #fecaca;
    color: #b91c1c;
    border-color: #f87171;
    transform: translateY(-1px);
    box-shadow: 0 4px 6px -1px rgba(239, 68, 68, 0.2);
  }
  
  .admin-delete-button.warning {
    background-color: #fef3c7;
    color: #d97706;
    border: 1px solid #fed7aa;
  }
  
  .admin-delete-button.warning:hover:not(.disabled) {
    background-color: #fed7aa;
    color: #c2410c;
    border-color: #fdba74;
    transform: translateY(-1px);
    box-shadow: 0 4px 6px -1px rgba(245, 158, 11, 0.2);
  }
  
  .admin-delete-button.disabled {
    opacity: 0.5;
    cursor: not-allowed;
    transform: none !important;
    box-shadow: none !important;
  }
  
  .admin-delete-button:active:not(.disabled) {
    transform: translateY(0);
  }
  
  /* Icon styling */
  .admin-delete-button i {
    font-size: 0.875em;
  }
  
  .admin-delete-button.small i {
    font-size: 0.75em;
  }
  
  .admin-delete-button.large i {
    font-size: 1em;
  }
</style>