"""
Security validation for Public Chatbot document uploads
Enhanced security checks for file uploads and content validation
"""
import os
import re
import hashlib
import logging
from typing import List, Dict, Any, Tuple
from pathlib import Path
import tempfile
# Optional python-magic for enhanced MIME type detection
try:
    import magic
    MAGIC_AVAILABLE = True
except ImportError:
    MAGIC_AVAILABLE = False

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import UploadedFile
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger('public_chatbot.security')


class DocumentSecurityValidator:
    """
    Comprehensive security validation for uploaded documents
    """
    
    # Dangerous file extensions (never allow)
    DANGEROUS_EXTENSIONS = {
        '.exe', '.bat', '.cmd', '.com', '.pif', '.scr', '.vbs', '.js', '.jar',
        '.app', '.deb', '.pkg', '.dmg', '.iso', '.bin', '.run', '.msi',
        '.ps1', '.sh', '.bash', '.zsh', '.fish', '.php', '.asp', '.jsp'
    }
    
    # Suspicious patterns in filenames
    SUSPICIOUS_PATTERNS = [
        r'\.\./',           # Directory traversal
        r'\\\\',            # Windows UNC paths
        r'[<>:"|?*]',       # Invalid filename characters
        r'^\.',             # Hidden files (starting with dot)
        r'\.php\.',         # Double extensions (PHP bypass)
        r'\.asp\.',         # Double extensions (ASP bypass)
        r'null|con|prn|aux|nul|com[1-9]|lpt[1-9]',  # Windows reserved names
    ]
    
    # Maximum file sizes by type (bytes)
    FILE_SIZE_LIMITS = {
        '.txt': 10 * 1024 * 1024,    # 10MB
        '.pdf': 50 * 1024 * 1024,    # 50MB
        '.docx': 25 * 1024 * 1024,   # 25MB
        '.html': 5 * 1024 * 1024,    # 5MB
        '.csv': 20 * 1024 * 1024,    # 20MB
        '.json': 10 * 1024 * 1024,   # 10MB
        '.md': 5 * 1024 * 1024,      # 5MB
        '.xlsx': 30 * 1024 * 1024,   # 30MB
    }
    
    # Content validation patterns (dangerous content)
    DANGEROUS_CONTENT_PATTERNS = [
        r'<script[^>]*>.*?</script>',                    # JavaScript
        r'javascript:',                                  # JavaScript protocol
        r'data:.*base64',                               # Base64 data URLs
        r'vbscript:',                                   # VBScript
        r'on\w+\s*=',                                   # Event handlers
        r'eval\s*\(',                                   # Eval functions
        r'exec\s*\(',                                   # Exec functions
        r'system\s*\(',                                 # System calls
        r'shell_exec\s*\(',                             # Shell execution
        r'<?php',                                       # PHP code
        r'<%.*%>',                                      # ASP/JSP code
        r'\$\{.*\}',                                    # Template injection
        r'{{.*}}',                                      # Template injection
        r'<%=.*%>',                                     # Server-side includes
    ]
    
    # Suspicious text patterns
    SUSPICIOUS_TEXT_PATTERNS = [
        r'password\s*[:=]\s*\w+',                       # Password exposure
        r'api[_-]?key\s*[:=]\s*[\w\-]{20,}',           # API key exposure
        r'secret\s*[:=]\s*\w+',                         # Secret exposure
        r'token\s*[:=]\s*[\w\-]{20,}',                 # Token exposure
        r'private[_-]?key\s*[:=]',                      # Private key exposure
        r'-----BEGIN \w+ PRIVATE KEY-----',             # PEM private keys
        r'mysql://|postgresql://|mongodb://',           # Database URLs
        r'smtp://|ftp://|sftp://',                      # Server URLs
    ]
    
    def __init__(self):
        self.validation_errors = []
        self.security_warnings = []
    
    def validate_upload_batch(self, files: List[UploadedFile]) -> Dict[str, Any]:
        """
        Validate a batch of uploaded files
        
        Args:
            files: List of uploaded files
            
        Returns:
            Dict with validation results
        """
        logger.info(f"🔒 SECURITY: Validating batch of {len(files)} files")
        
        # Reset state
        self.validation_errors = []
        self.security_warnings = []
        
        # Validate batch constraints
        self._validate_batch_constraints(files)
        
        # Validate individual files
        file_results = {}
        for file_obj in files:
            file_results[file_obj.name] = self._validate_single_file(file_obj)
        
        # Calculate overall result
        total_errors = len(self.validation_errors)
        total_warnings = len(self.security_warnings)
        valid_files = sum(1 for result in file_results.values() if result['valid'])
        
        logger.info(f"🔒 SECURITY: Validation complete - {valid_files}/{len(files)} valid, {total_errors} errors, {total_warnings} warnings")
        
        return {
            'valid': total_errors == 0,
            'files_validated': len(files),
            'files_valid': valid_files,
            'files_invalid': len(files) - valid_files,
            'total_errors': total_errors,
            'total_warnings': total_warnings,
            'batch_errors': self.validation_errors,
            'security_warnings': self.security_warnings,
            'file_results': file_results
        }
    
    def _validate_batch_constraints(self, files: List[UploadedFile]):
        """Validate batch-level constraints"""
        # Check file count limit
        if len(files) > 50:
            self.validation_errors.append({
                'type': 'batch_limit',
                'message': f'Too many files: {len(files)} (maximum: 50)'
            })
        
        # Check total size
        total_size = sum(f.size for f in files if hasattr(f, 'size'))
        max_batch_size = 200 * 1024 * 1024  # 200MB
        
        if total_size > max_batch_size:
            self.validation_errors.append({
                'type': 'batch_size',
                'message': f'Batch too large: {total_size/1024/1024:.1f}MB (maximum: {max_batch_size/1024/1024}MB)'
            })
        
        # Check for duplicate filenames
        filenames = [f.name for f in files if f.name]
        duplicates = set([name for name in filenames if filenames.count(name) > 1])
        if duplicates:
            self.validation_errors.append({
                'type': 'duplicate_names',
                'message': f'Duplicate filenames: {", ".join(duplicates)}'
            })
    
    def _validate_single_file(self, file_obj: UploadedFile) -> Dict[str, Any]:
        """Validate a single file"""
        file_errors = []
        file_warnings = []
        
        try:
            # Basic file validation
            self._validate_filename(file_obj.name, file_errors)
            self._validate_file_size(file_obj, file_errors)
            
            # MIME type validation
            if hasattr(file_obj, 'content_type'):
                self._validate_mime_type(file_obj, file_errors)
            
            # Content validation (for small files only)
            if file_obj.size < 5 * 1024 * 1024:  # Only scan files < 5MB
                self._validate_file_content(file_obj, file_warnings)
            
            return {
                'valid': len(file_errors) == 0,
                'errors': file_errors,
                'warnings': file_warnings,
                'scanned': True
            }
            
        except Exception as e:
            logger.error(f"🔒 SECURITY: Error validating {file_obj.name}: {e}")
            return {
                'valid': False,
                'errors': [f'Validation failed: {str(e)}'],
                'warnings': [],
                'scanned': False
            }
    
    def _validate_filename(self, filename: str, errors: List[str]):
        """Validate filename for security issues"""
        if not filename:
            errors.append("Empty filename")
            return
        
        # Check dangerous extensions
        file_path = Path(filename)
        extension = file_path.suffix.lower()
        
        if extension in self.DANGEROUS_EXTENSIONS:
            errors.append(f"Dangerous file extension: {extension}")
        
        # Check suspicious patterns
        filename_lower = filename.lower()
        for pattern in self.SUSPICIOUS_PATTERNS:
            if re.search(pattern, filename_lower):
                errors.append(f"Suspicious filename pattern: {pattern}")
        
        # Check length
        if len(filename) > 255:
            errors.append("Filename too long (max 255 characters)")
        
        # Check for null bytes
        if '\x00' in filename:
            errors.append("Null byte in filename")
    
    def _validate_file_size(self, file_obj: UploadedFile, errors: List[str]):
        """Validate file size constraints"""
        if not hasattr(file_obj, 'size') or file_obj.size is None:
            errors.append("Cannot determine file size")
            return
        
        # Check general size limit
        max_size = 50 * 1024 * 1024  # 50MB general limit
        if file_obj.size > max_size:
            errors.append(f"File too large: {file_obj.size/1024/1024:.1f}MB (max: {max_size/1024/1024}MB)")
        
        # Check type-specific limits
        extension = Path(file_obj.name).suffix.lower()
        if extension in self.FILE_SIZE_LIMITS:
            type_limit = self.FILE_SIZE_LIMITS[extension]
            if file_obj.size > type_limit:
                errors.append(f"{extension} file too large: {file_obj.size/1024/1024:.1f}MB (max: {type_limit/1024/1024}MB)")
        
        # Check minimum size (empty files)
        if file_obj.size < 10:  # Less than 10 bytes
            errors.append("File appears to be empty")
    
    def _validate_mime_type(self, file_obj: UploadedFile, errors: List[str]):
        """Validate MIME type against file extension"""
        declared_type = file_obj.content_type
        filename = file_obj.name
        
        if not declared_type:
            return  # Skip if no MIME type provided
        
        # Check for dangerous MIME types
        dangerous_types = [
            'application/x-executable',
            'application/x-msdownload',
            'application/x-msdos-program',
            'application/x-winexe',
            'application/x-javascript',
            'text/javascript',
            'application/javascript',
            'text/vbscript',
            'application/x-php',
            'application/x-httpd-php',
        ]
        
        if declared_type in dangerous_types:
            errors.append(f"Dangerous MIME type: {declared_type}")
        
        # Basic MIME type validation for common formats
        extension = Path(filename).suffix.lower()
        expected_types = {
            '.pdf': ['application/pdf'],
            '.txt': ['text/plain'],
            '.html': ['text/html'],
            '.csv': ['text/csv', 'application/csv'],
            '.json': ['application/json', 'text/json'],
            '.docx': ['application/vnd.openxmlformats-officedocument.wordprocessingml.document'],
            '.xlsx': ['application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'],
        }
        
        if extension in expected_types:
            if declared_type not in expected_types[extension]:
                # This is a warning, not an error (browsers can be inconsistent)
                self.security_warnings.append({
                    'file': filename,
                    'type': 'mime_mismatch',
                    'message': f'MIME type {declared_type} doesn\'t match extension {extension}'
                })
    
    def _validate_file_content(self, file_obj: UploadedFile, warnings: List[str]):
        """Validate file content for security issues"""
        try:
            # Read first 64KB for content analysis
            file_obj.seek(0)
            sample_content = file_obj.read(65536).decode('utf-8', errors='ignore')
            file_obj.seek(0)  # Reset file pointer
            
            # Check for dangerous content patterns
            for pattern in self.DANGEROUS_CONTENT_PATTERNS:
                if re.search(pattern, sample_content, re.IGNORECASE | re.DOTALL):
                    warnings.append(f"Suspicious content pattern detected: {pattern[:30]}...")
            
            # Check for sensitive information
            for pattern in self.SUSPICIOUS_TEXT_PATTERNS:
                matches = re.finditer(pattern, sample_content, re.IGNORECASE)
                for match in matches:
                    warnings.append(f"Potential sensitive information: {match.group()[:30]}...")
                    break  # Only report first match per pattern
            
            # Check for excessive binary content (could be embedded files)
            binary_ratio = sum(1 for c in sample_content if ord(c) > 127) / len(sample_content)
            if binary_ratio > 0.3:  # More than 30% non-ASCII
                warnings.append(f"High binary content ratio: {binary_ratio:.2f}")
                
        except Exception as e:
            # Content validation is optional, so don't fail the upload
            logger.warning(f"🔒 SECURITY: Content validation failed for {file_obj.name}: {e}")
    
    def generate_security_report(self, validation_result: Dict[str, Any]) -> str:
        """Generate a human-readable security report"""
        report_lines = []
        
        report_lines.append("🔒 SECURITY VALIDATION REPORT")
        report_lines.append("=" * 40)
        
        # Summary
        files_valid = validation_result['files_valid']
        files_total = validation_result['files_validated']
        errors = validation_result['total_errors']
        warnings = validation_result['total_warnings']
        
        report_lines.append(f"📊 Summary: {files_valid}/{files_total} files valid")
        report_lines.append(f"❌ Errors: {errors}")
        report_lines.append(f"⚠️  Warnings: {warnings}")
        report_lines.append("")
        
        # Batch errors
        if validation_result['batch_errors']:
            report_lines.append("🚨 BATCH ERRORS:")
            for error in validation_result['batch_errors']:
                report_lines.append(f"  - {error['message']}")
            report_lines.append("")
        
        # File-specific issues
        for filename, result in validation_result['file_results'].items():
            if result['errors'] or result['warnings']:
                report_lines.append(f"📁 {filename}:")
                
                for error in result['errors']:
                    report_lines.append(f"  ❌ {error}")
                
                for warning in result['warnings']:
                    report_lines.append(f"  ⚠️  {warning}")
                
                report_lines.append("")
        
        # Security warnings
        if validation_result['security_warnings']:
            report_lines.append("⚠️  SECURITY WARNINGS:")
            for warning in validation_result['security_warnings']:
                report_lines.append(f"  - {warning['file']}: {warning['message']}")
        
        return "\n".join(report_lines)


