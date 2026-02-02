# llm-backend Specification

## Purpose

Defines the requirements for the Google Gemini LLM backend used by axios-ai-bot for AI-powered XMPP interactions with dynamic tool execution.

## MODIFIED Requirements

### Requirement: Gemini API Integration

The system SHALL use Google Gemini API for all LLM operations.

#### Scenario: Bot startup with API key

- **GIVEN** the bot is configured with `geminiApiKeyFile` pointing to a valid key
- **WHEN** the bot starts
- **THEN** it initializes the Gemini client with the API key
- **AND** connects to the XMPP server

#### Scenario: Missing API key

- **GIVEN** no `geminiApiKeyFile` is configured
- **WHEN** NixOS evaluates the configuration
- **THEN** it fails with an assertion error

#### Scenario: Model selection

- **GIVEN** the bot is configured with a Gemini API key
- **WHEN** the bot processes any message
- **THEN** it uses `gemini-2.0-flash` for all operations (tool execution and simple responses)

### Requirement: Tool Execution

The system SHALL execute tools via mcp-gateway using Gemini's native function calling format.

#### Scenario: Single tool call

- **GIVEN** a user asks "What's on my calendar tomorrow?"
- **WHEN** Gemini processes the message with all available tools
- **THEN** it generates a `function_call` part
- **AND** the tool is executed via mcp-gateway
- **AND** the result is sent back as a `function_response` part
- **AND** Gemini returns a natural language summary

#### Scenario: Multi-step tool operation

- **GIVEN** a user sends "Email John about our meeting tomorrow"
- **WHEN** Gemini processes the message
- **THEN** it may call search_contacts to find John's email
- **AND** may call list_events to find tomorrow's meeting
- **AND** composes and sends the email
- **AND** confirms completion to the user

#### Scenario: All tools available

- **GIVEN** mcp-gateway has 25 tools registered across 5 MCP servers
- **WHEN** a user sends any message
- **THEN** all 25 tools are sent to Gemini as function declarations
- **AND** Gemini selects the appropriate tools based on the request

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

The system SHALL provide NixOS module options for Gemini backend configuration.

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
- **THEN** the bot service starts with Gemini backend
- **AND** connects to the XMPP server
- **AND** discovers tools from mcp-gateway

### Requirement: Error Handling

The system SHALL handle API errors gracefully.

#### Scenario: API rate limit

- **GIVEN** the Gemini API returns a rate limit error
- **WHEN** the bot processes the error
- **THEN** it responds with a user-friendly message
- **AND** logs the error for debugging

#### Scenario: API unavailable

- **GIVEN** the Gemini API is unreachable
- **WHEN** the bot attempts to send a request
- **THEN** it responds with "I'm sorry, the AI service is currently unavailable."
- **AND** logs the connection error

## REMOVED Requirements

### Requirement: Domain Routing

~~The system SHALL use Haiku for intent classification and Sonnet for execution.~~

Removed. Domain routing is eliminated. All tools are sent directly to Gemini Flash on every request. See design.md for rationale.

### Requirement: Claude API Integration

~~The system SHALL use Anthropic Claude API for all LLM operations.~~

Replaced by Gemini API Integration above.
