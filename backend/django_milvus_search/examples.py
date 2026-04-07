"""
Example usage of Django Milvus Search package
"""
import os
import sys
import django
from django.conf import settings

# Configure Django settings if running standalone
if not settings.configured:
    settings.configure(
        DEBUG=True,
        INSTALLED_APPS=[
            'django_milvus_search',
        ],
        MILVUS_CONFIG={
            'host': 'localhost',
            'port': '19530',
            'max_connections': 8,
            'timeout': 60.0,
        },
        LOGGING={
            'version': 1,
            'disable_existing_loggers': False,
            'handlers': {
                'console': {
                    'class': 'logging.StreamHandler',
                },
            },
            'loggers': {
                'django_milvus_search': {
                    'handlers': ['console'],
                    'level': 'INFO',
                },
            },
        }
    )
    django.setup()

from django_milvus_search import MilvusSearchService, AlgorithmTester
from django_milvus_search.models import (
    SearchRequest, SearchParams, IndexType, MetricType, ConnectionConfig
)
from django_milvus_search.utils import generate_random_vector


def example_basic_search():
    """Example: Basic vector search"""
    print("=== Basic Search Example ===")
    
    try:
        # Initialize service
        service = MilvusSearchService()
        
        # List available collections
        collections = service.list_collections()
        print(f"Available collections: {collections}")
        
        if not collections:
            print("No collections found. Please create a collection first.")
            return
        
        # Use first collection for demo
        collection_name = collections[0]
        
        # Generate a random query vector (adjust dimension as needed)
        query_vector = generate_random_vector(768)  # Common dimension
        
        # Create search request
        request = SearchRequest(
            collection_name=collection_name,
            query_vectors=[query_vector],
            index_type=IndexType.AUTOINDEX,
            metric_type=MetricType.COSINE,
            limit=5
        )
        
        # Perform search
        result = service.search(request)
        
        # Display results
        print(f"Search completed in {result.search_time:.4f}s")
        print(f"Found {result.total_results} results:")
        
        for i, hit in enumerate(result.hits, 1):
            print(f"  {i}. ID: {hit['id']}, Score: {hit['score']:.4f}")
        
    except Exception as e:
        print(f"Search failed: {e}")


def example_advanced_search():
    """Example: Advanced search with specific parameters"""
    print("\n=== Advanced Search Example ===")
    
    try:
        service = MilvusSearchService()
        collections = service.list_collections()
        
        if not collections:
            print("No collections found.")
            return
        
        collection_name = collections[0]
        query_vector = generate_random_vector(768)
        
        # Advanced search with HNSW and specific parameters
        request = SearchRequest(
            collection_name=collection_name,
            query_vectors=[query_vector],
            index_type=IndexType.HNSW,
            metric_type=MetricType.L2,
            search_params=SearchParams(ef=64),
            limit=10,
            output_fields=["id", "vector"]  # Specify output fields
        )
        
        result = service.search(request)
        
        print(f"Algorithm used: {result.algorithm_used}")
        print(f"Parameters: {result.parameters_used}")
        print(f"Results: {len(result.hits)}")
        
    except Exception as e:
        print(f"Advanced search failed: {e}")


def example_batch_search():
    """Example: Batch search operations"""
    print("\n=== Batch Search Example ===")
    
    try:
        service = MilvusSearchService()
        collections = service.list_collections()
        
        if not collections:
            print("No collections found.")
            return
        
        collection_name = collections[0]
        
        # Create multiple search requests
        requests = []
        for i in range(3):
            query_vector = generate_random_vector(768)
            request = SearchRequest(
                collection_name=collection_name,
                query_vectors=[query_vector],
                limit=3
            )
            requests.append(request)
        
        # Perform batch search
        results = service.batch_search(requests)
        
        print(f"Completed {len(results)} searches:")
        for i, result in enumerate(results, 1):
            print(f"  Search {i}: {result.total_results} results in {result.search_time:.4f}s")
        
    except Exception as e:
        print(f"Batch search failed: {e}")


