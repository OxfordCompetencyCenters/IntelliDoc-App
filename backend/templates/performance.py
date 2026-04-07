# templates/performance.py
import time
import psutil
import json
from typing import Dict, List, Optional
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone
from dataclasses import dataclass
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

@dataclass
class PerformanceMetrics:
    """Performance metrics data structure"""
    response_time_ms: float
    memory_usage_mb: float
    cpu_usage_percent: float
    cache_hit_rate: float
    filesystem_access_count: int
    error_count: int
    timestamp: float

class TemplatePerformanceMonitor:
    """Monitor template system performance and health"""
    
    # Performance thresholds
    MAX_RESPONSE_TIME_MS = 200
    MAX_MEMORY_USAGE_MB = 50
    MAX_CPU_USAGE_PERCENT = 80
    MIN_CACHE_HIT_RATE = 95
    
    # Monitoring configuration
    METRICS_RETENTION_HOURS = 24
    METRICS_COLLECTION_INTERVAL = 60  # seconds
    
    @classmethod
    def collect_metrics(cls) -> PerformanceMetrics:
        """Collect current performance metrics"""
        start_time = time.time()
        
        try:
            # Get cache statistics
            from .cache import TemplateDiscoveryCache
            cache_stats = TemplateDiscoveryCache.get_cache_statistics()
            
            # Measure response time
            templates = TemplateDiscoveryCache.get_cached_templates()
            response_time = (time.time() - start_time) * 1000
            
            # System metrics
            memory_info = psutil.virtual_memory()
            cpu_percent = psutil.cpu_percent(interval=0.1)
            
            # Calculate template system memory usage (approximation)
            template_memory_mb = cls._estimate_template_memory_usage(templates)
            
            metrics = PerformanceMetrics(
                response_time_ms=response_time,
                memory_usage_mb=template_memory_mb,
                cpu_usage_percent=cpu_percent,
                cache_hit_rate=cache_stats.get('hit_rate_percent', 0),
                filesystem_access_count=cache_stats.get('filesystem_checks', 0),
                error_count=0,  # TODO: Implement error tracking
                timestamp=time.time()
            )
            
            # Store metrics
            cls._store_metrics(metrics)
            
            return metrics
            
        except Exception as e:
            logger.error(f"Error collecting performance metrics: {str(e)}")
            return PerformanceMetrics(
                response_time_ms=0,
                memory_usage_mb=0,
                cpu_usage_percent=0,
                cache_hit_rate=0,
                filesystem_access_count=0,
                error_count=1,
                timestamp=time.time()
            )
    
    @classmethod
    def _estimate_template_memory_usage(cls, templates: Dict) -> float:
        """Estimate memory usage of template cache"""
        try:
            # Rough estimation based on template data size
            templates_json = json.dumps(templates)
            memory_bytes = len(templates_json.encode('utf-8'))
            return memory_bytes / (1024 * 1024)  # Convert to MB
        except Exception:
            return 0
    
    @classmethod
    def _store_metrics(cls, metrics: PerformanceMetrics):
        """Store metrics in cache for analysis"""
        try:
            # Get existing metrics
            cache_key = 'template_performance_metrics'
            existing_metrics = cache.get(cache_key, [])
            
            # Add new metrics
            existing_metrics.append({
                'response_time_ms': metrics.response_time_ms,
                'memory_usage_mb': metrics.memory_usage_mb,
                'cpu_usage_percent': metrics.cpu_usage_percent,
                'cache_hit_rate': metrics.cache_hit_rate,
                'filesystem_access_count': metrics.filesystem_access_count,
                'error_count': metrics.error_count,
                'timestamp': metrics.timestamp
            })
            
            # Keep only recent metrics
            cutoff_time = time.time() - (cls.METRICS_RETENTION_HOURS * 3600)
            existing_metrics = [m for m in existing_metrics if m['timestamp'] > cutoff_time]
            
            # Store back to cache
            cache.set(cache_key, existing_metrics, timeout=86400)  # 24 hours
            
        except Exception as e:
            logger.error(f"Error storing performance metrics: {str(e)}")
    
    @classmethod
    def get_performance_report(cls) -> Dict:
        """Get comprehensive performance report"""
        try:
            current_metrics = cls.collect_metrics()
            historical_metrics = cache.get('template_performance_metrics', [])
            
            # Calculate averages
            if historical_metrics:
                avg_response_time = sum(m['response_time_ms'] for m in historical_metrics) / len(historical_metrics)
                avg_memory_usage = sum(m['memory_usage_mb'] for m in historical_metrics) / len(historical_metrics)
                avg_cache_hit_rate = sum(m['cache_hit_rate'] for m in historical_metrics) / len(historical_metrics)
                max_response_time = max(m['response_time_ms'] for m in historical_metrics)
                min_response_time = min(m['response_time_ms'] for m in historical_metrics)
            else:
                avg_response_time = current_metrics.response_time_ms
                avg_memory_usage = current_metrics.memory_usage_mb
                avg_cache_hit_rate = current_metrics.cache_hit_rate
                max_response_time = current_metrics.response_time_ms
                min_response_time = current_metrics.response_time_ms
            
            # Performance status
            performance_status = cls._calculate_performance_status(current_metrics)
            
            return {
                'current_metrics': {
                    'response_time_ms': current_metrics.response_time_ms,
                    'memory_usage_mb': current_metrics.memory_usage_mb,
                    'cpu_usage_percent': current_metrics.cpu_usage_percent,
                    'cache_hit_rate': current_metrics.cache_hit_rate,
                    'filesystem_access_count': current_metrics.filesystem_access_count,
                    'timestamp': current_metrics.timestamp
                },
                'historical_averages': {
                    'avg_response_time_ms': round(avg_response_time, 2),
                    'avg_memory_usage_mb': round(avg_memory_usage, 2),
                    'avg_cache_hit_rate': round(avg_cache_hit_rate, 2),
                    'max_response_time_ms': round(max_response_time, 2),
                    'min_response_time_ms': round(min_response_time, 2)
                },
                'performance_status': performance_status,
                'thresholds': {
                    'max_response_time_ms': cls.MAX_RESPONSE_TIME_MS,
                    'max_memory_usage_mb': cls.MAX_MEMORY_USAGE_MB,
                    'min_cache_hit_rate': cls.MIN_CACHE_HIT_RATE
                },
                'metrics_count': len(historical_metrics),
                'collection_period_hours': cls.METRICS_RETENTION_HOURS
            }
            
        except Exception as e:
            logger.error(f"Error generating performance report: {str(e)}")
            return {'error': str(e)}
    
    @classmethod
    def _calculate_performance_status(cls, metrics: PerformanceMetrics) -> Dict:
        """Calculate overall performance status"""
        issues = []
        warnings = []
        
        # Check response time
        if metrics.response_time_ms > cls.MAX_RESPONSE_TIME_MS:
            issues.append(f"Response time ({metrics.response_time_ms:.2f}ms) exceeds threshold ({cls.MAX_RESPONSE_TIME_MS}ms)")
        elif metrics.response_time_ms > cls.MAX_RESPONSE_TIME_MS * 0.8:
            warnings.append(f"Response time ({metrics.response_time_ms:.2f}ms) approaching threshold")
        
        # Check memory usage
        if metrics.memory_usage_mb > cls.MAX_MEMORY_USAGE_MB:
            issues.append(f"Memory usage ({metrics.memory_usage_mb:.2f}MB) exceeds threshold ({cls.MAX_MEMORY_USAGE_MB}MB)")
        elif metrics.memory_usage_mb > cls.MAX_MEMORY_USAGE_MB * 0.8:
            warnings.append(f"Memory usage ({metrics.memory_usage_mb:.2f}MB) approaching threshold")
        
        # Check cache hit rate
        if metrics.cache_hit_rate < cls.MIN_CACHE_HIT_RATE:
            issues.append(f"Cache hit rate ({metrics.cache_hit_rate:.2f}%) below threshold ({cls.MIN_CACHE_HIT_RATE}%)")
        elif metrics.cache_hit_rate < cls.MIN_CACHE_HIT_RATE * 1.05:
            warnings.append(f"Cache hit rate ({metrics.cache_hit_rate:.2f}%) approaching threshold")
        
        # Overall status
        if issues:
            overall_status = 'CRITICAL'
        elif warnings:
            overall_status = 'WARNING'
        else:
            overall_status = 'HEALTHY'
        
        return {
            'overall_status': overall_status,
            'issues': issues,
            'warnings': warnings,
            'healthy': len(issues) == 0 and len(warnings) == 0
        }
    
    @classmethod
    def run_performance_benchmark(cls) -> Dict:
        """Run comprehensive performance benchmark"""
        logger.info("Starting template system performance benchmark")
        
        benchmark_results = {
            'timestamp': time.time(),
            'tests': []
        }
        
        try:
            # Test 1: Template discovery performance
            test_start = time.time()
            from .cache import TemplateDiscoveryCache
            
            # Cold cache test
            TemplateDiscoveryCache.clear_cache()
            cold_start = time.time()
            templates_cold = TemplateDiscoveryCache.get_cached_templates()
            cold_time = (time.time() - cold_start) * 1000
            
            # Warm cache test
            warm_start = time.time()
            templates_warm = TemplateDiscoveryCache.get_cached_templates()
            warm_time = (time.time() - warm_start) * 1000
            
            benchmark_results['tests'].append({
                'name': 'Template Discovery',
                'cold_cache_time_ms': cold_time,
                'warm_cache_time_ms': warm_time,
                'improvement_factor': cold_time / warm_time if warm_time > 0 else 0,
                'templates_count': len(templates_cold)
            })
            
            # Test 2: Configuration loading performance
            config_times = []
            for template_id in list(templates_cold.keys())[:5]:  # Test first 5 templates
                config_start = time.time()
                from .cache import TemplateConfigurationCache
                config = TemplateConfigurationCache.get_template_configuration(template_id)
                config_time = (time.time() - config_start) * 1000
                config_times.append(config_time)
            
            benchmark_results['tests'].append({
                'name': 'Configuration Loading',
                'average_time_ms': sum(config_times) / len(config_times) if config_times else 0,
                'max_time_ms': max(config_times) if config_times else 0,
                'min_time_ms': min(config_times) if config_times else 0,
                'templates_tested': len(config_times)
            })
            
            # Test 3: Concurrent access performance
            import threading
            concurrent_times = []
            threads = []
            
            def concurrent_test():
                start = time.time()
                TemplateDiscoveryCache.get_cached_templates()
                concurrent_times.append((time.time() - start) * 1000)
            
            # Start 10 concurrent requests
            for _ in range(10):
                thread = threading.Thread(target=concurrent_test)
                threads.append(thread)
                thread.start()
            
            # Wait for all threads
            for thread in threads:
                thread.join()
            
            benchmark_results['tests'].append({
                'name': 'Concurrent Access',
                'concurrent_requests': len(concurrent_times),
                'average_time_ms': sum(concurrent_times) / len(concurrent_times) if concurrent_times else 0,
                'max_time_ms': max(concurrent_times) if concurrent_times else 0,
                'total_time_ms': sum(concurrent_times)
            })
            
            # Overall benchmark summary
            total_time = (time.time() - test_start) * 1000
            benchmark_results['summary'] = {
                'total_benchmark_time_ms': total_time,
                'templates_discovered': len(templates_cold),
                'cache_performance': 'EXCELLENT' if warm_time < 10 else 'GOOD' if warm_time < 50 else 'NEEDS_IMPROVEMENT',
                'concurrent_performance': 'EXCELLENT' if max(concurrent_times) < 100 else 'GOOD' if max(concurrent_times) < 200 else 'NEEDS_IMPROVEMENT'
            }
            
            logger.info(f"Performance benchmark completed in {total_time:.2f}ms")
            return benchmark_results
            
        except Exception as e:
            logger.error(f"Error running performance benchmark: {str(e)}")
            benchmark_results['error'] = str(e)
            return benchmark_results


