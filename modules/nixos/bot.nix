# NixOS module for axios-ai-bot (Sid backend)
#
# XMPP chat bot powered by Sid (GenX64) via openclaw-gateway.
{
  config,
  lib,
  pkgs,
  ...
}:

with lib;

let
  cfg = config.services.axios-chat.bot;
in
{
  options.services.axios-chat.bot = {
    enable = mkEnableOption "axios-ai-bot XMPP chat (Sid backend)";

    package = mkOption {
      type = types.package;
      default = pkgs.axios-ai-bot;
      defaultText = literalExpression "pkgs.axios-ai-bot";
      description = "The axios-ai-bot package to use.";
    };

    # XMPP configuration
    xmppUser = mkOption {
      type = types.str;
      default = "sid";
      description = "XMPP username for the bot.";
    };

    xmppDomain = mkOption {
      type = types.str;
      example = "chat.home.ts.net";
      description = "XMPP domain for the bot to connect to.";
    };

    xmppServer = mkOption {
      type = types.str;
      default = "127.0.0.1";
      description = "XMPP server address (default: localhost for Prosody).";
    };

    xmppPort = mkOption {
      type = types.int;
      default = 5222;
      description = "XMPP server port.";
    };

    xmppPasswordFile = mkOption {
      type = types.path;
      description = "Path to file containing the bot's XMPP password.";
    };

    # Sid (openclaw-gateway) configuration
    gatewayUrl = mkOption {
      type = types.str;
      default = "http://127.0.0.1:18789";
      description = "URL of the openclaw-gateway instance.";
    };

    agentId = mkOption {
      type = types.str;
      default = "main";
      description = "OpenClaw agent ID to use.";
    };

    authTokenFile = mkOption {
      type = types.nullOr types.path;
      default = null;
      description = "Path to file containing the gateway auth token.";
    };

    timeout = mkOption {
      type = types.int;
      default = 300;
      description = "Request timeout in seconds.";
    };

    logLevel = mkOption {
      type = types.enum [ "DEBUG" "INFO" "WARNING" "ERROR" ];
      default = "INFO";
      description = "Logging level.";
    };

    # MUC (Multi-User Chat) configuration
    muc = {
      rooms = mkOption {
        type = types.listOf types.str;
        default = [];
        example = [ "family@conference.chat.example.ts.net" ];
        description = "List of MUC room JIDs to join.";
      };

      nick = mkOption {
        type = types.nullOr types.str;
        default = null;
        example = "Sid";
        description = "Nickname to use in MUC rooms. Defaults to xmppUser.";
      };
    };
  };

  config = mkIf cfg.enable {
    assertions = [
      {
        assertion = cfg.xmppDomain != "";
        message = "services.axios-chat.bot.xmppDomain must be set";
      }
    ];

    systemd.services.axios-ai-bot = {
      description = "Axios AI Bot (Sid)";
      after = [ "network-online.target" "prosody.service" "openclaw-gateway.service" ];
      wants = [ "network-online.target" ];
      wantedBy = [ "multi-user.target" ];

      environment = {
        XMPP_JID = "${cfg.xmppUser}@${cfg.xmppDomain}";
        XMPP_SERVER = cfg.xmppServer;
        XMPP_PORT = toString cfg.xmppPort;
        XMPP_PASSWORD_FILE = cfg.xmppPasswordFile;
        SID_GATEWAY_URL = cfg.gatewayUrl;
        SID_AGENT_ID = cfg.agentId;
        SID_TIMEOUT = toString cfg.timeout;
        PYTHONUNBUFFERED = "1";
        LOG_LEVEL = cfg.logLevel;
      } // optionalAttrs (cfg.authTokenFile != null) {
        SID_AUTH_TOKEN_FILE = cfg.authTokenFile;
      } // optionalAttrs (cfg.muc.rooms != []) {
        MUC_ROOMS = concatStringsSep "," cfg.muc.rooms;
      } // optionalAttrs (cfg.muc.nick != null) {
        MUC_NICK = cfg.muc.nick;
      };

      serviceConfig = {
        Type = "simple";
        ExecStart = "${cfg.package}/bin/axios-ai-bot";
        Restart = "always";
        RestartSec = 5;

        # Security hardening
        DynamicUser = true;
        NoNewPrivileges = true;
        ProtectSystem = "strict";
        ProtectHome = true;
        PrivateTmp = true;
        PrivateDevices = true;
        ProtectKernelTunables = true;
        ProtectKernelModules = true;
        ProtectControlGroups = true;
        RestrictAddressFamilies = [ "AF_INET" "AF_INET6" "AF_UNIX" ];
        RestrictNamespaces = true;
        LockPersonality = true;
        MemoryDenyWriteExecute = true;
        RestrictRealtime = true;
        RestrictSUIDSGID = true;
        RemoveIPC = true;

        BindReadOnlyPaths = [
          cfg.xmppPasswordFile
          "/etc/resolv.conf"
          "/etc/hosts"
          "/etc/nsswitch.conf"
          "/run/systemd/resolve"
        ] ++ optionals (cfg.authTokenFile != null) [ cfg.authTokenFile ];
      };
    };
  };
}
