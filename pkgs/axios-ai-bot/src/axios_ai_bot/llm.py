"""Claude API integration with Haiku routing and Sonnet execution."""

import logging
import random
from collections.abc import Awaitable, Callable
from typing import Any

from anthropic import Anthropic

logger = logging.getLogger(__name__)

# Model names
HAIKU_MODEL = "claude-3-5-haiku-latest"
SONNET_MODEL = "claude-sonnet-4-20250514"

# Type alias for progress callback
ProgressCallback = Callable[[str], Awaitable[None]]

# Witty progress messages organized by phase
PROGRESS_MESSAGES = {
    "thinking": [
        "🤔 Let me think about this...",
        "🧠 Processing your request...",
        "💭 Hmm, interesting question...",
        "🔍 Looking into it...",
        "⚡ On it!",
    ],
    "tool_start": [
        "🔧 Firing up the tools...",
        "🛠️ Rolling up my sleeves...",
        "⚙️ Getting to work...",
        "🎯 Found what I need, executing...",
        "🚀 Launching operation...",
    ],
    "tool_working": [
        "⏳ Still working on it...",
        "🔄 Making progress...",
        "📊 Crunching the data...",
        "🎪 Juggling some tasks here...",
        "🏃 Almost there...",
    ],
    "multi_step": [
        "📋 This needs a few steps, hang tight...",
        "🎯 Multi-step operation in progress...",
        "🔗 Chaining some actions together...",
        "🎭 Performing a little orchestration...",
    ],
    "slow_response": [
        "☕ Claude's thinking hard about this one...",
        "🐢 Taking a bit longer than usual...",
        "🌊 Navigating some heavy traffic...",
        "⏱️ Still here, just being thorough!",
        "🧘 Patience, grasshopper...",
    ],
}

# Default system prompts
DEFAULT_SYSTEM_PROMPT = """You are Axios AI, a helpful family assistant. You can help with:
- Email: Read, search, compose, and send emails
- Calendar: View and create events, check availability
- Contacts: Look up contact information
- General questions and conversation

Be concise and friendly. When using tools, explain what you're doing briefly.
If a task requires multiple steps, complete them without asking for confirmation unless critical."""

def get_progress_message(phase: str) -> str:
    """Get a random progress message for the given phase."""
    messages = PROGRESS_MESSAGES.get(phase, PROGRESS_MESSAGES["thinking"])
    return random.choice(messages)


CLASSIFIER_PROMPT = """Classify the user's intent into one or more categories.

Categories:
- email: Anything about reading, sending, or managing emails
- calendar: Events, schedules, meetings, appointments
- contacts: Looking up people, phone numbers, addresses
- code: Git operations, repositories, pull requests
- files: Reading or writing files
- search: Web searches, looking things up online
- general: Greetings, thanks, general questions, or unclear intent

Respond with ONLY the category names, comma-separated. If multiple apply, list all.
If it's just conversation (hi, thanks, etc.), respond with: general

Example inputs and outputs:
"What's on my calendar tomorrow?" -> calendar
"Send an email to John about the meeting" -> email,calendar
"Hi there!" -> general
"Search for the best restaurants nearby" -> search
"""


class LLMClient:
    """Claude API client with Haiku routing and Sonnet execution."""

    def __init__(
        self,
        api_key: str,
        system_prompt: str | None = None,
        max_context_messages: int = 10,
    ):
        """Initialize the LLM client.

        Args:
            api_key: Anthropic API key
            system_prompt: Custom system prompt, or None for default
            max_context_messages: Maximum conversation history to maintain
        """
        self.client = Anthropic(api_key=api_key)
        self.system_prompt = system_prompt or DEFAULT_SYSTEM_PROMPT
        self.max_context_messages = max_context_messages
        self.conversation_history: dict[str, list[dict[str, Any]]] = {}

    def _get_history(self, user_jid: str) -> list[dict[str, Any]]:
        """Get conversation history for a user."""
        if user_jid not in self.conversation_history:
            self.conversation_history[user_jid] = []
        return self.conversation_history[user_jid]

    def _add_to_history(self, user_jid: str, role: str, content: str) -> None:
        """Add a message to conversation history."""
        history = self._get_history(user_jid)
        history.append({"role": role, "content": content})

        # Trim history if too long
        if len(history) > self.max_context_messages * 2:
            # Keep the last N exchanges
            self.conversation_history[user_jid] = history[-self.max_context_messages * 2 :]

    def clear_history(self, user_jid: str) -> None:
        """Clear conversation history for a user."""
        self.conversation_history.pop(user_jid, None)

    async def classify_intent(self, message: str) -> list[str]:
        """Classify user intent using Haiku (fast, cheap).

        Args:
            message: The user message to classify

        Returns:
            List of detected categories
        """
        try:
            response = self.client.messages.create(
                model=HAIKU_MODEL,
                max_tokens=50,
                system=CLASSIFIER_PROMPT,
                messages=[{"role": "user", "content": message}],
            )

            # Parse the response
            result_text = response.content[0].text.strip().lower()
            categories = [c.strip() for c in result_text.split(",") if c.strip()]

            logger.debug(f"Intent classification: '{message}' -> {categories}")
            return categories

        except Exception as e:
            logger.error(f"Intent classification failed: {e}")
            return ["general"]

    async def execute_with_tools(
        self,
        user_jid: str,
        message: str,
        tools: list[dict[str, Any]],
        tool_executor: Any,  # Callable for executing tools
        progress_callback: ProgressCallback | None = None,
    ) -> str:
        """Execute a request using Sonnet with tools.

        Args:
            user_jid: The user's JID for conversation tracking
            message: The user's message
            tools: List of available tools in Claude format
            tool_executor: Async callable that takes (tool_name, arguments) and returns result
            progress_callback: Optional async callback for progress updates

        Returns:
            The assistant's final response text
        """
        # Add user message to history
        self._add_to_history(user_jid, "user", message)
        history = self._get_history(user_jid)

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
            self._add_to_history(user_jid, "assistant", final_response)

            return final_response

        except Exception as e:
            logger.error(f"LLM execution failed: {e}")
            return f"I'm sorry, I encountered an error: {e}"

    async def simple_response(self, user_jid: str, message: str) -> str:
        """Generate a simple response without tools (for general conversation).

        Args:
            user_jid: The user's JID for conversation tracking
            message: The user's message

        Returns:
            The assistant's response text
        """
        self._add_to_history(user_jid, "user", message)
        history = self._get_history(user_jid)

        try:
            response = self.client.messages.create(
                model=HAIKU_MODEL,  # Use Haiku for simple conversation (cheaper)
                max_tokens=1024,
                system=self.system_prompt,
                messages=history,
            )

            text_blocks = [block.text for block in response.content if hasattr(block, "text")]
            final_response = "\n".join(text_blocks)

            self._add_to_history(user_jid, "assistant", final_response)
            return final_response

        except Exception as e:
            logger.error(f"Simple response failed: {e}")
            return f"I'm sorry, I encountered an error: {e}"
