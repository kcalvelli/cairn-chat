# Domain Routing Capability

## ADDED Requirements

### Requirement: Intent Classification

The system MUST classify user messages into one or more domains before tool execution.

#### Scenario: Single domain classification
Given a user message "What's on my calendar today?"
When the intent router processes the message
Then it returns ["calendar"] as the classified domains

#### Scenario: Multi-domain classification
Given a user message "Email John from my contacts"
When the intent router processes the message
Then it returns ["contacts", "email"] as the classified domains

#### Scenario: General conversation classification
Given a user message "Tell me a joke"
When the intent router processes the message
Then it returns ["general"] as the classified domain

#### Scenario: Classification timeout fallback
Given the intent router takes longer than the configured timeout
When classification fails
Then the system falls back to ["general"] domain

---

### Requirement: Domain Registry

The system MUST maintain a registry mapping domains to MCP servers and tools.

#### Scenario: Domain tool lookup
Given a domain registry with "contacts" mapped to ["list_contacts", "search_contacts"]
When tools are requested for domain "contacts"
Then only the registered contact tools are returned

#### Scenario: Cross-domain tool merging
Given domains ["contacts", "email"] are classified
When tools are filtered for these domains
Then tools from both domains are combined into a single list

#### Scenario: Unknown domain handling
Given a classification returns an unknown domain "foo"
When the domain is looked up
Then the unknown domain is ignored and valid domains are used

---

### Requirement: Tool Filtering

The system MUST filter the full tool set to only include tools relevant to classified domains.

#### Scenario: Single domain filtering
Given 20 total tools available
And domain "calendar" has 4 registered tools
When filtering for ["calendar"]
Then only 4 calendar tools are returned

#### Scenario: General domain has no tools
Given domain "general" is classified
When tools are filtered
Then an empty tool list is returned
And simple response mode is used

---

### Requirement: Focused System Prompts

The system MUST construct focused system prompts based on active domains.

#### Scenario: Domain-specific prompt hints
Given domain "contacts" has prompt_hint "You are a contacts assistant"
When executing with domain "contacts"
Then the system prompt includes the domain-specific hint

#### Scenario: Multi-domain prompt combination
Given domains ["contacts", "email"] are active
When constructing the system prompt
Then hints from both domains are included

---

### Requirement: Routing Performance

The routing overhead MUST NOT significantly impact response times.

#### Scenario: Router timeout limit
Given the router timeout is configured to 10 seconds
When classification is attempted
Then it completes or times out within 10 seconds

#### Scenario: No tools means no routing overhead
Given domain "general" is classified
When the system processes the request
Then tool execution is skipped entirely
And response uses simple chat mode
