<!-- 
Advanced Template Management Dashboard
Phase 5: Advanced Template Features

Comprehensive dashboard for advanced template management including:
- Template versioning controls
- Analytics visualization
- Testing and validation
- System health monitoring
- Template lifecycle management
-->

<script lang="ts">
    import { onMount } from 'svelte';
    import { AdvancedTemplateFeaturesService } from '$lib/services/advancedTemplateFeatures';
    import type { 
        TemplateAnalyticsReport, 
        TemplateTestSuite, 
        SystemHealthReport,
        TemplateHealthReport,
        PopularityRankings,
        VersionHistory
    } from '$lib/services/advancedTemplateFeatures';
    import { Logger } from '$lib/utils/logger';
    
    const logger = Logger.getInstance();
    const advancedService = new AdvancedTemplateFeaturesService();
    
    // Component state
    let activeTab = 'analytics';
    let selectedTemplate = '';
    let loading = false;
    let error = '';
    
    // Data state
    let analyticsReport: TemplateAnalyticsReport | null = null;
    let testResults: TemplateTestSuite | null = null;
    let systemHealth: SystemHealthReport | null = null;
    let templateHealth: TemplateHealthReport | null = null;
    let popularityRankings: PopularityRankings | null = null;
    let versionHistory: VersionHistory | null = null;
    
    // Available templates (would come from template discovery)
    let availableTemplates = [
        { id: 'aicc-intellidoc', name: 'AICC-IntelliDoc' },
        { id: 'legal', name: 'Legal Analysis' },
        { id: 'medical', name: 'Medical Records' },
        { id: 'history', name: 'Historical Documents' }
    ];
    
    onMount(async () => {
        logger.componentMount('AdvancedTemplateManagement');
        
        // Set default template
        if (availableTemplates.length > 0) {
            selectedTemplate = availableTemplates[0].id;
        }
        
        // Load initial data
        await loadSystemHealth();
        await loadPopularityRankings();
        
        if (selectedTemplate) {
            await loadTemplateData();
        }
    });
    
    async function loadSystemHealth() {
        try {
            loading = true;
            systemHealth = await advancedService.getSystemHealth();
            logger.info('System health loaded successfully');
        } catch (err) {
            logger.error('Error loading system health:', err);
            error = `Failed to load system health: ${err.message}`;
        } finally {
            loading = false;
        }
    }
    
    async function loadPopularityRankings() {
        try {
            popularityRankings = await advancedService.getPopularityRankings();
            logger.info('Popularity rankings loaded successfully');
        } catch (err) {
            logger.error('Error loading popularity rankings:', err);
        }
    }
    
    async function loadTemplateData() {
        if (!selectedTemplate) return;
        
        try {
            loading = true;
            error = '';
            
            // Load template-specific data based on active tab
            switch (activeTab) {
                case 'analytics':
                    await loadAnalytics();
                    break;
                case 'testing':
                    await loadTemplateHealth();
                    break;
                case 'versioning':
                    await loadVersionHistory();
                    break;
                case 'health':
                    await loadTemplateHealth();
                    break;
            }
            
        } catch (err) {
            logger.error(`Error loading template data for ${selectedTemplate}:`, err);
            error = `Failed to load template data: ${err.message}`;
        } finally {
            loading = false;
        }
    }
    
    async function loadAnalytics() {
        analyticsReport = await advancedService.getAnalyticsReport(selectedTemplate, 30);
        logger.info(`Analytics loaded for ${selectedTemplate}`);
    }
    
    async function loadTemplateHealth() {
        templateHealth = await advancedService.getTemplateHealth(selectedTemplate);
        logger.info(`Template health loaded for ${selectedTemplate}`);
    }
    
    async function loadVersionHistory() {
        versionHistory = await advancedService.getVersionHistory(selectedTemplate);
        logger.info(`Version history loaded for ${selectedTemplate}`);
    }
    
    async function runTests() {
        if (!selectedTemplate) return;
        
        try {
            loading = true;
            testResults = await advancedService.runTests(selectedTemplate);
            logger.info(`Tests completed for ${selectedTemplate}`);
        } catch (err) {
            logger.error(`Error running tests for ${selectedTemplate}:`, err);
            error = `Failed to run tests: ${err.message}`;
        } finally {
            loading = false;
        }
    }
    
    async function handleTabChange(tab: string) {
        activeTab = tab;
        await loadTemplateData();
    }
    
    async function handleTemplateChange() {
        await loadTemplateData();
    }
    
    function getStatusBadgeClass(status: string): string {
        switch (status) {
            case 'healthy': return 'bg-green-100 text-green-800';
            case 'warning': return 'bg-yellow-100 text-yellow-800';
            case 'critical': return 'bg-red-100 text-red-800';
            default: return 'bg-gray-100 text-gray-800';
        }
    }
    
    function formatPercentage(value: number): string {
        return (value * 100).toFixed(1) + '%';
    }
    
    function formatDuration(seconds: number): string {
        return seconds.toFixed(2) + 's';
    }
