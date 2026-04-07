<script lang="ts">
  import { createEventDispatcher } from 'svelte';
  import { cleanUniversalApi } from '$lib/services/cleanUniversalApi';
  import { toasts } from '$lib/stores/toast';
  
  const dispatch = createEventDispatcher();
  
  export let projectId: string;
  export let projectName: string;
  export let showModal = false;
  
  // State
  let loading = true;
  let saving = false;
  let testing = false;
  let apiKeys: any[] = [];
  let activeTab = 'overview';
  
  // Form state for new/edit API key
  let editingKey: any = null;
  let showAddForm = false;
  let keyForm = {
    provider_type: '',
    encrypted_api_key: '',
    is_active: true
  };
  let formErrors = {
    provider_type: '',
    encrypted_api_key: ''
  };
  
  // Available providers
  const providers = [
    {
      type: 'openai',
      name: 'OpenAI',
      description: 'GPT models for chat, summarization, and analysis',
      icon: 'fa-robot',
      placeholder: 'sk-...',
      color: 'emerald'
    },
    {
      type: 'google',
      name: 'Google (Gemini)',
      description: 'Gemini models for document processing and OCR',
      icon: 'fa-google',
      placeholder: 'AIzaSy...',
      color: 'info'
    },
    {
      type: 'anthropic',
      name: 'Anthropic (Claude)',
      description: 'Claude models for advanced reasoning and analysis',
      icon: 'fa-brain',
      placeholder: 'sk-ant-...',
      color: 'royal-purple'
    },
    {
      type: 'ollama',
      name: 'Ollama (Local)',
      description: 'Local AI models via Docker — no API key required',
      icon: 'fa-server',
      placeholder: '',
      color: 'slate',
      noKeyRequired: true
    }
  ];
  
  $: if (showModal) {
    loadApiKeys();
  }
  
  async function loadApiKeys() {
    try {
      loading = true;
      apiKeys = await cleanUniversalApi.getProjectApiKeys(projectId);
    } catch (error) {
      console.error('Failed to load API keys:', error);
      toasts.error('Failed to load API keys');
      apiKeys = [];
    } finally {
      loading = false;
    }
  }
  
  function getProviderInfo(type: string) {
    return providers.find(p => p.type === type) || providers[0];
  }
  
  function getUsedProviders() {
    return apiKeys.map(key => key.provider_type);
  }
  
  function getAvailableProviders() {
    const usedProviders = getUsedProviders();
    return providers.filter(p => !usedProviders.includes(p.type) || editingKey?.provider_type === p.type);
  }
  
  function validateForm(): boolean {
    formErrors = { provider_type: '', encrypted_api_key: '' };
    let isValid = true;
    
    if (!keyForm.provider_type) {
      formErrors.provider_type = 'Provider is required';
      isValid = false;
    }
    
    if (!keyForm.encrypted_api_key || !keyForm.encrypted_api_key.trim()) {
      formErrors.encrypted_api_key = 'API key is required';
      isValid = false;
    } else {
      // Basic format validation
      if (keyForm.provider_type === 'openai' && !keyForm.encrypted_api_key.startsWith('sk-')) {
        formErrors.encrypted_api_key = 'OpenAI API key should start with "sk-"';
        isValid = false;
      } else if (keyForm.provider_type === 'anthropic' && !keyForm.encrypted_api_key.startsWith('sk-ant-')) {
        formErrors.encrypted_api_key = 'Anthropic API key should start with "sk-ant-"';
        isValid = false;
      } else if (keyForm.provider_type === 'google' && keyForm.encrypted_api_key.length < 20) {
        formErrors.encrypted_api_key = 'Google API key appears to be too short';
        isValid = false;
      }
    }
    
    return isValid;
  }
  
  async function saveApiKey() {
    if (!validateForm()) {
      return;
    }
    
    try {
      saving = true;
      
      if (editingKey) {
        // For editing, we need to update the existing key
        await cleanUniversalApi.updateProjectApiKey(projectId, editingKey.id, {
          provider_type: keyForm.provider_type,
          api_key: keyForm.encrypted_api_key || '',
          is_active: keyForm.is_active
        });
        toasts.success('API key updated successfully');
      } else {
        // For creating new key
        await cleanUniversalApi.saveProjectApiKey(projectId, {
          provider_type: keyForm.provider_type,
          api_key: keyForm.encrypted_api_key || '', // Map field name
          is_active: keyForm.is_active
        });
        toasts.success('API key added successfully');
      }
      
      await loadApiKeys();
      resetForm();
      
    } catch (error) {
      console.error('Failed to save API key:', error);
      toasts.error(error.message || 'Failed to save API key');
    } finally {
      saving = false;
    }
  }
  
  async function deleteApiKey(provider_type: string, keyName: string) {
    if (!confirm(`Are you sure you want to delete "${keyName}"? This action cannot be undone.`)) {
      return;
    }
    
    try {
      await cleanUniversalApi.deleteProjectApiKey(projectId, provider_type);
      toasts.success(`Deleted "${keyName}" successfully`);
      await loadApiKeys();
    } catch (error) {
      console.error('Failed to delete API key:', error);
      toasts.error('Failed to delete API key');
    }
  }
  
  async function testApiKey(provider_type: string, keyName: string) {
    try {
      testing = true;
      const result = await cleanUniversalApi.testProjectApiKey(projectId, provider_type);
      
      // Find the API key to get provider display name
      const apiKey = apiKeys.find(key => key.provider_type === provider_type);
      const providerName = apiKey?.provider_display_info?.name || provider_type;
      
      if (result.is_valid) {
        toasts.success(`${providerName} API key is valid and working`);
      } else {
        toasts.error(`${providerName} API key validation failed: ${result.error || 'Unknown error'}`);
      }
      
      await loadApiKeys(); // Refresh to get updated validation status
      
    } catch (error) {
      console.error('Failed to test API key:', error);
      toasts.error(`Failed to test "${keyName}"`);
    } finally {
      testing = false;
    }
  }
  
  function startAddKey() {
    resetForm();
    showAddForm = true;
  }
  
  // Auto-generate key name based on provider
  function getAutoKeyName(provider_type: string): string {
    const provider = getProviderInfo(provider_type);
    return `${provider.name} Key`;
  }
  
  function startEditKey(key: any) {
    editingKey = key;
    keyForm = {
      provider_type: key.provider_type,
      encrypted_api_key: '', // Don't populate for security
      is_active: key.is_active
    };
    showAddForm = true;
  }
  
  function resetForm() {
    editingKey = null;
    showAddForm = false;
    keyForm = {
      provider_type: '',
      encrypted_api_key: '',
      is_active: true
    };
    formErrors = { provider_type: '', encrypted_api_key: '' };
  }
  
  function closeModal() {
    showModal = false;
    resetForm();
    dispatch('close');
  }
  
  function formatDate(dateString: string): string {
    return new Date(dateString).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  }
