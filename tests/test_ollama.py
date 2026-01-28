"""Tests for Ollama LLM backend."""

import json
import pytest

from axios_ai_bot.llm.ollama import (
    parse_tool_calls,
    validate_tool_call,
    format_tools_for_ollama,
    format_tools_for_hermes_prompt,
)
from axios_ai_bot.llm.prompts import (
    get_hermes_tool_prompt,
    get_default_system_prompt,
    get_ollama_system_prompt,
)


class TestParseToolCalls:
    """Tests for parse_tool_calls function."""

    def test_single_tool_call(self):
        """Test parsing a single valid tool call."""
        response = '''I'll check your calendar.
<tool_call>
{"name": "calendar__list_events", "arguments": {"start_date": "2024-01-15"}}
</tool_call>'''

        calls = parse_tool_calls(response)
        assert len(calls) == 1
        assert calls[0]["name"] == "calendar__list_events"
        assert calls[0]["arguments"]["start_date"] == "2024-01-15"

    def test_multiple_tool_calls(self):
        """Test parsing multiple tool calls."""
        response = '''Let me search for contacts and check the calendar.
<tool_call>
{"name": "contacts__search", "arguments": {"query": "John"}}
</tool_call>
<tool_call>
{"name": "calendar__list_events", "arguments": {}}
</tool_call>'''

        calls = parse_tool_calls(response)
        assert len(calls) == 2
        assert calls[0]["name"] == "contacts__search"
        assert calls[1]["name"] == "calendar__list_events"

    def test_no_tool_calls(self):
        """Test response without tool calls."""
        response = "Hello! How can I help you today?"

        calls = parse_tool_calls(response)
        assert len(calls) == 0

    def test_malformed_json(self):
        """Test handling of malformed JSON in tool call."""
        response = '''<tool_call>
{"name": "broken", "arguments": {invalid json here}}
</tool_call>'''

        calls = parse_tool_calls(response)
        assert len(calls) == 0  # Should skip malformed calls

    def test_missing_name_field(self):
        """Test tool call without name field."""
        response = '''<tool_call>
{"arguments": {"foo": "bar"}}
</tool_call>'''

        calls = parse_tool_calls(response)
        assert len(calls) == 0  # Should skip invalid calls

    def test_missing_arguments_defaults_to_empty(self):
        """Test tool call without arguments field gets empty dict."""
        response = '''<tool_call>
{"name": "simple_tool"}
</tool_call>'''

        calls = parse_tool_calls(response)
        assert len(calls) == 1
        assert calls[0]["name"] == "simple_tool"
        assert calls[0]["arguments"] == {}

    def test_whitespace_handling(self):
        """Test tool calls with various whitespace."""
        response = '''<tool_call>   {"name": "test", "arguments": {}}   </tool_call>'''

        calls = parse_tool_calls(response)
        assert len(calls) == 1
        assert calls[0]["name"] == "test"

    def test_multiline_json(self):
        """Test tool call with multiline JSON."""
        response = '''<tool_call>
{
    "name": "email__send",
    "arguments": {
        "to": "john@example.com",
        "subject": "Hello",
        "body": "Hi there!"
    }
}
</tool_call>'''

        calls = parse_tool_calls(response)
        assert len(calls) == 1
        assert calls[0]["name"] == "email__send"
        assert calls[0]["arguments"]["to"] == "john@example.com"


class TestValidateToolCall:
    """Tests for validate_tool_call function."""

    @pytest.fixture
    def registered_tools(self):
        return {"email__send", "calendar__list_events", "contacts__search"}

    @pytest.fixture
    def tool_schemas(self):
        return {
            "email__send": {
                "type": "object",
                "properties": {
                    "to": {"type": "string"},
                    "subject": {"type": "string"},
                    "body": {"type": "string"},
                },
                "required": ["to", "subject", "body"],
            },
            "calendar__list_events": {
                "type": "object",
                "properties": {
                    "start_date": {"type": "string"},
                    "end_date": {"type": "string"},
                },
                "required": [],
            },
            "contacts__search": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                },
                "required": ["query"],
            },
        }

    def test_valid_tool_call(self, registered_tools, tool_schemas):
        """Test validation of a correct tool call."""
        call = {
            "name": "email__send",
            "arguments": {
                "to": "john@example.com",
                "subject": "Hello",
                "body": "Hi there!",
            },
        }

        is_valid, error = validate_tool_call(call, registered_tools, tool_schemas)
        assert is_valid is True
        assert error == ""

    def test_unknown_tool_name(self, registered_tools, tool_schemas):
        """Test rejection of unknown tool name."""
        call = {
            "name": "weather__forecast",
            "arguments": {"city": "NYC"},
        }

        is_valid, error = validate_tool_call(call, registered_tools, tool_schemas)
        assert is_valid is False
        assert "Unknown tool: weather__forecast" in error

    def test_missing_required_argument(self, registered_tools, tool_schemas):
        """Test rejection when required argument is missing."""
        call = {
            "name": "email__send",
            "arguments": {
                "to": "john@example.com",
                "subject": "Hello",
                # Missing 'body'
            },
        }

        is_valid, error = validate_tool_call(call, registered_tools, tool_schemas)
        assert is_valid is False
        assert "Missing required argument: body" in error

    def test_extra_argument(self, registered_tools, tool_schemas):
        """Test rejection of extra arguments."""
        call = {
            "name": "email__send",
            "arguments": {
                "to": "john@example.com",
                "subject": "Hello",
                "body": "Hi there!",
                "priority": "high",  # Extra argument
            },
        }

        is_valid, error = validate_tool_call(call, registered_tools, tool_schemas)
        assert is_valid is False
        assert "Unknown argument: priority" in error

    def test_tool_with_no_required_args(self, registered_tools, tool_schemas):
        """Test tool with no required arguments."""
        call = {
            "name": "calendar__list_events",
            "arguments": {},
        }

        is_valid, error = validate_tool_call(call, registered_tools, tool_schemas)
        assert is_valid is True

    def test_tool_with_optional_args(self, registered_tools, tool_schemas):
        """Test tool with optional arguments provided."""
        call = {
            "name": "calendar__list_events",
            "arguments": {
                "start_date": "2024-01-15",
            },
        }

        is_valid, error = validate_tool_call(call, registered_tools, tool_schemas)
        assert is_valid is True


