"""
Django management command for testing Milvus algorithms
"""
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
import json
import os

from django_milvus_search import MilvusSearchService, AlgorithmTester
from django_milvus_search.models import ConnectionConfig


class Command(BaseCommand):
    help = 'Test all Milvus algorithms and generate performance report'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--collections',
            nargs='+',
            help='Specific collections to test (optional)',
        )
        parser.add_argument(
            '--max-workers',
            type=int,
            default=5,
            help='Maximum number of parallel workers (default: 5)',
        )
        parser.add_argument(
            '--output',
            type=str,
            help='Output file path for results (optional)',
        )
        parser.add_argument(
            '--host',
            type=str,
            default='localhost',
            help='Milvus host (default: localhost)',
        )
        parser.add_argument(
            '--port',
            type=str,
            default='19530',
            help='Milvus port (default: 19530)',
        )
    
    def handle(self, *args, **options):
        self.stdout.write(
            self.style.SUCCESS('🧪 Starting Comprehensive Milvus Algorithm Test')
        )
        
        # Setup configuration
        config = ConnectionConfig(
            host=options['host'],
            port=options['port']
        )
        
        try:
            # Initialize service and tester
            service = MilvusSearchService(config=config)
            tester = AlgorithmTester(service=service)
            
            # Run comprehensive test
            self.stdout.write("Running algorithm tests...")
            results = tester.run_comprehensive_test(
                collections=options.get('collections'),
                max_workers=options['max_workers']
            )
            
            if "error" in results:
                raise CommandError(f"Test failed: {results['error']}")
            
            # Display summary
            summary = results["summary"]
            self.stdout.write("\n" + "="*70)
            self.stdout.write(self.style.SUCCESS("📊 TEST SUMMARY"))
            self.stdout.write("="*70)
            
            self.stdout.write(f"Total algorithms tested: {summary['total_tests']}")
            self.stdout.write(f"Successful: {summary['successful']} ({summary['success_rate']:.1f}%)")
            self.stdout.write(f"Failed: {summary['failed']}")
            
            # Index analysis
            if summary.get('index_analysis'):
                self.stdout.write("\n🔧 Index Type Performance:")
                for index_type, data in summary['index_analysis'].items():
                    self.stdout.write(
                        f"  {index_type:<12} Success: {data['success']}/{data['total']} "
                        f"({data.get('success_rate', 0):.1f}%) "
                        f"Avg Time: {data.get('avg_time', 0):.4f}s"
                    )
            
            # Top performers
            if summary.get('fastest_algorithms'):
                self.stdout.write("\n⚡ Top 5 Fastest Algorithms:")
                for i, (name, time_val) in enumerate(summary['fastest_algorithms'][:5], 1):
                    self.stdout.write(f"  {i}. {name:<30} {time_val*1000:.2f}ms")
            
            # Recommendations
            if summary.get('recommendations'):
                rec = summary['recommendations']
                self.stdout.write("\n🎯 RECOMMENDATIONS:")
                if rec.get('fastest_algorithm'):
                    self.stdout.write(f"  Fastest: {rec['fastest_algorithm']}")
                if rec.get('most_reliable_algorithm'):
                    self.stdout.write(f"  Most Reliable: {rec['most_reliable_algorithm']}")
                if rec.get('best_overall'):
                    self.stdout.write(f"  Best Overall: {rec['best_overall']}")
            
            # Save results
            output_file = options.get('output')
            if output_file:
                filename = tester.save_results(results, output_file)
            else:
                filename = tester.save_results(results)
            
            self.stdout.write(f"\n💾 Results saved to: {filename}")
            
            self.stdout.write(
                self.style.SUCCESS(f"\n🎉 Testing complete! {summary['successful']} algorithms working.")
            )
            
        except Exception as e:
            raise CommandError(f"Test failed: {e}")
        
        finally:
            try:
                service.shutdown()
            except:
                pass
