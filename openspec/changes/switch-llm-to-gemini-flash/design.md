# Design: Switch LLM Backend to Gemini Flash

## Architecture Decision: Remove Domain Routing

### Context

The domain routing system was originally designed for Ollama's VRAM/context constraints (12GB GPU, 7B param models), then repurposed as a cost optimization for Anthropic. It consists of:

1. `domains.py` — Static `DEFAULT_DOMAINS` dict mapping domain names to hardcoded tool name lists
2. `classify_intent()` in `AnthropicClient` — Haiku classifies user message into domain names
3. `get_tools_for_domains()` in `DomainRegistry` — Filters tools to only those in the whitelist
4. `execute_with_routing()` in `AnthropicClient` — Orchestrates the classify-then-execute flow

### Problem

The routing layer is fundamentally incompatible with dynamic tool discovery. New MCP servers added to mcp-gateway are fetched correctly by `DynamicToolRegistry.refresh()`, but `get_tools_for_domains()` only returns tools whose names appear in the hardcoded `DEFAULT_DOMAINS` tool lists. Tools from unknown servers are silently dropped.

### Decision

Remove domain routing entirely. Gemini 2.0 Flash at $0.10/$0.40 per MTok makes the optimization unnecessary. The router will always call `execute_with_tools` with all discovered tools.

### Consequences

- Positive: `/refresh` works for any MCP server without code changes
- Positive: One fewer API call per message (no Haiku classification step)
- Positive: Simpler codebase (~150 lines removed)
- Positive: Lower latency (no classification round-trip)
- Negative: Slightly more tokens per request (all tools sent every time). At Flash pricing this is negligible.

## Gemini Function Calling Integration

### SDK Choice

Use the official `google-genai` Python SDK (`google.genai`). This is the current-generation SDK for the Gemini API (distinct from the older `google-generativeai` package).

### Tool Format Translation

**Current (Claude format)**:
```python
{
    "name": "mcp-dav__list_events",
    "description": "List calendar events",
    "input_schema": {"type": "object", "properties": {...}}
}
```

**Target (Gemini format)**:
```python
from google.genai import types

types.Tool(function_declarations=[
    types.FunctionDeclaration(
        name="mcp-dav__list_events",
        description="List calendar events",
        parameters=types.Schema(type="OBJECT", properties={...})
    )
])
```

The `DynamicToolRegistry.format_tools_for_gemini()` method will convert the internal tool representation to Gemini's `FunctionDeclaration` format.

### Function Calling Loop

**Current (Claude)**:
1. Send message + tools to Sonnet
2. Response has `stop_reason == "tool_use"` with `tool_use` blocks
3. Execute tools, append `tool_result` blocks
4. Re-send to get final text response

**Target (Gemini)**:
1. Send message + tools to Gemini Flash
2. Response contains `function_call` parts
3. Execute tools, create `function_response` parts
4. Re-send to get final text response

The loop structure is identical; only the message format changes.

### Multimodal Content

**Current (Claude)**:
```python
{"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": "..."}}
{"type": "document", "source": {"type": "base64", "media_type": "application/pdf", "data": "..."}}
```

**Target (Gemini)**:
```python
types.Part.from_bytes(data=raw_bytes, mime_type="image/jpeg")
```

The `UserMessage` class gains a `to_gemini_content()` method alongside the existing `to_claude_content()`.

### Conversation History

Gemini uses a `contents` list with `role: "user"` and `role: "model"` messages (vs Claude's `"assistant"`). The history management logic in `GeminiClient` mirrors `AnthropicClient` with the role name adjusted.

## NixOS Module Changes

### Option Rename

| Old | New |
|-----|-----|
| `claudeApiKeyFile` | `geminiApiKeyFile` |
| `ANTHROPIC_API_KEY_FILE` | `GEMINI_API_KEY_FILE` |

### Nix Dependency

Replace `python3Packages.anthropic` with `python3Packages.google-generativeai` (or build `google-genai` from PyPI if not in nixpkgs).

### Consumer Impact

Any NixOS configuration importing this module must update:
```nix
# Before
services.axios-chat.bot.claudeApiKeyFile = config.age.secrets.anthropic.path;

# After
services.axios-chat.bot.geminiApiKeyFile = config.age.secrets.gemini-api-key.path;
```
