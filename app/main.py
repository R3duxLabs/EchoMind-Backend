import json
import logging
import os
import uuid
from datetime import datetime
from typing import List, Optional

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.database import get_db
from app.models import MemorySnapshot, SessionLog, SummaryLog, User
from app.get_api_key import get_api_key

app = FastAPI(title="EchoMind API v2")

# ----------------------------- Pydantic Schemas -----------------------------

class MemoryUpdate(BaseModel):
    user_id: str
    agent: str
    memory: dict
    summary: Optional[str] = None
    tags: Optional[List[str]] = []
    emotional_tone: Optional[str] = None
    confidence: Optional[float] = None

class MemoryRequest(BaseModel):
    user_id: str
    agent: str

class AgentSwitchLog(BaseModel):
    user_id: str
    from_agent: str
    to_agent: str
    reason: Optional[str] = None
    timestamp: Optional[str] = None

class SettingsInput(BaseModel):
    user_id: str
    therapist_name: Optional[str] = None
    tone_preference: Optional[str] = None
    pacing_preference: Optional[str] = None
    media_preference: Optional[List[str]] = []
    learning_style: Optional[str] = None

class LogSessionInput(BaseModel):
    user_id: str
    agent: Optional[str] = None
    message: str
    response: str
    tags: Optional[List[str]] = []
    emotional_tone: Optional[str] = None
    confidence: Optional[float] = None

class MilestoneInput(BaseModel):
    user_id: str
    agent: Optional[str] = "EchoMind"
    type: str
    description: str

# ----------------------------- Routes -----------------------------

@app.get("/")
def root():
    return {"message": "EchoMind API is live"}

@app.post("/get-memory")
async def get_memory(request: MemoryRequest, db: AsyncSession = Depends(get_db), _: str = Depends(get_api_key)):
    try:
        user = await db.get(User, request.user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        snapshot = await db.execute(select(MemorySnapshot).where(MemorySnapshot.user_id == request.user_id))
        agent_memory_map = {s.agent: s.summary_text for s in snapshot.scalars()}
        agent_memory = agent_memory_map.get(request.agent)

        if not agent_memory:
            fallback = list(agent_memory_map.values())
            agent_memory = fallback[-1] if fallback else "No previous sessions found. Let's begin fresh."

        summary_data = await db.execute(
            select(SummaryLog).where(SummaryLog.user_id == request.user_id, SummaryLog.agent == request.agent)
            .order_by(SummaryLog.timestamp.desc()).limit(10)
        )
        summaries = [
            {
                "summary": s.summary_text,
                "tags": s.tags,
                "emotional_tone": s.emotional_tone,
                "confidence": s.confidence,
                "timestamp": s.timestamp.isoformat()
            }
            for s in summary_data.scalars()
        ] or [{"summary": "No summaries found yet. You’re starting fresh.", "tags": [], "emotional_tone": None, "confidence": None, "timestamp": None}]

        return {"status": "ok", "agent_memory": agent_memory, "latest_summaries": summaries}
    except Exception as e:
        logging.error(f"Error in get_memory: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/get-shared-summary")
async def get_shared_summary(user_id: str, db: AsyncSession = Depends(get_db), _: str = Depends(get_api_key)):
    try:
        user = await db.get(User, user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        shared = await db.execute(
            select(MemorySnapshot).where(MemorySnapshot.user_id == user_id).order_by(MemorySnapshot.updated_at.desc()).limit(1)
        )
        latest = shared.scalars().first()
        return {"status": "ok", "shared_summary": latest.summary_text if latest else "No memory available yet."}
    except Exception as e:
        logging.error(f"Error in get_shared_summary: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.post("/update-memory")
async def update_memory(data: MemoryUpdate, db: AsyncSession = Depends(get_db), _: str = Depends(get_api_key)):
    try:
        user = await db.get(User, data.user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        snapshot = await db.execute(select(MemorySnapshot).where(MemorySnapshot.user_id == data.user_id, MemorySnapshot.agent == data.agent))
        existing = snapshot.scalars().first()
        memory_str = json.dumps(data.memory, indent=2)

        if existing:
            existing.summary_text = memory_str
            existing.updated_at = datetime.utcnow()
        else:
            db.add(MemorySnapshot(
                id=str(uuid.uuid4()),
                user_id=data.user_id,
                agent=data.agent,
                summary_text=memory_str
            ))

        if data.summary:
            db.add(SummaryLog(
                id=str(uuid.uuid4()),
                user_id=data.user_id,
                agent=data.agent,
                summary_text=data.summary,
                tags=data.tags or [],
                emotional_tone=data.emotional_tone,
                confidence=data.confidence,
                timestamp=datetime.utcnow()
            ))

        db.add(SessionLog(
            id=str(uuid.uuid4()),
            user_id=data.user_id,
            session_data={"event": "memory updated"},
            agent=data.agent,
            timestamp=datetime.utcnow()
        ))

        await db.commit()
        return {"status": "ok"}
    except Exception as e:
        logging.error(f"Error updating memory for user {data.user_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")