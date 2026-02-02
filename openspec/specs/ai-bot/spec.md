# ai-bot Specification

## Purpose
TBD - created by archiving change bootstrap-axios-chat. Update Purpose after archive.
## Requirements
### Requirement: XMPP Connection

The system SHALL connect to the Prosody server as an XMPP client.

#### Scenario: Bot connects on startup

- **GIVEN** axios-ai-bot is configured with valid XMPP credentials
- **WHEN** the service starts
- **THEN** it connects to the Prosody server
- **AND** sets presence to "available"
- **AND** appears in users' contact lists

#### Scenario: Connection failure

- **GIVEN** Prosody is not running
- **WHEN** axios-ai-bot attempts to connect
- **THEN** it logs an error
- **AND** retries with exponential backoff

#### Scenario: Reconnection

- **GIVEN** the bot is connected
- **WHEN** the connection is lost
- **THEN** the bot automatically reconnects
- **AND** resumes normal operation

### Requirement: Message Handling

The system SHALL receive and respond to direct messages.

#### Scenario: Receive direct message

- **GIVEN** the bot is connected
- **WHEN** a user sends a DM to the bot
- **THEN** the bot receives the message
- **AND** processes it through the LLM pipeline

#### Scenario: Send response

- **GIVEN** the bot has processed a message
- **WHEN** a response is ready
- **THEN** the bot sends the response to the user
- **AND** the message appears in the user's chat

#### Scenario: Typing indicator

- **GIVEN** the bot is processing a message
- **WHEN** processing takes more than 1 second
- **THEN** the bot sends a "composing" chat state
- **AND** clears it when the response is sent

### Requirement: Dynamic Tool Discovery

The system SHALL discover available tools from mcp-gateway at runtime and make all discovered tools available to the LLM.

#### Scenario: Initial tool discovery

- **GIVEN** mcp-gateway is running with registered MCP servers
- **WHEN** axios-ai-bot starts
- **THEN** it fetches the tool list from mcp-gateway
- **AND** all discovered tools are available to Gemini

#### Scenario: Periodic refresh

- **GIVEN** the bot is running
- **AND** `toolRefreshInterval = 300` (5 minutes)
- **WHEN** 5 minutes have elapsed
- **THEN** the bot refreshes its tool list
- **AND** new tools become available immediately

#### Scenario: On-demand refresh

- **GIVEN** the bot is running
- **AND** a new MCP server was enabled in mcp-gateway
- **WHEN** a user sends "/refresh"
- **THEN** the bot refreshes its tool list immediately
- **AND** confirms the number of available tools
- **AND** the new server's tools are usable in the next message

#### Scenario: Gateway unavailable

- **GIVEN** mcp-gateway is not running
- **WHEN** the bot attempts to refresh tools
- **THEN** it logs a warning
- **AND** continues with the previously cached tool list
- **AND** informs users that some capabilities may be unavailable

### Requirement: Tool Execution

The system SHALL execute tools via mcp-gateway using Gemini function calling.

#### Scenario: Successful tool call

- **GIVEN** the LLM requests tool "mcp-dav__list_events"
- **WHEN** the bot executes the tool
- **THEN** it calls `POST /api/tools/mcp-dav/list_events` on mcp-gateway
- **AND** returns the result to the LLM as a `function_response`

#### Scenario: Tool execution error

- **GIVEN** the LLM requests a tool
- **AND** the tool fails (e.g., permission denied)
- **WHEN** the bot receives the error
- **THEN** it passes the error to the LLM
- **AND** the LLM generates an appropriate user-facing message

#### Scenario: Multi-step tool chain

- **GIVEN** a user requests "Send an email to John about rescheduling"
- **WHEN** the LLM processes this
- **THEN** it may call search_contacts to find John's email
- **AND** then call compose_email with the found address
- **AND** then call send_email with the draft

### Requirement: Conversation Context

The system SHALL maintain conversation context within a session.

#### Scenario: Follow-up questions

- **GIVEN** a user asked "What's on my calendar tomorrow?"
- **AND** the bot responded with a list of events
- **WHEN** the user asks "Cancel the first one"
- **THEN** the bot understands "first one" refers to the first calendar event
- **AND** takes appropriate action

#### Scenario: Context window limit

- **GIVEN** a conversation has many messages
- **WHEN** the context exceeds the limit (e.g., 10 messages)
- **THEN** older messages are dropped
- **OR** summarized to preserve important context

### Requirement: NixOS Module Interface

The system SHALL provide a NixOS module for bot configuration.

#### Scenario: Minimal configuration

- **GIVEN** a NixOS configuration with:
  ```nix
  services.axios-chat.bot = {
    enable = true;
    xmppDomain = "chat.home.ts.net";
    xmppPasswordFile = "/run/secrets/bot-password";
    geminiApiKeyFile = "/run/secrets/gemini-api-key";
  };
  ```
- **WHEN** the system is rebuilt
- **THEN** the bot service starts
- **AND** connects to Prosody
- **AND** is ready to receive messages

#### Scenario: Custom mcp-gateway URL

- **GIVEN** `services.axios-chat.bot.mcpGatewayUrl = "http://192.168.1.10:8085"`
- **WHEN** the bot fetches tools
- **THEN** it connects to the specified URL

#### Scenario: Custom bot username

- **GIVEN** `services.axios-chat.bot.xmppUser = "assistant"`
- **WHEN** the bot connects
- **THEN** it uses JID "assistant@chat.home.ts.net"

### Requirement: System Prompt Customization

The system SHALL support customizable system prompts.

#### Scenario: Default persona

- **GIVEN** no custom system prompt is configured
- **WHEN** the bot processes messages
- **THEN** it uses the default "Axios AI Assistant" persona

#### Scenario: Custom persona

- **GIVEN** `services.axios-chat.bot.systemPromptFile = "/etc/axios-chat/prompt.txt"`
- **AND** the file contains a custom persona
- **WHEN** the bot processes messages
- **THEN** it uses the custom system prompt

### Requirement: Error Handling

The system SHALL handle errors gracefully.

#### Scenario: API rate limit

- **GIVEN** the Gemini API returns a rate limit error
- **WHEN** the bot receives this error
- **THEN** it informs the user about temporary unavailability
- **AND** implements backoff before retrying

#### Scenario: Invalid tool response

- **GIVEN** mcp-gateway returns malformed JSON
- **WHEN** the bot processes the response
- **THEN** it logs the error
- **AND** informs the user that the action couldn't be completed

