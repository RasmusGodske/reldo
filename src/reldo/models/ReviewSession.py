"""Session metadata for Reldo reviews."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class ReviewSession:
    """Metadata about a Reldo review session.

    Used for logging and tracking review history.

    Attributes:
        session_id: Unique identifier for this session.
        prompt: The review prompt that was submitted.
        started_at: When the session started.
        completed_at: When the session completed (if finished).
        config_snapshot: Snapshot of config used (for audit).
    """

    session_id: str
    prompt: str
    started_at: datetime = field(default_factory=datetime.now)
    completed_at: datetime | None = None
    config_snapshot: dict[str, Any] = field(default_factory=dict)
