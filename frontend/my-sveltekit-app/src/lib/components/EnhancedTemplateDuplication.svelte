<!-- Enhanced Template Duplication Component -->
<script lang="ts">
  import { onMount } from 'svelte';
  import { createTemplateLogger } from '$lib/logging/logger';
  import { enhancedTemplateDuplicationService } from '$lib/services/enhancedTemplateDuplication';
  import { toasts } from '$lib/stores/toast';
  import type { 
    TemplateDuplicationRequest, 
    TemplateDuplicationResult,
    DuplicationPreview,
    DuplicationValidation,
    DuplicationCapabilities,
    DuplicationProgress,
    Template
  } from '$lib/templates/types';
  
  const logger = createTemplateLogger('duplication', 'EnhancedDuplicationComponent');
  
  // Props
  export let sourceTemplate: Template;
  export let onDuplicationComplete: (result: TemplateDuplicationResult) => void = () => {};
  export let onCancel: () => void = () => {};
  
  // State
  let currentStep = 1;
  let totalSteps = 4;
  let loading = false;
  let duplicating = false;
  
  // Form data
  let newTemplateId = '';
  let templateName = '';
  let templateDescription = '';
  let templateType = 'custom';
  let author = '';
  
  // Advanced options
  let showAdvancedOptions = false;
  let skipVerification = false;
  let enableRollback = true;
  let preserveMetadata = true;
  let updateVersion = true;
  
  // Results and validation
  let preview: DuplicationPreview | null = null;
  let validation: DuplicationValidation | null = null;
  let capabilities: DuplicationCapabilities | null = null;
  let duplicationResult: TemplateDuplicationResult | null = null;
  let progress: DuplicationProgress | null = null;
  
  // Error handling
  let errors: string[] = [];
  let warnings: string[] = [];
  
  const stepTitles = [
    'Configuration',
    'Preview & Validation', 
    'Duplication Process',
    'Results & Verification'
  ];
  
  onMount(() => {
    logger.componentMount('EnhancedDuplicationComponent', { sourceTemplate: sourceTemplate.id });
    loadCapabilities();
    generateSuggestions();
  });
  
  async function loadCapabilities() {
    try {
      loading = true;
      capabilities = await enhancedTemplateDuplicationService.getDuplicationCapabilities();
      logger.info('Duplication capabilities loaded', capabilities);
    } catch (error) {
      logger.error('Failed to load duplication capabilities', error);
      toasts.error('Failed to load duplication capabilities');
    } finally {
      loading = false;
    }
  }
  
  function generateSuggestions() {
    // Generate suggested template ID and configuration
    const baseId = sourceTemplate.id;
    newTemplateId = `${baseId}-v2`;
    templateName = `${sourceTemplate.name} V2`;
    templateDescription = `Enhanced version of ${sourceTemplate.name}`;
    templateType = sourceTemplate.template_type || 'custom';
    author = 'Template Administrator';
    
    logger.templateAction('suggestions_generated', 'duplication', {
      suggested_id: newTemplateId,
      suggested_name: templateName
    });
  }
  
  async function proceedToPreview() {
    if (!validateStep1()) return;
    
    try {
      loading = true;
      errors = [];
      warnings = [];
      
      // Load preview
      preview = await enhancedTemplateDuplicationService.previewDuplication(sourceTemplate.id);
      
      // Validate request
      const duplicationRequest = createDuplicationRequest();
      validation = await enhancedTemplateDuplicationService.validateDuplicationRequest(duplicationRequest);
      
      if (!validation.request_valid) {
        errors = validation.validation_errors;
        toasts.error('Validation failed. Please check the errors and try again.');
        return;
      }
      
      if (validation.recommendations.length > 0) {
        warnings = validation.recommendations;
      }
      
      currentStep = 2;
      logger.userInteraction('proceed_to_preview', 'next_button');
      
    } catch (error) {
      logger.error('Failed to generate preview and validation', error);
      toasts.error('Failed to generate preview. Please try again.');
    } finally {
      loading = false;
    }
  }
  
  async function startDuplication() {
    try {
      duplicating = true;
      progress = null;
      duplicationResult = null;
      
      const duplicationRequest = createDuplicationRequest();
      
      logger.templateAction('duplication_start', sourceTemplate.id, duplicationRequest);
      
      // Start duplication with progress tracking
      duplicationResult = await enhancedTemplateDuplicationService.duplicateTemplateWithProgress(
        sourceTemplate.id,
        duplicationRequest,
        (progressUpdate) => {
          progress = progressUpdate;
          logger.info('Duplication progress update', progressUpdate);
        }
      );
      
      if (duplicationResult.status === 'completed') {
        logger.templateAction('duplication_completed', sourceTemplate.id, duplicationResult);
        toasts.success(`Template "${newTemplateId}" created successfully!`);
        currentStep = 4;
        onDuplicationComplete(duplicationResult);
      } else {
        logger.error('Duplication failed', duplicationResult);
        toasts.error('Template duplication failed. Check the results for details.');
        currentStep = 4;
      }
      
    } catch (error) {
      logger.error('Duplication process failed', error);
      toasts.error('Duplication process failed. Please try again.');
    } finally {
      duplicating = false;
    }
  }
  
  function createDuplicationRequest(): TemplateDuplicationRequest {
    return {
      new_template_id: newTemplateId,
      source_template_id: sourceTemplate.id,
      template_config: {
        name: templateName,
        description: templateDescription,
        version: updateVersion ? '1.0.0' : sourceTemplate.version,
        author: author,
        template_type: templateType,
        icon_class: sourceTemplate.icon_class,
        color_theme: sourceTemplate.color_theme,
        analysis_focus: sourceTemplate.analysis_focus
      },
      duplication_options: {
        preserve_metadata: preserveMetadata,
        update_version: updateVersion,
        target_environment: 'development'
      },
      skip_verification: skipVerification,
      enable_rollback: enableRollback
    };
  }
  
  function validateStep1(): boolean {
    const tempErrors = [];
    
    if (!newTemplateId.trim()) {
      tempErrors.push('Template ID is required');
    } else if (!/^[a-z][a-z0-9-]*$/.test(newTemplateId)) {
      tempErrors.push('Template ID must start with a letter and contain only lowercase letters, numbers, and hyphens');
    }
    
    if (!templateName.trim()) {
      tempErrors.push('Template name is required');
    }
    
    if (!templateDescription.trim()) {
      tempErrors.push('Template description is required');
    }
    
    errors = tempErrors;
    return tempErrors.length === 0;
  }
  
  function goBack() {
    if (currentStep > 1) {
      currentStep--;
      logger.userInteraction('go_back', 'back_button', { step: currentStep });
    }
  }
  
  function cancelDuplication() {
    logger.userInteraction('cancel_duplication', 'cancel_button');
    onCancel();
  }
  
  function resetForm() {
    currentStep = 1;
    newTemplateId = '';
    templateName = '';
    templateDescription = '';
    errors = [];
    warnings = [];
    preview = null;
    validation = null;
    duplicationResult = null;
    progress = null;
    generateSuggestions();
    logger.userInteraction('reset_form', 'reset_button');
  }
