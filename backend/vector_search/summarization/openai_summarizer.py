# OpenAI GPT Summarization and Topic Generation Service
# backend/vector_search/summarization/openai_summarizer.py

import os
import openai
import logging
from typing import Optional, Dict, Any
from django.conf import settings

logger = logging.getLogger(__name__)

class OpenAISummarizer:
    """Service for generating content summaries and topics using OpenAI GPT"""
    
    def __init__(self):
        # Initialize OpenAI client
        api_key = os.getenv('OPENAI_API_KEY') or getattr(settings, 'OPENAI_API_KEY', '')
        
        if not api_key:
            logger.warning("OpenAI API key not found. Summary and topic generation will be disabled.")
            self.client = None
        else:
            try:
                # Use the new OpenAI client syntax
                from openai import OpenAI
                self.client = OpenAI(api_key=api_key)
                logger.info("OpenAI summarizer initialized successfully")
            except ImportError:
                # Fallback to older syntax if needed
                openai.api_key = api_key
                self.client = openai
                logger.info("OpenAI summarizer initialized with legacy client")
        
        # Configuration
        self.model = getattr(settings, 'OPENAI_MODEL', 'gpt-3.5-turbo')
        self.max_tokens = getattr(settings, 'OPENAI_MAX_TOKENS', 150)
        self.temperature = getattr(settings, 'OPENAI_TEMPERATURE', 0.3)
        self.max_input_length = 3000  # Limit input to avoid token limits
    
    def generate_summary(self, content: str, document_metadata: Dict[str, Any] = None) -> Optional[str]:
        """Generate a concise summary of document content"""
        if not self.client or not content.strip():
            return None
        
        try:
            # Truncate content if too long
            if len(content) > self.max_input_length:
                content = content[:self.max_input_length] + "..."
                logger.info(f"Content truncated to {self.max_input_length} characters for summarization")
            
            # Build context-aware prompt
            prompt = self._build_summarization_prompt(content, document_metadata)
            
            # Call OpenAI API
            if hasattr(self.client, 'chat') and hasattr(self.client.chat, 'completions'):
                # New client syntax
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {
                            "role": "system",
                            "content": "You are a professional document summarizer. Create concise, informative summaries."
                        },
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ],
                    max_tokens=self.max_tokens,
                    temperature=self.temperature,
                    top_p=1,
                    frequency_penalty=0,
                    presence_penalty=0
                )
                summary = response.choices[0].message.content.strip()
            else:
                # Legacy client syntax
                response = self.client.ChatCompletion.create(
                    model=self.model,
                    messages=[
                        {
                            "role": "system",
                            "content": "You are a professional document summarizer. Create concise, informative summaries."
                        },
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ],
                    max_tokens=self.max_tokens,
                    temperature=self.temperature,
                    top_p=1,
                    frequency_penalty=0,
                    presence_penalty=0
                )
                summary = response.choices[0].message.content.strip()
            
            # Extract and validate summary
            if summary:
                # Validate summary constraints
                if self._validate_summary(summary):
                    logger.info("Summary generated successfully")
                    return summary
                else:
                    logger.warning("Generated summary didn't meet constraints, using truncated version")
                    return self._enforce_summary_constraints(summary)
            
            logger.warning("No valid response from OpenAI API")
            return None
            
        except Exception as e:
            logger.error(f"Failed to generate summary using OpenAI: {e}")
            return None
    
    def generate_topic(self, content: str, document_metadata: Dict[str, Any] = None) -> Optional[str]:
        """Generate a concise topic name for document content"""
        if not self.client or not content.strip():
            return None
        
        try:
            # Truncate content if too long
            if len(content) > self.max_input_length:
                content = content[:self.max_input_length] + "..."
                logger.info(f"Content truncated to {self.max_input_length} characters for topic generation")
            
            # Build topic generation prompt
            prompt = self._build_topic_prompt(content, document_metadata)
            
            # Call OpenAI API with different parameters for topic generation
            if hasattr(self.client, 'chat') and hasattr(self.client.chat, 'completions'):
                # New client syntax
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {
                            "role": "system",
                            "content": "You are an expert at creating concise, descriptive topic names. Generate clear, specific topic titles."
                        },
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ],
                    max_tokens=30,  # Much smaller for topic generation
                    temperature=0.2,  # Lower temperature for more focused topics
                    top_p=1,
                    frequency_penalty=0,
                    presence_penalty=0
                )
                topic = response.choices[0].message.content.strip()
            else:
                # Legacy client syntax
                response = self.client.ChatCompletion.create(
                    model=self.model,
                    messages=[
                        {
                            "role": "system",
                            "content": "You are an expert at creating concise, descriptive topic names. Generate clear, specific topic titles."
                        },
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ],
                    max_tokens=30,  # Much smaller for topic generation
                    temperature=0.2,  # Lower temperature for more focused topics
                    top_p=1,
                    frequency_penalty=0,
                    presence_penalty=0
                )
                topic = response.choices[0].message.content.strip()
            
            # Extract and clean topic
            if topic:
                # Clean and validate topic
                topic = self._clean_and_validate_topic(topic)
                
                if topic:
                    logger.info(f"Topic generated successfully: '{topic}'")
                    return topic
                else:
                    logger.warning("Generated topic didn't meet constraints")
                    return self._generate_fallback_topic(content, document_metadata)
            
            logger.warning("No valid response from OpenAI API for topic generation")
            return None
            
        except Exception as e:
            logger.error(f"Failed to generate topic using OpenAI: {e}")
            return None
    
    def _build_summarization_prompt(self, content: str, metadata: Dict[str, Any] = None) -> str:
        """Build a context-aware prompt for summarization"""
        
        # Base prompt
        prompt = "Please create a concise summary of the following document content.\n\nREQUIREMENTS:\n- Maximum 5 lines\n- Maximum 200 words total\n- Focus on key points and main ideas\n- Use clear, professional language\n\n"
        
        # Add context if metadata available
        if metadata:
            document_type = metadata.get('document_type', 'document')
            category = metadata.get('category', 'general')
            file_name = metadata.get('file_name', 'unknown')
            
            prompt += f"DOCUMENT CONTEXT:\n- File: {file_name}\n- Type: {document_type}\n- Category: {category}\n\n"
        
        prompt += f"CONTENT TO SUMMARIZE:\n{content}\n\nSUMMARY:"
        
        return prompt
    
    def _build_topic_prompt(self, content: str, metadata: Dict[str, Any] = None) -> str:
        """Build a context-aware prompt for topic generation"""
        
        # Base prompt
        prompt = "Please create a concise topic name for the following document content.\n\nREQUIREMENTS:\n- Maximum 8 words\n- Clear and descriptive\n- Use title case (capitalize major words)\n- Focus on the main subject/theme\n- No quotation marks or special formatting\n\n"
        
        # Add context if metadata available
        if metadata:
            document_type = metadata.get('document_type', 'document')
            category = metadata.get('category', 'general')
            file_name = metadata.get('file_name', 'unknown')
            section_title = metadata.get('section_title', '')
            
            prompt += f"DOCUMENT CONTEXT:\n- File: {file_name}\n- Type: {document_type}\n- Category: {category}"
            
            if section_title:
                prompt += f"\n- Section: {section_title}"
            
            prompt += "\n\n"
        
        prompt += f"CONTENT TO ANALYZE:\n{content}\n\nTOPIC (max 8 words):"
        
        return prompt
    
    def _clean_and_validate_topic(self, topic: str) -> Optional[str]:
        """Clean and validate the generated topic"""
        if not topic:
            return None
        
        # Remove quotes and extra formatting
        topic = topic.strip('"\'')
        topic = topic.strip()
        
        # Remove common prefixes that might be added
        prefixes_to_remove = [
            'Topic:', 'Title:', 'Subject:', 'Theme:', 'Content:', 
            'Document:', 'Section:', 'Chapter:', 'Unit:'
        ]
        
        for prefix in prefixes_to_remove:
            if topic.startswith(prefix):
                topic = topic[len(prefix):].strip()
        
        # Check word count (max 8 words)
        words = topic.split()
        if len(words) > 8:
            topic = ' '.join(words[:8])
        
        # Ensure it's not empty after cleaning
        if not topic.strip():
            return None
        
        # Convert to title case
        topic = topic.title()
        
        # Validate minimum length (at least 1 word for meaningful topics)
        if len(words) < 1:
            return None
        
        return topic
    
    def _generate_fallback_topic(self, content: str, metadata: Dict[str, Any] = None) -> str:
        """Generate a fallback topic when OpenAI fails"""
        # Extract key terms from content
        words = content.split()[:20]  # First 20 words
        
        # Filter out common words
        stop_words = {'the', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'is', 'are', 'was', 'were', 'be', 'been', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could', 'should', 'may', 'might', 'can', 'this', 'that', 'these', 'those', 'a', 'an'}
        
        # Safe punctuation removal
        content_words = []
        for word in words:
            # Simple punctuation removal - safe approach
            clean_word = ''
            for char in word:
                if char.isalnum():
                    clean_word += char
            
            if clean_word and clean_word.lower() not in stop_words and len(clean_word) > 2:
                content_words.append(clean_word.title())
        
        # Use section title if available
        if metadata and metadata.get('section_title'):
            section_title = metadata['section_title']
            if len(section_title.split()) <= 8:
                return section_title.title()
        
        # Use document type and category
        if metadata:
            doc_type = metadata.get('document_type', 'Document').title()
            category = metadata.get('category', 'General').title()
            chunk_type = metadata.get('chunk_type', 'Content').title()
            
            if content_words:
                # Combine category with first few content words
                topic_words = [category, doc_type] + content_words[:4]
                return ' '.join(topic_words[:8])
            else:
                return f"{category} {doc_type} {chunk_type}"
        
        # Final fallback
        if content_words:
            return ' '.join(content_words[:8])
        else:
            return "Document Content Analysis"
    
    def _validate_summary(self, summary: str) -> bool:
        """Validate that summary meets the requirements"""
        if not summary:
            return False
        
        # Check line count (max 5 lines)
        lines = [line.strip() for line in summary.split('\n') if line.strip()]
        if len(lines) > 5:
            return False
        
        # Check word count (max 200 words)
        word_count = len(summary.split())
        if word_count > 200:
            return False
        
        return True
    
    def _enforce_summary_constraints(self, summary: str) -> str:
        """Enforce summary constraints if validation fails"""
        lines = [line.strip() for line in summary.split('\n') if line.strip()]
        
        # Limit to 5 lines
        if len(lines) > 5:
            lines = lines[:5]
        
        # Join lines and check word count
        constrained_summary = '\n'.join(lines)
        words = constrained_summary.split()
        
        # Limit to 200 words
        if len(words) > 200:
            words = words[:200]
            # Try to end at a complete sentence
            constrained_summary = ' '.join(words)
            
            # Find last period to end at complete sentence
            last_period = constrained_summary.rfind('.')
            if last_period > len(constrained_summary) * 0.8:  # If period is in last 20%
                constrained_summary = constrained_summary[:last_period + 1]
        
        return constrained_summary
    
    def is_available(self) -> bool:
        """Check if the summarizer is available and configured"""
        return self.client is not None


# Fallback summarizer for when OpenAI is not available
class SimpleSummarizer:
    """Simple extractive summarizer and topic generator as fallback"""
    
    def generate_summary(self, content: str, document_metadata: Dict[str, Any] = None) -> str:
        """Generate a simple extractive summary"""
        if not content.strip():
            return "No content available for summary."
        
        # Simple extractive approach: take first few sentences
        sentences = content.replace('\n', ' ').split('. ')
        
        # Clean and filter sentences
        clean_sentences = []
        word_count = 0
        
        for sentence in sentences[:10]:  # Max 10 sentences to consider
            sentence = sentence.strip()
            if len(sentence) > 20:  # Filter out very short sentences
                sentence_words = len(sentence.split())
                if word_count + sentence_words <= 180:  # Leave room for summary formatting
                    clean_sentences.append(sentence)
                    word_count += sentence_words
                else:
                    break
        
        # Format as summary
        if not clean_sentences:
            return f"Document content analysis: {len(content)} characters of text content."
        
        summary = '. '.join(clean_sentences[:4])  # Max 4 sentences
        if not summary.endswith('.'):
            summary += '.'
        
        # Add a summary line
        file_name = document_metadata.get('file_name', 'document') if document_metadata else 'document'
        summary += f"\n\nDocument: {file_name} ({len(content):,} characters)"
        
        return summary
    
    def generate_topic(self, content: str, document_metadata: Dict[str, Any] = None) -> str:
        """Generate a simple topic from content"""
        if not content.strip():
            return "Document Content"
        
        # Extract key words from beginning of content
        words = content.split()[:15]  # First 15 words
        
        # Filter out common words and punctuation
        stop_words = {'the', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'is', 'are', 'was', 'were', 'this', 'that', 'a', 'an'}
        
        content_words = []
        for word in words:
            # Safe punctuation removal
            clean_word = ''
            for char in word:
                if char.isalnum():
                    clean_word += char
            
            if clean_word and clean_word.lower() not in stop_words and len(clean_word) > 2:
                content_words.append(clean_word.title())
        
        # Use section title if available
        if document_metadata and document_metadata.get('section_title'):
            section_title = document_metadata['section_title']
            title_words = section_title.split()
            if len(title_words) <= 8:
                return section_title.title()
            else:
                return ' '.join(title_words[:8]).title()
        
        # Use metadata to build topic
        if document_metadata:
            category = document_metadata.get('category', 'General').title()
            doc_type = document_metadata.get('document_type', 'Document').title()
            
            if content_words:
                # Combine metadata with content words
                topic_parts = [category]
                remaining_words = 8 - len(topic_parts)
                topic_parts.extend(content_words[:remaining_words])
                return ' '.join(topic_parts)
            else:
                return f"{category} {doc_type} Content"
        
        # Fallback to content words only
        if content_words:
            return ' '.join(content_words[:8])
        else:
            return "Document Content Analysis"
    
    def is_available(self) -> bool:
        """Simple summarizer is always available"""
        return True


# Factory function to get the appropriate summarizer
def get_summarizer():
    """Get the best available summarizer"""
    try:
        openai_summarizer = OpenAISummarizer()
        
        if openai_summarizer.is_available():
            logger.info("✅ Using OpenAI summarizer for AI-generated content")
            return openai_summarizer
        else:
            logger.warning("⚠️ OpenAI summarizer not available, falling back to simple summarizer")
            return SimpleSummarizer()
    except Exception as e:
        logger.error(f"❌ Error initializing OpenAI summarizer: {e}")
        logger.warning("🔄 Falling back to simple summarizer")
        return SimpleSummarizer()
