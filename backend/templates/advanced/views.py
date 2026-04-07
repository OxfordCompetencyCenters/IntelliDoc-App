"""
Advanced Template Management Views
Phase 5: Advanced Template Features

API endpoints for advanced template management including:
- Template versioning operations
- Template analytics and reporting
- Template testing and validation
- System health monitoring
- Template lifecycle management
"""

import logging
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from django.http import JsonResponse
from .versioning import TemplateVersioningService
from .analytics import TemplateAnalyticsService
from .testing import TemplateTestingFramework
from .health_monitoring import TemplateHealthMonitor

logger = logging.getLogger(__name__)


class AdvancedTemplateManagementMixin:
    """Mixin providing advanced template management capabilities"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.versioning_service = TemplateVersioningService()
        self.analytics_service = TemplateAnalyticsService()
        self.testing_framework = TemplateTestingFramework()
        self.health_monitor = TemplateHealthMonitor()
        logger.info("Initialized AdvancedTemplateManagementMixin")
    
    @action(detail=True, methods=['post'])
    def update_version(self, request, pk=None):
        """Update template version with changelog"""
        logger.info(f"Starting template version update for template: {pk}")
        
        try:
            template_id = pk
            new_version = request.data.get('new_version')
            increment_type = request.data.get('increment_type')  # 'major', 'minor', 'patch'
            changelog = request.data.get('changelog')
            
            if not new_version and not increment_type:
                logger.warning("No version or increment type provided")
                return Response({
                    'error': 'Either new_version or increment_type must be provided'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Get current version
            current_version = str(self.versioning_service.get_template_version(template_id))
            logger.info(f"Current version: {current_version}")
            
            # Calculate new version if increment type provided
            if increment_type and not new_version:
                new_version = self.versioning_service.increment_version(current_version, increment_type)
                logger.info(f"Calculated new version: {new_version}")
            
            # Validate new version format
            self.versioning_service.parse_version(new_version)
            
            # Update template version
            success = self.versioning_service.update_template_version(
                template_id, new_version, changelog
            )
            
            if success:
                logger.info(f"Template version updated successfully: {current_version} -> {new_version}")
                return Response({
                    'status': 'success',
                    'template_id': template_id,
                    'previous_version': current_version,
                    'new_version': new_version,
                    'changelog': changelog,
                    'timestamp': timezone.now().isoformat()
                })
            else:
                logger.error("Template version update failed")
                return Response({
                    'error': 'Version update failed'
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
        except Exception as e:
            logger.error(f"Error updating template version: {str(e)}")
            return Response({
                'error': f'Version update error: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['get'])
    def version_history(self, request, pk=None):
        """Get version history for a template"""
        logger.info(f"Getting version history for template: {pk}")
        
        try:
            template_id = pk
            history = self.versioning_service.get_version_history(template_id)
            current_version = str(self.versioning_service.get_template_version(template_id))
            
            logger.info(f"Retrieved version history with {len(history)} entries")
            return Response({
                'template_id': template_id,
                'current_version': current_version,
                'history': history,
                'total_versions': len(history)
            })
            
        except Exception as e:
            logger.error(f"Error getting version history: {str(e)}")
            return Response({
                'error': f'Version history error: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['get'])
    def compare_versions(self, request, pk=None):
        """Compare two versions of a template"""
        logger.info(f"Comparing template versions for: {pk}")
        
        try:
            template_id = pk
            version1 = request.query_params.get('version1')
            version2 = request.query_params.get('version2')
            
            if not version1 or not version2:
                return Response({
                    'error': 'Both version1 and version2 parameters are required'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            comparison_result = self.versioning_service.compare_versions(version1, version2)
            
            # Get compatibility information
            compatibility = self.versioning_service.check_version_compatibility(
                template_id, version2
            )
            
            logger.info(f"Version comparison completed: {version1} is {comparison_result} than {version2}")
            return Response({
                'template_id': template_id,
                'version1': version1,
                'version2': version2,
                'comparison': comparison_result,
                'compatibility': {
                    'compatible_versions': compatibility.compatible_versions,
                    'breaking_versions': compatibility.breaking_versions,
                    'deprecated_features': compatibility.deprecated_features,
                    'new_features': compatibility.new_features
                }
            })
            
        except Exception as e:
            logger.error(f"Error comparing versions: {str(e)}")
            return Response({
                'error': f'Version comparison error: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['get'])
    def analytics_report(self, request, pk=None):
        """Get comprehensive analytics report for a template"""
        logger.info(f"Generating analytics report for template: {pk}")
        
        try:
            template_id = pk
            days = int(request.query_params.get('days', 30))
            
            # Generate comprehensive analytics report
            report = self.analytics_service.generate_analytics_report(template_id, days)
            
            logger.info(f"Analytics report generated successfully for {template_id}")
            return Response(report)
            
        except Exception as e:
            logger.error(f"Error generating analytics report: {str(e)}")
            return Response({
                'error': f'Analytics report error: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['get'])
    def usage_metrics(self, request, pk=None):
        """Get usage metrics for a template"""
        logger.info(f"Getting usage metrics for template: {pk}")
        
        try:
            template_id = pk
            days = int(request.query_params.get('days', 30))
            
            usage_metrics = self.analytics_service.get_template_usage_metrics(template_id, days)
            performance_metrics = self.analytics_service.get_performance_metrics(template_id, days)
            
            logger.info(f"Usage metrics retrieved successfully for {template_id}")
            return Response({
                'template_id': template_id,
                'period_days': days,
                'usage_metrics': {
                    'total_projects': usage_metrics.total_projects,
                    'active_projects': usage_metrics.active_projects,
                    'completed_projects': usage_metrics.completed_projects,
                    'total_documents_processed': usage_metrics.total_documents_processed,
                    'success_rate': usage_metrics.success_rate,
                    'user_satisfaction_score': usage_metrics.user_satisfaction_score,
                    'last_used': usage_metrics.last_used.isoformat()
                },
                'performance_metrics': {
                    'average_processing_time': performance_metrics.average_processing_time,
                    'total_api_calls': performance_metrics.total_api_calls,
                    'error_rate': performance_metrics.error_rate,
                    'memory_usage_avg': performance_metrics.memory_usage_avg,
                    'cpu_usage_avg': performance_metrics.cpu_usage_avg
                }
            })
            
        except Exception as e:
            logger.error(f"Error getting usage metrics: {str(e)}")
            return Response({
                'error': f'Usage metrics error: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['post'])
    def run_tests(self, request, pk=None):
        """Run comprehensive test suite for a template"""
        logger.info(f"Running tests for template: {pk}")
        
        try:
            template_id = pk
            include_benchmarks = request.data.get('include_benchmarks', True)
            include_regression = request.data.get('include_regression', True)
            include_compatibility = request.data.get('include_compatibility', True)
            
            # Run comprehensive test suite
            test_suite = self.testing_framework.run_comprehensive_test_suite(
                template_id,
                include_benchmarks=include_benchmarks,
                include_regression=include_regression,
                include_compatibility=include_compatibility
            )
            
            logger.info(f"Test suite completed for {template_id}: "
                       f"{test_suite.passed} passed, {test_suite.failed} failed")
            
            return Response({
                'template_id': template_id,
                'test_suite': {
                    'suite_name': test_suite.suite_name,
                    'duration': test_suite.duration,
                    'statistics': {
                        'passed': test_suite.passed,
                        'failed': test_suite.failed,
                        'errors': test_suite.errors,
                        'skipped': test_suite.skipped,
                        'total': len(test_suite.results)
                    },
                    'results': [
                        {
                            'test_name': result.test_name,
                            'status': result.status,
                            'execution_time': result.execution_time,
                            'message': result.message,
                            'details': result.details
                        } for result in test_suite.results
                    ]
                }
            })
            
        except Exception as e:
            logger.error(f"Error running tests: {str(e)}")
            return Response({
                'error': f'Testing error: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'])
    def system_health(self, request):
        """Get system health status for all templates"""
        logger.info("Getting system health status")
        
        try:
            health_status = self.health_monitor.get_system_health()
            
            logger.info("System health status retrieved successfully")
            return Response(health_status)
            
        except Exception as e:
            logger.error(f"Error getting system health: {str(e)}")
            return Response({
                'error': f'System health error: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['get'])
    def template_health(self, request, pk=None):
        """Get health status for a specific template"""
        logger.info(f"Getting health status for template: {pk}")
        
        try:
            template_id = pk
            health_status = self.health_monitor.get_template_health(template_id)
            
            logger.info(f"Template health status retrieved for {template_id}")
            return Response(health_status)
            
        except Exception as e:
            logger.error(f"Error getting template health: {str(e)}")
            return Response({
                'error': f'Template health error: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['post'])
    def track_usage(self, request):
        """Track template usage event"""
        logger.info("Tracking template usage event")
        
        try:
            template_id = request.data.get('template_id')
            action = request.data.get('action')
            metadata = request.data.get('metadata', {})
            
            if not template_id or not action:
                return Response({
                    'error': 'template_id and action are required'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            self.analytics_service.track_template_usage(template_id, action, metadata)
            
            logger.info(f"Usage event tracked: {template_id} - {action}")
            return Response({
                'status': 'success',
                'message': 'Usage event tracked successfully'
            })
            
        except Exception as e:
            logger.error(f"Error tracking usage: {str(e)}")
            return Response({
                'error': f'Usage tracking error: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'])
    def popularity_rankings(self, request):
        """Get popularity rankings for all templates"""
        logger.info("Getting template popularity rankings")
        
        try:
            rankings = []
            
            # Get all templates (placeholder - would use template discovery)
            all_templates = ['aicc-intellidoc', 'legal', 'medical', 'history']
            
            for template_id in all_templates:
                try:
                    popularity_metrics = self.analytics_service.get_popularity_metrics(template_id)
                    rankings.append({
                        'template_id': template_id,
                        'rank': popularity_metrics.rank,
                        'popularity_score': popularity_metrics.popularity_score,
                        'trend_direction': popularity_metrics.trend_direction,
                        'growth_rate': popularity_metrics.growth_rate
                    })
                except Exception as e:
                    logger.warning(f"Error getting popularity for {template_id}: {str(e)}")
                    continue
            
            # Sort by rank
            rankings.sort(key=lambda x: x['rank'])
            
            logger.info(f"Popularity rankings retrieved for {len(rankings)} templates")
            return Response({
                'rankings': rankings,
                'total_templates': len(rankings),
                'timestamp': timezone.now().isoformat()
            })
            
        except Exception as e:
            logger.error(f"Error getting popularity rankings: {str(e)}")
            return Response({
                'error': f'Popularity rankings error: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
