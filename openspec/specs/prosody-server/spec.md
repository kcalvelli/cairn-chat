# prosody-server Specification

## Purpose
TBD - created by archiving change bootstrap-axios-chat. Update Purpose after archive.
## Requirements
### Requirement: Tailscale-Only Binding

The system SHALL bind Prosody exclusively to the Tailscale network interface.

#### Scenario: Server binds to Tailscale IP

- **GIVEN** axios-chat prosody is enabled
- **AND** the machine has a Tailscale IP (e.g., 100.x.x.x)
- **WHEN** Prosody starts
- **THEN** it listens only on the Tailscale IP
- **AND** is not accessible from other network interfaces

#### Scenario: Tailscale not running

- **GIVEN** axios-chat prosody is enabled
- **AND** Tailscale is not running
- **WHEN** Prosody attempts to start
- **THEN** the service fails with a clear error message
- **AND** suggests checking Tailscale status

### Requirement: Federation Disabled

The system SHALL disable XMPP server-to-server (s2s) federation.

#### Scenario: No external federation

- **GIVEN** axios-chat prosody is running
- **WHEN** an external XMPP server attempts to connect
- **THEN** the connection is refused
- **AND** no error is logged (silent rejection)

### Requirement: Virtual Host Configuration

The system SHALL configure a virtual host for the chat domain.

#### Scenario: Domain configuration

- **GIVEN** `services.axios-chat.prosody.domain = "chat.home.ts.net"`
- **WHEN** Prosody starts
- **THEN** it accepts connections for `chat.home.ts.net`
- **AND** users can register as `user@chat.home.ts.net`

#### Scenario: Admin users

- **GIVEN** `services.axios-chat.prosody.admins = ["keith@chat.home.ts.net"]`
- **WHEN** keith logs in
- **THEN** keith has administrative privileges
- **AND** can manage other users

### Requirement: Multi-User Chat (MUC)

The system SHALL provide MUC support for group chats.

#### Scenario: MUC domain

- **GIVEN** prosody is enabled with domain "chat.home.ts.net"
- **WHEN** Prosody starts
- **THEN** MUC is available at "muc.chat.home.ts.net"
- **AND** users can create and join rooms

#### Scenario: Room creation

- **GIVEN** MUC is enabled
- **WHEN** a user creates room "family@muc.chat.home.ts.net"
- **THEN** the room is created
- **AND** other users can join

### Requirement: Client-to-Server Encryption

The system SHALL require encryption for client connections.

#### Scenario: TLS required

- **GIVEN** axios-chat prosody is running
- **WHEN** a client attempts an unencrypted connection
- **THEN** the connection is upgraded to TLS
- **OR** rejected if TLS is not possible

### Requirement: Message Archive

The system SHALL store message history for offline delivery.

#### Scenario: Offline message delivery

- **GIVEN** user A sends a message to user B
- **AND** user B is offline
- **WHEN** user B comes online
- **THEN** user B receives the message

#### Scenario: Message archive query

- **GIVEN** messages have been exchanged in a conversation
- **WHEN** a client requests message history (MAM)
- **THEN** recent messages are returned
- **AND** the archive respects configured retention limits

### Requirement: NixOS Module Interface

The system SHALL provide a NixOS module with the following options.

#### Scenario: Minimal configuration

- **GIVEN** a NixOS configuration with:
  ```nix
  services.axios-chat.prosody = {
    enable = true;
    domain = "chat.home.ts.net";
  };
  ```
- **WHEN** the system is rebuilt
- **THEN** Prosody starts with secure defaults
- **AND** is accessible only via Tailscale

#### Scenario: Custom Tailscale IP

- **GIVEN** `services.axios-chat.prosody.tailscaleIP = "100.64.1.1"`
- **WHEN** Prosody starts
- **THEN** it binds to 100.64.1.1 specifically

#### Scenario: Disable MUC

- **GIVEN** `services.axios-chat.prosody.muc.enable = false`
- **WHEN** Prosody starts
- **THEN** MUC functionality is not available

