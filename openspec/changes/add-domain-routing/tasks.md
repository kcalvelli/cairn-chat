# Tasks: Add Domain-Aware Routing

## Phase 1: Domain Registry

- [ ] **1.1 Create domain registry module**
  - Create `axios_ai_bot/domains.py`
  - Define `DomainConfig` dataclass with servers, tools, prompt_hint
  - Define `DOMAIN_REGISTRY` with initial domains (contacts, calendar, email, time, general)
  - Add `get_domain_tools()` function
  - Verify: Unit tests for domain lookup

- [ ] **1.2 Add domain configuration to NixOS module**
  - Add `domainRegistry` option to bot.nix
  - Allow overriding/extending default domains
  - Pass domain config to service
  - Verify: Custom domains can be defined in Nix

## Phase 2: Intent Router

- [ ] **2.1 Create router prompt template**
  - Add `ROUTER_PROMPT_TEMPLATE` to `llm/prompts.py`
  - Include domain list with descriptions
  - Include few-shot examples for common patterns
  - Verify: Prompt generates valid output format

- [ ] **2.2 Implement intent classification**
  - Add `classify_intent()` method to `OllamaClient`
  - Call Ollama with router prompt (no tools)
  - Parse comma-separated domain response
  - Handle edge cases (empty, invalid, unknown domains)
  - Verify: Unit tests for classification parsing

- [ ] **2.3 Add router timeout handling**
  - Set short timeout for router (5-10 seconds)
  - Fall back to "general" on timeout
  - Log classification failures for debugging
  - Verify: Timeout doesn't block main flow

## Phase 3: Tool Filtering

- [ ] **3.1 Implement domain-based tool filtering**
  - Add `filter_tools_by_domains()` function
  - Accept list of domains and full tool list
  - Return filtered tool list based on domain registry
  - Handle cross-domain merging
  - Verify: Correct tools returned for each domain

- [ ] **3.2 Update tool loading in router.py**
  - Integrate domain filtering into tool selection
  - Log domain classification and filtered tool count
  - Maintain full tool list for fallback
  - Verify: Tool count reduced in logs

## Phase 4: Execution Flow Integration

- [ ] **4.1 Update execute_with_tools() for routing**
  - Add optional `domains` parameter
  - If domains provided, filter tools before execution
  - Build focused system prompt from domain hints
  - Verify: Execution uses filtered tools

- [ ] **4.2 Create orchestrated execution flow**
  - New entry point: `execute_with_routing()`
  - Step 1: Classify intent
  - Step 2: Filter tools by domains
  - Step 3: Execute with filtered tools
  - Return result to user
  - Verify: End-to-end flow works

- [ ] **4.3 Update XMPP handler to use routing**
  - Switch from direct `execute_with_tools()` to `execute_with_routing()`
  - Maintain backward compatibility option
  - Verify: Bot responds via XMPP with routing

## Phase 5: Testing

- [ ] **5.1 Unit tests for domain registry**
  - Test domain lookup
  - Test tool filtering
  - Test cross-domain merging
  - Test unknown domain handling
  - Verify: All cases covered

- [ ] **5.2 Unit tests for intent classification**
  - Test single domain detection
  - Test multi-domain detection
  - Test general/fallback cases
  - Test malformed responses
  - Verify: Parser is robust

- [ ] **5.3 Integration tests**
  - Test full routing flow with mock Ollama
  - Test contacts query → contacts domain
  - Test "email John" → contacts + email domains
  - Test general chat → general domain
  - Verify: Classification matches expected domains

- [ ] **5.4 Manual acceptance testing**
  - Test with real Ollama
  - Verify response times improved
  - Test cross-domain queries
  - Document success rate
  - Verify: Performance criteria met

## Phase 6: Documentation

- [ ] **6.1 Update README**
  - Document routing architecture
  - Explain domain configuration
  - Add troubleshooting for misclassification
  - Verify: Users understand the system

- [ ] **6.2 Update project.md**
  - Add routing to architecture
  - Document domain registry
  - Verify: Project docs accurate

## Verification Checklist

Before marking complete:

- [ ] All unit tests pass
- [ ] Single-domain queries < 30 seconds
- [ ] Cross-domain queries < 60 seconds
- [ ] Domain classification >= 95% accurate
- [ ] No regression in tool calling
- [ ] New MCP servers work without code changes
- [ ] Documentation updated
