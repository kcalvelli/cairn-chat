# Design: axios-chat Architecture

## Context

The axios ecosystem has several MCP-enabled services (axios-ai-mail, axios-dav) aggregated via mcp-gateway. Users currently interact with these via Claude Code or the mcp-gateway Web UI. There's a need for a more natural, always-available interface that:

1. Provides family messaging (human-to-human)
2. Offers AI assistance via natural conversation
3. Works across all devices (Linux, Windows, Android)
4. Stays entirely within the Tailscale network

**Constraints:**
- Must be a standalone flake (no circular deps with axios)
- Tailscale-only access (no application-level auth)
- Use existing XMPP clients (no custom app development)
- Claude API for reliable tool calling (local LLMs failed in testing)

## Goals / Non-Goals

**Goals:**
- Family IM experience with AI assistant as a contact
- Dynamic tool discovery from mcp-gateway
- Cost-effective LLM usage via smart routing
- Simple NixOS/home-manager configuration

**Non-Goals:**
- Web UI or PWA (use XMPP clients)
- Local LLM support (unreliable tool calling)
- XMPP federation (security via isolation)
- Voice/video calls (text only initially)

## Flake Structure

```
axios-chat/
├── flake.nix                      # Main flake definition
├── flake.lock
│
├── modules/
│   ├── nixos/
│   │   ├── default.nix            # Imports prosody + bot
│   │   ├── prosody.nix            # Tailnet-only Prosody config
│   │   └── bot.nix                # axios-ai-bot systemd service
│   │
│   └── home-manager/
│       └── default.nix            # User preferences
│
├── pkgs/
│   └── axios-ai-bot/
│       ├── pyproject.toml
│       └── src/
│           └── axios_ai_bot/
│               ├── __init__.py
│               ├── main.py        # Entry point
│               ├── xmpp.py        # slixmpp client
│               ├── llm.py         # Claude API (Haiku + Sonnet)
│               ├── tools.py       # Dynamic tool registry
│               └── router.py      # Intent classification
│
├── openspec/                      # Spec-driven development
└── docs/
```

## Decisions

### Decision 1: Prosody as XMPP Server

**Options Considered:**
1. Prosody (Lua, lightweight)
2. ejabberd (Erlang, feature-rich)
3. Custom XMPP implementation

**Chosen: Prosody**

**Rationale:**
- NixOS has excellent `services.prosody` module with 98 options
- Extremely lightweight (~25-50MB RAM)
- "Set and forget" reliability
- Sufficient features for family use

### Decision 2: slixmpp for Bot

**Options Considered:**
1. slixmpp (async, actively maintained)
2. sleekxmpp (deprecated)
3. xmpppy (sync, older)

**Chosen: slixmpp**

**Rationale:**
- Async-first design (works with asyncio/httpx/anthropic)
- Actively maintained fork of sleekxmpp
- Good documentation and examples

### Decision 3: Claude API with Haiku + Sonnet

**Options Considered:**
1. Local Ollama only
2. Claude API only (Sonnet for everything)
3. Hybrid: Haiku for routing, Sonnet for execution

**Chosen: Hybrid approach**

