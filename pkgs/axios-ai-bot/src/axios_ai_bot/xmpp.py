"""XMPP client using slixmpp for the AI bot."""

import asyncio
import logging
import ssl
from collections.abc import Callable, Coroutine
from typing import Any

import slixmpp
from slixmpp.exceptions import IqError, IqTimeout

logger = logging.getLogger(__name__)

# Type alias for message handler
MessageHandler = Callable[[str, str, str], Coroutine[Any, Any, str | None]]


class AxiosBot(slixmpp.ClientXMPP):
    """XMPP bot client for axios-chat."""

    def __init__(
        self,
        jid: str,
        password: str,
        message_handler: MessageHandler | None = None,
        server: str | None = None,
        port: int = 5222,
        use_tls: bool = True,
        verify_ssl: bool = False,
    ):
        """Initialize the XMPP bot.

        Args:
            jid: The bot's JID (e.g., ai@chat.example.ts.net)
            password: The bot's XMPP password
            message_handler: Async callback for handling messages.
                Takes (from_jid, to_jid, body) and returns optional response.
            server: XMPP server hostname (defaults to domain from JID)
            port: XMPP server port (default 5222)
            use_tls: Whether to use TLS (default True)
            verify_ssl: Whether to verify SSL certificates (default False for self-signed)
        """
        super().__init__(jid, password)

        self.message_handler = message_handler
        self._reconnect_delay = 1.0
        self._max_reconnect_delay = 60.0
        self._server = server
        self._port = port
        self._use_tls = use_tls

        # Configure SSL context for self-signed certificates
        if not verify_ssl:
            self.ssl_context = ssl.create_default_context()
            self.ssl_context.check_hostname = False
            self.ssl_context.verify_mode = ssl.CERT_NONE

        # Register plugins
        self.register_plugin("xep_0030")  # Service Discovery
        self.register_plugin("xep_0199")  # XMPP Ping
        self.register_plugin("xep_0085")  # Chat State Notifications

        # Event handlers
        self.add_event_handler("session_start", self._on_session_start)
        self.add_event_handler("message", self._on_message)
        self.add_event_handler("disconnected", self._on_disconnected)
        self.add_event_handler("connection_failed", self._on_connection_failed)

    async def _on_session_start(self, event: Any) -> None:
        """Handle session start - send presence and get roster."""
        try:
            await self.get_roster()
        except (IqError, IqTimeout) as e:
            logger.warning(f"Failed to get roster: {e}")

        self.send_presence(pstatus="Axios AI - Ready to help!")
        self._reconnect_delay = 1.0  # Reset on successful connection
        logger.info(f"XMPP session started as {self.boundjid.bare}")

    async def _on_message(self, msg: slixmpp.Message) -> None:
        """Handle incoming messages."""
        # Only handle chat messages (not groupchat, error, etc.)
        if msg["type"] not in ("chat", "normal"):
            return

        # Ignore messages from self
        if msg["from"].bare == self.boundjid.bare:
            return

        # Get message body
        body = msg["body"]
        if not body:
            return

        from_jid = msg["from"].bare
        to_jid = msg["to"].bare

        logger.info(f"Message from {from_jid}: {body[:50]}...")

        # Handle the message
        if self.message_handler:
            try:
                # Send "composing" state
                self._send_chat_state(from_jid, "composing")

                # Process the message
                response = await self.message_handler(from_jid, to_jid, body)

                # Send response if any
                if response:
                    self.send_message(mto=from_jid, mbody=response, mtype="chat")

                # Clear chat state
                self._send_chat_state(from_jid, "active")

            except Exception as e:
                logger.error(f"Error handling message: {e}")
                self.send_message(
                    mto=from_jid,
                    mbody=f"I'm sorry, I encountered an error processing your request: {e}",
                    mtype="chat",
                )
                self._send_chat_state(from_jid, "active")

    def _send_chat_state(self, to_jid: str, state: str) -> None:
        """Send a chat state notification.

        Args:
            to_jid: Recipient JID
            state: Chat state (composing, active, paused, inactive, gone)
        """
        try:
            msg = self.make_message(mto=to_jid, mtype="chat")
            msg["chat_state"] = state
            msg.send()
        except Exception as e:
            logger.debug(f"Failed to send chat state: {e}")

    async def _on_disconnected(self, event: Any) -> None:
        """Handle disconnection with exponential backoff reconnect."""
        logger.warning(f"Disconnected from XMPP server, reconnecting in {self._reconnect_delay}s")
        await asyncio.sleep(self._reconnect_delay)
        self._reconnect_delay = min(self._reconnect_delay * 2, self._max_reconnect_delay)

        try:
            if self._server:
                self.connect((self._server, self._port))
            else:
                self.connect()
        except Exception as e:
            logger.error(f"Reconnection failed: {e}")

    async def _on_connection_failed(self, event: Any) -> None:
        """Handle connection failure."""
        logger.error(f"Connection failed, retrying in {self._reconnect_delay}s")
        await asyncio.sleep(self._reconnect_delay)
        self._reconnect_delay = min(self._reconnect_delay * 2, self._max_reconnect_delay)

    def set_message_handler(self, handler: MessageHandler) -> None:
        """Set the message handler callback.

        Args:
            handler: Async callback for handling messages
        """
        self.message_handler = handler

    async def run(self) -> None:
        """Connect and run the bot."""
        if self._server:
            self.connect((self._server, self._port))
        else:
            self.connect()
        await self.disconnected
