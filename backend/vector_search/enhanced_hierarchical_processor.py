# Enhanced Hierarchical Document Processor with Complete Content Preservation
# backend/vector_search/enhanced_hierarchical_processor.py

from pathlib import Path
import os
import numpy as np
from typing import Dict, Any, Generator, List, Optional, Tuple
from dataclasses import dataclass
import uuid
from datetime import datetime
import logging
import re

from .embeddings import DocumentEmbedder
from .summarization import get_summarizer
from .gemini_extractor import get_gemini_extractor, initialize_gemini_extractor
from project_api_keys.integration_examples import ProjectAwareOpenAISummarizer

logger = logging.getLogger(__name__)

# Heuristic to detect binary content
def is_binary(content: str) -> bool:
    """Check if content is likely binary."""
    if not content or not isinstance(content, str):
        return False
    # Check for a significant number of non-printable characters or null bytes
    text_chars = "".join(c for c in content if c.isprintable() or c in '\n\r\t')
    # If more than 15% of the content is non-printable, it's likely binary
    if len(content) > 0 and len(text_chars) / len(content) < 0.85:
        return True
    # Check for common binary file signatures if needed (e.g., %PDF-)
    if content.strip().startswith('%PDF-'):
        return True
    return False

def get_file_path(document: Any) -> Optional[str]:
    """Get the full, validated file path for a document."""
    try:
        file_path = getattr(document, 'file_path', '')
        if not file_path:
            logger.error(f"Document {document.original_filename} has no file_path attribute.")
            return None

        # In a Django context, file_path is often relative to MEDIA_ROOT
        from django.conf import settings
        if not os.path.isabs(file_path):
            full_path = os.path.join(settings.MEDIA_ROOT, file_path)
        else:
            full_path = file_path

        if os.path.exists(full_path) and os.path.isfile(full_path):
            return full_path
        else:
            logger.error(f"File not found at path: {full_path}")
            return None
    except Exception as e:
        logger.error(f"Error getting file path for {document.original_filename}: {e}")
        return None


@dataclass
class DocumentChunk:
    """Individual chunk with hierarchical mapping"""
    content: str
    chunk_index: int
    total_chunks: int
    chunk_id: str
    parent_document_id: str
    hierarchical_path: str  # Maps chunk to file hierarchy
    chunk_type: str  # 'intro', 'section', 'content', 'conclusion'
    section_title: str  # Detected section if any
    embedding: Optional[np.ndarray] = None
    metadata: Dict[str, Any] = None

@dataclass
class HierarchicalDocumentInfo:
    """Enhanced document info with complete chunk hierarchy"""
    original_content: str  # Full document content
    document_metadata: Dict[str, Any]
    chunks: List[DocumentChunk]
    content_map: Dict[str, Any]  # Maps content structure
    embedding: Optional[np.ndarray] = None

