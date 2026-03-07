# Agents

In Agent Firewall, an **Agent** is a distinct entity with its own identity, configuration, capabilities, and memory scope. Agents are defined in the configuration file (e.g., `agent-shield.json`) and act as the primary actors for processing messages and executing tools.

## Configuration

Agents are configured under the `agents` key in the configuration file. You can define a default configuration applied to all agents, and a list of specific agent definitions.

**Schema Reference:** [src/config/zod-schema.ts](src/config/zod-schema.ts)

### Example Configuration

```json
{
  "agents": {
    "defaults": {
      "model": {
        "primary": "anthropic/claude-3-5-sonnet-20240620",
        "fallbacks": ["openai/gpt-4o"]
      },
      "sandbox": {
        "mode": "docker",
        "docker": { "image": "node:22-alpine" }
      }
    },
    "list": [
      {
        "id": "main",
        "default": true,
        "identity": {
          "name": "Shield Guardian",
          "emoji": "🛡️",
          "theme": "blue"
        },
        "skills": {
          "include": ["*"],
          "exclude": ["dangerous-tool"]
        }
      },
      {
        "id": "coder",
        "identity": { "name": "Code Assistant", "emoji": "💻" },
        "model": { "primary": "anthropic/claude-3-opus-20240229" },
        "workspace": "~/projects/agent-workspace"
      }
    ]
  }
}
```

## Agent Properties

Each agent entry in `agents.list` supports the following properties (see `AgentEntry` in [src/agents/agent-scope.ts](src/agents/agent-scope.ts)):

| Property       | Description                                                                         |
| :------------- | :---------------------------------------------------------------------------------- |
| `id`           | Unique identifier for the agent (e.g., "main", "coder"). Normalized to lowercase.   |
| `default`      | Boolean. If true, this agent handles requests that don't match other routing rules. |
| `identity`     | UI appearance settings (`name`, `emoji`, `avatar`, `theme`).                        |
| `model`        | Overrides the default model configuration (`primary`, `fallbacks`).                 |
| `skills`       | Configures available skills (`include`, `exclude` patterns).                        |
| `sandbox`      | Defines the execution environment (Docker, Browser, or Local).                      |
| `workspace`    | Custom workspace directory for file operations.                                     |
| `memorySearch` | Vector database search settings for this agent.                                     |
| `subagents`    | Configuration for sub-agent delegation.                                             |

## Routing & Resolution

Incoming messages are routed to a specific agent based on the session context or explicit bindings.

- **Resolution Logic:** `resolveSessionAgentId` in [src/agents/agent-scope.ts](src/agents/agent-scope.ts) determines the target agent.
- **Session Keys:** Sessions are namespaced by agent ID (e.g., `agent:coder:telegram:12345`).
- **Bindings:** You can bind specific channels or users to specific agents in the `bindings` configuration section.

## Architecture

The agent implementation is located in `src/agents/`:

- **Scope:** [src/agents/agent-scope.ts](src/agents/agent-scope.ts) handles configuration resolution and defaults.
- **Context:** [src/agents/context.ts](src/agents/context.ts) manages the runtime context for an agent's execution.
- **Sandbox:** [src/agents/sandbox.ts](src/agents/sandbox.ts) manages isolated execution environments.
- **Identity:** [src/agents/identity.ts](src/agents/identity.ts) handles agent persona and presentation.

## Defaults

Default settings are defined in [src/agents/defaults.ts](src/agents/defaults.ts):

- **Default Provider:** `anthropic`
- **Default Model:** `claude-opus-4-6`
- **Context Window:** 200,000 tokens (conservative fallback)

## Best Practices

1. **Role Separation:** Define separate agents for distinct responsibilities (e.g., "Reviewer", "Developer") to specialize prompts and tools.
2. **Sandboxing:** Always use Docker sandboxes (`sandbox.mode = "docker"`) for agents with filesystem or shell access to ensure isolation.
3. **Workspace Isolation:** Assign distinct `workspace` paths to agents to prevent accidental file overwrites between concurrent sessions.
