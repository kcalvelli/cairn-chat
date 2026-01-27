# NixOS module for Prosody XMPP server (Tailscale-only configuration)
#
# This module wraps services.prosody with secure defaults for family chat:
# - Binds only to Tailscale interface
# - Disables federation (s2s)
# - Enables MUC for group chats
# - Requires encryption
{
  config,
  lib,
  pkgs,
  ...
}:

with lib;

let
  cfg = config.services.axios-chat.prosody;
in
{
  options.services.axios-chat.prosody = {
    enable = mkEnableOption "Prosody XMPP server for axios-chat (Tailscale-only)";

    domain = mkOption {
      type = types.str;
      example = "chat.home.ts.net";
      description = ''
        The XMPP domain for the chat server.
        Users will have JIDs like user@<domain>.
      '';
    };

    tailscaleIP = mkOption {
      type = types.str;
      example = "100.64.0.1";
      description = ''
        The Tailscale IP address to bind Prosody to.
        This ensures the server is only accessible via Tailscale.
      '';
    };

    admins = mkOption {
      type = types.listOf types.str;
      default = [ ];
      example = [ "admin@chat.home.ts.net" ];
      description = "List of JIDs with administrative privileges.";
    };

    muc = {
      enable = mkEnableOption "Multi-User Chat (group chats)" // {
        default = true;
      };

      domain = mkOption {
        type = types.str;
        default = "";
        example = "rooms.chat.home.ts.net";
        description = ''
          Domain for MUC rooms. Defaults to muc.<domain>.
        '';
      };

      restrictRoomCreation = mkOption {
        type = types.bool;
        default = false;
        description = "If true, only admins can create rooms.";
      };
    };

    uploadHttp = {
      enable = mkEnableOption "HTTP file upload for sharing files";

      maxFileSize = mkOption {
        type = types.int;
        default = 10485760; # 10 MB
        description = "Maximum file size for HTTP uploads in bytes.";
      };
    };

    messageArchive = {
      enable = mkEnableOption "Message Archive Management (MAM)" // {
        default = true;
      };

      expireAfter = mkOption {
        type = types.str;
        default = "1w";
        description = "How long to keep archived messages (e.g., '1w', '30d', 'never').";
      };
    };

    extraConfig = mkOption {
      type = types.lines;
      default = "";
      description = "Extra Prosody configuration to append.";
    };
  };

  config = mkIf cfg.enable {
    # Assertions
    assertions = [
      {
        assertion = cfg.domain != "";
        message = "services.axios-chat.prosody.domain must be set";
      }
      {
        assertion = cfg.tailscaleIP != "";
        message = ''
          services.axios-chat.prosody.tailscaleIP must be set.

          You can find your Tailscale IP with: tailscale ip -4
        '';
      }
    ];

    # Configure Prosody
    services.prosody = {
      enable = true;

      # Bind only to Tailscale interface
      interfaces = [ cfg.tailscaleIP ];

      # Admin users
      admins = cfg.admins;

      # Virtual host
      virtualHosts.${cfg.domain} = {
        enabled = true;
        domain = cfg.domain;

        # SSL is handled by Prosody's automatic certificates
        # For Tailscale, we rely on network-level security
        ssl = {
          cert = "/var/lib/prosody/${cfg.domain}.crt";
          key = "/var/lib/prosody/${cfg.domain}.key";
        };
      };

      # MUC configuration
      muc = mkIf cfg.muc.enable [
        {
          domain = if cfg.muc.domain != "" then cfg.muc.domain else "muc.${cfg.domain}";
          restrictRoomCreation = cfg.muc.restrictRoomCreation;
        }
      ];

      # HTTP upload for file sharing
      uploadHttp = mkIf cfg.uploadHttp.enable {
        domain = "upload.${cfg.domain}";
        uploadFileSizeLimit = toString cfg.uploadHttp.maxFileSize;
      };

      # Require encryption for client connections
      c2sRequireEncryption = true;

      # Disable server-to-server (federation)
      s2sRequireEncryption = false;
      s2sSecureAuth = false;

      # Modules
      modules = [
        "roster"
        "saslauth"
        "tls"
        "dialback"
        "disco"
        "posix"
        "private"
        "vcard"
        "ping"
        "register"
        "admin_adhoc"
        "blocklist"
        "carbons"
        "smacks"
        "csi"
        "cloud_notify"
      ]
      ++ optionals cfg.messageArchive.enable [ "mam" ];

      # Disable s2s module
      extraModules = [ ];

      # Extra configuration
      extraConfig = ''
        -- Disable server-to-server federation
        modules_disabled = { "s2s" }

        -- Authentication
        authentication = "internal_hashed"

        -- Allow registration only by admins
        allow_registration = false

        -- Message Archive Management
        ${optionalString cfg.messageArchive.enable ''
          archive_expires_after = "${cfg.messageArchive.expireAfter}"
          default_archive_policy = true
        ''}

        -- Storage
        storage = "internal"

        -- Logging
        log = {
          info = "*syslog";
          warn = "*syslog";
          error = "*syslog";
        }

        ${cfg.extraConfig}
      '';
    };

    # Generate self-signed certificates for the domain
    # In production, you might want to use Let's Encrypt or similar
    systemd.services.prosody-cert-init = {
      description = "Generate Prosody self-signed certificates";
      before = [ "prosody.service" ];
      wantedBy = [ "multi-user.target" ];

      serviceConfig = {
        Type = "oneshot";
        RemainAfterExit = true;
      };

      script = ''
        CERT_DIR="/var/lib/prosody"
        CERT_FILE="$CERT_DIR/${cfg.domain}.crt"
        KEY_FILE="$CERT_DIR/${cfg.domain}.key"

        mkdir -p "$CERT_DIR"

        if [ ! -f "$CERT_FILE" ] || [ ! -f "$KEY_FILE" ]; then
          ${pkgs.openssl}/bin/openssl req -new -x509 -days 3650 -nodes \
            -out "$CERT_FILE" \
            -keyout "$KEY_FILE" \
            -subj "/CN=${cfg.domain}"
          chown prosody:prosody "$CERT_FILE" "$KEY_FILE"
          chmod 600 "$KEY_FILE"
        fi
      '';
    };

    # Ensure Tailscale is available
    systemd.services.prosody = {
      after = [ "tailscaled.service" ];
      wants = [ "tailscaled.service" ];
    };
  };
}
