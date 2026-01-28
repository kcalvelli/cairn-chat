"""System prompts and templates for LLM backends."""

import json
import random
from datetime import datetime

# Witty progress messages organized by phase (shared across backends)
PROGRESS_MESSAGES = {
    "thinking": [
        "Let me think about this...",
        "Processing your request...",
        "Hmm, interesting question...",
        "Looking into it...",
        "On it!",
    ],
    "tool_start": [
        "Firing up the tools...",
        "Rolling up my sleeves...",
        "Getting to work...",
        "Found what I need, executing...",
        "Launching operation...",
    ],
    "tool_working": [
        "Still working on it...",
        "Making progress...",
        "Crunching the data...",
        "Juggling some tasks here...",
        "Almost there...",
    ],
    "multi_step": [
        "This needs a few steps, hang tight...",
        "Multi-step operation in progress...",
        "Chaining some actions together...",
        "Performing a little orchestration...",
    ],
    "slow_response": [
        "Thinking hard about this one...",
        "Taking a bit longer than usual...",
        "Navigating some heavy traffic...",
        "Still here, just being thorough!",
        "Patience, grasshopper...",
    ],
}


def get_progress_message(phase: str) -> str:
    """Get a random progress message for the given phase."""
    messages = PROGRESS_MESSAGES.get(phase, PROGRESS_MESSAGES["thinking"])
    return random.choice(messages)


def get_current_date() -> str:
    """Get the current date formatted for prompts."""
    return datetime.now().strftime("%A, %B %d, %Y")


def get_default_system_prompt() -> str:
    """Generate the default system prompt with current date.

    This is the base prompt used when no custom prompt is provided.
    Backend-specific additions (like tool instructions) are added separately.
    """
    today = get_current_date()
    return f"""You are Axios AI, a helpful family assistant. Today is {today}.

You can help with:
- Email: Read, search, compose, and send emails
- Calendar: View and create events, check availability (includes religious/liturgical calendars)
- Contacts: Look up contact information
- General questions and conversation

Be concise and friendly. When using tools, explain what you're doing briefly.
If a task requires multiple steps, complete them without asking for confirmation unless critical.

CRITICAL RULES:
- NEVER invent, guess, or hallucinate information. Only use data returned by tools.
- If you need an email address, phone number, or other contact info, ALWAYS look it up first using the contact tools.
- If a tool search returns no results or missing data, tell the user clearly. Do NOT make up values.
- Example: If asked to email someone but their contact has no email address, say "I couldn't find an email address for [name] in your contacts."

IMPORTANT: Always use today's actual date ({today}) when checking calendars or scheduling."""


# Hermes-style tool calling template for Qwen3 and similar models
HERMES_TOOL_SYSTEM_TEMPLATE = """You are a function calling AI assistant. You MUST use the provided functions to answer questions about contacts, calendar, and email - you do not have direct access to this data.

<tools>
{tools_json}
</tools>

When you need to call a function, output a JSON object within <tool_call></tool_call> XML tags:
<tool_call>
{{"name": "function_name", "arguments": {{"arg1": "value1"}}}}
</tool_call>

IMPORTANT BEHAVIOR:
- You have NO built-in knowledge of the user's contacts, calendar, or emails
- The ONLY way to get this information is by calling the functions listed above
- When the user asks about their data, you MUST call a function - do NOT just say "I'll check" or "Let me look"
- Read the function descriptions carefully and choose the appropriate one
- Call the function IMMEDIATELY in your response using the <tool_call> format

CRITICAL RULES:
1. ONLY call functions that are listed in <tools>. NEVER invent function names.
2. ONLY use argument names that appear in the function's parameters. NEVER add extra arguments.
3. If you cannot complete a task with the available functions, say so - do NOT hallucinate a function.
4. If a required argument value is unknown, ask the user - do NOT guess or make up values.
5. Always validate your function call matches the schema before outputting it.

{base_prompt}

/nothink"""


def get_hermes_tool_prompt(tools: list[dict], base_prompt: str | None = None) -> str:
    """Generate a Hermes-style tool calling system prompt.

    Args:
        tools: List of tool definitions to include
        base_prompt: Optional base prompt to include (defaults to get_default_system_prompt())

    Returns:
        Complete system prompt with tool definitions
    """
    if base_prompt is None:
        base_prompt = get_default_system_prompt()

    # Format tools as JSON for the prompt
    tools_json = json.dumps(tools, indent=2)

    return HERMES_TOOL_SYSTEM_TEMPLATE.format(
        tools_json=tools_json,
        base_prompt=base_prompt,
    )


def get_ollama_system_prompt(base_prompt: str | None = None) -> str:
    """Generate the system prompt for Ollama without tools.

    Args:
        base_prompt: Optional custom base prompt

    Returns:
        System prompt for non-tool conversations
    """
    if base_prompt is None:
        base_prompt = get_default_system_prompt()

    return base_prompt


# Router prompt template for intent classification
ROUTER_PROMPT_TEMPLATE = """Classify the user's request into one or more domains.
Return ONLY the domain names as a comma-separated list. No explanation.

Available domains:
{domain_list}

Examples:
- "What time is it?" → time
- "Check my calendar for today" → calendar
- "Email John from my contacts" → contacts, email
- "Schedule a meeting with the team" → calendar
- "Find duplicate contacts" → contacts
- "What's the latest news about AI?" → search
- "Find pizza places near me" → search
- "Tell me a joke" → general
- "Hello" → general
- "Thanks!" → general

User: {message}
Domains:"""


def build_router_prompt(message: str, domain_list: str) -> str:
    """Build the router prompt with the domain list.

    Args:
        message: The user's message to classify
        domain_list: Formatted string of available domains

    Returns:
        Complete router prompt
    """
    return ROUTER_PROMPT_TEMPLATE.format(
        domain_list=domain_list,
        message=message,
    )


def format_domain_list(domains: list) -> str:
    """Format domains for the router prompt.

    Args:
        domains: List of DomainConfig objects sorted by priority

    Returns:
        Formatted domain list string
    """
    return "\n".join(f"- {d.name}: {d.description}" for d in domains)
