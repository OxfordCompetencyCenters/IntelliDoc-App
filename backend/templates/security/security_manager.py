import os
import json
import shutil
import tempfile
import hashlib
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Set
from django.conf import settings
from django.core.exceptions import ValidationError
import logging

logger = logging.getLogger(__name__)

class TemplateSecurityManager:
    """Handles secure template operations with comprehensive validation"""
    
    # Security constraints
    MAX_TEMPLATE_SIZE = 50 * 1024 * 1024  # 50MB
    MAX_FILES_PER_TEMPLATE = 100
    ALLOWED_EXTENSIONS = {'.py', '.json', '.md', '.txt', '.css', '.js', '.html', '.yml', '.yaml'}
    BLOCKED_FILENAMES = {'__pycache__', '.git', 'node_modules', '.DS_Store', 'thumbs.db'}
    BLOCKED_EXTENSIONS = {'.exe', '.bat', '.cmd', '.sh', '.ps1', '.vbs', '.scr', '.com', '.pif'}
    
    # Dangerous patterns in Python files
    DANGEROUS_PATTERNS = [
        'import os',
        'import sys', 
        'import subprocess',
        'exec(',
        'eval(',
        '__import__',
        'open(',
        'file(',
        'input(',
        'raw_input(',
        'getattr(',
        'setattr(',
        'delattr(',
        'hasattr('
    ]
    
    @classmethod
    def validate_template_directory(cls, template_dir: Path) -> Dict:
        """Comprehensive validation of template directory"""
        results = []
        
        try:
            # Check if directory exists
            if not template_dir.exists():
                return {'valid': False, 'errors': [f'Template directory does not exist: {template_dir}']}
            
            # Check directory size
            total_size = cls._calculate_directory_size(template_dir)
            if total_size > cls.MAX_TEMPLATE_SIZE:
                size_mb = total_size / (1024 * 1024)
                results.append(f'Template directory too large: {size_mb:.2f}MB (max: {cls.MAX_TEMPLATE_SIZE / (1024 * 1024):.2f}MB)')
            
            # Check file count
            file_count = cls._count_files_in_directory(template_dir)
            if file_count > cls.MAX_FILES_PER_TEMPLATE:
                results.append(f'Too many files in template: {file_count} (max: {cls.MAX_FILES_PER_TEMPLATE})')
            
            # Validate file structure
            structure_errors = cls._validate_file_structure(template_dir)
            results.extend(structure_errors)
            
            # Validate file security
            security_errors = cls._validate_file_security(template_dir)
            results.extend(security_errors)
            
            # Validate metadata
            metadata_errors = cls._validate_metadata_security(template_dir)
            results.extend(metadata_errors)
            
            # Validate Python files
            python_errors = cls._validate_python_files(template_dir)
            results.extend(python_errors)
            
        except Exception as e:
            logger.error(f"Error validating template directory {template_dir}: {str(e)}")
            results.append(f'Validation error: {str(e)}')
        
        return {'valid': len(results) == 0, 'errors': results}
    
    @classmethod
    def safe_duplicate_template(cls, source_dir: Path, target_dir: Path, 
                               new_template_id: str, metadata_updates: Dict) -> Tuple[bool, List[str]]:
        """Safely duplicate a template with security validation"""
        try:
            # Validate source template
            source_validation = cls.validate_template_directory(source_dir)
            if not source_validation['valid']:
                return False, source_validation['errors']
            
            # Check if target already exists
            if target_dir.exists():
                return False, [f'Target template already exists: {new_template_id}']
            
            # Validate new template ID
            if not cls._validate_template_id(new_template_id):
                return False, [f'Invalid template ID: {new_template_id}']
            
            # Create temporary staging area
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_target = Path(temp_dir) / new_template_id
                
                # Copy with security filters
                cls._safe_copy_tree(source_dir, temp_target)
                
                # Update metadata safely
                metadata_success, metadata_errors = cls._update_template_metadata(
                    temp_target / 'metadata.json', 
                    new_template_id, 
                    metadata_updates
                )
                
                if not metadata_success:
                    return False, metadata_errors
                
                # Validate duplicated template
                duplicate_validation = cls.validate_template_directory(temp_target)
                if not duplicate_validation['valid']:
                    return False, duplicate_validation['errors']
                
                # Atomic move to final location
                shutil.move(str(temp_target), str(target_dir))
                
            logger.info(f"Successfully duplicated template {source_dir.name} to {new_template_id}")
            return True, []
            
        except Exception as e:
            logger.error(f"Error duplicating template: {str(e)}")
            return False, [f'Duplication error: {str(e)}']
    
    @classmethod
    def _calculate_directory_size(cls, directory: Path) -> int:
        """Calculate total size of directory in bytes"""
        total_size = 0
        for dirpath, dirnames, filenames in os.walk(directory):
            for filename in filenames:
                filepath = Path(dirpath) / filename
                try:
                    total_size += filepath.stat().st_size
                except (OSError, IOError):
                    pass
        return total_size
    
    @classmethod
    def _count_files_in_directory(cls, directory: Path) -> int:
        """Count total number of files in directory"""
        count = 0
        for dirpath, dirnames, filenames in os.walk(directory):
            count += len(filenames)
        return count
    
    @classmethod
    def _validate_file_structure(cls, template_dir: Path) -> List[str]:
        """Validate required file structure"""
        errors = []
        
        # Check required files
        required_files = ['metadata.json', 'definition.py', '__init__.py']
        for required_file in required_files:
            if not (template_dir / required_file).exists():
                errors.append(f'Missing required file: {required_file}')
        
        return errors
    
    @classmethod
    def _validate_file_security(cls, template_dir: Path) -> List[str]:
        """Validate file security constraints"""
        errors = []
        
        for root, dirs, files in os.walk(template_dir):
            # Filter out blocked directories
            dirs[:] = [d for d in dirs if d not in cls.BLOCKED_FILENAMES]
            
            for filename in files:
                filepath = Path(root) / filename
                
                # Check blocked filenames
                if filename in cls.BLOCKED_FILENAMES:
                    errors.append(f'Blocked filename: {filename}')
                    continue
                
                # Check file extensions
                file_ext = filepath.suffix.lower()
                if file_ext in cls.BLOCKED_EXTENSIONS:
                    errors.append(f'Blocked file extension: {filename}')
                    continue
                
                if file_ext and file_ext not in cls.ALLOWED_EXTENSIONS:
                    errors.append(f'Disallowed file extension: {filename}')
                    continue
                
                # Check file size
                try:
                    file_size = filepath.stat().st_size
                    if file_size > 5 * 1024 * 1024:  # 5MB per file
                        errors.append(f'File too large: {filename} ({file_size / (1024*1024):.2f}MB)')
                except (OSError, IOError):
                    errors.append(f'Cannot access file: {filename}')
        
        return errors
    
    @classmethod
    def _validate_metadata_security(cls, template_dir: Path) -> List[str]:
        """Validate metadata.json security"""
        errors = []
        metadata_file = template_dir / 'metadata.json'
        
        if not metadata_file.exists():
            return ['Missing metadata.json file']
        
        try:
            with open(metadata_file, 'r') as f:
                metadata = json.load(f)
            
            # Check required fields
            required_fields = ['template_id', 'template_type', 'name', 'description', 'definition_class']
            for field in required_fields:
                if field not in metadata:
                    errors.append(f'Missing required metadata field: {field}')
            
            # Validate template_id format
            if 'template_id' in metadata:
                if not isinstance(metadata['template_id'], str) or not metadata['template_id'].strip():
                    errors.append('Invalid template_id format')
                elif not metadata['template_id'].replace('-', '').replace('_', '').isalnum():
                    errors.append('template_id must contain only alphanumeric characters, hyphens, and underscores')
            
            # Validate definition_class
            if 'definition_class' in metadata:
                if not isinstance(metadata['definition_class'], str) or not metadata['definition_class'].strip():
                    errors.append('Invalid definition_class format')
                elif not metadata['definition_class'].replace('_', '').isalnum():
                    errors.append('definition_class must be a valid Python class name')
            
            # Check for dangerous metadata values
            dangerous_keys = ['__import__', 'exec', 'eval', 'open', 'file']
            for key, value in metadata.items():
                if isinstance(value, str):
                    for dangerous_key in dangerous_keys:
                        if dangerous_key in value:
                            errors.append(f'Potentially dangerous content in metadata field: {key}')
        
        except json.JSONDecodeError as e:
            errors.append(f'Invalid JSON in metadata.json: {str(e)}')
        except Exception as e:
            errors.append(f'Error reading metadata.json: {str(e)}')
        
        return errors
    
    @classmethod
    def _validate_python_files(cls, template_dir: Path) -> List[str]:
        """Validate Python files for security"""
        errors = []
        
        for root, dirs, files in os.walk(template_dir):
            for filename in files:
                if filename.endswith('.py'):
                    filepath = Path(root) / filename
                    
                    try:
                        with open(filepath, 'r', encoding='utf-8') as f:
                            content = f.read()
                        
                        # Check for dangerous patterns
                        for pattern in cls.DANGEROUS_PATTERNS:
                            if pattern in content:
                                errors.append(f'Potentially dangerous code in {filename}: {pattern}')
                        
                        # Check for obvious shell commands
                        shell_patterns = ['os.system', 'subprocess.', 'commands.', 'popen']
                        for pattern in shell_patterns:
                            if pattern in content:
                                errors.append(f'Shell command detected in {filename}: {pattern}')
                        
                        # Basic syntax validation
                        try:
                            compile(content, filepath, 'exec')
                        except SyntaxError as e:
                            errors.append(f'Syntax error in {filename}: {str(e)}')
                    
                    except Exception as e:
                        errors.append(f'Error reading Python file {filename}: {str(e)}')
        
        return errors
    
    @classmethod
    def _validate_template_id(cls, template_id: str) -> bool:
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
    
    @classmethod
    def _safe_copy_tree(cls, source: Path, target: Path):
        """Safely copy directory tree with security filters"""
        def ignore_patterns(dir_path, names):
            ignored = []
            for name in names:
                # Ignore blocked filenames
                if name in cls.BLOCKED_FILENAMES:
                    ignored.append(name)
                    continue
                
                # Ignore files with blocked extensions
                if any(name.endswith(ext) for ext in cls.BLOCKED_EXTENSIONS):
                    ignored.append(name)
                    continue
                
                # For files, check allowed extensions
                if '.' in name and not os.path.isdir(os.path.join(dir_path, name)):
                    file_ext = Path(name).suffix.lower()
                    if file_ext and file_ext not in cls.ALLOWED_EXTENSIONS:
                        ignored.append(name)
            
            return ignored
        
        shutil.copytree(source, target, ignore=ignore_patterns)
    
    @classmethod
    def _update_template_metadata(cls, metadata_file: Path, new_template_id: str, 
                                 updates: Dict) -> Tuple[bool, List[str]]:
        """Safely update template metadata"""
        try:
            # Read existing metadata
            with open(metadata_file, 'r') as f:
                metadata = json.load(f)
            
            # Update template_id
            metadata['template_id'] = new_template_id
            
            # Apply safe updates
            safe_fields = ['name', 'description', 'author', 'version']
            for field in safe_fields:
                if field in updates and updates[field]:
                    metadata[field] = str(updates[field]).strip()
            
            # Validate updated metadata
            if not cls._validate_metadata_content(metadata):
                return False, ['Invalid metadata content after update']
            
            # Write updated metadata
            with open(metadata_file, 'w') as f:
                json.dump(metadata, f, indent=2, sort_keys=True)
            
            return True, []
            
        except Exception as e:
            logger.error(f"Error updating metadata: {str(e)}")
            return False, [f'Metadata update error: {str(e)}']
    
    @classmethod
    def _validate_metadata_content(cls, metadata: Dict) -> bool:
        """Validate metadata content structure"""
        required_fields = ['template_id', 'template_type', 'name', 'description', 'definition_class']
        
        for field in required_fields:
            if field not in metadata:
                return False
            if not isinstance(metadata[field], str) or not metadata[field].strip():
                return False
        
        return True
