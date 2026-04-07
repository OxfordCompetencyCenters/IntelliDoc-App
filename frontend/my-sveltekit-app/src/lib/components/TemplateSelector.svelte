<script lang="ts">
  import { onMount, createEventDispatcher } from 'svelte';
  import templateService from '$lib/services/templateService';
  import { toasts } from '$lib/stores/toast';
  import type { TemplateInfo, CompleteTemplateConfig } from '$lib/types';
  
  const dispatch = createEventDispatcher();
  
  // Props
  export let selectedTemplate: TemplateInfo | null = null;
  export let showConfiguration = false;
  export let compact = false;
  export let smallGrid = false; // New small grid mode
  
  // State
  let templates: TemplateInfo[] = [];
  let loading = true;
  let templateConfiguration: CompleteTemplateConfig | null = null;
  let loadingConfig = false;
  let showDropdown = false;
  
  onMount(() => {
    loadTemplates();
  });

  async function loadTemplates() {
    try {
      loading = true;
      templates = await templateService.loadTemplates();
      templates = templates.filter(template => template.id && template.template_type);
      // Auto-select if only one template available
      if (templates.length === 1 && !selectedTemplate) {
        await selectTemplate(templates[0]);
      }
    } catch (error) {
      console.error('Failed to load templates:', error);
      toasts.error('Failed to load project templates');
    } finally {
      loading = false;
    }
  }
  
  async function selectTemplate(template: TemplateInfo) {
    if (!template?.id) return;
    
    try {
      loadingConfig = true;
      templateConfiguration = await templateService.getTemplateConfiguration(template.id);
      selectedTemplate = template;
      showConfiguration = true;
      showDropdown = false;
      
      dispatch('templateSelected', {
        template: selectedTemplate,
        configuration: templateConfiguration
      });
    } catch (error) {
      console.error('Failed to load template configuration:', error);
      toasts.error('Failed to load template configuration');
    } finally {
      loadingConfig = false;
    }
  }
  
  function toggleDropdown() {
    if (compact) {
      showDropdown = !showDropdown;
    }
  }
</script>

