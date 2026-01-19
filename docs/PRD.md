# Reldo - Code Review Orchestrator PRD

> "The librarian has reviewed your code."

## Overview

**Reldo** is a Claude-powered code review orchestrator that coordinates specialized review agents. It uses the Claude Agent SDK's native agent system to delegate reviews to sub-agents (backend-reviewer, frontend-reviewer, etc.) and aggregates their results.

Named after the Varrock Palace librarian in RuneScape who researches and checks things against ancient tomes.

### Architecture

```
reldo review --prompt "Review these files..."
    │
    ▼
┌─────────────────────────────────┐
│  Orchestrator Agent             │
│  (prompt from config)           │
│                                 │
│  Has access to Task tool        │
│  Delegates to sub-agents        │
└─────────────────────────────────┘
    │
    ├──► backend-reviewer    (from config.agents)
    ├──► frontend-reviewer   (from config.agents)
    └──► architecture-reviewer (from config.agents)
    │
    ▼
  Aggregated Result
```

### Design Principle: SDK Passthrough

Reldo's configuration mirrors `ClaudeAgentOptions` from the Claude Agent SDK. Properties like `prompt`, `allowed_tools`, `mcp_servers`, and `agents` pass directly through to the SDK. This keeps Reldo simple and leverages the SDK's native capabilities.

## Problem Statement

When using Claude Code with subagents (backend-engineer, frontend-engineer), the code changes need to be reviewed before being accepted. Currently:

1. The review tool is embedded in a specific project (`devtools/code-reviewer`)
2. It's called via subprocess, adding overhead
3. It can't be easily reused across projects
4. Reviews are stored locally with no central collection for analysis

## Goals

1. **Reusable Package**: Installable via pip, usable across any project with the same tech stack
2. **Library + CLI**: Use as a Python library (no subprocess) OR as a CLI tool
3. **Project-Defined Rules**: The tool finds and uses rules from the project (CLAUDE.md, .claude/rules/), not bundled rules
4. **Review Collection** (Future): Upload reviews to a central server for feedback loop analysis

## Non-Goals (For Now)

- Review server/dashboard implementation
- JSON-based hook configuration (hooks require Python callables, so library-only)
- Support for different tech stacks (focus on Laravel/Vue/TypeScript first)
- IDE integrations

## Key Concepts

### Single `prompt` Parameter

Reldo takes a single `prompt` parameter. The caller constructs the full prompt - Reldo doesn't impose structure.

```python
# Library - you construct the prompt
result = await reldo.review(
    prompt="Review app/Models/User.php for compliance with backend conventions. Context: Added user registration feature."
)

# You decide the format
result = await reldo.review(
    prompt=f"""
    Review these files: {', '.join(files)}

    Task context: {task_description}

    Focus on: type safety, naming conventions
    """
)
```

```bash
# CLI - same principle
reldo review --prompt "Review app/Models/User.php. Context: Added user feature"
reldo review --prompt "$(cat review-request.txt)"
```

**Why single prompt?**
- Unopinionated - Reldo doesn't know about "files" vs "task"
- Flexible - caller decides the format
- Simple - one argument, passed through to SDK
- Consistent with Claude Agent SDK's `query(prompt=...)` interface

## User Stories

### As a SubAgentReviewer hook developer
I want to import reldo as a library and call it directly, so that I don't have subprocess overhead and get typed results.

```python
from reldo import Reldo, ReviewConfig
from pathlib import Path

# Load config with orchestrator and sub-agents defined
config = ReviewConfig.from_file(Path(".claude/reldo.json"))
reldo = Reldo(config=config)

# Single prompt argument - caller constructs the request
result = await reldo.review(
    prompt="Review app/Models/User.php and resources/js/Pages/Login.vue. Context: Added user registration."
)

if not result.structured_output["passed"]:
    return SubagentStopResponse.block(result.text)
```

### As a developer
I want to run code reviews from the command line, so that I can review changes before committing.

```bash
reldo review --prompt "Review app/Models/User.php. Context: Added user feature"
reldo review --prompt "Review $(git diff --name-only HEAD)" --json
```

