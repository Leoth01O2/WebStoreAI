from abc import ABC, abstractmethod
from typing import Dict, Any, Optional


class BaseAIProvider(ABC):
    """
    Abstract Base Class for AI Providers (Phase R5).
    Defines the contract for language model providers in StoreFlow AI:
    Google Gemini, Local Ollama, and Grounded Deterministic Fallback.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique provider identifier: 'gemini', 'ollama', or 'grounded'."""
        pass

    @abstractmethod
    def generate_text(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        temperature: float = 0.3,
        max_tokens: int = 2048,
        format: Optional[str] = None
    ) -> str:
        """
        Generates text output for a given prompt and system instruction.
        Must sanitize secrets from the output before returning.
        """
        pass

    @abstractmethod
    def health_check(self) -> Dict[str, Any]:
        """
        Checks provider availability and health status.
        Returns:
            {
                "provider": str,
                "available": bool,
                "status": str,
                "model": str,
                "details": Dict[str, Any]
            }
        """
        pass
