"""CLI entry point for Reldo."""

import argparse
import asyncio
import json
import sys
from pathlib import Path

from . import __version__
from .defaults import (
    DEFAULT_CONFIG,
    DEFAULT_CONFIG_PATH,
    DEFAULT_GITIGNORE,
    DEFAULT_ORCHESTRATOR_PATH,
    DEFAULT_ORCHESTRATOR_PROMPT,
)
from .models.ReviewConfig import ReviewConfig
from .models.ReviewResult import ReviewResult
from .reldo import Reldo


def create_parser() -> argparse.ArgumentParser:
    """Create the argument parser for the CLI.

    Returns:
        Configured ArgumentParser.
    """
    parser = argparse.ArgumentParser(
        prog="reldo",
        description="Claude-powered code review orchestrator",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )

    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # review command
    review_parser = subparsers.add_parser(
        "review",
        help="Run a code review",
        usage="%(prog)s PROMPT [options]",
    )
    review_parser.add_argument(
        "prompt",
        metavar="PROMPT",
        help="Review prompt (use '-' for stdin)",
    )
    review_parser.add_argument(
        "--config",
        default=None,
        help=f"Path to config file (default: {DEFAULT_CONFIG_PATH})",
    )
    review_parser.add_argument(
        "--cwd",
        help="Working directory (default: current directory)",
    )
    review_parser.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Output result as JSON",
    )
    review_parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging",
    )
    review_parser.add_argument(
        "--no-log",
        action="store_true",
        dest="no_log",
        help="Disable session logging",
    )
    review_parser.add_argument(
        "--exit-code",
        action="store_true",
        dest="exit_code",
        help="Exit with code 1 if review fails (for CI)",
    )

    # init command
    init_parser = subparsers.add_parser(
        "init",
        help="Initialize a new .reldo directory with default configuration",
    )
    init_parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing files",
    )

    return parser


def read_prompt(prompt_arg: str) -> str:
    """Read prompt from argument or stdin.

    Args:
        prompt_arg: The prompt argument (or '-' for stdin).

    Returns:
        The prompt text.
    """
    if prompt_arg == "-":
        return sys.stdin.read().strip()
    return prompt_arg


def load_config(config_path: str | None, cwd: str | None) -> ReviewConfig:
    """Load configuration from file or use defaults.

    Args:
        config_path: Path to config file, or None to use default.
        cwd: Optional working directory override.

    Returns:
        ReviewConfig instance.

    Raises:
        json.JSONDecodeError: If config file exists but isn't valid JSON.
    """
    working_dir = Path(cwd) if cwd else Path.cwd()

    # Determine config file path
    if config_path:
        path = Path(config_path)
        if not path.is_absolute():
            path = working_dir / config_path
    else:
        path = working_dir / DEFAULT_CONFIG_PATH

    # Try to load config file if it exists
    if path.exists():
        config = ReviewConfig.from_file(path)
    else:
        # No config file - use defaults
        config = _create_default_config(working_dir)

    # Override cwd if provided
    if cwd:
        config = ReviewConfig(
            prompt=config.prompt,
            allowed_tools=config.allowed_tools,
            mcp_servers=config.mcp_servers,
            agents=config.agents,
            output_schema=config.output_schema,
            cwd=working_dir,
            timeout_seconds=config.timeout_seconds,
            model=config.model,
            logging=config.logging,
        )

    return config


def _create_default_config(working_dir: Path) -> ReviewConfig:
    """Create a default configuration.

    Checks for orchestrator.md file, falls back to embedded default.

    Args:
        working_dir: The working directory.

    Returns:
        ReviewConfig with sensible defaults.
    """
    # Check if orchestrator.md exists in .reldo/
    orchestrator_path = working_dir / DEFAULT_ORCHESTRATOR_PATH
    if orchestrator_path.exists():
        prompt = DEFAULT_ORCHESTRATOR_PATH
    else:
        # Use embedded default prompt
        prompt = DEFAULT_ORCHESTRATOR_PROMPT

    return ReviewConfig(
        prompt=prompt,
        allowed_tools=["Read", "Glob", "Grep", "Bash", "Task"],
        mcp_servers={},
        agents={},
        output_schema=None,
        cwd=working_dir,
        timeout_seconds=180,
        model="claude-sonnet-4-20250514",
        logging={
            "enabled": True,
            "output_dir": ".reldo/sessions",
            "verbose": False,
        },
    )


def format_result(result: ReviewResult, as_json: bool) -> str:
    """Format the review result for output.

    Args:
        result: The review result.
        as_json: Whether to output as JSON.

    Returns:
        Formatted result string.
    """
    if as_json:
        data = {
            "text": result.text,
            "structured_output": result.structured_output,
            "input_tokens": result.input_tokens,
            "output_tokens": result.output_tokens,
            "total_tokens": result.total_tokens,
            "total_cost_usd": result.total_cost_usd,
            "duration_ms": result.duration_ms,
        }
        return json.dumps(data, indent=2)

    # Plain text output
    return result.text


