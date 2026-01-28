"""Ollama LLM backend using native tool calling."""

import json
import logging
import re
from typing import Any

import httpx

from ..domains import DomainRegistry
from .base import LLMBackend, ProgressCallback
from .prompts import (
    build_router_prompt,
    format_domain_list,
    get_default_system_prompt,
    get_ollama_system_prompt,
    get_progress_message,
    get_user_location_context,
)

logger = logging.getLogger(__name__)

# Regex pattern to extract tool calls from model output
TOOL_CALL_PATTERN = re.compile(
    r"<tool_call>\s*(\{.*?\})\s*</tool_call>",
    re.DOTALL,
)

# Maximum retries for tool call validation failures
MAX_TOOL_RETRIES = 3

# Maximum size for tool results before truncation
MAX_TOOL_RESULT_SIZE = 12000  # ~12KB to allow for more content


def extract_mcp_content(result: dict[str, Any]) -> tuple[str, int | None]:
    """Extract actual content from MCP gateway response wrapper.

    MCP responses have format: {"success": true, "result": [{"type": "text", "text": "..."}]}
    This extracts just the text content to save context space.

    Args:
        result: The raw MCP gateway response

    Returns:
        Tuple of (extracted_content, total_item_count or None)
    """
    if not isinstance(result, dict):
        return json.dumps(result), None

    # Check for MCP wrapper format
    if result.get("success") and "result" in result:
        mcp_result = result["result"]
        if isinstance(mcp_result, list) and len(mcp_result) > 0:
            first_item = mcp_result[0]
            if isinstance(first_item, dict) and first_item.get("type") == "text":
                text_content = first_item.get("text", "")
                # Try to count items if it's a JSON array
                try:
                    parsed = json.loads(text_content)
                    if isinstance(parsed, list):
                        return text_content, len(parsed)
                except (json.JSONDecodeError, TypeError):
                    pass
                return text_content, None

    # Not MCP format, return as-is
    return json.dumps(result), None


def truncate_result(content: str, max_size: int, total_items: int | None = None) -> tuple[str, bool]:
    """Truncate content intelligently, preserving JSON structure where possible.

    Args:
        content: The content to potentially truncate
        max_size: Maximum allowed size in bytes
        total_items: Total number of items if known (for informative message)

    Returns:
        Tuple of (content, was_truncated)
    """
    if len(content) <= max_size:
        return content, False

    # Try to truncate at a JSON array boundary for cleaner results
    truncated = content[:max_size]

    # Count how many complete items we have
    items_shown = truncated.count('"uid"')  # Rough heuristic for contacts
    if items_shown == 0:
        items_shown = truncated.count('"id"')  # Try generic id field

    # Build informative truncation message
    if total_items and items_shown > 0:
        msg = f"\n\n[TRUNCATED: Showing approximately {items_shown} of {total_items} total items. Ask user to be more specific or search for particular items.]"
    else:
        msg = f"\n\n[TRUNCATED: Result too large ({len(content)} bytes). Only partial data shown. Ask user to search for specific items instead of listing all.]"

    return truncated + msg, True


def parse_tool_calls(response: str) -> list[dict[str, Any]]:
    """Extract and validate tool calls from model response.

    Args:
        response: The model's response text

    Returns:
        List of parsed tool call dictionaries with 'name' and 'arguments' keys
    """
    calls = []
    for match in TOOL_CALL_PATTERN.finditer(response):
        try:
            call = json.loads(match.group(1))
            if "name" in call and "arguments" in call:
                calls.append(call)
            elif "name" in call:
                # Some models omit arguments for no-arg functions
                call["arguments"] = {}
                calls.append(call)
        except json.JSONDecodeError as e:
            logger.warning(f"Malformed tool call JSON: {e}")
            continue
    return calls


