# astrbot_plugin_DynamicPersona

AstrBot Dynamic Persona Plugin is an advanced extension designed to automatically switch language model personas and providers based on user intent analysis.

## Core Capabilities

- **Semantic Routing Engine**: Utilizes a Selector LLM to analyze user messages and map their semantic intent to the most appropriate persona from a configured candidate list.
- **Cross-Provider Dispatch (V2 Architecture)**: Natively intercepts AstrBot's provider instantiation pipeline (`on_waiting_llm_request`). Supports routing requests to entirely different LLM providers and specific models based on the selected persona, allowing seamless switching between local models (e.g., Ollama) and cloud APIs (e.g., OpenAI).
- **Session-Aware Caching**: Implements a configurable LRU-style cache per user session to minimize redundant Selector LLM invocations and reduce API cost and latency.
- **Native Context Preservation**: Gracefully skips dynamic routing if the user's current AstrBot conversation has an explicitly bound native persona, preventing conflicts.
- **Fault-Tolerant Fallback**: Automatically degrades to the root persona rule if the Selector LLM fails to return a valid JSON format or encounters network errors.

## Configuration Guide

Navigate to AstrBot WebUI -> Plugin Management -> Dynamic Persona -> Plugin Configuration to adjust the following settings:

### Global Settings

| Strategy | Description | Default |
|----------|-------------|---------|
| `enabled` | Master switch for the dynamic persona routing gateway. | true |
| `session_filter_mode` | Mode for access control: `disabled` (allow all), `whitelist`, or `blacklist`. | disabled |
| `session_filter_list` | List of Group IDs or Sender IDs subject to the access control mode. | [] |
| `selector_provider_id` | Dedicated provider for the Selector LLM. Highly recommended to specify a fast, low-latency model. If left empty, inherits the session's primary provider. | Empty |
| `inject_mode` | System prompt injection strategy: `replace` (overwrite) or `prepend` (append before existing prompt). | replace |
| `cache_ttl` | Number of consecutive messages to reuse a selected persona within the same session before re-evaluating. Set to 0 to force evaluation on every message. | 3 |
| `selector_prompt_extra` | Supplementary instructions appended to the Selector LLM system prompt for fine-tuning routing behavior. | Empty |

### Persona Rules (`persona_rules`)

Define at least two routing scenarios for the plugin to activate.

| Field | Description |
|-------|-------------|
| `rule_enabled` | Toggles the active state of the specific routing rule. |
| `persona_id` | The target AstrBot persona to apply. Selectable via the native dropdown interface. |
| `provider_id` | (Cross-Provider Feature) The dedicated LLM provider and model for this persona. Powered by AstrBot's native `select_providers` component. Leave empty to use the session's default model. |
| `persona_desc` | A concise definition of the persona's role and capabilities to inform the Selector LLM. |
| `scenario_desc` | A precise natural language description defining the triggering conditions for this persona. |

## Architectural Workflow

1. **Pre-Flight Hook (`on_waiting_llm_request`)**:
   - Evaluates master toggles, session filters, and native persona bindings.
   - Evaluates session cache validity.
   - Dispatches user message to Selector LLM for intent analysis.
   - Computes target `persona_id` and `provider_id`.
   - Mutates `event.set_extra("selected_provider")` and `event.set_extra("selected_model")` to force AstrBot framework to allocate the specified model backend.

2. **Injection Hook (`on_llm_request`)**:
   - Retrieves the finalized `system_prompt` from AstrBot's PersonaManager.
   - Applies the selected `inject_mode` to mutate the outgoing ProviderRequest.

## Administration Commands

The following commands require AstrBot SuperAdmin privileges.

| Command | Action |
|---------|--------|
| `/dp status` | Prints the gateway status, cache depth, and active routing rules for the current session. |
| `/dp personas` | Fetches and lists all registered persona templates across the AstrBot environment. |
| `/dp reload` | Purges the memory cache for all sessions, forcing a global re-evaluation on the next request. |
| `/dp enable` | Activates the core routing gateway. |
| `/dp disable` | Deactivates the gateway. Does not affect native AstrBot behavior. |
| `/dp sessionid` | Outputs the current tunnel identification metrics (Group ID, User ID, Session ID) for whitelist configuring. |

## System Requirements

- Minimum AstrBot Version: **v4.5.7** (Requires `event.set_extra` and modernized `ProviderRequest` lifecycle hooks).

## Version History

- **v2.0.0 (Current)**: Overhauled routing architecture. Implemented Pre-Flight Provider Interception allowing true engine-wide cross-provider scaling. Supported dual parsing for native `select_providers` component.
- **v1.3.0**: Initial Release. Basic semantic switching and cache management.
