// src/lib/services/api.ts - CLEANED VERSION (Phase 1 Complete)
// LEGACY FUNCTIONS REMOVED - Use cleanUniversalApi.ts for ALL project operations

import axios from 'axios';
import { get } from 'svelte/store';
import authStore, { logout } from '$lib/stores/auth';

// API Configuration - uses relative URL for proper proxy handling
const API_URL = '/api';

// Create axios instance
const api = axios.create({
  baseURL: API_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Add request interceptor for auth token
api.interceptors.request.use(
  (config) => {
    const auth = get(authStore);
    if (auth.token) {
      config.headers.Authorization = `Bearer ${auth.token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// Add response interceptor for handling token refresh
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;
    const auth = get(authStore);

    if (error.response?.status === 401 && auth.refreshToken && !originalRequest._retry) {
      originalRequest._retry = true;

      try {
        const response = await axios.post(`${API_URL}/token/refresh/`, {
          refresh: auth.refreshToken,
        });

        authStore.update(state => ({
          ...state,
          token: response.data.access,
        }));

        originalRequest.headers.Authorization = `Bearer ${response.data.access}`;
        return api(originalRequest);
      } catch (refreshError) {
        logout();
        return Promise.reject(refreshError);
      }
    }

    return Promise.reject(error);
  }
);

// ============================================================================
// AUTHENTICATION (Core system functions only)
// ============================================================================

export const loginUser = async (email: string, password: string) => {
  const response = await api.post('/token/', { email, password });
  return response.data;
};


export const getCurrentUser = async () => {
  const response = await api.get('/users/me/');
  return response.data;
};

// ============================================================================
// USER MANAGEMENT (Admin functions only)
// ============================================================================

export const getUsers = async () => {
  const response = await api.get('/users/');
  return response.data;
};

export const getUserById = async (id: string) => {
  const response = await api.get(`/users/${id}/`);
  return response.data;
};

export const updateUser = async (id: string, userData: any) => {
  const response = await api.patch(`/users/${id}/`, userData);
  return response.data;
};

export const deleteUser = async (id: string) => {
  const response = await api.delete(`/users/${id}/`);
  return response.data;
};

// ============================================================================
// PASSWORD RESET (Core auth functions only)
// ============================================================================

export const requestPasswordReset = async (email: string) => {
  const response = await api.post('/password-reset/', { email });
  return response.data;
};

export const confirmPasswordReset = async (data: any) => {
  const response = await api.post('/password-reset/confirm/', data);
  return response.data;
};

// ============================================================================
// DASHBOARD ICONS (Admin functions only)
// ============================================================================

export const getDashboardIcons = async () => {
  const response = await api.get('/dashboard-icons/');
  return response.data;
};

export const getMyDashboardIcons = async () => {
  const response = await api.get('/dashboard-icons/my_icons/');
  return response.data;
};

export const createDashboardIcon = async (iconData: any) => {
  const response = await api.post('/dashboard-icons/', iconData);
  return response.data;
};

export const updateDashboardIcon = async (id: string, iconData: any) => {
  const response = await api.patch(`/dashboard-icons/${id}/`, iconData);
  return response.data;
};

export const deleteDashboardIcon = async (id: string) => {
  const response = await api.delete(`/dashboard-icons/${id}/`);
  return response.data;
};

// ============================================================================
// ICON PERMISSIONS (Admin functions only)
// ============================================================================

export const getUserIconPermissions = async (userId: string) => {
  const response = await api.get(`/icon-permissions/by_user/?user_id=${userId}`);
  return response.data;
};

export const updateUserIconPermissions = async (userId: string, iconIds: number[]) => {
  const response = await api.post('/icon-permissions/bulk_update/', {
    user_id: userId,
    icon_ids: iconIds
  });
  return response.data;
};

// ============================================================================
// GROUP MANAGEMENT (Admin functions only)
// ============================================================================

export const getGroups = async () => {
  const response = await api.get('/groups/');
  return response.data;
};

export const getGroupById = async (id: string) => {
  const response = await api.get(`/groups/${id}/`);
  return response.data;
};

export const getGroupIconPermissions = async (groupId: string) => {
  const response = await api.get(`/group-icon-permissions/by_group/?group_id=${groupId}`);
  return response.data;
};

export const updateGroupIconPermissions = async (groupId: string, iconIds: number[]) => {
  const response = await api.post('/group-icon-permissions/bulk_update/', {
    group_id: groupId,
    icon_ids: iconIds
  });
  return response.data;
};

// ============================================================================
// IMPORTANT: PROJECT OPERATIONS REMOVED
// ============================================================================
// ALL PROJECT OPERATIONS HAVE BEEN MOVED TO cleanUniversalApi.ts
// 
// REMOVED FUNCTIONS:
// - getIntelliDocProjects() → Use cleanUniversalApi.getAllProjects()
// - createIntelliDocProject() → Use cleanUniversalApi.createProject()
// - deleteIntelliDocProject() → Use cleanUniversalApi.deleteProject()
// - getProjectDocuments() → Use cleanUniversalApi.getDocuments()
// - uploadProjectDocument() → Use cleanUniversalApi.uploadDocument()
// - deleteProjectDocument() → Use cleanUniversalApi.deleteDocument()
// - processProjectDocuments() → Use cleanUniversalApi.processDocuments()
// - searchProjectDocuments() → Use cleanUniversalApi.searchDocuments()
// - getProjectVectorStatus() → Use cleanUniversalApi.getProcessingStatus()
// - getProjectCapabilities() → Use cleanUniversalApi.getTemplateConfiguration()
// 
// PHASE 1 ACHIEVEMENT:
// ✅ Legacy project functions completely removed
// ✅ Single source of truth: cleanUniversalApi.ts
// ✅ No conflicting implementations
// ✅ Clean separation of concerns

// ============================================================================
// AGENT ORCHESTRATION API (Database Persistence)
// ============================================================================

export const getProjectWorkflows = async (projectId: string) => {
  const response = await api.get(`/projects/${projectId}/workflows/`);
  return response.data;
};

export const createWorkflow = async (projectId: string, workflowData: any) => {
  const response = await api.post(`/projects/${projectId}/workflows/`, workflowData);
  return response.data;
};

export const updateWorkflow = async (projectId: string, workflowId: string, workflowData: any) => {
  const response = await api.patch(`/projects/${projectId}/workflows/${workflowId}/`, workflowData);
  return response.data;
};

export const deleteWorkflow = async (projectId: string, workflowId: string) => {
  const response = await api.delete(`/projects/${projectId}/workflows/${workflowId}/`);
  return response.data;
};

export const getWorkflowById = async (projectId: string, workflowId: string) => {
  const response = await api.get(`/projects/${projectId}/workflows/${workflowId}/`);
  return response.data;
};

// Save workflow orchestration to database
export const saveWorkflowOrchestration = async (projectId: string, workflowId: string, orchestrationData: any) => {
  const response = await api.patch(`/projects/${projectId}/workflows/${workflowId}/`, {
    graph_json: orchestrationData.graph_json,
    name: orchestrationData.name,
    description: orchestrationData.description,
    status: 'draft' // or 'validated' based on validation
  });
  return response.data;
};

// Load workflow orchestration from database
export const loadWorkflowOrchestration = async (projectId: string, workflowId: string) => {
  const response = await api.get(`/projects/${projectId}/workflows/${workflowId}/`);
  return response.data;
};

// ============================================================================
// PROJECT PERMISSION API FUNCTIONS
// ============================================================================

// Get user permissions for a specific project
export const getUserProjectPermissions = async (projectId: string) => {
  const response = await api.get(`/user-project-permissions/by_project/?project_id=${projectId}`);
  return response.data;
};

// Update user permissions for a project (bulk update)
export const updateUserProjectPermissions = async (projectId: string, userIds: number[]) => {
  const response = await api.post('/user-project-permissions/bulk_update/', {
    project_id: projectId,
    user_ids: userIds
  });
  return response.data;
};

// Get group permissions for a specific project
export const getGroupProjectPermissions = async (projectId: string) => {
  const response = await api.get(`/group-project-permissions/by_project/?project_id=${projectId}`);
  return response.data;
};

// Update group permissions for a project (bulk update)
export const updateGroupProjectPermissions = async (projectId: string, groupIds: number[]) => {
  const response = await api.post('/group-project-permissions/bulk_update/', {
    project_id: projectId,
    group_ids: groupIds
  });
  return response.data;
};

export default api;
