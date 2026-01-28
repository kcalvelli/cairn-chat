"""Message router that sends all tools to the LLM for dynamic selection."""

import logging
from collections.abc import Awaitable, Callable

from .domains import DomainRegistry, get_default_registry
from .llm import LLMBackend
from .media import UserMessage
from .tools import DynamicToolRegistry

logger = logging.getLogger(__name__)

# Type alias for send message callback
SendMessageCallback = Callable[[str, str], Awaitable[None]]

# Commands that should be handled locally
LOCAL_COMMANDS: dict[str, str] = {
    "/help": "Available commands:\n"
    "  /help - Show this help message\n"
    "  /refresh - Refresh available tools\n"
    "  /tools - List available tools\n"
    "  /clear - Clear conversation history\n"
    "\nJust chat naturally - I'll use the right tools automatically!",
    "/ping": "Pong!",
}


class MessageRouter:
    """Routes messages to the LLM with all available tools."""

    def __init__(
        self,
        tool_registry: DynamicToolRegistry,
        llm_client: LLMBackend,
        send_message: SendMessageCallback | None = None,
        domain_registry: DomainRegistry | None = None,
        enable_domain_routing: bool = True,
    ):
        """Initialize the message router.

        Args:
            tool_registry: Dynamic tool registry for tool access
            llm_client: LLM backend for execution
            send_message: Optional callback to send XMPP messages (for progress updates)
            domain_registry: Optional domain registry for routing (defaults to built-in)
            enable_domain_routing: Whether to use domain-aware routing (default True)
        """
        self.tool_registry = tool_registry
        self.llm_client = llm_client
        self.send_message = send_message
        self.domain_registry = domain_registry or get_default_registry()
        self.enable_domain_routing = enable_domain_routing

    async def handle_message(self, user_jid: str, message: UserMessage) -> str:
        """Route a message and generate a response.

        Args:
            user_jid: The user's JID
            message: The user's message (text and optional media attachments)

        Returns:
            The response to send back
        """
        # Handle local commands (text-only, no media)
        text = message.text.strip()
        if text.startswith("/") and not message.has_attachments:
            return await self._handle_command(user_jid, text)

        # Get all available tools - let the LLM decide which to use based on descriptions
        tools = self.tool_registry.get_all_tools()

        if not tools:
            # No tools available, use simple response
            logger.info("No tools available, using simple response")
            return await self.llm_client.simple_response(user_jid, message)

        # Format tools for the LLM
        formatted_tools = self.tool_registry.format_tools_for_claude(tools)

        # Create progress callback if we have a send_message function
        progress_callback = None
        if self.send_message:

            async def progress_callback(msg: str) -> None:
                await self.send_message(user_jid, msg)

        # Use domain routing if enabled and client supports it
        if self.enable_domain_routing and hasattr(self.llm_client, "execute_with_routing"):
            logger.info(f"Using domain routing with {len(formatted_tools)} total tools")
            return await self.llm_client.execute_with_routing(
                user_id=user_jid,
                message=message,
                all_tools=formatted_tools,
                tool_executor=self.tool_registry.execute_tool,
                registry=self.domain_registry,
                progress_callback=progress_callback,
            )

        # Fallback: Send all tools to LLM (when routing disabled or not supported)
        logger.info(f"Using all {len(formatted_tools)} available tools (no routing)")
        return await self.llm_client.execute_with_tools(
            user_id=user_jid,
            message=message,
            tools=formatted_tools,
            tool_executor=self.tool_registry.execute_tool,
            progress_callback=progress_callback,
        )

    async def _handle_command(self, user_jid: str, command: str) -> str:
        """Handle a slash command.

        Args:
            user_jid: The user's JID
            command: The command (including /)

        Returns:
            The response
        """
        cmd = command.lower().split()[0]

        # Static commands
        if cmd in LOCAL_COMMANDS:
            return LOCAL_COMMANDS[cmd]

        # Dynamic commands
        if cmd == "/refresh":
            try:
                count = await self.tool_registry.refresh()
                return f"Refreshed {count} tools from mcp-gateway"
            except Exception as e:
                return f"Failed to refresh tools: {e}"

        if cmd == "/tools":
            tools = self.tool_registry.get_all_tools()
            if not tools:
                return "No tools available. Is mcp-gateway running?"

            # Group by server
            by_server: dict[str, list[str]] = {}
            for tool in tools:
                server = tool.get("server", "unknown")
                name = tool["name"].split("__")[-1]  # Get original name
                by_server.setdefault(server, []).append(name)

            lines = [f"Available tools ({len(tools)} total):"]
            for server in sorted(by_server.keys()):
                tool_names = ", ".join(sorted(by_server[server]))
                lines.append(f"  {server}: {tool_names}")
            return "\n".join(lines)

        if cmd == "/clear":
            self.llm_client.clear_history(user_jid)
            return "Conversation history cleared."

        return f"Unknown command: {cmd}\nType /help for available commands."


def create_message_handler(
    tool_registry: DynamicToolRegistry,
    llm_client: LLMBackend,
    send_message: SendMessageCallback | None = None,
) -> Any:
    """Create a message handler function for the XMPP bot.

    Args:
        tool_registry: Dynamic tool registry
        llm_client: LLM backend
        send_message: Optional callback to send XMPP messages (for progress updates)

    Returns:
        Async message handler function
    """
    router = MessageRouter(tool_registry, llm_client, send_message=send_message)

    async def handler(from_jid: str, to_jid: str, message: UserMessage) -> str | None:
        """Handle an incoming message."""
        return await router.handle_message(from_jid, message)

    return handler
