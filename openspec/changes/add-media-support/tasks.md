# Tasks: Add Media Support

## Phase 1: Prosody HTTP File Share

- [ ] **1.1 Migrate prosody.nix from uploadHttp to httpFileShare**
  - Replace `uploadHttp` option block with `httpFileShare` options
  - Map to NixOS `services.prosody.httpFileShare` (not the removed `uploadHttp`)
  - Options: `enable`, `maxFileSize` (default 10 MB), `expiresAfter` (default "1 week")
  - Verify: `nix flake check` passes

- [ ] **1.2 Expose HTTP upload port via Tailscale Serve**
  - Add second Tailscale Serve rule for HTTPS port 5281
  - Prosody serves uploads at `https://<domain>:5281/upload/`
  - Use `http_host = cfg.domain` to avoid needing separate upload domain DNS
  - Verify: `curl -k https://chat.<tailnet>.ts.net:5281/` returns Prosody HTTP response

- [ ] **1.3 Update cert-init for upload domain**
  - Add upload domain to certificate SANs (if using separate upload domain)
  - OR skip if using `http_host` approach (reuses primary domain cert)
  - Verify: No TLS errors when clients upload files

- [ ] **1.4 Enable and test file sharing**
  - Enable `httpFileShare` in edge.nix deployment config
  - Rebuild and test: send image from Conversations → file appears on server
  - Verify: XEP-0363 upload slot request works, file is downloadable

## Phase 2: Bot Media Detection and Download

- [ ] **2.1 Register XEP-0066 plugin in xmpp.py**
  - Add `self.register_plugin("xep_0066")` for Out-of-Band Data
  - Access media URLs via `msg["oob"]["url"]`
  - Verify: Bot logs OOB URLs from incoming image messages

- [ ] **2.2 Create media detection module**
  - New file: `axios_ai_bot/media.py`
  - Detect media URLs: check OOB element, then body URL matching upload domain
  - Download media via `httpx` (already a dependency)
  - Identify MIME type from Content-Type header or file extension
  - Enforce size limits (3.75 MB for images, 32 MB for PDFs)
  - Verify: Unit tests for URL detection, MIME type identification, size validation

- [ ] **2.3 Create UserMessage dataclass**
  - New types in `axios_ai_bot/media.py` or `axios_ai_bot/types.py`:
    - `MediaAttachment(data: bytes, mime_type: str, filename: str)`
    - `UserMessage(text: str, attachments: list[MediaAttachment])`
    - `to_claude_content()` method returns `str` or `list[dict]`
  - Verify: Unit tests for text-only → str, image → content blocks, PDF → document blocks

- [ ] **2.4 Update XMPP message handler**
  - Modify `_on_message()` to build `UserMessage` from incoming message
  - If OOB/URL detected: download media, create `UserMessage` with attachments
  - If text-only: create `UserMessage` with text only (backward compatible)
  - Update `MessageHandler` type alias to accept `UserMessage`
  - Verify: Bot correctly builds `UserMessage` for both text and image messages

## Phase 3: LLM Backend Multimodal Support

- [ ] **3.1 Update LLMBackend interface**
  - Change `execute_with_tools(message: str)` to `execute_with_tools(message: UserMessage)`
  - Change `simple_response(message: str)` to `simple_response(message: UserMessage)`
  - Update `_add_to_history()` to store Claude content blocks (not just strings)
  - Verify: Text-only messages still work identically

- [ ] **3.2 Update AnthropicClient for multimodal**
  - Use `message.to_claude_content()` when building API request
  - Store multimodal content in conversation history
  - Handle Claude's response to image/document queries
  - Verify: Send test image to Claude API, get description back

- [ ] **3.3 Update router.py for UserMessage**
  - Change `handle_message(user_jid, message: str)` to accept `UserMessage`
  - Pass `UserMessage` through to LLM backend
  - Domain routing: classify based on `message.text` (images don't change routing)
  - Verify: Image + text messages route correctly, text-only unchanged

- [ ] **3.4 Update main.py message handler wiring**
  - Ensure the handler chain passes `UserMessage` end-to-end
  - Verify: End-to-end test: send image from XMPP client → bot describes it

## Phase 4: Documentation and NixOS Module Updates

- [ ] **4.1 Update bot.nix for whisper option (Phase 3 prep)**
  - Add optional `whisper.enable`, `whisper.package`, `whisper.model` options
  - Wire whisper binary path into service environment
  - Verify: `nix flake check` passes

- [ ] **4.2 Update README**
  - Document HTTP file share setup
  - Document supported media types
  - Add example: sending images to the AI bot
  - Verify: Instructions are clear and complete

- [ ] **4.3 Update openspec project.md**
  - Add media support to project scope
  - Verify: Project docs match implementation

## Phase 5: Voice Transcription (Optional)

- [ ] **5.1 Add whisper-cpp integration**
  - Detect audio MIME types (audio/ogg, audio/opus, audio/mpeg)
  - Download audio file, convert to WAV if needed
  - Run whisper-cpp via `asyncio.create_subprocess_exec()`
  - Return transcription as `UserMessage(text="Voice message: ...")`
  - Verify: OGG voice message → text transcription

- [ ] **5.2 Add progress feedback for voice**
  - Send "Transcribing voice message..." while whisper processes
  - Verify: User sees progress before transcription completes

## Verification Checklist

Before marking complete:

- [ ] `nix flake check` passes
- [ ] Text-only messages work identically (no regression)
- [ ] Image sent from Conversations → bot describes it
- [ ] PDF sent from client → bot summarizes content
- [ ] Large images (>3.75 MB) are handled gracefully
- [ ] Unsupported file types get a friendly error message
- [ ] Prosody wrapper uses `httpFileShare` (no deprecation warnings)
- [ ] README documents media support setup
