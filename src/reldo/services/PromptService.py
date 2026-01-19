"""Service for loading and resolving prompts."""

from pathlib import Path


class PromptService:
    """Loads prompts from files or passes through inline strings.

    Handles:
    - Detecting if input is a file path or inline string
    - Resolving relative paths against cwd
    - Loading prompt content from files
    """

    def load(self, prompt_or_path: str, cwd: Path) -> str:
        """Load a prompt from a file path or return inline string.

        If the input looks like a file path (ends with .md/.txt or exists as a file),
        loads the file content. Otherwise, returns the input as-is (inline prompt).

        Args:
            prompt_or_path: Either a file path (relative to cwd) or inline prompt string.
            cwd: Working directory for resolving relative paths.

        Returns:
            The prompt content.

        Raises:
            FileNotFoundError: If a file path is provided but doesn't exist.
        """
        if self._is_file_path(prompt_or_path, cwd):
            return self._load_file(prompt_or_path, cwd)
        return prompt_or_path

    def _is_file_path(self, value: str, cwd: Path) -> bool:
        """Determine if value is a file path or inline string.

        Considers it a file path if:
        - Ends with .md or .txt extension
        - OR the resolved path exists as a file

        Args:
            value: The prompt string to check.
            cwd: Working directory for path resolution.

        Returns:
            True if value appears to be a file path.
        """
        # Check for common prompt file extensions
        if value.endswith((".md", ".txt")):
            return True

        # Check if it resolves to an existing file
        resolved = self._resolve_path(value, cwd)
        return resolved.is_file()

    def _resolve_path(self, path: str, cwd: Path) -> Path:
        """Resolve a path relative to cwd.

        If path is absolute, returns it as-is.
        If relative, resolves against cwd.

        Args:
            path: The path string to resolve.
            cwd: Working directory for relative paths.

        Returns:
            Resolved Path object.
        """
        path_obj = Path(path)
        if path_obj.is_absolute():
            return path_obj
        return cwd / path_obj

    def _load_file(self, path: str, cwd: Path) -> str:
        """Load content from a file.

        Args:
            path: The file path to load.
            cwd: Working directory for relative paths.

        Returns:
            File content as string.

        Raises:
            FileNotFoundError: If the file doesn't exist.
        """
        resolved = self._resolve_path(path, cwd)
        if not resolved.exists():
            raise FileNotFoundError(f"Prompt file not found: {resolved}")
        return resolved.read_text(encoding="utf-8")