class TestFormatToolsForOllama:
    """Tests for format_tools_for_ollama function."""

    def test_basic_formatting(self):
        """Test basic tool formatting for Ollama."""
        tools = [
            {
                "name": "test_tool",
                "description": "A test tool",
                "input_schema": {
                    "type": "object",
                    "properties": {"arg1": {"type": "string"}},
                },
            }
        ]

        formatted = format_tools_for_ollama(tools)

        assert len(formatted) == 1
        assert formatted[0]["type"] == "function"
        assert formatted[0]["function"]["name"] == "test_tool"
        assert formatted[0]["function"]["description"] == "A test tool"
        assert formatted[0]["function"]["parameters"]["type"] == "object"

    def test_multiple_tools(self):
        """Test formatting multiple tools."""
        tools = [
            {"name": "tool1", "description": "Tool 1", "input_schema": {}},
            {"name": "tool2", "description": "Tool 2", "input_schema": {}},
        ]

        formatted = format_tools_for_ollama(tools)

        assert len(formatted) == 2
        assert formatted[0]["function"]["name"] == "tool1"
        assert formatted[1]["function"]["name"] == "tool2"


class TestFormatToolsForHermesPrompt:
    """Tests for format_tools_for_hermes_prompt function."""

    def test_basic_formatting(self):
        """Test basic tool formatting for Hermes prompt."""
        tools = [
            {
                "name": "email__send",
                "description": "Send an email",
                "input_schema": {
                    "type": "object",
                    "properties": {"to": {"type": "string"}},
                },
            }
        ]

        formatted = format_tools_for_hermes_prompt(tools)

        assert len(formatted) == 1
        assert formatted[0]["name"] == "email__send"
        assert formatted[0]["description"] == "Send an email"
        assert "parameters" in formatted[0]


class TestPromptTemplates:
    """Tests for prompt template functions."""

    def test_default_system_prompt_contains_date(self):
        """Test that default prompt includes current date."""
        prompt = get_default_system_prompt()

        assert "Axios AI" in prompt
        assert "Today is" in prompt
        assert "Email" in prompt
        assert "Calendar" in prompt

    def test_hermes_tool_prompt_structure(self):
        """Test Hermes tool prompt has required structure."""
        tools = [
            {"name": "test_tool", "description": "Test", "parameters": {}},
        ]

        prompt = get_hermes_tool_prompt(tools)

        assert "<tools>" in prompt
        assert "</tools>" in prompt
        assert "<tool_call>" in prompt
        assert "CRITICAL RULES" in prompt
        assert "NEVER invent function names" in prompt
        assert "/nothink" in prompt

    def test_hermes_prompt_includes_tool_json(self):
        """Test that tools are included as JSON in prompt."""
        tools = [
            {"name": "my_tool", "description": "Does something", "parameters": {}},
        ]

        prompt = get_hermes_tool_prompt(tools)

        assert "my_tool" in prompt
        assert "Does something" in prompt

    def test_hermes_prompt_with_custom_base(self):
        """Test Hermes prompt with custom base prompt."""
        tools = [{"name": "test", "description": "Test", "parameters": {}}]
        custom_base = "You are a custom assistant."

        prompt = get_hermes_tool_prompt(tools, custom_base)

        assert "You are a custom assistant." in prompt
        assert "<tools>" in prompt

    def test_ollama_system_prompt_default(self):
        """Test Ollama system prompt uses default."""
        prompt = get_ollama_system_prompt()

        assert "Axios AI" in prompt

    def test_ollama_system_prompt_custom(self):
        """Test Ollama system prompt with custom base."""
        custom = "Custom system prompt"
        prompt = get_ollama_system_prompt(custom)

        assert prompt == custom


class TestAntiHallucinationRules:
    """Tests to verify anti-hallucination measures are in place."""

    def test_hermes_prompt_has_anti_hallucination_rules(self):
        """Test that Hermes prompt contains anti-hallucination instructions."""
        tools = [{"name": "test", "description": "Test", "parameters": {}}]
        prompt = get_hermes_tool_prompt(tools)

        # Check for key anti-hallucination phrases
        assert "ONLY call functions that are listed in <tools>" in prompt
        assert "NEVER invent function names" in prompt
        assert "NEVER add extra arguments" in prompt
        assert "do NOT hallucinate" in prompt.lower() or "do NOT guess" in prompt

    def test_hermes_prompt_has_nothink_directive(self):
        """Test that Hermes prompt disables thinking mode."""
        tools = [{"name": "test", "description": "Test", "parameters": {}}]
        prompt = get_hermes_tool_prompt(tools)

        assert "/nothink" in prompt
