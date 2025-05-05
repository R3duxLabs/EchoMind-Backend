from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from typing import Union, Dict, Any, List

from app.logging_config import get_logger

logger = get_logger(__name__)

class AppError(Exception):
    """Base application error class"""
    def __init__(
        self,
        status_code: int,
        error_code: str,
        message: str,
        details: Union[Dict[str, Any], List[Dict[str, Any]], None] = None
    ):
        self.status_code = status_code
        self.error_code = error_code
        self.message = message
        self.details = details
        super().__init__(self.message)

class NotFoundError(AppError):
    """Resource not found error"""
    def __init__(
        self,
        message: str = "The requested resource was not found",
        error_code: str = "NOT_FOUND",
        details: Union[Dict[str, Any], List[Dict[str, Any]], None] = None
    ):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            error_code=error_code,
            message=message,
            details=details
        )

class BadRequestError(AppError):
    """Bad request error"""
    def __init__(
        self,
        message: str = "Invalid request",
        error_code: str = "BAD_REQUEST",
        details: Union[Dict[str, Any], List[Dict[str, Any]], None] = None
    ):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            error_code=error_code,
            message=message,
            details=details
        )

class ValidationFailedError(BadRequestError):
    """Validation error"""
    def __init__(
        self,
        message: str = "Request validation failed",
        error_code: str = "VALIDATION_ERROR",
        details: Union[Dict[str, Any], List[Dict[str, Any]], None] = None
    ):
        super().__init__(message=message, error_code=error_code, details=details)

class UnauthorizedError(AppError):
    """Unauthorized error"""
    def __init__(
        self,
        message: str = "Unauthorized",
        error_code: str = "UNAUTHORIZED",
        details: Union[Dict[str, Any], List[Dict[str, Any]], None] = None
    ):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            error_code=error_code,
            message=message,
            details=details
        )

class ForbiddenError(AppError):
    """Forbidden error"""
    def __init__(
        self,
        message: str = "You don't have permission to access this resource",
        error_code: str = "FORBIDDEN",
        details: Union[Dict[str, Any], List[Dict[str, Any]], None] = None
    ):
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            error_code=error_code,
            message=message,
            details=details
        )

class InternalServerError(AppError):
    """Internal server error"""
    def __init__(
        self,
        message: str = "An unexpected error occurred",
        error_code: str = "INTERNAL_SERVER_ERROR",
        details: Union[Dict[str, Any], List[Dict[str, Any]], None] = None
    ):
        super().__init__(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            error_code=error_code,
            message=message,
            details=details
        )

def setup_error_handlers(app: FastAPI) -> None:
    """Setup FastAPI error handlers"""
    
    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError):
        """Handle application errors"""
        error_response = {
            "status": "error",
            "error": {
                "code": exc.error_code,
                "message": exc.message
            }
        }
        
        if exc.details:
            error_response["error"]["details"] = exc.details
        
        # Extract request ID from state if available
        request_id = getattr(request.state, "request_id", None)
        
        logger.error(f"App error: {exc.message}", extra={
            "error_code": exc.error_code,
            "status_code": exc.status_code,
            "request_id": request_id,
            "url": str(request.url),
            "method": request.method,
            "details": exc.details
        })
        
        return JSONResponse(
            status_code=exc.status_code,
            content=error_response
        )
    
    @app.exception_handler(ValidationError)
    async def validation_error_handler(request: Request, exc: ValidationError):
        """Handle pydantic validation errors"""
        details = []
        for error in exc.errors():
            details.append({
                "field": ".".join(str(x) for x in error["loc"]),
                "message": error["msg"],
                "type": error["type"]
            })
        
        # Extract request ID from state if available
        request_id = getattr(request.state, "request_id", None)
        
        logger.warning(f"Validation error", extra={
            "request_id": request_id,
            "url": str(request.url),
            "method": request.method,
            "validation_errors": details
        })
        
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "status": "error",
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "Request validation failed",
                    "details": details
                }
            }
        )
    
    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        """Handle unhandled exceptions"""
        # Extract request ID from state if available
        request_id = getattr(request.state, "request_id", None)
        
        logger.exception(f"Unhandled exception: {str(exc)}", extra={
            "request_id": request_id,
            "url": str(request.url),
            "method": request.method
        })
        
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "status": "error",
                "error": {
                    "code": "INTERNAL_SERVER_ERROR",
                    "message": "An unexpected error occurred"
                }
            }
        )