<!-- src/routes/features/intellidoc/+page.svelte -->
<script lang="ts">
  import { onMount } from 'svelte';
  import { toasts } from '$lib/stores/toast';
  import { cleanUniversalApi } from '$lib/services/cleanUniversalApi';
  import authStore, { isAdmin } from '$lib/stores/auth';
  import { get } from 'svelte/store';
  import { goto } from '$app/navigation';
  import ProjectCreator from '$lib/components/ProjectCreator.svelte';
  import AdminDeleteButton from '$lib/components/AdminDeleteButton.svelte';
  import type { IntelliDocProject } from '$lib/types';
  
  // State variables
  let projects: IntelliDocProject[] = [];
  let loading = true;
  let showCreateForm = false;
  let showDeleteModal = false;
  let projectToDelete: IntelliDocProject | null = null;
  
  // Delete modal state
  let deleting = false;
  
  // Get current user info
  $: currentUser = get(authStore)?.user;
  
  onMount(() => {
    fetchProjects();
  });
  
  async function fetchProjects() {
    try {
      loading = true;
      const response = await cleanUniversalApi.getAllProjects();
      
      // Handle response - cleanUniversalApi returns array directly
      if (Array.isArray(response)) {
        projects = response;
      } else {
        console.error('Unexpected response format:', response);
        projects = [];
      }
      
      // Log project configurations for debugging
      console.log('✅ Loaded projects with enhanced configurations:', projects.map(p => ({
        id: p.project_id,
        name: p.name,
        has_navigation: p.has_navigation,
        total_pages: p.total_pages,
        template_type: p.template_type
      })));
    } catch (error) {
      console.error('❌ Failed to fetch projects:', error);
      toasts.error('Failed to load projects');
    } finally {
      loading = false;
    }
  }
  
  function onProjectCreated(event: CustomEvent<IntelliDocProject>) {
    const newProject = event.detail;
    projects = [newProject, ...projects];
    showCreateForm = false;
    
    // Navigate to the newly created project
    goto(`/features/intellidoc/project/${newProject.project_id}`);
  }
  
  function openDeleteModal(project: IntelliDocProject) {
    projectToDelete = project;
    showDeleteModal = true;
  }

  function closeDeleteModal() {
    showDeleteModal = false;
    projectToDelete = null;
  }

  async function deleteProject() {
    if (!projectToDelete) return;

    try {
      deleting = true;
      await cleanUniversalApi.deleteProject(projectToDelete.project_id);
      projects = projects.filter(p => p.project_id !== projectToDelete!.project_id);
      toasts.success(`Project "${projectToDelete.name}" deleted successfully`);
      closeDeleteModal();
    } catch (error) {
      console.error('❌ Failed to delete project:', error);
      toasts.error('Failed to delete project.');
    } finally {
      deleting = false;
    }
  }
  
  function formatDate(dateString: string): string {
    return new Date(dateString).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric'
    });
  }
  
  function getProjectTypeIcon(templateType: string): string {
    switch (templateType) {
      case 'aicc-intellidoc':
        return 'fa-brain';
      case 'legal':
        return 'fa-balance-scale';
      case 'medical':
        return 'fa-user-md';
      case 'history':
        return 'fa-university';
      default:
        return 'fa-file-alt';
    }
  }
  
  function getProjectFeatures(project: IntelliDocProject): string[] {
    const features = [];
    
    if (project.has_navigation) {
      features.push(`${project.total_pages} page${project.total_pages > 1 ? 's' : ''}`);
    }
    
    if (project.processing_capabilities?.supports_ai_analysis) {
      features.push('AI Analysis');
    }
    
    if (project.processing_capabilities?.supports_vector_search) {
      features.push('Vector Search');
    }
    
    if (project.ui_configuration?.features?.drag_drop_upload) {
      features.push('Drag & Drop');
    }
    
    return features;
  }
</script>

<svelte:head>
  <title>IntelliDoc Projects - AI Catalogue</title>
</svelte:head>

