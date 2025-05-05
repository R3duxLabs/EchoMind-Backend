"""
Agent Memory Access Controls

This module implements the memory access control system for agents,
ensuring that each agent only has access to the memories it needs
and is authorized to access.
"""

from typing import Dict, List, Optional, Any, Union, Set
from enum import Enum
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.agents.protocol import (
    AgentMessage,
    MessageType,
    MemoryAccessRequest,
    create_message
)
from app.models import (
    MemorySnapshot,
    SummaryLog,
    User
)
from app.logging_config import get_logger

logger = get_logger(__name__)

class MemoryAccessLevel(str, Enum):
    """Access levels for memory"""
    NONE = "none"           # No access
    READ = "read"           # Read-only access
    WRITE = "write"         # Can read and write
    ADMIN = "admin"         # Full access including deletion

class MemoryCategory(str, Enum):
    """Categories of memory that can have different access controls"""
    GENERAL = "general"           # General memory
    EMOTIONAL = "emotional"       # Emotional state and history
    PERSONAL = "personal"         # Personal information
    MEDICAL = "medical"           # Medical information
    THERAPEUTIC = "therapeutic"   # Therapeutic insights and notes
    SYSTEM = "system"             # System-related memory
    SESSION = "session"           # Current session memory

class MemoryScope(str, Enum):
    """Scopes that limit memory access"""
    CURRENT_SESSION = "current_session"   # Limited to current session
    RECENT = "recent"                     # Limited to recent sessions
    HISTORICAL = "historical"             # Access to historical sessions
    ALL = "all"                           # Access to all memory

