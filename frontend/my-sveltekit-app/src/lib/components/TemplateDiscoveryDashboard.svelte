<!-- Enhanced Template Discovery Dashboard - Phase 3 -->
<script lang="ts">
  import { onMount } from 'svelte';
  import { createUniversalLogger } from '$lib/logging/logger';
  import { enhancedTemplateRouter } from '$lib/services/enhancedTemplateRouter';
  import { toasts } from '$lib/stores/toast';

  const logger = createUniversalLogger('TemplateDiscoveryDashboard');

  // Discovery state
  let discoveryResult: any = null;
  let architecturalStatus: any = null;
  let templateComparison: any = null;
  let loading = true;
  let refreshing = false;
  let activeTab = 'templates';

  // Filter and search state
  let searchQuery = '';
  let statusFilter = 'all';
  let independenceFilter = 'all';

  onMount(() => {
    logger.componentMount('TemplateDiscoveryDashboard');
    loadDashboardData();
  });

  async function loadDashboardData() {
    logger.info('Loading dashboard data');
    
    try {
      loading = true;
      
      // Load all dashboard data concurrently
      const [discovery, architectural, comparison] = await Promise.all([
        enhancedTemplateRouter.discoverTemplates(),
        enhancedTemplateRouter.getArchitecturalStatus(),
        enhancedTemplateRouter.compareTemplates()
      ]);

      discoveryResult = discovery;
      architecturalStatus = architectural;
      templateComparison = comparison;

      logger.info('Dashboard data loaded successfully');
      logger.info(`Loaded ${discovery.templates?.length || 0} templates`);
      
    } catch (error) {
      logger.error('Failed to load dashboard data', error);
      toasts.error('Failed to load template discovery dashboard');
    } finally {
      loading = false;
    }
  }

  async function refreshDiscoveryCache() {
    logger.info('Refreshing discovery cache');
    
    try {
      refreshing = true;
      
      await enhancedTemplateRouter.refreshDiscoveryCache();
      toasts.success('Discovery cache refreshed successfully');
      
      // Reload dashboard data
      await loadDashboardData();
      
    } catch (error) {
      logger.error('Failed to refresh discovery cache', error);
      toasts.error('Failed to refresh discovery cache');
    } finally {
      refreshing = false;
    }
  }

  async function validateTemplateRegistration(templateId: string) {
    logger.info(`Validating template registration: ${templateId}`);
    
    try {
      const validation = await enhancedTemplateRouter.validateTemplateRegistration(templateId);
      
      const status = validation.validation_status;
      const message = `Template ${templateId} registration: ${status}`;
      
      if (status === 'passed') {
        toasts.success(message);
      } else if (status === 'incomplete') {
        toasts.warning(message);
      } else {
        toasts.error(message);
      }
      
      logger.info(`Template validation completed: ${templateId} - ${status}`);
      
    } catch (error) {
      logger.error(`Failed to validate template ${templateId}`, error);
      toasts.error(`Failed to validate template ${templateId}`);
    }
  }

  // Computed properties
  $: filteredTemplates = discoveryResult?.templates?.filter(template => {
    const matchesSearch = !searchQuery || 
      template.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      template.template_id.toLowerCase().includes(searchQuery.toLowerCase());
    
    const matchesStatus = statusFilter === 'all' || 
      template.capabilities?.full_stack_status === statusFilter;
    
    const matchesIndependence = independenceFilter === 'all' || 
      template.capabilities?.independence_level === independenceFilter;
    
    return matchesSearch && matchesStatus && matchesIndependence;
  }) || [];

  function getStatusBadgeClass(status: string): string {
    switch (status) {
      case 'complete': return 'status-complete';
      case 'partial': return 'status-partial';
      case 'backend_only': return 'status-backend-only';
      case 'frontend_only': return 'status-frontend-only';
      case 'basic': return 'status-basic';
      default: return 'status-unknown';
    }
  }

  function getIndependenceBadgeClass(level: string): string {
    switch (level) {
      case 'complete': return 'independence-complete';
      case 'partial': return 'independence-partial';
      case 'basic': return 'independence-basic';
      default: return 'independence-unknown';
    }
  }
</script>

<svelte:head>
  <title>Template Discovery Dashboard - AI Catalogue</title>
</svelte:head>

