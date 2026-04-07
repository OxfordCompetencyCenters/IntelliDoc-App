"""
Advanced Embedding Strategies for Large Chunks
Supports multiple approaches to handle large text content
"""

import logging
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import numpy as np

# Try importing various embedding models
try:
    from sentence_transformers import SentenceTransformer
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SENTENCE_TRANSFORMERS_AVAILABLE = False

try:
    import torch
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False

logger = logging.getLogger('public_chatbot.embeddings')


class EmbeddingStrategy(Enum):
    """Available embedding strategies for large chunks"""
    TRUNCATION = "truncation"              # Truncate to model limit (current)
    SLIDING_WINDOW = "sliding_window"      # Multiple overlapping windows
    HIERARCHICAL = "hierarchical"          # Summary + detail embeddings
    MEAN_POOLING = "mean_pooling"         # Average of chunk embeddings
    MAX_POOLING = "max_pooling"           # Max of chunk embeddings
    WEIGHTED_AVERAGE = "weighted_average"  # Weighted by chunk importance
    LONGFORMER_STYLE = "longformer"       # Long sequence model (if available)


@dataclass
class EmbeddingConfig:
    """Configuration for embedding strategy"""
    strategy: EmbeddingStrategy
    model_name: str
    max_sequence_length: int
    window_size: int = 256
    window_overlap: int = 50
    use_gpu: bool = False
    normalize_embeddings: bool = True


@dataclass
class EmbeddingResult:
    """Result of embedding operation"""
    embedding: np.ndarray
    strategy_used: str
    model_used: str
    input_tokens: int
    processing_time_ms: float
    chunks_processed: int = 1
    metadata: Dict[str, Any] = None


