"""
Management command to sync approved knowledge to ChromaDB
Completely isolated from main AI Catalogue system
"""
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from public_chatbot.models import PublicKnowledgeDocument
from public_chatbot.services import PublicKnowledgeService
import logging

logger = logging.getLogger('public_chatbot')


class Command(BaseCommand):
    help = 'Sync approved public knowledge documents to ChromaDB (isolated from main system)'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--force-sync',
            action='store_true',
            help='Force sync all documents, even if already synced'
        )
        parser.add_argument(
            '--category',
            type=str,
            help='Only sync documents from specific category'
        )
        parser.add_argument(
            '--limit',
            type=int,
            default=100,
            help='Maximum number of documents to sync (default: 100)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be synced without actually syncing'
        )
    
    def handle(self, *args, **options):
        """Execute the sync command"""
        self.stdout.write(self.style.SUCCESS('🚀 Starting public knowledge sync to ChromaDB (isolated)'))
        
        # Get ChromaDB service
        try:
            knowledge_service = PublicKnowledgeService.get_instance()
            if not knowledge_service.is_ready:
                raise CommandError('❌ ChromaDB service is not ready. Check connection and try again.')
        except Exception as e:
            raise CommandError(f'❌ Failed to initialize ChromaDB service: {e}')
        
        # Build query for documents to sync
        query = PublicKnowledgeDocument.objects.filter(
            is_approved=True,
            security_reviewed=True
        )
        
        # Filter by category if specified
        if options['category']:
            query = query.filter(category=options['category'])
            self.stdout.write(f"📂 Filtering by category: {options['category']}")
        
        # Filter unsynced documents unless force sync
        if not options['force_sync']:
            query = query.filter(synced_to_chromadb=False)
            self.stdout.write("📋 Syncing only unsynced documents (use --force-sync to sync all)")
        else:
            self.stdout.write("🔄 Force sync enabled - syncing all approved documents")
        
        # Apply limit
        documents = query[:options['limit']]
        total_count = documents.count()
        
        if total_count == 0:
            self.stdout.write(self.style.WARNING('ℹ️ No documents found to sync'))
            return
        
        self.stdout.write(f"📊 Found {total_count} documents to sync")
        
        # Dry run mode
        if options['dry_run']:
            self.stdout.write(self.style.WARNING('🔍 DRY RUN MODE - No actual syncing'))
            for doc in documents:
                sync_status = "✅ SYNCED" if doc.synced_to_chromadb else "🆕 NEW"
                self.stdout.write(f"  {sync_status} {doc.title} ({doc.category})")
            return
        
        # Perform actual sync
        synced_count = 0
        error_count = 0
        
        for doc in documents:
            try:
                self.stdout.write(f"📝 Syncing: {doc.title[:50]}...")
                
                # Prepare document for ChromaDB
                success = self._sync_document(doc, knowledge_service, options['force_sync'])
                
                if success:
                    synced_count += 1
                    self.stdout.write(
                        self.style.SUCCESS(f"  ✅ Synced: {doc.title[:30]}... ({doc.category})")
                    )
                else:
                    error_count += 1
                    self.stdout.write(
                        self.style.ERROR(f"  ❌ Failed: {doc.title[:30]}...")
                    )
                    
            except Exception as e:
                error_count += 1
                logger.error(f"Sync error for document {doc.document_id}: {e}")
                self.stdout.write(
                    self.style.ERROR(f"  ❌ Error: {doc.title[:30]}... - {str(e)[:50]}")
                )
        
        # Summary
        self.stdout.write(self.style.SUCCESS(f"\n🎯 Sync completed:"))
        self.stdout.write(f"  ✅ Successfully synced: {synced_count}")
        self.stdout.write(f"  ❌ Errors: {error_count}")
        self.stdout.write(f"  📊 Total processed: {synced_count + error_count}")
        
        # Get final ChromaDB stats
        try:
            stats = knowledge_service.get_collection_stats()
            self.stdout.write(f"  📚 ChromaDB total documents: {stats.get('document_count', 'unknown')}")
        except:
            pass
    
    def _sync_document(self, doc: PublicKnowledgeDocument, service: PublicKnowledgeService, force_sync: bool) -> bool:
        """
        Sync individual document to ChromaDB
        
        Args:
            doc: PublicKnowledgeDocument to sync
            service: ChromaDB service instance
            force_sync: Whether to force sync even if already synced
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Check if service supports advanced chunking
            if hasattr(service, 'use_advanced_features') and service.use_advanced_features:
                # Use advanced chunking system
                success = self._sync_document_with_chunking(doc, service, force_sync)
            else:
                # Fallback to original method
                success = self._sync_document_legacy(doc, service, force_sync)
            
            return success
                
        except Exception as e:
            # Update error status
            doc.sync_error = str(e)[:500]  # Truncate error message
            doc.save()
            raise e
    
    def _sync_document_with_chunking(self, doc: 'PublicKnowledgeDocument', service: 'PublicKnowledgeService', force_sync: bool) -> bool:
        """
        Sync document using advanced chunking system
        """
        try:
            # Create base metadata for all chunks
            base_metadata = {
                'title': doc.title,
                'category': doc.category,
                'subcategory': doc.subcategory or '',
                'source': 'Public Knowledge Base',
                'document_id': doc.document_id,
                'quality_score': doc.quality_score,
                'language': doc.language,
                'tags': doc.tags,
                'source_url': doc.source_url or '',
                'sync_timestamp': timezone.now().isoformat(),
                'approved_by': doc.approved_by,
                'isolation_level': 'public_only'
            }
            
            # Chunk the document using advanced chunker
            chunks = service.chunker.chunk_document(
                content=doc.content,
                document_id=doc.document_id,
                metadata=base_metadata
            )
            
            if not chunks:
                self.stdout.write(self.style.WARNING(f"  ⚠️ No chunks created for {doc.title}"))
                return False
            
            # Prepare data for ChromaDB
            documents = []
            metadatas = []
            ids = []
            
            for chunk in chunks:
                documents.append(chunk.content)
                metadatas.append({
                    **chunk.metadata,
                    'chunk_index': chunk.chunk_index,
                    'total_chunks': chunk.total_chunks,
                    'chunk_type': chunk.chunk_type,
                    'token_count': chunk.token_count,
                    'char_count': chunk.char_count
                })
                ids.append(chunk.chunk_id)
            
            # Use smart sync to handle updates and prevent duplicates
            is_update = doc.synced_to_chromadb or force_sync
            success = service.smart_sync_knowledge(
                documents=documents,
                metadatas=metadatas, 
                ids=ids,
                document_id=doc.document_id,
                force_update=is_update
            )
            
            if success:
                # Update sync status
                doc.synced_to_chromadb = True
                doc.chromadb_id = f"pub_{doc.document_id}"  # Parent ID
                doc.last_synced = timezone.now()
                doc.sync_error = ''
                doc.save()
                
                self.stdout.write(
                    self.style.SUCCESS(f"  📄 Chunked into {len(chunks)} pieces using {service.chunker.strategy.value}")
                )
                return True
            else:
                doc.sync_error = f'Failed to add {len(chunks)} chunks to ChromaDB'
                doc.save()
                return False
                
        except Exception as e:
            doc.sync_error = f'Chunking failed: {str(e)[:400]}'
            doc.save()
            raise e
    
    def _sync_document_legacy(self, doc: 'PublicKnowledgeDocument', service: 'PublicKnowledgeService', force_sync: bool) -> bool:
        """
        Original sync method (fallback)
        """
        try:
            # Prepare document content and metadata (original method)
            documents = [doc.content]
            metadatas = [{
                'title': doc.title,
                'category': doc.category,
                'subcategory': doc.subcategory or '',
                'source': 'Public Knowledge Base',
                'document_id': doc.document_id,
                'quality_score': doc.quality_score,
                'language': doc.language,
                'tags': doc.tags,
                'source_url': doc.source_url or '',
                'sync_timestamp': timezone.now().isoformat(),
                'approved_by': doc.approved_by,
                'isolation_level': 'public_only'
            }]
            
            # Generate ChromaDB ID
            chromadb_id = f"pub_{doc.document_id}"
            ids = [chromadb_id]
            
            # Use smart sync to handle updates and prevent duplicates
            is_update = doc.synced_to_chromadb or force_sync
            success = service.smart_sync_knowledge(
                documents=documents,
                metadatas=metadatas,
                ids=ids,
                document_id=doc.document_id,
                force_update=is_update
            )
            
            if success:
                # Update sync status
                doc.synced_to_chromadb = True
                doc.chromadb_id = chromadb_id
                doc.last_synced = timezone.now()
                doc.sync_error = ''  # Clear any previous errors
                doc.save()
                
                return True
            else:
                # Update error status
                doc.sync_error = 'Failed to add to ChromaDB collection'
                doc.save()
                return False
                
        except Exception as e:
            doc.sync_error = str(e)[:500]
            doc.save()
            raise e