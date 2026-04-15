# cairn-chat

Prosody XMPP server for private family chat, accessible only within your Tailscale network.

## Features

- **Tailscale-Only Access**: Bound exclusively to your tailnet — no public exposure
- **Multi-User Chat**: Group conversations via MUC (XEP-0045)
- **File Sharing**: Images and documents via HTTP File Upload (XEP-0363)
- **Message Archive**: Offline delivery and history sync via MAM
- **Native Clients**: Use Conversations (Android), Gajim (Windows/Linux), Dino (Linux), or any XMPP client

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│  TAILNET                                                 │
│                                                          │
│  ┌────────────────────────────────────────────────────┐ │
│  │               XMPP Clients                          │ │
│  │  Conversations (Android) │ Gajim │ Dino │ Sid (AI) │ │
│  └──────────────────────┬─────────────────────────────┘ │
│                          │                               │
│                          ▼                               │
│  ┌────────────────────────────────────────────────────┐ │
│  │              Prosody XMPP Server                    │ │
│  │    Tailscale Serve + MUC + HTTP File Share + MAM    │ │
│  └────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────┘
```

Sid (the AI assistant) connects as a native XMPP client from the [sid](https://github.com/keithah/sid) repo.

## Installation

### As a Flake Input

```nix
{
  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixpkgs-unstable";
    cairn-chat.url = "github:kcalvelli/cairn-chat";
  };

  outputs = { self, nixpkgs, cairn-chat, ... }: {
    nixosConfigurations.myhost = nixpkgs.lib.nixosSystem {
      system = "x86_64-linux";
      modules = [
        cairn-chat.nixosModules.default
        ./configuration.nix
      ];
    };
  };
}
```

### NixOS Configuration

```nix
{ config, ... }:

{
  services.cairn-chat.prosody = {
    enable = true;
    domain = "chat.home.ts.net";
    tailscaleServe.enable = true;
    admins = [ "keith@chat.home.ts.net" ];

    muc.enable = true;  # Group chats (default: true)

    httpFileShare = {
      enable = true;
      maxFileSize = 10485760;    # 10 MB
      expiresAfter = "1 week";
    };

    messageArchive = {
      enable = true;
      expireAfter = "1w";
    };
  };
}
```

## User Account Setup

```bash
# Create user accounts
sudo prosodyctl adduser keith@chat.home.ts.net
sudo prosodyctl adduser spouse@chat.home.ts.net

# Create the AI bot account (used by sid)
sudo prosodyctl adduser sid@chat.home.ts.net
```

## Client Setup

### Android: Conversations

1. Install [Conversations](https://conversations.im/) from F-Droid or Play Store
2. Add account: `yourname@chat.home.ts.net`
3. Server: Use your Tailscale domain or IP

### Linux: Dino

1. Install Dino: `nix-shell -p dino`
2. Add account with your JID
3. Connect to your Tailscale domain

### Windows: Gajim

1. Download [Gajim](https://gajim.org/)
2. Add account with your JID
3. Set server to your Tailscale domain

## Related Projects

- [cairn](https://github.com/kcalvelli/cairn) - NixOS framework
- [sid](https://github.com/keithah/sid) - AI bot (connects to this server as a native XMPP client)

## License

MIT
