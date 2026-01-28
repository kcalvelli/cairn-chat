# Design: Add Media Support

## System Changes Overview

This change touches four layers: Prosody configuration, XMPP message handling, the message pipeline, and the LLM backend. Changes are sequenced so each phase builds on the previous.

## Layer 1: Prosody HTTP File Share

### Current State

`prosody.nix` defines `uploadHttp.enable` which maps to the **removed** NixOS option `services.prosody.uploadHttp`. This was deprecated in favor of `services.prosody.httpFileShare` using `mod_http_file_share`.

### Target State

Replace with `httpFileShare` options that map to the current NixOS module:

```nix
# In prosody.nix wrapper
services.prosody.httpFileShare = {
  domain = "upload.${cfg.domain}";
  http_host = cfg.domain;  # Reuse primary domain to avoid extra DNS/certs
  size_limit = cfg.httpFileShare.maxFileSize;
  expires_after = cfg.httpFileShare.expiresAfter;
};
```

### HTTP Port Exposure

Prosody's HTTP module listens on port 5280 (HTTP) or 5281 (HTTPS). For Tailscale-only access:
- Add a second Tailscale Serve rule for HTTPS on port 5281
- OR use `http_host` to serve uploads under the primary domain (avoids extra DNS)

The `http_host` approach is simpler: uploads are served at `https://<domain>:5281/upload/` without needing a separate `upload.<domain>` DNS entry.

### Certificate SANs

If using a separate upload domain, add it to the cert-init script's SANs. If using `http_host`, no additional certs are needed.

## Layer 2: XMPP Message Detection

### How Clients Send Media

When a user sends an image from Conversations/Dino:
1. Client requests an upload slot via XEP-0363 IQ to Prosody
2. Prosody returns PUT URL + GET URL
3. Client uploads file via HTTP PUT
4. Client sends `<message>` with:
   - `<body>https://upload.domain/abc123/photo.jpg</body>`
   - `<x xmlns="jabber:x:oob"><url>https://upload.domain/abc123/photo.jpg</url></x>`

### Detection Strategy

Register slixmpp's `xep_0066` plugin to access OOB data. Detection logic:

```
1. Check msg["oob"]["url"] for explicit OOB attachment
2. If no OOB, check if body is a single URL pointing to the upload domain
3. If media URL found: download, identify MIME type, build structured message
4. If no media: pass body as plain text (existing behavior)
```

### Supported MIME Types

| Type | Extensions | Claude Support | Phase |
|------|-----------|---------------|-------|
| JPEG | .jpg, .jpeg | ✅ Image block | 1 |
| PNG | .png | ✅ Image block | 1 |
| GIF | .gif | ✅ Image block | 1 |
| WebP | .webp | ✅ Image block | 1 |
| PDF | .pdf | ✅ Document block | 2 |
| OGG/Opus | .ogg, .opus | ❌ Needs transcription | 3 |
| MP3/M4A | .mp3, .m4a | ❌ Needs transcription | 3 |

### Size Limits

- Claude image limit: 3.75 MB per image, 8000×8000 px
- Prosody default: 10 MB upload limit
- Strategy: Download file, check size. If image > 3.75 MB, resize before encoding. If non-image > 32 MB (PDF limit), reject with user-friendly message.

## Layer 3: Message Pipeline Refactoring

### Current Pipeline (str-only)

```
xmpp.py: body = msg["body"]  (str)
    ↓
router.py: handle_message(user_jid, message: str)
    ↓
anthropic.py: _add_to_history(user_id, "user", message: str)
              execute_with_tools(message: str)
    ↓
Claude API: messages=[{role: "user", content: "text string"}]
```

### Target Pipeline (structured content)

```
xmpp.py: content = build_content(msg)  → UserMessage
    ↓
router.py: handle_message(user_jid, content: UserMessage)
    ↓
anthropic.py: _add_to_history(user_id, "user", content.to_claude_blocks())
              execute_with_tools(content: UserMessage)
    ↓
Claude API: messages=[{role: "user", content: [
              {type: "image", source: {type: "base64", ...}},
              {type: "text", text: "What is this?"}
            ]}]
```

### UserMessage Type

A lightweight dataclass to carry structured content through the pipeline:

```python
@dataclass
class MediaAttachment:
    data: bytes           # Raw file content
    mime_type: str        # e.g., "image/jpeg"
    filename: str         # e.g., "photo.jpg"

@dataclass
class UserMessage:
    text: str                              # Body text (may be empty if image-only)
    attachments: list[MediaAttachment]     # Zero or more media files

    def to_claude_content(self) -> str | list[dict]:
        """Convert to Claude API content format."""
        if not self.attachments:
            return self.text  # Plain string for text-only (backward compatible)
        # Build multimodal content blocks
        blocks = []
        for att in self.attachments:
            if att.mime_type.startswith("image/"):
                blocks.append({
                    "type": "image",
                    "source": {"type": "base64", "media_type": att.mime_type,
                               "data": base64.b64encode(att.data).decode()}
                })
            elif att.mime_type == "application/pdf":
                blocks.append({
                    "type": "document",
                    "source": {"type": "base64", "media_type": att.mime_type,
                               "data": base64.b64encode(att.data).decode()}
                })
        if self.text:
            blocks.append({"type": "text", "text": self.text})
        return blocks
```

### Backward Compatibility

- Text-only messages continue to work identically (UserMessage with empty attachments returns plain string)
- `LLMBackend` interface changes `message: str` to `message: UserMessage` but existing text behavior is preserved via `to_claude_content()`
- Conversation history stores Claude content blocks directly (already supports both string and list formats)

## Layer 4: Voice Transcription (Phase 3)

### Architecture

Voice messages follow the same download path as images, but add a transcription step:

```
Audio file downloaded → whisper-cpp → text → UserMessage(text="Voice: ...")
```

### Whisper Integration Options

1. **whisper-cpp CLI**: Run as a subprocess. Simple but blocks the event loop.
2. **whisper-cpp as a service**: Systemd service with HTTP API. Better for async.
3. **OpenAI Whisper API**: External, paid, but simplest integration.

Recommendation: Start with whisper-cpp CLI via `asyncio.create_subprocess_exec()`. Can upgrade to service if latency becomes an issue.

### NixOS Module

Add optional whisper configuration:

```nix
services.axios-chat.bot.whisper = {
  enable = mkEnableOption "voice message transcription";
  package = mkOption { type = types.package; default = pkgs.whisper-cpp; };
  model = mkOption { type = types.str; default = "base.en"; };
};
```

## Trade-offs

| Decision | Chosen | Alternative | Rationale |
|----------|--------|-------------|-----------|
| Image encoding | Base64 inline | Claude Files API | Files API is beta; base64 is stable and simple |
| Upload HTTP exposure | `http_host` reuse | Separate upload domain | Avoids extra DNS/cert complexity |
| Pipeline type | `UserMessage` dataclass | Dict / tuple | Type-safe, self-documenting, IDE-friendly |
| Voice STT | whisper-cpp subprocess | Service / external API | No new infrastructure, already in nix packages |
