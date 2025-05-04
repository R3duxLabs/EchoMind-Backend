import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.database import get_db
from app.get_api_key import get_api_key
from app.models import MilestoneLog

router = APIRouter()

@router.get("/milestones/{user_id}")
async def get_milestones(user_id: str, db: AsyncSession = Depends(get_db), api_key: str = Depends(get_api_key)):
    try:
        milestones = await db.execute(
            select(MilestoneLog).where(MilestoneLog.user_id == user_id).order_by(MilestoneLog.timestamp.desc())
        )
        return {
            "status": "ok",
            "milestones": [m.__dict__ for m in milestones.scalars()]
        }
    except Exception as e:
        logging.error(f"Error fetching milestones: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")
