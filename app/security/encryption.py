"""
Encryption Module

This module provides encryption and decryption utilities for sensitive data.
"""

import base64
import logging
import os
from typing import Union, Dict, Any, Optional
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from app.logging_config import get_logger

# Configure logger
logger = get_logger(__name__)

# Environment variables for encryption configuration
# In a real application, these would be fetched from actual environment variables
ENCRYPTION_KEY = os.environ.get("ENCRYPTION_KEY", "RpCFkNT6EwLAMaXHzDTiU_eLJ4Aw6uRDKTT7_QHcPKE=")
ENCRYPTION_SALT = os.environ.get("ENCRYPTION_SALT", "saltysaltysalt")

class EncryptionService:
    """Service for encrypting and decrypting sensitive data"""
    
    def __init__(self, key: Optional[str] = None, salt: Optional[str] = None):
        """
        Initialize the encryption service.
        
        Args:
            key: Base64-encoded key or None to use environment variable
            salt: Salt string or None to use environment variable
        """
        self.key = key or ENCRYPTION_KEY
        self.salt = salt or ENCRYPTION_SALT
        
        # Validate key
        if not self.key:
            raise ValueError("Encryption key is required")
            
        # Initialize Fernet cipher with the key
        try:
            key_bytes = base64.urlsafe_b64decode(self.key)
            self.cipher = Fernet(self.key)
        except Exception as e:
            logger.error(f"Error initializing encryption service: {str(e)}", exc_info=True)
            raise ValueError(f"Invalid encryption key: {str(e)}")
    
    @staticmethod
    def generate_key(password: str, salt: Optional[str] = None) -> str:
        """
        Generate an encryption key from a password.
        
        Args:
            password: Password string
            salt: Optional salt string
            
        Returns:
            Base64-encoded key
        """
        if not salt:
            salt = ENCRYPTION_SALT
            
        # Convert inputs to bytes
        password_bytes = password.encode()
        salt_bytes = salt.encode()
        
        # Use PBKDF2 to derive a key
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt_bytes,
            iterations=100000
        )
        
        key = base64.urlsafe_b64encode(kdf.derive(password_bytes))
        return key.decode()
    
    def encrypt(self, data: Union[str, bytes, Dict[str, Any]]) -> str:
        """
        Encrypt data.
        
        Args:
            data: Data to encrypt (string, bytes or JSON-serializable dict)
            
        Returns:
            Base64-encoded encrypted data
        """
        try:
            # Convert data to bytes
            if isinstance(data, dict):
                import json
                data_bytes = json.dumps(data).encode()
            elif isinstance(data, str):
                data_bytes = data.encode()
            else:
                data_bytes = data
                
            # Encrypt data
            encrypted_data = self.cipher.encrypt(data_bytes)
            
            # Return as base64 string
            return base64.urlsafe_b64encode(encrypted_data).decode()
            
        except Exception as e:
            logger.error(f"Encryption error: {str(e)}", exc_info=True)
            raise RuntimeError(f"Encryption failed: {str(e)}")
    
    def decrypt(self, encrypted_data: str, as_json: bool = False) -> Union[str, Dict[str, Any]]:
        """
        Decrypt data.
        
        Args:
            encrypted_data: Base64-encoded encrypted data
            as_json: Whether to parse the decrypted data as JSON
            
        Returns:
            Decrypted data as string or dict
        """
        try:
            # Convert from base64
            encrypted_bytes = base64.urlsafe_b64decode(encrypted_data)
            
            # Decrypt data
            decrypted_bytes = self.cipher.decrypt(encrypted_bytes)
            
            # Convert to string
            decrypted_str = decrypted_bytes.decode()
            
            # Parse as JSON if requested
            if as_json:
                import json
                return json.loads(decrypted_str)
                
            return decrypted_str
            
        except Exception as e:
            logger.error(f"Decryption error: {str(e)}", exc_info=True)
            raise RuntimeError(f"Decryption failed: {str(e)}")
    
    def encrypt_field(self, data: Union[str, Dict[str, Any]]) -> Dict[str, str]:
        """
        Encrypt a field and return both the encrypted value and metadata.
        
        Args:
            data: Data to encrypt
            
        Returns:
            Dictionary with encrypted_value and metadata
        """
        encrypted_value = self.encrypt(data)
        return {
            "encrypted_value": encrypted_value,
            "metadata": {
                "encrypted": True,
                "timestamp": str(int(datetime.utcnow().timestamp()))
            }
        }
    
    def decrypt_field(self, encrypted_field: Dict[str, Any], as_json: bool = False) -> Union[str, Dict[str, Any]]:
        """
        Decrypt a field from the encrypted_field format.
        
        Args:
            encrypted_field: Dictionary with encrypted_value and metadata
            as_json: Whether to parse the decrypted data as JSON
            
        Returns:
            Decrypted data
        """
        if not isinstance(encrypted_field, dict) or "encrypted_value" not in encrypted_field:
            raise ValueError("Invalid encrypted field format")
            
        metadata = encrypted_field.get("metadata", {})
        if not metadata.get("encrypted", False):
            return encrypted_field.get("encrypted_value")
            
        return self.decrypt(encrypted_field["encrypted_value"], as_json)


# Singleton instance for the application
from datetime import datetime

encryption_service = EncryptionService()

# Helper function to encrypt sensitive fields in a dictionary
def encrypt_sensitive_fields(data: Dict[str, Any], sensitive_fields: list) -> Dict[str, Any]:
    """
    Encrypt sensitive fields in a dictionary.
    
    Args:
        data: Dictionary containing data
        sensitive_fields: List of field names to encrypt
        
    Returns:
        Dictionary with sensitive fields encrypted
    """
    result = data.copy()
    
    for field in sensitive_fields:
        if field in result and result[field] is not None:
            result[field] = encryption_service.encrypt_field(result[field])
    
    return result

# Helper function to decrypt sensitive fields in a dictionary
def decrypt_sensitive_fields(data: Dict[str, Any], sensitive_fields: list) -> Dict[str, Any]:
    """
    Decrypt sensitive fields in a dictionary.
    
    Args:
        data: Dictionary containing data
        sensitive_fields: List of field names to decrypt
        
    Returns:
        Dictionary with sensitive fields decrypted
    """
    result = data.copy()
    
    for field in sensitive_fields:
        if field in result and isinstance(result[field], dict) and "encrypted_value" in result[field]:
            try:
                result[field] = encryption_service.decrypt_field(result[field])
            except Exception as e:
                logger.error(f"Error decrypting field '{field}': {str(e)}", exc_info=True)
                result[field] = "**DECRYPTION_ERROR**"
    
    return result