class MemoryAccessPolicy:
    """
    Defines access policies for memory
    
    This class manages the rules for which agents can access
    which types of memory and what operations they can perform.
    """
    
    # Default access policies by agent and memory category
    DEFAULT_POLICIES = {
        # Default agent has read access to general memory
        "EchoMind": {
            MemoryCategory.GENERAL: MemoryAccessLevel.WRITE,
            MemoryCategory.EMOTIONAL: MemoryAccessLevel.WRITE,
            MemoryCategory.PERSONAL: MemoryAccessLevel.READ,
            MemoryCategory.MEDICAL: MemoryAccessLevel.NONE,
            MemoryCategory.THERAPEUTIC: MemoryAccessLevel.READ,
            MemoryCategory.SYSTEM: MemoryAccessLevel.READ,
            MemoryCategory.SESSION: MemoryAccessLevel.WRITE
        },
        # Therapist has access to therapeutic and emotional memory
        "Therapist": {
            MemoryCategory.GENERAL: MemoryAccessLevel.WRITE,
            MemoryCategory.EMOTIONAL: MemoryAccessLevel.WRITE,
            MemoryCategory.PERSONAL: MemoryAccessLevel.READ,
            MemoryCategory.MEDICAL: MemoryAccessLevel.READ,
            MemoryCategory.THERAPEUTIC: MemoryAccessLevel.WRITE,
            MemoryCategory.SYSTEM: MemoryAccessLevel.READ,
            MemoryCategory.SESSION: MemoryAccessLevel.WRITE
        },
        # Bridge agent has limited access
        "Bridge": {
            MemoryCategory.GENERAL: MemoryAccessLevel.READ,
            MemoryCategory.EMOTIONAL: MemoryAccessLevel.READ,
            MemoryCategory.PERSONAL: MemoryAccessLevel.READ,
            MemoryCategory.MEDICAL: MemoryAccessLevel.NONE,
            MemoryCategory.THERAPEUTIC: MemoryAccessLevel.NONE,
            MemoryCategory.SYSTEM: MemoryAccessLevel.READ,
            MemoryCategory.SESSION: MemoryAccessLevel.WRITE
        },
        # Memory service has admin access to all memory
        "MemoryService": {
            MemoryCategory.GENERAL: MemoryAccessLevel.ADMIN,
            MemoryCategory.EMOTIONAL: MemoryAccessLevel.ADMIN,
            MemoryCategory.PERSONAL: MemoryAccessLevel.ADMIN,
            MemoryCategory.MEDICAL: MemoryAccessLevel.ADMIN,
            MemoryCategory.THERAPEUTIC: MemoryAccessLevel.ADMIN,
            MemoryCategory.SYSTEM: MemoryAccessLevel.ADMIN,
            MemoryCategory.SESSION: MemoryAccessLevel.ADMIN
        },
        # Default policy for any agent not explicitly listed
        "*": {
            MemoryCategory.GENERAL: MemoryAccessLevel.READ,
            MemoryCategory.EMOTIONAL: MemoryAccessLevel.READ,
            MemoryCategory.PERSONAL: MemoryAccessLevel.NONE,
            MemoryCategory.MEDICAL: MemoryAccessLevel.NONE,
            MemoryCategory.THERAPEUTIC: MemoryAccessLevel.NONE,
            MemoryCategory.SYSTEM: MemoryAccessLevel.READ,
            MemoryCategory.SESSION: MemoryAccessLevel.WRITE
        }
    }
    
    # Default memory time scopes by agent
    DEFAULT_SCOPES = {
        "EchoMind": MemoryScope.ALL,
        "Therapist": MemoryScope.ALL,
        "Bridge": MemoryScope.RECENT,
        "MemoryService": MemoryScope.ALL,
        "*": MemoryScope.CURRENT_SESSION
    }
    
    @classmethod
    def get_agent_access_level(cls, agent_name: str, memory_category: MemoryCategory) -> MemoryAccessLevel:
        """
        Get the access level for a given agent and memory category
        
        Args:
            agent_name: Name of the agent
            memory_category: Category of memory
            
        Returns:
            MemoryAccessLevel: The agent's access level for this memory category
        """
        # Get the agent's policy, falling back to default if not found
        agent_policy = cls.DEFAULT_POLICIES.get(agent_name, cls.DEFAULT_POLICIES.get("*", {}))
        
        # Get the access level for this category, falling back to NONE if not found
        return agent_policy.get(memory_category, MemoryAccessLevel.NONE)
    
    @classmethod
    def get_agent_scope(cls, agent_name: str) -> MemoryScope:
        """
        Get the memory scope for a given agent
        
        Args:
            agent_name: Name of the agent
            
        Returns:
            MemoryScope: The agent's memory scope
        """
        return cls.DEFAULT_SCOPES.get(agent_name, cls.DEFAULT_SCOPES.get("*", MemoryScope.CURRENT_SESSION))
    
    @classmethod
    def check_access(
        cls, 
        agent_name: str, 
        memory_category: MemoryCategory, 
        operation: str
    ) -> bool:
        """
        Check if an agent has access to perform an operation on memory
        
        Args:
            agent_name: Name of the agent
            memory_category: Category of memory
            operation: Operation to perform (read, write, update, delete)
            
        Returns:
            bool: Whether the agent has access
        """
        access_level = cls.get_agent_access_level(agent_name, memory_category)
        
        # Map operations to required access levels
        required_levels = {
            "read": {MemoryAccessLevel.READ, MemoryAccessLevel.WRITE, MemoryAccessLevel.ADMIN},
            "write": {MemoryAccessLevel.WRITE, MemoryAccessLevel.ADMIN},
            "update": {MemoryAccessLevel.WRITE, MemoryAccessLevel.ADMIN},
            "delete": {MemoryAccessLevel.ADMIN}
        }
        
        # Check if the agent's access level is sufficient
        return access_level in required_levels.get(operation.lower(), {MemoryAccessLevel.ADMIN})
    
    @classmethod
    def get_scope_time_filter(cls, agent_name: str) -> Optional[datetime]:
        """
        Get a time filter based on the agent's memory scope
        
        Args:
            agent_name: Name of the agent
            
        Returns:
            Optional[datetime]: Minimum timestamp for memory access, or None if no time limit
        """
        scope = cls.get_agent_scope(agent_name)
        
        now = datetime.utcnow()
        
        if scope == MemoryScope.CURRENT_SESSION:
            # Assume current session started within the last 24 hours at most
            return now - timedelta(hours=24)
        elif scope == MemoryScope.RECENT:
            # Recent is defined as the last 30 days
            return now - timedelta(days=30)
        elif scope == MemoryScope.HISTORICAL:
            # Historical is defined as the last year
            return now - timedelta(days=365)
        else:  # MemoryScope.ALL
            return None

