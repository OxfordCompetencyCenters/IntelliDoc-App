<!-- WorkflowEvaluation.svelte - Workflow Evaluation Component -->
<script lang="ts">
  import { onMount } from 'svelte';
  import { toasts } from '$lib/stores/toast';
  import { cleanUniversalApi } from '$lib/services/cleanUniversalApi';
  import { get } from 'svelte/store';
  import authStore from '$lib/stores/auth';
  
  export let project: any;
  export let projectId: string;
  
  // Component state
  let workflows: any[] = [];
  let selectedWorkflow: any = null;
  let csvFile: File | null = null;
  let csvFileName = '';
  let evaluating = false;
  let currentEvaluation: any = null;
  let evaluationResults: any[] = [];
  let aggregateStats: any = null;
  let evaluationHistory: any[] = [];
  let showHistory = false;
  
  // File upload state
  let dragActive = false;
  let fileInput: HTMLInputElement;
  
  onMount(() => {
    loadWorkflows();
    loadEvaluationHistory();
  });
  
  async function loadWorkflows() {
    try {
      console.log(`📋 EVALUATION: Loading workflows for project ${projectId}`);
      
      // Get auth token
      const auth = get(authStore);
      const token = auth?.token || '';
      
      // Use the correct endpoint - workflows are under /api/projects/{projectId}/workflows/
      const response = await fetch(`/api/projects/${projectId}/workflows/`, {
        method: 'GET',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      });
      
      if (!response.ok) {
        throw new Error(`Failed to load workflows: ${response.status}`);
      }
      
      const data = await response.json();
      workflows = Array.isArray(data) ? data : (data.workflows || data.results || []);
      console.log(`✅ EVALUATION: Loaded ${workflows.length} workflows`);
      
      if (workflows.length > 0 && !selectedWorkflow) {
        selectedWorkflow = workflows[0];
      }
    } catch (error) {
      console.error('❌ EVALUATION: Failed to load workflows:', error);
      toasts.error('Failed to load workflows');
    }
  }
  
  async function loadEvaluationHistory() {
    if (!selectedWorkflow) return;
    
    try {
      evaluationHistory = await cleanUniversalApi.getEvaluationHistory(projectId, selectedWorkflow.workflow_id);
    } catch (error) {
      console.error('❌ EVALUATION: Failed to load evaluation history:', error);
    }
  }
  
  function handleFileSelect(event: Event) {
    const input = event.target as HTMLInputElement;
    if (input.files && input.files.length > 0) {
      csvFile = input.files[0];
      csvFileName = csvFile.name;
      console.log(`📄 EVALUATION: Selected CSV file: ${csvFileName}`);
    }
  }
  
  function handleDragOver(event: DragEvent) {
    event.preventDefault();
    dragActive = true;
  }
  
  function handleDragLeave(event: DragEvent) {
    event.preventDefault();
    dragActive = false;
  }
  
  function handleDrop(event: DragEvent) {
    event.preventDefault();
    dragActive = false;
    
    if (event.dataTransfer?.files && event.dataTransfer.files.length > 0) {
      const file = event.dataTransfer.files[0];
      if (file.name.toLowerCase().endsWith('.csv')) {
        csvFile = file;
        csvFileName = file.name;
        console.log(`📄 EVALUATION: Dropped CSV file: ${csvFileName}`);
      } else {
        toasts.error('Please drop a CSV file');
      }
    }
  }
  
  async function startEvaluation() {
    if (!selectedWorkflow) {
      toasts.error('Please select a workflow');
      return;
    }
    
    if (!csvFile) {
      toasts.error('Please upload a CSV file');
      return;
    }
    
    try {
      evaluating = true;
      console.log(`🚀 EVALUATION: Starting evaluation for workflow ${selectedWorkflow.workflow_id}`);
      
      const result = await cleanUniversalApi.evaluateWorkflow(
        projectId,
        selectedWorkflow.workflow_id,
        csvFile
      );
      
      currentEvaluation = result;
      console.log(`✅ EVALUATION: Evaluation started - ID: ${result.evaluation_id}`);
      
      toasts.success(`Evaluation started successfully`);
      
      // Poll for results
      await pollEvaluationResults(result.evaluation_id);
      
    } catch (error) {
      console.error('❌ EVALUATION: Evaluation failed:', error);
      toasts.error(error.message || 'Failed to start evaluation');
    } finally {
      evaluating = false;
    }
  }
  
  async function pollEvaluationResults(evaluationId: string) {
    const maxAttempts = 300; // 5 minutes max (1 second intervals)
    let attempts = 0;
    
    while (attempts < maxAttempts) {
      try {
        const results = await cleanUniversalApi.getEvaluationResults(
          projectId,
          selectedWorkflow.workflow_id,
          evaluationId
        );
        
        currentEvaluation = results;
        evaluationResults = results.results || [];
        aggregateStats = results.aggregate_statistics;
        
        if (results.status === 'completed' || results.status === 'failed') {
          console.log(`✅ EVALUATION: Evaluation ${results.status}`);
          break;
        }
        
        // Wait 1 second before next poll
        await new Promise(resolve => setTimeout(resolve, 1000));
        attempts++;
        
      } catch (error) {
        console.error('❌ EVALUATION: Failed to poll results:', error);
        break;
      }
    }
  }
  
  async function loadEvaluationResults(evaluationId: string) {
    if (!selectedWorkflow) return;
    
    try {
      const results = await cleanUniversalApi.getEvaluationResults(
        projectId,
        selectedWorkflow.workflow_id,
        evaluationId
      );
      
      currentEvaluation = results;
      evaluationResults = results.results || [];
      aggregateStats = results.aggregate_statistics;
      showHistory = false;
      
    } catch (error) {
      console.error('❌ EVALUATION: Failed to load results:', error);
      toasts.error('Failed to load evaluation results');
    }
  }
  
  function exportResultsToCSV() {
    if (!evaluationResults || evaluationResults.length === 0) {
      toasts.error('No results to export');
      return;
    }
    
    // Create CSV content
    const headers = [
      'Row Number',
      'Input Text',
      'Expected Output',
      'Workflow Output',
      'ROUGE-1',
      'ROUGE-2',
      'ROUGE-L',
      'BLEU',
      'BERTScore',
      'Semantic Similarity',
      'Average Score',
      'Status',
      'Execution Time (s)'
    ];
    
    const rows = evaluationResults.map(result => [
      result.row_number,
      `"${(result.input_text || '').replace(/"/g, '""')}"`,
      `"${(result.expected_output || '').replace(/"/g, '""')}"`,
      `"${(result.workflow_output || '').replace(/"/g, '""')}"`,
      result.rouge_1_score?.toFixed(4) || '',
      result.rouge_2_score?.toFixed(4) || '',
      result.rouge_l_score?.toFixed(4) || '',
      result.bleu_score?.toFixed(4) || '',
      result.bert_score?.toFixed(4) || '',
      result.semantic_similarity?.toFixed(4) || '',
      result.average_score?.toFixed(4) || '',
      result.status,
      result.execution_time_seconds?.toFixed(2) || ''
    ]);
    
    const csvContent = [
      headers.join(','),
      ...rows.map(row => row.join(','))
    ].join('\n');
    
    // Download CSV
    const blob = new Blob([csvContent], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `evaluation_results_${currentEvaluation?.evaluation_id || 'results'}.csv`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    
    toasts.success('Results exported to CSV');
  }
  
  function formatScore(score: number | null | undefined): string {
    if (score === null || score === undefined) return '-';
    return (score * 100).toFixed(2) + '%';
  }
  
  function getScoreColor(score: number | null | undefined): string {
    if (score === null || score === undefined) return 'text-gray-500';
    if (score >= 0.8) return 'text-green-600';
    if (score >= 0.6) return 'text-yellow-600';
    return 'text-red-600';
  }
</script>

<div class="evaluation-page">
  <div class="evaluation-header">
    <h1 class="evaluation-title">
      <i class="fas fa-clipboard-check"></i>
      Workflow Evaluation
    </h1>
    <p class="evaluation-subtitle">
      Evaluate workflows using CSV input/output pairs with comprehensive metrics
    </p>
  </div>
  
  <!-- Workflow Selection -->
  <div class="evaluation-section">
    <h2 class="section-title">Select Workflow</h2>
    <div class="workflow-selector">
      <select
        bind:value={selectedWorkflow}
        on:change={() => {
          loadEvaluationHistory();
          currentEvaluation = null;
          evaluationResults = [];
        }}
        class="workflow-select"
        disabled={evaluating}
      >
        {#if workflows.length === 0}
          <option value={null}>No workflows available</option>
        {:else}
          {#each workflows as workflow}
            <option value={workflow}>{workflow.name}</option>
          {/each}
        {/if}
      </select>
    </div>
  </div>
  
  <!-- CSV Upload -->
  <div class="evaluation-section">
    <h2 class="section-title">Upload CSV File</h2>
    <p class="section-description">
      Upload a CSV file with columns: <strong>input</strong> and <strong>expected_output</strong>
    </p>
    
    <div
      class="csv-upload-area {dragActive ? 'drag-active' : ''}"
      on:dragover={handleDragOver}
      on:dragleave={handleDragLeave}
      on:drop={handleDrop}
    >
      {#if csvFile}
        <div class="file-selected">
          <i class="fas fa-file-csv"></i>
          <span>{csvFileName}</span>
          <button
            class="remove-file-btn"
            on:click={() => { csvFile = null; csvFileName = ''; }}
          >
            <i class="fas fa-times"></i>
          </button>
        </div>
      {:else}
        <div class="upload-prompt">
          <i class="fas fa-cloud-upload-alt"></i>
          <p>Drop CSV file here or click to browse</p>
          <button
            class="browse-btn"
            on:click={() => fileInput?.click()}
          >
            Browse Files
          </button>
        </div>
      {/if}
      
      <input
        type="file"
        accept=".csv"
        bind:this={fileInput}
        on:change={handleFileSelect}
        class="hidden"
      />
    </div>
    
    <div class="csv-format-info">
      <p><strong>CSV Format:</strong></p>
      <pre>input,expected_output
"Tell me a joke","Why did the chicken cross the road?"
"Summarize AI","AI is artificial intelligence..."</pre>
    </div>
  </div>
  
  <!-- Evaluation Actions -->
  <div class="evaluation-actions">
    <button
      class="evaluate-btn"
      on:click={startEvaluation}
      disabled={!selectedWorkflow || !csvFile || evaluating}
    >
      {#if evaluating}
        <i class="fas fa-spinner fa-spin"></i>
        Evaluating...
      {:else}
        <i class="fas fa-play"></i>
        Start Evaluation
      {/if}
    </button>
    
    <button
      class="history-btn"
      on:click={() => {
        showHistory = !showHistory;
        if (showHistory) loadEvaluationHistory();
      }}
      disabled={evaluating}
    >
      <i class="fas fa-history"></i>
      {showHistory ? 'Hide' : 'Show'} History
    </button>
  </div>
  
  <!-- Evaluation History -->
  {#if showHistory && evaluationHistory.length > 0}
    <div class="evaluation-section">
      <h2 class="section-title">Evaluation History</h2>
      <div class="history-table">
        <table>
          <thead>
            <tr>
              <th>Date</th>
              <th>CSV File</th>
              <th>Total Rows</th>
              <th>Completed</th>
              <th>Failed</th>
              <th>Status</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {#each evaluationHistory as evaluation}
              <tr>
                <td>{new Date(evaluation.created_at).toLocaleString()}</td>
                <td>{evaluation.csv_filename}</td>
                <td>{evaluation.total_rows}</td>
                <td>{evaluation.completed_rows}</td>
                <td>{evaluation.failed_rows}</td>
                <td>
                  <span class="status-badge status-{evaluation.status}">
                    {evaluation.status}
                  </span>
                </td>
                <td>
                  <button
                    class="view-results-btn"
                    on:click={() => loadEvaluationResults(evaluation.evaluation_id)}
                  >
                    View Results
                  </button>
                </td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
    </div>
  {/if}
  
  <!-- Current Evaluation Progress -->
  {#if currentEvaluation && (currentEvaluation.status === 'running' || evaluating)}
    <div class="evaluation-section">
      <h2 class="section-title">Evaluation Progress</h2>
      <div class="progress-info">
        <div class="progress-bar-container">
          <div
            class="progress-bar"
            style="width: {(currentEvaluation.completed_rows / currentEvaluation.total_rows * 100)}%"
          ></div>
        </div>
        <div class="progress-stats">
          <span>Completed: {currentEvaluation.completed_rows} / {currentEvaluation.total_rows}</span>
          <span>Failed: {currentEvaluation.failed_rows}</span>
        </div>
      </div>
    </div>
  {/if}
  
  <!-- Evaluation Results -->
  {#if currentEvaluation && evaluationResults.length > 0}
    <div class="evaluation-section">
      <div class="results-header">
        <h2 class="section-title">Evaluation Results</h2>
        <button
          class="export-btn"
          on:click={exportResultsToCSV}
        >
          <i class="fas fa-download"></i>
          Export to CSV
        </button>
      </div>
      
      <!-- Aggregate Statistics -->
      {#if aggregateStats}
        <div class="aggregate-stats">
          <h3>Average Scores</h3>
          <div class="stats-grid">
            <div class="stat-item">
              <span class="stat-label">ROUGE-1</span>
              <span class="stat-value">{formatScore(aggregateStats.rouge_1)}</span>
            </div>
            <div class="stat-item">
              <span class="stat-label">ROUGE-2</span>
              <span class="stat-value">{formatScore(aggregateStats.rouge_2)}</span>
            </div>
            <div class="stat-item">
              <span class="stat-label">ROUGE-L</span>
              <span class="stat-value">{formatScore(aggregateStats.rouge_l)}</span>
            </div>
            <div class="stat-item">
              <span class="stat-label">BLEU</span>
              <span class="stat-value">{formatScore(aggregateStats.bleu)}</span>
            </div>
            <div class="stat-item">
              <span class="stat-label">BERTScore</span>
              <span class="stat-value">{formatScore(aggregateStats.bert_score)}</span>
            </div>
            <div class="stat-item">
              <span class="stat-label">Semantic Similarity</span>
              <span class="stat-value">{formatScore(aggregateStats.semantic_similarity)}</span>
            </div>
            <div class="stat-item stat-item-highlight">
              <span class="stat-label">Overall Average</span>
              <span class="stat-value">{formatScore(aggregateStats.average_score)}</span>
            </div>
          </div>
        </div>
      {/if}
      
      <!-- Results Table -->
      <div class="results-table-container">
        <table class="results-table">
          <thead>
            <tr>
              <th>Row</th>
              <th>Input</th>
              <th>Expected Output</th>
              <th>Workflow Output</th>
              <th>ROUGE-1</th>
              <th>ROUGE-2</th>
              <th>ROUGE-L</th>
              <th>BLEU</th>
              <th>BERT</th>
              <th>Semantic</th>
              <th>Average</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {#each evaluationResults as result}
              <tr class={result.status === 'failed' ? 'row-failed' : ''}>
                <td>{result.row_number}</td>
                <td class="text-cell" title={result.input_text}>
                  {result.input_text?.substring(0, 50)}{result.input_text?.length > 50 ? '...' : ''}
                </td>
                <td class="text-cell" title={result.expected_output}>
                  {result.expected_output?.substring(0, 50)}{result.expected_output?.length > 50 ? '...' : ''}
                </td>
                <td class="text-cell" title={result.workflow_output}>
                  {result.workflow_output?.substring(0, 50)}{result.workflow_output?.length > 50 ? '...' : ''}
                </td>
                <td class={getScoreColor(result.rouge_1_score)}>
                  {formatScore(result.rouge_1_score)}
                </td>
                <td class={getScoreColor(result.rouge_2_score)}>
                  {formatScore(result.rouge_2_score)}
                </td>
                <td class={getScoreColor(result.rouge_l_score)}>
                  {formatScore(result.rouge_l_score)}
                </td>
                <td class={getScoreColor(result.bleu_score)}>
                  {formatScore(result.bleu_score)}
                </td>
                <td class={getScoreColor(result.bert_score)}>
                  {formatScore(result.bert_score)}
                </td>
                <td class={getScoreColor(result.semantic_similarity)}>
                  {formatScore(result.semantic_similarity)}
                </td>
                <td class={getScoreColor(result.average_score)}>
                  <strong>{formatScore(result.average_score)}</strong>
                </td>
                <td>
                  <span class="status-badge status-{result.status}">
                    {result.status}
                  </span>
                </td>
              </tr>
              {#if result.error_message}
                <tr class="error-row">
                  <td colspan="12" class="error-message">
                    <i class="fas fa-exclamation-triangle"></i>
                    Error: {result.error_message}
                  </td>
                </tr>
              {/if}
            {/each}
          </tbody>
        </table>
      </div>
    </div>
  {/if}
</div>

<style>
  .evaluation-page {
    padding: 24px;
    max-width: 1400px;
    margin: 0 auto;
  }
  
  .evaluation-header {
    margin-bottom: 32px;
  }
  
  .evaluation-title {
    font-size: 2rem;
    font-weight: 700;
    color: #111827;
    margin: 0 0 8px 0;
    display: flex;
    align-items: center;
    gap: 12px;
  }
  
  .evaluation-title i {
    color: #002147;
  }
  
  .evaluation-subtitle {
    color: #6b7280;
    font-size: 1rem;
    margin: 0;
  }
  
  .evaluation-section {
    background: white;
    border-radius: 12px;
    padding: 24px;
    margin-bottom: 24px;
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
  }
  
  .section-title {
    font-size: 1.25rem;
    font-weight: 600;
    color: #111827;
    margin: 0 0 16px 0;
  }
  
  .section-description {
    color: #6b7280;
    margin: 0 0 16px 0;
  }
  
  .workflow-selector {
    margin-bottom: 16px;
  }
  
  .workflow-select {
    width: 100%;
    padding: 10px 12px;
    border: 1px solid #d1d5db;
    border-radius: 6px;
    font-size: 0.875rem;
    background: white;
  }
  
  .workflow-select:focus {
    outline: none;
    border-color: #002147;
    box-shadow: 0 0 0 3px rgba(0, 33, 71, 0.1);
  }
  
  .csv-upload-area {
    border: 2px dashed #d1d5db;
    border-radius: 8px;
    padding: 48px;
    text-align: center;
    transition: all 0.2s ease;
    background: #f9fafb;
  }
  
  .csv-upload-area.drag-active {
    border-color: #002147;
    background: #eff6ff;
  }
  
  .upload-prompt {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 16px;
  }
  
  .upload-prompt i {
    font-size: 3rem;
    color: #9ca3af;
  }
  
  .upload-prompt p {
    color: #6b7280;
    margin: 0;
  }
  
  .browse-btn {
    padding: 10px 20px;
    background: #002147;
    color: white;
    border: none;
    border-radius: 6px;
    font-weight: 500;
    cursor: pointer;
    transition: background 0.2s ease;
  }
  
  .browse-btn:hover {
    background: #1e3a5f;
  }
  
  .file-selected {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 12px;
    color: #111827;
    font-weight: 500;
  }
  
  .file-selected i {
    font-size: 1.5rem;
    color: #002147;
  }
  
  .remove-file-btn {
    background: none;
    border: none;
    color: #ef4444;
    cursor: pointer;
    padding: 4px 8px;
    border-radius: 4px;
    transition: background 0.2s ease;
  }
  
  .remove-file-btn:hover {
    background: #fef2f2;
  }
  
  .csv-format-info {
    margin-top: 16px;
    padding: 16px;
    background: #f3f4f6;
    border-radius: 6px;
  }
  
  .csv-format-info pre {
    margin: 8px 0 0 0;
    font-size: 0.875rem;
    color: #374151;
  }
  
  .hidden {
    display: none;
  }
  
  .evaluation-actions {
    display: flex;
    gap: 12px;
    margin-bottom: 24px;
  }
  
  .evaluate-btn, .history-btn {
    padding: 12px 24px;
    border: none;
    border-radius: 6px;
    font-weight: 500;
    cursor: pointer;
    display: flex;
    align-items: center;
    gap: 8px;
    transition: all 0.2s ease;
  }
  
  .evaluate-btn {
    background: linear-gradient(135deg, #002147, #1e3a5f);
    color: white;
  }
  
  .evaluate-btn:hover:not(:disabled) {
    transform: translateY(-1px);
    box-shadow: 0 4px 12px rgba(0, 33, 71, 0.25);
  }
  
  .evaluate-btn:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
  
  .history-btn {
    background: white;
    color: #374151;
    border: 1px solid #d1d5db;
  }
  
  .history-btn:hover:not(:disabled) {
    background: #f9fafb;
  }
  
  .history-table {
    overflow-x: auto;
  }
  
  .history-table table {
    width: 100%;
    border-collapse: collapse;
  }
  
  .history-table th,
  .history-table td {
    padding: 12px;
    text-align: left;
    border-bottom: 1px solid #e5e7eb;
  }
  
  .history-table th {
    background: #f9fafb;
    font-weight: 600;
    color: #374151;
  }
  
  .status-badge {
    padding: 4px 8px;
    border-radius: 4px;
    font-size: 0.75rem;
    font-weight: 500;
    text-transform: capitalize;
  }
  
  .status-completed {
    background: #d1fae5;
    color: #065f46;
  }
  
  .status-running {
    background: #dbeafe;
    color: #1e40af;
  }
  
  .status-failed {
    background: #fee2e2;
    color: #991b1b;
  }
  
  .status-success {
    background: #d1fae5;
    color: #065f46;
  }
  
  .view-results-btn {
    padding: 6px 12px;
    background: #002147;
    color: white;
    border: none;
    border-radius: 4px;
    font-size: 0.875rem;
    cursor: pointer;
    transition: background 0.2s ease;
  }
  
  .view-results-btn:hover {
    background: #1e3a5f;
  }
  
  .progress-info {
    margin-top: 16px;
  }
  
  .progress-bar-container {
    width: 100%;
    height: 24px;
    background: #e5e7eb;
    border-radius: 12px;
    overflow: hidden;
    margin-bottom: 8px;
  }
  
  .progress-bar {
    height: 100%;
    background: linear-gradient(90deg, #002147, #1e3a5f);
    transition: width 0.3s ease;
  }
  
  .progress-stats {
    display: flex;
    justify-content: space-between;
    font-size: 0.875rem;
    color: #6b7280;
  }
  
  .results-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 24px;
  }
  
  .export-btn {
    padding: 8px 16px;
    background: #10b981;
    color: white;
    border: none;
    border-radius: 6px;
    font-weight: 500;
    cursor: pointer;
    display: flex;
    align-items: center;
    gap: 8px;
    transition: background 0.2s ease;
  }
  
  .export-btn:hover {
    background: #059669;
  }
  
  .aggregate-stats {
    margin-bottom: 24px;
    padding: 20px;
    background: #f9fafb;
    border-radius: 8px;
  }
  
  .aggregate-stats h3 {
    margin: 0 0 16px 0;
    font-size: 1rem;
    font-weight: 600;
    color: #111827;
  }
  
  .stats-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
    gap: 16px;
  }
  
  .stat-item {
    text-align: center;
    padding: 12px;
    background: white;
    border-radius: 6px;
  }
  
  .stat-item-highlight {
    background: #eff6ff;
    border: 2px solid #002147;
  }
  
  .stat-label {
    display: block;
    font-size: 0.75rem;
    color: #6b7280;
    margin-bottom: 4px;
  }
  
  .stat-value {
    display: block;
    font-size: 1.25rem;
    font-weight: 600;
    color: #111827;
  }
  
  .results-table-container {
    overflow-x: auto;
  }
  
  .results-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.875rem;
  }
  
  .results-table th,
  .results-table td {
    padding: 10px;
    text-align: left;
    border-bottom: 1px solid #e5e7eb;
  }
  
  .results-table th {
    background: #f9fafb;
    font-weight: 600;
    color: #374151;
    position: sticky;
    top: 0;
  }
  
  .results-table td.text-cell {
    max-width: 200px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  
  .results-table .row-failed {
    background: #fef2f2;
  }
  
  .error-row {
    background: #fef2f2;
  }
  
  .error-message {
    color: #991b1b;
    padding: 8px 10px;
    font-size: 0.8125rem;
  }
  
  .text-green-600 {
    color: #16a34a;
  }
  
  .text-yellow-600 {
    color: #ca8a04;
  }
  
  .text-red-600 {
    color: #dc2626;
  }
  
  .text-gray-500 {
    color: #6b7280;
  }
</style>

