<!-- src/lib/components/UniversalThemeProvider.svelte -->
<script lang="ts">
  import '../styles/universal.css';
</script>

<!-- This component provides universal theming to all child components -->
<div class="universal-theme-provider">
  <slot />
</div>

<style>
  .universal-theme-provider {
    /* Ensure all children inherit the universal theme */
    background-color: var(--theme-bg-primary);
    color: var(--theme-text-primary);
    min-height: 100vh;
    transition: background-color 0.3s ease, color 0.3s ease;
  }
  
  /* Global overrides for universal theming */
  .universal-theme-provider :global(*) {
    transition: background-color 0.3s ease, color 0.3s ease, border-color 0.3s ease;
  }
  
  /* Auto-apply universal classes to common elements */
  .universal-theme-provider :global(main) {
    background-color: var(--theme-bg-primary);
    color: var(--theme-text-primary);
  }
  
  .universal-theme-provider :global(.container) {
    background-color: var(--theme-bg-primary);
    color: var(--theme-text-primary);
  }
  
  .universal-theme-provider :global(h1) {
    color: var(--theme-text-primary);
  }
  
  .universal-theme-provider :global(h2) {
    color: var(--theme-text-primary);
  }
  
  .universal-theme-provider :global(h3) {
    color: var(--theme-text-primary);
  }
  
  .universal-theme-provider :global(p) {
    color: var(--theme-text-primary);
  }
  
  .universal-theme-provider :global(span) {
    color: var(--theme-text-primary);
  }
  
  .universal-theme-provider :global(div) {
    color: var(--theme-text-primary);
  }
  
  /* Auto-style cards */
  .universal-theme-provider :global(.card) {
    background-color: var(--theme-bg-card);
    border: 1px solid var(--theme-border-primary);
    box-shadow: var(--theme-shadow-md);
  }
  
  /* Auto-style forms */
  .universal-theme-provider :global(input) {
    background-color: var(--theme-bg-card);
    color: var(--theme-text-primary);
    border: 1px solid var(--theme-border-primary);
  }
  
  .universal-theme-provider :global(textarea) {
    background-color: var(--theme-bg-card);
    color: var(--theme-text-primary);
    border: 1px solid var(--theme-border-primary);
  }
  
  .universal-theme-provider :global(select) {
    background-color: var(--theme-bg-card);
    color: var(--theme-text-primary);
    border: 1px solid var(--theme-border-primary);
  }
</style>
