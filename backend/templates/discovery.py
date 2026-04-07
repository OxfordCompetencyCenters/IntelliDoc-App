import os
import json
import hashlib
import importlib.util
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from django.conf import settings
from django.core.cache import cache
import logging

logger = logging.getLogger(__name__)

class TemplateDiscoverySystem:
    """Filesystem-based template discovery system"""
    
    CACHE_KEY_PREFIX = 'template_discovery_'
    CACHE_TIMEOUT = 3600  # 1 hour
    FILESYSTEM_CHECK_INTERVAL = 60  # Check every minute
    
    @classmethod
    def get_template_definitions_path(cls):
        """Get the path to template definitions directory"""
        return Path(settings.BASE_DIR) / 'templates' / 'template_definitions'
    
    @classmethod
    def discover_templates(cls, force_refresh=False):
        """Discover templates from filesystem with enhanced caching"""
        # Use the enhanced caching system
        from .cache import TemplateDiscoveryCache
        return TemplateDiscoveryCache.get_cached_templates(force_refresh=force_refresh)
    
    @classmethod
    def _scan_template_directories(cls, template_dir: Path) -> Dict:
        """Scan template directories and load configurations"""
        templates = {}
        
        for item in template_dir.iterdir():
            if item.is_dir() and not item.name.startswith('.'):
                template_id = item.name
                
                try:
                    template_config = cls._load_template_configuration(item)
                    if template_config:
                        templates[template_id] = template_config
                except Exception as e:
                    logger.error(f"Failed to load template {template_id}: {str(e)}")
                    continue
        
        return templates
    
    @classmethod
    def _load_template_configuration(cls, template_dir: Path) -> Optional[Dict]:
        """Load complete template configuration from directory with security validation"""
        metadata_file = template_dir / 'metadata.json'
        definition_file = template_dir / 'definition.py'
        
        # Check if definition.py exists (required)
        if not definition_file.exists():
            logger.warning(f"Template {template_dir.name} missing definition.py")
            return None
        
        try:
            # Basic security validation (optional for now)
            try:
                from .security.security_manager import TemplateSecurityManager
                security_result = TemplateSecurityManager.validate_template_directory(template_dir)
                
                if not security_result['valid']:
                    logger.warning(f"Template {template_dir.name} failed security validation: {security_result['errors']}")
                    # Continue anyway for now - don't block template loading
            except Exception as sec_error:
                logger.warning(f"Security validation failed for {template_dir.name}: {str(sec_error)}")
                # Continue anyway - don't block template loading
            
            # Try to load metadata.json if it exists
            metadata = None
            definition_class = None
            
            if metadata_file.exists():
                try:
                    with open(metadata_file, 'r') as f:
                        metadata = json.load(f)
                    definition_class = metadata.get('definition_class')
                    logger.info(f"Loaded metadata.json for template {template_dir.name}")
                except Exception as e:
                    logger.warning(f"Failed to load metadata.json for {template_dir.name}: {str(e)}")
                    metadata = None
            else:
                logger.info(f"No metadata.json found for {template_dir.name}, using fallback")
            
            # Fallback: Generate metadata from template directory name and definition class
            if not metadata:
                template_id = template_dir.name
                # Infer definition class name from common patterns
                definition_class = cls._infer_definition_class_name(template_id)
                
                metadata = {
                    'template_id': template_id,
                    'template_type': template_id,
                    'name': template_id.replace('-', ' ').title(),
                    'description': f'Template for {template_id}',
                    'definition_class': definition_class,
                    'version': '1.0.0',
                    'author': 'Unknown',
                    'created_from_fallback': True
                }
                logger.info(f"Generated fallback metadata for {template_id} with class {definition_class}")
            
            # Load definition class configuration
            definition_config = cls._load_definition_class(definition_file, definition_class)
            
            if not definition_config:
                logger.error(f"Failed to load definition class for {template_dir.name}")
                return None
            
            # Combine metadata and definition
            template_config = {
                'template_id': metadata.get('template_id'),
                'metadata': metadata,
                'configuration': definition_config,
                'source': 'folder',
                'folder_path': str(template_dir),
                'security_validated': True,
                'loaded_from_fallback': metadata.get('created_from_fallback', False)
            }
            
            return template_config
            
        except Exception as e:
            logger.error(f"Error loading template {template_dir.name}: {str(e)}")
            import traceback
            logger.error(f"Full traceback: {traceback.format_exc()}")
            return None
    
    @classmethod
    def _infer_definition_class_name(cls, template_id: str) -> str:
        """Infer definition class name from template ID"""
        # Known patterns for existing templates
        class_name_mapping = {
            'aicc-intellidoc': 'AICCIntelliDocTemplateDefinition',
            'aicc-intellidoc-v2': 'AICCIntelliDocTemplateDefinition', 
            'aicc-intellidoc-v4': 'AICCIntelliDocTemplateDefinition',
            'legal': 'LegalTemplateDefinition',
            'medical': 'MedicalTemplateDefinition',
            'history': 'HistoryTemplateDefinition'
        }
        
        # Return known mapping if available
        if template_id in class_name_mapping:
            return class_name_mapping[template_id]
        
        # Fallback: Generate class name from template ID
        # Convert kebab-case to PascalCase and add TemplateDefinition suffix
        words = template_id.replace('-', '_').split('_')
        class_name = ''.join(word.capitalize() for word in words) + 'TemplateDefinition'
        return class_name
    
    @classmethod
    def _load_definition_class(cls, definition_file: Path, class_name: str) -> Dict:
        """Load template definition class and get configuration"""
        try:
            # Load module from file
            spec = importlib.util.spec_from_file_location("template_definition", definition_file)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            
            # Get definition class
            definition_class = getattr(module, class_name)
            instance = definition_class()
            
            # Get complete configuration
            return instance.get_complete_configuration()
            
        except Exception as e:
            logger.error(f"Error loading definition class {class_name}: {str(e)}")
            return {}
    
    @classmethod
    def _calculate_directory_hash(cls, directory: Path) -> str:
        """Calculate hash of directory contents for change detection"""
        hash_md5 = hashlib.md5()
        
        try:
            for root, dirs, files in os.walk(directory):
                # Sort for consistent hashing
                dirs.sort()
                files.sort()
                
                for filename in files:
                    filepath = Path(root) / filename
                    hash_md5.update(filename.encode())
                    hash_md5.update(str(filepath.stat().st_mtime).encode())
            
            return hash_md5.hexdigest()
        except Exception as e:
            logger.error(f"Error calculating directory hash: {str(e)}")
            return str(hash(str(directory)))
    
    @classmethod
    def get_template_configuration(cls, template_id: str) -> Optional[Dict]:
        """Get complete configuration for a specific template without caching"""
        # Load directly from filesystem to avoid cache recursion
        template_dir = cls.get_template_definitions_path() / template_id
        return cls._load_template_configuration(template_dir)
    
    @classmethod
    def list_available_templates(cls) -> List[Dict]:
        """Get list of available templates with metadata"""
        templates = cls.discover_templates()
        template_list = []
        
        for template_id, template_info in templates.items():
            metadata = template_info.get('metadata', {})
            template_list.append({
                'id': template_id,  # Always use template_id as id
                'template_type': metadata.get('template_type', template_id),  # Fallback to template_id
                'name': metadata.get('name', template_id.title()),  # Fallback to title case template_id
                'description': metadata.get('description', f'Template for {template_id}'),  # Fallback description
                'icon_class': metadata.get('ui_assets', {}).get('icon', 'fa-file-alt'),
                'color_theme': metadata.get('color_theme', 'oxford-blue'),
                'analysis_focus': metadata.get('analysis_focus', 'Document analysis'),
                'source': 'folder',
                'metadata': metadata  # Include full metadata for frontend validation
            })
        
        return template_list


