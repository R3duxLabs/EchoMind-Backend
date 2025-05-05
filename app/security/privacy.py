"""
Privacy Module

This module provides privacy-related functionality for the application.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Set, Any, Optional, Union
import re

from app.logging_config import get_logger
from app.security.encryption import encryption_service

# Configure logger
logger = get_logger(__name__)

class PrivacyService:
    """Service for handling privacy-related operations"""
    
    # PII (Personally Identifiable Information) patterns
    PII_PATTERNS = {
        "email": r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
        "phone": r'\b(?:\+\d{1,3}[- ]?)?\(?\d{3}\)?[- ]?\d{3}[- ]?\d{4}\b',
        "ssn": r'\b\d{3}[-]?\d{2}[-]?\d{4}\b',
        "credit_card": r'\b(?:\d{4}[- ]?){3}\d{4}\b',
        "address": r'\b\d+\s+[A-Za-z0-9\s,]+(?:avenue|ave|street|st|road|rd|boulevard|blvd|drive|dr|lane|ln|court|ct)[,\s]+[A-Za-z]+(?:[,\s]+[A-Za-z]{2})?[,\s]+\d{5}(?:-\d{4})?\b',
        "ip_address": r'\b(?:\d{1,3}\.){3}\d{1,3}\b',
        "date_of_birth": r'\b(?:0[1-9]|1[0-2])/(?:0[1-9]|[12]\d|3[01])/(?:19|20)\d{2}\b'
    }
    
    @staticmethod
    def detect_pii(text: str) -> Dict[str, List[str]]:
        """
        Detect PII in text.
        
        Args:
            text: Text to scan for PII
            
        Returns:
            Dictionary mapping PII types to lists of detected values
        """
        if not text:
            return {}
            
        results = {}
        
        for pii_type, pattern in PrivacyService.PII_PATTERNS.items():
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                results[pii_type] = matches
                
        return results
    
    @staticmethod
    def redact_pii(text: str, pii_types: Optional[List[str]] = None) -> str:
        """
        Redact PII from text.
        
        Args:
            text: Text to redact
            pii_types: Optional list of PII types to redact, redacts all if None
            
        Returns:
            Redacted text
        """
        if not text:
            return text
            
        redacted_text = text
        
        for pii_type, pattern in PrivacyService.PII_PATTERNS.items():
            if pii_types is None or pii_type in pii_types:
                # Replace matches with redacted text
                redacted_label = f"[REDACTED {pii_type.upper()}]"
                redacted_text = re.sub(pattern, redacted_label, redacted_text, flags=re.IGNORECASE)
                
        return redacted_text
    
    @staticmethod
    def anonymize_data(data: Dict[str, Any], fields_to_anonymize: List[str]) -> Dict[str, Any]:
        """
        Anonymize fields in a data dictionary.
        
        Args:
            data: Dictionary containing data
            fields_to_anonymize: List of field names to anonymize
            
        Returns:
            Anonymized data
        """
        anonymized_data = data.copy()
        
        for field in fields_to_anonymize:
            if field in anonymized_data:
                field_value = anonymized_data[field]
                
                # Skip None values
                if field_value is None:
                    continue
                    
                # Handle different field types
                if isinstance(field_value, str):
                    # Hash strings
                    import hashlib
                    anonymized_data[field] = hashlib.sha256(field_value.encode()).hexdigest()
                elif isinstance(field_value, (int, float)):
                    # Replace numbers with zero
                    anonymized_data[field] = 0
                elif isinstance(field_value, list):
                    # Anonymize list items recursively if they're dictionaries
                    anonymized_data[field] = [
                        PrivacyService.anonymize_data(item, fields_to_anonymize) 
                        if isinstance(item, dict) else "[ANONYMIZED]" 
                        for item in field_value
                    ]
                elif isinstance(field_value, dict):
                    # Anonymize nested dictionaries recursively
                    anonymized_data[field] = PrivacyService.anonymize_data(
                        field_value, fields_to_anonymize
                    )
                else:
                    # Default to simple replacement
                    anonymized_data[field] = "[ANONYMIZED]"
        
        return anonymized_data
    
    @staticmethod
    def encrypt_pii_fields(data: Dict[str, Any], pii_fields: List[str]) -> Dict[str, Any]:
        """
        Encrypt PII fields in a data dictionary.
        
        Args:
            data: Dictionary containing data
            pii_fields: List of field names containing PII to encrypt
            
        Returns:
            Data with encrypted PII fields
        """
        encrypted_data = data.copy()
        
        for field in pii_fields:
            if field in encrypted_data and encrypted_data[field] is not None:
                # Skip already encrypted fields
                if isinstance(encrypted_data[field], dict) and "encrypted_value" in encrypted_data[field]:
                    continue
                    
                try:
                    # Encrypt the field
                    encrypted_data[field] = encryption_service.encrypt_field(encrypted_data[field])
                except Exception as e:
                    logger.error(
                        f"Error encrypting field '{field}': {str(e)}",
                        extra={"field": field},
                        exc_info=True
                    )
        
        return encrypted_data
    
    @staticmethod
    def decrypt_pii_fields(data: Dict[str, Any], pii_fields: List[str]) -> Dict[str, Any]:
        """
        Decrypt PII fields in a data dictionary.
        
        Args:
            data: Dictionary containing data
            pii_fields: List of field names containing encrypted PII
            
        Returns:
            Data with decrypted PII fields
        """
        from app.security.encryption import decrypt_sensitive_fields
        return decrypt_sensitive_fields(data, pii_fields)
    
    @staticmethod
    def generate_data_export(
        user_id: str,
        data_categories: List[str],
        include_deleted: bool = False,
        anonymize: bool = False
    ) -> Dict[str, Any]:
        """
        Generate a data export for GDPR/privacy compliance.
        
        Args:
            user_id: User ID to export data for
            data_categories: Categories of data to include
            include_deleted: Whether to include deleted data
            anonymize: Whether to anonymize the data
            
        Returns:
            Dictionary with exported data
        """
        # This is a placeholder implementation
        # In a real application, this would query the database for the user's data
        
        export = {
            "user_id": user_id,
            "export_date": datetime.utcnow().isoformat(),
            "data_categories": data_categories,
            "data": {}
        }
        
        # Example data inclusion based on categories
        if "profile" in data_categories:
            export["data"]["profile"] = {
                "user_id": user_id,
                "name": "John Doe",
                "email": "john.doe@example.com"
            }
            
        if "sessions" in data_categories:
            export["data"]["sessions"] = [
                {"id": "session1", "date": "2023-01-01T00:00:00Z"},
                {"id": "session2", "date": "2023-01-02T00:00:00Z"}
            ]
            
        if "memories" in data_categories:
            export["data"]["memories"] = [
                {"id": "memory1", "type": "general", "content": "This is a memory"}
            ]
        
        # Anonymize if requested
        if anonymize:
            export = PrivacyService.anonymize_data(
                export, 
                ["email", "name", "phone_number", "address"]
            )
        
        return export


# Privacy policy versions
PRIVACY_POLICY_VERSIONS = {
    "1.0": {
        "version": "1.0",
        "effective_date": "2023-01-01",
        "text": "This is the initial privacy policy."
    },
    "1.1": {
        "version": "1.1", 
        "effective_date": "2023-02-15",
        "text": "Updated privacy policy with additional terms."
    },
    "2.0": {
        "version": "2.0",
        "effective_date": "2023-05-01",
        "text": "Major update to privacy policy."
    }
}

def get_current_privacy_policy() -> Dict[str, Any]:
    """
    Get the current privacy policy.
    
    Returns:
        Dictionary with privacy policy information
    """
    return PRIVACY_POLICY_VERSIONS["2.0"]

def get_privacy_policy_by_version(version: str) -> Optional[Dict[str, Any]]:
    """
    Get a privacy policy by version.
    
    Args:
        version: Privacy policy version
        
    Returns:
        Dictionary with privacy policy information or None if not found
    """
    return PRIVACY_POLICY_VERSIONS.get(version)

async def record_privacy_policy_acceptance(
    user_id: str,
    policy_version: str,
    accepted_at: Optional[datetime] = None
) -> bool:
    """
    Record a user's acceptance of a privacy policy.
    
    Args:
        user_id: User ID
        policy_version: Privacy policy version
        accepted_at: Optional timestamp, defaults to now
        
    Returns:
        True if successful, False otherwise
    """
    # This is a placeholder implementation
    # In a real application, this would store the acceptance in a database
    
    if policy_version not in PRIVACY_POLICY_VERSIONS:
        logger.warning(
            f"Invalid privacy policy version: {policy_version}",
            extra={"user_id": user_id, "policy_version": policy_version}
        )
        return False
        
    if accepted_at is None:
        accepted_at = datetime.utcnow()
        
    logger.info(
        f"User accepted privacy policy",
        extra={
            "user_id": user_id,
            "policy_version": policy_version,
            "accepted_at": accepted_at.isoformat()
        }
    )
    
    return True