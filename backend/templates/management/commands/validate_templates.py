from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from pathlib import Path
from templates.security import TemplateSecurityManager, TemplateValidator
from templates.discovery import TemplateDiscoverySystem
import json
import logging

logger = logging.getLogger(__name__)
User = get_user_model()

class Command(BaseCommand):
    help = 'Validate template security and integrity'
    
    def add_arguments(self, parser):
        parser.add_argument(
            'template_id',
            nargs='?',
            type=str,
            help='Template ID to validate (if not provided, validates all templates)'
        )
        parser.add_argument(
            '--level',
            type=str,
            choices=['basic', 'detailed', 'comprehensive'],
            default='comprehensive',
            help='Validation level (default: comprehensive)'
        )
        parser.add_argument(
            '--security-only',
            action='store_true',
            help='Only run security validation'
        )
        parser.add_argument(
            '--fix-issues',
            action='store_true',
            help='Attempt to fix found issues automatically'
        )
        parser.add_argument(
            '--output-format',
            type=str,
            choices=['text', 'json'],
            default='text',
            help='Output format (default: text)'
        )
    
    def handle(self, *args, **options):
        template_id = options['template_id']
        validation_level = options['level']
        security_only = options['security_only']
        fix_issues = options['fix_issues']
        output_format = options['output_format']
        
        self.stdout.write(self.style.SUCCESS('🔍 Starting template validation...'))
        
        if template_id:
            # Validate specific template
            self.validate_single_template(template_id, validation_level, security_only, fix_issues, output_format)
        else:
            # Validate all templates
            self.validate_all_templates(validation_level, security_only, fix_issues, output_format)
    
    def validate_single_template(self, template_id, validation_level, security_only, fix_issues, output_format):
        """Validate a single template"""
        template_dir = TemplateDiscoverySystem.get_template_definitions_path() / template_id
        
        if not template_dir.exists():
            self.stdout.write(self.style.ERROR(f'❌ Template not found: {template_id}'))
            return
        
        self.stdout.write(f'🔍 Validating template: {template_id}')
        
        # Run security validation
        if security_only:
            self.run_security_validation(template_dir, template_id, fix_issues, output_format)
        else:
            self.run_full_validation(template_dir, template_id, validation_level, fix_issues, output_format)
    
    def validate_all_templates(self, validation_level, security_only, fix_issues, output_format):
        """Validate all templates"""
        templates = TemplateDiscoverySystem.discover_templates(force_refresh=True)
        
        if not templates:
            self.stdout.write(self.style.WARNING('⚠️  No templates found'))
            return
        
        self.stdout.write(f'🔍 Validating {len(templates)} templates...')
        
        results = {}
        for template_id in templates.keys():
            template_dir = TemplateDiscoverySystem.get_template_definitions_path() / template_id
            
            if security_only:
                result = self.run_security_validation(template_dir, template_id, fix_issues, output_format)
            else:
                result = self.run_full_validation(template_dir, template_id, validation_level, fix_issues, output_format)
            
            results[template_id] = result
        
        # Summary
        self.print_validation_summary(results, output_format)
    
    def run_security_validation(self, template_dir, template_id, fix_issues, output_format):
        """Run security validation only"""
        try:
            validation_result = TemplateSecurityManager.validate_template_directory(template_dir)
            
            if validation_result['valid']:
                self.stdout.write(self.style.SUCCESS(f'✅ {template_id}: Security validation passed'))
                return {'valid': True, 'errors': [], 'warnings': []}
            else:
                self.stdout.write(self.style.ERROR(f'❌ {template_id}: Security validation failed'))
                
                for error in validation_result['errors']:
                    self.stdout.write(self.style.ERROR(f'   • {error}'))
                
                if fix_issues:
                    self.stdout.write(self.style.WARNING(f'⚙️  Attempting to fix security issues...'))
                    # Implement automatic fixes here
                    self.stdout.write(self.style.WARNING(f'⚠️  Automatic security fixes not implemented yet'))
                
                return {'valid': False, 'errors': validation_result['errors'], 'warnings': []}
        
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'❌ {template_id}: Validation error: {str(e)}'))
            return {'valid': False, 'errors': [str(e)], 'warnings': []}
    
    def run_full_validation(self, template_dir, template_id, validation_level, fix_issues, output_format):
        """Run full validation"""
        try:
            validator = TemplateValidator(template_dir)
            is_valid, results = validator.validate_template(validation_level)
            
            errors = [r for r in results if r.level.value == 'error']
            warnings = [r for r in results if r.level.value == 'warning']
            infos = [r for r in results if r.level.value == 'info']
            
            if is_valid:
                self.stdout.write(self.style.SUCCESS(f'✅ {template_id}: Validation passed'))
            else:
                self.stdout.write(self.style.ERROR(f'❌ {template_id}: Validation failed'))
            
            # Print results
            if output_format == 'text':
                for error in errors:
                    self.stdout.write(self.style.ERROR(f'   ERROR: {error.message}'))
                
                for warning in warnings:
                    self.stdout.write(self.style.WARNING(f'   WARNING: {warning.message}'))
                
                for info in infos:
                    self.stdout.write(f'   INFO: {info.message}')
            
            if fix_issues and (errors or warnings):
                self.stdout.write(self.style.WARNING(f'⚙️  Attempting to fix validation issues...'))
                # Implement automatic fixes here
                self.stdout.write(self.style.WARNING(f'⚠️  Automatic validation fixes not implemented yet'))
            
            return {
                'valid': is_valid,
                'errors': [r.message for r in errors],
                'warnings': [r.message for r in warnings],
                'infos': [r.message for r in infos]
            }
        
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'❌ {template_id}: Validation error: {str(e)}'))
            return {'valid': False, 'errors': [str(e)], 'warnings': []}
    
    def print_validation_summary(self, results, output_format):
        """Print validation summary"""
        if output_format == 'json':
            self.stdout.write(json.dumps(results, indent=2))
            return
        
        # Text summary
        total_templates = len(results)
        valid_templates = sum(1 for r in results.values() if r['valid'])
        invalid_templates = total_templates - valid_templates
        
        self.stdout.write('\n' + '='*60)
        self.stdout.write(self.style.SUCCESS(f'📊 VALIDATION SUMMARY'))
        self.stdout.write('='*60)
        self.stdout.write(f'Total templates: {total_templates}')
        self.stdout.write(self.style.SUCCESS(f'Valid templates: {valid_templates}'))
        
        if invalid_templates > 0:
            self.stdout.write(self.style.ERROR(f'Invalid templates: {invalid_templates}'))
            
            # Show failed templates
            self.stdout.write('\n❌ Failed templates:')
            for template_id, result in results.items():
                if not result['valid']:
                    error_count = len(result['errors'])
                    warning_count = len(result.get('warnings', []))
                    self.stdout.write(f'   • {template_id}: {error_count} errors, {warning_count} warnings')
        
        success_rate = (valid_templates / total_templates) * 100
        self.stdout.write(f'\n✨ Success rate: {success_rate:.1f}%')
