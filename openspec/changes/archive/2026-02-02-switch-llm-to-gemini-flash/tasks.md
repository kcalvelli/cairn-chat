# Tasks: Switch LLM Backend to Gemini Flash

## Implementation Order

Tasks are ordered by dependency. Tasks within the same group can be parallelized.

### Group 1: Dependencies and Configuration

- [x] **T1: Update Python dependencies**
  - Replace `anthropic>=0.18.0` with `google-genai>=1.0.0` in `pyproject.toml`
  - Verify: `pip install -e ./pkgs/cairn-ai-bot` succeeds

- [x] **T2: Update Nix package dependencies**
  - Replace `python3Packages.anthropic` with `python3Packages.google-genai` in `flake.nix`
  - Verify: `nix build .#cairn-ai-bot` succeeds

- [x] **T3: Update NixOS module options**
  - Rename `claudeApiKeyFile` to `geminiApiKeyFile` in `modules/nixos/bot.nix`
  - Replace `ANTHROPIC_API_KEY_FILE` with `GEMINI_API_KEY_FILE` in systemd environment
  - Update `BindReadOnlyPaths` to reference new option
  - Update module description comment
  - Verify: `nix flake check` passes

### Group 2: Core LLM Backend (depends on T1)

- [x] **T4: Implement GeminiClient**
  - Create `pkgs/cairn-ai-bot/src/cairn_ai_bot/llm/gemini.py` implementing `LLMBackend`
  - Implement `__init__` with `google.genai.Client` initialization
  - Implement `execute_with_tools` with Gemini function calling loop
  - Implement `simple_response` for tool-free conversations
  - Implement `clear_history`
  - Handle conversation history with `role: "user"` / `role: "model"`
  - Use `gemini-2.0-flash` model constant
  - Verify: unit tests pass for tool format conversion and response extraction

- [x] **T5: Add Gemini content format to UserMessage**
  - Add `to_gemini_parts()` method to `UserMessage` in `media.py`
  - Convert text to Gemini `Part` format
  - Convert image attachments to `Part.from_bytes()` with correct mime_type
  - Convert PDF attachments to `Part.from_bytes()` with correct mime_type
  - Verify: text-only and multimodal messages produce valid Gemini content

- [x] **T6: Add Gemini tool formatting to DynamicToolRegistry**
  - Add `format_tools_for_gemini()` method to `tools.py`
  - Convert internal tool representation to FunctionDeclaration dict format
  - Handle `input_schema` passthrough for Gemini
  - Verify: tools from mcp-gateway are correctly formatted for Gemini API

### Group 3: Wiring (depends on T4, T5, T6)

- [x] **T7: Update LLM factory and imports**
  - Update `llm/__init__.py`: replace `AnthropicClient` with `GeminiClient`
  - Update `create_llm_client` to accept `api_key` (Gemini key) and instantiate `GeminiClient`
  - Update `__all__` exports
  - Verify: `create_llm_client({"api_key": "test"})` returns `GeminiClient` instance

- [x] **T8: Update main.py configuration**
  - Replace `anthropic_key` / `ANTHROPIC_API_KEY_FILE` / `ANTHROPIC_API_KEY` with `gemini_key` / `GEMINI_API_KEY_FILE` / `GEMINI_API_KEY`
  - Pass `gemini_key` to `create_llm_client`
  - Verify: bot starts with `GEMINI_API_KEY` environment variable

- [x] **T9: Simplify router.py**
  - Remove `DomainRegistry` import and `domain_registry` parameter from `MessageRouter`
  - Remove `enable_domain_routing` parameter
  - Remove the `execute_with_routing` code path -- always use `execute_with_tools`
  - Update `create_message_handler` to not pass domain registry
  - Verify: messages route directly to `execute_with_tools` with all tools

### Group 4: Cleanup (depends on T7, T8, T9)

- [x] **T10: Remove Anthropic-specific code**
  - Delete `llm/anthropic.py`
  - Delete `domains.py`
  - Remove `format_tools_for_claude()` from `tools.py`
  - Remove `to_claude_content()` and `to_claude_content_block()` from `media.py`
  - Remove router prompt template and `build_router_prompt` / `format_domain_list` from `prompts.py`
  - Remove unused `base64` import from `media.py`
  - Verify: no remaining imports of deleted modules; `rg "anthropic|claude|domain" --type py` shows no stale references

- [x] **T11: Update system prompt**
  - Review `get_default_system_prompt()` in `prompts.py` for any Claude-specific language
  - Verify prompt is provider-neutral
  - Verify: system prompt contains no references to Claude or Anthropic

### Group 5: Specs and Documentation (depends on T10)

- [x] **T12: Update project.md and AGENTS.md**
  - Update tech stack in `openspec/project.md` (Gemini replaces Anthropic)
  - Update architecture principles (remove domain routing reference)
  - Update external dependencies (Gemini API key replaces Anthropic)
  - Update `openspec/AGENTS.md` Python code standards (Gemini SDK replaces Anthropic SDK)
  - Verify: `openspec validate switch-llm-to-gemini-flash --strict` passes

### Group 6: Integration Testing

- [x] **T13: End-to-end verification**
  - Build with `nix build .#cairn-ai-bot` -- passes
  - Smoke test: bot starts, imports Gemini SDK, fails correctly on missing XMPP_JID
  - Remaining manual tests (deploy with real key, tool calls, media, etc.) deferred to deployment
