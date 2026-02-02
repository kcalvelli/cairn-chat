# nix-modules Specification

## Purpose
TBD - created by archiving change bootstrap-axios-chat. Update Purpose after archive.
## Requirements
### Requirement: Flake Structure

The project SHALL be a standalone Nix flake with module exports.

#### Scenario: Flake outputs

- **GIVEN** the axios-chat flake
- **WHEN** inspected with `nix flake show`
- **THEN** it exposes:
  - `nixosModules.default` (combined prosody + bot)
  - `nixosModules.prosody` (prosody only)
  - `nixosModules.bot` (bot only)
  - `homeManagerModules.default`
  - `packages.${system}.axios-ai-bot`
  - `packages.${system}.default`

#### Scenario: Import in consumer flake

- **GIVEN** a consumer flake (e.g., axios) with:
  ```nix
  inputs.axios-chat.url = "github:kcalvelli/axios-chat";
  ```
- **WHEN** the consumer imports the NixOS module
- **THEN** `services.axios-chat.*` options become available

### Requirement: No Circular Dependencies

The flake SHALL NOT depend on axios or mcp-gateway as inputs.

#### Scenario: Standalone build

- **GIVEN** axios-chat flake.nix
- **WHEN** `nix build .#axios-ai-bot` is run
- **THEN** the build succeeds without axios or mcp-gateway inputs

#### Scenario: Runtime configuration

- **GIVEN** the bot module is enabled
- **WHEN** `mcpGatewayUrl` is configured
- **THEN** the bot connects to mcp-gateway at runtime
- **AND** no build-time dependency exists

### Requirement: NixOS Prosody Module Options

The system SHALL provide the following prosody configuration options.

#### Scenario: Enable option

- **GIVEN** `services.axios-chat.prosody.enable = true`
- **WHEN** the system is rebuilt
- **THEN** Prosody is installed and configured
- **AND** the systemd service is enabled

#### Scenario: Domain option

- **GIVEN** `services.axios-chat.prosody.domain = "chat.example.ts.net"`
- **WHEN** the system is rebuilt
- **THEN** Prosody is configured for that domain
- **AND** users can register with @chat.example.ts.net JIDs

#### Scenario: Tailscale IP option

- **GIVEN** `services.axios-chat.prosody.tailscaleIP = "100.64.0.1"`
- **WHEN** the system is rebuilt
- **THEN** Prosody binds only to that IP

#### Scenario: Auto-detect Tailscale IP

- **GIVEN** `services.axios-chat.prosody.tailscaleIP` is not set
- **WHEN** the system is rebuilt
- **THEN** the module attempts to detect the Tailscale IP
- **OR** fails with a helpful error message

#### Scenario: Admins option

- **GIVEN** `services.axios-chat.prosody.admins = ["admin@chat.ts.net"]`
- **WHEN** the system is rebuilt
- **THEN** those JIDs have administrative privileges

#### Scenario: MUC options

- **GIVEN** `services.axios-chat.prosody.muc.enable = true`
- **AND** `services.axios-chat.prosody.muc.domain = "rooms.chat.ts.net"`
- **WHEN** the system is rebuilt
- **THEN** MUC is available at the specified domain

### Requirement: NixOS Bot Module Options

The system SHALL provide the following bot configuration options.

#### Scenario: Gemini API key

- **GIVEN** `services.axios-chat.bot.geminiApiKeyFile = "/run/secrets/gemini-api-key"`
- **WHEN** the bot starts
- **THEN** it reads the API key from the file
- **AND** uses it for Gemini API calls

#### Scenario: Enable option

- **GIVEN** `services.axios-chat.bot.enable = true`
- **WHEN** the system is rebuilt
- **THEN** the axios-ai-bot systemd service is created
- **AND** it starts after prosody.service

#### Scenario: XMPP credentials

- **GIVEN**:
  ```nix
  services.axios-chat.bot = {
    xmppUser = "ai";
    xmppDomain = "chat.ts.net";
    xmppPasswordFile = "/run/secrets/bot-pw";
  };
  ```
- **WHEN** the bot starts
- **THEN** it connects as "ai@chat.ts.net"
- **AND** reads the password from the specified file

### Requirement: Systemd Service Configuration

The system SHALL configure the systemd service with Gemini environment variables.

#### Scenario: Environment variables

- **GIVEN** the bot is configured with `geminiApiKeyFile`
- **WHEN** the systemd service starts
- **THEN** `GEMINI_API_KEY_FILE` is set to the configured path
- **AND** `ANTHROPIC_API_KEY_FILE` is NOT present in the environment

#### Scenario: Secret file binding

- **GIVEN** `geminiApiKeyFile = "/run/agenix/gemini-api-key"`
- **WHEN** the systemd service is evaluated
- **THEN** the path is included in `BindReadOnlyPaths`
- **AND** the service can read the decrypted secret

### Requirement: Home-Manager Module

The system SHALL provide a home-manager module for user preferences.

#### Scenario: User preferences

- **GIVEN** a home-manager configuration with:
  ```nix
  programs.axios-chat = {
    enable = true;
    defaultAccount = "keith@chat.ts.net";
  };
  ```
- **WHEN** home-manager activates
- **THEN** user preferences are stored
- **AND** can be referenced by XMPP clients

### Requirement: Option Types and Defaults

The system SHALL use appropriate option types with sensible defaults.

#### Scenario: Type validation

- **GIVEN** `services.axios-chat.bot.toolRefreshInterval = "five minutes"`
- **WHEN** the system is rebuilt
- **THEN** the build fails with a type error
- **AND** indicates that an integer is required

#### Scenario: Default values

- **GIVEN** only `services.axios-chat.bot.enable = true` is set
- **WHEN** examining the evaluated config
- **THEN** `mcpGatewayUrl` defaults to "http://localhost:8085"
- **AND** `xmppUser` defaults to "ai"
- **AND** `toolRefreshInterval` defaults to 300

### Requirement: Integration with axios

The system SHALL integrate cleanly when imported by axios.

#### Scenario: Import in axios modules

- **GIVEN** axios imports axios-chat as a flake input
- **WHEN** axios adds `inputs.axios-chat.nixosModules.default` to imports
- **THEN** the module integrates without conflicts
- **AND** follows axios naming conventions (services.axios-chat.*)

#### Scenario: Secret management compatibility

- **GIVEN** axios uses agenix for secrets
- **WHEN** axios-chat bot is configured with:
  ```nix
  geminiApiKeyFile = config.age.secrets.gemini-api-key.path;
  ```
- **THEN** the bot reads the decrypted secret at runtime

### Requirement: Python Package Dependencies

The system SHALL build the bot with Gemini SDK dependencies.

#### Scenario: Nix build

- **GIVEN** the flake.nix package definition
- **WHEN** `nix build .#axios-ai-bot` is run
- **THEN** the build includes `google-generativeai` (or `google-genai`) Python package
- **AND** does NOT include `anthropic` Python package

