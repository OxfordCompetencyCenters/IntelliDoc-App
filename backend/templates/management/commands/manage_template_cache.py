# templates/management/commands/manage_template_cache.py
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
import json
import time
from templates.cache import TemplateDiscoveryCache, TemplateConfigurationCache, CacheWarmup
from templates.performance import TemplatePerformanceMonitor, TemplateHealthChecker

class Command(BaseCommand):
    help = 'Manage template cache system - refresh, clear, warmup, and monitor'

    def add_arguments(self, parser):
        parser.add_argument(
            'action',
            choices=['refresh', 'clear', 'warmup', 'status', 'performance', 'health', 'benchmark', 'start-updater', 'stop-updater'],
            help='Action to perform on template cache'
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force action even if cache is healthy'
        )
        parser.add_argument(
            '--template-id',
            type=str,
            help='Specific template ID for targeted operations'
        )
        parser.add_argument(
            '--output-format',
            choices=['json', 'table', 'summary'],
            default='summary',
            help='Output format for results'
        )

    def handle(self, *args, **options):
        action = options['action']
        force = options['force']
        template_id = options['template_id']
        output_format = options['output_format']

        try:
            if action == 'refresh':
                self.handle_refresh(force)
            elif action == 'clear':
                self.handle_clear(template_id)
            elif action == 'warmup':
                self.handle_warmup()
            elif action == 'status':
                self.handle_status(output_format)
            elif action == 'performance':
                self.handle_performance(output_format)
            elif action == 'health':
                self.handle_health(output_format)
            elif action == 'benchmark':
                self.handle_benchmark(output_format)
            elif action == 'start-updater':
                self.handle_start_updater()
            elif action == 'stop-updater':
                self.handle_stop_updater()
            else:
                raise CommandError(f'Unknown action: {action}')

        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Error executing {action}: {str(e)}')
            )
            raise CommandError(f'Command failed: {str(e)}')

    def handle_refresh(self, force):
        """Refresh template cache"""
        self.stdout.write('Refreshing template cache...')
        
        start_time = time.time()
        templates = TemplateDiscoveryCache.get_cached_templates(force_refresh=force)
        refresh_time = (time.time() - start_time) * 1000
        
        self.stdout.write(
            self.style.SUCCESS(
                f'Cache refreshed successfully!\n'
                f'  • Templates discovered: {len(templates)}\n'
                f'  • Refresh time: {refresh_time:.2f}ms\n'
                f'  • Force refresh: {force}'
            )
        )
        
        # Show template list
        if templates:
            self.stdout.write('\nDiscovered templates:')
            for template_id, template_info in templates.items():
                metadata = template_info.get('metadata', {})
                self.stdout.write(f'  • {template_id} - {metadata.get("name", "Unknown")} v{metadata.get("version", "1.0.0")}')

    def handle_clear(self, template_id):
        """Clear template cache"""
        if template_id:
            self.stdout.write(f'Clearing cache for template: {template_id}')
            TemplateConfigurationCache.clear_configuration_cache(template_id)
            self.stdout.write(self.style.SUCCESS(f'Cache cleared for template: {template_id}'))
        else:
            self.stdout.write('Clearing all template caches...')
            TemplateDiscoveryCache.clear_cache()
            TemplateConfigurationCache.clear_configuration_cache()
            self.stdout.write(self.style.SUCCESS('All template caches cleared'))

    def handle_warmup(self):
        """Warmup template cache"""
        self.stdout.write('Starting cache warmup...')
        
        start_time = time.time()
        CacheWarmup.warmup_template_cache()
        warmup_time = (time.time() - start_time) * 1000
        
        # Get statistics after warmup
        cache_stats = TemplateDiscoveryCache.get_cache_statistics()
        
        self.stdout.write(
            self.style.SUCCESS(
                f'Cache warmup completed!\n'
                f'  • Warmup time: {warmup_time:.2f}ms\n'
                f'  • Templates in cache: {cache_stats.get("memory_cache_size", 0)}\n'
                f'  • Background updater: {"Active" if cache_stats.get("background_updater_active", False) else "Inactive"}'
            )
        )

    def handle_status(self, output_format):
        """Show cache status"""
        cache_stats = TemplateDiscoveryCache.get_cache_statistics()
        
        if output_format == 'json':
            self.stdout.write(json.dumps(cache_stats, indent=2))
        elif output_format == 'table':
            self.print_table_format(cache_stats)
        else:
            self.print_summary_format(cache_stats)

    def handle_performance(self, output_format):
        """Show performance report"""
        self.stdout.write('Collecting performance metrics...')
        
        performance_report = TemplatePerformanceMonitor.get_performance_report()
        
        if output_format == 'json':
            self.stdout.write(json.dumps(performance_report, indent=2))
        else:
            self.print_performance_summary(performance_report)

    def handle_health(self, output_format):
        """Show health check results"""
        self.stdout.write('Performing health check...')
        
        health_report = TemplateHealthChecker.perform_health_check()
        
        if output_format == 'json':
            self.stdout.write(json.dumps(health_report, indent=2))
        else:
            self.print_health_summary(health_report)

    def handle_benchmark(self, output_format):
        """Run performance benchmark"""
        self.stdout.write('Running performance benchmark...')
        
        benchmark_results = TemplatePerformanceMonitor.run_performance_benchmark()
        
        if output_format == 'json':
            self.stdout.write(json.dumps(benchmark_results, indent=2))
        else:
            self.print_benchmark_summary(benchmark_results)

    def handle_start_updater(self):
        """Start background cache updater"""
        self.stdout.write('Starting background cache updater...')
        
        TemplateDiscoveryCache.start_background_updater()
        
        # Check if started successfully
        cache_stats = TemplateDiscoveryCache.get_cache_statistics()
        if cache_stats.get('background_updater_active', False):
            self.stdout.write(self.style.SUCCESS('Background cache updater started successfully'))
        else:
            self.stdout.write(self.style.WARNING('Background cache updater may not have started properly'))

    def handle_stop_updater(self):
        """Stop background cache updater"""
        self.stdout.write('Stopping background cache updater...')
        
        TemplateDiscoveryCache.stop_background_updater()
        self.stdout.write(self.style.SUCCESS('Background cache updater stopped'))

    def print_table_format(self, cache_stats):
        """Print cache statistics in table format"""
        self.stdout.write('\nCache Statistics:')
        self.stdout.write('─' * 50)
        
        stats_table = [
            ('Cache Hits', cache_stats.get('hits', 0)),
            ('Cache Misses', cache_stats.get('misses', 0)),
            ('Hit Rate', f"{cache_stats.get('hit_rate_percent', 0):.2f}%"),
            ('Filesystem Checks', cache_stats.get('filesystem_checks', 0)),
            ('Cache Refreshes', cache_stats.get('cache_refreshes', 0)),
            ('Avg Response Time', f"{cache_stats.get('average_response_time_ms', 0):.2f}ms"),
            ('Memory Cache Size', cache_stats.get('memory_cache_size', 0)),
            ('Background Updater', 'Active' if cache_stats.get('background_updater_active', False) else 'Inactive'),
        ]
        
        for label, value in stats_table:
            self.stdout.write(f'{label:<20}: {value}')

    def print_summary_format(self, cache_stats):
        """Print cache statistics in summary format"""
        total_requests = cache_stats.get('hits', 0) + cache_stats.get('misses', 0)
        hit_rate = cache_stats.get('hit_rate_percent', 0)
        avg_response = cache_stats.get('average_response_time_ms', 0)
        
        # Determine cache health
        if hit_rate >= 95 and avg_response <= 200:
            health_status = self.style.SUCCESS('HEALTHY')
        elif hit_rate >= 90 and avg_response <= 500:
            health_status = self.style.WARNING('GOOD')
        else:
            health_status = self.style.ERROR('NEEDS_IMPROVEMENT')
        
        self.stdout.write(f'\nTemplate Cache Status: {health_status}')
        self.stdout.write(f'  • Total Requests: {total_requests}')
        self.stdout.write(f'  • Hit Rate: {hit_rate:.2f}%')
        self.stdout.write(f'  • Average Response Time: {avg_response:.2f}ms')
        self.stdout.write(f'  • Templates Cached: {cache_stats.get("memory_cache_size", 0)}')
        self.stdout.write(f'  • Background Updater: {"Active" if cache_stats.get("background_updater_active", False) else "Inactive"}')

    def print_performance_summary(self, performance_report):
        """Print performance report in summary format"""
        if 'error' in performance_report:
            self.stdout.write(self.style.ERROR(f'Performance report error: {performance_report["error"]}'))
            return
        
        current = performance_report.get('current_metrics', {})
        historical = performance_report.get('historical_averages', {})
        status = performance_report.get('performance_status', {})
        
        # Overall status
        overall_status = status.get('overall_status', 'UNKNOWN')
        if overall_status == 'HEALTHY':
            status_style = self.style.SUCCESS
        elif overall_status == 'WARNING':
            status_style = self.style.WARNING
        else:
            status_style = self.style.ERROR
        
        self.stdout.write(f'\nPerformance Status: {status_style(overall_status)}')
        
        # Current metrics
        self.stdout.write('\nCurrent Metrics:')
        self.stdout.write(f'  • Response Time: {current.get("response_time_ms", 0):.2f}ms')
        self.stdout.write(f'  • Memory Usage: {current.get("memory_usage_mb", 0):.2f}MB')
        self.stdout.write(f'  • Cache Hit Rate: {current.get("cache_hit_rate", 0):.2f}%')
        
        # Historical averages
        self.stdout.write('\nHistorical Averages:')
        self.stdout.write(f'  • Avg Response Time: {historical.get("avg_response_time_ms", 0):.2f}ms')
        self.stdout.write(f'  • Avg Memory Usage: {historical.get("avg_memory_usage_mb", 0):.2f}MB')
        self.stdout.write(f'  • Avg Cache Hit Rate: {historical.get("avg_cache_hit_rate", 0):.2f}%')
        
        # Issues and warnings
        issues = status.get('issues', [])
        warnings = status.get('warnings', [])
        
        if issues:
            self.stdout.write('\nIssues:')
            for issue in issues:
                self.stdout.write(f'  • {self.style.ERROR(issue)}')
        
        if warnings:
            self.stdout.write('\nWarnings:')
            for warning in warnings:
                self.stdout.write(f'  • {self.style.WARNING(warning)}')

    def print_health_summary(self, health_report):
        """Print health check results in summary format"""
        if 'error' in health_report:
            self.stdout.write(self.style.ERROR(f'Health check error: {health_report["error"]}'))
            return
        
        overall_status = health_report.get('overall_status', 'UNKNOWN')
        if overall_status == 'HEALTHY':
            status_style = self.style.SUCCESS
        elif overall_status == 'UNHEALTHY':
            status_style = self.style.ERROR
        else:
            status_style = self.style.WARNING
        
        self.stdout.write(f'\nOverall Health Status: {status_style(overall_status)}')
        
        # Check results
        checks = health_report.get('checks', {})
        
        self.stdout.write('\nHealth Checks:')
        for check_name, check_result in checks.items():
            healthy = check_result.get('healthy', False)
            message = check_result.get('message', 'No message')
            
            if healthy:
                self.stdout.write(f'  ✓ {check_name}: {self.style.SUCCESS(message)}')
            else:
                self.stdout.write(f'  ✗ {check_name}: {self.style.ERROR(message)}')
        
        # Failed checks
        failed_checks = health_report.get('failed_checks', [])
        if failed_checks:
            self.stdout.write(f'\nFailed Checks: {", ".join(failed_checks)}')

    def print_benchmark_summary(self, benchmark_results):
        """Print benchmark results in summary format"""
        if 'error' in benchmark_results:
            self.stdout.write(self.style.ERROR(f'Benchmark error: {benchmark_results["error"]}'))
            return
        
        summary = benchmark_results.get('summary', {})
        tests = benchmark_results.get('tests', [])
        
        self.stdout.write('\nBenchmark Results:')
        self.stdout.write(f'  • Total Time: {summary.get("total_benchmark_time_ms", 0):.2f}ms')
        self.stdout.write(f'  • Templates Tested: {summary.get("templates_discovered", 0)}')
        self.stdout.write(f'  • Cache Performance: {summary.get("cache_performance", "Unknown")}')
        self.stdout.write(f'  • Concurrent Performance: {summary.get("concurrent_performance", "Unknown")}')
        
        # Individual test results
        self.stdout.write('\nTest Results:')
        for test in tests:
            test_name = test.get('name', 'Unknown Test')
            self.stdout.write(f'  • {test_name}:')
            
            if 'cold_cache_time_ms' in test:
                self.stdout.write(f'    - Cold Cache: {test["cold_cache_time_ms"]:.2f}ms')
                self.stdout.write(f'    - Warm Cache: {test["warm_cache_time_ms"]:.2f}ms')
                self.stdout.write(f'    - Improvement: {test["improvement_factor"]:.2f}x')
            
            if 'average_time_ms' in test:
                self.stdout.write(f'    - Average Time: {test["average_time_ms"]:.2f}ms')
                self.stdout.write(f'    - Max Time: {test["max_time_ms"]:.2f}ms')
                self.stdout.write(f'    - Min Time: {test["min_time_ms"]:.2f}ms')
            
            if 'concurrent_requests' in test:
                self.stdout.write(f'    - Concurrent Requests: {test["concurrent_requests"]}')
                self.stdout.write(f'    - Average Time: {test["average_time_ms"]:.2f}ms')
                self.stdout.write(f'    - Max Time: {test["max_time_ms"]:.2f}ms')
