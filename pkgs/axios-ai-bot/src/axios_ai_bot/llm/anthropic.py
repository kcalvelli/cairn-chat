"""Anthropic Claude API integration."""

import logging
from typing import Any

from anthropic import Anthropic

from ..domains import DomainRegistry
from .base import LLMBackend, ProgressCallback
from .prompts import (
    build_router_prompt,
    format_domain_list,
    get_default_system_prompt,
    get_progress_message,
    get_user_location_context,
)

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
        user_config: dict | None = None,
    ):
        """Initialize the Anthropic client.

        Args:
            api_key: Anthropic API key
            system_prompt: Custom system prompt, or None for default
            max_context_messages: Maximum conversation history to maintain
            user_config: Per-user configuration (location, timezone)
        """
        self.client = Anthropic(api_key=api_key)
        self.base_system_prompt = system_prompt or get_default_system_prompt()
        self.max_context_messages = max_context_messages
        self.user_config = user_config or {}
        self.conversation_history: dict[str, list[dict[str, Any]]] = {}

    def _get_system_prompt(self, user_id: str) -> str:
        """Get system prompt with per-user location context.

        Args:
            user_id: The user's JID

        Returns:
            System prompt with location context appended if available
        """
        location_context = get_user_location_context(user_id, self.user_config)
        if location_context:
            return self.base_system_prompt + "\n" + location_context
        return self.base_system_prompt

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
            # Get per-user system prompt with location context
            system_prompt = self._get_system_prompt(user_id)

            # Initial request
            response = self.client.messages.create(
                model=SONNET_MODEL,
                max_tokens=4096,
                system=system_prompt,
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
                    system=system_prompt,
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
            # Get per-user system prompt with location context
            system_prompt = self._get_system_prompt(user_id)

            response = self.client.messages.create(
                model=HAIKU_MODEL,  # Use Haiku for simple conversation (cheaper)
                max_tokens=1024,
                system=system_prompt,
                messages=history,
            )

            text_blocks = [block.text for block in response.content if hasattr(block, "text")]
            final_response = "\n".join(text_blocks)

            self._add_to_history(user_id, "assistant", final_response)
            return final_response

        except Exception as e:
            logger.error(f"Simple response failed: {e}")
            return f"I'm sorry, I encountered an error: {e}"

    async def classify_intent(
        self,
        message: str,
        registry: DomainRegistry,
    ) -> list[str]:
        """Classify user message into domains using Haiku (fast, cheap).

        Args:
            message: The user's message to classify
            registry: Domain registry with available domains

        Returns:
            List of domain names. Falls back to ["general"] on error.
        """
        # Build router prompt
        sorted_domains = registry.get_sorted_domains()
        domain_list = format_domain_list(sorted_domains)
        prompt = build_router_prompt(message, domain_list)

        try:
            response = self.client.messages.create(
                model=HAIKU_MODEL,  # Use Haiku for fast, cheap classification
                max_tokens=50,  # Domain names only
                system="You are a request classifier. Output only domain names, comma-separated. No explanation.",
                messages=[{"role": "user", "content": prompt}],
            )

            # Extract text response
            text_blocks = [block.text for block in response.content if hasattr(block, "text")]
            raw_response = "".join(text_blocks).strip()
            logger.info(f"Router classification raw: {raw_response}")

            # Parse domains
            domains = [d.strip().lower() for d in raw_response.split(",")]
            valid_domains = [d for d in domains if d in registry.domains]

            if valid_domains:
                logger.info(f"Classified domains: {valid_domains}")
                return valid_domains

            logger.warning(f"No valid domains in response: {raw_response}")
            return ["general"]

        except Exception as e:
            logger.error(f"Intent classification failed: {e}")
            return ["general"]

    async def execute_with_routing(
        self,
        user_id: str,
        message: str,
        all_tools: list[dict[str, Any]],
        tool_executor: Any,
        registry: DomainRegistry,
        progress_callback: ProgressCallback | None = None,
    ) -> str:
        """Execute with domain-based routing for efficiency.

        Uses Haiku for classification, then Sonnet with filtered tools.

        Args:
            user_id: The user's ID for conversation tracking
            message: The user's message
            all_tools: Full list of available tools
            tool_executor: Async callable for tool execution
            registry: Domain registry for routing
            progress_callback: Optional async callback for progress updates

        Returns:
            The assistant's final response text
        """
        # Step 1: Classify intent with Haiku
        domains = await self.classify_intent(message, registry)
        logger.info(f"Routed to domains: {domains}")

        # Step 2: Check if this is general (no tools needed)
        if "general" in domains and len(domains) == 1:
            logger.info("General domain - using simple response (no tools)")
            return await self.simple_response(user_id, message)

        # Step 3: Filter tools by domains
        filtered_tools = registry.get_tools_for_domains(domains, all_tools)
        logger.info(f"Filtered to {len(filtered_tools)} tools (from {len(all_tools)})")

        if not filtered_tools:
            logger.info("No tools after filtering - using simple response")
            return await self.simple_response(user_id, message)

        # Step 4: Execute with filtered tools using Sonnet
        return await self.execute_with_tools(
            user_id=user_id,
            message=message,
            tools=filtered_tools,
            tool_executor=tool_executor,
            progress_callback=progress_callback,
        )
