# templates/cache.py
import time
import threading
import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone
from threading import Lock
import logging

logger = logging.getLogger(__name__)

class TemplateDiscoveryCache:
    """Intelligent template caching system with multi-level optimization"""
    
    # Cache configuration
    CACHE_KEY_PREFIX = 'template_discovery_'
    CACHE_TIMEOUT = 3600  # 1 hour
    FILESYSTEM_CHECK_INTERVAL = 60  # Check every minute
    BACKGROUND_UPDATE_INTERVAL = 300  # Update every 5 minutes
    
    # Performance thresholds
    MAX_RESPONSE_TIME_MS = 200  # Target response time
    MAX_MEMORY_USAGE_MB = 50    # Max memory usage for cache
    
    # Class-level cache and locks
    _memory_cache: Dict = {}
    _cache_lock = Lock()
    _last_filesystem_check = 0
    _background_updater = None
    _cache_statistics = {
        'hits': 0,
        'misses': 0,
        'filesystem_checks': 0,
        'cache_refreshes': 0,
        'average_response_time': 0
    }
    
    @classmethod
    def get_cached_templates(cls, force_refresh=False) -> Dict:
        """Get templates with intelligent caching and performance optimization"""
        start_time = time.time()
        
        try:
            # CRITICAL FIX: Return memory cache immediately if available and not forcing refresh
            # This prevents unnecessary filesystem checks during startup
            if cls._memory_cache and not force_refresh:
                cls._cache_statistics['hits'] += 1
                response_time = (time.time() - start_time) * 1000
                cls._update_average_response_time(response_time)
                return cls._memory_cache.copy()
            
            current_time = time.time()
            
            # Check if refresh needed (only if cache is empty or forced)
            if (force_refresh or 
                not cls._memory_cache or
                current_time - cls._last_filesystem_check > cls.FILESYSTEM_CHECK_INTERVAL):
                
                return cls._refresh_cache_if_needed()
            
            # Return memory cache if available
            if cls._memory_cache:
                cls._cache_statistics['hits'] += 1
                response_time = (time.time() - start_time) * 1000
                cls._update_average_response_time(response_time)
                return cls._memory_cache.copy()
            
            # Cache miss - refresh cache
            cls._cache_statistics['misses'] += 1
            return cls._refresh_cache_if_needed()
            
        except Exception as e:
            logger.error(f"Error in template cache: {str(e)}")
            # Fallback to direct filesystem scan
            from .discovery import TemplateDiscoverySystem
            return TemplateDiscoverySystem.discover_templates(force_refresh=True)
    
    @classmethod
    def _refresh_cache_if_needed(cls) -> Dict:
        """Refresh cache only if directory changed"""
        with cls._cache_lock:
            try:
                from .discovery import TemplateDiscoverySystem
                
                # Calculate directory hash for change detection
                template_dir = TemplateDiscoverySystem.get_template_definitions_path()
                if not template_dir.exists():
                    return {}
                
                current_hash = cls._calculate_directory_hash(template_dir)
                cached_hash = cache.get(f'{cls.CACHE_KEY_PREFIX}directory_hash')
                
                # Only refresh if directory changed
                if cached_hash != current_hash:
                    logger.info("Template directory changed, refreshing cache")
                    
                    # Scan filesystem
                    discovered_templates = TemplateDiscoverySystem._scan_template_directories(template_dir)
                    
                    # Update all cache levels
                    cls._memory_cache = discovered_templates
                    cache.set(f'{cls.CACHE_KEY_PREFIX}templates', discovered_templates, cls.CACHE_TIMEOUT)
                    cache.set(f'{cls.CACHE_KEY_PREFIX}directory_hash', current_hash, cls.CACHE_TIMEOUT)
                    
                    cls._cache_statistics['cache_refreshes'] += 1
                    cls._last_filesystem_check = time.time()
                    
                    logger.info(f"Cache refreshed with {len(discovered_templates)} templates")
                    return discovered_templates
                else:
                    # Directory unchanged, use cached data
                    if not cls._memory_cache:
                        # Memory cache empty, try Django cache
                        cached_templates = cache.get(f'{cls.CACHE_KEY_PREFIX}templates')
                        if cached_templates:
                            cls._memory_cache = cached_templates
                        else:
                            # Both caches empty, force refresh
                            discovered_templates = TemplateDiscoverySystem._scan_template_directories(template_dir)
                            cls._memory_cache = discovered_templates
                            cache.set(f'{cls.CACHE_KEY_PREFIX}templates', discovered_templates, cls.CACHE_TIMEOUT)
                    
                    cls._last_filesystem_check = time.time()
                    return cls._memory_cache.copy()
                    
            except Exception as e:
                logger.error(f"Error refreshing template cache: {str(e)}")
                return {}
    
    @classmethod
    def _calculate_directory_hash(cls, directory: Path) -> str:
        """Fast directory hash calculation with optimization - stable for Docker volumes"""
        import hashlib
        import os
        
        hash_md5 = hashlib.md5()
        
        try:
            # CRITICAL FIX: Use file content hash instead of modification time
            # Docker volumes can have inconsistent mtime, causing false cache refreshes
            # Only hash file names and sizes (not mtime) for stability
            for root, dirs, files in os.walk(directory):
                dirs.sort()
                files.sort()
                
                # Only hash essential files for performance
                for filename in files:
                    if filename.endswith(('.json', '.py')):
                        filepath = Path(root) / filename
                        try:
                            file_stat = filepath.stat()
                            # Hash: relative path + file size (NOT mtime for Docker stability)
                            relative_path = str(filepath.relative_to(directory))
                            hash_md5.update(relative_path.encode())
                            hash_md5.update(str(file_stat.st_size).encode())
                        except (OSError, FileNotFoundError):
                            # File might have been deleted, skip it
                            continue
            
            return hash_md5.hexdigest()
            
        except Exception as e:
            logger.error(f"Error calculating directory hash: {str(e)}")
            # Return stable hash based on directory path only
            return hashlib.md5(str(directory).encode()).hexdigest()
    
    @classmethod
    def _update_average_response_time(cls, response_time: float):
        """Update average response time statistics"""
        current_avg = cls._cache_statistics['average_response_time']
        total_requests = cls._cache_statistics['hits'] + cls._cache_statistics['misses']
        
        if total_requests > 0:
            cls._cache_statistics['average_response_time'] = (
                (current_avg * (total_requests - 1) + response_time) / total_requests
            )
    
    @classmethod
    def get_cache_statistics(cls) -> Dict:
        """Get cache performance statistics"""
        total_requests = cls._cache_statistics['hits'] + cls._cache_statistics['misses']
        hit_rate = (cls._cache_statistics['hits'] / total_requests * 100) if total_requests > 0 else 0
        
        return {
            'hits': cls._cache_statistics['hits'],
            'misses': cls._cache_statistics['misses'],
            'hit_rate_percent': round(hit_rate, 2),
            'filesystem_checks': cls._cache_statistics['filesystem_checks'],
            'cache_refreshes': cls._cache_statistics['cache_refreshes'],
            'average_response_time_ms': round(cls._cache_statistics['average_response_time'], 2),
            'memory_cache_size': len(cls._memory_cache),
            'last_check': cls._last_filesystem_check,
            'background_updater_active': cls._background_updater is not None and cls._background_updater.is_alive()
        }
    
    @classmethod
    def clear_cache(cls):
        """Clear all cache levels"""
        with cls._cache_lock:
            cls._memory_cache.clear()
            cache.delete(f'{cls.CACHE_KEY_PREFIX}templates')
            cache.delete(f'{cls.CACHE_KEY_PREFIX}directory_hash')
            logger.info("Template cache cleared")
    
    @classmethod
    def preload_cache(cls):
        """Preload cache for improved performance"""
        logger.info("Preloading template cache")
        cls.get_cached_templates(force_refresh=True)
    
    @classmethod
    def start_background_updater(cls):
        """Start background cache updater"""
        if cls._background_updater and cls._background_updater.is_alive():
            logger.info("Background updater already running")
            return
        
        cls._background_updater = threading.Thread(
            target=cls._background_update_loop,
            daemon=True,
            name="TemplateCache-BackgroundUpdater"
        )
        cls._background_updater.start()
        logger.info("Background cache updater started")
    
    @classmethod
    def stop_background_updater(cls):
        """Stop background cache updater"""
        if cls._background_updater:
            cls._background_updater = None
            logger.info("Background cache updater stopped")
    
    @classmethod
    def _background_update_loop(cls):
        """Background cache update loop"""
        while cls._background_updater:
            try:
                time.sleep(cls.BACKGROUND_UPDATE_INTERVAL)
                
                # Check if cache needs refresh
                current_time = time.time()
                if current_time - cls._last_filesystem_check > cls.FILESYSTEM_CHECK_INTERVAL:
                    cls._refresh_cache_if_needed()
                
                # Health check
                cls._perform_health_check()
                
            except Exception as e:
                logger.error(f"Error in background cache updater: {str(e)}")
                time.sleep(60)  # Wait before retrying
    
    @classmethod
    def _perform_health_check(cls):
        """Perform cache health check"""
        stats = cls.get_cache_statistics()
        
        # Check response time
        if stats['average_response_time_ms'] > cls.MAX_RESPONSE_TIME_MS:
            logger.warning(f"Cache response time ({stats['average_response_time_ms']}ms) exceeds threshold ({cls.MAX_RESPONSE_TIME_MS}ms)")
        
        # Check hit rate
        if stats['hit_rate_percent'] < 90:
            logger.warning(f"Cache hit rate ({stats['hit_rate_percent']}%) below optimal threshold (90%)")
        
        # Log statistics periodically
        if stats['hits'] + stats['misses'] > 0 and (stats['hits'] + stats['misses']) % 100 == 0:
            logger.info(f"Cache statistics: {stats}")