def validate_tool_call(
    call: dict[str, Any],
    registered_tools: set[str],
    tool_schemas: dict[str, dict[str, Any]],
) -> tuple[bool, str]:
    """Validate a tool call against registered tools and schemas.

    Args:
        call: The tool call dictionary with 'name' and 'arguments'
        registered_tools: Set of valid tool names
        tool_schemas: Dict mapping tool names to their input schemas

    Returns:
        Tuple of (is_valid, error_message)
    """
    name = call.get("name", "")

    # Check tool exists
    if name not in registered_tools:
        return False, f"Unknown tool: {name}"

    # Validate arguments against schema
    schema = tool_schemas.get(name, {})
    required = schema.get("required", [])
    properties = schema.get("properties", {})
    arguments = call.get("arguments", {})

    # Check required arguments
    for req in required:
        if req not in arguments:
            return False, f"Missing required argument: {req}"

    # Check no extra arguments (only if properties are defined)
    if properties:
        for arg in arguments:
            if arg not in properties:
                return False, f"Unknown argument: {arg}"

    return True, ""


def format_tools_for_ollama(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Convert tools to Ollama's expected format.

    Args:
        tools: List of tools in internal format

    Returns:
        List of tools in Ollama API format
    """
    return [
        {
            "type": "function",
            "function": {
                "name": t["name"],
                "description": t["description"],
                "parameters": t["input_schema"],
            },
        }
        for t in tools
    ]


class OllamaClient(LLMBackend):
    """Ollama-based LLM client using native tool calling."""

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        model: str = "qwen3:14b-q4_K_M",
        system_prompt: str | None = None,
        max_context_messages: int = 10,
        temperature: float = 0.2,
        enable_thinking: bool = False,
        timeout: float = 120.0,
        user_config: dict | None = None,
    ):
        """Initialize the Ollama client.

        Args:
            base_url: Ollama server URL
            model: Model name to use
            system_prompt: Custom system prompt, or None for default
            max_context_messages: Maximum conversation history to maintain
            temperature: Sampling temperature (lower = more deterministic)
            enable_thinking: Whether to enable thinking mode
            timeout: Request timeout in seconds
            user_config: Per-user configuration (location, timezone)
        """
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.base_system_prompt = system_prompt
        self.max_context_messages = max_context_messages
        self.temperature = temperature
        self.enable_thinking = enable_thinking
        self.timeout = timeout
        self.user_config = user_config or {}
        self.conversation_history: dict[str, list[dict[str, Any]]] = {}

    def _get_system_prompt(self, user_id: str) -> str:
        """Get system prompt with per-user location context.

        Args:
            user_id: The user's JID

        Returns:
            System prompt with location context appended if available
        """
        base_prompt = self.base_system_prompt or get_ollama_system_prompt()
        location_context = get_user_location_context(user_id, self.user_config)
        if location_context:
            return base_prompt + "\n" + location_context
        return base_prompt

    def _get_history(self, user_id: str) -> list[dict[str, Any]]:
        """Get conversation history for a user."""
        if user_id not in self.conversation_history:
            self.conversation_history[user_id] = []
        return self.conversation_history[user_id]

    def _add_to_history(
        self, user_id: str, role: str, content: str | list[dict[str, Any]]
    ) -> None:
        """Add a message to conversation history."""
        history = self._get_history(user_id)
        history.append({"role": role, "content": content})

        # Trim history if too long
        if len(history) > self.max_context_messages * 2:
            self.conversation_history[user_id] = history[-self.max_context_messages * 2 :]

    def clear_history(self, user_id: str) -> None:
        """Clear conversation history for a user."""
        self.conversation_history.pop(user_id, None)

    async def warm_up(self) -> bool:
        """Pre-load the model into memory to avoid cold-start delays.

        Returns:
            True if warm-up succeeded, False otherwise.
        """
        logger.info(f"Warming up model {self.model}...")
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                # Send minimal request to load model into memory
                response = await client.post(
                    f"{self.base_url}/api/chat",
                    json={
                        "model": self.model,
                        "messages": [{"role": "user", "content": "hi"}],
                        "stream": False,
                        "options": {"num_predict": 1},  # Generate minimal tokens
                    },
                )
                if response.status_code == 200:
                    logger.info(f"Model {self.model} warmed up successfully")
                    return True
                else:
                    logger.warning(f"Model warm-up returned status {response.status_code}")
                    return False
        except Exception as e:
            logger.warning(f"Model warm-up failed: {e}")
            return False

    async def _chat(
        self,
        messages: list[dict[str, Any]],
        system_prompt: str,
        tools: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Send a chat request to Ollama.

        Args:
            messages: Conversation messages
            system_prompt: System prompt to use
            tools: Optional tools for native tool calling

        Returns:
            Ollama API response
        """
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            # Build messages with system prompt
            full_messages = [{"role": "system", "content": system_prompt}] + messages

            payload: dict[str, Any] = {
                "model": self.model,
                "messages": full_messages,
                "stream": False,
                "options": {
                    "temperature": self.temperature,
                    "num_ctx": 16384,  # Enough for tools (~5K tokens) while keeping more layers on GPU
                },
            }

            # Add native tool calling if tools provided
            if tools:
                payload["tools"] = tools
                payload["think"] = False  # Disable thinking for tool calls
            else:
                payload["think"] = self.enable_thinking

            response = await client.post(
                f"{self.base_url}/api/chat",
                json=payload,
            )
            response.raise_for_status()
            return response.json()

    async def execute_with_tools(
        self,
        user_id: str,
        message: str,
        tools: list[dict[str, Any]],
        tool_executor: Any,
        progress_callback: ProgressCallback | None = None,
    ) -> str:
        """Execute a request with tool access using Hermes-style prompting.

        Args:
            user_id: The user's ID for conversation tracking
            message: The user's message
            tools: List of available tools
            tool_executor: Async callable that takes (tool_name, arguments) and returns result
            progress_callback: Optional async callback for progress updates

        Returns:
            The assistant's final response text
        """
        # Build tool registry for validation
        registered_tools = {t["name"] for t in tools}
        tool_schemas = {t["name"]: t["input_schema"] for t in tools}

        # Format tools for Ollama's native tool calling
        ollama_tools = format_tools_for_ollama(tools)

        # Use simple system prompt (not Hermes-style) - Ollama handles tool format
        system_prompt = get_ollama_system_prompt(self.base_system_prompt)

        # Add user message to history
        self._add_to_history(user_id, "user", message)
        history = self._get_history(user_id)

        # Build messages for API (excluding system prompt, handled separately)
        messages = [
            {"role": m["role"], "content": m["content"]}
            for m in history
            if m["role"] != "system"
        ]

        async def send_progress(phase: str) -> None:
            """Send a progress message if callback is available."""
            if progress_callback:
                try:
                    await progress_callback(get_progress_message(phase))
                except Exception as e:
                    logger.debug(f"Failed to send progress: {e}")

        try:
            tool_iteration = 0
            retry_count = 0

            while True:
                # Call Ollama with native tool calling
                response = await self._chat(messages, system_prompt, tools=ollama_tools)
                response_text = response.get("message", {}).get("content", "")

                logger.info(f"Ollama response keys: {list(response.keys())}")
                logger.info(f"Response text length: {len(response_text)}")
                logger.info(f"Response text preview: {response_text[:500] if response_text else 'EMPTY'}")

                # Check for native tool calls first (Ollama's tool_calls field)
                native_tool_calls = response.get("message", {}).get("tool_calls", [])
                logger.info(f"Native tool calls: {len(native_tool_calls) if native_tool_calls else 0}")

                if native_tool_calls:
                    # Handle native Ollama tool calling
                    logger.info(f"Tool calls: {[tc.get('function', {}).get('name') for tc in native_tool_calls]}")
                    tool_iteration += 1

                    if tool_iteration == 1:
                        await send_progress("tool_start")
                    elif tool_iteration == 2:
                        await send_progress("multi_step")
                    else:
                        await send_progress("tool_working")

                    # Execute native tool calls
                    tool_results = []
                    for tc in native_tool_calls:
                        func = tc.get("function", {})
                        tool_name = func.get("name", "")
                        tool_args = func.get("arguments", {})

                        # Validate
                        is_valid, error = validate_tool_call(
                            {"name": tool_name, "arguments": tool_args},
                            registered_tools,
                            tool_schemas,
                        )

                        if is_valid:
                            logger.info(f"Executing tool: {tool_name} with args: {tool_args}")
                            result = await tool_executor(tool_name, tool_args)

                            # Extract content from MCP wrapper to save context space
                            content, total_items = extract_mcp_content(result)
                            original_size = len(content)

                            # Truncate if needed with informative message
                            content, was_truncated = truncate_result(
                                content, MAX_TOOL_RESULT_SIZE, total_items
                            )

                            if was_truncated:
                                logger.warning(
                                    f"Tool {tool_name} result truncated: {original_size} -> {len(content)} bytes"
                                    + (f" ({total_items} total items)" if total_items else "")
                                )
                            else:
                                logger.info(f"Tool {tool_name} result size: {original_size} bytes")

                            tool_results.append(
                                {"name": tool_name, "content": content}
                            )
                        else:
                            logger.warning(f"Invalid tool call: {error}")
                            tool_results.append({"name": tool_name, "content": f"Error: {error}"})

                    # Add to conversation for next Ollama call
                    # For native tool calling, include the tool_calls in the assistant message
                    messages.append({
                        "role": "assistant",
                        "content": response_text,
                        "tool_calls": native_tool_calls,
                    })

                    # Add tool results - Ollama expects role: "tool" with content
                    for i, tr in enumerate(tool_results):
                        messages.append({
                            "role": "tool",
                            "content": tr["content"],
                        })

                    logger.info(f"Added {len(tool_results)} tool results, continuing loop...")
                    continue

                # Check for Hermes-style tool calls in response text
                tool_calls = parse_tool_calls(response_text)

                if not tool_calls:
                    # No tool calls, this is the final response
                    # Extract text before any tool call tags (in case of partial)
                    final_text = response_text
                    if "<tool_call>" in final_text:
                        final_text = final_text.split("<tool_call>")[0].strip()

                    self._add_to_history(user_id, "assistant", final_text)
                    return final_text

                # Process Hermes-style tool calls
                tool_iteration += 1

                if tool_iteration == 1:
                    await send_progress("tool_start")
                elif tool_iteration == 2:
                    await send_progress("multi_step")
                else:
                    await send_progress("tool_working")

                # Validate and execute each tool call
                all_valid = True
                tool_results = []

                for call in tool_calls:
                    is_valid, error = validate_tool_call(call, registered_tools, tool_schemas)

                    if is_valid:
                        logger.info(f"Executing tool: {call['name']}")
                        result = await tool_executor(call["name"], call["arguments"])
                        tool_results.append(
                            {
                                "name": call["name"],
                                "content": json.dumps(result),
                            }
                        )
                    else:
                        logger.warning(f"Invalid tool call: {error}")
                        all_valid = False
                        tool_results.append(
                            {
                                "name": call.get("name", "unknown"),
                                "content": json.dumps({"error": error}),
                            }
                        )

                # Add assistant response and tool results to messages
                messages.append({"role": "assistant", "content": response_text})

                # Format tool results for the model
                tool_response_content = "\n".join(
                    f'<tool_response>\n{{"name": "{tr["name"]}", "content": {tr["content"]}}}\n</tool_response>'
                    for tr in tool_results
                )
                messages.append({"role": "user", "content": tool_response_content})

                # Check retry limit for validation failures
                if not all_valid:
                    retry_count += 1
                    if retry_count >= MAX_TOOL_RETRIES:
                        error_msg = "I'm sorry, I had trouble using the tools correctly. Please try rephrasing your request."
                        self._add_to_history(user_id, "assistant", error_msg)
                        return error_msg

        except httpx.ConnectError:
            logger.error(f"Failed to connect to Ollama at {self.base_url}")
            return "I'm sorry, the AI service is currently unavailable. Please try again later."
        except httpx.TimeoutException:
            logger.error("Ollama request timed out")
            return "The request took too long. Please try again."
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                logger.error(f"Model {self.model} not found in Ollama")
                return f"The AI model is not available. Please run: ollama pull {self.model}"
            logger.error(f"Ollama HTTP error: {e}")
            return f"I'm sorry, I encountered an error: {e}"
        except Exception as e:
            logger.error(f"Ollama execution failed: {e}")
            return f"I'm sorry, I encountered an error: {e}"

    async def simple_response(self, user_id: str, message: str) -> str:
        """Generate a simple response without tools.

        Args:
            user_id: The user's ID for conversation tracking
            message: The user's message

        Returns:
            The assistant's response text
        """
        system_prompt = get_ollama_system_prompt(self.base_system_prompt)

        self._add_to_history(user_id, "user", message)
        history = self._get_history(user_id)

        messages = [
            {"role": m["role"], "content": m["content"]}
            for m in history
            if m["role"] != "system"
        ]

        try:
            response = await self._chat(messages, system_prompt)
            response_text = response.get("message", {}).get("content", "")

            self._add_to_history(user_id, "assistant", response_text)
            return response_text

        except httpx.ConnectError:
            logger.error(f"Failed to connect to Ollama at {self.base_url}")
            return "I'm sorry, the AI service is currently unavailable. Please try again later."
        except httpx.TimeoutException:
            logger.error("Ollama request timed out")
            return "The request took too long. Please try again."
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                logger.error(f"Model {self.model} not found in Ollama")
                return f"The AI model is not available. Please run: ollama pull {self.model}"
            logger.error(f"Ollama HTTP error: {e}")
            return f"I'm sorry, I encountered an error: {e}"
        except Exception as e:
            logger.error(f"Simple response failed: {e}")
            return f"I'm sorry, I encountered an error: {e}"

    async def classify_intent(
        self,
        message: str,
        registry: DomainRegistry,
        timeout: float = 10.0,
    ) -> list[str]:
        """Classify user message into domains.

        Args:
            message: The user's message to classify
            registry: Domain registry with available domains
            timeout: Timeout in seconds for classification

        Returns:
            List of domain names. Falls back to ["general"] on error.
        """
        # Build router prompt
        sorted_domains = registry.get_sorted_domains()
        domain_list = format_domain_list(sorted_domains)
        prompt = build_router_prompt(message, domain_list)

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(
                    f"{self.base_url}/api/chat",
                    json={
                        "model": self.model,
                        "messages": [
                            {
                                "role": "system",
                                "content": "You are a request classifier. Output only domain names, comma-separated. No explanation.",
                            },
                            {"role": "user", "content": prompt},
                        ],
                        "stream": False,
                        "options": {
                            "temperature": 0.1,  # Very low for consistent classification
                            "num_ctx": 2048,  # Small context for fast classification
                        },
                    },
                )
                response.raise_for_status()

                result = response.json()
                content = result.get("message", {}).get("content", "").strip()

                logger.info(f"Router classification raw: {content}")

                # Parse comma-separated domains
                domains = [d.strip().lower() for d in content.split(",") if d.strip()]

                # Validate domains exist in registry
                valid_domains = [d for d in domains if d in registry.domains]

                if not valid_domains:
                    logger.warning(f"No valid domains from classification: {content}")
                    return ["general"]

                logger.info(f"Classified domains: {valid_domains}")
                return valid_domains

        except httpx.TimeoutException:
            logger.warning("Router classification timed out, falling back to general")
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
        router_timeout: float = 10.0,
    ) -> str:
        """Execute request with domain-aware routing.

        This method:
        1. Classifies the user's intent to determine relevant domains
        2. Filters tools to only those in the identified domains
        3. Executes with the focused tool set

        Args:
            user_id: The user's ID for conversation tracking
            message: The user's message
            all_tools: Full list of available tools
            tool_executor: Async callable that takes (tool_name, arguments) and returns result
            registry: Domain registry for routing
            progress_callback: Optional async callback for progress updates
            router_timeout: Timeout for intent classification

        Returns:
            The assistant's final response text
        """
        # Step 1: Classify intent
        domains = await self.classify_intent(message, registry, timeout=router_timeout)
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

        # Step 4: Build focused system prompt with domain hints
        base_prompt = self.base_system_prompt or get_default_system_prompt()
        domain_hints = registry.get_prompt_hints(domains)
        focused_prompt = f"{base_prompt}\n\n{domain_hints}"

        # Step 5: Execute with filtered tools
        # Temporarily override system prompt
        original_prompt = self.base_system_prompt
        self.base_system_prompt = focused_prompt

        try:
            result = await self.execute_with_tools(
                user_id=user_id,
                message=message,
                tools=filtered_tools,
                tool_executor=tool_executor,
                progress_callback=progress_callback,
            )
            return result
        finally:
            self.base_system_prompt = original_prompt
