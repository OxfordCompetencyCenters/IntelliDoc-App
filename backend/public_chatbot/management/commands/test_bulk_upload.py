"""
Test command for bulk document upload functionality
Creates sample files and tests the upload processor
"""
import os
import tempfile
from pathlib import Path
from django.core.management.base import BaseCommand
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone

from public_chatbot.document_processor import DocumentProcessor
from public_chatbot.security import DocumentSecurityValidator


class Command(BaseCommand):
    help = 'Test bulk document upload functionality with sample files'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--create-samples',
            action='store_true',
            help='Create sample files for testing'
        )
        parser.add_argument(
            '--test-security',
            action='store_true',
            help='Test security validation with malicious samples'
        )
        parser.add_argument(
            '--test-formats',
            action='store_true',
            help='Test all supported file formats'
        )
        parser.add_argument(
            '--output-dir',
            type=str,
            default='/tmp/chatbot_upload_test',
            help='Directory to create sample files'
        )
    
    def handle(self, *args, **options):
        """Execute test command"""
        self.stdout.write(self.style.SUCCESS('🧪 Testing Bulk Document Upload Functionality'))
        
        if options['create_samples']:
            self.create_sample_files(options['output_dir'])
        
        if options['test_security']:
            self.test_security_validation()
        
        if options['test_formats']:
            self.test_format_processing()
        
        self.stdout.write(self.style.SUCCESS('✅ Testing completed'))
    
    def create_sample_files(self, output_dir: str):
        """Create sample files for testing"""
        self.stdout.write('📁 Creating sample files...')
        
        # Create output directory
        os.makedirs(output_dir, exist_ok=True)
        
        # Sample content templates
        samples = {
            'sample_text.txt': """This is a sample text document for testing.
It contains multiple paragraphs and some structured content.

Key Points:
- Point one with important information
- Point two with additional details
- Point three with final thoughts

This document should be processed successfully by the upload system.""",
            
            'sample_markdown.md': """# Sample Markdown Document

This is a **markdown** document with various formatting elements.

## Features Tested

1. Headers at multiple levels
2. **Bold** and *italic* text
3. Lists and bullet points
4. Code blocks and `inline code`

```python
def hello_world():
    print("Hello, World!")
```

### Conclusion

This markdown file tests the markdown processing capabilities.""",
            
            'sample_html.html': """<!DOCTYPE html>
<html>
<head>
    <title>Sample HTML Document</title>
</head>
<body>
    <h1>Test HTML Document</h1>
    <p>This is a sample HTML document for testing the HTML processor.</p>
    
    <h2>Features</h2>
    <ul>
        <li>HTML tag processing</li>
        <li>Text extraction</li>
        <li>Structure preservation</li>
    </ul>
    
    <div class="content">
        <p>The processor should extract clean text from this HTML.</p>
    </div>
</body>
</html>""",
            
            'sample_data.csv': """Name,Category,Description,Score
Document A,Technical,"API documentation with examples",95
Document B,General,"User guide for beginners",87
Document C,FAQ,"Frequently asked questions",92
Document D,Technical,"Advanced configuration guide",89""",
            
            'sample_config.json': """{
    "application": {
        "name": "Test Application",
        "version": "1.0.0",
        "features": [
            "document_processing",
            "bulk_upload",
            "security_validation"
        ]
    },
    "settings": {
        "max_file_size": "50MB",
        "supported_formats": [".txt", ".pdf", ".docx", ".html"],
        "security_enabled": true
    },
    "metadata": {
        "created": "2025-01-01",
        "purpose": "Testing document upload functionality"
    }
}""",
            
            'large_document.txt': self._generate_large_text_content(),
        }
        
        # Create files
        created_files = []
        for filename, content in samples.items():
            file_path = Path(output_dir) / filename
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            created_files.append(str(file_path))
            
        self.stdout.write(f'✅ Created {len(created_files)} sample files in {output_dir}')
        
        # Create some malicious test files (for security testing)
        malicious_samples = {
            'malicious_script.js': 'alert("This should be blocked"); document.cookie = "stolen";',
            'suspicious_php.txt': '<?php system($_GET["cmd"]); ?>',
            'large_file.txt': 'X' * (60 * 1024 * 1024),  # 60MB file (should be rejected)
        }
        
        malicious_dir = Path(output_dir) / 'malicious'
        os.makedirs(malicious_dir, exist_ok=True)
        
        for filename, content in malicious_samples.items():
            file_path = malicious_dir / filename
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
        
        self.stdout.write(f'⚠️  Created {len(malicious_samples)} malicious test files in {malicious_dir}')
        
        # Show usage instructions
        self.stdout.write('\n📋 Usage Instructions:')
        self.stdout.write(f'1. Use files in {output_dir} for normal upload testing')
        self.stdout.write(f'2. Use files in {malicious_dir} for security testing')
        self.stdout.write('3. Access Django admin at /admin/public_chatbot/publicknowledgedocument/')
        self.stdout.write('4. Click "📁 Bulk Upload Documents" button')
        self.stdout.write('5. Upload the sample files and test the functionality')
    
    def test_security_validation(self):
        """Test security validation functionality"""
        self.stdout.write('🔒 Testing security validation...')
        
        # Create test files in memory
        test_files = [
            SimpleUploadedFile('normal.txt', b'This is normal content', content_type='text/plain'),
            SimpleUploadedFile('large.txt', b'X' * (60 * 1024 * 1024), content_type='text/plain'),  # Too large
            SimpleUploadedFile('malicious.js', b'alert("xss")', content_type='text/javascript'),
            SimpleUploadedFile('suspicious.php', b'<?php system($_GET["cmd"]); ?>', content_type='text/plain'),
            SimpleUploadedFile('../../../etc/passwd', b'root:x:0:0:root:/root:/bin/bash', content_type='text/plain'),
        ]
        
        validator = DocumentSecurityValidator()
        result = validator.validate_upload_batch(test_files)
        
        self.stdout.write(f'📊 Security validation results:')
        self.stdout.write(f'  Files validated: {result["files_validated"]}')
        self.stdout.write(f'  Files valid: {result["files_valid"]}')
        self.stdout.write(f'  Files invalid: {result["files_invalid"]}')
        self.stdout.write(f'  Total errors: {result["total_errors"]}')
        self.stdout.write(f'  Total warnings: {result["total_warnings"]}')
        
        if result['batch_errors']:
            self.stdout.write('🚨 Batch errors:')
            for error in result['batch_errors']:
                self.stdout.write(f'  - {error["message"]}')
        
        # Show detailed report
        report = validator.generate_security_report(result)
        self.stdout.write('\n' + report)
        
        if result['files_invalid'] > 0:
            self.stdout.write(self.style.SUCCESS('✅ Security validation working - blocked malicious files'))
        else:
            self.stdout.write(self.style.ERROR('❌ Security validation may not be working properly'))
    
    def test_format_processing(self):
        """Test document format processing"""
        self.stdout.write('📄 Testing format processing...')
        
        # Create test files for each supported format
        test_files = []
        
        # Text file
        test_files.append(SimpleUploadedFile(
            'test.txt', 
            b'This is a test text document with multiple lines.\nSecond line.\nThird line.',
            content_type='text/plain'
        ))
        
        # HTML file
        test_files.append(SimpleUploadedFile(
            'test.html',
            b'<html><body><h1>Test HTML</h1><p>This is a paragraph.</p></body></html>',
            content_type='text/html'
        ))
        
        # CSV file
        test_files.append(SimpleUploadedFile(
            'test.csv',
            b'Name,Value,Description\nItem1,100,First item\nItem2,200,Second item',
            content_type='text/csv'
        ))
        
        # JSON file
        test_files.append(SimpleUploadedFile(
            'test.json',
            b'{"name": "Test Document", "type": "JSON", "data": [1, 2, 3]}',
            content_type='application/json'
        ))
        
        # Markdown file
        test_files.append(SimpleUploadedFile(
            'test.md',
            b'# Test Markdown\n\nThis is **bold** and *italic* text.\n\n- List item 1\n- List item 2',
            content_type='text/markdown'
        ))
        
        # Process files
        processor = DocumentProcessor()
        result = processor.process_uploaded_files(test_files, 'test_category', 'test_user')
        
        self.stdout.write(f'📊 Processing results:')
        self.stdout.write(f'  Success: {result["success"]}')
        self.stdout.write(f'  Processed: {result["processed_count"]}')
        self.stdout.write(f'  Errors: {result["error_count"]}')
        self.stdout.write(f'  Warnings: {result["warning_count"]}')
        
        if result['errors']:
            self.stdout.write('❌ Errors:')
            for error in result['errors']:
                self.stdout.write(f'  - {error["file"]}: {error["error"]}')
        
        if result['warnings']:
            self.stdout.write('⚠️  Warnings:')
            for warning in result['warnings']:
                self.stdout.write(f'  - {warning["file"]}: {warning["warning"]}')
        
        # Show processed documents
        if result['documents']:
            self.stdout.write(f'\n📋 Processed Documents:')
            for doc in result['documents']:
                content_length = len(doc['content'])
                self.stdout.write(f'  📄 {doc["title"]}:')
                self.stdout.write(f'    Category: {doc["category"]}')
                self.stdout.write(f'    Content length: {content_length} characters')
                self.stdout.write(f'    Quality score: {doc["quality_score"]}')
                self.stdout.write(f'    Tags: {doc["tags"]}')
                self.stdout.write(f'    Content preview: {doc["content"][:100]}...')
                self.stdout.write('')
        
        # Check format support
        dependencies = DocumentProcessor.check_dependencies()
        self.stdout.write('\n🔧 Format support status:')
        for format_type, available in dependencies.items():
            status = '✅' if available else '❌'
            self.stdout.write(f'  {status} {format_type.upper()}: {"Available" if available else "Not available"}')
    
    def _generate_large_text_content(self) -> str:
        """Generate large text content for testing"""
        base_paragraph = """This is a test paragraph that will be repeated multiple times to create a large document. 
It contains sufficient text to test the chunking and processing capabilities of the system. 
The content includes various sentences with different structures and vocabulary to ensure proper processing. 
This paragraph tests how the system handles larger documents and validates the chunking algorithms work correctly."""
        
        # Repeat to create ~10KB document
        paragraphs = []
        for i in range(50):
            paragraphs.append(f"Paragraph {i+1}: {base_paragraph}")
        
        return "\n\n".join(paragraphs)