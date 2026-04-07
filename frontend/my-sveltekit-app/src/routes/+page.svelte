<!-- src/routes/+page.svelte — Desktop: redirect straight to IntelliDoc -->
<script lang="ts">
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';

  onMount(() => {
    goto('/features/intellidoc', { replaceState: true });
  });
</script>

<div class="min-h-screen flex items-center justify-center bg-gradient-to-br from-oxford-blue to-oxford-700">
  <div class="text-center text-white">
    <div class="animate-spin rounded-full h-10 w-10 border-b-2 border-white mx-auto mb-4"></div>
    <p class="text-lg">Loading AICC IntelliDoc...</p>
  </div>
</div>
