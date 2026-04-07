"""
Dynamic Template URL Router - Phase 3
=====================================

Dynamic URL routing system for template-specific endpoints with
automatic route registration and comprehensive logging.
"""

import importlib
import importlib.util
from pathlib import Path
from django.urls import path, include
from django.http import HttpResponse, Http404, JsonResponse
from django.conf import settings
from django.core.cache import cache
import logging

logger = logging.getLogger(__name__)

class DynamicTemplateRouter:
    """Dynamic URL router for template-specific endpoints"""
    
    def __init__(self):
        self.templates_dir = Path(settings.BASE_DIR) / 'templates' / 'template_definitions'
        self.cache_prefix = 'dynamic_template_router_'
        self.cache_timeout = 1800  # 30 minutes
        
        logger.info("Initializing Dynamic Template Router")
        logger.info(f"Templates directory: {self.templates_dir}")
    
    def get_template_urls(self, template_id: str):
        """Get URL patterns for a specific template with caching"""
        cache_key = f"{self.cache_prefix}urls_{template_id}"
        
        # Check cache first
        cached_urls = cache.get(cache_key)
        if cached_urls is not None:
            logger.info(f"Returning cached URLs for template: {template_id}")
            return cached_urls
        
        logger.info(f"Loading URLs for template: {template_id}")
        
        try:
            # Load template URLs dynamically
            urls_module = self._load_template_urls_module(template_id)
            
            if urls_module and hasattr(urls_module, 'urlpatterns'):
                template_urls = urls_module.urlpatterns
                
                # Cache the result
                cache.set(cache_key, template_urls, self.cache_timeout)
                
                logger.info(f"Successfully loaded {len(template_urls)} URL patterns for template: {template_id}")
                return template_urls
            else:
                logger.warning(f"No URL patterns found for template: {template_id}")
                return []
                
        except Exception as e:
            logger.error(f"Error loading URLs for template {template_id}: {str(e)}")
            return []
    
    def _load_template_urls_module(self, template_id: str):
        """Load URLs module for a specific template"""
        urls_file = self.templates_dir / template_id / 'urls.py'
        
        if not urls_file.exists():
            logger.warning(f"URLs file not found for template {template_id}: {urls_file}")
            return None
        
        try:
            # Load module from file
            module_name = f"template_{template_id}_urls"
            spec = importlib.util.spec_from_file_location(module_name, urls_file)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            
            logger.info(f"Successfully loaded URLs module for template: {template_id}")
            return module
            
        except Exception as e:
            logger.error(f"Error loading URLs module for template {template_id}: {str(e)}")
            return None
    
    def get_available_template_routes(self) -> dict:
        """Get all available template routes"""
        logger.info("Discovering all available template routes")
        
        available_routes = {}
        
        if not self.templates_dir.exists():
            logger.warning(f"Templates directory does not exist: {self.templates_dir}")
            return available_routes
        
        for template_dir in self.templates_dir.iterdir():
            if template_dir.is_dir() and not template_dir.name.startswith('.'):
                template_id = template_dir.name
                
                # Check if template has URLs
                urls_file = template_dir / 'urls.py'
                if urls_file.exists():
                    try:
                        url_patterns = self.get_template_urls(template_id)
                        route_info = self._analyze_url_patterns(url_patterns)
                        
                        available_routes[template_id] = {
                            'base_url': f'/api/templates/{template_id}',
                            'has_custom_urls': True,
                            'url_patterns_count': len(url_patterns),
                            'route_analysis': route_info,
                            'urls_file_path': str(urls_file)
                        }
                        
                        logger.info(f"Template {template_id} has {len(url_patterns)} custom URL patterns")
                        
                    except Exception as e:
                        logger.error(f"Error analyzing routes for template {template_id}: {str(e)}")
                        available_routes[template_id] = {
                            'base_url': f'/api/templates/{template_id}',
                            'has_custom_urls': False,
                            'error': str(e)
                        }
                else:
                    available_routes[template_id] = {
                        'base_url': f'/api/templates/{template_id}',
                        'has_custom_urls': False,
                        'note': 'No custom URLs file found'
                    }
        
        logger.info(f"Found routes for {len(available_routes)} templates")
        return available_routes
    
    def _analyze_url_patterns(self, url_patterns: list) -> dict:
        """Analyze URL patterns to extract route information"""
        analysis = {
            'total_patterns': len(url_patterns),
            'pattern_types': {},
            'view_functions': [],
            'route_patterns': []
        }
        
        for pattern in url_patterns:
            try:
                # Extract pattern information
                pattern_str = str(pattern.pattern)
                analysis['route_patterns'].append(pattern_str)
                
                # Classify pattern type
                if hasattr(pattern, 'callback'):
                    if hasattr(pattern.callback, 'view_class'):
                        pattern_type = 'class_based_view'
                        view_name = pattern.callback.view_class.__name__
                    else:
                        pattern_type = 'function_based_view'
                        view_name = pattern.callback.__name__
                    
                    analysis['view_functions'].append(view_name)
                    analysis['pattern_types'][pattern_type] = analysis['pattern_types'].get(pattern_type, 0) + 1
                elif hasattr(pattern, 'url_patterns'):
                    pattern_type = 'include_pattern'
                    analysis['pattern_types'][pattern_type] = analysis['pattern_types'].get(pattern_type, 0) + 1
                else:
                    pattern_type = 'unknown'
                    analysis['pattern_types'][pattern_type] = analysis['pattern_types'].get(pattern_type, 0) + 1
                    
            except Exception as e:
                logger.warning(f"Error analyzing URL pattern: {str(e)}")
                continue
        
        return analysis
    
    def clear_template_cache(self, template_id: str = None):
        """Clear URL cache for specific template or all templates"""
        if template_id:
            cache_key = f"{self.cache_prefix}urls_{template_id}"
            cache.delete(cache_key)
            logger.info(f"Cleared URL cache for template: {template_id}")
        else:
            # Clear all template URL caches
            # This is a simplified approach - in production you might want to track cache keys
            cache.clear()
            logger.info("Cleared all template URL caches")


