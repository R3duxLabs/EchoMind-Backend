"""
CORS Middleware for EchoMind API

This module configures Cross-Origin Resource Sharing (CORS) for the FastAPI application
to allow frontend applications to make requests to the API.
"""

import os
from typing import List, Optional

from fastapi.middleware.cors import CORSMiddleware
from starlette.applications import Starlette
from starlette.types import ASGIApp

from app.logging_config import get_logger

logger = get_logger(__name__)

def setup_cors(app: ASGIApp, origins: Optional[List[str]] = None) -> None:
    """
    Set up CORS middleware for the FastAPI application
    
    Args:
        app: The FastAPI application
        origins: List of allowed origins. If None, uses environment variable or defaults
    
    Returns:
        None
    """
    # Get allowed origins from environment or use defaults
    if origins is None:
        origins_env = os.getenv("CORS_ORIGINS", "")
        if origins_env:
            origins = [origin.strip() for origin in origins_env.split(",")]
        else:
            # Default allowed origins
            origins = [
                "http://localhost",
                "http://localhost:3000",
                "http://localhost:8000",
                "https://app.echomind.io",
                "https://dev.echomind.io",
                "https://staging.echomind.io"
            ]
    
    # Log configured origins
    logger.info(
        "Setting up CORS middleware", 
        extra={"origins": origins}
    )
    
    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=[
            "X-Rate-Limit-Limit",
            "X-Rate-Limit-Remaining", 
            "X-Rate-Limit-Reset"
        ]
    )