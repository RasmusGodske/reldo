# Changelog

All notable changes to Reldo will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-01-19

### Added

- Initial release of Reldo - Claude-powered code review orchestrator
- **Core Library**
  - `Reldo` class with `review(prompt)` async method
  - `ReviewConfig` dataclass for configuration
  - `ReviewResult` dataclass for review outcomes
  - Config loading from JSON files via `ReviewConfig.from_file()`
  - Variable substitution in config (`${cwd}`, `${env:VAR_NAME}`)
- **Claude Agent SDK Integration**
  - Direct passthrough of config properties to SDK
  - Support for custom agents via `agents` config property
  - Programmatic hooks support via `Reldo(config, hooks=...)` constructor
- **CLI Interface**
  - `reldo review --prompt "..."` command
  - JSON output mode (`--json`) for CI integration
  - Exit code support (`--exit-code`) for CI pipelines
  - Stdin prompt support (`--prompt -`)
  - Verbose mode (`--verbose`)
  - Session logging control (`--no-log`)
- **Built-in Logging**
  - Automatic session logging to timestamped directories
  - Session metadata in `session.json`
  - Review results in `result.json`
  - Full transcripts in `transcript.log` (verbose mode)
- **Example Configuration**
  - Orchestrator prompt template
  - Backend reviewer agent (PHP/Laravel)
  - Frontend reviewer agent (Vue/TypeScript)

### Dependencies

- claude-code-sdk >= 0.1.10
- Python >= 3.12
