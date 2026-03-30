# Task 1 Plan: Call an LLM from Code

## LLM Provider and Model

- **Provider:** Qwen Code API (self-hosted on VM)
- **Model:** `qwen3-coder-plus`
- **API Base:** `http://127.0.0.1:42006/v1`
- **Authentication:** Bearer token (`my-secret-qwen-key`)

### Why Qwen Code API?

- Provides 1000 free requests per day
- No credit card required
- OpenAI-compatible API endpoint
- Strong tool calling capabilities

## Agent Structure

The agent (`agent.py`) will:

1. **Parse CLI input** — accept a question as the first command-line argument
2. **Load configuration** — read `LLM_API_KEY`, `LLM_API_BASE`, `LLM_MODEL` from `.env.agent.secret`
3. **Call the LLM** — send POST request to `/v1/chat/completions` endpoint
4. **Format output** — return JSON with `answer` and `tool_calls` fields to stdout

### Output Format

```json
{"answer": "Representational State Transfer.", "tool_calls": []}
```

### Error Handling

- All debug/progress output goes to stderr
- Only valid JSON goes to stdout
- Exit code 0 on success, non-zero on failure
- 60-second timeout for API requests

## Implementation Notes

- For Task 1, `tool_calls` will always be an empty array
- Tools (`read_file`, `list_files`) will be added in Task 2
- The agentic loop will be implemented in Task 2
