"""
Utility functions and algorithm testing functionality
"""
import time
import numpy as np
from typing import Dict, List, Any, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
import logging
import json
from datetime import datetime

from .models import (
    ConnectionConfig, SearchRequest, SearchParams, IndexType, MetricType,
    AlgorithmConfiguration, TestResult
)
from .services import MilvusSearchService
from .exceptions import MilvusSearchError, MilvusConnectionError

logger = logging.getLogger(__name__)


def normalize_vector(vector: List[float]) -> List[float]:
    """Normalize a vector to unit length"""
    np_vector = np.array(vector, dtype=np.float32)
    norm = np.linalg.norm(np_vector)
    if norm == 0:
        return vector
    return (np_vector / norm).tolist()


def generate_random_vector(dimension: int, normalize: bool = True) -> List[float]:
    """Generate a random vector of specified dimension"""
    vector = np.random.random(dimension).astype(np.float32).tolist()
    return normalize_vector(vector) if normalize else vector


def calculate_similarity(vector1: List[float], vector2: List[float], 
                        metric: MetricType = MetricType.COSINE) -> float:
    """Calculate similarity between two vectors"""
    v1 = np.array(vector1, dtype=np.float32)
    v2 = np.array(vector2, dtype=np.float32)
    
    if metric == MetricType.COSINE:
        return np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2))
    elif metric == MetricType.IP:
        return np.dot(v1, v2)
    elif metric == MetricType.L2:
        return np.linalg.norm(v1 - v2)
    else:
        raise ValueError(f"Unsupported metric type: {metric}")


