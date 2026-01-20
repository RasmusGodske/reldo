"""Unit tests for Reldo models."""

import json
import tempfile
from datetime import datetime
from pathlib import Path

import pytest

from reldo.models import ReviewConfig, ReviewResult, ReviewSession


class TestReviewConfig:
    """Tests for ReviewConfig dataclass."""

    def test_from_dict_minimal(self) -> None:
        """Test creating config with only required field."""
        config = ReviewConfig.from_dict({"prompt": "You are a reviewer"})

        assert config.prompt == "You are a reviewer"
        assert config.allowed_tools == ["Read", "Glob", "Grep", "Bash", "Task"]
        assert config.mcp_servers == {}
        assert config.agents == {}
        assert config.output_schema is None
        assert config.timeout_seconds == 180
        assert config.model == "claude-sonnet-4-20250514"
        assert config.logging["enabled"] is True

    def test_from_dict_full(self) -> None:
        """Test creating config with all fields."""
        data = {
            "prompt": "You are a reviewer",
            "allowed_tools": ["Read", "Glob"],
            "mcp_servers": {
                "test": {"command": "echo", "args": ["hello"]}
            },
            "agents": {
                "test-agent": {
                    "description": "Test agent",
                    "prompt": "You are a test agent",
                    "tools": ["Read"]
                }
            },
            "output_schema": {"type": "object", "properties": {"passed": {"type": "boolean"}}},
            "cwd": "/tmp",
            "timeout_seconds": 60,
            "model": "claude-opus-4-20250514",
            "logging": {"enabled": False, "verbose": True}
        }

        config = ReviewConfig.from_dict(data)

        assert config.prompt == "You are a reviewer"
        assert config.allowed_tools == ["Read", "Glob"]
        assert "test" in config.mcp_servers
        assert "test-agent" in config.agents
        assert config.agents["test-agent"]["description"] == "Test agent"
        assert config.output_schema is not None
        assert config.output_schema["type"] == "object"
        assert config.cwd == Path("/tmp")
        assert config.timeout_seconds == 60
        assert config.model == "claude-opus-4-20250514"
        assert config.logging["enabled"] is False
        assert config.logging["verbose"] is True

    def test_from_dict_missing_prompt_raises(self) -> None:
        """Test that missing prompt raises ValueError."""
        with pytest.raises(ValueError, match="must include 'prompt'"):
            ReviewConfig.from_dict({})

    def test_from_dict_cwd_converted_to_path(self) -> None:
        """Test that cwd string is converted to Path."""
        config = ReviewConfig.from_dict({"prompt": "test", "cwd": "/some/path"})
        assert isinstance(config.cwd, Path)
        assert config.cwd == Path("/some/path")

    def test_from_dict_logging_defaults_merged(self) -> None:
        """Test that logging config merges with defaults."""
        config = ReviewConfig.from_dict({"prompt": "test", "logging": {"verbose": True}})

        # Should have default enabled and output_dir, plus our override
        assert config.logging["enabled"] is True
        assert config.logging["output_dir"] == ".reldo"
        assert config.logging["verbose"] is True

    def test_from_file(self) -> None:
        """Test loading config from JSON file."""
        config_data = {
            "prompt": "You are a reviewer",
            "allowed_tools": ["Read", "Glob"],
            "agents": {
                "test-agent": {
                    "description": "Test agent",
                    "prompt": "You are a test agent",
                    "tools": ["Read"]
                }
            },
            "cwd": "/tmp",
            "timeout_seconds": 60
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(config_data, f)
            f.flush()
            temp_path = Path(f.name)

        try:
            config = ReviewConfig.from_file(temp_path)

            assert config.prompt == "You are a reviewer"
            assert config.allowed_tools == ["Read", "Glob"]
            assert "test-agent" in config.agents
            assert config.timeout_seconds == 60
        finally:
            temp_path.unlink()

    def test_from_file_not_found_raises(self) -> None:
        """Test that missing file raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError, match="Config file not found"):
            ReviewConfig.from_file("/nonexistent/path/config.json")

    def test_from_file_invalid_json_raises(self) -> None:
        """Test that invalid JSON raises JSONDecodeError."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write("not valid json {")
            f.flush()
            temp_path = Path(f.name)

        try:
            with pytest.raises(json.JSONDecodeError):
                ReviewConfig.from_file(temp_path)
        finally:
            temp_path.unlink()

    def test_direct_instantiation(self) -> None:
        """Test creating config directly."""
        config = ReviewConfig(
            prompt="You are a reviewer",
            allowed_tools=["Read"],
            cwd=Path("/tmp")
        )

        assert config.prompt == "You are a reviewer"
        assert config.allowed_tools == ["Read"]
        assert config.cwd == Path("/tmp")


class TestReviewResult:
    """Tests for ReviewResult dataclass."""

    def test_minimal_result(self) -> None:
        """Test creating result with only required field."""
        result = ReviewResult(text="Review complete")

        assert result.text == "Review complete"
        assert result.input_tokens == 0
        assert result.output_tokens == 0
        assert result.total_tokens == 0
        assert result.total_cost_usd == 0.0
        assert result.duration_ms == 0
        assert result.structured_output is None

    def test_full_result(self) -> None:
        """Test creating result with all fields."""
        result = ReviewResult(
            text="Review complete",
            structured_output={"passed": True, "issues": []},
            input_tokens=100,
            output_tokens=50,
            total_tokens=150,
            total_cost_usd=0.001,
            duration_ms=5000
        )

        assert result.text == "Review complete"
        assert result.structured_output == {"passed": True, "issues": []}
        assert result.input_tokens == 100
        assert result.output_tokens == 50
        assert result.total_tokens == 150
        assert result.total_cost_usd == 0.001
        assert result.duration_ms == 5000


class TestReviewSession:
    """Tests for ReviewSession dataclass."""

    def test_minimal_session(self) -> None:
        """Test creating session with only required fields."""
        session = ReviewSession(
            session_id="test-123",
            prompt="Review this file"
        )

        assert session.session_id == "test-123"
        assert session.prompt == "Review this file"
        assert isinstance(session.started_at, datetime)
        assert session.completed_at is None
        assert session.config_snapshot == {}

    def test_full_session(self) -> None:
        """Test creating session with all fields."""
        now = datetime.now()
        session = ReviewSession(
            session_id="test-123",
            prompt="Review this file",
            started_at=now,
            completed_at=now,
            config_snapshot={"prompt": "test"}
        )

        assert session.session_id == "test-123"
        assert session.prompt == "Review this file"
        assert session.started_at == now
        assert session.completed_at == now
        assert session.config_snapshot == {"prompt": "test"}

    def test_session_started_at_auto_populated(self) -> None:
        """Test that started_at is auto-populated."""
        before = datetime.now()
        session = ReviewSession(session_id="test", prompt="test")
        after = datetime.now()

        assert before <= session.started_at <= after
