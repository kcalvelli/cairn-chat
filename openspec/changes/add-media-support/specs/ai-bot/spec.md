# ai-bot Spec Delta

## MODIFIED Requirements

### Requirement: Message Handling

The system SHALL receive and process messages containing media attachments.

#### Scenario: Receive image message

- **GIVEN** the bot is connected
- **AND** HTTP file share is enabled on Prosody
- **WHEN** a user sends an image from their XMPP client
- **THEN** the bot detects the image URL in the message (via OOB or body URL)
- **AND** downloads the image from the upload server
- **AND** sends it to Claude as a base64 image content block

#### Scenario: Receive image with caption

- **GIVEN** a user sends an image with the caption "What plant is this?"
- **WHEN** the bot processes the message
- **THEN** it includes both the image and the text in the Claude request
- **AND** Claude responds based on the image content and question

#### Scenario: Receive PDF document

- **GIVEN** a user sends a PDF file from their XMPP client
- **WHEN** the bot processes the message
- **THEN** it downloads the PDF and sends it to Claude as a document content block
- **AND** Claude can summarize or answer questions about the document

#### Scenario: Receive unsupported file type

- **GIVEN** a user sends a .zip or .exe file
- **WHEN** the bot processes the message
- **THEN** it responds with "I can understand images (JPEG, PNG, GIF, WebP) and PDFs, but I can't process .zip files."

#### Scenario: Image too large for Claude

- **GIVEN** a user sends an image larger than 3.75 MB
- **WHEN** the bot downloads the image
- **THEN** it resizes the image to fit within Claude's limits
- **AND** processes it normally

#### Scenario: Plain text message unchanged

- **GIVEN** a user sends a text-only message with no media
- **WHEN** the bot processes the message
- **THEN** it behaves identically to the current implementation
- **AND** no media detection overhead affects response time

## ADDED Requirements

### Requirement: Media URL Detection

The system SHALL detect media URLs in incoming XMPP messages.

#### Scenario: OOB element detection

- **GIVEN** a message contains an `<x xmlns="jabber:x:oob">` element with a URL
- **WHEN** the bot inspects the message
- **THEN** it recognizes the URL as a media attachment
- **AND** downloads the file for processing

#### Scenario: Body URL detection

- **GIVEN** a message body is a single URL pointing to the upload domain
- **AND** no OOB element is present
- **WHEN** the bot inspects the message
- **THEN** it recognizes the URL as a media attachment
- **AND** downloads the file for processing

#### Scenario: Non-media URL in body

- **GIVEN** a message body contains "Check out https://example.com"
- **WHEN** the bot inspects the message
- **THEN** it treats the entire body as plain text
- **AND** does NOT attempt to download the URL

### Requirement: Voice Message Transcription

The system SHALL transcribe voice messages when whisper is enabled.

#### Scenario: Voice message received

- **GIVEN** whisper transcription is enabled
- **AND** a user sends a voice message (OGG/Opus audio)
- **WHEN** the bot downloads the audio file
- **THEN** it transcribes the audio using whisper-cpp
- **AND** sends the transcription to Claude as text
- **AND** prefixes the transcription with context (e.g., "Voice message:")

#### Scenario: Whisper not enabled

- **GIVEN** whisper transcription is NOT enabled
- **AND** a user sends a voice message
- **WHEN** the bot detects the audio file
- **THEN** it responds with "Voice messages are not currently supported."

#### Scenario: Transcription failure

- **GIVEN** whisper transcription is enabled
- **AND** a user sends a corrupted audio file
- **WHEN** whisper fails to transcribe
- **THEN** the bot responds with "I couldn't understand that voice message. Could you try again or type your message?"
