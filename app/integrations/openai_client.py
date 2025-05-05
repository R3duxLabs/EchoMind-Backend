"""
OpenAI API Client

This module provides a client for the OpenAI API, including:
- Authentication and configuration
- Calling various models (GPT-4, GPT-3.5, etc.)
- Handling rate limits and retries
- Managing response parsing
"""

import asyncio
import json
import os
import time
from typing import Dict, List, Optional, Any, Union, Callable, Awaitable
from datetime import datetime, timedelta

import httpx
from dotenv import load_dotenv
from pydantic import BaseModel, Field

from app.logging_config import get_logger

# Load environment variables
load_dotenv()

logger = get_logger(__name__)

# OpenAI API configuration
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_ORG_ID = os.getenv("OPENAI_ORG_ID", "")
OPENAI_API_BASE = os.getenv("OPENAI_API_BASE", "https://api.openai.com/v1")

# Default values
DEFAULT_MODEL = os.getenv("OPENAI_DEFAULT_MODEL", "gpt-4-0613")
DEFAULT_MAX_TOKENS = int(os.getenv("OPENAI_DEFAULT_MAX_TOKENS", "1024"))
DEFAULT_TEMPERATURE = float(os.getenv("OPENAI_DEFAULT_TEMPERATURE", "0.7"))

# Rate limiting
MAX_REQUESTS_PER_MINUTE = int(os.getenv("OPENAI_MAX_REQUESTS_PER_MINUTE", "60"))
TOKEN_LIMIT_WARNING_THRESHOLD = 0.8  # Log warning when token usage exceeds 80% of limit

class OpenAIMessage(BaseModel):
    """
    Message format for OpenAI Chat API
    """
    role: str = Field(..., description="Role of the message sender (system, user, assistant)")
    content: str = Field(..., description="Content of the message")
    name: Optional[str] = Field(None, description="Name of the sender (optional)")
    
    class Config:
        schema_extra = {
            "example": {
                "role": "user",
                "content": "Hello, how are you?",
                "name": "John"
            }
        }

class TokenUsage(BaseModel):
    """
    Token usage statistics
    """
    prompt_tokens: int = Field(..., description="Tokens used in the prompt")
    completion_tokens: int = Field(..., description="Tokens used in the completion")
    total_tokens: int = Field(..., description="Total tokens used")
    
    class Config:
        schema_extra = {
            "example": {
                "prompt_tokens": 100,
                "completion_tokens": 50,
                "total_tokens": 150
            }
        }

class APIResponse(BaseModel):
    """
    Response model for OpenAI API requests
    """
    success: bool = Field(..., description="Whether the request was successful")
    data: Optional[Any] = Field(None, description="Response data if successful")
    error: Optional[str] = Field(None, description="Error message if request failed")
    usage: Optional[TokenUsage] = Field(None, description="Token usage statistics")
    model: Optional[str] = Field(None, description="Model used for the request")
    
    class Config:
        schema_extra = {
            "example": {
                "success": True,
                "data": {
                    "id": "chatcmpl-123",
                    "object": "chat.completion",
                    "created": 1677858242,
                    "model": "gpt-4-0613",
                    "choices": [
                        {
                            "message": {
                                "role": "assistant",
                                "content": "Hello! How can I help you today?"
                            },
                            "index": 0,
                            "finish_reason": "stop"
                        }
                    ]
                },
                "usage": {
                    "prompt_tokens": 100,
                    "completion_tokens": 50,
                    "total_tokens": 150
                },
                "model": "gpt-4-0613"
            }
        }

