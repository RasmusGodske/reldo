"""Configuration for Reldo reviews."""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from reldo.utils import substitute_variables


@dataclass
class ReviewConfig:
    """Configuration for a Reldo review session.

    Mirrors ClaudeAgentOptions from the Claude Agent SDK.
    Properties pass through directly to the SDK.

    Attributes:
        prompt: Orchestrator prompt (path to file or inline string).
        allowed_tools: Tools available to the orchestrator.
        mcp_servers: MCP server configurations.
        agents: Sub-agent definitions (merged with discovered agents).
        setting_sources: Where to load agent/settings from (default: ['project']).
        output_schema: JSON schema for structured output (optional).
        cwd: Working directory.
        timeout_seconds: Maximum review duration.
        model: Claude model to use.
        logging: Logging configuration.
    """

    prompt: str
    allowed_tools: list[str] = field(
        default_factory=lambda: ["Read", "Glob", "Grep", "Bash", "Task"]
    )
    mcp_servers: dict[str, Any] = field(default_factory=dict)
    agents: dict[str, dict[str, Any]] = field(default_factory=dict)
    setting_sources: list[str] | None = None
    output_schema: dict[str, Any] | None = None
    cwd: Path | str = field(default_factory=Path.cwd)
    timeout_seconds: int = 180
    model: str = "claude-sonnet-4-20250514"
    logging: dict[str, Any] = field(
        default_factory=lambda: {
            "enabled": True,
            "output_dir": ".reldo",
            "verbose": False,
        }
    )

    @classmethod
    def from_file(cls, path: Path | str) -> "ReviewConfig":
        """Load configuration from a JSON file.

        Args:
            path: Path to the JSON configuration file.

        Returns:
            ReviewConfig instance.

        Raises:
            FileNotFoundError: If the config file doesn't exist.
            json.JSONDecodeError: If the file isn't valid JSON.
        """
        file_path = Path(path)
        if not file_path.exists():
            raise FileNotFoundError(f"Config file not found: {file_path}")

        content = file_path.read_text(encoding="utf-8")
        data = json.loads(content)
        return cls.from_dict(data)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ReviewConfig":
        """Create configuration from a dictionary.

        Applies variable substitution to mcp_servers and agents fields.
        Supported variables:
        - ${cwd} → working directory
        - ${env:VAR_NAME} → environment variable value

        Args:
            data: Configuration dictionary.

        Returns:
            ReviewConfig instance.

        Raises:
            ValueError: If required field 'prompt' is missing.
        """
        if "prompt" not in data:
            raise ValueError("Configuration must include 'prompt' field")

        # Process cwd - convert string to Path if present
        cwd = data.get("cwd")
        if cwd is not None:
            cwd = Path(cwd)
        else:
            cwd = Path.cwd()

        # Apply variable substitution to mcp_servers and agents
        mcp_servers = substitute_variables(data.get("mcp_servers", {}), cwd)
        agents = substitute_variables(data.get("agents", {}), cwd)

        # Build logging config with defaults
        default_logging = {"enabled": True, "output_dir": ".reldo", "verbose": False}
        logging_config = {**default_logging, **data.get("logging", {})}

        return cls(
            prompt=data["prompt"],
            allowed_tools=data.get("allowed_tools", ["Read", "Glob", "Grep", "Bash", "Task"]),
            mcp_servers=mcp_servers,
            agents=agents,
            setting_sources=data.get("setting_sources"),
            output_schema=data.get("output_schema"),
            cwd=cwd,
            timeout_seconds=data.get("timeout_seconds", 180),
            model=data.get("model", "claude-sonnet-4-20250514"),
            logging=logging_config,
        )
