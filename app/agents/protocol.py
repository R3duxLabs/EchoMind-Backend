"""
Agent Communication Protocol

This module defines the standard protocol for agent communication in the EchoMind system.
It includes message structures, request/response formats, and serialization methods.
"""

from enum import Enum
from typing import Dict, List, Optional, Any, Union
from datetime import datetime
from pydantic import BaseModel, Field, validator

# Agent communication message types
class MessageType(str, Enum):
    """Types of messages that can be exchanged between agents"""
    QUERY = "query"                # Request for information
    RESPONSE = "response"          # Response to a query
    HANDOFF = "handoff"            # Transfer control to another agent
    MEMORY_ACCESS = "memory_access"  # Memory access request/response
    SYSTEM = "system"              # System message (not from user)
    USER = "user"                  # Message from user
    ASSISTANT = "assistant"        # Message from assistant/agent

class MessagePriority(str, Enum):
    """Priority levels for agent messages"""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"

class EmotionalState(BaseModel):
    """Representation of an emotional state within the system"""
    primary: str = Field(..., description="Primary emotion detected")
    intensity: float = Field(..., ge=0.0, le=1.0, description="Intensity of emotion (0-1)")
    secondary: Optional[List[Dict[str, float]]] = Field(None, description="Secondary emotions with intensities")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence in emotion detection (0-1)")
    
    class Config:
        schema_extra = {
            "example": {
                "primary": "joy",
                "intensity": 0.8,
                "secondary": [
                    {"sadness": 0.2},
                    {"surprise": 0.4}
                ],
                "confidence": 0.9
            }
        }

class AgentCapability(str, Enum):
    """Capabilities that agents can advertise and request"""
    EMOTIONAL_SUPPORT = "emotional_support"
    PARENTING_ADVICE = "parenting_advice"
    CONFLICT_RESOLUTION = "conflict_resolution"
    GOAL_SETTING = "goal_setting"
    COGNITIVE_REFRAMING = "cognitive_reframing"
    THERAPY = "therapy"
    COACHING = "coaching"
    FRIENDSHIP = "friendship"
    BRIDGING = "bridging"

class AgentMessage(BaseModel):
    """
    Standard message format for agent communication
    All messages between agents must follow this format
    """
    id: str = Field(..., description="Unique message identifier")
    type: MessageType = Field(..., description="Type of message")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="When the message was created")
    sender: str = Field(..., description="Agent or component that sent the message")
    recipient: str = Field(..., description="Intended recipient agent")
    content: Dict[str, Any] = Field(..., description="Message content")
    session_id: str = Field(..., description="Session this message belongs to")
    user_id: str = Field(..., description="User this message belongs to")
    request_id: Optional[str] = Field(None, description="Request ID if this message is part of a request/response pair")
    priority: MessagePriority = Field(default=MessagePriority.NORMAL, description="Message priority")
    requires_response: bool = Field(default=False, description="Whether this message requires a response")
    ttl: Optional[int] = Field(None, description="Time to live in seconds (for expiring messages)")
    
    class Config:
        schema_extra = {
            "example": {
                "id": "msg_123456789",
                "type": "query",
                "timestamp": "2023-05-05T10:30:00.000Z",
                "sender": "EchoMind",
                "recipient": "Elora",
                "content": {
                    "query": "how is user feeling",
                    "context": {"recent_messages": 5}
                },
                "session_id": "session_987654321",
                "user_id": "user_12345",
                "request_id": "req_123456789",
                "priority": "normal",
                "requires_response": True,
                "ttl": 30
            }
        }

class MemoryAccessRequest(BaseModel):
    """Request to access or modify agent memory"""
    operation: str = Field(..., description="Operation to perform (read, write, update, delete)")
    memory_type: str = Field(..., description="Type of memory to access")
    path: str = Field(..., description="Path/key to the memory")
    data: Optional[Any] = Field(None, description="Data for write/update operations")
    filters: Optional[Dict[str, Any]] = Field(None, description="Filters for read operations")
    
    class Config:
        schema_extra = {
            "example": {
                "operation": "read",
                "memory_type": "emotional_state",
                "path": "recent.primary",
                "filters": {"since": "2023-05-01T00:00:00Z"}
            }
        }

class AgentHandoff(BaseModel):
    """Data model for handing off a conversation to another agent"""
    target_agent: str = Field(..., description="Agent to hand off to")
    reason: str = Field(..., description="Reason for the handoff")
    context: Dict[str, Any] = Field(..., description="Context to provide to the new agent")
    conversation_state: Dict[str, Any] = Field(..., description="Current state of the conversation")
    suggested_response: Optional[str] = Field(None, description="Suggested response for the new agent")
    emotional_state: Optional[EmotionalState] = Field(None, description="Current emotional state assessment")
    urgency: MessagePriority = Field(default=MessagePriority.NORMAL, description="Urgency of the handoff")
    
    class Config:
        schema_extra = {
            "example": {
                "target_agent": "Therapist",
                "reason": "User showing signs of distress that require therapeutic approach",
                "context": {
                    "recent_topic": "childhood trauma",
                    "session_duration": 15
                },
                "conversation_state": {
                    "last_user_message": "I can't stop thinking about what happened",
                    "topic_history": ["family", "childhood", "trauma"]
                },
                "suggested_response": "I understand this is difficult to talk about. Would it help to explore how these memories are affecting you now?",
                "emotional_state": {
                    "primary": "distress",
                    "intensity": 0.7,
                    "secondary": [{"fear": 0.5}, {"sadness": 0.6}],
                    "confidence": 0.8
                },
                "urgency": "high"
            }
        }