</script>

{#if showModal}
  <div class="modal-overlay" on:click={closeModal}>
    <div class="modal-container" on:click|stopPropagation>
      <div class="modal-header">
        <div class="header-content">
          <div class="header-icon">
            <i class="fas fa-key"></i>
          </div>
          <div class="header-text">
            <h2>API Management</h2>
            <p>{projectName}</p>
          </div>
        </div>
        <button class="close-button" on:click={closeModal}>
          <i class="fas fa-times"></i>
        </button>
      </div>
      
      <div class="modal-content">
        <!-- Tabs -->
        <div class="tabs-container">
          <button 
            class="tab {activeTab === 'overview' ? 'active' : ''}"
            on:click={() => activeTab = 'overview'}
          >
            <i class="fas fa-list"></i>
            Overview
          </button>
          <button 
            class="tab {activeTab === 'security' ? 'active' : ''}"
            on:click={() => activeTab = 'security'}
          >
            <i class="fas fa-shield-alt"></i>
            Security
          </button>
        </div>
        
        <!-- Overview Tab -->
        {#if activeTab === 'overview'}
          <div class="tab-content">
            {#if loading}
              <div class="loading-state">
                <div class="spinner"></div>
                <p>Loading API keys...</p>
              </div>
            {:else}
              <!-- API Keys List -->
              <div class="section">
                <div class="section-header">
                  <h3>
                    <i class="fas fa-key"></i>
                    API Keys ({apiKeys.length})
                  </h3>
                  <button 
                    class="btn btn-primary"
                    on:click={startAddKey}
                    disabled={getAvailableProviders().length === 0}
                  >
                    <i class="fas fa-plus"></i>
                    Add API Key
                  </button>
                </div>
                
                {#if apiKeys.length === 0}
                  <div class="empty-state">
                    <div class="empty-icon">
                      <i class="fas fa-key"></i>
                    </div>
                    <h4>No API keys configured</h4>
                    <p>Add API keys to enable AI-powered features for this project.</p>
                  </div>
                {:else}
                  <div class="api-keys-list">
                    {#each apiKeys as apiKey}
                      {@const provider = getProviderInfo(apiKey.provider_type)}
                      <div class="api-key-card">
                        <div class="key-header">
                          <div class="key-info">
                            <div class="key-icon" style="color: var(--{provider.color}, #3b82f6)">
                              <i class="fas {provider.icon}"></i>
                            </div>
                            <div class="key-details">
                              <div class="key-name">{apiKey.key_name}</div>
                              <div class="key-provider">{provider.name}</div>
                              <div class="key-masked">{apiKey.masked_key}</div>
                            </div>
                          </div>
                          
                          <div class="key-status">
                            <span class="status-badge {apiKey.is_validated ? 'validated' : 'not-validated'}">
                              {#if apiKey.is_validated}
                                <i class="fas fa-check-circle"></i>
                                Validated
                              {:else}
                                <i class="fas fa-exclamation-circle"></i>
                                Not Validated
                              {/if}
                            </span>
                          </div>
                        </div>
                        
                        <div class="key-meta">
                          <div class="meta-item">
                            <i class="fas fa-calendar"></i>
                            Added {formatDate(apiKey.created_at)}
                          </div>
                          {#if apiKey.last_used_at}
                            <div class="meta-item">
                              <i class="fas fa-clock"></i>
                              Last used {formatDate(apiKey.last_used_at)}
                            </div>
                          {/if}
                          {#if apiKey.usage_count > 0}
                            <div class="meta-item">
                              <i class="fas fa-chart-line"></i>
                              Used {apiKey.usage_count} times
                            </div>
                          {/if}
                        </div>
                        
                        <div class="key-actions">
                          <button 
                            class="btn btn-secondary small"
                            on:click={() => testApiKey(apiKey.provider_type, apiKey.key_name)}
                            disabled={testing}
                          >
                            {#if testing}
                              <i class="fas fa-spinner fa-spin"></i>
                            {:else}
                              <i class="fas fa-vial"></i>
                            {/if}
                            Test
                          </button>
                          <button 
                            class="btn btn-secondary small"
                            on:click={() => startEditKey(apiKey)}
                          >
                            <i class="fas fa-edit"></i>
                            Edit
                          </button>
                          <button 
                            class="btn btn-danger small"
                            on:click={() => deleteApiKey(apiKey.provider_type, apiKey.key_name)}
                          >
                            <i class="fas fa-trash"></i>
                            Delete
                          </button>
                        </div>
                      </div>
                    {/each}
                  </div>
                {/if}
              </div>
            {/if}
          </div>
        {/if}
        
        <!-- Security Tab -->
        {#if activeTab === 'security'}
          <div class="tab-content">
            <div class="section">
              <h3>
                <i class="fas fa-shield-alt"></i>
                Security Information
              </h3>
              
              <div class="security-info">
                <div class="info-card">
                  <div class="info-icon">
                    <i class="fas fa-lock"></i>
                  </div>
                  <div class="info-content">
                    <h4>Encryption</h4>
                    <p>All API keys are encrypted using AES-256 encryption before storage. Keys are only decrypted when needed for API calls.</p>
                  </div>
                </div>
                
                <div class="info-card">
                  <div class="info-icon">
                    <i class="fas fa-users-slash"></i>
                  </div>
                  <div class="info-content">
                    <h4>Project Isolation</h4>
                    <p>API keys are strictly isolated to this project only. They cannot be accessed or used by any other projects.</p>
                  </div>
                </div>
                
                <div class="info-card">
                  <div class="info-icon">
                    <i class="fas fa-eye-slash"></i>
                  </div>
                  <div class="info-content">
                    <h4>Access Control</h4>
                    <p>Only project members with appropriate permissions can view, edit, or delete API keys. Keys are never displayed in full.</p>
                  </div>
                </div>
                
                <div class="info-card">
                  <div class="info-icon">
                    <i class="fas fa-history"></i>
                  </div>
                  <div class="info-content">
                    <h4>Usage Tracking</h4>
                    <p>API key usage is tracked and logged for security auditing. You can see usage statistics for each key.</p>
                  </div>
                </div>
              </div>
            </div>
          </div>
        {/if}
      </div>
    </div>
  </div>
{/if}

<!-- Add/Edit API Key Modal -->
{#if showAddForm}
  <div class="modal-overlay" on:click={resetForm}>
    <div class="modal-container small" on:click|stopPropagation>
      <div class="modal-header">
        <h2>
          {#if editingKey}
            <i class="fas fa-edit"></i>
            Edit API Key
          {:else}
            <i class="fas fa-plus"></i>
            Add API Key
          {/if}
        </h2>
        <button class="close-button" on:click={resetForm}>
          <i class="fas fa-times"></i>
        </button>
      </div>
      
      <div class="modal-content">
        <form on:submit|preventDefault={saveApiKey} class="api-key-form">
          <div class="form-group">
            <label for="provider">Provider *</label>
            <select 
              id="provider"
              bind:value={keyForm.provider_type}
              class="form-select {formErrors.provider_type ? 'error' : ''}"
              disabled={!!editingKey}
              required
            >
              <option value="">Select provider...</option>
              {#each getAvailableProviders() as provider}
                <option value={provider.type}>{provider.name}</option>
              {/each}
            </select>
            {#if formErrors.provider_type}
              <span class="error-text">{formErrors.provider_type}</span>
            {/if}
          </div>
          
          {#if keyForm.provider_type}
            {@const provider = getProviderInfo(keyForm.provider_type)}
            {#if provider?.noKeyRequired}
              <div class="form-group">
                <div class="bg-green-50 border border-green-200 rounded-lg p-4">
                  <div class="flex items-center gap-2 text-green-700">
                    <i class="fas fa-check-circle"></i>
                    <span class="font-medium">No API key required</span>
                  </div>
                  <p class="text-sm text-green-600 mt-1">{provider.description}</p>
                  <p class="text-xs text-green-500 mt-2">Ollama runs locally via Docker. Manage models from the Processing Configuration panel.</p>
                </div>
              </div>
            {:else}
              <div class="form-group">
                <label for="apiKey">API Key *</label>
                <input
                  id="apiKey"
                  type="password"
                  bind:value={keyForm.encrypted_api_key}
                  class="form-input {formErrors.encrypted_api_key ? 'error' : ''}"
                  placeholder={provider.placeholder}
                  required
                />
                {#if formErrors.encrypted_api_key}
                  <span class="error-text">{formErrors.encrypted_api_key}</span>
                {/if}
                <div class="field-help">
                  {provider.description}
                </div>
              </div>
            {/if}
          {/if}
          

          
          <div class="form-group">
            <label class="checkbox-label">
              <input
                type="checkbox"
                bind:checked={keyForm.is_active}
              />
              <span class="checkmark"></span>
              Active
            </label>
            <div class="field-help">
              Only active keys will be used for API calls
            </div>
          </div>
          
          <div class="form-actions">
            <button type="button" class="btn btn-secondary" on:click={resetForm}>
              Cancel
            </button>
            <button 
              type="submit" 
              class="btn btn-primary"
              disabled={saving}
            >
              {#if saving}
                <i class="fas fa-spinner fa-spin"></i>
                {editingKey ? 'Updating...' : 'Adding...'}
              {:else}
                <i class="fas {editingKey ? 'fa-save' : 'fa-plus'}"></i>
                {editingKey ? 'Update Key' : 'Add Key'}
              {/if}
            </button>
          </div>
        </form>
      </div>
    </div>
  </div>
{/if}

<style>
  /* CSS Variables for colors */
  :global(:root) {
    --emerald: #10b981;
    --info: #3b82f6;
    --royal-purple: #7c3aed;
  }
  
  .modal-overlay {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: rgba(0, 0, 0, 0.5);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 1000;
    padding: 20px;
  }
  
  .modal-container {
    background: white;
    border-radius: 16px;
    box-shadow: 0 20px 40px rgba(0, 0, 0, 0.15);
    max-width: 1000px;
    width: 100%;
    max-height: 90vh;
    overflow-y: auto;
  }
  
  .modal-container.small {
    max-width: 500px;
  }
  
  .modal-header {
    padding: 24px 32px;
    background: linear-gradient(135deg, #002147 0%, #1e3a5f 100%);
    color: white;
    display: flex;
    justify-content: space-between;
    align-items: center;
    border-radius: 16px 16px 0 0;
  }
  
  .header-content {
    display: flex;
    align-items: center;
    gap: 16px;
  }
  
  .header-icon {
    width: 48px;
    height: 48px;
    background: rgba(255, 255, 255, 0.2);
    border-radius: 12px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 1.25rem;
  }
  
  .header-text h2 {
    margin: 0;
    font-size: 1.5rem;
    font-weight: 600;
  }
  
  .header-text p {
    margin: 4px 0 0 0;
    opacity: 0.8;
    font-size: 0.875rem;
  }
  
  .close-button {
    background: none;
    border: none;
    font-size: 1.25rem;
    color: rgba(255, 255, 255, 0.8);
    cursor: pointer;
    padding: 8px;
    border-radius: 8px;
    transition: all 0.2s ease;
  }
  
  .close-button:hover {
    color: white;
    background: rgba(255, 255, 255, 0.1);
  }
  
  .modal-content {
    padding: 0;
    background: #f8fafc;
  }
  
  .tabs-container {
    display: flex;
    background: white;
    border-bottom: 1px solid #e5e7eb;
  }
  
  .tab {
    flex: 1;
    padding: 16px 24px;
    background: none;
    border: none;
    cursor: pointer;
    font-size: 0.875rem;
    font-weight: 500;
    color: #6b7280;
    display: flex;
    align-items: center;
    gap: 8px;
    transition: all 0.2s ease;
    border-bottom: 2px solid transparent;
  }
  
  .tab:hover {
    color: #002147;
    background: #f8fafc;
  }
  
  .tab.active {
    color: #002147;
    background: #f8fafc;
    border-bottom-color: #002147;
  }
  
  .tab-content {
    padding: 24px 32px;
  }
  
  .section {
    margin-bottom: 32px;
  }
  
  .section:last-child {
    margin-bottom: 0;
  }
  
  .section-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 16px;
  }
  
  .section h3 {
    margin: 0;
    font-size: 1.125rem;
    font-weight: 600;
    color: #111827;
    display: flex;
    align-items: center;
    gap: 8px;
  }
  
  .loading-state {
    text-align: center;
    padding: 48px 24px;
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
  
  .empty-state {
    text-align: center;
    padding: 48px 24px;
    background: white;
    border-radius: 12px;
    border: 2px dashed #e5e7eb;
  }
  
  .empty-icon {
    font-size: 3rem;
    color: #d1d5db;
    margin-bottom: 16px;
  }
  
  .empty-state h4 {
    margin: 0 0 8px 0;
    color: #111827;
    font-size: 1.125rem;
  }
  
  .empty-state p {
    margin: 0 0 24px 0;
    color: #6b7280;
  }
  
  .api-keys-list {
    display: flex;
    flex-direction: column;
    gap: 16px;
  }
  
  .api-key-card {
    background: white;
    border-radius: 12px;
    padding: 24px;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);
    border: 1px solid #e5e7eb;
  }
  
  .key-header {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    margin-bottom: 16px;
  }
  
  .key-info {
    display: flex;
    align-items: center;
    gap: 16px;
  }
  
  .key-icon {
    font-size: 1.5rem;
  }
  
  .key-details {
    line-height: 1.4;
  }
  
  .key-name {
    font-weight: 600;
    color: #111827;
    font-size: 1rem;
    margin-bottom: 2px;
  }
  
  .key-provider {
    color: #6b7280;
    font-size: 0.875rem;
    margin-bottom: 4px;
  }
  
  .key-masked {
    font-family: monospace;
    font-size: 0.75rem;
    color: #9ca3af;
    background: #f3f4f6;
    padding: 2px 6px;
    border-radius: 4px;
  }
  
  .key-status {
    text-align: right;
  }
  
  .status-badge {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    padding: 4px 8px;
    border-radius: 6px;
    font-size: 0.75rem;
    font-weight: 500;
  }
  
  .status-badge.validated {
    background: #d1fae5;
    color: #065f46;
  }
  
  .status-badge.not-validated {
    background: #fef3c7;
    color: #92400e;
  }
  
  .key-meta {
    display: flex;
    flex-wrap: wrap;
    gap: 16px;
    margin-bottom: 16px;
    font-size: 0.75rem;
    color: #6b7280;
  }
  
  .meta-item {
    display: flex;
    align-items: center;
    gap: 4px;
  }
  
  .key-actions {
    display: flex;
    gap: 8px;
  }
  
  .btn {
    padding: 8px 16px;
    border-radius: 8px;
    font-weight: 500;
    cursor: pointer;
    transition: all 0.2s ease;
    display: inline-flex;
    align-items: center;
    gap: 6px;
    font-size: 0.875rem;
    border: 1px solid transparent;
  }
  
  .btn.small {
    padding: 6px 12px;
    font-size: 0.8125rem;
  }
  
  .btn-primary {
    background: linear-gradient(135deg, #002147, #1e3a5f);
    color: white;
  }
  
  .btn-primary:hover:not(:disabled) {
    transform: translateY(-1px);
    box-shadow: 0 4px 12px rgba(0, 33, 71, 0.25);
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
  
  .btn-danger {
    background: #fef2f2;
    color: #dc2626;
    border-color: #fecaca;
  }
  
  .btn-danger:hover {
    background: #fee2e2;
    color: #b91c1c;
  }
  
  .btn:disabled {
    opacity: 0.5;
    cursor: not-allowed;
    transform: none;
    box-shadow: none;
  }
  
  .security-info {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
    gap: 16px;
  }
  
  .info-card {
    background: white;
    border-radius: 12px;
    padding: 20px;
    display: flex;
    gap: 16px;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);
    border: 1px solid #e5e7eb;
  }
  
  .info-icon {
    width: 48px;
    height: 48px;
    background: #eff6ff;
    border-radius: 12px;
    display: flex;
    align-items: center;
    justify-content: center;
    color: #3b82f6;
    font-size: 1.25rem;
    flex-shrink: 0;
  }
  
  .info-content h4 {
    margin: 0 0 8px 0;
    font-size: 1rem;
    font-weight: 600;
    color: #111827;
  }
  
  .info-content p {
    margin: 0;
    font-size: 0.875rem;
    color: #6b7280;
    line-height: 1.5;
  }
  
  
  /* Form Styles */
  .api-key-form {
    padding: 24px;
  }
  
  .form-group {
    margin-bottom: 20px;
  }
  
  .form-group:last-child {
    margin-bottom: 0;
  }
  
  .form-group label {
    display: block;
    margin-bottom: 6px;
    font-weight: 500;
    color: #374151;
    font-size: 0.875rem;
  }
  
  .form-input, .form-select {
    width: 100%;
    padding: 10px 12px;
    border: 1px solid #d1d5db;
    border-radius: 8px;
    font-size: 0.875rem;
    transition: border-color 0.2s ease;
  }
  
  .form-input:focus, .form-select:focus {
    outline: none;
    border-color: #002147;
    box-shadow: 0 0 0 3px rgba(0, 33, 71, 0.1);
  }
  
  .form-input.error, .form-select.error {
    border-color: #dc2626;
    box-shadow: 0 0 0 3px rgba(220, 38, 38, 0.1);
  }
  
  .error-text {
    color: #dc2626;
    font-size: 0.75rem;
    margin-top: 4px;
    display: block;
  }
  
  .field-help {
    font-size: 0.75rem;
    color: #6b7280;
    margin-top: 4px;
  }
  
  .checkbox-label {
    display: flex !important;
    align-items: center;
    gap: 8px;
    cursor: pointer;
    font-size: 0.875rem;
  }
  
  .checkbox-label input[type="checkbox"] {
    width: auto;
    margin: 0;
  }
  
  .form-actions {
    display: flex;
    justify-content: flex-end;
    gap: 12px;
    margin-top: 24px;
    padding-top: 24px;
    border-top: 1px solid #e5e7eb;
  }
  
  @media (max-width: 768px) {
    .modal-container {
      margin: 20px;
      max-width: calc(100% - 40px);
    }
    
    .tab-content {
      padding: 16px 20px;
    }
    
    .key-header {
      flex-direction: column;
      gap: 12px;
      align-items: flex-start;
    }
    
    .key-actions {
      width: 100%;
      justify-content: flex-end;
    }
    
    .security-info {
      grid-template-columns: 1fr;
    }
  }
</style>
