import logging
import traceback
from typing import Dict, List, Optional, Any
from pathlib import Path
from django.core.cache import cache
from django.utils import timezone
from contextlib import contextmanager
import json

logger = logging.getLogger(__name__)

class TemplateErrorType:
    """Template error types for categorization"""
    VALIDATION_ERROR = "validation_error"
    SECURITY_ERROR = "security_error"
    FILESYSTEM_ERROR = "filesystem_error"
    CONCURRENCY_ERROR = "concurrency_error"
    METADATA_ERROR = "metadata_error"
    DEFINITION_ERROR = "definition_error"
    CACHE_ERROR = "cache_error"
    PERMISSION_ERROR = "permission_error"

class TemplateError:
    """Structured template error with context"""
    
    def __init__(self, error_type: str, message: str, template_id: str = None, 
                 location: str = None, details: Dict = None, exception: Exception = None):
        self.error_type = error_type
        self.message = message
        self.template_id = template_id
        self.location = location
        self.details = details or {}
        self.exception = exception
        self.timestamp = timezone.now()
        self.traceback = traceback.format_exc() if exception else None
    
    def to_dict(self) -> Dict:
        """Convert error to dictionary"""
        return {
            'error_type': self.error_type,
            'message': self.message,
            'template_id': self.template_id,
            'location': self.location,
            'details': self.details,
            'timestamp': self.timestamp.isoformat(),
            'traceback': self.traceback
        }
    
    def __str__(self):
        return f"[{self.error_type}] {self.message}"