### As a CI/CD pipeline
I want to run reldo in CI and get a JSON result, so that I can gate merges on review passing.

```bash
reldo review --prompt "Review $(git diff --name-only main)" --json --exit-code
```

### As a team lead
I want to define which reviewers run and what they check, without modifying reldo's code.

```json
{
  "prompt": ".claude/reldo/orchestrator.md",
  "agents": {
    "backend-reviewer": { ... },
    "frontend-reviewer": { ... },
    "security-reviewer": { ... }
  }
}
```

## Functional Requirements

### FR1: Library Interface

```python
from reldo import Reldo, ReviewConfig
from pathlib import Path

# Load config from file (recommended)
config = ReviewConfig.from_file(Path(".claude/reldo.json"))
reldo = Reldo(config=config)

# Or with hooks (programmatic only - see FR9)
from reldo import HookMatcher
reldo = Reldo(
    config=config,
    hooks={
        "PostToolUse": [HookMatcher(hooks=[my_audit_logger])]
    }
)

# Run a review - single prompt argument
result = await reldo.review(
    prompt="Review app/Models/User.php and resources/js/Pages/Login.vue. Context: Added user registration feature."
)

# Result object (always available)
result.text              # str: Raw output
result.input_tokens      # int: Tokens used (input)
result.output_tokens     # int: Tokens used (output)
result.total_tokens      # int: Total tokens
result.total_cost_usd    # float: Estimated cost
result.duration_ms       # int: Review duration

# If output_schema was configured:
result.structured_output # dict | None: Validated JSON matching your schema
```

The config defines agents, tools, MCP servers, and optionally output schema. The `prompt` is entirely up to you. Hooks are optional and only available programmatically. See FR4 for configuration, FR6 for output options, and FR9 for hooks.

### FR2: CLI Interface

```bash
# Basic review - single prompt argument
reldo review --prompt "Review app/Models/User.php for backend conventions"

# With context
reldo review --prompt "Review app/Models/User.php. Context: Added user feature"

# From file or stdin
reldo review --prompt "$(cat review-request.txt)"
echo "Review these files..." | reldo review --prompt -

# With config file
reldo review --prompt "..." --config .claude/reldo.json

# With explicit working directory
reldo review --prompt "..." --cwd /path/to/project

# JSON output (for programmatic use)
reldo review --prompt "..." --json

# Exit code mode (0=pass, 1=fail) for CI
reldo review --prompt "..." --exit-code

# Verbose logging
reldo review --prompt "..." --verbose
```

### FR3: Project Rule Discovery

Reldo discovers rules from the project, in order of precedence:

1. `CLAUDE.md` - Main project instructions
2. `.claude/rules/**/*.md` - Rule files (auto-loaded based on file paths being reviewed)
3. `.claude/settings.json` - Project settings

The tool does NOT bundle rules. It reads what the project defines.

### FR4: Configuration

Reldo's configuration mirrors `ClaudeAgentOptions` from the Claude Agent SDK. The core properties (`prompt`, `allowed_tools`, `mcp_servers`, `agents`) pass directly through to the SDK.

#### Config File (`.claude/reldo.json`)

