#!/usr/bin/env python3
"""
Claude Code Terminal Interface

A command-line interface for running code with Claude Code.
"""

import argparse
import json
import os
import sys
import requests
from typing import Dict, Any, Optional, List, Union
import httpx
import asyncio
from rich.console import Console
from rich.syntax import Syntax
from rich.markdown import Markdown
from rich.panel import Panel
from rich import print as rprint

# Configure rich console
console = Console()

class ClaudeCodeTerminal:
    """Terminal interface for Claude Code"""
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        api_base: Optional[str] = None,
        model: str = "claude-3-sonnet-20240229",
        temperature: float = 0.7,
        top_p: float = 0.9,
        json_output: bool = False
    ):
        """
        Initialize the Claude Code terminal interface
        
        Args:
            api_key: Anthropic API key. If not provided, will look for ANTHROPIC_API_KEY env var
            api_base: Anthropic API base URL. If not provided, will use the default
            model: Claude model to use
            temperature: Temperature for generation
            top_p: Top-p for generation
            json_output: Whether to output results as JSON
        """
        # Use provided API key or get from environment
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not self.api_key:
            console.print("[bold red]Error:[/bold red] No API key provided. Set the ANTHROPIC_API_KEY environment variable or pass it with --api-key")
            sys.exit(1)
        
        # Use provided API base or get from environment, or use default
        self.api_base = api_base or os.environ.get("ANTHROPIC_API_BASE", "https://api.anthropic.com")
        
        # Set model and generation parameters
        self.model = model
        self.temperature = temperature
        self.top_p = top_p
        
        # Whether to output results as JSON
        self.json_output = json_output
        
        # Conversation history - for future use with interactive mode
        self.conversation_id = None
        self.messages = []
    
    async def call_claude_api(self, prompt: str, system_prompt: Optional[str] = None) -> Dict[str, Any]:
        """
        Call the Claude API and return the response.
        
        Args:
            prompt: Prompt to send to Claude
            system_prompt: Optional system prompt
            
        Returns:
            Claude API response
        """
        # Prepare the request to Claude API
        claude_request = {
            "model": self.model,
            "temperature": self.temperature,
            "top_p": self.top_p,
            "max_tokens": 4096,
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
        
        # Add conversation ID if we have one (for continuing conversations)
        if self.conversation_id:
            claude_request["conversation_id"] = self.conversation_id
        
        async with httpx.AsyncClient(timeout=300) as client:  # 5-minute timeout
            try:
                response = await client.post(
                    f"{self.api_base}/v1/messages",
                    headers={
                        "x-api-key": self.api_key,
                        "anthropic-version": "2023-06-01",
                        "content-type": "application/json"
                    },
                    json=claude_request
                )
                response.raise_for_status()
                return response.json()
            except httpx.RequestError as e:
                console.print(f"[bold red]Error:[/bold red] {str(e)}")
                sys.exit(1)
            except httpx.HTTPStatusError as e:
                console.print(f"[bold red]Error:[/bold red] {e.response.status_code} - {e.response.text}")
                sys.exit(1)
    
    def print_claude_response(self, response: Dict[str, Any]) -> None:
        """
        Print Claude's response.
        
        Args:
            response: Claude API response
        """
        # Save conversation ID for future use
        self.conversation_id = response.get("conversation_id")
        
        # Print JSON output if requested
        if self.json_output:
            print(json.dumps(response, indent=2))
            return
        
        # Otherwise, print formatted output
        console.print("\n[bold green]Claude's Response:[/bold green]")
        console.print("=" * 80)
        
        # Process content blocks
        for content_item in response.get("content", []):
            if content_item.get("type") == "text":
                md = Markdown(content_item.get("text", ""))
                console.print(md)
            elif content_item.get("type") == "code":
                code_text = content_item.get("text", "")
                language = "python"  # Default to Python
                
                # Try to detect language from code block
                first_line = code_text.strip().split("\n")[0]
                if first_line.startswith("```"):
                    language = first_line[3:].strip()
                    code_text = "\n".join(code_text.strip().split("\n")[1:])
                if code_text.endswith("```"):
                    code_text = "\n".join(code_text.strip().split("\n")[:-1])
                
                syntax = Syntax(code_text, language, theme="monokai", line_numbers=True)
                console.print(Panel(syntax, border_style="green"))
        
        # Print usage information
        usage = response.get("usage", {})
        input_tokens = usage.get("input_tokens", 0)
        output_tokens = usage.get("output_tokens", 0)
        total_tokens = input_tokens + output_tokens
        
        console.print("\n[dim]Token Usage:[/dim]")
        console.print(f"[dim]Input: {input_tokens} | Output: {output_tokens} | Total: {total_tokens}[/dim]")
    
    async def process_code(self, prompt: str, system_prompt: Optional[str] = None) -> None:
        """
        Process code with Claude Code.
        
        Args:
            prompt: Prompt to send to Claude
            system_prompt: Optional system prompt
        """
        console.print("[bold]Sending request to Claude...[/bold]")
        response = await self.call_claude_api(prompt, system_prompt)
        self.print_claude_response(response)
    
    async def process_file(self, file_path: str, system_prompt: Optional[str] = None) -> None:
        """
        Process a file with Claude Code.
        
        Args:
            file_path: Path to the file to process
            system_prompt: Optional system prompt
        """
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                code = f.read()
            
            # Create prompt with the file content
            prompt = f"I have the following code from {os.path.basename(file_path)}. Please analyze it, suggest improvements, and explain what it does:\n\n```\n{code}\n```"
            
            await self.process_code(prompt, system_prompt)
        except FileNotFoundError:
            console.print(f"[bold red]Error:[/bold red] File not found: {file_path}")
            sys.exit(1)
        except Exception as e:
            console.print(f"[bold red]Error:[/bold red] {str(e)}")
            sys.exit(1)

def parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description="Claude Code Terminal Interface")
    
    # Input options
    input_group = parser.add_mutually_exclusive_group()
    input_group.add_argument("-f", "--file", help="Execute code from FILE")
    input_group.add_argument("-c", "--code", help="Execute CODE directly")
    
    # API options
    parser.add_argument("--api-key", help="Anthropic API key (defaults to ANTHROPIC_API_KEY env var)")
    parser.add_argument("--api-base", help="Anthropic API base URL (defaults to https://api.anthropic.com)")
    
    # Model options
    parser.add_argument("--model", default="claude-3-sonnet-20240229",
                        help="Claude model to use (default: claude-3-sonnet-20240229)")
    parser.add_argument("--temperature", type=float, default=0.7,
                        help="Temperature for generation (default: 0.7)")
    parser.add_argument("--top-p", type=float, default=0.9,
                        help="Top-p for generation (default: 0.9)")
    parser.add_argument("--system-prompt", help="System prompt for Claude")
    
    # Output options
    parser.add_argument("-j", "--json", action="store_true",
                        help="Output result as JSON")
    
    return parser.parse_args()

async def main():
    """Main entry point"""
    args = parse_args()
    
    # Initialize Claude Code terminal
    claude_code = ClaudeCodeTerminal(
        api_key=args.api_key,
        api_base=args.api_base,
        model=args.model,
        temperature=args.temperature,
        top_p=args.top_p,
        json_output=args.json
    )
    
    if args.file:
        await claude_code.process_file(args.file, args.system_prompt)
    elif args.code:
        await claude_code.process_code(args.code, args.system_prompt)
    else:
        # Read from stdin if no file or code is provided
        console.print("[bold]Reading from stdin. Enter your prompt and press Ctrl+D when finished:[/bold]")
        prompt = sys.stdin.read().strip()
        if prompt:
            await claude_code.process_code(prompt, args.system_prompt)
        else:
            console.print("[bold red]Error:[/bold red] No input provided")
            sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())