class EnhancedHierarchicalProcessor:
    """Enhanced processor with MANDATORY AI content generation using project-specific API keys"""

    def __init__(
        self, 
        project, 
        embedder: DocumentEmbedder = None, 
        max_chunk_size: int = 35000,
        llm_provider: str = None,
        llm_model: str = None,
        enable_summary: bool = True,
        folder_organization_map: Optional[Dict[str, str]] = None,
    ):
        """
        Initialize processor with project-specific API keys and LLM configuration

        Args:
            project: IntelliDocProject instance (REQUIRED)
            embedder: DocumentEmbedder instance
            max_chunk_size: Maximum chunk size in characters
            llm_provider: LLM provider to use (e.g., 'openai', 'anthropic', 'google')
            llm_model: LLM model to use (e.g., 'gpt-5.3-chat-latest', 'claude-3-opus')
            enable_summary: Whether to generate summaries for chunks

        Raises:
            ValueError: If project has no API key configured for selected provider
        """
        self.project = project
        self.embedder = embedder or DocumentEmbedder()
        self.max_chunk_size = max_chunk_size
        self.supported_extensions = {'.txt', '.text', '.pdf', '.docx', '.doc', '.md', '.rtf', '.odt'}
        self.enable_summary = enable_summary
        
        # Get preserve_original_folder_structure setting from project
        self.preserve_original_folder_structure = getattr(project, 'preserve_original_folder_structure', False)

        # Optional LLM-provided folder mapping: {str(document_id): "Category/Subcategory"}
        # Used when preserve_original_folder_structure=True to replace uploaded folder paths.
        self.folder_organization_map: Dict[str, str] = folder_organization_map or {}

        # Determine LLM provider and model (default to OpenAI if not specified)
        self.llm_provider = llm_provider or 'openai'
        self.llm_model = llm_model or 'gpt-5.3-chat-latest'

        logger.info(
            "📋 PROCESSOR: Initializing with LLM Provider: %s, Model: %s, Enable Summary: %s, Preserve Original Folders: %s",
            self.llm_provider,
            self.llm_model,
            self.enable_summary,
            self.preserve_original_folder_structure,
        )

        # Chunk-level summary/topic generation has been removed.
        # Document-level summaries will be generated separately (file-based) during Start Processing.
        self.summarizer = None

        # Initialize PDF extractor (use Google/Gemini if selected, otherwise fallback)
        self._initialize_extractors()

        logger.info(f"🚀 Enhanced Hierarchical Processor initialized for project '{project.name}' with LLM Provider: {self.llm_provider}, Model: {self.llm_model}")
    
    def _initialize_extractors(self):
        """Initialize text extraction services using project-specific API keys"""
        try:
            from project_api_keys.services import ProjectAPIKeyService

            service = ProjectAPIKeyService()
            
            # If Google/Gemini is selected as LLM provider, try to use Gemini for PDF extraction
            if self.llm_provider in ['google', 'gemini']:
                gemini_api_key = service.get_project_api_key(self.project, 'google')
                if gemini_api_key:
                    initialize_gemini_extractor(gemini_api_key)
                    logger.info(f"✅ Gemini PDF extractor initialized with project-specific API key for project '{self.project.name}'")
                else:
                    logger.warning(f"⚠️ No Google API key configured for project '{self.project.name}' - PDF extraction will use fallback methods (PyPDF2/pdfplumber)")
                    initialize_gemini_extractor(None)
            else:
                # For non-Google providers, use fallback PDF extraction methods
                logger.info(f"ℹ️ Using fallback PDF extraction methods (PyPDF2/pdfplumber) for {self.llm_provider} provider")
                initialize_gemini_extractor(None)

        except Exception as e:
            logger.error(f"❌ Error initializing extractors: {e}")
            # Initialize with None to ensure fallback methods are used
            initialize_gemini_extractor(None)
    
    def process_project_documents_enhanced(self, project_documents: List[Any]) -> Generator[HierarchicalDocumentInfo, None, None]:
        """Process project documents with enhanced hierarchical chunking"""
        
        # Build filename-based hierarchy
        filename_hierarchy = self._build_filename_hierarchy(project_documents)
        
        for document in project_documents:
            try:
                doc_info = self._process_document_enhanced(document, filename_hierarchy)
                if doc_info:
                    yield doc_info
            except Exception as e:
                logger.error(f"Error processing document {document.original_filename}: {e}")
    
    def _build_filename_hierarchy(self, documents: List[Any]) -> Dict[str, Any]:
        """Build comprehensive filename-based hierarchy"""
        hierarchy = {
            'documents': {},
            'categories': {},
            'folder_structure': {},
            'filename_patterns': {}
        }
        
        for doc in documents:
            filename = doc.original_filename
            if self.preserve_original_folder_structure:
                # preserve_original_folder_structure now means:
                # use LLM-chosen folder organization only.
                folder_override = self.folder_organization_map.get(str(getattr(doc, "document_id", "")), "")
                hierarchy_info = self._build_llm_structure_path(filename, folder_override or "General")
            else:
                hierarchy_info = self._analyze_filename_structure(filename)
            
            # Store document in hierarchy
            hierarchy['documents'][doc.id] = hierarchy_info
            
            # Build category mapping
            category = hierarchy_info['category']
            if category not in hierarchy['categories']:
                hierarchy['categories'][category] = []
            hierarchy['categories'][category].append(doc.id)
            
            # Build folder structure
            virtual_path = hierarchy_info['virtual_path']
            path_parts = virtual_path.split('/')
            current_level = hierarchy['folder_structure']
            
            for part in path_parts[:-1]:  # Exclude filename
                if part not in current_level:
                    current_level[part] = {}
                current_level = current_level[part]
        
        return hierarchy
    
    def _analyze_filename_structure(self, filename: str) -> Dict[str, Any]:
        """Enhanced filename analysis with detailed hierarchy mapping.

        This path is used only when preserve_original_folder_structure=False.
        """
        return self._build_auto_classified_path(filename)
    
    def _build_original_structure_path(self, filename: str) -> Dict[str, Any]:
        """Build virtual path preserving the original folder structure from uploads
        
        Handles edge cases:
        - Backslashes (Windows paths) converted to forward slashes
        - Multiple consecutive slashes collapsed to single slash
        - Leading/trailing slashes stripped
        - Empty folder names filtered out
        - Empty file names handled gracefully
        """
        # Extract folder path and file name from the original filename
        # filename could be "Documents/MyFiles/Doc1.pdf" or just "Doc1.pdf"
        
        # Normalize path separators: convert backslashes and collapse multiple slashes
        normalized_filename = filename.replace('\\', '/')
        # Collapse multiple consecutive slashes to single slash
        normalized_filename = re.sub(r'/+', '/', normalized_filename)
        # Strip leading and trailing slashes
        normalized_filename = normalized_filename.strip('/')
        
        # Split into folder path and file name
        if '/' in normalized_filename:
            folder_parts = normalized_filename.rsplit('/', 1)
            folder_path = folder_parts[0]
            file_only = folder_parts[1]
        else:
            folder_path = ''
            file_only = normalized_filename
        
        # Validate file_only is not empty - fallback to original filename if needed
        if not file_only:
            logger.warning(f"Empty file name detected in path: '{filename}', using original filename")
            # Try to extract just the filename from the original
            file_only = Path(filename).name or filename or 'unknown_file'
        
        # Get file name without extension for base_name
        name_without_ext = Path(file_only).stem.lower()
        
        # Build virtual path preserving original structure
        if folder_path:
            virtual_path = f'documents/{folder_path}/{file_only}'
            # Filter out empty strings from folder levels (handles edge cases like "a//b")
            folder_levels = [f for f in folder_path.split('/') if f]
            subcategory = folder_levels[-1] if folder_levels else None
            # Get top-level folder as category
            category = folder_levels[0] if folder_levels else 'user_uploads'
            hierarchy_level = len(folder_levels)
        else:
            virtual_path = f'documents/{file_only}'
            subcategory = None
            category = 'user_uploads'
            hierarchy_level = 0
        
        # Determine organization level based on folder depth
        if hierarchy_level == 0:
            organization_level = 'flat'
        elif hierarchy_level <= 2:
            organization_level = 'structured'
        else:
            organization_level = 'highly_organized'
        
        structure = {
            'original_filename': filename,
            'base_name': name_without_ext,
            'category': category,
            'subcategory': subcategory,
            'document_type': 'document',
            'hierarchy_level': hierarchy_level,
            'virtual_path': virtual_path,
            'folder_indicators': ['user_defined'] if folder_path else [],
            'content_type_hints': [],
            'organization_level': organization_level,
            'original_folder_path': folder_path  # Store original folder path for reference
        }
        
        logger.debug(f"📁 PRESERVE ORIGINAL: {filename} -> {virtual_path}")
        return structure

    def _build_llm_structure_path(self, filename: str, folder_path: str) -> Dict[str, Any]:
        """
        Build virtual path using an LLM-decided folder_path instead of uploaded folder names.
        Example:
          folder_path="Legal/Contracts" -> documents/Legal/Contracts/<file_only>
        """
        normalized_filename = (filename or "").replace('\\', '/')
        normalized_filename = re.sub(r'/+', '/', normalized_filename)
        normalized_filename = normalized_filename.strip('/')

        if '/' in normalized_filename:
            _, file_only = normalized_filename.rsplit('/', 1)
        else:
            file_only = normalized_filename

        if not file_only:
            logger.warning("Empty file name detected while building LLM structure path; using Path().name fallback")
            file_only = Path(filename).name or filename or "unknown_file"

        file_only = str(file_only).strip()
        name_without_ext = Path(file_only).stem.lower()

        folder_path = (folder_path or "").replace('\\', '/').strip('/')
        folder_levels = [p for p in folder_path.split('/') if p.strip()]
        if not folder_levels:
            # Keep behavior predictable if the LLM produced an empty/invalid folder path.
            folder_levels = []

        category = folder_levels[0] if len(folder_levels) >= 1 else 'General'
        subcategory = folder_levels[1] if len(folder_levels) >= 2 else None
        hierarchy_level = len(folder_levels)

        if hierarchy_level == 0:
            organization_level = 'flat'
        elif hierarchy_level <= 2:
            organization_level = 'structured'
        else:
            organization_level = 'highly_organized'

        if folder_levels:
            safe_folder_path = '/'.join(folder_levels[:2])
            virtual_path = f'documents/{safe_folder_path}/{file_only}'
        else:
            virtual_path = f'documents/{file_only}'

        structure = {
            'original_filename': filename,
            'base_name': name_without_ext,
            'category': category,
            'subcategory': subcategory,
            'document_type': 'document',
            'hierarchy_level': hierarchy_level,
            'virtual_path': virtual_path,
            'folder_indicators': ['llm_organized'] if folder_levels else [],
            'content_type_hints': [],
            'organization_level': organization_level,
            # Store the LLM-chosen folder path for reference/debugging.
            'original_folder_path': '/'.join(folder_levels[:2]) if folder_levels else '',
        }

        logger.debug("📁 LLM FOLDER ORG: %s -> %s", filename, virtual_path)
        return structure
    
    def _build_auto_classified_path(self, filename: str) -> Dict[str, Any]:
        """Build virtual path using auto-classification based on filename patterns"""
        name_without_ext = Path(filename).stem.lower()
        
        # Initialize structure
        structure = {
            'original_filename': filename,
            'base_name': name_without_ext,
            'category': 'general',
            'subcategory': None,
            'document_type': 'document',
            'hierarchy_level': 0,
            'virtual_path': f'documents/general/{filename}',
            'folder_indicators': [],
            'content_type_hints': [],
            'organization_level': 'flat'
        }
        
        # Detect category and subcategory
        category_patterns = {
            'legal': {
                'patterns': ['legal', 'law', 'contract', 'agreement', 'policy', 'terms', 'conditions'],
                'subcategories': {
                    'contracts': ['contract', 'agreement', 'mou', 'nda'],
                    'policies': ['policy', 'procedure', 'guideline'],
                    'compliance': ['compliance', 'audit', 'regulation']
                }
            },
            'medical': {
                'patterns': ['medical', 'health', 'patient', 'clinical', 'diagnosis', 'treatment'],
                'subcategories': {
                    'reports': ['report', 'summary', 'analysis'],
                    'records': ['record', 'history', 'chart'],
                    'procedures': ['procedure', 'protocol', 'guideline']
                }
            },
            'technical': {
                'patterns': ['tech', 'spec', 'manual', 'guide', 'documentation', 'api'],
                'subcategories': {
                    'specifications': ['spec', 'specification', 'requirement'],
                    'manuals': ['manual', 'guide', 'handbook'],
                    'documentation': ['doc', 'documentation', 'readme']
                }
            },
            'research': {
                'patterns': ['research', 'study', 'analysis', 'report', 'paper', 'thesis'],
                'subcategories': {
                    'papers': ['paper', 'article', 'publication'],
                    'reports': ['report', 'study', 'analysis'],
                    'data': ['data', 'dataset', 'results']
                }
            },
            'financial': {
                'patterns': ['financial', 'budget', 'invoice', 'payment', 'cost', 'expense'],
                'subcategories': {
                    'budgets': ['budget', 'forecast', 'projection'],
                    'invoices': ['invoice', 'bill', 'receipt'],
                    'reports': ['report', 'statement', 'summary']
                }
            }
        }
        
        # Find category and subcategory
        for category, config in category_patterns.items():
            if any(pattern in name_without_ext for pattern in config['patterns']):
                structure['category'] = category
                structure['hierarchy_level'] = 1
                
                # Find subcategory
                for subcat, patterns in config['subcategories'].items():
                    if any(pattern in name_without_ext for pattern in patterns):
                        structure['subcategory'] = subcat
                        structure['hierarchy_level'] = 2
                        break
                break
        
        # Detect document type and content hints
        document_types = {
            'report': ['report', 'summary', 'overview', 'analysis'],
            'manual': ['manual', 'guide', 'handbook', 'instructions'],
            'specification': ['spec', 'specification', 'requirements'],
            'policy': ['policy', 'procedure', 'protocol'],
            'presentation': ['presentation', 'slides', 'deck'],
            'correspondence': ['email', 'letter', 'memo', 'note']
        }
        
        for doc_type, patterns in document_types.items():
            if any(pattern in name_without_ext for pattern in patterns):
                structure['document_type'] = doc_type
                structure['content_type_hints'].append(doc_type)
        
        # Detect organizational patterns
        org_patterns = {
            'dated': [r'20\d{2}[-_]\d{2}[-_]\d{2}', r'20\d{2}[-_]\d{2}', r'20\d{2}'],
            'versioned': [r'v\d+', r'version', r'draft', r'final', r'rev'],
            'sectioned': [r'part\d+', r'section\d+', r'chapter\d+'],
            'numbered': [r'^\d+[-_]', r'[-_]\d+[-_]']
        }
        
        for pattern_type, patterns in org_patterns.items():
            for pattern in patterns:
                if re.search(pattern, name_without_ext):
                    structure['folder_indicators'].append(pattern_type)
                    structure['hierarchy_level'] += 1
        
        # Build virtual path
        path_parts = ['documents']
        
        if structure['category'] != 'general':
            path_parts.append(structure['category'])
            
        if structure['subcategory']:
            path_parts.append(structure['subcategory'])
            
        # Add organizational structure
        if 'dated' in structure['folder_indicators']:
            # Extract year if possible
            year_match = re.search(r'20\d{2}', name_without_ext)
            if year_match:
                path_parts.append(year_match.group())
                
        if 'versioned' in structure['folder_indicators']:
            path_parts.append('versions')
            
        path_parts.append(filename)
        structure['virtual_path'] = '/'.join(path_parts)
        
        # Determine organization level
        if structure['hierarchy_level'] == 0:
            structure['organization_level'] = 'flat'
        elif structure['hierarchy_level'] <= 2:
            structure['organization_level'] = 'structured'
        else:
            structure['organization_level'] = 'highly_organized'
        
        return structure
    
    def _process_document_enhanced(self, document: Any, filename_hierarchy: Dict[str, Any]) -> Optional[HierarchicalDocumentInfo]:
        """Process a single document with robust extraction and hierarchical chunking."""
        logger.info(f"🚀 Starting enhanced processing for document: {document.original_filename} (ID: {document.id})")
        
        try:
            # 1. Extract and validate content
            logger.info(f"   [1/5]  EXTRACTING content...")
            content = self._extract_document_content(document)
            
            if not content or is_binary(content):
                logger.error(f"❌ Failed to extract valid text content from {document.original_filename}. Aborting processing for this document.")
                return None
            logger.info(f"   [1/5] ✔️ EXTRACTION successful. Content length: {len(content)} chars.")

            # 2. Get hierarchical info and build metadata
            logger.info(f"   [2/5] BUILDING metadata...")
            hier_info = filename_hierarchy['documents'].get(document.id, {})
            document_metadata = self._build_enhanced_metadata(document, hier_info, content)
            logger.info(f"   [2/5] ✔️ METADATA built. Category: '{document_metadata['category']}', Virtual Path: '{document_metadata['virtual_path']}'")
            
            # 3. Analyze content structure
            logger.info(f"   [3/5] ANALYZING content structure...")
            content_map = self._analyze_content_structure(content, hier_info)
            logger.info(f"   [3/5] ✔️ ANALYSIS complete. Structure type: '{content_map['structure_type']}', Sections found: {len(content_map['sections'])}")
            
            # 4. Create hierarchical chunks
            logger.info(f"   [4/5] CREATING hierarchical chunks...")
            chunks = self._create_hierarchical_chunks(content, document_metadata, hier_info, content_map)
            
            if not chunks:
                logger.warning(f"⚠️ No chunks were created for {document.original_filename}. Aborting.")
                return None
            logger.info(f"   [4/5] ✔️ CHUNKING successful. Created {len(chunks)} chunks.")

            # 5. Create document-level embedding
            logger.info(f"   [5/5] CREATING document-level embedding...")
            summary_for_embedding = chunks[0].content[:1000]
            doc_embedding = self.embedder.create_embeddings(summary_for_embedding)
            logger.info(f"   [5/5] ✔️ EMBEDDING created for document.")
            
            logger.info(f"✅ Successfully processed document: {document.original_filename}")
            return HierarchicalDocumentInfo(
                original_content=content,
                document_metadata=document_metadata,
                chunks=chunks,
                content_map=content_map,
                embedding=doc_embedding
            )
            
        except Exception as e:
            logger.exception(f"💥 Unhandled exception while processing {document.original_filename}: {e}")
            return None
    
    def _build_enhanced_metadata(self, document: Any, hier_info: Dict[str, Any], content: str) -> Dict[str, Any]:
        """Build comprehensive metadata for the document"""
        return {
            'document_id': str(document.document_id),
            'project_id': str(document.project.project_id),
            'file_name': document.original_filename,
            'file_type': document.file_type,
            'file_size': document.file_size,
            'uploaded_at': document.uploaded_at.isoformat(),
            'uploaded_by': document.uploaded_by.email,
            'virtual_path': hier_info.get('virtual_path', f"documents/general/{document.original_filename}"),
            'category': hier_info.get('category', 'general'),
            'subcategory': hier_info.get('subcategory'),
            'document_type': hier_info.get('document_type', 'document'),
            'hierarchy_level': hier_info.get('hierarchy_level', 0),
            'organization_level': hier_info.get('organization_level', 'flat'),
            'folder_indicators': hier_info.get('folder_indicators', []),
            'content_type_hints': hier_info.get('content_type_hints', []),
            'original_content_length': len(content),
            'estimated_reading_time': len(content.split()) // 200,
            'processed_at': datetime.now().isoformat(),
            'total_chunks': 0,
            'chunk_strategy': 'enhanced_hierarchical',
            'max_chunk_size': self.max_chunk_size
        }
    
    def _analyze_content_structure(self, content: str, hier_info: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze document content structure for intelligent chunking."""
        content_map = {
            'total_length': len(content),
            'estimated_chunks': (len(content) + self.max_chunk_size - 1) // self.max_chunk_size,
            'content_type': hier_info.get('document_type', 'document'),
            'sections': [],
            'structure_type': 'linear'
        }
        
        lines = content.split('\n')
        potential_headers = []
        header_patterns = [
            r'^\d+\.\s+', r'^[A-Z][A-Z\s]+$', r'^#+\s+', 
            r'^[IVX]+\.\s+', r'^(Chapter|Section|Part)\s+\d+'
        ]

        for i, line in enumerate(lines):
            line_stripped = line.strip()
            if 0 < len(line_stripped) < 100:
                for pattern in header_patterns:
                    if re.match(pattern, line_stripped, re.IGNORECASE):
                        potential_headers.append({
                            'line_index': i,
                            'title': line_stripped,
                            'char_position': sum(len(l) + 1 for l in lines[:i])
                        })
                        logger.info(f"Found potential header: '{line_stripped}'")
                        break
        
        if potential_headers:
            content_map['sections'] = potential_headers
            content_map['structure_type'] = 'sectioned'
        
        return content_map
    
    def _create_hierarchical_chunks(self, content: str, document_metadata: Dict[str, Any], 
                                  hier_info: Dict[str, Any], content_map: Dict[str, Any]) -> List[DocumentChunk]:
        """Create hierarchical chunks, splitting if necessary."""
        chunks = []
        logger.info(f"   [4.1] Determining chunking strategy...")
        
        # CORRECTED LOGIC: Split if content is large OR if sections are detected.
        if len(content) > self.max_chunk_size or (content_map['structure_type'] == 'sectioned' and content_map['sections']):
            if content_map['structure_type'] == 'sectioned' and content_map['sections']:
                logger.info("   [4.1] Strategy: Section-based chunking.")
                chunks = self._create_section_based_chunks(content, document_metadata, hier_info, content_map)
            else:
                logger.info("   [4.1] Strategy: Sequential chunking for large content.")
                chunks = self._create_sequential_chunks(content, document_metadata, hier_info, content_map)
        else:
            # If content is small and has no sections, create a single chunk.
            logger.info("   [4.1] Strategy: Single chunk for small, linear content.")
            chunk = self._create_single_chunk(
                content=content, chunk_index=0, total_chunks=1,
                document_metadata=document_metadata, hier_info=hier_info,
                chunk_type='complete_document', section_title='Complete Document'
            )
            chunks.append(chunk)
        
        # Finalize chunk metadata
        logger.info(f"   [4.2] Finalizing and creating embeddings for {len(chunks)} chunks...")
        total_chunks = len(chunks)
        document_metadata['total_chunks'] = total_chunks
        for i, chunk in enumerate(chunks):
            chunk.total_chunks = total_chunks
            if chunk.metadata:
                chunk.metadata['total_chunks'] = total_chunks

        # Batch embedding: collect all chunks needing embeddings and process in one call
        chunks_needing_embeddings = [(i, chunk) for i, chunk in enumerate(chunks) if chunk.embedding is None]
        if chunks_needing_embeddings:
            try:
                texts = [chunk.content for _, chunk in chunks_needing_embeddings]
                logger.info(f"      [4.2] Batch embedding {len(texts)} chunks...")
                embeddings = self.embedder.batch_create_embeddings(texts)
                for idx, (_, chunk) in enumerate(chunks_needing_embeddings):
                    chunk.embedding = embeddings[idx]
                logger.info(f"      [4.2] ✅ Batch embedded {len(texts)} chunks")
            except Exception as e:
                logger.error(f"      [4.2] ❌ Batch embedding failed, falling back to per-chunk: {e}")
                for i, chunk in chunks_needing_embeddings:
                    if chunk.embedding is None:
                        try:
                            chunk.embedding = self.embedder.create_embeddings(chunk.content)
                        except Exception as chunk_err:
                            logger.error(f"      [4.2.{i+1}] ❌ Failed to create embedding for chunk {chunk.chunk_index}: {chunk_err}")

        logger.info(f"   [4.2] ✔️ All chunks finalized.")
        return chunks
    
    def _create_section_based_chunks(self, content: str, document_metadata: Dict[str, Any], 
                                   hier_info: Dict[str, Any], content_map: Dict[str, Any]) -> List[DocumentChunk]:
        """Create chunks based on detected sections."""
        chunks = []
        sections = content_map['sections']
        section_positions = []

        for i, section in enumerate(sections):
            start_pos = section['char_position']
            end_pos = sections[i + 1]['char_position'] if i + 1 < len(sections) else len(content)
            section_positions.append({
                'title': section['title'],
                'content': content[start_pos:end_pos].strip()
            })
        
        chunk_index = 0
        
        # Handle content before the first section as an introduction
        if sections and sections[0]['char_position'] > 0:
            intro_content = content[:sections[0]['char_position']].strip()
            if intro_content:
                intro_chunks = self._split_large_content(
                    intro_content, chunk_index, document_metadata, hier_info, 
                    'introduction', 'Document Introduction'
                )
                chunks.extend(intro_chunks)
                chunk_index += len(intro_chunks)
        
        # Process each section
        for section_info in section_positions:
            if section_info['content']:
                section_chunks = self._split_large_content(
                    section_info['content'], chunk_index, document_metadata, hier_info,
                    'section', section_info['title']
                )
                chunks.extend(section_chunks)
                chunk_index += len(section_chunks)
        
        return chunks
    
    def _create_sequential_chunks(self, content: str, document_metadata: Dict[str, Any], 
                                hier_info: Dict[str, Any], content_map: Dict[str, Any]) -> List[DocumentChunk]:
        """Create sequential chunks for large, non-sectioned content."""
        chunks = []
        content_parts = self._split_content_intelligently(content)
        
        for i, part in enumerate(content_parts):
            chunk = self._create_single_chunk(
                content=part, chunk_index=i, total_chunks=0,
                document_metadata=document_metadata, hier_info=hier_info,
                chunk_type='content', section_title=f'Content Part {i + 1}'
            )
            chunks.append(chunk)
            
        return chunks
    
    def _split_content_intelligently(self, content: str) -> List[str]:
        """Split content into parts, respecting paragraph boundaries."""
        if len(content) <= self.max_chunk_size:
            return [content]
        
        parts = []
        current_chunk = ""
        paragraphs = content.split('\n\n')

        for para in paragraphs:
            para = para.strip()
            if not para:
                continue
            
            if len(current_chunk) + len(para) + 2 > self.max_chunk_size:
                if current_chunk:
                    parts.append(current_chunk)
                # If a single paragraph is too long, split it by sentences
                if len(para) > self.max_chunk_size:
                    parts.extend(self._split_long_paragraph(para))
                    current_chunk = ""
                else:
                    current_chunk = para
            else:
                current_chunk += ("\n\n" + para) if current_chunk else para
        
        if current_chunk:
            parts.append(current_chunk)
        
        return parts

    def _split_long_paragraph(self, paragraph: str) -> List[str]:
        """Split a very long paragraph by sentences."""
        parts = []
        current_chunk = ""
        # Split by sentences, keeping the delimiter
        sentences = re.split(r'(?<=[.!?])\s+', paragraph)

        for sent in sentences:
            if len(current_chunk) + len(sent) + 1 > self.max_chunk_size:
                if current_chunk:
                    parts.append(current_chunk)
                # If a single sentence is too long, it must be truncated
                if len(sent) > self.max_chunk_size:
                    parts.append(sent[:self.max_chunk_size])
                    current_chunk = ""
                else:
                    current_chunk = sent
            else:
                current_chunk += (" " + sent) if current_chunk else sent

        if current_chunk:
            parts.append(current_chunk)
            
        return parts

    def _split_large_content(self, content: str, start_index: int, document_metadata: Dict[str, Any], 
                           hier_info: Dict[str, Any], chunk_type: str, section_title: str) -> List[DocumentChunk]:
        """Helper to split a large block of content and create chunks."""
        content_parts = self._split_content_intelligently(content)
        chunks = []
        
        for i, part in enumerate(content_parts):
            chunk = self._create_single_chunk(
                content=part, chunk_index=start_index + i, total_chunks=0,
                document_metadata=document_metadata, hier_info=hier_info,
                chunk_type=f"{chunk_type}_part" if len(content_parts) > 1 else chunk_type,
                section_title=f"{section_title} (Part {i + 1})" if len(content_parts) > 1 else section_title
            )
            chunks.append(chunk)
        
        return chunks

    def _create_single_chunk(self, content: str, chunk_index: int, total_chunks: int,
                           document_metadata: Dict[str, Any], hier_info: Dict[str, Any],
                           chunk_type: str, section_title: str) -> DocumentChunk:
        """Create a single document chunk (no summary/topic generation)."""
        
        logger.info(f"      Creating chunk {chunk_index} ('{chunk_type}' / '{section_title}')...")
        
        base_path = hier_info.get('virtual_path', f"documents/general/{document_metadata['file_name']}")
        path_parts = base_path.split('/')
        file_part = path_parts[-1]
        folder_path = '/'.join(path_parts[:-1])
        chunk_hierarchical_path = f"{folder_path}/{file_part}#chunk_{chunk_index:03d}"
        
        chunk_id = str(uuid.uuid4())
        chunk_metadata = {
            **document_metadata,
            'chunk_id': chunk_id,
            'chunk_index': chunk_index,
            'chunk_type': chunk_type,
            'section_title': section_title,
            'content_length': len(content),
        }
        
        logger.info(f"      ✔️ Chunk {chunk_index} created successfully.")
        return DocumentChunk(
            content=content,
            chunk_index=chunk_index,
            total_chunks=total_chunks,
            chunk_id=chunk_id,
            parent_document_id=document_metadata['document_id'],
            hierarchical_path=chunk_hierarchical_path,
            chunk_type=chunk_type,
            section_title=section_title,
            embedding=None, # Embedding is now created in the main loop
            metadata=chunk_metadata
        )
    
    def _extract_document_content(self, document: Any) -> Optional[str]:
        """
        Robustly extracts text content from a document.
        It prioritizes fresh extraction and validates any pre-existing text.
        """
        filename = document.original_filename
        logger.info(f"   [1.1] Starting content extraction for: {filename}")

        # 1. Get the file path
        file_path = get_file_path(document)
        if not file_path:
            # If file doesn't exist, check for existing text but be skeptical
            if hasattr(document, 'extraction_text') and document.extraction_text:
                existing_text = document.extraction_text.strip()
                if not is_binary(existing_text):
                    logger.warning(f"   [1.1] ⚠️ File for {filename} not found, but using valid existing text from database.")
                    return existing_text
            logger.error(f"   [1.1] ❌ File for {filename} not found and no valid existing text. Aborting.")
            return self._generate_placeholder_content(document, "File not found on server.")

        # 2. Prioritize fresh extraction from the file
        file_ext = getattr(document, 'file_extension', Path(filename).suffix).lower()
        extracted_content = None
        
        # Debug logging
        logger.info(f"   [1.2] File extension is '{file_ext}'. Attempting extraction.")
        logger.info(f"   [1.2] Document file_type: {getattr(document, 'file_type', 'Not set')}")
        logger.info(f"   [1.2] Filename: {filename}")
        logger.info(f"   [1.2] Filename ends with .pdf: {filename.lower().endswith('.pdf')}")
        
        try:
            # Use Ollama vision extractor when Ollama is the provider
            if self.llm_provider == 'ollama':
                try:
                    from .ollama_vision_extractor import OllamaVisionExtractor
                    vision = OllamaVisionExtractor(model=self.llm_model)
                    extracted_content = vision.extract_document_text(file_path, file_ext.strip('.'))
                    if extracted_content and len(extracted_content) > 50:
                        logger.info(f"   [1.2] ✅ Ollama vision extracted {len(extracted_content)} chars from {filename}")
                    else:
                        logger.warning(f"   [1.2] ⚠️ Ollama vision returned insufficient text, falling back to standard extraction")
                        extracted_content = None
                except Exception as e:
                    logger.warning(f"   [1.2] ⚠️ Ollama vision failed for {filename}: {e}, falling back")
                    extracted_content = None

            # Standard extraction (fallback or when not using Ollama)
            if not extracted_content:
                # More robust PDF detection
                is_pdf = (file_ext == '.pdf' or
                         filename.lower().endswith('.pdf') or
                         (hasattr(document, 'file_type') and 'pdf' in document.file_type.lower()))

                logger.info(f"   [1.2] PDF detection result: {is_pdf}")

                if is_pdf:
                    logger.info(f"   [1.2] 📔 Starting PDF extraction for {filename}")
                    extracted_content = self._extract_pdf_content_properly(file_path, filename)
                elif file_ext in ['.txt', '.text', '.md', '.rtf']:
                    logger.info(f"   [1.2] 📄 Starting text extraction for {filename}")
                    extracted_content = self._extract_text_content(file_path, filename)
                elif file_ext in ['.docx', '.doc']:
                    logger.info(f"   [1.2] 📃 Starting Word extraction for {filename}")
                    extracted_content = self._extract_word_content(file_path, filename)
                else:
                    logger.warning(f"   [1.2] ⚠️ Unsupported file type {file_ext} for {filename}.")
                    return self._generate_placeholder_content(document, f"Unsupported file type: {file_ext}")
        except Exception as e:
            logger.exception(f"   [1.2] 💥 Extraction failed for {filename}: {e}")
            return self._generate_placeholder_content(document, "A critical error occurred during content extraction.")

        # 3. Validate the extracted content
        logger.info(f"   [1.3] Validating extracted content...")
        if not extracted_content or is_binary(extracted_content):
            logger.error(f"   [1.3] ❌ Extraction from {filename} resulted in invalid or binary content.")
            return self._generate_placeholder_content(document, "Content could not be extracted or appears to be binary.")
        logger.info(f"   [1.3] ✔️ Content is valid text.")

        # 4. If successful, update the document object for future use
        try:
            document.extraction_text = extracted_content
            document.save(update_fields=['extraction_text'])
            logger.info(f"   [1.4] ✔️ Successfully extracted and saved text for {filename}.")
        except Exception as e:
            logger.warning(f"   [1.4] ⚠️ Could not save extracted text back to document {filename}: {e}")

        return extracted_content
    
    def _extract_pdf_content_properly(self, file_path: str, filename: str) -> str:
        """Extract text from PDF using Gemini with automatic fallback to PyPDF2/pdfplumber."""
        
        logger.info(f"      [PDF] Attempting PDF extraction for {filename}")
        logger.info(f"      [PDF] File path: {file_path}")
        
        try:
            # Check if file exists and is readable
            if not os.path.exists(file_path):
                raise FileNotFoundError(f"PDF file not found: {file_path}")
                
            if not os.access(file_path, os.R_OK):
                raise PermissionError(f"PDF file not readable: {file_path}")
                
            # Check file size
            file_size = os.path.getsize(file_path)
            logger.info(f"      [PDF] File size: {file_size} bytes")
            
            if file_size == 0:
                raise ValueError(f"PDF file is empty: {file_path}")
            
            # Get Gemini extractor (may be None if not initialized)
            gemini_extractor = get_gemini_extractor()
            
            # If Gemini extractor is available, try it first
            if gemini_extractor and hasattr(gemini_extractor, 'gemini_available') and gemini_extractor.gemini_available:
                logger.info(f"      [PDF] Gemini extractor available, attempting Gemini extraction...")
                try:
                    text = gemini_extractor.extract_pdf_text(file_path)
                    
                    if text and not is_binary(text):
                        logger.info(f"      [PDF] ✅ Gemini extraction successful for {filename} - extracted {len(text)} characters")
                        return text
                    else:
                        logger.warning(f"      [PDF] ⚠️ Gemini extraction returned empty or binary content, falling back to PyPDF2/pdfplumber")
                except Exception as gemini_error:
                    logger.warning(f"      [PDF] ⚠️ Gemini extraction failed: {gemini_error}, falling back to PyPDF2/pdfplumber")
            else:
                logger.info(f"      [PDF] Gemini extractor not available, using fallback methods (PyPDF2/pdfplumber)")
            
            # Fallback: Use PyPDF2/pdfplumber directly
            # The extract_pdf_text method already has fallback, but if extractor is None, we need to do it ourselves
            if gemini_extractor:
                # Try the extractor's fallback method
                logger.info(f"      [PDF] Using extractor's fallback method...")
                text = gemini_extractor._fallback_pdf_extraction(file_path)
            else:
                # Direct fallback if no extractor at all
                logger.info(f"      [PDF] Using direct PyPDF2/pdfplumber fallback...")
                text = self._fallback_pdf_extraction_direct(file_path)
            
            if not text or is_binary(text):
                raise ValueError(f"Fallback PDF extraction returned empty or binary content for {filename}")
                
            logger.info(f"      [PDF] ✅ Fallback extraction successful for {filename} - extracted {len(text)} characters")
            return text

        except Exception as e:
            logger.error(f"      [PDF] 💥 All PDF extraction methods failed for {filename}: {e}")
            logger.error(f"      [PDF] Exception type: {type(e).__name__}")
            # Re-raise to trigger placeholder generation
            raise RuntimeError(f"Failed to extract content from PDF '{filename}': {str(e)}") from e
    
    def _fallback_pdf_extraction_direct(self, file_path: str) -> str:
        """Direct fallback PDF extraction using PyPDF2/pdfplumber when Gemini extractor is not available."""
        try:
            import pdfplumber
            logger.info(f"      [PDF] Attempting pdfplumber extraction...")
            with pdfplumber.open(file_path) as pdf:
                text = '\n\n'.join(page.extract_text() or '' for page in pdf.pages)
                if text and text.strip():
                    return text
        except Exception as e:
            logger.warning(f"      [PDF] pdfplumber failed: {e}, trying PyPDF2...")
        
        try:
            import PyPDF2
            logger.info(f"      [PDF] Attempting PyPDF2 extraction...")
            with open(file_path, 'rb') as f:
                pdf_reader = PyPDF2.PdfReader(f)
                text = '\n\n'.join(page.extract_text() or '' for page in pdf_reader.pages)
                if text and text.strip():
                    return text
        except Exception as e:
            logger.error(f"      [PDF] PyPDF2 extraction also failed: {e}")
        
        return ""

    def _extract_text_content(self, file_path: str, filename: str) -> str:
        """Extract content from text files."""
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                return f.read()
        except Exception as e:
            logger.error(f"Text extraction failed for {filename}: {e}")
            return ""

    def _extract_word_content(self, file_path: str, filename: str) -> str:
        """Extract content from Word documents."""
        try:
            from docx import Document
            doc = Document(file_path)
            return '\n\n'.join(p.text for p in doc.paragraphs if p.text.strip())
        except ImportError:
            logger.error("python-docx is not installed. Cannot extract from Word documents.")
        except Exception as e:
            logger.error(f"Word extraction failed for {filename}: {e}")
        return ""
    
    def _generate_placeholder_content(self, document: Any, reason: str) -> str:
        """Generate meaningful placeholder content for unsupported or failed files."""
        filename = getattr(document, 'original_filename', 'unknown')
        file_type = getattr(document, 'file_type', 'unknown')
        logger.warning(f"Generating placeholder for {filename}. Reason: {reason}")
        
        return f"""Document: {filename}
File Type: {file_type}
Extraction Status: FAILED
Reason: {reason}

This document could not be processed automatically. 
Manual inspection or a different extraction tool may be required."""

class EnhancedHierarchicalChunkMapper:
    """Utility class for mapping chunks back to document hierarchy"""
    
    @staticmethod
    def map_chunks_to_hierarchy(chunks: List[DocumentChunk]) -> Dict[str, Any]:
        """Create a hierarchical map of chunks"""
        hierarchy_map = {
            'root': {},
            'by_document': {},
            'by_category': {},
            'by_section': {},
            'flat_list': chunks
        }
        
        for chunk in chunks:
            doc_id = chunk.parent_document_id
            
            # Group by document
            if doc_id not in hierarchy_map['by_document']:
                hierarchy_map['by_document'][doc_id] = []
            hierarchy_map['by_document'][doc_id].append(chunk)
            
            # Group by category
            if chunk.metadata:
                category = chunk.metadata.get('category', 'general')
                if category not in hierarchy_map['by_category']:
                    hierarchy_map['by_category'][category] = []
                hierarchy_map['by_category'][category].append(chunk)
                
                # Group by section type
                section_type = chunk.chunk_type
                if section_type not in hierarchy_map['by_section']:
                    hierarchy_map['by_section'][section_type] = []
                hierarchy_map['by_section'][section_type].append(chunk)
        
        return hierarchy_map
    
    @staticmethod
    def get_chunk_hierarchy_path(chunk: DocumentChunk) -> List[str]:
        """Get the full hierarchical path for a chunk"""
        if chunk.hierarchical_path:
            return chunk.hierarchical_path.split('/')
        return ['documents', 'general', 'unknown', 'chunks', f'chunk_{chunk.chunk_index}']
    
    @staticmethod
    def rebuild_document_from_chunks(chunks: List[DocumentChunk]) -> str:
        """Rebuild complete document content from chunks"""
        # Sort chunks by index
        sorted_chunks = sorted(chunks, key=lambda x: x.chunk_index)
        
        # Combine content
        full_content = ""
        for chunk in sorted_chunks:
            if chunk.chunk_type == 'complete_document':
                return chunk.content
            
            # Add section separator for different sections
            if full_content and chunk.chunk_type in ['section', 'introduction']:
                full_content += "\n\n"
            elif full_content:
                full_content += "\n"
                
            full_content += chunk.content
        
        return full_content