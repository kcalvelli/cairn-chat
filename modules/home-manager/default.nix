# Home-Manager module for axios-chat user preferences
#
# This module provides user-level configuration for axios-chat,
# such as default XMPP account and future client configuration.
{
  config,
  lib,
  pkgs,
  ...
}:

with lib;

let
  cfg = config.programs.axios-chat;
in
{
  options.programs.axios-chat = {
    enable = mkEnableOption "axios-chat user configuration";

    defaultAccount = mkOption {
      type = types.nullOr types.str;
      default = null;
      example = "user@chat.home.ts.net";
      description = ''
        Default XMPP account JID.
        This can be used by XMPP client configurations.
      '';
    };

    # Future expansion points:
    # - XMPP client configuration (Dino, Gajim)
    # - Notification preferences
    # - Bot personality settings
  };

  config = mkIf cfg.enable {
    # Currently a placeholder for future user-level configuration
    # Examples of what could be added:
    #
    # - Configure Dino/Gajim with the default account
    # - Set up desktop notifications
    # - Configure keyboard shortcuts for XMPP clients

    home.sessionVariables = mkIf (cfg.defaultAccount != null) {
      AXIOS_CHAT_ACCOUNT = cfg.defaultAccount;
    };
  };
}
