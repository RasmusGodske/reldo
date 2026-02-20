# Changelog

All notable changes to Reldo will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.6.1] - 2026-02-20

### Fixed

- **Fix invisible output when run from Claude Code's Bash tool** - The inner Claude Code CLI subprocess was deleting the parent's task output file during initialization, causing all output (including pre-SDK prints) to disappear. Fixed by using an isolated temporary directory as the inner CLI's working directory, with the real project directory added via `--add-dir`.

### Added

- **Lightweight progress reporting** - New `on_progress` callback on `Reldo.review()` emits a handful of status lines (agent connected, turn count, tool calls) so callers can see the review is progressing. CLI outputs these to stderr in non-JSON mode. Uses exponential backoff to stay under 4 lines total.

## [0.5.1] - 2026-02-18

### Fixed

- **Only output final result** - The `on_text` callback now receives only the final review result, not intermediate agent messages (orchestrator thinking, diff context, tool calls). This keeps CLI output clean and focused on the actual review.

## [0.5.0] - 2026-02-18

### Added

- **Streaming output** - CLI now streams text to stdout as the review progresses instead of waiting until completion
  - New `on_text` callback parameter on `Reldo.review()` and `ReviewService.review()` for programmatic streaming
  - CLI passes a stdout writer callback in non-JSON mode, so users see output in real-time
  - JSON mode (`--json`) still buffers and outputs the complete result at the end
  - Falls back to printing the full result if no text was streamed (e.g. result came only from `ResultMessage.result`)

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
