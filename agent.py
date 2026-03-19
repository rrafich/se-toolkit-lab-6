#!/usr/bin/env python3
"""Agent CLI with tools and agentic loop.

Usage:
    uv run agent.py "Your question here"

Output:
    JSON to stdout: {"answer": "...", "source": "...", "tool_calls": [...]}
    Errors to stderr
"""

import json
import os
import sys
import urllib.request
import urllib.error
from pathlib import Path
from typing import Any


def load_env() -> dict[str, str]:
    """Load environment variables from .env.agent.secret."""
    env = {}
    env_file = ".env.agent.secret"
    
    if os.path.exists(env_file):
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" not in line:
                    continue
                key, _, value = line.partition("=")
                env[key.strip()] = value.strip().strip('"').strip("'")
    
    for key in ["LLM_API_KEY", "LLM_API_BASE", "LLM_MODEL"]:
        if key in os.environ:
            env[key] = os.environ[key]
    
    return env


def get_project_root() -> Path:
    """Get the project root directory."""
    return Path(__file__).parent.resolve()


def read_file(path: str) -> dict[str, Any]:
    """Read a file from the project repository.
    
    Args:
        path: Relative path from project root
        
    Returns:
        Dict with 'success' and 'content' or 'error'
    """
    # Security: prevent path traversal
    if ".." in path or path.startswith("/"):
        return {"success": False, "error": "Invalid path: path traversal not allowed"}
    
    project_root = get_project_root()
    file_path = project_root / path
    
    # Ensure the path is within project root
    try:
        file_path.resolve().relative_to(project_root.resolve())
    except ValueError:
        return {"success": False, "error": "Invalid path: outside project directory"}
    
    if not file_path.exists():
        return {"success": False, "error": f"File not found: {path}"}
    
    if not file_path.is_file():
        return {"success": False, "error": f"Not a file: {path}"}
    
    try:
        content = file_path.read_text()
        # Truncate if too long (LLM context limit)
        max_length = 8000
        if len(content) > max_length:
            content = content[:max_length] + "\n\n... [truncated]"
        return {"success": True, "content": content}
    except Exception as e:
        return {"success": False, "error": f"Error reading file: {e}"}


def list_files(path: str) -> dict[str, Any]:
    """List files and directories at a given path.
    
    Args:
        path: Relative directory path from project root
        
    Returns:
        Dict with 'success' and 'entries' or 'error'
    """
    # Security: prevent path traversal
    if ".." in path or path.startswith("/"):
        return {"success": False, "error": "Invalid path: path traversal not allowed"}
    
    project_root = get_project_root()
    dir_path = project_root / path
    
    # Ensure the path is within project root
    try:
        dir_path.resolve().relative_to(project_root.resolve())
    except ValueError:
        return {"success": False, "error": "Invalid path: outside project directory"}
    
    if not dir_path.exists():
        return {"success": False, "error": f"Directory not found: {path}"}
    
    if not dir_path.is_dir():
        return {"success": False, "error": f"Not a directory: {path}"}
    
    try:
        entries = []
        for entry in sorted(dir_path.iterdir()):
            entry_type = "dir" if entry.is_dir() else "file"
            entries.append(f"{entry_type}: {entry.name}")
        return {"success": True, "entries": entries}
    except Exception as e:
        return {"success": False, "error": f"Error listing directory: {e}"}


def get_tool_schemas() -> list[dict[str, Any]]:
    """Return tool schemas for OpenAI function calling."""
    return [
        {
            "type": "function",
            "function": {
                "name": "read_file",
                "description": "Read a file from the project repository. Use this to read documentation, source code, or configuration files.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Relative path from project root (e.g., 'wiki/git-workflow.md')"
                        }
                    },
                    "required": ["path"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "list_files",
                "description": "List files and directories at a given path. Use this to discover what files exist in a directory.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Relative directory path from project root (e.g., 'wiki')"
                        }
                    },
                    "required": ["path"]
                }
            }
        }
    ]


def execute_tool(tool_name: str, args: dict[str, Any]) -> dict[str, Any]:
    """Execute a tool and return the result."""
    if tool_name == "read_file":
        path = args.get("path", "")
        result = read_file(path)
        if result.get("success"):
            return {"success": True, "content": result.get("content", "")}
        else:
            return {"success": False, "error": result.get("error", "Unknown error")}
    
    elif tool_name == "list_files":
        path = args.get("path", "")
        result = list_files(path)
        if result.get("success"):
            return {"success": True, "entries": result.get("entries", [])}
        else:
            return {"success": False, "error": result.get("error", "Unknown error")}
    
    else:
        return {"success": False, "error": f"Unknown tool: {tool_name}"}


