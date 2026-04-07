/**
 * Advanced Template Management Service
 * Phase 5: Advanced Template Features
 * 
 * Frontend service for advanced template management including:
 * - Template versioning operations
 * - Analytics and reporting
 * - Testing and validation
 * - Health monitoring
 * - System diagnostics
 */

import { browser } from '$app/environment';

export interface TemplateVersion {
	major: number;
	minor: number;
	patch: number;
	prerelease?: string;
	build?: string;
}

export interface VersionHistory {
	from_version: string;
	to_version: string;
	timestamp: string;
	changelog: string;
}

export interface TemplateUsageMetrics {
	template_id: string;
	total_projects: number;
	active_projects: number;
	completed_projects: number;
	total_documents_processed: number;
	success_rate: number;
	user_satisfaction_score: number;
	last_used: string;
}

export interface PerformanceMetrics {
	template_id: string;
	average_processing_time: number;
	total_api_calls: number;
	error_rate: number;
	memory_usage_avg: number;
	cpu_usage_avg: number;
}

export interface AnalyticsReport {
	template_id: string;
	report_date: string;
	period_days: number;
	usage_metrics: TemplateUsageMetrics;
	performance_metrics: PerformanceMetrics;
	insights: string[];
}

export interface TestResult {
	test_name: string;
	template_id: string;
	status: 'passed' | 'failed' | 'skipped' | 'error';
	execution_time: number;
	message: string;
	details?: any;
}

export interface TestSuite {
	template_id: string;
	test_suite: {
		suite_name: string;
		duration: number;
		statistics: {
			passed: number;
			failed: number;
			errors: number;
			skipped: number;
			total: number;
		};
		results: TestResult[];
	};
}

export interface HealthStatus {
	component: string;
	status: 'healthy' | 'warning' | 'critical' | 'unknown';
	message: string;
	details?: any;
	timestamp: string;
}

export interface SystemHealthReport {
	overall_status: 'healthy' | 'warning' | 'critical' | 'unknown';
	timestamp: string;
	components: HealthStatus[];
	system_metrics: {
		total_components: number;
		healthy_components: number;
		warning_components: number;
		critical_components: number;
		uptime: string;
	};
	recommendations: string[];
}

export interface TemplateHealthReport {
	template_id: string;
	status: 'healthy' | 'warning' | 'critical' | 'unknown';
	availability: number;
	performance_score: number;
	error_rate: number;
	last_successful_operation: string;
	issues: string[];
	recommendations: string[];
}

export interface PopularityRanking {
	template_id: string;
	rank: number;
	popularity_score: number;
	trend_direction: 'increasing' | 'stable' | 'decreasing';
	growth_rate: number;
}

export interface VersionUpdateRequest {
	new_version?: string;
	increment_type?: 'major' | 'minor' | 'patch';
	changelog?: string;
}

export interface VersionComparisonRequest {
	version1: string;
	version2: string;
}

export interface UsageTrackingRequest {
	template_id: string;
	action: string;
	metadata?: Record<string, any>;
}

export interface TestingRequest {
	include_benchmarks?: boolean;
	include_regression?: boolean;
	include_compatibility?: boolean;
}

class AdvancedTemplateManagementService {
	private baseUrl = '/api/enhanced-project-templates';

	private async request<T>(
		endpoint: string,
		options: RequestInit = {}
	): Promise<T> {
		if (!browser) {
			throw new Error('Service can only be used in browser environment');
		}

		const url = `${this.baseUrl}${endpoint}`;
		
		const defaultHeaders = {
			'Content-Type': 'application/json',
		};

		// Add authentication token if available
		const token = localStorage.getItem('token');
		if (token) {
			defaultHeaders['Authorization'] = `Bearer ${token}`;
		}

		const response = await fetch(url, {
			...options,
			headers: {
				...defaultHeaders,
				...options.headers,
			},
		});

		if (!response.ok) {
			const errorData = await response.json().catch(() => null);
			throw new Error(errorData?.error || `Request failed: ${response.status}`);
		}

		return response.json();
	}

