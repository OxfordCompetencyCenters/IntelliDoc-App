<!-- MultiPageNavigation.svelte -->
<script lang="ts">
  import { createEventDispatcher } from 'svelte';
  import { getProjectPages, getProjectPageContent } from '$lib/services/api';
  
  export let project: any;
  export let currentPage: number = 1;
  
  const dispatch = createEventDispatcher();
  
  // Navigation state based on cloned project configuration
  $: hasNavigation = project?.has_navigation === true;
  $: totalPages = project?.total_pages || 1;
  $: navigationPages = project?.navigation_pages || [];
  
  // Get current page configuration
  $: currentPageConfig = getCurrentPageConfig();
  
  function getCurrentPageConfig() {
    if (!hasNavigation || !navigationPages.length) {
      return { 
        page_number: 1,
        name: 'Main',
        short_name: 'Main',
        icon: 'fa-home',
        features: ['upload', 'processing', 'analysis'] 
      };
    }
    
    return navigationPages.find(p => p.page_number === currentPage) || {
      page_number: currentPage,
      name: `Page ${currentPage}`,
      short_name: `P${currentPage}`,
      icon: 'fa-file',
      features: ['upload']
    };
  }
  
  function goToPage(pageNumber: number) {
    if (pageNumber >= 1 && pageNumber <= totalPages && pageNumber !== currentPage) {
      dispatch('pageChange', { 
        page: pageNumber, 
        config: navigationPages.find(p => p.page_number === pageNumber) 
      });
    }
  }
  
  function goToNextPage() {
    if (currentPage < totalPages) {
      goToPage(currentPage + 1);
    }
  }
  
  function goToPreviousPage() {
    if (currentPage > 1) {
      goToPage(currentPage - 1);
    }
  }
  
  function getFeatureIcon(feature: string): string {
    const icons: { [key: string]: string } = {
      'upload': 'fa-upload',
      'processing': 'fa-cogs',
      'analysis': 'fa-chart-line',
      'search': 'fa-search',
      'documents': 'fa-file-alt',
      'dashboard': 'fa-tachometer-alt',
      'settings': 'fa-cog',
      'reports': 'fa-chart-bar',
      'collaboration': 'fa-users',
      'export': 'fa-download'
    };
    return icons[feature] || 'fa-circle';
  }
  
  function getFeatureName(feature: string): string {
    const names: { [key: string]: string } = {
      'upload': 'Document Upload',
      'processing': 'AI Processing',
      'analysis': 'Analysis Tools',
      'search': 'Search & Query',
      'documents': 'Document Manager',
      'dashboard': 'Analytics Dashboard',
      'settings': 'Configuration',
      'reports': 'Report Generation',
      'collaboration': 'Team Collaboration',
      'export': 'Data Export'
    };
    return names[feature] || feature.charAt(0).toUpperCase() + feature.slice(1);
  }
  
  // Keyboard navigation
  function handleKeydown(event: KeyboardEvent) {
    if (event.key === 'ArrowLeft') {
      goToPreviousPage();
    } else if (event.key === 'ArrowRight') {
      goToNextPage();
    }
  }
</script>

<svelte:window on:keydown={handleKeydown} />

