# templates/tests.py

from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
from django.core.exceptions import ValidationError

from .models import ProjectTemplate
from users.models import UserRole

User = get_user_model()


class ProjectTemplateModelTest(TestCase):
    """Test cases for ProjectTemplate model"""
    
    def setUp(self):
        """Set up test data"""
        self.template_data = {
            'name': 'Test Template',
            'template_type': 'legal',
            'description': 'Test template description',
            'instructions': 'Test instructions',
            'suggested_questions': ['Question 1', 'Question 2'],
            'required_fields': ['field1', 'field2'],
            'analysis_focus': 'Test focus',
            'icon_class': 'fa-test',
            'color_theme': 'oxford-blue',
        }
    
    def test_create_template(self):
        """Test creating a new template"""
        template = ProjectTemplate.objects.create(**self.template_data)
        
        self.assertEqual(template.name, 'Test Template')
        self.assertEqual(template.template_type, 'legal')
        self.assertTrue(template.is_active)
        self.assertIsNotNone(template.created_at)
        self.assertIsNotNone(template.updated_at)
    
    def test_template_str_representation(self):
        """Test string representation of template"""
        template = ProjectTemplate.objects.create(**self.template_data)
        self.assertEqual(str(template), 'Test Template')
    
    def test_get_template_config(self):
        """Test get_template_config method"""
        template = ProjectTemplate.objects.create(**self.template_data)
        config = template.get_template_config()
        
        self.assertEqual(config['name'], 'Test Template')
        self.assertEqual(config['template_type'], 'legal')
        self.assertEqual(len(config['suggested_questions']), 2)
        self.assertEqual(len(config['required_fields']), 2)


class ProjectTemplateViewSetTest(TestCase):
    """Test cases for ProjectTemplateViewSet"""
    
    def setUp(self):
        """Set up test data"""
        self.client = APIClient()
        
        # Create users
        self.admin_user = User.objects.create_user(
            email='admin@test.com',
            password='testpass123',
            role=UserRole.ADMIN
        )
        
        self.regular_user = User.objects.create_user(
            email='user@test.com',
            password='testpass123',
            role=UserRole.USER
        )
        
        # Create test template
        self.template = ProjectTemplate.objects.create(
            name='Test Template',
            template_type='legal',
            description='Test description',
            instructions='Test instructions',
            suggested_questions=['Question 1'],
            required_fields=['field1'],
            analysis_focus='Test focus',
            icon_class='fa-test',
            color_theme='oxford-blue',
        )
    
    def test_list_templates_authenticated(self):
        """Test listing templates as authenticated user"""
        self.client.force_authenticate(user=self.regular_user)
        response = self.client.get('/api/project-templates/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(len(response.data['templates']), 1)
    
    def test_list_templates_unauthenticated(self):
        """Test listing templates as unauthenticated user"""
        response = self.client.get('/api/project-templates/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_get_active_templates(self):
        """Test getting only active templates"""
        self.client.force_authenticate(user=self.regular_user)
        
        # Create inactive template
        ProjectTemplate.objects.create(
            name='Inactive Template',
            template_type='history',
            description='Inactive description',
            is_active=False
        )
        
        response = self.client.get('/api/project-templates/active/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)  # Only active template
    
    def test_get_template_types(self):
        """Test getting template types"""
        self.client.force_authenticate(user=self.regular_user)
        
        response = self.client.get('/api/project-templates/types/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 4)  # 4 template types