def call_llm_with_tools(
    question: str,
    api_key: str,
    api_base: str,
    model: str,
    max_iterations: int = 10
) -> tuple[str, str, list[dict[str, Any]]]:
    """Call the LLM with tool support and return (answer, source, tool_calls).
    
    Args:
        question: The user's question
        api_key: API key for authentication
        api_base: Base URL of the API
        model: Model name to use
        max_iterations: Maximum tool call iterations
        
    Returns:
        Tuple of (answer, source, tool_calls_list)
    """
    url = f"{api_base}/chat/completions"
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    
    # System prompt
    system_prompt = """You are a helpful assistant that answers questions by reading project documentation.

IMPORTANT: For any question about this project, wiki, or repository:
1. ALWAYS use list_files first to discover what files exist
2. ALWAYS use read_file to find the actual content - do NOT rely on your training data
3. The project documentation may differ from general knowledge - verify by reading files
4. Include a source reference at the end: "Source: wiki/filename.md#section"

You have access to these tools:
- read_file: Read a file from the project repository
- list_files: List files and directories at a given path

Think step by step. Always verify information by reading actual files."""

    # Initialize conversation
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": question}
    ]
    
    tool_calls_log = []
    
    for iteration in range(max_iterations):
        # Build request body
        body = {
            "model": model,
            "messages": messages,
            "tools": get_tool_schemas(),
            "tool_choice": "auto",
            "temperature": 0.0,
        }
        
        data = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers=headers, method="POST")
        
        try:
            with urllib.request.urlopen(req, timeout=60) as response:
                result = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            error_body = e.read().decode() if e.fp else ""
            print(f"API error {e.code}: {error_body}", file=sys.stderr)
            sys.exit(1)
        except urllib.error.URLError as e:
            print(f"Cannot reach API: {e.reason}", file=sys.stderr)
            sys.exit(1)
        
        # Get the assistant message
        choices = result.get("choices", [])
        if not choices:
            print("No choices in LLM response", file=sys.stderr)
            sys.exit(1)
        
        message = choices[0].get("message", {})
        content = message.get("content") or ""
        tool_calls = message.get("tool_calls") or []
        
        # If no tool calls, we have the final answer
        if not tool_calls:
            # Extract source from content (look for file references)
            source = extract_source(content)
            return content, source, tool_calls_log
        
        # Execute each tool call
        for tool_call in tool_calls:
            function = tool_call.get("function", {})
            tool_name = function.get("name", "")
            args_str = function.get("arguments", "{}")
            
            try:
                args = json.loads(args_str)
            except json.JSONDecodeError:
                args = {}
            
            # Execute the tool
            tool_result = execute_tool(tool_name, args)
            
            # Log the tool call
            tool_call_log = {
                "tool": tool_name,
                "args": args,
                "result": tool_result
            }
            tool_calls_log.append(tool_call_log)
            
            # Format result for LLM
            if tool_result.get("success"):
                if "content" in tool_result:
                    result_content = tool_result["content"]
                elif "entries" in tool_result:
                    result_content = "\n".join(tool_result["entries"])
                else:
                    result_content = str(tool_result)
            else:
                result_content = f"Error: {tool_result.get('error', 'Unknown error')}"
            
            # Add tool result to messages
            messages.append({
                "role": "assistant",
                "content": None,
                "tool_calls": [tool_call]
            })
            
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.get("id", ""),
                "content": result_content
            })
    
    # Max iterations reached
    return "Max tool call iterations reached.", "", tool_calls_log


def extract_source(content: str) -> str:
    """Extract source reference from the LLM's answer."""
    import re
    
    # First, look for explicit "Source: wiki/..." pattern
    source_pattern = r'[Ss]ource:\s*(wiki/[\w\-/]+\.md(?:#[\w\-]+)?)'
    match = re.search(source_pattern, content)
    if match:
        return match.group(1)
    
    # Second, look for any wiki/...md pattern
    pattern = r'(wiki/[\w\-/]+\.md(?:#[\w\-]+)?)'
    match = re.search(pattern, content, re.IGNORECASE)
    if match:
        return match.group(1)
    
    # Default: return empty if no source found
    return ""


def main() -> None:
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: uv run agent.py \"Your question\"", file=sys.stderr)
        sys.exit(1)
    
    question = sys.argv[1]
    
    # Load configuration
    env = load_env()
    
    api_key = env.get("LLM_API_KEY", "")
    api_base = env.get("LLM_API_BASE", "")
    model = env.get("LLM_MODEL", "qwen3-coder-plus")
    
    if not api_key:
        print("Missing LLM_API_KEY in .env.agent.secret", file=sys.stderr)
        sys.exit(1)
    
    if not api_base:
        print("Missing LLM_API_BASE in .env.agent.secret", file=sys.stderr)
        sys.exit(1)
    
    # Call the LLM with tools
    answer, source, tool_calls = call_llm_with_tools(question, api_key, api_base, model)
    
    # Output JSON result
    result = {
        "answer": answer,
        "source": source,
        "tool_calls": tool_calls
    }
    
    print(json.dumps(result))


if __name__ == "__main__":
    main()