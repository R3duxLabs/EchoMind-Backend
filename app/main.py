import json
import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any

from fastapi import Depends, FastAPI, HTTPException, Response, status
from pydantic import BaseModel, Field, validator
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.database import get_db
from app.get_api_key import get_api_key, APIKeyHeader
from app.models import MemorySnapshot, SessionLog, SummaryLog, User, MilestoneLog

# Configure logging
logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

app = FastAPI(
    title="EchoMind API",
    description="API for managing user memory, sessions, and summaries",
    version="2.0.0"
)

# ----------------------------- Pydantic Schemas -----------------------------

class MemoryUpdate(BaseModel):
    user_id: str = Field(..., description="User's unique identifier")
    agent: str = Field(..., description="Agent handling the interaction")
    memory: Dict[str, Any] = Field(..., description="Memory data structure")
    summary: Optional[str] = Field(None, description="Optional summary text")
    tags: List[str] = Field(default_factory=list, description="Tags for categorization")
    emotional_tone: Optional[str] = Field(None, description="Detected emotional tone")
    confidence: Optional[float] = Field(None, ge=0.0, le=1.0, description="Confidence score (0-1)")

    @validator('confidence')
    def validate_confidence(cls, v):
        if v is not None and (v < 0.0 or v > 1.0):
            raise ValueError('Confidence must be between 0 and 1')
        return v

class MemoryRequest(BaseModel):
    user_id: str = Field(..., description="User's unique identifier")
    agent: str = Field(..., description="Agent to retrieve memory for")

class AgentSwitchLog(BaseModel):
    user_id: str = Field(..., description="User's unique identifier")
    from_agent: str = Field(..., description="Original agent")
    to_agent: str = Field(..., description="New agent")
    reason: Optional[str] = Field(None, description="Reason for the switch")
    timestamp: Optional[str] = Field(None, description="Timestamp of the switch")

class SettingsInput(BaseModel):
    user_id: str = Field(..., description="User's unique identifier")
    therapist_name: Optional[str] = Field(None, description="Preferred therapist name")
    tone_preference: Optional[str] = Field(None, description="Preferred conversation tone")
    pacing_preference: Optional[str] = Field(None, description="Preferred session pacing")
    media_preference: List[str] = Field(default_factory=list, description="Preferred media types")
    learning_style: Optional[str] = Field(None, description="User's learning style")

class LogSessionInput(BaseModel):
    user_id: str = Field(..., description="User's unique identifier")
    agent: str = Field("EchoMind", description="Agent handling the session")
    message: str = Field(..., description="User's message")
    response: str = Field(..., description="System's response")
    tags: List[str] = Field(default_factory=list, description="Session tags")
    emotional_tone: Optional[str] = Field(None, description="Detected emotional tone")
    confidence: Optional[float] = Field(None, ge=0.0, le=1.0, description="Confidence score")

class MilestoneInput(BaseModel):
    user_id: str = Field(..., description="User's unique identifier")
    agent: str = Field("EchoMind", description="Agent recording the milestone")
    type: str = Field(..., description="Type of milestone")
    description: str = Field(..., description="Milestone description")

class APIResponse(BaseModel):
    status: str
    message: Optional[str] = None
    data: Optional[Dict[str, Any]] = None

# ----------------------------- Error Handling -----------------------------

class APIException(Exception):
    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail

@app.exception_handler(APIException)
async def api_exception_handler(request, exc):
    return Response(
        status_code=exc.status_code,
        content=json.dumps({"status": "error", "message": exc.detail}),
        media_type="application/json"
    )

# ----------------------------- Middleware -----------------------------

@app.middleware("http")
async def logging_middleware(request, call_next):
    start_time = datetime.utcnow()
    try:
        response = await call_next(request)
        process_time = datetime.utcnow() - start_time
        logger.info(
            f"Request: {request.method} {request.url.path} - Status: {response.status_code} - "
            f"Duration: {process_time.total_seconds():.3f}s"
        )
        return response
    except Exception as e:
        logger.error(f"Request failed: {request.method} {request.url.path} - Error: {str(e)}")
        raise

# ----------------------------- Routes -----------------------------

@app.get("/", response_model=APIResponse)
async def root():
    """Health check endpoint"""
    return APIResponse(status="ok", message="EchoMind API is live")

