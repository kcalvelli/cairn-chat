"""LLM backend implementations for axios-ai-bot.

This module provides the Anthropic Claude client for AI responses.
"""

from typing import Any

from .base import LLMBackend, ProgressCallback
from .anthropic import AnthropicClient
from .prompts import get_default_system_prompt, get_progress_message

__all__ = [
    "LLMBackend",
    "ProgressCallback",
    "AnthropicClient",
    "create_llm_client",
    "get_default_system_prompt",
    "get_progress_message",
]


def create_llm_client(config: dict[str, Any]) -> LLMBackend:
    """Create an Anthropic LLM client.

    Args:
        config: Configuration dictionary with options:
            - api_key: Anthropic API key (required)
            - system_prompt: Custom system prompt (optional)
            - max_context_messages: Max conversation history (optional, default 10)
            - user_config: Per-user location/timezone config (optional)

    Returns:
        An AnthropicClient instance
    """
    return AnthropicClient(
        api_key=config["api_key"],
        system_prompt=config.get("system_prompt"),
        max_context_messages=config.get("max_context_messages", 10),
        user_config=config.get("user_config", {}),
    )
