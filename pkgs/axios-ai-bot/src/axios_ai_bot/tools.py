"""Dynamic tool registry that fetches tools from mcp-gateway."""

import asyncio
import logging
from collections import defaultdict
from typing import Any

import httpx

logger = logging.getLogger(__name__)

# Category mappings inferred from server names
SERVER_CATEGORIES: dict[str, str] = {
    "axios-ai-mail": "email",
    "mcp-dav": "calendar",
    "git": "code",
    "github": "code",
    "filesystem": "files",
    "brave-search": "search",
    "context7": "search",
    "time": "general",
    "sequential-thinking": "general",
}

# Tool name patterns that override server category
TOOL_NAME_CATEGORIES: dict[str, str] = {
    "contact": "contacts",  # Any tool with "contact" in name -> contacts category
    "search": "search",
}

# Keywords for fast intent classification
CATEGORY_KEYWORDS: dict[str, list[str]] = {
    "email": [
        "email",
        "mail",
        "send",
        "inbox",
        "message to",
        "reply",
        "draft",
        "unread",
    ],
    "calendar": [
        "calendar",
        "schedule",
        "meeting",
        "appointment",
        "event",
        "busy",
        "free",
        "tomorrow",
        "today",
        "next week",
    ],
    "contacts": [
        "contact",
        "contacts",
        "phone number",
        "address",
        "email address",
        "who is",
        "find person",
        "look up person",
        "named",  # "anyone named John"
    ],
    "code": [
        "git",
        "commit",
        "branch",
        "pull request",
        "pr",
        "push",
        "repository",
        "repo",
    ],
    "files": [
        "file",
        "folder",
        "directory",
        "read",
        "write",
        "create file",
    ],
    "search": [
        "search",
        "look up",
        "find online",
        "google",
        "web search",
    ],
}


class DynamicToolRegistry:
    """Manages dynamic tool discovery from mcp-gateway."""

    def __init__(self, gateway_url: str, refresh_interval: int = 300):
        """Initialize the tool registry.

        Args:
            gateway_url: URL of the mcp-gateway instance
            refresh_interval: Seconds between automatic refreshes
        """
        self.gateway_url = gateway_url.rstrip("/")
        self.refresh_interval = refresh_interval
        self.tools: list[dict[str, Any]] = []
        self.tool_categories: dict[str, list[str]] = defaultdict(list)
        self.tool_map: dict[str, tuple[str, str]] = {}  # tool_name -> (server_id, original_name)
        self._refresh_task: asyncio.Task[None] | None = None
        self._last_refresh: float = 0

    async def start(self) -> None:
        """Start the periodic refresh task."""
        await self.refresh()
        self._refresh_task = asyncio.create_task(self._periodic_refresh())

    async def stop(self) -> None:
        """Stop the periodic refresh task."""
        if self._refresh_task:
            self._refresh_task.cancel()
            try:
                await self._refresh_task
            except asyncio.CancelledError:
                pass

    async def _periodic_refresh(self) -> None:
        """Periodically refresh tools from mcp-gateway."""
        while True:
            await asyncio.sleep(self.refresh_interval)
            try:
                await self.refresh()
            except Exception as e:
                logger.warning(f"Failed to refresh tools: {e}")

    async def refresh(self) -> int:
        """Fetch tools from mcp-gateway and categorize them.

        Returns:
            Number of tools discovered
        """
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(f"{self.gateway_url}/api/tools")
                resp.raise_for_status()
                raw = resp.json()
        except httpx.HTTPError as e:
            logger.error(f"Failed to fetch tools from mcp-gateway: {e}")
            raise

        self.tools = []
        self.tool_categories = defaultdict(list)
        self.tool_map = {}

        # API returns a flat list of tools with server_id field
        for tool in raw:
            server_id = tool.get("server_id", "unknown")
            original_name = tool["name"]
            tool_name = f"{server_id}__{original_name}"

            # Infer category from tool name patterns first, then server
            category = self._infer_category_from_name(original_name, server_id)

            self.tools.append(
                {
                    "name": tool_name,
                    "description": tool.get("description", ""),
                    "input_schema": tool.get("inputSchema", {}),
                    "category": category,
                    "server": server_id,
                }
            )
            self.tool_categories[category].append(tool_name)
            self.tool_map[tool_name] = (server_id, original_name)

        self._last_refresh = asyncio.get_event_loop().time()
        logger.info(f"Refreshed {len(self.tools)} tools from mcp-gateway")
        return len(self.tools)

    def _infer_category_from_name(self, tool_name: str, server_id: str) -> str:
        """Infer category from tool name patterns, falling back to server ID.

        Args:
            tool_name: The original tool name (e.g., 'search_contacts')
            server_id: The server ID (e.g., 'mcp-dav')

        Returns:
            The inferred category
        """
        tool_name_lower = tool_name.lower()

        # Check tool name patterns first
        for pattern, category in TOOL_NAME_CATEGORIES.items():
            if pattern in tool_name_lower:
                return category

        # Fall back to server-based category
        return SERVER_CATEGORIES.get(server_id, "other")

    def _infer_category(self, server_id: str) -> str:
        """Infer category from server ID."""
        return SERVER_CATEGORIES.get(server_id, "other")

    def get_tools_for_categories(self, categories: list[str]) -> list[dict[str, Any]]:
        """Return only tools matching the given categories.

        Args:
            categories: List of category names to filter by

        Returns:
            List of tool definitions for the specified categories
        """
        names: set[str] = set()
        for cat in categories:
            names.update(self.tool_categories.get(cat, []))
        return [t for t in self.tools if t["name"] in names]

    def get_all_tools(self) -> list[dict[str, Any]]:
        """Return all available tools."""
        return self.tools

    def get_categories(self) -> list[str]:
        """Return list of available categories."""
        return list(self.tool_categories.keys())

    def format_tools_for_claude(
        self, tools: list[dict[str, Any]] | None = None
    ) -> list[dict[str, Any]]:
        """Format tools for Claude API.

        Args:
            tools: List of tools to format, or None for all tools

        Returns:
            List of tool definitions in Claude's expected format
        """
        if tools is None:
            tools = self.tools

        return [
            {
                "name": t["name"],
                "description": t["description"],
                "input_schema": t["input_schema"],
            }
            for t in tools
        ]

    async def execute_tool(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """Execute a tool via mcp-gateway.

        Args:
            tool_name: The namespaced tool name (server__tool)
            arguments: The tool arguments

        Returns:
            The tool result
        """
        if tool_name not in self.tool_map:
            return {"error": f"Unknown tool: {tool_name}"}

        server_id, original_name = self.tool_map[tool_name]

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(
                    f"{self.gateway_url}/api/tools/{server_id}/{original_name}",
                    json=arguments,
                )
                resp.raise_for_status()
                return resp.json()
        except httpx.HTTPError as e:
            logger.error(f"Failed to execute tool {tool_name}: {e}")
            return {"error": f"Tool execution failed: {e}"}


def classify_intent_fast(message: str) -> list[str]:
    """Fast keyword-based intent classification.

    Args:
        message: The user message to classify

    Returns:
        List of detected categories, empty if no match
    """
    message_lower = message.lower()
    detected: list[str] = []

    for category, keywords in CATEGORY_KEYWORDS.items():
        if any(kw in message_lower for kw in keywords):
            detected.append(category)

    return detected
