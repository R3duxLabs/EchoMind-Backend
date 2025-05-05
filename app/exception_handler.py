import json
import logging
from datetime import datetime

from fastapi import HTTPException, Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger("uvicorn.error")

class APIException(Exception):
    """Custom API exception with status code and detail message"""
    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail

async def api_exception_handler(request, exc):
    """Handle API exceptions and return appropriate response"""
    return Response(
        status_code=exc.status_code,
        content=json.dumps({"status": "error", "message": exc.detail}),
        media_type="application/json"
    )

async def http_exception_handler(request: Request, exc: HTTPException):
    logger.error(f"HTTP error: {exc.detail}")
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
    )

async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled error")
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal Server Error"},
    )

class LoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start_time = datetime.utcnow()
        try:
            response = await call_next(request)
            process_time = datetime.utcnow() - start_time
            logger.info(
                f"Request: {request.method} {request.url.path} - "
                f"Status: {response.status_code} - "
                f"Duration: {process_time.total_seconds():.3f}s"
            )
            return response
        except Exception as e:
            logger.error(f"Request failed: {request.method} {request.url.path} - Error: {str(e)}")
            raise
