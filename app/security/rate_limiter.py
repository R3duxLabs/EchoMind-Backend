"""
Rate Limiter Module

This module provides rate limiting functionality to protect API endpoints.
"""

import time
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional, Any, Callable
from fastapi import Request, HTTPException, status, Depends

from app.logging_config import get_logger

# Configure logger
logger = get_logger(__name__)

class RateLimiter:
    """Rate limiter using a simple in-memory store"""
    
    def __init__(self, limit: int, window_seconds: int):
        """
        Initialize the rate limiter.
        
        Args:
            limit: Maximum number of requests allowed in the window
            window_seconds: Time window in seconds
        """
        self.limit = limit
        self.window_seconds = window_seconds
        self.requests = {}  # client_key -> [(timestamp, count), ...]
    
    def _clean_old_requests(self, client_key: str, now: float) -> None:
        """
        Clean up old request records.
        
        Args:
            client_key: Client identifier
            now: Current timestamp
        """
        if client_key not in self.requests:
            return
            
        # Remove entries older than the window
        window_start = now - self.window_seconds
        self.requests[client_key] = [
            (ts, count) for ts, count in self.requests[client_key]
            if ts >= window_start
        ]
    
    def is_allowed(self, client_key: str) -> Tuple[bool, Dict[str, Any]]:
        """
        Check if a request is allowed.
        
        Args:
            client_key: Client identifier
            
        Returns:
            Tuple of (is_allowed, rate_limit_info)
        """
        now = time.time()
        
        # Clean up old requests
        self._clean_old_requests(client_key, now)
        
        # Initialize client record if not exists
        if client_key not in self.requests:
            self.requests[client_key] = [(now, 1)]
            return True, {
                "limit": self.limit,
                "remaining": self.limit - 1,
                "reset": now + self.window_seconds
            }
        
        # Count total requests in the window
        total_requests = sum(count for _, count in self.requests[client_key])
        
        # Check if limit is exceeded
        if total_requests >= self.limit:
            # Get reset time
            oldest_ts = min(ts for ts, _ in self.requests[client_key])
            reset_time = oldest_ts + self.window_seconds
            
            return False, {
                "limit": self.limit,
                "remaining": 0,
                "reset": reset_time
            }
        
        # Add current request
        self.requests[client_key].append((now, 1))
        
        # Calculate remaining
        remaining = self.limit - total_requests - 1
        
        return True, {
            "limit": self.limit,
            "remaining": remaining,
            "reset": now + self.window_seconds
        }


# In-memory rate limiter instances
rate_limiters = {
    "default": RateLimiter(limit=100, window_seconds=60),  # 100 requests per minute
    "auth": RateLimiter(limit=10, window_seconds=60),  # 10 auth attempts per minute
    "high_volume": RateLimiter(limit=1000, window_seconds=60),  # 1000 requests per minute
    "low_volume": RateLimiter(limit=30, window_seconds=60),  # 30 requests per minute
}

def get_client_key(request: Request) -> str:
    """
    Get a unique key for the client.
    
    Args:
        request: FastAPI request object
        
    Returns:
        Client key string
    """
    # Use forwarded IP if available (for proxied requests)
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        client_ip = forwarded_for.split(",")[0].strip()
    else:
        client_ip = request.client.host if request.client else "unknown"
    
    # Include API key if available
    api_key = request.headers.get("X-API-Key", "")
    api_key_prefix = api_key[:6] if api_key else ""
    
    # Include route for granular rate limiting
    route = request.url.path
    
    return f"{client_ip}:{api_key_prefix}:{route}"

async def rate_limit_dependency(
    request: Request,
    limiter_key: str = "default"
) -> None:
    """
    FastAPI dependency for rate limiting.
    
    Args:
        request: FastAPI request object
        limiter_key: Key for the rate limiter to use
        
    Raises:
        HTTPException if rate limit is exceeded
    """
    # Get client key
    client_key = get_client_key(request)
    
    # Get rate limiter
    limiter = rate_limiters.get(limiter_key, rate_limiters["default"])
    
    # Check if request is allowed
    allowed, rate_limit_info = limiter.is_allowed(client_key)
    
    # Add rate limit headers to response
    request.state.rate_limit_info = rate_limit_info
    
    if not allowed:
        # Calculate retry after in seconds
        retry_after = int(rate_limit_info["reset"] - time.time())
        retry_after = max(0, retry_after)
        
        logger.warning(
            "Rate limit exceeded",
            extra={
                "client_key": client_key,
                "limiter_key": limiter_key,
                "limit": rate_limit_info["limit"],
                "retry_after": retry_after
            }
        )
        
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded",
            headers={
                "Retry-After": str(retry_after),
                "X-RateLimit-Limit": str(rate_limit_info["limit"]),
                "X-RateLimit-Remaining": str(rate_limit_info["remaining"]),
                "X-RateLimit-Reset": str(int(rate_limit_info["reset"]))
            }
        )

# Middleware for adding rate limit headers to responses
async def add_rate_limit_headers(request: Request, call_next):
    """
    Middleware for adding rate limit headers to responses.
    
    Args:
        request: FastAPI request object
        call_next: Next middleware function
        
    Returns:
        Response with rate limit headers
    """
    response = await call_next(request)
    
    # Add rate limit headers if available
    if hasattr(request.state, "rate_limit_info"):
        rate_limit_info = request.state.rate_limit_info
        response.headers["X-RateLimit-Limit"] = str(rate_limit_info["limit"])
        response.headers["X-RateLimit-Remaining"] = str(rate_limit_info["remaining"])
        response.headers["X-RateLimit-Reset"] = str(int(rate_limit_info["reset"]))
    
    return response

# Helper function to create a rate-limited route
def rate_limited(limiter_key: str = "default"):
    """
    Decorator for rate-limited routes.
    
    Args:
        limiter_key: Key for the rate limiter to use
        
    Returns:
        Dependency function for the route
    """
    async def dependency(request: Request):
        await rate_limit_dependency(request, limiter_key)
    
    return Depends(dependency)