	// Template Versioning Operations

	async updateTemplateVersion(
		templateId: string, 
		request: VersionUpdateRequest
	): Promise<any> {
		console.log(`[AdvancedTemplateService] Updating version for template: ${templateId}`, request);
		
		try {
			const result = await this.request(`/${templateId}/update_version/`, {
				method: 'POST',
				body: JSON.stringify(request),
			});
			
			console.log(`[AdvancedTemplateService] Version update successful:`, result);
			return result;
		} catch (error) {
			console.error(`[AdvancedTemplateService] Version update failed:`, error);
			throw error;
		}
	}

	async getVersionHistory(templateId: string): Promise<{
		template_id: string;
		current_version: string;
		history: VersionHistory[];
		total_versions: number;
	}> {
		console.log(`[AdvancedTemplateService] Getting version history for: ${templateId}`);
		
		try {
			const result = await this.request(`/${templateId}/version_history/`);
			console.log(`[AdvancedTemplateService] Version history retrieved:`, result);
			return result;
		} catch (error) {
			console.error(`[AdvancedTemplateService] Failed to get version history:`, error);
			throw error;
		}
	}

	async compareVersions(
		templateId: string, 
		request: VersionComparisonRequest
	): Promise<any> {
		console.log(`[AdvancedTemplateService] Comparing versions for: ${templateId}`, request);
		
		try {
			const params = new URLSearchParams(request);
			const result = await this.request(`/${templateId}/compare_versions/?${params}`);
			console.log(`[AdvancedTemplateService] Version comparison completed:`, result);
			return result;
		} catch (error) {
			console.error(`[AdvancedTemplateService] Version comparison failed:`, error);
			throw error;
		}
	}

	// Analytics and Reporting

	async getAnalyticsReport(
		templateId: string, 
		days: number = 30
	): Promise<AnalyticsReport> {
		console.log(`[AdvancedTemplateService] Getting analytics report for: ${templateId}`);
		
		try {
			const result = await this.request(`/${templateId}/analytics_report/?days=${days}`);
			console.log(`[AdvancedTemplateService] Analytics report retrieved:`, result);
			return result;
		} catch (error) {
			console.error(`[AdvancedTemplateService] Failed to get analytics report:`, error);
			throw error;
		}
	}

	async getUsageMetrics(
		templateId: string, 
		days: number = 30
	): Promise<{
		template_id: string;
		period_days: number;
		usage_metrics: TemplateUsageMetrics;
		performance_metrics: PerformanceMetrics;
	}> {
		console.log(`[AdvancedTemplateService] Getting usage metrics for: ${templateId}`);
		
		try {
			const result = await this.request(`/${templateId}/usage_metrics/?days=${days}`);
			console.log(`[AdvancedTemplateService] Usage metrics retrieved:`, result);
			return result;
		} catch (error) {
			console.error(`[AdvancedTemplateService] Failed to get usage metrics:`, error);
			throw error;
		}
	}

	async getPopularityRankings(): Promise<{
		rankings: PopularityRanking[];
		total_templates: number;
		timestamp: string;
	}> {
		console.log(`[AdvancedTemplateService] Getting popularity rankings`);
		
		try {
			const result = await this.request(`/popularity_rankings/`);
			console.log(`[AdvancedTemplateService] Popularity rankings retrieved:`, result);
			return result;
		} catch (error) {
			console.error(`[AdvancedTemplateService] Failed to get popularity rankings:`, error);
			throw error;
		}
	}

	async trackUsage(request: UsageTrackingRequest): Promise<{ status: string; message: string }> {
		console.log(`[AdvancedTemplateService] Tracking usage:`, request);
		
		try {
			const result = await this.request(`/track_usage/`, {
				method: 'POST',
				body: JSON.stringify(request),
			});
			console.log(`[AdvancedTemplateService] Usage tracked successfully:`, result);
			return result;
		} catch (error) {
			console.error(`[AdvancedTemplateService] Failed to track usage:`, error);
			throw error;
		}
	}

