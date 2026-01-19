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

    def _get_sdk_transcript_path(self, sdk_session_id: str, cwd: str) -> str:
        """Build the path to the SDK's JSONL transcript file.

        The SDK stores transcripts at:
        ~/.claude/projects/{project-path-hash}/{session_id}.jsonl

        Args:
            sdk_session_id: The session ID from the SDK's ResultMessage.
            cwd: The working directory used for the session.

        Returns:
            Path to the SDK's JSONL transcript file.
        """
        # Convert cwd to project hash (slashes become dashes)
        project_hash = cwd.replace("/", "-")
        if project_hash.startswith("-"):
            project_hash = project_hash  # Keep leading dash

        claude_dir = Path.home() / ".claude" / "projects" / project_hash
        return str(claude_dir / f"{sdk_session_id}.jsonl")

    def save_sdk_transcript_reference(
        self, session_id: str, sdk_session_id: str, cwd: str
    ) -> None:
        """Update session.json with a reference to the SDK's transcript.

        Args:
            session_id: The reldo session ID.
            sdk_session_id: The session ID from the SDK's ResultMessage.
            cwd: The working directory used for the session.
        """
        session_dir = self._get_session_dir(session_id)
        session_file = session_dir / "session.json"

        # Read existing session.json
        session_data = json.loads(session_file.read_text(encoding="utf-8"))

        # Add SDK transcript reference
        sdk_transcript_path = self._get_sdk_transcript_path(sdk_session_id, cwd)
        session_data["sdk_session_id"] = sdk_session_id
        session_data["sdk_transcript_path"] = sdk_transcript_path

        # Write updated session.json
        session_file.write_text(
            json.dumps(session_data, indent=2, default=str),
            encoding="utf-8"
        )

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

    def _format_block(self, block: Any) -> str:
        """Format a single content block for logging.

        Args:
            block: A content block (text, tool_use, tool_result, etc.)

        Returns:
            Formatted string representation.
        """
        # Text block
        if hasattr(block, "text"):
            return f"[THOUGHT]\n{block.text}"

        # Tool use block
        if hasattr(block, "name") and hasattr(block, "input"):
            tool_name = getattr(block, "name", "unknown")
            tool_input = getattr(block, "input", {})
            tool_id = getattr(block, "id", "")
            # Format input nicely
            if isinstance(tool_input, dict):
                input_str = json.dumps(tool_input, indent=2, default=str)
            else:
                input_str = str(tool_input)
            return f"[TOOL_CALL] {tool_name} (id: {tool_id})\n{input_str}"

        # Tool result block
        if hasattr(block, "tool_use_id"):
            tool_id = getattr(block, "tool_use_id", "")
            content = getattr(block, "content", "")
            # Content might be a list or string
            if isinstance(content, list):
                content_str = "\n".join(
                    getattr(c, "text", str(c)) for c in content
                )
            else:
                content_str = str(content)
            # Truncate very long results
            if len(content_str) > 2000:
                content_str = content_str[:2000] + "\n... [truncated]"
            return f"[TOOL_RESULT] (id: {tool_id})\n{content_str}"

        # Fallback: convert to string
        return f"[BLOCK] {type(block).__name__}\n{block!s}"

    def save_transcript(self, session_id: str, messages: list[Any]) -> None:
        """Save the full transcript with tool calls and thoughts.

        Only saves if verbose mode is enabled.

        Args:
            session_id: The session to save to.
            messages: The transcript messages from the SDK.
        """
        if not self._verbose:
            return

        session_dir = self._get_session_dir(session_id)

        lines: list[str] = []
        lines.append("=" * 60)
        lines.append("RELDO SESSION TRANSCRIPT")
        lines.append("=" * 60)
        lines.append("")

        for i, msg in enumerate(messages):
            # Determine message type/role
            role = getattr(msg, "role", None)
            msg_type = type(msg).__name__

            lines.append(f"{'=' * 40}")
            if role:
                lines.append(f"MESSAGE {i + 1} [{role.upper()}]")
            else:
                lines.append(f"MESSAGE {i + 1} [{msg_type}]")
            lines.append(f"{'=' * 40}")

            # Handle messages with content blocks
            if hasattr(msg, "content"):
                content = getattr(msg, "content", [])
                if isinstance(content, list):
                    for block in content:
                        lines.append(self._format_block(block))
                        lines.append("")
                else:
                    lines.append(str(content))
                    lines.append("")

            # Handle ResultMessage (final message with usage stats)
            elif hasattr(msg, "session_id") and hasattr(msg, "usage"):
                lines.append("[RESULT]")
                if hasattr(msg, "result") and msg.result:
                    lines.append(msg.result)
                usage = getattr(msg, "usage", {})
                if usage:
                    lines.append(f"\n[USAGE] {json.dumps(usage, indent=2)}")
                lines.append("")

            # Fallback
            else:
                lines.append(str(msg))
                lines.append("")

        lines.append("=" * 60)
        lines.append("END OF TRANSCRIPT")
        lines.append("=" * 60)

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