def check_review_passed(result: ReviewResult) -> bool:
    """Check if the review passed (for exit-code mode).

    Looks for PASS/FAIL indicators in the result text.

    Args:
        result: The review result.

    Returns:
        True if review appears to have passed.
    """
    text_upper = result.text.upper()

    # Check for explicit FAIL indicators
    if "STATUS: FAIL" in text_upper or "FAIL:" in text_upper:
        return False

    # Check for explicit PASS indicators
    if "STATUS: PASS" in text_upper or "PASS:" in text_upper:
        return True

    # Default to passed if no clear indicator
    return True


async def run_review(args: argparse.Namespace) -> int:
    """Run the review command.

    Args:
        args: Parsed command-line arguments.

    Returns:
        Exit code (0 for success, 1 for failure).
    """
    try:
        # Read prompt
        prompt = read_prompt(args.prompt)

        # Load config
        config = load_config(args.config, args.cwd)

        # Apply CLI overrides to logging config
        logging_config = dict(config.logging)
        if args.verbose:
            logging_config["verbose"] = True
        if args.no_log:
            logging_config["enabled"] = False

        # Create updated config with logging overrides
        config = ReviewConfig(
            prompt=config.prompt,
            allowed_tools=config.allowed_tools,
            mcp_servers=config.mcp_servers,
            agents=config.agents,
            output_schema=config.output_schema,
            cwd=config.cwd,
            timeout_seconds=config.timeout_seconds,
            model=config.model,
            logging=logging_config,
        )

        # Run review
        reldo = Reldo(config=config)
        result = await reldo.review(prompt=prompt)

        # Output result
        output = format_result(result, args.json_output)
        print(output)

        # Check exit code if requested
        if args.exit_code and not check_review_passed(result):
            return 1

        return 0

    except FileNotFoundError as e:
        _print_error(str(e), args.json_output)
        return 1

    except json.JSONDecodeError as e:
        _print_error(f"Invalid JSON in config: {e}", args.json_output)
        return 1

    except Exception as e:
        _print_error(str(e), args.json_output)
        return 1


def _print_error(message: str, as_json: bool) -> None:
    """Print an error message to stderr.

    Args:
        message: The error message.
        as_json: Whether to output as JSON.
    """
    if as_json:
        print(json.dumps({"error": message}), file=sys.stderr)
    else:
        print(f"Error: {message}", file=sys.stderr)


def run_init(args: argparse.Namespace) -> int:
    """Initialize a new .reldo directory with default configuration.

    Args:
        args: Parsed command-line arguments.

    Returns:
        Exit code (0 for success, 1 for failure).
    """
    cwd = Path.cwd()
    reldo_dir = cwd / ".reldo"
    settings_file = reldo_dir / "settings.json"
    orchestrator_file = reldo_dir / "orchestrator.md"
    gitignore_file = reldo_dir / ".gitignore"
    sessions_dir = reldo_dir / "sessions"
    agents_dir = reldo_dir / "agents"

    # Check if already exists
    if reldo_dir.exists() and not args.force:
        print(f"Error: {reldo_dir} already exists. Use --force to overwrite.")
        return 1

    try:
        # Create directories
        reldo_dir.mkdir(exist_ok=True)
        sessions_dir.mkdir(exist_ok=True)
        agents_dir.mkdir(exist_ok=True)

        # Write settings.json
        settings_file.write_text(
            json.dumps(DEFAULT_CONFIG, indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"Created {settings_file}")

        # Write orchestrator.md
        orchestrator_file.write_text(DEFAULT_ORCHESTRATOR_PROMPT, encoding="utf-8")
        print(f"Created {orchestrator_file}")

        # Write .gitignore
        gitignore_file.write_text(DEFAULT_GITIGNORE, encoding="utf-8")
        print(f"Created {gitignore_file}")

        print(f"\nInitialized reldo in {reldo_dir}")
        print("\nNext steps:")
        print("  1. Customize .reldo/orchestrator.md with your review guidelines")
        print("  2. Add agent prompts to .reldo/agents/ if needed")
        print("  3. Run: reldo review \"Review my changes\"")

        return 0

    except OSError as e:
        print(f"Error: Failed to create files: {e}", file=sys.stderr)
        return 1


def main() -> int:
    """Main entry point for the CLI.

    Returns:
        Exit code (0 for success, 1 for failure).
    """
    parser = create_parser()
    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        return 0

    if args.command == "review":
        return asyncio.run(run_review(args))

    if args.command == "init":
        return run_init(args)

    return 0


if __name__ == "__main__":
    sys.exit(main())
