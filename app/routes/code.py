from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
import uuid
from datetime import datetime
from sqlalchemy import select
from typing import Dict, Any, List, Optional

from app.database import get_db
from app.get_api_key import get_api_key
from app.models import SessionLog
from app.code_execution import execute_python_code

router = APIRouter()

class CodeExecutionRequest(BaseModel):
    """
    Request model for code execution
    """
    user_id: str = Field(..., description="User's unique identifier")
    code: str = Field(..., description="Code to execute")
    language: str = Field("python", description="Programming language (only Python supported for now)")
    context: Dict[str, Any] = Field({}, description="Optional context variables for code execution")
    
    class Config:
        schema_extra = {
            "example": {
                "user_id": "user123",
                "code": "print('Hello, world!')\nx = 5\ny = 10\nprint(f'Sum: {x + y}')",
                "language": "python",
                "context": {"input_value": 42}
            }
        }
    
class CodeExecutionResponse(BaseModel):
    """
    Response model for code execution results
    """
    result: Dict[str, Any] = Field(..., description="Execution result including stdout, stderr, and exceptions")
    execution_id: str = Field(..., description="Unique identifier for this execution")
    execution_time: float = Field(..., description="Time taken to execute the code in seconds")
    status: str = Field(..., description="Execution status: 'success' or 'error'")
    
    class Config:
        schema_extra = {
            "example": {
                "result": {
                    "stdout": "Hello, world!\nSum: 15\n",
                    "stderr": "",
                    "execution_time": 0.0023,
                    "success": True
                },
                "execution_id": "550e8400-e29b-41d4-a716-446655440000",
                "execution_time": 0.0023,
                "status": "success"
            }
        }

class ExecutionListResponse(BaseModel):
    """
    Response model for listing code executions
    """
    executions: List[Dict[str, Any]] = Field(..., description="List of code execution summaries")
    
    class Config:
        schema_extra = {
            "example": {
                "executions": [
                    {
                        "id": "550e8400-e29b-41d4-a716-446655440000",
                        "language": "python",
                        "timestamp": "2023-05-05T10:30:00.000Z",
                        "code_preview": "print('Hello, world!')..."
                    }
                ]
            }
        }

class ExecutionDetailResponse(BaseModel):
    """
    Response model for a specific code execution
    """
    id: str = Field(..., description="Execution ID")
    user_id: str = Field(..., description="User ID")
    code: str = Field(..., description="Executed code")
    language: str = Field(..., description="Programming language")
    result: Dict[str, Any] = Field(..., description="Execution result")
    timestamp: str = Field(..., description="Execution timestamp")
    
    class Config:
        schema_extra = {
            "example": {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "user_id": "user123",
                "code": "print('Hello, world!')\nx = 5\ny = 10\nprint(f'Sum: {x + y}')",
                "language": "python",
                "result": {
                    "stdout": "Hello, world!\nSum: 15\n",
                    "stderr": "",
                    "execution_time": 0.0023,
                    "success": True
                },
                "timestamp": "2023-05-05T10:30:00.000Z"
            }
        }

@router.get("/ping", 
            summary="Health Check",
            description="Simple health check endpoint to verify the code execution service is running")
async def ping_code(api_key: str = Depends(get_api_key)):
    """Health check endpoint for the code execution service"""
    return {"message": "Code execution routes active"}

@router.post("/execute", 
             response_model=CodeExecutionResponse,
             summary="Execute Code",
             description="Execute Python code and return the results")
async def execute_code(
    request: CodeExecutionRequest, 
    db: AsyncSession = Depends(get_db), 
    api_key: str = Depends(get_api_key)
):
    """
    Execute code and return the results
    
    This endpoint allows executing Python code with optional context variables.
    The code execution is sandboxed for security.
    
    - The code is executed in a restricted environment
    - Execution results include stdout, stderr, and any exceptions
    - Results are stored for later retrieval
    """
    try:
        execution_id = str(uuid.uuid4())
        timestamp = datetime.utcnow()
        
        # Only handle Python for now
        if request.language.lower() != "python":
            raise HTTPException(
                status_code=400, 
                detail=f"Unsupported language: {request.language}. Only Python is currently supported."
            )
        
        # Execute the code
        execution_result = execute_python_code(request.code, request.context)
        status = "success" if execution_result["success"] else "error"
        
        # Log as a session
        session_log = SessionLog(
            id=execution_id,
            user_id=request.user_id,
            agent="ClaudeCode",
            session_data={
                "code": request.code,
                "language": request.language,
                "context": request.context,
                "result": execution_result,
                "timestamp": timestamp.isoformat()
            },
            timestamp=timestamp
        )
        db.add(session_log)
        await db.commit()
        
        return CodeExecutionResponse(
            result=execution_result,
            execution_id=execution_id,
            execution_time=execution_result["execution_time"],
            status=status
        )
        
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/executions/{user_id}", 
            response_model=ExecutionListResponse,
            summary="List Executions",
            description="List recent code executions for a specific user")
async def list_executions(
    user_id: str, 
    limit: int = Query(10, description="Maximum number of executions to return", ge=1, le=100),
    db: AsyncSession = Depends(get_db), 
    api_key: str = Depends(get_api_key)
):
    """
    List recent code executions for a user
    
    Returns a list of recent code executions for the specified user, ordered by timestamp
    (most recent first).
    
    - Results are paginated with a default limit of 10 items
    - Each result includes a preview of the executed code
    """
    try:
        query = select(SessionLog).where(
            SessionLog.user_id == user_id,
            SessionLog.agent == "ClaudeCode"
        ).order_by(
            SessionLog.timestamp.desc()
        ).limit(limit)
        
        result = await db.execute(query)
        executions = result.scalars().all()
        
        return ExecutionListResponse(
            executions=[
                {
                    "id": e.id,
                    "language": e.session_data.get("language", "python"),
                    "timestamp": e.timestamp.isoformat(),
                    "code_preview": e.session_data.get("code", "")[:100] + "..." 
                        if len(e.session_data.get("code", "")) > 100 
                        else e.session_data.get("code", "")
                }
                for e in executions
            ]
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/execution/{execution_id}", 
            response_model=ExecutionDetailResponse,
            summary="Get Execution Details",
            description="Get detailed information about a specific code execution")
async def get_execution(
    execution_id: str,
    db: AsyncSession = Depends(get_db), 
    api_key: str = Depends(get_api_key)
):
    """
    Get details of a specific code execution
    
    Returns detailed information about a specific code execution, including:
    - The executed code
    - Execution results (stdout, stderr, exceptions)
    - Execution timestamp
    """
    try:
        session = await db.get(SessionLog, execution_id)
        if not session or session.agent != "ClaudeCode":
            raise HTTPException(status_code=404, detail="Execution not found")
            
        return ExecutionDetailResponse(
            id=session.id,
            user_id=session.user_id,
            code=session.session_data.get("code", ""),
            language=session.session_data.get("language", "python"),
            result=session.session_data.get("result", {}),
            timestamp=session.timestamp.isoformat()
        )
        
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=str(e))