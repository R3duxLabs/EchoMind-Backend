"""
Context Window Management

This module provides utilities for managing the context window
for LLM interactions, including:
- Tracking token counts
- Truncating and summarizing conversation history
- Prioritizing important context
"""

from typing import Dict, List, Optional, Any, Union, Tuple
import re
import json
from datetime import datetime

from app.logging_config import get_logger

logger = get_logger(__name__)

# Approximate token counts for different models
TOKEN_LIMITS = {
    "gpt-3.5-turbo": 4096,
    "gpt-3.5-turbo-16k": 16384,
    "gpt-4": 8192,
    "gpt-4-32k": 32768,
    "gpt-4-0613": 8192,
    "gpt-4-0125-preview": 128000,  # as of early 2024
    "claude-2": 100000,
    "claude-instant": 100000
}

# Default token limit if model not specified
DEFAULT_TOKEN_LIMIT = 4096

class TokenCounter:
    """
    Utility for estimating token counts
    
    This is a very approximate estimator. For production use,
    consider using a proper tokenizer like tiktoken.
    """
    
    @staticmethod
    def estimate_tokens(text: str) -> int:
        """
        Estimate the number of tokens in a text
        
        This is a very rough approximation based on words and punctuation.
        For accurate counts, use a proper tokenizer.
        
        Args:
            text: Text to estimate tokens for
            
        Returns:
            int: Estimated token count
        """
        if not text:
            return 0
            
        # Count words (roughly 0.75 tokens per word)
        words = len(re.findall(r'\b\w+\b', text))
        
        # Count punctuation and special characters (roughly 1 token each)
        punctuation = len(re.findall(r'[^\w\s]', text))
        
        # Count whitespace (roughly 0.25 tokens per whitespace)
        whitespace = len(re.findall(r'\s+', text))
        
        # Combine for final estimate
        return int(words * 0.75 + punctuation + whitespace * 0.25)
    
    @staticmethod
    def estimate_messages_tokens(messages: List[Dict[str, str]]) -> int:
        """
        Estimate the number of tokens in a list of messages
        
        Args:
            messages: List of chat messages
            
        Returns:
            int: Estimated token count
        """
        # Base token cost for message formatting
        # Each message has a small overhead
        base_tokens = len(messages) * 4
        
        # Sum up tokens in each message
        for message in messages:
            content = message.get("content", "")
            role = message.get("role", "")
            name = message.get("name", "")
            
            base_tokens += TokenCounter.estimate_tokens(content)
            base_tokens += len(role) // 4  # Approximate cost of role
            base_tokens += len(name) // 4 if name else 0  # Approximate cost of name
        
        return base_tokens