</script>

<div class="enhanced-duplication-modal">
  <div class="modal-header">
    <h2>Enhanced Template Duplication</h2>
    <button class="close-button" on:click={cancelDuplication}>
      <i class="fas fa-times"></i>
    </button>
  </div>
  
  <!-- Progress Steps -->
  <div class="progress-steps">
    {#each stepTitles as title, index}
      <div class="step" class:active={currentStep === index + 1} class:completed={currentStep > index + 1}>
        <div class="step-number">{index + 1}</div>
        <div class="step-title">{title}</div>
      </div>
    {/each}
  </div>
  
  <!-- Step Content -->
  <div class="modal-content">
    {#if currentStep === 1}
      <!-- Step 1: Configuration -->
      <div class="step-content">
        <h3>Template Configuration</h3>
        <p class="step-description">
          Configure the new template based on <strong>{sourceTemplate.name}</strong>
        </p>
        
        <div class="form-grid">
          <div class="form-group">
            <label for="newTemplateId">Template ID *</label>
            <input 
              id="newTemplateId"
              type="text" 
              bind:value={newTemplateId}
              placeholder="e.g., my-custom-template"
              class="form-input"
              class:error={errors.some(e => e.includes('Template ID'))}
            />
            <div class="input-help">Must be lowercase, start with letter, use hyphens for spaces</div>
          </div>
          
          <div class="form-group">
            <label for="templateName">Template Name *</label>
            <input 
              id="templateName"
              type="text" 
              bind:value={templateName}
              placeholder="e.g., My Custom Template"
              class="form-input"
              class:error={errors.some(e => e.includes('Template name'))}
            />
          </div>
          
          <div class="form-group">
            <label for="templateType">Template Type</label>
            <select id="templateType" bind:value={templateType} class="form-select">
              <option value="custom">Custom</option>
              <option value="aicc-intellidoc">AICC-IntelliDoc</option>
              <option value="legal">Legal</option>
              <option value="medical">Medical</option>
              <option value="history">History</option>
              <option value="research">Research</option>
              <option value="analysis">Analysis</option>
            </select>
          </div>
          
          <div class="form-group">
            <label for="author">Author</label>
            <input 
              id="author"
              type="text" 
              bind:value={author}
              placeholder="Template creator"
              class="form-input"
            />
          </div>
        </div>
        
        <div class="form-group">
          <label for="templateDescription">Description *</label>
          <textarea 
            id="templateDescription"
            bind:value={templateDescription}
            placeholder="Describe the purpose and features of this template"
            class="form-textarea"
            rows="4"
            class:error={errors.some(e => e.includes('Template description'))}
          ></textarea>
        </div>
        
        <!-- Advanced Options -->
        <div class="advanced-options">
          <button 
            type="button"
            class="toggle-advanced" 
            on:click={() => showAdvancedOptions = !showAdvancedOptions}
          >
            <i class="fas fa-cog"></i>
            Advanced Options
            <i class="fas fa-chevron-{showAdvancedOptions ? 'up' : 'down'}"></i>
          </button>
          
          {#if showAdvancedOptions}
            <div class="advanced-content">
              <div class="checkbox-group">
                <label class="checkbox-label">
                  <input type="checkbox" bind:checked={preserveMetadata} />
                  <span class="checkmark"></span>
                  Preserve original metadata
                </label>
                
                <label class="checkbox-label">
                  <input type="checkbox" bind:checked={updateVersion} />
                  <span class="checkmark"></span>
                  Update version to 1.0.0
                </label>
                
                <label class="checkbox-label">
                  <input type="checkbox" bind:checked={enableRollback} />
                  <span class="checkmark"></span>
                  Enable automatic rollback on failure
                </label>
                
                <label class="checkbox-label">
                  <input type="checkbox" bind:checked={skipVerification} />
                  <span class="checkmark"></span>
                  Skip template independence verification (not recommended)
                </label>
              </div>
            </div>
          {/if}
        </div>
        
        <!-- Errors -->
        {#if errors.length > 0}
          <div class="error-section">
            <h4><i class="fas fa-exclamation-triangle"></i> Please fix the following errors:</h4>
            <ul>
              {#each errors as error}
                <li>{error}</li>
              {/each}
            </ul>
          </div>
        {/if}
        
        <!-- Actions -->
        <div class="step-actions">
          <button type="button" class="action-button secondary" on:click={cancelDuplication}>
            Cancel
          </button>
          <button 
            type="button"
            class="action-button primary" 
            on:click={proceedToPreview}
            disabled={loading}
          >
            {#if loading}
              <i class="fas fa-spinner fa-spin"></i>
              Validating...
            {:else}
              <i class="fas fa-arrow-right"></i>
              Preview & Validate
            {/if}
          </button>
        </div>
      </div>
    {:else if currentStep === 2}
      <!-- Step 2: Preview & Validation -->
      <div class="step-content">
        <h3>Duplication Preview & Validation</h3>
        <p class="step-description">
          Review what will be duplicated and validation results
        </p>
        
        {#if preview}
          <div class="preview-section">
            <h4>What will be duplicated:</h4>
            
            <!-- Backend Structure Preview -->
            <div class="structure-preview">
              <h5><i class="fas fa-server"></i> Backend Structure</h5>
              <div class="preview-grid">
                <div class="preview-item">
                  <span class="label">Files to duplicate:</span>
                  <span class="value">{preview.backend_structure.files_to_duplicate.length}</span>
                </div>
                <div class="preview-item">
                  <span class="label">Directories to duplicate:</span>
                  <span class="value">{preview.backend_structure.directories_to_duplicate.length}</span>
                </div>
              </div>
              
              {#if preview.backend_structure.files_to_duplicate.length > 0}
                <div class="file-list">
                  <strong>Files:</strong>
                  {#each preview.backend_structure.files_to_duplicate as file}
                    <span class="file-tag">{file}</span>
                  {/each}
                </div>
              {/if}
            </div>
            
            <!-- Frontend Structure Preview -->
            <div class="structure-preview">
              <h5><i class="fas fa-desktop"></i> Frontend Structure</h5>
              <div class="preview-grid">
                <div class="preview-item">
                  <span class="label">Routes to duplicate:</span>
                  <span class="value">{preview.frontend_structure.routes_to_duplicate.length}</span>
                </div>
                <div class="preview-item">
                  <span class="label">Libraries to duplicate:</span>
                  <span class="value">{preview.frontend_structure.libraries_to_duplicate.length}</span>
                </div>
              </div>
            </div>
            
            <!-- Integration Points -->
            <div class="structure-preview">
              <h5><i class="fas fa-link"></i> Integration Coordination</h5>
              <div class="integration-points">
                {#each preview.integration_points as point}
                  <div class="integration-point">
                    <i class="fas fa-check-circle"></i>
                    {point}
                  </div>
                {/each}
              </div>
            </div>
            
            <!-- Complexity & Duration -->
            <div class="duplication-metrics">
              <div class="metric">
                <span class="metric-label">Complexity:</span>
                <span class="metric-value complexity-{preview.complexity_level}">{preview.complexity_level}</span>
              </div>
              <div class="metric">
                <span class="metric-label">Estimated Duration:</span>
                <span class="metric-value">{preview.estimated_duration}</span>
              </div>
            </div>
          </div>
        {/if}
        
        {#if validation}
          <!-- Validation Results -->
          <div class="validation-section">
            <h4>
              <i class="fas fa-{validation.request_valid ? 'check-circle' : 'exclamation-triangle'}"></i>
              Validation Results
            </h4>
            
            {#if validation.request_valid}
              <div class="validation-success">
                <p><strong>✅ Validation Passed</strong> - Template is ready for duplication</p>
              </div>
            {:else}
              <div class="validation-errors">
                <p><strong>❌ Validation Failed</strong> - Please address the following issues:</p>
                <ul>
                  {#each validation.validation_errors as error}
                    <li>{error}</li>
                  {/each}
                </ul>
              </div>
            {/if}
            
            {#if validation.recommendations && validation.recommendations.length > 0}
              <div class="validation-recommendations">
                <h5>Recommendations:</h5>
                <ul>
                  {#each validation.recommendations as recommendation}
                    <li>{recommendation}</li>
                  {/each}
                </ul>
              </div>
            {/if}
            
            <!-- Requirements Check -->
            <div class="requirements-check">
              <h5>Requirements Status:</h5>
              <div class="requirements-grid">
                {#each Object.entries(validation.requirements_check) as [requirement, met]}
                  <div class="requirement-item" class:met class:not-met={!met}>
                    <i class="fas fa-{met ? 'check' : 'times'}"></i>
                    <span>{requirement.replace(/_/g, ' ')}</span>
                  </div>
                {/each}
              </div>
            </div>
          </div>
        {/if}
        
        <!-- Warnings -->
        {#if warnings.length > 0}
          <div class="warning-section">
            <h4><i class="fas fa-exclamation-triangle"></i> Warnings</h4>
            <ul>
              {#each warnings as warning}
                <li>{warning}</li>
              {/each}
            </ul>
          </div>
        {/if}
        
        <!-- Actions -->
        <div class="step-actions">
          <button type="button" class="action-button secondary" on:click={goBack}>
            <i class="fas fa-arrow-left"></i>
            Back
          </button>
          <button 
            type="button"
            class="action-button primary" 
            on:click={() => currentStep = 3}
            disabled={!validation?.request_valid}
          >
            <i class="fas fa-rocket"></i>
            Start Duplication
          </button>
        </div>
      </div>
    {:else if currentStep === 3}
      <!-- Step 3: Duplication Process -->
      <div class="step-content">
        <h3>Template Duplication in Progress</h3>
        <p class="step-description">
          Performing complete full-stack template duplication...
        </p>
        
        {#if !duplicating && !duplicationResult}
          <div class="duplication-ready">
            <div class="ready-icon">
              <i class="fas fa-rocket"></i>
            </div>
            <h4>Ready to start duplication</h4>
            <p>Click the button below to begin the enhanced template duplication process.</p>
            
            <div class="duplication-summary">
              <div class="summary-item">
                <span class="label">Source Template:</span>
                <span class="value">{sourceTemplate.name}</span>
              </div>
              <div class="summary-item">
                <span class="label">New Template ID:</span>
                <span class="value">{newTemplateId}</span>
              </div>
              <div class="summary-item">
                <span class="label">Template Name:</span>
                <span class="value">{templateName}</span>
              </div>
            </div>
            
            <button type="button" class="action-button primary large" on:click={startDuplication}>
              <i class="fas fa-play"></i>
              Start Duplication Process
            </button>
          </div>
        {:else if duplicating || progress}
          <div class="duplication-progress">
            {#if progress}
              <div class="progress-info">
                <h4>Phase: {progress.current_phase.replace(/_/g, ' ')}</h4>
                <p>{progress.current_operation}</p>
              </div>
              
              <div class="progress-bar">
                <div 
                  class="progress-fill" 
                  style="width: {progress.progress_percentage}%"
                ></div>
              </div>
              
              <div class="progress-details">
                <span class="progress-percentage">{progress.progress_percentage}%</span>
                {#if progress.estimated_completion}
                  <span class="estimated-completion">
                    ETA: {new Date(progress.estimated_completion).toLocaleTimeString()}
                  </span>
                {/if}
              </div>
            {:else}
              <div class="loading-state">
                <div class="spinner"></div>
                <p>Initializing duplication process...</p>
              </div>
            {/if}
          </div>
        {/if}
        
        <!-- Actions -->
        <div class="step-actions">
          <button 
            type="button"
            class="action-button secondary" 
            on:click={goBack}
            disabled={duplicating}
          >
            <i class="fas fa-arrow-left"></i>
            Back
          </button>
        </div>
      </div>
    {:else if currentStep === 4}
      <!-- Step 4: Results & Verification -->
      <div class="step-content">
        <h3>Duplication Results</h3>
        
        {#if duplicationResult}
          <div class="results-section">
            {#if duplicationResult.status === 'completed'}
              <div class="success-header">
                <div class="success-icon">
                  <i class="fas fa-check-circle"></i>
                </div>
                <h4>Template Duplication Completed Successfully!</h4>
                <p>Your new template "{duplicationResult.new_template}" has been created.</p>
              </div>
              
              <!-- Duration -->
              {#if duplicationResult.duration_seconds}
                <div class="duration-info">
                  <i class="fas fa-clock"></i>
                  Completed in {Math.round(duplicationResult.duration_seconds)} seconds
                </div>
              {/if}
            {:else}
              <!-- Failure Results -->
              <div class="failure-header">
                <div class="failure-icon">
                  <i class="fas fa-exclamation-triangle"></i>
                </div>
                <h4>Template Duplication Failed</h4>
                <p>The duplication process encountered errors and could not be completed.</p>
              </div>
              
              {#if duplicationResult.errors.length > 0}
                <div class="error-details">
                  <h5>Errors:</h5>
                  <ul>
                    {#each duplicationResult.errors as error}
                      <li>{error}</li>
                    {/each}
                  </ul>
                </div>
              {/if}
            {/if}
            
            <!-- Warnings -->
            {#if duplicationResult.warnings && duplicationResult.warnings.length > 0}
              <div class="warning-details">
                <h5>Warnings:</h5>
                <ul>
                  {#each duplicationResult.warnings as warning}
                    <li>{warning}</li>
                  {/each}
                </ul>
              </div>
            {/if}
          </div>
        {/if}
        
        <!-- Actions -->
        <div class="step-actions">
          {#if duplicationResult?.status === 'completed'}
            <button type="button" class="action-button secondary" on:click={resetForm}>
              <i class="fas fa-plus"></i>
              Duplicate Another
            </button>
            <button type="button" class="action-button primary" on:click={() => onDuplicationComplete(duplicationResult)}>
              <i class="fas fa-check"></i>
              Done
            </button>
          {:else}
            <button type="button" class="action-button secondary" on:click={goBack}>
              <i class="fas fa-arrow-left"></i>
              Back
            </button>
            <button type="button" class="action-button primary" on:click={cancelDuplication}>
              <i class="fas fa-times"></i>
              Close
            </button>
          {/if}
        </div>
      </div>
    {/if}
  </div>
</div>

<style>
  .enhanced-duplication-modal {
    background: white;
    border-radius: 20px;
    box-shadow: 0 24px 48px rgba(0, 0, 0, 0.15);
    max-width: 900px;
    width: 100%;
    max-height: 90vh;
    overflow-y: auto;
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  }
  
  .modal-header {
    background: linear-gradient(135deg, #002147 0%, #1e3a5f 100%);
    color: white;
    padding: 24px 32px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    border-radius: 20px 20px 0 0;
  }
  
  .modal-header h2 {
    margin: 0;
    font-size: 1.5rem;
    font-weight: 600;
  }
  
  .close-button {
    background: none;
    border: none;
    color: rgba(255, 255, 255, 0.8);
    font-size: 1.25rem;
    cursor: pointer;
    padding: 8px;
    border-radius: 8px;
    transition: all 0.2s ease;
  }
  
  .close-button:hover {
    color: white;
    background: rgba(255, 255, 255, 0.1);
  }
  
  .progress-steps {
    display: flex;
    justify-content: space-between;
    padding: 24px 32px;
    background: #f8fafc;
    border-bottom: 1px solid #e2e8f0;
  }
  
  .step {
    display: flex;
    flex-direction: column;
    align-items: center;
    flex: 1;
    position: relative;
  }
  
  .step:not(:last-child)::after {
    content: '';
    position: absolute;
    top: 16px;
    right: -50%;
    width: 100%;
    height: 2px;
    background: #e2e8f0;
    z-index: 1;
  }
  
  .step.completed:not(:last-child)::after {
    background: #10b981;
  }
  
  .step-number {
    width: 32px;
    height: 32px;
    border-radius: 50%;
    background: #e2e8f0;
    color: #64748b;
    display: flex;
    align-items: center;
    justify-content: center;
    font-weight: 600;
    font-size: 0.875rem;
    margin-bottom: 8px;
    position: relative;
    z-index: 2;
    transition: all 0.2s ease;
  }
  
  .step.active .step-number {
    background: #002147;
    color: white;
  }
  
  .step.completed .step-number {
    background: #10b981;
    color: white;
  }
  
  .step-title {
    font-size: 0.75rem;
    color: #64748b;
    text-align: center;
    font-weight: 500;
  }
  
  .step.active .step-title {
    color: #002147;
    font-weight: 600;
  }
  
  .modal-content {
    padding: 32px;
  }
  
  .step-content {
    max-width: 100%;
  }
  
  .step-content h3 {
    margin: 0 0 8px 0;
    color: #1e293b;
    font-size: 1.5rem;
    font-weight: 700;
  }
  
  .step-description {
    margin: 0 0 32px 0;
    color: #64748b;
    font-size: 1rem;
    line-height: 1.5;
  }
  
  .form-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
    gap: 24px;
    margin-bottom: 24px;
  }
  
  .form-group {
    margin-bottom: 24px;
  }
  
  .form-group label {
    display: block;
    margin-bottom: 8px;
    font-weight: 600;
    color: #374151;
    font-size: 0.875rem;
  }
  
  .form-input, .form-select, .form-textarea {
    width: 100%;
    padding: 12px 16px;
    border: 2px solid #e5e7eb;
    border-radius: 10px;
    font-size: 0.875rem;
    transition: all 0.2s ease;
    font-family: inherit;
  }
  
  .form-input:focus, .form-select:focus, .form-textarea:focus {
    outline: none;
    border-color: #002147;
    box-shadow: 0 0 0 3px rgba(0, 33, 71, 0.1);
  }
  
  .form-input.error, .form-textarea.error {
    border-color: #ef4444;
    box-shadow: 0 0 0 3px rgba(239, 68, 68, 0.1);
  }
  
  .input-help {
    margin-top: 4px;
    font-size: 0.75rem;
    color: #64748b;
  }
  
  .form-textarea {
    resize: vertical;
    min-height: 100px;
  }
  
  .advanced-options {
    margin-top: 32px;
    border: 1px solid #e2e8f0;
    border-radius: 12px;
    overflow: hidden;
  }
  
  .toggle-advanced {
    width: 100%;
    padding: 16px 20px;
    background: #f8fafc;
    border: none;
    display: flex;
    align-items: center;
    justify-content: space-between;
    font-weight: 500;
    color: #374151;
    cursor: pointer;
    transition: all 0.2s ease;
  }
  
  .toggle-advanced:hover {
    background: #f1f5f9;
  }
  
  .advanced-content {
    padding: 20px;
    background: white;
    border-top: 1px solid #e2e8f0;
  }
  
  .checkbox-group {
    display: flex;
    flex-direction: column;
    gap: 16px;
  }
  
  .checkbox-label {
    display: flex;
    align-items: center;
    gap: 12px;
    font-size: 0.875rem;
    color: #374151;
    cursor: pointer;
  }
  
  .checkbox-label input[type="checkbox"] {
    margin: 0;
  }
  
  .error-section {
    background: #fef2f2;
    border: 1px solid #fecaca;
    border-radius: 12px;
    padding: 20px;
    margin-top: 24px;
  }
  
  .error-section h4 {
    margin: 0 0 12px 0;
    color: #dc2626;
    font-size: 1rem;
    font-weight: 600;
  }
  
  .error-section ul {
    margin: 0;
    padding-left: 20px;
    color: #dc2626;
  }
  
  .step-actions {
    display: flex;
    justify-content: flex-end;
    gap: 16px;
    margin-top: 32px;
    padding-top: 24px;
    border-top: 1px solid #e2e8f0;
  }
  
  .action-button {
    padding: 12px 24px;
    border: none;
    border-radius: 10px;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.2s ease;
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 0.875rem;
  }
  
  .action-button.primary {
    background: linear-gradient(135deg, #002147, #1e3a5f);
    color: white;
  }
  
  .action-button.primary:hover:not(:disabled) {
    transform: translateY(-2px);
    box-shadow: 0 8px 24px rgba(0, 33, 71, 0.3);
  }
  
  .action-button.secondary {
    background: #f8fafc;
    color: #64748b;
    border: 1px solid #e2e8f0;
  }
  
  .action-button.secondary:hover:not(:disabled) {
    background: #f1f5f9;
    color: #475569;
  }
  
  .action-button.large {
    padding: 16px 32px;
    font-size: 1rem;
  }
  
  .action-button:disabled {
    opacity: 0.5;
    cursor: not-allowed;
    transform: none;
  }
  
  .preview-section {
    background: #f8fafc;
    border-radius: 12px;
    padding: 24px;
    margin-bottom: 24px;
  }
  
  .structure-preview {
    margin-bottom: 24px;
    padding: 20px;
    background: white;
    border-radius: 12px;
    border: 1px solid #e2e8f0;
  }
  
  .structure-preview h5 {
    margin: 0 0 16px 0;
    color: #1e293b;
    font-size: 1.125rem;
    font-weight: 600;
    display: flex;
    align-items: center;
    gap: 8px;
  }
  
  .preview-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: 16px;
    margin-bottom: 16px;
  }
  
  .preview-item {
    display: flex;
    justify-content: space-between;
    padding: 12px 16px;
    background: #f8fafc;
    border-radius: 8px;
    border: 1px solid #e2e8f0;
  }
  
  .preview-item .label {
    color: #64748b;
    font-size: 0.875rem;
  }
  
  .preview-item .value {
    color: #1e293b;
    font-weight: 600;
    font-size: 0.875rem;
  }
  
  .file-list {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    align-items: center;
  }
  
  .file-tag {
    background: #eff6ff;
    color: #1e40af;
    padding: 4px 8px;
    border-radius: 6px;
    font-size: 0.75rem;
    font-weight: 500;
  }
  
  .integration-points {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }
  
  .integration-point {
    display: flex;
    align-items: center;
    gap: 8px;
    color: #374151;
    font-size: 0.875rem;
  }
  
  .integration-point i {
    color: #10b981;
  }
  
  .duplication-metrics {
    display: flex;
    gap: 24px;
    margin-top: 20px;
    padding: 16px;
    background: #f1f5f9;
    border-radius: 8px;
  }
  
  .metric {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }
  
  .metric-label {
    font-size: 0.75rem;
    color: #64748b;
    font-weight: 500;
  }
  
  .metric-value {
    font-size: 1rem;
    font-weight: 600;
    color: #1e293b;
  }
  
  .complexity-low { color: #10b981; }
  .complexity-medium { color: #f59e0b; }
  .complexity-high { color: #ef4444; }
  .complexity-very_high { color: #dc2626; }
  
  .validation-section {
    background: #f8fafc;
    border-radius: 12px;
    padding: 24px;
    margin-bottom: 24px;
  }
  
  .validation-success {
    background: #dcfce7;
    border: 1px solid #bbf7d0;
    border-radius: 8px;
    padding: 16px;
    margin-bottom: 16px;
  }
  
  .validation-errors {
    background: #fef2f2;
    border: 1px solid #fecaca;
    border-radius: 8px;
    padding: 16px;
    margin-bottom: 16px;
  }
  
  .validation-recommendations {
    background: #fffbeb;
    border: 1px solid #fed7aa;
    border-radius: 8px;
    padding: 16px;
    margin-bottom: 16px;
  }
  
  .requirements-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
    gap: 12px;
    margin-top: 12px;
  }
  
  .requirement-item {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 8px 12px;
    border-radius: 6px;
    font-size: 0.875rem;
  }
  
  .requirement-item.met {
    background: #dcfce7;
    color: #166534;
  }
  
  .requirement-item.not-met {
    background: #fef2f2;
    color: #dc2626;
  }
  
  .warning-section {
    background: #fffbeb;
    border: 1px solid #fed7aa;
    border-radius: 12px;
    padding: 20px;
    margin-bottom: 24px;
  }
  
  .warning-section h4 {
    margin: 0 0 12px 0;
    color: #d97706;
    font-size: 1rem;
    font-weight: 600;
  }
  
  .duplication-ready {
    text-align: center;
    padding: 40px 20px;
  }
  
  .ready-icon {
    width: 80px;
    height: 80px;
    background: linear-gradient(135deg, #002147, #1e3a5f);
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    margin: 0 auto 20px;
    color: white;
    font-size: 2rem;
  }
  
  .duplication-summary {
    background: #f8fafc;
    border-radius: 12px;
    padding: 20px;
    margin: 24px 0;
    text-align: left;
  }
  
  .summary-item {
    display: flex;
    justify-content: space-between;
    padding: 8px 0;
    border-bottom: 1px solid #e2e8f0;
  }
  
  .summary-item:last-child {
    border-bottom: none;
  }
  
  .summary-item .label {
    color: #64748b;
    font-weight: 500;
  }
  
  .summary-item .value {
    color: #1e293b;
    font-weight: 600;
  }
  
  .duplication-progress {
    text-align: center;
    padding: 40px 20px;
  }
  
  .progress-info h4 {
    margin: 0 0 8px 0;
    color: #1e293b;
    font-size: 1.25rem;
    font-weight: 600;
    text-transform: capitalize;
  }
  
  .progress-info p {
    margin: 0 0 24px 0;
    color: #64748b;
  }
  
  .progress-bar {
    width: 100%;
    height: 8px;
    background: #e2e8f0;
    border-radius: 4px;
    overflow: hidden;
    margin-bottom: 16px;
  }
  
  .progress-fill {
    height: 100%;
    background: linear-gradient(90deg, #002147, #1e3a5f);
    border-radius: 4px;
    transition: width 0.3s ease;
  }
  
  .progress-details {
    display: flex;
    justify-content: space-between;
    font-size: 0.875rem;
  }
  
  .progress-percentage {
    color: #1e293b;
    font-weight: 600;
  }
  
  .estimated-completion {
    color: #64748b;
  }
  
  .loading-state {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 16px;
  }
  
  .spinner {
    width: 32px;
    height: 32px;
    border: 3px solid #e5e7eb;
    border-top: 3px solid #002147;
    border-radius: 50%;
    animation: spin 1s linear infinite;
  }
  
  @keyframes spin {
    0% { transform: rotate(0deg); }
    100% { transform: rotate(360deg); }
  }
  
  .results-section {
    margin-bottom: 24px;
  }
  
  .success-header, .failure-header {
    text-align: center;
    padding: 24px;
    margin-bottom: 32px;
  }
  
  .success-icon {
    width: 80px;
    height: 80px;
    background: #10b981;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    margin: 0 auto 16px;
    color: white;
    font-size: 2rem;
  }
  
  .failure-icon {
    width: 80px;
    height: 80px;
    background: #ef4444;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    margin: 0 auto 16px;
    color: white;
    font-size: 2rem;
  }
  
  .success-header h4, .failure-header h4 {
    margin: 0 0 8px 0;
    font-size: 1.5rem;
    font-weight: 700;
  }
  
  .success-header h4 {
    color: #10b981;
  }
  
  .failure-header h4 {
    color: #ef4444;
  }
  
  .error-details, .warning-details {
    background: #fef2f2;
    border: 1px solid #fecaca;
    border-radius: 12px;
    padding: 20px;
    margin-top: 24px;
  }
  
  .warning-details {
    background: #fffbeb;
    border-color: #fed7aa;
  }
  
  .error-details h5, .warning-details h5 {
    margin: 0 0 12px 0;
    font-size: 1rem;
    font-weight: 600;
  }
  
  .error-details h5 {
    color: #dc2626;
  }
  
  .warning-details h5 {
    color: #d97706;
  }
  
  .duration-info {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
    margin-bottom: 24px;
    padding: 12px 20px;
    background: #f1f5f9;
    border-radius: 8px;
    color: #64748b;
    font-size: 0.875rem;
  }
  
  /* Responsive Design */
  @media (max-width: 768px) {
    .enhanced-duplication-modal {
      margin: 10px;
      max-width: calc(100% - 20px);
    }
    
    .modal-header {
      padding: 20px 24px;
    }
    
    .modal-content {
      padding: 24px;
    }
    
    .progress-steps {
      padding: 20px 24px;
    }
    
    .step {
      font-size: 0.75rem;
    }
    
    .form-grid {
      grid-template-columns: 1fr;
    }
    
    .step-actions {
      flex-direction: column;
    }
    
    .action-button {
      justify-content: center;
    }
    
    .preview-grid {
      grid-template-columns: 1fr;
    }
    
    .requirements-grid {
      grid-template-columns: 1fr;
    }
    
    .duplication-metrics {
      flex-direction: column;
      gap: 12px;
    }
  }
</style>
