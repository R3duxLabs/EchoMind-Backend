"""
Authorization Module

This module provides authorization mechanisms for controlling access to resources.
"""

import logging
from enum import Enum
from typing import Dict, List, Set, Optional, Any, Union
from datetime import datetime

from fastapi import HTTPException, status, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.models import User, MemoryAccessLevel, Memory
from app.database import get_db
from app.logging_config import get_logger
from app.security.authentication import get_current_user

# Configure logger
logger = get_logger(__name__)

# Permission types
class PermissionType(str, Enum):
    """Types of permissions in the system"""
    READ = "read"
    WRITE = "write"
    DELETE = "delete"
    ADMIN = "admin"
    SHARE = "share"
    EXECUTE = "execute"
    CREATE = "create"

# Resource types
class ResourceType(str, Enum):
    """Types of resources in the system"""
    MEMORY = "memory"
    USER = "user"
    SESSION = "session"
    SUMMARY = "summary"
    MILESTONE = "milestone"
    AGENT = "agent"
    SYSTEM = "system"

class AuthorizationService:
    """Service for authorization checks"""
    
    @staticmethod
    async def check_permission(
        user_id: str,
        resource_type: ResourceType,
        resource_id: str,
        permission: PermissionType,
        db: AsyncSession
    ) -> bool:
        """
        Check if a user has a specific permission on a resource.
        
        Args:
            user_id: The user ID
            resource_type: Type of resource
            resource_id: ID of the resource
            permission: Permission to check
            db: Database session
            
        Returns:
            True if the user has the permission, False otherwise
        """
        # Get user
        user = await db.get(User, user_id)
        if not user:
            logger.warning(
                "Authorization check for nonexistent user",
                extra={
                    "user_id": user_id,
                    "resource_type": resource_type,
                    "resource_id": resource_id,
                    "permission": permission
                }
            )
            return False
            
        # Admin users have all permissions
        if user.role == "admin":
            logger.info(
                "Admin user granted permission",
                extra={
                    "user_id": user_id,
                    "resource_type": resource_type,
                    "resource_id": resource_id,
                    "permission": permission
                }
            )
            return True
        
        # Handle different resource types
        if resource_type == ResourceType.MEMORY:
            return await AuthorizationService._check_memory_permission(
                user_id, resource_id, permission, db
            )
        elif resource_type == ResourceType.USER:
            return await AuthorizationService._check_user_permission(
                user_id, resource_id, permission, db
            )
        elif resource_type == ResourceType.SESSION:
            return await AuthorizationService._check_session_permission(
                user_id, resource_id, permission, db
            )
        elif resource_type == ResourceType.AGENT:
            return await AuthorizationService._check_agent_permission(
                user_id, resource_id, permission, db
            )
        else:
            # Default resource checks
            return await AuthorizationService._check_default_permission(
                user, resource_type, resource_id, permission, db
            )
    
    @staticmethod
    async def _check_memory_permission(
        user_id: str,
        memory_id: str,
        permission: PermissionType,
        db: AsyncSession
    ) -> bool:
        """
        Check permission for memory resources.
        
        Args:
            user_id: The user ID
            memory_id: Memory ID
            permission: Permission to check
            db: Database session
            
        Returns:
            True if the user has the permission, False otherwise
        """
        # Get the memory
        memory = await db.get(Memory, memory_id)
        if not memory:
            logger.warning(
                "Authorization check for nonexistent memory",
                extra={
                    "user_id": user_id,
                    "memory_id": memory_id,
                    "permission": permission
                }
            )
            return False
        
        # Owner has all permissions
        if memory.user_id == user_id:
            return True
        
        # Check access level
        if memory.access_level == MemoryAccessLevel.PRIVATE:
            # Private memories are only accessible to the owner
            return False
        elif memory.access_level == MemoryAccessLevel.PUBLIC:
            # Public memories are readable by everyone, but only writable by the owner
            if permission == PermissionType.READ:
                return True
            else:
                return False
        elif memory.access_level == MemoryAccessLevel.SHARED:
            # Check for sharing permissions
            from app.models import MemorySharingPermission
            
            query = select(MemorySharingPermission).where(
                (MemorySharingPermission.memory_id == memory_id) &
                (MemorySharingPermission.shared_with_user_id == user_id)
            )
            
            result = await db.execute(query)
            sharing = result.scalars().first()
            
            if sharing:
                # Check if sharing has expired
                if sharing.expires_at and sharing.expires_at < datetime.utcnow():
                    return False
                    
                # For now, sharing grants read-only access
                if permission == PermissionType.READ:
                    return True
            
            return False
        elif memory.access_level == MemoryAccessLevel.AGENT_ONLY:
            # For agent-only access, we'd need to check if the request is from an agent
            # This would require additional context that we don't have in this function
            return False
        
        # Default deny
        return False
    
    @staticmethod
    async def _check_user_permission(
        user_id: str,
        target_user_id: str,
        permission: PermissionType,
        db: AsyncSession
    ) -> bool:
        """
        Check permission for user resources.
        
        Args:
            user_id: The user ID
            target_user_id: Target user ID
            permission: Permission to check
            db: Database session
            
        Returns:
            True if the user has the permission, False otherwise
        """
        # Users can read their own profile
        if user_id == target_user_id:
            if permission in [PermissionType.READ, PermissionType.WRITE]:
                return True
                
        # Check relationships
        from app.models import Relationship, RelationshipType, VisibilityLevel
        
        # Look for a relationship between the users
        query = select(Relationship).where(
            (
                ((Relationship.user_a_id == user_id) & 
                 (Relationship.user_b_id == target_user_id)) |
                ((Relationship.user_a_id == target_user_id) & 
                 (Relationship.user_b_id == user_id))
            ) &
            (Relationship.approved == True)
        )
        
        result = await db.execute(query)
        relationship = result.scalars().first()
        
        if relationship:
            # Check visibility level
            if relationship.visibility_level == VisibilityLevel.NONE:
                return False
            elif relationship.visibility_level == VisibilityLevel.SUMMARY:
                # Summary allows reading basic info
                if permission == PermissionType.READ:
                    return True
            elif relationship.visibility_level == VisibilityLevel.FULL:
                # Full allows reading everything
                if permission == PermissionType.READ:
                    return True
            elif relationship.visibility_level == VisibilityLevel.CUSTOM:
                # Custom would check visibility_rules
                # This is a simplified example
                visibility_rules = relationship.visibility_rules or {}
                if permission == PermissionType.READ and visibility_rules.get("can_read", False):
                    return True
        
        # Default deny
        return False
    
    @staticmethod
    async def _check_session_permission(
        user_id: str,
        session_id: str,
        permission: PermissionType,
        db: AsyncSession
    ) -> bool:
        """
        Check permission for session resources.
        
        Args:
            user_id: The user ID
            session_id: Session ID
            permission: Permission to check
            db: Database session
            
        Returns:
            True if the user has the permission, False otherwise
        """
        # Get the session
        from app.models import SessionLog
        
        session = await db.get(SessionLog, session_id)
        if not session:
            logger.warning(
                "Authorization check for nonexistent session",
                extra={
                    "user_id": user_id,
                    "session_id": session_id,
                    "permission": permission
                }
            )
            return False
        
        # Session owner has all permissions
        if session.user_id == user_id:
            return True
            
        # Other users don't have access by default
        return False
    
    @staticmethod
    async def _check_agent_permission(
        user_id: str,
        agent_id: str,
        permission: PermissionType,
        db: AsyncSession
    ) -> bool:
        """
        Check permission for agent resources.
        
        Args:
            user_id: The user ID
            agent_id: Agent ID
            permission: Permission to check
            db: Database session
            
        Returns:
            True if the user has the permission, False otherwise
        """
        # Get the agent definition
        from app.models import AgentDefinition
        
        agent = await db.get(AgentDefinition, agent_id)
        if not agent:
            logger.warning(
                "Authorization check for nonexistent agent",
                extra={
                    "user_id": user_id,
                    "agent_id": agent_id,
                    "permission": permission
                }
            )
            return False
        
        # Anyone can read public agents
        if permission == PermissionType.READ and agent.is_active:
            return True
            
        # Only admins can modify agents
        user = await db.get(User, user_id)
        if user and user.role == "admin":
            return True
            
        # Default deny
        return False
    
    @staticmethod
    async def _check_default_permission(
        user: User,
        resource_type: ResourceType,
        resource_id: str,
        permission: PermissionType,
        db: AsyncSession
    ) -> bool:
        """
        Default permission checking for other resource types.
        
        Args:
            user: User object
            resource_type: Type of resource
            resource_id: ID of the resource
            permission: Permission to check
            db: Database session
            
        Returns:
            True if the user has the permission, False otherwise
        """
        # For other resources, implement your logic here
        # This is a placeholder implementation
        
        # System resources require admin permissions
        if resource_type == ResourceType.SYSTEM:
            return user.role == "admin"
            
        # Default deny
        return False


# Dependency for checking resource permissions
async def require_permission(
    resource_type: ResourceType,
    resource_id: str,
    permission: PermissionType,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> User:
    """
    Dependency for requiring a specific permission on a resource.
    
    Args:
        resource_type: Type of resource
        resource_id: ID of the resource
        permission: Permission to check
        user: Current user from authentication
        db: Database session
        
    Returns:
        User object if they have permission
        
    Raises:
        HTTPException if the user doesn't have permission
    """
    has_permission = await AuthorizationService.check_permission(
        user_id=user.id,
        resource_type=resource_type,
        resource_id=resource_id,
        permission=permission,
        db=db
    )
    
    if not has_permission:
        logger.warning(
            "Permission denied",
            extra={
                "user_id": user.id,
                "resource_type": resource_type,
                "resource_id": resource_id,
                "permission": permission
            }
        )
        
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"You don't have {permission} permission on this {resource_type}"
        )
    
    return user