```json
{
  "prompt": ".claude/reldo/orchestrator.md",
  "allowed_tools": ["Read", "Glob", "Grep", "Bash", "Task"],
  "mcp_servers": {
    "serena": {
      "command": "uvx",
      "args": ["--from", "git+https://github.com/oraios/serena", "serena", "start-mcp-server", "--project", "${cwd}"]
    }
  },
  "agents": {
    "backend-reviewer": {
      "description": "Reviews PHP/Laravel code for conventions and patterns",
      "prompt": ".claude/reldo/agents/backend-reviewer.md",
      "tools": ["Read", "Glob", "Grep", "Bash"]
    },
    "frontend-reviewer": {
      "description": "Reviews Vue/TypeScript code for conventions and patterns",
      "prompt": ".claude/reldo/agents/frontend-reviewer.md",
      "tools": ["Read", "Glob", "Grep", "Bash"]
    },
    "architecture-reviewer": {
      "description": "Reviews code for architectural patterns and cross-cutting concerns",
      "prompt": ".claude/reldo/agents/architecture-reviewer.md",
      "tools": ["Read", "Glob", "Grep"]
    }
  },
  "output_schema": {
    "type": "object",
    "properties": {
      "passed": { "type": "boolean" },
      "reviewers": {
        "type": "object",
        "additionalProperties": { "type": "boolean" }
      },
      "violations": {
        "type": "array",
        "items": {
          "type": "object",
          "properties": {
            "file": { "type": "string" },
            "line": { "type": "number" },
            "message": { "type": "string" },
            "reviewer": { "type": "string" }
          }
        }
      }
    },
    "required": ["passed"]
  },
  "cwd": "/path/to/project",
  "timeout_seconds": 180,
  "model": "claude-sonnet-4-20250514"
}
```

**Note:** `output_schema` is optional. If omitted, Reldo returns raw text output from the orchestrator.

#### SDK Passthrough Properties

These properties map directly to `ClaudeAgentOptions`:

| Config Property | SDK Property | Description |
|-----------------|--------------|-------------|
| `prompt` | `prompt` parameter | Orchestrator prompt (path to file or inline string) |
| `allowed_tools` | `allowed_tools` | Tools available to the orchestrator (include `Task` for sub-agents) |
| `mcp_servers` | `mcp_servers` | MCP server configurations |
| `agents` | `agents` | Sub-agent definitions (maps to `AgentDefinition`) |
| `output_schema` | `outputFormat.schema` | JSON schema for structured output (optional) |

#### Reldo-Specific Properties

These are Reldo conveniences, not direct SDK passthrough:

| Property | Type | Default | Description |
|----------|------|---------|-------------|
| `cwd` | `string` | Current directory | Working directory (also passed to SDK) |
| `timeout_seconds` | `int` | `180` | Maximum review duration |
| `model` | `string` | `"claude-sonnet-4-20250514"` | Claude model to use |
| `logging` | `dict` | `{"enabled": true}` | Logging configuration (see FR7) |

**Note:** Reldo's config is intentionally minimal. Most properties pass directly to the SDK, keeping Reldo unopinionated.

#### Agent Definition Structure

Each agent in the `agents` dict follows the Claude Agent SDK's `AgentDefinition` structure:

```json
{
  "agent-name": {
    "description": "Short description for the Task tool",
    "prompt": "Full prompt or path to .md file",
    "tools": ["Read", "Glob", "Grep", "Bash"]
  }
}
```

The `prompt` field can be:
- A path to a markdown file (e.g., `.claude/reldo/agents/backend-reviewer.md`)
- An inline prompt string

#### CLI Usage

```bash
# Use config file
reldo review --prompt "Review app/Models/User.php" --config .claude/reldo.json

# Override working directory
reldo review --prompt "Review app/Models/User.php" --cwd /path/to/project

# Default: looks for .claude/reldo.json in cwd
reldo review --prompt "Review app/Models/User.php"
```

#### Library Usage

```python
from reldo import Reldo, ReviewConfig
from pathlib import Path

# From config file (recommended)
config = ReviewConfig.from_file(Path(".claude/reldo.json"))
reldo = Reldo(config=config)

# Programmatic configuration
config = ReviewConfig(
    prompt=".claude/reldo/orchestrator.md",
    allowed_tools=["Read", "Glob", "Grep", "Bash", "Task"],
    mcp_servers={
        "serena": {
            "command": "uvx",
            "args": ["--from", "git+https://github.com/oraios/serena", "serena", "start-mcp-server"]
        }
    },
    agents={
        "backend-reviewer": {
            "description": "Reviews PHP/Laravel code",
            "prompt": ".claude/reldo/agents/backend-reviewer.md",
            "tools": ["Read", "Glob", "Grep", "Bash"]
        }
    },
    cwd=Path("/path/to/project"),
    timeout_seconds=180,
)
reldo = Reldo(config=config)
```

