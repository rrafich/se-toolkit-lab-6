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
import re
from pathlib import Path
from typing import Any


def load_env() -> dict[str, str]:
    """Load environment variables from .env.agent.secret and .env.docker.secret."""
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
    
    # Also load LMS_API_KEY from .env.docker.secret if not already set
    if "LMS_API_KEY" not in env:
        docker_env_file = ".env.docker.secret"
        if os.path.exists(docker_env_file):
            with open(docker_env_file) as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    if "=" not in line:
                        continue
                    key, _, value = line.partition("=")
                    if key.strip() == "LMS_API_KEY":
                        env["LMS_API_KEY"] = value.strip().strip('"').strip("'")
                        break
    
    # Environment variables override file values
    for key in ["LLM_API_KEY", "LLM_API_BASE", "LLM_MODEL", "LMS_API_KEY", "AGENT_API_BASE_URL"]:
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


def query_api(method: str, path: str, body: str = None, api_key: str = None, api_base: str = None) -> dict[str, Any]:
    """Call the backend API and return the response.
    
    Args:
        method: HTTP method (GET, POST, etc.)
        path: API endpoint path (e.g., '/items/')
        body: Optional JSON request body for POST/PUT requests
        api_key: LMS API key for authentication
        api_base: Base URL for the API
        
    Returns:
        Dict with 'status_code' and 'body' or 'error'
    """
    if not api_base:
        api_base = "http://localhost:42002"  # Default to caddy proxy
    
    # Ensure path starts with /
    if not path.startswith("/"):
        path = "/" + path
    
    url = f"{api_base}{path}"
    
    headers = {
        "Content-Type": "application/json",
    }
    
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    
    data = None
    if body:
        data = body.encode("utf-8")
    
    try:
        req = urllib.request.Request(url, data=data, headers=headers, method=method.upper())
        
        with urllib.request.urlopen(req, timeout=30) as response:
            response_body = response.read().decode("utf-8")
            status_code = response.status
            
            # Try to parse as JSON
            try:
                parsed_body = json.loads(response_body)
            except json.JSONDecodeError:
                parsed_body = response_body
            
            return {
                "success": True,
                "status_code": status_code,
                "body": parsed_body
            }
    
    except urllib.error.HTTPError as e:
        error_body = e.read().decode() if e.fp else ""
        try:
            error_body = json.loads(error_body)
        except json.JSONDecodeError:
            pass
        return {
            "success": False,
            "status_code": e.code,
            "error": f"HTTP {e.code}: {error_body}"
        }
    except urllib.error.URLError as e:
        return {
            "success": False,
            "error": f"Cannot reach API: {e.reason}"
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Error querying API: {str(e)}"
        }


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
        },
        {
            "type": "function",
            "function": {
                "name": "query_api",
                "description": "Call the backend API to fetch data or check system status. Use this for questions about current data, item counts, scores, or system information.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "method": {
                            "type": "string",
                            "description": "HTTP method (GET, POST, PUT, DELETE)"
                        },
                        "path": {
                            "type": "string",
                            "description": "API endpoint path (e.g., '/items/', '/scores/')"
                        },
                        "body": {
                            "type": "string",
                            "description": "Optional JSON request body for POST/PUT requests"
                        }
                    },
                    "required": ["method", "path"]
                }
            }
        }
    ]


def execute_tool(tool_name: str, args: dict[str, Any], env: dict[str, str] = None) -> dict[str, Any]:
    """Execute a tool and return the result."""
    if env is None:
        env = {}
    
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
    
    elif tool_name == "query_api":
        method = args.get("method", "GET")
        path = args.get("path", "")
        body = args.get("body")
        api_key = env.get("LMS_API_KEY", "")
        api_base = env.get("AGENT_API_BASE_URL", "")
        result = query_api(method, path, body, api_key, api_base)
        return result
    
    else:
        return {"success": False, "error": f"Unknown tool: {tool_name}"}


def extract_source(content: str) -> str:
    """Extract source reference from the LLM's answer."""
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


def call_llm_with_tools(
    question: str,
    api_key: str,
    api_base: str,
    model: str,
    env: dict[str, str],
    max_iterations: int = 10
) -> tuple[str, str, list[dict[str, Any]]]:
    """Call the LLM with tool support and return (answer, source, tool_calls).
    
    Args:
        question: The user's question
        api_key: API key for authentication
        api_base: Base URL of the API
        model: Model name to use
        env: Environment variables dict
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
    system_prompt = """You are a helpful assistant that answers questions by reading project documentation and querying the system API.

IMPORTANT: For any question about this project, wiki, or repository:
1. ALWAYS use list_files first to discover what files exist
2. ALWAYS use read_file to find the actual content - do NOT rely on your training data
3. The project documentation may differ from general knowledge - verify by reading files
4. Include a source reference at the end: "Source: wiki/filename.md#section"

For questions about current data, item counts, scores, or system status:
1. Use query_api to fetch real-time data from the backend

You have access to these tools:
- read_file: Read a file from the project repository
- list_files: List files and directories at a given path
- query_api: Call the backend API to fetch data or check system status

Think step by step. Always verify information by reading actual files or querying the API."""

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
            tool_result = execute_tool(tool_name, args, env)
            
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
                elif "body" in tool_result:
                    result_content = json.dumps(tool_result["body"])
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
    answer, source, tool_calls = call_llm_with_tools(question, api_key, api_base, model, env)
    
    # Output JSON result
    result = {
        "answer": answer,
        "source": source,
        "tool_calls": tool_calls
    }
    
    print(json.dumps(result))
    sys.exit(0)


if __name__ == "__main__":
    main()
