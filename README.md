# Reldo

> "The librarian has reviewed your code."

A Claude-powered code review orchestrator that coordinates specialized review agents.

Named after the Varrock Palace librarian in RuneScape who researches and checks things against ancient tomes.

## Installation

```bash
# From source (development)
pip install -e .

# Or with uv
uv pip install -e .
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
  "agents": {
    "backend-reviewer": {
      "description": "Reviews PHP/Laravel code",
      "prompt": ".claude/reldo/agents/backend-reviewer.md",
      "tools": ["Read", "Glob", "Grep", "Bash"]
    },
    "frontend-reviewer": {
      "description": "Reviews Vue/TypeScript code",
      "prompt": ".claude/reldo/agents/frontend-reviewer.md",
      "tools": ["Read", "Glob", "Grep", "Bash"]
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
