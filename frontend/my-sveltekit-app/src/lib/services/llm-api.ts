// src/lib/services/llm-api.ts
import api from './api';

// LLM Provider functions
export const getAvailableLLMProviders = async () => {
  const response = await api.get('/llm-providers/available/');
  return response.data;
};

export const getAllLLMProviders = async () => {
  const response = await api.get('/llm-providers/');
  return response.data;
};

export const createLLMProvider = async (providerData: any) => {
  const response = await api.post('/llm-providers/', providerData);
  return response.data;
};

export const updateLLMProvider = async (id: string, providerData: any) => {
  const response = await api.patch(`/llm-providers/${id}/`, providerData);
  return response.data;
};

export const deleteLLMProvider = async (id: string) => {
  const response = await api.delete(`/llm-providers/${id}/`);
  return response.data;
};

export const getProviderModels = async (providerId: string) => {
  const response = await api.get(`/llm-providers/${providerId}/models/`);
  return response.data;
};

// API Key Management functions
export const getAPIKeys = async () => {
  const response = await api.get('/api-keys/');
  return response.data;
};

export const createAPIKey = async (keyData: any) => {
  const response = await api.post('/api-keys/', keyData);
  return response.data;
};

export const updateAPIKey = async (id: string, keyData: any) => {
  const response = await api.patch(`/api-keys/${id}/`, keyData);
  return response.data;
};

export const deleteAPIKey = async (id: string) => {
  const response = await api.delete(`/api-keys/${id}/`);
  return response.data;
};

// LLM Comparison functions
export const getLLMComparisons = async () => {
  const response = await api.get('/llm-comparisons/');
  return response.data;
};

export const getLLMComparison = async (id: string) => {
  const response = await api.get(`/llm-comparisons/${id}/`);
  return response.data;
};

export const deleteLLMComparison = async (id: string) => {
  const response = await api.delete(`/llm-comparisons/${id}/`);
  return response.data;
};

export const createLLMComparison = async (comparisonData: any) => {
  const response = await api.post('/llm-comparisons/', comparisonData);
  return response.data;
};

export const getLLMComparisonResponses = async (id: string) => {
  const response = await api.get(`/llm-comparisons/${id}/responses/`);
  return response.data;
};

// User API Access functions
export const getUserAPIAccess = async (userId: string) => {
  const response = await api.get(`/user-api-access/by_user/?user_id=${userId}`);
  return response.data;
};

export const updateUserAPIAccess = async (userId: string, apiKeyConfigIds: number[]) => {
  const response = await api.post('/user-api-access/bulk_update/', {
    user_id: userId,
    api_key_config_ids: apiKeyConfigIds
  });
  return response.data;
};

// Group API Access functions
export const getGroupAPIAccess = async (groupId: string) => {
  const response = await api.get(`/group-api-access/by_group/?group_id=${groupId}`);
  return response.data;
};

export const updateGroupAPIAccess = async (groupId: string, apiKeyConfigIds: number[]) => {
  const response = await api.post('/group-api-access/bulk_update/', {
    group_id: groupId,
    api_key_config_ids: apiKeyConfigIds
  });
  return response.data;
};