class TemplateErrorHandler:
    """Centralized error handling and recovery for template operations"""
    
    ERROR_CACHE_KEY = "template_errors"
    ERROR_CACHE_TIMEOUT = 3600  # 1 hour
    MAX_CACHED_ERRORS = 100
    
    @classmethod
    def handle_error(cls, error: TemplateError) -> Dict:
        """Handle template error with logging and caching"""
        # Log error
        logger.error(f"Template error: {error}")
        
        # Cache error for debugging
        cls._cache_error(error)
        
        # Determine recovery strategy
        recovery_strategy = cls._determine_recovery_strategy(error)
        
        # Attempt recovery if possible
        recovery_result = None
        if recovery_strategy:
            try:
                recovery_result = cls._attempt_recovery(error, recovery_strategy)
            except Exception as e:
                logger.error(f"Recovery failed for error {error.error_type}: {str(e)}")
        
        return {
            'error': error.to_dict(),
            'recovery_strategy': recovery_strategy,
            'recovery_result': recovery_result
        }
    
    @classmethod
    def _cache_error(cls, error: TemplateError):
        """Cache error for debugging and analysis"""
        try:
            cached_errors = cache.get(cls.ERROR_CACHE_KEY, [])
            
            # Add new error
            cached_errors.append(error.to_dict())
            
            # Limit cache size
            if len(cached_errors) > cls.MAX_CACHED_ERRORS:
                cached_errors = cached_errors[-cls.MAX_CACHED_ERRORS:]
            
            cache.set(cls.ERROR_CACHE_KEY, cached_errors, cls.ERROR_CACHE_TIMEOUT)
            
        except Exception as e:
            logger.error(f"Failed to cache error: {str(e)}")
    
    @classmethod
    def _determine_recovery_strategy(cls, error: TemplateError) -> Optional[str]:
        """Determine appropriate recovery strategy for error"""
        strategies = {
            TemplateErrorType.VALIDATION_ERROR: 'validate_and_fix',
            TemplateErrorType.SECURITY_ERROR: 'security_quarantine',
            TemplateErrorType.FILESYSTEM_ERROR: 'filesystem_repair',
            TemplateErrorType.CONCURRENCY_ERROR: 'retry_with_backoff',
            TemplateErrorType.METADATA_ERROR: 'metadata_repair',
            TemplateErrorType.DEFINITION_ERROR: 'definition_repair',
            TemplateErrorType.CACHE_ERROR: 'cache_refresh',
            TemplateErrorType.PERMISSION_ERROR: 'permission_check'
        }
        
        return strategies.get(error.error_type)
    
    @classmethod
    def _attempt_recovery(cls, error: TemplateError, strategy: str) -> Dict:
        """Attempt error recovery based on strategy"""
        recovery_methods = {
            'validate_and_fix': cls._recover_validation_error,
            'security_quarantine': cls._recover_security_error,
            'filesystem_repair': cls._recover_filesystem_error,
            'retry_with_backoff': cls._recover_concurrency_error,
            'metadata_repair': cls._recover_metadata_error,
            'definition_repair': cls._recover_definition_error,
            'cache_refresh': cls._recover_cache_error,
            'permission_check': cls._recover_permission_error
        }
        
        recovery_method = recovery_methods.get(strategy)
        if recovery_method:
            return recovery_method(error)
        
        return {'success': False, 'message': f'No recovery method for strategy: {strategy}'}
    
    @classmethod
    def _recover_validation_error(cls, error: TemplateError) -> Dict:
        """Recover from validation errors"""
        if not error.template_id:
            return {'success': False, 'message': 'No template ID provided'}
        
        try:
            from templates.discovery import TemplateDiscoverySystem
            from templates.security import TemplateValidator
            
            template_dir = TemplateDiscoverySystem.get_template_definitions_path() / error.template_id
            
            if not template_dir.exists():
                return {'success': False, 'message': 'Template directory not found'}
            
            # Run validation to get specific issues
            validator = TemplateValidator(template_dir)
            is_valid, results = validator.validate_template('basic')
            
            if is_valid:
                return {'success': True, 'message': 'Template validation passed on retry'}
            
            # Attempt basic fixes
            fixes_applied = []
            
            # Check for missing __init__.py
            init_file = template_dir / '__init__.py'
            if not init_file.exists():
                init_file.touch()
                fixes_applied.append('Created missing __init__.py')
            
            # Check for basic metadata issues
            metadata_file = template_dir / 'metadata.json'
            if metadata_file.exists():
                try:
                    with open(metadata_file, 'r') as f:
                        metadata = json.load(f)
                    
                    # Fix missing template_id
                    if 'template_id' not in metadata:
                        metadata['template_id'] = error.template_id
                        with open(metadata_file, 'w') as f:
                            json.dump(metadata, f, indent=2)
                        fixes_applied.append('Fixed missing template_id in metadata')
                    
                except Exception as e:
                    logger.error(f"Failed to fix metadata: {str(e)}")
            
            return {
                'success': len(fixes_applied) > 0,
                'message': f'Applied {len(fixes_applied)} fixes',
                'fixes_applied': fixes_applied
            }
            
        except Exception as e:
            logger.error(f"Validation recovery failed: {str(e)}")
            return {'success': False, 'message': f'Recovery failed: {str(e)}'}
    
    @classmethod
    def _recover_security_error(cls, error: TemplateError) -> Dict:
        """Recover from security errors by quarantining template"""
        if not error.template_id:
            return {'success': False, 'message': 'No template ID provided'}
        
        try:
            from templates.discovery import TemplateDiscoverySystem
            
            template_dir = TemplateDiscoverySystem.get_template_definitions_path() / error.template_id
            
            if not template_dir.exists():
                return {'success': False, 'message': 'Template directory not found'}
            
            # Create quarantine directory
            quarantine_dir = template_dir.parent / 'quarantine'
            quarantine_dir.mkdir(exist_ok=True)
            
            # Move template to quarantine
            quarantine_path = quarantine_dir / error.template_id
            if quarantine_path.exists():
                import shutil
                shutil.rmtree(quarantine_path)
            
            import shutil
            shutil.move(str(template_dir), str(quarantine_path))
            
            # Log quarantine action
            logger.warning(f"Template {error.template_id} quarantined due to security error")
            
            return {
                'success': True,
                'message': f'Template quarantined to {quarantine_path}',
                'quarantine_path': str(quarantine_path)
            }
            
        except Exception as e:
            logger.error(f"Security recovery failed: {str(e)}")
            return {'success': False, 'message': f'Recovery failed: {str(e)}'}
    
    @classmethod
    def _recover_filesystem_error(cls, error: TemplateError) -> Dict:
        """Recover from filesystem errors"""
        try:
            # Check filesystem permissions
            from templates.discovery import TemplateDiscoverySystem
            
            template_dir = TemplateDiscoverySystem.get_template_definitions_path()
            
            if not template_dir.exists():
                template_dir.mkdir(parents=True, exist_ok=True)
                return {'success': True, 'message': 'Created missing template directory'}
            
            # Check read/write permissions
            if not os.access(template_dir, os.R_OK | os.W_OK):
                return {'success': False, 'message': 'Insufficient filesystem permissions'}
            
            return {'success': True, 'message': 'Filesystem appears healthy'}
            
        except Exception as e:
            logger.error(f"Filesystem recovery failed: {str(e)}")
            return {'success': False, 'message': f'Recovery failed: {str(e)}'}
    
    @classmethod
    def _recover_concurrency_error(cls, error: TemplateError) -> Dict:
        """Recover from concurrency errors"""
        try:
            # Clear any stale locks
            from templates.security.concurrency_manager import TemplateOperationManager
            
            TemplateOperationManager.cleanup_stale_operations(max_age_hours=1)
            
            # Wait briefly then retry
            import time
            time.sleep(0.5)
            
            return {'success': True, 'message': 'Cleaned up stale operations, retry recommended'}
            
        except Exception as e:
            logger.error(f"Concurrency recovery failed: {str(e)}")
            return {'success': False, 'message': f'Recovery failed: {str(e)}'}
    
    @classmethod
    def _recover_metadata_error(cls, error: TemplateError) -> Dict:
        """Recover from metadata errors"""
        if not error.template_id:
            return {'success': False, 'message': 'No template ID provided'}
        
        try:
            from templates.discovery import TemplateDiscoverySystem
            
            template_dir = TemplateDiscoverySystem.get_template_definitions_path() / error.template_id
            metadata_file = template_dir / 'metadata.json'
            
            if not metadata_file.exists():
                # Create basic metadata
                basic_metadata = {
                    'template_id': error.template_id,
                    'template_type': error.template_id,
                    'version': '1.0.0',
                    'name': error.template_id.replace('-', ' ').title(),
                    'description': f'Template: {error.template_id}',
                    'author': 'System',
                    'definition_class': 'TemplateDefinition',
                    'is_active': True
                }
                
                with open(metadata_file, 'w') as f:
                    json.dump(basic_metadata, f, indent=2)
                
                return {'success': True, 'message': 'Created basic metadata file'}
            
            # Try to fix corrupted metadata
            try:
                with open(metadata_file, 'r') as f:
                    metadata = json.load(f)
                
                # Ensure required fields exist
                required_fields = {
                    'template_id': error.template_id,
                    'template_type': error.template_id,
                    'version': '1.0.0',
                    'name': error.template_id.replace('-', ' ').title(),
                    'description': f'Template: {error.template_id}',
                    'author': 'System',
                    'definition_class': 'TemplateDefinition'
                }
                
                fixes_applied = []
                for field, default_value in required_fields.items():
                    if field not in metadata:
                        metadata[field] = default_value
                        fixes_applied.append(f'Added missing field: {field}')
                
                if fixes_applied:
                    with open(metadata_file, 'w') as f:
                        json.dump(metadata, f, indent=2)
                    
                    return {
                        'success': True,
                        'message': f'Fixed metadata: {", ".join(fixes_applied)}',
                        'fixes_applied': fixes_applied
                    }
                
                return {'success': True, 'message': 'Metadata appears valid'}
                
            except json.JSONDecodeError:
                # Backup corrupted file and create new one
                import shutil
                backup_file = metadata_file.with_suffix('.json.backup')
                shutil.copy(metadata_file, backup_file)
                
                # Create new metadata
                basic_metadata = {
                    'template_id': error.template_id,
                    'template_type': error.template_id,
                    'version': '1.0.0',
                    'name': error.template_id.replace('-', ' ').title(),
                    'description': f'Template: {error.template_id}',
                    'author': 'System',
                    'definition_class': 'TemplateDefinition',
                    'is_active': True
                }
                
                with open(metadata_file, 'w') as f:
                    json.dump(basic_metadata, f, indent=2)
                
                return {
                    'success': True,
                    'message': f'Replaced corrupted metadata (backed up to {backup_file})'
                }
            
        except Exception as e:
            logger.error(f"Metadata recovery failed: {str(e)}")
            return {'success': False, 'message': f'Recovery failed: {str(e)}'}
    
    @classmethod
    def _recover_definition_error(cls, error: TemplateError) -> Dict:
        """Recover from definition errors"""
        if not error.template_id:
            return {'success': False, 'message': 'No template ID provided'}
        
        try:
            from templates.discovery import TemplateDiscoverySystem
            
            template_dir = TemplateDiscoverySystem.get_template_definitions_path() / error.template_id
            definition_file = template_dir / 'definition.py'
            
            if not definition_file.exists():
                # Create basic definition file
                basic_definition = f'''class TemplateDefinition:
    """Basic template definition for {error.template_id}"""
    
    def get_complete_configuration(self):
        """Return complete template configuration for project cloning"""
        return {{
            'name': '{error.template_id.replace("-", " ").title()}',
            'template_type': '{error.template_id}',
            'description': 'Template: {error.template_id}',
            'instructions': 'Upload documents for analysis.',
            'suggested_questions': [
                'What are the key themes in this document?',
                'Can you summarize the main points?'
            ],
            'required_fields': ['document_upload'],
            'analysis_focus': 'Document analysis',
            'icon_class': 'fa-file-alt',
            'color_theme': 'oxford-blue',
            'has_navigation': False,
            'total_pages': 1,
            'navigation_pages': [],
            'processing_capabilities': {{
                'supports_ai_analysis': True,
                'supports_vector_search': True,
                'max_file_size': 10485760,
                'supported_formats': ['pdf', 'doc', 'docx', 'txt']
            }},
            'validation_rules': {{
                'required_fields': ['document_upload'],
                'max_documents': 50,
                'allowed_file_types': ['pdf', 'doc', 'docx', 'txt']
            }},
            'ui_configuration': {{
                'layout': 'single_page',
                'theme': 'default',
                'features': {{
                    'drag_drop_upload': True,
                    'real_time_processing': True
                }}
            }}
        }}
'''
                
                with open(definition_file, 'w') as f:
                    f.write(basic_definition)
                
                return {'success': True, 'message': 'Created basic definition file'}
            
            return {'success': True, 'message': 'Definition file exists'}
            
        except Exception as e:
            logger.error(f"Definition recovery failed: {str(e)}")
            return {'success': False, 'message': f'Recovery failed: {str(e)}'}
    
    @classmethod
    def _recover_cache_error(cls, error: TemplateError) -> Dict:
        """Recover from cache errors"""
        try:
            from templates.discovery import TemplateDiscoverySystem
            
            # Force cache refresh
            TemplateDiscoverySystem.discover_templates(force_refresh=True)
            
            return {'success': True, 'message': 'Template cache refreshed'}
            
        except Exception as e:
            logger.error(f"Cache recovery failed: {str(e)}")
            return {'success': False, 'message': f'Recovery failed: {str(e)}'}
    
    @classmethod
    def _recover_permission_error(cls, error: TemplateError) -> Dict:
        """Recover from permission errors"""
        try:
            from templates.discovery import TemplateDiscoverySystem
            
            template_dir = TemplateDiscoverySystem.get_template_definitions_path()
            
            # Check directory permissions
            if not template_dir.exists():
                return {'success': False, 'message': 'Template directory does not exist'}
            
            import os
            if not os.access(template_dir, os.R_OK):
                return {'success': False, 'message': 'No read permission on template directory'}
            
            if not os.access(template_dir, os.W_OK):
                return {'success': False, 'message': 'No write permission on template directory'}
            
            return {'success': True, 'message': 'Permissions appear correct'}
            
        except Exception as e:
            logger.error(f"Permission recovery failed: {str(e)}")
            return {'success': False, 'message': f'Recovery failed: {str(e)}'}
    
    @classmethod
    def get_recent_errors(cls, hours: int = 24) -> List[Dict]:
        """Get recent template errors"""
        try:
            cached_errors = cache.get(cls.ERROR_CACHE_KEY, [])
            
            # Filter by time
            cutoff_time = timezone.now() - timezone.timedelta(hours=hours)
            
            recent_errors = []
            for error_dict in cached_errors:
                error_time = timezone.datetime.fromisoformat(error_dict['timestamp'])
                if error_time >= cutoff_time:
                    recent_errors.append(error_dict)
            
            return recent_errors
            
        except Exception as e:
            logger.error(f"Failed to get recent errors: {str(e)}")
            return []
    
    @classmethod
    def clear_error_cache(cls):
        """Clear the error cache"""
        cache.delete(cls.ERROR_CACHE_KEY)

