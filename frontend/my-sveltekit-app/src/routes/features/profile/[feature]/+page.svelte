<!-- src/routes/features/[feature]/+page.svelte -->
<script lang="ts">
  import { page } from '$app/stores';
  
  // Extract feature name from the URL
  $: featureName = $page.params.feature.charAt(0).toUpperCase() + $page.params.feature.slice(1);
</script>

<svelte:head>
  <title>{featureName}</title>
</svelte:head>

<div class="mb-6">
  <h1 class="text-3xl font-bold text-gray-900">
    {featureName}
  </h1>
</div>

<div class="bg-white shadow overflow-hidden sm:rounded-lg p-6">
  <h2 class="text-xl font-semibold mb-4">{featureName} Feature</h2>
  <p class="mb-4">This is a placeholder for the {featureName} feature.</p>
  <p>Feature content will be implemented in a future update.</p>
  
  <div class="mt-6 p-4 bg-gray-50 rounded border border-gray-200">
    <h3 class="text-lg font-medium mb-2">Feature Details</h3>
    <ul class="list-disc list-inside space-y-1 text-gray-600">
      <li>This is a sample {featureName} page</li>
      <li>URL path: {$page.url.pathname}</li>
      <li>Feature ID: {$page.params.feature}</li>
    </ul>
  </div>
</div>
