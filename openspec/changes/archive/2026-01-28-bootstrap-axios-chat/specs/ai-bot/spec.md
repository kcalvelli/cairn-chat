# ai-bot Specification

## Purpose

Provide an AI-powered XMPP bot that connects to mcp-gateway for tool execution, enabling natural language automation of email, calendar, contacts, and other MCP-enabled services.

## ADDED Requirements

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

The system SHALL discover available tools from mcp-gateway at runtime.

#### Scenario: Initial tool discovery

- **GIVEN** mcp-gateway is running with registered MCP servers
- **WHEN** axios-ai-bot starts
- **THEN** it fetches the tool list from mcp-gateway
- **AND** categorizes tools by server/domain

#### Scenario: Periodic refresh

- **GIVEN** the bot is running
- **AND** `toolRefreshInterval = 300` (5 minutes)
- **WHEN** 5 minutes have elapsed
- **THEN** the bot refreshes its tool list
- **AND** new tools become available immediately

#### Scenario: On-demand refresh

- **GIVEN** the bot is running
- **WHEN** a user sends "/refresh"
- **THEN** the bot refreshes its tool list immediately
- **AND** confirms the number of available tools

#### Scenario: Gateway unavailable

- **GIVEN** mcp-gateway is not running
- **WHEN** the bot attempts to refresh tools
- **THEN** it logs a warning
- **AND** continues with the previously cached tool list
- **AND** informs users that some capabilities may be unavailable

### Requirement: Intent Classification

The system SHALL classify user intent before tool selection.

#### Scenario: Email intent

- **GIVEN** a user sends "Send an email to John about lunch"
- **WHEN** the message is processed
- **THEN** the router classifies intent as "email"
- **AND** only email-related tools are sent to Sonnet

#### Scenario: Calendar intent

- **GIVEN** a user sends "What meetings do I have tomorrow?"
- **WHEN** the message is processed
- **THEN** the router classifies intent as "calendar"
- **AND** only calendar-related tools are sent to Sonnet

#### Scenario: Multiple intents

- **GIVEN** a user sends "Check my calendar and email John if I'm free"
- **WHEN** the message is processed
- **THEN** the router identifies both "calendar" and "email" intents
- **AND** tools from both categories are included

#### Scenario: General conversation

- **GIVEN** a user sends "Hello, how are you?"
- **WHEN** the message is processed
- **THEN** the router classifies intent as "general"
- **AND** no tools are sent (pure conversation)

### Requirement: Tool Execution

The system SHALL execute tools via mcp-gateway.

#### Scenario: Successful tool call

- **GIVEN** the LLM requests tool "mcp-dav__list_events"
- **WHEN** the bot executes the tool
- **THEN** it calls `POST /api/tools/mcp-dav/list_events` on mcp-gateway
- **AND** returns the result to the LLM

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

### Requirement: Cost Optimization

The system SHALL minimize API costs through smart routing.

#### Scenario: Haiku for classification

- **GIVEN** a user sends any message
- **WHEN** intent classification occurs
- **THEN** Claude Haiku is used (not Sonnet)
- **AND** minimal context is sent (just the message, not full history)

#### Scenario: Sonnet with filtered tools

- **GIVEN** intent is classified as "calendar"
- **AND** there are 20 total tools available
- **WHEN** Sonnet is invoked
- **THEN** only 3-5 calendar tools are included
- **AND** token usage is reduced by ~60%

#### Scenario: Local handling of simple queries

- **GIVEN** a user sends "What time is it?"
- **WHEN** the message is processed
- **THEN** the bot responds locally (no API call)
- **OR** uses the minimal Haiku path

### Requirement: NixOS Module Interface

The system SHALL provide a NixOS module for bot configuration.

#### Scenario: Minimal configuration

- **GIVEN** a NixOS configuration with:
  ```nix
  services.axios-chat.bot = {
    enable = true;
    xmppDomain = "chat.home.ts.net";
    xmppPasswordFile = "/run/secrets/bot-password";
    anthropicKeyFile = "/run/secrets/anthropic-key";
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

- **GIVEN** the Anthropic API returns a rate limit error
- **WHEN** the bot receives this error
- **THEN** it informs the user about temporary unavailability
- **AND** implements backoff before retrying

#### Scenario: Invalid tool response

- **GIVEN** mcp-gateway returns malformed JSON
- **WHEN** the bot processes the response
- **THEN** it logs the error
- **AND** informs the user that the action couldn't be completed
