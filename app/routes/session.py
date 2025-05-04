from fastapi import APIRouter, Depends

from app.get_api_key import get_api_key

router = APIRouter()

@router.get("/ping")
async def ping_session(api_key: str = Depends(get_api_key)):
    return {"message": "Session routes active"}
