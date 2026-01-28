# llm-backend Specification

## Purpose

Defines the abstracted LLM backend interface supporting multiple providers (Anthropic Claude, Ollama with Qwen3, and potentially others). This enables switching between cloud and local LLM providers while maintaining consistent tool calling behavior.

## ADDED Requirements

### Requirement: Backend Abstraction

The system SHALL support multiple LLM backends through a common interface.

#### Scenario: Backend selection via configuration

- **GIVEN** the bot is configured with `llmBackend = "ollama"`
- **AND** `ollamaUrl = "http://localhost:11434"`
- **AND** `ollamaModel = "qwen3:14b-q4_K_M"`
- **WHEN** the bot starts
- **THEN** it uses the Ollama backend for all LLM operations
- **AND** does not require an Anthropic API key

#### Scenario: Fallback to Anthropic

- **GIVEN** the bot is configured with `llmBackend = "anthropic"`
- **WHEN** the bot starts
- **THEN** it uses the Anthropic Claude backend
- **AND** requires the Claude API key file

#### Scenario: Invalid backend configuration

- **GIVEN** the bot is configured with `llmBackend = "invalid"`
- **WHEN** NixOS evaluates the configuration
- **THEN** it fails with a type error
- **AND** lists valid options (anthropic, ollama)

### Requirement: Ollama Tool Calling

The system SHALL execute tools via local Ollama using Hermes-style prompting for Qwen3.

#### Scenario: Single tool call

- **GIVEN** the bot is using Ollama backend with qwen3:14b-q4_K_M
- **AND** a user sends "What's on my calendar tomorrow?"
- **WHEN** the message is processed
- **THEN** the bot sends a Hermes-formatted prompt with calendar tools
- **AND** parses the `<tool_call>` response
- **AND** executes the calendar tool via mcp-gateway
- **AND** returns a natural language summary

#### Scenario: Multi-tool operation

- **GIVEN** the bot is using Ollama backend
- **AND** a user sends "Email John about our meeting tomorrow"
- **WHEN** the message is processed
- **THEN** the bot may call search_contacts to find John's email
- **AND** may call list_events to find tomorrow's meeting
- **AND** composes and sends the email
- **AND** confirms completion to the user

#### Scenario: Tool not found

- **GIVEN** the bot is using Ollama backend
- **AND** the model generates a tool call for "nonexistent_tool"
- **WHEN** the tool call is validated
- **THEN** the validation fails
- **AND** an error is returned to the model
- **AND** the model can retry with a valid tool

### Requirement: Anti-Hallucination Measures

The system SHALL prevent tool call hallucinations through multiple validation layers.

#### Scenario: Unknown tool name rejected

- **GIVEN** the bot has tools ["email__send", "calendar__list_events"]
- **AND** the model outputs `<tool_call>{"name": "weather__forecast", "arguments": {}}</tool_call>`
- **WHEN** the tool call is validated
- **THEN** validation fails with "Unknown tool: weather__forecast"
- **AND** the tool is NOT executed
- **AND** the error is fed back to the model for correction

#### Scenario: Extra arguments rejected

- **GIVEN** a tool "email__send" with schema `{required: ["to", "subject", "body"]}`
- **AND** the model outputs arguments `{"to": "...", "subject": "...", "body": "...", "priority": "high"}`
- **WHEN** the tool call is validated
- **THEN** validation fails with "Unknown argument: priority"
- **AND** the tool is NOT executed

#### Scenario: Missing required argument rejected

- **GIVEN** a tool "email__send" with schema `{required: ["to", "subject", "body"]}`
- **AND** the model outputs arguments `{"to": "...", "subject": "..."}`
- **WHEN** the tool call is validated
- **THEN** validation fails with "Missing required argument: body"
- **AND** the tool is NOT executed

#### Scenario: Valid tool call accepted

- **GIVEN** a tool "email__send" with schema `{required: ["to", "subject", "body"]}`
- **AND** the model outputs valid arguments matching the schema
- **WHEN** the tool call is validated
- **THEN** validation succeeds
- **AND** the tool is executed via mcp-gateway

### Requirement: Hermes Prompt Template

The system SHALL use Hermes-style prompting optimized for Qwen3 tool calling.

#### Scenario: Tools in system prompt