class ContextWindowManager:
    """
    Manages the context window for LLM interactions
    
    This class helps ensure that messages sent to the LLM don't
    exceed the context window, optimizing for the most important context.
    """
    
    def __init__(
        self,
        model_name: str = "gpt-4",
        max_tokens: Optional[int] = None,
        buffer_tokens: int = 1000
    ):
        """
        Initialize a context window manager
        
        Args:
            model_name: Name of the model to manage context for
            max_tokens: Maximum token limit (overrides model default)
            buffer_tokens: Buffer to leave for the response
        """
        self.model_name = model_name
        self.max_tokens = max_tokens or TOKEN_LIMITS.get(model_name, DEFAULT_TOKEN_LIMIT)
        self.buffer_tokens = buffer_tokens
        self.logger = get_logger(__name__)
        
        # Calculate effective token limit (reserving buffer for response)
        self.effective_limit = self.max_tokens - self.buffer_tokens
        
        self.logger.info(
            f"Initialized context window manager",
            extra={
                "model_name": model_name,
                "max_tokens": self.max_tokens,
                "buffer_tokens": buffer_tokens,
                "effective_limit": self.effective_limit
            }
        )
    
    def fit_to_context_window(
        self,
        messages: List[Dict[str, str]],
        include_system_prompt: bool = True,
        important_indices: Optional[List[int]] = None
    ) -> List[Dict[str, str]]:
        """
        Ensure messages fit within the context window
        
        Truncates or summarizes messages if necessary to fit within the token limit.
        Prioritizes important messages (e.g., system prompt, recent messages).
        
        Args:
            messages: List of messages to fit
            include_system_prompt: Whether to prioritize system prompts
            important_indices: Indices of messages to prioritize (0-based)
            
        Returns:
            List[Dict[str, str]]: Messages that fit within the context window
        """
        # Estimate token count
        estimated_tokens = TokenCounter.estimate_messages_tokens(messages)
        
        # If already within limit, return as is
        if estimated_tokens <= self.effective_limit:
            return messages
        
        self.logger.info(
            f"Messages exceed context window, trimming",
            extra={
                "estimated_tokens": estimated_tokens,
                "effective_limit": self.effective_limit,
                "overflow": estimated_tokens - self.effective_limit,
                "message_count": len(messages)
            }
        )
        
        # Prepare to prioritize messages
        system_messages = []
        user_messages = []
        assistant_messages = []
        other_messages = []
        
        # Important messages to preserve (set by caller)
        important_messages = []
        
        # Organize messages by type
        for i, message in enumerate(messages):
            role = message.get("role", "")
            
            # Check if this is an important message to preserve
            if important_indices and i in important_indices:
                important_messages.append(message)
                continue
            
            if role == "system":
                system_messages.append(message)
            elif role == "user":
                user_messages.append(message)
            elif role == "assistant":
                assistant_messages.append(message)
            else:
                other_messages.append(message)
        
        # Strategy: First, try truncating (dropping oldest messages)
        # While preserving system prompt and important messages
        
        # Start with required messages
        result = []
        
        # Always include system messages if specified
        if include_system_prompt:
            result.extend(system_messages)
        
        # Always include important messages
        result.extend(important_messages)
        
        # Estimate tokens used so far
        tokens_used = TokenCounter.estimate_messages_tokens(result)
        
        # Add recent user and assistant messages, maintaining conversation flow
        # We interleave them in reverse chronological order (newest first)
        remaining = []
        
        # Pair user and assistant messages for proper conversation flow
        paired_messages = []
        user_idx, assistant_idx = len(user_messages) - 1, len(assistant_messages) - 1
        
        while user_idx >= 0 or assistant_idx >= 0:
            # Add user message if available
            if user_idx >= 0:
                paired_messages.append(user_messages[user_idx])
                user_idx -= 1
            
            # Add assistant response if available
            if assistant_idx >= 0:
                paired_messages.append(assistant_messages[assistant_idx])
                assistant_idx -= 1
                
        # Add as many paired messages as will fit
        for message in paired_messages:
            message_tokens = TokenCounter.estimate_tokens(message.get("content", "")) + 4
            if tokens_used + message_tokens <= self.effective_limit:
                remaining.append(message)
                tokens_used += message_tokens
            else:
                break
        
        # Add other messages if space permits
        for message in other_messages:
            message_tokens = TokenCounter.estimate_tokens(message.get("content", "")) + 4
            if tokens_used + message_tokens <= self.effective_limit:
                remaining.append(message)
                tokens_used += message_tokens
            else:
                break
        
        # Combine all messages, with remaining messages in the original order
        # We need to preserve original order to maintain conversation flow
        original_order = []
        processed_indices = set()
        
        # First add result messages (system and important) which maintain their positions
        for i, message in enumerate(messages):
            if message.get("role") == "system" and include_system_prompt:
                original_order.append(message)
                processed_indices.add(i)
            elif important_indices and i in important_indices:
                original_order.append(message)
                processed_indices.add(i)
        
        # Then add remaining messages in original order
        for i, message in enumerate(messages):
            if i not in processed_indices and message in remaining:
                original_order.append(message)
        
        # If we still have too many tokens, add a summary message
        final_tokens = TokenCounter.estimate_messages_tokens(original_order)
        if final_tokens > self.effective_limit:
            # Create a summary message
            summary = self._create_history_summary(original_order)
            
            # Replace all but system and last few messages with summary
            preserved_count = min(4, len(original_order))  # Keep at most 4 recent messages
            
            # Keep system messages
            new_messages = [m for m in original_order if m.get("role") == "system"]
            
            # Add summary message
            new_messages.append({
                "role": "system",
                "content": f"Earlier conversation summary: {summary}"
            })
            
            # Add most recent messages
            new_messages.extend(original_order[-preserved_count:])
            
            # Return truncated conversation with summary
            return new_messages
            
        # Return reorganized messages
        return original_order
    
    def _create_history_summary(self, messages: List[Dict[str, str]]) -> str:
        """
        Create a summary of conversation history
        
        Args:
            messages: List of messages to summarize
            
        Returns:
            str: Summary of the conversation
        """
        # Extract key points from each message
        points = []
        
        for message in messages:
            role = message.get("role", "")
            content = message.get("content", "")
            
            if role == "system":
                # Skip system messages from summary
                continue
                
            # Extract a snippet to represent this message
            if len(content) > 100:
                snippet = content[:100] + "..."
            else:
                snippet = content
                
            points.append(f"{role}: {snippet}")
        
        # Combine into a summary (simple for now)
        summary = "This conversation covered: "
        summary += "; ".join(points[:3])  # Just include first few points
        summary += f" (plus {len(points) - 3} more messages)" if len(points) > 3 else ""
        
        return summary
    
    def prioritize_context(
        self,
        context_items: List[Dict[str, Any]],
        max_tokens: Optional[int] = None,
        prioritization_fn: Optional[Callable[[Dict[str, Any]], float]] = None
    ) -> List[Dict[str, Any]]:
        """
        Prioritize context items to fit within token limit
        
        Args:
            context_items: List of context items to prioritize
            max_tokens: Maximum tokens to use for context
            prioritization_fn: Function to assign priority to items
            
        Returns:
            List[Dict[str, Any]]: Prioritized context items
        """
        if not context_items:
            return []
            
        # Use provided max_tokens or a fraction of the effective limit
        if max_tokens is None:
            max_tokens = int(self.effective_limit * 0.3)  # Use up to 30% for context
        
        # Serialize items to estimate tokens
        serialized_items = []
        for item in context_items:
            if isinstance(item, dict):
                serialized = json.dumps(item)
            elif isinstance(item, str):
                serialized = item
            else:
                serialized = str(item)
            serialized_items.append((item, serialized))
        
        # Calculate token counts for each item
        items_with_tokens = [
            (item, serialized, TokenCounter.estimate_tokens(serialized))
            for item, serialized in serialized_items
        ]
        
        # If we have a prioritization function, apply it
        if prioritization_fn:
            # Sort by priority (higher first) and then recency
            items_with_tokens.sort(key=lambda x: (prioritization_fn(x[0]), x[0].get("timestamp", "")), reverse=True)
        else:
            # Default: sort by recency if available, otherwise original order
            items_with_tokens.sort(
                key=lambda x: x[0].get("timestamp", datetime.min.isoformat()),
                reverse=True
            )
        
        # Select items that fit within token limit
        result = []
        tokens_used = 0
        
        for item, _, tokens in items_with_tokens:
            if tokens_used + tokens <= max_tokens:
                result.append(item)
                tokens_used += tokens
            else:
                break
        
        return result

def truncate_conversation(
    messages: List[Dict[str, str]],
    model_name: str = "gpt-4",
    max_tokens: Optional[int] = None
) -> List[Dict[str, str]]:
    """
    Convenience function to truncate conversation to fit context window
    
    Args:
        messages: List of messages to truncate
        model_name: Name of the model
        max_tokens: Maximum tokens for context window
        
    Returns:
        List[Dict[str, str]]: Truncated conversation
    """
    manager = ContextWindowManager(model_name=model_name, max_tokens=max_tokens)
    return manager.fit_to_context_window(messages)