# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Build and Development Commands

```bash
# Install dependencies (using poetry)
poetry install

# Install with dev dependencies
poetry install --with dev

# Run all tests
poetry run pytest

# Run a single test file
poetry run pytest tests/test_cli.py

# Run a specific test
poetry run pytest tests/test_cli.py::test_review_command_with_prompt -v

# Type checking
poetry run mypy src/reldo

# Linting
poetry run ruff check src/reldo tests
poetry run ruff format --check src/reldo tests

# Auto-fix lint issues
poetry run ruff check --fix src/reldo tests
poetry run ruff format src/reldo tests
```

## Architecture Overview

Reldo is a Claude-powered code review orchestrator that uses the Claude Agent SDK to coordinate specialized review agents.

### Core Design Pattern: SDK Passthrough

The configuration mirrors `ClaudeAgentOptions` from the Claude Agent SDK. Properties like `prompt`, `allowed_tools`, `mcp_servers`, and `agents` pass directly through to the SDK. This keeps Reldo thin and leverages the SDK's native capabilities.

### Package Structure

```
src/reldo/
├── reldo.py          # Main entry point - thin facade over ReviewService
├── cli.py            # CLI using argparse, delegates to Reldo class
├── defaults.py       # Default prompts and configuration values
├── models/           # Dataclasses (ReviewConfig, ReviewResult, ReviewSession)
├── services/         # Business logic
│   ├── ReviewService.py   # Core orchestration - builds SDK options, runs query()
│   ├── PromptService.py   # Loads prompts from file paths or inline strings
│   └── LoggingService.py  # Session logging to .reldo/sessions/
└── utils/
    └── substitution.py    # Variable substitution (${cwd}, ${env:VAR})
```

### Key Flow

1. `Reldo.review(prompt)` delegates to `ReviewService.review()`
2. `ReviewService` builds `ClaudeAgentOptions` from `ReviewConfig`
3. Prompts are loaded via `PromptService` (file paths resolved relative to cwd)
4. The SDK's `query()` streams messages; text is collected, `ResultMessage` provides usage stats
5. `LoggingService` saves session metadata, results, and transcripts

### Configuration Resolution

The CLI checks for `.reldo/settings.json`, falling back to sensible defaults. The `reldo init` command scaffolds the `.reldo/` directory with `settings.json`, `orchestrator.md`, and a `.gitignore`.

### Async Design

The library is async-native. The CLI wraps async calls with `asyncio.run()`.