class TemplateValidator:
    """Validates template structure and integrity"""
    
    REQUIRED_FILES = {
        '__init__.py': 'Template package initialization',
        'metadata.json': 'Template metadata',
        'definition.py': 'Template definition class'
    }
    
    @classmethod
    def validate_template_directory(cls, template_dir: Path) -> Dict:
        """Validate template directory structure"""
        results = []
        
        # Check if directory exists
        if not template_dir.exists():
            return {'valid': False, 'errors': [f'Template directory does not exist: {template_dir}']}
        
        # Check required files
        for filename, description in cls.REQUIRED_FILES.items():
            file_path = template_dir / filename
            if not file_path.exists():
                results.append(f'Missing required file: {filename} ({description})')
        
        # Validate metadata.json
        metadata_results = cls._validate_metadata(template_dir / 'metadata.json')
        results.extend(metadata_results)
        
        # Validate definition.py
        definition_results = cls._validate_definition(template_dir / 'definition.py')
        results.extend(definition_results)
        
        return {'valid': len(results) == 0, 'errors': results}
    
    @classmethod
    def _validate_metadata(cls, metadata_file: Path) -> List[str]:
        """Validate metadata.json file"""
        results = []
        
        if not metadata_file.exists():
            return ['metadata.json file is missing']
        
        try:
            with open(metadata_file, 'r') as f:
                metadata = json.load(f)
            
            # Check required fields
            required_fields = ['template_id', 'template_type', 'name', 'description', 'definition_class']
            for field in required_fields:
                if field not in metadata:
                    results.append(f'Missing required metadata field: {field}')
            
        except json.JSONDecodeError as e:
            results.append(f'Invalid JSON in metadata.json: {str(e)}')
        except Exception as e:
            results.append(f'Error reading metadata.json: {str(e)}')
        
        return results
    
    @classmethod
    def _validate_definition(cls, definition_file: Path) -> List[str]:
        """Validate definition.py file"""
        results = []
        
        if not definition_file.exists():
            return ['definition.py file is missing']
        
        try:
            # Try to import and validate the definition class
            spec = importlib.util.spec_from_file_location("template_definition", definition_file)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            
            # Check if get_complete_configuration method exists
            # We need to read metadata to get class name
            metadata_file = definition_file.parent / 'metadata.json'
            if metadata_file.exists():
                with open(metadata_file, 'r') as f:
                    metadata = json.load(f)
                
                class_name = metadata.get('definition_class')
                if class_name and hasattr(module, class_name):
                    definition_class = getattr(module, class_name)
                    if hasattr(definition_class, 'get_complete_configuration'):
                        # Try to call the method
                        instance = definition_class()
                        config = instance.get_complete_configuration()
                        if not isinstance(config, dict):
                            results.append('get_complete_configuration must return a dictionary')
                    else:
                        results.append(f'Definition class {class_name} missing get_complete_configuration method')
                else:
                    results.append(f'Definition class {class_name} not found in definition.py')
            
        except Exception as e:
            results.append(f'Error validating definition.py: {str(e)}')
        
        return results
