"""
Custom exceptions for Milvus search operations
"""


class MilvusSearchBaseException(Exception):
    """Base exception for all Milvus search related errors"""
    
    def __init__(self, message: str, details: dict = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}


class MilvusConnectionError(MilvusSearchBaseException):
    """Raised when connection to Milvus fails"""
    pass


class MilvusSearchError(MilvusSearchBaseException):
    """Raised when search operation fails"""
    pass


class MilvusConfigurationError(MilvusSearchBaseException):
    """Raised when configuration is invalid"""
    pass


class MilvusCollectionError(MilvusSearchBaseException):
    """Raised when collection operations fail"""
    pass


class MilvusIndexError(MilvusSearchBaseException):
    """Raised when index operations fail"""
    pass


class MilvusValidationError(MilvusSearchBaseException):
    """Raised when data validation fails"""
    pass
