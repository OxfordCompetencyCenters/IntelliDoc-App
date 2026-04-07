# templates/management/commands/create_templates.py

from django.core.management.base import BaseCommand
from django.utils import timezone
from templates.definitions import (
    LegalTemplateDefinition,
    HistoryTemplateDefinition,
    MedicalTemplateDefinition,
    AICCIntelliDocTemplateDefinition
)


class Command(BaseCommand):
    help = 'Create or update project templates'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--template-type',
            type=str,
            choices=['legal', 'history', 'medical', 'aicc-intellidoc', 'all'],
            default='all',
            help='Specify which template to create/update'
        )
        parser.add_argument(
            '--force-update',
            action='store_true',
            help='Force update existing templates with new data'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be created/updated without making changes'
        )
    
    def handle(self, *args, **options):
        template_type = options['template_type']
        force_update = options['force_update']
        dry_run = options['dry_run']
        
        if dry_run:
            self.stdout.write(
                self.style.WARNING('DRY RUN MODE - No changes will be made')
            )
        
        # Define template definitions
        template_definitions = {
            'legal': LegalTemplateDefinition,
            'history': HistoryTemplateDefinition,
            'medical': MedicalTemplateDefinition,
            'aicc-intellidoc': AICCIntelliDocTemplateDefinition
        }
        
        # Determine which templates to process
        if template_type == 'all':
            templates_to_process = template_definitions.items()
        else:
            templates_to_process = [(template_type, template_definitions[template_type])]
        
        created_count = 0
        updated_count = 0
        
        for template_name, template_definition in templates_to_process:
            if dry_run:
                self.show_template_preview(template_name, template_definition)
            else:
                created, updated = self.create_or_update_template(
                    template_name, 
                    template_definition, 
                    force_update
                )
                if created:
                    created_count += 1
                if updated:
                    updated_count += 1
        
        if not dry_run:
            self.stdout.write(
                self.style.SUCCESS(
                    f'Templates processing completed: {created_count} created, {updated_count} updated'
                )
            )
        
    def show_template_preview(self, template_name, template_definition):
        """Show preview of template without creating it"""
        template_data = template_definition.get_template_data()
        
        self.stdout.write(f'\n--- {template_name.upper()} TEMPLATE PREVIEW ---')
        self.stdout.write(f'Name: {template_data["name"]}')
        self.stdout.write(f'Type: {template_data["template_type"]}')
        self.stdout.write(f'Description: {template_data["description"][:100]}...')
        self.stdout.write(f'Icon: {template_data["icon_class"]}')
        self.stdout.write(f'Color: {template_data["color_theme"]}')
        self.stdout.write(f'Questions: {len(template_data["suggested_questions"])}')
        self.stdout.write(f'Required Fields: {len(template_data["required_fields"])}')
        
        if hasattr(template_definition, 'supports_navigation') and template_definition.supports_navigation():
            self.stdout.write(f'Navigation: Enabled')
        
    def create_or_update_template(self, template_name, template_definition, force_update):
        """Create or update a template"""
        try:
            template, created = template_definition.create_template()
            
            if created:
                self.stdout.write(
                    self.style.SUCCESS(f'✓ Created {template_name} template: {template.name}')
                )
                return True, False
            else:
                if force_update:
                    # Force update existing template
                    template_data = template_definition.get_template_data()
                    updated_fields = []
                    
                    for key, value in template_data.items():
                        if getattr(template, key) != value:
                            setattr(template, key, value)
                            updated_fields.append(key)
                    
                    if updated_fields:
                        template.save()
                        self.stdout.write(
                            self.style.WARNING(
                                f'⚠ Updated {template_name} template: {template.name} '
                                f'(fields: {", ".join(updated_fields)})'
                            )
                        )
                        return False, True
                    else:
                        self.stdout.write(
                            self.style.SUCCESS(f'✓ {template_name} template already up to date: {template.name}')
                        )
                        return False, False
                else:
                    self.stdout.write(
                        self.style.SUCCESS(f'✓ {template_name} template already exists: {template.name}')
                    )
                    return False, False
                    
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'✗ Failed to create {template_name} template: {str(e)}')
            )
            return False, False
    
    def get_template_status(self):
        """Get current template status"""
        from templates.models import ProjectTemplate
        
        templates = ProjectTemplate.objects.all()
        
        self.stdout.write('\n--- CURRENT TEMPLATE STATUS ---')
        for template in templates:
            status = "Active" if template.is_active else "Inactive"
            self.stdout.write(f'{template.name} ({template.template_type}): {status}')
        
        if not templates.exists():
            self.stdout.write('No templates found in database')
