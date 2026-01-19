"""CLI entry point for Reldo."""

import argparse
import asyncio
import json
import sys
from pathlib import Path

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
        version="%(prog)s 0.1.0",
    )

    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # review command
    review_parser = subparsers.add_parser("review", help="Run a code review")
    review_parser.add_argument(
        "--prompt",
        required=True,
        help="Review prompt (use '-' for stdin)",
    )
    review_parser.add_argument(
        "--config",
        default=".claude/reldo.json",
        help="Path to config file (default: .claude/reldo.json)",
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


def load_config(config_path: str, cwd: str | None) -> ReviewConfig:
    """Load configuration from file.

    Args:
        config_path: Path to config file.
        cwd: Optional working directory override.

    Returns:
        ReviewConfig instance.

    Raises:
        FileNotFoundError: If config file doesn't exist.
        json.JSONDecodeError: If config isn't valid JSON.
    """
    path = Path(config_path)

    # If path is relative and doesn't exist, try from cwd
    if not path.is_absolute() and not path.exists():
        if cwd:
            path = Path(cwd) / config_path
        else:
            path = Path.cwd() / config_path

    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    config = ReviewConfig.from_file(path)

    # Override cwd if provided
    if cwd:
        config = ReviewConfig(
            prompt=config.prompt,
            allowed_tools=config.allowed_tools,
            mcp_servers=config.mcp_servers,
            agents=config.agents,
            output_schema=config.output_schema,
            cwd=Path(cwd),
            timeout_seconds=config.timeout_seconds,
            model=config.model,
            logging=config.logging,
        )

    return config


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

    return 0


if __name__ == "__main__":
    sys.exit(main())
