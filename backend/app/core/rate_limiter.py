import time
import re
from typing import Dict, List, Optional, Tuple
from fastapi import Request, HTTPException, status, Depends

from app.core.config import settings
from app.core.rbac import get_current_user_optional


class AIRateLimiter:
    """
    In-memory Sliding Window Rate Limiter & Anti-Spam Guard for AI Endpoints.
    Provides role-differentiated request limits, cooldown between consecutive requests,
    message length bounds, and output sanitization to prevent accidental secret leakage.
    """

    # Role-based quotas and limits
    ROLE_CONFIG = {
        "guest": {
            "max_requests_per_minute": 10,
            "cooldown_seconds": 1.5,
            "max_input_length": 500,
        },
        "customer": {
            "max_requests_per_minute": 25,
            "cooldown_seconds": 0.5,
            "max_input_length": 1000,
        },
        "staff": {
            "max_requests_per_minute": 40,
            "cooldown_seconds": 0.2,
            "max_input_length": 1500,
        },
        "admin": {
            "max_requests_per_minute": 60,
            "cooldown_seconds": 0.1,
            "max_input_length": 2000,
        },
        "superadmin": {
            "max_requests_per_minute": 120,
            "cooldown_seconds": 0.0,
            "max_input_length": 4000,
        },
    }

    def __init__(self):
        # Stores list of timestamps per key: { key: [timestamp1, timestamp2, ...] }
        self._requests: Dict[str, List[float]] = {}
        # Stores last request timestamp per key: { key: float }
        self._last_request_time: Dict[str, float] = {}

    def _get_client_key(self, request: Request, user: Optional[dict] = None) -> str:
        """Derives a rate limiting key from authenticated user ID or client IP."""
        if user and user.get("id"):
            return f"user:{user['id']}"
        # Extract client IP (handling X-Forwarded-For if behind reverse proxy)
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            ip = forwarded.split(",")[0].strip()
        elif request.client and request.client.host:
            ip = request.client.host
        else:
            ip = "127.0.0.1"
        return f"ip:{ip}"

    def check_rate_limit(
        self,
        request: Request,
        user: Optional[dict] = None
    ) -> Tuple[bool, Optional[str], Optional[int]]:
        """
        Validates rate limit and cooldown for the current caller.
        Returns: (is_allowed, error_message, retry_after_seconds)
        """
        role = (user.get("role") if user else "guest") or "guest"
        config = self.ROLE_CONFIG.get(role, self.ROLE_CONFIG["guest"])
        key = self._get_client_key(request, user)
        now = time.time()

        # 1. Check cooldown between consecutive requests
        last_time = self._last_request_time.get(key, 0.0)
        cooldown = config["cooldown_seconds"]
        if cooldown > 0 and (now - last_time) < cooldown:
            wait_time = int(cooldown - (now - last_time)) + 1
            return (
                False,
                f"Bạn đang gửi yêu cầu quá nhanh. Vui lòng chờ {wait_time} giây trước khi gửi tiếp.",
                wait_time
            )

        # 2. Check sliding window limit (60 seconds)
        timestamps = self._requests.get(key, [])
        # Retain only timestamps within the last 60 seconds
        valid_timestamps = [t for t in timestamps if now - t < 60.0]

        max_allowed = config["max_requests_per_minute"]
        if len(valid_timestamps) >= max_allowed:
            # Time until oldest request in window expires
            oldest = valid_timestamps[0]
            retry_after = max(1, int(60.0 - (now - oldest)))
            return (
                False,
                f"Bạn đã vượt quá giới hạn {max_allowed} câu hỏi AI / phút cho vai trò {role.upper()}. "
                f"Vui lòng thử lại sau {retry_after} giây.",
                retry_after
            )

        # Record this request
        valid_timestamps.append(now)
        self._requests[key] = valid_timestamps
        self._last_request_time[key] = now
        return (True, None, None)

    def validate_input_length(
        self,
        text: str,
        user: Optional[dict] = None
    ) -> Tuple[bool, Optional[str]]:
        """
        Validates that user input text does not exceed the allowed character limit for their role.
        """
        role = (user.get("role") if user else "guest") or "guest"
        config = self.ROLE_CONFIG.get(role, self.ROLE_CONFIG["guest"])
        max_len = config["max_input_length"]

        if len(text) > max_len:
            return (
                False,
                f"Câu hỏi của bạn quá dài ({len(text)} ký tự). "
                f"Giới hạn cho vai trò {role.upper()} là tối đa {max_len} ký tự."
            )
        return (True, None)

    def sanitize_output(self, text: str) -> str:
        """
        Redacts sensitive tokens, API keys, password hashes, and internal secrets from AI output.
        """
        if not text:
            return text

        # Redact Gemini API Key if matched
        if settings.GEMINI_API_KEY and len(settings.GEMINI_API_KEY) > 8:
            text = text.replace(settings.GEMINI_API_KEY, "[REDACTED_API_KEY]")

        # Redact JWT Secret Key
        if settings.SECRET_KEY and len(settings.SECRET_KEY) > 8:
            text = text.replace(settings.SECRET_KEY, "[REDACTED_SECRET]")

        # Redact bcrypt password hashes ($2b$... or $2a$...)
        text = re.sub(r'\$2[abxy]\$\d+\$[./A-Za-z0-9]{53}', '[REDACTED_PASSWORD_HASH]', text)

        # Redact common API key patterns (e.g. AIzaSy...)
        text = re.sub(r'AIzaSy[A-Za-z0-9_-]{20,60}', '[REDACTED_API_KEY]', text)

        return text

    def reset(self) -> None:
        """Clears memory buffers (used in test fixtures)."""
        self._requests.clear()
        self._last_request_time.clear()


