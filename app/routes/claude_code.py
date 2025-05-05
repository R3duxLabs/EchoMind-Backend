from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Body
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional, Union
import httpx
import asyncio
import os
import json
import logging

from app.database import get_db
from app.get_api_key import get_api_key
from app.models import SessionLog

# Configure logging
logger = logging.getLogger(__name__)

router = APIRouter()

class ClaudeCodeRequest(BaseModel):
    """
    Request model for Claude Code execution
    """
    user_id: str = Field(..., description="User's unique identifier")
    prompt: str = Field(..., description="Prompt to send to Claude Code")
    system_prompt: Optional[str] = Field(None, description="Optional system prompt for Claude")
    conversation_id: Optional[str] = Field(None, description="Optional conversation ID to continue an existing conversation")
    model: str = Field("claude-3-sonnet-20240229", description="Claude model to use")
    tools: Optional[List[Dict[str, Any]]] = Field(None, description="List of tools to provide to Claude")
    tool_choice: Optional[Union[str, Dict[str, Any]]] = Field(None, description="Tool choice configuration")
    temperature: Optional[float] = Field(0.7, description="Temperature for generation", ge=0, le=1)
    top_p: Optional[float] = Field(0.9, description="Top-p for generation", ge=0, le=1)
    
    class Config:
        schema_extra = {
            "example": {
                "user_id": "user123",
                "prompt": "Can you write a function to calculate the Fibonacci sequence?",
                "model": "claude-3-sonnet-20240229",
                "temperature": 0.7
            }
        }
    
class ClaudeCodeResponse(BaseModel):
    """
    Response model for Claude Code execution results
    """
    execution_id: str = Field(..., description="Unique identifier for this execution")
    conversation_id: str = Field(..., description="Conversation ID that can be used for follow-ups")
    response: Dict[str, Any] = Field(..., description="Claude's response")
    
    class Config:
        schema_extra = {
            "example": {
                "execution_id": "550e8400-e29b-41d4-a716-446655440000",
                "conversation_id": "conv_123456789",
                "response": {
                    "content": [
                        {
                            "type": "text",
                            "text": "Here's a function to calculate the Fibonacci sequence:"
                        },
                        {
                            "type": "code",
                            "text": "def fibonacci(n):\n    if n <= 0:\n        return []\n    elif n == 1:\n        return [0]\n    elif n == 2:\n        return [0, 1]\n    \n    fib = [0, 1]\n    for i in range(2, n):\n        fib.append(fib[i-1] + fib[i-2])\n    \n    return fib\n\n# Example usage\nprint(fibonacci(10))"
                        }
                    ],
                    "model": "claude-3-sonnet-20240229",
                    "stop_reason": "end_turn",
                    "usage": {
                        "input_tokens": 10,
                        "output_tokens": 150
                    }
                }
            }
        }

class ExecutionListResponse(BaseModel):
    """
    Response model for listing Claude Code executions
    """
    executions: List[Dict[str, Any]] = Field(..., description="List of Claude Code executions")
    
    class Config:
        schema_extra = {
            "example": {
                "executions": [
                    {
                        "id": "550e8400-e29b-41d4-a716-446655440000",
                        "prompt_preview": "Can you write a function to calculate...",
                        "timestamp": "2023-05-05T10:30:00.000Z",
                        "model": "claude-3-sonnet-20240229"
                    }
                ]
            }
        }

class ExecutionDetailResponse(BaseModel):
    """
    Response model for a specific Claude Code execution
    """
    id: str = Field(..., description="Execution ID")
    user_id: str = Field(..., description="User ID")
    prompt: str = Field(..., description="Submitted prompt")
    response: Dict[str, Any] = Field(..., description="Claude's response")
    model: str = Field(..., description="Claude model used")
    timestamp: str = Field(..., description="Execution timestamp")
    conversation_id: Optional[str] = Field(None, description="Conversation ID")
    
    class Config:
        schema_extra = {
            "example": {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "user_id": "user123",
                "prompt": "Can you write a function to calculate the Fibonacci sequence?",
                "response": {
                    "content": [
                        {
                            "type": "text",
                            "text": "Here's a function to calculate the Fibonacci sequence:"
                        },
                        {
                            "type": "code",
                            "text": "def fibonacci(n):\n    if n <= 0:\n        return []\n    elif n == 1:\n        return [0]\n    elif n == 2:\n        return [0, 1]\n    \n    fib = [0, 1]\n    for i in range(2, n):\n        fib.append(fib[i-1] + fib[i-2])\n    \n    return fib\n\n# Example usage\nprint(fibonacci(10))"
                        }
                    ]
                },
                "model": "claude-3-sonnet-20240229",
                "timestamp": "2023-05-05T10:30:00.000Z",
                "conversation_id": "conv_123456789"
            }
        }

