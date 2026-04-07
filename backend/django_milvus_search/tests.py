"""
Tests for Django Milvus Search package
"""
import unittest
from unittest.mock import Mock, patch
import numpy as np

from django.test import TestCase, RequestFactory
from django.http import JsonResponse

from django_milvus_search.models import (
    ConnectionConfig, SearchRequest, SearchParams, IndexType, MetricType,
    AlgorithmConfiguration, TestResult
)
from django_milvus_search.services import MilvusSearchService
from django_milvus_search.utils import AlgorithmTester, normalize_vector, generate_random_vector
from django_milvus_search.views import MilvusSearchView
from django_milvus_search.exceptions import MilvusConnectionError, MilvusSearchError


class TestModels(TestCase):
    """Test data models"""
    
    def test_connection_config(self):
        """Test ConnectionConfig"""
        config = ConnectionConfig(host="test-host", port="19530")
        self.assertEqual(config.host, "test-host")
        self.assertEqual(config.port, "19530")
        
        config_dict = config.to_dict()
        self.assertIn("host", config_dict)
        self.assertIn("port", config_dict)
    
    def test_search_request_validation(self):
        """Test SearchRequest validation"""
        # Valid request
        request = SearchRequest(
            collection_name="test_collection",
            query_vectors=[[0.1, 0.2, 0.3]]
        )
        self.assertEqual(request.collection_name, "test_collection")
        
        # Invalid request - empty vectors
        with self.assertRaises(ValueError):
            SearchRequest(
                collection_name="test_collection",
                query_vectors=[]
            )
        
        # Invalid request - negative limit
        with self.assertRaises(ValueError):
            SearchRequest(
                collection_name="test_collection",
                query_vectors=[[0.1, 0.2, 0.3]],
                limit=-1
            )
    
    def test_search_params(self):
        """Test SearchParams"""
        params = SearchParams(nprobe=16, ef=64)
        params_dict = params.to_dict()
        
        self.assertEqual(params_dict["nprobe"], 16)
        self.assertEqual(params_dict["ef"], 64)
        self.assertNotIn("search_k", params_dict)  # None values excluded
    
    def test_algorithm_configuration(self):
        """Test AlgorithmConfiguration"""
        config = AlgorithmConfiguration(
            name="HNSW+L2",
            index_type=IndexType.HNSW,
            metric_type=MetricType.L2,
            search_params=SearchParams(ef=64),
            description="HNSW with L2 metric"
        )
        
        config_dict = config.to_dict()
        self.assertEqual(config_dict["name"], "HNSW+L2")
        self.assertEqual(config_dict["index_type"], "HNSW")
        self.assertEqual(config_dict["metric_type"], "L2")
    
    def test_test_result(self):
        """Test TestResult"""
        config = AlgorithmConfiguration(
            name="TEST",
            index_type=IndexType.FLAT,
            metric_type=MetricType.L2
        )
        
        result = TestResult(
            configuration=config,
            status="✅ SUCCESS",
            search_time=0.05
        )
        
        self.assertTrue(result.is_successful)
        
        failed_result = TestResult(
            configuration=config,
            status="❌ FAILED",
            error="Test error"
        )
        
        self.assertFalse(failed_result.is_successful)


class TestUtils(TestCase):
    """Test utility functions"""
    
    def test_normalize_vector(self):
        """Test vector normalization"""
        vector = [3.0, 4.0]  # Magnitude = 5
        normalized = normalize_vector(vector)
        
        # Check that magnitude is 1
        magnitude = sum(x**2 for x in normalized) ** 0.5
        self.assertAlmostEqual(magnitude, 1.0, places=5)
    
    def test_generate_random_vector(self):
        """Test random vector generation"""
        vector = generate_random_vector(128, normalize=True)
        
        self.assertEqual(len(vector), 128)
        
        # Check normalization
        magnitude = sum(x**2 for x in vector) ** 0.5
        self.assertAlmostEqual(magnitude, 1.0, places=5)
    
    def test_algorithm_tester_config_generation(self):
        """Test algorithm configuration generation"""
        with patch('django_milvus_search.utils.MilvusSearchService'):
            tester = AlgorithmTester()
            configs = tester.generate_algorithm_configurations()
            
            self.assertGreater(len(configs), 0)
            
            # Check that we have different index types
            index_types = {config.index_type for config in configs}
            self.assertIn(IndexType.FLAT, index_types)
            self.assertIn(IndexType.HNSW, index_types)
            self.assertIn(IndexType.AUTOINDEX, index_types)