<div class="template-selector {compact ? 'compact' : ''} {smallGrid ? 'small-grid' : ''}">
  {#if loading}
    <div class="loading-state">
      <div class="spinner"></div>
      <p>Loading templates...</p>
    </div>
  {:else if templates.length === 0}
    <div class="empty-state">
      <p>No templates available</p>
    </div>
  {:else if compact}
    <!-- Compact dropdown view -->
    <div class="template-dropdown">
      <button 
        class="dropdown-trigger {selectedTemplate ? 'selected' : ''}"
        on:click={toggleDropdown}
      >
        {#if selectedTemplate}
          <div class="selected-template">
            <i class="fas {selectedTemplate.icon_class}"></i>
            <span>{selectedTemplate.name}</span>
          </div>
        {:else}
          <span class="placeholder">Select a template...</span>
        {/if}
        <i class="fas fa-chevron-down {showDropdown ? 'rotated' : ''}"></i>
      </button>
      
      {#if showDropdown}
        <div class="dropdown-options">
          {#each templates as template}
            <div 
              class="template-option {selectedTemplate?.id === template.id ? 'selected' : ''}"
              on:click={() => selectTemplate(template)}
              role="button"
              tabindex="0"
            >
              <div class="option-icon">
                <i class="fas {template.icon_class}"></i>
              </div>
              <div class="option-info">
                <span class="option-name">{template.name}</span>
                <span class="option-type">{template.template_type}</span>
              </div>
              {#if selectedTemplate?.id === template.id}
                <i class="fas fa-check-circle selected-check"></i>
              {/if}
            </div>
          {/each}
        </div>
      {/if}
    </div>
  {:else}
    <!-- Full grid view -->
    <div class="templates-grid">
      {#each templates as template}
        <div 
          class="template-card {selectedTemplate?.id === template.id ? 'selected' : ''}"
          on:click={() => selectTemplate(template)}
          role="button"
          tabindex="0"
        >
          <div class="card-header">
            <div class="template-icon">
              <i class="fas {template.icon_class}"></i>
            </div>
            {#if selectedTemplate?.id === template.id}
              <div class="selected-indicator">
                <i class="fas fa-check-circle"></i>
              </div>
            {/if}
          </div>
          
          <div class="template-info">
            <h4 class="template-name">{template.name}</h4>
            <p class="template-description">{template.description}</p>
          </div>
        </div>
      {/each}
    </div>
  {/if}
  
  {#if loadingConfig}
    <div class="config-loading">
      <div class="spinner small"></div>
      <span>Loading configuration...</span>
    </div>
  {/if}
</div>

<style>
  .template-selector {
    background: white;
    border-radius: 6px;
    overflow: visible;
  }
  
  .template-selector.small-grid {
    border: 1px solid #e5e7eb;
    border-radius: 6px;
    background: white;
  }
  
  .template-selector.small-grid .templates-container {
    padding: 12px;
  }
  
  .template-selector.small-grid .templates-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
    gap: 8px;
    padding: 0;
  }
  
  .template-selector.small-grid .template-card {
    background: white;
    border: 1px solid #e5e7eb;
    border-radius: 6px;
    padding: 10px;
    cursor: pointer;
    transition: all 0.2s ease;
    position: relative;
  }
  
  .template-selector.small-grid .template-card:hover {
    border-color: #002147;
    box-shadow: 0 2px 6px rgba(0, 33, 71, 0.1);
  }
  
  .template-selector.small-grid .template-card.selected {
    border-color: #002147;
    background: #f0f9ff;
    box-shadow: 0 2px 8px rgba(0, 33, 71, 0.15);
  }
  
  .template-selector.small-grid .card-header {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    margin-bottom: 8px;
  }
  
  .template-selector.small-grid .template-icon {
    width: 28px;
    height: 28px;
    background: linear-gradient(135deg, #002147, #1e3a5f);
    border-radius: 6px;
    display: flex;
    align-items: center;
    justify-content: center;
    color: white;
    font-size: 0.75rem;
  }
  
  .template-selector.small-grid .selected-indicator {
    color: #10b981;
    font-size: 0.875rem;
  }
  
  .template-selector.small-grid .template-info {
    margin-bottom: 0;
  }
  
  .template-selector.small-grid .template-name {
    margin: 0 0 3px 0;
    font-size: 0.75rem;
    font-weight: 600;
    color: #111827;
    line-height: 1.2;
  }
  
  .template-selector.small-grid .template-description {
    margin: 0;
    font-size: 0.625rem;
    color: #6b7280;
    line-height: 1.3;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
  }
  
  .loading-state, .empty-state {
    padding: 16px;
    text-align: center;
    color: #6b7280;
    font-size: 0.875rem;
  }
  
  .spinner {
    width: 20px;
    height: 20px;
    border: 2px solid #e5e7eb;
    border-top: 2px solid #002147;
    border-radius: 50%;
    animation: spin 1s linear infinite;
    margin: 0 auto 8px;
  }
  
  .spinner.small {
    width: 16px;
    height: 16px;
  }
  
  @keyframes spin {
    0% { transform: rotate(0deg); }
    100% { transform: rotate(360deg); }
  }
  
  /* Compact dropdown styles */
  .template-dropdown {
    position: relative;
  }
  
  .dropdown-trigger {
    width: 100%;
    padding: 9px 12px;
    border: none;
    background: white;
    border-radius: 6px;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: space-between;
    transition: all 0.2s ease;
    text-align: left;
    font-size: 0.875rem;
  }
  
  .dropdown-trigger:hover {
    background: #f9fafb;
  }
  
  .dropdown-trigger.selected {
    background: #f0f9ff;
  }
  
  .selected-template {
    display: flex;
    align-items: center;
    gap: 8px;
    color: #374151;
  }
  
  .selected-template i {
    color: #002147;
  }
  
  .placeholder {
    color: #9ca3af;
    font-size: 0.875rem;
  }
  
  .fa-chevron-down {
    transition: transform 0.2s ease;
    color: #6b7280;
  }
  
  .fa-chevron-down.rotated {
    transform: rotate(180deg);
  }
  
  .dropdown-options {
    position: absolute;
    top: 100%;
    left: -1px;
    right: -1px;
    background: white;
    border: 1px solid #d1d5db;
    border-top: none;
    border-radius: 0 0 6px 6px;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
    z-index: 1000;
    max-height: 250px;
    overflow-y: auto;
  }
  
  .template-option {
    padding: 10px 12px;
    display: flex;
    align-items: center;
    gap: 10px;
    cursor: pointer;
    transition: background-color 0.2s ease;
    border-bottom: 1px solid #f3f4f6;
  }
  
  .template-option:last-child {
    border-bottom: none;
  }
  
  .template-option:hover {
    background: #f8fafc;
  }
  
  .template-option.selected {
    background: #eff6ff;
  }
  
  .option-icon {
    width: 28px;
    height: 28px;
    background: linear-gradient(135deg, #002147, #1e3a5f);
    border-radius: 5px;
    display: flex;
    align-items: center;
    justify-content: center;
    color: white;
    font-size: 0.75rem;
    flex-shrink: 0;
  }
  
  .option-info {
    flex: 1;
    min-width: 0;
  }
  
  .option-name {
    font-weight: 500;
    color: #111827;
    font-size: 0.8125rem;
    display: block;
    margin-bottom: 2px;
  }
  
  .option-type {
    color: #6b7280;
    font-size: 0.6875rem;
    text-transform: uppercase;
    font-weight: 500;
  }
  
  .selected-check {
    color: #10b981;
    font-size: 0.875rem;
  }
  
  /* Full grid styles */
  .templates-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
    gap: 16px;
    padding: 16px;
  }
  
  .template-card {
    background: white;
    border: 1px solid #e5e7eb;
    border-radius: 8px;
    padding: 16px;
    cursor: pointer;
    transition: all 0.2s ease;
    position: relative;
  }
  
  .template-card:hover {
    border-color: #002147;
    box-shadow: 0 2px 8px rgba(0, 33, 71, 0.1);
  }
  
  .template-card.selected {
    border-color: #002147;
    background: #f8fafc;
    box-shadow: 0 2px 12px rgba(0, 33, 71, 0.15);
  }
  
  .card-header {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    margin-bottom: 12px;
  }
  
  .template-icon {
    width: 40px;
    height: 40px;
    background: linear-gradient(135deg, #002147, #1e3a5f);
    border-radius: 8px;
    display: flex;
    align-items: center;
    justify-content: center;
    color: white;
    font-size: 1rem;
  }
  
  .selected-indicator {
    color: #10b981;
    font-size: 1.125rem;
  }
  
  .template-info {
    margin-bottom: 12px;
  }
  
  .template-name {
    margin: 0 0 6px 0;
    font-size: 1rem;
    font-weight: 600;
    color: #111827;
  }
  
  .template-description {
    margin: 0;
    font-size: 0.875rem;
    color: #6b7280;
    line-height: 1.4;
  }
  
  .config-loading {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
    padding: 16px;
    color: #6b7280;
    font-size: 0.875rem;
  }
  
  @media (max-width: 768px) {
    .templates-grid {
      grid-template-columns: 1fr;
    }
  }
</style>