#### How Reldo Passes Config to SDK

```python
# Internally, Reldo constructs ClaudeAgentOptions like this:
agent_options = ClaudeAgentOptions(
    allowed_tools=config.allowed_tools,
    mcp_servers=config.mcp_servers,
    agents={
        name: AgentDefinition(
            description=agent["description"],
            prompt=load_prompt(agent["prompt"]),  # Resolves file paths
            tools=agent["tools"]
        )
        for name, agent in config.agents.items()
    },
    cwd=str(config.cwd),
    max_turns=config.max_turns,
)

# Then calls query() with the orchestrator prompt
async for message in query(
    prompt=load_prompt(config.prompt).format(files=files, task=task),
    options=agent_options
):
    ...
```

#### Variable Substitution in Config

Config values support variable substitution:
- `${cwd}` - Replaced with the configured working directory
- `${env:VAR_NAME}` - Replaced with environment variable value

```json
{
  "mcp_servers": {
    "serena": {
      "args": ["--project", "${cwd}"]
    }
  }
}
```

### FR5: Review Context

Reldo uses Claude with access to tools and MCP servers as defined in configuration:

1. **Tools**: Configured via `allowed_tools` (default: Read, Glob, Grep, Bash)
2. **MCP servers**: Configured via `mcp_servers` (e.g., Serena for semantic code navigation)
3. **Project context**: CLAUDE.md, relevant rules based on files being reviewed

### FR6: Review Output

Reldo is unopinionated about output format. The output depends on your configuration:

#### Option A: Raw Text Output (default)

If no `output_schema` is provided, Reldo returns the raw orchestrator output:

```python
result = await reldo.review(prompt="Review app/Models/User.php")

result.text           # str: Raw output from orchestrator
result.input_tokens   # int: Tokens used (input)
result.output_tokens  # int: Tokens used (output)
result.total_cost_usd # float: Estimated cost
result.duration_ms    # int: Review duration
```

The format of `result.text` depends entirely on your orchestrator prompt.

#### Option B: Structured Output (with schema)

If `output_schema` is provided in config, Reldo passes it to the SDK's `outputFormat` option. The SDK validates the output and returns structured JSON:

```json
{
  "output_schema": {
    "type": "object",
    "properties": {
      "passed": { "type": "boolean" },
      "reviewers": {
        "type": "object",
        "additionalProperties": { "type": "boolean" }
      },
      "issues": {
        "type": "array",
        "items": {
          "type": "object",
          "properties": {
            "file": { "type": "string" },
            "line": { "type": "number" },
            "message": { "type": "string" },
            "reviewer": { "type": "string" }
          }
        }
      }
    },
    "required": ["passed", "reviewers", "issues"]
  }
}
```

```python
result = await reldo.review(prompt="Review app/Models/User.php")

result.structured_output  # dict: Validated JSON matching your schema
# {
#   "passed": false,
#   "reviewers": {"backend-reviewer": false, "architecture-reviewer": true},
#   "issues": [{"file": "...", "line": 42, "message": "...", "reviewer": "..."}]
# }

result.text              # str: Raw text (also available)
result.input_tokens      # int: Tokens used
result.total_cost_usd    # float: Estimated cost
```

#### How Reldo Passes Output Schema to SDK

```python
# If output_schema is configured:
options = ClaudeAgentOptions(
    # ... other options ...
    output_format={
        "type": "json_schema",
        "schema": config.output_schema
    }
)
```

The schema is defined by YOU in config. Reldo just passes it through. This keeps Reldo unopinionated - you decide what structure you want back.

### FR7: Built-in Logging

Reldo automatically logs review sessions for debugging and analysis. This is built-in, not configurable via handlers.

#### Log Location

```
.reldo/
└── sessions/
    └── 2024-01-15T10-30-00-{session-id}/
        ├── session.json      # Metadata (prompt, config, timestamps)
        ├── result.json       # Review result
        └── transcript.log    # Full agent transcript (optional, verbose mode)
```

