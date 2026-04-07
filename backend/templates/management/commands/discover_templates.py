from django.core.management.base import BaseCommand
from templates.discovery import TemplateDiscoverySystem, TemplateValidator


class Command(BaseCommand):
    help = 'Discover templates from filesystem'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--force-refresh',
            action='store_true',
            help='Force refresh of template cache'
        )
        parser.add_argument(
            '--validate',
            action='store_true',
            help='Validate discovered templates'
        )
    
    def handle(self, *args, **options):
        force_refresh = options['force_refresh']
        validate = options['validate']
        
        self.stdout.write('Discovering templates from filesystem...')
        
        templates = TemplateDiscoverySystem.discover_templates(force_refresh=force_refresh)
        
        if not templates:
            self.stdout.write(self.style.WARNING('No templates found'))
            return
        
        self.stdout.write(self.style.SUCCESS(f'Discovered {len(templates)} templates:'))
        
        for template_id, template_info in templates.items():
            metadata = template_info.get('metadata', {})
            name = metadata.get('name', template_id)
            version = metadata.get('version', 'unknown')
            
            self.stdout.write(f'  - {template_id}: {name} (v{version})')
            
            if validate:
                from pathlib import Path
                template_dir = Path(template_info['folder_path'])
                validation_result = TemplateValidator.validate_template_directory(template_dir)
                
                if validation_result['valid']:
                    self.stdout.write(f'    ✓ Valid template')
                else:
                    self.stdout.write(f'    ✗ Validation errors:')
                    for error in validation_result['errors']:
                        self.stdout.write(f'      - {error}')
        
        if validate:
            self.stdout.write('\nValidation complete.')
        else:
            self.stdout.write('\nDiscovery complete. Use --validate to check template integrity.')
