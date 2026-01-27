{
  description = "axios-chat - Family XMPP chat with AI assistant for the axios ecosystem";

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
      # Overlay - adds axios-ai-bot to pkgs
      overlays.default = final: prev: {
        axios-ai-bot = self.packages.${final.system}.default;
      };

      # NixOS modules
      nixosModules = {
        default = import ./modules/nixos;
        prosody = import ./modules/nixos/prosody.nix;
        bot = import ./modules/nixos/bot.nix;
      };

      # Home-Manager module
      homeManagerModules.default = import ./modules/home-manager;

      # Python package
      packages = forAllSystems (
        system:
        let
          pkgs = nixpkgs.legacyPackages.${system};
        in
        {
          axios-ai-bot = pkgs.python3Packages.buildPythonApplication {
            pname = "axios-ai-bot";
            version = "0.1.0";
            pyproject = true;

            src = ./pkgs/axios-ai-bot;

            build-system = with pkgs.python3Packages; [
              hatchling
            ];

            dependencies = with pkgs.python3Packages; [
              slixmpp # Async XMPP client
              anthropic # Claude API
              httpx # Async HTTP client
              pydantic # Data validation
            ];

            # No tests yet
            doCheck = false;

            meta = with pkgs.lib; {
              description = "AI-powered XMPP bot for the axios ecosystem";
              homepage = "https://github.com/kcalvelli/axios-chat";
              license = licenses.mit;
              maintainers = [ ];
              mainProgram = "axios-ai-bot";
              platforms = platforms.linux;
            };
          };

          default = self.packages.${system}.axios-ai-bot;
        }
      );

      # Development shell
      devShells = forAllSystems (
        system:
        let
          pkgs = nixpkgs.legacyPackages.${system};
        in
        {
          default = pkgs.mkShell {
            packages = with pkgs; [
              # Nix tools
              nil
              nixfmt-rfc-style

              # Python development
              python311
              python311Packages.black
              python311Packages.ruff
              python311Packages.mypy
              python311Packages.pytest
              python311Packages.pip
              python311Packages.venvShellHook
            ];

            venvDir = "./.venv";

            postVenvCreation = ''
              unset SOURCE_DATE_EPOCH
              pip install -e ./pkgs/axios-ai-bot
            '';

            postShellHook = ''
              unset SOURCE_DATE_EPOCH
              echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
              echo "  axios-chat development environment"
              echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
              echo ""
              echo "Commands:"
              echo "  nix build .#axios-ai-bot  - Build the bot package"
              echo "  pytest                    - Run tests"
              echo "  black .                   - Format Python code"
              echo "  nix fmt                   - Format Nix code"
            '';
          };
        }
      );

      # Formatter
      formatter = forAllSystems (system: nixpkgs.legacyPackages.${system}.nixfmt-rfc-style);
    };
}
