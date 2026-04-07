<!-- src/routes/+layout.svelte -->
<script lang="ts">
  import "../app.css";
  import ToastContainer from '$lib/components/ToastContainer.svelte';
  import Navigation from '$lib/components/Navigation.svelte';
  import UniversalThemeProvider from '$lib/components/UniversalThemeProvider.svelte';
</script>

<UniversalThemeProvider>
  <Navigation />
  <ToastContainer />
  <slot />
</UniversalThemeProvider>