<div class="discovery-dashboard">
  <!-- Header -->
  <div class="dashboard-header">
    <div class="header-content">
      <h1><i class="fas fa-search"></i> Template Discovery Dashboard</h1>
      <p>Comprehensive template discovery and architectural analysis - Phase 3</p>
    </div>
    
    <div class="header-actions">
      <button 
        class="refresh-button" 
        on:click={refreshDiscoveryCache}
        disabled={refreshing}
      >
        <i class="fas {refreshing ? 'fa-spinner fa-spin' : 'fa-sync-alt'}"></i>
        {refreshing ? 'Refreshing...' : 'Refresh Cache'}
      </button>
    </div>
  </div>

  {#if loading}
    <div class="loading-state">
      <div class="spinner"></div>
      <p>Loading enhanced template discovery data...</p>
    </div>
  {:else}
    <!-- Dashboard Content -->
    <div class="dashboard-content">
      <div class="overview-section">
        <h2>Discovery Overview</h2>
        <div class="overview-stats">
          <div class="stat-card">
            <div class="stat-value">{discoveryResult?.templates?.length || 0}</div>
            <div class="stat-label">Templates Discovered</div>
          </div>
          <div class="stat-card">
            <div class="stat-value">{discoveryResult?.discovery_metadata?.discovery_statistics?.complete_templates || 0}</div>
            <div class="stat-label">Complete Templates</div>
          </div>
          <div class="stat-card">
            <div class="stat-value">{discoveryResult?.discovery_metadata?.discovery_statistics?.backend_endpoints_total || 0}</div>
            <div class="stat-label">Backend Endpoints</div>
          </div>
          <div class="stat-card">
            <div class="stat-value">{discoveryResult?.discovery_metadata?.discovery_statistics?.frontend_routes_total || 0}</div>
            <div class="stat-label">Frontend Routes</div>
          </div>
        </div>
      </div>

      <!-- Templates Grid -->
      <div class="templates-section">
        <div class="section-header">
          <h2>Enhanced Template Discovery</h2>
          <div class="filters">
            <input 
              type="text" 
              placeholder="Search templates..."
              bind:value={searchQuery}
              class="search-input"
            />
            <select bind:value={statusFilter} class="filter-select">
              <option value="all">All Status</option>
              <option value="complete">Complete</option>
              <option value="partial">Partial</option>
              <option value="basic">Basic</option>
            </select>
          </div>
        </div>

        <div class="templates-grid">
          {#each filteredTemplates as template}
            <div class="enhanced-template-card">
              <div class="template-header">
                <div class="template-icon">
                  <i class="fas {template.icon_class || 'fa-file-alt'}"></i>
                </div>
                <div class="template-info">
                  <h3>{template.name}</h3>
                  <div class="template-meta">
                    <span class="template-id">{template.template_id}</span>
                    <span class="template-version">v{template.version || '1.0.0'}</span>
                  </div>
                </div>
                <div class="status-badges">
                  <span class="status-badge {getStatusBadgeClass(template.capabilities?.full_stack_status)}">
                    {template.capabilities?.full_stack_status || 'unknown'}
                  </span>
                  <span class="independence-badge {getIndependenceBadgeClass(template.capabilities?.independence_level)}">
                    {template.capabilities?.independence_level || 'unknown'}
                  </span>
                </div>
              </div>

              <div class="template-description">
                <p>{template.description}</p>
              </div>

              <div class="capabilities-overview">
                <div class="capability-group">
                  <h4><i class="fas fa-server"></i> Backend</h4>
                  <div class="capability-metrics">
                    <span>Endpoints: {template.capabilities?.backend?.endpoints?.custom_views?.length || 0}</span>
                    <div class="capability-flags">
                      {#if template.capabilities?.backend?.has_custom_views}
                        <span class="flag active">Views</span>
                      {/if}
                      {#if template.capabilities?.backend?.has_custom_serializers}
                        <span class="flag active">Serializers</span>
                      {/if}
                      {#if template.capabilities?.backend?.has_custom_urls}
                        <span class="flag active">URLs</span>
                      {/if}
                    </div>
                  </div>
                </div>

                <div class="capability-group">
                  <h4><i class="fas fa-desktop"></i> Frontend</h4>
                  <div class="capability-metrics">
                    <span>Routes: {template.capabilities?.frontend?.routes?.route_files?.length || 0}</span>
                    <div class="capability-flags">
                      {#if template.capabilities?.frontend?.has_selection_page}
                        <span class="flag active">Selection</span>
                      {/if}
                      {#if template.capabilities?.frontend?.has_custom_components}
                        <span class="flag active">Components</span>
                      {/if}
                    </div>
                  </div>
                </div>
              </div>

              <div class="template-actions">
                <button 
                  class="action-btn primary"
                  on:click={() => enhancedTemplateRouter.navigateToTemplate(template.template_id)}
                >
                  <i class="fas fa-external-link-alt"></i>
                  Open Template
                </button>
                <button 
                  class="action-btn secondary"
                  on:click={() => validateTemplateRegistration(template.template_id)}
                >
                  <i class="fas fa-check-circle"></i>
                  Validate
                </button>
              </div>
            </div>
          {/each}
        </div>

        {#if filteredTemplates.length === 0}
          <div class="no-templates">
            <i class="fas fa-search"></i>
            <h3>No templates found</h3>
            <p>Try adjusting your search criteria or refresh the discovery cache.</p>
          </div>
        {/if}
      </div>

      <!-- Architectural Status -->
      {#if architecturalStatus}
        <div class="architectural-section">
          <h2>Architectural Status</h2>
          <div class="architectural-grid">
            <div class="status-card">
              <div class="status-icon system">
                <i class="fas fa-heartbeat"></i>
              </div>
              <div class="status-content">
                <h3>System Health</h3>
                <p class="status-value">{architecturalStatus.system_health || 'Unknown'}</p>
              </div>
            </div>

            <div class="status-card">
              <div class="status-icon independence">
                <i class="fas fa-puzzle-piece"></i>
              </div>
              <div class="status-content">
                <h3>Template Independence</h3>
                <p class="status-value">{architecturalStatus.template_independence ? 'Complete' : 'Partial'}</p>
              </div>
            </div>

            <div class="status-card">
              <div class="status-icon coverage">
                <i class="fas fa-layer-group"></i>
              </div>
              <div class="status-content">
                <h3>Full-Stack Coverage</h3>
                <p class="status-value">{Math.round((architecturalStatus.full_stack_coverage || 0) * 100)}%</p>
              </div>
            </div>
          </div>

          {#if architecturalStatus.system_recommendations?.length > 0}
            <div class="recommendations">
              <h3>System Recommendations</h3>
              <div class="recommendations-list">
                {#each architecturalStatus.system_recommendations as recommendation}
                  <div class="recommendation">
                    <i class="fas fa-lightbulb"></i>
                    <span>{recommendation}</span>
                  </div>
                {/each}
              </div>
            </div>
          {/if}
        </div>
      {/if}
    </div>
  {/if}
</div>

<style>
  .discovery-dashboard {
    min-height: 100vh;
    background: #f8fafc;
    padding: 24px;
  }

  .dashboard-header {
    background: linear-gradient(135deg, #002147 0%, #1e3a5f 100%);
    border-radius: 16px;
    padding: 32px;
    margin-bottom: 32px;
    color: white;
    display: flex;
    justify-content: space-between;
    align-items: center;
  }

  .header-content h1 {
    margin: 0 0 8px 0;
    font-size: 2rem;
    font-weight: 700;
    display: flex;
    align-items: center;
    gap: 12px;
  }

  .header-content p {
    margin: 0;
    opacity: 0.9;
    font-size: 1.125rem;
  }

  .refresh-button {
    background: rgba(255, 255, 255, 0.1);
    color: white;
    border: 2px solid rgba(255, 255, 255, 0.2);
    padding: 12px 24px;
    border-radius: 8px;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.2s ease;
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .refresh-button:hover:not(:disabled) {
    background: rgba(255, 255, 255, 0.2);
    border-color: rgba(255, 255, 255, 0.4);
  }

  .refresh-button:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }

  .loading-state {
    text-align: center;
    padding: 64px 32px;
    background: white;
    border-radius: 16px;
    box-shadow: 0 2px 12px rgba(0, 0, 0, 0.05);
  }

  .spinner {
    width: 32px;
    height: 32px;
    border: 3px solid #e5e7eb;
    border-top: 3px solid #002147;
    border-radius: 50%;
    animation: spin 1s linear infinite;
    margin: 0 auto 16px;
  }

  @keyframes spin {
    0% { transform: rotate(0deg); }
    100% { transform: rotate(360deg); }
  }

  .dashboard-content {
    display: flex;
    flex-direction: column;
    gap: 32px;
  }

  .overview-section {
    background: white;
    border-radius: 16px;
    padding: 32px;
    box-shadow: 0 2px 12px rgba(0, 0, 0, 0.05);
  }

  .overview-section h2 {
    margin: 0 0 24px 0;
    font-size: 1.5rem;
    font-weight: 700;
    color: #111827;
  }

  .overview-stats {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: 24px;
  }

  .stat-card {
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 12px;
    padding: 24px;
    text-align: center;
  }

  .stat-value {
    font-size: 2.5rem;
    font-weight: 700;
    color: #002147;
    margin-bottom: 8px;
  }

  .stat-label {
    font-size: 0.875rem;
    font-weight: 500;
    color: #6b7280;
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }

  .templates-section {
    background: white;
    border-radius: 16px;
    padding: 32px;
    box-shadow: 0 2px 12px rgba(0, 0, 0, 0.05);
  }

  .section-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 32px;
    gap: 24px;
  }

  .section-header h2 {
    margin: 0;
    font-size: 1.5rem;
    font-weight: 700;
    color: #111827;
  }

  .filters {
    display: flex;
    gap: 12px;
  }

  .search-input, .filter-select {
    padding: 8px 16px;
    border: 1px solid #e2e8f0;
    border-radius: 8px;
    font-size: 0.875rem;
    background: white;
  }

  .search-input {
    min-width: 200px;
  }

  .templates-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(400px, 1fr));
    gap: 24px;
  }

  .enhanced-template-card {
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 12px;
    padding: 24px;
    transition: all 0.2s ease;
  }

  .enhanced-template-card:hover {
    box-shadow: 0 8px 24px rgba(0, 0, 0, 0.1);
    transform: translateY(-2px);
  }

  .template-header {
    display: flex;
    align-items: flex-start;
    gap: 16px;
    margin-bottom: 16px;
  }

  .template-icon {
    width: 48px;
    height: 48px;
    background: linear-gradient(135deg, #002147, #1e3a5f);
    border-radius: 12px;
    display: flex;
    align-items: center;
    justify-content: center;
    color: white;
    font-size: 1.25rem;
    flex-shrink: 0;
  }

  .template-info {
    flex: 1;
    min-width: 0;
  }

  .template-info h3 {
    margin: 0 0 8px 0;
    font-size: 1.125rem;
    font-weight: 600;
    color: #111827;
  }

  .template-meta {
    display: flex;
    gap: 12px;
    align-items: center;
  }

  .template-id {
    font-size: 0.75rem;
    color: #6b7280;
    font-family: monospace;
    background: #f1f5f9;
    padding: 2px 6px;
    border-radius: 4px;
  }

  .template-version {
    font-size: 0.75rem;
    color: #10b981;
    font-weight: 600;
  }

  .status-badges {
    display: flex;
    flex-direction: column;
    gap: 6px;
    align-items: flex-end;
  }

  .status-badge, .independence-badge {
    padding: 4px 8px;
    border-radius: 6px;
    font-size: 0.75rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }

  .status-complete { background: #dcfce7; color: #16a34a; }
  .status-partial { background: #fef3c7; color: #d97706; }
  .status-backend-only { background: #e0f2fe; color: #0277bd; }
  .status-frontend-only { background: #f3e8ff; color: #7c3aed; }
  .status-basic { background: #f1f5f9; color: #64748b; }
  .status-unknown { background: #fef2f2; color: #dc2626; }

  .independence-complete { background: #dcfce7; color: #16a34a; }
  .independence-partial { background: #fef3c7; color: #d97706; }
  .independence-basic { background: #f1f5f9; color: #64748b; }
  .independence-unknown { background: #fef2f2; color: #dc2626; }

  .template-description {
    margin-bottom: 20px;
  }

  .template-description p {
    margin: 0;
    color: #374151;
    font-size: 0.875rem;
    line-height: 1.5;
  }

  .capabilities-overview {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 20px;
    margin-bottom: 24px;
  }

  .capability-group h4 {
    margin: 0 0 12px 0;
    font-size: 0.875rem;
    font-weight: 600;
    color: #374151;
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .capability-metrics {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .capability-metrics > span {
    font-size: 0.75rem;
    color: #6b7280;
    font-family: monospace;
  }

  .capability-flags {
    display: flex;
    gap: 6px;
    flex-wrap: wrap;
  }

  .flag {
    padding: 2px 6px;
    border-radius: 4px;
    font-size: 0.625rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    background: #f1f5f9;
    color: #64748b;
  }

  .flag.active {
    background: #dcfce7;
    color: #16a34a;
  }

  .template-actions {
    display: flex;
    gap: 12px;
  }

  .action-btn {
    flex: 1;
    padding: 10px 16px;
    border: none;
    border-radius: 8px;
    font-weight: 500;
    cursor: pointer;
    transition: all 0.2s ease;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 6px;
    font-size: 0.875rem;
  }

  .action-btn.primary {
    background: #002147;
    color: white;
  }

  .action-btn.primary:hover {
    background: #1e3a5f;
    transform: translateY(-1px);
  }

  .action-btn.secondary {
    background: #f8fafc;
    color: #64748b;
    border: 1px solid #e2e8f0;
  }

  .action-btn.secondary:hover {
    background: #f1f5f9;
    color: #475569;
  }

  .no-templates {
    text-align: center;
    padding: 64px 32px;
    color: #64748b;
  }

  .no-templates i {
    font-size: 3rem;
    margin-bottom: 16px;
    color: #cbd5e1;
  }

  .no-templates h3 {
    margin: 0 0 8px 0;
    color: #374151;
  }

  .architectural-section {
    background: white;
    border-radius: 16px;
    padding: 32px;
    box-shadow: 0 2px 12px rgba(0, 0, 0, 0.05);
  }

  .architectural-section h2 {
    margin: 0 0 24px 0;
    font-size: 1.5rem;
    font-weight: 700;
    color: #111827;
  }

  .architectural-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
    gap: 24px;
    margin-bottom: 32px;
  }

  .status-card {
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 12px;
    padding: 24px;
    display: flex;
    align-items: center;
    gap: 16px;
  }

  .status-icon {
    width: 48px;
    height: 48px;
    border-radius: 12px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 1.25rem;
    color: white;
  }

  .status-icon.system { background: linear-gradient(135deg, #16a34a, #22c55e); }
  .status-icon.independence { background: linear-gradient(135deg, #7c3aed, #a855f7); }
  .status-icon.coverage { background: linear-gradient(135deg, #0277bd, #29b6f6); }

  .status-content h3 {
    margin: 0 0 4px 0;
    font-size: 0.875rem;
    font-weight: 600;
    color: #6b7280;
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }

  .status-value {
    margin: 0;
    font-size: 1.25rem;
    font-weight: 700;
    color: #111827;
  }

  .recommendations {
    background: #fffbeb;
    border: 1px solid #fbbf24;
    border-radius: 12px;
    padding: 24px;
  }

  .recommendations h3 {
    margin: 0 0 16px 0;
    font-size: 1.125rem;
    font-weight: 600;
    color: #92400e;
  }

  .recommendations-list {
    display: flex;
    flex-direction: column;
    gap: 12px;
  }

  .recommendation {
    display: flex;
    align-items: center;
    gap: 12px;
    font-size: 0.875rem;
    color: #92400e;
  }

  .recommendation i {
    color: #f59e0b;
    font-size: 1rem;
  }

  /* Responsive Design */
  @media (max-width: 768px) {
    .discovery-dashboard {
      padding: 16px;
    }

    .dashboard-header {
      flex-direction: column;
      gap: 16px;
      text-align: center;
    }

    .section-header {
      flex-direction: column;
      align-items: stretch;
    }

    .filters {
      flex-direction: column;
    }

    .templates-grid {
      grid-template-columns: 1fr;
    }

    .capabilities-overview {
      grid-template-columns: 1fr;
    }

    .template-actions {
      flex-direction: column;
    }

    .overview-stats {
      grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
    }

    .architectural-grid {
      grid-template-columns: 1fr;
    }
  }
</style>