class OpenAIClient:
    """
    Client for interacting with the OpenAI API
    """
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        org_id: Optional[str] = None,
        api_base: Optional[str] = None,
        default_model: Optional[str] = None,
        default_max_tokens: Optional[int] = None,
        default_temperature: Optional[float] = None
    ):
        """
        Initialize the OpenAI client
        
        Args:
            api_key: OpenAI API key (default: from environment)
            org_id: OpenAI organization ID (default: from environment)
            api_base: OpenAI API base URL (default: from environment)
            default_model: Default model to use (default: from environment)
            default_max_tokens: Default max tokens (default: from environment)
            default_temperature: Default temperature (default: from environment)
        """
        self.api_key = api_key or OPENAI_API_KEY
        self.org_id = org_id or OPENAI_ORG_ID
        self.api_base = api_base or OPENAI_API_BASE
        self.default_model = default_model or DEFAULT_MODEL
        self.default_max_tokens = default_max_tokens or DEFAULT_MAX_TOKENS
        self.default_temperature = default_temperature or DEFAULT_TEMPERATURE
        
        if not self.api_key:
            logger.warning("No OpenAI API key provided. API calls will fail.")
        
        # Configure the HTTP client with timeouts and retries
        self.client = httpx.AsyncClient(
            timeout=60.0,  # 60 second timeout
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
        )
        
        if self.org_id:
            self.client.headers["OpenAI-Organization"] = self.org_id
        
        # Rate limiting
        self.request_timestamps = []
        
        logger.info(
            "OpenAI client initialized",
            extra={
                "api_base": self.api_base,
                "default_model": self.default_model,
                "default_max_tokens": self.default_max_tokens,
                "default_temperature": self.default_temperature
            }
        )
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
    
    async def close(self):
        """Close the HTTP client session"""
        await self.client.aclose()
    
    async def _check_rate_limit(self):
        """
        Check if we're within the rate limit
        
        Waits if necessary to stay within rate limits.
        """
        now = time.time()
        
        # Remove timestamps older than 1 minute
        self.request_timestamps = [ts for ts in self.request_timestamps if now - ts < 60]
        
        # If we're at the rate limit, wait until we can make another request
        if len(self.request_timestamps) >= MAX_REQUESTS_PER_MINUTE:
            oldest_timestamp = min(self.request_timestamps)
            wait_time = 60 - (now - oldest_timestamp)
            
            if wait_time > 0:
                logger.warning(
                    f"Rate limit reached. Waiting {wait_time:.2f} seconds",
                    extra={
                        "rate_limit": MAX_REQUESTS_PER_MINUTE,
                        "wait_time": wait_time
                    }
                )
                await asyncio.sleep(wait_time)
                # Recursive call after waiting to check again
                await self._check_rate_limit()
    
    async def _make_request(
        self,
        endpoint: str,
        data: Dict[str, Any],
        retry_count: int = 0,
        max_retries: int = 3
    ) -> APIResponse:
        """
        Make a request to the OpenAI API
        
        Args:
            endpoint: API endpoint path
            data: Request data
            retry_count: Current retry count
            max_retries: Maximum number of retries
            
        Returns:
            APIResponse: Response from the API
        """
        await self._check_rate_limit()
        
        url = f"{self.api_base}/{endpoint}"
        
        try:
            # Add timestamp for rate limiting
            self.request_timestamps.append(time.time())
            
            # Make the request
            start_time = time.time()
            response = await self.client.post(url, json=data)
            duration = time.time() - start_time
            
            # Log request
            logger.info(
                f"OpenAI API request to {endpoint}",
                extra={
                    "endpoint": endpoint,
                    "duration": duration,
                    "model": data.get("model", self.default_model),
                    "status_code": response.status_code
                }
            )
            
            # Check for success
            if response.status_code == 200:
                # Parse response
                response_data = response.json()
                
                # Extract usage
                usage = None
                if "usage" in response_data:
                    usage = TokenUsage(
                        prompt_tokens=response_data["usage"]["prompt_tokens"],
                        completion_tokens=response_data["usage"]["completion_tokens"],
                        total_tokens=response_data["usage"]["total_tokens"]
                    )
                    
                    # Log usage
                    logger.info(
                        "OpenAI API token usage",
                        extra={
                            "endpoint": endpoint,
                            "model": data.get("model", self.default_model),
                            "prompt_tokens": usage.prompt_tokens,
                            "completion_tokens": usage.completion_tokens,
                            "total_tokens": usage.total_tokens
                        }
                    )
                
                # Return successful response
                return APIResponse(
                    success=True,
                    data=response_data,
                    usage=usage,
                    model=data.get("model", self.default_model)
                )
                
            else:
                # Handle error responses
                error_data = response.json()
                error_message = error_data.get("error", {}).get("message", "Unknown error")
                
                # Handle rate limiting
                if response.status_code == 429:
                    # Server asked us to retry after a delay
                    retry_after = response.headers.get("Retry-After")
                    
                    if retry_after:
                        retry_after = float(retry_after)
                    else:
                        # Default to exponential backoff
                        retry_after = min(2 ** retry_count, 60)
                    
                    logger.warning(
                        f"OpenAI API rate limit reached. Retrying after {retry_after} seconds",
                        extra={
                            "endpoint": endpoint,
                            "retry_count": retry_count,
                            "retry_after": retry_after
                        }
                    )
                    
                    if retry_count < max_retries:
                        await asyncio.sleep(retry_after)
                        return await self._make_request(
                            endpoint=endpoint,
                            data=data,
                            retry_count=retry_count + 1,
                            max_retries=max_retries
                        )
                
                # Log error
                logger.error(
                    f"OpenAI API error: {error_message}",
                    extra={
                        "endpoint": endpoint,
                        "status_code": response.status_code,
                        "error": error_message
                    }
                )
                
                # Return error response
                return APIResponse(
                    success=False,
                    error=error_message,
                    model=data.get("model", self.default_model)
                )
                
        except Exception as e:
            logger.error(
                f"Error calling OpenAI API: {str(e)}",
                extra={
                    "endpoint": endpoint,
                    "error": str(e)
                },
                exc_info=True
            )
            
            # Retry on network errors
            if retry_count < max_retries:
                retry_after = min(2 ** retry_count, 60)
                logger.info(
                    f"Retrying OpenAI API request after {retry_after} seconds",
                    extra={
                        "endpoint": endpoint,
                        "retry_count": retry_count,
                        "retry_after": retry_after
                    }
                )
                await asyncio.sleep(retry_after)
                return await self._make_request(
                    endpoint=endpoint,
                    data=data,
                    retry_count=retry_count + 1,
                    max_retries=max_retries
                )
            
            # Return error response
            return APIResponse(
                success=False,
                error=f"Error calling OpenAI API: {str(e)}",
                model=data.get("model", self.default_model)
            )
    
    async def chat_completion(
        self,
        messages: List[Union[OpenAIMessage, Dict[str, str]]],
        model: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        frequency_penalty: Optional[float] = None,
        presence_penalty: Optional[float] = None,
        top_p: Optional[float] = None,
        stop: Optional[Union[str, List[str]]] = None,
        response_format: Optional[Dict[str, str]] = None,
        stream: bool = False
    ) -> APIResponse:
        """
        Create a chat completion
        
        Args:
            messages: List of messages in the conversation
            model: Model to use
            max_tokens: Maximum tokens in the response
            temperature: Temperature for sampling
            frequency_penalty: Frequency penalty
            presence_penalty: Presence penalty
            top_p: Top p sampling parameter
            stop: Stop sequences
            response_format: Format to return the response in (e.g. JSON)
            stream: Whether to stream the response
            
        Returns:
            APIResponse: Response from the API
        """
        # Process messages to ensure they're in the right format
        processed_messages = []
        for message in messages:
            if isinstance(message, OpenAIMessage):
                processed_messages.append(message.dict(exclude_none=True))
            elif isinstance(message, dict):
                # Validate message has required fields
                if "role" not in message or "content" not in message:
                    logger.error(
                        "Invalid message format: missing required fields",
                        extra={"message": message}
                    )
                    return APIResponse(
                        success=False,
                        error="Invalid message format: missing required fields"
                    )
                processed_messages.append(message)
            else:
                logger.error(
                    "Invalid message format: must be OpenAIMessage or dict",
                    extra={"message": message}
                )
                return APIResponse(
                    success=False,
                    error="Invalid message format: must be OpenAIMessage or dict"
                )
        
        # Build request data
        data = {
            "model": model or self.default_model,
            "messages": processed_messages,
            "stream": stream
        }
        
        # Add optional parameters if provided
        if max_tokens is not None:
            data["max_tokens"] = max_tokens
        elif self.default_max_tokens:
            data["max_tokens"] = self.default_max_tokens
            
        if temperature is not None:
            data["temperature"] = temperature
        elif self.default_temperature:
            data["temperature"] = self.default_temperature
            
        if frequency_penalty is not None:
            data["frequency_penalty"] = frequency_penalty
            
        if presence_penalty is not None:
            data["presence_penalty"] = presence_penalty
            
        if top_p is not None:
            data["top_p"] = top_p
            
        if stop is not None:
            data["stop"] = stop
            
        if response_format is not None:
            data["response_format"] = response_format
        
        # Make the request
        return await self._make_request("chat/completions", data)
    
    async def simple_completion(
        self,
        prompt: str,
        system_message: Optional[str] = None,
        model: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None
    ) -> str:
        """
        Simple wrapper for chat completion that just returns the text
        
        Args:
            prompt: User prompt text
            system_message: Optional system message
            model: Model to use
            max_tokens: Maximum tokens in the response
            temperature: Temperature for sampling
            
        Returns:
            str: Response text or error message
        """
        # Build messages
        messages = []
        
        if system_message:
            messages.append({"role": "system", "content": system_message})
            
        messages.append({"role": "user", "content": prompt})
        
        # Make the request
        response = await self.chat_completion(
            messages=messages,
            model=model,
            max_tokens=max_tokens,
            temperature=temperature
        )
        
        # Return the response text or error
        if response.success:
            choices = response.data.get("choices", [])
            if choices:
                return choices[0]["message"]["content"]
            else:
                return "No response content"
        else:
            return f"Error: {response.error}"
    
    async def create_embedding(
        self,
        text: Union[str, List[str]],
        model: Optional[str] = None
    ) -> APIResponse:
        """
        Create embeddings for text
        
        Args:
            text: Text or list of texts to embed
            model: Model to use (default: text-embedding-ada-002)
            
        Returns:
            APIResponse: Response from the API
        """
        # Ensure text is a list
        if isinstance(text, str):
            input_texts = [text]
        else:
            input_texts = text
        
        # Build request data
        data = {
            "model": model or "text-embedding-ada-002",
            "input": input_texts
        }
        
        # Make the request
        return await self._make_request("embeddings", data)
    
    async def moderation(
        self,
        text: Union[str, List[str]],
        model: Optional[str] = None
    ) -> APIResponse:
        """
        Check text for harmful content
        
        Args:
            text: Text or list of texts to check
            model: Moderation model to use
            
        Returns:
            APIResponse: Response from the API
        """
        # Ensure text is a list
        if isinstance(text, str):
            input_texts = [text]
        else:
            input_texts = text
        
        # Build request data
        data = {
            "input": input_texts
        }
        
        if model:
            data["model"] = model
        
        # Make the request
        return await self._make_request("moderations", data)

# Create a default client instance
default_client = OpenAIClient()

# Convenience functions that use the default client
async def chat_completion(*args, **kwargs) -> APIResponse:
    """Convenience function for chat completions using the default client"""
    return await default_client.chat_completion(*args, **kwargs)

async def simple_completion(*args, **kwargs) -> str:
    """Convenience function for simple completions using the default client"""
    return await default_client.simple_completion(*args, **kwargs)

async def create_embedding(*args, **kwargs) -> APIResponse:
    """Convenience function for embeddings using the default client"""
    return await default_client.create_embedding(*args, **kwargs)

async def moderation(*args, **kwargs) -> APIResponse:
    """Convenience function for moderation using the default client"""
    return await default_client.moderation(*args, **kwargs)