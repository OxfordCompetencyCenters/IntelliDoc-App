from django.core.management.base import BaseCommand
from templates.discovery import TemplateDiscoverySystem


class Command(BaseCommand):
    help = 'List all available templates'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--detailed',
            action='store_true',
            help='Show detailed template information'
        )
    
    def handle(self, *args, **options):
        detailed = options['detailed']
        
        templates = TemplateDiscoverySystem.list_available_templates()
        
        if not templates:
            self.stdout.write(self.style.WARNING('No templates available'))
            return
        
        self.stdout.write(self.style.SUCCESS(f'Available Templates ({len(templates)}):'))
        self.stdout.write('=' * 50)
        
        for template in templates:
            self.stdout.write(f"ID: {template['id']}")
            self.stdout.write(f"Name: {template['name']}")
            self.stdout.write(f"Type: {template['template_type']}")
            
            if detailed:
                self.stdout.write(f"Description: {template['description']}")
                self.stdout.write(f"Version: {template.get('version', 'unknown')}")
                self.stdout.write(f"Author: {template.get('author', 'unknown')}")
                self.stdout.write(f"Icon: {template['icon_class']}")
                self.stdout.write(f"Source: {template['source']}")
                
                features = template.get('features', {})
                if features:
                    self.stdout.write("Features:")
                    for feature, enabled in features.items():
                        status = "✓" if enabled else "✗"
                        self.stdout.write(f"  {status} {feature}")
            
            self.stdout.write('-' * 30)
