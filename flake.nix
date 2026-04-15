{
  description = "cairn-chat - Family XMPP server (Prosody on Tailscale)";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixpkgs-unstable";
  };

  outputs =
    { self, nixpkgs }:
    let
      supportedSystems = [
        "x86_64-linux"
        "aarch64-linux"
      ];
      forAllSystems = nixpkgs.lib.genAttrs supportedSystems;
    in
    {
      # NixOS modules
      nixosModules = {
        default = import ./modules/nixos;
        prosody = import ./modules/nixos/prosody.nix;
      };

      # Home-Manager module
      homeManagerModules.default = import ./modules/home-manager;

      # Development shell
      devShells = forAllSystems (
        system:
        let
          pkgs = nixpkgs.legacyPackages.${system};
        in
        {
          default = pkgs.mkShell {
            packages = with pkgs; [
              nil
              nixfmt-rfc-style
            ];

            shellHook = ''
              echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
              echo "  cairn-chat development environment"
              echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
              echo ""
              echo "Commands:"
              echo "  nix fmt  - Format Nix code"
              echo ""
              echo "This repo provides the Prosody XMPP server module."
              echo "The AI bot (Sid) lives in the sid repo."
            '';
          };
        }
      );

      # Formatter
      formatter = forAllSystems (system: nixpkgs.legacyPackages.${system}.nixfmt-rfc-style);
    };
}