def example_algorithm_testing():
    """Example: Comprehensive algorithm testing"""
    print("\n=== Algorithm Testing Example ===")
    
    try:
        # Initialize tester
        tester = AlgorithmTester()
        
        print("Starting comprehensive algorithm test...")
        print("This will test all available algorithms with your collections.")
        
        # Run test (limit to 3 workers for demo)
        results = tester.run_comprehensive_test(max_workers=3)
        
        if "error" in results:
            print(f"Test failed: {results['error']}")
            return
        
        # Display summary
        summary = results["summary"]
        print(f"\n📊 Test Results:")
        print(f"Total algorithms tested: {summary['total_tests']}")
        print(f"Successful: {summary['successful']} ({summary['success_rate']:.1f}%)")
        print(f"Failed: {summary['failed']}")
        
        # Show top performers
        if summary.get('fastest_algorithms'):
            print(f"\n⚡ Top 3 Fastest Algorithms:")
            for i, (name, time_val) in enumerate(summary['fastest_algorithms'][:3], 1):
                print(f"  {i}. {name}: {time_val*1000:.2f}ms")
        
        # Show recommendations
        if summary.get('recommendations'):
            rec = summary['recommendations']
            print(f"\n🎯 Recommendations:")
            if rec.get('fastest_algorithm'):
                print(f"  Fastest: {rec['fastest_algorithm']}")
            if rec.get('best_overall'):
                print(f"  Best Overall: {rec['best_overall']}")
        
        # Save results
        filename = tester.save_results(results)
        print(f"\n💾 Detailed results saved to: {filename}")
        
    except Exception as e:
        print(f"Algorithm testing failed: {e}")


def example_performance_monitoring():
    """Example: Performance monitoring"""
    print("\n=== Performance Monitoring Example ===")
    
    try:
        service = MilvusSearchService()
        
        # Perform some searches
        collections = service.list_collections()
        if collections:
            collection_name = collections[0]
            
            # Perform multiple searches
            for i in range(5):
                query_vector = generate_random_vector(768)
                request = SearchRequest(
                    collection_name=collection_name,
                    query_vectors=[query_vector],
                    limit=3
                )
                service.search(request)
        
        # Get metrics
        metrics = service.get_metrics()
        
        print("📈 Performance Metrics:")
        print(f"  Total searches: {metrics['total_searches']}")
        print(f"  Successful searches: {metrics['successful_searches']}")
        print(f"  Failed searches: {metrics['failed_searches']}")
        print(f"  Average search time: {metrics.get('average_search_time', 0):.4f}s")
        print(f"  Success rate: {metrics.get('success_rate', 0):.2%}")
        
        # Health check
        health = service.health_check()
        print(f"\n🏥 Health Status: {health['status']}")
        print(f"  Collections available: {health.get('collections_count', 0)}")
        
    except Exception as e:
        print(f"Performance monitoring failed: {e}")


def example_custom_configuration():
    """Example: Custom configuration"""
    print("\n=== Custom Configuration Example ===")
    
    # Create custom configuration
    config = ConnectionConfig(
        host="localhost",
        port="19530",
        max_connections=16,
        timeout=30.0
    )
    
    try:
        # Initialize service with custom config
        service = MilvusSearchService(config=config, max_workers=8)
        
        # Test connection
        health = service.health_check()
        print(f"Connection test: {health['status']}")
        print(f"Configuration: {health.get('config', {})}")
        
        service.shutdown()
        
    except Exception as e:
        print(f"Custom configuration failed: {e}")


def main():
    """Run all examples"""
    print("🧪 Django Milvus Search Package Examples")
    print("=" * 50)
    
    try:
        # Run examples
        example_basic_search()
        example_advanced_search()
        example_batch_search()
        example_performance_monitoring()
        example_custom_configuration()
        
        # Ask user if they want to run algorithm testing
        print("\n" + "=" * 50)
        response = input("Run comprehensive algorithm testing? (y/N): ")
        if response.lower() in ['y', 'yes']:
            example_algorithm_testing()
        else:
            print("Skipping algorithm testing (can be time-consuming)")
        
        print("\n✅ All examples completed successfully!")
        print("\nNext steps:")
        print("- Review the generated results files")
        print("- Integrate the package into your Django application")
        print("- Use the Django management command: python manage.py test_milvus_algorithms")
        print("- Set up the REST API endpoints in your URLs")
        
    except KeyboardInterrupt:
        print("\n⚠️ Examples interrupted by user")
    except Exception as e:
        print(f"\n❌ Examples failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
