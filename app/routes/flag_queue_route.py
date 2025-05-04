
from admin_stats_route import router as admin_stats_router
from capsule_preview_route import router as capsule_preview_router
from fastapi import FastAPI
from flag_queue_route import router as flag_queue_router
from log_milestone_route import router as log_milestone_router
from log_session_route import router as log_session_router
from log_summary_route import router as log_summary_router

from app.routes import admin, media, milestone, session, summary

app = FastAPI(title="EchoMind API v2")

app.include_router(session.router, prefix="/session")
app.include_router(summary.router, prefix="/summary")
app.include_router(milestone.router, prefix="/milestone")
app.include_router(media.router, prefix="/media")
app.include_router(admin.router, prefix="/admin")

app.include_router(log_session_router)
app.include_router(log_summary_router)
app.include_router(log_milestone_router)
app.include_router(admin_stats_router)
app.include_router(capsule_preview_router)
app.include_router(flag_queue_router)

@app.get("/")
def root():
    return {"message": "EchoMind API is live"}
