"""Main entry point for axios-ai-bot (Sid backend)."""

import asyncio
import logging
import os
import signal
import sys
from pathlib import Path
from typing import Any

from .llm import SidClient
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
    """Load a secret from a file."""
    return Path(path).read_text().strip()


def get_config() -> dict[str, Any]:
    """Load configuration from environment variables."""
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

    # Sid backend configuration
    config["sid_gateway_url"] = os.environ.get("SID_GATEWAY_URL", "http://127.0.0.1:18789")
    config["sid_agent_id"] = os.environ.get("SID_AGENT_ID", "main")
    config["sid_timeout"] = float(os.environ.get("SID_TIMEOUT", "300"))

    # Auth token (optional but recommended)
    sid_token_file = os.environ.get("SID_AUTH_TOKEN_FILE")
    if sid_token_file:
        config["sid_auth_token"] = load_secret(sid_token_file)
    else:
        config["sid_auth_token"] = os.environ.get("SID_AUTH_TOKEN")

    # XMPP server address (for connecting to localhost with different domain)
    config["xmpp_server"] = os.environ.get("XMPP_SERVER", "")
    config["xmpp_port"] = int(os.environ.get("XMPP_PORT", "5222"))
    config["xmpp_verify_ssl"] = os.environ.get("XMPP_VERIFY_SSL", "false").lower() == "true"

    return config


async def async_main() -> None:
    """Async main entry point."""
    logger.info("Starting axios-ai-bot with Sid backend...")

    # Load configuration
    config = get_config()

    # Create Sid LLM client
    logger.info(f"Connecting to Sid at {config['sid_gateway_url']}")
    llm_client = SidClient(
        gateway_url=config["sid_gateway_url"],
        auth_token=config.get("sid_auth_token"),
        agent_id=config["sid_agent_id"],
        timeout=config["sid_timeout"],
    )

    # Tool registry - not used with Sid (Sid has its own tools)
    # but keep for potential future use or /tools command
    tool_registry = DynamicToolRegistry(
        gateway_url="http://localhost:8085",  # Not actually used
        refresh_interval=3600,  # Refresh rarely since not used
    )

    # Create XMPP bot
    bot = AxiosBot(
        jid=config["xmpp_jid"],
        password=config["xmpp_password"],
        message_handler=None,
        server=config["xmpp_server"] or None,
        port=config["xmpp_port"],
        verify_ssl=config["xmpp_verify_ssl"],
    )

    # Create send_message callback for progress updates
    async def send_progress_message(to_jid: str, message: str) -> None:
        """Send a progress message to the user."""
        bot.send_message(mto=to_jid, mbody=message, mtype="chat")

    # Create message handler
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

    # Run the bot
    server_info = ""
    if config["xmpp_server"]:
        server_info = f" via {config['xmpp_server']}:{config['xmpp_port']}"
    logger.info(f"Connecting as {config['xmpp_jid']}{server_info}...")
    if config["xmpp_server"]:
        bot.connect(config["xmpp_server"], config["xmpp_port"])
    else:
        bot.connect()

    # Wait for shutdown
    async def wait_for_stop():
        await stop_event.wait()
        bot.disconnect()

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
    await llm_client.close()
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
