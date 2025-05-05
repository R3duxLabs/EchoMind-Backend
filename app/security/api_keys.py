"""
API Key Management

This module provides functions for API key management.
"""

import secrets
import hashlib
import logging
from datetime import datetime, timedelta
from typing import Dict, Optional, List, Any, Tuple
import json

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import or_, and_

from app.logging_config import get_logger
from app.models import User

# Configure logger
logger = get_logger(__name__)

# Define a model for API keys
# In a real application, this would be a SQLAlchemy model
class ApiKeyStore:
    """In-memory store for API keys (for demonstration purposes)"""
    
    # In a real application, this would be a database table
    _keys: Dict[str, Dict[str, Any]] = {}
    
    @classmethod
    async def add_key(cls, key_data: Dict[str, Any]) -> None:
        """Add a key to the store"""
        if "key" not in key_data:
            raise ValueError("Key is required")
            
        cls._keys[key_data["key"]] = key_data
    
    @classmethod
    async def get_key(cls, key: str) -> Optional[Dict[str, Any]]:
        """Get a key from the store"""
        return cls._keys.get(key)
    
    @classmethod
    async def get_keys_for_user(cls, user_id: str) -> List[Dict[str, Any]]:
        """Get all keys for a user"""
        return [
            k for k in cls._keys.values() 
            if k.get("owner_id") == user_id
        ]
    
    @classmethod
    async def delete_key(cls, key: str) -> bool:
        """Delete a key from the store"""
        if key in cls._keys:
            del cls._keys[key]
            return True
        return False
    
    @classmethod
    async def update_key(cls, key: str, key_data: Dict[str, Any]) -> bool:
        """Update a key in the store"""
        if key in cls._keys:
            updated_data = cls._keys[key].copy()
            updated_data.update(key_data)
            cls._keys[key] = updated_data
            return True
        return False

# API Key functions
async def generate_api_key(
    user_id: str,
    name: Optional[str] = None,
    scopes: Optional[List[str]] = None,
    expires_in_days: Optional[int] = None,
    db: AsyncSession = None
) -> Tuple[str, Dict[str, Any]]:
    """
    Generate a new API key for a user.
    
    Args:
        user_id: The user ID to create the key for
        name: Optional name for the key
        scopes: Optional list of scopes for the key
        expires_in_days: Optional expiration in days
        db: Database session
        
    Returns:
        Tuple of (api_key, key_data)
    """
    # Verify user exists
    user = await db.get(User, user_id)
    if not user:
        logger.error(
            "Failed to generate API key: user not found",
            extra={"user_id": user_id}
        )
        raise ValueError(f"User with ID {user_id} not found")
    
    # Generate a random API key
    api_key = secrets.token_urlsafe(32)
    
    # Set default scopes if none provided
    if scopes is None:
        if user.role == "admin":
            scopes = ["user", "admin"]
        else:
            scopes = ["user"]
    
    # Set expiration date if specified
    expires_at = None
    if expires_in_days:
        expires_at = datetime.utcnow() + timedelta(days=expires_in_days)
    
    # Create key data
    key_data = {
        "key": api_key,
        "owner_id": user_id,
        "scopes": scopes,
        "created_at": datetime.utcnow().isoformat(),
        "is_active": True,
        "name": name or f"API Key for {user.name}",
        "expires_at": expires_at.isoformat() if expires_at else None
    }
    
    # Store the key
    # In a real implementation, this would be stored in a database
    await ApiKeyStore.add_key(key_data)
    
    logger.info(
        "Generated new API key",
        extra={
            "user_id": user_id,
            "api_key_prefix": api_key[:6] + "...",
            "scopes": scopes,
            "expires_at": expires_at.isoformat() if expires_at else None
        }
    )
    
    return api_key, key_data

async def get_api_key_info(api_key: str, db: AsyncSession) -> Optional[Dict[str, Any]]:
    """
    Get information about an API key.
    
    Args:
        api_key: The API key to look up
        db: Database session
        
    Returns:
        Key data if found, otherwise None
    """
    # In a real implementation, this would query a database
    key_data = await ApiKeyStore.get_key(api_key)
    
    if not key_data:
        return None
    
    # Convert expires_at from string to datetime if it exists
    if key_data.get("expires_at"):
        key_data["expires_at"] = datetime.fromisoformat(key_data["expires_at"])
        
    # Convert created_at from string to datetime
    if key_data.get("created_at"):
        key_data["created_at"] = datetime.fromisoformat(key_data["created_at"])
    
    return key_data

async def get_user_api_keys(user_id: str, db: AsyncSession) -> List[Dict[str, Any]]:
    """
    Get all API keys for a user.
    
    Args:
        user_id: The user ID to get keys for
        db: Database session
        
    Returns:
        List of key data dictionaries
    """
    # In a real implementation, this would query a database
    keys = await ApiKeyStore.get_keys_for_user(user_id)
    
    # Process dates
    for key in keys:
        if key.get("expires_at"):
            key["expires_at"] = datetime.fromisoformat(key["expires_at"])
        if key.get("created_at"):
            key["created_at"] = datetime.fromisoformat(key["created_at"])
        
        # Don't return the actual key in listings
        key["key"] = key["key"][:6] + "..." + key["key"][-4:]
    
    return keys

async def revoke_api_key(api_key: str, db: AsyncSession) -> bool:
    """
    Revoke an API key.
    
    Args:
        api_key: The API key to revoke
        db: Database session
        
    Returns:
        True if successful, False if key not found
    """
    # In a real implementation, this would update a database
    key_data = await ApiKeyStore.get_key(api_key)
    
    if not key_data:
        logger.warning(
            "Failed to revoke API key: key not found",
            extra={"api_key_prefix": api_key[:6] + "..."}
        )
        return False
    
    # Update key data
    result = await ApiKeyStore.update_key(api_key, {"is_active": False})
    
    if result:
        logger.info(
            "Revoked API key",
            extra={
                "api_key_prefix": api_key[:6] + "...",
                "user_id": key_data.get("owner_id")
            }
        )
    
    return result

async def update_api_key_scopes(
    api_key: str, 
    scopes: List[str],
    db: AsyncSession
) -> bool:
    """
    Update scopes for an API key.
    
    Args:
        api_key: The API key to update
        scopes: New list of scopes
        db: Database session
        
    Returns:
        True if successful, False if key not found
    """
    # In a real implementation, this would update a database
    key_data = await ApiKeyStore.get_key(api_key)
    
    if not key_data:
        logger.warning(
            "Failed to update API key scopes: key not found",
            extra={"api_key_prefix": api_key[:6] + "..."}
        )
        return False
    
    # Update key data
    old_scopes = key_data.get("scopes", [])
    result = await ApiKeyStore.update_key(api_key, {"scopes": scopes})
    
    if result:
        logger.info(
            "Updated API key scopes",
            extra={
                "api_key_prefix": api_key[:6] + "...",
                "user_id": key_data.get("owner_id"),
                "old_scopes": old_scopes,
                "new_scopes": scopes
            }
        )
    
    return result