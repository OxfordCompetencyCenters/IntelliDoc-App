"""
Django views for Milvus search operations
"""
from django.http import JsonResponse, HttpRequest
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.views import View
import json
import logging

from django_milvus_search import MilvusSearchService, AlgorithmTester
from django_milvus_search.models import SearchRequest, SearchParams, IndexType, MetricType
from django_milvus_search.exceptions import MilvusSearchBaseException

logger = logging.getLogger(__name__)


class MilvusSearchView(View):
    """
    RESTful API view for Milvus search operations
    """
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.service = MilvusSearchService()
    
    @method_decorator(csrf_exempt)
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)
    
    def post(self, request: HttpRequest) -> JsonResponse:
        """
        Perform vector search
        
        POST /milvus/search/
        {
            "collection_name": "my_collection",
            "query_vectors": [[0.1, 0.2, 0.3, ...]],
            "index_type": "AUTOINDEX",
            "metric_type": "L2",
            "search_params": {"nprobe": 16},
            "limit": 10,
            "output_fields": ["id", "text"]
        }
        """
        try:
            data = json.loads(request.body)
            
            # Parse search parameters
            search_params = None
            if data.get('search_params'):
                search_params = SearchParams(**data['search_params'])
            
            # Create search request
            search_request = SearchRequest(
                collection_name=data['collection_name'],
                query_vectors=data['query_vectors'],
                index_type=IndexType(data.get('index_type', 'AUTOINDEX')),
                metric_type=MetricType(data.get('metric_type', 'L2')),
                search_params=search_params,
                limit=data.get('limit', 10),
                offset=data.get('offset', 0),
                output_fields=data.get('output_fields'),
                filter_expression=data.get('filter_expression')
            )
            
            # Perform search
            result = self.service.search(search_request)
            
            return JsonResponse({
                'success': True,
                'data': result.to_dict()
            })
            
        except MilvusSearchBaseException as e:
            logger.error(f"Milvus search error: {e}")
            return JsonResponse({
                'success': False,
                'error': str(e),
                'error_type': type(e).__name__
            }, status=400)
            
        except Exception as e:
            logger.error(f"Unexpected error in search: {e}")
            return JsonResponse({
                'success': False,
                'error': 'Internal server error'
            }, status=500)
    
    def get(self, request: HttpRequest) -> JsonResponse:
        """
        Get service information and health check
        
        GET /milvus/search/
        """
        try:
            health = self.service.health_check()
            metrics = self.service.get_metrics()
            
            return JsonResponse({
                'success': True,
                'health': health,
                'metrics': metrics
            })
            
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=500)


class MilvusCollectionsView(View):
    """
    API view for collection operations
    """
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.service = MilvusSearchService()
    
    def get(self, request: HttpRequest) -> JsonResponse:
        """
        List all collections or get specific collection info
        
        GET /milvus/collections/
        GET /milvus/collections/?collection=my_collection
        """
        try:
            collection_name = request.GET.get('collection')
            
            if collection_name:
                # Get specific collection info
                info = self.service.get_collection_info(collection_name)
                return JsonResponse({
                    'success': True,
                    'collection': info
                })
            else:
                # List all collections
                collections = self.service.list_collections()
                return JsonResponse({
                    'success': True,
                    'collections': collections
                })
                
        except MilvusSearchBaseException as e:
            logger.error(f"Collection operation error: {e}")
            return JsonResponse({
                'success': False,
                'error': str(e),
                'error_type': type(e).__name__
            }, status=400)
            
        except Exception as e:
            logger.error(f"Unexpected error in collections: {e}")
            return JsonResponse({
                'success': False,
                'error': 'Internal server error'
            }, status=500)


class MilvusTestView(View):
    """
    API view for algorithm testing operations
    """
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.service = MilvusSearchService()
        self.tester = AlgorithmTester(self.service)
    
    @method_decorator(csrf_exempt)
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)
    
    def post(self, request: HttpRequest) -> JsonResponse:
        """
        Run comprehensive algorithm test
        
        POST /milvus/test/
        {
            "collections": ["collection1", "collection2"],  # optional
            "max_workers": 5  # optional
        }
        """
        try:
            data = json.loads(request.body) if request.body else {}
            
            collections = data.get('collections')
            max_workers = data.get('max_workers', 5)
            
            # Run comprehensive test
            results = self.tester.run_comprehensive_test(
                collections=collections,
                max_workers=max_workers
            )
            
            if "error" in results:
                return JsonResponse({
                    'success': False,
                    'error': results['error']
                }, status=400)
            
            return JsonResponse({
                'success': True,
                'results': results
            })
            
        except Exception as e:
            logger.error(f"Algorithm test error: {e}")
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=500)


# Function-based views for simpler usage
@require_http_methods(["POST"])
@csrf_exempt
def search_vectors(request: HttpRequest) -> JsonResponse:
    """
    Simple function-based view for vector search
    """
    view = MilvusSearchView()
    return view.post(request)


@require_http_methods(["GET"])
def list_collections(request: HttpRequest) -> JsonResponse:
    """
    Simple function-based view for listing collections
    """
    view = MilvusCollectionsView()
    return view.get(request)


@require_http_methods(["GET"])
def health_check(request: HttpRequest) -> JsonResponse:
    """
    Simple function-based view for health check
    """
    view = MilvusSearchView()
    return view.get(request)
