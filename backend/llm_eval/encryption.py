from cryptography.fernet import Fernet
from django.conf import settings
import base64
import os

def get_encryption_key():
    """Get or create encryption key for API keys"""
    # In production, this should be stored securely (environment variable, AWS KMS, etc.)
    key = getattr(settings, 'API_KEY_ENCRYPTION_KEY', None)
    if not key:
        # Generate a new key (for development only)
        key = Fernet.generate_key()
        print(f"Generated new encryption key: {key.decode()}")
        print("Add this to your settings: API_KEY_ENCRYPTION_KEY = '{}'".format(key.decode()))
    else:
        key = key.encode() if isinstance(key, str) else key
    
    return key

def encrypt_api_key(api_key: str) -> str:
    """Encrypt an API key for storage"""
    try:
        f = Fernet(get_encryption_key())
        encrypted_key = f.encrypt(api_key.encode('utf-8'))
        return base64.urlsafe_b64encode(encrypted_key).decode('utf-8')
    except Exception as e:
        print(f"Encryption error: {e}")
        raise

def decrypt_api_key(encrypted_key: str) -> str:
    """Decrypt an API key for use"""
    try:
        f = Fernet(get_encryption_key())
        
        # Handle both old and new format
        try:
            # Try new format (base64 encoded)
            encrypted_bytes = base64.urlsafe_b64decode(encrypted_key.encode('utf-8'))
            decrypted_key = f.decrypt(encrypted_bytes)
        except Exception:
            # Try old format (direct bytes)
            decrypted_key = f.decrypt(encrypted_key.encode('utf-8'))
        
        return decrypted_key.decode('utf-8')
    except Exception as e:
        print(f"Decryption error: {e}")
        print(f"Encrypted key format: {type(encrypted_key)}, length: {len(encrypted_key)}")
        # For debugging - try to return the key as-is if it looks like a plain API key
        if encrypted_key.startswith('AIza') and len(encrypted_key) > 30:
            print("Warning: Using unencrypted API key (development only)")
            return encrypted_key
        raise
