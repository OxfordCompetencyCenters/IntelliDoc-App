<!-- src/lib/components/ToastContainer.svelte -->
<script lang="ts">
  import { toasts } from '$lib/stores/toast';
  import Toast from './Toast.svelte';
</script>

<div class="fixed top-4 right-4 z-50 space-y-2">
  {#each $toasts as toast (toast.id)}
    <Toast 
      type={toast.type} 
      message={toast.message} 
      duration={toast.duration || 5000}
      onClose={() => toasts.remove(toast.id)} 
    />
  {/each}
</div>
