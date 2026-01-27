# NixOS module for Prosody XMPP server (Tailscale-only configuration)
#
# This module wraps services.prosody with secure defaults for family chat:
# - Uses Tailscale serve for DNS name (chat.<tailnet>.ts.net)
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
  useTailscaleServe = cfg.tailscaleServe.enable;
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

    tailscaleServe = {
      enable = mkEnableOption "Tailscale serve for XMPP (creates chat.<tailnet>.ts.net)" // {
        default = true;
      };

      serviceName = mkOption {
        type = types.str;
        default = "chat";
        description = ''
          Tailscale service name. Creates DNS: <serviceName>.<tailnet>.ts.net
        '';
      };
    };

    tailscaleIP = mkOption {
      type = types.nullOr types.str;
      default = null;
      example = "100.64.0.1";
      description = ''
        The Tailscale IP address to bind Prosody to (legacy mode).
        Only needed if tailscaleServe.enable = false.
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
        assertion = useTailscaleServe || cfg.tailscaleIP != null;
        message = ''
          services.axios-chat.prosody requires either:
          - tailscaleServe.enable = true (recommended), OR
          - tailscaleIP to be set (legacy mode)

          You can find your Tailscale IP with: tailscale ip -4
        '';
      }
    ];

    # Configure Prosody
    services.prosody = {
      enable = true;

      # Disable XEP-0423 compliance check (not needed for internal family chat)
      xmppComplianceSuite = false;

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

      # Modules - only use options exposed by NixOS prosody module
      modules = {
        roster = true;
        saslauth = true;
        tls = true;
        dialback = false; # Disable s2s dialback (no federation)
        disco = true;
        private = true;
        vcard = true;
        ping = true;
        register = true;
        admin_adhoc = true;
        blocklist = true;
        carbons = true;
        smacks = true;
        csi = true;
        cloud_notify = true;
        mam = cfg.messageArchive.enable;
        # Note: posix module is handled by NixOS systemd integration
      };

      # Extra configuration
      # NOTE: Avoid duplicating options already set by NixOS prosody module
      # (modules_enabled, authentication, allow_registration, log are set above)
      extraConfig = ''
        -- Bind to localhost (Tailscale serve) or Tailscale IP (legacy)
        interfaces = { "${if useTailscaleServe then "127.0.0.1" else cfg.tailscaleIP}" }

        -- Disable s2s module (federation)
        modules_disabled = { "s2s" }

        -- Message Archive Management
        ${optionalString cfg.messageArchive.enable ''
          archive_expires_after = "${cfg.messageArchive.expireAfter}"
          default_archive_policy = true
        ''}

        -- Storage
        storage = "internal"

        ${cfg.extraConfig}
      '';
    };

    # Generate self-signed certificates for the domain with proper SANs
    # Modern TLS requires Subject Alternative Names for hostname validation
    systemd.services.prosody-cert-init = {
      description = "Generate Prosody self-signed certificates";
      before = [ "prosody.service" ];
      wantedBy = [ "multi-user.target" ];

      serviceConfig = {
        Type = "oneshot";
        RemainAfterExit = true;
      };

      script =
        let
          mucDomain = if cfg.muc.domain != "" then cfg.muc.domain else "muc.${cfg.domain}";
        in
        ''
          CERT_DIR="/var/lib/prosody"
          CERT_FILE="$CERT_DIR/${cfg.domain}.crt"
          KEY_FILE="$CERT_DIR/${cfg.domain}.key"
          RUN_CERT_DIR="/run/prosody/certs"

          mkdir -p "$CERT_DIR"
          mkdir -p "$RUN_CERT_DIR"

          # Generate cert with SANs if missing or outdated (no SAN support)
          NEEDS_REGEN=0
          if [ ! -f "$CERT_FILE" ] || [ ! -f "$KEY_FILE" ]; then
            NEEDS_REGEN=1
          elif ! ${pkgs.openssl}/bin/openssl x509 -in "$CERT_FILE" -noout -ext subjectAltName 2>/dev/null | grep -q "DNS:"; then
            echo "Certificate missing SANs, regenerating..."
            NEEDS_REGEN=1
          fi

          if [ "$NEEDS_REGEN" = "1" ]; then
            ${pkgs.openssl}/bin/openssl req -new -x509 -days 3650 -nodes \
              -out "$CERT_FILE" \
              -keyout "$KEY_FILE" \
              -subj "/CN=${cfg.domain}" \
              -addext "subjectAltName=DNS:${cfg.domain},DNS:${mucDomain},DNS:localhost,IP:127.0.0.1"
            chown prosody:prosody "$CERT_FILE" "$KEY_FILE"
            chmod 600 "$KEY_FILE"
          fi

          # Symlink certs to /run/prosody/certs for certmanager auto-discovery
          ln -sf "$CERT_FILE" "$RUN_CERT_DIR/"
          ln -sf "$KEY_FILE" "$RUN_CERT_DIR/"
          chown -h prosody:prosody "$RUN_CERT_DIR"/*
        '';
    };

    # Ensure Tailscale is available
    systemd.services.prosody = {
      after = [ "tailscaled.service" ];
      wants = [ "tailscaled.service" ];
    };

    # Tailscale serve for XMPP (creates chat.<tailnet>.ts.net)
    systemd.services.tailscale-serve-xmpp = mkIf useTailscaleServe {
      description = "Tailscale Serve for XMPP (${cfg.tailscaleServe.serviceName})";
      after = [
        "tailscaled.service"
        "prosody.service"
        "network-online.target"
      ];
      wants = [
        "tailscaled.service"
        "network-online.target"
      ];
      wantedBy = [ "multi-user.target" ];

      # Wait for Tailscale to be fully ready
      preStart = ''
        # Wait for Tailscale to be connected
        for i in $(seq 1 30); do
          status=$(${pkgs.tailscale}/bin/tailscale status --json 2>/dev/null | ${pkgs.jq}/bin/jq -r '.BackendState // "NoState"')
          if [ "$status" = "Running" ]; then
            break
          fi
          echo "Waiting for Tailscale to be ready (attempt $i/30, state: $status)..."
          sleep 2
        done
      '';

      serviceConfig = {
        Type = "oneshot";
        RemainAfterExit = true;
        # Expose XMPP c2s port (5222) via Tailscale serve
        ExecStart = "${pkgs.tailscale}/bin/tailscale serve --service=svc:${cfg.tailscaleServe.serviceName} --tcp=5222 tcp://127.0.0.1:5222";
        ExecStop = "${pkgs.tailscale}/bin/tailscale serve --service=svc:${cfg.tailscaleServe.serviceName} --tcp=5222 off";
        Restart = "on-failure";
        RestartSec = "5s";
      };
    };
  };
}
