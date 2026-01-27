# axios-ai-bot

AI-powered XMPP bot for the axios ecosystem.

## Features

- Connects to Prosody XMPP server as an AI assistant
- Integrates with Claude API (Haiku + Sonnet)
- Dynamic tool discovery from mcp-gateway
- Intent-based routing for cost optimization

## Installation

This package is typically installed via the axios-chat NixOS module. See the main project README for details.

## Environment Variables

- `XMPP_JID`: Bot's XMPP JID (e.g., `ai@chat.example.ts.net`)
- `XMPP_PASSWORD_FILE`: Path to file containing XMPP password
- `ANTHROPIC_API_KEY_FILE`: Path to file containing Anthropic API key
- `MCP_GATEWAY_URL`: URL of mcp-gateway (default: `http://localhost:8085`)
- `TOOL_REFRESH_INTERVAL`: Seconds between tool refreshes (default: `300`)
- `SYSTEM_PROMPT_FILE`: Optional custom system prompt file

## License

MIT