**Rationale:**
- Local LLMs failed tool calling tests (user's experience with OpenWebUI)
- Sonnet-only is expensive due to tool definition overhead
- Haiku can classify intent cheaply (~$0.001)
- Sonnet executes with minimal tool set based on classification

**Cost breakdown:**
```
User: "What's on my calendar?"
         │
         ▼
┌─────────────────────────────┐
│  Haiku Classification       │  Input: ~500 tokens
│  "Is this: email/calendar/  │  Output: ~20 tokens
│   contacts/general/other?"  │  Cost: ~$0.001
└─────────────────────────────┘
         │
         ▼ "calendar"
┌─────────────────────────────┐
│  Sonnet + Calendar Tools    │  Input: ~2000 tokens (vs 5000)
│  (3 tools instead of 20)    │  Output: ~200 tokens
│                             │  Cost: ~$0.009 (vs $0.018)
└─────────────────────────────┘

Total: ~$0.010 per interaction (vs ~$0.020 without routing)
```

### Decision 4: Dynamic Tool Discovery

**Options Considered:**
1. Static tool definitions at build time
2. Dynamic discovery at startup only
3. Periodic refresh with on-demand option

**Chosen: Periodic refresh + on-demand**

**Rationale:**
- New MCP servers added to gateway should be immediately usable
- Startup-only misses runtime additions
- Periodic refresh (every 5 min) + `/refresh` command covers all cases

```python
class DynamicToolRegistry:
    def __init__(self, gateway_url: str, refresh_interval: int = 300):
        self.gateway_url = gateway_url
        self.refresh_interval = refresh_interval
        self.tools: list[dict] = []
        self.tool_categories: dict[str, list[str]] = {}

    async def refresh(self):
        """Fetch tools from mcp-gateway and categorize them."""
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{self.gateway_url}/api/tools")
            raw = resp.json()

        self.tools = []
        self.tool_categories = defaultdict(list)

        for server_id, server_tools in raw.items():
            category = self._infer_category(server_id)
            for tool in server_tools:
                tool_name = f"{server_id}__{tool['name']}"
                self.tools.append({
                    "name": tool_name,
                    "description": tool["description"],
                    "input_schema": tool["inputSchema"],
                    "category": category,
                    "server": server_id,
                })
                self.tool_categories[category].append(tool_name)

    def get_tools_for_categories(self, categories: list[str]) -> list[dict]:
        """Return only tools matching the given categories."""
        names = set()
        for cat in categories:
            names.update(self.tool_categories.get(cat, []))
        return [t for t in self.tools if t["name"] in names]
```

### Decision 5: Tailscale Interface Binding

**Approach:**
Prosody binds only to the Tailscale interface IP, making it unreachable from outside the tailnet.

```nix
# modules/nixos/prosody.nix
services.prosody = {
  enable = true;

  # Bind only to Tailscale interface
  interfaces = [ config.services.axios-chat.prosody.tailscaleIP ];

  # Disable federation
  modules_disabled = [ "s2s" ];

  # No c2s on standard ports from other interfaces
  c2sRequireEncryption = true;
};
```

The `tailscaleIP` is derived from the machine's Tailscale status or configured explicitly.

### Decision 6: Secret Management Pattern

Follow axios ecosystem patterns using file-based secrets:

```nix
services.axios-chat.bot = {
  enable = true;
  anthropicKeyFile = config.age.secrets.anthropic-api-key.path;
  xmppPasswordFile = config.age.secrets.axios-ai-bot-password.path;
};
```

At runtime, the bot reads secrets from these files:

```python
def load_secret(path: str) -> str:
    with open(path) as f:
        return f.read().strip()
```

## Message Flow

```
User (Conversations app)                axios-ai-bot                     Claude API                    mcp-gateway
         │                                    │                              │                              │
         │  "What's on my calendar           │                              │                              │
         │   tomorrow?"                       │                              │                              │
         │ ──────────────────────────────────>│                              │                              │
         │                                    │                              │                              │
         │                                    │  Classify intent             │                              │
         │                                    │  (Haiku, minimal context)    │                              │
         │                                    │ ─────────────────────────────>│                              │
         │                                    │                              │                              │
         │                                    │  "category: calendar"        │                              │
         │                                    │ <─────────────────────────────│                              │
         │                                    │                              │                              │
         │                                    │  Execute with calendar tools │                              │
         │                                    │  (Sonnet, 3 tools only)      │                              │
         │                                    │ ─────────────────────────────>│                              │
         │                                    │                              │                              │
         │                                    │  tool_call: list_events      │                              │
         │                                    │ <─────────────────────────────│                              │
         │                                    │                              │                              │
         │                                    │  POST /api/tools/mcp-dav/list_events                        │
         │                                    │ ─────────────────────────────────────────────────────────────>│
         │                                    │                              │                              │
         │                                    │  [events...]                 │                              │
         │                                    │ <─────────────────────────────────────────────────────────────│
         │                                    │                              │                              │
         │                                    │  Format response             │                              │
         │                                    │  (Sonnet continues)          │                              │
         │                                    │ ─────────────────────────────>│                              │
         │                                    │                              │                              │
         │                                    │  "Tomorrow you have..."      │                              │
         │                                    │ <─────────────────────────────│                              │
         │                                    │                              │                              │
         │  "Tomorrow you have:              │                              │                              │
         │   - 10am: Dentist                 │                              │                              │
         │   - 2pm: Team standup"            │                              │                              │
         │ <──────────────────────────────────│                              │                              │
         │                                    │                              │                              │
```

## Configuration Examples

### Minimal NixOS Configuration (in axios consumer)

```nix
services.axios-chat = {
  prosody = {
    enable = true;
    domain = "chat.home.ts.net";
    admins = [ "keith@chat.home.ts.net" ];
  };

  bot = {
    enable = true;
    xmppDomain = "chat.home.ts.net";
    anthropicKeyFile = config.age.secrets.anthropic.path;
    xmppPasswordFile = config.age.secrets.ai-bot.path;
  };
};

# Ensure mcp-gateway is running
services.mcp-gateway.enable = true;
```

### User Account Setup

```bash
# Create XMPP accounts via prosodyctl
prosodyctl adduser keith@chat.home.ts.net
prosodyctl adduser spouse@chat.home.ts.net
prosodyctl adduser ai@chat.home.ts.net  # Bot account
```

Or declaratively via home-manager module (future enhancement).

## Risks / Trade-offs

| Risk | Mitigation |
|------|------------|
| Claude API costs | Intent-based routing, Haiku for classification |
| mcp-gateway unavailable | Graceful degradation with error message |
| Prosody misconfiguration exposes server | Strong defaults, validation in module |
| Bot overwhelmed by messages | Rate limiting per user |
| Tool definitions grow too large | Dynamic filtering by category |

## Open Questions

1. **Should the bot support group chat mentions?** Initial: DM only. Group chat via @ai mention in future.
2. **How to handle conversation context?** Initial: Last 5 messages. May need summarization for long conversations.
3. **Should there be per-user tool restrictions?** Deferred: All users get same capabilities initially.
4. **Voice message transcription?** Deferred: Text only for MVP.