@contextmanager
def template_error_context(template_id: str = None, operation: str = None):
    """Context manager for template error handling"""
    try:
        yield
    except Exception as e:
        error_type = TemplateErrorType.VALIDATION_ERROR
        
        # Determine error type based on exception
        if 'permission' in str(e).lower():
            error_type = TemplateErrorType.PERMISSION_ERROR
        elif 'security' in str(e).lower():
            error_type = TemplateErrorType.SECURITY_ERROR
        elif 'filesystem' in str(e).lower() or 'file' in str(e).lower():
            error_type = TemplateErrorType.FILESYSTEM_ERROR
        elif 'lock' in str(e).lower() or 'concurrency' in str(e).lower():
            error_type = TemplateErrorType.CONCURRENCY_ERROR
        elif 'metadata' in str(e).lower():
            error_type = TemplateErrorType.METADATA_ERROR
        elif 'definition' in str(e).lower():
            error_type = TemplateErrorType.DEFINITION_ERROR
        elif 'cache' in str(e).lower():
            error_type = TemplateErrorType.CACHE_ERROR
        
        template_error = TemplateError(
            error_type=error_type,
            message=str(e),
            template_id=template_id,
            location=operation,
            exception=e
        )
        
        # Handle error and attempt recovery
        result = TemplateErrorHandler.handle_error(template_error)
        
        # Re-raise if recovery failed
        if not result.get('recovery_result', {}).get('success', False):
            raise
