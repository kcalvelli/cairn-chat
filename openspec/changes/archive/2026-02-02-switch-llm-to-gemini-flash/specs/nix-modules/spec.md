# nix-modules Specification

## Purpose

TBD - created by archiving change bootstrap-axios-chat. Update Purpose after archive.

## ADDED Requirements

### Requirement: Python Package Dependencies

The system SHALL build the bot with Gemini SDK dependencies.

#### Scenario: Nix build

- **GIVEN** the flake.nix package definition
- **WHEN** `nix build .#axios-ai-bot` is run
- **THEN** the build includes `google-generativeai` (or `google-genai`) Python package
- **AND** does NOT include `anthropic` Python package

## MODIFIED Requirements

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
