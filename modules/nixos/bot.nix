# NixOS module for axios-ai-bot
#
# Provides the systemd service for the AI-powered XMPP bot
# that connects to mcp-gateway for tool execution.
# Supports both Anthropic Claude and local Ollama backends.
{
  config,
  lib,
  pkgs,
  ...
}:

with lib;

let
  cfg = config.services.axios-chat.bot;
  isOllama = cfg.llmBackend == "ollama";
  isAnthropic = cfg.llmBackend == "anthropic";
in
{
  options.services.axios-chat.bot = {
    enable = mkEnableOption "axios-ai-bot XMPP AI assistant";

    package = mkOption {
      type = types.package;
      default = pkgs.axios-ai-bot;
      defaultText = literalExpression "pkgs.axios-ai-bot";
      description = "The axios-ai-bot package to use.";
    };

    xmppUser = mkOption {
      type = types.str;
      default = "ai";
      description = ''
        XMPP username for the bot.
        The full JID will be <xmppUser>@<xmppDomain>.
      '';
    };

    xmppDomain = mkOption {
      type = types.str;
      example = "chat.home.ts.net";
      description = "XMPP domain for the bot to connect to.";
    };

    xmppServer = mkOption {
      type = types.str;
      default = "127.0.0.1";
      description = ''
        XMPP server address to connect to.
        Defaults to 127.0.0.1 for local Prosody with Tailscale serve.
        Set to the actual server IP/hostname for remote connections.
      '';
    };

    xmppPort = mkOption {
      type = types.int;
      default = 5222;
      description = "XMPP server port.";
    };

    xmppPasswordFile = mkOption {
      type = types.path;
      description = ''
        Path to file containing the bot's XMPP password.
        The file should contain only the password with no trailing newline.
      '';
    };

    # LLM Backend selection
    llmBackend = mkOption {
      type = types.enum [
        "anthropic"
        "ollama"
      ];
      default = "anthropic";
      description = ''
        LLM backend to use for AI responses.
        - anthropic: Use Claude API (requires claudeApiKeyFile)
        - ollama: Use local Ollama server (requires ollamaUrl)
      '';
    };

    # Anthropic-specific options
    claudeApiKeyFile = mkOption {
      type = types.nullOr types.path;
      default = null;
      description = ''
        Path to file containing the Claude/Anthropic API key.
        Required when llmBackend is "anthropic".
        The file should contain only the API key with no trailing newline.
      '';
    };

    # Ollama-specific options
    ollamaUrl = mkOption {
      type = types.str;
      default = "http://localhost:11434";
      description = "URL of the Ollama server.";
    };

    ollamaModel = mkOption {
      type = types.str;
      default = "qwen3:14b-q4_K_M";
      description = "Ollama model to use for inference.";
    };

    ollamaTemperature = mkOption {
      type = types.float;
      default = 0.2;
      description = ''
        Temperature for Ollama inference.
        Lower values (0.1-0.3) are more deterministic and better for tool calling.
        Higher values (0.7-1.0) are more creative.
      '';
    };

    # Common options
    mcpGatewayUrl = mkOption {
      type = types.str;
      default = "http://localhost:8085";
      description = "URL of the mcp-gateway instance.";
    };

    toolRefreshInterval = mkOption {
      type = types.int;
      default = 300;
      description = "Seconds between automatic tool registry refreshes.";
    };

    systemPromptFile = mkOption {
      type = types.nullOr types.path;
      default = null;
      description = ''
        Path to file containing a custom system prompt for the AI.
        If null, uses the default prompt.
      '';
    };

    logLevel = mkOption {
      type = types.enum [
        "DEBUG"
        "INFO"
        "WARNING"
        "ERROR"
      ];
      default = "INFO";
      description = "Logging level for the bot.";
    };
  };

  config = mkIf cfg.enable {
    # Assertions
    assertions = [
      {
        assertion = cfg.xmppDomain != "";
        message = "services.axios-chat.bot.xmppDomain must be set";
      }
      {
        assertion = isAnthropic -> cfg.claudeApiKeyFile != null;
        message = "services.axios-chat.bot.claudeApiKeyFile must be set when using anthropic backend";
      }
    ];

    # Systemd service
    systemd.services.axios-ai-bot = {
      description = "Axios AI Bot - XMPP AI Assistant";
      after =
        [
          "network-online.target"
          "prosody.service"
          "mcp-gateway.service"
        ]
        ++ optionals isOllama [ "ollama.service" ];
      wants =
        [
          "network-online.target"
          "mcp-gateway.service"
        ]
        ++ optionals isOllama [ "ollama.service" ];
      wantedBy = [ "multi-user.target" ];

      environment =
        {
          XMPP_JID = "${cfg.xmppUser}@${cfg.xmppDomain}";
          XMPP_SERVER = cfg.xmppServer;
          XMPP_PORT = toString cfg.xmppPort;
          XMPP_PASSWORD_FILE = cfg.xmppPasswordFile;
          LLM_BACKEND = cfg.llmBackend;
          MCP_GATEWAY_URL = cfg.mcpGatewayUrl;
          TOOL_REFRESH_INTERVAL = toString cfg.toolRefreshInterval;
          PYTHONUNBUFFERED = "1";
          LOG_LEVEL = cfg.logLevel;
        }
        // optionalAttrs isAnthropic {
          ANTHROPIC_API_KEY_FILE = cfg.claudeApiKeyFile;
        }
        // optionalAttrs isOllama {
          OLLAMA_URL = cfg.ollamaUrl;
          OLLAMA_MODEL = cfg.ollamaModel;
          OLLAMA_TEMPERATURE = toString cfg.ollamaTemperature;
        }
        // optionalAttrs (cfg.systemPromptFile != null) {
          SYSTEM_PROMPT_FILE = cfg.systemPromptFile;
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
        RestrictAddressFamilies = [
          "AF_INET"
          "AF_INET6"
          "AF_UNIX"
        ];
        RestrictNamespaces = true;
        LockPersonality = true;
        MemoryDenyWriteExecute = true;
        RestrictRealtime = true;
        RestrictSUIDSGID = true;
        RemoveIPC = true;

        # Allow reading secret files and DNS resolution
        BindReadOnlyPaths =
          [
            cfg.xmppPasswordFile
            # DNS resolution (required for Tailscale MagicDNS)
            "/etc/resolv.conf"
            "/etc/hosts"
            "/etc/nsswitch.conf"
            "/run/systemd/resolve"
          ]
          ++ optionals (isAnthropic && cfg.claudeApiKeyFile != null) [ cfg.claudeApiKeyFile ]
          ++ optionals (cfg.systemPromptFile != null) [ cfg.systemPromptFile ];
      };
    };
  };
}
