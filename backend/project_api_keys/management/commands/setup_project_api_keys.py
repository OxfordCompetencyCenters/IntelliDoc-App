# backend/project_api_keys/management/commands/setup_project_api_keys.py

"""
Management command for setting up and testing project-specific API keys.
"""

from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model
from cryptography.fernet import Fernet
import os

from users.models import IntelliDocProject, ProjectAPIKey
from project_api_keys.services import get_project_api_key_service
from project_api_keys.encryption import encryption_service

User = get_user_model()

class Command(BaseCommand):
    help = 'Setup and manage project-specific API keys'
    
    def add_arguments(self, parser):
        parser.add_argument(
            'action',
            choices=['generate-key', 'test-encryption', 'list-projects', 'add-key', 'validate-key', 'list-keys'],
            help='Action to perform'
        )
        
        parser.add_argument(
            '--project-id',
            type=str,
            help='Project ID (UUID) for project-specific operations'
        )
        
        parser.add_argument(
            '--provider',
            choices=['openai', 'google', 'anthropic'],
            help='API provider type'
        )
        
        parser.add_argument(
            '--api-key',
            type=str,
            help='API key to add (will be encrypted)'
        )
        
        parser.add_argument(
            '--key-name',
            type=str,
            help='Descriptive name for the API key'
        )
        
        parser.add_argument(
            '--user-email',
            type=str,
            help='Email of user who is adding the key'
        )
        
        parser.add_argument(
            '--validate',
            action='store_true',
            help='Validate the API key with the provider'
        )
    
    def handle(self, *args, **options):
        action = options['action']
        
        try:
            if action == 'generate-key':
                self.generate_encryption_key()
            elif action == 'test-encryption':
                self.test_encryption()
            elif action == 'list-projects':
                self.list_projects()
            elif action == 'add-key':
                self.add_api_key(options)
            elif action == 'validate-key':
                self.validate_api_key(options)
            elif action == 'list-keys':
                self.list_api_keys(options)
            else:
                raise CommandError(f'Unknown action: {action}')
                
        except Exception as e:
            raise CommandError(f'Command failed: {str(e)}')
    
    def generate_encryption_key(self):
        """Generate a new encryption key for PROJECT_API_KEY_ENCRYPTION_KEY"""
        self.stdout.write(
            self.style.WARNING('Generating new encryption key for project API keys...')
        )
        
        key = Fernet.generate_key()
        key_string = key.decode()
        
        self.stdout.write('\n' + '='*70)
        self.stdout.write(self.style.SUCCESS('🔑 ENCRYPTION KEY GENERATED'))
        self.stdout.write('='*70)
        self.stdout.write(f'Add this to your .env file:')
        self.stdout.write(f'PROJECT_API_KEY_ENCRYPTION_KEY={key_string}')
        self.stdout.write('='*70)
        
        # Check if key is already set in environment
        current_key = os.getenv('PROJECT_API_KEY_ENCRYPTION_KEY')
        if current_key:
            self.stdout.write(
                self.style.WARNING('\n⚠️  WARNING: PROJECT_API_KEY_ENCRYPTION_KEY is already set!')
            )
            self.stdout.write('Changing the encryption key will make existing encrypted API keys unreadable.')
            self.stdout.write('Only change this if you are setting up for the first time.')
        else:
            self.stdout.write(
                self.style.SUCCESS('\n✅ No existing encryption key found. Safe to set this key.')
            )
    
    def test_encryption(self):
        """Test encryption/decryption functionality"""
        self.stdout.write('Testing encryption service...')
        
        try:
            # encryption_service is already instantiated
            
            # Test encryption cycle
            test_key = 'sk-test-api-key-12345'
            test_project_id = 'test-project-uuid'
            
            # Encrypt
            encrypted = encryption_service.encrypt_api_key(test_project_id, test_key)
            self.stdout.write(f'✅ Encryption successful: {len(encrypted)} characters')
            
            # Decrypt
            decrypted = encryption_service.decrypt_api_key(test_project_id, encrypted)
            self.stdout.write(f'✅ Decryption successful: {decrypted == test_key}')
            
            # Validate setup
            is_valid = encryption_service.test_encryption(test_project_id, test_key)
            
            if is_valid:
                self.stdout.write(
                    self.style.SUCCESS('🔐 Encryption service is working correctly!')
                )
            else:
                self.stdout.write(
                    self.style.ERROR('❌ Encryption service validation failed!')
                )
                
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'❌ Encryption test failed: {str(e)}')
            )
            self.stdout.write('Make sure PROJECT_API_KEY_ENCRYPTION_KEY is set in your environment.')
    
    def list_projects(self):
        """List all projects with their API key status"""
        self.stdout.write('📋 Listing all projects and their API key status...\n')
        
        projects = IntelliDocProject.objects.all().select_related('created_by')
        service = get_project_api_key_service()
        
        if not projects:
            self.stdout.write('No projects found.')
            return
        
        for project in projects:
            self.stdout.write(f'🔹 Project: {project.name}')
            self.stdout.write(f'   ID: {project.project_id}')
            self.stdout.write(f'   Owner: {project.created_by.email}')
            self.stdout.write(f'   Created: {project.created_at.strftime("%Y-%m-%d")}')
            
            # Get API key status
            try:
                status = service.get_project_api_keys_status(project)
                providers = status.get('providers', [])
                
                has_keys = any(p['has_key'] for p in providers)
                if has_keys:
                    self.stdout.write('   API Keys:')
                    for provider in providers:
                        if provider['has_key']:
                            status_icon = '✅' if provider['is_validated'] else '⚠️'
                            self.stdout.write(f'     {status_icon} {provider["display_name"]}: {provider["status_display"]}')
                else:
                    self.stdout.write('   API Keys: None configured')
                    
            except Exception as e:
                self.stdout.write(f'   API Keys: Error - {str(e)}')
            
            self.stdout.write('')  # Empty line between projects
    
    def add_api_key(self, options):
        """Add an API key to a project"""
        project_id = options.get('project_id')
        provider = options.get('provider')
        api_key = options.get('api_key')
        key_name = options.get('key_name', '')
        user_email = options.get('user_email')
        validate = options.get('validate', False)
        
        if not all([project_id, provider, api_key, user_email]):
            raise CommandError(
                'Required arguments: --project-id, --provider, --api-key, --user-email'
            )
        
        # Get project and user
        try:
            project = IntelliDocProject.objects.get(project_id=project_id)
        except IntelliDocProject.DoesNotExist:
            raise CommandError(f'Project with ID {project_id} not found')
        
        try:
            user = User.objects.get(email=user_email)
        except User.DoesNotExist:
            raise CommandError(f'User with email {user_email} not found')
        
        self.stdout.write(f'Adding {provider} API key to project "{project.name}"...')
        
        # Add the API key
        service = get_project_api_key_service()
        try:
            api_key_obj, created = service.set_project_api_key(
                project=project,
                provider_type=provider,
                api_key=api_key,
                user=user,
                key_name=key_name,
                validate_key=validate
            )
            
            if created:
                self.stdout.write(
                    self.style.SUCCESS(f'✅ Created new {provider} API key for project')
                )
            else:
                self.stdout.write(
                    self.style.SUCCESS(f'✅ Updated {provider} API key for project')
                )
            
            # Show validation status
            if validate:
                if api_key_obj.is_validated:
                    self.stdout.write(
                        self.style.SUCCESS('✅ API key validation successful')
                    )
                else:
                    self.stdout.write(
                        self.style.WARNING(f'⚠️ API key validation failed: {api_key_obj.validation_error}')
                    )
            else:
                self.stdout.write('ℹ️ API key validation skipped')
                
        except Exception as e:
            raise CommandError(f'Failed to add API key: {str(e)}')
    
    def validate_api_key(self, options):
        """Validate an existing API key"""
        project_id = options.get('project_id')
        provider = options.get('provider')
        
        if not all([project_id, provider]):
            raise CommandError('Required arguments: --project-id, --provider')
        
        try:
            project = IntelliDocProject.objects.get(project_id=project_id)
        except IntelliDocProject.DoesNotExist:
            raise CommandError(f'Project with ID {project_id} not found')
        
        try:
            api_key_obj = ProjectAPIKey.objects.get(
                project=project,
                provider_type=provider
            )
        except ProjectAPIKey.DoesNotExist:
            raise CommandError(f'No {provider} API key found for project')
        
        self.stdout.write(f'Validating {provider} API key for project "{project.name}"...')
        
        service = get_project_api_key_service()
        try:
            result = service.validate_api_key(api_key_obj)
            
            if result['is_valid']:
                self.stdout.write(
                    self.style.SUCCESS(f'✅ API key is valid!')
                )
            else:
                self.stdout.write(
                    self.style.ERROR(f'❌ API key validation failed: {result["error"]}')
                )
                
        except Exception as e:
            raise CommandError(f'Validation error: {str(e)}')
    
    def list_api_keys(self, options):
        """List API keys for a specific project"""
        project_id = options.get('project_id')
        
        if not project_id:
            raise CommandError('Required argument: --project-id')
        
        try:
            project = IntelliDocProject.objects.get(project_id=project_id)
        except IntelliDocProject.DoesNotExist:
            raise CommandError(f'Project with ID {project_id} not found')
        
        self.stdout.write(f'📋 API keys for project "{project.name}":')
        self.stdout.write(f'Project ID: {project.project_id}\n')
        
        service = get_project_api_key_service()
        try:
            status = service.get_project_api_keys_status(project)
            providers = status.get('providers', [])
            
            has_keys = any(p['has_key'] for p in providers)
            
            if not has_keys:
                self.stdout.write('No API keys configured for this project.')
                self.stdout.write('\nTo add an API key, use:')
                self.stdout.write(f'python manage.py setup_project_api_keys add-key --project-id {project_id} --provider openai --api-key sk-... --user-email user@example.com')
                return
            
            for provider in providers:
                icon = '🔑' if provider['has_key'] else '❌'
                self.stdout.write(f'{icon} {provider["display_name"]} ({provider["code"]})')
                
                if provider['has_key']:
                    self.stdout.write(f'   Status: {provider["status_display"]}')
                    self.stdout.write(f'   Key: {provider["masked_key"]}')
                    self.stdout.write(f'   Usage: {provider["usage_count"]} times')
                    
                    if provider['last_used_at']:
                        self.stdout.write(f'   Last used: {provider["last_used_at"]}')
                    
                    if provider['last_validated_at']:
                        self.stdout.write(f'   Last validated: {provider["last_validated_at"]}')
                    
                    if provider['validation_error']:
                        self.stdout.write(f'   Validation error: {provider["validation_error"]}')
                
                self.stdout.write('')  # Empty line between providers
                
        except Exception as e:
            raise CommandError(f'Failed to list API keys: {str(e)}')
