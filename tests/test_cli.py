"""Unit tests for CLI module."""

import io
import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock

import pytest

from reldo.cli import (
    create_parser,
    read_prompt,
    load_config,
    format_result,
    check_review_passed,
    main,
    run_review,
    run_init,
)
from reldo.models import ReviewConfig, ReviewResult


class TestCreateParser:
    """Tests for create_parser function."""

    def test_parser_has_version(self) -> None:
        """Test that parser has --version flag."""
        parser = create_parser()
        # Version action raises SystemExit with version string
        with pytest.raises(SystemExit):
            parser.parse_args(["--version"])

    def test_parser_has_review_subcommand(self) -> None:
        """Test that parser has review subcommand."""
        parser = create_parser()
        args = parser.parse_args(["review", "Test"])
        assert args.command == "review"
        assert args.prompt == "Test"

    def test_review_has_all_options(self) -> None:
        """Test that review command has all options."""
        parser = create_parser()
        args = parser.parse_args([
            "review",
            "Test",
            "--config", "custom.json",
            "--cwd", "/tmp",
            "--json",
            "--verbose",
            "--no-log",
            "--exit-code",
        ])

        assert args.prompt == "Test"
        assert args.config == "custom.json"
        assert args.cwd == "/tmp"
        assert args.json_output is True
        assert args.verbose is True
        assert args.no_log is True
        assert args.exit_code is True

    def test_review_default_config(self) -> None:
        """Test that config default is None (uses sensible defaults)."""
        parser = create_parser()
        args = parser.parse_args(["review", "Test"])
        assert args.config is None


class TestReadPrompt:
    """Tests for read_prompt function."""

    def test_read_prompt_from_arg(self) -> None:
        """Test reading prompt from argument."""
        prompt = read_prompt("Test prompt")
        assert prompt == "Test prompt"

    def test_read_prompt_from_stdin(self) -> None:
        """Test reading prompt from stdin."""
        with patch.object(sys, "stdin", io.StringIO("Stdin prompt\n")):
            prompt = read_prompt("-")
            assert prompt == "Stdin prompt"

    def test_read_prompt_stdin_strips_whitespace(self) -> None:
        """Test that stdin prompt is stripped."""
        with patch.object(sys, "stdin", io.StringIO("  Trimmed  \n\n")):
            prompt = read_prompt("-")
            assert prompt == "Trimmed"


class TestLoadConfig:
    """Tests for load_config function."""

    def test_load_config_from_file(self) -> None:
        """Test loading config from file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / "config.json"
            config_file.write_text('{"prompt": "Test reviewer"}', encoding="utf-8")

            config = load_config(str(config_file), None)
            assert config.prompt == "Test reviewer"

    def test_load_config_relative_path(self) -> None:
        """Test loading config from relative path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / ".claude" / "reldo.json"
            config_file.parent.mkdir(parents=True)
            config_file.write_text('{"prompt": "Relative config"}', encoding="utf-8")

            config = load_config(".claude/reldo.json", tmpdir)
            assert config.prompt == "Relative config"

    def test_load_config_missing_uses_defaults(self) -> None:
        """Test that missing config uses sensible defaults."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = load_config(None, tmpdir)
            # Should return a valid config with defaults
            assert config.prompt is not None
            assert config.allowed_tools is not None
            assert config.cwd == Path(tmpdir)

    def test_load_config_with_cwd_override(self) -> None:
        """Test that cwd override works."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / "config.json"
            config_file.write_text('{"prompt": "Test", "cwd": "/original"}', encoding="utf-8")

            config = load_config(str(config_file), "/override")
            assert config.cwd == Path("/override")


class TestFormatResult:
    """Tests for format_result function."""

    def test_format_as_text(self) -> None:
        """Test formatting result as plain text."""
        result = ReviewResult(text="Review passed")
        output = format_result(result, as_json=False)
        assert output == "Review passed"

    def test_format_as_json(self) -> None:
        """Test formatting result as JSON."""
        result = ReviewResult(
            text="PASS: All good",
            input_tokens=100,
            output_tokens=50,
            total_tokens=150,
            total_cost_usd=0.001,
            duration_ms=5000,
        )
        output = format_result(result, as_json=True)
        data = json.loads(output)

        assert data["text"] == "PASS: All good"
        assert data["input_tokens"] == 100
        assert data["output_tokens"] == 50
        assert data["total_tokens"] == 150
        assert data["total_cost_usd"] == 0.001
        assert data["duration_ms"] == 5000


