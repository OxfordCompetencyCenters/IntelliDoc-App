import json
import shutil
from pathlib import Path
from django.core.management.base import BaseCommand, CommandError
from templates.discovery import TemplateDiscoverySystem, TemplateValidator


class Command(BaseCommand):
    help = 'Duplicate an existing template'
    
    def add_arguments(self, parser):
        parser.add_argument('source_template', type=str, help='Source template ID to duplicate')
        parser.add_argument('new_template_id', type=str, help='New template ID')
        parser.add_argument('--name', type=str, help='New template name')
        parser.add_argument('--description', type=str, help='New template description')
        parser.add_argument('--author', type=str, help='New template author')
    
    def handle(self, *args, **options):
        source_template = options['source_template']
        new_template_id = options['new_template_id']
        new_name = options.get('name')
        new_description = options.get('description')
        new_author = options.get('author')
        
        self.stdout.write(f'Duplicating template: {source_template} -> {new_template_id}')
        
        # Get template definitions path
        template_dir = TemplateDiscoverySystem.get_template_definitions_path()
        source_dir = template_dir / source_template
        target_dir = template_dir / new_template_id
        
        # Validate source template
        if not source_dir.exists():
            raise CommandError(f'Source template not found: {source_template}')
        
        validation_result = TemplateValidator.validate_template_directory(source_dir)
        if not validation_result['valid']:
            raise CommandError(f'Source template is invalid: {validation_result["errors"]}')
        
        # Check target doesn't exist
        if target_dir.exists():
            raise CommandError(f'Target template already exists: {new_template_id}')
        
        try:
            # Copy template directory
            self.stdout.write('Copying template files...')
            shutil.copytree(source_dir, target_dir)
            
            # Update metadata
            self.stdout.write('Updating metadata...')
            metadata_file = target_dir / 'metadata.json'
            
            with open(metadata_file, 'r') as f:
                metadata = json.load(f)
            
            # Update metadata fields
            metadata['template_id'] = new_template_id
            if new_name:
                metadata['name'] = new_name
            if new_description:
                metadata['description'] = new_description
            if new_author:
                metadata['author'] = new_author
            
            # Update version for duplicated template
            metadata['version'] = '1.0.0'
            metadata['created_date'] = '2025-07-16'
            
            with open(metadata_file, 'w') as f:
                json.dump(metadata, f, indent=2)
            
            # Validate duplicated template
            self.stdout.write('Validating duplicated template...')
            validation_result = TemplateValidator.validate_template_directory(target_dir)
            
            if not validation_result['valid']:
                # Clean up if validation fails
                shutil.rmtree(target_dir)
                raise CommandError(f'Duplicated template is invalid: {validation_result["errors"]}')
            
            self.stdout.write(self.style.SUCCESS(f'Template duplicated successfully: {new_template_id}'))
            self.stdout.write(f'Location: {target_dir}')
            
            # Show updated template info
            if new_name or new_description:
                self.stdout.write('Updated template information:')
                if new_name:
                    self.stdout.write(f'  Name: {new_name}')
                if new_description:
                    self.stdout.write(f'  Description: {new_description}')
                if new_author:
                    self.stdout.write(f'  Author: {new_author}')
            
        except Exception as e:
            # Clean up on error
            if target_dir.exists():
                shutil.rmtree(target_dir)
            raise CommandError(f'Error duplicating template: {str(e)}')
