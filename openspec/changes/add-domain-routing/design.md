# Design: Domain-Aware Routing Architecture

## Overview

This document details the technical design for domain-aware routing, enabling efficient local LLM execution by reducing context size through intelligent request classification.

## Component Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        axios-ai-bot                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐       │
│  │ XMPP Handler │───▶│   Router     │───▶│  Executor    │       │
│  │              │    │              │    │              │       │
│  │ Receives msg │    │ Classifies   │    │ Calls tools  │       │
│  │              │    │ domains      │    │ Gets response│       │
│  └──────────────┘    └──────┬───────┘    └──────────────┘       │
│                             │                    ▲               │
│                             ▼                    │               │
│                      ┌──────────────┐    ┌──────┴───────┐       │
│                      │   Domain     │    │    Tool      │       │
│                      │   Registry   │───▶│   Filter     │       │
│                      │              │    │              │       │
│                      └──────────────┘    └──────────────┘       │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
                               │
                               ▼
                      ┌──────────────┐
                      │  mcp-gateway │
                      │              │
                      │ axios-ai-mail│
                      │ mcp-dav      │
                      │ time         │
                      └──────────────┘
```

## Data Structures

### DomainConfig

```python
from dataclasses import dataclass, field

@dataclass
class DomainConfig:
    """Configuration for a single domain."""
    name: str
    description: str  # For router prompt
    servers: list[str] = field(default_factory=list)  # MCP server names
    tools: list[str] = field(default_factory=list)  # Tool name patterns
    prompt_hint: str = ""  # Added to system prompt when domain is active
    priority: int = 0  # For ordering in router prompt

@dataclass
class DomainRegistry:
    """Registry of all available domains."""
    domains: dict[str, DomainConfig] = field(default_factory=dict)

    def get_tools_for_domains(
        self,
        domain_names: list[str],
        all_tools: list[dict]
    ) -> list[dict]:
        """Filter tools to only those in the specified domains."""
        allowed_tools = set()
        for name in domain_names:
            if name in self.domains:
                allowed_tools.update(self.domains[name].tools)

        return [t for t in all_tools if t["name"] in allowed_tools]

    def get_prompt_hints(self, domain_names: list[str]) -> str:
        """Combine prompt hints for active domains."""
        hints = []
        for name in domain_names:
            if name in self.domains and self.domains[name].prompt_hint:
                hints.append(self.domains[name].prompt_hint)
        return "\n".join(hints)
```

### Default Domain Registry

```python
DEFAULT_DOMAINS = {
    "contacts": DomainConfig(
        name="contacts",
        description="Looking up, searching, or modifying contact information",
        servers=["mcp-dav"],
        tools=[
            "mcp-dav__list_contacts",
            "mcp-dav__search_contacts",
            "mcp-dav__get_contact",
            "mcp-dav__create_contact",
            "mcp-dav__update_contact",
            "mcp-dav__delete_contact",
        ],
        prompt_hint="You are a contacts assistant. Use contact tools to look up and manage contact information.",
        priority=1,
    ),
    "calendar": DomainConfig(
        name="calendar",
        description="Events, scheduling, availability, and reminders",
        servers=["mcp-dav"],
        tools=[
            "mcp-dav__list_events",
            "mcp-dav__search_events",
            "mcp-dav__create_event",
            "mcp-dav__get_free_busy",
        ],
        prompt_hint="You are a calendar assistant. Use calendar tools to check and manage events.",
        priority=2,
    ),
    "email": DomainConfig(
        name="email",
        description="Reading, searching, composing, or sending emails",
        servers=["axios-ai-mail"],
        tools=[
            "axios-ai-mail__list_accounts",
            "axios-ai-mail__search_emails",
            "axios-ai-mail__read_email",
            "axios-ai-mail__compose_email",
            "axios-ai-mail__send_email",
            "axios-ai-mail__reply_to_email",
            "axios-ai-mail__mark_read",
            "axios-ai-mail__delete_email",
        ],
        prompt_hint="You are an email assistant. Use email tools to search, read, and send messages.",
        priority=3,
    ),
    "time": DomainConfig(
        name="time",
        description="Checking current time or converting between timezones",
        servers=["time"],
        tools=[
            "time__get_current_time",
            "time__convert_time",
        ],
        prompt_hint="You can check the current time and convert between timezones.",
        priority=4,
    ),
    "general": DomainConfig(
        name="general",
        description="General conversation, questions, or tasks not requiring data access",
        servers=[],
        tools=[],
        prompt_hint="You are a helpful assistant. Answer questions conversationally.",
        priority=99,  # Always last
    ),
}
```

## Router Implementation

### Router Prompt

```python
ROUTER_PROMPT_TEMPLATE = """Classify the user's request into one or more domains.
Return ONLY the domain names as a comma-separated list. No explanation.

Available domains:
{domain_list}

Examples:
- "What time is it?" → time
- "Check my calendar for today" → calendar
- "Email John from my contacts" → contacts, email
- "Schedule a meeting with the team" → calendar
- "Find duplicate contacts" → contacts
- "Tell me a joke" → general
- "What's the weather like?" → general

User: {message}
Domains:"""

