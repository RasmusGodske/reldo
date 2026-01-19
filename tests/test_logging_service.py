"""Unit tests for LoggingService."""

import json
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from reldo.models import ReviewResult
from reldo.services import LoggingService


@dataclass
class MockTextBlock:
    """Mock text block for transcript testing."""
    text: str


@dataclass
class MockMessage:
    """Mock message for transcript testing."""
    content: list[Any]


class TestLoggingServiceInit:
    """Tests for LoggingService initialization."""

    def test_init_stores_output_dir(self) -> None:
        """Test that __init__ stores output directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            ls = LoggingService(output_dir=output_dir)
            assert ls._output_dir == output_dir

    def test_init_verbose_default_false(self) -> None:
        """Test that verbose defaults to False."""
        with tempfile.TemporaryDirectory() as tmpdir:
            ls = LoggingService(output_dir=Path(tmpdir))
            assert ls._verbose is False

    def test_init_verbose_true(self) -> None:
        """Test that verbose can be set to True."""
        with tempfile.TemporaryDirectory() as tmpdir:
            ls = LoggingService(output_dir=Path(tmpdir), verbose=True)
            assert ls._verbose is True

    def test_init_empty_sessions(self) -> None:
        """Test that sessions dict starts empty."""
        with tempfile.TemporaryDirectory() as tmpdir:
            ls = LoggingService(output_dir=Path(tmpdir))
            assert ls._sessions == {}


class TestLoggingServiceStartSession:
    """Tests for LoggingService.start_session()."""

    def test_start_session_returns_id(self) -> None:
        """Test that start_session returns a session ID."""
        with tempfile.TemporaryDirectory() as tmpdir:
            ls = LoggingService(output_dir=Path(tmpdir))
            session_id = ls.start_session(prompt="Test prompt", config={"prompt": "test"})

            assert isinstance(session_id, str)
            assert len(session_id) == 8  # Short UUID

    def test_start_session_creates_directory(self) -> None:
        """Test that start_session creates session directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            ls = LoggingService(output_dir=output_dir)
            session_id = ls.start_session(prompt="Test", config={})

            sessions_dir = output_dir / "sessions"
            assert sessions_dir.exists()
            dirs = list(sessions_dir.iterdir())
            assert len(dirs) == 1
            assert session_id in dirs[0].name

    def test_start_session_creates_session_json(self) -> None:
        """Test that start_session creates session.json."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            ls = LoggingService(output_dir=output_dir)
            session_id = ls.start_session(prompt="Review code", config={"prompt": "test"})

            session_dir = ls.get_session_path(session_id)
            session_file = session_dir / "session.json"
            assert session_file.exists()

            data = json.loads(session_file.read_text())
            assert data["session_id"] == session_id
            assert data["prompt"] == "Review code"
            assert data["config"] == {"prompt": "test"}
            assert "started_at" in data

    def test_start_session_stores_in_sessions(self) -> None:
        """Test that start_session stores session in dict."""
        with tempfile.TemporaryDirectory() as tmpdir:
            ls = LoggingService(output_dir=Path(tmpdir))
            session_id = ls.start_session(prompt="Test", config={})

            assert session_id in ls._sessions
            assert ls._sessions[session_id].exists()

    def test_start_session_multiple_sessions(self) -> None:
        """Test creating multiple sessions."""
        with tempfile.TemporaryDirectory() as tmpdir:
            ls = LoggingService(output_dir=Path(tmpdir))

            id1 = ls.start_session(prompt="First", config={})
            id2 = ls.start_session(prompt="Second", config={})

            assert id1 != id2
            assert len(ls._sessions) == 2


class TestLoggingServiceSaveResult:
    """Tests for LoggingService.save_result()."""

    def test_save_result_creates_file(self) -> None:
        """Test that save_result creates result.json."""
        with tempfile.TemporaryDirectory() as tmpdir:
            ls = LoggingService(output_dir=Path(tmpdir))
            session_id = ls.start_session(prompt="Test", config={})

            result = ReviewResult(
                text="Review passed",
                input_tokens=100,
                output_tokens=50,
                total_tokens=150,
                total_cost_usd=0.001,
                duration_ms=5000
            )
            ls.save_result(session_id, result)

            session_dir = ls.get_session_path(session_id)
            result_file = session_dir / "result.json"
            assert result_file.exists()

    def test_save_result_contains_data(self) -> None:
        """Test that result.json contains expected data."""
        with tempfile.TemporaryDirectory() as tmpdir:
            ls = LoggingService(output_dir=Path(tmpdir))
            session_id = ls.start_session(prompt="Test", config={})

            result = ReviewResult(
                text="PASS: All checks succeeded",
                structured_output={"passed": True, "issues": []},
                input_tokens=500,
                output_tokens=200,
                total_tokens=700,
                total_cost_usd=0.005,
                duration_ms=10000
            )
            ls.save_result(session_id, result)

            session_dir = ls.get_session_path(session_id)
            result_file = session_dir / "result.json"
            data = json.loads(result_file.read_text())

            assert data["text"] == "PASS: All checks succeeded"
            assert data["structured_output"] == {"passed": True, "issues": []}
            assert data["input_tokens"] == 500
            assert data["output_tokens"] == 200
            assert data["total_tokens"] == 700
            assert data["total_cost_usd"] == 0.005
            assert data["duration_ms"] == 10000
            assert "completed_at" in data

    def test_save_result_unknown_session_raises(self) -> None:
        """Test that save_result raises for unknown session."""
        with tempfile.TemporaryDirectory() as tmpdir:
            ls = LoggingService(output_dir=Path(tmpdir))
            result = ReviewResult(text="Test")

            with pytest.raises(ValueError, match="Unknown session"):
                ls.save_result("nonexistent", result)


class TestLoggingServiceSaveTranscript:
    """Tests for LoggingService.save_transcript()."""

    def test_save_transcript_verbose_creates_file(self) -> None:
        """Test that save_transcript creates file in verbose mode."""
        with tempfile.TemporaryDirectory() as tmpdir:
            ls = LoggingService(output_dir=Path(tmpdir), verbose=True)
            session_id = ls.start_session(prompt="Test", config={})

            messages = [
                MockMessage(content=[MockTextBlock("Hello")]),
                MockMessage(content=[MockTextBlock("World")]),
            ]
            ls.save_transcript(session_id, messages)

            session_dir = ls.get_session_path(session_id)
            transcript_file = session_dir / "transcript.log"
            assert transcript_file.exists()

    def test_save_transcript_verbose_contains_messages(self) -> None:
        """Test that transcript.log contains message content."""
        with tempfile.TemporaryDirectory() as tmpdir:
            ls = LoggingService(output_dir=Path(tmpdir), verbose=True)
            session_id = ls.start_session(prompt="Test", config={})

            messages = [
                MockMessage(content=[MockTextBlock("First message")]),
                MockMessage(content=[MockTextBlock("Second message")]),
            ]
            ls.save_transcript(session_id, messages)

            session_dir = ls.get_session_path(session_id)
            transcript_file = session_dir / "transcript.log"
            content = transcript_file.read_text()

            assert "First message" in content
            assert "Second message" in content

    def test_save_transcript_non_verbose_no_file(self) -> None:
        """Test that save_transcript does nothing when not verbose."""
        with tempfile.TemporaryDirectory() as tmpdir:
            ls = LoggingService(output_dir=Path(tmpdir), verbose=False)
            session_id = ls.start_session(prompt="Test", config={})

            messages = [MockMessage(content=[MockTextBlock("Should not save")])]
            ls.save_transcript(session_id, messages)

            session_dir = ls.get_session_path(session_id)
            transcript_file = session_dir / "transcript.log"
            assert not transcript_file.exists()

    def test_save_transcript_handles_string_messages(self) -> None:
        """Test that save_transcript handles plain string messages."""
        with tempfile.TemporaryDirectory() as tmpdir:
            ls = LoggingService(output_dir=Path(tmpdir), verbose=True)
            session_id = ls.start_session(prompt="Test", config={})

            # Plain strings (no content attribute)
            messages = ["Simple string", "Another string"]
            ls.save_transcript(session_id, messages)

            session_dir = ls.get_session_path(session_id)
            transcript_file = session_dir / "transcript.log"
            content = transcript_file.read_text()

            assert "Simple string" in content
            assert "Another string" in content


class TestLoggingServiceGetSessionPath:
    """Tests for LoggingService.get_session_path()."""

    def test_get_session_path_returns_path(self) -> None:
        """Test that get_session_path returns correct path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            ls = LoggingService(output_dir=Path(tmpdir))
            session_id = ls.start_session(prompt="Test", config={})

            path = ls.get_session_path(session_id)
            assert path.exists()
            assert session_id in str(path)

    def test_get_session_path_unknown_raises(self) -> None:
        """Test that get_session_path raises for unknown session."""
        with tempfile.TemporaryDirectory() as tmpdir:
            ls = LoggingService(output_dir=Path(tmpdir))

            with pytest.raises(ValueError, match="Unknown session"):
                ls.get_session_path("nonexistent")


