# backend/project_api_keys/tests.py

"""
Tests for project-specific API key management system.
"""

from django.test import TestCase, override_settings
from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase
from rest_framework import status
from unittest.mock import patch, MagicMock
import os

from users.models import IntelliDocProject, ProjectAPIKey
from .services import get_project_api_key_service
from .encryption import get_encryption_service
from .integrations import get_project_api_key_integration

User = get_user_model()

class ProjectAPIKeyEncryptionTests(TestCase):
    """Tests for encryption service"""
    
    def setUp(self):
        self.encryption_service = get_encryption_service()
    
    def test_encryption_decryption_cycle(self):
        """Test that encryption and decryption work correctly"""
        original_key = 'sk-test-api-key-123456789'
        project_id = 'test-project-uuid'
        
        # Encrypt
        encrypted_key = self.encryption_service.encrypt_api_key(original_key, project_id)
        self.assertIsInstance(encrypted_key, str)
        self.assertNotEqual(encrypted_key, original_key)
        
        # Decrypt
        decrypted_key = self.encryption_service.decrypt_api_key(encrypted_key, project_id)
        self.assertEqual(decrypted_key, original_key)
    
    def test_encryption_validation(self):
        """Test encryption setup validation"""
        is_valid = self.encryption_service.validate_encryption_setup()
        self.assertTrue(is_valid)

class ProjectAPIKeyServiceTests(TestCase):
    """Tests for API key service"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )
        
        self.project = IntelliDocProject.objects.create(
            name='Test Project',
            description='Test project for API key management',
            created_by=self.user
        )
        
        self.service = get_project_api_key_service()
    
    def test_set_and_get_api_key(self):
        """Test setting and retrieving an API key"""
        api_key = 'sk-test123456789'
        
        # Set API key
        api_key_obj, created = self.service.set_project_api_key(
            project=self.project,
            provider_type='openai',
            api_key=api_key,
            user=self.user,
            validate_key=False  # Skip validation in tests
        )
        
        self.assertTrue(created)
        self.assertEqual(api_key_obj.provider_type, 'openai')
        self.assertEqual(api_key_obj.project, self.project)
        self.assertEqual(api_key_obj.created_by, self.user)
        
        # Get API key
        retrieved_key = self.service.get_project_api_key(self.project, 'openai')
        self.assertEqual(retrieved_key, api_key)
    
    def test_update_existing_api_key(self):
        """Test updating an existing API key"""
        # Set initial key
        initial_key = 'sk-initial123'
        api_key_obj, created = self.service.set_project_api_key(
            project=self.project,
            provider_type='openai',
            api_key=initial_key,
            user=self.user,
            validate_key=False
        )
        
        self.assertTrue(created)
        
        # Update key
        updated_key = 'sk-updated456'
        api_key_obj, created = self.service.set_project_api_key(
            project=self.project,
            provider_type='openai',
            api_key=updated_key,
            user=self.user,
            validate_key=False
        )
        
        self.assertFalse(created)  # Should be an update, not creation
        
        # Verify updated key
        retrieved_key = self.service.get_project_api_key(self.project, 'openai')
        self.assertEqual(retrieved_key, updated_key)
    
    def test_delete_api_key(self):
        """Test deleting an API key"""
        # Set API key first
        self.service.set_project_api_key(
            project=self.project,
            provider_type='openai',
            api_key='sk-test123',
            user=self.user,
            validate_key=False
        )
        
        # Verify it exists
        retrieved_key = self.service.get_project_api_key(self.project, 'openai')
        self.assertEqual(retrieved_key, 'sk-test123')
        
        # Delete it
        success = self.service.delete_project_api_key(self.project, 'openai')
        self.assertTrue(success)
        
        # Verify it's gone
        retrieved_key = self.service.get_project_api_key(self.project, 'openai')
        self.assertIsNone(retrieved_key)
    
    def test_get_project_api_keys_status(self):
        """Test getting comprehensive status of all API keys"""
        # Set some API keys
        self.service.set_project_api_key(
            project=self.project,
            provider_type='openai',
            api_key='sk-openai123',
            user=self.user,
            key_name='OpenAI Production Key',
            validate_key=False
        )
        
        # Get status
        status = self.service.get_project_api_keys_status(self.project)
        
        self.assertEqual(status['project_id'], str(self.project.project_id))
        self.assertEqual(status['project_name'], self.project.name)
        self.assertIsInstance(status['providers'], list)
        
        # Find OpenAI provider status
        openai_status = next(
            (p for p in status['providers'] if p['code'] == 'openai'),
            None
        )
        
        self.assertIsNotNone(openai_status)
        self.assertTrue(openai_status['has_key'])
        self.assertTrue(openai_status['is_active'])
        self.assertEqual(openai_status['status_display'], 'Not Validated')
    
    def test_available_providers(self):
        """Test getting available providers"""
        providers = self.service.get_available_providers()
        
        self.assertIsInstance(providers, list)
        self.assertGreater(len(providers), 0)
        
        # Check that required providers are present
        provider_codes = [p['code'] for p in providers]
        self.assertIn('openai', provider_codes)
        self.assertIn('google', provider_codes)
        self.assertIn('anthropic', provider_codes)
        
        # Check provider structure
        openai_provider = next(p for p in providers if p['code'] == 'openai')
        self.assertIn('display_name', openai_provider)
        self.assertIn('description', openai_provider)
        self.assertIn('icon', openai_provider)
        self.assertIn('color', openai_provider)

class ProjectAPIKeyIntegrationTests(TestCase):
    """Tests for integration service"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )
        
        self.project = IntelliDocProject.objects.create(
            name='Test Project',
            description='Test project for integration',
            created_by=self.user
        )
        
        self.integration = get_project_api_key_integration()
        self.service = get_project_api_key_service()
    
    def test_validate_project_has_provider(self):
        """Test checking if project has a provider configured"""
        # Initially no provider
        has_openai = self.integration.validate_project_has_provider(self.project, 'openai')
        self.assertFalse(has_openai)
        
        # Add OpenAI key
        self.service.set_project_api_key(
            project=self.project,
            provider_type='openai',
            api_key='sk-test123',
            user=self.user,
            validate_key=False
        )
        
        # Now should have provider
        has_openai = self.integration.validate_project_has_provider(self.project, 'openai')
        self.assertTrue(has_openai)
    
    def test_get_available_providers_for_project(self):
        """Test getting provider availability for specific project"""
        # Add some API keys
        self.service.set_project_api_key(
            project=self.project,
            provider_type='openai',
            api_key='sk-openai123',
            user=self.user,
            validate_key=False
        )
        
        self.service.set_project_api_key(
            project=self.project,
            provider_type='google',
            api_key='AIza-google123',
            user=self.user,
            validate_key=False
        )
        
        # Get availability
        availability = self.integration.get_available_providers_for_project(self.project)
        
        self.assertTrue(availability['openai'])
        self.assertTrue(availability['google'])
        self.assertFalse(availability['anthropic'])  # Not set
    
    def test_get_fallback_message(self):
        """Test fallback message generation"""
        message = self.integration.get_fallback_message(self.project, 'openai')
        
        self.assertIn('OpenAI', message)
        self.assertIn(self.project.name, message)
        self.assertIn('API Management', message)
        self.assertIn('❌', message)