<div class="intellidoc-page">
  <!-- Header Section -->
  <div class="header-section">
    <div class="header-content">
      <div class="page-title">
        <div class="title-icon">
          <i class="fas fa-brain"></i>
        </div>
        <div class="title-text">
          <h1>IntelliDoc Projects</h1>
          <p>AI-powered document analysis with enhanced template system</p>
        </div>
      </div>
      
      <div class="header-stats">
        <div class="stat-item">
          <div class="stat-value">{projects.length}</div>
          <div class="stat-label">Projects</div>
        </div>
        <div class="stat-item">
          <div class="stat-value">{projects.filter(p => p.has_navigation).length}</div>
          <div class="stat-label">Multi-page</div>
        </div>
      </div>
    </div>
    
    <div class="header-actions">
      <button
        class="create-button"
        on:click={() => showCreateForm = true}
      >
        <i class="fas fa-plus"></i>
        Create New Project
      </button>
    </div>
  </div>
  
  <!-- Main Content -->
  <div class="main-content">
    {#if loading}
      <div class="loading-state">
        <div class="spinner"></div>
        <p>Loading projects...</p>
      </div>
    {:else if projects.length === 0}
      <div class="empty-state">
        <div class="empty-icon">
          <i class="fas fa-folder-open"></i>
        </div>
        <h3>No projects yet</h3>
        <p>Create your first IntelliDoc project to get started with AI-powered document analysis.</p>
        {#if $isAdmin}
          <button 
            class="create-button primary"
            on:click={() => showCreateForm = true}
          >
            <i class="fas fa-rocket"></i>
            Create Your First Project
          </button>
        {:else}
          <p class="text-gray-600 text-center">
            <i class="fas fa-info-circle"></i>
            No projects available. Contact your administrator to get access to projects.
          </p>
        {/if}
      </div>
    {:else}
      <div class="projects-grid">
        {#each projects as project}
          <div class="project-card">
            <div class="card-header">
              <div class="project-icon">
                <i class="fas {getProjectTypeIcon(project.template_type)}"></i>
              </div>
              <div class="project-info">
                <h3 class="project-name">{project.name}</h3>
                <div class="project-id">ID: {project.project_id}</div>
              </div>
              <div class="project-actions-menu">
                <AdminDeleteButton
                  size="small"
                  itemName={project.name}
                  confirmMessage="This will permanently delete the project and all its documents. Are you sure?"
                  on:delete={() => openDeleteModal(project)}
                />
              </div>
            </div>
            
            <div class="template-badge">
              <i class="fas {project.icon_class}"></i>
              {project.template_name}
            </div>
            
            <p class="project-description">{project.description}</p>
            
            <div class="project-meta">
              <div class="meta-item">
                <i class="fas fa-calendar"></i>
                <span>Created {formatDate(project.created_at)}</span>
              </div>
              <div class="meta-item">
                <i class="fas fa-user"></i>
                <span>by {project.created_by?.first_name || 'Unknown'}</span>
              </div>
            </div>
            
            {#if getProjectFeatures(project).length > 0}
              <div class="project-features">
                <div class="features-label">Features:</div>
                <div class="features-list">
                  {#each getProjectFeatures(project) as feature}
                    <span class="feature-tag">{feature}</span>
                  {/each}
                </div>
              </div>
            {/if}
            
            <div class="card-actions">
              <button 
                class="action-button primary"
                on:click={() => goto(`/features/intellidoc/project/${project.project_id}`)}
              >
                <i class="fas fa-arrow-right"></i>
                Open Project
              </button>
            </div>
          </div>
        {/each}
      </div>
    {/if}
  </div>
</div>

<!-- Create Project Modal -->
{#if showCreateForm}
  <div class="modal-overlay" on:click={() => showCreateForm = false}>
    <div class="modal-container" on:click|stopPropagation>
      <div class="modal-header">
        <h2>Create New Project</h2>
        <button class="close-button" on:click={() => showCreateForm = false}>
          <i class="fas fa-times"></i>
        </button>
      </div>
      <div class="modal-content">
        <ProjectCreator on:projectCreated={onProjectCreated} />
      </div>
    </div>
  </div>
{/if}

<!-- Delete Confirmation Modal -->
{#if showDeleteModal && projectToDelete}
  <div class="modal-overlay" on:click={closeDeleteModal}>
    <div class="modal-container small" on:click|stopPropagation>
      <div class="modal-header">
        <h2>Delete Project</h2>
        <button class="close-button" on:click={closeDeleteModal}>
          <i class="fas fa-times"></i>
        </button>
      </div>
      <div class="modal-content">
        <div class="delete-warning">
          <div class="warning-icon">
            <i class="fas fa-exclamation-triangle"></i>
          </div>
          <div class="warning-content">
            <h3>Are you sure?</h3>
            <p>This will permanently delete the project <strong>"{projectToDelete.name}"</strong> and all its data.</p>
            <p class="warning-note">This action cannot be undone.</p>
          </div>
        </div>

        <div class="modal-actions">
          <button class="action-button secondary" on:click={closeDeleteModal}>
            No, Cancel
          </button>
          <button
            class="action-button danger"
            on:click={deleteProject}
            disabled={deleting}
          >
            {#if deleting}
              <i class="fas fa-spinner fa-spin"></i>
              Deleting...
            {:else}
              <i class="fas fa-trash"></i>
              Yes, Delete
            {/if}
          </button>
        </div>
      </div>
    </div>
  </div>
{/if}

<style>
  .intellidoc-page {
    min-height: 100vh;
    background: #f8fafc;
    padding: 24px;
  }
  
  .header-section {
    background: white;
    border-radius: 16px;
    padding: 32px;
    margin-bottom: 32px;
    box-shadow: 0 2px 12px rgba(0, 0, 0, 0.05);
    display: flex;
    justify-content: space-between;
    align-items: center;
  }
  
  .header-content {
    display: flex;
    align-items: center;
    gap: 32px;
  }
  
  .page-title {
    display: flex;
    align-items: center;
    gap: 16px;
  }
  
  .title-icon {
    width: 64px;
    height: 64px;
    background: linear-gradient(135deg, #002147, #1e3a5f);
    border-radius: 16px;
    display: flex;
    align-items: center;
    justify-content: center;
    color: white;
    font-size: 1.5rem;
  }
  
  .title-icon i {
    color: white !important;
  }
  
  .title-text h1 {
    margin: 0 0 8px 0;
    font-size: 2rem;
    font-weight: 700;
    color: #111827;
  }
  
  .title-text p {
    margin: 0;
    color: #6b7280;
    font-size: 1rem;
  }
  
  .header-stats {
    display: flex;
    gap: 24px;
  }
  
  .stat-item {
    text-align: center;
  }
  
  .stat-value {
    font-size: 2rem;
    font-weight: 700;
    color: #002147;
    margin-bottom: 4px;
  }
  
  .stat-label {
    font-size: 0.875rem;
    color: #6b7280;
    text-transform: uppercase;
    font-weight: 500;
  }
  
  .create-button {
    background: linear-gradient(135deg, #002147, #1e3a5f);
    color: white;
    border: none;
    padding: 12px 24px;
    border-radius: 10px;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.2s ease;
    display: flex;
    align-items: center;
    gap: 8px;
  }
  
  .create-button:hover {
    transform: translateY(-2px);
    box-shadow: 0 8px 24px rgba(0, 33, 71, 0.3);
  }
  
  .create-button.secondary {
    background: #f8fafc;
    color: #002147;
    border: 2px solid #002147;
  }
  
  .create-button.secondary:hover {
    background: #002147;
    color: white;
    transform: translateY(-2px);
    box-shadow: 0 8px 24px rgba(0, 33, 71, 0.3);
  }
  
  .create-button.primary {
    padding: 16px 32px;
    font-size: 1.125rem;
  }
  
  .header-actions {
    display: flex;
    gap: 12px;
  }
  
  .loading-state, .empty-state {
    text-align: center;
    padding: 64px 32px;
  }
  
  .empty-state {
    background: white;
    border-radius: 16px;
    box-shadow: 0 2px 12px rgba(0, 0, 0, 0.05);
  }
  
  .empty-icon {
    font-size: 4rem;
    color: #d1d5db;
    margin-bottom: 24px;
  }
  
  .empty-state h3 {
    margin: 0 0 12px 0;
    color: #111827;
    font-size: 1.5rem;
  }
  
  .empty-state p {
    margin: 0 0 32px 0;
    color: #6b7280;
    font-size: 1rem;
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
  
  .projects-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(400px, 1fr));
    gap: 24px;
  }
  
  .project-card {
    background: white;
    border-radius: 16px;
    padding: 24px;
    box-shadow: 0 2px 12px rgba(0, 0, 0, 0.05);
    transition: all 0.2s ease;
    border: 1px solid #e5e7eb;
  }
  
  .project-card:hover {
    transform: translateY(-4px);
    box-shadow: 0 8px 24px rgba(0, 0, 0, 0.1);
  }
  
  .card-header {
    display: flex;
    align-items: flex-start;
    gap: 16px;
    margin-bottom: 16px;
  }
  
  .project-icon {
    width: 48px;
    height: 48px;
    background: linear-gradient(135deg, #002147, #1e3a5f);
    border-radius: 12px;
    display: flex;
    align-items: center;
    justify-content: center;
    color: white;
    font-size: 1.125rem;
    flex-shrink: 0;
  }
  
  .project-icon i {
    color: white !important;
  }
  
  .project-info {
    flex: 1;
    min-width: 0;
  }
  
  .project-name {
    margin: 0 0 8px 0;
    font-size: 1.25rem;
    font-weight: 600;
    color: #111827;
    word-break: break-word;
  }
  
  .project-id {
    font-size: 0.75rem;
    color: #9ca3af;
    background: #f1f5f9;
    padding: 4px 8px;
    border-radius: 6px;
    font-family: 'Monaco', 'Menlo', monospace;
    width: fit-content;
  }
  
  .project-actions-menu {
    display: flex;
    gap: 8px;
  }
  
  .template-badge {
    display: flex;
    align-items: center;
    gap: 8px;
    background: #eff6ff;
    color: #1e40af;
    padding: 8px 12px;
    border-radius: 8px;
    font-size: 0.875rem;
    font-weight: 500;
    margin-bottom: 16px;
    border: 1px solid #dbeafe;
  }
  
  .project-description {
    color: #64748b;
    margin: 0 0 16px 0;
    line-height: 1.6;
    font-size: 0.9rem;
  }
  
  .project-meta {
    display: flex;
    flex-direction: column;
    gap: 8px;
    margin-bottom: 16px;
  }
  
  .meta-item {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 0.875rem;
    color: #64748b;
  }
  
  .meta-item i {
    width: 16px;
    text-align: center;
  }
  
  .project-features {
    margin-bottom: 20px;
  }
  
  .features-label {
    font-size: 0.875rem;
    color: #374151;
    font-weight: 500;
    margin-bottom: 8px;
  }
  
  .features-list {
    display: flex;
    gap: 6px;
    flex-wrap: wrap;
  }
  
  .feature-tag {
    background: #f0f9ff;
    color: #0369a1;
    padding: 4px 8px;
    border-radius: 8px;
    font-size: 0.75rem;
    font-weight: 500;
  }
  
  .card-actions {
    display: flex;
    gap: 12px;
  }
  
  .action-button {
    padding: 10px 16px;
    border: none;
    border-radius: 8px;
    font-weight: 500;
    cursor: pointer;
    transition: all 0.2s ease;
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 0.875rem;
    flex: 1;
    justify-content: center;
  }
  
  .action-button.small {
    padding: 6px 8px;
    flex: none;
  }
  
  .action-button.primary {
    background: linear-gradient(135deg, #3b82f6, #1d4ed8);
    color: white;
  }
  
  .action-button.primary:hover {
    transform: translateY(-1px);
    box-shadow: 0 4px 12px rgba(59, 130, 246, 0.3);
  }
  
  .action-button.secondary {
    background: #f8fafc;
    color: #64748b;
    border: 1px solid #e2e8f0;
  }
  
  .action-button.secondary:hover {
    background: #f1f5f9;
    color: #475569;
  }
  
  .action-button.danger {
    background: #fef2f2;
    color: #ef4444;
    border: 1px solid #fecaca;
  }
  
  .action-button.danger:hover {
    background: #fee2e2;
    color: #dc2626;
  }
  
  .action-button:disabled {
    opacity: 0.5;
    cursor: not-allowed;
    transform: none;
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
  }
  
  .modal-header h2 {
    margin: 0;
    font-size: 1.25rem;
    font-weight: 600;
    color: white;
  }
  
  .close-button {
    background: none;
    border: none;
    font-size: 1.25rem;
    color: rgba(255, 255, 255, 0.8);
    cursor: pointer;
    padding: 4px;
    border-radius: 4px;
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
  
  .delete-warning {
    display: flex;
    gap: 16px;
    padding: 24px 32px;
    align-items: flex-start;
  }
  
  .warning-icon {
    width: 48px;
    height: 48px;
    background: #fef2f2;
    border-radius: 12px;
    display: flex;
    align-items: center;
    justify-content: center;
    color: #ef4444;
    font-size: 1.25rem;
    flex-shrink: 0;
  }
  
  .warning-content h3 {
    margin: 0 0 8px 0;
    color: #111827;
    font-size: 1.125rem;
  }
  
  .warning-content p {
    margin: 0 0 8px 0;
    color: #6b7280;
    line-height: 1.5;
  }
  
  .warning-note {
    color: #dc2626;
    font-weight: 500;
    font-size: 0.875rem;
  }
  
  .password-input {
    padding: 0 32px 24px;
  }
  
  .password-input label {
    display: block;
    margin-bottom: 8px;
    font-weight: 500;
    color: #374151;
  }
  
  .form-input {
    width: 100%;
    padding: 12px 16px;
    border: 2px solid #e5e7eb;
    border-radius: 8px;
    font-size: 0.875rem;
    transition: all 0.2s ease;
  }
  
  .form-input:focus {
    outline: none;
    border-color: #002147;
    box-shadow: 0 0 0 3px rgba(0, 33, 71, 0.1);
  }
  
  .modal-actions {
    padding: 24px 32px;
    border-top: 1px solid #e5e7eb;
    display: flex;
    justify-content: flex-end;
    gap: 12px;
  }
  
  @media (max-width: 768px) {
    .header-section {
      flex-direction: column;
      align-items: stretch;
      gap: 24px;
    }
    
    .header-content {
      flex-direction: column;
      align-items: stretch;
      gap: 16px;
    }
    
    .page-title {
      flex-direction: column;
      text-align: center;
    }
    
    .projects-grid {
      grid-template-columns: 1fr;
    }
    
    .modal-container {
      margin: 20px;
      max-width: calc(100% - 40px);
    }
  }
</style>
