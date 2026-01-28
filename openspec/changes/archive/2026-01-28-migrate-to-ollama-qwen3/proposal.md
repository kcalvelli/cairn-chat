# Proposal: Migrate from Claude API to Local Ollama with Qwen3

## Summary

Replace the Anthropic Claude API integration with a local Ollama-based LLM backend using the `qwen3:14b-q4_K_M` model. This eliminates API costs and rate limiting while maintaining reliable tool calling capabilities through optimized prompting and the Hermes-style function calling protocol.

## Motivation

### Current Pain Points

1. **Cost**: Claude API usage incurs ongoing costs per token
2. **Rate Limiting**: Anthropic API has rate limits that can affect availability
3. **Latency**: Network round-trips to external API add latency
4. **Privacy**: All conversations currently traverse Anthropic's servers

### Benefits of Migration

1. **Zero marginal cost**: Once hardware is provisioned, no per-request costs
2. **No rate limits**: Local inference has no external throttling
3. **Lower latency**: Local processing eliminates network overhead
4. **Full privacy**: Conversations never leave the local network
5. **Offline capability**: Works without internet access

## Model Selection: qwen3:14b-q4_K_M

The `qwen3:14b-q4_K_M` model was selected based on:

- **Strong tool calling**: Qwen3 models excel at function calling with proper prompting
- **Balanced size**: 14B parameters provides good reasoning without excessive resource requirements
- **Q4_K_M quantization**: Optimal balance of quality and memory efficiency (~8GB VRAM)
- **Apache 2.0 license**: Permissive licensing for any use case
- **32K context window**: Sufficient for multi-turn conversations with tool results

## Key Technical Decisions

### 1. Hermes-Style Tool Calling Protocol

Qwen3 documentation explicitly recommends Hermes-style tool use for maximum function calling performance. This involves:

- Tools defined in `<tools></tools>` XML tags with JSON Schema
- Tool calls wrapped in `<tool_call>{"name": "...", "arguments": {...}}</tool_call>`
- Tool results returned in `<tool_response>` tags
- Explicit instructions to never hallucinate functions or arguments

### 2. Thinking Mode Strategy

Qwen3 supports a "thinking" mode that can improve reasoning but may interfere with tool calling. Our strategy:

- **Disable thinking for tool calls**: Use `/nothink` in prompts when tools are provided
- **Enable thinking for complex reasoning**: Optional for non-tool conversations
- This prevents the model from outputting stopwords in the thinking section that could break tool parsing

### 3. Anti-Hallucination Measures

Multiple layers of defense against tool hallucinations:

1. **Explicit system prompt constraints**: "ONLY use tools from the provided list. NEVER invent tool names or arguments."
2. **JSON schema validation**: Validate tool call JSON before execution
3. **Tool name allowlist**: Reject any tool call not in the registered tool set
4. **Structured output enforcement**: Use JSON mode where available
5. **Conservative temperature**: Use temperature 0.1-0.3 for tool calling to reduce creativity

### 4. Dual-Backend Architecture

To manage the transition and provide fallback:

- New `OllamaClient` class parallel to existing `LLMClient`
- Configuration option to select backend: `ollama` or `anthropic`
- Potential for hybrid mode: Ollama for general chat, Claude for complex tasks

## Scope

### In Scope

- New `OllamaClient` class implementing the Ollama API
- Hermes-style prompt template for tool calling
- JSON schema validation for tool calls
- NixOS module options for Ollama configuration
- System prompt optimized for Qwen3 tool calling
- Integration tests with mock Ollama responses

### Out of Scope

- Ollama server installation (separate NixOS service)
- GPU driver configuration (assumed pre-existing)
- Model fine-tuning
- Streaming responses (phase 2 enhancement)

## Dependencies

- Ollama server running locally (typically port 11434)
- `qwen3:14b-q4_K_M` model pulled to Ollama
- Sufficient RAM/VRAM for model inference (~10GB recommended)

## Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Tool calling less reliable than Claude | Medium | High | Extensive prompt engineering, validation layers, fallback to Claude |
| Higher latency for first token | Medium | Low | Accept trade-off for cost savings, use keep-alive |
| Model hallucinations | Medium | Medium | Multi-layer validation, explicit constraints in prompts |
| Resource constraints on server | Low | Medium | Q4_K_M quantization keeps memory reasonable |

## Success Criteria

1. Tool calling success rate >= 95% (matching current Claude performance)
2. No hallucinated tool names or arguments in production
3. Response latency < 10 seconds for typical queries
4. Zero external API costs after migration

## Related Changes

This proposal creates one new capability spec:
- `llm-backend`: Defines the abstracted LLM backend interface supporting multiple providers
