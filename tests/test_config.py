"""Unit tests for config variable substitution."""

import os
from pathlib import Path

import pytest

from reldo.models import ReviewConfig
from reldo.utils import substitute_variables


class TestSubstituteVariables:
    """Tests for substitute_variables function."""

    def test_substitute_cwd(self) -> None:
        """Test ${cwd} substitution."""
        result = substitute_variables("${cwd}/config", Path("/my/project"))
        assert result == "/my/project/config"

    def test_substitute_env_var(self) -> None:
        """Test ${env:VAR_NAME} substitution."""
        os.environ["TEST_RELDO_VAR"] = "test_value"
        try:
            result = substitute_variables("prefix-${env:TEST_RELDO_VAR}-suffix", Path("/tmp"))
            assert result == "prefix-test_value-suffix"
        finally:
            del os.environ["TEST_RELDO_VAR"]

    def test_substitute_missing_env_var_unchanged(self) -> None:
        """Test that missing env var leaves placeholder unchanged."""
        # Make sure the variable doesn't exist
        if "NONEXISTENT_VAR_12345" in os.environ:
            del os.environ["NONEXISTENT_VAR_12345"]

        result = substitute_variables("${env:NONEXISTENT_VAR_12345}", Path("/tmp"))
        assert result == "${env:NONEXISTENT_VAR_12345}"

    def test_substitute_in_list(self) -> None:
        """Test substitution in list values."""
        result = substitute_variables(["${cwd}", "static", "${cwd}/sub"], Path("/my/path"))
        assert result == ["/my/path", "static", "/my/path/sub"]

    def test_substitute_in_dict(self) -> None:
        """Test substitution in dict values."""
        result = substitute_variables(
            {"path": "${cwd}/config", "static": "unchanged"},
            Path("/project")
        )
        assert result == {"path": "/project/config", "static": "unchanged"}

    def test_substitute_nested_structure(self) -> None:
        """Test substitution in nested structures."""
        data = {
            "servers": {
                "test": {
                    "command": "uvx",
                    "args": ["--project", "${cwd}"]
                }
            }
        }
        result = substitute_variables(data, Path("/my/project"))
        assert result["servers"]["test"]["args"] == ["--project", "/my/project"]

    def test_substitute_non_string_unchanged(self) -> None:
        """Test that non-string values are unchanged."""
        assert substitute_variables(42, Path("/tmp")) == 42
        assert substitute_variables(3.14, Path("/tmp")) == 3.14
        assert substitute_variables(True, Path("/tmp")) is True
        assert substitute_variables(None, Path("/tmp")) is None

    def test_substitute_unknown_variable_unchanged(self) -> None:
        """Test that unknown variables are left unchanged."""
        result = substitute_variables("${unknown_pattern}", Path("/tmp"))
        assert result == "${unknown_pattern}"

    def test_multiple_substitutions_in_string(self) -> None:
        """Test multiple substitutions in same string."""
        os.environ["TEST_VAR_A"] = "aaa"
        os.environ["TEST_VAR_B"] = "bbb"
        try:
            result = substitute_variables(
                "${cwd}/${env:TEST_VAR_A}/${env:TEST_VAR_B}",
                Path("/root")
            )
            assert result == "/root/aaa/bbb"
        finally:
            del os.environ["TEST_VAR_A"]
            del os.environ["TEST_VAR_B"]


class TestReviewConfigSubstitution:
    """Tests for variable substitution in ReviewConfig."""

    def test_mcp_servers_substitution(self) -> None:
        """Test that mcp_servers values get substituted."""
        config = ReviewConfig.from_dict({
            "prompt": "test",
            "cwd": "/my/project",
            "mcp_servers": {
                "serena": {
                    "command": "uvx",
                    "args": ["--project", "${cwd}"]
                }
            }
        })

        assert config.mcp_servers["serena"]["args"] == ["--project", "/my/project"]

    def test_agents_substitution(self) -> None:
        """Test that agents values get substituted."""
        os.environ["AGENT_TOOLS_PATH"] = "/tools/bin"
        try:
            config = ReviewConfig.from_dict({
                "prompt": "test",
                "cwd": "/project",
                "agents": {
                    "test-agent": {
                        "description": "Test",
                        "prompt": "${cwd}/agents/test.md",
                        "tools_path": "${env:AGENT_TOOLS_PATH}"
                    }
                }
            })

            assert config.agents["test-agent"]["prompt"] == "/project/agents/test.md"
            assert config.agents["test-agent"]["tools_path"] == "/tools/bin"
        finally:
            del os.environ["AGENT_TOOLS_PATH"]

    def test_no_substitution_in_other_fields(self) -> None:
        """Test that prompt and allowed_tools are not substituted."""
        # The prompt field should NOT be substituted because it's typically
        # a file path that PromptService will resolve separately
        config = ReviewConfig.from_dict({
            "prompt": "${cwd}/prompt.md",
            "allowed_tools": ["Read"],
            "cwd": "/project"
        })

        # Prompt is not substituted - it will be resolved by PromptService
        assert config.prompt == "${cwd}/prompt.md"
