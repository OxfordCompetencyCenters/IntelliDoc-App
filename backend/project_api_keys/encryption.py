# backend/project_api_keys/encryption.py

import os
import base64
from cryptography.fernet import Fernet
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

class ProjectAPIKeyEncryption:
    """
    Handles encryption/decryption of project-specific API keys using project-isolated keys.
    Each project gets its own encryption derived from the base key + project ID.
    """
    
    def __init__(self):
        self.base_key = self._get_base_encryption_key()
    
    def _get_base_encryption_key(self) -> bytes:
        """Get the base encryption key from environment"""
        key_str = os.environ.get('PROJECT_API_KEY_ENCRYPTION_KEY')
        
        if not key_str:
            raise ImproperlyConfigured(
                "PROJECT_API_KEY_ENCRYPTION_KEY environment variable not set. "
                "Generate one with: python manage.py setup_project_api_keys generate-key"
            )
        
        try:
            return base64.urlsafe_b64decode(key_str.encode())
        except Exception as e:
            raise ImproperlyConfigured(f"Invalid encryption key format: {e}")
    
    def _get_project_key(self, project_id: str) -> Fernet:
        """Generate project-specific encryption key derived from base key + project ID"""
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
        
        # Use project ID as salt for key derivation
        salt = project_id.encode('utf-8')[:16].ljust(16, b'0')  # Ensure 16 bytes
        
        # Derive project-specific key
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        
        derived_key = kdf.derive(self.base_key)
        fernet_key = base64.urlsafe_b64encode(derived_key)
        
        return Fernet(fernet_key)
    
    def encrypt_api_key(self, project_id: str, api_key: str) -> str:
        """Encrypt API key for specific project"""
        if not api_key or not api_key.strip():
            raise ValueError("API key cannot be empty")
        
        if not project_id:
            raise ValueError("Project ID is required for encryption")
        
        fernet = self._get_project_key(project_id)
        encrypted_bytes = fernet.encrypt(api_key.encode('utf-8'))
        return base64.urlsafe_b64encode(encrypted_bytes).decode('utf-8')
    
    def decrypt_api_key(self, project_id: str, encrypted_key: str) -> str:
        """Decrypt API key for specific project"""
        if not encrypted_key:
            raise ValueError("Encrypted key cannot be empty")
        
        if not project_id:
            raise ValueError("Project ID is required for decryption")
        
        try:
            fernet = self._get_project_key(project_id)
            encrypted_bytes = base64.urlsafe_b64decode(encrypted_key.encode('utf-8'))
            decrypted_bytes = fernet.decrypt(encrypted_bytes)
            return decrypted_bytes.decode('utf-8')
        except Exception as e:
            raise ValueError(f"Failed to decrypt API key: {e}")
    
    def test_encryption(self, project_id: str, test_key: str = "sk-test-key-12345") -> bool:
        """Test encryption/decryption for a project"""
        try:
            encrypted = self.encrypt_api_key(project_id, test_key)
            decrypted = self.decrypt_api_key(project_id, encrypted)
            return decrypted == test_key
        except Exception:
            return False
    
    def encrypt_mcp_credentials(self, project_id: str, credentials_dict: dict) -> str:
        """
        Encrypt MCP server credentials (JSON dict) for specific project
        
        Args:
            project_id: Project ID for key derivation
            credentials_dict: Dictionary containing credentials (OAuth tokens, client IDs, etc.)
            
        Returns:
            Base64-encoded encrypted JSON string
        """
        import json
        
        if not credentials_dict:
            raise ValueError("Credentials dictionary cannot be empty")
        
        if not project_id:
            raise ValueError("Project ID is required for encryption")
        
        # Convert dict to JSON string
        credentials_json = json.dumps(credentials_dict)
        
        # Encrypt using same method as API keys
        fernet = self._get_project_key(project_id)
        encrypted_bytes = fernet.encrypt(credentials_json.encode('utf-8'))
        return base64.urlsafe_b64encode(encrypted_bytes).decode('utf-8')
    
    def decrypt_mcp_credentials(self, project_id: str, encrypted_credentials: str) -> dict:
        """
        Decrypt MCP server credentials for specific project
        
        Args:
            project_id: Project ID for key derivation
            encrypted_credentials: Base64-encoded encrypted credentials JSON
            
        Returns:
            Dictionary containing decrypted credentials
        """
        import json
        
        if not encrypted_credentials:
            raise ValueError("Encrypted credentials cannot be empty")
        
        if not project_id:
            raise ValueError("Project ID is required for decryption")
        
        try:
            fernet = self._get_project_key(project_id)
            encrypted_bytes = base64.urlsafe_b64decode(encrypted_credentials.encode('utf-8'))
            decrypted_bytes = fernet.decrypt(encrypted_bytes)
            credentials_json = decrypted_bytes.decode('utf-8')
            return json.loads(credentials_json)
        except json.JSONDecodeError as e:
            raise ValueError(f"Failed to parse decrypted credentials JSON: {e}")
        except Exception as e:
            raise ValueError(f"Failed to decrypt MCP credentials: {e}")

# Global instance
encryption_service = ProjectAPIKeyEncryption()