class LargeChunkEmbedder:
    """
    Advanced embedding system for large text chunks
    Implements multiple strategies to handle text longer than model limits
    """
    
    # Available embedding models with their specifications
    EMBEDDING_MODELS = {
        'all-MiniLM-L6-v2': {
            'max_length': 256,
            'dimension': 384,
            'good_for': ['small_to_medium', 'fast_inference'],
            'description': 'Current model - fast but limited'
        },
        'all-mpnet-base-v2': {
            'max_length': 384, 
            'dimension': 768,
            'good_for': ['better_quality', 'medium_length'],
            'description': 'Better quality, longer sequences'
        },
        'multi-qa-mpnet-base-dot-v1': {
            'max_length': 512,
            'dimension': 768, 
            'good_for': ['qa_tasks', 'longer_context'],
            'description': 'Optimized for Q&A, longer context'
        },
        'paraphrase-multilingual-mpnet-base-v2': {
            'max_length': 512,
            'dimension': 768,
            'good_for': ['multilingual', 'paraphrasing'],
            'description': 'Multilingual support, good for paraphrasing'
        }
    }
    
    def __init__(
        self, 
        strategy: EmbeddingStrategy = EmbeddingStrategy.SLIDING_WINDOW,
        model_name: str = "all-MiniLM-L6-v2",
        use_enhanced_model: bool = True
    ):
        """
        Initialize the large chunk embedder
        
        Args:
            strategy: Embedding strategy to use
            model_name: Name of the embedding model
            use_enhanced_model: Whether to upgrade to better model
        """
        self.strategy = strategy
        
        # Upgrade to better model if requested and available
        if use_enhanced_model and SENTENCE_TRANSFORMERS_AVAILABLE:
            self.model_name = self._select_best_available_model()
        else:
            self.model_name = model_name
            
        self.model = None
        self.config = self._create_config()
        self._initialize_model()
        
        logger.info(f"🧠 EMBEDDER: Initialized with {strategy.value} strategy using {self.model_name}")
    
    def _select_best_available_model(self) -> str:
        """
        Select the best available embedding model for large chunks
        """
        try:
            # Try to load better model for longer sequences
            preferred_models = [
                'multi-qa-mpnet-base-dot-v1',  # Best for Q&A with 512 tokens
                'all-mpnet-base-v2',           # Good quality with 384 tokens
                'all-MiniLM-L6-v2'             # Fallback with 256 tokens
            ]
            
            for model_name in preferred_models:
                try:
                    test_model = SentenceTransformer(model_name)
                    logger.info(f"🧠 EMBEDDER: Successfully loaded enhanced model {model_name}")
                    return model_name
                except Exception as e:
                    logger.warning(f"🧠 EMBEDDER: Could not load {model_name}: {e}")
                    continue
            
            # Fallback to current model
            return 'all-MiniLM-L6-v2'
            
        except Exception as e:
            logger.error(f"🧠 EMBEDDER: Error selecting model: {e}")
            return 'all-MiniLM-L6-v2'
    
    def _create_config(self) -> EmbeddingConfig:
        """Create configuration based on model and strategy"""
        model_info = self.EMBEDDING_MODELS.get(self.model_name, self.EMBEDDING_MODELS['all-MiniLM-L6-v2'])
        
        return EmbeddingConfig(
            strategy=self.strategy,
            model_name=self.model_name,
            max_sequence_length=model_info['max_length'],
            window_size=min(model_info['max_length'] - 20, 400),  # Leave buffer for special tokens
            window_overlap=50,
            use_gpu=TORCH_AVAILABLE and torch.cuda.is_available(),
            normalize_embeddings=True
        )
    
    def _initialize_model(self):
        """Initialize the embedding model"""
        try:
            if not SENTENCE_TRANSFORMERS_AVAILABLE:
                raise ImportError("SentenceTransformers not available")
            
            self.model = SentenceTransformer(self.model_name)
            
            # Configure device
            if self.config.use_gpu:
                self.model = self.model.cuda()
                logger.info(f"🧠 EMBEDDER: Using GPU acceleration")
            
            # Get actual model specifications
            actual_max_length = getattr(self.model, 'max_seq_length', self.config.max_sequence_length)
            self.config.max_sequence_length = actual_max_length
            
            logger.info(f"🧠 EMBEDDER: Model loaded - max_length: {actual_max_length}")
            
        except Exception as e:
            logger.error(f"🧠 EMBEDDER: Failed to initialize model: {e}")
            self.model = None
    
    def embed_large_text(self, text: str, metadata: Optional[Dict[str, Any]] = None) -> EmbeddingResult:
        """
        Embed large text using the configured strategy
        
        Args:
            text: Text to embed (can be very large)
            metadata: Optional metadata
            
        Returns:
            EmbeddingResult with the final embedding
        """
        if not self.model:
            raise RuntimeError("Embedding model not initialized")
        
        metadata = metadata or {}
        start_time = self._get_current_time_ms()
        
        try:
            if self.strategy == EmbeddingStrategy.TRUNCATION:
                result = self._embed_with_truncation(text, metadata)
            elif self.strategy == EmbeddingStrategy.SLIDING_WINDOW:
                result = self._embed_with_sliding_window(text, metadata)
            elif self.strategy == EmbeddingStrategy.HIERARCHICAL:
                result = self._embed_with_hierarchical(text, metadata)
            elif self.strategy == EmbeddingStrategy.MEAN_POOLING:
                result = self._embed_with_mean_pooling(text, metadata)
            elif self.strategy == EmbeddingStrategy.MAX_POOLING:
                result = self._embed_with_max_pooling(text, metadata)
            elif self.strategy == EmbeddingStrategy.WEIGHTED_AVERAGE:
                result = self._embed_with_weighted_average(text, metadata)
            else:
                # Fallback to sliding window
                result = self._embed_with_sliding_window(text, metadata)
            
            # Calculate processing time
            end_time = self._get_current_time_ms()
            result.processing_time_ms = end_time - start_time
            
            logger.info(f"🧠 EMBEDDER: Processed {len(text)} chars in {result.processing_time_ms:.1f}ms using {self.strategy.value}")
            return result
            
        except Exception as e:
            logger.error(f"🧠 EMBEDDER: Failed to embed text: {e}")
            raise
    
    def _embed_with_truncation(self, text: str, metadata: Dict[str, Any]) -> EmbeddingResult:
        """Original strategy: truncate to model limit"""
        embedding = self.model.encode(text, normalize_embeddings=self.config.normalize_embeddings)
        
        return EmbeddingResult(
            embedding=embedding,
            strategy_used=self.strategy.value,
            model_used=self.model_name,
            input_tokens=self._estimate_tokens(text),
            processing_time_ms=0,  # Will be set by caller
            chunks_processed=1,
            metadata=metadata
        )
    
    def _embed_with_sliding_window(self, text: str, metadata: Dict[str, Any]) -> EmbeddingResult:
        """
        Sliding window approach: embed overlapping windows and average
        Best for preserving information across long text
        """
        tokens = text.split()  # Simple tokenization
        window_size = self.config.window_size
        overlap = self.config.window_overlap
        
        if len(tokens) <= window_size:
            # Text fits in single window
            return self._embed_with_truncation(text, metadata)
        
        windows = []
        embeddings = []
        
        # Create overlapping windows
        start = 0
        while start < len(tokens):
            end = min(start + window_size, len(tokens))
            window_text = ' '.join(tokens[start:end])
            windows.append(window_text)
            
            # Embed this window
            window_embedding = self.model.encode(
                window_text, 
                normalize_embeddings=self.config.normalize_embeddings
            )
            embeddings.append(window_embedding)
            
            start += (window_size - overlap)
            if start >= len(tokens):
                break
        
        # Average all window embeddings
        final_embedding = np.mean(embeddings, axis=0)
        
        # Normalize final embedding if requested
        if self.config.normalize_embeddings:
            norm = np.linalg.norm(final_embedding)
            if norm > 0:
                final_embedding = final_embedding / norm
        
        return EmbeddingResult(
            embedding=final_embedding,
            strategy_used=self.strategy.value,
            model_used=self.model_name,
            input_tokens=len(tokens),
            processing_time_ms=0,
            chunks_processed=len(windows),
            metadata={**metadata, 'windows': len(windows)}
        )
    
    def _embed_with_hierarchical(self, text: str, metadata: Dict[str, Any]) -> EmbeddingResult:
        """
        Hierarchical approach: create summary + detail embeddings
        Good for documents with clear structure
        """
        # Create a summary (first and last parts + middle sample)
        words = text.split()
        if len(words) <= self.config.window_size:
            return self._embed_with_truncation(text, metadata)
        
        # Take first 30%, last 30%, and middle 40%
        first_part = ' '.join(words[:int(len(words) * 0.3)])
        last_part = ' '.join(words[int(len(words) * 0.7):])
        middle_sample = ' '.join(words[int(len(words) * 0.3):int(len(words) * 0.7)])
        
        # Create summary
        summary = f"{first_part} ... {middle_sample[:200]} ... {last_part}"
        
        # If summary is still too long, truncate
        summary_words = summary.split()
        if len(summary_words) > self.config.window_size:
            summary = ' '.join(summary_words[:self.config.window_size])
        
        # Embed summary
        embedding = self.model.encode(summary, normalize_embeddings=self.config.normalize_embeddings)
        
        return EmbeddingResult(
            embedding=embedding,
            strategy_used=self.strategy.value,
            model_used=self.model_name,
            input_tokens=len(words),
            processing_time_ms=0,
            chunks_processed=1,
            metadata={**metadata, 'summary_length': len(summary_words)}
        )
    
    def _embed_with_mean_pooling(self, text: str, metadata: Dict[str, Any]) -> EmbeddingResult:
        """Mean pooling of multiple chunks"""
        return self._embed_with_pooling(text, metadata, 'mean')
    
    def _embed_with_max_pooling(self, text: str, metadata: Dict[str, Any]) -> EmbeddingResult:
        """Max pooling of multiple chunks"""
        return self._embed_with_pooling(text, metadata, 'max')
    
    def _embed_with_pooling(self, text: str, metadata: Dict[str, Any], pooling_type: str) -> EmbeddingResult:
        """
        Generic pooling approach for chunk embeddings
        """
        words = text.split()
        chunk_size = self.config.window_size
        
        if len(words) <= chunk_size:
            return self._embed_with_truncation(text, metadata)
        
        # Split into non-overlapping chunks
        chunks = []
        for i in range(0, len(words), chunk_size):
            chunk = ' '.join(words[i:i + chunk_size])
            chunks.append(chunk)
        
        # Embed all chunks
        embeddings = []
        for chunk in chunks:
            embedding = self.model.encode(chunk, normalize_embeddings=False)  # Don't normalize yet
            embeddings.append(embedding)
        
        embeddings = np.array(embeddings)
        
        # Apply pooling
        if pooling_type == 'mean':
            final_embedding = np.mean(embeddings, axis=0)
        elif pooling_type == 'max':
            final_embedding = np.max(embeddings, axis=0)
        else:
            final_embedding = np.mean(embeddings, axis=0)  # Default to mean
        
        # Normalize final embedding
        if self.config.normalize_embeddings:
            norm = np.linalg.norm(final_embedding)
            if norm > 0:
                final_embedding = final_embedding / norm
        
        return EmbeddingResult(
            embedding=final_embedding,
            strategy_used=f"{self.strategy.value}_{pooling_type}",
            model_used=self.model_name,
            input_tokens=len(words),
            processing_time_ms=0,
            chunks_processed=len(chunks),
            metadata={**metadata, 'pooling_type': pooling_type}
        )
    
    def _embed_with_weighted_average(self, text: str, metadata: Dict[str, Any]) -> EmbeddingResult:
        """
        Weighted average based on chunk position and content importance
        """
        words = text.split()
        chunk_size = self.config.window_size
        
        if len(words) <= chunk_size:
            return self._embed_with_truncation(text, metadata)
        
        # Split into chunks
        chunks = []
        weights = []
        
        for i in range(0, len(words), chunk_size):
            chunk = ' '.join(words[i:i + chunk_size])
            chunks.append(chunk)
            
            # Calculate weight based on position (beginning and end are more important)
            position = i / len(words)
            if position < 0.2 or position > 0.8:  # First 20% and last 20%
                weight = 1.5
            else:
                weight = 1.0
            weights.append(weight)
        
        # Normalize weights
        total_weight = sum(weights)
        weights = [w / total_weight for w in weights]
        
        # Embed all chunks
        embeddings = []
        for chunk in chunks:
            embedding = self.model.encode(chunk, normalize_embeddings=False)
            embeddings.append(embedding)
        
        # Weighted average
        weighted_embeddings = [emb * weight for emb, weight in zip(embeddings, weights)]
        final_embedding = np.sum(weighted_embeddings, axis=0)
        
        # Normalize
        if self.config.normalize_embeddings:
            norm = np.linalg.norm(final_embedding)
            if norm > 0:
                final_embedding = final_embedding / norm
        
        return EmbeddingResult(
            embedding=final_embedding,
            strategy_used=self.strategy.value,
            model_used=self.model_name,
            input_tokens=len(words),
            processing_time_ms=0,
            chunks_processed=len(chunks),
            metadata={**metadata, 'weights': weights}
        )
    
    def _estimate_tokens(self, text: str) -> int:
        """Estimate number of tokens in text"""
        return len(text.split()) * 1.33  # Approximate conversion
    
    def _get_current_time_ms(self) -> float:
        """Get current time in milliseconds"""
        import time
        return time.time() * 1000
    
    @classmethod
    def get_recommended_strategy(cls, text_length: int, use_case: str = "general") -> EmbeddingStrategy:
        """
        Recommend optimal embedding strategy based on text characteristics
        
        Args:
            text_length: Length of text in characters
            use_case: Type of use case ('qa', 'search', 'classification', 'general')
            
        Returns:
            Recommended EmbeddingStrategy
        """
        estimated_tokens = len(text_length.split()) * 1.33 if isinstance(text_length, str) else text_length / 4
        
        if estimated_tokens <= 256:
            return EmbeddingStrategy.TRUNCATION
        elif estimated_tokens <= 1000:
            return EmbeddingStrategy.SLIDING_WINDOW
        elif use_case == "qa":
            return EmbeddingStrategy.HIERARCHICAL
        elif estimated_tokens <= 4000:
            return EmbeddingStrategy.MEAN_POOLING
        else:
            return EmbeddingStrategy.WEIGHTED_AVERAGE
    
    def get_model_info(self) -> Dict[str, Any]:
        """Get information about the current model"""
        if not self.model:
            return {'error': 'Model not initialized'}
        
        model_info = self.EMBEDDING_MODELS.get(self.model_name, {})
        
        return {
            'model_name': self.model_name,
            'strategy': self.strategy.value,
            'max_sequence_length': self.config.max_sequence_length,
            'embedding_dimension': model_info.get('dimension', 'unknown'),
            'using_gpu': self.config.use_gpu,
            'model_description': model_info.get('description', 'No description available'),
            'good_for': model_info.get('good_for', [])
        }