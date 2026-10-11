import time
from typing import Dict, Any, Optional
from google import genai
from google.genai import types

from app.core.config import settings
from app.core.rate_limiter import ai_rate_limiter
from app.core.prompt_loader import prompt_loader
from app.services.ai_providers.base import BaseAIProvider


class GeminiProvider(BaseAIProvider):
    """
    Google Gemini AI Provider (Gemini 3.6 Flash via google-genai SDK).
    Used for online cloud generation when GEMINI_API_KEY is configured.
    """

    def __init__(self):
        self._client: Optional[genai.Client] = None

    @property
    def name(self) -> str:
        return "gemini"

    @property
    def client(self) -> genai.Client:
        if self._client is None:
            if not settings.GEMINI_API_KEY:
                raise RuntimeError("GEMINI_API_KEY is not configured.")
            self._client = genai.Client(api_key=settings.GEMINI_API_KEY)
        return self._client

    def is_configured(self) -> bool:
        key = (settings.GEMINI_API_KEY or "").strip()
        return bool(key and not key.startswith("SAFE_MOCK"))

    def generate_text(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        temperature: float = 0.3,
        max_tokens: int = 2048
    ) -> str:
        from app.services.ai_service import ai_service
        try:
            return ai_service._call_gemini(prompt, system_instruction)
        except TypeError:
            return ai_service._call_gemini(prompt)

    def health_check(self) -> Dict[str, Any]:
        configured = self.is_configured()
        if not configured:
            return {
                "provider": self.name,
                "available": False,
                "status": "not_configured",
                "model": settings.GEMINI_MODEL,
                "details": {
                    "reason": "GEMINI_API_KEY is missing or in mock mode"
                }
            }

        return {
            "provider": self.name,
            "available": True,
            "status": "configured",
            "model": settings.GEMINI_MODEL,
            "details": {
                "sdk": "google-genai",
                "model": settings.GEMINI_MODEL
            }
        }
