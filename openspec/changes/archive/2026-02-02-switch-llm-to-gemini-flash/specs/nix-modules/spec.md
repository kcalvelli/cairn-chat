# nix-modules Specification

## Purpose

TBD - created by archiving change bootstrap-cairn-chat. Update Purpose after archive.

## ADDED Requirements

### Requirement: Python Package Dependencies

The system SHALL build the bot with Gemini SDK dependencies.

#### Scenario: Nix build

- **GIVEN** the flake.nix package definition
- **WHEN** `nix build .#cairn-ai-bot` is run
- **THEN** the build includes `google-generativeai` (or `google-genai`) Python package
- **AND** does NOT include `anthropic` Python package

## MODIFIED Requirements

### Requirement: NixOS Bot Module Options

The system SHALL provide the following bot configuration options.

#### Scenario: Gemini API key

- **GIVEN** `services.cairn-chat.bot.geminiApiKeyFile = "/run/secrets/gemini-api-key"`
- **WHEN** the bot starts
- **THEN** it reads the API key from the file
- **AND** uses it for Gemini API calls

#### Scenario: Enable option

- **GIVEN** `services.cairn-chat.bot.enable = true`
- **WHEN** the system is rebuilt
- **THEN** the cairn-ai-bot systemd service is created
- **AND** it starts after prosody.service

#### Scenario: XMPP credentials

- **GIVEN**:
  ```nix
  services.cairn-chat.bot = {
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

### Requirement: Integration with cairn

The system SHALL integrate cleanly when imported by cairn.

#### Scenario: Import in cairn modules

- **GIVEN** cairn imports cairn-chat as a flake input
- **WHEN** cairn adds `inputs.cairn-chat.nixosModules.default` to imports
- **THEN** the module integrates without conflicts
- **AND** follows cairn naming conventions (services.cairn-chat.*)

#### Scenario: Secret management compatibility

- **GIVEN** cairn uses agenix for secrets
- **WHEN** cairn-chat bot is configured with:
  ```nix
  geminiApiKeyFile = config.age.secrets.gemini-api-key.path;
  ```
- **THEN** the bot reads the decrypted secret at runtime
