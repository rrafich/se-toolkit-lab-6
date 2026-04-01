# Agent Architecture

## Overview

This agent is a CLI tool that answers questions by calling an LLM (Qwen Code API) and using tools to read project documentation and query the system API.

## LLM Provider

- **Provider:** Qwen Code API (self-hosted on VM)
- **Model:** qwen3-coder-plus
- **API Base:** http://127.0.0.1:42006/v1
- **Authentication:** Bearer token from `.env.agent.secret`

## Tools

The agent has three tools that the LLM can call via function calling:

### read_file

Reads a file from the project repository.

- **Parameters:** `path` (string) — relative path from project root (e.g., `wiki/git-workflow.md`)
- **Security:** 
  - Blocks path traversal (`../`)
  - Validates resolved path is within project directory using `relative_to()`
  - Returns error for paths outside project boundary
- **Returns:** 
  - Success: `{ "success": true, "content": "<file contents>" }`
  - Error: `{ "success": false, "error": "<error message>" }`
- **Truncation:** File contents truncated to 8000 chars to prevent context overflow

### list_files

Lists files and directories at a given path.

- **Parameters:** `path` (string) — relative directory path from project root
- **Security:** 
  - Blocks path traversal (`../`)
  - Validates resolved path is within project directory
  - Only allows listing directories (not files)
- **Returns:** 
  - Success: `{ "success": true, "entries": ["file: example.md", "dir: images"] }`
  - Error: `{ "success": false, "error": "<error message>" }`

### query_api

Calls the backend API to fetch data or check system status.

- **Parameters:**
  - `method` (string) — HTTP method (GET, POST, PUT, DELETE)
  - `path` (string) — API endpoint path (e.g., `/items/`, `/scores/`)
  - `body` (string, optional) — JSON request body for POST/PUT requests
- **Authentication:** Uses `LMS_API_KEY` from `.env.docker.secret`
- **Default API Base:** `http://localhost:42002` (caddy proxy)
- **Returns:** JSON object with `status_code` and `body`, or `error` on failure

## Agentic Loop

The agent uses an iterative loop to answer questions by calling tools:

```
┌─────────────────────────────────────────────────────────────┐
│  1. Send user question + tool schemas to LLM                │
│                                                             │
│  2. Parse LLM response:                                     │
│     - If tool_calls present:                                │
│       a. Execute each tool                                  │
│       b. Append results as "tool" role messages             │
│       c. Send updated conversation back to LLM              │
│       d. Repeat (max 10 iterations)                         │
│     - If no tool_calls (text answer):                       │
│       a. Extract source reference from answer               │
│       b. Return (answer, source, tool_calls_log)            │
│                                                             │
│  3. If max iterations reached, return partial answer        │
└─────────────────────────────────────────────────────────────┘
```

### Implementation Details

1. **Message Format:** Uses OpenAI-compatible message format with roles: `system`, `user`, `assistant`, `tool`
2. **Tool Execution:** Each tool call is executed synchronously, results formatted for LLM consumption
3. **Result Formatting:** 
   - `read_file`: Returns file content directly
   - `list_files`: Returns newline-separated entries
   - `query_api`: Returns JSON response body
4. **Error Handling:** Tool errors are returned as formatted error messages to the LLM

## System Prompt Strategy

The system prompt guides the LLM to use tools effectively:

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

### Key Strategies

1. **Discovery First:** LLM is instructed to use `list_files` before `read_file` to discover available documentation
2. **Verification:** LLM must verify information by reading actual files, not relying on training data
3. **Source Attribution:** LLM must include source references in answers
4. **Tool Selection:** LLM chooses `query_api` for real-time system data vs `read_file` for documentation

## Output Format

```json
{
  "answer": "Edit the conflicting file, choose which changes to keep, then stage and commit.",
  "source": "wiki/git-workflow.md#resolving-merge-conflicts",
  "tool_calls": [
    {
      "tool": "list_files",
      "args": {"path": "wiki"},
      "result": {"success": true, "entries": ["file: git-workflow.md", "dir: images"]}
    },
    {
      "tool": "read_file",
      "args": {"path": "wiki/git-workflow.md"},
      "result": {"success": true, "content": "# Git Workflow\n\n..."}
    }
  ]
}
```

- `answer` (string, required) — The LLM's final answer
- `source` (string, required) — Wiki section reference (e.g., `wiki/filename.md#section`)
- `tool_calls` (array, required) — All tool calls made during the agentic loop

## Source Extraction

The `extract_source()` function uses regex patterns to find source references:

1. **Pattern 1:** Explicit `Source: wiki/...` format
2. **Pattern 2:** Any `wiki/...md` reference in the answer
3. **Default:** Empty string if no source found

## Environment Variables

| Variable | Purpose | Source |
|----------|---------|--------|
| `LLM_API_KEY` | LLM provider API key | `.env.agent.secret` |
| `LLM_API_BASE` | LLM API endpoint URL | `.env.agent.secret` |
| `LLM_MODEL` | Model name | `.env.agent.secret` |
| `LMS_API_KEY` | Backend API key for `query_api` auth | `.env.docker.secret` |
| `AGENT_API_BASE_URL` | Base URL for `query_api` | Optional, defaults to `http://localhost:42002` |

## Usage

```bash
# Basic question
uv run agent.py "What is 2+2?"

# Documentation question
uv run agent.py "How do you resolve a merge conflict?"

# System data question
uv run agent.py "How many items are in the database?"

# Directory listing question
uv run agent.py "What files are in the wiki directory?"
```

## Security

### Path Traversal Prevention

Both `read_file` and `list_files` implement security checks:

1. **String Check:** Reject paths containing `..` or starting with `/`
2. **Path Resolution:** Use `resolve().relative_to()` to validate final path is within project root
3. **Error Response:** Return descriptive error message for invalid paths

### File Access Control

- `read_file` only reads regular files (returns error for directories)
- `list_files` only lists directories (returns error for files)
- File content truncation prevents context overflow attacks
