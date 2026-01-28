"""Main entry point for axios-ai-bot."""

import asyncio
import json
import logging
import os
import signal
import sys
from pathlib import Path
from typing import Any

from .llm import create_llm_client
from .router import create_message_handler
from .tools import DynamicToolRegistry
from .xmpp import AxiosBot

# Configure logging
log_level = os.environ.get("LOG_LEVEL", "INFO")
logging.basicConfig(
    level=getattr(logging, log_level),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Enable slixmpp debug logging if DEBUG level
if log_level == "DEBUG":
    logging.getLogger("slixmpp").setLevel(logging.DEBUG)


def load_secret(path: str) -> str:
    """Load a secret from a file.

    Args:
        path: Path to the secret file

    Returns:
        The secret value with whitespace stripped
    """
    return Path(path).read_text().strip()


def get_config() -> dict[str, Any]:
    """Load configuration from environment variables.

    Returns:
        Configuration dictionary
    """
    config: dict[str, Any] = {}

    # Required: XMPP credentials
    xmpp_jid = os.environ.get("XMPP_JID")
    if not xmpp_jid:
        logger.error("XMPP_JID environment variable is required")
        sys.exit(1)
    config["xmpp_jid"] = xmpp_jid

    xmpp_password_file = os.environ.get("XMPP_PASSWORD_FILE")
    if xmpp_password_file:
        config["xmpp_password"] = load_secret(xmpp_password_file)
    else:
        xmpp_password = os.environ.get("XMPP_PASSWORD")
        if not xmpp_password:
            logger.error("XMPP_PASSWORD or XMPP_PASSWORD_FILE is required")
            sys.exit(1)
        config["xmpp_password"] = xmpp_password

    # Anthropic API key (required)
    anthropic_key_file = os.environ.get("ANTHROPIC_API_KEY_FILE")
    if anthropic_key_file:
        config["anthropic_key"] = load_secret(anthropic_key_file)
    else:
        anthropic_key = os.environ.get("ANTHROPIC_API_KEY")
        if not anthropic_key:
            logger.error("ANTHROPIC_API_KEY or ANTHROPIC_API_KEY_FILE is required")
            sys.exit(1)
        config["anthropic_key"] = anthropic_key

    # Optional: mcp-gateway URL
    config["mcp_gateway_url"] = os.environ.get("MCP_GATEWAY_URL", "http://localhost:8085")

    # Optional: Tool refresh interval
    config["tool_refresh_interval"] = os.environ.get("TOOL_REFRESH_INTERVAL", "300")

    # Optional: Custom system prompt
    system_prompt_file = os.environ.get("SYSTEM_PROMPT_FILE")
    if system_prompt_file and Path(system_prompt_file).exists():
        config["system_prompt"] = Path(system_prompt_file).read_text()
    else:
        config["system_prompt"] = ""

    # Optional: XMPP server address (for connecting to localhost with different domain)
    config["xmpp_server"] = os.environ.get("XMPP_SERVER", "")
    config["xmpp_port"] = int(os.environ.get("XMPP_PORT", "5222"))
    config["xmpp_verify_ssl"] = os.environ.get("XMPP_VERIFY_SSL", "false").lower() == "true"

    # Optional: Per-user configuration (location, timezone)
    user_config_json = os.environ.get("USER_CONFIG", "")
    if user_config_json:
        try:
            config["user_config"] = json.loads(user_config_json)
            logger.info(f"Loaded user config for {len(config['user_config'].get('users', {}))} users")
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse USER_CONFIG: {e}")
            config["user_config"] = {}
    else:
        config["user_config"] = {}

    return config


async def async_main() -> None:
    """Async main entry point."""
    logger.info("Starting axios-ai-bot...")

    # Load configuration
    config = get_config()

    # Initialize components
    tool_registry = DynamicToolRegistry(
        gateway_url=config["mcp_gateway_url"],
        refresh_interval=int(config["tool_refresh_interval"]),
    )

    # Create LLM client (Anthropic Claude)
    llm_config = {
        "api_key": config["anthropic_key"],
        "system_prompt": config["system_prompt"] or None,
        "user_config": config["user_config"],
    }
    llm_client = create_llm_client(llm_config)

    # Create XMPP bot first (without handler)
    bot = AxiosBot(
        jid=config["xmpp_jid"],
        password=config["xmpp_password"],
        message_handler=None,  # Set after creating handler
        server=config["xmpp_server"] or None,
        port=config["xmpp_port"],
        verify_ssl=config["xmpp_verify_ssl"],
    )

    # Create send_message callback for progress updates
    async def send_progress_message(to_jid: str, message: str) -> None:
        """Send a progress message to the user."""
        bot.send_message(mto=to_jid, mbody=message, mtype="chat")

    # Create message handler with progress callback
    message_handler = create_message_handler(
        tool_registry, llm_client, send_message=send_progress_message
    )
    bot.set_message_handler(message_handler)

    # Set up signal handlers
    loop = asyncio.get_running_loop()
    stop_event = asyncio.Event()

    def signal_handler() -> None:
        logger.info("Shutdown signal received")
        stop_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, signal_handler)

    # Start tool registry refresh
    try:
        await tool_registry.start()
        logger.info(f"Loaded {len(tool_registry.tools)} tools from mcp-gateway")
    except Exception as e:
        logger.warning(f"Failed to load tools from mcp-gateway: {e}")
        logger.warning("Bot will continue without tools - check mcp-gateway status")

    # Run the bot
    server_info = ""
    if config["xmpp_server"]:
        server_info = f" via {config['xmpp_server']}:{config['xmpp_port']}"
    logger.info(f"Connecting as {config['xmpp_jid']}{server_info}...")
    if config["xmpp_server"]:
        bot.connect(config["xmpp_server"], config["xmpp_port"])
    else:
        bot.connect()

    # Wait for either shutdown signal or bot disconnection
    # This allows slixmpp's event loop to process while we wait
    async def wait_for_stop():
        await stop_event.wait()
        bot.disconnect()

    # Run until stopped or disconnected
    try:
        await asyncio.gather(
            wait_for_stop(),
            bot.disconnected,
            return_exceptions=True,
        )
    except asyncio.CancelledError:
        pass

    # Cleanup
    logger.info("Shutting down...")
    await tool_registry.stop()
    if bot.is_connected():
        bot.disconnect()
    logger.info("Goodbye!")


def main() -> None:
    """Main entry point."""
    try:
        asyncio.run(async_main())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