- **GIVEN** tools are available from mcp-gateway
- **WHEN** a message with tools is sent to Ollama
- **THEN** the system prompt contains `<tools>` XML tags
- **AND** each tool is described with JSON Schema
- **AND** the prompt includes explicit anti-hallucination instructions

#### Scenario: Tool call format

- **GIVEN** the model decides to call a tool
- **WHEN** generating output
- **THEN** it wraps the call in `<tool_call>` tags
- **AND** includes `{"name": "...", "arguments": {...}}` JSON

#### Scenario: Tool result format

- **GIVEN** a tool has been executed
- **WHEN** the result is fed back to the model
- **THEN** it is wrapped in `<tool_response>` tags
- **AND** includes the tool name and result content

#### Scenario: Thinking mode disabled for tools

- **GIVEN** the bot is processing a request that may need tools
- **WHEN** the prompt is constructed
- **THEN** it includes `/nothink` directive
- **AND** the `think` parameter is set to false
- **AND** no `<think>` blocks appear in tool-calling responses

### Requirement: Conversation Context

The system SHALL maintain conversation context across turns with the Ollama backend.

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

### Requirement: Error Handling

The system SHALL handle Ollama-specific errors gracefully.

#### Scenario: Ollama server unavailable

- **GIVEN** the Ollama server is not running
- **WHEN** the bot attempts to send a request
- **THEN** it catches the connection error
- **AND** responds with "I'm sorry, the AI service is currently unavailable."
- **AND** logs the error for debugging

#### Scenario: Model not found

- **GIVEN** the configured model "qwen3:14b-q4_K_M" is not pulled
- **WHEN** the bot attempts to chat
- **THEN** Ollama returns a 404 error
- **AND** the bot responds with a helpful error message
- **AND** suggests running `ollama pull qwen3:14b-q4_K_M`

#### Scenario: Malformed tool call JSON

- **GIVEN** the model outputs `<tool_call>not valid json</tool_call>`
- **WHEN** the response is parsed
- **THEN** the malformed call is skipped
- **AND** a warning is logged
- **AND** the model is prompted to retry with valid JSON

#### Scenario: Timeout handling

- **GIVEN** the Ollama server is slow to respond
- **AND** the request exceeds the 120-second timeout
- **WHEN** the timeout occurs
- **THEN** the bot responds with "The request took too long. Please try again."
- **AND** logs the timeout

### Requirement: NixOS Module Interface

The system SHALL provide NixOS module options for Ollama backend configuration.

#### Scenario: Ollama backend configuration

- **GIVEN** a NixOS configuration with:
  ```nix
  services.axios-chat.bot = {
    enable = true;
    llmBackend = "ollama";
    ollamaUrl = "http://localhost:11434";
    ollamaModel = "qwen3:14b-q4_K_M";
    ollamaTemperature = 0.2;
    xmppDomain = "chat.home.ts.net";
    xmppPasswordFile = "/run/secrets/bot-password";
  };
  ```
- **WHEN** the system is rebuilt
- **THEN** the bot service starts with Ollama backend
- **AND** connects to the specified Ollama server
- **AND** uses the specified model
- **AND** does NOT require claudeApiKeyFile

#### Scenario: Default temperature for tool calling

- **GIVEN** `ollamaTemperature` is not specified
- **WHEN** the bot processes tool-assisted requests
- **THEN** it uses temperature 0.2 (default)
- **AND** tool calls are deterministic and reliable

#### Scenario: Ollama service dependency

- **GIVEN** `llmBackend = "ollama"`
- **AND** `ollamaUrl = "http://localhost:11434"`
- **WHEN** the systemd service is configured
- **THEN** it includes `After=ollama.service` (if local)
- **AND** waits for Ollama to be ready before starting

### Requirement: Performance Optimization

The system SHALL optimize Ollama performance for responsive interactions.

#### Scenario: Model keep-alive

- **GIVEN** the bot is using Ollama backend
- **WHEN** processing requests
- **THEN** it uses keep-alive to maintain model in memory
- **AND** subsequent requests have lower latency

#### Scenario: Reasonable response time

- **GIVEN** a typical user query requiring one tool call
- **WHEN** processed by Ollama with qwen3:14b-q4_K_M
- **THEN** the total response time is under 10 seconds
- **AND** progress messages are sent for longer operations