#### Configuration

```json
{
  "logging": {
    "enabled": true,
    "output_dir": ".reldo/sessions",
    "verbose": false
  }
}
```

| Option | Default | Description |
|--------|---------|-------------|
| `enabled` | `true` | Whether to log sessions |
| `output_dir` | `.reldo/sessions` | Where to store logs |
| `verbose` | `false` | Include full agent transcript |

#### CLI Flags

```bash
reldo review --prompt "..." --verbose    # Enable verbose logging
reldo review --prompt "..." --no-log     # Disable logging entirely
```

### FR8: Orchestrator Prompt

The `prompt` config property defines the orchestrator's behavior. This is the system prompt that controls how Reldo coordinates reviews.

#### Prompt Structure

Based on [Claude Agent SDK best practices](https://www.anthropic.com/engineering/building-agents-with-the-claude-agent-sdk), prompts should use XML tags for clear sections:

| Tag | Purpose |
|-----|---------|
| `<role>` | Defines what the agent is and how it behaves (including output format) |
| `<instructions>` | Step-by-step instructions for the task |

Keep prompts focused (300-600 tokens). Each agent should have a single job.

#### Example Orchestrator Prompt

`.claude/reldo/orchestrator.md`:

```markdown
# Code Review Orchestrator

<role>
You coordinate code reviews by delegating to specialized reviewer agents.
You analyze files, invoke the appropriate reviewers in parallel, aggregate
their results, and return a structured result with overall pass/fail status,
per-reviewer outcomes, and combined violations.
</role>

<instructions>
1. Analyze the provided files to determine which reviewers apply:
   - `*.php` (not in e2e/) → backend-reviewer
   - `*.vue`, `*.ts`, `*.tsx` (not in e2e/) → frontend-reviewer
   - All code files → architecture-reviewer

2. Invoke appropriate reviewers using the Task tool:
   - Run reviewers in PARALLEL (multiple Task calls in one message)
   - Pass the relevant files to each reviewer

3. Aggregate results:
   - PASS only if ALL reviewers pass
   - Collect all violations from all reviewers
   - Return the combined result
</instructions>
```

#### Example Sub-Agent Prompt

`.claude/reldo/agents/backend-reviewer.md`:

```markdown
# Backend Reviewer

<role>
You review PHP/Laravel code for compliance with backend conventions.
You read project rules, run linters, check code against conventions, and
report violations with file paths and line numbers. Return STATUS: PASS
if no issues, STATUS: FAIL with violations list if issues found.
</role>

<instructions>
1. Read relevant rules from `.claude/rules/techstack/backend/`
2. Run `lint:php` on the files to catch type errors
3. Check code against the rules you read
4. Report any violations found
</instructions>
```

#### Prompt Resolution

The `prompt` field (for both orchestrator and agents) can be:
- A path to a `.md` file (resolved relative to `cwd`)
- An inline string

Reldo resolves file paths and loads the content before passing to the SDK.

### FR9: Hooks (Programmatic Only)

Hooks allow library users to tap into Reldo's lifecycle events. **Hooks are only available when using Reldo programmatically** - they cannot be defined in JSON config (Python callables can't be serialized).

#### Why No JSON Hooks?

The Claude Agent SDK requires hooks to be Python async callables. There's no way to define a Python function in JSON. This is a deliberate trade-off:

- **Library users**: Full hook support via Python callables
- **CLI/JSON users**: Built-in logging only (FR7)

#### Available Hook Types

Reldo passes hooks through to the Claude Agent SDK. Available hooks:

| Hook | When | Use Case |
|------|------|----------|
| `PreToolUse` | Before tool execution | Block dangerous operations, modify inputs |
| `PostToolUse` | After tool execution | Audit logging, metrics collection |
| `SubagentStop` | When sub-agent completes | Intercept reviewer results |
| `Stop` | When orchestrator completes | Final processing, notifications |

#### Hook Signature

