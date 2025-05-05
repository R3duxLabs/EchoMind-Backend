"""
Authentication Module

This module provides authentication mechanisms for the application.
"""

import logging
import json
from datetime import datetime, timedelta
from typing import Dict, Optional, Any, Union, List

from fastapi import Depends, HTTPException, status, Request, Security
from fastapi.security import OAuth2PasswordBearer, APIKeyHeader, SecurityScopes
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel, ValidationError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.database import get_db
from app.models import User
from app.logging_config import get_logger

# Configure logger
logger = get_logger(__name__)

# Configuration (would be moved to environment variables in production)
SECRET_KEY = "securerandomsecretkey"  # Replace with a secure secret key in production
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# Define password context for hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Define OAuth2 scheme for token authentication
oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="token",
    scopes={
        "user": "Standard user access",
        "admin": "Admin privileges",
        "system": "System operations"
    }
)

# Define API key header for API access
api_key_header = APIKeyHeader(name="X-API-Key")

# Authentication models
class Token(BaseModel):
    """Token response model"""
    access_token: str
    token_type: str
    expires_at: datetime
    user_id: str
    scopes: List[str]

class TokenData(BaseModel):
    """Token data model"""
    username: Optional[str] = None
    scopes: List[str] = []
    user_id: Optional[str] = None
    exp: Optional[datetime] = None

class UserCredentials(BaseModel):
    """User credentials for authentication"""
    username: str
    password: str

class ApiKey(BaseModel):
    """API key model"""
    key: str
    owner_id: str
    scopes: List[str]
    expires_at: Optional[datetime] = None
    created_at: datetime = datetime.utcnow()
    is_active: bool = True
    name: Optional[str] = None