@router.get("/ping", 
            summary="Health Check",
            description="Simple health check endpoint to verify the Claude Code service is running")
async def ping_claude_code(api_key: str = Depends(get_api_key)):
    """Health check endpoint for the Claude Code service"""
    return {"message": "Claude Code service is active"}

async def call_claude_api(request_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Call the Claude API and return the response.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="ANTHROPIC_API_KEY environment variable not set")
    
    async with httpx.AsyncClient(timeout=300) as client:  # 5-minute timeout
        try:
            response = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json"
                },
                json=request_data
            )
            response.raise_for_status()
            return response.json()
        except httpx.RequestError as e:
            logger.error(f"Error calling Claude API: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error calling Claude API: {str(e)}")
        except httpx.HTTPStatusError as e:
            logger.error(f"Claude API returned error: {e.response.status_code} - {e.response.text}")
            try:
                error_detail = e.response.json()
                error_message = error_detail.get("error", {}).get("message", str(e))
            except:
                error_message = str(e)
            raise HTTPException(status_code=e.response.status_code, detail=error_message)

@router.post("/execute", 
             response_model=ClaudeCodeResponse,
             summary="Execute Claude Code",
             description="Send a prompt to Claude and return the response")
async def execute_claude_code(
    request: ClaudeCodeRequest, 
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db), 
    api_key: str = Depends(get_api_key)
):
    """
    Execute Claude Code and return the results
    
    This endpoint sends a prompt to Claude and returns the response. It also
    logs the request and response for later retrieval.
    
    - The prompt is sent to the specified Claude model
    - The response includes Claude's response and conversation ID for follow-ups
    - Results are stored for later retrieval
    """
    try:
        execution_id = str(uuid.uuid4())
        timestamp = datetime.utcnow()
        
        # Prepare the request to Claude API
        claude_request = {
            "model": request.model,
            "temperature": request.temperature,
            "top_p": request.top_p,
            "max_tokens": 4096,  # Default max tokens
            "messages": [
                {
                    "role": "user",
                    "content": request.prompt
                }
            ]
        }
        
        # Add system prompt if provided
        if request.system_prompt:
            claude_request["system"] = request.system_prompt
        
        # Add conversation ID if provided
        if request.conversation_id:
            claude_request["conversation_id"] = request.conversation_id
        
        # Add tools if provided
        if request.tools:
            claude_request["tools"] = request.tools
        
        # Add tool choice if provided
        if request.tool_choice:
            claude_request["tool_choice"] = request.tool_choice
        
        # Call Claude API
        claude_response = await call_claude_api(claude_request)
        
        # Get or create conversation ID
        conversation_id = claude_response.get("conversation_id", str(uuid.uuid4()))
        
        # Log the request and response
        session_log = SessionLog(
            id=execution_id,
            user_id=request.user_id,
            agent="ClaudeCode",
            session_data={
                "prompt": request.prompt,
                "system_prompt": request.system_prompt,
                "model": request.model,
                "response": claude_response,
                "conversation_id": conversation_id,
                "timestamp": timestamp.isoformat()
            },
            timestamp=timestamp
        )
        db.add(session_log)
        await db.commit()
        
        return ClaudeCodeResponse(
            execution_id=execution_id,
            conversation_id=conversation_id,
            response=claude_response
        )
        
    except Exception as e:
        logger.error(f"Error in execute_claude_code: {str(e)}")
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/executions/{user_id}", 
            response_model=ExecutionListResponse,
            summary="List Claude Code Executions",
            description="List recent Claude Code executions for a specific user")