def include_template_urls(template_id: str):
    """Dynamic URL include function for template-specific routes"""
    router = DynamicTemplateRouter()
    
    try:
        template_urls = router.get_template_urls(template_id)
        
        if template_urls:
            logger.info(f"Including {len(template_urls)} URL patterns for template: {template_id}")
            return template_urls
        else:
            logger.warning(f"No URL patterns found for template: {template_id}")
            # Return empty patterns to avoid 404
            return []
            
    except Exception as e:
        logger.error(f"Error including URLs for template {template_id}: {str(e)}")
        return []


def dynamic_template_url_handler(request, template_id, path=''):
    """Handle dynamic template URL routing"""
    logger.info(f"Dynamic URL handler called for template: {template_id}, path: {path}")
    
    router = DynamicTemplateRouter()
    
    try:
        # Get template URLs
        template_urls = router.get_template_urls(template_id)
        
        if not template_urls:
            logger.warning(f"No URL patterns found for template: {template_id}")
            raise Http404(f"Template {template_id} not found or has no URL patterns")
        
        # Try to match the path against template URL patterns
        from django.urls import resolve
        from django.urls.resolvers import URLResolver
        
        # Create a temporary resolver for this template
        resolver = URLResolver(r'^', template_urls)
        
        try:
            match = resolver.resolve(path)
            if match:
                logger.info(f"Successfully resolved path {path} for template {template_id}")
                return match.func(request, *match.args, **match.kwargs)
        except Exception as resolve_error:
            logger.warning(f"Could not resolve path {path} for template {template_id}: {str(resolve_error)}")
        
        # If we get here, the path wasn't found
        raise Http404(f"Path {path} not found in template {template_id}")
        
    except Http404:
        raise
    except Exception as e:
        logger.error(f"Error in dynamic URL handler for template {template_id}: {str(e)}")
        return HttpResponse(f"Error processing template {template_id}: {str(e)}", status=500)


