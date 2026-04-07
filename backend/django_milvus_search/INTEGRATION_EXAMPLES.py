"""
Practical Integration Examples for Your Django Application
=========================================================

These are ready-to-use code snippets you can copy into your Django application.
"""

# =============================================================================
# 1. REPLACE YOUR EXISTING VECTOR SEARCH VIEWS
# =============================================================================

from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
import json
import logging

from django_milvus_search import MilvusSearchService
from django_milvus_search.models import SearchRequest, IndexType, MetricType, SearchParams
from django_milvus_search.exceptions import MilvusSearchError

logger = logging.getLogger(__name__)

@require_http_methods(["POST"])
@csrf_exempt
def enhanced_vector_search(request):
    """
    Enhanced vector search using optimized Milvus algorithms
    
    Replace your existing vector search view with this
    """
    try:
        data = json.loads(request.body)
        
        # Initialize the service
        service = MilvusSearchService()
        
        # Create optimized search request
        search_request = SearchRequest(
            collection_name=data['collection_name'],
            query_vectors=[data['query_vector']],
            index_type=IndexType.HNSW,  # Optimized algorithm
            metric_type=MetricType.COSINE,
            search_params=SearchParams(ef=64),  # High precision
            limit=data.get('limit', 10),
            output_fields=data.get('output_fields', ['document_id', 'content', 'file_name'])
        )
        
        # Perform search
        result = service.search(search_request)
        
        # Get performance metrics
        metrics = service.get_metrics()
        
        return JsonResponse({
            'success': True,
            'results': result.hits,
            'metadata': {
                'search_time': result.search_time,
                'algorithm_used': result.algorithm_used,
                'total_results': result.total_results,
                'collection': result.collection_name
            },
            'performance': {
                'total_searches': metrics['total_searches'],
                'success_rate': metrics['success_rate'],
                'avg_search_time': metrics['average_search_time']
            }
        })
        
    except MilvusSearchError as e:
        logger.error(f"Milvus search error: {e}")
        return JsonResponse({
            'success': False,
            'error': 'Search operation failed',
            'details': str(e)
        }, status=500)
        
    except Exception as e:
        logger.error(f"Unexpected error in vector search: {e}")
        return JsonResponse({
            'success': False,
            'error': 'Internal server error'
        }, status=500)


# =============================================================================
# 2. BATCH SEARCH FOR MULTIPLE QUERIES
# =============================================================================