class TestCheckReviewPassed:
    """Tests for check_review_passed function."""

    def test_pass_with_status_pass(self) -> None:
        """Test that STATUS: PASS indicates pass."""
        result = ReviewResult(text="STATUS: PASS\nAll checks succeeded")
        assert check_review_passed(result) is True

    def test_fail_with_status_fail(self) -> None:
        """Test that STATUS: FAIL indicates failure."""
        result = ReviewResult(text="STATUS: FAIL\n3 violations found")
        assert check_review_passed(result) is False

    def test_pass_with_pass_prefix(self) -> None:
        """Test that PASS: prefix indicates pass."""
        result = ReviewResult(text="PASS: No issues found")
        assert check_review_passed(result) is True

    def test_fail_with_fail_prefix(self) -> None:
        """Test that FAIL: prefix indicates failure."""
        result = ReviewResult(text="FAIL: Missing documentation")
        assert check_review_passed(result) is False

    def test_default_to_pass(self) -> None:
        """Test that ambiguous text defaults to pass."""
        result = ReviewResult(text="Review complete. Some notes here.")
        assert check_review_passed(result) is True

    def test_case_insensitive(self) -> None:
        """Test that detection is case insensitive."""
        result = ReviewResult(text="status: pass")
        assert check_review_passed(result) is True

        result = ReviewResult(text="Status: Fail")
        assert check_review_passed(result) is False


