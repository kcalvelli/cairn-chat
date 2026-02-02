"""Google Gemini API integration."""

import logging
from typing import Any

from google import genai
from google.genai import types

from ..media import UserMessage
from .base import LLMBackend, ProgressCallback
from .prompts import (
    get_default_system_prompt,
    get_progress_message,
    get_user_location_context,
)

logger = logging.getLogger(__name__)

# Model name
FLASH_MODEL = "gemini-2.0-flash"


class GeminiClient(LLMBackend):
    """Gemini API client for tool execution."""

    def __init__(
        self,
        api_key: str,
        system_prompt: str | None = None,
        max_context_messages: int = 10,
        user_config: dict | None = None,
    ):
        """Initialize the Gemini client.

        Args:
            api_key: Google Gemini API key
            system_prompt: Custom system prompt, or None for default
            max_context_messages: Maximum conversation history to maintain
            user_config: Per-user configuration (location, timezone)
        """
        self.client = genai.Client(api_key=api_key)
        self.base_system_prompt = system_prompt or get_default_system_prompt()
        self.max_context_messages = max_context_messages
        self.user_config = user_config or {}
        self.conversation_history: dict[str, list[types.Content]] = {}

    def _get_system_prompt(self, user_id: str) -> str:
        """Get system prompt with per-user location context."""
        location_context = get_user_location_context(user_id, self.user_config)
        if location_context:
            return self.base_system_prompt + "\n" + location_context
        return self.base_system_prompt

    def _get_history(self, user_id: str) -> list[types.Content]:
        """Get conversation history for a user."""
        if user_id not in self.conversation_history:
            self.conversation_history[user_id] = []
        return self.conversation_history[user_id]

    def _add_to_history(
        self, user_id: str, role: str, parts: list[types.Part]
    ) -> None:
        """Add a message to conversation history.

        Args:
            user_id: The user's ID
            role: Message role ("user" or "model")
            parts: List of content parts
        """
        history = self._get_history(user_id)
        history.append(types.Content(role=role, parts=parts))

        # Trim history if too long
        if len(history) > self.max_context_messages * 2:
            self.conversation_history[user_id] = history[-self.max_context_messages * 2 :]

    def clear_history(self, user_id: str) -> None:
        """Clear conversation history for a user."""
        self.conversation_history.pop(user_id, None)

    async def execute_with_tools(
        self,
        user_id: str,
        message: UserMessage,
        tools: list[dict[str, Any]],
        tool_executor: Any,
        progress_callback: ProgressCallback | None = None,
    ) -> str:
        """Execute a request using Gemini Flash with tools.

        Args:
            user_id: The user's ID for conversation tracking
            message: The user's message (text and optional media attachments)
            tools: List of available tools as Gemini FunctionDeclaration dicts
            tool_executor: Async callable that takes (tool_name, arguments) and returns result
            progress_callback: Optional async callback for progress updates

        Returns:
            The assistant's final response text
        """
        # Convert UserMessage to Gemini content parts
        gemini_parts = message.to_gemini_parts()

        # Add user message to history
        self._add_to_history(user_id, "user", gemini_parts)
        history = self._get_history(user_id)

        async def send_progress(phase: str) -> None:
            """Send a progress message if callback is available."""
            if progress_callback:
                try:
                    await progress_callback(get_progress_message(phase))
                except Exception as e:
                    logger.debug(f"Failed to send progress: {e}")

        try:
            system_prompt = self._get_system_prompt(user_id)

            # Build Gemini tool definition
            gemini_tools = types.Tool(function_declarations=tools) if tools else None

            config = types.GenerateContentConfig(
                system_instruction=system_prompt,
                tools=[gemini_tools] if gemini_tools else None,
                automatic_function_calling=types.AutomaticFunctionCallingConfig(
                    disable=True,
                ),
            )

            # Initial request
            response = self.client.models.generate_content(
                model=FLASH_MODEL,
                contents=history,
                config=config,
            )

            # Track tool iterations for multi-step progress
            tool_iteration = 0

            # Process function calls in a loop
            while response.function_calls:
                tool_iteration += 1
                function_calls = response.function_calls

                # Send appropriate progress message
                if tool_iteration == 1:
                    await send_progress("tool_start")
                elif tool_iteration == 2:
                    await send_progress("multi_step")
                elif tool_iteration > 2:
                    await send_progress("tool_working")

                # Add model response to history
                history.append(response.candidates[0].content)

                # Execute each function call and collect responses
                function_response_parts = []
                for fc in function_calls:
                    logger.info(f"Executing tool: {fc.name}")
                    result = await tool_executor(fc.name, dict(fc.args) if fc.args else {})
                    function_response_parts.append(
                        types.Part.from_function_response(
                            name=fc.name,
                            response={"result": result},
                        )
                    )

                # Add function responses to history
                history.append(types.Content(role="user", parts=function_response_parts))

                # Continue the conversation
                response = self.client.models.generate_content(
                    model=FLASH_MODEL,
                    contents=history,
                    config=config,
                )

            # Extract final text response
            final_response = response.text or ""

            # Add assistant response to history
            self._add_to_history(user_id, "model", [types.Part.from_text(text=final_response)])

            return final_response

        except Exception as e:
            logger.error(f"LLM execution failed: {e}")
            return f"I'm sorry, I encountered an error: {e}"

    async def simple_response(self, user_id: str, message: UserMessage) -> str:
        """Generate a simple response without tools.

        Args:
            user_id: The user's ID for conversation tracking
            message: The user's message (text and optional media attachments)

        Returns:
            The assistant's response text
        """
        gemini_parts = message.to_gemini_parts()
        self._add_to_history(user_id, "user", gemini_parts)
        history = self._get_history(user_id)

        try:
            system_prompt = self._get_system_prompt(user_id)

            config = types.GenerateContentConfig(
                system_instruction=system_prompt,
            )

            response = self.client.models.generate_content(
                model=FLASH_MODEL,
                contents=history,
                config=config,
            )

            final_response = response.text or ""
            self._add_to_history(user_id, "model", [types.Part.from_text(text=final_response)])
            return final_response

        except Exception as e:
            logger.error(f"Simple response failed: {e}")
            return f"I'm sorry, I encountered an error: {e}"
