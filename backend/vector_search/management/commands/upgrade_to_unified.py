# Management Command for Unified Vector Search System
# backend/vector_search/management/commands/upgrade_to_unified.py

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from users.models import IntelliDocProject, ProjectVectorCollection
from vector_search.unified_services import UnifiedVectorSearchManager
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Upgrade projects to use the unified vector search system with enhanced features'

    def add_arguments(self, parser):
        parser.add_argument(
            '--project-id',
            type=str,
            help='Specific project ID to upgrade (if not provided, all projects will be upgraded)',
        )
        parser.add_argument(
            '--processing-mode',
            type=str,
            default='enhanced',
            choices=['enhanced', 'hierarchical', 'chunked', 'simple'],
            help='Processing mode to use for upgrade (default: enhanced)',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be upgraded without making changes',
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force upgrade even if project already has enhanced processing',
        )
        parser.add_argument(
            '--list-projects',
            action='store_true',
            help='List all projects with their current processing status',
        )

    def handle(self, *args, **options):
        self.stdout.write(
            self.style.SUCCESS('🚀 AI Catalogue - Unified Vector Search System Upgrade')
        )
        self.stdout.write('=' * 60)
        
        if options['list_projects']:
            self._list_projects()
            return
        
        project_id = options['project_id']
        processing_mode = options['processing_mode']
        dry_run = options['dry_run']
        force = options['force']
        
        if dry_run:
            self.stdout.write(self.style.WARNING('🔍 DRY RUN MODE - No changes will be made'))
            self.stdout.write('')
        
        if project_id:
            self._upgrade_single_project(project_id, processing_mode, dry_run, force)
        else:
            self._upgrade_all_projects(processing_mode, dry_run, force)
    
    def _list_projects(self):
        """List all projects with their current processing status"""
        self.stdout.write(self.style.SUCCESS('📊 Project Processing Status Report'))
        self.stdout.write('=' * 60)
        
        projects = IntelliDocProject.objects.all()
        
        if not projects.exists():
            self.stdout.write(self.style.WARNING('❌ No projects found'))
            return
        
        total_projects = 0
        enhanced_projects = 0
        unprocessed_projects = 0
        
        for project in projects:
            total_projects += 1
            
            # Get project capabilities
            capabilities = UnifiedVectorSearchManager.get_project_capabilities(str(project.project_id))
            current_mode = capabilities.get('current_processing_mode', 'unknown')
            processing_status = capabilities.get('processing_status', {})
            
            # Count project types
            if current_mode == 'enhanced':
                enhanced_projects += 1
                status_icon = '✅'
                status_color = self.style.SUCCESS
            elif current_mode == 'unknown' or processing_status.get('status') == 'not_processed':
                unprocessed_projects += 1
                status_icon = '❌'
                status_color = self.style.ERROR
            else:
                status_icon = '⚠️'
                status_color = self.style.WARNING
            
            # Display project info
            self.stdout.write(
                f\"{status_icon} {status_color(project.name)} (ID: {project.project_id})\"\
            )\
            self.stdout.write(\
                f\"   Mode: {current_mode}, Documents: {capabilities.get('document_count', 0)}, \"\
                f\"Ready: {capabilities.get('ready_document_count', 0)}\"\
            )\
            \
            if processing_status.get('last_processed_at'):\
                self.stdout.write(\
                    f\"   Last Processed: {processing_status['last_processed_at']}\"\
                )\
            \
            self.stdout.write('')\
        \
        # Summary\
        self.stdout.write('=' * 60)\
        self.stdout.write(self.style.SUCCESS('📈 Summary:'))\
        self.stdout.write(f\"Total Projects: {total_projects}\")\
        self.stdout.write(f\"Enhanced Projects: {enhanced_projects}\")\
        self.stdout.write(f\"Unprocessed Projects: {unprocessed_projects}\")\
        self.stdout.write(f\"Upgradeable Projects: {total_projects - enhanced_projects}\")\
    \
    def _upgrade_single_project(self, project_id: str, processing_mode: str, dry_run: bool, force: bool):\
        \\\"\\\"\\\"Upgrade a single project\\\"\\\"\\\"\
        try:\
            # Get project\
            try:\
                project = IntelliDocProject.objects.get(project_id=project_id)\
            except IntelliDocProject.DoesNotExist:\
                try:\
                    project = IntelliDocProject.objects.get(id=int(project_id))\
                except (ValueError, IntelliDocProject.DoesNotExist):\
                    raise CommandError(f\\\"Project with ID '{project_id}' not found\\\")\
            \
            self.stdout.write(\
                self.style.SUCCESS(f\\\"🎯 Upgrading Project: {project.name} (ID: {project.project_id})\\\")\
            )\
            \
            # Get current capabilities\
            capabilities = UnifiedVectorSearchManager.get_project_capabilities(str(project.project_id))\
            current_mode = capabilities.get('current_processing_mode', 'unknown')\
            \
            # Check if upgrade is needed\
            if current_mode == processing_mode and not force:\
                self.stdout.write(\
                    self.style.WARNING(\
                        f\\\"⚠️  Project is already using {processing_mode} mode. Use --force to reprocess.\\\"\
                    )\
                )\
                return\
            \
            # Check if documents are ready\
            ready_documents = capabilities.get('ready_document_count', 0)\
            if ready_documents == 0:\
                self.stdout.write(\
                    self.style.ERROR(\
                        f\\\"❌ No documents ready for processing. Total documents: {capabilities.get('document_count', 0)}\\\"\
                    )\
                )\
                return\
            \
            self.stdout.write(f\\\"📋 Current Mode: {current_mode}\\\")\
            self.stdout.write(f\\\"📋 Target Mode: {processing_mode}\\\")\
            self.stdout.write(f\\\"📋 Documents Ready: {ready_documents}\\\")\
            \
            if dry_run:\
                self.stdout.write(\
                    self.style.WARNING(\
                        f\\\"🔍 DRY RUN: Would upgrade project to {processing_mode} mode\\\"\
                    )\
                )\
                return\
            \
            # Perform upgrade\
            self.stdout.write(f\\\"🚀 Starting {processing_mode} processing...\\\")\
            \
            result = UnifiedVectorSearchManager.process_project_documents(\
                project_id=str(project.project_id),\
                processing_mode=processing_mode\
            )\
            \
            # Report results\
            if result['status'] == 'completed':\
                self.stdout.write(\
                    self.style.SUCCESS(\
                        f\\\"✅ Upgrade completed successfully!\\\"\
                    )\
                )\
                self.stdout.write(f\\\"   Processed Documents: {result['processed_documents']}\\\")\
                self.stdout.write(f\\\"   Failed Documents: {result['failed_documents']}\\\")\
                \
                if 'total_chunks_created' in result:\
                    self.stdout.write(f\\\"   Total Chunks Created: {result['total_chunks_created']}\\\")\
                \
                if 'performance_metrics' in result:\
                    metrics = result['performance_metrics']\
                    if 'ai_content_metrics' in metrics:\
                        ai_metrics = metrics['ai_content_metrics']\
                        self.stdout.write(f\\\"   AI Summaries Generated: {ai_metrics.get('total_summaries_generated', 0)}\\\")\
                        self.stdout.write(f\\\"   AI Topics Generated: {ai_metrics.get('total_topics_generated', 0)}\\\")\
            else:\
                self.stdout.write(\
                    self.style.ERROR(\
                        f\\\"❌ Upgrade failed: {result.get('message', 'Unknown error')}\\\"\
                    )\
                )\
                \
        except Exception as e:\
            raise CommandError(f\\\"Failed to upgrade project: {e}\\\")\
    \
    def _upgrade_all_projects(self, processing_mode: str, dry_run: bool, force: bool):\
        \\\"\\\"\\\"Upgrade all projects\\\"\\\"\\\"\
        projects = IntelliDocProject.objects.all()\
        \
        if not projects.exists():\
            self.stdout.write(self.style.WARNING('❌ No projects found'))\
            return\
        \
        self.stdout.write(\
            self.style.SUCCESS(\
                f\\\"🌍 Upgrading All Projects to {processing_mode.upper()} mode\\\"\
            )\
        )\
        self.stdout.write(f\\\"Total Projects: {projects.count()}\\\")\
        self.stdout.write('')\
        \
        upgraded_count = 0\
        skipped_count = 0\
        failed_count = 0\
        \
        for project in projects:\
            try:\
                self.stdout.write(f\\\"Processing: {project.name}...\\\")\
                \
                # Get current capabilities\
                capabilities = UnifiedVectorSearchManager.get_project_capabilities(str(project.project_id))\
                current_mode = capabilities.get('current_processing_mode', 'unknown')\
                ready_documents = capabilities.get('ready_document_count', 0)\
                \
                # Check if upgrade is needed\
                if current_mode == processing_mode and not force:\
                    self.stdout.write(\
                        self.style.WARNING(\
                            f\\\"  ⚠️  Already using {processing_mode} mode - skipped\\\"\
                        )\
                    )\
                    skipped_count += 1\
                    continue\
                \
                # Check if documents are ready\
                if ready_documents == 0:\
                    self.stdout.write(\
                        self.style.WARNING(\
                            f\\\"  ⚠️  No documents ready - skipped\\\"\
                        )\
                    )\
                    skipped_count += 1\
                    continue\
                \
                if dry_run:\
                    self.stdout.write(\
                        self.style.WARNING(\
                            f\\\"  🔍 DRY RUN: Would upgrade from {current_mode} to {processing_mode}\\\"\
                        )\
                    )\
                    continue\
                \
                # Perform upgrade\
                result = UnifiedVectorSearchManager.process_project_documents(\
                    project_id=str(project.project_id),\
                    processing_mode=processing_mode\
                )\
                \
                if result['status'] == 'completed':\
                    self.stdout.write(\
                        self.style.SUCCESS(\
                            f\\\"  ✅ Upgraded - {result['processed_documents']} docs, \\\"\
                            f\\\"{result.get('total_chunks_created', 0)} chunks\\\"\
                        )\
                    )\
                    upgraded_count += 1\
                else:\
                    self.stdout.write(\
                        self.style.ERROR(\
                            f\\\"  ❌ Failed - {result.get('message', 'Unknown error')}\\\"\
                        )\
                    )\
                    failed_count += 1\
                    \
            except Exception as e:\
                self.stdout.write(\
                    self.style.ERROR(\
                        f\\\"  ❌ Exception - {str(e)}\\\"\
                    )\
                )\
                failed_count += 1\
            \
            self.stdout.write('')\
        \
        # Final summary\
        self.stdout.write('=' * 60)\
        self.stdout.write(self.style.SUCCESS('🎉 Batch Upgrade Complete'))\
        self.stdout.write(f\\\"Upgraded: {upgraded_count}\\\")\
        self.stdout.write(f\\\"Skipped: {skipped_count}\\\")\
        self.stdout.write(f\\\"Failed: {failed_count}\\\")\
        self.stdout.write(f\\\"Total: {projects.count()}\\\")\
\
# Usage examples:\
# python manage.py upgrade_to_unified --list-projects\
# python manage.py upgrade_to_unified --project-id abc123 --processing-mode enhanced\
# python manage.py upgrade_to_unified --processing-mode enhanced --dry-run\
# python manage.py upgrade_to_unified --processing-mode enhanced --force\
