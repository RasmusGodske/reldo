"""Core review service that orchestrates Claude Agent SDK calls."""

import time
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

    def _build_agent_options(self) -> ClaudeAgentOptions:
        """Build ClaudeAgentOptions from config.

        Maps ReviewConfig properties to SDK options:
        - prompt → system_prompt
        - allowed_tools → allowed_tools
        - mcp_servers → mcp_servers
        - setting_sources → setting_sources (defaults to ['project'] for .claude/agents/)
        - agents → agents (with prompt files loaded, merged with discovered agents)
        - cwd → cwd
        - model → model
        - hooks → hooks

        Note: The output_schema is NOT passed here - it would need
        to be handled differently in the SDK (currently not directly supported).

        Returns:
            ClaudeAgentOptions instance configured from self._config.
        """
        system_prompt = self._load_orchestrator_prompt()
        agents = self._load_agents()

        # Use configured setting_sources or default to ['project'] for .claude/agents/ discovery
        setting_sources = self._config.setting_sources
        if setting_sources is None:
            setting_sources = DEFAULT_SETTING_SOURCES

        # Build base options
        options_kwargs: dict[str, Any] = {
            "system_prompt": system_prompt,
            "allowed_tools": self._config.allowed_tools,
            "mcp_servers": self._config.mcp_servers,
            "setting_sources": setting_sources,
            "cwd": str(self._get_cwd()),
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

    async def review(self, prompt: str) -> ReviewResult:
        """Run a code review.

        Args:
            prompt: The review prompt (what to review).

        Returns:
            ReviewResult with the review outcome.
        """
        start_time = time.time()
        options = self._build_agent_options()

        # Start logging session if enabled
        session_id: str | None = None
        if self._logging_service:
            session_id = self._logging_service.start_session(
                prompt=prompt,
                config=self._get_config_snapshot()
            )

        # Collect all text output and messages for transcript
        text_parts: list[str] = []
        all_messages: list[Any] = []
        result_message: ResultMessage | None = None

        # Stream through the query results
        async for message in query(prompt=prompt, options=options):
            all_messages.append(message)

            # Handle different message types
            # Use duck typing: ResultMessage has 'session_id' and 'usage' but no 'content'
            if hasattr(message, "session_id") and hasattr(message, "usage"):
                result_message = message  # type: ignore[assignment]
            elif hasattr(message, "content"):
                # Extract text from message content
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