```python
from typing import Any

async def my_hook(
    input_data: dict[str, Any],
    tool_use_id: str,
    context: dict[str, Any]
) -> dict[str, Any] | None:
    """
    Args:
        input_data: Hook-specific data (tool_name, tool_input, etc.)
        tool_use_id: Unique identifier for this tool invocation
        context: Additional context (session_id, cwd, etc.)

    Returns:
        None to allow, or dict with decision/reason to block/modify
    """
    # Example: log all tool calls
    print(f"Tool called: {input_data.get('tool_name')}")
    return None  # Allow
```

#### Library Usage

```python
from reldo import Reldo, ReviewConfig, HookMatcher
from pathlib import Path

async def audit_logger(input_data, tool_use_id, context):
    """Log all tool calls to external system."""
    await send_to_audit_service(input_data)
    return None

async def block_dangerous_commands(input_data, tool_use_id, context):
    """Block rm -rf and similar."""
    if input_data.get("tool_name") == "Bash":
        command = input_data.get("tool_input", {}).get("command", "")
        if "rm -rf" in command:
            return {"decision": "block", "reason": "Dangerous command blocked"}
    return None

config = ReviewConfig.from_file(Path(".claude/reldo.json"))
reldo = Reldo(
    config=config,
    hooks={
        "PreToolUse": [
            HookMatcher(
                matcher="Bash",  # Only for Bash tool
                hooks=[block_dangerous_commands]
            )
        ],
        "PostToolUse": [
            HookMatcher(hooks=[audit_logger])  # All tools
        ]
    }
)

result = await reldo.review(prompt="Review app/Models/User.php")
```

#### Hook Return Values

```python
# Allow (default)
return None

# Block execution
return {
    "decision": "block",
    "reason": "Explanation shown to user"
}

# Modify tool input (PreToolUse only)
return {
    "hookSpecificOutput": {
        "updatedInput": {"modified": "value"}
    }
}

# Inject context into conversation
return {
    "systemMessage": "Additional context for Claude to see"
}
```

#### CLI Without Hooks

CLI users don't have hook support - they get built-in logging (FR7) only:

```bash
# No --hooks flag - hooks require Python code
reldo review --prompt "Review app/Models/User.php" --verbose
```

If you need hooks via CLI, write a thin Python wrapper that configures hooks and calls Reldo programmatically.


## Technical Requirements

### TR1: Package Structure

```
reldo/
├── src/reldo/
│   ├── __init__.py                 # Exports: Reldo, ReviewResult, ReviewConfig, HookMatcher
│   ├── reldo.py                    # Main Reldo class (thin facade over services)
│   ├── cli.py                      # CLI entry point (thin wrapper around library)
│   │
│   ├── models/                     # Dataclasses and data structures
│   │   ├── __init__.py
│   │   ├── ReviewConfig.py         # Configuration dataclass
│   │   ├── ReviewResult.py         # Result dataclass with issues, tokens, cost
│   │   ├── ReviewIssue.py          # Individual issue dataclass
│   │   └── ReviewSession.py        # Session metadata dataclass
│   │
│   ├── services/                   # Core business logic
│   │   ├── __init__.py
│   │   ├── ReviewService.py        # Main review orchestration (calls Claude)
│   │   ├── SessionService.py       # Session creation, saving, loading
│   │   ├── ContextService.py       # Project context/rule discovery
│   │   ├── PromptService.py        # Prompt template loading and rendering
│   │   └── LoggingService.py       # Session logging to disk
│
├── prompts/
│   └── default.md                  # Default review prompt template
│
├── pyproject.toml
└── README.md
```

#### Directory Responsibilities

| Directory | Responsibility |
|-----------|----------------|
| `models/` | Pure dataclasses with no business logic. Serializable to/from JSON. |
| `services/` | Business logic and orchestration. Each service has a single responsibility. |
| `prompts/` | Bundled prompt templates. Projects can override via config. |

#### Key Classes

