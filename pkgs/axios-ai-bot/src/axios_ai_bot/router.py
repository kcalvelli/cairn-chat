"""Intent router that combines fast keyword matching with LLM classification."""

import logging
from collections.abc import Awaitable, Callable
from typing import Any

from .llm import LLMClient
from .tools import DynamicToolRegistry, classify_intent_fast

logger = logging.getLogger(__name__)

# Type alias for send message callback
SendMessageCallback = Callable[[str, str], Awaitable[None]]

# Commands that should be handled locally
LOCAL_COMMANDS: dict[str, str] = {
    "/help": "Available commands:\n"
    "  /help - Show this help message\n"
    "  /refresh - Refresh available tools\n"
    "  /tools - List available tool categories\n"
    "  /clear - Clear conversation history\n"
    "\nYou can also just chat naturally! Ask me to:\n"
    "  - Check your calendar\n"
    "  - Send an email\n"
    "  - Look up a contact\n"
    "  - Search the web\n"
    "  - And more!",
    "/ping": "Pong!",
}


class IntentRouter:
    """Routes messages to appropriate handlers based on intent."""

    def __init__(
        self,
        tool_registry: DynamicToolRegistry,
        llm_client: LLMClient,
        send_message: SendMessageCallback | None = None,
        use_haiku_classification: bool = True,
    ):
        """Initialize the intent router.

        Args:
            tool_registry: Dynamic tool registry for tool access
            llm_client: LLM client for classification and execution
            send_message: Optional callback to send XMPP messages (for progress updates)
            use_haiku_classification: Whether to use Haiku for ambiguous cases
        """
        self.tool_registry = tool_registry
        self.llm_client = llm_client
        self.send_message = send_message
        self.use_haiku_classification = use_haiku_classification

    async def handle_message(self, user_jid: str, message: str) -> str:
        """Route a message and generate a response.

        Args:
            user_jid: The user's JID
            message: The user's message

        Returns:
            The response to send back
        """
        message = message.strip()

        # Handle local commands
        if message.startswith("/"):
            return await self._handle_command(user_jid, message)

        # Fast keyword-based classification
        categories = classify_intent_fast(message)

        # If no keywords matched, use LLM classification (if enabled)
        if not categories and self.use_haiku_classification:
            categories = await self.llm_client.classify_intent(message)

        # If still no categories or just "general", use simple response
        if not categories or categories == ["general"]:
            return await self.llm_client.simple_response(user_jid, message)

        # Get tools for the detected categories
        tools = self.tool_registry.get_tools_for_categories(categories)

        if not tools:
            # No tools available for these categories
            logger.warning(f"No tools for categories {categories}, falling back to simple response")
            return await self.llm_client.simple_response(user_jid, message)

        # Format tools for Claude and execute
        formatted_tools = self.tool_registry.format_tools_for_claude(tools)
        logger.info(f"Using {len(formatted_tools)} tools for categories: {categories}")

        # Create progress callback if we have a send_message function
        progress_callback = None
        if self.send_message:
            async def progress_callback(msg: str) -> None:
                await self.send_message(user_jid, msg)

        return await self.llm_client.execute_with_tools(
            user_jid=user_jid,
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
                categories = self.tool_registry.get_categories()
                cat_list = ", ".join(categories)
                return f"Refreshed {count} tools in {len(categories)} categories: {cat_list}"
            except Exception as e:
                return f"Failed to refresh tools: {e}"

        if cmd == "/tools":
            categories = self.tool_registry.get_categories()
            tools = self.tool_registry.get_all_tools()
            if not tools:
                return "No tools available. Is mcp-gateway running?"

            lines = ["Available tool categories:"]
            for cat in sorted(categories):
                cat_tools = self.tool_registry.tool_categories.get(cat, [])
                lines.append(f"  {cat}: {len(cat_tools)} tools")
            return "\n".join(lines)

        if cmd == "/clear":
            self.llm_client.clear_history(user_jid)
            return "Conversation history cleared."

        return f"Unknown command: {cmd}\nType /help for available commands."


def create_message_handler(
    tool_registry: DynamicToolRegistry,
    llm_client: LLMClient,
    send_message: SendMessageCallback | None = None,
) -> Any:
    """Create a message handler function for the XMPP bot.

    Args:
        tool_registry: Dynamic tool registry
        llm_client: LLM client
        send_message: Optional callback to send XMPP messages (for progress updates)

    Returns:
        Async message handler function
    """
    router = IntentRouter(tool_registry, llm_client, send_message=send_message)

    async def handler(from_jid: str, to_jid: str, body: str) -> str | None:
        """Handle an incoming message."""
        return await router.handle_message(from_jid, body)

    return handler
