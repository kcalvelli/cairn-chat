"""LLM backend implementations for axios-ai-bot.

This module provides a unified interface for different LLM backends:
- AnthropicClient: Claude API (Haiku + Sonnet)
- OllamaClient: Local Ollama with Qwen3

Use create_llm_client() factory function to instantiate the appropriate backend
based on configuration.
"""

from typing import Any

from .base import LLMBackend, ProgressCallback
from .anthropic import AnthropicClient
from .ollama import OllamaClient
from .prompts import get_default_system_prompt, get_progress_message

__all__ = [
    "LLMBackend",
    "ProgressCallback",
    "AnthropicClient",
    "OllamaClient",
    "create_llm_client",
    "get_default_system_prompt",
    "get_progress_message",
]


def create_llm_client(
    backend: str,
    config: dict[str, Any],
) -> LLMBackend:
    """Factory function to create the appropriate LLM client.

    Args:
        backend: The backend type ("anthropic" or "ollama")
        config: Configuration dictionary with backend-specific options

    Returns:
        An LLMBackend instance

    Raises:
        ValueError: If the backend type is not recognized

    Config options for "anthropic":
        - api_key: Anthropic API key (required)
        - system_prompt: Custom system prompt (optional)
        - max_context_messages: Max conversation history (optional, default 10)

    Config options for "ollama":
        - base_url: Ollama server URL (optional, default "http://localhost:11434")
        - model: Model name (optional, default "qwen3:14b-q4_K_M")
        - system_prompt: Custom system prompt (optional)
        - max_context_messages: Max conversation history (optional, default 10)
        - temperature: Sampling temperature (optional, default 0.2)
        - enable_thinking: Enable thinking mode (optional, default False)
        - timeout: Request timeout in seconds (optional, default 120.0)
    """
    if backend == "anthropic":
        return AnthropicClient(
            api_key=config["api_key"],
            system_prompt=config.get("system_prompt"),
            max_context_messages=config.get("max_context_messages", 10),
            user_config=config.get("user_config", {}),
        )
    elif backend == "ollama":
        return OllamaClient(
            base_url=config.get("base_url", "http://localhost:11434"),
            model=config.get("model", "qwen3:14b-q4_K_M"),
            system_prompt=config.get("system_prompt"),
            max_context_messages=config.get("max_context_messages", 10),
            temperature=config.get("temperature", 0.2),
            enable_thinking=config.get("enable_thinking", False),
            timeout=config.get("timeout", 120.0),
            user_config=config.get("user_config", {}),
        )
    else:
        raise ValueError(f"Unknown LLM backend: {backend}. Valid options: anthropic, ollama")