class TemplateRouteRegistry:
    """Registry for tracking template routes and their status"""
    
    def __init__(self):
        self.router = DynamicTemplateRouter()
        self.registry_cache_key = 'template_route_registry'
        self.cache_timeout = 3600  # 1 hour
        
        logger.info("Initializing Template Route Registry")
    
    def register_template_routes(self, template_id: str) -> dict:
        """Register routes for a specific template"""
        logger.info(f"Registering routes for template: {template_id}")
        
        try:
            # Get available routes
            available_routes = self.router.get_available_template_routes()
            template_routes = available_routes.get(template_id)
            
            if not template_routes:
                raise Exception(f"No routes found for template {template_id}")
            
            # Update registry
            registry = self._get_registry()
            registry[template_id] = {
                **template_routes,
                'registration_status': 'registered',
                'registration_timestamp': self._get_current_timestamp(),
                'last_accessed': None,
                'access_count': 0
            }
            
            self._save_registry(registry)
            
            logger.info(f"Successfully registered routes for template: {template_id}")
            return registry[template_id]
            
        except Exception as e:
            logger.error(f"Error registering routes for template {template_id}: {str(e)}")
            raise
    
    def unregister_template_routes(self, template_id: str):
        """Unregister routes for a specific template"""
        logger.info(f"Unregistering routes for template: {template_id}")
        
        try:
            registry = self._get_registry()
            
            if template_id in registry:
                del registry[template_id]
                self._save_registry(registry)
                
                # Clear template cache
                self.router.clear_template_cache(template_id)
                
                logger.info(f"Successfully unregistered routes for template: {template_id}")
            else:
                logger.warning(f"Template {template_id} not found in registry")
                
        except Exception as e:
            logger.error(f"Error unregistering routes for template {template_id}: {str(e)}")
            raise
    
    def get_registered_templates(self) -> dict:
        """Get all registered templates"""
        registry = self._get_registry()
        logger.info(f"Retrieved {len(registry)} registered templates")
        return registry
    
    def update_template_access(self, template_id: str):
        """Update access statistics for a template"""
        try:
            registry = self._get_registry()
            
            if template_id in registry:
                registry[template_id]['last_accessed'] = self._get_current_timestamp()
                registry[template_id]['access_count'] = registry[template_id].get('access_count', 0) + 1
                
                self._save_registry(registry)
                logger.info(f"Updated access statistics for template: {template_id}")
            
        except Exception as e:
            logger.warning(f"Error updating access statistics for template {template_id}: {str(e)}")
    
    def get_template_statistics(self) -> dict:
        """Get statistics about template route usage"""
        registry = self._get_registry()
        
        statistics = {
            'total_registered_templates': len(registry),
            'templates_with_custom_urls': len([t for t in registry.values() if t.get('has_custom_urls', False)]),
            'total_url_patterns': sum(t.get('url_patterns_count', 0) for t in registry.values()),
            'most_accessed_template': None,
            'least_accessed_template': None,
            'templates_by_access_count': {}
        }
        
        # Find most and least accessed templates
        access_counts = [(tid, t.get('access_count', 0)) for tid, t in registry.items()]
        
        if access_counts:
            access_counts.sort(key=lambda x: x[1])
            statistics['least_accessed_template'] = access_counts[0]
            statistics['most_accessed_template'] = access_counts[-1]
            
            # Group by access count
            for template_id, access_count in access_counts:
                if access_count not in statistics['templates_by_access_count']:
                    statistics['templates_by_access_count'][access_count] = []
                statistics['templates_by_access_count'][access_count].append(template_id)
        
        return statistics
    
    def _get_registry(self) -> dict:
        """Get registry from cache or create new one"""
        registry = cache.get(self.registry_cache_key)
        if registry is None:
            registry = {}
            logger.info("Created new template route registry")
        return registry
    
    def _save_registry(self, registry: dict):
        """Save registry to cache"""
        cache.set(self.registry_cache_key, registry, self.cache_timeout)
        logger.info(f"Saved template route registry with {len(registry)} templates")
    
    def _get_current_timestamp(self) -> str:
        """Get current timestamp in ISO format"""
        from datetime import datetime
        return datetime.now().isoformat()


# Global registry instance
template_route_registry = TemplateRouteRegistry()


def get_template_route_patterns():
    """Generate URL patterns for all registered templates"""
    router = DynamicTemplateRouter()
    available_routes = router.get_available_template_routes()
    
    patterns = []
    
    for template_id in available_routes.keys():
        # Create dynamic URL pattern for each template
        pattern = path(
            f'templates/{template_id}/',
            include_template_urls(template_id),
            name=f'template_{template_id}'
        )
        patterns.append(pattern)
        
        logger.info(f"Created URL pattern for template: {template_id}")
    
    logger.info(f"Generated {len(patterns)} template URL patterns")
    return patterns