async def list_claude_code_executions(
    user_id: str, 
    limit: int = 10,
    db: AsyncSession = Depends(get_db), 
    api_key: str = Depends(get_api_key)
):
    """
    List recent Claude Code executions for a user
    
    Returns a list of recent Claude Code executions for the specified user, ordered by timestamp
    (most recent first).
    
    - Results are paginated with a default limit of 10 items
    - Each result includes a preview of the submitted prompt
    """
    try:
        query = """
            SELECT id, session_data, timestamp 
            FROM session_log 
            WHERE user_id = :user_id AND agent = 'ClaudeCode'
            ORDER BY timestamp DESC
            LIMIT :limit
        """
        
        result = await db.execute(query, {"user_id": user_id, "limit": limit})
        executions = result.fetchall()
        
        return ExecutionListResponse(
            executions=[
                {
                    "id": e.id,
                    "prompt_preview": e.session_data.get("prompt", "")[:100] + "..." 
                        if len(e.session_data.get("prompt", "")) > 100 
                        else e.session_data.get("prompt", ""),
                    "timestamp": e.timestamp.isoformat(),
                    "model": e.session_data.get("model", "unknown")
                }
                for e in executions
            ]
        )
        
    except Exception as e:
        logger.error(f"Error in list_claude_code_executions: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/execution/{execution_id}", 
            response_model=ExecutionDetailResponse,
            summary="Get Claude Code Execution Details",
            description="Get detailed information about a specific Claude Code execution")
async def get_claude_code_execution(
    execution_id: str,
    db: AsyncSession = Depends(get_db), 
    api_key: str = Depends(get_api_key)
):
    """
    Get details of a specific Claude Code execution
    
    Returns detailed information about a specific Claude Code execution, including:
    - The submitted prompt
    - Claude's response
    - Execution timestamp
    - Conversation ID for follow-ups
    """
    try:
        session = await db.get(SessionLog, execution_id)
        if not session or session.agent != "ClaudeCode":
            raise HTTPException(status_code=404, detail="Claude Code execution not found")
            
        return ExecutionDetailResponse(
            id=session.id,
            user_id=session.user_id,
            prompt=session.session_data.get("prompt", ""),
            response=session.session_data.get("response", {}),
            model=session.session_data.get("model", "unknown"),
            timestamp=session.timestamp.isoformat(),
            conversation_id=session.session_data.get("conversation_id")
        )
        
    except Exception as e:
        logger.error(f"Error in get_claude_code_execution: {str(e)}")
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/conversation/{conversation_id}", 
             response_model=ClaudeCodeResponse,
             summary="Continue Claude Code Conversation",
             description="Continue an existing Claude Code conversation")
async def continue_claude_code_conversation(
    conversation_id: str,
    prompt: str = Body(..., embed=True),
    user_id: str = Body(..., embed=True),
    system_prompt: Optional[str] = Body(None, embed=True),
    model: str = Body("claude-3-sonnet-20240229", embed=True),
    tools: Optional[List[Dict[str, Any]]] = Body(None, embed=True),
    tool_choice: Optional[Union[str, Dict[str, Any]]] = Body(None, embed=True),
    temperature: Optional[float] = Body(0.7, embed=True),
    top_p: Optional[float] = Body(0.9, embed=True),
    db: AsyncSession = Depends(get_db), 
    api_key: str = Depends(get_api_key)
):
    """
    Continue an existing Claude Code conversation
    
    This endpoint sends a follow-up prompt to an existing Claude conversation and
    returns the response. It also logs the request and response for later retrieval.
    
    - The prompt is sent to the specified Claude model with the provided conversation ID
    - The response includes Claude's response and the same conversation ID for further follow-ups
    - Results are stored for later retrieval
    """
    try:
        execution_id = str(uuid.uuid4())
        timestamp = datetime.utcnow()
        
        # Prepare the request to Claude API
        claude_request = {
            "model": model,
            "conversation_id": conversation_id,
            "temperature": temperature,
            "top_p": top_p,
            "max_tokens": 4096,  # Default max tokens
            "messages": [
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        }
        
        # Add system prompt if provided
        if system_prompt:
            claude_request["system"] = system_prompt
        
        # Add tools if provided
        if tools:
            claude_request["tools"] = tools
        
        # Add tool choice if provided
        if tool_choice:
            claude_request["tool_choice"] = tool_choice
        
        # Call Claude API
        claude_response = await call_claude_api(claude_request)
        
        # Log the request and response
        session_log = SessionLog(
            id=execution_id,
            user_id=user_id,
            agent="ClaudeCode",
            session_data={
                "prompt": prompt,
                "system_prompt": system_prompt,
                "model": model,
                "response": claude_response,
                "conversation_id": conversation_id,
                "timestamp": timestamp.isoformat(),
                "is_continuation": True
            },
            timestamp=timestamp
        )
        db.add(session_log)
        await db.commit()
        
        return ClaudeCodeResponse(
            execution_id=execution_id,
            conversation_id=conversation_id,
            response=claude_response
        )
        
    except Exception as e:
        logger.error(f"Error in continue_claude_code_conversation: {str(e)}")
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=str(e))