# Helper functions
def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify that a plain password matches the hashed password"""
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    """Generate a password hash"""
    return pwd_context.hash(password)

def create_access_token(
    data: Dict[str, Any], 
    expires_delta: Optional[timedelta] = None
) -> str:
    """Create a JWT access token"""
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    
    logger.info(
        "Created access token",
        extra={
            "user_id": data.get("sub"),
            "scopes": data.get("scopes", []),
            "expires_at": expire.isoformat()
        }
    )
    
    return encoded_jwt

async def authenticate_user(
    username: str, 
    password: str,
    db: AsyncSession
) -> Optional[User]:
    """Authenticate a user with username and password"""
    query = select(User).where(User.email == username.lower())
    result = await db.execute(query)
    user = result.scalars().first()
    
    if not user:
        logger.warning(
            "Authentication failed: user not found",
            extra={"username": username}
        )
        return None
        
    if not user.is_active:
        logger.warning(
            "Authentication failed: user is not active",
            extra={"username": username, "user_id": user.id}
        )
        return None
    
    # In this simplified version, we assume password is already hashed in the database
    # In a real implementation, you would verify against a hashed password
    if not verify_password(password, user.password_hash):
        logger.warning(
            "Authentication failed: incorrect password",
            extra={"username": username, "user_id": user.id}
        )
        return None
        
    # Update last login timestamp
    user.last_login = datetime.utcnow()
    await db.commit()
    
    logger.info(
        "User authenticated successfully",
        extra={"username": username, "user_id": user.id}
    )
    
    return user

# API Key validation functions
async def validate_api_key(
    api_key: str, 
    db: AsyncSession,
    required_scopes: Optional[List[str]] = None
) -> Optional[Dict[str, Any]]:
    """Validate an API key and return user info"""
    # In a real implementation, this would look up the API key in a database
    # For this example, we use a simplified approach
    
    from app.security.api_keys import get_api_key_info
    
    api_key_info = await get_api_key_info(api_key, db)
    
    if not api_key_info:
        logger.warning(
            "API key validation failed: key not found",
            extra={"api_key_prefix": api_key[:6] + "..."}
        )
        return None
        
    if api_key_info.get("expires_at") and api_key_info["expires_at"] < datetime.utcnow():
        logger.warning(
            "API key validation failed: key expired",
            extra={
                "api_key_prefix": api_key[:6] + "...",
                "user_id": api_key_info.get("user_id")
            }
        )
        return None
        
    if not api_key_info.get("is_active", True):
        logger.warning(
            "API key validation failed: key is inactive",
            extra={
                "api_key_prefix": api_key[:6] + "...",
                "user_id": api_key_info.get("user_id")
            }
        )
        return None
    
    # Check scopes if required
    if required_scopes:
        key_scopes = api_key_info.get("scopes", [])
        if not all(scope in key_scopes for scope in required_scopes):
            logger.warning(
                "API key validation failed: insufficient scopes",
                extra={
                    "api_key_prefix": api_key[:6] + "...",
                    "user_id": api_key_info.get("user_id"),
                    "required_scopes": required_scopes,
                    "key_scopes": key_scopes
                }
            )
            return None
    
    logger.info(
        "API key validated successfully",
        extra={
            "api_key_prefix": api_key[:6] + "...",
            "user_id": api_key_info.get("user_id")
        }
    )
    
    return api_key_info

# Dependency for token authentication
async def get_current_user(
    security_scopes: SecurityScopes, 
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
) -> User:
    """Get the current user from JWT token"""
    if security_scopes.scopes:
        authenticate_value = f'Bearer scope="{security_scopes.scope_str}"'
    else:
        authenticate_value = "Bearer"
        
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": authenticate_value},
    )
    
    try:
        # Decode the JWT
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        token_scopes = payload.get("scopes", [])
        user_id = payload.get("user_id")
        
        if username is None or user_id is None:
            logger.warning("JWT validation failed: missing username or user_id")
            raise credentials_exception
            
        token_data = TokenData(
            username=username, 
            scopes=token_scopes, 
            user_id=user_id,
            exp=datetime.fromtimestamp(payload.get("exp", 0))
        )
        
    except (JWTError, ValidationError) as e:
        logger.warning(
            f"JWT validation failed: {str(e)}",
            exc_info=True
        )
        raise credentials_exception
    
    # Get the user from database
    user = await db.get(User, token_data.user_id)
    
    if user is None or not user.is_active:
        logger.warning(
            "JWT validation failed: user not found or inactive",
            extra={"user_id": token_data.user_id}
        )
        raise credentials_exception
        
    # Check if token is expired
    if token_data.exp and token_data.exp < datetime.utcnow():
        logger.warning(
            "JWT validation failed: token expired",
            extra={"user_id": token_data.user_id}
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expired",
            headers={"WWW-Authenticate": authenticate_value},
        )
    
    # Check if user has required scopes
    for scope in security_scopes.scopes:
        if scope not in token_data.scopes:
            logger.warning(
                "JWT validation failed: insufficient scopes",
                extra={
                    "user_id": token_data.user_id,
                    "required_scopes": security_scopes.scopes,
                    "token_scopes": token_data.scopes
                }
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not enough permissions",
                headers={"WWW-Authenticate": authenticate_value},
            )
    
    logger.info(
        "JWT validation successful",
        extra={"user_id": token_data.user_id}
    )
    
    return user

# Dependency for API key authentication
async def get_api_user(
    api_key: str = Depends(api_key_header),
    db: AsyncSession = Depends(get_db),
    required_scopes: Optional[List[str]] = None
) -> Dict[str, Any]:
    """Get user info from API key"""
    api_key_info = await validate_api_key(api_key, db, required_scopes)
    
    if not api_key_info:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API Key",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    
    return api_key_info

# Dependency for admin access
async def get_admin_user(
    current_user: User = Security(get_current_user, scopes=["admin"])
) -> User:
    """Get current user and verify admin role"""
    if current_user.role != "admin":
        logger.warning(
            "Admin access denied: user is not an admin",
            extra={"user_id": current_user.id, "role": current_user.role}
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    
    logger.info(
        "Admin access granted",
        extra={"user_id": current_user.id}
    )
    
    return current_user

# Enhanced middleware for auth logging and tracking
async def log_auth_activity(request: Request, user_id: str) -> None:
    """Log authentication and authorization activity"""
    try:
        client_host = request.client.host if request.client else "unknown"
        path = request.url.path
        method = request.method
        
        logger.info(
            "Auth activity",
            extra={
                "user_id": user_id,
                "client_host": client_host,
                "path": path,
                "method": method
            }
        )
    except Exception as e:
        logger.error(
            f"Error logging auth activity: {str(e)}",
            exc_info=True
        )
    
# Token endpoint function to generate JWT tokens
async def create_user_token(
    credentials: UserCredentials,
    db: AsyncSession
) -> Optional[Token]:
    """Create a JWT token for a user"""
    user = await authenticate_user(credentials.username, credentials.password, db)
    
    if not user:
        return None
    
    # Determine scopes based on user role
    scopes = ["user"]
    if user.role == "admin":
        scopes.append("admin")
    
    # Create token with expiration
    expires_delta = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    expires_at = datetime.utcnow() + expires_delta
    
    token_data = {
        "sub": user.email,
        "scopes": scopes,
        "user_id": user.id
    }
    
    access_token = create_access_token(
        data=token_data,
        expires_delta=expires_delta
    )
    
    return Token(
        access_token=access_token,
        token_type="bearer",
        expires_at=expires_at,
        user_id=user.id,
        scopes=scopes
    )