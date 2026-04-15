# Design: Migrate to Ollama with Qwen3

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                     cairn-ai-bot                            │
├─────────────────────────────────────────────────────────────┤
│  router.py                                                  │
│    └── MessageRouter                                        │
│          └── llm_client: LLMBackend (abstract)             │
├─────────────────────────────────────────────────────────────┤
│  llm/                                                       │
│    ├── __init__.py     (LLMBackend ABC, factory)           │
│    ├── anthropic.py    (AnthropicClient - existing logic)  │
│    ├── ollama.py       (OllamaClient - new)                │
│    └── prompts.py      (Hermes templates, system prompts)  │
├─────────────────────────────────────────────────────────────┤
│  tools.py                                                   │
│    └── DynamicToolRegistry (unchanged)                      │
│          └── format_tools_for_llm(backend: str)            │
└─────────────────────────────────────────────────────────────┘
```

## Component Design

### 1. LLMBackend Abstract Base Class

```python
from abc import ABC, abstractmethod
from typing import Any, Callable, Awaitable

class LLMBackend(ABC):
    """Abstract base class for LLM backends."""

    @abstractmethod
    async def execute_with_tools(
        self,
        user_id: str,
        message: str,
        tools: list[dict[str, Any]],
        tool_executor: Callable[[str, dict], Awaitable[dict]],
        progress_callback: Callable[[str], Awaitable[None]] | None = None,
    ) -> str:
        """Execute a request with tool access."""
        pass

    @abstractmethod
    async def simple_response(self, user_id: str, message: str) -> str:
        """Generate a response without tools."""
        pass

    @abstractmethod
    def clear_history(self, user_id: str) -> None:
        """Clear conversation history for a user."""
        pass
```

### 2. OllamaClient Implementation

```python
class OllamaClient(LLMBackend):
    """Ollama-based LLM client using Qwen3."""

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        model: str = "qwen3:14b-q4_K_M",
        system_prompt: str | None = None,
        max_context_messages: int = 10,
        temperature: float = 0.2,  # Low for tool calling
        enable_thinking: bool = False,  # Disabled for tool reliability
    ):
        self.base_url = base_url
        self.model = model
        self.system_prompt = system_prompt or get_ollama_system_prompt()
        self.max_context_messages = max_context_messages
        self.temperature = temperature
        self.enable_thinking = enable_thinking
        self.conversation_history: dict[str, list[dict]] = {}
```

### 3. Hermes-Style Prompt Template

The key to reliable tool calling with Qwen3 is proper prompt formatting:

```python
HERMES_TOOL_SYSTEM_PROMPT = """You are a function calling AI assistant. You are provided with function signatures within <tools></tools> XML tags.

You may call one or more functions to assist with the user query. Don't make assumptions about what values to plug into functions.

<tools>
{tools_json}
</tools>

For each function call, return a JSON object with function name and arguments within <tool_call></tool_call> XML tags:
<tool_call>
{{"name": "function_name", "arguments": {{"arg1": "value1"}}}}
</tool_call>

CRITICAL RULES:
1. ONLY call functions that are listed in <tools>. NEVER invent function names.
2. ONLY use argument names that appear in the function's parameters. NEVER add extra arguments.
3. If you cannot complete a task with the available functions, say so - do NOT hallucinate a function.
4. If a required argument value is unknown, ask the user - do NOT guess or make up values.
5. Always validate your function call matches the schema before outputting it.

/nothink"""
```

### 4. Tool Call Parsing and Validation

```python
import re
import json
from typing import Any

TOOL_CALL_PATTERN = re.compile(
    r'<tool_call>\s*(\{.*?\})\s*</tool_call>',
    re.DOTALL
)

def parse_tool_calls(response: str) -> list[dict[str, Any]]:
    """Extract and validate tool calls from model response."""
    calls = []
    for match in TOOL_CALL_PATTERN.finditer(response):
        try:
            call = json.loads(match.group(1))
            if "name" in call and "arguments" in call:
                calls.append(call)
        except json.JSONDecodeError:
            continue  # Skip malformed JSON
    return calls

def validate_tool_call(call: dict, registered_tools: set[str], tool_schemas: dict) -> tuple[bool, str]:
    """Validate a tool call against registered tools and schemas."""
    name = call.get("name", "")

    # Check tool exists
    if name not in registered_tools:
        return False, f"Unknown tool: {name}"

    # Validate arguments against schema
    schema = tool_schemas.get(name, {})
    required = schema.get("required", [])
    properties = schema.get("properties", {})
    arguments = call.get("arguments", {})

    # Check required arguments
    for req in required:
        if req not in arguments:
            return False, f"Missing required argument: {req}"

    # Check no extra arguments
    for arg in arguments:
        if arg not in properties:
            return False, f"Unknown argument: {arg}"

    return True, ""