@require_http_methods(["POST"])
@csrf_exempt
def batch_vector_search(request):
    """
    Perform multiple searches efficiently using thread pool
    """
    try:
        data = json.loads(request.body)
        service = MilvusSearchService()
        
        # Create multiple search requests
        requests = []
        for query in data['queries']:
            search_request = SearchRequest(
                collection_name=query['collection_name'],
                query_vectors=[query['query_vector']],
                index_type=IndexType.HNSW,
                metric_type=MetricType.COSINE,
                limit=query.get('limit', 5)
            )
            requests.append(search_request)
        
        # Perform batch search
        results = service.batch_search(requests)
        
        # Format results
        formatted_results = []
        for i, result in enumerate(results):
            formatted_results.append({
                'query_index': i,
                'hits': result.hits,
                'search_time': result.search_time,
                'algorithm_used': result.algorithm_used
            })
        
        return JsonResponse({
            'success': True,
            'batch_results': formatted_results,
            'total_queries': len(requests)
        })
        
    except Exception as e:
        logger.error(f"Batch search error: {e}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


# =============================================================================
# 3. PERFORMANCE MONITORING ENDPOINT
# =============================================================================

@require_http_methods(["GET"])
def search_performance_dashboard(request):
    """
    Get comprehensive performance metrics for monitoring dashboard
    """
    try:
        service = MilvusSearchService()
        
        # Health check
        health = service.health_check()
        
        # Performance metrics
        metrics = service.get_metrics()
        
        # Collection information
        collections = service.list_collections()
        collection_info = {}
        
        for collection_name in collections[:5]:  # Limit to first 5 for performance
            try:
                info = service.get_collection_info(collection_name)
                collection_info[collection_name] = {
                    'entities': info.get('num_entities', 0),
                    'status': 'loaded' if info.get('is_loaded') else 'not_loaded'
                }
            except Exception as e:
                collection_info[collection_name] = {'error': str(e)}
        
        return JsonResponse({
            'success': True,
            'health': health,
            'metrics': metrics,
            'collections': {
                'total': len(collections),
                'details': collection_info
            },
            'recommendations': {
                'status': 'good' if metrics.get('success_rate', 0) > 0.9 else 'needs_attention',
                'performance': 'fast' if metrics.get('average_search_time', 0) < 0.1 else 'acceptable'
            }
        })
        
    except Exception as e:
        logger.error(f"Performance dashboard error: {e}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


# =============================================================================
# 4. INTEGRATION WITH YOUR EXISTING VECTOR_SEARCH APP
# =============================================================================

class EnhancedVectorSearchMixin:
    """
    Mixin to add to your existing vector search views
    """
    
    def __init__(self):
        self.milvus_service = MilvusSearchService()
    
    def perform_enhanced_search(self, collection_name, query_vector, **kwargs):
        """
        Enhanced search method to replace your existing search logic
        """
        try:
            search_request = SearchRequest(
                collection_name=collection_name,
                query_vectors=[query_vector],
                index_type=IndexType.HNSW,  # Optimized for your collections
                metric_type=MetricType.COSINE,
                search_params=SearchParams(ef=64),
                limit=kwargs.get('limit', 10),
                output_fields=kwargs.get('output_fields'),
                filter_expression=kwargs.get('filter')
            )
            
            result = self.milvus_service.search(search_request)
            
            return {
                'success': True,
                'hits': result.hits,
                'search_time': result.search_time,
                'algorithm_used': result.algorithm_used,
                'total_results': result.total_results
            }
            
        except Exception as e:
            logger.error(f"Enhanced search failed: {e}")
            return {
                'success': False,
                'error': str(e),
                'hits': []
            }
    
    def get_search_health(self):
        """Get search service health status"""
        return self.milvus_service.health_check()


# =============================================================================
# 5. ALGORITHM OPTIMIZATION FUNCTION
# =============================================================================

def optimize_collection_algorithms(collection_names=None):
    """
    Background function to optimize algorithms for collections
    Can be called from Celery task or management command
    """
    from django_milvus_search.utils import AlgorithmTester
    
    try:
        tester = AlgorithmTester()
        
        if collection_names is None:
            # Use your specific collections
            collection_names = [
                "hello_68c8822f_0b2d_42aa_ae9c_cbf4571ee1f5",
                "hello_a6be3a0f_3c90_448b_ac56_9d0220b7d198",
                # Add more of your collections
            ]
        
        results = tester.run_comprehensive_test(
            collections=collection_names,
            max_workers=3  # Don't overwhelm your system
        )
        
        if 'error' in results:
            return {'success': False, 'error': results['error']}
        
        summary = results['summary']
        recommendations = summary.get('recommendations', {})
        
        return {
            'success': True,
            'collections_tested': len(collection_names),
            'success_rate': summary.get('success_rate'),
            'best_algorithm': recommendations.get('best_overall'),
            'fastest_algorithm': recommendations.get('fastest_algorithm'),
            'detailed_results': results
        }
        
    except Exception as e:
        logger.error(f"Algorithm optimization failed: {e}")
        return {'success': False, 'error': str(e)}


# =============================================================================
# 6. DJANGO MODEL INTEGRATION (Optional)
# =============================================================================

from django.db import models
from django.utils import timezone

class SearchQuery(models.Model):
    """
    Model to log search queries and performance (optional)
    """
    collection_name = models.CharField(max_length=255)
    query_vector_hash = models.CharField(max_length=64)  # Hash of query vector
    algorithm_used = models.CharField(max_length=50)
    search_time = models.FloatField()
    results_count = models.IntegerField()
    success = models.BooleanField()
    error_message = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(default=timezone.now)
    
    class Meta:
        ordering = ['-created_at']
    
    @classmethod
    def log_search(cls, search_request, result, success=True, error=None):
        """Log a search operation"""
        import hashlib
        
        # Create hash of query vector for privacy
        vector_str = str(search_request.query_vectors[0])
        vector_hash = hashlib.sha256(vector_str.encode()).hexdigest()[:64]
        
        return cls.objects.create(
            collection_name=search_request.collection_name,
            query_vector_hash=vector_hash,
            algorithm_used=result.algorithm_used if result else 'unknown',
            search_time=result.search_time if result else 0,
            results_count=result.total_results if result else 0,
            success=success,
            error_message=str(error) if error else None
        )


# =============================================================================
# 7. URL PATTERNS FOR YOUR APP
# =============================================================================

"""
Add these to your urls.py:

from django.urls import path
from . import your_integration_views

urlpatterns = [
    # Enhanced vector search
    path('api/search/enhanced/', your_integration_views.enhanced_vector_search, name='enhanced-search'),
    
    # Batch search
    path('api/search/batch/', your_integration_views.batch_vector_search, name='batch-search'),
    
    # Performance monitoring
    path('api/search/performance/', your_integration_views.search_performance_dashboard, name='search-performance'),
    
    # Your existing URLs...
]
"""

# =============================================================================
# 8. USAGE EXAMPLES
# =============================================================================

if __name__ == "__main__":
    print("🚀 Django Milvus Search Integration Examples")
    print("=" * 50)
    print("Copy the functions above into your Django application")
    print("\n📋 Quick Integration Steps:")
    print("1. Copy enhanced_vector_search() to replace your existing search view")
    print("2. Add search_performance_dashboard() for monitoring")
    print("3. Use EnhancedVectorSearchMixin in your existing classes")
    print("4. Run optimize_collection_algorithms() to find best algorithms")
    print("\n🎯 Your collections ready for optimization:")
    collections = [
        "hello_68c8822f_0b2d_42aa_ae9c_cbf4571ee1f5",
        "hello_a6be3a0f_3c90_448b_ac56_9d0220b7d198", 
        "test_4f517db9_3175_43d3_853d_a22164fc20db",
        "hybrid_search_test"
    ]
    for collection in collections:
        print(f"  ✅ {collection}")