@app.post("/get-memory", response_model=APIResponse)
async def get_memory(
    request: MemoryRequest, 
    db: AsyncSession = Depends(get_db), 
    api_key: str = Depends(APIKeyHeader)
):
    """Retrieve memory for a specific user and agent"""
    try:
        user = await db.get(User, request.user_id)
        if not user:
            raise APIException(status_code=404, detail="User not found")

        # Get memory snapshot for the specific agent
        snapshot = await db.execute(
            select(MemorySnapshot)
            .where(MemorySnapshot.user_id == request.user_id, MemorySnapshot.agent == request.agent)
            .order_by(MemorySnapshot.updated_at.desc())
        )
        memory_snapshot = snapshot.scalars().first()

        # If no memory for this agent, get most recent memory from any agent
        if not memory_snapshot:
            fallback = await db.execute(
                select(MemorySnapshot)
                .where(MemorySnapshot.user_id == request.user_id)
                .order_by(MemorySnapshot.updated_at.desc())
            )
            memory_snapshot = fallback.scalars().first()

        agent_memory = memory_snapshot.summary_text if memory_snapshot else "No previous sessions found. Let's begin fresh."

        # Try to parse JSON if it's stored as a string
        try:
            agent_memory = json.loads(agent_memory) if isinstance(agent_memory, str) and agent_memory.strip().startswith("{") else agent_memory
        except json.JSONDecodeError:
            # If not valid JSON, keep as is
            pass

        # Get recent summaries
        summary_data = await db.execute(
            select(SummaryLog)
            .where(SummaryLog.user_id == request.user_id, SummaryLog.agent == request.agent)
            .order_by(SummaryLog.timestamp.desc())
            .limit(10)
        )

        summaries = [
            {
                "id": s.id,
                "summary": s.summary_text,
                "tags": s.tags,
                "emotional_tone": s.emotional_tone,
                "confidence": s.confidence,
                "timestamp": s.timestamp.isoformat()
            }
            for s in summary_data.scalars()
        ] or [{"summary": "No summaries found yet. You're starting fresh.", "tags": [], "emotional_tone": None, "confidence": None, "timestamp": None}]

        return APIResponse(
            status="ok", 
            data={
                "agent_memory": agent_memory, 
                "latest_summaries": summaries
            }
        )
    except APIException as e:
        raise e
    except Exception as e:
        logger.error(f"Error in get_memory: {str(e)}", exc_info=True)
        raise APIException(status_code=500, detail=f"Internal server error: {str(e)}")

@app.get("/get-shared-summary", response_model=APIResponse)
async def get_shared_summary(
    user_id: str, 
    db: AsyncSession = Depends(get_db), 
    api_key: str = Depends(APIKeyHeader)
):
    """Get the most recent shared memory summary for a user"""
    try:
        user = await db.get(User, user_id)
        if not user:
            raise APIException(status_code=404, detail="User not found")

        shared = await db.execute(
            select(MemorySnapshot)
            .where(MemorySnapshot.user_id == user_id)
            .order_by(MemorySnapshot.updated_at.desc())
            .limit(1)
        )
        latest = shared.scalars().first()

        summary = latest.summary_text if latest else "No memory available yet."

        # Try to parse JSON if it's stored as a string
        try:
            if isinstance(summary, str) and summary.strip().startswith("{"):
                summary = json.loads(summary)
        except json.JSONDecodeError:
            # If not valid JSON, keep as is
            pass

        return APIResponse(status="ok", data={"shared_summary": summary})
    except APIException as e:
        raise e
    except Exception as e:
        logger.error(f"Error in get_shared_summary: {str(e)}", exc_info=True)
        raise APIException(status_code=500, detail=f"Internal server error: {str(e)}")

@app.post("/update-memory", response_model=APIResponse)
async def update_memory(
    data: MemoryUpdate, 
    db: AsyncSession = Depends(get_db), 
    api_key: str = Depends(APIKeyHeader)
):
    """Update memory for a specific user and agent"""
    async with db.begin():
        try:
            user = await db.get(User, data.user_id)
            if not user:
                raise APIException(status_code=404, detail="User not found")

            # Find existing memory snapshot
            snapshot_query = await db.execute(
                select(MemorySnapshot)
                .where(MemorySnapshot.user_id == data.user_id, MemorySnapshot.agent == data.agent)
            )
            existing = snapshot_query.scalars().first()

            # Convert memory dict to JSON string
            memory_str = json.dumps(data.memory, ensure_ascii=False, indent=2)

            # Update or create memory snapshot
            timestamp = datetime.utcnow()
            if existing:
                existing.summary_text = memory_str
                existing.updated_at = timestamp
            else:
                new_snapshot = MemorySnapshot(
                    id=str(uuid.uuid4()),
                    user_id=data.user_id,
                    agent=data.agent,
                    summary_text=memory_str,
                    created_at=timestamp,
                    updated_at=timestamp
                )
                db.add(new_snapshot)

            # Add summary log if provided
            if data.summary:
                summary_log = SummaryLog(
                    id=str(uuid.uuid4()),
                    user_id=data.user_id,
                    agent=data.agent,
                    summary_text=data.summary,
                    tags=data.tags or [],
                    emotional_tone=data.emotional_tone,
                    confidence=data.confidence,
                    timestamp=timestamp
                )
                db.add(summary_log)

            # Log the memory update event
            session_log = SessionLog(
                id=str(uuid.uuid4()),
                user_id=data.user_id,
                session_data={"event": "memory_updated", "timestamp": timestamp.isoformat()},
                agent=data.agent,
                timestamp=timestamp
            )
            db.add(session_log)

            return APIResponse(status="ok", message="Memory updated successfully")
        except APIException as e:
            raise e
        except Exception as e:
            logger.error(f"Error updating memory for user {data.user_id}: {str(e)}", exc_info=True)
            raise APIException(status_code=500, detail=f"Internal server error: {str(e)}")

