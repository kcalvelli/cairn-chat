# nix-modules Specification

## Purpose

NixOS module packaging for the cairn-chat Prosody XMPP server, providing
declarative configuration for private family chat over Tailscale.

## Requirements

### Requirement: Flake Structure

The project SHALL be a standalone Nix flake with module exports.

#### Scenario: Flake outputs

- **GIVEN** the cairn-chat flake
- **WHEN** inspected with `nix flake show`
- **THEN** it exposes:
  - `nixosModules.default` (prosody module)
  - `nixosModules.prosody` (prosody only, same as default)
  - `homeManagerModules.default`

#### Scenario: Import in consumer flake

- **GIVEN** a consumer flake (e.g., cairn) with:
  ```nix
  inputs.cairn-chat.url = "github:kcalvelli/cairn-chat";
  ```
- **WHEN** the consumer imports the NixOS module
- **THEN** `services.cairn-chat.prosody.*` options become available

### Requirement: No Circular Dependencies

The flake SHALL NOT depend on cairn or other downstream projects as inputs.

#### Scenario: Standalone evaluation

- **GIVEN** cairn-chat flake.nix
- **WHEN** `nix flake check` is run
- **THEN** the check succeeds without external inputs beyond nixpkgs

### Requirement: NixOS Prosody Module Options

The system SHALL provide prosody configuration options under `services.cairn-chat.prosody`.

#### Scenario: Enable option

- **GIVEN** `services.cairn-chat.prosody.enable = true`
- **WHEN** the system is rebuilt
- **THEN** Prosody is installed and configured
- **AND** the systemd service is enabled

#### Scenario: Domain option

- **GIVEN** `services.cairn-chat.prosody.domain = "chat.example.ts.net"`
- **WHEN** the system is rebuilt
- **THEN** Prosody is configured for that domain
- **AND** users can register with @chat.example.ts.net JIDs

#### Scenario: Tailscale Serve option

- **GIVEN** `services.cairn-chat.prosody.tailscaleServe.enable = true`
- **WHEN** the system is rebuilt
- **THEN** XMPP is exposed via Tailscale Serve
- **AND** a DNS name is created for the service

#### Scenario: Tailscale IP option (legacy)

- **GIVEN** `services.cairn-chat.prosody.tailscaleIP = "100.64.0.1"`
- **AND** `services.cairn-chat.prosody.tailscaleServe.enable = false`
- **WHEN** the system is rebuilt
- **THEN** Prosody binds only to that IP

#### Scenario: Admins option

- **GIVEN** `services.cairn-chat.prosody.admins = ["keith@chat.home.ts.net"]`
- **WHEN** keith logs in
- **THEN** keith has administrative privileges

#### Scenario: MUC options

- **GIVEN** `services.cairn-chat.prosody.muc.enable = true`
- **AND** `services.cairn-chat.prosody.muc.domain = "rooms.chat.ts.net"`
- **WHEN** the system is rebuilt
- **THEN** MUC is available at the specified domain

### Requirement: Home-Manager Module

The system SHALL provide a home-manager module for user preferences.

#### Scenario: User preferences

- **GIVEN** a home-manager configuration with:
  ```nix
  programs.cairn-chat = {
    enable = true;
    defaultAccount = "keith@chat.ts.net";
  };
  ```
- **WHEN** home-manager activates
- **THEN** user preferences are stored
- **AND** can be referenced by XMPP clients

### Requirement: Integration with cairn

The system SHALL integrate cleanly when imported by cairn.

#### Scenario: Import in cairn modules

- **GIVEN** cairn imports cairn-chat as a flake input
- **WHEN** cairn adds `inputs.cairn-chat.nixosModules.default` to imports
- **THEN** the module integrates without conflicts
- **AND** follows cairn naming conventions (services.cairn-chat.*)

#### Scenario: Secret management compatibility

- **GIVEN** cairn uses agenix for secrets
- **WHEN** XMPP user passwords are managed via agenix
- **THEN** Prosody can read the decrypted secrets at runtime
