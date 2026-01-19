"""Integration tests for main Reldo class."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any, AsyncIterator
from unittest.mock import patch

import pytest

from importlib import import_module

from reldo import Reldo, ReviewConfig, ReviewResult, HookMatcher


# Import the ReviewService module for patching
review_service_module = import_module("reldo.services.ReviewService")


@dataclass
class MockTextBlock:
    """Mock text block for message content."""
    text: str


@dataclass
class MockMessage:
    """Mock message from SDK."""
    content: list[Any]


@dataclass
class MockResultMessage:
    """Mock ResultMessage from SDK."""
    subtype: str = "success"
    duration_ms: int = 5000
    duration_api_ms: int = 4500
    is_error: bool = False
    num_turns: int = 5
    session_id: str = "test-session-123"
    total_cost_usd: float | None = 0.005
    usage: dict[str, Any] | None = None
    result: str | None = "Review complete. All checks passed."

    def __post_init__(self) -> None:
        if self.usage is None:
            self.usage = {"input_tokens": 1000, "output_tokens": 500}


class TestReldoExports:
    """Tests for public API exports."""

    def test_reldo_class_exported(self) -> None:
        """Test that Reldo class is exported."""
        assert Reldo is not None

    def test_review_config_exported(self) -> None:
        """Test that ReviewConfig is exported."""
        assert ReviewConfig is not None

    def test_review_result_exported(self) -> None:
        """Test that ReviewResult is exported."""
        assert ReviewResult is not None

    def test_hook_matcher_exported(self) -> None:
        """Test that HookMatcher is exported (may be None if SDK not installed)."""
        # HookMatcher should be available when SDK is installed
        # May be None in test environment without SDK
        from reldo import HookMatcher
        # Just check it's exported, even if None
        pass


class TestReldoInit:
    """Tests for Reldo initialization."""

    def test_init_with_config(self) -> None:
        """Test Reldo initializes with config."""
        config = ReviewConfig(prompt="You are a reviewer")
        reldo = Reldo(config=config)

        assert reldo is not None
        assert reldo._config == config

    def test_init_with_hooks(self) -> None:
        """Test Reldo initializes with hooks."""
        async def my_hook(data: Any, id: str, ctx: Any) -> None:
            return None

        config = ReviewConfig(prompt="test")
        reldo = Reldo(config=config, hooks={"PreToolUse": [my_hook]})

        assert reldo is not None
        assert reldo._service._hooks is not None

    def test_init_creates_review_service(self) -> None:
        """Test that init creates internal ReviewService."""
        config = ReviewConfig(
            prompt="You are a reviewer",
            allowed_tools=["Read", "Glob"],
        )
        reldo = Reldo(config=config)

        assert reldo._service is not None


class TestReldoReview:
    """Tests for Reldo.review() method."""

    @pytest.mark.asyncio
    async def test_review_returns_result(self) -> None:
        """Test that review() returns ReviewResult."""
        mock_result = MockResultMessage(
            result="Review complete. PASS.",
            usage={"input_tokens": 100, "output_tokens": 50},
            total_cost_usd=0.001,
            duration_ms=3000,
        )

        async def mock_query_gen() -> AsyncIterator[Any]:
            yield mock_result

        config = ReviewConfig(prompt="You are a reviewer")
        reldo = Reldo(config=config)

        with patch.object(review_service_module, "query", return_value=mock_query_gen()):
            result = await reldo.review("Review app/Models/User.php")

        assert isinstance(result, ReviewResult)
        assert result.text == "Review complete. PASS."
        assert result.total_tokens == 150

    @pytest.mark.asyncio
    async def test_review_passes_prompt_through(self) -> None:
        """Test that review() passes prompt to SDK."""
        captured_prompts: list[str] = []

        async def mock_query_gen() -> AsyncIterator[Any]:
            yield MockResultMessage(result="Done")

        def mock_query(prompt: str, **kwargs: Any) -> AsyncIterator[Any]:
            captured_prompts.append(prompt)
            return mock_query_gen()

        config = ReviewConfig(prompt="test")
        reldo = Reldo(config=config)

        with patch.object(review_service_module, "query", side_effect=mock_query):
            await reldo.review("Review this specific file")

        assert len(captured_prompts) == 1
        assert captured_prompts[0] == "Review this specific file"


class TestReldoIntegration:
    """Integration-style tests for full Reldo flow."""

    @pytest.mark.asyncio
    async def test_full_flow_with_file_config(self) -> None:
        """Test complete flow with file-based config."""
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create config file
            config_file = Path(tmpdir) / "reldo.json"
            config_file.write_text("""{
                "prompt": "You are a code reviewer",
                "allowed_tools": ["Read", "Glob", "Grep"],
                "cwd": "/tmp"
            }""", encoding="utf-8")

            # Load config from file
            config = ReviewConfig.from_file(config_file)

            # Create Reldo instance
            reldo = Reldo(config=config)

            # Mock SDK response
            mock_result = MockResultMessage(
                result="PASS: No issues found.",
                usage={"input_tokens": 500, "output_tokens": 200},
                total_cost_usd=0.002,
                duration_ms=8000,
            )

            async def mock_query_gen() -> AsyncIterator[Any]:
                yield mock_result

            with patch.object(review_service_module, "query", return_value=mock_query_gen()):
                result = await reldo.review("Review app/Models/User.php")

            assert "PASS" in result.text
            assert result.total_tokens == 700
            assert result.total_cost_usd == 0.002

    @pytest.mark.asyncio
    async def test_full_flow_with_hooks(self) -> None:
        """Test complete flow with programmatic hooks."""
        hook_calls: list[str] = []

        async def pre_tool_hook(data: Any, id: str, ctx: Any) -> None:
            hook_calls.append(f"pre_tool:{id}")
            return None

        config = ReviewConfig(prompt="test reviewer")
        reldo = Reldo(config=config, hooks={"PreToolUse": [pre_tool_hook]})

        mock_result = MockResultMessage(result="Done")

        async def mock_query_gen() -> AsyncIterator[Any]:
            yield mock_result

        with patch.object(review_service_module, "query", return_value=mock_query_gen()):
            result = await reldo.review("Quick review")

        # Hooks are passed to SDK, not called directly in our code
        # So we verify the service has the hooks configured
        assert reldo._service._hooks is not None
        assert "PreToolUse" in reldo._service._hooks
