"""Dynamic tool registry that fetches tools from mcp-gateway."""

import asyncio
import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)


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
        self.tool_map: dict[str, tuple[str, str]] = {}  # tool_name -> (server_id, original_name)
        self._refresh_task: asyncio.Task[None] | None = None
        self._last_refresh: float = 0

    async def start(self) -> None:
        """Start the periodic refresh task."""
        try:
            await self.refresh()
        except Exception as e:
            logger.warning(f"Initial tool refresh failed: {e}")
            logger.info("Periodic refresh will retry automatically")
        # Always start the periodic refresh task, even if initial refresh failed
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
        """Fetch tools from mcp-gateway.

        Returns:
            Number of tools discovered
        """
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                # First get the tool list
                resp = await client.get(f"{self.gateway_url}/api/tools")
                resp.raise_for_status()
                tool_list = resp.json()

                # Fetch full schemas in parallel
                async def fetch_schema(tool: dict) -> dict:
                    server_id = tool.get("server_id", "unknown")
                    name = tool["name"]
                    try:
                        schema_resp = await client.get(
                            f"{self.gateway_url}/api/tools/{server_id}/{name}"
                        )
                        if schema_resp.status_code == 200:
                            return schema_resp.json()
                    except Exception as e:
                        logger.debug(f"Failed to fetch schema for {server_id}/{name}: {e}")
                    return tool  # Return original if schema fetch fails

                # Fetch all schemas in parallel
                tools_with_schemas = await asyncio.gather(
                    *[fetch_schema(t) for t in tool_list],
                    return_exceptions=True
                )

        except httpx.HTTPError as e:
            logger.error(f"Failed to fetch tools from mcp-gateway: {e}")
            raise

        self.tools = []
        self.tool_map = {}

        # Process tools with their schemas
        for i, tool in enumerate(tools_with_schemas):
            if isinstance(tool, Exception):
                tool = tool_list[i]  # Fallback to original

            server_id = tool.get("server_id", tool_list[i].get("server_id", "unknown"))
            original_name = tool.get("name", tool_list[i]["name"])
            # Sanitize tool name for Claude API (only allows [a-zA-Z0-9_-])
            safe_name = original_name.replace(".", "_").replace(" ", "_")
            tool_name = f"{server_id}__{safe_name}"

            # Get input schema, ensuring it has required 'type' field for Claude
            input_schema = tool.get("input_schema") or tool.get("inputSchema") or {}
            if not input_schema or "type" not in input_schema:
                # Default to empty object schema if not provided
                input_schema = {"type": "object", "properties": {}}

            self.tools.append(
                {
                    "name": tool_name,
                    "description": tool.get("description", ""),
                    "input_schema": input_schema,
                    "server": server_id,
                }
            )
            self.tool_map[tool_name] = (server_id, original_name)

        self._last_refresh = asyncio.get_event_loop().time()
        logger.info(f"Refreshed {len(self.tools)} tools from mcp-gateway")
        return len(self.tools)

    def get_all_tools(self) -> list[dict[str, Any]]:
        """Return all available tools."""
        return self.tools

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