class ProjectAPIKeyAPITests(APITestCase):
    """Tests for API endpoints"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )
        
        self.project = IntelliDocProject.objects.create(
            name='Test Project',
            description='Test project for API testing',
            created_by=self.user
        )
        
        # Authenticate user
        self.client.force_authenticate(user=self.user)
    
    def test_get_available_providers(self):
        """Test GET /api/project-api-keys/providers/"""
        url = '/api/project-api-keys/providers/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        
        self.assertTrue(data['success'])
        self.assertIsInstance(data['providers'], list)
        self.assertGreater(len(data['providers']), 0)
    
    def test_get_project_status(self):
        """Test GET /api/project-api-keys/project/{project_id}/status/"""
        url = f'/api/project-api-keys/project/{self.project.project_id}/status/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        
        self.assertTrue(data['success'])
        self.assertEqual(data['status']['project_id'], str(self.project.project_id))
        self.assertEqual(data['status']['project_name'], self.project.name)
    
    def test_set_api_key(self):
        """Test POST /api/project-api-keys/project/{project_id}/keys/"""
        url = f'/api/project-api-keys/project/{self.project.project_id}/keys/'
        data = {
            'provider_type': 'openai',
            'api_key': 'sk-test123456789',
            'key_name': 'Test Key',
            'validate_key': False  # Skip validation in tests
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = response.json()
        
        self.assertTrue(response_data['success'])
        self.assertTrue(response_data['created'])
        self.assertEqual(response_data['api_key']['provider_type'], 'openai')
    
    def test_list_project_keys(self):
        """Test GET /api/project-api-keys/project/{project_id}/keys/"""
        # Add a key first
        service = get_project_api_key_service()
        service.set_project_api_key(
            project=self.project,
            provider_type='openai',
            api_key='sk-test123',
            user=self.user,
            key_name='Test Key',
            validate_key=False
        )
        
        url = f'/api/project-api-keys/project/{self.project.project_id}/keys/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        
        self.assertTrue(data['success'])
        self.assertEqual(data['count'], 1)
        self.assertIsInstance(data['api_keys'], list)
    
    def test_delete_api_key(self):
        """Test DELETE /api/project-api-keys/project/{project_id}/keys/{provider_type}/"""
        # Add a key first
        service = get_project_api_key_service()
        service.set_project_api_key(
            project=self.project,
            provider_type='openai',
            api_key='sk-test123',
            user=self.user,
            validate_key=False
        )
        
        url = f'/api/project-api-keys/project/{self.project.project_id}/keys/openai/'
        response = self.client.delete(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        
        self.assertTrue(data['success'])
        
        # Verify key is deleted
        retrieved_key = service.get_project_api_key(self.project, 'openai')
        self.assertIsNone(retrieved_key)
    
    def test_unauthorized_access(self):
        """Test that unauthorized users cannot access API keys"""
        # Create another user and project
        other_user = User.objects.create_user(
            email='other@example.com',
            password='otherpass123'
        )
        
        other_project = IntelliDocProject.objects.create(
            name='Other Project',
            created_by=other_user
        )
        
        # Try to access other user's project
        url = f'/api/project-api-keys/project/{other_project.project_id}/status/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

class ProjectAPIKeyModelTests(TestCase):
    """Tests for ProjectAPIKey model"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )
        
        self.project = IntelliDocProject.objects.create(
            name='Test Project',
            created_by=self.user
        )
    
    def test_create_project_api_key(self):
        """Test creating a ProjectAPIKey instance"""
        # Note: In real usage, keys are encrypted by the service
        # Here we test the model structure
        
        api_key = ProjectAPIKey.objects.create(
            project=self.project,
            provider_type='openai',
            encrypted_api_key='encrypted-key-data',
            key_name='Test Key',
            created_by=self.user,
            is_active=True
        )
        
        self.assertEqual(api_key.provider_type, 'openai')
        self.assertEqual(api_key.project, self.project)
        self.assertEqual(api_key.created_by, self.user)
        self.assertTrue(api_key.is_active)
        self.assertEqual(str(api_key), f"{self.project.name} - Test Key (openai)")
    
    def test_unique_constraint(self):
        """Test that only one key per provider per project is allowed"""
        # Create first key
        ProjectAPIKey.objects.create(
            project=self.project,
            provider_type='openai',
            encrypted_api_key='encrypted-key-1',
            created_by=self.user
        )
        
        # Try to create second key for same provider and project
        from django.db import IntegrityError
        with self.assertRaises(IntegrityError):
            ProjectAPIKey.objects.create(
                project=self.project,
                provider_type='openai',  # Same provider
                encrypted_api_key='encrypted-key-2',
                created_by=self.user
            )
    
    def test_provider_display_info(self):
        """Test provider display information"""
        api_key = ProjectAPIKey(provider_type='openai')
        
        display_info = api_key.get_provider_display_info()
        
        self.assertIn('name', display_info)
        self.assertIn('description', display_info)
        self.assertIn('icon', display_info)
        self.assertIn('color', display_info)
        
        self.assertEqual(display_info['name'], 'OpenAI')
        self.assertIn('GPT', display_info['description'])
    
    def test_status_display(self):
        """Test status display property"""
        api_key = ProjectAPIKey(
            provider_type='openai',
            is_active=True,
            is_validated=True
        )
        
        self.assertEqual(api_key.status_display, 'Active')
        
        api_key.is_active = False
        self.assertEqual(api_key.status_display, 'Inactive')
        
        api_key.is_active = True
        api_key.is_validated = False
        self.assertEqual(api_key.status_display, 'Not Validated')
        
        api_key.validation_error = 'Some error'
        self.assertEqual(api_key.status_display, 'Validation Failed')
