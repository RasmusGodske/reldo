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

Create `.reldo/settings.json`:

```json
{
  "prompt": ".reldo/orchestrator.md",
  "allowed_tools": ["Read", "Glob", "Grep", "Bash", "Task"],
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
| `setting_sources` | string[] | `["project"]` | Where to discover agents from (see [Agent Discovery](#agent-discovery)) |
| `agents` | object | `{}` | Additional agent definitions (merged with discovered agents) |
| `model` | string | `"claude-sonnet-4-20250514"` | Claude model to use |
| `timeout_seconds` | int | `180` | Maximum review duration |
| `cwd` | string | current directory | Working directory |
| `logging` | object | `{"enabled": true, ...}` | Logging configuration |

## Agent Discovery

Reldo automatically discovers agents from your project's `.claude/agents/` directory. This means you can use the **same agents** that Claude Code uses - no duplication needed.

### How It Works

By default, `setting_sources` is set to `["project"]`, which tells the Claude Agent SDK to load agents from `.claude/agents/`. These agents are immediately available to your review orchestrator.

```
your-project/
├── .claude/
│   └── agents/
│       ├── backend-reviewer.md      # ← Auto-discovered
│       ├── frontend-reviewer.md     # ← Auto-discovered
│       └── architecture-reviewer.md # ← Auto-discovered
└── .reldo/
    └── settings.json                # ← No agent config needed!
```

### Agent File Format

Agents in `.claude/agents/` use markdown with YAML frontmatter:

```markdown
---
name: backend-reviewer
description: Reviews PHP/Laravel code for conventions and patterns
model: inherit
---

# Backend Reviewer

You review PHP/Laravel code for best practices...
```

### Controlling Agent Discovery

The `setting_sources` option controls where agents are loaded from:

| Value | Behavior |
|-------|----------|
| `["project"]` (default) | Loads agents from `.claude/agents/` |
| `["project", "local"]` | Also includes local settings overrides |
| `["user", "project", "local"]` | Includes user-global agents too |
| `[]` | Disables auto-discovery (only explicit agents) |

### Merging Explicit Agents

If you define agents in `.reldo/settings.json`, they are **merged** with discovered agents:

```json
{
  "prompt": ".reldo/orchestrator.md",
  "agents": {
    "reldo-specific-agent": {
      "description": "An agent only for reldo reviews",
      "prompt": ".reldo/agents/special.md"
    }
  }
}
```

Result: Both `.claude/agents/*` AND `reldo-specific-agent` are available.

### Disabling Auto-Discovery

To use **only** explicitly defined agents:

```json
{
  "prompt": ".reldo/orchestrator.md",
  "setting_sources": [],
  "agents": {
    "my-reviewer": {
      "description": "Custom reviewer",
      "prompt": ".reldo/agents/my-reviewer.md"
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