def build_router_prompt(message: str, registry: DomainRegistry) -> str:
    """Build the router prompt with current domain list."""
    domain_list = "\n".join(
        f"- {d.name}: {d.description}"
        for d in sorted(registry.domains.values(), key=lambda x: x.priority)
    )
    return ROUTER_PROMPT_TEMPLATE.format(
        domain_list=domain_list,
        message=message,
    )
```

### Intent Classification

```python
async def classify_intent(
    self,
    message: str,
    registry: DomainRegistry,
    timeout: float = 10.0,
) -> list[str]:
    """Classify user message into domains.

    Returns list of domain names. Falls back to ["general"] on error.
    """
    prompt = build_router_prompt(message, registry)

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                f"{self.base_url}/api/chat",
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": "You are a request classifier. Output only domain names."},
                        {"role": "user", "content": prompt},
                    ],
                    "stream": False,
                    "options": {"temperature": 0.1},  # Very low for consistent classification
                },
            )
            response.raise_for_status()

            result = response.json()
            content = result.get("message", {}).get("content", "").strip()

            # Parse comma-separated domains
            domains = [d.strip().lower() for d in content.split(",") if d.strip()]

            # Validate domains exist
            valid_domains = [d for d in domains if d in registry.domains]

            if not valid_domains:
                logger.warning(f"No valid domains from classification: {content}")
                return ["general"]

            return valid_domains

    except Exception as e:
        logger.error(f"Intent classification failed: {e}")
        return ["general"]
```

## Execution Flow

### Orchestrated Execution

```python
async def execute_with_routing(
    self,
    user_id: str,
    message: str,
    all_tools: list[dict],
    tool_executor: Any,
    registry: DomainRegistry,
    progress_callback: ProgressCallback | None = None,
) -> str:
    """Execute request with domain-aware routing.

    1. Classify intent to determine domains
    2. Filter tools to relevant domains
    3. Execute with focused tool set
    """
    # Step 1: Classify
    domains = await self.classify_intent(message, registry)
    logger.info(f"Classified domains: {domains}")

    # Step 2: Filter tools
    if "general" in domains and len(domains) == 1:
        # Pure general - no tools needed
        return await self.simple_response(user_id, message)

    filtered_tools = registry.get_tools_for_domains(domains, all_tools)
    logger.info(f"Filtered to {len(filtered_tools)} tools (from {len(all_tools)})")

    if not filtered_tools:
        # No tools for these domains - fall back to general
        return await self.simple_response(user_id, message)

    # Step 3: Build focused prompt
    base_prompt = self.base_system_prompt or get_default_system_prompt()
    domain_hints = registry.get_prompt_hints(domains)
    focused_prompt = f"{base_prompt}\n\n{domain_hints}"

    # Step 4: Execute with filtered tools
    # Temporarily override system prompt
    original_prompt = self.base_system_prompt
    self.base_system_prompt = focused_prompt

    try:
        result = await self.execute_with_tools(
            user_id=user_id,
            message=message,
            tools=filtered_tools,
            tool_executor=tool_executor,
            progress_callback=progress_callback,
        )
        return result
    finally:
        self.base_system_prompt = original_prompt
```

## Configuration Integration

### NixOS Module Options

```nix
services.axios-chat.bot = {
  # ... existing options ...

  enableDomainRouting = lib.mkEnableOption "domain-aware routing" // {
    default = true;  # Enable by default for Ollama
  };

  routerTimeout = lib.mkOption {
    type = lib.types.float;
    default = 10.0;
    description = "Timeout in seconds for intent classification";
  };

  # Allow custom domain definitions
  extraDomains = lib.mkOption {
    type = lib.types.attrsOf (lib.types.submodule {
      options = {
        description = lib.mkOption { type = lib.types.str; };
        servers = lib.mkOption { type = lib.types.listOf lib.types.str; default = []; };
        tools = lib.mkOption { type = lib.types.listOf lib.types.str; default = []; };
        promptHint = lib.mkOption { type = lib.types.str; default = ""; };
      };
    });
    default = {};
    description = "Additional domain definitions";
  };
};
```

## Performance Expectations

| Scenario | Before (all tools) | After (routed) | Improvement |
|----------|-------------------|----------------|-------------|
| "List contacts" | 20 tools, ~5K tokens | 6 tools, ~1.5K tokens | 70% reduction |
| "What's on calendar" | 20 tools, ~5K tokens | 4 tools, ~1K tokens | 80% reduction |
| "Email John" | 20 tools, ~5K tokens | 14 tools, ~3.5K tokens | 30% reduction |
| "Tell me a joke" | 20 tools, ~5K tokens | 0 tools, ~0.5K tokens | 90% reduction |

Router overhead: ~5-10 seconds (minimal context, fast inference)

Net improvement: Significant for single-domain queries, moderate for cross-domain.

## Future Enhancements

1. **Model-per-domain**: Use faster model for simple domains (time, general)
2. **Learned routing**: Fine-tune router on classification data
3. **Hierarchical domains**: Sub-domains for finer-grained control
4. **Domain caching**: Cache classifications for similar messages
5. **Parallel domain execution**: Execute multi-domain queries in parallel
