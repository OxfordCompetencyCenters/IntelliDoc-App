# Fix Documents Management Command
# backend/vector_search/management/commands/fix_documents.py

from django.core.management.base import BaseCommand
from django.utils import timezone
import logging

from users.models import IntelliDocProject
from vector_search.unified_services_fixed import fix_existing_documents, UnifiedVectorSearchManager

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Fix existing documents by extracting content from binary data and reprocessing'

    def add_arguments(self, parser):
        parser.add_argument(
            '--project-id',
            type=str,
            help='Specific project ID to fix (optional)'
        )
        parser.add_argument(
            '--reprocess',
            action='store_true',
            help='Reprocess documents after fixing content extraction'
        )
        parser.add_argument(
            '--processing-mode',
            type=str,
            default='enhanced',
            choices=['simple', 'chunked', 'hierarchical', 'enhanced'],
            help='Processing mode to use for reprocessing'
        )
        parser.add_argument(
            '--list-projects',
            action='store_true',
            help='List all projects with their document counts'
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('🔧 Starting document fixing process...'))
        
        # List projects if requested
        if options['list_projects']:
            self.list_projects()
            return
        
        # Fix content extraction
        self.stdout.write('📚 Step 1: Fixing content extraction...')
        fix_result = fix_existing_documents(options.get('project_id'))
        
        if fix_result['status'] == 'completed':
            self.stdout.write(self.style.SUCCESS(
                f"✅ Content extraction fixed: {fix_result['fixed_documents']} documents"
            ))
        else:
            self.stdout.write(self.style.ERROR(
                f"❌ Content extraction failed: {fix_result['message']}"
            ))
            return
        
        # Reprocess if requested
        if options['reprocess']:
            self.stdout.write('🚀 Step 2: Reprocessing documents...')
            self.reprocess_documents(options.get('project_id'), options['processing_mode'])
    
    def list_projects(self):
        """List all projects with document counts"""
        self.stdout.write(self.style.SUCCESS('📋 Projects and Document Counts:'))
        self.stdout.write('-' * 80)
        
        projects = IntelliDocProject.objects.all()
        
        for project in projects:
            doc_count = project.documents.count()
            ready_count = project.documents.filter(upload_status='ready').count()
            extracted_count = project.documents.filter(
                extraction_text__isnull=False
            ).exclude(extraction_text='').count()
            
            self.stdout.write(f"📁 {project.name}")
            self.stdout.write(f"   ID: {project.project_id}")
            self.stdout.write(f"   Documents: {doc_count} total, {ready_count} ready, {extracted_count} extracted")
            self.stdout.write(f"   Created: {project.created_at}")
            self.stdout.write('-' * 40)
    
    def reprocess_documents(self, project_id: str = None, processing_mode: str = 'enhanced'):
        """Reprocess documents with specified mode"""
        try:
            # Get projects to reprocess
            if project_id:
                projects = IntelliDocProject.objects.filter(project_id=project_id)
            else:
                projects = IntelliDocProject.objects.all()
            
            total_processed = 0
            total_failed = 0
            
            for project in projects:
                self.stdout.write(f"🔄 Reprocessing project: {project.name}")
                
                # Process with unified system
                result = UnifiedVectorSearchManager.process_project_documents(
                    str(project.project_id), 
                    processing_mode
                )
                
                if result['status'] == 'completed':
                    processed = result['processed_documents']
                    failed = result['failed_documents']
                    
                    total_processed += processed
                    total_failed += failed
                    
                    self.stdout.write(self.style.SUCCESS(
                        f"✅ {project.name}: {processed} processed, {failed} failed"
                    ))
                else:
                    self.stdout.write(self.style.ERROR(
                        f"❌ {project.name}: {result['message']}"
                    ))
                    total_failed += 1
            
            self.stdout.write(self.style.SUCCESS(
                f"🎉 Reprocessing completed: {total_processed} documents processed, {total_failed} failed"
            ))
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ Reprocessing failed: {e}"))
