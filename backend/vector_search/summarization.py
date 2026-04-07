# AI Summarization Service
# backend/vector_search/summarization.py

import os
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

# Try to import OpenAI
try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    logger.warning("OpenAI package not installed. Summarization will use fallback methods.")
    OpenAI = None

class OpenAISummarizer:
    """OpenAI-powered summarization and topic generation service"""
    
    def __init__(self):
        # Get OpenAI API key from environment
        self.api_key = os.getenv('OPENAI_API_KEY')
        logger.info(f"Initializing OpenAI summarizer...")
        
        if not self.api_key:
            logger.warning("OpenAI API key not found. Set OPENAI_API_KEY environment variable. Summarizer will use fallback methods.")
            self.available = False
            self.client = None
            return
            
        if not OPENAI_AVAILABLE:
            logger.warning("OpenAI package is not installed. Summarizer will use fallback methods.")
            self.available = False
            self.client = None
            return

        try:
            self.client = OpenAI(api_key=self.api_key)
            self.available = True
            logger.info("✅ OpenAI summarizer initialized successfully")
        except Exception as e:
            logger.warning(f"⚠️ Failed to initialize OpenAI client: {e}. Summarizer will use fallback methods.")
            self.available = False
            self.client = None
    
    def is_available(self) -> bool:
        """Check if OpenAI API is available"""
        return self.available
    
    def generate_summary(self, content: str, metadata: Dict[str, Any] = None) -> Optional[str]:
        """Generate a summary of the content using OpenAI GPT or fallback method"""
        if not content.strip():
            return None
            
        # If OpenAI is not available, use fallback summary generation
        if not self.available:
            return self._generate_fallback_summary(content, metadata)
        
        logger.info(f"Generating OpenAI summary for content of length {len(content)}")
        
        try:
            # Prepare context information
            context = ""
            if metadata:
                context_parts = []
                if metadata.get('file_name'):
                    context_parts.append(f"Document: {metadata['file_name']}")
                if metadata.get('category'):
                    context_parts.append(f"Category: {metadata['category']}")
                if metadata.get('section_title'):
                    context_parts.append(f"Section: {metadata['section_title']}")
                
                if context_parts:
                    context = " | ".join(context_parts) + "\n\n"
            
            # Create summarization prompt
            prompt = f"""{context}Please provide a concise summary of the following content in 2-3 sentences. Focus on the main points and key information:

{content[:3000]}"""  # Limit content to avoid token limits
            
            # Call OpenAI API with timeout
            import concurrent.futures
            
            def call_openai():
                return self.client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[
                        {"role": "system", "content": "You are a helpful assistant that creates concise, informative summaries."},
                        {"role": "user", "content": prompt}
                    ],
                    max_tokens=150,
                    temperature=0.3
                )
            
            # Use thread-based timeout since signal doesn't work in Django
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(call_openai)
                try:
                    response = future.result(timeout=30)  # 30 second timeout
                except concurrent.futures.TimeoutError:
                    logger.warning("OpenAI API call timed out after 30 seconds, using fallback")
                    return self._generate_fallback_summary(content, metadata)
            
            summary = response.choices[0].message.content.strip()
            logger.info("Summary generated successfully")
            return summary
            
        except Exception as e:
            logger.warning(f"Error generating OpenAI summary: {e}, using fallback")
            return self._generate_fallback_summary(content, metadata)
    
    def generate_topic(self, content: str, metadata: Dict[str, Any] = None) -> Optional[str]:
        """Generate a topic/title for the content using OpenAI GPT or fallback method"""
        if not content.strip():
            return None
            
        # If OpenAI is not available, use fallback topic generation
        if not self.available:
            return self._generate_fallback_topic(content, metadata)
        
        logger.info(f"Generating OpenAI topic for content of length {len(content)}")
        
        try:
            # Prepare context information
            context = ""
            if metadata:
                if metadata.get('category'):
                    context += f"Category: {metadata['category']} | "
                if metadata.get('document_type'):
                    context += f"Type: {metadata['document_type']} | "
            
            # Create topic generation prompt
            prompt = f"""{context}Please generate a clear, descriptive topic/title for the following content. The topic should be 3-8 words and capture the main subject:

{content[:2000]}"""  # Limit content to avoid token limits
            
            # Call OpenAI API with timeout
            import concurrent.futures
            
            def call_openai():
                return self.client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[
                        {"role": "system", "content": "You are a helpful assistant that creates clear, descriptive topics and titles."},
                        {"role": "user", "content": prompt}
                    ],
                    max_tokens=50,
                    temperature=0.3
                )
            
            # Use thread-based timeout since signal doesn't work in Django
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(call_openai)
                try:
                    response = future.result(timeout=30)  # 30 second timeout
                except concurrent.futures.TimeoutError:
                    logger.warning("OpenAI API call timed out after 30 seconds, using fallback")
                    return self._generate_fallback_topic(content, metadata)
            
            topic = response.choices[0].message.content.strip()
            # Remove quotes if present
            topic = topic.strip('"\'')
            logger.info(f"Topic generated successfully: '{topic}'")
            return topic
            
        except Exception as e:
            logger.warning(f"Error generating OpenAI topic: {e}, using fallback")
            return self._generate_fallback_topic(content, metadata)
    
    def _generate_fallback_summary(self, content: str, metadata: Dict[str, Any] = None) -> str:
        """Generate a simple summary using text processing when OpenAI is not available"""
        logger.info("Using fallback method for summary generation")
        
        # Clean content
        cleaned_content = content.strip()
        
        # Get first paragraph or sentences
        paragraphs = [p.strip() for p in cleaned_content.split('\n\n') if p.strip()]
        if not paragraphs:
            sentences = [s.strip() for s in cleaned_content.split('.') if s.strip()]
            if sentences:
                # Take first 2-3 sentences, limit to 200 chars
                summary = '. '.join(sentences[:3])[:200]
                if not summary.endswith('.'):
                    summary += '.'
                return summary
        else:
            # Take first paragraph, limit to 200 chars
            summary = paragraphs[0][:200]
            if not summary.endswith('.'):
                summary += '.'
                
        # Add context if available
        context_parts = []
        if metadata:
            if metadata.get('file_name'):
                context_parts.append(f"from {metadata['file_name']}")
            if metadata.get('section_title') and metadata['section_title'] != 'Complete Document':
                context_parts.append(f"section '{metadata['section_title']}'")
        
        if context_parts:
            return f"Content {' '.join(context_parts)}: {summary}"
        
        return summary or "Document content extracted successfully."
    
    def _generate_fallback_topic(self, content: str, metadata: Dict[str, Any] = None) -> str:
        """Generate a simple topic using metadata and content analysis when OpenAI is not available"""
        logger.info("Using fallback method for topic generation")
        
        # Try to use section title first
        if metadata and metadata.get('section_title') and metadata['section_title'] != 'Complete Document':
            return metadata['section_title']
            
        # Try to use filename
        if metadata and metadata.get('file_name'):
            filename = metadata['file_name']
            # Remove extension and clean up
            base_name = filename.split('.')[0]
            # Convert underscores/hyphens to spaces and title case
            topic = base_name.replace('_', ' ').replace('-', ' ').title()
            if len(topic.split()) <= 8:
                return topic
        
        # Use category as fallback
        if metadata and metadata.get('category') and metadata['category'] != 'general':
            return f"{metadata['category'].title()} Document"
            
        # Extract potential topic from first line
        lines = [line.strip() for line in content.split('\n') if line.strip()]
        if lines:
            first_line = lines[0]
            # If first line is short and looks like a title
            if len(first_line) < 80 and len(first_line.split()) <= 12:
                return first_line.title()
        
        return "Document Content"

# Singleton instance of the summarizer
_summarizer_instance = None

def get_summarizer():
    """Get the singleton summarizer instance, creating it if necessary."""
    global _summarizer_instance
    if _summarizer_instance is None:
        logger.info("Creating new OpenAISummarizer instance.")
        _summarizer_instance = OpenAISummarizer()
    return _summarizer_instance