class TestServices(TestCase):
    """Test MilvusSearchService"""
    
    @patch('django_milvus_search.services.connections')
    @patch('django_milvus_search.services.Collection')
    @patch('django_milvus_search.services.utility')
    def test_search_operation(self, mock_utility, mock_collection_class, mock_connections):
        """Test search operation"""
        # Setup mocks
        mock_collection = Mock()
        mock_collection_class.return_value = mock_collection
        mock_utility.has_collection.return_value = True
        
        # Mock search results
        mock_hit = Mock()
        mock_hit.id = 1
        mock_hit.distance = 0.5
        mock_hit.entity = Mock()
        mock_hit.entity.fields = {"text": "sample text"}
        
        mock_result = Mock()
        mock_result.__iter__ = Mock(return_value=iter([mock_hit]))
        mock_collection.search.return_value = [mock_result]
        
        # Create service and search request
        service = MilvusSearchService()
        request = SearchRequest(
            collection_name="test_collection",
            query_vectors=[[0.1, 0.2, 0.3]]
        )
        
        # Perform search
        result = service.search(request)
        
        # Verify results
        self.assertEqual(len(result.hits), 1)
        self.assertEqual(result.hits[0]["id"], 1)
        self.assertEqual(result.hits[0]["distance"], 0.5)
        self.assertIn("text", result.hits[0])
    
    @patch('django_milvus_search.services.connections')
    @patch('django_milvus_search.services.utility')
    def test_list_collections(self, mock_utility, mock_connections):
        """Test list collections operation"""
        mock_utility.list_collections.return_value = ["collection1", "collection2"]
        
        service = MilvusSearchService()
        collections = service.list_collections()
        
        self.assertEqual(len(collections), 2)
        self.assertIn("collection1", collections)
        self.assertIn("collection2", collections)
    
    def test_health_check(self):
        """Test health check functionality"""
        with patch.object(MilvusSearchService, 'list_collections') as mock_list:
            mock_list.return_value = ["test_collection"]
            
            service = MilvusSearchService()
            health = service.health_check()
            
            self.assertEqual(health["status"], "healthy")
            self.assertEqual(health["collections_count"], 1)
            self.assertIn("metrics", health)


class TestViews(TestCase):
    """Test Django views"""
    
    def setUp(self):
        self.factory = RequestFactory()
    
    @patch('django_milvus_search.views.MilvusSearchService')
    def test_search_view_post(self, mock_service_class):
        """Test search view POST request"""
        # Setup mock service
        mock_service = Mock()
        mock_service_class.return_value = mock_service
        
        # Mock search result
        mock_result = Mock()
        mock_result.to_dict.return_value = {
            "hits": [{"id": 1, "distance": 0.5}],
            "search_time": 0.05,
            "total_results": 1
        }
        mock_service.search.return_value = mock_result
        
        # Create request data
        request_data = {
            "collection_name": "test_collection",
            "query_vectors": [[0.1, 0.2, 0.3]],
            "limit": 10
        }
        
        # Create Django request
        request = self.factory.post(
            '/milvus/search/',
            data=request_data,
            content_type='application/json'
        )
        
        # Process request
        view = MilvusSearchView()
        response = view.post(request)
        
        # Verify response
        self.assertEqual(response.status_code, 200)
        response_data = response.json()
        self.assertTrue(response_data["success"])
        self.assertIn("data", response_data)
    
    @patch('django_milvus_search.views.MilvusSearchService')
    def test_search_view_get(self, mock_service_class):
        """Test search view GET request (health check)"""
        # Setup mock service
        mock_service = Mock()
        mock_service_class.return_value = mock_service
        mock_service.health_check.return_value = {"status": "healthy"}
        mock_service.get_metrics.return_value = {"total_searches": 0}
        
        # Create Django request
        request = self.factory.get('/milvus/search/')
        
        # Process request
        view = MilvusSearchView()
        response = view.get(request)
        
        # Verify response
        self.assertEqual(response.status_code, 200)
        response_data = response.json()
        self.assertTrue(response_data["success"])
        self.assertIn("health", response_data)
        self.assertIn("metrics", response_data)


class TestIntegration(TestCase):
    """Integration tests"""
    
    @patch('django_milvus_search.services.connections')
    @patch('django_milvus_search.services.Collection')
    @patch('django_milvus_search.services.utility')
    def test_end_to_end_search(self, mock_utility, mock_collection_class, mock_connections):
        """Test end-to-end search workflow"""
        # Setup mocks for successful search
        mock_collection = Mock()
        mock_collection_class.return_value = mock_collection
        mock_utility.has_collection.return_value = True
        
        # Mock search results
        mock_hit = Mock()
        mock_hit.id = 1
        mock_hit.distance = 0.3
        mock_hit.entity = Mock()
        mock_hit.entity.fields = {"title": "Test Document", "content": "Sample content"}
        
        mock_result = Mock()
        mock_result.__iter__ = Mock(return_value=iter([mock_hit]))
        mock_collection.search.return_value = [mock_result]
        
        # Create service and perform search
        service = MilvusSearchService()
        
        request = SearchRequest(
            collection_name="documents",
            query_vectors=[[0.1, 0.2, 0.3, 0.4]],
            index_type=IndexType.HNSW,
            metric_type=MetricType.COSINE,
            search_params=SearchParams(ef=64),
            limit=5,
            output_fields=["title", "content"]
        )
        
        result = service.search(request)
        
        # Verify results
        self.assertEqual(len(result.hits), 1)
        self.assertEqual(result.collection_name, "documents")
        self.assertEqual(result.algorithm_used, "HNSW+COSINE")
        self.assertIn("title", result.hits[0])
        self.assertIn("content", result.hits[0])
        self.assertEqual(result.hits[0]["title"], "Test Document")


if __name__ == '__main__':
    unittest.main()