class TemplateHealthChecker:
    """Health check system for template infrastructure"""
    
    @classmethod
    def perform_health_check(cls) -> Dict:
        """Perform comprehensive health check"""
        health_report = {
            'timestamp': time.time(),
            'overall_status': 'HEALTHY',
            'checks': {}
        }
        
        try:
            # Check 1: Template directory accessibility
            health_report['checks']['template_directory'] = cls._check_template_directory()
            
            # Check 2: Cache system health
            health_report['checks']['cache_system'] = cls._check_cache_system()
            
            # Check 3: Template validation
            health_report['checks']['template_validation'] = cls._check_template_validation()
            
            # Check 4: Performance health
            health_report['checks']['performance'] = cls._check_performance_health()
            
            # Check 5: Memory health
            health_report['checks']['memory'] = cls._check_memory_health()
            
            # Determine overall status
            failed_checks = [name for name, result in health_report['checks'].items() if not result.get('healthy', False)]
            if failed_checks:
                health_report['overall_status'] = 'UNHEALTHY'
                health_report['failed_checks'] = failed_checks
            
            return health_report
            
        except Exception as e:
            logger.error(f"Error performing health check: {str(e)}")
            health_report['overall_status'] = 'ERROR'
            health_report['error'] = str(e)
            return health_report
    
    @classmethod
    def _check_template_directory(cls) -> Dict:
        """Check template directory accessibility"""
        try:
            from .discovery import TemplateDiscoverySystem
            template_dir = TemplateDiscoverySystem.get_template_definitions_path()
            
            if not template_dir.exists():
                return {
                    'healthy': False,
                    'message': f'Template directory does not exist: {template_dir}',
                    'path': str(template_dir)
                }
            
            if not template_dir.is_dir():
                return {
                    'healthy': False,
                    'message': f'Template path is not a directory: {template_dir}',
                    'path': str(template_dir)
                }
            
            # Check read permissions
            if not os.access(template_dir, os.R_OK):
                return {
                    'healthy': False,
                    'message': f'No read permission for template directory: {template_dir}',
                    'path': str(template_dir)
                }
            
            # Count template subdirectories
            template_count = len([d for d in template_dir.iterdir() if d.is_dir() and not d.name.startswith('.')])
            
            return {
                'healthy': True,
                'message': f'Template directory accessible with {template_count} templates',
                'path': str(template_dir),
                'template_count': template_count
            }
            
        except Exception as e:
            return {
                'healthy': False,
                'message': f'Error checking template directory: {str(e)}',
                'error': str(e)
            }
    
    @classmethod
    def _check_cache_system(cls) -> Dict:
        """Check cache system health"""
        try:
            from .cache import TemplateDiscoveryCache
            
            # Test cache functionality
            test_start = time.time()
            templates = TemplateDiscoveryCache.get_cached_templates()
            response_time = (time.time() - test_start) * 1000
            
            # Get cache statistics
            cache_stats = TemplateDiscoveryCache.get_cache_statistics()
            
            # Check cache performance
            issues = []
            if response_time > 200:
                issues.append(f'Slow cache response time: {response_time:.2f}ms')
            
            if cache_stats.get('hit_rate_percent', 0) < 90:
                issues.append(f'Low cache hit rate: {cache_stats.get("hit_rate_percent", 0):.2f}%')
            
            return {
                'healthy': len(issues) == 0,
                'message': 'Cache system healthy' if len(issues) == 0 else f'Cache issues: {"; ".join(issues)}',
                'response_time_ms': response_time,
                'cache_statistics': cache_stats,
                'issues': issues
            }
            
        except Exception as e:
            return {
                'healthy': False,
                'message': f'Error checking cache system: {str(e)}',
                'error': str(e)
            }
    
    @classmethod
    def _check_template_validation(cls) -> Dict:
        """Check template validation health"""
        try:
            from .cache import TemplateDiscoveryCache
            from .discovery import TemplateValidator
            
            templates = TemplateDiscoveryCache.get_cached_templates()
            validation_results = []
            
            for template_id, template_info in templates.items():
                folder_path = Path(template_info.get('folder_path', ''))
                if folder_path.exists():
                    validation_result = TemplateValidator.validate_template_directory(folder_path)
                    validation_results.append({
                        'template_id': template_id,
                        'valid': validation_result['valid'],
                        'errors': validation_result.get('errors', [])
                    })
            
            # Count validation results
            valid_templates = sum(1 for r in validation_results if r['valid'])
            invalid_templates = len(validation_results) - valid_templates
            
            return {
                'healthy': invalid_templates == 0,
                'message': f'{valid_templates} valid templates, {invalid_templates} invalid templates',
                'valid_templates': valid_templates,
                'invalid_templates': invalid_templates,
                'total_templates': len(validation_results),
                'validation_results': validation_results
            }
            
        except Exception as e:
            return {
                'healthy': False,
                'message': f'Error checking template validation: {str(e)}',
                'error': str(e)
            }
    
    @classmethod
    def _check_performance_health(cls) -> Dict:
        """Check performance health"""
        try:
            metrics = TemplatePerformanceMonitor.collect_metrics()
            
            issues = []
            if metrics.response_time_ms > 200:
                issues.append(f'High response time: {metrics.response_time_ms:.2f}ms')
            
            if metrics.cache_hit_rate < 95:
                issues.append(f'Low cache hit rate: {metrics.cache_hit_rate:.2f}%')
            
            return {
                'healthy': len(issues) == 0,
                'message': 'Performance healthy' if len(issues) == 0 else f'Performance issues: {"; ".join(issues)}',
                'response_time_ms': metrics.response_time_ms,
                'cache_hit_rate': metrics.cache_hit_rate,
                'issues': issues
            }
            
        except Exception as e:
            return {
                'healthy': False,
                'message': f'Error checking performance: {str(e)}',
                'error': str(e)
            }
    
    @classmethod
    def _check_memory_health(cls) -> Dict:
        """Check memory usage health"""
        try:
            from .cache import TemplateDiscoveryCache
            
            # Get memory statistics
            memory_info = psutil.virtual_memory()
            
            # Estimate template system memory usage
            templates = TemplateDiscoveryCache.get_cached_templates()
            template_memory_mb = TemplatePerformanceMonitor._estimate_template_memory_usage(templates)
            
            # Check memory usage
            issues = []
            if template_memory_mb > 50:
                issues.append(f'High template memory usage: {template_memory_mb:.2f}MB')
            
            if memory_info.percent > 90:
                issues.append(f'High system memory usage: {memory_info.percent:.2f}%')
            
            return {
                'healthy': len(issues) == 0,
                'message': 'Memory usage healthy' if len(issues) == 0 else f'Memory issues: {"; ".join(issues)}',
                'template_memory_mb': template_memory_mb,
                'system_memory_percent': memory_info.percent,
                'available_memory_mb': memory_info.available / (1024 * 1024),
                'issues': issues
            }
            
        except Exception as e:
            return {
                'healthy': False,
                'message': f'Error checking memory health: {str(e)}',
                'error': str(e)
            }
