"""
Forms for Public Chatbot Admin - Simplified Bulk Document Upload
"""
from django import forms
from django.core.exceptions import ValidationError


class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True

class MultipleFileField(forms.FileField):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("widget", MultipleFileInput())
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        single_file_clean = super().clean
        if isinstance(data, (list, tuple)):
            result = [single_file_clean(d, initial) for d in data]
        else:
            result = single_file_clean(data, initial)
        return result

class BulkDocumentUploadForm(forms.Form):
    """
    Simplified form for bulk document upload in Django admin
    """
    
    # Multiple file upload field
    files = MultipleFileField(
        widget=MultipleFileInput(attrs={
            'class': 'form-control-file',
            'accept': '.txt,.pdf,.docx,.html,.md,.csv,.json'
        }),
        help_text="Select multiple files to upload. Supported formats: TXT, PDF, DOCX, HTML, MD, CSV, JSON",
        required=True
    )
    
    # Category selection
    category = forms.CharField(
        max_length=50,
        initial='general',
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'e.g., documentation, faq, technical'
        }),
        help_text="Category for all uploaded documents"
    )
    
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
    
    def clean_files(self):
        """Extract and validate files from request.FILES"""
        # Get files from request.FILES using getlist for multiple files
        if hasattr(self, 'data'):
            # This is handled by Django's standard form processing
            pass
        
        # The files will be in request.FILES, we'll handle them in the view
        return self.cleaned_data.get('files')

