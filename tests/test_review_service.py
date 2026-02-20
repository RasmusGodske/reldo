"""Unit tests for ReviewService with mocked SDK."""

import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, AsyncIterator
from unittest.mock import MagicMock, patch

import pytest

from importlib import import_module

from reldo.models import ReviewConfig
from reldo.services import ReviewService

# Import the actual module (not the class) for patching
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


class TestReviewService:
    """Tests for ReviewService."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.config = ReviewConfig(
            prompt="You are a code reviewer",
            allowed_tools=["Read", "Glob", "Grep"],
            cwd=Path("/tmp/test-project"),
        )

    def test_init_stores_config(self) -> None:
        """Test that __init__ stores config."""
        service = ReviewService(self.config)
        assert service._config == self.config
        assert service._hooks is None

    def test_init_with_hooks(self) -> None:
        """Test that __init__ stores hooks."""
        hooks = {"PreToolUse": [MagicMock()]}
        service = ReviewService(self.config, hooks=hooks)
        assert service._hooks == hooks

    def test_get_cwd_from_path(self) -> None:
        """Test _get_cwd with Path cwd."""
        service = ReviewService(self.config)
        assert service._get_cwd() == Path("/tmp/test-project")

    def test_get_cwd_from_string(self) -> None:
        """Test _get_cwd with string cwd."""
        config = ReviewConfig(prompt="test", cwd="/tmp/string-path")
        service = ReviewService(config)
        assert service._get_cwd() == Path("/tmp/string-path")

    def test_build_agent_options_inline_prompt(self) -> None:
        """Test _build_agent_options with inline prompt."""
        service = ReviewService(self.config)
        isolated_cwd = Path(tempfile.mkdtemp(prefix="reldo-test-"))
        options = service._build_agent_options(isolated_cwd)

        assert "You are a code reviewer" in options.system_prompt
        assert options.allowed_tools == ["Read", "Glob", "Grep"]
        assert options.cwd == str(isolated_cwd)
        assert options.permission_mode == "bypassPermissions"

    def test_build_agent_options_file_prompt(self) -> None:
        """Test _build_agent_options with file prompt."""
        with tempfile.TemporaryDirectory() as tmpdir:
            prompt_file = Path(tmpdir) / "orchestrator.md"
            prompt_file.write_text("# Orchestrator\nYou review code.", encoding="utf-8")

            config = ReviewConfig(
                prompt="orchestrator.md",
                cwd=tmpdir,
            )
            service = ReviewService(config)
            isolated_cwd = Path(tempfile.mkdtemp(prefix="reldo-test-"))
            options = service._build_agent_options(isolated_cwd)

            assert "You review code" in options.system_prompt

    def test_build_agent_options_with_mcp_servers(self) -> None:
        """Test that mcp_servers are passed through."""
        config = ReviewConfig(
            prompt="test",
            mcp_servers={
                "test-server": {
                    "command": "echo",
                    "args": ["hello"]
                }
            }
        )
        service = ReviewService(config)
        isolated_cwd = Path(tempfile.mkdtemp(prefix="reldo-test-"))
        options = service._build_agent_options(isolated_cwd)

        assert "test-server" in options.mcp_servers

    def test_build_agent_options_with_model(self) -> None:
        """Test that model is passed through."""
        config = ReviewConfig(
            prompt="test",
            model="claude-opus-4-20250514"
        )
        service = ReviewService(config)
        isolated_cwd = Path(tempfile.mkdtemp(prefix="reldo-test-"))
        options = service._build_agent_options(isolated_cwd)

        assert options.model == "claude-opus-4-20250514"

    def test_build_agent_options_with_hooks(self) -> None:
        """Test that hooks are passed through."""
        hooks = {"PreToolUse": [MagicMock()]}
        service = ReviewService(self.config, hooks=hooks)
        isolated_cwd = Path(tempfile.mkdtemp(prefix="reldo-test-"))
        options = service._build_agent_options(isolated_cwd)

        assert options.hooks == hooks


class TestReviewServiceAsync:
    """Async tests for ReviewService review method."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.config = ReviewConfig(
            prompt="You are a code reviewer",
            allowed_tools=["Read", "Glob", "Grep"],
            cwd=Path("/tmp/test-project"),
        )

    @pytest.mark.asyncio
    async def test_review_collects_result(self) -> None:
        """Test that review() collects and returns result."""
        # Create mock messages
        mock_text = MockMessage(content=[MockTextBlock("Reviewing...")])
        mock_result = MockResultMessage(
            result="Review complete. PASS.",
            usage={"input_tokens": 100, "output_tokens": 50},
            total_cost_usd=0.001,
            duration_ms=3000,
        )

        # Create async generator for query
        async def mock_query_gen() -> AsyncIterator[Any]:
            yield mock_text
            yield mock_result

        with patch.object(review_service_module, "query", return_value=mock_query_gen()):
            service = ReviewService(self.config)
            result = await service.review("Review app/Models/User.php")

        assert result.text == "Review complete. PASS."
        assert result.input_tokens == 100
        assert result.output_tokens == 50
        assert result.total_tokens == 150
        assert result.total_cost_usd == 0.001
        assert result.duration_ms == 3000

    @pytest.mark.asyncio
    async def test_review_fallback_without_result_message(self) -> None:
        """Test review() fallback when no ResultMessage."""
        mock_text = MockMessage(content=[MockTextBlock("Some output")])

        async def mock_query_gen() -> AsyncIterator[Any]:
            yield mock_text

        with patch.object(review_service_module, "query", return_value=mock_query_gen()):
            service = ReviewService(self.config)
            result = await service.review("Review something")

        assert result.text == "Some output"
        assert result.input_tokens == 0
        assert result.output_tokens == 0

    @pytest.mark.asyncio
    async def test_review_multiple_text_blocks(self) -> None:
        """Test that multiple text blocks are collected."""
        mock_text1 = MockMessage(content=[MockTextBlock("Part 1")])
        mock_text2 = MockMessage(content=[MockTextBlock("Part 2")])

        async def mock_query_gen() -> AsyncIterator[Any]:
            yield mock_text1
            yield mock_text2

        with patch.object(review_service_module, "query", return_value=mock_query_gen()):
            service = ReviewService(self.config)
            result = await service.review("Review")

        assert "Part 1" in result.text
        assert "Part 2" in result.text


