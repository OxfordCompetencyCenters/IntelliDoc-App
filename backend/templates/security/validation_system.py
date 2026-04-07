import os
import json
import importlib.util
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from enum import Enum
import logging

logger = logging.getLogger(__name__)

class ValidationLevel(Enum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"

class ValidationResult:
    def __init__(self, level: ValidationLevel, message: str, location: str = None):
        self.level = level
        self.message = message
        self.location = location
        self.timestamp = None
    
    def __str__(self):
        location_str = f" ({self.location})" if self.location else ""
        return f"[{self.level.value.upper()}] {self.message}{location_str}"

class TemplateValidator:
    """Comprehensive template validation system"""
    
    REQUIRED_FILES = {
        '__init__.py': 'Template package initialization',
        'metadata.json': 'Template metadata',
        'definition.py': 'Template definition class'
    }
    
    OPTIONAL_FILES = {
        'config.py': 'Basic template configuration',
        'navigation.py': 'Navigation configuration',
        'processing.py': 'Processing capabilities',
        'ui_config.py': 'UI configuration',
        'validation.py': 'Validation rules',
        'README.md': 'Template documentation'
    }
    
    def __init__(self, template_dir: Path):
        self.template_dir = template_dir
        self.results: List[ValidationResult] = []
        self.metadata = None
        self.definition_class = None
    
    def validate_template(self, validation_level: str = 'comprehensive') -> Tuple[bool, List[ValidationResult]]:
        """Validate template with specified level"""
        self.results.clear()
        
        try:
            # Basic validation
            self._validate_directory_structure()
            self._validate_required_files()
            self._validate_metadata()
            
            if validation_level in ['comprehensive', 'detailed']:
                self._validate_definition_class()
                self._validate_optional_files()
                self._validate_template_consistency()
            
            if validation_level == 'comprehensive':
                self._validate_template_functionality()
                self._validate_security()
                self._validate_performance()
            
            has_errors = any(result.level == ValidationLevel.ERROR for result in self.results)
            return not has_errors, self.results
            
        except Exception as e:
            logger.error(f"Error validating template {self.template_dir}: {str(e)}")
            self.results.append(ValidationResult(
                ValidationLevel.ERROR,
                f"Validation error: {str(e)}",
                str(self.template_dir)
            ))
            return False, self.results
    
    def _validate_directory_structure(self):
        """Validate template directory structure"""
        if not self.template_dir.exists():
            self.results.append(ValidationResult(
                ValidationLevel.ERROR,
                f"Template directory does not exist: {self.template_dir}",
                str(self.template_dir)
            ))
            return
        
        if not self.template_dir.is_dir():
            self.results.append(ValidationResult(
                ValidationLevel.ERROR,
                f"Template path is not a directory: {self.template_dir}",
                str(self.template_dir)
            ))
            return
        
        # Check for assets directory
        assets_dir = self.template_dir / 'assets'
        if assets_dir.exists():
            if not assets_dir.is_dir():
                self.results.append(ValidationResult(
                    ValidationLevel.WARNING,
                    "Assets path exists but is not a directory",
                    str(assets_dir)
                ))
            else:
                self.results.append(ValidationResult(
                    ValidationLevel.INFO,
                    "Assets directory found",
                    str(assets_dir)
                ))
    
    def _validate_required_files(self):
        """Validate required template files"""
        for filename, description in self.REQUIRED_FILES.items():
            file_path = self.template_dir / filename
            if not file_path.exists():
                self.results.append(ValidationResult(
                    ValidationLevel.ERROR,
                    f"Missing required file: {filename} ({description})",
                    str(file_path)
                ))
            elif not file_path.is_file():
                self.results.append(ValidationResult(
                    ValidationLevel.ERROR,
                    f"Required file is not a file: {filename}",
                    str(file_path)
                ))
    
    def _validate_metadata(self):
        """Validate metadata.json file"""
        metadata_file = self.template_dir / 'metadata.json'
        
        if not metadata_file.exists():
            self.results.append(ValidationResult(
                ValidationLevel.ERROR,
                "metadata.json file is missing",
                str(metadata_file)
            ))
            return
        
        try:
            with open(metadata_file, 'r') as f:
                self.metadata = json.load(f)
            
            # Check required fields
            required_fields = [
                'template_id', 'template_type', 'name', 'description', 
                'definition_class', 'version', 'author'
            ]
            
            for field in required_fields:
                if field not in self.metadata:
                    self.results.append(ValidationResult(
                        ValidationLevel.ERROR,
                        f"Missing required metadata field: {field}",
                        str(metadata_file)
                    ))
                elif not isinstance(self.metadata[field], str) or not self.metadata[field].strip():
                    self.results.append(ValidationResult(
                        ValidationLevel.ERROR,
                        f"Invalid or empty metadata field: {field}",
                        str(metadata_file)
                    ))
            
            # Validate specific fields
            if 'template_id' in self.metadata:
                if not self._validate_template_id_format(self.metadata['template_id']):
                    self.results.append(ValidationResult(
                        ValidationLevel.ERROR,
                        f"Invalid template_id format: {self.metadata['template_id']}",
                        str(metadata_file)
                    ))
            
            # Check optional but recommended fields
            recommended_fields = ['category', 'tags', 'features', 'requirements']
            for field in recommended_fields:
                if field not in self.metadata:
                    self.results.append(ValidationResult(
                        ValidationLevel.INFO,
                        f"Recommended metadata field missing: {field}",
                        str(metadata_file)
                    ))
            
            # Validate version format
            if 'version' in self.metadata:
                if not self._validate_version_format(self.metadata['version']):
                    self.results.append(ValidationResult(
                        ValidationLevel.WARNING,
                        f"Invalid version format: {self.metadata['version']}",
                        str(metadata_file)
                    ))
            
        except json.JSONDecodeError as e:
            self.results.append(ValidationResult(
                ValidationLevel.ERROR,
                f"Invalid JSON in metadata.json: {str(e)}",
                str(metadata_file)
            ))
        except Exception as e:
            self.results.append(ValidationResult(
                ValidationLevel.ERROR,
                f"Error reading metadata.json: {str(e)}",
                str(metadata_file)
            ))
    
    def _validate_definition_class(self):
        """Validate definition.py file and class"""
        definition_file = self.template_dir / 'definition.py'
        
        if not definition_file.exists():
            self.results.append(ValidationResult(
                ValidationLevel.ERROR,
                "definition.py file is missing",
                str(definition_file)
            ))
            return
        
        if not self.metadata:
            self.results.append(ValidationResult(
                ValidationLevel.ERROR,
                "Cannot validate definition class without metadata",
                str(definition_file)
            ))
            return
        
        try:
            # Load module from file
            spec = importlib.util.spec_from_file_location("template_definition", definition_file)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            
            # Get definition class
            class_name = self.metadata.get('definition_class')
            if not class_name:
                self.results.append(ValidationResult(
                    ValidationLevel.ERROR,
                    "definition_class not specified in metadata",
                    str(definition_file)
                ))
                return
            
            if not hasattr(module, class_name):
                self.results.append(ValidationResult(
                    ValidationLevel.ERROR,
                    f"Definition class {class_name} not found in definition.py",
                    str(definition_file)
                ))
                return
            
            self.definition_class = getattr(module, class_name)
            
            # Check required method
            if not hasattr(self.definition_class, 'get_complete_configuration'):
                self.results.append(ValidationResult(
                    ValidationLevel.ERROR,
                    f"Definition class {class_name} missing get_complete_configuration method",
                    str(definition_file)
                ))
                return
            
            # Test instantiation
            try:
                instance = self.definition_class()
                config = instance.get_complete_configuration()
                
                if not isinstance(config, dict):
                    self.results.append(ValidationResult(
                        ValidationLevel.ERROR,
                        "get_complete_configuration must return a dictionary",
                        str(definition_file)
                    ))
                else:
                    self.results.append(ValidationResult(
                        ValidationLevel.INFO,
                        f"Definition class {class_name} validated successfully",
                        str(definition_file)
                    ))
                    
            except Exception as e:
                self.results.append(ValidationResult(
                    ValidationLevel.ERROR,
                    f"Error testing definition class: {str(e)}",
                    str(definition_file)
                ))
            
        except Exception as e:
            self.results.append(ValidationResult(
                ValidationLevel.ERROR,
                f"Error loading definition.py: {str(e)}",
                str(definition_file)
            ))
    
    def _validate_optional_files(self):
        """Validate optional template files"""
        for filename, description in self.OPTIONAL_FILES.items():
            file_path = self.template_dir / filename
            if file_path.exists():
                if not file_path.is_file():
                    self.results.append(ValidationResult(
                        ValidationLevel.WARNING,
                        f"Optional file is not a file: {filename}",
                        str(file_path)
                    ))
                else:
                    self.results.append(ValidationResult(
                        ValidationLevel.INFO,
                        f"Optional file found: {filename} ({description})",
                        str(file_path)
                    ))
    
    def _validate_template_consistency(self):
        """Validate consistency between template files"""
        if not self.metadata or not self.definition_class:
            return
        
        try:
            # Get configuration from definition class
            instance = self.definition_class()
            config = instance.get_complete_configuration()
            
            # Check consistency between metadata and configuration
            consistency_checks = [
                ('name', 'name'),
                ('template_type', 'template_type'),
                ('description', 'description')
            ]
            
            for metadata_field, config_field in consistency_checks:
                if metadata_field in self.metadata and config_field in config:
                    if self.metadata[metadata_field] != config[config_field]:
                        self.results.append(ValidationResult(
                            ValidationLevel.WARNING,
                            f"Inconsistency: metadata.{metadata_field} != config.{config_field}",
                            str(self.template_dir)
                        ))
            
            # Validate configuration structure
            required_config_fields = [
                'name', 'template_type', 'description', 'instructions',
                'suggested_questions', 'required_fields', 'analysis_focus',
                'icon_class', 'color_theme', 'has_navigation', 'total_pages',
                'navigation_pages', 'processing_capabilities', 'validation_rules',
                'ui_configuration'
            ]
            
            for field in required_config_fields:
                if field not in config:
                    self.results.append(ValidationResult(
                        ValidationLevel.ERROR,
                        f"Missing required configuration field: {field}",
                        str(self.template_dir / 'definition.py')
                    ))
            
        except Exception as e:
            self.results.append(ValidationResult(
                ValidationLevel.ERROR,
                f"Error validating template consistency: {str(e)}",
                str(self.template_dir)
            ))
    
    def _validate_template_functionality(self):
        """Validate template functionality"""
        if not self.definition_class:
            return
        
        try:
            instance = self.definition_class()
            config = instance.get_complete_configuration()
            
            # Test navigation configuration
            if config.get('has_navigation'):
                navigation_pages = config.get('navigation_pages', [])
                if not navigation_pages:
                    self.results.append(ValidationResult(
                        ValidationLevel.WARNING,
                        "Template has navigation enabled but no navigation pages defined",
                        str(self.template_dir)
                    ))
                else:
                    # Validate navigation pages structure
                    for i, page in enumerate(navigation_pages):
                        required_page_fields = ['page_number', 'name', 'features']
                        for field in required_page_fields:
                            if field not in page:
                                self.results.append(ValidationResult(
                                    ValidationLevel.ERROR,
                                    f"Navigation page {i+1} missing required field: {field}",
                                    str(self.template_dir)
                                ))
            
            # Test processing capabilities
            processing_caps = config.get('processing_capabilities', {})
            if processing_caps:
                if 'supported_formats' not in processing_caps:
                    self.results.append(ValidationResult(
                        ValidationLevel.WARNING,
                        "Processing capabilities missing supported_formats",
                        str(self.template_dir)
                    ))
                
                if 'max_file_size' not in processing_caps:
                    self.results.append(ValidationResult(
                        ValidationLevel.INFO,
                        "Processing capabilities missing max_file_size",
                        str(self.template_dir)
                    ))
            
            # Test UI configuration
            ui_config = config.get('ui_configuration', {})
            if ui_config:
                if 'layout' not in ui_config:
                    self.results.append(ValidationResult(
                        ValidationLevel.WARNING,
                        "UI configuration missing layout specification",
                        str(self.template_dir)
                    ))
            
        except Exception as e:
            self.results.append(ValidationResult(
                ValidationLevel.ERROR,
                f"Error validating template functionality: {str(e)}",
                str(self.template_dir)
            ))
    
    def _validate_security(self):
        """Validate template security aspects"""
        # This integrates with the SecurityManager
        from .security_manager import TemplateSecurityManager
        
        security_result = TemplateSecurityManager.validate_template_directory(self.template_dir)
        
        if not security_result['valid']:
            for error in security_result['errors']:
                self.results.append(ValidationResult(
                    ValidationLevel.ERROR,
                    f"Security violation: {error}",
                    str(self.template_dir)
                ))
        else:
            self.results.append(ValidationResult(
                ValidationLevel.INFO,
                "Template passed security validation",
                str(self.template_dir)
            ))
    
    def _validate_performance(self):
        """Validate template performance aspects"""
        try:
            # Check template size
            template_size = sum(f.stat().st_size for f in self.template_dir.rglob('*') if f.is_file())
            if template_size > 10 * 1024 * 1024:  # 10MB
                self.results.append(ValidationResult(
                    ValidationLevel.WARNING,
                    f"Template size is large: {template_size / (1024*1024):.2f}MB",
                    str(self.template_dir)
                ))
            
            # Check number of files
            file_count = len(list(self.template_dir.rglob('*')))
            if file_count > 50:
                self.results.append(ValidationResult(
                    ValidationLevel.WARNING,
                    f"Template has many files: {file_count}",
                    str(self.template_dir)
                ))
            
            # Test configuration loading performance
            if self.definition_class:
                import time
                start_time = time.time()
                
                instance = self.definition_class()
                config = instance.get_complete_configuration()
                
                load_time = time.time() - start_time
                
                if load_time > 1.0:  # 1 second
                    self.results.append(ValidationResult(
                        ValidationLevel.WARNING,
                        f"Template configuration loading is slow: {load_time:.3f}s",
                        str(self.template_dir)
                    ))
                else:
                    self.results.append(ValidationResult(
                        ValidationLevel.INFO,
                        f"Template configuration loads quickly: {load_time:.3f}s",
                        str(self.template_dir)
                    ))
            
        except Exception as e:
            self.results.append(ValidationResult(
                ValidationLevel.WARNING,
                f"Error validating template performance: {str(e)}",
                str(self.template_dir)
            ))
    
    def _validate_template_id_format(self, template_id: str) -> bool:
        """Validate template ID format"""
        if not template_id or not isinstance(template_id, str):
            return False
        
        # Check length
        if len(template_id) < 3 or len(template_id) > 50:
            return False
        
        # Check characters
        if not template_id.replace('-', '').replace('_', '').isalnum():
            return False
        
        # Check start/end characters
        if template_id.startswith(('-', '_')) or template_id.endswith(('-', '_')):
            return False
        
        return True
    
    def _validate_version_format(self, version: str) -> bool:
        """Validate version format (semantic versioning)"""
        if not version or not isinstance(version, str):
            return False
        
        # Simple semantic versioning check
        parts = version.split('.')
        if len(parts) != 3:
            return False
        
        for part in parts:
            if not part.isdigit():
                return False
        
        return True
