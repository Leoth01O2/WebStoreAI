import os
from pathlib import Path
from pydantic_settings import BaseSettings

BASE_DIR = Path(__file__).resolve().parent.parent.parent

class Settings(BaseSettings):
    APP_NAME: str = "StoreFlow AI"
    APP_ENV: str = "development"
    DEBUG: bool = True
    PORT: int = 8000
    HOST: str = "0.0.0.0"

    # Security
    SECRET_KEY: str = "storeflow_dev_secret_key_super_secure_change_in_production_2026"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480
    TRUST_PROXY_HEADERS: bool = False

    # Database
    DATABASE_PATH: str = str(BASE_DIR / "webstore.db")

    # AI & Gemini
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-3.6-flash"

    # Ollama & Pluggable AI Providers (Phase R5)
    AI_PROVIDER: str = "auto"  # "auto", "ollama", "gemini", "grounded"
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "qwen2.5:1.5b"
    OLLAMA_TIMEOUT_SECONDS: float = 60.0

    # ChromaDB
    CHROMA_PERSIST_DIRECTORY: str = str(BASE_DIR / "chroma_data")

    model_config = {
        "env_file": str(BASE_DIR / ".env"),
        "env_file_encoding": "utf-8",
        "extra": "ignore"
    }

INSECURE_DEV_SECRET_KEYS = {
    "storeflow_dev_secret_key_super_secure_change_in_production_2026",
    "secret",
    "changeme",
    "default",
    "secret_key",
    "admin",
    "123456",
}

def validate_boot_safety(settings_obj: Settings) -> None:
    """
    Kiểm tra an toàn cấu hình khi khởi động (Boot Safety Check).
    Trong môi trường production/staging:
    - Bắt buộc từ chối khởi động (raise RuntimeError) nếu SECRET_KEY rỗng,
      dùng khóa dev mặc định, hoặc có độ dài không an toàn (< 32 ký tự).
    """
    env_normalized = (settings_obj.APP_ENV or "").strip().lower()
    if env_normalized in ("production", "prod", "staging"):
        secret = (settings_obj.SECRET_KEY or "").strip()
        if not secret:
            raise RuntimeError(
                "CRITICAL SECURITY CONFIGURATION ERROR: APP_ENV is set to production/staging, "
                "but SECRET_KEY is empty. Application boot aborted. "
                "Please configure a strong, unique SECRET_KEY in your environment."
            )
        if secret in INSECURE_DEV_SECRET_KEYS or secret.startswith("storeflow_dev_secret_key"):
            raise RuntimeError(
                "CRITICAL SECURITY CONFIGURATION ERROR: Production environment detected, "
                "but default development SECRET_KEY is still in use. Application boot aborted. "
                "Never deploy to production with the default development secret key."
            )
        if len(secret) < 32:
            raise RuntimeError(
                "CRITICAL SECURITY CONFIGURATION ERROR: Production SECRET_KEY is too short (< 32 characters). "
                "Application boot aborted. Please provide a cryptographic key with sufficient entropy."
            )

settings = Settings()
validate_boot_safety(settings)
