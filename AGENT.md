# Agent Architecture

## Overview

This agent is a CLI tool that answers questions by calling an LLM (Qwen Code API) and using tools to read project documentation and query the system API.

## LLM Provider

- **Provider:** Qwen Code API (self-hosted on VM)
- **Model:** qwen3-coder-plus
- **API Base:** http://127.0.0.1:42006/v1
- **Authentication:** Bearer token from `.env.agent.secret`

## Tools

### read_file
Reads a file from the project repository.
- **Parameters:** `path` (string) - relative path from project root
- **Security:** Blocks path traversal (`../`), only allows paths within project directory
- **Returns:** File content (truncated to 8000 chars if too long)

### list_files
Lists files and directories at a given path.
- **Parameters:** `path` (string) - relative directory path from project root
- **Security:** Blocks paths outside project directory
- **Returns:** List of entries with type prefix (e.g., "file: example.md", "dir: images")

### query_api
Calls the backend API to fetch data or check system status.
- **Parameters:**
  - `method` (string) - HTTP method (GET, POST, PUT, DELETE)
  - `path` (string) - API endpoint path (e.g., `/items/`, `/scores/`)
  - `body` (string, optional) - JSON request body for POST/PUT requests
- **Authentication:** Uses `LMS_API_KEY` from `.env.docker.secret`
- **Default API Base:** `http://localhost:42002` (caddy proxy)
- **Returns:** JSON object with `status_code` and `body`, or `error` on failure

## Agentic Loop

The agent uses an iterative loop to answer questions:

1. Send user question + tool definitions to LLM
2. If LLM returns tool calls:
   - Execute each tool
   - Append results as "tool" role messages
   - Send back to LLM
   - Repeat (max 10 iterations)
3. If LLM returns text answer (no tool calls):
   - Extract source reference from answer
   - Output JSON and exit

## System Prompt Strategy

The system prompt guides the LLM to:
- Use `list_files` first to discover what files exist
- Use `read_file` to find actual content from documentation
- Use `query_api` for questions about current data, item counts, scores, or system status
- Include source references in answers (e.g., "Source: wiki/filename.md#section")

## Output Format

```json
{
  "answer": "...",
  "source": "wiki/filename.md#section",
  "tool_calls": [
    {"tool": "list_files", "args": {"path": "wiki"}, "result": {...}},
    {"tool": "read_file", "args": {"path": "wiki/filename.md"}, "result": {...}},
    {"tool": "query_api", "args": {"method": "GET", "path": "/items/"}, "result": {...}}
  ]
}
```

Note: `source` is optional for system questions that don't have wiki documentation sources.

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
```
