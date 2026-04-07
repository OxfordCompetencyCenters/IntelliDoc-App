"""
Django Milvus Search Package

A comprehensive, highly maintainable Milvus search integration for Django applications.
"""

__version__ = "1.0.0"
__author__ = "AI Catalogue Team"

from .models import *
from .services import MilvusSearchService
from .exceptions import *
from .utils import *

__all__ = [
    'MilvusSearchService',
    'ConnectionConfig',
    'SearchRequest',
    'SearchResult', 
    'IndexType',
    'MetricType',
    'SearchParams',
    'MilvusConnectionError',
    'MilvusSearchError',
    'MilvusConfigurationError',
    'AlgorithmTester',
]
