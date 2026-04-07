"""
Django models and data structures for Milvus search operations
"""
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Union
from enum import Enum
import json
from datetime import datetime


class IndexType(str, Enum):
    """Supported Milvus index types"""
    FLAT = "FLAT"
    IVF_FLAT = "IVF_FLAT"
    IVF_SQ8 = "IVF_SQ8"
    IVF_PQ = "IVF_PQ"
    HNSW = "HNSW"
    SCANN = "SCANN"
    AUTOINDEX = "AUTOINDEX"


class MetricType(str, Enum):
    """Supported Milvus metric types"""
    L2 = "L2"
    IP = "IP"
    COSINE = "COSINE"


@dataclass
class ConnectionConfig:
    """Milvus connection configuration"""
    host: str = "localhost"
    port: str = "19530"
    max_connections: int = 8
    timeout: float = 60.0
    user: Optional[str] = None
    password: Optional[str] = None
    secure: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for connection"""
        config = {
            "host": self.host,
            "port": self.port,
        }
        if self.user:
            config["user"] = self.user
        if self.password:
            config["password"] = self.password
        if self.secure:
            config["secure"] = self.secure
        return config


@dataclass
class SearchParams:
    """Search parameters for different index types"""
    nprobe: Optional[int] = None
    ef: Optional[int] = None
    search_k: Optional[int] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary, excluding None values"""
        return {k: v for k, v in self.__dict__.items() if v is not None}


@dataclass
class SearchRequest:
    """Search request structure"""
    collection_name: str
    query_vectors: List[List[float]]
    index_type: IndexType = IndexType.AUTOINDEX
    metric_type: MetricType = MetricType.L2
    search_params: Optional[SearchParams] = None
    limit: int = 10
    offset: int = 0
    output_fields: Optional[List[str]] = None
    filter_expression: Optional[str] = None
    
    def __post_init__(self):
        """Validate request after initialization"""
        if not self.query_vectors:
            raise ValueError("query_vectors cannot be empty")
        if self.limit <= 0:
            raise ValueError("limit must be positive")
        if self.offset < 0:
            raise ValueError("offset cannot be negative")


@dataclass
class SearchResult:
    """Search result structure"""
    hits: List[Dict[str, Any]]
    search_time: float
    total_results: int
    algorithm_used: str
    parameters_used: Dict[str, Any]
    collection_name: str
    query_id: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "hits": self.hits,
            "search_time": self.search_time,
            "total_results": self.total_results,
            "algorithm_used": self.algorithm_used,
            "parameters_used": self.parameters_used,
            "collection_name": self.collection_name,
            "query_id": self.query_id,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class AlgorithmConfiguration:
    """Configuration for a specific algorithm test"""
    name: str
    index_type: IndexType
    metric_type: MetricType
    search_params: Optional[SearchParams] = None
    description: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "name": self.name,
            "index_type": self.index_type.value,
            "metric_type": self.metric_type.value,
            "search_params": self.search_params.to_dict() if self.search_params else {},
            "description": self.description,
        }


@dataclass
class TestResult:
    """Result of an algorithm test"""
    configuration: AlgorithmConfiguration
    status: str
    search_time: float = 0.0
    total_time: float = 0.0
    results_found: int = 0
    algorithm_used: str = ""
    parameters_used: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    error_type: Optional[str] = None
    
    @property
    def is_successful(self) -> bool:
        """Check if test was successful"""
        return "SUCCESS" in self.status
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "configuration": self.configuration.to_dict(),
            "status": self.status,
            "search_time": self.search_time,
            "total_time": self.total_time,
            "results_found": self.results_found,
            "algorithm_used": self.algorithm_used,
            "parameters_used": self.parameters_used,
            "error": self.error,
            "error_type": self.error_type,
        }