class AgentThought(BaseModel):
    """Internal thought process of an agent, not shown to the user"""
    reasoning: str = Field(..., description="Agent's reasoning process")
    observations: List[str] = Field(..., description="Observations about the conversation or user")
    emotional_assessment: Optional[EmotionalState] = Field(None, description="Assessment of user's emotional state")
    next_steps: List[str] = Field(..., description="Potential next steps")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence in this assessment")
    
    class Config:
        schema_extra = {
            "example": {
                "reasoning": "User's short responses and mentions of avoiding social situations suggest possible anxiety",
                "observations": [
                    "User gives brief answers",
                    "User mentioned cancelling plans twice",
                    "User uses qualifiers like 'I guess' and 'maybe'"
                ],
                "emotional_assessment": {
                    "primary": "anxiety",
                    "intensity": 0.6,
                    "secondary": [{"sadness": 0.3}],
                    "confidence": 0.7
                },
                "next_steps": [
                    "Explore reasons for social withdrawal",
                    "Ask about physical symptoms of anxiety",
                    "Consider suggesting relaxation techniques"
                ],
                "confidence": 0.75
            }
        }

# Protocol utility functions
def create_message(
    message_type: MessageType,
    sender: str,
    recipient: str,
    content: Dict[str, Any],
    session_id: str,
    user_id: str,
    **kwargs
) -> AgentMessage:
    """
    Create a new agent message
    
    Args:
        message_type: Type of message
        sender: Agent or component sending the message
        recipient: Intended recipient agent
        content: Message content
        session_id: Session identifier
        user_id: User identifier
        **kwargs: Additional message properties
        
    Returns:
        AgentMessage: Properly formatted agent message
    """
    from uuid import uuid4
    
    # Generate IDs if not provided
    if 'id' not in kwargs:
        kwargs['id'] = f"msg_{uuid4()}"
    
    if 'request_id' not in kwargs and message_type == MessageType.RESPONSE:
        # For responses, a request_id should be provided
        raise ValueError("request_id is required for response messages")
    
    # Create the message
    return AgentMessage(
        type=message_type,
        sender=sender,
        recipient=recipient,
        content=content,
        session_id=session_id,
        user_id=user_id,
        **kwargs
    )

def create_handoff_message(
    sender: str,
    target_agent: str,
    reason: str,
    context: Dict[str, Any],
    conversation_state: Dict[str, Any],
    session_id: str,
    user_id: str,
    **kwargs
) -> AgentMessage:
    """
    Create a handoff message to transfer control to another agent
    
    Args:
        sender: Agent sending the handoff
        target_agent: Agent to hand off to
        reason: Reason for the handoff
        context: Context information for the new agent
        conversation_state: Current state of the conversation
        session_id: Session identifier
        user_id: User identifier
        **kwargs: Additional message properties
        
    Returns:
        AgentMessage: Properly formatted handoff message
    """
    handoff = AgentHandoff(
        target_agent=target_agent,
        reason=reason,
        context=context,
        conversation_state=conversation_state,
        **{k: v for k, v in kwargs.items() if k in AgentHandoff.__fields__}
    )
    
    return create_message(
        message_type=MessageType.HANDOFF,
        sender=sender,
        recipient=target_agent,
        content=handoff.dict(),
        session_id=session_id,
        user_id=user_id,
        priority=kwargs.get('priority', MessagePriority.HIGH),
        **{k: v for k, v in kwargs.items() if k not in AgentHandoff.__fields__}
    )

def create_memory_request(
    sender: str,
    operation: str,
    memory_type: str,
    path: str,
    session_id: str,
    user_id: str,
    data: Any = None,
    filters: Dict[str, Any] = None,
    **kwargs
) -> AgentMessage:
    """
    Create a memory access request message
    
    Args:
        sender: Agent or component sending the request
        operation: Operation to perform (read, write, update, delete)
        memory_type: Type of memory to access
        path: Path/key to the memory
        session_id: Session identifier
        user_id: User identifier
        data: Data for write/update operations
        filters: Filters for read operations
        **kwargs: Additional message properties
        
    Returns:
        AgentMessage: Properly formatted memory access request
    """
    memory_request = MemoryAccessRequest(
        operation=operation,
        memory_type=memory_type,
        path=path,
        data=data,
        filters=filters
    )
    
    return create_message(
        message_type=MessageType.MEMORY_ACCESS,
        sender=sender,
        # Memory requests always go to the Memory Service
        recipient="MemoryService",
        content=memory_request.dict(),
        session_id=session_id,
        user_id=user_id,
        requires_response=True,
        **kwargs
    )