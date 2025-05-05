#!/usr/bin/env python3
"""
Test script for Claude Code integration in EchoMind API
"""

import os
import sys
import json
import requests
import argparse
from typing import Dict, Any, Optional
from datetime import datetime

def test_claude_code_api(base_url: str, api_key: str, prompt: str, verbose: bool = False) -> None:
    """
    Test the Claude Code API endpoints.
    
    Args:
        base_url: Base URL of the EchoMind API
        api_key: API key for authentication
        prompt: Prompt to send to Claude Code
        verbose: Whether to print verbose output
    """
    # Make sure base_url doesn't end with a slash
    if base_url.endswith('/'):
        base_url = base_url[:-1]
    
    # Headers for all requests
    headers = {
        "Content-Type": "application/json",
        "X-API-Key": api_key
    }
    
    print("Testing Claude Code API...\n")
    
    # Test the ping endpoint
    try:
        response = requests.get(f"{base_url}/claude-code/ping", headers=headers)
        response.raise_for_status()
        print("✅ Ping endpoint is working")
        if verbose:
            print(f"Response: {json.dumps(response.json(), indent=2)}\n")
    except requests.exceptions.RequestException as e:
        print(f"❌ Ping endpoint failed: {str(e)}")
        if verbose and hasattr(e, 'response') and e.response:
            print(f"Response: {e.response.text}\n")
        sys.exit(1)
    
    # Test the execute endpoint
    try:
        request_data = {
            "user_id": "test_user",
            "prompt": prompt,
            "model": "claude-3-sonnet-20240229",
            "temperature": 0.7
        }
        
        print(f"Sending prompt to Claude Code: {prompt[:50]}...")
        response = requests.post(
            f"{base_url}/claude-code/execute", 
            headers=headers,
            json=request_data
        )
        response.raise_for_status()
        result = response.json()
        print("✅ Execute endpoint is working")
        
        # Print Claude's response
        claude_response = result.get("response", {})
        print("\nClaude's Response:")
        print("-----------------")
        
        if "content" in claude_response:
            for content_item in claude_response.get("content", []):
                if content_item.get("type") == "text":
                    print(content_item.get("text", ""))
                elif content_item.get("type") == "code":
                    print("\n```")
                    print(content_item.get("text", ""))
                    print("```\n")
        else:
            print("No content in Claude's response")
        
        if verbose:
            print("\nFull API Response:")
            print("-----------------")
            print(f"{json.dumps(result, indent=2)}\n")
        
        # Store execution ID for later
        execution_id = result.get("execution_id")
        conversation_id = result.get("conversation_id")
        
        # Test the get execution details endpoint
        if execution_id:
            print(f"\nTesting execution details for ID: {execution_id}")
            response = requests.get(
                f"{base_url}/claude-code/execution/{execution_id}", 
                headers=headers
            )
            response.raise_for_status()
            print("✅ Get execution details endpoint is working")
            if verbose:
                print(f"Response: {json.dumps(response.json(), indent=2)}\n")
        
        # Test the list executions endpoint
        print("\nTesting list executions endpoint")
        response = requests.get(
            f"{base_url}/claude-code/executions/test_user", 
            headers=headers
        )
        response.raise_for_status()
        print("✅ List executions endpoint is working")
        if verbose:
            print(f"Response: {json.dumps(response.json(), indent=2)}\n")
        
        # Test conversation continuation if we have a conversation ID
        if conversation_id:
            print(f"\nTesting conversation continuation with ID: {conversation_id}")
            
            continuation_prompt = "Can you refine the previous response to make it more efficient?"
            request_data = {
                "prompt": continuation_prompt,
                "user_id": "test_user",
                "model": "claude-3-sonnet-20240229",
                "temperature": 0.7
            }
            
            print(f"Sending follow-up prompt: {continuation_prompt}")
            response = requests.post(
                f"{base_url}/claude-code/conversation/{conversation_id}", 
                headers=headers,
                json=request_data
            )
            response.raise_for_status()
            result = response.json()
            print("✅ Conversation continuation endpoint is working")
            
            # Print Claude's response
            claude_response = result.get("response", {})
            print("\nClaude's Follow-up Response:")
            print("---------------------------")
            
            if "content" in claude_response:
                for content_item in claude_response.get("content", []):
                    if content_item.get("type") == "text":
                        print(content_item.get("text", ""))
                    elif content_item.get("type") == "code":
                        print("\n```")
                        print(content_item.get("text", ""))
                        print("```\n")
            else:
                print("No content in Claude's response")
            
            if verbose:
                print("\nFull API Response:")
                print("-----------------")
                print(f"{json.dumps(result, indent=2)}\n")
        
    except requests.exceptions.RequestException as e:
        print(f"❌ Execute endpoint failed: {str(e)}")
        if verbose and hasattr(e, 'response') and e.response:
            print(f"Response: {e.response.text}\n")
        sys.exit(1)
    
    print("\nAll tests completed successfully! 🎉")

def main():
    parser = argparse.ArgumentParser(description="Test the Claude Code API integration in EchoMind")
    parser.add_argument("--base-url", default="http://localhost:8000", help="Base URL of the EchoMind API")
    parser.add_argument("--api-key", default=os.environ.get("ECHOMIND_API_KEY"), help="API key for authentication")
    parser.add_argument("--prompt", default="Write a Python function to calculate the factorial of a number", help="Prompt to send to Claude Code")
    parser.add_argument("--verbose", "-v", action="store_true", help="Print verbose output")
    
    args = parser.parse_args()
    
    if not args.api_key:
        parser.error("API key is required. Provide it with --api-key or set the ECHOMIND_API_KEY environment variable.")
    
    test_claude_code_api(args.base_url, args.api_key, args.prompt, args.verbose)

if __name__ == "__main__":
    main()