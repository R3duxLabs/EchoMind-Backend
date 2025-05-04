import uuid
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.get_api_key import get_api_key
from app.models import SummaryLog, User

router = APIRouter()

class LogSummaryInput(BaseModel):
    user_id: str
    agent: str
    summary_text: str
    tags: Optional[List[str]] = []
    emotional_tone: Optional[str] = None
    confidence: Optional[float] = None

@router.post("/log-summary")
async def log_summary(data: LogSummaryInput, db: AsyncSession = Depends(get_db), api_key: str = Depends(get_api_key)):
    try:
        user = await db.get(User, data.user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        summary = SummaryLog(
            id=str(uuid.uuid4()),
            user_id=data.user_id,
            agent=data.agent,
            summary_text=data.summary_text,
            tags=data.tags,
            emotional_tone=data.emotional_tone,
            confidence=data.confidence,
            timestamp=datetime.utcnow()
        )
        db.add(summary)
        await db.commit()
        return {"status": "ok"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
