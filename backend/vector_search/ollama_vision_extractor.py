"""
Ollama Vision-Based Document Extractor

Converts PDF pages to images and sends each page to an Ollama vision model
for text extraction. Produces higher quality extraction than PyPDF2 for
documents with complex layouts, tables, and figures.
"""
import base64
import io
import json
import logging
import os
import urllib.request
from typing import Optional

logger = logging.getLogger(__name__)

OLLAMA_URL = os.getenv('OLLAMA_URL', 'http://127.0.0.1:11434')

PAGE_EXTRACTION_PROMPT = (
    "Extract ALL text from this document page exactly as it appears. "
    "Include headings, paragraphs, bullet points, table contents, "
    "figure captions, and footnotes. "
    "Preserve the reading order. Output plain text only, no markdown formatting."
)


class OllamaVisionExtractor:
    """Extract text from documents using Ollama vision models."""

    def __init__(self, model: str = 'gemma4:e4b', ollama_url: str = None):
        self.model = model
        self.ollama_url = ollama_url or OLLAMA_URL

    def extract_document_text(self, file_path: str, file_extension: str) -> str:
        """Main entry point: extract text from any supported document type."""
        ext = (file_extension or '').lower().strip('.')

        if ext == 'pdf':
            return self._extract_pdf_via_vision(file_path)
        elif ext in ('txt', 'md', 'rtf'):
            return self._read_text_file(file_path)
        elif ext in ('doc', 'docx'):
            return self._extract_docx(file_path)
        else:
            logger.warning(f"Unsupported file type for vision extraction: {ext}")
            return ''

    def _extract_pdf_via_vision(self, file_path: str) -> str:
        """Convert PDF to page images, send each to Ollama vision model."""
        images = self._pdf_to_images(file_path)
        if not images:
            logger.error(f"Failed to convert PDF to images: {file_path}")
            return ''

        logger.info(f"📸 Ollama vision: extracting {len(images)} pages from {os.path.basename(file_path)}")

        all_text = []
        for i, img_bytes in enumerate(images):
            page_num = i + 1
            try:
                img_b64 = base64.b64encode(img_bytes).decode('utf-8')
                text = self._call_ollama_vision(img_b64, page_num, len(images))
                if text:
                    all_text.append(f"--- Page {page_num} ---\n{text}")
                    logger.info(f"  Page {page_num}/{len(images)}: {len(text)} chars extracted")
                else:
                    logger.warning(f"  Page {page_num}/{len(images)}: no text extracted")
            except Exception as e:
                logger.error(f"  Page {page_num}/{len(images)}: vision extraction failed: {e}")
                # Try PyPDF2 fallback for this page
                fallback = self._fallback_page_extraction(file_path, i)
                if fallback:
                    all_text.append(f"--- Page {page_num} ---\n{fallback}")

        full_text = '\n\n'.join(all_text)
        logger.info(f"✅ Ollama vision: extracted {len(full_text)} chars total from {os.path.basename(file_path)}")
        return full_text

    def _call_ollama_vision(self, image_b64: str, page_num: int, total_pages: int) -> str:
        """Send a single page image to Ollama and get extracted text."""
        body = {
            'model': self.model,
            'messages': [{
                'role': 'user',
                'content': PAGE_EXTRACTION_PROMPT,
                'images': [image_b64],
            }],
            'stream': False,
            'options': {
                'num_predict': 4096,
                'temperature': 0.1,  # Low temperature for faithful extraction
            },
        }

        req = urllib.request.Request(
            f'{self.ollama_url}/api/chat',
            data=json.dumps(body).encode('utf-8'),
            headers={'Content-Type': 'application/json'},
        )

        try:
            resp = urllib.request.urlopen(req, timeout=120)  # 2 min per page
            data = json.loads(resp.read().decode('utf-8'))
            return data.get('message', {}).get('content', '').strip()
        except Exception as e:
            logger.error(f"Ollama vision API call failed for page {page_num}: {e}")
            return ''

    def _pdf_to_images(self, file_path: str) -> list:
        """Convert PDF pages to PNG image bytes. Tries PyMuPDF first, then pdf2image."""
        images = []

        # Try PyMuPDF (fitz) first — faster, no poppler dependency
        try:
            import fitz
            doc = fitz.open(file_path)
            for page in doc:
                # Render at 150 DPI (good balance of quality vs speed)
                mat = fitz.Matrix(150 / 72, 150 / 72)
                pix = page.get_pixmap(matrix=mat)
                images.append(pix.tobytes('png'))
            doc.close()
            logger.info(f"  PyMuPDF: converted {len(images)} pages to images")
            return images
        except ImportError:
            logger.debug("PyMuPDF not available, trying pdf2image")
        except Exception as e:
            logger.warning(f"PyMuPDF failed: {e}, trying pdf2image")

        # Fallback: pdf2image (requires poppler)
        try:
            from pdf2image import convert_from_path
            pil_images = convert_from_path(file_path, dpi=150)
            for img in pil_images:
                buf = io.BytesIO()
                img.save(buf, format='PNG')
                images.append(buf.getvalue())
            logger.info(f"  pdf2image: converted {len(images)} pages to images")
            return images
        except ImportError:
            logger.error("Neither PyMuPDF nor pdf2image available for PDF→image conversion")
        except Exception as e:
            logger.error(f"pdf2image failed: {e}")

        return images

    def _fallback_page_extraction(self, file_path: str, page_index: int) -> str:
        """Fallback: extract text from a single PDF page using PyPDF2."""
        try:
            from PyPDF2 import PdfReader
            reader = PdfReader(file_path)
            if page_index < len(reader.pages):
                return reader.pages[page_index].extract_text() or ''
        except Exception:
            pass
        return ''

    def _read_text_file(self, file_path: str) -> str:
        """Read a plain text file."""
        try:
            for encoding in ['utf-8', 'latin-1', 'cp1252']:
                try:
                    with open(file_path, 'r', encoding=encoding) as f:
                        return f.read()
                except UnicodeDecodeError:
                    continue
        except Exception as e:
            logger.error(f"Failed to read text file {file_path}: {e}")
        return ''

    def _extract_docx(self, file_path: str) -> str:
        """Extract text from DOCX using python-docx (text extraction is reliable for DOCX)."""
        try:
            import docx
            doc = docx.Document(file_path)
            paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
            return '\n\n'.join(paragraphs)
        except Exception as e:
            logger.error(f"Failed to extract DOCX {file_path}: {e}")
            return ''
