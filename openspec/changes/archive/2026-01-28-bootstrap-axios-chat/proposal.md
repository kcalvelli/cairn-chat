# Change: Bootstrap cairn-chat

## Why

The cairn ecosystem needs a unified communication platform that combines family messaging with AI-powered automation. Current options (OpenWebUI, standalone chat apps) don't provide reliable tool calling or integrate well with the existing MCP infrastructure.

cairn-chat provides:
- A private family instant messenger (like AIM, but Tailscale-only)
- An AI assistant that can actually "do stuff" via mcp-gateway
- Native XMPP clients on all platforms (no custom app development)
- Seamless integration with cairn-ai-mail, cairn-dav, and future MCP servers

## What Changes

This is a greenfield project that creates:

### 1. Project Infrastructure
- Nix flake with NixOS and home-manager module exports
- Python package for cairn-ai-bot
- OpenSpec structure for spec-driven development

### 2. Prosody XMPP Server Module
- NixOS module wrapping `services.prosody` with tailnet-only defaults
- Disabled federation (s2s)
- MUC (Multi-User Chat) support for group chats
- Tailscale interface binding

### 3. cairn-ai-bot
- Python package using slixmpp for XMPP
- Claude API integration (Haiku for routing, Sonnet for execution)
- Dynamic tool discovery from mcp-gateway
- Intent-based tool selection for cost optimization

### 4. NixOS Module for Bot
- Systemd service configuration
- Secret management (API keys, XMPP password)
- Runtime configuration (mcp-gateway URL, refresh intervals)

### 5. Home-Manager Module
- User XMPP account configuration
- Bot personality/system prompt customization

## Impact

- **New project**: No existing code affected
- **Dependencies**:
  - Runtime: mcp-gateway, Anthropic API
  - Build: nixpkgs, slixmpp, anthropic, httpx
- **Integration**: cairn imports as flake input

## Architecture Overview

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
│  │               (services.cairn-chat.prosody)                       │  │
│  └──────────────────────────────┬───────────────────────────────────┘  │
│                                 │                                       │
│                                 ▼                                       │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │                     cairn-ai-bot                                  │  │
│  │               (services.cairn-chat.bot)                           │  │
│  │                                                                   │  │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐   │  │
│  │  │ XMPP Client │  │ Tool Router │  │ Dynamic Tool Registry   │   │  │
│  │  │ (slixmpp)   │  │ (Haiku)     │  │ (from mcp-gateway)      │   │  │
│  │  └─────────────┘  └─────────────┘  └─────────────────────────┘   │  │
│  │                          │                      ▲                 │  │
│  │                          │         GET /api/tools (periodic)      │  │
│  │                          ▼                      │                 │  │
│  │              ┌───────────────────────┐          │                 │  │
│  │              │    Claude API         │          │                 │  │
│  │              │  (Haiku + Sonnet)     │          │                 │  │
│  │              └───────────────────────┘          │                 │  │
│  └──────────────────────────┬──────────────────────┘                 │  │
│                             │                                         │
│                             ▼                                         │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │                      mcp-gateway                                  │  │
│  │              (dynamic tool aggregation)                           │  │
│  └──────────────────────────┬───────────────────────────────────────┘  │
│                             │                                         │
│           ┌─────────────────┼─────────────────┐                       │
│           ▼                 ▼                 ▼                       │
│  ┌─────────────┐   ┌─────────────┐   ┌─────────────┐                 │
│  │cairn-ai-mail│   │  mcp-dav    │   │  Future MCP │                 │
│  │  (email)    │   │ (cal/cont)  │   │  servers    │                 │
│  └─────────────┘   └─────────────┘   └─────────────┘                 │
│                                                                       │
└───────────────────────────────────────────────────────────────────────┘
```

## Cost Model

| Usage Level | Interactions/Day | Estimated Monthly Cost |
|-------------|------------------|------------------------|
| Light       | 5                | ~$2-4                  |
| Moderate    | 15               | ~$6-10                 |
| Heavy       | 30               | ~$12-20                |

Costs are minimized via:
- Haiku for intent classification (~$0.001/request)
- Dynamic tool injection (only send relevant tools)
- Local handling of simple queries (greetings, time)