	// Testing and Validation

	async runTests(
		templateId: string, 
		request: TestingRequest = {}
	): Promise<TestSuite> {
		console.log(`[AdvancedTemplateService] Running tests for: ${templateId}`, request);
		
		try {
			const result = await this.request(`/${templateId}/run_tests/`, {
				method: 'POST',
				body: JSON.stringify(request),
			});
			console.log(`[AdvancedTemplateService] Tests completed:`, result);
			return result;
		} catch (error) {
			console.error(`[AdvancedTemplateService] Test execution failed:`, error);
			throw error;
		}
	}

	// Health Monitoring

	async getSystemHealth(): Promise<SystemHealthReport> {
		console.log(`[AdvancedTemplateService] Getting system health status`);
		
		try {
			const result = await this.request(`/system_health/`);
			console.log(`[AdvancedTemplateService] System health retrieved:`, result);
			return result;
		} catch (error) {
			console.error(`[AdvancedTemplateService] Failed to get system health:`, error);
			throw error;
		}
	}

	async getTemplateHealth(templateId: string): Promise<TemplateHealthReport> {
		console.log(`[AdvancedTemplateService] Getting health status for: ${templateId}`);
		
		try {
			const result = await this.request(`/${templateId}/template_health/`);
			console.log(`[AdvancedTemplateService] Template health retrieved:`, result);
			return result;
		} catch (error) {
			console.error(`[AdvancedTemplateService] Failed to get template health:`, error);
			throw error;
		}
	}

	// Utility Methods

	parseVersion(versionString: string): TemplateVersion {
		const pattern = /^(\d+)\.(\d+)\.(\d+)(?:-([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?(?:\+([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?$/;
		const match = versionString.match(pattern);
		
		if (!match) {
			throw new Error(`Invalid semantic version format: ${versionString}`);
		}
		
		const [, major, minor, patch, prerelease, build] = match;
		
		return {
			major: parseInt(major, 10),
			minor: parseInt(minor, 10),
			patch: parseInt(patch, 10),
			prerelease: prerelease || undefined,
			build: build || undefined,
		};
	}

	formatVersion(version: TemplateVersion): string {
		let versionString = `${version.major}.${version.minor}.${version.patch}`;
		if (version.prerelease) {
			versionString += `-${version.prerelease}`;
		}
		if (version.build) {
			versionString += `+${version.build}`;
		}
		return versionString;
	}

	getHealthStatusColor(status: string): string {
		switch (status) {
			case 'healthy':
				return 'text-green-600';
			case 'warning':
				return 'text-yellow-600';
			case 'critical':
				return 'text-red-600';
			default:
				return 'text-gray-600';
		}
	}

	getHealthStatusIcon(status: string): string {
		switch (status) {
			case 'healthy':
				return '✅';
			case 'warning':
				return '⚠️';
			case 'critical':
				return '❌';
			default:
				return '❓';
		}
	}

	formatDuration(seconds: number): string {
		if (seconds < 60) {
			return `${seconds.toFixed(1)}s`;
		} else if (seconds < 3600) {
			return `${(seconds / 60).toFixed(1)}m`;
		} else {
			return `${(seconds / 3600).toFixed(1)}h`;
		}
	}

	formatPercentage(value: number): string {
		return `${(value * 100).toFixed(1)}%`;
	}

	formatBytes(bytes: number): string {
		const units = ['B', 'KB', 'MB', 'GB'];
		let size = bytes;
		let unitIndex = 0;
		
		while (size >= 1024 && unitIndex < units.length - 1) {
			size /= 1024;
			unitIndex++;
		}
		
		return `${size.toFixed(1)}${units[unitIndex]}`;
	}
}

// Export singleton instance
export const advancedTemplateManagementService = new AdvancedTemplateManagementService();
export default advancedTemplateManagementService;
