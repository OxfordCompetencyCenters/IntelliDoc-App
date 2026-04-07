"""
Advanced Text Chunking System for ChromaDB Public Chatbot
Supports multiple chunking strategies including large chunks
"""

import re
import logging
from typing import List, Dict, Any, Tuple, Optional
from dataclasses import dataclass
from enum import Enum
import hashlib

logger = logging.getLogger('public_chatbot.chunking')


class ChunkStrategy(Enum):
    """Available chunking strategies"""
    SMALL_SEMANTIC = "small_semantic"      # 512 tokens, overlap 50
    MEDIUM_SEMANTIC = "medium_semantic"    # 1024 tokens, overlap 100  
    LARGE_SEMANTIC = "large_semantic"      # 2048 tokens, overlap 200
    XLARGE_SEMANTIC = "xlarge_semantic"    # 4096 tokens, overlap 300
    PARAGRAPH_BASED = "paragraph_based"    # Natural paragraph breaks
    SECTION_BASED = "section_based"        # Headers and sections
    HYBRID = "hybrid"                      # Multiple strategies combined


@dataclass
class ChunkConfig:
    """Configuration for chunking strategy"""
    strategy: ChunkStrategy
    max_tokens: int
    overlap_tokens: int
    preserve_sentences: bool = True
    preserve_paragraphs: bool = True
    min_chunk_size: int = 50
    max_chunks_per_document: int = 50


@dataclass
class DocumentChunk:
    """Represents a single chunk of a document"""
    chunk_id: str
    parent_document_id: str
    content: str
    chunk_index: int
    total_chunks: int
    chunk_type: str
    token_count: int
    char_count: int
    metadata: Dict[str, Any]
    overlap_start: int = 0
    overlap_end: int = 0


