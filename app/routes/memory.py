"""
Memory API endpoints

This module provides API endpoints for creating, reading, updating, and deleting memory.
"""

from datetime import datetime
from typing import Dict, List, Optional, Any, Union
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Body
from pydantic import BaseModel, Field, validator
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.database import get_db
from app.get_api_key import get_api_key
from app.models import MemorySnapshot, SummaryLog, User
from app.logging_config import get_logger

logger = get_logger(__name__)

router = APIRouter()

# ----------------------------- Pydantic Models -----------------------------

class MemoryCreateRequest(BaseModel):
    """Request model for creating new memory"""
    user_id: str = Field(..., description="User's unique identifier")
    agent: str = Field(..., description="Agent creating the memory")
    memory_type: str = Field("general", description="Type of memory (general, emotional, etc.)")
    content: Dict[str, Any] = Field(..., description="Memory content")
    
    class Config:
        schema_extra = {
            "example": {
                "user_id": "user123",
                "agent": "Therapist",
                "memory_type": "general",
                "content": {
                    "topics": ["anxiety", "work stress"],
                    "key_insights": ["User feels overwhelmed at work", "Stress affects sleep quality"],
                    "recommendations": ["Practice mindfulness techniques", "Consider work-life boundaries"]
                }
            }
        }

class MemoryUpdateRequest(BaseModel):
    """Request model for updating memory"""
    user_id: str = Field(..., description="User's unique identifier")
    agent: str = Field(..., description="Agent updating the memory")
    memory_type: str = Field("general", description="Type of memory to update")
    path: str = Field(..., description="Path to the memory to update (e.g. 'topics[0]')")
    content: Any = Field(..., description="New content for the specified path")
    
    class Config:
        schema_extra = {
            "example": {
                "user_id": "user123",
                "agent": "Therapist",
                "memory_type": "general",
                "path": "recommendations",
                "content": ["Practice deep breathing exercises", "Set firm boundaries at work"]
            }
        }

class EmotionalMemory(BaseModel):
    """Model for emotional memory entry"""
    emotional_tone: str = Field(..., description="Primary emotional tone")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence in the emotional assessment")
    summary: str = Field(..., description="Summary text related to this emotional state")
    tags: List[str] = Field(default_factory=list, description="Tags for categorization")
    timestamp: str = Field(..., description="When this emotional state was recorded")
    
    class Config:
        schema_extra = {
            "example": {
                "emotional_tone": "anxiety",
                "confidence": 0.85,
                "summary": "User expressed feelings of anxiety about upcoming job interview",
                "tags": ["anxiety", "work", "interview"],
                "timestamp": "2023-05-05T10:30:00.000Z"
            }
        }

class EmotionalMemoryCreateRequest(BaseModel):
    """Request model for creating emotional memory"""
    user_id: str = Field(..., description="User's unique identifier")
    agent: str = Field(..., description="Agent creating the memory")
    emotional_tone: str = Field(..., description="Primary emotional tone detected")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence in the emotional assessment")
    summary_text: str = Field(..., description="Summary related to the emotional state")
    tags: List[str] = Field(default_factory=list, description="Tags for categorization")
    
    class Config:
        schema_extra = {
            "example": {
                "user_id": "user123",
                "agent": "Therapist",
                "emotional_tone": "anxiety",
                "confidence": 0.85,
                "summary_text": "User expressed feelings of anxiety about upcoming job interview",
                "tags": ["anxiety", "work", "interview"]
            }
        }

class MemoryResponse(BaseModel):
    """Standard memory response model"""
    status: str = Field(..., description="Status of the request (ok, error)")
    message: Optional[str] = Field(None, description="Response message")
    data: Optional[Dict[str, Any]] = Field(None, description="Response data")
    
    class Config:
        schema_extra = {
            "example": {
                "status": "ok",
                "message": "Memory created successfully",
                "data": {
                    "memory_id": "mem_123456789",
                    "timestamp": "2023-05-05T10:30:00.000Z"
                }
            }
        }

# ----------------------------- Endpoints -----------------------------

@router.get("/ping")
async def ping_memory(api_key: str = Depends(get_api_key)):
    """Health check endpoint for the memory service"""
    return {"message": "Memory API is active"}

