import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.get_api_key import get_api_key
from app.models import MilestoneLog, MilestoneType

router = APIRouter()

class MilestoneInput(BaseModel):
    user_id: str
    agent: str
    type: MilestoneType
    description: str

@router.post("/log-milestone")
async def log_milestone(data: MilestoneInput, db: AsyncSession = Depends(get_db), api_key: str = Depends(get_api_key)):
    try:
        milestone = MilestoneLog(
            id=str(uuid.uuid4()),
            user_id=data.user_id,
            agent=data.agent,
            type=data.type,
            description=data.description,
            timestamp=datetime.utcnow()
        )
        db.add(milestone)
        await db.commit()
        return {"status": "ok"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
