# prosody-server Spec Delta

## MODIFIED Requirements

### Requirement: NixOS Module Interface

The system SHALL provide HTTP file sharing options using `mod_http_file_share`.

#### Scenario: Enable HTTP file share

- **GIVEN** `services.axios-chat.prosody.httpFileShare.enable = true`
- **WHEN** the system is rebuilt
- **THEN** Prosody enables `mod_http_file_share`
- **AND** clients can upload files via XEP-0363

#### Scenario: File size limit

- **GIVEN** `services.axios-chat.prosody.httpFileShare.maxFileSize = 20971520`
- **WHEN** a client uploads a 15 MB file
- **THEN** the upload succeeds
- **AND** a 25 MB upload is rejected

#### Scenario: File expiration

- **GIVEN** `services.axios-chat.prosody.httpFileShare.expiresAfter = "1 week"`
- **WHEN** a file was uploaded 8 days ago
- **THEN** the file is automatically deleted

#### Scenario: Default file share configuration

- **GIVEN** `services.axios-chat.prosody.httpFileShare.enable = true`
- **AND** no other file share options are set
- **WHEN** the system is rebuilt
- **THEN** the max file size defaults to 10 MB
- **AND** files expire after 1 week

## ADDED Requirements

### Requirement: HTTP Port Exposure

The system SHALL expose Prosody's HTTP port for file uploads via Tailscale Serve.

#### Scenario: Tailscale Serve for HTTP uploads

- **GIVEN** prosody is enabled with `tailscaleServe.enable = true`
- **AND** `httpFileShare.enable = true`
- **WHEN** the system starts
- **THEN** Tailscale Serve exposes port 5281 (HTTPS) for file uploads
- **AND** XMPP clients can discover and use the upload service

#### Scenario: Upload domain certificate

- **GIVEN** HTTP file share is enabled
- **WHEN** the cert-init service runs
- **THEN** the self-signed certificate includes the upload domain in SANs
- **AND** clients can upload files without TLS errors

## REMOVED Requirements

### Requirement: uploadHttp Configuration (Removed)

The deprecated `uploadHttp` option is removed in favor of `httpFileShare`.
