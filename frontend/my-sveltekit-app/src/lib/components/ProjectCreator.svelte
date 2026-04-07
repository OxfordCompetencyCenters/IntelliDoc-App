<script lang="ts">
  import { createEventDispatcher } from 'svelte';
  import templateService from '$lib/services/templateService';
  import { cleanUniversalApi } from '$lib/services/cleanUniversalApi';
  import { toasts } from '$lib/stores/toast';
  import TemplateSelector from './TemplateSelector.svelte';
  import type { TemplateInfo, CompleteTemplateConfig, IntelliDocProject } from '$lib/types';
  
  const dispatch = createEventDispatcher();
  
  // Form state
  let projectName = '';
  let projectDescription = '';
  let selectedTemplate: TemplateInfo | null = null;
  let templateConfiguration: CompleteTemplateConfig | null = null;
  let creating = false;
  
  // API Keys state - optional during project creation
  let apiKeys = {
    openai: '',
    google: '', // Using google consistently (not gemini)
    anthropic: ''
  };
  let showApiKeysSection = false;
  
  // Validation state
  let nameError = '';
  let descriptionError = '';
  let templateError = '';
  let apiKeyErrors = {
    openai: '',
    google: '',
    anthropic: ''
  };
  
  function validateForm(): boolean {
    let isValid = true;
    
    // Reset errors
    nameError = '';
    descriptionError = '';
    templateError = '';
    apiKeyErrors = { openai: '', google: '', anthropic: '' };
    
    // Validate project name
    if (!projectName.trim()) {
      nameError = 'Project name is required';
      isValid = false;
    } else if (projectName.trim().length < 3) {
      nameError = 'Name must be at least 3 characters';
      isValid = false;
    }
    
    // Validate description
    if (!projectDescription.trim()) {
      descriptionError = 'Description is required';
      isValid = false;
    } else if (projectDescription.trim().length < 10) {
      descriptionError = 'Please provide more details (min 10 characters)';
      isValid = false;
    }
    
    // Validate template selection
    if (!selectedTemplate) {
      templateError = 'Please select a template';
      isValid = false;
    }
    
    // API keys are optional - only validate format if provided
    if (apiKeys.openai.trim() && !apiKeys.openai.startsWith('sk-')) {
      apiKeyErrors.openai = 'OpenAI API key should start with "sk-"';
      isValid = false;
    }
    
    if (apiKeys.google.trim() && apiKeys.google.length < 20) {
      apiKeyErrors.google = 'Google API key appears to be too short';
      isValid = false;
    }
    
    if (apiKeys.anthropic.trim() && !apiKeys.anthropic.startsWith('sk-ant-')) {
      apiKeyErrors.anthropic = 'Anthropic API key should start with "sk-ant-"';
      isValid = false;
    }
    
    return isValid;
  }
  
  async function createProject() {
    if (!validateForm()) {
      toasts.error('Please fix the form errors before creating the project');
      return;
    }
    
    try {
      creating = true;
      
      const projectData = {
        name: projectName.trim(),
        description: projectDescription.trim(),
        template_id: selectedTemplate!.id
      };
      
      // Create the project first
      const createdProject = await cleanUniversalApi.createProject(projectData);
      
      // If API keys were provided, save them to the project
      const providedKeys = Object.entries(apiKeys).filter(([_, value]) => value.trim() !== '');
      
      if (providedKeys.length > 0) {
      try {
      for (const [provider, key] of providedKeys) {
      await cleanUniversalApi.saveProjectApiKey(createdProject.project_id, {
      provider_type: provider,
      api_key: key.trim(), // Backend will handle encryption
      is_active: true
      });
      }
          
          toasts.success(`Project "${createdProject.name}" created with ${providedKeys.length} API key(s)!`);
        } catch (apiKeyError) {
          // Project was created but API keys failed - still success, just warn
          console.warn('API key setup failed:', apiKeyError);
          toasts.warning(`Project created successfully, but API key setup failed. You can add them later via API Management.`);
        }
      } else {
        toasts.success(`Project "${createdProject.name}" created successfully!`);
      }
      
      dispatch('projectCreated', createdProject);
      resetForm();
      
    } catch (error) {
      console.error('Failed to create project:', error);
      toasts.error(error.message || 'Failed to create project');
    } finally {
      creating = false;
    }
  }
  
  function resetForm() {
    projectName = '';
    projectDescription = '';
    selectedTemplate = null;
    templateConfiguration = null;
    apiKeys = { openai: '', google: '', anthropic: '' };
    showApiKeysSection = false;
    nameError = '';
    descriptionError = '';
    templateError = '';
    apiKeyErrors = { openai: '', google: '', anthropic: '' };
  }
  
  function onTemplateSelected(event: CustomEvent) {
    const { template, configuration } = event.detail;
    selectedTemplate = template;
    templateConfiguration = configuration;
    templateError = '';
  }
  
  function toggleApiKeysSection() {
    showApiKeysSection = !showApiKeysSection;
  }
  
  function getProviderInfo(provider: string) {
    const info = {
      openai: {
        name: 'OpenAI',
        description: 'GPT models for chat, summarization, and analysis',
        placeholder: 'sk-...',
        icon: 'fa-robot'
      },
      google: {
        name: 'Google (Gemini)',
        description: 'Gemini models for document processing',
        placeholder: 'AIzaSy...',
        icon: 'fa-google'
      },
      anthropic: {
        name: 'Anthropic (Claude)',
        description: 'Claude models for advanced reasoning',
        placeholder: 'sk-ant-...',
        icon: 'fa-brain'
      }
    };
    return info[provider] || { name: provider, description: '', placeholder: '', icon: 'fa-key' };
  }
  
  // Clear validation errors when user types
  $: if (projectName.trim()) nameError = '';
  $: if (projectDescription.trim()) descriptionError = '';
  $: if (apiKeys.openai.trim()) apiKeyErrors.openai = '';
  $: if (apiKeys.google.trim()) apiKeyErrors.google = '';
  $: if (apiKeys.anthropic.trim()) apiKeyErrors.anthropic = '';
