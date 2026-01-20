"""Default configuration and prompts for Reldo."""

# Default orchestrator prompt used when no config file exists
DEFAULT_ORCHESTRATOR_PROMPT = """# Code Review

You are a code reviewer. Review the code changes described in the prompt.

## Guidelines

1. **Read the files** mentioned in the prompt using the Read tool
2. **Check for issues** like:
   - Bugs or logic errors
   - Security vulnerabilities
   - Performance problems
   - Code style inconsistencies
   - Missing error handling
3. **Provide feedback** with specific file paths and line numbers

## Output Format

```
## Review Summary

### Issues Found
- **[file:line]** [severity] - Description of issue

### Suggestions
- [Optional improvements]

## Status

STATUS: PASS|FAIL

[PASS if no critical issues, FAIL if there are bugs or security issues]
```

Be concise and actionable. Focus on real problems, not style nitpicks.
"""

# Default configuration values (for init command)
DEFAULT_CONFIG = {
    "prompt": ".reldo/orchestrator.md",
    "allowed_tools": ["Read", "Glob", "Grep", "Bash", "Task"],
    "mcp_servers": {},
    "agents": {},
    "timeout_seconds": 180,
    "model": "claude-sonnet-4-20250514",
    "logging": {
        "enabled": True,
        "output_dir": ".reldo",
        "verbose": False,
    },
}

# Default .gitignore content for .reldo directory
DEFAULT_GITIGNORE = """# Reldo session logs (auto-generated)
sessions/
"""

# Default config file path
DEFAULT_CONFIG_PATH = ".reldo/settings.json"

# Default orchestrator prompt file path (checked before using embedded default)
DEFAULT_ORCHESTRATOR_PATH = ".reldo/orchestrator.md"

# Default agents directory (legacy - prefer .claude/agents via setting_sources)
DEFAULT_AGENTS_DIR = ".reldo/agents"

# Default setting_sources - enables automatic discovery of agents from .claude/agents/
# See: https://docs.anthropic.com/en/docs/claude-code/agents
DEFAULT_SETTING_SOURCES: list[str] = ["project"]
