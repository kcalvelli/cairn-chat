# Change: Switch LLM Backend from Anthropic Claude to Google Gemini Flash

## Why

Two problems converge on the same solution:

1. **Broken dynamic tool discovery**: The domain routing system (Haiku classifies intent, hardcoded `DEFAULT_DOMAINS` filters tools for Sonnet) silently drops any MCP tools not pre-registered in `domains.py`. Enabling a new MCP server in mcp-gateway and running `/refresh` correctly updates the tool registry, but the routing layer filters the new tools out before they reach the LLM. This is the root cause of the reported defect.

2. **Cost**: Anthropic Sonnet 4 costs $3.00/$15.00 per MTok (input/output). The domain routing was built to reduce token costs by filtering tools. Google Gemini 2.0 Flash costs $0.10/$0.40 per MTok -- 30x cheaper on input, 37x cheaper on output -- making the routing optimization unnecessary.

Switching to Gemini Flash eliminates the domain routing layer entirely. All discovered tools are sent on every request. No hardcoded whitelist, no Haiku classification step, no silent filtering. `/refresh` works as expected.

## What Changes

- **BREAKING**: Replaces Anthropic Claude with Google Gemini as the LLM provider
- New `GeminiClient` implementing the existing `LLMBackend` abstract interface
- `AnthropicClient` removed along with `domains.py` and all domain routing logic
- Tool format translation: mcp-gateway tools formatted as Gemini `function_declarations` instead of Claude `tool_use` format
- Gemini function calling response loop replaces Claude's `tool_use` / `tool_result` loop
- Media support translated: base64 image/document content blocks adapted to Gemini's `inline_data` format
- `google-genai` Python SDK replaces `anthropic` SDK in dependencies
- NixOS module: `claudeApiKeyFile` replaced by `geminiApiKeyFile`; `ANTHROPIC_API_KEY_FILE` env var replaced by `GEMINI_API_KEY_FILE`
- Router simplified: `enable_domain_routing` removed, all tools always sent via `execute_with_tools`
- `prompts.py` retains system prompt, progress messages, and user location context; router prompt template removed
- `create_llm_client` factory updated to instantiate `GeminiClient`
- `project.md` and `AGENTS.md` updated to reflect new provider

## Impact

- Affected specs: `llm-backend`, `ai-bot`, `nix-modules`
- Affected code:
  - `pkgs/axios-ai-bot/src/axios_ai_bot/llm/anthropic.py` (removed, replaced by `gemini.py`)
  - `pkgs/axios-ai-bot/src/axios_ai_bot/llm/__init__.py` (factory update)
  - `pkgs/axios-ai-bot/src/axios_ai_bot/llm/base.py` (no change)
  - `pkgs/axios-ai-bot/src/axios_ai_bot/llm/prompts.py` (remove router template)
  - `pkgs/axios-ai-bot/src/axios_ai_bot/domains.py` (removed)
  - `pkgs/axios-ai-bot/src/axios_ai_bot/router.py` (simplified, domain routing removed)
  - `pkgs/axios-ai-bot/src/axios_ai_bot/main.py` (config key rename)
  - `pkgs/axios-ai-bot/src/axios_ai_bot/media.py` (add Gemini content block format)
  - `pkgs/axios-ai-bot/src/axios_ai_bot/tools.py` (remove `format_tools_for_claude`, add `format_tools_for_gemini`)
  - `pkgs/axios-ai-bot/pyproject.toml` (swap `anthropic` for `google-genai`)
  - `flake.nix` (swap `anthropic` for `google-generativeai` in Nix deps)
  - `modules/nixos/bot.nix` (option rename, env var rename)
- Affected secrets: Gemini API key must be provisioned via agenix (same pattern as existing `claudeApiKeyFile`)
