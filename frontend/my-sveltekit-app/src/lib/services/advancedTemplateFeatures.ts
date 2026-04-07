/**
 * Advanced Template Features Service
 * Phase 5: Advanced Template Management
 * 
 * Frontend service for advanced template management features including:
 * - Template versioning operations
 * - Template analytics and reporting
 * - Template testing and validation
 * - System health monitoring
 * - Advanced template lifecycle management
 */

import { Logger } from '$lib/utils/logger';

const logger = Logger.getInstance();

// Types for Phase 5 Advanced Features
export interface TemplateVersion {
    major: number;
    minor: number;
    patch: number;
    prerelease?: string;
    build?: string;
}

export interface VersionUpdateRequest {
    new_version?: string;
    increment_type?: 'major' | 'minor' | 'patch';
    changelog?: string;
}

export interface VersionUpdateResult {
    status: string;
    template_id: string;
    previous_version: string;
    new_version: string;
    changelog?: string;
    timestamp: string;
}

export interface VersionHistory {
    template_id: string;
    current_version: string;
    history: Array<{
        from_version: string;
        to_version: string;
        timestamp: string;
        changelog: string;
    }>;
    total_versions: number;
}

export interface VersionComparison {
    template_id: string;
    version1: string;
    version2: string;
    comparison: 'older' | 'newer' | 'equal';
    compatibility: {
        compatible_versions: string[];
        breaking_versions: string[];
        deprecated_features: string[];
        new_features: string[];
    };
}

export interface TemplateAnalyticsReport {
    template_id: string;
    report_date: string;
    period_days: number;
    usage_metrics: {
        total_projects: number;
        active_projects: number;
        completed_projects: number;
        total_documents_processed: number;
        success_rate: number;
        user_satisfaction_score: number;
        last_used: string;
    };
    performance_metrics: {
        average_processing_time: number;
        total_api_calls: number;
        error_rate: number;
        memory_usage_avg: number;
        cpu_usage_avg: number;
    };
    behavior_metrics: {
        bounce_rate: number;
        session_duration_avg: number;
        pages_per_session: number;
        feature_usage: Record<string, number>;
        most_used_features: string[];
        least_used_features: string[];
    };
    popularity_metrics: {
        rank: number;
        total_rank: number;
        popularity_score: number;
        trend_direction: string;
        growth_rate: number;
    };
    insights: string[];
}

export interface TemplateTestResult {
    test_name: string;
    status: 'passed' | 'failed' | 'skipped' | 'error';
    execution_time: number;
    message: string;
    details?: Record<string, any>;
}

export interface TemplateTestSuite {
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
        results: TemplateTestResult[];
    };
}

export interface SystemHealthReport {
    overall_status: 'healthy' | 'warning' | 'critical' | 'unknown';
    timestamp: string;
    components: Array<{
        component: string;
        status: 'healthy' | 'warning' | 'critical' | 'unknown';
        message: string;
        details?: Record<string, any>;
    }>;
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

export interface PopularityRankings {
    rankings: Array<{
        template_id: string;
        rank: number;
        popularity_score: number;
        trend_direction: string;
        growth_rate: number;
    }>;
    total_templates: number;
    timestamp: string;
}

export class AdvancedTemplateFeaturesService {
    private baseUrl = '/api/enhanced-project-templates';

    /**
     * Update template version
     */
    async updateTemplateVersion(templateId: string, request: VersionUpdateRequest): Promise<VersionUpdateResult> {
        logger.info(`Updating template version for: ${templateId}`, request);

        try {
            const response = await fetch(`${this.baseUrl}/${templateId}/update_version/`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(request)
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.error || `HTTP ${response.status}`);
            }

            const result = await response.json();
            logger.info(`Template version updated successfully: ${templateId}`);
            return result;

        } catch (error) {
            logger.error(`Error updating template version for ${templateId}:`, error);
            throw error;
        }
    }

    /**
     * Get template version history
     */
    async getVersionHistory(templateId: string): Promise<VersionHistory> {
        logger.info(`Getting version history for template: ${templateId}`);

        try {
            const response = await fetch(`${this.baseUrl}/${templateId}/version_history/`);

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.error || `HTTP ${response.status}`);
            }