class AlgorithmTester:
    """
    Comprehensive algorithm tester for Milvus search operations.
    
    This class provides functionality to test all available Milvus algorithms
    with different configurations and parameters, making it easy to find the
    best performing algorithms for your specific use case.
    """
    
    def __init__(self, service: Optional[MilvusSearchService] = None):
        """
        Initialize algorithm tester
        
        Args:
            service: MilvusSearchService instance (optional)
        """
        self.service = service or MilvusSearchService()
        self.test_results = {}
        self.working_collections = []
        self.working_dimension = None
    
    def detect_working_configuration(self, collections: Optional[List[str]] = None,
                                   dimensions_to_test: Optional[List[int]] = None) -> Tuple[str, int]:
        """
        Auto-detect working collection and vector dimension
        
        Args:
            collections: List of collection names to test
            dimensions_to_test: List of dimensions to test
            
        Returns:
            Tuple of (collection_name, dimension)
        """
        if collections is None:
            collections = self.service.list_collections()
        
        if dimensions_to_test is None:
            dimensions_to_test = [64, 128, 256, 384, 512, 768, 1024, 1536, 2048]
        
        logger.info("Auto-detecting working configuration...")
        
        for collection in collections:
            logger.info(f"Testing collection: {collection}")
            
            for dim in dimensions_to_test:
                try:
                    test_vector = generate_random_vector(dim)
                    
                    request = SearchRequest(
                        collection_name=collection,
                        query_vectors=[test_vector],
                        index_type=IndexType.AUTOINDEX,
                        metric_type=MetricType.L2,
                        limit=1
                    )
                    
                    result = self.service.search(request)
                    
                    self.working_dimension = dim
                    self.working_collections.append(collection)
                    
                    logger.info(f"Found working configuration: {collection} with dimension {dim}")
                    return collection, dim
                    
                except Exception as e:
                    if "dimension" in str(e).lower():
                        continue
                    logger.debug(f"Error with {collection} dim {dim}: {e}")
                    continue
        
        raise MilvusConnectionError("Could not find working configuration")
    
    def generate_algorithm_configurations(self) -> List[AlgorithmConfiguration]:
        """Generate all algorithm configurations to test"""
        configurations = []
        
        # FLAT Index configurations
        for metric in [MetricType.L2, MetricType.IP, MetricType.COSINE]:
            configurations.append(AlgorithmConfiguration(
                name=f"FLAT+{metric.value}",
                index_type=IndexType.FLAT,
                metric_type=metric,
                description=f"Exact search with {metric.value} metric"
            ))
        
        # IVF_FLAT configurations
        for metric in [MetricType.L2, MetricType.IP, MetricType.COSINE]:
            for nprobe in [1, 16, 64]:
                configurations.append(AlgorithmConfiguration(
                    name=f"IVF_FLAT+{metric.value}+nprobe{nprobe}",
                    index_type=IndexType.IVF_FLAT,
                    metric_type=metric,
                    search_params=SearchParams(nprobe=nprobe),
                    description=f"IVF_FLAT with {metric.value} metric, nprobe={nprobe}"
                ))
        
        # IVF_SQ8 configurations
        for metric in [MetricType.L2, MetricType.IP]:  # COSINE often not supported
            for nprobe in [1, 16, 64]:
                configurations.append(AlgorithmConfiguration(
                    name=f"IVF_SQ8+{metric.value}+nprobe{nprobe}",
                    index_type=IndexType.IVF_SQ8,
                    metric_type=metric,
                    search_params=SearchParams(nprobe=nprobe),
                    description=f"IVF_SQ8 with {metric.value} metric, nprobe={nprobe}"
                ))
        
        # IVF_PQ configurations
        for metric in [MetricType.L2, MetricType.IP]:
            for nprobe in [1, 16, 64]:
                configurations.append(AlgorithmConfiguration(
                    name=f"IVF_PQ+{metric.value}+nprobe{nprobe}",
                    index_type=IndexType.IVF_PQ,
                    metric_type=metric,
                    search_params=SearchParams(nprobe=nprobe),
                    description=f"IVF_PQ with {metric.value} metric, nprobe={nprobe}"
                ))
        
        # HNSW configurations
        for metric in [MetricType.L2, MetricType.IP, MetricType.COSINE]:
            for ef in [16, 64, 200]:
                configurations.append(AlgorithmConfiguration(
                    name=f"HNSW+{metric.value}+ef{ef}",
                    index_type=IndexType.HNSW,
                    metric_type=metric,
                    search_params=SearchParams(ef=ef),
                    description=f"HNSW with {metric.value} metric, ef={ef}"
                ))
        
        # SCANN configurations
        for metric in [MetricType.L2, MetricType.IP, MetricType.COSINE]:
            for search_k in [20, 50, 100]:
                configurations.append(AlgorithmConfiguration(
                    name=f"SCANN+{metric.value}+searchk{search_k}",
                    index_type=IndexType.SCANN,
                    metric_type=metric,
                    search_params=SearchParams(search_k=search_k, nprobe=16),
                    description=f"SCANN with {metric.value} metric, search_k={search_k}"
                ))
        
        # AUTOINDEX configurations
        for metric in [MetricType.L2, MetricType.IP, MetricType.COSINE]:
            configurations.append(AlgorithmConfiguration(
                name=f"AUTOINDEX+{metric.value}",
                index_type=IndexType.AUTOINDEX,
                metric_type=metric,
                description=f"Auto-selected index with {metric.value} metric"
            ))
        
        logger.info(f"Generated {len(configurations)} algorithm configurations")
        return configurations
    
    def test_single_algorithm(self, config: AlgorithmConfiguration, 
                            collection_name: str, dimension: int) -> TestResult:
        """Test a single algorithm configuration"""
        try:
            # Generate test vector
            test_vector = generate_random_vector(dimension)
            
            # Create search request
            request = SearchRequest(
                collection_name=collection_name,
                query_vectors=[test_vector],
                index_type=config.index_type,
                metric_type=config.metric_type,
                search_params=config.search_params,
                limit=5
            )
            
            # Execute search with timing
            start_time = time.time()
            result = self.service.search(request)
            total_time = time.time() - start_time
            
            return TestResult(
                configuration=config,
                status="✅ SUCCESS",
                search_time=result.search_time,
                total_time=total_time,
                results_found=result.total_results,
                algorithm_used=result.algorithm_used,
                parameters_used=result.parameters_used
            )
            
        except Exception as e:
            error_type = self._classify_error(str(e))
            
            return TestResult(
                configuration=config,
                status="❌ FAILED",
                error=str(e),
                error_type=error_type
            )
    
    def _classify_error(self, error_msg: str) -> str:
        """Classify error type based on error message"""
        error_msg_lower = error_msg.lower()
        
        if "not supported" in error_msg_lower:
            return "NOT_SUPPORTED"
        elif "dimension" in error_msg_lower:
            return "DIMENSION_MISMATCH"
        elif "index" in error_msg_lower:
            return "INDEX_ERROR"
        elif "metric" in error_msg_lower:
            return "METRIC_ERROR"
        elif "timeout" in error_msg_lower:
            return "TIMEOUT"
        else:
            return "UNKNOWN"
    
    def run_comprehensive_test(self, collections: Optional[List[str]] = None,
                             max_workers: int = 5) -> Dict[str, Any]:
        """
        Run comprehensive test of all algorithms
        
        Args:
            collections: List of collections to test (optional)
            max_workers: Maximum number of parallel tests
            
        Returns:
            Dictionary with test results and analysis
        """
        logger.info("Starting comprehensive algorithm test")
        
        # Auto-detect working configuration
        try:
            collection_name, dimension = self.detect_working_configuration(collections)
        except Exception as e:
            return {"error": f"Could not detect working configuration: {e}"}
        
        # Generate algorithm configurations
        configs = self.generate_algorithm_configurations()
        
        logger.info(f"Testing {len(configs)} algorithm configurations")
        
        # Run tests
        results = {}
        successful_tests = 0
        failed_tests = 0
        
        # Use ThreadPoolExecutor for parallel testing
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all test tasks
            future_to_config = {
                executor.submit(self.test_single_algorithm, config, collection_name, dimension): config
                for config in configs
            }
            
            # Collect results as they complete
            for i, future in enumerate(as_completed(future_to_config), 1):
                config = future_to_config[future]
                
                try:
                    result = future.result(timeout=30)  # 30 second timeout per test
                    results[config.name] = result
                    
                    if result.is_successful:
                        successful_tests += 1
                        logger.info(f"[{i:2d}/{len(configs)}] {config.name}: SUCCESS ({result.search_time:.4f}s)")
                    else:
                        failed_tests += 1
                        logger.warning(f"[{i:2d}/{len(configs)}] {config.name}: FAILED ({result.error_type})")
                        
                except Exception as e:
                    failed_tests += 1
                    logger.error(f"[{i:2d}/{len(configs)}] {config.name}: EXCEPTION ({e})")
                    
                    # Create error result
                    results[config.name] = TestResult(
                        configuration=config,
                        status="❌ EXCEPTION",
                        error=str(e),
                        error_type="EXCEPTION"
                    )
        
        # Generate analysis
        analysis = self._analyze_results(results, successful_tests, failed_tests)
        
        return {
            "summary": analysis,
            "results": {name: result.to_dict() for name, result in results.items()},
            "test_config": {
                "collection": collection_name,
                "dimension": dimension,
                "total_tests": len(configs),
                "timestamp": datetime.now().isoformat()
            }
        }
    
    def _analyze_results(self, results: Dict[str, TestResult], 
                        successful: int, failed: int) -> Dict[str, Any]:
        """Analyze test results and generate summary"""
        total_tests = successful + failed
        success_rate = (successful / total_tests) * 100 if total_tests > 0 else 0
        
        # Analyze by index type
        index_analysis = {}
        metric_analysis = {}
        speed_analysis = []
        error_analysis = {}
        
        for name, result in results.items():
            index_type = result.configuration.index_type.value
            metric_type = result.configuration.metric_type.value
            
            # Index type analysis
            if index_type not in index_analysis:
                index_analysis[index_type] = {"success": 0, "total": 0, "times": []}
            
            index_analysis[index_type]["total"] += 1
            
            if result.is_successful:
                index_analysis[index_type]["success"] += 1
                index_analysis[index_type]["times"].append(result.search_time)
                speed_analysis.append((name, result.search_time))
                
                # Metric type analysis
                if metric_type not in metric_analysis:
                    metric_analysis[metric_type] = {"success": 0, "total": 0}
                metric_analysis[metric_type]["success"] += 1
            else:
                # Error analysis
                error_type = result.error_type or "UNKNOWN"
                if error_type not in error_analysis:
                    error_analysis[error_type] = 0
                error_analysis[error_type] += 1
            
            # Count metric totals
            if metric_type not in metric_analysis:
                metric_analysis[metric_type] = {"success": 0, "total": 0}
            metric_analysis[metric_type]["total"] += 1
        
        # Calculate averages for index types
        for index_type, data in index_analysis.items():
            if data["times"]:
                data["avg_time"] = sum(data["times"]) / len(data["times"])
                data["success_rate"] = (data["success"] / data["total"]) * 100
            else:
                data["avg_time"] = 0.0
                data["success_rate"] = 0.0
        
        # Sort speed analysis
        speed_analysis.sort(key=lambda x: x[1])
        
        return {
            "total_tests": total_tests,
            "successful": successful,
            "failed": failed,
            "success_rate": success_rate,
            "index_analysis": index_analysis,
            "metric_analysis": metric_analysis,
            "fastest_algorithms": speed_analysis[:10],
            "error_analysis": error_analysis,
            "recommendations": self._generate_recommendations(index_analysis, speed_analysis)
        }
    
    def _generate_recommendations(self, index_analysis: Dict[str, Any], 
                                speed_analysis: List[Tuple[str, float]]) -> Dict[str, Any]:
        """Generate recommendations based on test results"""
        recommendations = {
            "fastest_algorithm": None,
            "most_reliable_algorithm": None,
            "best_overall": None,
            "production_ready": []
        }
        
        if speed_analysis:
            recommendations["fastest_algorithm"] = speed_analysis[0][0]
        
        # Find most reliable (highest success rate)
        best_reliability = 0
        for index_type, data in index_analysis.items():
            if data["success_rate"] > best_reliability:
                best_reliability = data["success_rate"]
                recommendations["most_reliable_algorithm"] = index_type
        
        # Find production ready algorithms (good balance of speed and reliability)
        for index_type, data in index_analysis.items():
            if data["success_rate"] >= 80 and data["avg_time"] > 0:
                recommendations["production_ready"].append({
                    "algorithm": index_type,
                    "success_rate": data["success_rate"],
                    "avg_time": data["avg_time"]
                })
        
        # Sort production ready by performance score
        recommendations["production_ready"].sort(
            key=lambda x: x["success_rate"] / (x["avg_time"] * 1000 + 1)
        )
        
        if recommendations["production_ready"]:
            recommendations["best_overall"] = recommendations["production_ready"][0]["algorithm"]
        
        return recommendations
    
    def save_results(self, results: Dict[str, Any], filename: Optional[str] = None):
        """Save test results to JSON file"""
        if filename is None:
            timestamp = int(time.time())
            filename = f"milvus_algorithm_test_results_{timestamp}.json"
        
        try:
            with open(filename, 'w') as f:
                json.dump(results, f, indent=2, default=str)
            
            logger.info(f"Results saved to: {filename}")
            return filename
            
        except Exception as e:
            logger.error(f"Could not save results: {e}")
            raise
