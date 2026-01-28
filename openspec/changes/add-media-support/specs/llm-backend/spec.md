# llm-backend Spec Delta

## MODIFIED Requirements

### Requirement: Claude API Integration

The system SHALL send multimodal content (text, images, documents) to Claude.

#### Scenario: Text-only message

- **GIVEN** a user sends a plain text message
- **WHEN** the message is sent to Claude
- **THEN** the content is a plain string (existing behavior preserved)

#### Scenario: Image message

- **GIVEN** a user sends a JPEG image
- **WHEN** the message is sent to Claude
- **THEN** the content is a list of blocks:
  - `{type: "image", source: {type: "base64", media_type: "image/jpeg", data: "..."}}`
  - `{type: "text", text: "user's caption or empty"}` (if caption provided)

#### Scenario: PDF document

- **GIVEN** a user sends a PDF file
- **WHEN** the message is sent to Claude
- **THEN** the content is a list of blocks:
  - `{type: "document", source: {type: "base64", media_type: "application/pdf", data: "..."}}`
  - `{type: "text", text: "user's caption or empty"}` (if caption provided)

#### Scenario: Image with tools

- **GIVEN** a user sends an image of a restaurant menu
- **AND** asks "Find this restaurant's phone number"
- **WHEN** Sonnet processes the message
- **THEN** it can read the restaurant name from the image
- **AND** use contact/search tools to find the phone number

### Requirement: Conversation Context

The system SHALL maintain multimodal content in conversation history.

#### Scenario: Multimodal history

- **GIVEN** a user sent an image in the previous message
- **AND** the bot described it
- **WHEN** the user asks "What color was the flower in that image?"
- **THEN** the image is included in the conversation history
- **AND** Claude can reference the previous image

#### Scenario: History trimming with media

- **GIVEN** a conversation has many messages including images
- **AND** `max_context_messages = 10`
- **WHEN** history is trimmed
- **THEN** older multimodal messages are dropped like text messages
- **AND** the most recent exchanges are preserved

## ADDED Requirements

### Requirement: Structured Message Type

The system SHALL use a structured message type for the internal pipeline.

#### Scenario: UserMessage with text only

- **GIVEN** a plain text message is received
- **WHEN** a `UserMessage` is created
- **THEN** `text` contains the message body
- **AND** `attachments` is empty
- **AND** `to_claude_content()` returns a plain string

#### Scenario: UserMessage with image

- **GIVEN** an image message is received
- **WHEN** a `UserMessage` is created
- **THEN** `text` may be empty or contain a caption
- **AND** `attachments` contains one `MediaAttachment` with image data
- **AND** `to_claude_content()` returns a list of content blocks

#### Scenario: UserMessage with multiple attachments

- **GIVEN** a client sends multiple images in sequence
- **WHEN** processed as separate messages
- **THEN** each creates its own `UserMessage` with one attachment
- **AND** conversation history preserves all images