| Class | Location | Responsibility |
|-------|----------|----------------|
| `Reldo` | `reldo.py` | Main entry point. Thin facade that delegates to services. |
| `ReviewConfig` | `models/` | Configuration. Loaded from file or constructed programmatically. |
| `ReviewResult` | `models/` | Review output. Contains passed, feedback, issues, usage stats. |
| `ReviewService` | `services/` | Core review logic. Calls Claude with tools and MCP. |
| `SessionService` | `services/` | Manages review sessions (create, save, load). |
| `ContextService` | `services/` | Discovers project rules (CLAUDE.md, .claude/rules/). |
| `PromptService` | `services/` | Loads and renders prompt templates. |
| `LoggingService` | `services/` | Session logging to disk (JSON/transcript files). |
| `HookMatcher` | Re-export from SDK | Matches hooks to tools by regex pattern. |

### TR2: Dependencies

```toml
[project]
dependencies = [
    "claude-agent-sdk>=0.1.0",  # Claude API with tool use
]

[project.optional-dependencies]
mcp = [
    "mcp>=1.0.0",  # For Serena MCP support
]
```

### TR3: Python Version

- Minimum: Python 3.11
- Target: Python 3.12+

### TR4: Async Design

The library is async-native (uses claude-agent-sdk which is async):

```python
# Library is async
result = await reldo.review(prompt="...")

# CLI handles the async internally
# reldo review --prompt "..."  (sync CLI, async internals)
```

## Migration Path

### From Current code-reviewer

1. Extract core logic from `devtools/code-reviewer/` into `reldo` package
2. Update `SubAgentReviewer` to use `reldo` as library instead of subprocess
3. Keep `devtools/code-reviewer/` as thin wrapper during transition (optional)

### Integration with SubAgentReviewer

```python
# Before (subprocess)
self._reviewer_service = ReviewerService(
    tool_path=self._paths.devtools_dir / "code-reviewer" / "cli.py",
    timeout_seconds=90,
    project_dir=self._paths.project_root,
)
result = self._reviewer_service.review(files=file_paths, original_task=task)

# After (library)
from reldo import Reldo, ReviewConfig

config = ReviewConfig.from_file(self._paths.project_root / ".claude" / "reldo.json")
self._reldo = Reldo(config=config)

# Caller constructs the prompt
prompt = f"Review {', '.join(file_paths)}. Context: {task}"
result = await self._reldo.review(prompt=prompt)
```

## Success Metrics

1. **Adoption**: Used in 3+ projects within 1 month
2. **Performance**: <5s average review time for typical changes
3. **Reliability**: <1% error rate in production use
4. **Developer Experience**: Can be installed and running in <5 minutes

## Open Questions

1. ~~**Prompt customization**: Should projects be able to override the review prompt entirely, or just provide additional context?~~ **Resolved**: Yes, full prompt override via `prompt` config. The prompt is the orchestrator that controls everything.

2. ~~**Architecture**: Single smart reviewer vs multiple specialized reviewers?~~ **Resolved**: Orchestrator pattern - one orchestrator delegates to specialized sub-agents defined in config via SDK passthrough.

3. ~~**Agent reuse**: Should reldo reuse agents from `.claude/agents/`?~~ **Deferred**: For now, agents are defined inline in config. Reusing existing agent definitions can be added later.

4. **Rule filtering**: Should reldo auto-detect which rules apply based on files being reviewed (like Claude Code does with frontmatter paths)?

5. **Caching**: Should reldo cache anything between reviews (e.g., project context)?

6. **Parallel execution**: The orchestrator prompt instructs parallel reviewer invocation, but is this actually supported by the SDK's Task tool? Need to verify.

## Appendix

### A: Name Origin

Reldo is the librarian in Varrock Palace in RuneScape (OSRS/RS3). He:
- Researches and checks things against ancient tomes (rules)
- Tells you what's wrong and points you to resources
- Knows the lore and conventions of the world

Perfect metaphor for a code review tool that checks code against project conventions.

### B: Related Packages

- `claude-hook-utils` - Hook infrastructure (SubagentStart/Stop handling)
- `claude-agent-sdk` - Claude API with tool use

### C: Repository Location

Standalone repository: `reldo` → Published to PyPI as `reldo`