@router.post("/create", response_model=MemoryResponse, 
            summary="Create Memory",
            description="Create a new memory entry for a user")
async def create_memory(
    request: MemoryCreateRequest,
    db: AsyncSession = Depends(get_db),
    api_key: str = Depends(get_api_key)
):
    """
    Create a new memory entry
    
    Creates a new memory snapshot for the specified user and agent.
    The memory content is stored as JSON.
    """
    try:
        # Verify user exists
        user = await db.get(User, request.user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Create memory snapshot
        memory_id = str(uuid4())
        timestamp = datetime.utcnow()
        
        import json
        memory_content = json.dumps(request.content)
        
        memory = MemorySnapshot(
            id=memory_id,
            user_id=request.user_id,
            agent=request.agent,
            memory_type=request.memory_type,
            summary_text=memory_content,
            created_at=timestamp,
            updated_at=timestamp
        )
        
        db.add(memory)
        await db.commit()
        
        logger.info(
            f"Created memory for user {request.user_id}",
            extra={
                "user_id": request.user_id,
                "agent": request.agent,
                "memory_type": request.memory_type,
                "memory_id": memory_id
            }
        )
        
        return MemoryResponse(
            status="ok",
            message="Memory created successfully",
            data={
                "memory_id": memory_id,
                "timestamp": timestamp.isoformat()
            }
        )
        
    except Exception as e:
        logger.error(
            f"Error creating memory: {str(e)}",
            extra={
                "user_id": request.user_id,
                "agent": request.agent,
                "memory_type": request.memory_type
            },
            exc_info=True
        )
        
        if isinstance(e, HTTPException):
            raise e
        
        raise HTTPException(status_code=500, detail=f"Error creating memory: {str(e)}")

@router.get("/get/{user_id}", response_model=MemoryResponse,
          summary="Get Memory",
          description="Get a user's memory for a specific agent")
async def get_memory(
    user_id: str = Path(..., description="User's unique identifier"),
    agent: str = Query(..., description="Agent name"),
    memory_type: str = Query("general", description="Type of memory to retrieve"),
    db: AsyncSession = Depends(get_db),
    api_key: str = Depends(get_api_key)
):
    """
    Get a user's memory
    
    Retrieves the most recent memory snapshot for the specified user and agent.
    """
    try:
        # Verify user exists
        user = await db.get(User, user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Get memory snapshot
        query = select(MemorySnapshot).where(
            MemorySnapshot.user_id == user_id,
            MemorySnapshot.agent == agent,
            MemorySnapshot.memory_type == memory_type
        ).order_by(MemorySnapshot.updated_at.desc()).limit(1)
        
        result = await db.execute(query)
        memory = result.scalars().first()
        
        if not memory:
            return MemoryResponse(
                status="ok",
                message=f"No {memory_type} memory found for user {user_id} and agent {agent}",
                data={
                    "memory": None
                }
            )
        
        # Parse memory content
        try:
            import json
            memory_content = json.loads(memory.summary_text)
        except json.JSONDecodeError:
            memory_content = memory.summary_text
        
        return MemoryResponse(
            status="ok",
            data={
                "memory_id": memory.id,
                "memory_type": memory.memory_type,
                "agent": memory.agent,
                "created_at": memory.created_at.isoformat(),
                "updated_at": memory.updated_at.isoformat(),
                "content": memory_content
            }
        )
        
    except Exception as e:
        logger.error(
            f"Error getting memory: {str(e)}",
            extra={
                "user_id": user_id,
                "agent": agent,
                "memory_type": memory_type
            },
            exc_info=True
        )
        
        if isinstance(e, HTTPException):
            raise e
        
        raise HTTPException(status_code=500, detail=f"Error getting memory: {str(e)}")

@router.post("/update", response_model=MemoryResponse,
            summary="Update Memory",
            description="Update a user's memory at a specific path")
async def update_memory(
    request: MemoryUpdateRequest,
    db: AsyncSession = Depends(get_db),
    api_key: str = Depends(get_api_key)
):
    """
    Update a user's memory
    
    Updates a specific path in the user's memory.
    Creates a new memory if none exists.
    """
    try:
        # Verify user exists
        user = await db.get(User, request.user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Get memory snapshot
        query = select(MemorySnapshot).where(
            MemorySnapshot.user_id == request.user_id,
            MemorySnapshot.agent == request.agent,
            MemorySnapshot.memory_type == request.memory_type
        ).order_by(MemorySnapshot.updated_at.desc()).limit(1)
        
        result = await db.execute(query)
        memory = result.scalars().first()
        
        timestamp = datetime.utcnow()
        
        if not memory:
            # Create new memory if none exists
            memory_id = str(uuid4())
            import json
            memory_content = {request.path: request.content}
            memory_json = json.dumps(memory_content)
            
            memory = MemorySnapshot(
                id=memory_id,
                user_id=request.user_id,
                agent=request.agent,
                memory_type=request.memory_type,
                summary_text=memory_json,
                created_at=timestamp,
                updated_at=timestamp
            )
            
            db.add(memory)
            await db.commit()
            
            logger.info(
                f"Created new memory during update for user {request.user_id}",
                extra={
                    "user_id": request.user_id,
                    "agent": request.agent,
                    "memory_type": request.memory_type,
                    "memory_id": memory_id,
                    "path": request.path
                }
            )
            
            return MemoryResponse(
                status="ok",
                message="New memory created with the updated content",
                data={
                    "memory_id": memory_id,
                    "timestamp": timestamp.isoformat(),
                    "operation": "create"
                }
            )
        
        # Update existing memory
        try:
            import json
            memory_content = json.loads(memory.summary_text)
        except json.JSONDecodeError:
            memory_content = {}
        
        # Update path
        # For simplicity, we're just replacing at the top level
        # A more advanced implementation could handle nested paths like 'topics[0]'
        memory_content[request.path] = request.content
        
        # Update memory
        memory.summary_text = json.dumps(memory_content)
        memory.updated_at = timestamp
        
        await db.commit()
        
        logger.info(
            f"Updated memory for user {request.user_id}",
            extra={
                "user_id": request.user_id,
                "agent": request.agent,
                "memory_type": request.memory_type,
                "memory_id": memory.id,
                "path": request.path
            }
        )
        
        return MemoryResponse(
            status="ok",
            message="Memory updated successfully",
            data={
                "memory_id": memory.id,
                "timestamp": timestamp.isoformat(),
                "operation": "update"
            }
        )
        
    except Exception as e:
        logger.error(
            f"Error updating memory: {str(e)}",
            extra={
                "user_id": request.user_id,
                "agent": request.agent,
                "memory_type": request.memory_type,
                "path": request.path
            },
            exc_info=True
        )
        
        if isinstance(e, HTTPException):
            raise e
        
        raise HTTPException(status_code=500, detail=f"Error updating memory: {str(e)}")

@router.post("/emotional", response_model=MemoryResponse,
            summary="Create Emotional Memory",
            description="Create an emotional memory entry for a user")
async def create_emotional_memory(
    request: EmotionalMemoryCreateRequest,
    db: AsyncSession = Depends(get_db),
    api_key: str = Depends(get_api_key)
):
    """
    Create an emotional memory entry
    
    Creates a new emotional memory entry for the specified user.
    Emotional memories are stored as SummaryLog entries with emotional_tone set.
    """
    try:
        # Verify user exists
        user = await db.get(User, request.user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Create summary log for emotional memory
        memory_id = str(uuid4())
        timestamp = datetime.utcnow()
        
        summary = SummaryLog(
            id=memory_id,
            user_id=request.user_id,
            agent=request.agent,
            summary_text=request.summary_text,
            emotional_tone=request.emotional_tone,
            confidence=request.confidence,
            tags=request.tags,
            timestamp=timestamp
        )
        
        db.add(summary)
        await db.commit()
        
        logger.info(
            f"Created emotional memory for user {request.user_id}",
            extra={
                "user_id": request.user_id,
                "agent": request.agent,
                "emotional_tone": request.emotional_tone,
                "memory_id": memory_id
            }
        )
        
        return MemoryResponse(
            status="ok",
            message="Emotional memory created successfully",
            data={
                "memory_id": memory_id,
                "timestamp": timestamp.isoformat()
            }
        )
        
    except Exception as e:
        logger.error(
            f"Error creating emotional memory: {str(e)}",
            extra={
                "user_id": request.user_id,
                "agent": request.agent,
                "emotional_tone": request.emotional_tone
            },
            exc_info=True
        )
        
        if isinstance(e, HTTPException):
            raise e
        
        raise HTTPException(status_code=500, detail=f"Error creating emotional memory: {str(e)}")

@router.get("/emotional/{user_id}", response_model=MemoryResponse,
          summary="Get Emotional Memory",
          description="Get a user's emotional memory history")
async def get_emotional_memory(
    user_id: str = Path(..., description="User's unique identifier"),
    agent: Optional[str] = Query(None, description="Filter by agent (optional)"),
    limit: int = Query(10, description="Maximum number of entries to return"),
    db: AsyncSession = Depends(get_db),
    api_key: str = Depends(get_api_key)
):
    """
    Get a user's emotional memory
    
    Retrieves the user's emotional memory history.
    Returns a list of emotional memory entries, ordered by most recent first.
    """
    try:
        # Verify user exists
        user = await db.get(User, user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Query for emotional summaries
        query = select(SummaryLog).where(
            SummaryLog.user_id == user_id,
            SummaryLog.emotional_tone.isnot(None)
        ).order_by(SummaryLog.timestamp.desc()).limit(limit)
        
        if agent:
            query = query.where(SummaryLog.agent == agent)
        
        result = await db.execute(query)
        summaries = result.scalars().all()
        
        if not summaries:
            return MemoryResponse(
                status="ok",
                message=f"No emotional memory found for user {user_id}",
                data={
                    "memories": []
                }
            )
        
        # Format emotional memories
        emotional_memories = [
            {
                "id": s.id,
                "emotional_tone": s.emotional_tone,
                "confidence": s.confidence,
                "summary": s.summary_text,
                "tags": s.tags,
                "timestamp": s.timestamp.isoformat(),
                "agent": s.agent
            }
            for s in summaries
        ]
        
        return MemoryResponse(
            status="ok",
            data={
                "memories": emotional_memories
            }
        )
        
    except Exception as e:
        logger.error(
            f"Error getting emotional memory: {str(e)}",
            extra={
                "user_id": user_id,
                "agent": agent
            },
            exc_info=True
        )
        
        if isinstance(e, HTTPException):
            raise e
        
        raise HTTPException(status_code=500, detail=f"Error getting emotional memory: {str(e)}")

@router.delete("/{memory_id}", response_model=MemoryResponse,
             summary="Delete Memory",
             description="Delete a specific memory entry")
async def delete_memory(
    memory_id: str = Path(..., description="ID of the memory to delete"),
    memory_type: str = Query("general", description="Type of memory to delete (general or emotional)"),
    db: AsyncSession = Depends(get_db),
    api_key: str = Depends(get_api_key)
):
    """
    Delete a memory entry
    
    Deletes a specific memory entry by ID.
    The memory type parameter determines which memory store to delete from.
    """
    try:
        if memory_type == "emotional":
            # Delete from SummaryLog
            memory = await db.get(SummaryLog, memory_id)
            if not memory:
                raise HTTPException(status_code=404, detail="Emotional memory not found")
            
            user_id = memory.user_id
            await db.delete(memory)
            
        else:
            # Delete from MemorySnapshot
            memory = await db.get(MemorySnapshot, memory_id)
            if not memory:
                raise HTTPException(status_code=404, detail="Memory not found")
            
            user_id = memory.user_id
            await db.delete(memory)
        
        await db.commit()
        
        logger.info(
            f"Deleted {memory_type} memory {memory_id}",
            extra={
                "memory_id": memory_id,
                "memory_type": memory_type,
                "user_id": user_id
            }
        )
        
        return MemoryResponse(
            status="ok",
            message=f"{memory_type.capitalize()} memory deleted successfully"
        )
        
    except Exception as e:
        logger.error(
            f"Error deleting memory: {str(e)}",
            extra={
                "memory_id": memory_id,
                "memory_type": memory_type
            },
            exc_info=True
        )
        
        if isinstance(e, HTTPException):
            raise e
        
        raise HTTPException(status_code=500, detail=f"Error deleting memory: {str(e)}")