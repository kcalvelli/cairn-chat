"""LLM backend implementations for axios-ai-bot.

This module provides the Google Gemini client for AI responses.
"""

from typing import Any

from .base import LLMBackend, ProgressCallback
from .gemini import GeminiClient
from .prompts import get_default_system_prompt, get_progress_message

__all__ = [
    "LLMBackend",
    "ProgressCallback",
    "GeminiClient",
    "create_llm_client",
    "get_default_system_prompt",
    "get_progress_message",
]


def create_llm_client(config: dict[str, Any]) -> LLMBackend:
    """Create a Gemini LLM client.

    Args:
        config: Configuration dictionary with options:
            - api_key: Google Gemini API key (required)
            - system_prompt: Custom system prompt (optional)
            - max_context_messages: Max conversation history (optional, default 10)
            - user_config: Per-user location/timezone config (optional)

    Returns:
        A GeminiClient instance
    """
    return GeminiClient(
        api_key=config["api_key"],
        system_prompt=config.get("system_prompt"),
        max_context_messages=config.get("max_context_messages", 10),
        user_config=config.get("user_config", {}),
    )
