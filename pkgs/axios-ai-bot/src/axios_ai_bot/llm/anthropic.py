"""Anthropic Claude API integration."""

import logging
from typing import Any

from anthropic import Anthropic

from .base import LLMBackend, ProgressCallback
from .prompts import get_default_system_prompt, get_progress_message

logger = logging.getLogger(__name__)

# Model names
HAIKU_MODEL = "claude-3-5-haiku-latest"
SONNET_MODEL = "claude-sonnet-4-20250514"


class AnthropicClient(LLMBackend):
    """Claude API client for tool execution."""

    def __init__(
        self,
        api_key: str,
        system_prompt: str | None = None,
        max_context_messages: int = 10,
    ):
        """Initialize the Anthropic client.

        Args:
            api_key: Anthropic API key
            system_prompt: Custom system prompt, or None for default
            max_context_messages: Maximum conversation history to maintain
        """
        self.client = Anthropic(api_key=api_key)
        self.system_prompt = system_prompt or get_default_system_prompt()
        self.max_context_messages = max_context_messages
        self.conversation_history: dict[str, list[dict[str, Any]]] = {}

    def _get_history(self, user_id: str) -> list[dict[str, Any]]:
        """Get conversation history for a user."""
        if user_id not in self.conversation_history:
            self.conversation_history[user_id] = []
        return self.conversation_history[user_id]

    def _add_to_history(self, user_id: str, role: str, content: str) -> None:
        """Add a message to conversation history."""
        history = self._get_history(user_id)
        history.append({"role": role, "content": content})

        # Trim history if too long
        if len(history) > self.max_context_messages * 2:
            # Keep the last N exchanges
            self.conversation_history[user_id] = history[-self.max_context_messages * 2 :]

    def clear_history(self, user_id: str) -> None:
        """Clear conversation history for a user."""
        self.conversation_history.pop(user_id, None)

    async def execute_with_tools(
        self,
        user_id: str,
        message: str,
        tools: list[dict[str, Any]],
        tool_executor: Any,  # Callable for executing tools
        progress_callback: ProgressCallback | None = None,
    ) -> str:
        """Execute a request using Sonnet with tools.

        Args:
            user_id: The user's ID for conversation tracking
            message: The user's message
            tools: List of available tools in Claude format
            tool_executor: Async callable that takes (tool_name, arguments) and returns result
            progress_callback: Optional async callback for progress updates

        Returns:
            The assistant's final response text
        """
        # Add user message to history
        self._add_to_history(user_id, "user", message)
        history = self._get_history(user_id)

        async def send_progress(phase: str) -> None:
            """Send a progress message if callback is available."""
            if progress_callback:
                try:
                    await progress_callback(get_progress_message(phase))
                except Exception as e:
                    logger.debug(f"Failed to send progress: {e}")

        try:
            # Initial request
            response = self.client.messages.create(
                model=SONNET_MODEL,
                max_tokens=4096,
                system=self.system_prompt,
                messages=history,
                tools=tools if tools else None,
            )

            # Track tool iterations for multi-step progress
            tool_iteration = 0

            # Process tool calls in a loop
            while response.stop_reason == "tool_use":
                tool_iteration += 1

                # Find all tool use blocks
                tool_uses = [block for block in response.content if block.type == "tool_use"]

                # Send appropriate progress message
                if tool_iteration == 1:
                    await send_progress("tool_start")
                elif tool_iteration == 2:
                    await send_progress("multi_step")
                elif tool_iteration > 2:
                    await send_progress("tool_working")

                # Execute each tool
                tool_results = []
                for tool_use in tool_uses:
                    logger.info(f"Executing tool: {tool_use.name}")
                    result = await tool_executor(tool_use.name, tool_use.input)
                    tool_results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": tool_use.id,
                            "content": str(result),
                        }
                    )

                # Add assistant response and tool results to history
                history.append({"role": "assistant", "content": response.content})
                history.append({"role": "user", "content": tool_results})

                # Continue the conversation
                response = self.client.messages.create(
                    model=SONNET_MODEL,
                    max_tokens=4096,
                    system=self.system_prompt,
                    messages=history,
                    tools=tools if tools else None,
                )

            # Extract final text response
            text_blocks = [block.text for block in response.content if hasattr(block, "text")]
            final_response = "\n".join(text_blocks)

            # Add assistant response to history
            self._add_to_history(user_id, "assistant", final_response)

            return final_response

        except Exception as e:
            logger.error(f"LLM execution failed: {e}")
            return f"I'm sorry, I encountered an error: {e}"

    async def simple_response(self, user_id: str, message: str) -> str:
        """Generate a simple response without tools (for general conversation).

        Args:
            user_id: The user's ID for conversation tracking
            message: The user's message

        Returns:
            The assistant's response text
        """
        self._add_to_history(user_id, "user", message)
        history = self._get_history(user_id)

        try:
            response = self.client.messages.create(
                model=HAIKU_MODEL,  # Use Haiku for simple conversation (cheaper)
                max_tokens=1024,
                system=self.system_prompt,
                messages=history,
            )

            text_blocks = [block.text for block in response.content if hasattr(block, "text")]
            final_response = "\n".join(text_blocks)

            self._add_to_history(user_id, "assistant", final_response)
            return final_response

        except Exception as e:
            logger.error(f"Simple response failed: {e}")
            return f"I'm sorry, I encountered an error: {e}"
