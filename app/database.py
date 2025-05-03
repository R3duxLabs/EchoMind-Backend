from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from models import User, Session, SummaryLog, MilestoneLog, Relationship
from database import get_db, export_user_data
from datetime import datetime
from typing import Optional
from pydantic import BaseModel
import uuid
import logging
from collections import Counter

router = APIRouter()

@router.get("/get-milestones")
async def get_milestones(user_id: str, db: AsyncSession = Depends(get_db)):
  try:
      milestones = await db.execute(
          select(MilestoneLog)
          .where(MilestoneLog.user_id == user_id)
          .order_by(MilestoneLog.timestamp.desc())
      )
      return {
          "status": "ok",
          "milestones": [m.__dict__ for m in milestones.scalars()]
      }
  except Exception as e:
      logging.error(f"Error fetching milestones: {str(e)}")
      raise HTTPException(status_code=500, detail="Internal server error")
@router.get("/capsule/preview")
async def capsule_preview(user_id: str, db: AsyncSession = Depends(get_db)):
try:
summaries = await db.execute(
select(SummaryLog).where(SummaryLog.user_id == user_id).order_by(SummaryLog.timestamp.desc()).limit(5)
)
milestones = await db.execute(
select(MilestoneLog).where(MilestoneLog.user_id == user_id).order_by(MilestoneLog.timestamp.desc()).limit(5)
)
return {
"status": "ok",
"summary_samples": [s.dict for s in summaries.scalars()],
"milestone_samples": [m.dict for m in milestones.scalars()]
}
except Exception as e:
logging.error(f"Error generating capsule preview: {str(e)}")
raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/capsule/export")
async def capsule_export(user_id: str, db: AsyncSession = Depends(get_db)):
try:
data = await export_user_data(user_id, db)
if not data:
raise HTTPException(status_code=404, detail="User not found")
return {"status": "ok", "capsule": data}
except Exception as e:
logging.error(f"Error exporting capsule: {str(e)}")
raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/emotion-stats/summary")
async def emotion_summary(user_id: str, db: AsyncSession = Depends(get_db)):
try:
result = await db.execute(
select(SummaryLog.tags).where(SummaryLog.user_id == user_id)
)
tag_list = [tag for row in result.scalars() if row for tag in row]
return {"status": "ok", "tag_counts": dict(Counter(tag_list))}
except Exception as e:
logging.error(f"Error compiling emotion stats: {str(e)}")
raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/emotion-stats/timeline")
async def emotion_timeline(user_id: str):
return {"status": "ok", "timeline": []}  # Future timeline analysis logic

class RelationshipInput(BaseModel):
user_a_id: str
user_b_id: str
relationship_type: str

@router.post("/create-relationship")
async def create_relationship(payload: RelationshipInput, db: AsyncSession = Depends(get_db)):
try:
new_relation = Relationship(
id=str(uuid.uuid4()),
user_a_id=payload.user_a_id,
user_b_id=payload.user_b_id,
relationship_type=payload.relationship_type,
approved=False,
visibility_level="summary",
visibility_rules="{}"
)
db.add(new_relation)
await db.commit()
return {"status": "ok", "relationship_id": new_relation.id}
except Exception as e:
logging.error(f"Relationship creation failed: {str(e)}")
raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/admin/stats")
async def admin_stats(db: AsyncSession = Depends(get_db)):
try:
user_count = await db.execute(select(User))
session_count = await db.execute(select(Session))
summary_count = await db.execute(select(SummaryLog))
return {
"status": "ok",
"users": len(user_count.scalars().all()),
"sessions": len(session_count.scalars().all()),
"summaries": len(summary_count.scalars().all())
}
except Exception as e:
logging.error(f"Error retrieving admin stats: {str(e)}")
raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/flag-queue")
async def flag_queue():
return {"status": "ok", "flags": []}  # Placeholder for future moderation queue