class AdvancedTextChunker:
    """
    Professional text chunking system supporting multiple strategies
    Designed for ChromaDB optimization with large chunk support
    """
    
    # Predefined chunk configurations
    CHUNK_CONFIGS = {
        ChunkStrategy.SMALL_SEMANTIC: ChunkConfig(
            strategy=ChunkStrategy.SMALL_SEMANTIC,
            max_tokens=512,
            overlap_tokens=50,
            preserve_sentences=True
        ),
        ChunkStrategy.MEDIUM_SEMANTIC: ChunkConfig(
            strategy=ChunkStrategy.MEDIUM_SEMANTIC, 
            max_tokens=1024,
            overlap_tokens=100,
            preserve_sentences=True
        ),
        ChunkStrategy.LARGE_SEMANTIC: ChunkConfig(
            strategy=ChunkStrategy.LARGE_SEMANTIC,
            max_tokens=2048, 
            overlap_tokens=750,
            preserve_sentences=True
        ),
        ChunkStrategy.XLARGE_SEMANTIC: ChunkConfig(
            strategy=ChunkStrategy.XLARGE_SEMANTIC,
            max_tokens=4096,
            overlap_tokens=750,
            preserve_sentences=True
        ),
        ChunkStrategy.PARAGRAPH_BASED: ChunkConfig(
            strategy=ChunkStrategy.PARAGRAPH_BASED,
            max_tokens=1500,
            overlap_tokens=0,
            preserve_paragraphs=True
        ),
        ChunkStrategy.SECTION_BASED: ChunkConfig(
            strategy=ChunkStrategy.SECTION_BASED,
            max_tokens=3000,
            overlap_tokens=100,
            preserve_paragraphs=True
        )
    }
    
    def __init__(self, strategy: ChunkStrategy = ChunkStrategy.LARGE_SEMANTIC):
        """
        Initialize chunker with specified strategy
        
        Args:
            strategy: Chunking strategy to use
        """
        self.strategy = strategy
        self.config = self.CHUNK_CONFIGS[strategy]
        logger.info(f"📄 CHUNKER: Initialized with {strategy.value} strategy")
    
    def chunk_document(
        self, 
        content: str, 
        document_id: str, 
        metadata: Optional[Dict[str, Any]] = None
    ) -> List[DocumentChunk]:
        """
        Chunk a document using the configured strategy
        
        Args:
            content: Full document content
            document_id: Unique document identifier
            metadata: Additional metadata to include
            
        Returns:
            List of DocumentChunk objects
        """
        if not content or not content.strip():
            logger.warning(f"📄 CHUNKER: Empty content for document {document_id}")
            return []
        
        metadata = metadata or {}
        
        try:
            if self.strategy == ChunkStrategy.PARAGRAPH_BASED:
                chunks = self._chunk_by_paragraphs(content, document_id, metadata)
            elif self.strategy == ChunkStrategy.SECTION_BASED:
                chunks = self._chunk_by_sections(content, document_id, metadata)
            elif self.strategy == ChunkStrategy.HYBRID:
                chunks = self._chunk_hybrid(content, document_id, metadata)
            else:
                # Semantic chunking (all size variants)
                chunks = self._chunk_semantic(content, document_id, metadata)
            
            logger.info(f"📄 CHUNKER: Created {len(chunks)} chunks for document {document_id}")
            return chunks
            
        except Exception as e:
            logger.error(f"📄 CHUNKER: Failed to chunk document {document_id}: {e}")
            # Fallback: return original content as single chunk
            return [self._create_fallback_chunk(content, document_id, metadata)]
    
    def _chunk_semantic(
        self, 
        content: str, 
        document_id: str, 
        metadata: Dict[str, Any]
    ) -> List[DocumentChunk]:
        """
        Semantic chunking with configurable sizes and overlap
        Supports large chunks up to 4096 tokens
        """
        # Split into sentences for better boundary detection
        sentences = self._split_into_sentences(content)
        chunks = []
        current_chunk = ""
        current_tokens = 0
        chunk_index = 0
        
        # Approximate tokens (1 token ≈ 4 characters for English)
        avg_chars_per_token = 4
        max_chars = self.config.max_tokens * avg_chars_per_token
        overlap_chars = self.config.overlap_tokens * avg_chars_per_token
        
        i = 0
        while i < len(sentences):
            sentence = sentences[i]
            sentence_chars = len(sentence)
            
            # Check if adding this sentence would exceed limit
            if current_tokens + sentence_chars > max_chars and current_chunk:
                # Create chunk
                chunk = self._create_chunk(
                    content=current_chunk.strip(),
                    document_id=document_id,
                    chunk_index=chunk_index,
                    metadata=metadata,
                    chunk_type=self.strategy.value
                )
                chunks.append(chunk)
                
                # Prepare for next chunk with overlap
                if self.config.overlap_tokens > 0:
                    overlap_content = self._get_overlap_content(
                        current_chunk, overlap_chars
                    )
                    current_chunk = overlap_content + " " + sentence
                    current_tokens = len(overlap_content) + sentence_chars
                else:
                    current_chunk = sentence
                    current_tokens = sentence_chars
                
                chunk_index += 1
            else:
                # Add sentence to current chunk
                current_chunk += (" " if current_chunk else "") + sentence
                current_tokens += sentence_chars
            
            i += 1
        
        # Add final chunk if there's content
        if current_chunk.strip():
            chunk = self._create_chunk(
                content=current_chunk.strip(),
                document_id=document_id, 
                chunk_index=chunk_index,
                metadata=metadata,
                chunk_type=self.strategy.value
            )
            chunks.append(chunk)
        
        # Update total chunks count
        for chunk in chunks:
            chunk.total_chunks = len(chunks)
        
        return chunks
    
    def _chunk_by_paragraphs(
        self, 
        content: str, 
        document_id: str, 
        metadata: Dict[str, Any]
    ) -> List[DocumentChunk]:
        """
        Chunk by natural paragraph boundaries
        Good for preserving document structure
        """
        paragraphs = [p.strip() for p in content.split('\n\n') if p.strip()]
        chunks = []
        
        for i, paragraph in enumerate(paragraphs):
            if len(paragraph) > self.config.max_tokens * 4:  # Too large
                # Further split large paragraphs
                sub_chunks = self._chunk_semantic(paragraph, document_id, metadata)
                for j, sub_chunk in enumerate(sub_chunks):
                    sub_chunk.chunk_id = f"{document_id}_para_{i}_{j}"
                    sub_chunk.chunk_index = len(chunks)
                    sub_chunk.chunk_type = "paragraph_split"
                    chunks.append(sub_chunk)
            else:
                chunk = self._create_chunk(
                    content=paragraph,
                    document_id=document_id,
                    chunk_index=i,
                    metadata=metadata,
                    chunk_type="paragraph"
                )
                chunks.append(chunk)
        
        # Update total chunks count
        for chunk in chunks:
            chunk.total_chunks = len(chunks)
        
        return chunks
    
    def _chunk_by_sections(
        self, 
        content: str, 
        document_id: str, 
        metadata: Dict[str, Any]
    ) -> List[DocumentChunk]:
        """
        Chunk by headers and sections
        Ideal for structured documents
        """
        # Detect headers (markdown style or numbered)
        header_patterns = [
            r'^#+\s+(.+)$',          # Markdown headers
            r'^(\d+\.?\s+.+)$',      # Numbered sections
            r'^([A-Z][A-Za-z\s:]+)$' # Title case headers
        ]
        
        lines = content.split('\n')
        sections = []
        current_section = ""
        current_header = ""
        
        for line in lines:
            is_header = False
            for pattern in header_patterns:
                if re.match(pattern, line.strip()):
                    is_header = True
                    break
            
            if is_header and current_section:
                # Save previous section
                sections.append({
                    'header': current_header,
                    'content': current_section.strip()
                })
                current_section = ""
                current_header = line.strip()
            
            current_section += line + '\n'
            
            if is_header:
                current_header = line.strip()
        
        # Add final section
        if current_section.strip():
            sections.append({
                'header': current_header,
                'content': current_section.strip()
            })
        
        chunks = []
        for i, section in enumerate(sections):
            section_content = f"{section['header']}\n\n{section['content']}"
            
            if len(section_content) > self.config.max_tokens * 4:
                # Split large sections
                sub_chunks = self._chunk_semantic(section_content, document_id, metadata)
                for j, sub_chunk in enumerate(sub_chunks):
                    sub_chunk.chunk_id = f"{document_id}_sec_{i}_{j}"
                    sub_chunk.chunk_index = len(chunks) 
                    sub_chunk.chunk_type = "section_split"
                    chunks.append(sub_chunk)
            else:
                chunk = self._create_chunk(
                    content=section_content,
                    document_id=document_id,
                    chunk_index=i,
                    metadata={**metadata, 'section_header': section['header']},
                    chunk_type="section"
                )
                chunks.append(chunk)
        
        # Update total chunks count
        for chunk in chunks:
            chunk.total_chunks = len(chunks)
        
        return chunks
    
    def _chunk_hybrid(
        self, 
        content: str, 
        document_id: str, 
        metadata: Dict[str, Any]
    ) -> List[DocumentChunk]:
        """
        Hybrid approach: Try section-based first, fallback to semantic
        """
        try:
            # Try section-based first
            section_chunker = AdvancedTextChunker(ChunkStrategy.SECTION_BASED)
            chunks = section_chunker._chunk_by_sections(content, document_id, metadata)
            
            # If we get too few or too many chunks, use semantic
            if len(chunks) < 2 or len(chunks) > 20:
                semantic_chunker = AdvancedTextChunker(ChunkStrategy.LARGE_SEMANTIC)
                chunks = semantic_chunker._chunk_semantic(content, document_id, metadata)
            
            return chunks
            
        except Exception:
            # Fallback to semantic chunking
            return self._chunk_semantic(content, document_id, metadata)
    
    def _split_into_sentences(self, text: str) -> List[str]:
        """
        Split text into sentences with improved boundary detection
        """
        # Enhanced sentence splitting
        sentence_endings = r'[.!?]+(?:\s|$)'
        sentences = re.split(sentence_endings, text)
        
        # Clean and filter
        cleaned_sentences = []
        for sentence in sentences:
            sentence = sentence.strip()
            if sentence and len(sentence) > 10:  # Minimum sentence length
                cleaned_sentences.append(sentence)
        
        return cleaned_sentences
    
    def _get_overlap_content(self, content: str, overlap_chars: int) -> str:
        """
        Get the last N characters for overlap, preserving word boundaries
        """
        if overlap_chars <= 0 or len(content) <= overlap_chars:
            return content
        
        # Try to break at word boundary
        overlap_text = content[-overlap_chars:]
        space_pos = overlap_text.find(' ')
        
        if space_pos > 0:
            return overlap_text[space_pos:].strip()
        else:
            return overlap_text
    
    def _create_chunk(
        self, 
        content: str, 
        document_id: str, 
        chunk_index: int, 
        metadata: Dict[str, Any],
        chunk_type: str
    ) -> DocumentChunk:
        """Create a DocumentChunk object"""
        chunk_id = f"{document_id}_chunk_{chunk_index}"
        
        return DocumentChunk(
            chunk_id=chunk_id,
            parent_document_id=document_id,
            content=content,
            chunk_index=chunk_index,
            total_chunks=0,  # Will be updated later
            chunk_type=chunk_type,
            token_count=len(content) // 4,  # Approximate
            char_count=len(content),
            metadata={
                **metadata,
                'chunk_strategy': self.strategy.value,
                'chunk_id': chunk_id
            }
        )
    
    def _create_fallback_chunk(
        self, 
        content: str, 
        document_id: str, 
        metadata: Dict[str, Any]
    ) -> DocumentChunk:
        """Create a single fallback chunk when chunking fails"""
        return DocumentChunk(
            chunk_id=f"{document_id}_fallback_0",
            parent_document_id=document_id,
            content=content,
            chunk_index=0,
            total_chunks=1,
            chunk_type="fallback",
            token_count=len(content) // 4,
            char_count=len(content),
            metadata={**metadata, 'chunk_strategy': 'fallback'}
        )

    @staticmethod
    def estimate_tokens(text: str) -> int:
        """
        Estimate token count for text
        More accurate than simple character division
        """
        # Better token estimation
        words = text.split()
        # Average: 1 token per 0.75 words for English
        return int(len(words) * 1.33)
    
    @staticmethod
    def get_optimal_strategy(content: str, target_chunks: int = 5) -> ChunkStrategy:
        """
        Recommend optimal chunking strategy based on content
        
        Args:
            content: Document content
            target_chunks: Desired number of chunks
            
        Returns:
            Recommended ChunkStrategy
        """
        content_length = len(content)
        estimated_tokens = AdvancedTextChunker.estimate_tokens(content)
        
        if estimated_tokens < 512:
            return ChunkStrategy.SMALL_SEMANTIC
        elif estimated_tokens < 2048:
            return ChunkStrategy.MEDIUM_SEMANTIC
        elif estimated_tokens < 8192:
            return ChunkStrategy.LARGE_SEMANTIC
        else:
            return ChunkStrategy.XLARGE_SEMANTIC