class TestLoggingServiceIntegration:
    """Integration tests for full logging workflow."""

    def test_full_workflow(self) -> None:
        """Test complete logging workflow."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            ls = LoggingService(output_dir=output_dir, verbose=True)

            # Start session
            session_id = ls.start_session(
                prompt="Review app/Models/User.php",
                config={"prompt": "orchestrator.md", "allowed_tools": ["Read"]}
            )

            # Save result
            result = ReviewResult(
                text="PASS: No violations found",
                input_tokens=1000,
                output_tokens=400,
                total_tokens=1400,
                total_cost_usd=0.01,
                duration_ms=15000
            )
            ls.save_result(session_id, result)

            # Save transcript
            messages = [
                MockMessage(content=[MockTextBlock("Reading file...")]),
                MockMessage(content=[MockTextBlock("Analysis complete")]),
            ]
            ls.save_transcript(session_id, messages)

            # Verify all files exist
            session_dir = ls.get_session_path(session_id)
            assert (session_dir / "session.json").exists()
            assert (session_dir / "result.json").exists()
            assert (session_dir / "transcript.log").exists()

            # Verify content
            session_data = json.loads((session_dir / "session.json").read_text())
            assert session_data["prompt"] == "Review app/Models/User.php"

            result_data = json.loads((session_dir / "result.json").read_text())
            assert result_data["text"] == "PASS: No violations found"
            assert result_data["total_tokens"] == 1400
