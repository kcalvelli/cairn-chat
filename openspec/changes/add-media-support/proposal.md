# Proposal: Add Media Support (Images, Documents, Voice)

## Summary

Enable the XMPP chat system to handle images, documents, and voice messages. Users can send photos and files from Conversations/Dino/Gajim and have Claude understand and respond to them. Phased approach: images first, documents second, voice third.

## Motivation

### Current Limitation

The bot processes only plain text. When a user sends an image from Conversations, the bot receives the HTTP URL in `msg["body"]` but ignores it — it treats it as text and sends it to Claude as a string. Users cannot ask "What's in this photo?" or share documents for analysis.

### Why This Matters

- **Family use case**: Parents want to send photos ("What plant is this?", "Help me read this label")
- **Document analysis**: Share a PDF receipt, menu, or school notice for the AI to summarize
- **Voice messages**: Quick voice queries when typing is inconvenient (driving, cooking)
- **Claude supports it**: Claude 3+ natively accepts images and PDFs — we're just not using it

## Architecture

```
User sends image from Conversations
      │
      ▼
┌─────────────────────────────────────┐
│  Prosody (mod_http_file_share)      │
│  ← Client HTTP PUTs image           │
│  → Returns GET URL                  │
└──────────────────┬──────────────────┘
                   │ Message with URL in body + OOB
                   ▼
┌─────────────────────────────────────┐
│  axios-ai-bot (xmpp.py)            │
│  1. Detect URL in body/OOB element  │
│  2. Download image via httpx         │
│  3. Base64-encode for Claude         │
└──────────────────┬──────────────────┘
                   │ Multimodal content blocks
                   ▼
┌─────────────────────────────────────┐
│  Anthropic Client                   │
│  content: [                         │
│    {type: "image", source: base64}, │
│    {type: "text", text: "..."}      │
│  ]                                  │
└─────────────────────────────────────┘
```

## Key Technical Decisions

### 1. Prosody HTTP File Share (prerequisite)

The current `prosody.nix` wrapper uses the **deprecated** `uploadHttp` option which maps to the removed `mod_http_upload`. NixOS has migrated to `services.prosody.httpFileShare` using the built-in `mod_http_file_share`.

- Migrate wrapper to use `httpFileShare`
- Expose HTTP port via Tailscale Serve (like c2s on 5222)
- Add `upload.<domain>` to cert SANs

### 2. Base64 (not URL) for Claude

Prosody's upload server is Tailscale-internal — Anthropic's API cannot fetch URLs from it. The bot must:
1. Download the file from the upload URL via `httpx` (already a dependency)
2. Base64-encode the content
3. Send as an inline content block to Claude

### 3. Message Pipeline Refactoring

The entire message pipeline currently passes `str`:
- `MessageHandler = Callable[[str, str, str], ...]` — body is a string
- `LLMBackend.execute_with_tools(message: str)` — string only
- `_add_to_history(content: str)` — stores strings

This must become structured content to support multimodal:
- Body text + optional list of media attachments
- Claude content blocks: `[{type: "image", ...}, {type: "text", ...}]`
- History stores content blocks, not just strings

### 4. Voice via External Transcription (Phase 3)

Claude API does not accept audio. Voice messages (OGG/Opus from XMPP clients) must be transcribed first. Options:
- `whisper-cpp` (already available in axios AI packages)
- OpenAI Whisper API (external, paid)

Transcribed text is sent to Claude as a normal message with a note: "Voice message: ..."

## Phases

### Phase 1: Images (core value)
- Migrate Prosody to `httpFileShare`
- Bot detects and downloads image URLs
- Refactor message pipeline for multimodal content
- Send images to Claude as base64 content blocks

### Phase 2: Documents
- Extend media detection to PDFs, text files
- Send PDFs as base64 document blocks to Claude
- Minimal additional effort once Phase 1 is complete

### Phase 3: Voice Messages (optional)
- Detect audio file URLs (OGG/Opus/MP3)
- Transcribe via whisper-cpp or Whisper API
- Send transcription as text to Claude

## Scope

### In Scope

- Prosody `mod_http_file_share` configuration
- Bot: detect media URLs in incoming messages (OOB / body URL)
- Bot: download and base64-encode media files
- LLM backend: accept multimodal content blocks
- Conversation history: store multimodal content
- NixOS module options for file share configuration

### Out of Scope

- Bot sending images/files back to users (Claude doesn't generate images)
- End-to-end encryption (OMEMO) for media
- Image generation or manipulation
- Video file processing
- Real-time voice/audio streaming

## Success Criteria

1. User sends a photo from Conversations → bot describes it accurately
2. User sends a PDF → bot summarizes its contents
3. File uploads work for all family members on the Tailnet
4. No regression in text-only message handling
5. Prosody wrapper uses current NixOS options (no deprecation warnings)

## Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Large images exceed Claude token limits | Low | Medium | Resize images >3.75 MB before encoding |
| Prosody HTTP port exposure on Tailnet | Low | Low | Tailscale provides network-level security |
| Bot downloads malicious files | Low | Low | Validate MIME type, enforce size limit |
| Voice transcription latency | Medium | Low | Send "Transcribing voice message..." progress |

## Dependencies

- NixOS `services.prosody.httpFileShare` module (available in nixpkgs)
- `httpx` (already a dependency for mcp-gateway calls)
- For Phase 3: `whisper-cpp` or equivalent STT service