def refresh_all_template_routes():
    """Refresh all template routes and clear caches"""
    logger.info("Refreshing all template routes")
    
    try:
        router = DynamicTemplateRouter()
        registry = template_route_registry
        
        # Clear all caches
        router.clear_template_cache()
        cache.delete(registry.registry_cache_key)
        
        # Rediscover all routes
        available_routes = router.get_available_template_routes()
        
        # Re-register all templates
        for template_id in available_routes.keys():
            try:
                registry.register_template_routes(template_id)
                logger.info(f"Re-registered routes for template: {template_id}")
            except Exception as e:
                logger.error(f"Error re-registering template {template_id}: {str(e)}")
                continue
        
        logger.info(f"Successfully refreshed routes for {len(available_routes)} templates")
        return True
        
    except Exception as e:
        logger.error(f"Error refreshing template routes: {str(e)}")
        return False


class TemplateURLManagementView:
    """Template URL Management API View"""
    
    @staticmethod
    def discover_templates(request):
        """Discover all available templates and their routes"""
        logger.info("Template discovery API called")
        
        try:
            router = DynamicTemplateRouter()
            available_routes = router.get_available_template_routes()
            
            # Get registry statistics
            registry = template_route_registry
            statistics = registry.get_template_statistics()
            
            response_data = {
                'status': 'success',
                'templates': available_routes,
                'statistics': statistics,
                'total_templates': len(available_routes),
                'message': f'Discovered {len(available_routes)} templates'
            }
            
            logger.info(f"Template discovery completed: {len(available_routes)} templates found")
            return JsonResponse(response_data)
            
        except Exception as e:
            logger.error(f"Error in template discovery: {str(e)}")
            return JsonResponse({
                'status': 'error',
                'error': str(e),
                'message': 'Failed to discover templates'
            }, status=500)
    
    @staticmethod
    def get_template_endpoints(request):
        """Get all template-specific endpoints"""
        logger.info("Template endpoints API called")
        
        try:
            router = DynamicTemplateRouter()
            available_routes = router.get_available_template_routes()
            
            endpoints = {}
            
            for template_id, route_info in available_routes.items():
                endpoints[template_id] = {
                    'base_url': route_info.get('base_url'),
                    'has_custom_urls': route_info.get('has_custom_urls', False),
                    'endpoints': []
                }
                
                if route_info.get('route_analysis'):
                    route_patterns = route_info['route_analysis'].get('route_patterns', [])
                    for pattern in route_patterns:
                        full_endpoint = f"{route_info['base_url']}/{pattern}".replace('//', '/')
                        endpoints[template_id]['endpoints'].append(full_endpoint)
            
            response_data = {
                'status': 'success',
                'endpoints': endpoints,
                'total_templates': len(endpoints),
                'message': f'Retrieved endpoints for {len(endpoints)} templates'
            }
            
            logger.info(f"Template endpoints retrieved: {len(endpoints)} templates")
            return JsonResponse(response_data)
            
        except Exception as e:
            logger.error(f"Error retrieving template endpoints: {str(e)}")
            return JsonResponse({
                'status': 'error',
                'error': str(e),
                'message': 'Failed to retrieve template endpoints'
            }, status=500)
    
    @staticmethod
    def refresh_urls(request):
        """Refresh all template URLs and clear caches"""
        logger.info("Template URL refresh API called")
        
        try:
            success = refresh_all_template_routes()
            
            if success:
                # Get updated statistics
                registry = template_route_registry
                statistics = registry.get_template_statistics()
                
                response_data = {
                    'status': 'success',
                    'message': 'Template URLs refreshed successfully',
                    'statistics': statistics,
                    'timestamp': registry._get_current_timestamp()
                }
                
                logger.info("Template URLs refreshed successfully")
                return JsonResponse(response_data)
            else:
                logger.error("Failed to refresh template URLs")
                return JsonResponse({
                    'status': 'error',
                    'message': 'Failed to refresh template URLs'
                }, status=500)
                
        except Exception as e:
            logger.error(f"Error refreshing template URLs: {str(e)}")
            return JsonResponse({
                'status': 'error',
                'error': str(e),
                'message': 'Error occurred while refreshing template URLs'
            }, status=500)
