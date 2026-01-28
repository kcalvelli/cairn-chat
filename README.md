# axios-chat

A family-oriented XMPP chat system with an integrated AI assistant, designed for the axios ecosystem.

## Features

- **Private Family Messenger**: Like AIM, but only accessible within your Tailscale network
- **AI Assistant**: Chat with `@ai` to manage email, calendar, contacts, and more
- **Native Clients**: Use Conversations (Android), Gajim (Windows/Linux), Dino (Linux), or any XMPP client
- **Dynamic Tool Discovery**: New MCP servers added to mcp-gateway are automatically available
- **Flexible LLM Backend**: Choose between Claude API (cloud) or Ollama (local) for AI

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│  TAILNET                                                                │
│                                                                         │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │                     XMPP Clients                                  │  │
│  │  Conversations (Android) │ Gajim (Windows) │ Dino (Linux)        │  │
│  └──────────────────────────────┬───────────────────────────────────┘  │
│                                 │                                       │
│                                 ▼                                       │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │                    Prosody XMPP Server                            │  │
│  │               (Tailscale interface only)                          │  │
│  └──────────────────────────────┬───────────────────────────────────┘  │
│                                 │                                       │
│                                 ▼                                       │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │                     axios-ai-bot                                  │  │
│  │  Router → [Claude API | Ollama] → mcp-gateway → Tools            │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

## Installation

### As a Flake Input (Recommended)

Add to your `flake.nix`:

```nix
{
  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixpkgs-unstable";
    axios-chat.url = "github:kcalvelli/axios-chat";
  };

  outputs = { self, nixpkgs, axios-chat, ... }: {
    nixosConfigurations.myhost = nixpkgs.lib.nixosSystem {
      system = "x86_64-linux";
      modules = [
        axios-chat.nixosModules.default
        ./configuration.nix
      ];
    };
  };
}
```

### NixOS Configuration (Claude API)

```nix
{ config, ... }:

{
  # Enable axios-chat with Prosody and the AI bot (Claude backend)
  services.axios-chat = {
    prosody = {
      enable = true;
      domain = "chat.home.ts.net";  # Your Tailscale domain
      tailscaleIP = "100.64.0.1";   # Your machine's Tailscale IP
      admins = [ "admin@chat.home.ts.net" ];
    };

    bot = {
      enable = true;
      xmppDomain = "chat.home.ts.net";
      xmppPasswordFile = config.age.secrets.ai-bot-password.path;
      llmBackend = "anthropic";  # Default
      claudeApiKeyFile = config.age.secrets.anthropic-key.path;
      mcpGatewayUrl = "http://localhost:8085";
    };
  };

  # Ensure mcp-gateway is running for tool access
  services.mcp-gateway.enable = true;
}
```

### NixOS Configuration (Ollama - Local LLM)

```nix
{ config, ... }:

{
  # Enable Ollama service
  services.ollama = {
    enable = true;
    acceleration = "cuda";  # or "rocm" for AMD, null for CPU
  };

  # Enable axios-chat with Ollama backend
  services.axios-chat = {
    prosody = {
      enable = true;
      domain = "chat.home.ts.net";
      tailscaleIP = "100.64.0.1";
      admins = [ "admin@chat.home.ts.net" ];
    };

    bot = {
      enable = true;
      xmppDomain = "chat.home.ts.net";
      xmppPasswordFile = config.age.secrets.ai-bot-password.path;

      # Use local Ollama instead of Claude API
      llmBackend = "ollama";
      ollamaUrl = "http://localhost:11434";
      ollamaModel = "qwen3:14b-q4_K_M";
      ollamaTemperature = 0.2;  # Lower = more deterministic

      mcpGatewayUrl = "http://localhost:8085";
    };
  };

  services.mcp-gateway.enable = true;
}
```

### Ollama Model Setup

Before using the Ollama backend, pull the required model:

```bash
ollama pull qwen3:14b-q4_K_M
```

**Recommended models for tool calling:**
- `qwen3:14b-q4_K_M` - Best balance of quality and speed (~8GB VRAM)
- `qwen3:32b-q4_K_M` - Higher quality, more resources (~18GB VRAM)
- `qwen3:8b-q4_K_M` - Faster, less accurate (~5GB VRAM)

## User Account Setup

After enabling the module, create XMPP accounts:

```bash
# Create user accounts
sudo prosodyctl adduser keith@chat.home.ts.net
sudo prosodyctl adduser spouse@chat.home.ts.net

# Create the AI bot account
sudo prosodyctl adduser ai@chat.home.ts.net
# Use the same password as in your xmppPasswordFile
```

## Client Setup

### Android: Conversations

1. Install [Conversations](https://conversations.im/) from F-Droid or Play Store
2. Add account: `yourname@chat.home.ts.net`
3. Server: Use your Tailscale IP (e.g., `100.64.0.1`)
4. Add `ai@chat.home.ts.net` as a contact to chat with the AI

### Linux: Dino

1. Install Dino: `nix-shell -p dino`
2. Add account with your JID
3. Connect to your Tailscale IP

### Windows: Gajim

1. Download [Gajim](https://gajim.org/)
2. Add account with your JID
3. Set server to your Tailscale IP

## Talking to the AI

Once connected, add `ai@chat.home.ts.net` as a contact and start chatting:

```
You: What's on my calendar tomorrow?
AI: Tomorrow you have:
    - 10:00 AM: Dentist appointment
    - 2:00 PM: Team standup

You: Send an email to John about rescheduling lunch
AI: I'll send that email for you.
    [Searches contacts for John]
    [Composes email]
    Done! I've sent an email to john@example.com about rescheduling lunch.

You: /help
AI: Available commands:
    /help - Show this help message
    /refresh - Refresh available tools
    /tools - List available tool categories
    /clear - Clear conversation history
```

## Cost Comparison

### Claude API (Cloud)

| Usage Level | Interactions/Day | Monthly Cost |
|-------------|------------------|--------------|
| Light       | 5                | ~$2-4        |
| Moderate    | 15               | ~$6-10       |
| Heavy       | 30               | ~$12-20      |

### Ollama (Local)

| Cost Type | Amount |
|-----------|--------|
| Monthly API cost | $0 |
| Electricity | ~$5-15/month if running 24/7 |
| Hardware | One-time GPU investment |

**Ollama advantages:**
- No per-request costs
- Full privacy (data never leaves your network)
- No rate limits
- Works offline

**Claude advantages:**
- No hardware requirements
- Generally more reliable tool calling
- Easier setup

## Related Projects

- [axios](https://github.com/kcalvelli/axios) - NixOS framework
- [mcp-gateway](https://github.com/kcalvelli/mcp-gateway) - MCP tool aggregation
- [axios-ai-mail](https://github.com/kcalvelli/axios-ai-mail) - Email MCP server
- [axios-dav](https://github.com/kcalvelli/axios-dav) - Calendar/contacts MCP server

## License

MIT
