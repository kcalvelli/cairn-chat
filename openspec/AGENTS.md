# Agent Instructions for axios-chat

You are an AI developer assistant working on axios-chat, a family XMPP chat system with AI assistant integration. Follow these instructions to maintain project integrity and ensure spec-driven development.

## Spec-Driven Development (SDD) Workflow

axios-chat uses the **OpenSpec** framework for SDD:

1. **Specs are the Source of Truth**: Consult `openspec/specs/` before making changes.
2. **Changes start in `openspec/changes/`**: Plan features as "deltas" before implementation.
3. **Tasks guide implementation**: Each change has a `tasks.md` with verification steps.

### Implementation Process

1. **Analyze**: Read user request and existing specs in `openspec/specs/`.
2. **Propose Delta**: Create `openspec/changes/[change-name]/`.
3. **Stage Specs**: Copy/modify relevant specs in `openspec/changes/[change-name]/specs/`.
4. **Create Tasks**: Write `tasks.md` with a checklist.
5. **Execute**: Implement code changes as defined in tasks.
6. **Finalize**: Update main specs and archive the change.

## axios-chat Specific Constraints

### Flake Architecture

- This is a **standalone flake** that other projects (like axios) import.
- Do NOT add axios as an input—this creates a circular dependency.
- mcp-gateway is a **runtime** dependency (URL config), not a flake input.

### Security Model

- **Tailscale-only**: All services bind to Tailscale interface.
- **No application auth**: Tailscale provides identity and access control.
- **Secrets via files**: Use `*File` options for API keys and passwords.

### NixOS Module Patterns

- Wrap all configs in `lib.mkIf cfg.enable { ... }`.
- Use `types.path` for secret file paths.
- Follow axios ecosystem naming: `services.axios-chat.*`.

### Python Code Standards

- Use `slixmpp` for async XMPP.
- Use `httpx` for async HTTP to mcp-gateway.
- Use `anthropic` SDK for Claude API.
- All functions should be typed.

## Summary of OpenSpec Files

- `openspec/project.md`: Project identity, tech stack, and core rules.
- `openspec/specs/`: Current source of truth for all features.
- `openspec/changes/`: Ongoing development deltas.
- `openspec/AGENTS.md`: (This file) Your operational instructions.
