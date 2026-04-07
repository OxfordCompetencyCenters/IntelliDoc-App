"""
Django settings configuration for Milvus Search

Add this to your Django settings.py file:
"""

# Milvus Configuration
MILVUS_CONFIG = {
    'host': 'localhost',
    'port': '19530',
    'max_connections': 8,
    'timeout': 60.0,
    'user': None,  # Optional
    'password': None,  # Optional
    'secure': False,  # Set to True for TLS connections
}

# Logging configuration for Milvus operations
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'milvus_file': {
            'level': 'INFO',
            'class': 'logging.FileHandler',
            'filename': 'milvus_search.log',
            'formatter': 'verbose',
        },
        'console': {
            'level': 'DEBUG',
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
        },
    },
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {message}',
            'style': '{',
        },
    },
    'loggers': {
        'django_milvus_search': {
            'handlers': ['milvus_file', 'console'],
            'level': 'INFO',
            'propagate': True,
        },
    },
}

# Cache configuration (optional, for performance optimization)
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.redis.RedisCache',
        'LOCATION': 'redis://127.0.0.1:6379/1',
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
        },
        'KEY_PREFIX': 'milvus_search',
        'TIMEOUT': 300,  # 5 minutes
    }
}
