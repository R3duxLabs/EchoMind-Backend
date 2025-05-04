import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.get_api_key import get_api_key
from app.models import SessionLog

router = APIRouter()

class LogSessionInput(BaseModel):
    user_id: str
    agent: str
    session_data: dict

@router.post("/log-session")
async def log_session(data: LogSessionInput, db: AsyncSession = Depends(get_db), api_key: str = Depends(get_api_key)):
    try:
        log = SessionLog(
            id=str(uuid.uuid4()),
            user_id=data.user_id,
            agent=data.agent,
            session_data=data.session_data,
            timestamp=datetime.utcnow()
        )
        db.add(log)
        await db.commit()
        return {"status": "ok"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
