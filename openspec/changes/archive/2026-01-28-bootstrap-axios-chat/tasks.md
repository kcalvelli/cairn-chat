# Tasks: Bootstrap cairn-chat

## Phase 1: Project Infrastructure

### 1.1 Flake Setup
- [x] 1.1.1 Create `flake.nix` with nixpkgs and flake-parts inputs
- [x] 1.1.2 Configure supported systems (x86_64-linux, aarch64-linux)
- [x] 1.1.3 Export nixosModules (default, prosody, bot)
- [x] 1.1.4 Export homeManagerModules.default
- [x] 1.1.5 Export packages.${system}.cairn-ai-bot
- [x] 1.1.6 Verify with `nix flake check`

### 1.2 Directory Structure
- [x] 1.2.1 Create `modules/nixos/` directory
- [x] 1.2.2 Create `modules/home-manager/` directory
- [x] 1.2.3 Create `pkgs/cairn-ai-bot/` directory
- [x] 1.2.4 Create `docs/` directory

### 1.3 Documentation
- [x] 1.3.1 Create README.md with project overview
- [x] 1.3.2 Document installation instructions
- [x] 1.3.3 Document configuration examples
- [x] 1.3.4 Add CODE_OF_ETHICS.md (copy from cairn ecosystem)

## Phase 2: Prosody NixOS Module

### 2.1 Module Structure
- [x] 2.1.1 Create `modules/nixos/prosody.nix` with option definitions
- [x] 2.1.2 Define `services.cairn-chat.prosody.enable` option
- [x] 2.1.3 Define `services.cairn-chat.prosody.domain` option
- [x] 2.1.4 Define `services.cairn-chat.prosody.tailscaleIP` option
- [x] 2.1.5 Define `services.cairn-chat.prosody.admins` option
- [x] 2.1.6 Define `services.cairn-chat.prosody.muc.*` options

### 2.2 Prosody Configuration
- [x] 2.2.1 Configure interface binding to Tailscale IP
- [x] 2.2.2 Disable s2s (federation) module
- [x] 2.2.3 Enable required modules (roster, sasl, tls, dialback, disco, posix, private, vcard, ping, register, admin_adhoc, mam)
- [x] 2.2.4 Configure virtual host from domain option
- [x] 2.2.5 Configure MUC component when enabled
- [x] 2.2.6 Set c2sRequireEncryption = true
- [x] 2.2.7 Configure message archive (MAM) settings

### 2.3 Tailscale Integration
- [x] 2.3.1 Add assertion for Tailscale service dependency
- [ ] 2.3.2 Implement Tailscale IP auto-detection (optional) - Deferred
- [x] 2.3.3 Add helpful error message when Tailscale IP not configured

### 2.4 Testing
- [x] 2.4.1 Test module imports without errors
- [ ] 2.4.2 Test with minimal configuration - Requires actual NixOS system
- [ ] 2.4.3 Verify Prosody binds only to Tailscale IP - Requires actual NixOS system
- [ ] 2.4.4 Verify federation is disabled - Requires actual NixOS system

## Phase 3: cairn-ai-bot Python Package

### 3.1 Package Setup
- [x] 3.1.1 Create `pkgs/cairn-ai-bot/pyproject.toml`
- [x] 3.1.2 Define dependencies: slixmpp, anthropic, httpx, pydantic
- [x] 3.1.3 Create `pkgs/cairn-ai-bot/src/cairn_ai_bot/__init__.py`
- [x] 3.1.4 Create package build in flake.nix using buildPythonApplication
- [x] 3.1.5 Verify package builds with `nix build .#cairn-ai-bot`

### 3.2 XMPP Client Module
- [x] 3.2.1 Create `src/cairn_ai_bot/xmpp.py`
- [x] 3.2.2 Implement slixmpp ClientXMPP subclass
- [x] 3.2.3 Implement connection with credentials from environment
- [x] 3.2.4 Implement message handler for incoming DMs
- [x] 3.2.5 Implement send_message method
- [x] 3.2.6 Implement reconnection logic with backoff
- [x] 3.2.7 Implement chat state notifications (composing)

### 3.3 Tool Registry Module
- [x] 3.3.1 Create `src/cairn_ai_bot/tools.py`
- [x] 3.3.2 Implement DynamicToolRegistry class
- [x] 3.3.3 Implement refresh() to fetch from mcp-gateway
- [x] 3.3.4 Implement tool categorization by server name
- [x] 3.3.5 Implement get_tools_for_categories() method
- [x] 3.3.6 Implement execute_tool() via mcp-gateway HTTP
- [x] 3.3.7 Add caching and periodic refresh logic

### 3.4 Intent Router Module
- [x] 3.4.1 Create `src/cairn_ai_bot/router.py`
- [x] 3.4.2 Implement keyword-based fast classification
- [x] 3.4.3 Implement Haiku-based classification fallback
- [x] 3.4.4 Define category mappings (email, calendar, contacts, general, etc.)
- [x] 3.4.5 Implement classify_intent() async method

### 3.5 LLM Integration Module
- [x] 3.5.1 Create `src/cairn_ai_bot/llm.py`
- [x] 3.5.2 Implement AnthropicClient class (named LLMClient)
- [x] 3.5.3 Implement classify_with_haiku() method (named classify_intent)
- [x] 3.5.4 Implement execute_with_sonnet() method with tools (named execute_with_tools)
- [x] 3.5.5 Implement tool result handling loop
- [x] 3.5.6 Implement conversation context management
- [x] 3.5.7 Add error handling for rate limits