</script>

<div class="advanced-template-management p-6 bg-white rounded-lg shadow-lg">
    <!-- Header -->
    <div class="mb-6">
        <h1 class="text-2xl font-bold text-[#002147] mb-2">Advanced Template Management</h1>
        <p class="text-gray-600">Comprehensive template analytics, testing, and health monitoring</p>
    </div>
    
    <!-- Template Selection -->
    <div class="mb-6">
        <label for="template-select" class="block text-sm font-medium text-gray-700 mb-2">
            Select Template
        </label>
        <select 
            id="template-select"
            bind:value={selectedTemplate}
            on:change={handleTemplateChange}
            class="block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-[#002147] focus:border-[#002147]"
        >
            {#each availableTemplates as template}
                <option value={template.id}>{template.name}</option>
            {/each}
        </select>
    </div>
    
    <!-- Navigation Tabs -->
    <div class="mb-6">
        <nav class="flex space-x-8">
            {#each [
                { id: 'analytics', label: 'Analytics', icon: '📊' },
                { id: 'testing', label: 'Testing', icon: '🧪' },
                { id: 'versioning', label: 'Versioning', icon: '🔄' },
                { id: 'health', label: 'Health', icon: '❤️' }
            ] as tab}
                <button
                    class="flex items-center px-3 py-2 text-sm font-medium rounded-md transition-colors duration-200 {
                        activeTab === tab.id 
                            ? 'bg-[#002147] text-white' 
                            : 'text-gray-500 hover:text-gray-700'
                    }"
                    on:click={() => handleTabChange(tab.id)}
                >
                    <span class="mr-2">{tab.icon}</span>
                    {tab.label}
                </button>
            {/each}
        </nav>
    </div>
    
    <!-- Error Display -->
    {#if error}
        <div class="mb-6 p-4 bg-red-50 border border-red-200 rounded-md">
            <div class="flex">
                <div class="flex-shrink-0">
                    <span class="text-red-400">⚠️</span>
                </div>
                <div class="ml-3">
                    <h3 class="text-sm font-medium text-red-800">Error</h3>
                    <p class="mt-1 text-sm text-red-700">{error}</p>
                </div>
            </div>
        </div>
    {/if}
    
    <!-- Loading State -->
    {#if loading}
        <div class="flex justify-center items-center py-12">
            <div class="animate-spin rounded-full h-8 w-8 border-b-2 border-[#002147]"></div>
            <span class="ml-3 text-gray-600">Loading...</span>
        </div>
    {/if}
    
    <!-- Content Tabs -->
    <div class="tab-content">
        
        <!-- Analytics Tab -->
        {#if activeTab === 'analytics' && analyticsReport && !loading}
            <div class="analytics-content">
                <h2 class="text-xl font-semibold text-[#002147] mb-4">Template Analytics Report</h2>
                
                <!-- Usage Metrics -->
                <div class="grid grid-cols-1 md:grid-cols-3 gap-6 mb-6">
                    <div class="bg-blue-50 p-4 rounded-lg">
                        <h3 class="text-lg font-medium text-blue-800 mb-2">Usage Metrics</h3>
                        <div class="space-y-2">
                            <div class="flex justify-between">
                                <span class="text-blue-600">Total Projects:</span>
                                <span class="font-semibold">{analyticsReport.usage_metrics.total_projects}</span>
                            </div>
                            <div class="flex justify-between">
                                <span class="text-blue-600">Active Projects:</span>
                                <span class="font-semibold">{analyticsReport.usage_metrics.active_projects}</span>
                            </div>
                            <div class="flex justify-between">
                                <span class="text-blue-600">Success Rate:</span>
                                <span class="font-semibold">{formatPercentage(analyticsReport.usage_metrics.success_rate)}</span>
                            </div>
                        </div>
                    </div>
                    
                    <div class="bg-green-50 p-4 rounded-lg">
                        <h3 class="text-lg font-medium text-green-800 mb-2">Performance</h3>
                        <div class="space-y-2">
                            <div class="flex justify-between">
                                <span class="text-green-600">Avg Processing:</span>
                                <span class="font-semibold">{formatDuration(analyticsReport.performance_metrics.average_processing_time)}</span>
                            </div>
                            <div class="flex justify-between">
                                <span class="text-green-600">API Calls:</span>
                                <span class="font-semibold">{analyticsReport.performance_metrics.total_api_calls}</span>
                            </div>
                            <div class="flex justify-between">
                                <span class="text-green-600">Error Rate:</span>
                                <span class="font-semibold">{formatPercentage(analyticsReport.performance_metrics.error_rate)}</span>
                            </div>
                        </div>
                    </div>
                    
                    <div class="bg-purple-50 p-4 rounded-lg">
                        <h3 class="text-lg font-medium text-purple-800 mb-2">Popularity</h3>
                        <div class="space-y-2">
                            <div class="flex justify-between">
                                <span class="text-purple-600">Rank:</span>
                                <span class="font-semibold">#{analyticsReport.popularity_metrics.rank} of {analyticsReport.popularity_metrics.total_rank}</span>
                            </div>
                            <div class="flex justify-between">
                                <span class="text-purple-600">Score:</span>
                                <span class="font-semibold">{analyticsReport.popularity_metrics.popularity_score.toFixed(1)}</span>
                            </div>
                            <div class="flex justify-between">
                                <span class="text-purple-600">Trend:</span>
                                <span class="font-semibold capitalize">{analyticsReport.popularity_metrics.trend_direction}</span>
                            </div>
                        </div>
                    </div>
                </div>
                
                <!-- Insights -->
                {#if analyticsReport.insights.length > 0}
                    <div class="bg-yellow-50 p-4 rounded-lg">
                        <h3 class="text-lg font-medium text-yellow-800 mb-2">💡 Insights</h3>
                        <ul class="space-y-1">
                            {#each analyticsReport.insights as insight}
                                <li class="text-yellow-700">• {insight}</li>
                            {/each}
                        </ul>
                    </div>
                {/if}
            </div>
        {/if}
        
        <!-- Testing Tab -->
        {#if activeTab === 'testing'}
            <div class="testing-content">
                <div class="flex justify-between items-center mb-4">
                    <h2 class="text-xl font-semibold text-[#002147]">Template Testing</h2>
                    <button
                        on:click={runTests}
                        disabled={loading || !selectedTemplate}
                        class="px-4 py-2 bg-[#002147] text-white rounded-md hover:bg-blue-900 disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                        Run Tests
                    </button>
                </div>
                
                {#if testResults}
                    <div class="bg-gray-50 p-4 rounded-lg">
                        <h3 class="text-lg font-medium text-gray-800 mb-3">Test Results</h3>
                        
                        <!-- Test Statistics -->
                        <div class="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
                            <div class="text-center p-3 bg-green-100 rounded">
                                <div class="text-2xl font-bold text-green-800">{testResults.test_suite.statistics.passed}</div>
                                <div class="text-sm text-green-600">Passed</div>
                            </div>
                            <div class="text-center p-3 bg-red-100 rounded">
                                <div class="text-2xl font-bold text-red-800">{testResults.test_suite.statistics.failed}</div>
                                <div class="text-sm text-red-600">Failed</div>
                            </div>
                            <div class="text-center p-3 bg-yellow-100 rounded">
                                <div class="text-2xl font-bold text-yellow-800">{testResults.test_suite.statistics.errors}</div>
                                <div class="text-sm text-yellow-600">Errors</div>
                            </div>
                            <div class="text-center p-3 bg-gray-100 rounded">
                                <div class="text-2xl font-bold text-gray-800">{testResults.test_suite.statistics.skipped}</div>
                                <div class="text-sm text-gray-600">Skipped</div>
                            </div>
                        </div>
                        
                        <!-- Individual Test Results -->
                        <div class="space-y-2">
                            {#each testResults.test_suite.results as result}
                                <div class="flex items-center justify-between p-3 bg-white rounded border">
                                    <div>
                                        <span class="font-medium">{result.test_name}</span>
                                        <p class="text-sm text-gray-600">{result.message}</p>
                                    </div>
                                    <div class="flex items-center">
                                        <span class="px-2 py-1 text-xs font-medium rounded {getStatusBadgeClass(result.status)}">
                                            {result.status}
                                        </span>
                                        <span class="ml-2 text-sm text-gray-500">{formatDuration(result.execution_time)}</span>
                                    </div>
                                </div>
                            {/each}
                        </div>
                    </div>
                {/if}
                
                {#if templateHealth}
                    <div class="mt-6 bg-white p-4 rounded-lg border">
                        <h3 class="text-lg font-medium text-gray-800 mb-3">Template Health Status</h3>
                        
                        <div class="flex items-center mb-4">
                            <span class="px-3 py-1 text-sm font-medium rounded {getStatusBadgeClass(templateHealth.status)}">
                                {templateHealth.status.toUpperCase()}
                            </span>
                            <span class="ml-3 text-gray-600">Availability: {templateHealth.availability.toFixed(1)}%</span>
                            <span class="ml-3 text-gray-600">Performance Score: {templateHealth.performance_score.toFixed(1)}</span>
                        </div>
                        
                        {#if templateHealth.issues.length > 0}
                            <div class="mb-4">
                                <h4 class="font-medium text-red-800 mb-2">Issues:</h4>
                                <ul class="space-y-1">
                                    {#each templateHealth.issues as issue}
                                        <li class="text-red-700">• {issue}</li>
                                    {/each}
                                </ul>
                            </div>
                        {/if}
                        
                        {#if templateHealth.recommendations.length > 0}
                            <div>
                                <h4 class="font-medium text-blue-800 mb-2">Recommendations:</h4>
                                <ul class="space-y-1">
                                    {#each templateHealth.recommendations as recommendation}
                                        <li class="text-blue-700">• {recommendation}</li>
                                    {/each}
                                </ul>
                            </div>
                        {/if}
                    </div>
                {/if}
            </div>
        {/if}
        
        <!-- Versioning Tab -->
        {#if activeTab === 'versioning' && versionHistory && !loading}
            <div class="versioning-content">
                <h2 class="text-xl font-semibold text-[#002147] mb-4">Version History</h2>
                
                <div class="bg-gray-50 p-4 rounded-lg mb-4">
                    <div class="flex items-center justify-between">
                        <div>
                            <h3 class="text-lg font-medium">Current Version</h3>
                            <p class="text-2xl font-bold text-[#002147]">{versionHistory.current_version}</p>
                        </div>
                        <div class="text-right">
                            <p class="text-sm text-gray-600">Total Versions</p>
                            <p class="text-xl font-semibold">{versionHistory.total_versions}</p>
                        </div>
                    </div>
                </div>
                
                <div class="space-y-3">
                    {#each versionHistory.history as entry}
                        <div class="bg-white p-4 rounded-lg border">
                            <div class="flex items-center justify-between">
                                <div>
                                    <span class="font-medium">{entry.from_version} → {entry.to_version}</span>
                                    <p class="text-sm text-gray-600 mt-1">{entry.changelog}</p>
                                </div>
                                <div class="text-right">
                                    <p class="text-sm text-gray-500">
                                        {new Date(entry.timestamp).toLocaleDateString()}
                                    </p>
                                </div>
                            </div>
                        </div>
                    {/each}
                </div>
            </div>
        {/if}
        
        <!-- Health Tab -->
        {#if activeTab === 'health'}
            <div class="health-content">
                <h2 class="text-xl font-semibold text-[#002147] mb-4">System Health Monitor</h2>
                
                {#if systemHealth}
                    <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
                        <!-- Overall Status -->
                        <div class="bg-white p-6 rounded-lg border">
                            <h3 class="text-lg font-medium mb-4">System Overview</h3>
                            
                            <div class="flex items-center mb-4">
                                <span class="px-4 py-2 text-lg font-medium rounded {getStatusBadgeClass(systemHealth.overall_status)}">
                                    {systemHealth.overall_status.toUpperCase()}
                                </span>
                            </div>
                            
                            <div class="grid grid-cols-2 gap-4">
                                <div class="text-center p-3 bg-green-50 rounded">
                                    <div class="text-xl font-bold text-green-800">{systemHealth.system_metrics.healthy_components}</div>
                                    <div class="text-sm text-green-600">Healthy</div>
                                </div>
                                <div class="text-center p-3 bg-yellow-50 rounded">
                                    <div class="text-xl font-bold text-yellow-800">{systemHealth.system_metrics.warning_components}</div>
                                    <div class="text-sm text-yellow-600">Warnings</div>
                                </div>
                                <div class="text-center p-3 bg-red-50 rounded">
                                    <div class="text-xl font-bold text-red-800">{systemHealth.system_metrics.critical_components}</div>
                                    <div class="text-sm text-red-600">Critical</div>
                                </div>
                                <div class="text-center p-3 bg-gray-50 rounded">
                                    <div class="text-xl font-bold text-gray-800">{systemHealth.system_metrics.total_components}</div>
                                    <div class="text-sm text-gray-600">Total</div>
                                </div>
                            </div>
                            
                            <div class="mt-4 text-sm text-gray-600">
                                <p>Uptime: {systemHealth.system_metrics.uptime}</p>
                            </div>
                        </div>
                        
                        <!-- Components Status -->
                        <div class="bg-white p-6 rounded-lg border">
                            <h3 class="text-lg font-medium mb-4">Component Status</h3>
                            
                            <div class="space-y-3">
                                {#each systemHealth.components as component}
                                    <div class="flex items-center justify-between p-3 bg-gray-50 rounded">
                                        <div>
                                            <span class="font-medium">{component.component}</span>
                                            <p class="text-sm text-gray-600">{component.message}</p>
                                        </div>
                                        <span class="px-2 py-1 text-xs font-medium rounded {getStatusBadgeClass(component.status)}">
                                            {component.status}
                                        </span>
                                    </div>
                                {/each}
                            </div>
                        </div>
                    </div>
                    
                    <!-- Recommendations -->
                    {#if systemHealth.recommendations.length > 0}
                        <div class="mt-6 bg-blue-50 p-4 rounded-lg">
                            <h3 class="text-lg font-medium text-blue-800 mb-2">🔧 Recommendations</h3>
                            <ul class="space-y-1">
                                {#each systemHealth.recommendations as recommendation}
                                    <li class="text-blue-700">• {recommendation}</li>
                                {/each}
                            </ul>
                        </div>
                    {/if}
                {/if}
            </div>
        {/if}
    </div>
</div>

<style>
    .advanced-template-management {
        font-family: 'Inter', sans-serif;
    }
    
    .tab-content {
        min-height: 400px;
    }
    
    /* Custom scrollbar for long lists */
    .space-y-3::-webkit-scrollbar {
        width: 6px;
    }
    
    .space-y-3::-webkit-scrollbar-track {
        background: #f1f1f1;
        border-radius: 3px;
    }
    
    .space-y-3::-webkit-scrollbar-thumb {
        background: #888;
        border-radius: 3px;
    }
    
    .space-y-3::-webkit-scrollbar-thumb:hover {
        background: #555;
    }
</style>