@app.post("/log-session", response_model=APIResponse)
async def log_session(
    data: LogSessionInput, 
    db: AsyncSession = Depends(get_db), 
    api_key: str = Depends(APIKeyHeader)
):
    """Log a new session interaction"""
    async with db.begin():
        try:
            user = await db.get(User, data.user_id)
            if not user:
                raise APIException(status_code=404, detail="User not found")

            timestamp = datetime.utcnow()
            session_log = SessionLog(
                id=str(uuid.uuid4()),
                user_id=data.user_id,
                agent=data.agent,
                session_data={
                    "message": data.message,
                    "response": data.response,
                    "tags": data.tags,
                    "emotional_tone": data.emotional_tone,
                    "confidence": data.confidence
                },
                timestamp=timestamp
            )
            db.add(session_log)

            return APIResponse(status="ok", message="Session logged successfully")
        except APIException as e:
            raise e
        except Exception as e:
            logger.error(f"Error logging session for user {data.user_id}: {str(e)}", exc_info=True)
            raise APIException(status_code=500, detail=f"Internal server error: {str(e)}")

@app.post("/log-milestone", response_model=APIResponse)
async def log_milestone(
    data: MilestoneInput, 
    db: AsyncSession = Depends(get_db), 
    api_key: str = Depends(APIKeyHeader)
):
    """Log a user milestone"""
    async with db.begin():
        try:
            user = await db.get(User, data.user_id)
            if not user:
                raise APIException(status_code=404, detail="User not found")

            milestone = MilestoneLog(
                id=str(uuid.uuid4()),
                user_id=data.user_id,
                agent=data.agent,
                milestone_type=data.type,
                description=data.description,
                timestamp=datetime.utcnow()
            )
            db.add(milestone)

            return APIResponse(status="ok", message=f"Milestone '{data.type}' logged successfully")
        except APIException as e:
            raise e
        except Exception as e:
            logger.error(f"Error logging milestone for user {data.user_id}: {str(e)}", exc_info=True)
            raise APIException(status_code=500, detail=f"Internal server error: {str(e)}")

@app.post("/log-agent-switch", response_model=APIResponse)
async def log_agent_switch(
    data: AgentSwitchLog, 
    db: AsyncSession = Depends(get_db), 
    api_key: str = Depends(APIKeyHeader)
):
    """Log an agent switch event"""
    async with db.begin():
        try:
            user = await db.get(User, data.user_id)
            if not user:
                raise APIException(status_code=404, detail="User not found")

            timestamp = datetime.utcnow() if not data.timestamp else datetime.fromisoformat(data.timestamp)

            session_log = SessionLog(
                id=str(uuid.uuid4()),
                user_id=data.user_id,
                agent=data.to_agent,
                session_data={
                    "event": "agent_switch",
                    "from_agent": data.from_agent,
                    "to_agent": data.to_agent,
                    "reason": data.reason
                },
                timestamp=timestamp
            )
            db.add(session_log)

            return APIResponse(status="ok", message=f"Agent switch from {data.from_agent} to {data.to_agent} logged successfully")
        except APIException as e:
            raise e
        except Exception as e:
            logger.error(f"Error logging agent switch for user {data.user_id}: {str(e)}", exc_info=True)
            raise APIException(status_code=500, detail=f"Internal server error: {str(e)}")

@app.post("/update-settings", response_model=APIResponse)
async def update_settings(
    data: SettingsInput, 
    db: AsyncSession = Depends(get_db), 
    api_key: str = Depends(APIKeyHeader)
):
    """Update user settings"""
    async with db.begin():
        try:
            user = await db.get(User, data.user_id)
            if not user:
                raise APIException(status_code=404, detail="User not found")

            # Update only the fields that are provided
            if data.therapist_name is not None:
                user.therapist_name = data.therapist_name
            if data.tone_preference is not None:
                user.tone_preference = data.tone_preference
            if data.pacing_preference is not None:
                user.pacing_preference = data.pacing_preference
            if data.media_preference:
                user.media_preference = data.media_preference
            if data.learning_style is not None:
                user.learning_style = data.learning_style

            user.updated_at = datetime.utcnow()

            return APIResponse(status="ok", message="User settings updated successfully")
        except APIException as e:
            raise e
        except Exception as e:
            logger.error(f"Error updating settings for user {data.user_id}: {str(e)}", exc_info=True)
            raise APIException(status_code=500, detail=f"Internal server error: {str(e)}")

# Only execute this if running the script directly
if __name__ == "__main__":
    import uvicorn

    # Configure file paths - make sure these directories exist
    Path("/mnt/data/app").mkdir(parents=True, exist_ok=True)
    Path("/mnt/data/logs").mkdir(parents=True, exist_ok=True)

    # Setup file logging
    file_handler = logging.FileHandler("/mnt/data/logs/api.log")
    file_handler.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
    logger.addHandler(file_handler)

    uvicorn.run(app, host="0.0.0.0", port=8000)