### 3.6 Main Entry Point
- [x] 3.6.1 Create `src/cairn_ai_bot/main.py`
- [x] 3.6.2 Implement configuration loading from environment
- [x] 3.6.3 Implement secret loading from files
- [x] 3.6.4 Wire together XMPP client, tool registry, router, LLM
- [x] 3.6.5 Implement graceful shutdown handling
- [x] 3.6.6 Add CLI entry point in pyproject.toml

### 3.7 Testing
- [x] 3.7.1 Create `tests/` directory
- [ ] 3.7.2 Write unit tests for tool registry - Deferred to Phase 7
- [ ] 3.7.3 Write unit tests for intent router - Deferred to Phase 7
- [ ] 3.7.4 Write integration tests with mocked APIs - Deferred to Phase 7

## Phase 4: Bot NixOS Module

### 4.1 Module Structure
- [x] 4.1.1 Create `modules/nixos/bot.nix` with option definitions
- [x] 4.1.2 Define `services.cairn-chat.bot.enable` option
- [x] 4.1.3 Define `services.cairn-chat.bot.xmppUser` option (default: "ai")
- [x] 4.1.4 Define `services.cairn-chat.bot.xmppDomain` option
- [x] 4.1.5 Define `services.cairn-chat.bot.xmppPasswordFile` option
- [x] 4.1.6 Define `services.cairn-chat.bot.anthropicKeyFile` option
- [x] 4.1.7 Define `services.cairn-chat.bot.mcpGatewayUrl` option (default: "http://localhost:8085")
- [x] 4.1.8 Define `services.cairn-chat.bot.toolRefreshInterval` option (default: 300)
- [x] 4.1.9 Define `services.cairn-chat.bot.systemPromptFile` option

### 4.2 Systemd Service
- [x] 4.2.1 Create systemd service definition
- [x] 4.2.2 Set After=network-online.target, prosody.service
- [x] 4.2.3 Set Restart=always, RestartSec=5
- [x] 4.2.4 Configure environment variables from options
- [x] 4.2.5 Add security hardening (DynamicUser, ProtectSystem, etc.)
- [x] 4.2.6 Reference cairn-ai-bot package in ExecStart

### 4.3 Testing
- [x] 4.3.1 Test module imports without errors
- [ ] 4.3.2 Test service definition generation - Requires actual NixOS system
- [ ] 4.3.3 Verify environment variable mapping - Requires actual NixOS system

## Phase 5: Combined NixOS Module

### 5.1 Module Integration
- [x] 5.1.1 Create `modules/nixos/default.nix` importing prosody and bot
- [x] 5.1.2 Add assertion: bot requires prosody or external XMPP
- [x] 5.1.3 Test combined module import

## Phase 6: Home-Manager Module

### 6.1 Module Structure
- [x] 6.1.1 Create `modules/home-manager/default.nix`
- [x] 6.1.2 Define `programs.cairn-chat.enable` option
- [x] 6.1.3 Define `programs.cairn-chat.defaultAccount` option
- [x] 6.1.4 Document future expansion points

## Phase 7: Integration Testing

### 7.1 Local Testing
- [ ] 7.1.1 Create NixOS VM test configuration
- [ ] 7.1.2 Test Prosody starts and accepts connections
- [ ] 7.1.3 Test bot connects to Prosody
- [ ] 7.1.4 Test bot responds to messages

### 7.2 cairn Integration
- [ ] 7.2.1 Add cairn-chat as input to cairn flake
- [ ] 7.2.2 Import module in cairn configuration
- [ ] 7.2.3 Verify builds without conflicts
- [ ] 7.2.4 Test on actual Tailscale network

## Phase 8: Documentation Finalization

### 8.1 User Documentation
- [x] 8.1.1 Write XMPP client setup guide (Conversations, Gajim, Dino)
- [x] 8.1.2 Document user account creation with prosodyctl
- [ ] 8.1.3 Write troubleshooting guide - Deferred until testing
- [x] 8.1.4 Document cost estimation and optimization

### 8.2 OpenSpec Finalization
- [ ] 8.2.1 Move specs to main `openspec/specs/` directory
- [ ] 8.2.2 Archive this change directory
- [ ] 8.2.3 Update project.md if needed

---

## Summary

**Completed Phases:**
- Phase 1: Project Infrastructure ✅
- Phase 2: Prosody NixOS Module ✅ (minus runtime testing)
- Phase 3: cairn-ai-bot Python Package ✅ (unit tests deferred)
- Phase 4: Bot NixOS Module ✅ (minus runtime testing)
- Phase 5: Combined NixOS Module ✅
- Phase 6: Home-Manager Module ✅

**Pending Phases:**
- Phase 7: Integration Testing (requires actual NixOS system with Tailscale)
- Phase 8: Documentation Finalization (partial - troubleshooting guide pending)

**Deferred Items:**
- Tailscale IP auto-detection (2.3.2)
- Unit tests for Python modules (3.7.x)
- Runtime testing on actual NixOS system (2.4.x, 4.3.x, 7.x)
- OpenSpec archival (8.2.x)

## Dependency Graph

```
Phase 1 (Infrastructure) ✅
    │
    ├──> Phase 2 (Prosody Module) ✅
    │         │
    │         └──> Phase 5 (Combined Module) ✅
    │                     │
    │                     └──> Phase 7 (Integration) ⏳
    │
    └──> Phase 3 (Python Package) ✅
              │
              └──> Phase 4 (Bot Module) ✅
                        │
                        └──> Phase 5 (Combined Module) ✅

Phase 6 (Home-Manager) ✅ - Completed independently

Phase 8 (Docs) ⏳ - Partially complete
```
