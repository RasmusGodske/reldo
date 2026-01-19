# Reldo

> "The librarian has reviewed your code."

A Claude-powered code review orchestrator that coordinates specialized review agents.

Named after the Varrock Palace librarian in RuneScape who researches and checks things against ancient tomes.

## Installation

```bash
# From PyPI
pip install reldo

# Or with uv
uv tool install reldo
```

## Usage

### As a Library

```python
from reldo import Reldo, ReviewConfig
from pathlib import Path

# Load config from file
config = ReviewConfig.from_file(Path(".claude/reldo.json"))
reldo = Reldo(config=config)

# Run a review - single prompt argument
result = await reldo.review(
    prompt="Review app/Models/User.php for backend conventions. Context: Added user registration."
)

print(result.text)
print(f"Tokens used: {result.total_tokens}")
```

### As a CLI

```bash
# Basic review
reldo review --prompt "Review app/Models/User.php"

# With JSON output (for CI)
reldo review --prompt "Review $(git diff --name-only HEAD)" --json --exit-code

# With custom config
reldo review --prompt "..." --config .claude/reldo.json
```

## Configuration

Create `.claude/reldo.json`:

```json
{
  "prompt": ".claude/reldo/orchestrator.md",
  "allowed_tools": ["Read", "Glob", "Grep", "Bash", "Task"],
  "mcp_servers": {
    "my-server": {
      "command": "node",
      "args": ["./mcp-server.js"]
    }
  },
  "agents": {
    "backend-reviewer": {
      "description": "Reviews PHP/Laravel code",
      "prompt": ".claude/reldo/agents/backend-reviewer.md",
      "tools": ["Read", "Glob", "Grep"]
    },
    "frontend-reviewer": {
      "description": "Reviews Vue/TypeScript code",
      "prompt": ".claude/reldo/agents/frontend-reviewer.md"
    }
  },
  "model": "claude-sonnet-4-20250514",
  "timeout_seconds": 300
}
```

### Configuration Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `prompt` | string | required | Path to orchestrator prompt file |
| `allowed_tools` | string[] | `["Read", "Glob", "Grep", "Bash", "Task"]` | Tools available to the orchestrator |
| `mcp_servers` | object | `{}` | MCP server configurations |
| `agents` | object | `{}` | Sub-agent definitions |
| `model` | string | `"claude-sonnet-4-20250514"` | Claude model to use |
| `timeout_seconds` | int | `180` | Maximum review duration |
| `cwd` | string | current directory | Working directory |
| `logging` | object | `{"enabled": true, ...}` | Logging configuration |

### Agent Definition

Each agent in the `agents` object has the following properties:

| Property | Type | Required | Description |
|----------|------|----------|-------------|
| `description` | string | yes | Description of when to use this agent |
| `prompt` | string | yes | Path to agent prompt file |
| `tools` | string[] | no | Tools available to this agent. **If omitted, inherits all tools from the orchestrator** |
| `model` | string | no | Model override (`"sonnet"`, `"opus"`, `"haiku"`, or `"inherit"`) |

#### Tool Inheritance

If you omit the `tools` property from an agent definition, it inherits all tools from the parent orchestrator, including any MCP server tools:

```json
{
  "allowed_tools": ["Read", "Glob", "Grep", "Bash", "Task"],
  "mcp_servers": {
    "laravel-boost": {
      "command": "php",
      "args": ["artisan", "boost:mcp"]
    }
  },
  "agents": {
    "full-access-reviewer": {
      "description": "Has access to all orchestrator tools + MCP",
      "prompt": ".claude/agents/full-reviewer.md"
    },
    "limited-reviewer": {
      "description": "Only has read access",
      "prompt": ".claude/agents/limited-reviewer.md",
      "tools": ["Read", "Glob", "Grep"]
    }
  }
}
```

### MCP Server Configuration

Reldo supports MCP (Model Context Protocol) servers for extended functionality:

```json
{
  "mcp_servers": {
    "server-name": {
      "command": "executable",
      "args": ["arg1", "arg2"],
      "env": {
        "ENV_VAR": "value"
      }
    }
  }
}
```

#### Variable Substitution

MCP server configurations support variable substitution:

- `${cwd}` - Replaced with the working directory

```json
{
  "mcp_servers": {
    "serena": {
      "command": "uvx",
      "args": ["serena", "start-mcp-server", "--project", "${cwd}"]
    }
  }
}
```

## CLI Reference

```bash
reldo review --prompt "..."     # Review prompt
             --config PATH      # Config file (default: .claude/reldo.json)
             --cwd PATH         # Working directory
             --json             # Output as JSON
             --verbose          # Verbose logging
             --no-log           # Disable session logging
             --exit-code        # Exit 1 if review fails (for CI)
```

## Documentation

- [Product Requirements Document](docs/PRD.md)

## License

MIT
