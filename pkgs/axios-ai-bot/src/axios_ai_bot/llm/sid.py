"""Sid (GenX64) LLM backend via openclaw-gateway OpenAI-compatible API."""

import logging
from typing import Any

import httpx

from ..media import UserMessage
from .base import LLMBackend, ProgressCallback

logger = logging.getLogger(__name__)

# Default timeout for API calls (Sid can be slow with complex tool use)
DEFAULT_TIMEOUT = 300.0


class SidClient(LLMBackend):
    """Sid LLM client using openclaw-gateway's OpenAI-compatible HTTP API.

    Sid is the GenX64 AI agent with full persona, workspace context, and tool access.
    This client connects to openclaw-gateway which handles:
    - Conversation history (via user field for session continuity)
    - Tool execution (mcp-gateway integration)
    - Persona and workspace context (SOUL.md, IDENTITY.md, etc.)
    """

    def __init__(
        self,
        gateway_url: str = "http://127.0.0.1:18789",
        auth_token: str | None = None,
        agent_id: str = "main",
        timeout: float = DEFAULT_TIMEOUT,
    ):
        """Initialize the Sid client.

        Args:
            gateway_url: openclaw-gateway URL (default: http://127.0.0.1:18789)
            auth_token: Gateway authentication token
            agent_id: OpenClaw agent ID (default: "main")
            timeout: Request timeout in seconds
        """
        self.gateway_url = gateway_url.rstrip("/")
        self.auth_token = auth_token
        self.agent_id = agent_id
        self.timeout = timeout
        self._client = httpx.AsyncClient(timeout=timeout)

    async def _call_api(
        self,
        user_id: str,
        message: str,
        stream: bool = False,
    ) -> str:
        """Make API call to openclaw-gateway.

        Args:
            user_id: User identifier for session continuity
            message: The message to send
            stream: Whether to use streaming (not implemented yet)

        Returns:
            The assistant's response text
        """
        url = f"{self.gateway_url}/v1/chat/completions"

        headers = {"Content-Type": "application/json"}
        if self.auth_token:
            headers["Authorization"] = f"Bearer {self.auth_token}"

        # Use user field for session continuity - openclaw derives stable session key
        payload = {
            "model": f"openclaw:{self.agent_id}",
            "user": user_id,
            "messages": [{"role": "user", "content": message}],
            "stream": stream,
        }

        try:
            response = await self._client.post(url, json=payload, headers=headers)
            response.raise_for_status()

            data = response.json()

            # Extract response text from OpenAI format
            if "choices" in data and len(data["choices"]) > 0:
                choice = data["choices"][0]
                if "message" in choice and "content" in choice["message"]:
                    return choice["message"]["content"] or ""

            logger.warning(f"Unexpected response format: {data}")
            return ""

        except httpx.TimeoutException:
            logger.error(f"Sid API timeout after {self.timeout}s")
            return "I'm sorry, the request timed out. Please try again."
        except httpx.HTTPStatusError as e:
            logger.error(f"Sid API error: {e.response.status_code} - {e.response.text}")
            return f"I'm sorry, I encountered an error: {e.response.status_code}"
        except Exception as e:
            logger.error(f"Sid API call failed: {e}")
            return f"I'm sorry, I encountered an error: {e}"

    async def execute_with_tools(
        self,
        user_id: str,
        message: UserMessage,
        tools: list[dict[str, Any]],
        tool_executor: Any,
        progress_callback: ProgressCallback | None = None,
    ) -> str:
        """Execute a request with tool access.

        Note: Sid handles tools internally via openclaw-gateway's mcp-gateway integration.
        The tools and tool_executor parameters are ignored - Sid has its own tool set.

        Args:
            user_id: Unique identifier for the user (XMPP JID)
            message: The user's message
            tools: Ignored - Sid uses its own tools
            tool_executor: Ignored - Sid executes tools internally
            progress_callback: Optional async callback for progress updates

        Returns:
            The assistant's final response text
        """
        # Send progress indicator since Sid can take a while with tools
        if progress_callback:
            try:
                await progress_callback("Thinking...")
            except Exception as e:
                logger.debug(f"Failed to send progress: {e}")

        # Extract text from UserMessage
        # Note: Sid doesn't support media attachments via this API yet
        text = message.text
        if message.attachments:
            logger.warning("Sid API does not support media attachments - text only")

        return await self._call_api(user_id, text)

    async def simple_response(self, user_id: str, message: UserMessage) -> str:
        """Generate a response without tools.

        Note: Sid always has access to its tools - this is the same as execute_with_tools.

        Args:
            user_id: Unique identifier for the user
            message: The user's message

        Returns:
            The assistant's response text
        """
        text = message.text
        if message.attachments:
            logger.warning("Sid API does not support media attachments - text only")

        return await self._call_api(user_id, text)

    def clear_history(self, user_id: str) -> None:
        """Clear conversation history for a user.

        Note: openclaw-gateway manages sessions internally based on the user field.
        This is a no-op - to truly clear history, the session would need to be
        deleted via the gateway's session management API.
        """
        logger.info(f"clear_history called for {user_id} - Sid manages sessions internally")

    async def close(self) -> None:
        """Close the HTTP client."""
        await self._client.aclose()