# Global Singleton Rate Limiter
ai_rate_limiter = AIRateLimiter()


def enforce_ai_rate_limit(
    request: Request,
    current_user: Optional[dict] = Depends(get_current_user_optional)
) -> Optional[dict]:
    """
    FastAPI Dependency that enforces rate limiting and cooldown on AI routes.
    Raises HTTP 429 Too Many Requests if rate limit is exceeded.
    """
    allowed, error_msg, retry_after = ai_rate_limiter.check_rate_limit(request, current_user)
    if not allowed:
        headers = {}
        if retry_after:
            headers["Retry-After"] = str(retry_after)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=error_msg or "Bạn đã gửi quá nhiều yêu cầu AI. Vui lòng thử lại sau.",
            headers=headers
        )
    return current_user


# ===========================================================================
# LOGIN ENDPOINT BRUTE-FORCE PROTECTION (PHASE R1A)
# ===========================================================================

class LoginRateLimiter:
    """
    In-memory Rate Limiter chuyên trách bảo vệ endpoint Đăng nhập (/api/v1/auth/login).
    - Ngưỡng: Tối đa 5 lần thử thất bại trong cửa sổ 60 giây.
    - Khóa theo cặp (client_ip, normalized_username) để chống khóa nhầm các tài khoản khác khi dùng chung IP (văn phòng/quán cafe).
    - Không tin cậy mù quáng header X-Forwarded-For trừ khi được cấu hình TRUST_PROXY_HEADERS.
    - Tự động xóa lịch sử thất bại ngay khi tài khoản đăng nhập thành công.
    - Độc lập hoàn toàn với AIRateLimiter, không làm ảnh hưởng tính năng AI.
    """
    def __init__(self, max_failed_attempts: int = 5, window_seconds: float = 60.0):
        self.max_failed_attempts = max_failed_attempts
        self.window_seconds = window_seconds
        # Key: "ip:username" -> List[float] (danh sách timestamps các lần thử thất bại)
        self._failed_attempts: Dict[str, List[float]] = {}

    def _get_client_ip(self, request: Request) -> str:
        """Trích xuất địa chỉ IP tin cậy của client kết nối."""
        if getattr(settings, "TRUST_PROXY_HEADERS", False):
            forwarded = request.headers.get("x-forwarded-for")
            if forwarded:
                return forwarded.split(",")[0].strip()
        if request.client and request.client.host:
            return request.client.host
        return "127.0.0.1"

    def _make_key(self, request: Request, username: str) -> str:
        ip = self._get_client_ip(request)
        clean_user = (username or "").strip().lower()
        return f"{ip}:{clean_user}"

    def is_rate_limited(self, request: Request, username: str) -> Tuple[bool, int]:
        """
        Kiểm tra xem cặp (ip, username) hiện tại có đang bị chặn do vượt ngưỡng thử sai không.
        Trả về: (is_limited, retry_after_seconds)
        """
        key = self._make_key(request, username)
        now = time.time()
        attempts = self._failed_attempts.get(key, [])
        valid_attempts = [t for t in attempts if now - t < self.window_seconds]
        self._failed_attempts[key] = valid_attempts

        if len(valid_attempts) >= self.max_failed_attempts:
            oldest = valid_attempts[0]
            retry_after = max(1, int(self.window_seconds - (now - oldest)))
            return True, retry_after
        return False, 0

    def record_failure(self, request: Request, username: str) -> None:
        """Ghi nhận 1 lần đăng nhập thất bại vào cửa sổ trượt."""
        key = self._make_key(request, username)
        now = time.time()
        attempts = self._failed_attempts.get(key, [])
        valid_attempts = [t for t in attempts if now - t < self.window_seconds]
        valid_attempts.append(now)
        self._failed_attempts[key] = valid_attempts

    def record_success(self, request: Request, username: str) -> None:
        """Đăng nhập thành công: Xóa ngay bộ đếm thất bại để người dùng không bị tích lũy lỗi cũ."""
        key = self._make_key(request, username)
        self._failed_attempts.pop(key, None)

    def reset(self) -> None:
        """Xóa sạch bộ đếm phục vụ kiểm thử biệt lập."""
        self._failed_attempts.clear()


