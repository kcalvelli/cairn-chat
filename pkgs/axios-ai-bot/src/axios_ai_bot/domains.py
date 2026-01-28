"""Domain registry for intent-based routing.

This module defines domains that map user intents to specific MCP servers
and their tools, enabling efficient local LLM execution by reducing context size.
"""

from dataclasses import dataclass, field


@dataclass
class DomainConfig:
    """Configuration for a single domain."""

    name: str
    description: str  # For router prompt
    servers: list[str] = field(default_factory=list)  # MCP server names
    tools: list[str] = field(default_factory=list)  # Tool name patterns
    prompt_hint: str = ""  # Added to system prompt when domain is active
    priority: int = 0  # For ordering in router prompt (lower = first)


@dataclass
class DomainRegistry:
    """Registry of all available domains."""

    domains: dict[str, DomainConfig] = field(default_factory=dict)

    def get_tools_for_domains(
        self,
        domain_names: list[str],
        all_tools: list[dict],
    ) -> list[dict]:
        """Filter tools to only those in the specified domains.

        Args:
            domain_names: List of domain names to include
            all_tools: Full list of available tools

        Returns:
            Filtered list of tools matching the domains
        """
        allowed_tools = set()
        for name in domain_names:
            if name in self.domains:
                allowed_tools.update(self.domains[name].tools)

        return [t for t in all_tools if t["name"] in allowed_tools]

    def get_prompt_hints(self, domain_names: list[str]) -> str:
        """Combine prompt hints for active domains.

        Args:
            domain_names: List of active domain names

        Returns:
            Combined prompt hints string
        """
        hints = []
        for name in domain_names:
            if name in self.domains and self.domains[name].prompt_hint:
                hints.append(self.domains[name].prompt_hint)
        return "\n".join(hints)

    def get_sorted_domains(self) -> list[DomainConfig]:
        """Get domains sorted by priority.

        Returns:
            List of domains sorted by priority (lower first)
        """
        return sorted(self.domains.values(), key=lambda x: x.priority)


# Default domain registry for axios-ai-bot
DEFAULT_DOMAINS = {
    "contacts": DomainConfig(
        name="contacts",
        description="Looking up, searching, or modifying contact information",
        servers=["mcp-dav"],
        tools=[
            "mcp-dav__list_contacts",
            "mcp-dav__search_contacts",
            "mcp-dav__get_contact",
            "mcp-dav__create_contact",
            "mcp-dav__update_contact",
            "mcp-dav__delete_contact",
        ],
        prompt_hint="You are a contacts assistant. Use contact tools to look up and manage contact information.",
        priority=1,
    ),
    "calendar": DomainConfig(
        name="calendar",
        description="Events, scheduling, availability, and reminders",
        servers=["mcp-dav"],
        tools=[
            "mcp-dav__list_events",
            "mcp-dav__search_events",
            "mcp-dav__create_event",
            "mcp-dav__get_free_busy",
        ],
        prompt_hint="You are a calendar assistant. Use calendar tools to check and manage events.",
        priority=2,
    ),
    "email": DomainConfig(
        name="email",
        description="Reading, searching, composing, or sending emails",
        servers=["axios-ai-mail"],
        tools=[
            "axios-ai-mail__list_accounts",
            "axios-ai-mail__search_emails",
            "axios-ai-mail__read_email",
            "axios-ai-mail__compose_email",
            "axios-ai-mail__send_email",
            "axios-ai-mail__reply_to_email",
            "axios-ai-mail__mark_read",
            "axios-ai-mail__delete_email",
        ],
        prompt_hint="You are an email assistant. Use email tools to search, read, and send messages.",
        priority=3,
    ),
    "time": DomainConfig(
        name="time",
        description="Checking current time or converting between timezones",
        servers=["time"],
        tools=[
            "time__get_current_time",
            "time__convert_time",
        ],
        prompt_hint="You can check the current time and convert between timezones.",
        priority=4,
    ),
    "search": DomainConfig(
        name="search",
        description="Searching the web for information, news, or general questions",
        servers=["brave-search"],
        tools=[
            "brave-search__brave_web_search",
            "brave-search__brave_local_search",
        ],
        prompt_hint="You can search the web for current information. Use web search for general queries and local search for businesses/places.",
        priority=5,
    ),
    "general": DomainConfig(
        name="general",
        description="General conversation, questions, or tasks not requiring data access",
        servers=[],
        tools=[],
        prompt_hint="You are a helpful assistant. Answer questions conversationally.",
        priority=99,  # Always last
    ),
}


def get_default_registry() -> DomainRegistry:
    """Get the default domain registry.

    Returns:
        DomainRegistry with default domains configured
    """
    return DomainRegistry(domains=DEFAULT_DOMAINS.copy())
