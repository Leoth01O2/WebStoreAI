import time
import logging
from typing import Dict, Any, Optional, List
import httpx

from app.core.config import settings
from app.core.rate_limiter import ai_rate_limiter
from app.core.prompt_loader import prompt_loader
from app.services.ai_providers.base import BaseAIProvider

logger = logging.getLogger(__name__)


def detect_repetition(text: str) -> bool:
    """
    Detects severe repetitive loops in LLM generated output.
    Returns True if degenerate repetition is detected.
    """
    if not text or len(text) < 80:
        return False

    lines = [line.strip() for line in text.split("\n") if len(line.strip()) >= 20]
    line_counts = {}
    for line in lines:
        line_counts[line] = line_counts.get(line, 0) + 1
        if line_counts[line] >= 4:
            return True

    sentences = [s.strip() for s in text.replace("!", ".").replace("?", ".").split(".") if len(s.strip()) >= 25]
    sent_counts = {}
    for s in sentences:
        sent_counts[s] = sent_counts.get(s, 0) + 1
        if sent_counts[s] >= 4:
            return True

    words = text.split()
    if len(words) >= 40:
        ngram_size = 6
        ngrams = [" ".join(words[i:i+ngram_size]) for i in range(len(words) - ngram_size + 1)]
        ng_counts = {}
        for ng in ngrams:
            ng_counts[ng] = ng_counts.get(ng, 0) + 1
            if ng_counts[ng] >= 5:
                return True

    return False


class OllamaProvider(BaseAIProvider):

    """
    Local Ollama AI Provider (Phase R5).
    Runs local open-weights LLMs (such as Qwen 2.5 1.5B/3B) offline on localhost.
    Provides tokens/second telemetry, model health check, and graceful error handling.
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        timeout: Optional[float] = None
    ):
        self.base_url = (base_url or settings.OLLAMA_BASE_URL).rstrip("/")
        self.model = model or settings.OLLAMA_MODEL
        self.timeout = timeout if timeout is not None else settings.OLLAMA_TIMEOUT_SECONDS
        self._last_metrics: Dict[str, Any] = {}

    @property
    def name(self) -> str:
        return "ollama"

    @property
    def last_metrics(self) -> Dict[str, Any]:
        """Returns telemetry metrics from the most recent generation."""
        return self._last_metrics

    def _get_client(self) -> httpx.Client:
        return httpx.Client(base_url=self.base_url, timeout=self.timeout)

    def list_installed_models(self) -> List[Dict[str, Any]]:
        """Queries Ollama for all installed/pulled models."""
        try:
            with self._get_client() as client:
                res = client.get("/api/tags")
                if res.status_code == 200:
                    data = res.json()
                    return data.get("models", [])
        except Exception as e:
            logger.warning(f"Failed to query Ollama models from {self.base_url}: {e}")
        return []

    def is_model_installed(self, model_name: Optional[str] = None) -> bool:
        """Checks if the target model is downloaded and ready in Ollama."""
        target = model_name or self.model
        target_base = target.split(":")[0].lower()
        target_tag = target.split(":")[1] if ":" in target else "latest"

        models = self.list_installed_models()
        for m in models:
            m_name = m.get("name", "").lower()
            if m_name == target.lower():
                return True
            # Also match prefix:tag
            if m_name == f"{target_base}:{target_tag}":
                return True
        return False

    def is_service_running(self) -> bool:
        """Checks if Ollama service is reachable on localhost."""
        try:
            with self._get_client() as client:
                res = client.get("/api/tags")
                return res.status_code == 200
        except Exception:
            return False

    def generate_text(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        temperature: float = 0.3,
        max_tokens: int = 2048,
        format: Optional[str] = None
    ) -> str:
        """
        Invokes Ollama /api/chat with the provided prompt and system instruction.
        Records performance metrics (latency, eval_count, tokens/sec).
        """
        sys_inst = system_instruction or prompt_loader.get_system_prompt()
        start_time = time.time()

        options = {
            "temperature": temperature,
            "num_predict": max_tokens,
            "repeat_penalty": 1.22,
            "stop": [
                "<|im_end|>",
                "<|endoftext|>",
                "[HẾT BÁO CÁO]",
                "--- HẾT BÁO CÁO ---",
                "[HẾT]",
                "--- HẾT ---",
                "Phong cách giao tiếp:",
                "**Phong cách giao tiếp:**",
                "Quyết định:\n",
                "**Quyết định:**",
                "[QUY TẮC",
                "[HỆ THỐNG",
            ]
        }
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": sys_inst},
                {"role": "user", "content": prompt}
            ],
            "stream": False,
            "options": options
        }
        if format:
            payload["format"] = format


        try:
            with self._get_client() as client:
                res = client.post("/api/chat", json=payload)
                if res.status_code != 200:
                    raise RuntimeError(f"Ollama API returned HTTP {res.status_code}: {res.text[:200]}")
                data = res.json()
        except httpx.ConnectError:
            raise RuntimeError(f"Cannot connect to Ollama at {self.base_url}. Service may not be running.")
        except httpx.TimeoutException:
            raise RuntimeError(f"Ollama generation timed out after {self.timeout}s.")
        except Exception as e:
            if isinstance(e, RuntimeError):
                raise
            raise RuntimeError(f"Ollama generation failed: {str(e)}")

        raw_text = data.get("message", {}).get("content", "")

        # Extract telemetry
        eval_count = data.get("eval_count", 0)
        eval_duration_ns = data.get("eval_duration", 0)
        total_duration_ns = data.get("total_duration", 0)
        eval_duration_sec = eval_duration_ns / 1e9 if eval_duration_ns > 0 else (time.time() - start_time)
        tokens_per_second = round(eval_count / eval_duration_sec, 2) if eval_duration_sec > 0 and eval_count > 0 else 0.0

        self._last_metrics = {
            "model": self.model,
            "eval_count": eval_count,
            "prompt_eval_count": data.get("prompt_eval_count", 0),
            "eval_duration_sec": round(eval_duration_sec, 3),
            "total_duration_sec": round(total_duration_ns / 1e9, 3) if total_duration_ns else round(time.time() - start_time, 3),
            "tokens_per_second": tokens_per_second,
            "latency_ms": int((time.time() - start_time) * 1000)
        }

        return ai_rate_limiter.sanitize_output(raw_text)

    def health_check(self) -> Dict[str, Any]:
        """Performs health and availability inspection."""
        running = self.is_service_running()
        if not running:
            return {
                "provider": self.name,
                "available": False,
                "status": "service_offline",
                "model": self.model,
                "details": {
                    "base_url": self.base_url,
                    "error": "Ollama service is not reachable on localhost."
                }
            }

        installed = self.is_model_installed()
        models = [m.get("name") for m in self.list_installed_models()]

        return {
            "provider": self.name,
            "available": installed,
            "status": "ready" if installed else "model_not_found",
            "model": self.model,
            "details": {
                "base_url": self.base_url,
                "target_model_installed": installed,
                "installed_models": models,
                "last_metrics": self._last_metrics
            }
        }
