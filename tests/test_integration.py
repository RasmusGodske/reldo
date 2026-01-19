"""Integration tests for Reldo with real API calls.

These tests require an ANTHROPIC_API_KEY environment variable.
They are skipped automatically when the API key is not available.
"""

import os
from pathlib import Path

import pytest

from reldo import Reldo, ReviewConfig


# Skip marker for tests that require API key
requires_api_key = pytest.mark.skipif(
    not os.environ.get("ANTHROPIC_API_KEY"),
    reason="ANTHROPIC_API_KEY not set - skipping integration tests"
)


@requires_api_key
class TestReldoIntegrationWithAPI:
    """Integration tests that make real API calls."""

    @pytest.fixture
    def project_root(self) -> Path:
        """Get the project root directory."""
        # This test file is in reldo/tests/, project root is two levels up
        return Path(__file__).parent.parent.parent

    @pytest.fixture
    def example_config_path(self, project_root: Path) -> Path:
        """Get path to example config."""
        return project_root / ".claude" / "reldo.json"

    @pytest.mark.asyncio
    async def test_review_with_example_config(
        self, project_root: Path, example_config_path: Path
    ) -> None:
        """Test running a review with the example config."""
        if not example_config_path.exists():
            pytest.skip(f"Example config not found: {example_config_path}")

        config = ReviewConfig.from_file(example_config_path)
        # Override cwd to project root
        config = ReviewConfig(
            prompt=config.prompt,
            allowed_tools=config.allowed_tools,
            mcp_servers=config.mcp_servers,
            agents=config.agents,
            output_schema=config.output_schema,
            cwd=project_root,
            timeout_seconds=60,  # Shorter timeout for test
            model=config.model,
            logging={"enabled": False},  # Disable logging for test
        )

        reldo = Reldo(config=config)

        # Simple review that should complete quickly
        result = await reldo.review(
            prompt="Briefly check if app/Models/User.php exists. "
                   "Just say PASS if it exists, FAIL if not."
        )

        assert result.text is not None
        assert len(result.text) > 0
        # Should have some token usage
        assert result.total_tokens > 0

    @pytest.mark.asyncio
    async def test_review_with_inline_config(self, project_root: Path) -> None:
        """Test running a review with inline config."""
        config = ReviewConfig(
            prompt="You are a simple code checker. Just verify the file exists.",
            allowed_tools=["Read", "Glob"],
            cwd=project_root,
            timeout_seconds=60,
            logging={"enabled": False},
        )

        reldo = Reldo(config=config)

        result = await reldo.review(
            prompt="Check if README.md exists in the reldo directory. "
                   "Respond with STATUS: PASS or STATUS: FAIL."
        )

        assert result.text is not None
        assert "STATUS:" in result.text.upper() or "PASS" in result.text.upper()


class TestConfigValidation:
    """Tests for config validation without API calls."""

    def test_example_config_loads(self) -> None:
        """Test that the example config file loads correctly."""
        project_root = Path(__file__).parent.parent.parent
        config_path = project_root / ".claude" / "reldo.json"

        if not config_path.exists():
            pytest.skip(f"Example config not found: {config_path}")

        config = ReviewConfig.from_file(config_path)

        assert config.prompt == ".claude/reldo/orchestrator.md"
        assert "Read" in config.allowed_tools
        assert "Task" in config.allowed_tools
        assert "backend-reviewer" in config.agents
        assert "frontend-reviewer" in config.agents

    def test_example_prompts_exist(self) -> None:
        """Test that example prompt files exist."""
        project_root = Path(__file__).parent.parent.parent

        prompts = [
            ".claude/reldo/orchestrator.md",
            ".claude/reldo/agents/backend-reviewer.md",
            ".claude/reldo/agents/frontend-reviewer.md",
        ]

        for prompt_path in prompts:
            full_path = project_root / prompt_path
            if not full_path.exists():
                pytest.skip(f"Prompt file not found: {full_path}")

            content = full_path.read_text()
            assert "<role>" in content, f"{prompt_path} missing <role>"
            assert "<instructions>" in content, f"{prompt_path} missing <instructions>"

    def test_example_prompts_have_structure(self) -> None:
        """Test that example prompts follow expected structure."""
        project_root = Path(__file__).parent.parent.parent
        orchestrator_path = project_root / ".claude/reldo/orchestrator.md"

        if not orchestrator_path.exists():
            pytest.skip("Orchestrator prompt not found")

        content = orchestrator_path.read_text()

        # Should have role and instructions sections
        assert "<role>" in content
        assert "</role>" in content
        assert "<instructions>" in content
        assert "</instructions>" in content

        # Should mention STATUS: PASS/FAIL
        assert "STATUS: PASS" in content
        assert "STATUS: FAIL" in content
