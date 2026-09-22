import os
from pathlib import Path
from typing import Dict, Any, Optional

from app.core.config import BASE_DIR

PROMPTS_DIR = BASE_DIR / "prompts"


class PromptLoader:
    """
    Manages loading, caching, and formatting prompt templates from the prompts/ directory.
    Ensures separation of concerns between code logic and prompt engineering.
    """

    def __init__(self, prompts_dir: Optional[Path] = None):
        self.prompts_dir = prompts_dir or PROMPTS_DIR
        self._cache: Dict[str, str] = {}

    def _normalize_name(self, template_name: str) -> str:
        if not template_name.endswith(".txt"):
            return f"{template_name}.txt"
        return template_name

    def get_template(self, template_name: str, force_reload: bool = False) -> str:
        """
        Reads the prompt template from disk or memory cache.
        """
        filename = self._normalize_name(template_name)
        if not force_reload and filename in self._cache:
            return self._cache[filename]

        file_path = self.prompts_dir / filename
        if not file_path.exists():
            raise FileNotFoundError(f"Prompt template '{filename}' not found in {self.prompts_dir}")

        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        self._cache[filename] = content
        return content

    def format_prompt(self, template_name: str, **kwargs: Any) -> str:
        """
        Loads and safely formats a template by replacing keyword arguments.
        Missing keys are handled cleanly.
        """
        template = self.get_template(template_name)
        try:
            return template.format(**kwargs)
        except KeyError as e:
            # Fallback or informative error
            raise ValueError(f"Missing required parameter {e} for prompt template '{template_name}'")

    def get_system_prompt(self) -> str:
        """Convenience method to retrieve the base system prompt."""
        return self.get_template("system_prompt")

    def clear_cache(self) -> None:
        """Clears the template memory cache."""
        self._cache.clear()


# Global instance
prompt_loader = PromptLoader()
