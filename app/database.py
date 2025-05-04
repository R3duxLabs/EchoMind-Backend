import os
import uuid
from typing import Dict, List, Optional, Any

from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.future import select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.sql import Select
from contextlib import asynccontextmanager

from app.models import MilestoneLog, Relationship, SessionLog, SummaryLog, User

# Force load .env.production to ensure async driver is loaded
load_dotenv(dotenv_path=".env.production", override=True)

DATABASE_URL = os.getenv("DATABASE_URL")

# Ensure correct driver is in use
if not DATABASE_URL or "+asyncpg" not in DATABASE_URL:
    raise ValueError("DATABASE_URL must use asyncpg driver (postgresql+asyncpg://...)")

# Configure async engine with connection pooling
engine = create_async_engine(
    DATABASE_URL,
    echo=os.getenv("SQL_ECHO", "false").lower() == "true",
    pool_size=5,
    max_overflow=10,
    pool_timeout=30,
    pool_recycle=1800,
)

AsyncSessionLocal = sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False
)

@asynccontextmanager
async def get_db():
    """Provide a database session with proper error handling and cleanup."""
    db = AsyncSessionLocal()
    try:
        yield db
    finally:
        await db.close()

def serialize_model(model_instance) -> Dict[str, Any]:
    """Convert SQLAlchemy model to dict, excluding private attributes."""
    if model_instance is None:
        return None
        
    result = {}
    for key, value in model_instance.__dict__.items():
        # Skip SQLAlchemy internal attributes and relationship objects
        if not key.startswith('_'):
            result[key] = value
    return result

async def execute_query(db: AsyncSession, query: Select) -> List[Any]:
    """Execute a query and return serialized results."""
    result = await db.execute(query)
    return [serialize_model(item) for item in result.scalars()]

async def export_user_data(user_id: str, db: AsyncSession) -> Optional[Dict[str, Any]]:
    """
    Export all data related to a specific user.
    
    Args:
        user_id: The unique identifier of the user
        db: Database session
        
    Returns:
        Dictionary containing user data and related records or None if user not found
    """
    try:
        # Get user record
        user = await db.get(User, user_id)
        if not user:
            return None
            
        # Prepare queries for related data
        queries = {
            "sessions": select(SessionLog).where(SessionLog.user_id == user_id).order_by(SessionLog.created_at.desc()),
            "summaries": select(SummaryLog).where(SummaryLog.user_id == user_id).order_by(SummaryLog.created_at.desc()),
            "milestones": select(MilestoneLog).where(MilestoneLog.user_id == user_id).order_by(MilestoneLog.created_at.desc()),
            "relationships": select(Relationship).where(Relationship.user_a_id == user_id),
        }
        
        # Execute all queries and compile results
        results = {
            "user": serialize_model(user),
        }
        
        # Execute all queries concurrently
        for key, query in queries.items():
            results[key] = await execute_query(db, query)
            
        # Add metadata
        results["metadata"] = {
            "export_date": datetime.datetime.now().isoformat(),
            "record_counts": {key: len(value) for key, value in results.items() if isinstance(value, list)}
        }
            
        return results
        
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"Error exporting user data: {error_details}")
        return {
            "error": str(e),
            "user_id": user_id,
            "timestamp": datetime.datetime.now().isoformat()
        }

# Example usage with pagination
async def export_user_data_paginated(
    user_id: str, 
    db: AsyncSession,
    page_size: int = 100
) -> Dict[str, Any]:
    """Export user data with pagination for large datasets."""
    try:
        user = await db.get(User, user_id)
        if not user:
            return None
            
        results = {"user": serialize_model(user)}
        
        # Define tables to export with pagination
        tables = {
            "sessions": SessionLog,
            "summaries": SummaryLog,
            "milestones": MilestoneLog,
        }
        
        # Export each table with pagination
        for key, model in tables.items():
            results[key] = []
            offset = 0
            
            while True:
                query = select(model).where(
                    model.user_id == user_id
                ).order_by(
                    model.created_at.desc()
                ).limit(page_size).offset(offset)
                
                batch = await execute_query(db, query)
                
                if not batch:
                    break
                    
                results[key].extend(batch)
                offset += page_size
                
                if len(batch) < page_size:
                    break
        
        # Get relationships (typically smaller, no pagination needed)
        results["relationships"] = await execute_query(
            db, select(Relationship).where(Relationship.user_a_id == user_id)
        )
        
        return results
        
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"Error exporting user data: {error_details}")
        return {"error": str(e)}
