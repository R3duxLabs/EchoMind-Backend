from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.get_api_key import get_api_key
from app.models import MilestoneLog, SessionLog, SummaryLog, User

router = APIRouter()

@router.get("/admin/stats")
async def get_admin_stats(db: AsyncSession = Depends(get_db), api_key: str = Depends(get_api_key)):
    try:
        total_users = await db.scalar(select(func.count()).select_from(User))
        total_sessions = await db.scalar(select(func.count()).select_from(SessionLog))
        total_milestones = await db.scalar(select(func.count()).select_from(MilestoneLog))
        total_summaries = await db.scalar(select(func.count()).select_from(SummaryLog))

        return {
            "users": total_users,
            "sessions": total_sessions,
            "milestones": total_milestones,
            "summaries": total_summaries
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
