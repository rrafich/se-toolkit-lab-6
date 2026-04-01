# Task 2 Plan: The Documentation Agent

## Overview

This plan describes the implementation of the Documentation Agent with tools (`read_file`, `list_files`) and an agentic loop that enables the LLM to navigate and read project documentation.

## Tools to Implement

### read_file

**Purpose:** Read a file from the project repository.

**Parameters:**
- `path` (string, required) — relative path from project root (e.g., `wiki/git-workflow.md`)

**Returns:**
- On success: `{ "success": true, "content": "<file contents>" }`
- On error: `{ "success": false, "error": "<error message>" }`

**Security:**
- Block `../` path traversal attempts
- Validate resolved path is within project root directory
- Return error for paths outside project boundary

**Implementation:**
```python
def read_file(path: str) -> dict[str, Any]:
    # Check for path traversal
    if ".." in path or path.startswith("/"):
        return {"success": False, "error": "Invalid path: path traversal not allowed"}
    
    # Resolve and validate path
    project_root = get_project_root()
    file_path = project_root / path
    
    try:
        file_path.resolve().relative_to(project_root.resolve())
    except ValueError:
        return {"success": False, "error": "Invalid path: outside project directory"}
    
    # Read file (truncate if > 8000 chars)
    content = file_path.read_text()
    return {"success": True, "content": content}
```

### list_files

**Purpose:** List files and directories at a given path.

**Parameters:**
- `path` (string, required) — relative directory path from project root

**Returns:**
- On success: `{ "success": true, "entries": ["file: example.md", "dir: images"] }`
- On error: `{ "success": false, "error": "<error message>" }`

**Security:**
- Same path traversal protection as `read_file`
- Only list directories within project root

**Implementation:**
```python
def list_files(path: str) -> dict[str, Any]:
    # Same security checks as read_file
    
    dir_path = project_root / path
    entries = []
    for entry in sorted(dir_path.iterdir()):
        entry_type = "dir" if entry.is_dir() else "file"
        entries.append(f"{entry_type}: {entry.name}")
    
    return {"success": True, "entries": entries}
```

## Tool Schema Format (OpenAI Function Calling)

Tools are registered with the LLM using OpenAI-compatible function calling schemas:

```json
{
  "type": "function",
  "function": {
    "name": "read_file",
    "description": "Read a file from the project repository...",
    "parameters": {
      "type": "object",
      "properties": {
        "path": {
          "type": "string",
          "description": "Relative path from project root"
        }
      },
      "required": ["path"]
    }
  }
}
```

## Agentic Loop Design

The agentic loop enables iterative tool use:

```
1. Send user question + tool schemas to LLM
2. Parse LLM response:
   - If tool_calls present:
     a. Execute each tool
     b. Append tool results as "tool" role messages
     c. Send updated conversation back to LLM
     d. Repeat (max 10 iterations)
   - If no tool_calls (text answer):
     a. Extract source reference from answer
     b. Return (answer, source, tool_calls_log)
3. If max iterations reached, return partial answer
```

**Loop Implementation:**
```python
def call_llm_with_tools(question, api_key, api_base, model, env, max_iterations=10):
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": question}
    ]
    
    tool_calls_log = []
    
    for iteration in range(max_iterations):
        # Call LLM with tools
        response = call_api(messages, tools=get_tool_schemas())
        message = response["choices"][0]["message"]
        
        # Check for tool calls
        if not message.get("tool_calls"):
            return message["content"], extract_source(message["content"]), tool_calls_log
        
        # Execute tools and append results
        for tool_call in message["tool_calls"]:
            result = execute_tool(tool_call["function"]["name"], tool_call["function"]["arguments"])
            tool_calls_log.append({"tool": ..., "args": ..., "result": result})
            
            # Append to messages for next iteration
            messages.append({"role": "assistant", "tool_calls": [tool_call]})
            messages.append({"role": "tool", "tool_call_id": ..., "content": format_result(result)})
    
    return "Max iterations reached", "", tool_calls_log
```

## System Prompt Strategy

The system prompt guides the LLM to:

1. **Use tools in order:** `list_files` first to discover files, then `read_file` for content
2. **Verify information:** Always check actual files rather than relying on training data
3. **Include source references:** Format as `Source: wiki/filename.md#section`
4. **Use query_api for system data:** For questions about current database state, scores, etc.

**System Prompt:**
```
You are a helpful assistant that answers questions by reading project documentation and querying the system API.

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

Think step by step. Always verify information by reading actual files or querying the API.
```

## Source Extraction

The `extract_source()` function uses regex to find source references in the LLM's answer:

```python
def extract_source(content: str) -> str:
    # Pattern 1: Explicit "Source: wiki/..." format
    match = re.search(r'[Ss]ource:\s*(wiki/[\w\-/]+\.md(?:#[\w\-]+)?)', content)
    if match:
        return match.group(1)
    
    # Pattern 2: Any wiki/...md reference
    match = re.search(r'(wiki/[\w\-/]+\.md(?:#[\w\-]+)?)', content, re.IGNORECASE)
    if match:
        return match.group(1)
    
    return ""
```

## Output Format

```json
{
  "answer": "Edit the conflicting file, choose which changes to keep, then stage and commit.",
  "source": "wiki/git-workflow.md#resolving-merge-conflicts",
  "tool_calls": [
    {
      "tool": "list_files",
      "args": {"path": "wiki"},
      "result": {"success": true, "entries": ["file: git-workflow.md", ...]}
    },
    {
      "tool": "read_file",
      "args": {"path": "wiki/git-workflow.md"},
      "result": {"success": true, "content": "..."}
    }
  ]
}
```

## Security Considerations

1. **Path Traversal Prevention:**
   - Check for `..` in paths
   - Validate resolved paths are within project root using `relative_to()`
   - Return error for any path outside project boundary

2. **File Access Control:**
   - Only allow reading files (not directories) with `read_file`
   - Only allow listing directories (not files) with `list_files`
   - Truncate file contents to 8000 chars to prevent context overflow

## Testing Strategy

Tests will verify:
1. Basic questions work (may not need tools)
2. Documentation questions use `read_file` tool
3. Directory listing questions use `list_files` tool
4. Merge conflict questions find correct wiki source
5. Git workflow questions return proper source references