class TestReviewServiceStreaming:
    """Tests for on_text callback."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.config = ReviewConfig(
            prompt="You are a code reviewer",
            allowed_tools=["Read", "Glob", "Grep"],
            cwd=Path("/tmp/test-project"),
        )

    @pytest.mark.asyncio
    async def test_on_text_called_with_final_result(self) -> None:
        """Test that on_text is called once with the final result text."""
        mock_text1 = MockMessage(content=[MockTextBlock("Intermediate 1")])
        mock_text2 = MockMessage(content=[MockTextBlock("Intermediate 2")])
        mock_result = MockResultMessage(result="Final result")

        streamed: list[str] = []

        async def mock_query_gen() -> AsyncIterator[Any]:
            yield mock_text1
            yield mock_text2
            yield mock_result

        with patch.object(review_service_module, "query", return_value=mock_query_gen()):
            service = ReviewService(self.config)
            await service.review("Review", on_text=streamed.append)

        # Only the final result, not intermediate messages
        assert streamed == ["Final result"]

    @pytest.mark.asyncio
    async def test_on_text_not_called_without_callback(self) -> None:
        """Test that review works fine without on_text."""
        mock_text = MockMessage(content=[MockTextBlock("Output")])
        mock_result = MockResultMessage(result="Done")

        async def mock_query_gen() -> AsyncIterator[Any]:
            yield mock_text
            yield mock_result

        with patch.object(review_service_module, "query", return_value=mock_query_gen()):
            service = ReviewService(self.config)
            result = await service.review("Review")

        assert result.text == "Done"

    @pytest.mark.asyncio
    async def test_on_text_with_fallback_result(self) -> None:
        """Test that on_text receives fallback text when no ResultMessage."""
        mock_text = MockMessage(content=[MockTextBlock("Fallback output")])

        streamed: list[str] = []

        async def mock_query_gen() -> AsyncIterator[Any]:
            yield mock_text

        with patch.object(review_service_module, "query", return_value=mock_query_gen()):
            service = ReviewService(self.config)
            await service.review("Review", on_text=streamed.append)

        assert streamed == ["Fallback output"]


class TestReviewServiceIntegration:
    """Integration-style tests for ReviewService (still mocked)."""

    @pytest.mark.asyncio
    async def test_full_review_flow(self) -> None:
        """Test complete review flow with realistic data."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create orchestrator prompt
            prompt_file = Path(tmpdir) / "orchestrator.md"
            prompt_file.write_text("""# Code Review Orchestrator

You coordinate code reviews by checking files against project conventions.
""", encoding="utf-8")

            config = ReviewConfig(
                prompt="orchestrator.md",
                allowed_tools=["Read", "Glob", "Grep", "Bash", "Task"],
                cwd=tmpdir,
                model="claude-sonnet-4-20250514",
            )

            # Mock SDK response
            mock_result = MockResultMessage(
                result="Review complete. STATUS: PASS. No violations found.",
                usage={"input_tokens": 2000, "output_tokens": 800},
                total_cost_usd=0.01,
                duration_ms=15000,
            )

            async def mock_query_gen() -> AsyncIterator[Any]:
                yield mock_result

            with patch.object(review_service_module, "query", return_value=mock_query_gen()):
                service = ReviewService(config)
                result = await service.review(
                    "Review app/Models/User.php for backend conventions"
                )

            assert "PASS" in result.text
            assert result.total_tokens == 2800
            assert result.total_cost_usd == 0.01
