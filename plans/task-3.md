# Task 3 Plan: The System Agent

## Overview

Task 3 extends the Documentation Agent (Task 2) with a new `query_api` tool that allows the agent to interact with the deployed backend API. This enables the agent to answer both static system questions and data-dependent queries.

## New Tool: query_api

### Purpose
Call the deployed backend API to fetch real-time data from the system.

### Parameters
- `method` (string) — HTTP method (GET, POST, etc.)
- `path` (string) — API endpoint path (e.g., `/items/`)
- `body` (string, optional) — JSON request body for POST/PUT requests

### Returns
JSON string with:
- `status_code` — HTTP response status code
- `body` — Response body (parsed JSON or text)

### Authentication
Uses `LMS_API_KEY` from `.env.docker.secret` for Authorization header.

## Implementation Plan

1. **Add `query_api` function** — Implement HTTP client using `urllib.request`
2. **Add tool schema** — Register function-calling schema alongside existing tools
3. **Update `execute_tool`** — Add handler for `query_api` tool
4. **Update system prompt** — Teach LLM when to use `query_api` vs wiki tools
5. **Update environment loading** — Load `LMS_API_KEY` and `AGENT_API_BASE_URL`

## Environment Variables

| Variable | Purpose | Default |
|----------|---------|---------|
| `LMS_API_KEY` | Backend API authentication | From `.env.docker.secret` |
| `AGENT_API_BASE_URL` | Backend API base URL | `http://localhost:42002` |

## System Prompt Strategy

The system prompt will guide the LLM to:
- Use `list_files` and `read_file` for wiki/documentation questions
- Use `query_api` for questions about:
  - Current data (e.g., "How many items are in the database?")
  - System status (e.g., "What is the API status?")
  - Framework/port information that may be in the running system

## Output Format

Same as Task 2, but `source` is now optional (system questions may not have wiki sources):

```json
{
  "answer": "There are 120 items in the database.",
  "source": "",
  "tool_calls": [
    {"tool": "query_api", "args": {"method": "GET", "path": "/items/"}, "result": {...}}
  ]
}
```
