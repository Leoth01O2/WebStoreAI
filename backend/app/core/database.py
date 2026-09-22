import sqlite3
from contextlib import contextmanager
from typing import Generator
from app.core.config import settings

def get_db_connection() -> sqlite3.Connection:
    """
    Tạo kết nối SQLite với cấu hình tối ưu:
    - WAL Mode (Write-Ahead Logging) cho concurrency tốt
    - PRAGMA foreign_keys = ON bảo đảm toàn vẹn khóa ngoại
    - Row factory sqlite3.Row cho phép truy xuất dữ liệu theo tên cột
    - busy_timeout = 5000ms tránh locked database
    """
    conn = sqlite3.connect(
        settings.DATABASE_PATH,
        timeout=10.0,
        isolation_level=None  # Cho phép tự kiểm soát transaction rõ ràng (BEGIN IMMEDIATE)
    )
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA busy_timeout = 5000;")
    return conn

@contextmanager
def get_db() -> Generator[sqlite3.Connection, None, None]:
    """
    Context manager cho các truy vấn đọc (Read-only / Auto-commit queries).
    """
    conn = get_db_connection()
    try:
        yield conn
    finally:
        conn.close()

@contextmanager
def get_db_transaction() -> Generator[sqlite3.Connection, None, None]:
    """
    Context manager cho các giao dịch ghi Atomic (Atomic Write Transactions).
    Bắt đầu với `BEGIN IMMEDIATE` để khóa ghi ngay lập tức, ngăn race condition.
    Tự động COMMIT khi thành công và ROLLBACK toàn bộ khi có lỗi.
    """
    conn = get_db_connection()
    try:
        conn.execute("BEGIN IMMEDIATE;")
        yield conn
        conn.execute("COMMIT;")
    except Exception:
        conn.execute("ROLLBACK;")
        raise
    finally:
        conn.close()
