"""Unit tests for PromptService."""

import tempfile
from pathlib import Path

import pytest

from reldo.services import PromptService


class TestPromptService:
    """Tests for PromptService."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.service = PromptService()

    def test_load_inline_string(self) -> None:
        """Test that inline strings are returned as-is."""
        result = self.service.load("You are a code reviewer", cwd=Path("/tmp"))
        assert result == "You are a code reviewer"

    def test_load_inline_multiline(self) -> None:
        """Test that multiline inline strings work."""
        prompt = """You are a code reviewer.

Review the code for:
- Type safety
- Naming conventions
"""
        result = self.service.load(prompt, cwd=Path("/tmp"))
        assert result == prompt

    def test_load_from_md_file(self) -> None:
        """Test loading prompt from .md file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            prompt_path = Path(tmpdir) / "prompt.md"
            prompt_path.write_text("You are a code reviewer.", encoding="utf-8")

            result = self.service.load("prompt.md", cwd=Path(tmpdir))
            assert result == "You are a code reviewer."

    def test_load_from_txt_file(self) -> None:
        """Test loading prompt from .txt file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            prompt_path = Path(tmpdir) / "prompt.txt"
            prompt_path.write_text("Review this code", encoding="utf-8")

            result = self.service.load("prompt.txt", cwd=Path(tmpdir))
            assert result == "Review this code"

    def test_load_relative_path(self) -> None:
        """Test loading from relative path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create nested directory
            agents_dir = Path(tmpdir) / "agents"
            agents_dir.mkdir()
            prompt_path = agents_dir / "backend.md"
            prompt_path.write_text("Backend reviewer", encoding="utf-8")

            result = self.service.load("agents/backend.md", cwd=Path(tmpdir))
            assert result == "Backend reviewer"

    def test_load_absolute_path(self) -> None:
        """Test loading from absolute path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            prompt_path = Path(tmpdir) / "prompt.md"
            prompt_path.write_text("Absolute path prompt", encoding="utf-8")

            # Use absolute path
            result = self.service.load(str(prompt_path), cwd=Path("/different/cwd"))
            assert result == "Absolute path prompt"

    def test_load_missing_file_raises(self) -> None:
        """Test that missing file raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError, match="Prompt file not found"):
            self.service.load("nonexistent.md", cwd=Path("/tmp"))

    def test_inline_string_not_treated_as_path(self) -> None:
        """Test that strings without file extensions are treated as inline."""
        # This string should NOT be treated as a file path
        result = self.service.load("Review the code carefully", cwd=Path("/tmp"))
        assert result == "Review the code carefully"

    def test_is_file_path_with_md_extension(self) -> None:
        """Test _is_file_path with .md extension."""
        assert self.service._is_file_path("prompt.md", Path("/tmp")) is True

    def test_is_file_path_with_txt_extension(self) -> None:
        """Test _is_file_path with .txt extension."""
        assert self.service._is_file_path("prompt.txt", Path("/tmp")) is True

    def test_is_file_path_with_existing_file(self) -> None:
        """Test _is_file_path with existing file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            prompt_path = Path(tmpdir) / "my_prompt"  # No extension
            prompt_path.write_text("test", encoding="utf-8")

            assert self.service._is_file_path("my_prompt", Path(tmpdir)) is True

    def test_is_file_path_with_inline_string(self) -> None:
        """Test _is_file_path with inline string."""
        assert self.service._is_file_path("You are a reviewer", Path("/tmp")) is False
