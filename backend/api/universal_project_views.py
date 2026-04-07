# Universal Project API System - Phase 3 CLEAN VERSION (AutoGen Removed)
# backend/api/universal_project_views.py

from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db import transaction, connection
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from django.http import FileResponse, Http404
from asgiref.sync import async_to_sync
import mimetypes
from users.models import (
    IntelliDocProject,
    ProjectDocument,
    ProjectDocumentSummary,
    AgentWorkflow,
    SimulationRun,
    AgentMessage,
)
from templates.discovery import TemplateDiscoverySystem
from .serializers import IntelliDocProjectSerializer, ProjectDocumentSerializer
from .template_cloning_utils import clone_template_configuration
from .template_schema_validator import validate_template_config_schema
from agent_orchestration.serializers import (
    AgentWorkflowSerializer, SimulationRunSerializer, AgentMessageSerializer,
    WorkflowValidationSerializer, WorkflowExecutionSerializer
)
import logging
import uuid
import os
import json
import zipfile
import tempfile
from typing import Dict, Any, List, Tuple

# Try to import our custom schema validator, but don't fail if jsonschema isn't installed
try:
    from schemas.workflow_validator import AgentWorkflowValidator
    SCHEMA_VALIDATOR_AVAILABLE = True
except ImportError as e:
    SCHEMA_VALIDATOR_AVAILABLE = False
    print(f"⚠️  Schema validator not available: {e}")

logger = logging.getLogger(__name__)