class MemoryAccessManager:
    """
    Manages memory access for agents
    
    This class handles memory access requests, enforcing access controls
    and providing a unified interface for memory operations.
    """
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.logger = get_logger(__name__)
    
    async def handle_memory_request(self, message: AgentMessage) -> AgentMessage:
        """
        Handle a memory access request
        
        Args:
            message: Memory access request message
            
        Returns:
            AgentMessage: Response message with the results
        """
        if message.type != MessageType.MEMORY_ACCESS:
            raise ValueError(f"Expected MEMORY_ACCESS message, got {message.type}")
        
        # Extract the memory request from the message
        memory_request = message.content
        
        operation = memory_request.get("operation")
        memory_type = memory_request.get("memory_type")
        path = memory_request.get("path")
        
        # Validate required fields
        if not all([operation, memory_type, path]):
            return self._create_error_response(
                message,
                "Invalid memory request: missing required fields"
            )
        
        # Map memory type to category
        try:
            memory_category = self._map_memory_type_to_category(memory_type)
        except ValueError as e:
            return self._create_error_response(message, str(e))
        
        # Check access
        if not MemoryAccessPolicy.check_access(message.sender, memory_category, operation):
            return self._create_error_response(
                message,
                f"Access denied: {message.sender} cannot {operation} {memory_category} memory"
            )
        
        # Handle the operation
        try:
            if operation == "read":
                result = await self._handle_read(
                    message.sender,
                    memory_type,
                    path,
                    message.user_id,
                    memory_request.get("filters", {})
                )
            elif operation == "write":
                result = await self._handle_write(
                    message.sender,
                    memory_type,
                    path,
                    message.user_id,
                    memory_request.get("data")
                )
            elif operation == "update":
                result = await self._handle_update(
                    message.sender,
                    memory_type,
                    path,
                    message.user_id,
                    memory_request.get("data")
                )
            elif operation == "delete":
                result = await self._handle_delete(
                    message.sender,
                    memory_type,
                    path,
                    message.user_id
                )
            else:
                return self._create_error_response(
                    message,
                    f"Invalid operation: {operation}"
                )
            
            # Create success response
            return create_message(
                message_type=MessageType.RESPONSE,
                sender="MemoryService",
                recipient=message.sender,
                content={
                    "status": "success",
                    "result": result
                },
                session_id=message.session_id,
                user_id=message.user_id,
                request_id=message.id
            )
            
        except Exception as e:
            self.logger.error(
                f"Error handling memory request: {str(e)}",
                extra={
                    "message_id": message.id,
                    "operation": operation,
                    "memory_type": memory_type,
                    "path": path,
                    "user_id": message.user_id,
                    "error": str(e)
                },
                exc_info=True
            )
            
            return self._create_error_response(
                message,
                f"Error handling memory request: {str(e)}"
            )
    
    def _create_error_response(self, request: AgentMessage, error_message: str) -> AgentMessage:
        """
        Create an error response message
        
        Args:
            request: Original request message
            error_message: Error message text
            
        Returns:
            AgentMessage: Error response message
        """
        return create_message(
            message_type=MessageType.RESPONSE,
            sender="MemoryService",
            recipient=request.sender,
            content={
                "status": "error",
                "error": error_message
            },
            session_id=request.session_id,
            user_id=request.user_id,
            request_id=request.id
        )
    
    def _map_memory_type_to_category(self, memory_type: str) -> MemoryCategory:
        """
        Map a memory type string to a MemoryCategory
        
        Args:
            memory_type: Memory type string
            
        Returns:
            MemoryCategory: Corresponding memory category
            
        Raises:
            ValueError: If the memory type is unknown
        """
        # Map of memory types to categories
        type_map = {
            "general": MemoryCategory.GENERAL,
            "emotional": MemoryCategory.EMOTIONAL,
            "emotional_state": MemoryCategory.EMOTIONAL,
            "personal": MemoryCategory.PERSONAL,
            "profile": MemoryCategory.PERSONAL,
            "medical": MemoryCategory.MEDICAL,
            "health": MemoryCategory.MEDICAL,
            "therapeutic": MemoryCategory.THERAPEUTIC,
            "therapy": MemoryCategory.THERAPEUTIC,
            "system": MemoryCategory.SYSTEM,
            "session": MemoryCategory.SESSION,
            "conversation": MemoryCategory.SESSION
        }
        
        category = type_map.get(memory_type.lower())
        if not category:
            raise ValueError(f"Unknown memory type: {memory_type}")
        
        return category
    
    async def _handle_read(
        self,
        agent: str,
        memory_type: str,
        path: str,
        user_id: str,
        filters: Dict[str, Any]
    ) -> Any:
        """
        Handle a read operation
        
        Args:
            agent: Agent making the request
            memory_type: Type of memory to read
            path: Path within the memory
            user_id: User ID
            filters: Additional filters
            
        Returns:
            Any: The requested memory data
        """
        # Apply time scope filter if applicable
        time_filter = MemoryAccessPolicy.get_scope_time_filter(agent)
        if time_filter and "since" not in filters:
            filters["since"] = time_filter.isoformat()
        
        # Read from memory
        if memory_type == "emotional" or memory_type == "emotional_state":
            return await self._read_emotional_memory(user_id, path, filters)
        elif memory_type == "general":
            return await self._read_general_memory(user_id, agent, path, filters)
        elif memory_type == "session" or memory_type == "conversation":
            return await self._read_session_memory(user_id, path, filters)
        else:
            # For other types, use a generic approach
            return await self._read_generic_memory(memory_type, user_id, path, filters)
    
    async def _read_emotional_memory(
        self,
        user_id: str,
        path: str,
        filters: Dict[str, Any]
    ) -> Any:
        """
        Read emotional memory
        
        Args:
            user_id: User ID
            path: Path within the memory
            filters: Additional filters
            
        Returns:
            Any: The requested emotional memory data
        """
        # Parse time filter if present
        since = None
        if "since" in filters:
            since = datetime.fromisoformat(filters["since"])
        
        # Query for emotional data in summary logs
        query = select(SummaryLog).where(
            SummaryLog.user_id == user_id,
            SummaryLog.emotional_tone.isnot(None)
        ).order_by(SummaryLog.timestamp.desc())
        
        if since:
            query = query.where(SummaryLog.timestamp >= since)
        
        if "limit" in filters:
            query = query.limit(int(filters["limit"]))
        else:
            query = query.limit(10)  # Default limit
        
        result = await self.db.execute(query)
        summaries = result.scalars().all()
        
        # Extract emotional data
        emotional_data = [
            {
                "timestamp": s.timestamp.isoformat(),
                "emotional_tone": s.emotional_tone,
                "confidence": s.confidence,
                "summary": s.summary_text,
                "tags": s.tags
            }
            for s in summaries
        ]
        
        # Navigate to specific path if requested
        if path == "recent":
            return emotional_data[0] if emotional_data else None
        elif path == "history":
            return emotional_data
        elif path == "recent.emotional_tone" and emotional_data:
            return emotional_data[0]["emotional_tone"]
        else:
            # Default to returning all data
            return emotional_data
    
    async def _read_general_memory(
        self,
        user_id: str,
        agent: str,
        path: str,
        filters: Dict[str, Any]
    ) -> Any:
        """
        Read general memory
        
        Args:
            user_id: User ID
            agent: Agent making the request
            path: Path within the memory
            filters: Additional filters
            
        Returns:
            Any: The requested general memory data
        """
        # Query for the most recent memory snapshot
        query = select(MemorySnapshot).where(
            MemorySnapshot.user_id == user_id,
            MemorySnapshot.agent == agent
        ).order_by(MemorySnapshot.updated_at.desc()).limit(1)
        
        result = await self.db.execute(query)
        snapshot = result.scalars().first()
        
        if not snapshot:
            return None
        
        # Extract memory from snapshot
        memory = snapshot.summary_text
        
        # Navigate to specific path if requested
        if path == "all":
            return memory
        else:
            # Try to navigate path in memory
            try:
                import json
                memory_dict = json.loads(memory) if isinstance(memory, str) else memory
                parts = path.split('.')
                current = memory_dict
                for part in parts:
                    if part in current:
                        current = current[part]
                    else:
                        return None
                return current
            except (json.JSONDecodeError, AttributeError, KeyError):
                return None
    
    async def _read_session_memory(
        self,
        user_id: str,
        path: str,
        filters: Dict[str, Any]
    ) -> Any:
        """
        Read session memory
        
        Args:
            user_id: User ID
            path: Path within the memory
            filters: Additional filters
            
        Returns:
            Any: The requested session memory data
        """
        # TODO: Implement reading from session memory
        # For now, return a placeholder
        return {
            "messages": [
                {"role": "user", "content": "Hello"},
                {"role": "assistant", "content": "Hi there! How can I help you today?"}
            ],
            "topic": "general conversation",
            "session_id": "placeholder_session_id",
            "session_start": datetime.utcnow().isoformat()
        }
    
    async def _read_generic_memory(
        self,
        memory_type: str,
        user_id: str,
        path: str,
        filters: Dict[str, Any]
    ) -> Any:
        """
        Read from generic memory
        
        Args:
            memory_type: Type of memory
            user_id: User ID
            path: Path within the memory
            filters: Additional filters
            
        Returns:
            Any: The requested memory data
        """
        # TODO: Implement more specific memory types
        # For now, return a placeholder
        return {
            "type": memory_type,
            "user_id": user_id,
            "path": path,
            "note": "This is a placeholder for generic memory access"
        }
    
    async def _handle_write(
        self,
        agent: str,
        memory_type: str,
        path: str,
        user_id: str,
        data: Any
    ) -> Dict[str, Any]:
        """
        Handle a write operation
        
        Args:
            agent: Agent making the request
            memory_type: Type of memory to write
            path: Path within the memory
            user_id: User ID
            data: Data to write
            
        Returns:
            Dict[str, Any]: Status of the write operation
        """
        # TODO: Implement write operations for different memory types
        # For now, log the request and return success
        self.logger.info(
            f"Memory write request from {agent}",
            extra={
                "agent": agent,
                "memory_type": memory_type,
                "path": path,
                "user_id": user_id,
                "data": data
            }
        )
        
        return {
            "success": True,
            "memory_type": memory_type,
            "path": path
        }
    
    async def _handle_update(
        self,
        agent: str,
        memory_type: str,
        path: str,
        user_id: str,
        data: Any
    ) -> Dict[str, Any]:
        """
        Handle an update operation
        
        Args:
            agent: Agent making the request
            memory_type: Type of memory to update
            path: Path within the memory
            user_id: User ID
            data: Data to update with
            
        Returns:
            Dict[str, Any]: Status of the update operation
        """
        # TODO: Implement update operations for different memory types
        # For now, log the request and return success
        self.logger.info(
            f"Memory update request from {agent}",
            extra={
                "agent": agent,
                "memory_type": memory_type,
                "path": path,
                "user_id": user_id,
                "data": data
            }
        )
        
        return {
            "success": True,
            "memory_type": memory_type,
            "path": path
        }
    
    async def _handle_delete(
        self,
        agent: str,
        memory_type: str,
        path: str,
        user_id: str
    ) -> Dict[str, Any]:
        """
        Handle a delete operation
        
        Args:
            agent: Agent making the request
            memory_type: Type of memory to delete
            path: Path within the memory
            user_id: User ID
            
        Returns:
            Dict[str, Any]: Status of the delete operation
        """
        # TODO: Implement delete operations for different memory types
        # For now, log the request and return success
        self.logger.info(
            f"Memory delete request from {agent}",
            extra={
                "agent": agent,
                "memory_type": memory_type,
                "path": path,
                "user_id": user_id
            }
        )
        
        return {
            "success": True,
            "memory_type": memory_type,
            "path": path
        }