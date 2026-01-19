"""Variable substitution utilities for config values."""

import os
import re
from pathlib import Path
from typing import Any


def substitute_variables(value: Any, cwd: Path) -> Any:
    """Recursively substitute variables in a value.

    Supported patterns:
    - ${cwd} → working directory path
    - ${env:VAR_NAME} → environment variable value

    Args:
        value: Value to process (string, list, dict, or other).
        cwd: Working directory for ${cwd} substitution.

    Returns:
        Value with variables substituted.
    """
    if isinstance(value, str):
        return _substitute_string(value, cwd)
    elif isinstance(value, dict):
        return {k: substitute_variables(v, cwd) for k, v in value.items()}
    elif isinstance(value, list):
        return [substitute_variables(item, cwd) for item in value]
    else:
        return value


def _substitute_string(value: str, cwd: Path) -> str:
    """Substitute variables in a string value.

    Args:
        value: String to process.
        cwd: Working directory for ${cwd} substitution.

    Returns:
        String with variables substituted.
    """
    # Pattern for ${cwd} and ${env:VAR_NAME}
    pattern = r"\$\{([^}]+)\}"

    def replace_match(match: re.Match[str]) -> str:
        var_spec = match.group(1)

        # Handle ${cwd}
        if var_spec == "cwd":
            return str(cwd)

        # Handle ${env:VAR_NAME}
        if var_spec.startswith("env:"):
            env_var = var_spec[4:]  # Remove "env:" prefix
            env_value = os.environ.get(env_var)
            if env_value is None:
                # Return original placeholder if env var not set
                return match.group(0)
            return env_value

        # Unknown variable - return as-is
        return match.group(0)

    return re.sub(pattern, replace_match, value)
