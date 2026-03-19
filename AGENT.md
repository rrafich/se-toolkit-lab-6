# Agent Architecture

## Overview

This agent is a CLI tool that answers questions by calling an LLM (Qwen Code API) and using tools to read project documentation.

## LLM Provider

- **Provider:** Qwen Code API (self-hosted on VM)
- **Model:** qwen3-coder-plus
- **API Base:** http://10.93.26.71:8080/v1
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

## Output Format

```json
{
  "answer": "...",
  "source": "wiki/filename.md#section",
  "tool_calls": [
    {"tool": "list_files", "args": {"path": "wiki"}, "result": {...}},
    {"tool": "read_file", "args": {"path": "wiki/filename.md"}, "result": {...}}
  ]
}