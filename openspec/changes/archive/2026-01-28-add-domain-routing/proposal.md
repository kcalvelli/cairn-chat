# Proposal: Add Domain-Aware Routing for Efficient Local LLM Execution

## Summary

Implement a domain-aware routing architecture that classifies user requests and routes them to specialized agents with focused tool sets. This reduces context size, improves inference speed, and enables cross-domain operations while maintaining dynamic MCP server integration.

## Motivation

### Current Pain Points

1. **Context Overload**: Sending all 20+ tools to Ollama creates ~5K tokens of tool definitions
2. **Slow Inference**: Large context + tool results exceeds efficient processing capacity for local models
3. **Timeouts**: Complex queries with large data responses (contacts list, email search) cause 2+ minute timeouts
4. **VRAM Constraints**: 12GB GPU can only fit 24/41 layers with 16K context, causing CPU fallback

### Why Routing Helps

1. **Smaller Context**: Each domain has 4-7 tools instead of 20+ (60-80% reduction)
2. **Faster Inference**: Less context = more computation on GPU = faster responses
3. **Focused Prompts**: Specialized system prompts improve tool selection accuracy
4. **Cross-Domain Support**: Router can identify multi-domain requests and combine tool sets

## Architecture

```
User Message
      ↓
┌─────────────────────────────────┐
│       Intent Router             │
│  (Minimal context - no tools)   │
│                                 │
│  Input: User message            │
│  Output: ["contacts", "email"]  │
└───────────────┬─────────────────┘
                ↓
        Load relevant tools
        from identified domains
                ↓
┌─────────────────────────────────┐
│      Execution Agent            │
│  Focused prompt + tools subset  │
│                                 │
│  1. search_contacts("John")     │
│  2. compose_email(john@...)     │
└─────────────────────────────────┘
```

## Key Technical Decisions

### 1. Lightweight Intent Router

The router runs with **no tools in context**, making it fast:

```
Classify the user's request into domains. Return ONLY domain names, comma-separated.

Domains:
- contacts: Looking up, searching, modifying contact information
- calendar: Events, scheduling, availability, reminders
- email: Reading, searching, composing, sending emails
- general: Conversation, questions, no data access needed

Examples:
"Email John from my contacts" → contacts, email
"What's on my calendar today?" → calendar
"Schedule meeting with John" → contacts, calendar
"Tell me a joke" → general

User: "{message}"
Domains:
```

### 2. Domain Registry

Map domains to MCP servers and their tools:

```python
DOMAIN_REGISTRY = {
    "contacts": {
        "servers": ["mcp-dav"],
        "tools": ["list_contacts", "search_contacts", "get_contact",
                  "create_contact", "update_contact", "delete_contact"],
        "prompt_hint": "You are a contacts assistant. Use the contact tools to help the user."
    },
    "calendar": {
        "servers": ["mcp-dav"],
        "tools": ["list_events", "search_events", "create_event", "get_free_busy"],
        "prompt_hint": "You are a calendar assistant. Use calendar tools to manage events."
    },
    "email": {
        "servers": ["axios-ai-mail"],
        "tools": ["list_accounts", "search_emails", "read_email",
                  "compose_email", "send_email", "reply_to_email", "mark_read", "delete_email"],
        "prompt_hint": "You are an email assistant. Use email tools to manage messages."
    },
    "time": {
        "servers": ["time"],
        "tools": ["get_current_time", "convert_time"],
        "prompt_hint": "You can check and convert times."
    },
    "general": {
        "servers": [],
        "tools": [],
        "prompt_hint": "You are a helpful assistant. Answer conversationally."
    }
}
```

### 3. Cross-Domain Execution

When router returns multiple domains (e.g., `["contacts", "email"]`):

1. Combine tool sets from all identified domains
2. Merge prompt hints into system prompt
3. Execute with combined (but still reduced) tool set

Example: "Email John from my contacts"
- Domains: contacts, email
- Tools: 6 contact tools + 8 email tools = 14 tools (vs 20+)
- Context is still smaller than full tool set

### 4. Dynamic Domain Discovery

Domains are defined in configuration, not hardcoded. New MCP servers can register with domain metadata:

```nix
services.mcp-gateway.servers.my-new-server = {
  domain = "inventory";  # New domain
  # tools auto-discovered from MCP server
};
```

### 5. Fallback Behavior

- If router returns empty/invalid: Use "general" domain (no tools)
- If router returns unknown domain: Log warning, skip that domain
- If all tools filtered out: Fall back to general conversation

## Scope

### In Scope

- Intent router with structured output parsing
- Domain registry configuration
- Tool filtering by domain
- Cross-domain tool combination
- Focused system prompts per domain
- Integration with existing mcp-gateway tool loading

### Out of Scope

- Different models per domain (future enhancement)
- Learning/adapting domain classifications
- Sub-domain routing (e.g., "work email" vs "personal email")
- Caching of domain classifications

## Success Criteria

1. **Response time < 30 seconds** for single-domain queries
2. **Response time < 60 seconds** for cross-domain queries
3. **Correct domain classification** >= 95% of requests
4. **No regression** in tool calling accuracy
5. **Dynamic MCP support** maintained (new servers work without code changes)

## Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Router misclassifies intent | Medium | Medium | Include examples in prompt, allow multi-domain fallback |
| Cross-domain queries still too slow | Low | Medium | Limit to 2 domains, prioritize most relevant |
| Domain boundaries too rigid | Medium | Low | Allow "fuzzy" matching, general fallback |
| New MCP servers don't fit domains | Low | Low | Default to "general" domain, log for review |

## Dependencies

- Existing Ollama backend (from `migrate-to-ollama-qwen3`)
- mcp-gateway tool discovery
- Structured output parsing (simple string split)

## Related Changes

This proposal modifies existing specs:
- `llm-backend`: Add router phase before tool execution
- `tool-calling`: Add domain filtering capability
