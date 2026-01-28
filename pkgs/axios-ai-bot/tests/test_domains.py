"""Tests for domain registry."""

import pytest

from axios_ai_bot.domains import (
    DEFAULT_DOMAINS,
    DomainConfig,
    DomainRegistry,
    get_default_registry,
)


class TestDomainConfig:
    """Tests for DomainConfig dataclass."""

    def test_basic_creation(self):
        """Test creating a domain config."""
        config = DomainConfig(
            name="test",
            description="Test domain",
            servers=["test-server"],
            tools=["tool1", "tool2"],
            prompt_hint="You are a test assistant.",
            priority=5,
        )
        assert config.name == "test"
        assert config.description == "Test domain"
        assert config.servers == ["test-server"]
        assert config.tools == ["tool1", "tool2"]
        assert config.prompt_hint == "You are a test assistant."
        assert config.priority == 5

    def test_default_values(self):
        """Test default values for optional fields."""
        config = DomainConfig(name="minimal", description="Minimal config")
        assert config.servers == []
        assert config.tools == []
        assert config.prompt_hint == ""
        assert config.priority == 0


class TestDomainRegistry:
    """Tests for DomainRegistry."""

    @pytest.fixture
    def sample_registry(self):
        """Create a sample registry for testing."""
        return DomainRegistry(
            domains={
                "contacts": DomainConfig(
                    name="contacts",
                    description="Contact management",
                    tools=["list_contacts", "search_contacts"],
                    prompt_hint="Contact assistant.",
                    priority=1,
                ),
                "email": DomainConfig(
                    name="email",
                    description="Email management",
                    tools=["search_emails", "send_email"],
                    prompt_hint="Email assistant.",
                    priority=2,
                ),
                "general": DomainConfig(
                    name="general",
                    description="General chat",
                    tools=[],
                    prompt_hint="Helpful assistant.",
                    priority=99,
                ),
            }
        )

    @pytest.fixture
    def sample_tools(self):
        """Sample tool list for filtering tests."""
        return [
            {"name": "list_contacts", "description": "List contacts"},
            {"name": "search_contacts", "description": "Search contacts"},
            {"name": "search_emails", "description": "Search emails"},
            {"name": "send_email", "description": "Send email"},
            {"name": "get_time", "description": "Get current time"},
        ]

    def test_get_tools_single_domain(self, sample_registry, sample_tools):
        """Test filtering tools for a single domain."""
        result = sample_registry.get_tools_for_domains(["contacts"], sample_tools)
        assert len(result) == 2
        assert all(t["name"] in ["list_contacts", "search_contacts"] for t in result)

    def test_get_tools_multiple_domains(self, sample_registry, sample_tools):
        """Test filtering tools for multiple domains (cross-domain)."""
        result = sample_registry.get_tools_for_domains(
            ["contacts", "email"], sample_tools
        )
        assert len(result) == 4
        names = [t["name"] for t in result]
        assert "list_contacts" in names
        assert "search_contacts" in names
        assert "search_emails" in names
        assert "send_email" in names

    def test_get_tools_general_domain(self, sample_registry, sample_tools):
        """Test that general domain returns no tools."""
        result = sample_registry.get_tools_for_domains(["general"], sample_tools)
        assert len(result) == 0

    def test_get_tools_unknown_domain(self, sample_registry, sample_tools):
        """Test that unknown domains are ignored."""
        result = sample_registry.get_tools_for_domains(["unknown"], sample_tools)
        assert len(result) == 0

    def test_get_tools_mixed_valid_invalid(self, sample_registry, sample_tools):
        """Test that valid domains work even with invalid ones mixed in."""
        result = sample_registry.get_tools_for_domains(
            ["contacts", "unknown", "invalid"], sample_tools
        )
        assert len(result) == 2  # Only contacts tools

    def test_get_prompt_hints_single_domain(self, sample_registry):
        """Test getting prompt hints for a single domain."""
        result = sample_registry.get_prompt_hints(["contacts"])
        assert result == "Contact assistant."

    def test_get_prompt_hints_multiple_domains(self, sample_registry):
        """Test getting combined prompt hints for multiple domains."""
        result = sample_registry.get_prompt_hints(["contacts", "email"])
        assert "Contact assistant." in result
        assert "Email assistant." in result

    def test_get_prompt_hints_unknown_domain(self, sample_registry):
        """Test that unknown domains return empty hints."""
        result = sample_registry.get_prompt_hints(["unknown"])
        assert result == ""

    def test_get_sorted_domains(self, sample_registry):
        """Test domains are sorted by priority."""
        sorted_domains = sample_registry.get_sorted_domains()
        priorities = [d.priority for d in sorted_domains]
        assert priorities == sorted(priorities)
        assert sorted_domains[0].name == "contacts"  # priority 1
        assert sorted_domains[-1].name == "general"  # priority 99


class TestDefaultRegistry:
    """Tests for the default domain registry."""

    def test_default_registry_has_all_domains(self):
        """Test that default registry has expected domains."""
        registry = get_default_registry()
        expected = ["contacts", "calendar", "email", "time", "search", "general"]
        for domain in expected:
            assert domain in registry.domains

    def test_default_domains_have_tools(self):
        """Test that non-general domains have tools defined."""
        registry = get_default_registry()
        for name, config in registry.domains.items():
            if name != "general":
                assert len(config.tools) > 0, f"Domain {name} should have tools"

    def test_general_domain_has_no_tools(self):
        """Test that general domain has no tools."""
        registry = get_default_registry()
        assert len(registry.domains["general"].tools) == 0

    def test_default_domains_have_descriptions(self):
        """Test that all domains have descriptions."""
        registry = get_default_registry()
        for name, config in registry.domains.items():
            assert config.description, f"Domain {name} should have a description"

    def test_default_domains_have_prompt_hints(self):
        """Test that all domains have prompt hints."""
        registry = get_default_registry()
        for name, config in registry.domains.items():
            assert config.prompt_hint, f"Domain {name} should have a prompt hint"

    def test_tool_naming_convention(self):
        """Test that tools follow server__tool naming convention."""
        registry = get_default_registry()
        for name, config in registry.domains.items():
            for tool in config.tools:
                assert (
                    "__" in tool
                ), f"Tool {tool} in domain {name} should use server__tool format"