            const history = await response.json();
            logger.info(`Version history retrieved for ${templateId}: ${history.total_versions} versions`);
            return history;

        } catch (error) {
            logger.error(`Error getting version history for ${templateId}:`, error);
            throw error;
        }
    }

    /**
     * Compare template versions
     */
    async compareVersions(templateId: string, version1: string, version2: string): Promise<VersionComparison> {
        logger.info(`Comparing versions for ${templateId}: ${version1} vs ${version2}`);

        try {
            const params = new URLSearchParams({
                version1,
                version2
            });

            const response = await fetch(`${this.baseUrl}/${templateId}/compare_versions/?${params}`);

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.error || `HTTP ${response.status}`);
            }

            const comparison = await response.json();
            logger.info(`Version comparison completed for ${templateId}`);
            return comparison;

        } catch (error) {
            logger.error(`Error comparing versions for ${templateId}:`, error);
            throw error;
        }
    }

    /**
     * Get comprehensive analytics report
     */
    async getAnalyticsReport(templateId: string, days: number = 30): Promise<TemplateAnalyticsReport> {
        logger.info(`Getting analytics report for ${templateId} (${days} days)`);

        try {
            const params = new URLSearchParams({
                days: days.toString()
            });

            const response = await fetch(`${this.baseUrl}/${templateId}/analytics_report/?${params}`);

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.error || `HTTP ${response.status}`);
            }

            const report = await response.json();
            logger.info(`Analytics report retrieved for ${templateId}`);
            return report;

        } catch (error) {
            logger.error(`Error getting analytics report for ${templateId}:`, error);
            throw error;
        }
    }

    /**
     * Get template usage metrics
     */
    async getUsageMetrics(templateId: string, days: number = 30): Promise<any> {
        logger.info(`Getting usage metrics for ${templateId} (${days} days)`);

        try {
            const params = new URLSearchParams({
                days: days.toString()
            });

            const response = await fetch(`${this.baseUrl}/${templateId}/usage_metrics/?${params}`);

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.error || `HTTP ${response.status}`);
            }

            const metrics = await response.json();
            logger.info(`Usage metrics retrieved for ${templateId}`);
            return metrics;

        } catch (error) {
            logger.error(`Error getting usage metrics for ${templateId}:`, error);
            throw error;
        }
    }

    /**
     * Run comprehensive test suite
     */
    async runTests(templateId: string, options: {
        include_benchmarks?: boolean;
        include_regression?: boolean;
        include_compatibility?: boolean;
    } = {}): Promise<TemplateTestSuite> {
        logger.info(`Running tests for template: ${templateId}`, options);

        try {
            const response = await fetch(`${this.baseUrl}/${templateId}/run_tests/`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    include_benchmarks: options.include_benchmarks ?? true,
                    include_regression: options.include_regression ?? true,
                    include_compatibility: options.include_compatibility ?? true
                })
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.error || `HTTP ${response.status}`);
            }

            const testResults = await response.json();
            logger.info(`Tests completed for ${templateId}: ${testResults.test_suite.statistics.passed} passed, ${testResults.test_suite.statistics.failed} failed`);
            return testResults;

        } catch (error) {
            logger.error(`Error running tests for ${templateId}:`, error);
            throw error;
        }
    }

    /**
     * Get system health status
     */
    async getSystemHealth(): Promise<SystemHealthReport> {
        logger.info('Getting system health status');

        try {
            const response = await fetch(`${this.baseUrl}/system_health/`);

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.error || `HTTP ${response.status}`);
            }

            const health = await response.json();
            logger.info(`System health status retrieved: ${health.overall_status}`);
            return health;

        } catch (error) {
            logger.error('Error getting system health status:', error);
            throw error;
        }
    }

    /**
     * Get template health status
     */
    async getTemplateHealth(templateId: string): Promise<TemplateHealthReport> {
        logger.info(`Getting health status for template: ${templateId}`);

        try {
            const response = await fetch(`${this.baseUrl}/${templateId}/template_health/`);

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.error || `HTTP ${response.status}`);
            }

            const health = await response.json();
            logger.info(`Template health status retrieved for ${templateId}: ${health.status}`);
            return health;

        } catch (error) {
            logger.error(`Error getting template health for ${templateId}:`, error);
            throw error;
        }
    }

    /**
     * Track template usage event
     */
    async trackUsage(templateId: string, action: string, metadata: Record<string, any> = {}): Promise<void> {
        logger.info(`Tracking usage event: ${templateId} - ${action}`);

        try {
            const response = await fetch(`${this.baseUrl}/track_usage/`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    template_id: templateId,
                    action,
                    metadata
                })
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.error || `HTTP ${response.status}`);
            }

            logger.info(`Usage event tracked successfully: ${templateId} - ${action}`);

        } catch (error) {
            logger.error(`Error tracking usage for ${templateId}:`, error);
            // Don't throw error for tracking failures to avoid disrupting user flow
        }
    }

    /**
     * Get template popularity rankings
     */
    async getPopularityRankings(): Promise<PopularityRankings> {
        logger.info('Getting template popularity rankings');

        try {
            const response = await fetch(`${this.baseUrl}/popularity_rankings/`);

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.error || `HTTP ${response.status}`);
            }

            const rankings = await response.json();
            logger.info(`Popularity rankings retrieved: ${rankings.total_templates} templates`);
            return rankings;

        } catch (error) {
            logger.error('Error getting popularity rankings:', error);
            throw error;
        }
    }
}
