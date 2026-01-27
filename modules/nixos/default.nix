# Combined NixOS module for axios-chat
#
# Imports both the Prosody XMPP server and AI bot modules.
# Use this for a complete axios-chat installation.
{
  config,
  lib,
  pkgs,
  ...
}:

with lib;

{
  imports = [
    ./prosody.nix
    ./bot.nix
  ];

  # Assertions for the combined module
  config = {
    assertions = [
      {
        assertion =
          config.services.axios-chat.bot.enable
          -> (config.services.axios-chat.prosody.enable || config.services.axios-chat.bot.xmppDomain != "");
        message = ''
          services.axios-chat.bot requires either:
          - services.axios-chat.prosody.enable = true (local Prosody server)
          - services.axios-chat.bot.xmppDomain pointing to an external XMPP server
        '';
      }
    ];
  };
}
