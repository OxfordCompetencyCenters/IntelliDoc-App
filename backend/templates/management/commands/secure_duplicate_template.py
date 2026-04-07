from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from pathlib import Path
from templates.security import TemplateSecurityManager, TemplateOperationManager
from templates.discovery import TemplateDiscoverySystem
import json
import logging

logger = logging.getLogger(__name__)
User = get_user_model()

class Command(BaseCommand):
    help = 'Securely duplicate a template with validation'
    
    def add_arguments(self, parser):
        parser.add_argument(
            'source_template',
            type=str,
            help='Source template ID to duplicate'
        )
        parser.add_argument(
            'new_template_id',
            type=str,
            help='New template ID'
        )
        parser.add_argument(
            '--name',
            type=str,
            help='New template name (optional)'
        )
        parser.add_argument(
            '--description',
            type=str,
            help='New template description (optional)'
        )
        parser.add_argument(
            '--author',
            type=str,
            help='New template author (optional)'
        )
        parser.add_argument(
            '--version',
            type=str,
            default='1.0.0',
            help='New template version (default: 1.0.0)'
        )
        parser.add_argument(
            '--user',
            type=str,
            help='User email for operation tracking (uses system user if not provided)'
        )
        parser.add_argument(
            '--skip-validation',
            action='store_true',
            help='Skip validation of source template'
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force duplication even if target exists'
        )
    
    def handle(self, *args, **options):
        source_template = options['source_template']
        new_template_id = options['new_template_id']
        new_name = options['name']
        new_description = options['description']
        new_author = options['author']
        version = options['version']
        user_email = options['user']
        skip_validation = options['skip_validation']
        force = options['force']
        
        # Get user for operation tracking
        if user_email:
            try:
                user = User.objects.get(email=user_email)
            except User.DoesNotExist:
                self.stdout.write(self.style.ERROR(f'❌ User not found: {user_email}'))
                return
        else:
            # Use system user or first admin user
            user = User.objects.filter(is_staff=True).first()
            if not user:
                self.stdout.write(self.style.ERROR('❌ No admin user found for operation tracking'))
                return
        
        self.stdout.write(self.style.SUCCESS('🔄 Starting secure template duplication...'))
        
        # Get template paths
        template_dir = TemplateDiscoverySystem.get_template_definitions_path()
        source_dir = template_dir / source_template
        target_dir = template_dir / new_template_id
        
        # Validate source template exists
        if not source_dir.exists():
            self.stdout.write(self.style.ERROR(f'❌ Source template not found: {source_template}'))
            return
        
        # Check if target exists
        if target_dir.exists() and not force:
            self.stdout.write(self.style.ERROR(f'❌ Target template already exists: {new_template_id}'))
            self.stdout.write(self.style.WARNING('💡 Use --force to override'))
            return
        
        # Validate source template
        if not skip_validation:
            self.stdout.write(f'🔍 Validating source template: {source_template}')
            validation_result = TemplateSecurityManager.validate_template_directory(source_dir)
            
            if not validation_result['valid']:
                self.stdout.write(self.style.ERROR(f'❌ Source template validation failed:'))
                for error in validation_result['errors']:
                    self.stdout.write(self.style.ERROR(f'   • {error}'))
                
                self.stdout.write(self.style.WARNING('💡 Use --skip-validation to bypass'))
                return
            
            self.stdout.write(self.style.SUCCESS(f'✅ Source template validated'))
        
        # Prepare metadata updates
        metadata_updates = {
            'version': version
        }
        
        if new_name:
            metadata_updates['name'] = new_name
        if new_description:
            metadata_updates['description'] = new_description
        if new_author:
            metadata_updates['author'] = new_author
        
        # Use concurrency manager for safe duplication
        try:
            with TemplateOperationManager.template_operation(
                'duplicate', 
                source_template, 
                user, 
                details={
                    'source_template': source_template,
                    'new_template_id': new_template_id,
                    'metadata_updates': metadata_updates
                }
            ) as operation:
                
                self.stdout.write(f'🔒 Acquired lock for template operation')
                
                # Remove target if force is enabled
                if force and target_dir.exists():
                    self.stdout.write(f'⚠️  Removing existing target: {new_template_id}')
                    import shutil
                    shutil.rmtree(target_dir)
                
                # Perform secure duplication
                self.stdout.write(f'📋 Duplicating template: {source_template} → {new_template_id}')
                
                success, errors = TemplateSecurityManager.safe_duplicate_template(
                    source_dir=source_dir,
                    target_dir=target_dir,
                    new_template_id=new_template_id,
                    metadata_updates=metadata_updates
                )
                
                if success:
                    self.stdout.write(self.style.SUCCESS(f'✅ Template duplicated successfully'))
                    
                    # Validate duplicated template
                    self.stdout.write(f'🔍 Validating duplicated template...')
                    validation_result = TemplateSecurityManager.validate_template_directory(target_dir)
                    
                    if validation_result['valid']:
                        self.stdout.write(self.style.SUCCESS(f'✅ Duplicated template validated'))
                    else:
                        self.stdout.write(self.style.WARNING(f'⚠️  Duplicated template has validation issues:'))
                        for error in validation_result['errors']:
                            self.stdout.write(self.style.WARNING(f'   • {error}'))
                    
                    # Show summary
                    self.show_duplication_summary(source_template, new_template_id, target_dir)
                    
                else:
                    self.stdout.write(self.style.ERROR(f'❌ Template duplication failed:'))
                    for error in errors:
                        self.stdout.write(self.style.ERROR(f'   • {error}'))
                    
                    # Clean up failed duplication
                    if target_dir.exists():
                        import shutil
                        shutil.rmtree(target_dir)
                        self.stdout.write(f'🧹 Cleaned up failed duplication')
                    
                    raise Exception(f'Duplication failed: {"; ".join(errors)}')
        
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'❌ Operation failed: {str(e)}'))
            logger.error(f'Template duplication failed: {str(e)}')
    
    def show_duplication_summary(self, source_template, new_template_id, target_dir):
        """Show duplication summary"""
        self.stdout.write('\n' + '='*60)
        self.stdout.write(self.style.SUCCESS(f'📊 DUPLICATION SUMMARY'))
        self.stdout.write('='*60)
        
        # Load metadata
        try:
            metadata_file = target_dir / 'metadata.json'
            if metadata_file.exists():
                with open(metadata_file, 'r') as f:
                    metadata = json.load(f)
                
                self.stdout.write(f'Source template: {source_template}')
                self.stdout.write(f'New template ID: {new_template_id}')
                self.stdout.write(f'Name: {metadata.get("name", "N/A")}')
                self.stdout.write(f'Description: {metadata.get("description", "N/A")}')
                self.stdout.write(f'Version: {metadata.get("version", "N/A")}')
                self.stdout.write(f'Author: {metadata.get("author", "N/A")}')
                self.stdout.write(f'Location: {target_dir}')
                
                # Count files
                file_count = len(list(target_dir.rglob('*')))
                self.stdout.write(f'Files created: {file_count}')
                
                # Calculate size
                total_size = sum(f.stat().st_size for f in target_dir.rglob('*') if f.is_file())
                size_mb = total_size / (1024 * 1024)
                self.stdout.write(f'Total size: {size_mb:.2f} MB')
                
        except Exception as e:
            self.stdout.write(self.style.WARNING(f'⚠️  Could not load metadata: {str(e)}'))
        
        self.stdout.write('\n✨ Template duplication completed successfully!')
        self.stdout.write(self.style.SUCCESS('💡 The new template is now available for use'))
