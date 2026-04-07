<!-- src/routes/features/+layout.svelte -->
<script lang="ts">
  import { page } from '$app/stores';
</script>

<svelte:head>
  {#if $page.url.pathname.startsWith('/features/intellidoc')}
    <title>IntelliDoc Projects - AI Catalogue</title>
  {:else}
    <title>AI Catalogue</title>
  {/if}
</svelte:head>

<div class="min-h-screen bg-gray-100 w-full">
  <main class="w-full min-h-screen">
    <slot />
  </main>
</div>
