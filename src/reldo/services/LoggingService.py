"""Service for logging review sessions."""

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from ..models.ReviewResult import ReviewResult


class LoggingService:
    """Manages session logging for Reldo reviews.

    Creates directory structure:
    {output_dir}/sessions/
    └── 2024-01-15T10-30-00-{session-id}/
        ├── session.json      # Metadata
        ├── result.json       # Review result
        └── transcript.log    # Full transcript (verbose mode)

    Attributes:
        _output_dir: Base directory for session logs.
        _verbose: Whether to include full transcripts.
        _sessions: Mapping of session_id to session directory path.
    """

    def __init__(self, output_dir: Path, verbose: bool = False) -> None:
        """Initialize the logging service.

        Args:
            output_dir: Base directory for session logs.
            verbose: Whether to include full transcripts.
        """
        self._output_dir = output_dir
        self._verbose = verbose
        self._sessions: dict[str, Path] = {}

    def _generate_session_id(self) -> str:
        """Generate a unique session ID.

        Returns:
            Short UUID for session identification.
        """
        return str(uuid.uuid4())[:8]

    def _create_session_dir(self, session_id: str) -> Path:
        """Create the session directory.

        Args:
            session_id: The session identifier.

        Returns:
            Path to the created session directory.
        """
        timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
        dir_name = f"{timestamp}-{session_id}"
        session_dir = self._output_dir / "sessions" / dir_name
        session_dir.mkdir(parents=True, exist_ok=True)
        return session_dir

    def start_session(self, prompt: str, config: dict[str, Any]) -> str:
        """Start a new logging session.

        Creates the session directory and saves initial metadata.

        Args:
            prompt: The review prompt.
            config: Config snapshot for the session.

        Returns:
            Session ID.
        """
        session_id = self._generate_session_id()
        session_dir = self._create_session_dir(session_id)

        # Store session directory for later use
        self._sessions[session_id] = session_dir

        # Create session metadata
        session_data = {
            "session_id": session_id,
            "prompt": prompt,
            "config": config,
            "started_at": datetime.now().isoformat(),
            "verbose": self._verbose,
        }

        # Save session.json
        session_file = session_dir / "session.json"
        session_file.write_text(
            json.dumps(session_data, indent=2, default=str),
            encoding="utf-8"
        )

        return session_id

    def _get_session_dir(self, session_id: str) -> Path:
        """Get the directory for a session.

        Args:
            session_id: The session identifier.

        Returns:
            Path to the session directory.

        Raises:
            ValueError: If session_id is not found.
        """
        if session_id not in self._sessions:
            raise ValueError(f"Unknown session: {session_id}")
        return self._sessions[session_id]

    def save_result(self, session_id: str, result: ReviewResult) -> None:
        """Save the review result.

        Args:
            session_id: The session to save to.
            result: The review result.
        """
        session_dir = self._get_session_dir(session_id)

        # Convert ReviewResult to dict, handling dataclass fields
        result_data = {
            "text": result.text,
            "structured_output": result.structured_output,
            "input_tokens": result.input_tokens,
            "output_tokens": result.output_tokens,
            "total_tokens": result.total_tokens,
            "total_cost_usd": result.total_cost_usd,
            "duration_ms": result.duration_ms,
            "completed_at": datetime.now().isoformat(),
        }

        # Save result.json
        result_file = session_dir / "result.json"
        result_file.write_text(
            json.dumps(result_data, indent=2, default=str),
            encoding="utf-8"
        )

    def save_transcript(self, session_id: str, messages: list[Any]) -> None:
        """Save the full transcript (verbose mode only).

        Only saves if verbose mode is enabled.

        Args:
            session_id: The session to save to.
            messages: The transcript messages.
        """
        if not self._verbose:
            return

        session_dir = self._get_session_dir(session_id)

        # Format messages for logging
        lines: list[str] = []
        for i, msg in enumerate(messages):
            lines.append(f"=== Message {i + 1} ===")
            if hasattr(msg, "content"):
                # Handle message objects with content
                for block in getattr(msg, "content", []):
                    if hasattr(block, "text"):
                        lines.append(block.text)
                    else:
                        lines.append(str(block))
            else:
                # Handle other message types
                lines.append(str(msg))
            lines.append("")

        # Save transcript.log
        transcript_file = session_dir / "transcript.log"
        transcript_file.write_text("\n".join(lines), encoding="utf-8")

    def get_session_path(self, session_id: str) -> Path:
        """Get the path to a session's directory.

        Args:
            session_id: The session identifier.

        Returns:
            Path to the session directory.
        """
        return self._get_session_dir(session_id)