class UniversalProjectViewSet(viewsets.ModelViewSet):
    """
    Universal Project API - Phase 3 (CUSTOM Agent Implementation)
    
    Single API for ALL project operations regardless of template type.
    Uses CUSTOM agent orchestration system with JSON schema validation.
    AutoGen has been completely removed and replaced with our own implementation.
    """
    serializer_class = IntelliDocProjectSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = 'project_id'

    def _mark_vector_collection_stale(self, project):
        """
        Mark vector status as stale after document corpus changes (upload/delete).
        This prevents old COMPLETED status from being shown for a changed corpus.
        """
        try:
            from users.models import ProjectVectorCollection, VectorProcessingStatus

            collection = ProjectVectorCollection.objects.filter(project=project).first()
            if not collection:
                return

            collection.status = VectorProcessingStatus.PENDING
            collection.error_message = ''
            collection.total_documents = project.documents.count()
            collection.processed_documents = 0
            collection.failed_documents = 0
            collection.save(
                update_fields=[
                    'status',
                    'error_message',
                    'total_documents',
                    'processed_documents',
                    'failed_documents',
                    'updated_at',
                ]
            )
        except Exception as e:
            logger.warning(
                "⚠️ UNIVERSAL: Failed to mark vector collection stale for project %s: %s",
                getattr(project, 'project_id', None),
                e,
            )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if SCHEMA_VALIDATOR_AVAILABLE:
            self.workflow_validator = AgentWorkflowValidator()
        else:
            self.workflow_validator = None
    
    def get_queryset(self):
        """Get projects accessible to current user based on permissions"""
        user = self.request.user
        
        # Superusers and admin users can see all projects
        if user.is_superuser or user.is_admin:
            return IntelliDocProject.objects.all()
        
        # Regular users see projects they created + projects they have permission to access
        from django.db.models import Q
        
        # Get projects where user is creator
        created_projects = Q(created_by=user)
        
        # Get projects with direct user permissions
        user_permissions = Q(user_permissions__user=user)
        
        # Get projects with group permissions
        user_groups = user.groups.all()
        group_permissions = Q(group_permissions__group__in=user_groups)
        
        # Combine all conditions with OR
        return IntelliDocProject.objects.filter(
            created_projects | user_permissions | group_permissions
        ).distinct()
    
    def list(self, request, *args, **kwargs):
        """
        List all projects for current user
        GET /api/projects/
        """
        logger.info(f"📋 UNIVERSAL: Listing projects for user {request.user.email}")
        
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        
        # Enhanced response with metadata
        response_data = {
            'projects': serializer.data,
            'total_count': queryset.count(),
            'user_email': request.user.email,
            'templates_used': list(queryset.values_list('template_name', flat=True).distinct()),
            'project_types': list(queryset.values_list('template_type', flat=True).distinct()),
            'api_version': 'universal_v1',
            'agent_system': 'custom_aicc_schema' if SCHEMA_VALIDATOR_AVAILABLE else 'basic',
            'schema_validator_available': SCHEMA_VALIDATOR_AVAILABLE,
            'timestamp': timezone.now().isoformat()
        }
        
        logger.info(f"📊 UNIVERSAL: Returning {len(serializer.data)} projects")
        return Response(response_data)
    
    def retrieve(self, request, *args, **kwargs):
        """
        Get single project details
        GET /api/projects/{project_id}/
        """
        project = self.get_object()
        logger.info(f"📄 UNIVERSAL: Retrieving project {project.name} ({project.project_id})")
        
        serializer = self.get_serializer(project)
        
        # Enhanced response with additional metadata
        response_data = {
            **serializer.data,
            'documents_count': project.documents.count(),
            'ready_documents_count': project.documents.filter(upload_status='ready').count(),
            'processing_documents_count': project.documents.filter(upload_status='processing').count(),
            'api_version': 'universal_v1',
            'agent_system': 'custom_aicc_schema' if SCHEMA_VALIDATOR_AVAILABLE else 'basic',
            'schema_validator_available': SCHEMA_VALIDATOR_AVAILABLE,
            'retrieved_at': timezone.now().isoformat(),
            'template_independence': True,
            'universal_interface': True
        }
        
        return Response(response_data)
    
    @transaction.atomic
    def create(self, request, *args, **kwargs):
        """
        Create new project from template (lightweight — no deep copy).
        Template config is injected at read time via the serializer.
        POST /api/projects/
        """
        logger.info(f"🏗️ UNIVERSAL: Creating project for user {request.user.email}")

        template_id = request.data.get('template_id')
        if not template_id:
            return Response({
                'error': 'template_id is required',
                'message': 'Please specify which template to use for project creation'
            }, status=status.HTTP_400_BAD_REQUEST)

        try:
            # Verify template exists
            template_data = TemplateDiscoverySystem.get_template_configuration(template_id)
            if not template_data:
                return Response({
                    'error': 'Template not found',
                    'message': f'Template with ID {template_id} does not exist'
                }, status=status.HTTP_404_NOT_FOUND)

            template_config = template_data.get('configuration', {})
            template_metadata = template_data.get('metadata', {})
            template_name = template_config.get('name') or template_metadata.get('name') or template_id.title()
            template_type = template_config.get('template_type') or template_id

            # Lightweight project record — no deep copy of template config
            project_data = {
                'name': request.data.get('name', '').strip(),
                'description': request.data.get('description', '').strip(),
                'project_id': str(uuid.uuid4()),
                'template_name': template_name,
                'template_type': template_type,
                'template_version': template_metadata.get('version', '1.0.0'),
                'icon_class': template_config.get('icon_class', 'fa-file-alt'),
                'color_theme': template_config.get('color_theme', 'oxford-blue'),
                'has_navigation': template_config.get('has_navigation', True),
                'total_pages': template_config.get('total_pages', 1),
                # These stay empty — serializer injects template config at read time
                'navigation_pages': [],
                'processing_capabilities': {},
                'validation_rules': {},
                'ui_configuration': {},
            }

            serializer = self.get_serializer(data=project_data)
            serializer.is_valid(raise_exception=True)
            project = serializer.save(created_by=request.user)

            logger.info(f"✅ UNIVERSAL: Created project {project.name} ({project.project_id})")
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        except Exception as e:
            import traceback
            logger.error(f"❌ UNIVERSAL: Project creation failed: {e}\n{traceback.format_exc()}")
            return Response({
                'error': str(e),
                'message': 'Failed to create project',
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['post'])
    def preview_template_clone(self, request):
        """
        Preview what will be cloned from a template before creating a project.
        POST /api/projects/preview_template_clone/
        """
        template_id = request.data.get('template_id')
        if not template_id:
            return Response({
                'error': 'template_id is required',
                'message': 'Please specify which template to preview'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            template_data = TemplateDiscoverySystem.get_template_configuration(template_id)
            if not template_data:
                return Response({
                    'error': 'Template not found',
                    'message': f'Template with ID {template_id} does not exist'
                }, status=status.HTTP_404_NOT_FOUND)
            
            template_config = template_data.get('configuration', {})
            template_metadata = template_data.get('metadata', {})
            
            # Get cloning preview with audit trail
            cloned_config, audit_trail = clone_template_configuration(
                template_config,
                template_metadata,
                include_audit_trail=True
            )
            
            # Get schema validation summary
            from .template_schema_validator import get_schema_validation_summary
            schema_summary = get_schema_validation_summary(template_config)
            
            # Build preview response
            template_name = cloned_config.get('name') or template_metadata.get('name') or template_id.title()
            template_type = cloned_config.get('template_type') or template_metadata.get('template_type') or template_id
            icon_class = cloned_config.get('icon_class') or template_metadata.get('ui_assets', {}).get('icon', 'fa-file-alt')
            
            preview = {
                'template_id': template_id,
                'template_name': template_name,
                'template_type': template_type,
                'template_version': template_metadata.get('version', '1.0.0'),
                'icon_class': icon_class,
                'will_clone': {
                    'navigation_pages_count': len(cloned_config.get('navigation_pages', [])),
                    'navigation_pages': cloned_config.get('navigation_pages', [])[:3],  # First 3 pages as sample
                    'processing_capabilities_keys': list(cloned_config.get('processing_capabilities', {}).keys()),
                    'validation_rules_keys': list(cloned_config.get('validation_rules', {}).keys()),
                    'ui_configuration_keys': list(cloned_config.get('ui_configuration', {}).keys()),
                    'suggested_questions_count': len(cloned_config.get('suggested_questions', [])),
                    'has_navigation': cloned_config.get('has_navigation', False),
                    'total_pages': cloned_config.get('total_pages', 1)
                },
                'cloning_audit': audit_trail,
                'schema_validation': schema_summary,
                'preview_generated_at': timezone.now().isoformat()
            }
            
            return Response(preview, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Preview template clone failed: {e}")
            return Response({
                'error': str(e),
                'message': 'Failed to generate preview',
                'template_id': template_id
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['get'], url_path='experiment-metrics')
    def experiment_metrics(self, request, project_id=None):
        """Experiment metrics removed for Electron desktop version."""
        return Response({"detail": "Feature removed in desktop version."}, status=404)

    @action(detail=True, methods=['get'], url_path='analytics')
    def analytics(self, request, project_id=None):
        """Analytics removed for Electron desktop version."""
        return Response({"detail": "Feature removed in desktop version."}, status=404)

    @action(detail=True, methods=['get'])
    def documents(self, request, project_id=None):
        """Get project documents"""
        project = self.get_object()
        documents = project.documents.all().order_by('-uploaded_at')
        serializer = ProjectDocumentSerializer(documents, many=True)
        
        return Response({
            'documents': serializer.data,
            'total_count': documents.count(),
            'project_id': project.project_id,
            'api_version': 'universal_v1'
        })
    
    @action(detail=True, methods=['post'])
    def upload_document(self, request, project_id=None):
        """Upload document to project"""
        project = self.get_object()

        if 'file' not in request.FILES:
            return Response({'error': 'No file provided'}, status=status.HTTP_400_BAD_REQUEST)

        uploaded_file = request.FILES['file']

        # Check for duplicate filename
        if ProjectDocument.objects.filter(project=project, original_filename=uploaded_file.name).exists():
            return Response(
                {'error': f'File "{uploaded_file.name}" already exists in this project'},
                status=status.HTTP_409_CONFLICT
            )

        try:
            with transaction.atomic():
                document = ProjectDocument.objects.create(
                    project=project,
                    original_filename=uploaded_file.name,
                    file_size=uploaded_file.size,
                    file_type=uploaded_file.content_type,
                    file_extension=os.path.splitext(uploaded_file.name)[1].lower(),
                    upload_status='processing',
                    uploaded_by=request.user
                )
                
                file_path = document.get_storage_path()
                saved_path = default_storage.save(file_path, ContentFile(uploaded_file.read()))
                document.file_path = saved_path
                document.upload_status = 'ready'
                document.save()
                self._mark_vector_collection_stale(project)
                
                serializer = ProjectDocumentSerializer(document)
                return Response({
                    **serializer.data,
                    'message': 'Document uploaded successfully',
                    'api_version': 'universal_v1'
                }, status=status.HTTP_201_CREATED)
                
        except Exception as e:
            return Response({'error': 'Upload failed', 'detail': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['post'])
    def upload_bulk_files(self, request, project_id=None):
        """Upload multiple files in a single request"""
        project = self.get_object()

        if not request.FILES:
            return Response({'error': 'No files provided'}, status=status.HTTP_400_BAD_REQUEST)

        uploaded_documents = []
        failed_uploads = []
        skipped_duplicates = []

        # Pre-fetch existing filenames for fast duplicate checking
        existing_filenames = set(
            ProjectDocument.objects.filter(project=project)
            .values_list('original_filename', flat=True)
        )

        for file_key, uploaded_file in request.FILES.items():
            # Skip duplicates with a clear message
            if uploaded_file.name in existing_filenames:
                skipped_duplicates.append(uploaded_file.name)
                failed_uploads.append({
                    'filename': uploaded_file.name,
                    'error': 'File already exists in this project'
                })
                continue

            try:
                with transaction.atomic():
                    document = ProjectDocument.objects.create(
                        project=project,
                        original_filename=uploaded_file.name,
                        file_size=uploaded_file.size,
                        file_type=uploaded_file.content_type,
                        file_extension=os.path.splitext(uploaded_file.name)[1].lower(),
                        upload_status='processing',
                        uploaded_by=request.user
                    )

                    file_path = document.get_storage_path()
                    saved_path = default_storage.save(file_path, ContentFile(uploaded_file.read()))
                    document.file_path = saved_path
                    document.upload_status = 'ready'
                    document.save()
                    self._mark_vector_collection_stale(project)

                    uploaded_documents.append(ProjectDocumentSerializer(document).data)
                    existing_filenames.add(uploaded_file.name)

            except Exception as e:
                failed_uploads.append({
                    'filename': uploaded_file.name,
                    'error': str(e)
                })
                logger.error(f"Failed to upload {uploaded_file.name}: {e}")

        return Response({
            'uploaded_documents': uploaded_documents,
            'failed_uploads': failed_uploads,
            'skipped_duplicates': skipped_duplicates,
            'total_attempted': len(request.FILES),
            'total_successful': len(uploaded_documents),
            'total_failed': len(failed_uploads),
            'message': f'Bulk upload completed: {len(uploaded_documents)} successful, {len(failed_uploads)} failed',
            'api_version': 'universal_v1'
        }, status=status.HTTP_201_CREATED if uploaded_documents else status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['post'])
    def upload_zip_file(self, request, project_id=None):
        """Upload and extract a zip file containing documents"""
        project = self.get_object()
        
        if 'file' not in request.FILES:
            return Response({'error': 'No zip file provided'}, status=status.HTTP_400_BAD_REQUEST)
        
        uploaded_file = request.FILES['file']
        
        # Validate it's a zip file
        if not uploaded_file.name.lower().endswith('.zip'):
            return Response({'error': 'File must be a zip archive'}, status=status.HTTP_400_BAD_REQUEST)
        
        uploaded_documents = []
        failed_extractions = []
        extracted_files_info = []
        
        try:
            with tempfile.NamedTemporaryFile(delete=False) as temp_file:
                # Save uploaded zip to temporary file
                for chunk in uploaded_file.chunks():
                    temp_file.write(chunk)
                temp_file_path = temp_file.name
            
            try:
                with zipfile.ZipFile(temp_file_path, 'r') as zip_ref:
                    # Get list of all files in zip
                    file_list = zip_ref.namelist()
                    
                    # Filter out directories and system files more comprehensively
                    valid_files = []
                    for f in file_list:
                        # Skip directories
                        if f.endswith('/'):
                            continue
                        # Skip system files and directories
                        if (f.startswith('__MACOSX/') or 
                            f.startswith('.DS_Store') or
                            '/.DS_Store' in f or
                            f.endswith('.tmp') or
                            '/.git/' in f or
                            f.startswith('.git/')):
                            continue
                        # Clean up path separators
                        clean_path = f.replace('\\', '/').strip('/')
                        if clean_path:  # Make sure we have a valid path
                            valid_files.append(f)
                    
                    if not valid_files:
                        return Response({
                            'error': 'No valid files found in zip archive',
                            'message': 'Zip file contains no extractable documents'
                        }, status=status.HTTP_400_BAD_REQUEST)
                    
                    # Check for supported file types
                    supported_extensions = ['.pdf', '.doc', '.docx', '.txt', '.md', '.rtf']
                    
                    # Pre-fetch existing filenames for duplicate checking
                    existing_filenames = set(
                        ProjectDocument.objects.filter(project=project)
                        .values_list('original_filename', flat=True)
                    )

                    for file_path in valid_files:
                        try:
                            # Get file extension
                            _, ext = os.path.splitext(file_path.lower())

                            if ext not in supported_extensions:
                                failed_extractions.append({
                                    'filename': file_path,
                                    'error': f'Unsupported file type: {ext}'
                                })
                                continue

                            # Extract file data
                            with zip_ref.open(file_path) as extracted_file:
                                file_data = extracted_file.read()

                            # Preserve the full relative path (like folder upload)
                            filename = file_path
                            filename = filename.replace('\\', '/').strip('/')

                            # Skip system files
                            if (filename.startswith('__MACOSX/') or
                                filename.startswith('.DS_Store') or
                                '/.DS_Store' in filename):
                                failed_extractions.append({
                                    'filename': filename,
                                    'error': 'System file or directory'
                                })
                                continue

                            # Skip duplicates with a clear message
                            if filename in existing_filenames:
                                failed_extractions.append({
                                    'filename': filename,
                                    'error': 'File already exists in this project'
                                })
                                continue

                            with transaction.atomic():
                                document = ProjectDocument.objects.create(
                                    project=project,
                                    original_filename=filename,
                                    file_size=len(file_data),
                                    file_type=self._get_mime_type_from_extension(ext),
                                    file_extension=ext,
                                    upload_status='processing',
                                    uploaded_by=request.user
                                )

                                doc_file_path = document.get_storage_path()
                                saved_path = default_storage.save(doc_file_path, ContentFile(file_data))
                                document.file_path = saved_path
                                document.upload_status = 'ready'
                                document.save()
                                self._mark_vector_collection_stale(project)

                            uploaded_documents.append(ProjectDocumentSerializer(document).data)
                            extracted_files_info.append({
                                'original_path': file_path,
                                'filename': filename,
                                'size': len(file_data),
                                'extension': ext
                            })
                            existing_filenames.add(filename)

                        except Exception as e:
                            failed_extractions.append({
                                'filename': file_path,
                                'error': str(e)
                            })
                            logger.error(f"Failed to extract {file_path}: {e}")
                
            finally:
                # Clean up temporary file
                try:
                    os.unlink(temp_file_path)
                except:
                    pass
            
            return Response({
                'uploaded_documents': uploaded_documents,
                'failed_extractions': failed_extractions,
                'extracted_files_info': extracted_files_info,
                'zip_filename': uploaded_file.name,
                'total_files_in_zip': len(file_list),
                'total_valid_files': len(valid_files),
                'total_extracted': len(uploaded_documents),
                'total_failed': len(failed_extractions),
                'message': f'Zip extraction completed: {len(uploaded_documents)} files extracted, {len(failed_extractions)} failed',
                'api_version': 'universal_v1'
            }, status=status.HTTP_201_CREATED if uploaded_documents else status.HTTP_400_BAD_REQUEST)
            
        except zipfile.BadZipFile:
            return Response({
                'error': 'Invalid zip file', 
                'message': 'The uploaded file is not a valid zip archive'
            }, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({'error': 'Zip upload failed', 'detail': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def _get_mime_type_from_extension(self, ext: str) -> str:
        """Get MIME type from file extension"""
        mime_types = {
            '.pdf': 'application/pdf',
            '.doc': 'application/msword',
            '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            '.txt': 'text/plain',
            '.md': 'text/markdown',
            '.rtf': 'application/rtf'
        }
        return mime_types.get(ext.lower(), 'application/octet-stream')
    
    @action(detail=True, methods=['get'], url_path='documents/(?P<document_id>[^/.]+)/download')
    def download_document(self, request, project_id=None, document_id=None):
        """Download a document from the project"""
        project = self.get_object()
        
        try:
            # Get document with security check - must belong to this project
            document = ProjectDocument.objects.get(
                document_id=document_id,
                project=project
            )
            
            # Check if file exists — support absolute paths (Electron) and storage-relative
            file_path = document.file_path
            if not file_path:
                return Response({
                    'error': 'File not found',
                    'message': 'The document file could not be found in storage'
                }, status=status.HTTP_404_NOT_FOUND)

            if os.path.isabs(file_path) and os.path.exists(file_path):
                file_handle = open(file_path, 'rb')
            elif default_storage.exists(file_path):
                file_handle = default_storage.open(file_path, 'rb')
            else:
                return Response({
                    'error': 'File not found',
                    'message': 'The document file could not be found in storage'
                }, status=status.HTTP_404_NOT_FOUND)
            
            # Determine content type
            content_type = document.file_type or mimetypes.guess_type(document.original_filename)[0] or 'application/octet-stream'
            
            # Create response with file
            response = FileResponse(
                file_handle,
                content_type=content_type,
                as_attachment=False  # Allow browser to display PDFs inline
            )
            
            # Set Content-Disposition header
            filename = document.original_filename
            # Handle filenames with special characters
            response['Content-Disposition'] = f'inline; filename="{filename}"'
            response['Content-Length'] = document.file_size
            
            # Add cache control headers
            response['Cache-Control'] = 'private, max-age=3600'
            
            logger.info(f"📥 DOWNLOAD: Serving document {document_id} ({filename}) for project {project_id}")
            
            return response
            
        except ProjectDocument.DoesNotExist:
            return Response({
                'error': 'Document not found',
                'message': f'No document found with ID {document_id} in this project'
            }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"❌ DOWNLOAD: Error downloading document {document_id}: {e}")
            return Response({
                'error': 'Download failed',
                'detail': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['get'], url_path='documents/(?P<document_id>[^/.]+)/summary')
    def document_summary(self, request, project_id=None, document_id=None):
        """Return AI-generated long/short summaries for a project document."""
        project = self.get_object()
        try:
            document = ProjectDocument.objects.get(
                document_id=document_id,
                project=project,
            )
        except ProjectDocument.DoesNotExist:
            return Response(
                {
                    'error': 'Document not found',
                    'message': f'No document found with ID {document_id} in this project',
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        summary_row = (
            ProjectDocumentSummary.objects.filter(document=document).first()
        )
        long_text = ""
        short_text = ""
        generated_at = None
        updated_at = None
        llm_provider = ""
        llm_model = ""

        if summary_row:
            long_text = (summary_row.long_summary or "").strip()
            short_text = (summary_row.short_summary or "").strip()
            generated_at = (
                summary_row.generated_at.isoformat()
                if summary_row.generated_at
                else None
            )
            updated_at = (
                summary_row.updated_at.isoformat()
                if summary_row.updated_at
                else None
            )
            llm_provider = summary_row.llm_provider or ""
            llm_model = summary_row.llm_model or ""

        has_summary = bool(long_text or short_text)
        message = ""
        if not has_summary:
            message = (
                "No AI summary yet. Run processing with Enable Summary turned on "
                "in Document Processing."
            )

        return Response(
            {
                'document_id': str(document.document_id),
                'original_filename': document.original_filename,
                'long_summary': long_text,
                'short_summary': short_text,
                'has_summary': has_summary,
                'generated_at': generated_at,
                'updated_at': updated_at,
                'llm_provider': llm_provider,
                'llm_model': llm_model,
                'message': message,
                'api_version': 'universal_v1',
            },
            status=status.HTTP_200_OK,
        )
    
    @action(detail=True, methods=['post'], url_path='documents/upload-to-llm')
    def upload_documents_to_llm(self, request, project_id=None):
        """
        Upload project documents to LLM provider File APIs.
        
        This stores the provider-specific file_id on each document so it can be
        referenced later via the File Attachments feature without re-uploading.
        
        Request body:
        {
            "document_ids": ["uuid1", "uuid2"],  // optional, defaults to all ready docs
            "providers": ["openai", "anthropic"]  // optional, defaults to all with API keys
        }
        """
        project = self.get_object()
        
        document_ids = request.data.get('document_ids', [])
        providers = request.data.get('providers', [])
        
        try:
            # Get documents to upload
            if document_ids:
                documents = ProjectDocument.objects.filter(
                    project=project,
                    document_id__in=document_ids
                )
            else:
                documents = ProjectDocument.objects.filter(
                    project=project,
                    upload_status='ready'
                )
            
            if not documents.exists():
                return Response({
                    'error': 'No documents found',
                    'message': 'No matching documents found for upload'
                }, status=status.HTTP_404_NOT_FOUND)
            
            # Default providers to all that have API keys
            if not providers:
                providers = ['openai', 'anthropic', 'google']
            
            # Upload using LLMFileUploadService
            from agent_orchestration.llm_file_service import LLMFileUploadService
            
            service = LLMFileUploadService(project)
            
            results = {}
            for doc in documents:
                doc_key = str(doc.document_id)
                doc_results = {}
                
                for provider in providers:
                    # Skip if already uploaded (deduplication)
                    existing_id = LLMFileUploadService.get_file_id_for_provider(doc, provider)
                    if existing_id:
                        doc_results[provider] = {
                            'file_id': existing_id,
                            'status': 'already_uploaded'
                        }
                        continue
                    
                    # Check provider support before uploading
                    supported, reason = LLMFileUploadService.check_provider_support(doc, provider)
                    if not supported:
                        doc_results[provider] = {
                            'error': reason,
                            'status': 'unsupported'
                        }
                        continue
                    
                    # Perform the upload (sync wrapper around async method)
                    try:
                        result = async_to_sync(service._upload_to_provider)(doc, provider)
                        if result.get('file_id'):
                            doc_results[provider] = {
                                'file_id': result['file_id'],
                                'status': result.get('status', 'uploaded')
                            }
                        else:
                            doc_results[provider] = {
                                'error': result.get('error', 'Unknown error'),
                                'status': result.get('status', 'failed'),
                                'reason': result.get('reason')
                            }
                    except Exception as e:
                        doc_results[provider] = {
                            'error': str(e),
                            'status': 'failed'
                        }
                
                results[doc_key] = {
                    'filename': doc.original_filename,
                    'providers': doc_results
                }
            
            # Count successes
            total_uploaded = sum(
                1 for doc_result in results.values()
                for prov_result in doc_result['providers'].values()
                if prov_result.get('status') == 'uploaded'
            )
            total_already = sum(
                1 for doc_result in results.values()
                for prov_result in doc_result['providers'].values()
                if prov_result.get('status') == 'already_uploaded'
            )
            
            logger.info(
                f"📎 LLM UPLOAD: Project {project_id} - "
                f"{total_uploaded} new uploads, {total_already} already uploaded"
            )
            
            return Response({
                'status': 'completed',
                'documents': results,
                'summary': {
                    'total_documents': len(results),
                    'new_uploads': total_uploaded,
                    'already_uploaded': total_already,
                    'providers_targeted': providers
                }
            })
            
        except Exception as e:
            logger.error(f"❌ LLM UPLOAD: Error uploading documents for project {project_id}: {e}")
            import traceback
            logger.error(f"❌ LLM UPLOAD: Traceback: {traceback.format_exc()}")
            return Response({
                'error': 'Upload failed',
                'detail': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['post'])
    def process_documents(self, request, project_id=None):
        """Process project documents using consolidated processing - FIXED"""
        from vector_search.consolidated_api_views import process_unified_consolidated

        # Enforce project access: get_object() uses get_queryset() and returns 404 for inaccessible projects
        project = self.get_object()

        # Extract LLM configuration from request
        llm_provider = request.data.get('llm_provider', 'openai')
        llm_model = request.data.get('llm_model', 'gpt-5.3-chat-latest')
        enable_summary = request.data.get('enable_summary', True)

        logger.info(f"🚀 UNIVERSAL: Delegating document processing for project {project.project_id}")
        logger.info(f"📋 UNIVERSAL: LLM Config - Provider: {llm_provider}, Model: {llm_model}, Enable Summary: {enable_summary}")

        # Prepare LLM config dict
        llm_config = {
            'llm_provider': llm_provider,
            'llm_model': llm_model,
            'enable_summary': enable_summary
        }

        # Pass the DRF request object and LLM config as parameter
        return process_unified_consolidated(request, str(project.project_id), llm_config=llm_config)
    
    @action(detail=True, methods=['post'])
    def search(self, request, project_id=None):
        """Search project documents using consolidated search"""
        from vector_search.consolidated_api_views import search_unified_consolidated

        # Enforce project access: get_object() uses get_queryset() and returns 404 for inaccessible projects
        project = self.get_object()
        logger.info(f"🔍 UNIVERSAL: Delegating document search for project {project.project_id}")
        return search_unified_consolidated(request._request, str(project.project_id))
    
    @action(detail=True, methods=['get'])
    def vector_status(self, request, project_id=None):
        """Get vector status using consolidated status endpoint"""
        from vector_search.consolidated_api_views import get_vector_status_consolidated

        # Enforce project access: get_object() uses get_queryset() and returns 404 for inaccessible projects
        project = self.get_object()
        logger.info(f"📊 UNIVERSAL: Delegating vector status for project {project.project_id}")
        return get_vector_status_consolidated(request._request, str(project.project_id))
    
    @action(detail=True, methods=['get'])
    def capabilities(self, request, project_id=None):
        """Get project capabilities using consolidated capabilities endpoint"""
        from vector_search.consolidated_api_views import get_project_capabilities_consolidated

        # Enforce project access: get_object() uses get_queryset() and returns 404 for inaccessible projects
        project = self.get_object()
        logger.info(f"🎯 UNIVERSAL: Delegating capabilities check for project {project.project_id}")
        return get_project_capabilities_consolidated(request._request, str(project.project_id))
    
    @action(detail=True, methods=['patch'], url_path='folder-structure-setting')
    def folder_structure_setting(self, request, project_id=None):
        """
        Update the preserve_original_folder_structure setting for a project.
        
        When enabled, folder organization is driven by LLM-based decisions
        (using per-document short summaries) instead of filename/path auto-classification.
        
        PATCH /api/projects/{project_id}/folder-structure-setting/
        Body: {"preserve_original_folder_structure": true/false}
        """
        project = self.get_object()
        
        # Get the new value from request data
        preserve_original = request.data.get('preserve_original_folder_structure')
        
        if preserve_original is None:
            return Response({
                "error": "preserve_original_folder_structure field is required",
                "api_version": "universal_v1"
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Convert string to boolean if needed
        if isinstance(preserve_original, str):
            preserve_original = preserve_original.lower() in ('true', '1', 'yes')
        
        old_value = project.preserve_original_folder_structure

        # Update the project setting
        project.preserve_original_folder_structure = preserve_original
        project.save(update_fields=['preserve_original_folder_structure', 'updated_at'])
        
        logger.info(
            "📁 UNIVERSAL: Folder structure setting changed %s -> %s for project %s (%s)",
            old_value, preserve_original, project.name, project_id,
        )
        
        return Response({
            "project_id": str(project.project_id),
            "preserve_original_folder_structure": project.preserve_original_folder_structure,
            "message": f"Folder structure setting updated. {'LLM-based folder organization will be used' if preserve_original else 'Filename/path auto-classification will be used'}.",
            "api_version": "universal_v1"
        })
    
    # ============================================================================
    # LOCAL FILE REGISTRATION (Electron Desktop Mode)
    # ============================================================================

    @action(detail=True, methods=['post'], url_path='register_local_files')
    def register_local_files(self, request, project_id=None):
        """Register local filesystem files by path (Electron desktop mode)."""
        project = self.get_object()
        file_paths = request.data.get('file_paths', [])

        if not file_paths:
            return Response({'error': 'No file paths provided'}, status=status.HTTP_400_BAD_REQUEST)

        SUPPORTED_EXTENSIONS = {'.pdf', '.doc', '.docx', '.txt', '.md', '.rtf'}
        registered = []
        failed = []
        skipped = []

        # Pre-fetch existing filenames for duplicate check
        existing_filenames = set(
            project.documents.values_list('original_filename', flat=True)
        )

        for file_path in file_paths:
            try:
                file_path = str(file_path).strip()
                if not os.path.isfile(file_path):
                    failed.append({'path': file_path, 'error': 'File not found'})
                    continue

                filename = os.path.basename(file_path)
                ext = os.path.splitext(filename)[1].lower()

                if ext not in SUPPORTED_EXTENSIONS:
                    failed.append({'path': file_path, 'error': f'Unsupported file type: {ext}'})
                    continue

                if filename in existing_filenames:
                    skipped.append({'path': file_path, 'reason': 'Duplicate filename'})
                    continue

                file_size = os.path.getsize(file_path)
                file_type = mimetypes.guess_type(file_path)[0] or 'application/octet-stream'

                doc = ProjectDocument.objects.create(
                    project=project,
                    original_filename=filename,
                    file_path=file_path,
                    file_size=file_size,
                    file_type=file_type,
                    file_extension=ext,
                    upload_status='ready',
                    uploaded_by=request.user,
                )

                existing_filenames.add(filename)
                registered.append({
                    'document_id': str(doc.document_id),
                    'filename': filename,
                    'file_path': file_path,
                    'file_size': file_size,
                })

            except Exception as e:
                failed.append({'path': file_path, 'error': str(e)})

        # Mark vector collection as stale if documents were registered
        if registered:
            self._mark_vector_collection_stale(project)

        logger.info(
            f"📁 REGISTER FILES: Project {project_id} - "
            f"{len(registered)} registered, {len(failed)} failed, {len(skipped)} skipped"
        )

        return Response({
            'registered_documents': registered,
            'failed': failed,
            'skipped_duplicates': skipped,
            'total_registered': len(registered),
            'total_failed': len(failed),
            'total_skipped': len(skipped),
        })

    @action(detail=True, methods=['post'], url_path='register_local_directory')
    def register_local_directory(self, request, project_id=None):
        """Register all supported files from a local directory (Electron desktop mode)."""
        project = self.get_object()
        directory_path = request.data.get('directory_path', '').strip()

        if not directory_path or not os.path.isdir(directory_path):
            return Response({'error': 'Invalid directory path'}, status=status.HTTP_400_BAD_REQUEST)

        SUPPORTED_EXTENSIONS = {'.pdf', '.doc', '.docx', '.txt', '.md', '.rtf'}

        # Collect all supported files recursively
        file_paths = []
        for root, dirs, files in os.walk(directory_path):
            # Skip hidden directories
            dirs[:] = [d for d in dirs if not d.startswith('.')]
            for filename in files:
                if filename.startswith('.'):
                    continue
                ext = os.path.splitext(filename)[1].lower()
                if ext in SUPPORTED_EXTENSIONS:
                    full_path = os.path.join(root, filename)
                    file_paths.append(full_path)

        if not file_paths:
            return Response({
                'registered_documents': [],
                'failed': [],
                'skipped_duplicates': [],
                'total_registered': 0,
                'total_failed': 0,
                'total_skipped': 0,
                'directory': directory_path,
                'message': 'No supported files found in directory',
            })

        existing_filenames = set(
            project.documents.values_list('original_filename', flat=True)
        )

        registered = []
        failed = []
        skipped = []

        for file_path in file_paths:
            try:
                # Use relative path from directory as the filename (preserves folder structure)
                rel_path = os.path.relpath(file_path, directory_path)
                filename = rel_path  # e.g., "subfolder/document.pdf"
                ext = os.path.splitext(file_path)[1].lower()

                if filename in existing_filenames:
                    skipped.append({'path': file_path, 'reason': 'Duplicate filename'})
                    continue

                file_size = os.path.getsize(file_path)
                file_type = mimetypes.guess_type(file_path)[0] or 'application/octet-stream'

                doc = ProjectDocument.objects.create(
                    project=project,
                    original_filename=filename,
                    file_path=file_path,
                    file_size=file_size,
                    file_type=file_type,
                    file_extension=ext,
                    upload_status='ready',
                    uploaded_by=request.user,
                )

                existing_filenames.add(filename)
                registered.append({
                    'document_id': str(doc.document_id),
                    'filename': filename,
                    'file_path': file_path,
                    'file_size': file_size,
                })

            except Exception as e:
                failed.append({'path': file_path, 'error': str(e)})

        if registered:
            self._mark_vector_collection_stale(project)

        logger.info(
            f"📂 REGISTER DIR: Project {project_id} - directory '{directory_path}' - "
            f"{len(registered)} registered, {len(failed)} failed, {len(skipped)} skipped"
        )

        return Response({
            'registered_documents': registered,
            'failed': failed,
            'skipped_duplicates': skipped,
            'total_registered': len(registered),
            'total_failed': len(failed),
            'total_skipped': len(skipped),
            'directory': directory_path,
        })

    def _cleanup_llm_files(self, document, project):
        """Best-effort deletion of files uploaded to LLM provider APIs."""
        for provider, field in [('openai', 'llm_file_id_openai'), ('anthropic', 'llm_file_id_anthropic'), ('google', 'llm_file_id_google')]:
            file_id = getattr(document, field, None)
            if not file_id:
                continue
            try:
                from agent_orchestration.llm_file_service import LLMFileUploadService
                service = LLMFileUploadService(project)
                from asgiref.sync import async_to_sync
                async_to_sync(service.delete_file)(provider, file_id)
                logger.info(f"🗑️ LLM FILE: Deleted {provider} file {file_id[:20]}... for {document.original_filename}")
            except Exception as e:
                logger.warning(f"⚠️ LLM FILE: Failed to delete {provider} file for {document.original_filename}: {e}")

    def _cleanup_workflow_references(self, project, deleted_filenames):
        """Remove references to deleted documents from workflow graph_json nodes."""
        from users.models import AgentWorkflow
        workflows_cleaned = 0
        for workflow in AgentWorkflow.objects.filter(project=project):
            graph = workflow.graph_json
            if not graph or not graph.get('nodes'):
                continue
            changed = False
            for node in graph['nodes']:
                data = node.get('data', {})
                # Clean file_attachment_documents
                fa_docs = data.get('file_attachment_documents')
                if isinstance(fa_docs, list):
                    filtered = [f for f in fa_docs if f not in deleted_filenames]
                    if len(filtered) != len(fa_docs):
                        data['file_attachment_documents'] = filtered
                        changed = True
                # Clean inline_file_attachments
                inline = data.get('inline_file_attachments')
                if isinstance(inline, list):
                    filtered = [a for a in inline if a.get('filename') not in deleted_filenames]
                    if len(filtered) != len(inline):
                        data['inline_file_attachments'] = filtered
                        changed = True
            if changed:
                workflow.graph_json = graph
                workflow.save(update_fields=['graph_json'])
                workflows_cleaned += 1
                logger.info(f"🗑️ WORKFLOW: Cleaned references in workflow {workflow.name} ({workflow.workflow_id})")
        return workflows_cleaned

    def _delete_single_document(self, document, project):
        """Full cleanup and deletion of a single document. Returns document name on success."""
        from users.models import DocumentVectorStatus, ProjectDocumentSummary, ProjectDocumentFolderOrganization
        doc_name = document.original_filename
        doc_uuid = str(document.document_id)

        # 1. Delete LLM provider files
        self._cleanup_llm_files(document, project)

        # 2. Clean up related DB records
        DocumentVectorStatus.objects.filter(document=document).delete()
        ProjectDocumentSummary.objects.filter(document=document).delete()
        ProjectDocumentFolderOrganization.objects.filter(document=document).delete()

        # 3. Delete ChromaDB vectors
        try:
            from vector_search.chromadb_service import create_project_vector_database
            vector_db = create_project_vector_database(str(project.project_id))
            vector_db.delete_document(doc_uuid)
        except Exception as vec_err:
            logger.warning(f"⚠️ UNIVERSAL: Failed to delete vectors for {doc_name}: {vec_err}")

        # 4. Delete physical file (skip for absolute paths — user's local files)
        if document.file_path and not os.path.isabs(document.file_path):
            try:
                if default_storage.exists(document.file_path):
                    default_storage.delete(document.file_path)
            except Exception:
                pass

        # 5. Delete DB record
        document.delete()
        return doc_name

    @action(detail=True, methods=['delete'], url_path='bulk_delete_documents')
    def bulk_delete_documents(self, request, project_id=None):
        """Delete multiple documents from the project with full cleanup."""
        project = self.get_object()
        document_ids = request.data.get('document_ids', [])

        if not document_ids:
            return Response({'error': 'document_ids list is required'}, status=status.HTTP_400_BAD_REQUEST)

        deleted = []
        failed = []
        deleted_filenames = set()

        documents = list(project.documents.filter(document_id__in=document_ids))
        found_ids = {str(d.document_id) for d in documents}
        for doc_id in document_ids:
            if doc_id not in found_ids:
                failed.append({'document_id': doc_id, 'error': 'Document not found'})

        for document in documents:
            try:
                doc_name = self._delete_single_document(document, project)
                deleted.append({'document_id': str(document.document_id), 'filename': doc_name})
                deleted_filenames.add(doc_name)
            except Exception as e:
                failed.append({'document_id': str(document.document_id), 'error': str(e)})
                logger.error(f"❌ BULK DELETE: Failed to delete {document.original_filename}: {e}")

        # Clean workflow references for all deleted filenames at once
        workflows_cleaned = 0
        if deleted_filenames:
            workflows_cleaned = self._cleanup_workflow_references(project, deleted_filenames)
            self._mark_vector_collection_stale(project)

        logger.info(f"🗑️ BULK DELETE: {len(deleted)} deleted, {len(failed)} failed, {workflows_cleaned} workflows cleaned")

        return Response({
            'deleted': deleted,
            'failed': failed,
            'total_deleted': len(deleted),
            'total_failed': len(failed),
            'workflows_cleaned': workflows_cleaned,
            'message': f'{len(deleted)} document(s) deleted successfully',
            'api_version': 'universal_v1'
        }, status=status.HTTP_200_OK)

    @action(detail=True, methods=['delete'])
    def delete_document(self, request, project_id=None):
        """Delete a specific document from the project with full cleanup."""
        project = self.get_object()
        document_id = request.data.get('document_id') or request.query_params.get('document_id')

        if not document_id:
            return Response({
                'error': 'document_id is required',
                'message': 'Please specify which document to delete'
            }, status=status.HTTP_400_BAD_REQUEST)

        try:
            try:
                document = project.documents.get(document_id=document_id)
            except (ValueError, ProjectDocument.DoesNotExist):
                document = project.documents.get(id=document_id)

            document_name = self._delete_single_document(document, project)
            self._cleanup_workflow_references(project, {document_name})
            self._mark_vector_collection_stale(project)

            logger.info(f"🗑️ UNIVERSAL: Deleted document {document_name} from project {project_id}")

            return Response({
                'message': f'Document "{document_name}" deleted successfully',
                'document_id': document_id,
                'project_id': project_id,
                'api_version': 'universal_v1'
            }, status=status.HTTP_200_OK)

        except ProjectDocument.DoesNotExist:
            return Response({
                'error': 'Document not found',
                'message': f'Document with ID {document_id} does not exist in this project'
            }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"❌ UNIVERSAL: Failed to delete document {document_id}: {e}")
            return Response({
                'error': 'Delete failed',
                'detail': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    # ============================================================================
    # CUSTOM AGENT ORCHESTRATION ENDPOINTS (JSON Schema Based - When Available)
    # ============================================================================
    
    @action(detail=True, methods=['get', 'post'])
    def agent_workflows(self, request, project_id=None):
        """
        Universal agent workflow management with CUSTOM JSON schema validation
        """
        project = self.get_object()
        logger.info(f"🤖 UNIVERSAL: Agent workflows request for project {project.name} ({project_id})")
        
        if not SCHEMA_VALIDATOR_AVAILABLE:
            return Response({
                'error': 'Schema validator not available',
                'message': 'Please install jsonschema package: pip install jsonschema>=4.0.0',
                'workflows': [],
                'total_count': 0,
                'api_version': 'universal_v1',
                'agent_system': 'basic'
            }, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        
        if request.method == 'GET':
            workflows = project.agent_workflows.all().order_by('-updated_at')
            serializer = AgentWorkflowSerializer(workflows, many=True)
            
            response_data = {
                'workflows': serializer.data,
                'total_count': workflows.count(),
                'project_id': project_id,
                'project_name': project.name,
                'template_type': project.template_type,
                'agent_capabilities': {
                    'schema_version': '1.0.0',
                    'system_type': 'custom_aicc_schema',
                    'supports_json_validation': True,
                    'supports_flow_analysis': True,
                    'autogen_removed': True
                },
                'api_version': 'universal_v1',
                'agent_system': 'custom_aicc_schema',
                'retrieved_at': timezone.now().isoformat()
            }
            
            return Response(response_data, status=status.HTTP_200_OK)
        
        elif request.method == 'POST':
            workflow_data = request.data.copy()
            
            # Validate workflow using our custom JSON schema
            if 'graph_json' in workflow_data and self.workflow_validator:
                is_valid, validation_errors, analysis = self.workflow_validator.validate_workflow(
                    workflow_data['graph_json']
                )
                
                if not is_valid:
                    return Response({
                        'error': 'Workflow validation failed',
                        'validation_errors': validation_errors,
                        'schema_analysis': analysis,
                        'api_version': 'universal_v1',
                        'agent_system': 'custom_aicc_schema'
                    }, status=status.HTTP_400_BAD_REQUEST)
            
            workflow_data['project'] = project.id
            workflow_data['created_by'] = request.user.id
            
            serializer = AgentWorkflowSerializer(data=workflow_data)
            if serializer.is_valid():
                workflow = serializer.save(project=project, created_by=request.user)
                
                response_data = {
                    **serializer.data,
                    'message': 'Workflow created successfully with custom JSON schema validation',
                    'project_id': project_id,
                    'api_version': 'universal_v1',
                    'agent_system': 'custom_aicc_schema',
                    'created_at': timezone.now().isoformat()
                }
                
                return Response(response_data, status=status.HTTP_201_CREATED)
            else:
                return Response({
                    'error': 'Invalid workflow data',
                    'validation_errors': serializer.errors,
                    'api_version': 'universal_v1'
                }, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['get', 'put', 'delete'])
    def agent_workflow(self, request, project_id=None):
        """Single agent workflow management"""
        project = self.get_object()
        workflow_id = request.query_params.get('workflow_id')
        
        if not workflow_id:
            return Response({
                'error': 'workflow_id parameter required',
                'api_version': 'universal_v1'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            workflow = project.agent_workflows.get(workflow_id=workflow_id)
        except AgentWorkflow.DoesNotExist:
            return Response({
                'error': 'Workflow not found',
                'api_version': 'universal_v1'
            }, status=status.HTTP_404_NOT_FOUND)
        
        if request.method == 'GET':
            serializer = AgentWorkflowSerializer(workflow)
            return Response({
                **serializer.data,
                'project_id': project_id,
                'api_version': 'universal_v1',
                'agent_system': 'custom_aicc_schema' if SCHEMA_VALIDATOR_AVAILABLE else 'basic'
            })
        
        elif request.method == 'PUT':
            serializer = AgentWorkflowSerializer(workflow, data=request.data, partial=True)
            if serializer.is_valid():
                serializer.save()
                return Response({
                    **serializer.data,
                    'message': 'Workflow updated successfully',
                    'api_version': 'universal_v1'
                })
            else:
                return Response({
                    'error': 'Invalid update data',
                    'validation_errors': serializer.errors,
                    'api_version': 'universal_v1'
                }, status=status.HTTP_400_BAD_REQUEST)
        
        elif request.method == 'DELETE':
            workflow_name = workflow.name
            workflow.delete()
            return Response({
                'message': f'Workflow "{workflow_name}" deleted successfully',
                'api_version': 'universal_v1'
            }, status=status.HTTP_204_NO_CONTENT)
    
    def destroy(self, request, *args, **kwargs):
        """
        Delete a project.
        DELETE /api/projects/{project_id}/
        """
        # Get the project
        project = self.get_object()
        project_name = project.name
        project_id = project.project_id
        documents_count = project.documents.count()
        
        logger.warning(f"🗑️ UNIVERSAL: Admin {request.user.email} deleting project {project_name} ({project_id}) with {documents_count} documents")
        
        # Store project info before deletion (in case we need it for manual deletion)
        project_id_to_delete = project.project_id
        project_name_to_delete = project.name
        
        try:
            with transaction.atomic():
                # Delete all associated files from storage
                deleted_files = 0
                for document in project.documents.all():
                    if document.file_path and default_storage.exists(document.file_path):
                        try:
                            default_storage.delete(document.file_path)
                            deleted_files += 1
                        except Exception as e:
                            logger.error(f"❌ UNIVERSAL: Failed to delete file {document.file_path}: {e}")
                
                # Delete vector collections if they exist
                try:
                    if hasattr(project, 'vector_collection'):
                        project.vector_collection.delete()
                        logger.info(f"🗑️ UNIVERSAL: Deleted vector collection for project {project_name}")
                except Exception as e:
                    logger.error(f"❌ UNIVERSAL: Failed to delete vector collection: {e}")
                
                # Delete agent_orchestration deployment-related records BEFORE workflows
                # This prevents foreign key constraint violations
                try:
                    with connection.cursor() as cursor:
                        # Delete DeploymentExecution records (references WorkflowExecution)
                        cursor.execute("""
                            DELETE FROM agent_orchestration_deploymentexecution 
                            WHERE workflow_execution_id IN (
                                SELECT id FROM users_workflowexecution 
                                WHERE workflow_id IN (
                                    SELECT id FROM users_agentworkflow 
                                    WHERE project_id = %s
                                )
                            )
                        """, [project.id])
                        deployment_executions_count = cursor.rowcount
                        if deployment_executions_count > 0:
                            logger.info(f"🗑️ UNIVERSAL: Deleted {deployment_executions_count} deployment executions")
                        
                        # Delete DeploymentSession records (references WorkflowDeployment)
                        cursor.execute("""
                            DELETE FROM agent_orchestration_deploymentsession 
                            WHERE deployment_id IN (
                                SELECT id FROM agent_orchestration_workflowdeployment 
                                WHERE project_id = %s
                            )
                        """, [project.id])
                        deployment_sessions_count = cursor.rowcount
                        if deployment_sessions_count > 0:
                            logger.info(f"🗑️ UNIVERSAL: Deleted {deployment_sessions_count} deployment sessions")
                        
                        # Delete WorkflowDeploymentRequest records (references WorkflowDeployment)
                        cursor.execute("""
                            DELETE FROM agent_orchestration_workflowdeploymentrequest 
                            WHERE deployment_id IN (
                                SELECT id FROM agent_orchestration_workflowdeployment 
                                WHERE project_id = %s
                            )
                        """, [project.id])
                        deployment_requests_count = cursor.rowcount
                        if deployment_requests_count > 0:
                            logger.info(f"🗑️ UNIVERSAL: Deleted {deployment_requests_count} deployment requests")
                        
                        # Delete WorkflowAllowedOrigin records (references WorkflowDeployment)
                        cursor.execute("""
                            DELETE FROM agent_orchestration_workflowallowedorigin 
                            WHERE deployment_id IN (
                                SELECT id FROM agent_orchestration_workflowdeployment 
                                WHERE project_id = %s
                            )
                        """, [project.id])
                        allowed_origins_count = cursor.rowcount
                        if allowed_origins_count > 0:
                            logger.info(f"🗑️ UNIVERSAL: Deleted {allowed_origins_count} allowed origins")
                        
                        # Delete WorkflowDeployment records (references AgentWorkflow)
                        cursor.execute("""
                            DELETE FROM agent_orchestration_workflowdeployment 
                            WHERE project_id = %s
                        """, [project.id])
                        workflow_deployments_count = cursor.rowcount
                        if workflow_deployments_count > 0:
                            logger.info(f"🗑️ UNIVERSAL: Deleted {workflow_deployments_count} workflow deployments")
                except Exception as deployment_error:
                    logger.warning(f"⚠️ UNIVERSAL: Error deleting deployment records (may not exist): {deployment_error}")
                
                # Delete all agent workflows (this will cascade delete evaluations, execution history, etc.)
                workflows_count = project.agent_workflows.count()
                if workflows_count > 0:
                    project.agent_workflows.all().delete()
                    logger.info(f"🗑️ UNIVERSAL: Deleted {workflows_count} agent workflows")
                
                # Delete all project API keys explicitly (CASCADE should handle it, but explicit is safer)
                api_keys_count = project.api_keys.count()
                if api_keys_count > 0:
                    project.api_keys.all().delete()
                    logger.info(f"🗑️ UNIVERSAL: Deleted {api_keys_count} API keys")
                
                # Delete MCP server credentials if they exist (table may not exist if migrations haven't been run)
                # Check if table exists first using raw SQL to avoid transaction abort
                mcp_table_exists = False
                try:
                    with connection.cursor() as cursor:
                        cursor.execute("""
                            SELECT EXISTS (
                                SELECT FROM information_schema.tables 
                                WHERE table_schema = 'public' 
                                AND table_name = 'users_mcpservercredential'
                            );
                        """)
                        mcp_table_exists = cursor.fetchone()[0]
                except Exception as check_error:
                    logger.warning(f"⚠️ UNIVERSAL: Could not check MCP credentials table existence: {check_error}")
                
                if mcp_table_exists:
                    try:
                        mcp_credentials_count = project.mcp_server_credentials.count()
                        if mcp_credentials_count > 0:
                            project.mcp_server_credentials.all().delete()
                            logger.info(f"🗑️ UNIVERSAL: Deleted {mcp_credentials_count} MCP server credentials")
                    except Exception as mcp_error:
                        logger.warning(f"⚠️ UNIVERSAL: Error deleting MCP credentials (table exists but query failed): {mcp_error}")
                else:
                    logger.info(f"ℹ️ UNIVERSAL: MCP server credentials table does not exist, skipping deletion (migrations may not have been run)")
                
                # Delete the project itself (will cascade delete documents, permissions, etc.)
                # Try to delete normally first
                try:
                    project.delete()
                except Exception as delete_error:
                    # Check if error is due to missing MCP credentials table
                    error_str = str(delete_error).lower()
                    if 'mcpservercredential' in error_str and ('does not exist' in error_str or 'relation' in error_str):
                        # Re-raise to exit the atomic block, then handle manually in outer exception handler
                        raise
                    else:
                        # Re-raise if it's a different error
                        logger.error(f"❌ UNIVERSAL: Unexpected error during project deletion: {delete_error}")
                        raise
                
                logger.info(f"✅ UNIVERSAL: Successfully deleted project {project_name} ({project_id})")
                
                return Response({
                    'message': f'Project "{project_name}" deleted successfully',
                    'project_id': str(project_id),
                    'project_name': project_name,
                    'deleted_documents': documents_count,
                    'deleted_files': deleted_files,
                    'deleted_workflows': workflows_count,
                    'deleted_by': request.user.email,
                    'deleted_at': timezone.now().isoformat(),
                    'api_version': 'universal_v1'
                }, status=status.HTTP_200_OK)
                
        except Exception as e:
            import traceback
            error_traceback = traceback.format_exc()
            error_str = str(e).lower()
            
            # Check if error is due to missing MCP credentials table
            if 'mcpservercredential' in error_str and ('does not exist' in error_str or 'relation' in error_str):
                logger.warning(f"⚠️ UNIVERSAL: MCP server credentials table not found during cascade delete, attempting manual deletion")
                # The atomic block will rollback automatically, now do manual deletion in a new transaction
                try:
                    # Store project info before attempting manual deletion
                    project_id_to_delete = project_id
                    project_name_to_delete = project_name
                    
                    # Re-fetch the project in the new transaction (since the old one rolled back)
                    try:
                        project_to_delete = IntelliDocProject.objects.get(project_id=project_id_to_delete)
                    except IntelliDocProject.DoesNotExist:
                        logger.info(f"ℹ️ UNIVERSAL: Project {project_name_to_delete} ({project_id_to_delete}) already deleted")
                        return Response({
                            'message': f'Project "{project_name_to_delete}" was already deleted',
                            'project_id': str(project_id_to_delete),
                            'project_name': project_name_to_delete,
                            'api_version': 'universal_v1'
                        }, status=status.HTTP_200_OK)
                    
                    with transaction.atomic():
                        # Delete all related objects first (workflows, API keys, etc.)
                        # IMPORTANT: Delete workflow dependencies in correct order to avoid foreign key violations
                        
                        with connection.cursor() as cursor:
                            # STEP 0: Delete agent_orchestration deployment-related records FIRST
                            # These must be deleted before WorkflowExecution and AgentWorkflow
                            
                            # 0.1. Delete DeploymentExecution records (references WorkflowExecution and DeploymentSession)
                            cursor.execute("""
                                DELETE FROM agent_orchestration_deploymentexecution 
                                WHERE workflow_execution_id IN (
                                    SELECT id FROM users_workflowexecution 
                                    WHERE workflow_id IN (
                                        SELECT id FROM users_agentworkflow 
                                        WHERE project_id = (SELECT id FROM users_intellidocproject WHERE project_id = %s)
                                    )
                                )
                            """, [project_id_to_delete])
                            deployment_executions_count = cursor.rowcount
                            if deployment_executions_count > 0:
                                logger.info(f"🗑️ UNIVERSAL: Manually deleted {deployment_executions_count} deployment executions (raw SQL)")
                            
                            # 0.2. Delete DeploymentSession records (references WorkflowDeployment)
                            cursor.execute("""
                                DELETE FROM agent_orchestration_deploymentsession 
                                WHERE deployment_id IN (
                                    SELECT id FROM agent_orchestration_workflowdeployment 
                                    WHERE project_id = (SELECT id FROM users_intellidocproject WHERE project_id = %s)
                                )
                            """, [project_id_to_delete])
                            deployment_sessions_count = cursor.rowcount
                            if deployment_sessions_count > 0:
                                logger.info(f"🗑️ UNIVERSAL: Manually deleted {deployment_sessions_count} deployment sessions (raw SQL)")
                            
                            # 0.3. Delete WorkflowDeploymentRequest records (references WorkflowDeployment)
                            cursor.execute("""
                                DELETE FROM agent_orchestration_workflowdeploymentrequest 
                                WHERE deployment_id IN (
                                    SELECT id FROM agent_orchestration_workflowdeployment 
                                    WHERE project_id = (SELECT id FROM users_intellidocproject WHERE project_id = %s)
                                )
                            """, [project_id_to_delete])
                            deployment_requests_count = cursor.rowcount
                            if deployment_requests_count > 0:
                                logger.info(f"🗑️ UNIVERSAL: Manually deleted {deployment_requests_count} deployment requests (raw SQL)")
                            
                            # 0.4. Delete WorkflowAllowedOrigin records (references WorkflowDeployment)
                            cursor.execute("""
                                DELETE FROM agent_orchestration_workflowallowedorigin 
                                WHERE deployment_id IN (
                                    SELECT id FROM agent_orchestration_workflowdeployment 
                                    WHERE project_id = (SELECT id FROM users_intellidocproject WHERE project_id = %s)
                                )
                            """, [project_id_to_delete])
                            allowed_origins_count = cursor.rowcount
                            if allowed_origins_count > 0:
                                logger.info(f"🗑️ UNIVERSAL: Manually deleted {allowed_origins_count} allowed origins (raw SQL)")
                            
                            # 0.5. Delete WorkflowDeployment records (references AgentWorkflow)
                            cursor.execute("""
                                DELETE FROM agent_orchestration_workflowdeployment 
                                WHERE project_id = (SELECT id FROM users_intellidocproject WHERE project_id = %s)
                            """, [project_id_to_delete])
                            workflow_deployments_count = cursor.rowcount
                            if workflow_deployments_count > 0:
                                logger.info(f"🗑️ UNIVERSAL: Manually deleted {workflow_deployments_count} workflow deployments (raw SQL)")
                            
                            # 1. Delete WorkflowExecutionMessage records (depends on WorkflowExecution)
                            cursor.execute("""
                                DELETE FROM users_workflowexecutionmessage 
                                WHERE execution_id IN (
                                    SELECT id FROM users_workflowexecution 
                                    WHERE workflow_id IN (
                                        SELECT id FROM users_agentworkflow 
                                        WHERE project_id = (SELECT id FROM users_intellidocproject WHERE project_id = %s)
                                    )
                                )
                            """, [project_id_to_delete])
                            messages_count = cursor.rowcount
                            if messages_count > 0:
                                logger.info(f"🗑️ UNIVERSAL: Manually deleted {messages_count} workflow execution messages (raw SQL)")
                            
                            # 2. Delete HumanInputInteraction records (depends on WorkflowExecution)
                            cursor.execute("""
                                DELETE FROM users_humaninputinteraction 
                                WHERE execution_id IN (
                                    SELECT id FROM users_workflowexecution 
                                    WHERE workflow_id IN (
                                        SELECT id FROM users_agentworkflow 
                                        WHERE project_id = (SELECT id FROM users_intellidocproject WHERE project_id = %s)
                                    )
                                )
                            """, [project_id_to_delete])
                            human_inputs_count = cursor.rowcount
                            if human_inputs_count > 0:
                                logger.info(f"🗑️ UNIVERSAL: Manually deleted {human_inputs_count} human input interactions (raw SQL)")
                            
                            # 3. Delete WorkflowExecution records (depends on AgentWorkflow)
                            cursor.execute("""
                                DELETE FROM users_workflowexecution 
                                WHERE workflow_id IN (
                                    SELECT id FROM users_agentworkflow 
                                    WHERE project_id = (SELECT id FROM users_intellidocproject WHERE project_id = %s)
                                )
                            """, [project_id_to_delete])
                            executions_count = cursor.rowcount
                            if executions_count > 0:
                                logger.info(f"🗑️ UNIVERSAL: Manually deleted {executions_count} workflow executions (raw SQL)")
                            
                            # 4. Delete WorkflowEvaluationResult records (depends on WorkflowEvaluation)
                            cursor.execute("""
                                DELETE FROM users_workflowevaluationresult 
                                WHERE evaluation_id IN (
                                    SELECT id FROM users_workflowevaluation 
                                    WHERE workflow_id IN (
                                        SELECT id FROM users_agentworkflow 
                                        WHERE project_id = (SELECT id FROM users_intellidocproject WHERE project_id = %s)
                                    )
                                )
                            """, [project_id_to_delete])
                            eval_results_count = cursor.rowcount
                            if eval_results_count > 0:
                                logger.info(f"🗑️ UNIVERSAL: Manually deleted {eval_results_count} workflow evaluation results (raw SQL)")
                            
                            # 5. Delete WorkflowEvaluation records (depends on AgentWorkflow)
                            cursor.execute("""
                                DELETE FROM users_workflowevaluation 
                                WHERE workflow_id IN (
                                    SELECT id FROM users_agentworkflow 
                                    WHERE project_id = (SELECT id FROM users_intellidocproject WHERE project_id = %s)
                                )
                            """, [project_id_to_delete])
                            evaluations_count = cursor.rowcount
                            if evaluations_count > 0:
                                logger.info(f"🗑️ UNIVERSAL: Manually deleted {evaluations_count} workflow evaluations (raw SQL)")
                            
                            # 6. Delete SimulationRun records (depends on AgentWorkflow)
                            cursor.execute("""
                                DELETE FROM users_simulationrun 
                                WHERE workflow_id IN (
                                    SELECT id FROM users_agentworkflow 
                                    WHERE project_id = (SELECT id FROM users_intellidocproject WHERE project_id = %s)
                                )
                            """, [project_id_to_delete])
                            simulation_runs_count = cursor.rowcount
                            if simulation_runs_count > 0:
                                logger.info(f"🗑️ UNIVERSAL: Manually deleted {simulation_runs_count} simulation runs (raw SQL)")
                            
                            # 7. Finally, delete workflows themselves
                            cursor.execute("""
                                SELECT COUNT(*) FROM users_agentworkflow 
                                WHERE project_id = (SELECT id FROM users_intellidocproject WHERE project_id = %s)
                            """, [project_id_to_delete])
                            workflows_count = cursor.fetchone()[0]
                            
                            if workflows_count > 0:
                                cursor.execute("""
                                    DELETE FROM users_agentworkflow 
                                    WHERE project_id = (SELECT id FROM users_intellidocproject WHERE project_id = %s)
                                """, [project_id_to_delete])
                                logger.info(f"🗑️ UNIVERSAL: Manually deleted {workflows_count} agent workflows (raw SQL)")
                        
                        # Delete user permissions
                        with connection.cursor() as cursor:
                            cursor.execute("""
                                DELETE FROM users_userprojectpermission 
                                WHERE project_id = (SELECT id FROM users_intellidocproject WHERE project_id = %s)
                            """, [project_id_to_delete])
                            logger.info(f"🗑️ UNIVERSAL: Deleted user project permissions")
                        
                        # Delete group permissions
                        with connection.cursor() as cursor:
                            cursor.execute("""
                                DELETE FROM users_groupprojectpermission 
                                WHERE project_id = (SELECT id FROM users_intellidocproject WHERE project_id = %s)
                            """, [project_id_to_delete])
                            logger.info(f"🗑️ UNIVERSAL: Deleted group project permissions")
                        
                        # Delete API keys
                        api_keys_count = project_to_delete.api_keys.count()
                        if api_keys_count > 0:
                            project_to_delete.api_keys.all().delete()
                            logger.info(f"🗑️ UNIVERSAL: Manually deleted {api_keys_count} API keys")
                        
                        # Delete documents
                        documents_count = project_to_delete.documents.count()
                        if documents_count > 0:
                            project_to_delete.documents.all().delete()
                            logger.info(f"🗑️ UNIVERSAL: Manually deleted {documents_count} documents")
                        
                        # Now delete the project itself using raw SQL to bypass ORM cascade
                        with connection.cursor() as cursor:
                            cursor.execute("DELETE FROM users_intellidocproject WHERE project_id = %s", [project_id_to_delete])
                        logger.info(f"🗑️ UNIVERSAL: Manually deleted project {project_name_to_delete} ({project_id_to_delete})")
                    
                    return Response({
                        'message': f'Project "{project_name_to_delete}" deleted successfully (manual deletion due to missing MCP table)',
                        'project_id': str(project_id_to_delete),
                        'project_name': project_name_to_delete,
                        'deleted_documents': documents_count,
                        'deleted_files': 0,  # Files were deleted in the previous transaction
                        'deleted_workflows': workflows_count if 'workflows_count' in locals() else 0,
                        'deleted_by': request.user.email,
                        'deleted_at': timezone.now().isoformat(),
                        'api_version': 'universal_v1',
                        'note': 'Manual deletion due to missing MCP server credentials table'
                    }, status=status.HTTP_200_OK)
                except Exception as manual_error:
                    logger.error(f"❌ UNIVERSAL: Failed to manually delete project {project_name}: {manual_error}")
                    import traceback
                    logger.error(f"❌ UNIVERSAL: Manual deletion error traceback:\n{traceback.format_exc()}")
                    return Response({
                        'error': 'Deletion failed',
                        'detail': f'Failed to delete project: {str(manual_error)}',
                        'project_id': str(project_id),
                        'project_name': project_name,
                        'api_version': 'universal_v1'
                    }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            else:
                # Re-raise if it's a different error
                logger.error(f"❌ UNIVERSAL: Failed to delete project {project_name}: {e}")
                logger.error(f"❌ UNIVERSAL: Delete error traceback:\n{error_traceback}")
                return Response({
                    'error': 'Deletion failed',
                    'detail': str(e),
                    'project_id': str(project_id),
                    'project_name': project_name,
                    'api_version': 'universal_v1'
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def health(self, request):
        """Health check for universal project API"""
        return Response({
            'status': 'healthy',
            'api_version': 'universal_v1',
            'agent_system': 'custom_aicc_schema' if SCHEMA_VALIDATOR_AVAILABLE else 'basic',
            'schema_validator_available': SCHEMA_VALIDATOR_AVAILABLE,
            'timestamp': timezone.now().isoformat(),
            'message': 'Universal Project API is operational (AutoGen completely removed)',
            'features': {
                'template_independence': True,
                'universal_interface': True,
                'autogen_removed': True,
                'custom_implementation_ready': SCHEMA_VALIDATOR_AVAILABLE
            }
        })