```

### 5. Ollama API Integration

The Ollama API follows a simple REST pattern:

```python
async def _chat(self, messages: list[dict], tools: list[dict] | None = None) -> dict:
    """Send chat request to Ollama."""
    async with httpx.AsyncClient(timeout=120.0) as client:
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": self.temperature,
            }
        }

        # Add tools if provided (native Ollama tool calling)
        if tools:
            payload["tools"] = tools
            payload["think"] = self.enable_thinking

        response = await client.post(
            f"{self.base_url}/api/chat",
            json=payload
        )
        response.raise_for_status()
        return response.json()
```

### 6. Tool Format Conversion

Ollama expects tools in a slightly different format than Claude:

```python
def format_tools_for_ollama(tools: list[dict]) -> list[dict]:
    """Convert tools to Ollama's expected format."""
    return [
        {
            "type": "function",
            "function": {
                "name": t["name"],
                "description": t["description"],
                "parameters": t["input_schema"],
            }
        }
        for t in tools
    ]
```

### 7. Configuration and Backend Selection

NixOS module additions:

```nix
llmBackend = mkOption {
  type = types.enum [ "anthropic" "ollama" ];
  default = "anthropic";
  description = "LLM backend to use for AI responses.";
};

ollamaUrl = mkOption {
  type = types.str;
  default = "http://localhost:11434";
  description = "URL of the Ollama server.";
};

ollamaModel = mkOption {
  type = types.str;
  default = "qwen3:14b-q4_K_M";
  description = "Ollama model to use.";
};

ollamaTemperature = mkOption {
  type = types.float;
  default = 0.2;
  description = "Temperature for Ollama inference (lower = more deterministic).";
};
```

## Anti-Hallucination Strategy

### Layer 1: Prompt Engineering

The system prompt explicitly forbids hallucination:
- "ONLY call functions that are listed in <tools>"
- "NEVER invent function names"
- "NEVER add extra arguments"
- "If you cannot complete a task with the available functions, say so"

### Layer 2: Output Parsing

The `parse_tool_calls` function uses strict regex matching:
- Only extracts content within `<tool_call>` tags
- Requires valid JSON
- Requires both `name` and `arguments` fields

### Layer 3: Validation

The `validate_tool_call` function enforces:
- Tool name must be in registered tool set
- All required arguments must be present
- No unrecognized arguments allowed

### Layer 4: Graceful Failure

When validation fails:
1. Log the invalid tool call for debugging
2. Return error message to the model
3. Allow model to retry with correction
4. After 3 retries, respond with apology to user

## Thinking Mode Decision Matrix

| Scenario | Tools Provided | Thinking Mode | Rationale |
|----------|---------------|---------------|-----------|
| Tool-assisted query | Yes | OFF | Prevents stopword issues in tool parsing |
| Complex reasoning | No | ON | Improves answer quality |
| Simple chat | No | OFF | Faster response |
| Multi-step planning | Yes | OFF | Tool reliability > reasoning display |

## Conversation Flow

```
User: "What events do I have tomorrow?"

1. Router receives message
2. Router gets tools from registry
3. Router calls OllamaClient.execute_with_tools()
4. OllamaClient formats Hermes prompt with tools
5. Ollama generates response with <tool_call>
6. OllamaClient parses and validates tool call
7. Valid: Execute via tool_executor
   Invalid: Return error, allow retry
8. Tool result added to conversation
9. Ollama generates final response
10. Response returned to user
```

## Error Handling

### Ollama Server Unavailable

```python
try:
    response = await self._chat(messages, tools)
except httpx.ConnectError:
    return "I'm sorry, the AI service is currently unavailable. Please try again later."
```

### Tool Call Parsing Failure

```python
calls = parse_tool_calls(response_text)
if not calls and "<tool_call>" in response_text:
    # Model tried to call a tool but output was malformed
    logger.warning(f"Malformed tool call: {response_text}")
    # Retry with instruction to fix format
```

### Validation Failure

```python
valid, error = validate_tool_call(call, registered_tools, schemas)
if not valid:
    # Add error to conversation and retry
    messages.append({
        "role": "user",
        "content": f"<tool_response>{{'error': '{error}'}}</tool_response>"
    })
```

## Performance Considerations

### Keep-Alive

Ollama supports keeping the model loaded in memory:
```python
# Ping to keep model loaded
await client.post(f"{base_url}/api/generate", json={
    "model": model,
    "keep_alive": "30m"
})
```

### Batch Processing

For multi-tool scenarios, consider parallel validation:
```python
results = await asyncio.gather(*[
    tool_executor(call["name"], call["arguments"])
    for call in validated_calls
])
```

## Testing Strategy

### Unit Tests

- `test_parse_tool_calls`: Various valid/invalid formats
- `test_validate_tool_call`: Schema validation cases
- `test_format_tools_for_ollama`: Conversion correctness

### Integration Tests

- Mock Ollama server responses
- End-to-end tool calling flow
- Error recovery scenarios

### Acceptance Tests

- Real Ollama with qwen3 model
- Common tool calling scenarios (email, calendar, contacts)
- Edge cases (ambiguous requests, missing info)