login_rate_limiter = LoginRateLimiter(max_failed_attempts=5, window_seconds=60.0)


# ===========================================================================
# PUBLIC CUSTOMER REGISTRATION RATE LIMITER (PHASE R1B)
# ===========================================================================

class RegisterRateLimiter:
    """
    In-memory Rate Limiter bảo vệ endpoint Đăng ký tài khoản Khách hàng (/api/v1/auth/register).
    - Ngưỡng: Tối đa 3 lượt đăng ký / IP trong cửa sổ 10 phút (600 giây).
    - Không tin cậy header X-Forwarded-For nếu chưa cấu hình TRUST_PROXY_HEADERS.
    - Độc lập hoàn toàn với login_rate_limiter và ai_rate_limiter.
    """
    def __init__(self, max_requests: int = 3, window_seconds: float = 600.0):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        # Key: "register:ip" -> List[float] (timestamps các lần đăng ký)
        self._requests: Dict[str, List[float]] = {}

    def _get_client_ip(self, request: Request) -> str:
        if getattr(settings, "TRUST_PROXY_HEADERS", False):
            forwarded = request.headers.get("x-forwarded-for")
            if forwarded:
                return forwarded.split(",")[0].strip()
        if request.client and request.client.host:
            return request.client.host
        return "127.0.0.1"

    def is_rate_limited(self, request: Request) -> Tuple[bool, int]:
        """
        Kiểm tra IP hiện tại có bị vượt quá 3 lượt đăng ký / 10 phút không.
        Trả về: (is_limited, retry_after_seconds)
        """
        ip = self._get_client_ip(request)
        key = f"register:{ip}"
        now = time.time()
        timestamps = self._requests.get(key, [])
        valid = [t for t in timestamps if now - t < self.window_seconds]
        self._requests[key] = valid

        if len(valid) >= self.max_requests:
            oldest = valid[0]
            retry_after = max(1, int(self.window_seconds - (now - oldest)))
            return True, retry_after
        return False, 0

    def record_attempt(self, request: Request) -> None:
        """Ghi nhận 1 lượt đăng ký thành công hoặc hợp lệ từ IP"""
        ip = self._get_client_ip(request)
        key = f"register:{ip}"
        now = time.time()
        timestamps = self._requests.get(key, [])
        valid = [t for t in timestamps if now - t < self.window_seconds]
        valid.append(now)
        self._requests[key] = valid

    def reset(self) -> None:
        """Xóa sạch bộ đếm phục vụ kiểm thử"""
        self._requests.clear()


register_rate_limiter = RegisterRateLimiter(max_requests=3, window_seconds=600.0)
