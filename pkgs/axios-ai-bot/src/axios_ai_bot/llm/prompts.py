"""System prompts and templates for the LLM backend."""

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


def get_user_location_context(
    user_id: str,
    user_config: dict,
) -> str:
    """Get location context for a specific user.

    Args:
        user_id: The user's JID (e.g., "keith@localhost")
        user_config: User configuration dict with 'users', 'defaultLocation', 'defaultTimezone'

    Returns:
        Location context string to inject into the system prompt, or empty string if no location
    """
    users = user_config.get("users", {})
    default_location = user_config.get("defaultLocation", "")
    default_timezone = user_config.get("defaultTimezone", "America/New_York")

    # Check for user-specific config (try with and without resource)
    user_bare = user_id.split("/")[0]  # Remove XMPP resource if present
    user_data = users.get(user_bare) or users.get(user_id)

    if user_data:
        location = user_data.get("location", "")
        timezone = user_data.get("timezone", default_timezone)
    else:
        location = default_location
        timezone = default_timezone

    if not location:
        return ""

    return f"""
User's location: {location}
User's timezone: {timezone}
Use this location for local searches, weather queries, and "near me" requests."""


def get_default_system_prompt() -> str:
    """Generate the default system prompt with current date.

    This is the base prompt used when no custom prompt is provided.
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