class TemplateConfigurationCache:
    """Specialized cache for individual template configurations"""
    
    CACHE_KEY_PREFIX = 'template_config_'
    CACHE_TIMEOUT = 1800  # 30 minutes
    
    @classmethod
    def get_template_configuration(cls, template_id: str) -> Optional[Dict]:
        """Get cached template configuration"""
        cache_key = f'{cls.CACHE_KEY_PREFIX}{template_id}'
        
        # Try cache first
        cached_config = cache.get(cache_key)
        if cached_config:
            return cached_config
        
        # Cache miss - load from filesystem
        from .discovery import TemplateDiscoverySystem
        config = TemplateDiscoverySystem.get_template_configuration(template_id)
        
        if config:
            # Cache the configuration
            cache.set(cache_key, config, cls.CACHE_TIMEOUT)
        
        return config
    
    @classmethod
    def clear_configuration_cache(cls, template_id: str = None):
        """Clear configuration cache for specific template or all templates"""
        if template_id:
            cache_key = f'{cls.CACHE_KEY_PREFIX}{template_id}'
            cache.delete(cache_key)
        else:
            # Clear all template configuration caches
            # This is a simplified approach - in production, consider using cache versioning
            templates = TemplateDiscoveryCache.get_cached_templates()
            for tid in templates.keys():
                cache_key = f'{cls.CACHE_KEY_PREFIX}{tid}'
                cache.delete(cache_key)


class CacheWarmup:
    """Cache warmup utilities for improved performance"""
    
    @classmethod
    def warmup_template_cache(cls):
        """Warmup template discovery cache"""
        logger.info("Starting template cache warmup")
        
        # Preload template discovery cache
        TemplateDiscoveryCache.preload_cache()
        
        # Preload individual template configurations
        templates = TemplateDiscoveryCache.get_cached_templates()
        for template_id in templates.keys():
            TemplateConfigurationCache.get_template_configuration(template_id)
        
        logger.info(f"Cache warmup completed for {len(templates)} templates")
    
    @classmethod
    def warmup_on_startup(cls):
        """Warmup cache on application startup"""
        import threading
        from django.conf import settings
        
        # Run warmup in background to avoid blocking startup
        warmup_thread = threading.Thread(
            target=cls.warmup_template_cache,
            daemon=True,
            name="CacheWarmup"
        )
        warmup_thread.start()
        
        # CRITICAL FIX: Only start background updater in production
        # In development, Django's StatReloader already watches for changes
        # Starting background updater causes unnecessary overhead
        if not getattr(settings, 'DEBUG', True):
            TemplateDiscoveryCache.start_background_updater()
