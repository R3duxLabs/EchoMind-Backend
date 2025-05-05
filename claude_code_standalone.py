#!/usr/bin/env python3
"""
Claude Code Standalone Application

A standalone application for running code with Claude Code.
This can be used independently of the EchoMind backend.
"""

import argparse
import json
import os
import sys
import requests
import time
import tempfile
import subprocess
from typing import Dict, Any, Optional, List, Union
import httpx
import asyncio
from rich.console import Console
from rich.syntax import Syntax
from rich.markdown import Markdown
from rich.panel import Panel
from rich.progress import Progress
from rich import print as rprint
import tkinter as tk
from tkinter import ttk, scrolledtext, filedialog, messagebox
import textwrap

# Configure rich console
console = Console()

class ClaudeCodeAPI:
    """Interface for interacting with Claude API"""
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        api_base: Optional[str] = None,
        model: str = "claude-3-sonnet-20240229",
        temperature: float = 0.7,
        top_p: float = 0.9
    ):
        """
        Initialize the Claude Code API interface
        
        Args:
            api_key: Anthropic API key. If not provided, will look for ANTHROPIC_API_KEY env var
            api_base: Anthropic API base URL. If not provided, will use the default
            model: Claude model to use
            temperature: Temperature for generation
            top_p: Top-p for generation
        """
        # Use provided API key or get from environment
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError("No API key provided. Set the ANTHROPIC_API_KEY environment variable or pass it with --api-key")
        
        # Use provided API base or get from environment, or use default
        self.api_base = api_base or os.environ.get("ANTHROPIC_API_BASE", "https://api.anthropic.com")
        
        # Set model and generation parameters
        self.model = model
        self.temperature = temperature
        self.top_p = top_p
        
        # Conversation history
        self.conversation_id = None
        self.messages = []
    
    async def call_claude_api(self, prompt: str, system_prompt: Optional[str] = None, tools: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        """
        Call the Claude API and return the response.
        
        Args:
            prompt: Prompt to send to Claude
            system_prompt: Optional system prompt
            tools: Optional list of tools to provide to Claude
            
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
        
        # Add tools if provided
        if tools:
            claude_request["tools"] = tools
        
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
                raise RuntimeError(f"Request error: {str(e)}")
            except httpx.HTTPStatusError as e:
                raise RuntimeError(f"HTTP error {e.response.status_code}: {e.response.text}")

class ClaudeCodeCLI:
    """Command-line interface for Claude Code"""
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        api_base: Optional[str] = None,
        model: str = "claude-3-sonnet-20240229",
        temperature: float = 0.7,
        top_p: float = 0.9,
        json_output: bool = False,
        execute_code: bool = False
    ):
        """
        Initialize the Claude Code CLI
        
        Args:
            api_key: Anthropic API key
            api_base: Anthropic API base URL
            model: Claude model to use
            temperature: Temperature for generation
            top_p: Top-p for generation
            json_output: Whether to output results as JSON
            execute_code: Whether to execute generated code
        """
        self.api = ClaudeCodeAPI(
            api_key=api_key,
            api_base=api_base,
            model=model,
            temperature=temperature,
            top_p=top_p
        )
        
        self.json_output = json_output
        self.execute_code = execute_code
    
    def print_claude_response(self, response: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Print Claude's response.
        
        Args:
            response: Claude API response
            
        Returns:
            List of code blocks extracted from the response
        """
        # Save conversation ID for future use
        self.api.conversation_id = response.get("conversation_id")
        
        # Print JSON output if requested
        if self.json_output:
            print(json.dumps(response, indent=2))
            return []
        
        # Otherwise, print formatted output
        console.print("\n[bold green]Claude's Response:[/bold green]")
        console.print("=" * 80)
        
        # Process content blocks and collect code blocks
        code_blocks = []
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
                
                # Add to code blocks
                code_blocks.append({
                    "language": language,
                    "code": code_text
                })
        
        # Print usage information
        usage = response.get("usage", {})
        input_tokens = usage.get("input_tokens", 0)
        output_tokens = usage.get("output_tokens", 0)
        total_tokens = input_tokens + output_tokens
        
        console.print("\n[dim]Token Usage:[/dim]")
        console.print(f"[dim]Input: {input_tokens} | Output: {output_tokens} | Total: {total_tokens}[/dim]")
        
        return code_blocks
    
    def execute_python_code(self, code: str) -> None:
        """
        Execute Python code and print the output.
        
        Args:
            code: Python code to execute
        """
        if not self.execute_code:
            return
        
        console.print("\n[bold yellow]Executing Python code:[/bold yellow]")
        console.print("=" * 80)
        
        with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
            f.write(code)
            temp_file = f.name
        
        try:
            result = subprocess.run(
                [sys.executable, temp_file],
                capture_output=True,
                text=True,
                timeout=30  # 30-second timeout
            )
            
            if result.stdout:
                console.print("\n[bold green]Output:[/bold green]")
                console.print(result.stdout)
            
            if result.stderr:
                console.print("\n[bold red]Error:[/bold red]")
                console.print(result.stderr)
            
            if not result.stdout and not result.stderr:
                console.print("\n[dim]No output[/dim]")
            
            if result.returncode != 0:
                console.print(f"\n[bold red]Process exited with code {result.returncode}[/bold red]")
        except subprocess.TimeoutExpired:
            console.print("\n[bold red]Execution timed out after 30 seconds[/bold red]")
        except Exception as e:
            console.print(f"\n[bold red]Error executing code: {str(e)}[/bold red]")
        finally:
            try:
                os.unlink(temp_file)
            except:
                pass
    
    async def process_code(self, prompt: str, system_prompt: Optional[str] = None) -> None:
        """
        Process code with Claude Code.
        
        Args:
            prompt: Prompt to send to Claude
            system_prompt: Optional system prompt
        """
        with Progress() as progress:
            task = progress.add_task("[cyan]Sending request to Claude...", total=1)
            
            try:
                response = await self.api.call_claude_api(prompt, system_prompt)
                progress.update(task, completed=1)
                
                code_blocks = self.print_claude_response(response)
                
                # Execute Python code if requested and we have Python code blocks
                python_blocks = [block for block in code_blocks if block["language"] == "python"]
                if self.execute_code and python_blocks:
                    self.execute_python_code(python_blocks[0]["code"])
            except Exception as e:
                progress.update(task, completed=1)
                console.print(f"[bold red]Error:[/bold red] {str(e)}")
                sys.exit(1)
    
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

class ClaudeCodeGUI:
    """GUI interface for Claude Code"""
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        api_base: Optional[str] = None,
        model: str = "claude-3-sonnet-20240229",
        temperature: float = 0.7,
        top_p: float = 0.9,
        execute_code: bool = False
    ):
        """
        Initialize the Claude Code GUI
        
        Args:
            api_key: Anthropic API key
            api_base: Anthropic API base URL
            model: Claude model to use
            temperature: Temperature for generation
            top_p: Top-p for generation
            execute_code: Whether to execute generated code
        """
        self.api = ClaudeCodeAPI(
            api_key=api_key,
            api_base=api_base,
            model=model,
            temperature=temperature,
            top_p=top_p
        )
        
        self.execute_code = execute_code
        self.conversation_id = None
        self.code_blocks = []
        
        # Set up the GUI
        self.root = tk.Tk()
        self.root.title("Claude Code")
        self.root.geometry("1000x800")
        
        # Create the main frame
        self.main_frame = ttk.Frame(self.root)
        self.main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Create the top frame for input
        self.top_frame = ttk.Frame(self.main_frame)
        self.top_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Create the prompt label and text area
        ttk.Label(self.top_frame, text="Prompt:").pack(anchor=tk.W)
        self.prompt_text = scrolledtext.ScrolledText(self.top_frame, height=8)
        self.prompt_text.pack(fill=tk.X)
        
        # Create the middle frame for options
        self.middle_frame = ttk.Frame(self.main_frame)
        self.middle_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Create the options frame
        self.options_frame = ttk.LabelFrame(self.middle_frame, text="Options")
        self.options_frame.pack(fill=tk.X)
        
        # Create the model selector
        ttk.Label(self.options_frame, text="Model:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        self.model_var = tk.StringVar(value=model)
        self.model_combo = ttk.Combobox(
            self.options_frame,
            textvariable=self.model_var,
            values=["claude-3-opus-20240229", "claude-3-sonnet-20240229", "claude-3-haiku-20240307"]
        )
        self.model_combo.grid(row=0, column=1, sticky=tk.W, padx=5, pady=5)
        
        # Create the temperature slider
        ttk.Label(self.options_frame, text="Temperature:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        self.temperature_var = tk.DoubleVar(value=temperature)
        self.temperature_scale = ttk.Scale(
            self.options_frame,
            from_=0.0,
            to=1.0,
            orient=tk.HORIZONTAL,
            variable=self.temperature_var,
            length=200
        )
        self.temperature_scale.grid(row=1, column=1, sticky=tk.W, padx=5, pady=5)
        self.temperature_label = ttk.Label(self.options_frame, text=f"{temperature:.1f}")
        self.temperature_label.grid(row=1, column=2, sticky=tk.W)
        self.temperature_scale.bind("<Motion>", self.update_temperature_label)
        
        # Create the execute code checkbox
        self.execute_var = tk.BooleanVar(value=execute_code)
        self.execute_check = ttk.Checkbutton(
            self.options_frame,
            text="Execute Python code",
            variable=self.execute_var
        )
        self.execute_check.grid(row=2, column=0, columnspan=2, sticky=tk.W, padx=5, pady=5)
        
        # Create the buttons frame
        self.buttons_frame = ttk.Frame(self.middle_frame)
        self.buttons_frame.pack(fill=tk.X, pady=(10, 0))
        
        # Create the submit button
        self.submit_button = ttk.Button(
            self.buttons_frame,
            text="Submit",
            command=self.submit_prompt
        )
        self.submit_button.pack(side=tk.LEFT, padx=5)
        
        # Create the load file button
        self.load_button = ttk.Button(
            self.buttons_frame,
            text="Load File",
            command=self.load_file
        )
        self.load_button.pack(side=tk.LEFT, padx=5)
        
        # Create the clear button
        self.clear_button = ttk.Button(
            self.buttons_frame,
            text="Clear",
            command=self.clear_all
        )
        self.clear_button.pack(side=tk.LEFT, padx=5)
        
        # Create the bottom frame for output
        self.bottom_frame = ttk.Frame(self.main_frame)
        self.bottom_frame.pack(fill=tk.BOTH, expand=True)
        
        # Create the response label and text area
        ttk.Label(self.bottom_frame, text="Response:").pack(anchor=tk.W)
        self.response_text = scrolledtext.ScrolledText(self.bottom_frame)
        self.response_text.pack(fill=tk.BOTH, expand=True)
        
        # Create the status bar
        self.status_var = tk.StringVar(value="Ready")
        self.status_bar = ttk.Label(
            self.root,
            textvariable=self.status_var,
            relief=tk.SUNKEN,
            anchor=tk.W
        )
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)
    
    def update_temperature_label(self, event):
        """Update the temperature label when the slider is moved"""
        self.temperature_label.config(text=f"{self.temperature_var.get():.1f}")
    
    def submit_prompt(self):
        """Submit the prompt to Claude"""
        prompt = self.prompt_text.get("1.0", tk.END).strip()
        if not prompt:
            messagebox.showerror("Error", "Please enter a prompt")
            return
        
        # Get the options
        model = self.model_var.get()
        temperature = self.temperature_var.get()
        execute_code = self.execute_var.get()
        
        # Update the API parameters
        self.api.model = model
        self.api.temperature = temperature
        
        # Disable the submit button and update status
        self.submit_button.config(state=tk.DISABLED)
        self.status_var.set("Sending request to Claude...")
        self.root.update()
        
        # Run the API call in a separate thread
        self.root.after(100, self.run_api_call, prompt, execute_code)
    
    def run_api_call(self, prompt, execute_code):
        """Run the API call in a separate thread"""
        try:
            # Create asyncio event loop and run the API call
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            response = loop.run_until_complete(self.api.call_claude_api(prompt))
            loop.close()
            
            # Process and display the response
            self.display_response(response)
            
            # Execute code if requested
            if execute_code:
                self.execute_python_code()
            
            # Update status
            self.status_var.set("Ready")
        except Exception as e:
            self.status_var.set("Error")
            messagebox.showerror("Error", str(e))
        finally:
            # Re-enable the submit button
            self.submit_button.config(state=tk.NORMAL)
    
    def display_response(self, response):
        """Display Claude's response"""
        # Save conversation ID for future use
        self.api.conversation_id = response.get("conversation_id")
        
        # Clear the response text
        self.response_text.delete("1.0", tk.END)
        
        # Process content blocks and collect code blocks
        self.code_blocks = []
        for content_item in response.get("content", []):
            if content_item.get("type") == "text":
                self.response_text.insert(tk.END, content_item.get("text", "") + "\n\n")
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
                
                # Add to response text
                self.response_text.insert(tk.END, f"\n```{language}\n{code_text}\n```\n\n")
                
                # Add to code blocks
                self.code_blocks.append({
                    "language": language,
                    "code": code_text
                })
        
        # Scroll to the top
        self.response_text.see("1.0")
    
    def execute_python_code(self):
        """Execute Python code and show the output"""
        python_blocks = [block for block in self.code_blocks if block["language"] == "python"]
        if not python_blocks:
            messagebox.showinfo("Execute Code", "No Python code found in the response")
            return
        
        code = python_blocks[0]["code"]
        
        with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
            f.write(code)
            temp_file = f.name
        
        try:
            result = subprocess.run(
                [sys.executable, temp_file],
                capture_output=True,
                text=True,
                timeout=30  # 30-second timeout
            )
            
            # Create output message
            output = ""
            if result.stdout:
                output += f"Output:\n{result.stdout}\n\n"
            
            if result.stderr:
                output += f"Error:\n{result.stderr}\n\n"
            
            if not result.stdout and not result.stderr:
                output = "No output"
            
            if result.returncode != 0:
                output += f"Process exited with code {result.returncode}\n"
            
            # Show output in a dialog
            messagebox.showinfo("Code Execution Result", output)
        except subprocess.TimeoutExpired:
            messagebox.showerror("Error", "Execution timed out after 30 seconds")
        except Exception as e:
            messagebox.showerror("Error", f"Error executing code: {str(e)}")
        finally:
            try:
                os.unlink(temp_file)
            except:
                pass
    
    def load_file(self):
        """Load a file and create a prompt with its contents"""
        file_path = filedialog.askopenfilename(
            title="Select a file",
            filetypes=[
                ("Python files", "*.py"),
                ("Text files", "*.txt"),
                ("All files", "*.*")
            ]
        )
        
        if not file_path:
            return
        
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                code = f.read()
            
            # Create prompt with the file content
            prompt = f"I have the following code from {os.path.basename(file_path)}. Please analyze it, suggest improvements, and explain what it does:\n\n```\n{code}\n```"
            
            # Set the prompt
            self.prompt_text.delete("1.0", tk.END)
            self.prompt_text.insert(tk.END, prompt)
        except Exception as e:
            messagebox.showerror("Error", f"Error loading file: {str(e)}")
    
    def clear_all(self):
        """Clear all text areas"""
        self.prompt_text.delete("1.0", tk.END)
        self.response_text.delete("1.0", tk.END)
        self.status_var.set("Ready")
    
    def run(self):
        """Run the GUI"""
        self.root.mainloop()

def parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description="Claude Code Standalone Application")
    
    # Mode selection
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument("--gui", action="store_true",
                           help="Run in GUI mode")
    mode_group.add_argument("--cli", action="store_true",
                           help="Run in CLI mode (default)")
    
    # Input options (CLI mode only)
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
                        help="Output result as JSON (CLI mode only)")
    parser.add_argument("-e", "--execute", action="store_true",
                        help="Execute generated Python code")
    
    return parser.parse_args()

async def main_cli(args):
    """Main entry point for CLI mode"""
    # Initialize Claude Code CLI
    claude_code = ClaudeCodeCLI(
        api_key=args.api_key,
        api_base=args.api_base,
        model=args.model,
        temperature=args.temperature,
        top_p=args.top_p,
        json_output=args.json,
        execute_code=args.execute
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

def main_gui(args):
    """Main entry point for GUI mode"""
    # Initialize Claude Code GUI
    claude_code = ClaudeCodeGUI(
        api_key=args.api_key,
        api_base=args.api_base,
        model=args.model,
        temperature=args.temperature,
        top_p=args.top_p,
        execute_code=args.execute
    )
    
    # Run the GUI
    claude_code.run()

def main():
    """Main entry point"""
    args = parse_args()
    
    # Run in GUI mode if requested
    if args.gui:
        main_gui(args)
    else:  # CLI mode
        asyncio.run(main_cli(args))

if __name__ == "__main__":
    main()