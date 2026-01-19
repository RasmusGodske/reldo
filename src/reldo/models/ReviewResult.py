"""Result from a Reldo review."""

from dataclasses import dataclass
from typing import Any


@dataclass
class ReviewResult:
    """Result from a Reldo review session.

    Attributes:
        text: Raw output text from the orchestrator.
        structured_output: Validated JSON matching output_schema (if configured).
        input_tokens: Number of input tokens used.
        output_tokens: Number of output tokens used.
        total_tokens: Total tokens used.
        total_cost_usd: Estimated cost in USD.
        duration_ms: Review duration in milliseconds.
    """

    text: str
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    total_cost_usd: float = 0.0
    duration_ms: int = 0
    structured_output: dict[str, Any] | None = None
