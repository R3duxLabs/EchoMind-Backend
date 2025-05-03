from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.get_api_key import get_api_key

router = APIRouter()

@router.get("/ping")
async def ping_milestone(api_key: str = Depends(get_api_key)):
    return {"message": "Milestone routes active"}