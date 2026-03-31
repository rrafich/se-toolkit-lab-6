# Task 2 Plan: The Documentation Agent

## Tools to Implement

### read_file
- **Purpose:** Read a file from the project repository
- **Parameters:** `path` (string) - relative path from project root
- **Returns:** File contents as string, or error message
- **Security:** Block `../` traversal, only allow paths within project

### list_files
- **Purpose:** List files/directories at a given path
- **Parameters:** `path` (string) - relative directory path from project root
- **Returns:** Newline-separated listing
- **Security:** Block paths outside project directory

## Agentic Loop Design

1. Send user question + tool definitions to LLM
2. If LLM returns `tool_calls`:
   - Execute each tool
   - Append results as "tool" role messages
   - Send back to LLM
   - Repeat (max 10 iterations)
3. If LLM returns text answer (no tool calls):
   - Extract answer and source
   - Output JSON and exit

## Tool Schema Format

Using OpenAI function-calling format:
```json
{
  "name": "read_file",
  "description": "Read a file from the project",
  "parameters": {
    "type": "object",
    "properties": {
      "path": {"type": "string", "description": "Relative path from project root"}
    },
    "required": ["path"]
  }
}