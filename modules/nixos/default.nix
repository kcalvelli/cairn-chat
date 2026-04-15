# NixOS module for cairn-chat
#
# Prosody XMPP server for private family chat over Tailscale.
# The AI bot (Sid) connects as a native XMPP client from the sid repo.
{
  imports = [
    ./prosody.nix
  ];
}
