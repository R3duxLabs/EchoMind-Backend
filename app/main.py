import json
import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, Any

from fastapi import Depends, FastAPI, Request
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.openapi.utils import get_openapi
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.get_api_key import get_api_key, APIKeyHeader
from app.exception_handler import APIException, api_exception_handler, LoggingMiddleware
from app.error_handlers import setup_error_handlers
from app.routes import (
    code,
    health,
    session, 
    summary,
    milestone,
    admin_stats_route,
    log_session_route, 
    log_summary_route, 
    log_milestone_route,
    capsule_preview_route
)

# Import and configure logging
from app.logging_config import setup_logging, get_logger

# Set up structured logging
setup_logging(log_level="INFO", log_dir="/mnt/data/logs")
logger = get_logger(__name__)

app = FastAPI(
    title="EchoMind API",
    description="API for managing user memory, sessions, summaries, and code execution",
    version="2.0.0",
    docs_url=None,  # Disable the default docs URL
    redoc_url=None,  # Disable the default redoc URL
)

# Add routes
app.include_router(code.router, prefix="/code", tags=["Code Execution"])
app.include_router(health.router, tags=["Health"])
app.include_router(session.router, prefix="/session", tags=["Sessions"])
app.include_router(summary.router, prefix="/summary", tags=["Summaries"])
app.include_router(milestone.router, prefix="/milestone", tags=["Milestones"])
app.include_router(log_session_route.router, prefix="/log-session", tags=["Logging"])
app.include_router(log_summary_route.router, prefix="/log-summary", tags=["Logging"])
app.include_router(log_milestone_route.router, prefix="/log-milestone", tags=["Logging"])
app.include_router(admin_stats_route.router, prefix="/admin", tags=["Admin"])
app.include_router(capsule_preview_route.router, prefix="/capsule", tags=["Capsule"])

# Add error handlers
app.add_exception_handler(APIException, api_exception_handler)
setup_error_handlers(app)

# Add middleware
app.add_middleware(LoggingMiddleware)

# ----------------------------- Response Models -----------------------------

class APIResponse(BaseModel):
    """Standard API response model used across endpoints"""
    status: str
    message: Optional[str] = None
    data: Optional[Dict[str, Any]] = None

# ----------------------------- Custom OpenAPI Documentation -----------------------------

def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    
    openapi_schema = get_openapi(
        title="EchoMind API",
        version="2.0.0",
        description="""
        # EchoMind API
        
        This API provides endpoints for managing user memory, sessions, summaries, and code execution.
        
        ## Authentication
        
        All API endpoints require an API key for authentication. Add your API key to the request 
        headers using the `X-API-Key` header.
        
        ## Response Format
        
        Most endpoints return responses in the following format:
        
        ```json
        {
            "status": "ok",
            "message": "Operation completed successfully",
            "data": { ... }
        }
        ```
        
        ## Error Handling
        
        Error responses have the following format:
        
        ```json
        {
            "status": "error",
            "message": "Description of the error"
        }
        ```
        
        ## Rate Limiting
        
        API endpoints are rate-limited to prevent abuse. If you exceed the rate limit,
        you will receive a 429 Too Many Requests response.
        """,
        routes=app.routes,
    )
    
    # Add custom documentation for each tag
    for tag in openapi_schema["tags"]:
        if tag["name"] == "Code Execution":
            tag["description"] = "Endpoints for executing and managing code"
        elif tag["name"] == "Health":
            tag["description"] = "Health check endpoints"
        elif tag["name"] == "Sessions":
            tag["description"] = "Endpoints for managing user sessions"
        elif tag["name"] == "Summaries":
            tag["description"] = "Endpoints for accessing and managing user summaries"
        elif tag["name"] == "Milestones":
            tag["description"] = "Endpoints for tracking user milestones"
        elif tag["name"] == "Logging":
            tag["description"] = "Endpoints for logging user interactions"
        elif tag["name"] == "Admin":
            tag["description"] = "Admin-only endpoints for system management"
        elif tag["name"] == "Capsule":
            tag["description"] = "Endpoints for managing memory capsules"
    
    app.openapi_schema = openapi_schema
    return app.openapi_schema

app.openapi = custom_openapi

@app.get("/docs", include_in_schema=False)
async def custom_swagger_ui_html():
    """Custom Swagger UI documentation endpoint"""
    return get_swagger_ui_html(
        openapi_url="/openapi.json",
        title="EchoMind API Documentation",
        swagger_js_url="https://cdn.jsdelivr.net/npm/swagger-ui-dist@4/swagger-ui-bundle.js",
        swagger_css_url="https://cdn.jsdelivr.net/npm/swagger-ui-dist@4/swagger-ui.css",
    )

# ----------------------------- Root Route -----------------------------

@app.get("/", response_model=APIResponse, 
         summary="API Status",
         description="Health check endpoint to verify that the API is running")
async def root():
    """Health check endpoint"""
    return APIResponse(status="ok", message="EchoMind API is live")

# Generate a unique request ID middleware
@app.middleware("http")
async def add_request_id(request: Request, call_next):
    request_id = str(uuid.uuid4())
    request.state.request_id = request_id
    # Get user ID from request if available
    user_id = None
    try:
        if "X-API-Key" in request.headers:
            # This is a placeholder - in a real app, you would extract the user ID 
            # from the authenticated session
            user_id = "anonymous"
    except:
        pass
    
    # Create a request-specific logger
    request_logger = get_logger("app.request")
    request_logger.info(f"Request started", extra={
        "request_id": request_id,
        "user_id": user_id,
        "method": request.method,
        "url": str(request.url),
        "client_host": request.client.host if request.client else None
    })
    
    start_time = datetime.now()
    try:
        response = await call_next(request)
        process_time = (datetime.now() - start_time).total_seconds()
        
        request_logger.info(f"Request completed", extra={
            "request_id": request_id,
            "status_code": response.status_code,
            "processing_time": process_time
        })
        
        return response
    except Exception as e:
        process_time = (datetime.now() - start_time).total_seconds()
        request_logger.error(f"Request failed", extra={
            "request_id": request_id,
            "error": str(e),
            "processing_time": process_time
        })
        raise

# Only execute this if running the script directly
if __name__ == "__main__":
    import uvicorn

    # Configure file paths - make sure these directories exist
    Path("/mnt/data/app").mkdir(parents=True, exist_ok=True)
    Path("/mnt/data/logs").mkdir(parents=True, exist_ok=True)

    logger.info("Starting EchoMind API", extra={
        "version": "2.0.0",
        "environment": "development"
    })

    uvicorn.run(app, host="0.0.0.0", port=8000)