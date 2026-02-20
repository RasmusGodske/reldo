"""Core review service that orchestrates Claude Agent SDK calls."""

import shutil
import tempfile
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from claude_agent_sdk import ClaudeAgentOptions, ResultMessage, query
from claude_agent_sdk.types import AgentDefinition

from ..defaults import DEFAULT_SETTING_SOURCES
from ..models.ReviewConfig import ReviewConfig
from ..models.ReviewResult import ReviewResult
from .LoggingService import LoggingService
from .PromptService import PromptService


class ReviewService:
    """Orchestrates code reviews using the Claude Agent SDK.

    This is the core service that:
    - Builds ClaudeAgentOptions from ReviewConfig
    - Loads orchestrator and agent prompts
    - Calls the SDK's query() function
    - Collects results and builds ReviewResult

    Attributes:
        _config: The review configuration.
        _hooks: Optional hooks for SDK integration.
        _prompt_service: Service for loading prompts from files.
    """

    def __init__(self, config: ReviewConfig, hooks: dict[str, Any] | None = None) -> None:
        """Initialize the review service.

        Args:
            config: Review configuration.
            hooks: Optional hooks dict to pass through to SDK.
        """
        self._config = config
        self._hooks = hooks
        self._prompt_service = PromptService()
        self._logging_service: LoggingService | None = None

        # Initialize logging if enabled
        logging_config = config.logging
        if logging_config.get("enabled", True):
            output_dir = self._get_cwd() / logging_config.get("output_dir", ".reldo")
            verbose = logging_config.get("verbose", False)
            self._logging_service = LoggingService(output_dir=output_dir, verbose=verbose)

    def _get_cwd(self) -> Path:
        """Get the working directory as a Path."""
        cwd = self._config.cwd
        if isinstance(cwd, str):
            return Path(cwd)
        return cwd

    def _load_orchestrator_prompt(self) -> str:
        """Load the orchestrator prompt from config.

        Returns:
            The orchestrator prompt content.
        """
        return self._prompt_service.load(self._config.prompt, self._get_cwd())

    def _load_agents(self) -> dict[str, AgentDefinition] | None:
        """Load agent definitions from config, resolving prompt file paths.

        Transforms reldo's agent config (with file paths) into SDK-compatible
        AgentDefinition dataclass instances (with actual prompt content).

        Returns:
            Dictionary of agent definitions, or None if no agents configured.
        """
        if not self._config.agents:
            return None

        agents: dict[str, AgentDefinition] = {}
        cwd = self._get_cwd()

        for agent_name, agent_config in self._config.agents.items():
            # Load prompt content from file path
            prompt_path = agent_config.get("prompt", "")
            prompt_content = self._prompt_service.load(prompt_path, cwd)

            # Build SDK-compatible AgentDefinition dataclass instance
            agent_def = AgentDefinition(
                description=agent_config.get("description", ""),
                prompt=prompt_content,
                tools=agent_config.get("tools"),
                model=agent_config.get("model"),
            )

            agents[agent_name] = agent_def

        return agents if agents else None

    def _create_isolated_cwd(self) -> Path:
        """Create an isolated temporary working directory for the inner Claude Code subprocess.

        Background — the problem:
            Claude Code's Bash tool captures command output by writing it to a temp
            file at ``/tmp/claude-{uid}/{project-path}/tasks/{id}.output``. It reads
            this file **by path** after the subprocess exits.

            The Claude Agent SDK spawns an inner Claude Code CLI subprocess. During
            initialization (~400 ms after connect), the inner CLI scans
            ``/tmp/claude-{uid}/{project-path}/tasks/`` and deletes stale task files.
            If the inner CLI shares the same working directory as the parent, it
            deletes the parent's **active** output file. The file descriptor stays
            valid (``st_nlink`` drops to 0 but writes still succeed), so reldo
            finishes normally — but when the Bash tool tries to read the file by path,
            it's gone. The parent sees zero output: "Tool ran without output or errors".

        The fix:
            Use an isolated temp directory as the inner CLI's ``--cwd`` and add the
            real project directory via ``--add-dir``. The inner CLI now derives a
            different tasks path (``/tmp/claude-{uid}/{temp-path}/tasks/``) and never
            touches the parent's output file. The system prompt is prepended with the
            project path so the inner CLI resolves relative file paths correctly.

        Removal criteria:
            This workaround can be removed if a future Claude Code version stops
            cleaning up sibling task files on startup, or if the Bash tool switches
            from path-based reads to fd-based reads.

        Returns:
            Path to the isolated temporary directory.
        """
        return Path(tempfile.mkdtemp(prefix="reldo-"))

    def _cleanup_isolated_cwd(self, isolated_cwd: Path) -> None:
        """Remove the isolated temporary working directory.

        Args:
            isolated_cwd: Path to the temp directory to remove.
        """
        shutil.rmtree(isolated_cwd, ignore_errors=True)

    def _build_agent_options(self, isolated_cwd: Path) -> ClaudeAgentOptions:
        """Build ClaudeAgentOptions from config.

        Maps ReviewConfig properties to SDK options:
        - prompt → system_prompt
        - allowed_tools → allowed_tools
        - mcp_servers → mcp_servers
        - setting_sources → setting_sources (defaults to ['project'] for .claude/agents/)
        - agents → agents (with prompt files loaded, merged with discovered agents)
        - cwd → isolated temp dir (to prevent task file cleanup conflicts)
        - add_dirs → [actual project dir] (so the inner CLI can access project files)
        - model → model
        - hooks → hooks

        Args:
            isolated_cwd: Isolated temp directory for the inner Claude Code subprocess.

        Returns:
            ClaudeAgentOptions instance configured from self._config.
        """
        system_prompt = self._load_orchestrator_prompt()
        agents = self._load_agents()

        # Use configured setting_sources or default to ['project'] for .claude/agents/ discovery
        setting_sources = self._config.setting_sources
        if setting_sources is None:
            setting_sources = DEFAULT_SETTING_SOURCES

        project_dir = str(self._get_cwd())

        # Prepend project directory context to system prompt so the inner CLI
        # resolves file paths correctly (since CWD is the isolated temp dir)
        system_prompt = (
            f"Your primary working directory is: {project_dir}\n"
            f"Always resolve file paths relative to {project_dir}.\n\n"
            + system_prompt
        )

        # Build base options
        options_kwargs: dict[str, Any] = {
            "system_prompt": system_prompt,
            "allowed_tools": self._config.allowed_tools,
            "mcp_servers": self._config.mcp_servers,
            "setting_sources": setting_sources,
            "cwd": str(isolated_cwd),
            "add_dirs": [project_dir],
            "model": self._config.model if self._config.model else None,
            "max_turns": (
                self._config.timeout_seconds // 10 if self._config.timeout_seconds else None
            ),
            "hooks": self._hooks,
            "permission_mode": "bypassPermissions",  # Allow all tools in review context
        }

        # Only pass agents if explicitly configured (empty dict or None = let SDK auto-discover)
        if agents:
            options_kwargs["agents"] = agents

        options = ClaudeAgentOptions(**options_kwargs)

        return options

    def _get_config_snapshot(self) -> dict[str, Any]:
        """Create a snapshot of the config for logging.

        Returns:
            Dictionary representation of config (without Path objects).
        """
        return {
            "prompt": self._config.prompt,
            "allowed_tools": self._config.allowed_tools,
            "model": self._config.model,
            "timeout_seconds": self._config.timeout_seconds,
            "cwd": str(self._config.cwd),
        }

    async def review(
        self,
        prompt: str,
        on_text: Callable[[str], None] | None = None,
        on_progress: Callable[[str], None] | None = None,
    ) -> ReviewResult:
        """Run a code review.

        Uses an isolated temporary directory as the inner Claude Code CLI's working
        directory to prevent a task file cleanup conflict. Without this, the inner
        CLI deletes the parent's Bash tool output file during initialization,
        causing the parent to capture zero output. See ``_create_isolated_cwd``
        for the full explanation.

        Args:
            prompt: The review prompt (what to review).
            on_text: Optional callback invoked with the final result text once available.
                     Intermediate agent messages are NOT streamed — only the final
                     review output is passed to this callback.
            on_progress: Optional callback invoked with short status strings as the
                         review progresses. Intended for lightweight progress reporting
                         (e.g., writing to stderr) — emits at most a handful of lines.

        Returns:
            ReviewResult with the review outcome.
        """
        start_time = time.time()
        isolated_cwd = self._create_isolated_cwd()
        try:
            return await self._run_review(
                prompt=prompt,
                on_text=on_text,
                on_progress=on_progress,
                isolated_cwd=isolated_cwd,
                start_time=start_time,
            )
        finally:
            self._cleanup_isolated_cwd(isolated_cwd)

    async def _run_review(
        self,
        prompt: str,
        on_text: Callable[[str], None] | None,
        on_progress: Callable[[str], None] | None,
        isolated_cwd: Path,
        start_time: float,
    ) -> ReviewResult:
        """Internal review implementation.

        Args:
            prompt: The review prompt.
            on_text: Optional text callback.
            on_progress: Optional progress callback.
            isolated_cwd: Isolated temp directory for the inner CLI.
            start_time: Review start timestamp.

        Returns:
            ReviewResult with the review outcome.
        """
        options = self._build_agent_options(isolated_cwd)

        # Start logging session if enabled
        session_id: str | None = None
        if self._logging_service:
            session_id = self._logging_service.start_session(
                prompt=prompt, config=self._get_config_snapshot()
            )

        # Collect all text output and messages for transcript
        text_parts: list[str] = []
        all_messages: list[Any] = []
        result_message: ResultMessage | None = None

        # Progress tracking — emit a few status lines without flooding output.
        # At most: 1 "connected" line + up to 3 periodic turn updates.
        got_first_message = False
        tool_call_count = 0
        last_tool_name = ""
        agent_turn_count = 0
        progress_updates_emitted = 0
        max_progress_updates = 3
        # Emit at turns 3, 6, 12 (doubling interval to stay under the cap)
        next_progress_turn = 3

        # Stream through the query results
        async for message in query(prompt=prompt, options=options):
            all_messages.append(message)

            # Handle different message types
            # Use duck typing: ResultMessage has 'session_id' and 'usage' but no 'content'
            if hasattr(message, "session_id") and hasattr(message, "usage"):
                result_message = message  # type: ignore[assignment]
            elif hasattr(message, "content"):
                # Track progress milestones
                if on_progress:
                    if not got_first_message:
                        got_first_message = True
                        on_progress("Agent connected, reviewing...")

                    for block in getattr(message, "content", []):
                        if hasattr(block, "name"):
                            tool_call_count += 1
                            last_tool_name = block.name

                    # Count agent turns (assistant messages that aren't tool-result follow-ups)
                    if not getattr(message, "parent_tool_use_id", None):
                        agent_turn_count += 1

                        if (
                            agent_turn_count >= next_progress_turn
                            and progress_updates_emitted < max_progress_updates
                            and tool_call_count > 0
                        ):
                            on_progress(
                                f"Still working... turn {agent_turn_count}, "
                                f"{tool_call_count} tool calls (last: {last_tool_name})"
                            )
                            progress_updates_emitted += 1
                            next_progress_turn *= 2  # 3 → 6 → 12

                # Extract text from message content (for fallback if no ResultMessage)
                for block in getattr(message, "content", []):
                    if hasattr(block, "text"):
                        text_parts.append(block.text)

        # Calculate duration
        duration_ms = int((time.time() - start_time) * 1000)

        # Build result from ResultMessage if available
        if result_message:
            usage = result_message.usage or {}
            result = ReviewResult(
                text=result_message.result or "\n".join(text_parts),
                input_tokens=usage.get("input_tokens", 0),
                output_tokens=usage.get("output_tokens", 0),
                total_tokens=usage.get("input_tokens", 0) + usage.get("output_tokens", 0),
                total_cost_usd=result_message.total_cost_usd or 0.0,
                duration_ms=result_message.duration_ms or duration_ms,
                structured_output=None,  # TODO: Parse if output_schema configured
            )
        else:
            # Fallback if no ResultMessage received
            result = ReviewResult(
                text="\n".join(text_parts),
                duration_ms=duration_ms,
            )

        # Stream the final result text if callback provided
        if on_text:
            on_text(result.text)

        # Save logging data if enabled
        if self._logging_service and session_id:
            self._logging_service.save_result(session_id, result)
            self._logging_service.save_transcript(session_id, all_messages)

            # Save reference to SDK's transcript JSONL
            if result_message and hasattr(result_message, "session_id"):
                sdk_session_id = result_message.session_id
                if sdk_session_id:
                    self._logging_service.save_sdk_transcript_reference(
                        session_id=session_id,
                        sdk_session_id=sdk_session_id,
                        cwd=str(self._get_cwd()),
                    )

        return result
