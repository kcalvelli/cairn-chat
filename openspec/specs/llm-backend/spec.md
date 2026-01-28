# llm-backend Specification

## Purpose

Defines the requirements for the Anthropic Claude LLM backend used by axios-ai-bot for AI-powered XMPP interactions with domain routing (Haiku for classification, Sonnet for execution).

## Requirements

### Requirement: Claude API Integration

The system SHALL use Anthropic Claude API for all LLM operations.

#### Scenario: Bot startup with API key

- **GIVEN** the bot is configured with `claudeApiKeyFile` pointing to a valid key
- **WHEN** the bot starts
- **THEN** it initializes the Anthropic client
- **AND** connects to the XMPP server

#### Scenario: Missing API key

- **GIVEN** no `claudeApiKeyFile` is configured
- **WHEN** NixOS evaluates the configuration
- **THEN** it fails with an assertion error

### Requirement: Domain Routing

The system SHALL use Haiku for intent classification and Sonnet for execution.

#### Scenario: Simple query routing

- **GIVEN** a user sends "What time is it?"
- **WHEN** the message is processed
- **THEN** Haiku classifies the intent as "time" domain
- **AND** only time-related tools are passed to Sonnet
- **AND** Sonnet executes the appropriate tool

#### Scenario: Multi-domain query

- **GIVEN** a user sends "Email John about our meeting tomorrow"
- **WHEN** the message is processed
- **THEN** Haiku classifies as "contacts, email, calendar" domains
- **AND** tools from all matched domains are passed to Sonnet

#### Scenario: General conversation

- **GIVEN** a user sends "Tell me a joke"
- **WHEN** Haiku classifies the intent
- **THEN** it routes to the "general" domain
- **AND** Sonnet responds without tools

### Requirement: Tool Execution

The system SHALL execute tools via mcp-gateway using Claude's native tool_use format.

#### Scenario: Single tool call

- **GIVEN** a user asks "What's on my calendar tomorrow?"
- **WHEN** Sonnet processes the message with calendar tools
- **THEN** it generates a native tool_use block
- **AND** the tool is executed via mcp-gateway
- **AND** the result is fed back to Sonnet
- **AND** Sonnet returns a natural language summary

#### Scenario: Multi-step tool operation

- **GIVEN** a user sends "Email John about our meeting tomorrow"
- **WHEN** Sonnet processes the message
- **THEN** it may call search_contacts to find John's email
- **AND** may call list_events to find tomorrow's meeting
- **AND** composes and sends the email
- **AND** confirms completion to the user

### Requirement: Anti-Hallucination Measures

The system SHALL prevent fabricated information in responses.

#### Scenario: Tool data only

- **GIVEN** a user asks for contact information
- **WHEN** the contact tool returns no results
- **THEN** the bot tells the user the contact was not found
- **AND** does NOT fabricate contact details

#### Scenario: Missing data acknowledged

- **GIVEN** a tool returns partial results
- **WHEN** the bot generates a response
- **THEN** it only uses data from the tool response
- **AND** clearly indicates what information is missing

### Requirement: Conversation Context

The system SHALL maintain conversation context across turns.

#### Scenario: Context preserved

- **GIVEN** a user asked "What meetings do I have tomorrow?"
- **AND** the bot responded with a list
- **WHEN** the user asks "Cancel the first one"
- **THEN** the model has access to the previous exchange
- **AND** understands "first one" refers to the first meeting

#### Scenario: Context limit enforced

- **GIVEN** a conversation has 50 messages
- **AND** `max_context_messages = 10`
- **WHEN** a new message is processed
- **THEN** only the last 20 messages (10 exchanges) are sent
- **AND** older messages are dropped

### Requirement: NixOS Module Interface

The system SHALL provide NixOS module options for Claude backend configuration.

#### Scenario: Minimal configuration

- **GIVEN** a NixOS configuration with:
  ```nix
  services.axios-chat.bot = {
    enable = true;
    xmppDomain = "chat.home.ts.net";
    xmppPasswordFile = "/run/secrets/bot-password";
    claudeApiKeyFile = "/run/secrets/claude-api-key";
  };
  ```
- **WHEN** the system is rebuilt
- **THEN** the bot service starts with Claude backend
- **AND** connects to the XMPP server
- **AND** discovers tools from mcp-gateway

### Requirement: Error Handling

The system SHALL handle API errors gracefully.

#### Scenario: API rate limit

- **GIVEN** the Claude API returns a rate limit error
- **WHEN** the bot processes the error
- **THEN** it responds with a user-friendly message
- **AND** logs the error for debugging

#### Scenario: API unavailable

- **GIVEN** the Anthropic API is unreachable
- **WHEN** the bot attempts to send a request
- **THEN** it responds with "I'm sorry, the AI service is currently unavailable."
- **AND** logs the connection error