{#if hasNavigation && totalPages > 1}
  <div class="multi-page-navigation">
    <div class="nav-header">
      <div class="nav-title">
        <i class="fas fa-sitemap"></i>
        Project Navigation
      </div>
      <div class="nav-info">
        <span class="page-counter">{currentPage} / {totalPages}</span>
      </div>
    </div>
    
    <div class="nav-content">
      <!-- Page Tabs -->
      <div class="page-tabs">
        {#each navigationPages as page}
          <button 
            class="page-tab"
            class:active={page.page_number === currentPage}
            on:click={() => goToPage(page.page_number)}
            title={page.name}
          >
            <div class="tab-icon">
              <i class="fas {page.icon}"></i>
            </div>
            <div class="tab-content">
              <div class="tab-name">{page.short_name}</div>
              <div class="tab-features">
                {#each page.features.slice(0, 2) as feature}
                  <span class="feature-indicator">{feature}</span>
                {/each}
                {#if page.features.length > 2}
                  <span class="feature-indicator more">+{page.features.length - 2}</span>
                {/if}
              </div>
            </div>
          </button>
        {/each}
      </div>
      
      <!-- Navigation Controls -->
      <div class="nav-controls">
        <button 
          class="nav-btn prev"
          on:click={goToPreviousPage}
          disabled={currentPage === 1}
          title="Previous Page (←)"
        >
          <i class="fas fa-chevron-left"></i>
          <span>Previous</span>
        </button>
        
        <div class="page-indicator">
          <span class="current-page-name">{currentPageConfig.name}</span>
          <div class="page-dots">
            {#each Array(totalPages) as _, i}
              <button 
                class="page-dot"
                class:active={i + 1 === currentPage}
                on:click={() => goToPage(i + 1)}
                title="Go to page {i + 1}"
              >
                {i + 1}
              </button>
            {/each}
          </div>
        </div>
        
        <button 
          class="nav-btn next"
          on:click={goToNextPage}
          disabled={currentPage === totalPages}
          title="Next Page (→)"
        >
          <span>Next</span>
          <i class="fas fa-chevron-right"></i>
        </button>
      </div>
    </div>
    
    <!-- Current Page Features -->
    <div class="current-page-features">
      <div class="features-header">
        <i class="fas {currentPageConfig.icon}"></i>
        <span>Available Features</span>
      </div>
      <div class="features-list">
        {#each currentPageConfig.features as feature}
          <div class="feature-item">
            <i class="fas {getFeatureIcon(feature)}"></i>
            <span>{getFeatureName(feature)}</span>
          </div>
        {/each}
      </div>
    </div>
  </div>
{/if}

<style>
  .multi-page-navigation {
    background: white;
    border-radius: 12px;
    box-shadow: 0 2px 12px rgba(0, 0, 0, 0.08);
    margin-bottom: 24px;
    overflow: hidden;
  }
  
  .nav-header {
    background: linear-gradient(135deg, #002147, #1e3a5f);
    color: white;
    padding: 16px 24px;
    display: flex;
    justify-content: space-between;
    align-items: center;
  }
  
  .nav-title {
    font-size: 1.125rem;
    font-weight: 600;
    display: flex;
    align-items: center;
    gap: 8px;
  }
  
  .nav-info {
    display: flex;
    align-items: center;
    gap: 12px;
  }
  
  .page-counter {
    background: rgba(255, 255, 255, 0.2);
    padding: 4px 12px;
    border-radius: 20px;
    font-size: 0.875rem;
    font-weight: 500;
  }
  
  .nav-content {
    padding: 24px;
  }
  
  .page-tabs {
    display: flex;
    gap: 8px;
    margin-bottom: 24px;
    overflow-x: auto;
    padding-bottom: 8px;
  }
  
  .page-tab {
    background: #f8fafc;
    border: 2px solid #e2e8f0;
    border-radius: 8px;
    padding: 12px 16px;
    cursor: pointer;
    transition: all 0.2s ease;
    display: flex;
    align-items: center;
    gap: 12px;
    min-width: 140px;
  }
  
  .page-tab:hover {
    background: #f1f5f9;
    border-color: #cbd5e1;
  }
  
  .page-tab.active {
    background: #eff6ff;
    border-color: #3b82f6;
    box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
  }
  
  .tab-icon {
    width: 32px;
    height: 32px;
    background: #e2e8f0;
    border-radius: 8px;
    display: flex;
    align-items: center;
    justify-content: center;
    color: #64748b;
    font-size: 0.875rem;
  }
  
  .page-tab.active .tab-icon {
    background: #3b82f6;
    color: white;
  }
  
  .tab-content {
    flex: 1;
    text-align: left;
  }
  
  .tab-name {
    font-weight: 500;
    color: #1e293b;
    margin-bottom: 4px;
    font-size: 0.875rem;
  }
  
  .tab-features {
    display: flex;
    gap: 4px;
    flex-wrap: wrap;
  }
  
  .feature-indicator {
    background: #f1f5f9;
    color: #64748b;
    padding: 2px 6px;
    border-radius: 4px;
    font-size: 0.75rem;
    font-weight: 500;
  }
  
  .feature-indicator.more {
    background: #e2e8f0;
    color: #475569;
  }
  
  .nav-controls {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 24px;
    padding: 16px;
    background: #f8fafc;
    border-radius: 8px;
  }
  
  .nav-btn {
    padding: 8px 16px;
    border: 1px solid #e2e8f0;
    border-radius: 6px;
    background: white;
    color: #64748b;
    font-size: 0.875rem;
    cursor: pointer;
    transition: all 0.2s ease;
    display: flex;
    align-items: center;
    gap: 6px;
  }
  
  .nav-btn:hover:not(:disabled) {
    background: #f1f5f9;
    color: #475569;
    border-color: #cbd5e1;
  }
  
  .nav-btn:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
  
  .page-indicator {
    text-align: center;
  }
  
  .current-page-name {
    display: block;
    font-weight: 600;
    color: #1e293b;
    margin-bottom: 8px;
  }
  
  .page-dots {
    display: flex;
    gap: 4px;
    justify-content: center;
  }
  
  .page-dot {
    width: 32px;
    height: 32px;
    border: 1px solid #e2e8f0;
    border-radius: 6px;
    background: white;
    color: #64748b;
    font-size: 0.75rem;
    cursor: pointer;
    transition: all 0.2s ease;
    display: flex;
    align-items: center;
    justify-content: center;
  }
  
  .page-dot:hover {
    background: #f1f5f9;
    border-color: #cbd5e1;
  }
  
  .page-dot.active {
    background: #3b82f6;
    color: white;
    border-color: #3b82f6;
  }
  
  .current-page-features {
    border-top: 1px solid #e2e8f0;
    padding: 20px 24px;
    background: #f8fafc;
  }
  
  .features-header {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 12px;
    font-weight: 600;
    color: #374151;
  }
  
  .features-list {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: 8px;
  }
  
  .feature-item {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 8px 12px;
    background: white;
    border: 1px solid #e2e8f0;
    border-radius: 6px;
    font-size: 0.875rem;
    color: #64748b;
  }
  
  .feature-item i {
    color: #002147;
    width: 16px;
    text-align: center;
  }
  
  @media (max-width: 768px) {
    .nav-header {
      flex-direction: column;
      gap: 12px;
      text-align: center;
    }
    
    .page-tabs {
      flex-direction: column;
    }
    
    .page-tab {
      min-width: auto;
    }
    
    .nav-controls {
      flex-direction: column;
      gap: 16px;
    }
    
    .nav-btn {
      width: 100%;
      justify-content: center;
    }
    
    .features-list {
      grid-template-columns: 1fr;
    }
  }
</style>
