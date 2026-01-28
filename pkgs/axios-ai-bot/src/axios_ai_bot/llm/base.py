"""Abstract base class for LLM backends."""

from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable
from typing import Any

# Type alias for progress callback
ProgressCallback = Callable[[str], Awaitable[None]]


class LLMBackend(ABC):
    """Abstract base class for LLM backends.

    All LLM implementations (Anthropic, Ollama, etc.) must inherit from this
    class and implement the required methods.
    """

    @abstractmethod
    async def execute_with_tools(
        self,
        user_id: str,
        message: str,
        tools: list[dict[str, Any]],
        tool_executor: Callable[[str, dict[str, Any]], Awaitable[dict[str, Any]]],
        progress_callback: ProgressCallback | None = None,
    ) -> str:
        """Execute a request with tool access.

        Args:
            user_id: Unique identifier for the user (e.g., JID)
            message: The user's message
            tools: List of available tools in the backend's expected format
            tool_executor: Async callable that takes (tool_name, arguments) and returns result
            progress_callback: Optional async callback for progress updates

        Returns:
            The assistant's final response text
        """
        pass

    @abstractmethod
    async def simple_response(self, user_id: str, message: str) -> str:
        """Generate a response without tools.

        Args:
            user_id: Unique identifier for the user
            message: The user's message

        Returns:
            The assistant's response text
        """
        pass

    @abstractmethod
    def clear_history(self, user_id: str) -> None:
        """Clear conversation history for a user.

        Args:
            user_id: Unique identifier for the user
        """
        pass