</script>

<div class="project-creator">
  <form on:submit|preventDefault={createProject} class="creation-form">
    <!-- Compact form fields -->
    <div class="form-fields">
      <div class="field-group">
        <label for="projectName">Project Name *</label>
        <input 
          id="projectName"
          type="text" 
          class="form-input {nameError ? 'error' : ''}"
          bind:value={projectName}
          placeholder="e.g., Legal Document Analysis"
          maxlength="200"
          required
        />
        {#if nameError}
          <span class="error-text">{nameError}</span>
        {/if}
      </div>
      
      <div class="field-group">
        <label for="projectDescription">Description *</label>
        <textarea 
          id="projectDescription"
          class="form-textarea {descriptionError ? 'error' : ''}"
          bind:value={projectDescription}
          placeholder="Brief description of your analysis goals"
          rows="2"
          maxlength="500"
          required
        ></textarea>
        {#if descriptionError}
          <span class="error-text">{descriptionError}</span>
        {/if}
      </div>
      
      <div class="field-group template-field">
        <label>Template *</label>
        <TemplateSelector 
          bind:selectedTemplate
          on:templateSelected={onTemplateSelected}
          compact={false}
          smallGrid={true}
        />
        {#if templateError}
          <span class="error-text">{templateError}</span>
        {/if}
      </div>
      
      <!-- API Keys Section (Optional) -->
      <div class="field-group">
        <div class="api-keys-header">
          <button 
            type="button" 
            class="toggle-api-keys"
            on:click={toggleApiKeysSection}
          >
            <i class="fas {showApiKeysSection ? 'fa-chevron-down' : 'fa-chevron-right'}"></i>
            <i class="fas fa-key api-key-icon"></i>
            API Keys (Optional)
          </button>
          <span class="api-keys-subtitle">Configure project-specific API keys</span>
        </div>
        
        {#if showApiKeysSection}
          <div class="api-keys-section">
            <div class="api-keys-info">
              <div class="info-box">
                <i class="fas fa-info-circle"></i>
                <div>
                  <strong>Optional:</strong> Add API keys now or later via API Management.
                  <br>These keys will be securely stored and used only for this project.
                </div>
              </div>
            </div>
            
            {#each Object.entries(apiKeys) as [provider, value]}
              {@const info = getProviderInfo(provider)}
              <div class="api-key-field">
                <label for="apiKey-{provider}">
                  <i class="fas {info.icon}"></i>
                  {info.name}
                </label>
                <input
                  id="apiKey-{provider}"
                  type="password"
                  class="form-input api-key-input {apiKeyErrors[provider] ? 'error' : ''}"
                  bind:value={apiKeys[provider]}
                  placeholder={info.placeholder}
                />
                <div class="api-key-description">{info.description}</div>
                {#if apiKeyErrors[provider]}
                  <span class="error-text">{apiKeyErrors[provider]}</span>
                {/if}
              </div>
            {/each}
          </div>
        {/if}
      </div>
    </div>
    
    <!-- Selected template preview (compact) -->
    {#if selectedTemplate && templateConfiguration}
      <div class="template-preview">
        <div class="preview-header">
          <div class="template-icon">
            <i class="fas {selectedTemplate.icon_class}"></i>
          </div>
          <div class="template-info">
            <span class="template-name">{selectedTemplate.name}</span>
            <div class="template-features">
              <span class="feature-tag">{templateConfiguration.total_pages} page{templateConfiguration.total_pages > 1 ? 's' : ''}</span>
              {#if templateConfiguration.processing_capabilities?.supports_ai_analysis}
                <span class="feature-tag">AI Analysis</span>
              {/if}
              {#if templateConfiguration.processing_capabilities?.supports_vector_search}
                <span class="feature-tag">Vector Search</span>
              {/if}
            </div>
          </div>
          <button 
            type="button" 
            class="clear-btn"
            on:click={() => { selectedTemplate = null; templateConfiguration = null; }}
            title="Clear selection"
          >
            <i class="fas fa-times"></i>
          </button>
        </div>
      </div>
    {/if}
    
    <!-- Action buttons -->
    <div class="form-actions">
      <button 
        type="button" 
        class="btn btn-secondary"
        on:click={resetForm}
        disabled={creating}
      >
        Reset
      </button>
      
      <button 
        type="submit" 
        class="btn btn-primary"
        disabled={creating || !selectedTemplate}
      >
        {#if creating}
          <i class="fas fa-spinner fa-spin"></i>
          Creating...
        {:else}
          <i class="fas fa-plus"></i>
          Create Project
        {/if}
      </button>
    </div>
  </form>
</div>

<style>
  .project-creator {
    max-width: 100%;
    margin: 0;
    background: transparent;
    border-radius: 0;
    box-shadow: none;
    overflow: visible;
  }
  
  .creation-form {
    padding: 24px;
    background: white;
    margin: 0;
  }
  
  .form-fields {
    display: flex;
    flex-direction: column;
    gap: 16px;
    margin-bottom: 16px;
  }
  
  .field-group {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }
  
  .template-field {
    gap: 6px;
  }
  
  label {
    font-size: 0.875rem;
    font-weight: 500;
    color: #374151;
  }
  
  .form-input, .form-textarea {
    padding: 10px 12px;
    border: 1px solid #d1d5db;
    border-radius: 6px;
    font-size: 0.875rem;
    transition: border-color 0.2s ease;
    background: white;
  }
  
  .form-input:focus, .form-textarea:focus {
    outline: none;
    border-color: #002147;
    box-shadow: 0 0 0 3px rgba(0, 33, 71, 0.1);
  }
  
  .form-input.error, .form-textarea.error {
    border-color: #dc2626;
    box-shadow: 0 0 0 3px rgba(220, 38, 38, 0.1);
  }
  
  .form-textarea {
    resize: vertical;
    font-family: inherit;
    line-height: 1.4;
  }
  
  .error-text {
    color: #dc2626;
    font-size: 0.75rem;
    margin-top: 2px;
  }
  
  /* API Keys Section Styles */
  .api-keys-header {
    margin-bottom: 8px;
  }
  
  .toggle-api-keys {
    background: none;
    border: none;
    color: #374151;
    font-size: 0.875rem;
    font-weight: 500;
    cursor: pointer;
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 8px 0;
    transition: all 0.2s ease;
  }
  
  .toggle-api-keys:hover {
    color: #002147;
  }
  
  .api-key-icon {
    color: #6b7280;
  }
  
  .api-keys-subtitle {
    display: block;
    font-size: 0.75rem;
    color: #6b7280;
    margin-top: 2px;
    margin-left: 24px;
  }
  
  .api-keys-section {
    border: 1px solid #e2e8f0;
    border-radius: 8px;
    padding: 16px;
    background: #f8fafc;
    margin-top: 8px;
  }
  
  .api-keys-info {
    margin-bottom: 16px;
  }
  
  .info-box {
    display: flex;
    gap: 8px;
    align-items: flex-start;
    padding: 12px;
    background: #eff6ff;
    border: 1px solid #dbeafe;
    border-radius: 6px;
    font-size: 0.8125rem;
    color: #1e40af;
  }
  
  .info-box i {
    color: #3b82f6;
    margin-top: 2px;
  }
  
  .api-key-field {
    margin-bottom: 16px;
  }
  
  .api-key-field:last-child {
    margin-bottom: 0;
  }
  
  .api-key-field label {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 4px;
    font-size: 0.8125rem;
    font-weight: 500;
  }
  
  .api-key-input {
    font-family: monospace;
    font-size: 0.8125rem;
  }
  
  .api-key-description {
    font-size: 0.75rem;
    color: #6b7280;
    margin-top: 2px;
  }
  
  /* Template Preview */
  .template-preview {
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 6px;
    padding: 12px;
    margin-bottom: 16px;
    margin-top: 8px;
  }
  
  .preview-header {
    display: flex;
    align-items: center;
    gap: 10px;
  }
  
  .template-icon {
    width: 32px;
    height: 32px;
    background: linear-gradient(135deg, #002147, #1e3a5f);
    border-radius: 6px;
    display: flex;
    align-items: center;
    justify-content: center;
    color: white;
    font-size: 0.75rem;
    flex-shrink: 0;
  }
  
  .template-info {
    flex: 1;
    min-width: 0;
  }
  
  .template-name {
    font-weight: 500;
    color: #111827;
    font-size: 0.8125rem;
    display: block;
    margin-bottom: 3px;
  }
  
  .template-features {
    display: flex;
    gap: 6px;
    flex-wrap: wrap;
  }
  
  .feature-tag {
    background: #eff6ff;
    color: #1e40af;
    padding: 1px 5px;
    border-radius: 3px;
    font-size: 0.6rem;
    font-weight: 500;
  }
  
  .clear-btn {
    background: none;
    border: none;
    color: #6b7280;
    cursor: pointer;
    padding: 4px;
    border-radius: 4px;
    transition: all 0.2s ease;
    flex-shrink: 0;
  }
  
  .clear-btn:hover {
    color: #dc2626;
    background: #fef2f2;
  }
  
  /* Form Actions */
  .form-actions {
    display: flex;
    justify-content: flex-end;
    gap: 10px;
    padding-top: 16px;
    border-top: 1px solid #e5e7eb;
  }
  
  .btn {
    padding: 10px 20px;
    border-radius: 6px;
    font-weight: 500;
    cursor: pointer;
    transition: all 0.2s ease;
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 0.875rem;
    border: 1px solid transparent;
  }
  
  .btn-secondary {
    background: white;
    color: #374151;
    border-color: #d1d5db;
  }
  
  .btn-secondary:hover {
    background: #f9fafb;
    border-color: #9ca3af;
  }
  
  .btn-primary {
    background: linear-gradient(135deg, #002147, #1e3a5f);
    color: white;
    border-color: #002147;
  }
  
  .btn-primary:hover:not(:disabled) {
    background: linear-gradient(135deg, #1e3a5f, #002147);
    transform: translateY(-1px);
    box-shadow: 0 4px 12px rgba(0, 33, 71, 0.25);
  }
  
  .btn:disabled {
    opacity: 0.5;
    cursor: not-allowed;
    transform: none;
    box-shadow: none;
  }
  
  @media (max-width: 640px) {
    .project-creator {
      margin: 0 16px;
      max-width: calc(100% - 32px);
    }
    
    .creation-form {
      padding: 20px;
    }
    
    .form-actions {
      flex-direction: column;
    }
    
    .btn {
      justify-content: center;
    }
  }
</style>
