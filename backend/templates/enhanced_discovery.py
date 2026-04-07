"""
Enhanced Template Discovery & Registration System - Phase 3
===========================================================

Comprehensive template discovery with backend/frontend capability detection,
dynamic routing, and template independence verification.

This system discovers templates with their complete architectural components:
- Backend endpoints and capabilities
- Frontend routes and components  
- Template independence levels
- Full-stack integration status
"""

import os
import json
import importlib
import importlib.util
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from django.conf import settings
from django.urls import URLPattern, URLResolver
from django.core.cache import cache
import logging

logger = logging.getLogger(__name__)

class EnhancedTemplateDiscovery:
    """Enhanced template discovery with comprehensive capability detection"""
    
    def __init__(self):
        self.templates_dir = Path(settings.BASE_DIR) / 'templates' / 'template_definitions'
        self.frontend_dir = self._get_frontend_directory()
        self.cache_prefix = 'enhanced_template_discovery_'
        self.cache_timeout = 3600  # 1 hour
        
        logger.info("Initializing Enhanced Template Discovery System")
        logger.info(f"Templates directory: {self.templates_dir}")
        logger.info(f"Frontend directory: {self.frontend_dir}")
    
    def _get_frontend_directory(self) -> Optional[Path]:
        """Detect frontend directory dynamically"""
        possible_paths = [
            Path(settings.BASE_DIR).parent / 'frontend' / 'my-sveltekit-app' / 'src',
            Path(settings.BASE_DIR).parent / 'frontend' / 'src',
            Path(settings.BASE_DIR) / '..' / 'frontend' / 'my-sveltekit-app' / 'src',
        ]
        
        for path in possible_paths:
            if path.exists() and (path / 'routes').exists():
                logger.info(f"Frontend directory detected: {path}")
                return path
                
        logger.warning("Frontend directory not found - frontend capabilities will be limited")
        return None
    
    def discover_all_templates(self, force_refresh: bool = False) -> Dict[str, Any]:
        """
        Discover all templates with comprehensive capability analysis
        
        Returns:
            Dict containing:
            - templates: Dict of template configurations
            - discovery_metadata: Analysis results
            - architectural_status: Full-stack integration status
        """
        cache_key = f"{self.cache_prefix}complete_discovery"
        
        if not force_refresh:
            cached_result = cache.get(cache_key)
            if cached_result:
                logger.info("Returning cached complete template discovery results")
                return cached_result
        
        logger.info("Starting comprehensive template discovery process")
        
        # Discover backend templates
        backend_templates = self._discover_backend_templates()
        logger.info(f"Found {len(backend_templates)} backend templates")
        
        # Discover frontend capabilities
        frontend_capabilities = self._discover_frontend_capabilities()
        logger.info(f"Found frontend capabilities for {len(frontend_capabilities)} templates")
        
        # Combine and analyze
        enhanced_templates = self._combine_template_data(backend_templates, frontend_capabilities)
        
        # Generate discovery metadata
        discovery_metadata = self._generate_discovery_metadata(enhanced_templates)
        
        # Assess architectural status
        architectural_status = self._assess_architectural_status(enhanced_templates)
        
        result = {
            'templates': enhanced_templates,
            'discovery_metadata': discovery_metadata,
            'architectural_status': architectural_status,
            'timestamp': self._get_current_timestamp(),
            'discovery_version': '3.0.0'
        }
        
        # Cache the result
        cache.set(cache_key, result, self.cache_timeout)
        logger.info("Complete template discovery completed and cached")
        
        return result
    
    def _discover_backend_templates(self) -> Dict[str, Any]:
        """Discover templates with backend capabilities"""
        templates = {}
        
        if not self.templates_dir.exists():
            logger.warning(f"Templates directory does not exist: {self.templates_dir}")
            return templates
        
        for template_dir in self.templates_dir.iterdir():
            if template_dir.is_dir() and not template_dir.name.startswith('.'):
                template_id = template_dir.name
                logger.info(f"Analyzing backend template: {template_id}")
                
                try:
                    template_config = self._analyze_backend_template(template_dir)
                    if template_config:
                        templates[template_id] = template_config
                        logger.info(f"Backend template {template_id} analyzed successfully")
                    else:
                        logger.warning(f"Backend template {template_id} analysis failed")
                except Exception as e:
                    logger.error(f"Error analyzing backend template {template_id}: {str(e)}")
                    continue
        
        return templates
    
    def _analyze_backend_template(self, template_dir: Path) -> Optional[Dict[str, Any]]:
        """Analyze individual backend template with comprehensive capability detection"""
        template_id = template_dir.name
        
        # Load basic configuration
        metadata = self._load_template_metadata(template_dir)
        if not metadata:
            return None
        
        definition_config = self._load_template_definition(template_dir, metadata)
        
        # Discover backend endpoints
        backend_endpoints = self._discover_backend_endpoints(template_dir)
        
        # Analyze backend components
        backend_components = self._analyze_backend_components(template_dir)
        
        # Check independence level
        independence_analysis = self._analyze_template_independence(template_dir)
        
        return {
            'template_id': template_id,
            'metadata': metadata,
            'definition_config': definition_config,
            'backend_capabilities': {
                'endpoints': backend_endpoints,
                'components': backend_components,
                'independence_level': independence_analysis['independence_level'],
                'has_custom_views': len(backend_endpoints.get('custom_views', [])) > 0,
                'has_custom_serializers': backend_components.get('has_serializers', False),
                'has_custom_urls': backend_components.get('has_urls', False),
                'has_custom_services': backend_components.get('has_services', False),
            },
            'independence_analysis': independence_analysis,
            'source_type': 'filesystem',
            'discovery_timestamp': self._get_current_timestamp()
        }
    
    def _discover_backend_endpoints(self, template_dir: Path) -> Dict[str, List[str]]:
        """Discover backend API endpoints for template"""
        endpoints = {
            'custom_views': [],
            'url_patterns': [],
            'api_endpoints': []
        }
        
        # Check for custom views
        views_file = template_dir / 'views.py'
        if views_file.exists():
            try:
                endpoints['custom_views'] = self._extract_view_classes(views_file)
            except Exception as e:
                logger.error(f"Error extracting views from {views_file}: {str(e)}")
        
        # Check for custom URLs
        urls_file = template_dir / 'urls.py'
        if urls_file.exists():
            try:
                endpoints['url_patterns'] = self._extract_url_patterns(urls_file)
                endpoints['api_endpoints'] = self._generate_api_endpoints(template_dir.name, endpoints['url_patterns'])
            except Exception as e:
                logger.error(f"Error extracting URLs from {urls_file}: {str(e)}")
        
        return endpoints
    
    def _analyze_backend_components(self, template_dir: Path) -> Dict[str, Any]:
        """Analyze backend components for completeness"""
        components = {
            'has_views': (template_dir / 'views.py').exists(),
            'has_serializers': (template_dir / 'serializers.py').exists(),
            'has_urls': (template_dir / 'urls.py').exists(),
            'has_services': (template_dir / 'services.py').exists(),
            'has_models': (template_dir / 'models.py').exists(),
            'has_components_dir': (template_dir / 'components').exists(),
            'component_files': []
        }
        
        # Analyze components directory
        components_dir = template_dir / 'components'
        if components_dir.exists():
            components['component_files'] = [
                f.name for f in components_dir.iterdir() 
                if f.is_file() and f.suffix == '.py' and not f.name.startswith('__')
            ]
        
        # Calculate completeness score
        required_components = ['has_views', 'has_serializers', 'has_urls']
        completeness_score = sum(1 for comp in required_components if components[comp]) / len(required_components)
        components['completeness_score'] = completeness_score
        components['architecture_level'] = self._determine_architecture_level(components)
        
        return components
    
    def _discover_frontend_capabilities(self) -> Dict[str, Any]:
        """Discover frontend capabilities for all templates"""
        capabilities = {}
        
        if not self.frontend_dir:
            logger.warning("Frontend directory not available - skipping frontend discovery")
            return capabilities
        
        features_dir = self.frontend_dir / 'routes' / 'features'
        if not features_dir.exists():
            logger.warning(f"Features directory not found: {features_dir}")
            return capabilities
        
        # Check each template directory in features
        for template_dir in features_dir.iterdir():
            if template_dir.is_dir() and not template_dir.name.startswith('.'):
                # Skip universal interface directories
                if template_dir.name in ['intellidoc', 'llm-eval', 'profile']:
                    continue
                    
                template_id = template_dir.name
                logger.info(f"Analyzing frontend capabilities for: {template_id}")
                
                try:
                    frontend_analysis = self._analyze_frontend_template(template_dir, template_id)
                    if frontend_analysis:
                        capabilities[template_id] = frontend_analysis
                        logger.info(f"Frontend analysis completed for {template_id}")
                except Exception as e:
                    logger.error(f"Error analyzing frontend for {template_id}: {str(e)}")
                    continue
        
        return capabilities
    
    def _analyze_frontend_template(self, template_dir: Path, template_id: str) -> Dict[str, Any]:
        """Analyze frontend template capabilities"""
        
        # Discover routes
        frontend_routes = self._discover_frontend_routes(template_dir)
        
        # Check for template-specific components
        template_components = self._discover_template_components(template_id)
        
        # Check for template-specific services
        template_services = self._discover_template_services(template_id)
        
        # Analyze independence level
        independence_analysis = self._analyze_frontend_independence(template_dir, template_id)
        
        return {
            'frontend_capabilities': {
                'routes': frontend_routes,
                'components': template_components,
                'services': template_services,
                'independence_level': independence_analysis['independence_level'],
                'has_selection_page': frontend_routes.get('has_selection_page', False),
                'has_project_interface': frontend_routes.get('has_project_interface', False),
                'has_custom_components': len(template_components.get('component_files', [])) > 0,
                'has_api_services': len(template_services.get('service_files', [])) > 0,
            },
            'independence_analysis': independence_analysis,
            'discovery_timestamp': self._get_current_timestamp()
        }
    
    def _discover_frontend_routes(self, template_dir: Path) -> Dict[str, Any]:
        """Discover frontend routes for template"""
        routes = {
            'has_selection_page': False,
            'has_project_interface': False,
            'route_files': [],
            'route_patterns': []
        }
        
        # Check for selection page
        selection_page = template_dir / '+page.svelte'
        if selection_page.exists():
            routes['has_selection_page'] = True
            routes['route_files'].append('+page.svelte')
        
        # Check for project interface
        project_dir = template_dir / 'project'
        if project_dir.exists():
            routes['has_project_interface'] = True
            routes['route_files'].extend(self._get_route_files(project_dir))
        
        # Generate route patterns
        template_id = template_dir.name
        routes['route_patterns'] = [
            f'/features/{template_id}/',  # Selection page
            f'/features/{template_id}/project/[id]/'  # Project interface (if exists)
        ]
        
        return routes
    
    def _discover_template_components(self, template_id: str) -> Dict[str, Any]:
        """Discover template-specific components"""
        components = {
            'component_files': [],
            'component_types': [],
            'has_components': False
        }
        
        if not self.frontend_dir:
            return components
        
        # Check lib/templates/{template_id}/components/
        components_dir = self.frontend_dir / 'lib' / 'templates' / template_id / 'components'
        if components_dir.exists():
            components['has_components'] = True
            components['component_files'] = [
                f.name for f in components_dir.iterdir() 
                if f.is_file() and f.suffix == '.svelte'
            ]
            components['component_types'] = self._classify_component_types(components['component_files'])
        
        return components
    
    def _discover_template_services(self, template_id: str) -> Dict[str, Any]:
        """Discover template-specific API services"""
        services = {
            'service_files': [],
            'api_services': [],
            'has_services': False
        }
        
        if not self.frontend_dir:
            return services
        
        # Check lib/templates/{template_id}/services/
        services_dir = self.frontend_dir / 'lib' / 'templates' / template_id / 'services'
        if services_dir.exists():
            services['has_services'] = True
            services['service_files'] = [
                f.name for f in services_dir.iterdir() 
                if f.is_file() and f.suffix == '.ts'
            ]
            services['api_services'] = self._extract_api_service_methods(services_dir)
        
        return services
    
    def _combine_template_data(self, backend_templates: Dict, frontend_capabilities: Dict) -> Dict[str, Any]:
        """Combine backend and frontend discovery data"""
        enhanced_templates = {}
        
        # Process templates with backend data
        for template_id, backend_data in backend_templates.items():
            enhanced_template = {
                **backend_data,
                'frontend_capabilities': frontend_capabilities.get(template_id, {}),
                'full_stack_status': 'partial'  # Will be determined below
            }
            
            # Determine full-stack status
            has_backend = len(backend_data.get('backend_capabilities', {}).get('endpoints', {}).get('custom_views', [])) > 0
            has_frontend = template_id in frontend_capabilities
            
            if has_backend and has_frontend:
                enhanced_template['full_stack_status'] = 'complete'
            elif has_backend:
                enhanced_template['full_stack_status'] = 'backend_only'
            elif has_frontend:
                enhanced_template['full_stack_status'] = 'frontend_only'
            else:
                enhanced_template['full_stack_status'] = 'basic'
            
            enhanced_templates[template_id] = enhanced_template
        
        # Add frontend-only templates (shouldn't happen in our architecture, but for completeness)
        for template_id, frontend_data in frontend_capabilities.items():
            if template_id not in enhanced_templates:
                enhanced_templates[template_id] = {
                    'template_id': template_id,
                    'metadata': {'template_id': template_id, 'name': template_id.title()},
                    'backend_capabilities': {},
                    'frontend_capabilities': frontend_data,
                    'full_stack_status': 'frontend_only'
                }
        
        return enhanced_templates
    
    def _generate_discovery_metadata(self, templates: Dict[str, Any]) -> Dict[str, Any]:
        """Generate comprehensive discovery metadata"""
        return {
            'total_templates': len(templates),
            'templates_by_status': self._count_by_status(templates),
            'independence_levels': self._count_by_independence(templates),
            'architectural_completeness': self._assess_architectural_completeness(templates),
            'discovery_statistics': {
                'backend_endpoints_total': sum(
                    len(t.get('backend_capabilities', {}).get('endpoints', {}).get('custom_views', []))
                    for t in templates.values()
                ),
                'frontend_routes_total': sum(
                    len(t.get('frontend_capabilities', {}).get('frontend_capabilities', {}).get('routes', {}).get('route_files', []))
                    for t in templates.values()
                ),
                'complete_templates': len([t for t in templates.values() if t.get('full_stack_status') == 'complete'])
            }
        }
    
    def _assess_architectural_status(self, templates: Dict[str, Any]) -> Dict[str, Any]:
        """Assess overall architectural status of template system"""
        return {
            'system_health': 'operational' if len(templates) > 0 else 'no_templates',
            'template_independence': all(
                t.get('independence_analysis', {}).get('independence_level') == 'complete'
                for t in templates.values()
            ),
            'full_stack_coverage': len([t for t in templates.values() if t.get('full_stack_status') == 'complete']) / max(len(templates), 1),
            'architectural_recommendations': self._generate_architectural_recommendations(templates)
        }
    
    def _analyze_template_independence(self, template_dir: Path) -> Dict[str, Any]:
        """Analyze template independence level"""
        # For Phase 3, we'll implement basic independence checking
        # This can be enhanced in future phases
        
        template_id = template_dir.name
        has_custom_backend = any([
            (template_dir / 'views.py').exists(),
            (template_dir / 'urls.py').exists(),
            (template_dir / 'serializers.py').exists()
        ])
        
        return {
            'independence_level': 'complete' if has_custom_backend else 'basic',
            'has_custom_backend': has_custom_backend,
            'template_specific_files': [
                f.name for f in template_dir.iterdir() 
                if f.is_file() and f.suffix == '.py' and f.name not in ['__init__.py', 'definition.py']
            ]
        }
    
    def _analyze_frontend_independence(self, template_dir: Path, template_id: str) -> Dict[str, Any]:
        """Analyze frontend template independence"""
        has_selection_page = (template_dir / '+page.svelte').exists()
        has_project_interface = (template_dir / 'project').exists()
        
        # Check for template-specific components and services
        has_components = False
        has_services = False
        
        if self.frontend_dir:
            components_dir = self.frontend_dir / 'lib' / 'templates' / template_id / 'components'
            services_dir = self.frontend_dir / 'lib' / 'templates' / template_id / 'services'
            has_components = components_dir.exists()
            has_services = services_dir.exists()
        
        independence_score = sum([has_selection_page, has_components, has_services]) / 3
        
        return {
            'independence_level': 'complete' if independence_score >= 0.67 else 'partial',
            'has_selection_page': has_selection_page,
            'has_project_interface': has_project_interface,
            'has_components': has_components,
            'has_services': has_services,
            'independence_score': independence_score
        }
    
    # Helper methods for data extraction and analysis
    
    def _load_template_metadata(self, template_dir: Path) -> Optional[Dict]:
        """Load template metadata.json"""
        metadata_file = template_dir / 'metadata.json'
        if not metadata_file.exists():
            return None
            
        try:
            with open(metadata_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading metadata from {metadata_file}: {str(e)}")
            return None
    
    def _load_template_definition(self, template_dir: Path, metadata: Dict) -> Dict:
        """Load template definition configuration"""
        definition_file = template_dir / 'definition.py'
        if not definition_file.exists():
            return {}
            
        try:
            class_name = metadata.get('definition_class', 'TemplateDefinition')
            spec = importlib.util.spec_from_file_location("template_definition", definition_file)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            
            if hasattr(module, class_name):
                definition_class = getattr(module, class_name)
                instance = definition_class()
                if hasattr(instance, 'get_complete_configuration'):
                    return instance.get_complete_configuration()
            
            return {}
        except Exception as e:
            logger.error(f"Error loading definition from {definition_file}: {str(e)}")
            return {}
    
    def _extract_view_classes(self, views_file: Path) -> List[str]:
        """Extract view class names from views.py"""
        # Simple regex-based extraction for now
        # Can be enhanced with AST parsing
        try:
            with open(views_file, 'r') as f:
                content = f.read()
            
            import re
            pattern = r'class\s+(\w+(?:View|ViewSet))\s*\('
            matches = re.findall(pattern, content)
            return matches
        except Exception as e:
            logger.error(f"Error extracting views from {views_file}: {str(e)}")
            return []
    
    def _extract_url_patterns(self, urls_file: Path) -> List[str]:
        """Extract URL patterns from urls.py"""
        try:
            with open(urls_file, 'r') as f:
                content = f.read()
            
            import re
            pattern = r'path\(\s*[\'"]([^\'"]+)[\'"]'
            matches = re.findall(pattern, content)
            return matches
        except Exception as e:
            logger.error(f"Error extracting URLs from {urls_file}: {str(e)}")
            return []
    
    def _generate_api_endpoints(self, template_id: str, url_patterns: List[str]) -> List[str]:
        """Generate full API endpoint URLs"""
        base_url = f'/api/templates/{template_id}'
        return [f"{base_url}/{pattern.rstrip('/')}" for pattern in url_patterns]
    
    def _determine_architecture_level(self, components: Dict) -> str:
        """Determine template architecture level"""
        score = components.get('completeness_score', 0)
        
        if score >= 0.8:
            return 'complete'
        elif score >= 0.5:
            return 'partial'
        else:
            return 'basic'
    
    def _get_route_files(self, directory: Path) -> List[str]:
        """Get all route files in directory"""
        route_files = []
        for item in directory.rglob('*.svelte'):
            route_files.append(str(item.relative_to(directory)))
        return route_files
    
    def _classify_component_types(self, component_files: List[str]) -> List[str]:
        """Classify component types based on filenames"""
        types = set()
        
        for filename in component_files:
            lower_name = filename.lower()
            if 'upload' in lower_name:
                types.add('upload')
            elif 'search' in lower_name:
                types.add('search')
            elif 'navigation' in lower_name or 'nav' in lower_name:
                types.add('navigation')
            elif 'modal' in lower_name or 'dialog' in lower_name:
                types.add('modal')
            else:
                types.add('general')
        
        return list(types)
    
    def _extract_api_service_methods(self, services_dir: Path) -> List[str]:
        """Extract API service method names"""
        methods = []
        
        for service_file in services_dir.glob('*.ts'):
            try:
                with open(service_file, 'r') as f:
                    content = f.read()
                
                import re
                # Extract async method names
                pattern = r'async\s+(\w+)\s*\('
                file_methods = re.findall(pattern, content)
                methods.extend(file_methods)
            except Exception as e:
                logger.error(f"Error extracting methods from {service_file}: {str(e)}")
                continue
        
        return methods
    
    def _count_by_status(self, templates: Dict) -> Dict[str, int]:
        """Count templates by full-stack status"""
        status_counts = {}
        for template in templates.values():
            status = template.get('full_stack_status', 'unknown')
            status_counts[status] = status_counts.get(status, 0) + 1
        return status_counts
    
    def _count_by_independence(self, templates: Dict) -> Dict[str, int]:
        """Count templates by independence level"""
        independence_counts = {}
        for template in templates.values():
            level = template.get('independence_analysis', {}).get('independence_level', 'unknown')
            independence_counts[level] = independence_counts.get(level, 0) + 1
        return independence_counts
    
    def _assess_architectural_completeness(self, templates: Dict) -> Dict[str, float]:
        """Assess overall architectural completeness"""
        if not templates:
            return {'backend_completeness': 0.0, 'frontend_completeness': 0.0, 'overall_completeness': 0.0}
        
        backend_scores = []
        frontend_scores = []
        
        for template in templates.values():
            # Backend completeness
            backend_caps = template.get('backend_capabilities', {})
            backend_score = backend_caps.get('components', {}).get('completeness_score', 0.0)
            backend_scores.append(backend_score)
            
            # Frontend completeness
            frontend_caps = template.get('frontend_capabilities', {})
            frontend_analysis = frontend_caps.get('independence_analysis', {})
            frontend_score = frontend_analysis.get('independence_score', 0.0)
            frontend_scores.append(frontend_score)
        
        avg_backend = sum(backend_scores) / len(backend_scores)
        avg_frontend = sum(frontend_scores) / len(frontend_scores)
        overall = (avg_backend + avg_frontend) / 2
        
        return {
            'backend_completeness': avg_backend,
            'frontend_completeness': avg_frontend,
            'overall_completeness': overall
        }
    
    def _generate_architectural_recommendations(self, templates: Dict) -> List[str]:
        """Generate architectural improvement recommendations"""
        recommendations = []
        
        # Check for incomplete templates
        incomplete_templates = [
            t['template_id'] for t in templates.values() 
            if t.get('full_stack_status') != 'complete'
        ]
        
        if incomplete_templates:
            recommendations.append(
                f"Complete full-stack implementation for templates: {', '.join(incomplete_templates)}"
            )
        
        # Check independence levels
        basic_templates = [
            t['template_id'] for t in templates.values() 
            if t.get('independence_analysis', {}).get('independence_level') == 'basic'
        ]
        
        if basic_templates:
            recommendations.append(
                f"Enhance independence level for templates: {', '.join(basic_templates)}"
            )
        
        return recommendations
    
    def _get_current_timestamp(self) -> str:
        """Get current timestamp in ISO format"""
        from datetime import datetime
        return datetime.now().isoformat()


class TemplateRegistrationSystem:
    """Dynamic template registration and routing system"""
    
    def __init__(self):
        self.discovery = EnhancedTemplateDiscovery()
        logger.info("Initializing Template Registration System")
    
    def register_template_routes(self, template_id: str) -> Dict[str, Any]:
        """Register dynamic routes for a template"""
        logger.info(f"Registering routes for template: {template_id}")
        
        try:
            # Get template discovery data
            discovery_result = self.discovery.discover_all_templates()
            template_data = discovery_result['templates'].get(template_id)
            
            if not template_data:
                raise Exception(f"Template {template_id} not found in discovery results")
            
            # Register backend routes
            backend_routes = self._register_backend_routes(template_id, template_data)
            
            # Register frontend routes  
            frontend_routes = self._register_frontend_routes(template_id, template_data)
            
            registration_result = {
                'template_id': template_id,
                'backend_routes': backend_routes,
                'frontend_routes': frontend_routes,
                'registration_status': 'success',
                'timestamp': self.discovery._get_current_timestamp()
            }
            
            logger.info(f"Template {template_id} routes registered successfully")
            return registration_result
            
        except Exception as e:
            logger.error(f"Error registering routes for template {template_id}: {str(e)}")
            return {
                'template_id': template_id,
                'registration_status': 'error',
                'error_message': str(e),
                'timestamp': self.discovery._get_current_timestamp()
            }
    
    def _register_backend_routes(self, template_id: str, template_data: Dict) -> Dict[str, Any]:
        """Register backend API routes for template"""
        backend_caps = template_data.get('backend_capabilities', {})
        endpoints = backend_caps.get('endpoints', {})
        
        registered_routes = {
            'base_url': f'/api/templates/{template_id}',
            'endpoints': endpoints.get('api_endpoints', []),
            'view_classes': endpoints.get('custom_views', []),
            'has_custom_urls': backend_caps.get('has_custom_urls', False)
        }
        
        # Generate route information for Django URL dispatcher
        if registered_routes['has_custom_urls']:
            registered_routes['url_include_path'] = f'templates.template_definitions.{template_id}.urls'
        
        return registered_routes
    
    def _register_frontend_routes(self, template_id: str, template_data: Dict) -> Dict[str, Any]:
        """Register frontend routes for template"""
        frontend_caps = template_data.get('frontend_capabilities', {}).get('frontend_capabilities', {})
        routes = frontend_caps.get('routes', {})
        
        registered_routes = {
            'base_route': f'/features/{template_id}',
            'has_selection_page': routes.get('has_selection_page', False),
            'has_project_interface': routes.get('has_project_interface', False),
            'route_patterns': routes.get('route_patterns', [])
        }
        
        # Add component and service information
        registered_routes['components'] = frontend_caps.get('components', {})
        registered_routes['services'] = frontend_caps.get('services', {})
        
        return registered_routes
    
    def get_template_routing_info(self, template_id: str) -> Dict[str, Any]:
        """Get comprehensive routing information for a template"""
        try:
            registration_result = self.register_template_routes(template_id)
            
            if registration_result['registration_status'] == 'error':
                return registration_result
            
            # Add navigation information
            routing_info = {
                **registration_result,
                'navigation': {
                    'template_selection_url': f'/features/{template_id}/',
                    'project_creation_api': f'/api/templates/{template_id}/projects/',
                    'universal_project_interface': '/features/intellidoc/project/{id}/',
                    'template_management_api': f'/api/templates/{template_id}/'
                },
                'independence_status': {
                    'template_endpoints': registration_result['backend_routes']['endpoints'],
                    'universal_project_endpoints': [
                        '/api/projects/{id}/upload/',
                        '/api/projects/{id}/process/',
                        '/api/projects/{id}/search/',
                        '/api/projects/{id}/status/'
                    ],
                    'frontend_independence': registration_result['frontend_routes']['has_selection_page']
                }
            }
            
            return routing_info
            
        except Exception as e:
            logger.error(f"Error getting routing info for template {template_id}: {str(e)}")
            return {
                'template_id': template_id,
                'status': 'error',
                'error_message': str(e)
            }
    
    def validate_template_registration(self, template_id: str) -> Dict[str, Any]:
        """Validate template registration completeness"""
        logger.info(f"Validating template registration: {template_id}")
        
        try:
            routing_info = self.get_template_routing_info(template_id)
            
            if routing_info.get('status') == 'error':
                return {
                    'template_id': template_id,
                    'validation_status': 'failed',
                    'error_message': routing_info.get('error_message', 'Unknown error')
                }
            
            # Validation checks
            validation_results = {
                'has_backend_endpoints': len(routing_info['backend_routes']['endpoints']) > 0,
                'has_frontend_routes': routing_info['frontend_routes']['has_selection_page'],
                'has_custom_views': len(routing_info['backend_routes']['view_classes']) > 0,
                'registration_complete': False
            }
            
            # Overall validation
            validation_results['registration_complete'] = all([
                validation_results['has_backend_endpoints'],
                validation_results['has_frontend_routes']
            ])
            
            return {
                'template_id': template_id,
                'validation_status': 'passed' if validation_results['registration_complete'] else 'incomplete',
                'validation_results': validation_results,
                'recommendations': self._generate_registration_recommendations(validation_results)
            }
            
        except Exception as e:
            logger.error(f"Error validating template registration {template_id}: {str(e)}")
            return {
                'template_id': template_id,
                'validation_status': 'error',
                'error_message': str(e)
            }
    
    def _generate_registration_recommendations(self, validation_results: Dict) -> List[str]:
        """Generate recommendations for improving template registration"""
        recommendations = []
        
        if not validation_results['has_backend_endpoints']:
            recommendations.append("Add custom backend API endpoints in views.py and urls.py")
        
        if not validation_results['has_frontend_routes']:
            recommendations.append("Create template selection page at /features/{template_id}/+page.svelte")
        
        if not validation_results['has_custom_views']:
            recommendations.append("Implement custom view classes for template-specific functionality")
        
        return recommendations
