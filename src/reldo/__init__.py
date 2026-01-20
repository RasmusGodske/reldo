"""
Reldo - Claude-powered code review orchestrator.

"The librarian has reviewed your code."

Example:
    ```python
    from reldo import Reldo, ReviewConfig
    from pathlib import Path

    config = ReviewConfig.from_file(Path(".claude/reldo.json"))
    reldo = Reldo(config=config)

    result = await reldo.review(prompt="Review app/Models/User.php")
    print(result.text)
    ```
"""

from importlib.metadata import version

__version__ = version("reldo")

from .models.ReviewConfig import ReviewConfig
from .models.ReviewResult import ReviewResult
from .models.ReviewSession import ReviewSession
from .reldo import Reldo

# Re-export HookMatcher from SDK for programmatic hook usage
# Will be enabled when claude-agent-sdk is installed
try:
    from claude_agent_sdk import HookMatcher
except ImportError:
    HookMatcher = None  # type: ignore[misc, assignment]

__all__ = [
    "Reldo",
    "ReviewConfig",
    "ReviewResult",
    "ReviewSession",
    "HookMatcher",
]