def scan_for_malware_signatures(file_content: bytes) -> List[str]:
    """
    Basic malware signature detection
    This is a simple implementation - in production, use proper antivirus scanning
    """
    signatures = [
        b'MZ\x90\x00',  # PE executable header
        b'PK\x03\x04',  # ZIP file (could contain executables)
        b'\x7fELF',     # ELF executable
        b'\xca\xfe\xba\xbe',  # Java class file
        b'<?php',       # PHP script
        b'<script',     # JavaScript
        b'javascript:',  # JavaScript URL
        b'vbscript:',   # VBScript URL
    ]
    
    detected = []
    for i, signature in enumerate(signatures):
        if signature in file_content:
            detected.append(f"Signature_{i+1}")
    
    return detected


def hash_file_content(file_obj: UploadedFile) -> str:
    """Generate SHA-256 hash of file content for integrity checking"""
    file_obj.seek(0)
    content = file_obj.read()
    file_obj.seek(0)
    
    return hashlib.sha256(content).hexdigest()


def sanitize_filename(filename: str) -> str:
    """Sanitize filename for safe storage"""
    # Remove dangerous characters
    sanitized = re.sub(r'[<>:"|?*\\]', '_', filename)
    
    # Remove path separators
    sanitized = sanitized.replace('/', '_').replace('\\', '_')
    
    # Remove leading dots (hidden files)
    sanitized = sanitized.lstrip('.')
    
    # Ensure reasonable length
    if len(sanitized) > 200:
        name, ext = os.path.splitext(sanitized)
        sanitized = name[:200-len(ext)] + ext
    
    # Ensure not empty
    if not sanitized:
        sanitized = f"upload_{int(timezone.now().timestamp())}"
    
    return sanitized