class TestMain:
    """Tests for main function."""

    def test_main_no_command_shows_help(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Test that no command shows help."""
        with patch.object(sys, "argv", ["reldo"]):
            exit_code = main()
            assert exit_code == 0

        captured = capsys.readouterr()
        assert "reldo" in captured.out
        assert "review" in captured.out


class TestRunReview:
    """Tests for run_review function."""

    @pytest.mark.asyncio
    async def test_run_review_explicit_config_not_found(self) -> None:
        """Test that explicitly specified missing config returns error."""
        args = MagicMock()
        args.prompt = "Test"
        args.config = "/nonexistent.json"  # Explicit path that doesn't exist
        args.cwd = None
        args.json_output = False
        args.verbose = False
        args.no_log = False
        args.exit_code = False

        exit_code = await run_review(args)
        assert exit_code == 1

    @pytest.mark.asyncio
    async def test_run_review_no_config_uses_defaults(self) -> None:
        """Test that no config uses sensible defaults."""
        with tempfile.TemporaryDirectory() as tmpdir:
            args = MagicMock()
            args.prompt = "Review this"
            args.config = None  # No explicit config
            args.cwd = tmpdir
            args.json_output = False
            args.verbose = False
            args.no_log = True
            args.exit_code = False

            mock_result = ReviewResult(text="STATUS: PASS\nAll good")

            with patch("reldo.cli.Reldo") as MockReldo:
                mock_instance = MagicMock()
                mock_instance.review = AsyncMock(return_value=mock_result)
                MockReldo.return_value = mock_instance

                exit_code = await run_review(args)

            assert exit_code == 0

    @pytest.mark.asyncio
    async def test_run_review_success(self) -> None:
        """Test successful review run."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create config
            config_file = Path(tmpdir) / "config.json"
            config_file.write_text('{"prompt": "Test"}', encoding="utf-8")

            args = MagicMock()
            args.prompt = "Review this"
            args.config = str(config_file)
            args.cwd = tmpdir
            args.json_output = False
            args.verbose = False
            args.no_log = True
            args.exit_code = False

            # Mock the Reldo class
            mock_result = ReviewResult(text="STATUS: PASS\nAll good")

            with patch("reldo.cli.Reldo") as MockReldo:
                mock_instance = MagicMock()
                mock_instance.review = AsyncMock(return_value=mock_result)
                MockReldo.return_value = mock_instance

                exit_code = await run_review(args)

            assert exit_code == 0

    @pytest.mark.asyncio
    async def test_run_review_exit_code_on_failure(self) -> None:
        """Test that exit-code returns 1 on failure."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / "config.json"
            config_file.write_text('{"prompt": "Test"}', encoding="utf-8")

            args = MagicMock()
            args.prompt = "Review this"
            args.config = str(config_file)
            args.cwd = tmpdir
            args.json_output = False
            args.verbose = False
            args.no_log = True
            args.exit_code = True  # Enable exit code

            mock_result = ReviewResult(text="STATUS: FAIL\nViolations found")

            with patch("reldo.cli.Reldo") as MockReldo:
                mock_instance = MagicMock()
                mock_instance.review = AsyncMock(return_value=mock_result)
                MockReldo.return_value = mock_instance

                exit_code = await run_review(args)

            assert exit_code == 1


class TestCLIHelp:
    """Tests for CLI help output."""

    def test_help_shows_options(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Test that help shows all options."""
        parser = create_parser()

        with pytest.raises(SystemExit):
            parser.parse_args(["review", "--help"])

        captured = capsys.readouterr()
        assert "PROMPT" in captured.out  # Positional argument
        assert "--config" in captured.out
        assert "--json" in captured.out
        assert "--verbose" in captured.out
        assert "--no-log" in captured.out
        assert "--exit-code" in captured.out


class TestRunInit:
    """Tests for run_init function."""

    def test_init_creates_directory_structure(self) -> None:
        """Test that init creates .reldo directory structure."""
        with tempfile.TemporaryDirectory() as tmpdir:
            original_cwd = Path.cwd()
            try:
                import os
                os.chdir(tmpdir)

                args = MagicMock()
                args.force = False

                exit_code = run_init(args)

                assert exit_code == 0
                assert (Path(tmpdir) / ".reldo").exists()
                assert (Path(tmpdir) / ".reldo" / "settings.json").exists()
                assert (Path(tmpdir) / ".reldo" / "orchestrator.md").exists()
                assert (Path(tmpdir) / ".reldo" / ".gitignore").exists()
                assert (Path(tmpdir) / ".reldo" / "sessions").exists()
                assert (Path(tmpdir) / ".reldo" / "agents").exists()
            finally:
                os.chdir(original_cwd)

    def test_init_settings_contains_config(self) -> None:
        """Test that settings.json contains valid config."""
        with tempfile.TemporaryDirectory() as tmpdir:
            original_cwd = Path.cwd()
            try:
                import os
                os.chdir(tmpdir)

                args = MagicMock()
                args.force = False

                run_init(args)

                settings_path = Path(tmpdir) / ".reldo" / "settings.json"
                config = json.loads(settings_path.read_text(encoding="utf-8"))
                assert config["prompt"] == ".reldo/orchestrator.md"
                assert "allowed_tools" in config
                assert "model" in config
            finally:
                os.chdir(original_cwd)

    def test_init_fails_if_exists_without_force(self) -> None:
        """Test that init fails if .reldo exists without --force."""
        with tempfile.TemporaryDirectory() as tmpdir:
            original_cwd = Path.cwd()
            try:
                import os
                os.chdir(tmpdir)

                # Create existing .reldo directory
                (Path(tmpdir) / ".reldo").mkdir()

                args = MagicMock()
                args.force = False

                exit_code = run_init(args)
                assert exit_code == 1
            finally:
                os.chdir(original_cwd)

    def test_init_succeeds_with_force(self) -> None:
        """Test that init succeeds with --force even if .reldo exists."""
        with tempfile.TemporaryDirectory() as tmpdir:
            original_cwd = Path.cwd()
            try:
                import os
                os.chdir(tmpdir)

                # Create existing .reldo directory
                (Path(tmpdir) / ".reldo").mkdir()

                args = MagicMock()
                args.force = True

                exit_code = run_init(args)
                assert exit_code == 0
                assert (Path(tmpdir) / ".reldo" / "settings.json").exists()
            finally:
                os.chdir(original_cwd)

    def test_parser_has_init_subcommand(self) -> None:
        """Test that parser has init subcommand."""
        parser = create_parser()
        args = parser.parse_args(["init"])
        assert args.command == "init"
        assert args.force is False

    def test_parser_init_with_force(self) -> None:
        """Test that init command accepts --force flag."""
        parser = create_parser()
        args = parser.parse_args(["init", "--force"])
        assert args.command == "init"
        assert args.force is True
