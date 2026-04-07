"""
Simple Template Duplication Service

Implements practical template duplication with file copying and reference updates
"""

import os
import shutil
import logging
import json
import re
from pathlib import Path
from typing import Dict, List, Any, Tuple
from django.conf import settings
from django.core.exceptions import ValidationError

logger = logging.getLogger('templates.simple_duplication')

class SimpleTemplateDuplicationService:
    """
    Service for practical template duplication with file copying and reference updates
    """
    
    def __init__(self):
        self.templates_root = Path(settings.BASE_DIR) / 'templates' / 'template_definitions'
        self.frontend_root = self._get_frontend_root()
        logger.info("Simple Template Duplication Service initialized")
        
    def _get_frontend_root(self) -> Path:
        """Get frontend root directory"""
        frontend_root = Path(settings.BASE_DIR).parent / 'frontend' / 'my-sveltekit-app' / 'src'
        if not frontend_root.exists():
            logger.warning(f"Frontend root not found at {frontend_root}")
        return frontend_root
    
    def duplicate_template(
        self, 
        source_template_id: str, 
        new_template_id: str,
        new_name: str,
        new_description: str,
        version: str,
        author: str
    ) -> Tuple[bool, List[str]]:
        """
        Duplicate a template with complete file copying and reference updates
        
        Args:
            source_template_id: ID of source template to duplicate
            new_template_id: ID for the new template
            new_name: Display name for new template
            new_description: Description for new template
            version: Version for new template
            author: Author for new template
            
        Returns:
            Tuple of (success, errors)
        """
        logger.info(f"Starting template duplication: {source_template_id} -> {new_template_id}")
        
        errors = []
        
        try:
            # Step 1: Validate inputs
            validation_errors = self._validate_duplication_request(source_template_id, new_template_id)
            if validation_errors:
                return False, validation_errors
            
            # Step 2: Duplicate backend structure
            logger.info("Step 1: Duplicating backend structure")
            backend_success, backend_errors = self._duplicate_backend_structure(
                source_template_id, new_template_id, new_name, new_description, version, author
            )
            
            if not backend_success:
                errors.extend(backend_errors)
                return False, errors
            
            # Step 3: Duplicate frontend structure  
            logger.info("Step 2: Duplicating frontend structure")
            frontend_success, frontend_errors = self._duplicate_frontend_structure(
                source_template_id, new_template_id
            )
            
            if not frontend_success:
                errors.extend(frontend_errors)
                # Cleanup backend on frontend failure
                self._cleanup_backend(new_template_id)
                return False, errors
            
            # Step 4: Update file references
            logger.info("Step 3: Updating file references")
            update_success, update_errors = self._update_file_references(
                source_template_id, new_template_id, new_name, new_description
            )
            
            if not update_success:
                errors.extend(update_errors)
                # Cleanup on failure
                self._cleanup_all(new_template_id)
                return False, errors
            
            logger.info(f"Template duplication completed successfully: {new_template_id}")
            return True, []
            
        except Exception as e:
            error_msg = f"Template duplication failed: {str(e)}"
            logger.error(error_msg)
            
            # Cleanup on exception
            try:
                self._cleanup_all(new_template_id)
            except Exception as cleanup_error:
                logger.error(f"Cleanup failed: {cleanup_error}")
            
            return False, [error_msg]
    
    def _validate_duplication_request(self, source_template_id: str, new_template_id: str) -> List[str]:
        """Validate duplication request"""
        errors = []
        
        # Check source template exists
        source_path = self.templates_root / source_template_id
        if not source_path.exists():
            errors.append(f"Source template '{source_template_id}' not found")
        
        # Check target template doesn't exist
        target_path = self.templates_root / new_template_id
        if target_path.exists():
            errors.append(f"Target template '{new_template_id}' already exists")
        
        # Validate template ID format
        if not re.match(r'^[a-z0-9-]+$', new_template_id):
            errors.append("Template ID must contain only lowercase letters, numbers, and hyphens")
        
        return errors
    
    def _duplicate_backend_structure(
        self, 
        source_template_id: str, 
        new_template_id: str,
        new_name: str,
        new_description: str,
        version: str,
        author: str
    ) -> Tuple[bool, List[str]]:
        """Duplicate backend template structure"""
        try:
            source_path = self.templates_root / source_template_id
            target_path = self.templates_root / new_template_id
            
            logger.info(f"Copying backend structure: {source_path} -> {target_path}")
            
            # Copy entire directory structure
            shutil.copytree(source_path, target_path)
            
            # Update metadata.json if exists
            metadata_file = target_path / 'metadata.json'
            if metadata_file.exists():
                with open(metadata_file, 'r', encoding='utf-8') as f:
                    metadata = json.load(f)
                
                # Update metadata with new template info
                metadata.update({
                    'template_id': new_template_id,
                    'name': new_name,
                    'description': new_description,
                    'version': version,
                    'author': author,
                    'created_date': '2025-07-21'  # Current date
                })
                
                with open(metadata_file, 'w', encoding='utf-8') as f:
                    json.dump(metadata, f, indent=2)
                
                logger.info("Updated metadata.json")
            
            logger.info("Backend structure duplicated successfully")
            return True, []
            
        except Exception as e:
            error_msg = f"Backend duplication failed: {str(e)}"
            logger.error(error_msg)
            return False, [error_msg]
    
    def _duplicate_frontend_structure(
        self, 
        source_template_id: str, 
        new_template_id: str
    ) -> Tuple[bool, List[str]]:
        """Duplicate frontend template structure"""
        try:
            # Duplicate frontend routes if they exist
            source_routes = self.frontend_root / 'routes' / 'features' / source_template_id
            target_routes = self.frontend_root / 'routes' / 'features' / new_template_id
            
            if source_routes.exists():
                logger.info(f"Copying frontend routes: {source_routes} -> {target_routes}")
                shutil.copytree(source_routes, target_routes)
                logger.info("Frontend routes duplicated successfully")
            else:
                logger.info("No frontend routes found to duplicate")
            
            # Duplicate template library if it exists
            source_lib = self.frontend_root / 'lib' / 'templates' / source_template_id
            target_lib = self.frontend_root / 'lib' / 'templates' / new_template_id
            
            if source_lib.exists():
                logger.info(f"Copying template library: {source_lib} -> {target_lib}")
                shutil.copytree(source_lib, target_lib)
                logger.info("Template library duplicated successfully")
            else:
                logger.info("No template library found to duplicate")
            
            return True, []
            
        except Exception as e:
            error_msg = f"Frontend duplication failed: {str(e)}"
            logger.error(error_msg)
            return False, [error_msg]
    
    def _update_file_references(
        self, 
        source_template_id: str, 
        new_template_id: str,
        new_name: str,
        new_description: str
    ) -> Tuple[bool, List[str]]:
        """Update file references in all duplicated files"""
        try:
            target_path = self.templates_root / new_template_id
            
            # Files to update in backend
            backend_files = [
                'definition.py',
                'views.py',
                'serializers.py',
                'urls.py',
                'services.py',
                'hierarchical_config.py'
            ]
            
            logger.info("Updating backend file references")
            for file_name in backend_files:
                file_path = target_path / file_name
                if file_path.exists():
                    self._update_file_content(file_path, source_template_id, new_template_id, new_name)
            
            # Update frontend files
            logger.info("Updating frontend file references")
            
            # Update frontend routes
            frontend_routes = self.frontend_root / 'routes' / 'features' / new_template_id
            if frontend_routes.exists():
                for file_path in frontend_routes.rglob('*.svelte'):
                    self._update_file_content(file_path, source_template_id, new_template_id, new_name)
                for file_path in frontend_routes.rglob('*.ts'):
                    self._update_file_content(file_path, source_template_id, new_template_id, new_name)
            
            # Update frontend library
            frontend_lib = self.frontend_root / 'lib' / 'templates' / new_template_id
            if frontend_lib.exists():
                for file_path in frontend_lib.rglob('*.ts'):
                    self._update_file_content(file_path, source_template_id, new_template_id, new_name)
            
            logger.info("File references updated successfully")
            return True, []
            
        except Exception as e:
            error_msg = f"File reference updates failed: {str(e)}"
            logger.error(error_msg)
            return False, [error_msg]
    
    def _update_file_content(
        self, 
        file_path: Path, 
        source_template_id: str, 
        new_template_id: str,
        new_name: str
    ):
        """Update content of a specific file"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            original_content = content
            
            # Replace template ID references
            content = content.replace(source_template_id, new_template_id)
            
            # Replace class names (convert kebab-case to PascalCase)
            source_class_name = self._to_class_name(source_template_id)
            new_class_name = self._to_class_name(new_template_id)
            content = content.replace(source_class_name, new_class_name)
            
            # Replace API endpoint references
            content = content.replace(f'/api/templates/{source_template_id}/', f'/api/templates/{new_template_id}/')
            content = content.replace(f'templates/{source_template_id}', f'templates/{new_template_id}')
            
            # Replace import paths
            content = content.replace(
                f'lib/templates/{source_template_id}',
                f'lib/templates/{new_template_id}'
            )
            
            # Only write if content changed
            if content != original_content:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                logger.debug(f"Updated references in {file_path.name}")
            
        except Exception as e:
            logger.error(f"Failed to update file {file_path}: {str(e)}")
            raise
    
    def _to_class_name(self, template_id: str) -> str:
        """Convert template ID to class name format (PascalCase)"""
        # Convert kebab-case to PascalCase
        parts = template_id.split('-')
        return ''.join(word.capitalize() for word in parts)
    
    def _cleanup_backend(self, template_id: str):
        """Cleanup backend files on failure"""
        try:
            backend_path = self.templates_root / template_id
            if backend_path.exists():
                shutil.rmtree(backend_path)
                logger.info(f"Cleaned up backend directory: {backend_path}")
        except Exception as e:
            logger.error(f"Backend cleanup failed: {e}")
    
    def _cleanup_frontend(self, template_id: str):
        """Cleanup frontend files on failure"""
        try:
            # Cleanup routes
            routes_path = self.frontend_root / 'routes' / 'features' / template_id
            if routes_path.exists():
                shutil.rmtree(routes_path)
                logger.info(f"Cleaned up frontend routes: {routes_path}")
            
            # Cleanup library
            lib_path = self.frontend_root / 'lib' / 'templates' / template_id
            if lib_path.exists():
                shutil.rmtree(lib_path)
                logger.info(f"Cleaned up frontend library: {lib_path}")
        except Exception as e:
            logger.error(f"Frontend cleanup failed: {e}")
    
    def _cleanup_all(self, template_id: str):
        """Cleanup all files on failure"""
        self._cleanup_backend(template_id)
        self._cleanup_frontend(template_id)
        logger.info(f"Complete cleanup performed for template: {template_id}")
    
    def get_available_templates(self) -> List[Dict[str, Any]]:
        """Get list of available templates for duplication"""
        templates = []
        
        try:
            if not self.templates_root.exists():
                logger.warning(f"Templates directory not found: {self.templates_root}")
                return templates
            
            for template_dir in self.templates_root.iterdir():
                if template_dir.is_dir() and not template_dir.name.startswith('.'):
                    template_info = self._get_template_info(template_dir)
                    if template_info:
                        templates.append(template_info)
            
            logger.info(f"Found {len(templates)} available templates")
            return templates
            
        except Exception as e:
            logger.error(f"Failed to get available templates: {str(e)}")
            return templates
    
    def _get_template_info(self, template_dir: Path) -> Dict[str, Any]:
        """Get template information from directory"""
        try:
            template_id = template_dir.name
            
            # Try to get metadata from metadata.json
            metadata_file = template_dir / 'metadata.json'
            if metadata_file.exists():
                with open(metadata_file, 'r', encoding='utf-8') as f:
                    metadata = json.load(f)
                
                return {
                    'id': template_id,
                    'name': metadata.get('name', template_id.replace('-', ' ').title()),
                    'description': metadata.get('description', f'Template for {template_id}'),
                    'version': metadata.get('version', '1.0.0'),
                    'author': metadata.get('author', 'Unknown'),
                    'created_date': metadata.get('created_date'),
                    'template_type': metadata.get('template_type', template_id),
                    'icon_class': metadata.get('ui_assets', {}).get('icon', 'fa-file-alt'),
                    'color_theme': metadata.get('color_theme', 'oxford-blue')
                }
            
            # Fallback to directory name
            return {
                'id': template_id,
                'name': template_id.replace('-', ' ').title(),
                'description': f'Template for {template_id}',
                'version': '1.0.0',
                'author': 'Unknown',
                'template_type': template_id,
                'icon_class': 'fa-file-alt',
                'color_theme': 'oxford-blue'
            }
            
        except Exception as e:
            logger.error(f"Failed to get template info for {template_dir.name}: {str(e)}")
            return None
