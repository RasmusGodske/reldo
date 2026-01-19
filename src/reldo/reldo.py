"""Main Reldo class - the public API."""

from typing import Any

from .models.ReviewConfig import ReviewConfig
from .models.ReviewResult import ReviewResult
from .services.ReviewService import ReviewService


class Reldo:
    """Claude-powered code review orchestrator.

    Reldo coordinates specialized review agents using the Claude Agent SDK.
    It provides a simple interface for running code reviews.

    Example:
        ```python
        from reldo import Reldo, ReviewConfig
        from pathlib import Path

        config = ReviewConfig.from_file(Path(".claude/reldo.json"))
        reldo = Reldo(config=config)

        result = await reldo.review(
            prompt="Review app/Models/User.php for backend conventions"
        )
        print(result.text)
        ```

    Attributes:
        _config: The review configuration.
        _service: The underlying review service.
    """

    def __init__(self, config: ReviewConfig, hooks: dict[str, Any] | None = None) -> None:
        """Initialize Reldo.

        Args:
            config: Review configuration (from file or programmatic).
            hooks: Optional hooks dict for SDK integration (programmatic only).
        """
        self._config = config
        self._service = ReviewService(config=config, hooks=hooks)

    async def review(self, prompt: str) -> ReviewResult:
        """Run a code review.

        Args:
            prompt: The review prompt describing what to review.
                   You construct the full prompt - Reldo doesn't impose structure.

        Returns:
            ReviewResult with the review outcome.

        Example:
            ```python
            result = await reldo.review(
                prompt="Review app/Models/User.php. Context: Added user registration."
            )
            ```
        """
        return await self._service.review(prompt=prompt)
