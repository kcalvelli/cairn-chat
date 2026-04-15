# ai-bot Specification

## Purpose

TBD - created by archiving change bootstrap-cairn-chat. Update Purpose after archive.

## MODIFIED Requirements

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

### Requirement: Dynamic Tool Discovery

The system SHALL discover available tools from mcp-gateway at runtime and make all discovered tools available to the LLM.

#### Scenario: Initial tool discovery

- **GIVEN** mcp-gateway is running with registered MCP servers
- **WHEN** cairn-ai-bot starts
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

## REMOVED Requirements

### Requirement: Intent Classification

~~The system SHALL classify user intent before tool selection.~~

Removed. All tools are sent to Gemini on every request. Gemini selects the appropriate tools based on user message content and tool descriptions.

### Requirement: Cost Optimization

~~The system SHALL minimize API costs through smart routing.~~

Removed. Gemini Flash pricing ($0.10/$0.40 per MTok) makes per-request tool filtering unnecessary. The cost of sending all tools is negligible.
