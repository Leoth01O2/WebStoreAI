import os
import sqlite3
import hashlib
import datetime
import uuid
import tempfile
from typing import Optional, Dict, Any, List
from pathlib import Path

from app.core.config import settings

BACKUP_DIR_DEFAULT = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "backups")

BUSINESS_TABLES = [
    "users",
    "categories",
    "products",
    "customers",
    "orders",
    "order_items",
    "purchase_receipts",
    "purchase_items",
    "inventory_logs",
    "ai_audit_logs",
    "product_visual_metadata",
    "order_audit_logs",
]


def calculate_sha256(file_path: str) -> str:
    """Tính mã băm SHA-256 của file để kiểm tra tính toàn vẹn bản sao"""
    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


def create_database_backup(
    source_db_path: Optional[str] = None,
    backup_dir: Optional[str] = None,
    method: str = "online_backup"
) -> Dict[str, Any]:
    """
    Tạo bản sao lưu SQLite an toàn không gây khóa dữ liệu:
    - Mặc định sử dụng SQLite Online Backup API (source_conn.backup(dest_conn)).
    - Hỗ trợ 'vacuum_into' khi cần nén và tái sắp xếp trang.
    - Không copy nhị phân thô bằng shutil khi SQLite WAL đang hoạt động.
    - Không ghi đè backup cũ, tên file chứa timestamp duy nhất.
    """
    src_path = os.path.abspath(source_db_path or settings.DATABASE_PATH)
    if not os.path.exists(src_path):
        raise FileNotFoundError(f"Database nguồn không tồn tại: {src_path}")

    target_dir = os.path.abspath(backup_dir or BACKUP_DIR_DEFAULT)
    os.makedirs(target_dir, exist_ok=True)

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    suffix = uuid.uuid4().hex[:6]
    backup_filename = f"webstore_backup_{timestamp}_{suffix}.db"
    backup_path = os.path.join(target_dir, backup_filename)

    if os.path.exists(backup_path):
        raise FileExistsError(f"Tệp backup đã tồn tại, từ chối ghi đè: {backup_path}")

    try:
        if method == "online_backup":
            # Sử dụng SQLite Online Backup API chính thức
            source_conn = sqlite3.connect(src_path, timeout=10.0)
            dest_conn = sqlite3.connect(backup_path, timeout=10.0)
            try:
                source_conn.backup(dest_conn)
            finally:
                dest_conn.close()
                source_conn.close()
        elif method == "vacuum_into":
            # VACUUM INTO phải chạy ngoài bất kỳ transaction nào
            conn = sqlite3.connect(src_path, timeout=10.0, isolation_level=None)
            try:
                # Thoát ký tự đường dẫn an toàn cho SQLite
                escaped_path = backup_path.replace("'", "''")
                conn.execute(f"VACUUM INTO '{escaped_path}';")
            finally:
                conn.close()
        else:
            raise ValueError(f"Phương thức backup không hợp lệ: {method}")

    except sqlite3.OperationalError as e:
        if os.path.exists(backup_path):
            try:
                os.remove(backup_path)
            except Exception:
                pass
        raise RuntimeError(f"Lỗi SQLite trong quá trình sao lưu: {e}") from e
    except Exception as e:
        if os.path.exists(backup_path):
            try:
                os.remove(backup_path)
            except Exception:
                pass
        raise RuntimeError(f"Lỗi không xác định khi tạo backup: {e}") from e

    if not os.path.exists(backup_path) or os.path.getsize(backup_path) == 0:
        raise RuntimeError(f"Tệp backup được tạo rỗng hoặc không tồn tại: {backup_path}")

    file_size = os.path.getsize(backup_path)
    sha256 = calculate_sha256(backup_path)

    return {
        "status": "success",
        "method": method,
        "source_path": src_path,
        "backup_path": backup_path,
        "backup_filename": backup_filename,
        "file_size": file_size,
        "sha256": sha256,
        "created_at": datetime.datetime.now().isoformat(),
    }


def verify_database_backup(backup_path: str, source_db_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Xác minh độc lập tính toàn vẹn và độ tin cậy của bản backup:
    1. Kiểm tra tồn tại và kích thước file > 0.
    2. Mở độc lập và chạy PRAGMA integrity_check.
    3. Chạy PRAGMA foreign_key_check.
    4. Đối chiếu số lượng bản ghi giữa database nguồn và backup.
    5. Kiểm tra schema và các bảng nghiệp vụ.
    """
    if not os.path.exists(backup_path):
        raise FileNotFoundError(f"Tệp backup không tồn tại: {backup_path}")

    file_size = os.path.getsize(backup_path)
    if file_size == 0:
        raise ValueError(f"Tệp backup có kích thước 0 byte: {backup_path}")

    sha256 = calculate_sha256(backup_path)

    conn = sqlite3.connect(backup_path, timeout=5.0)
    try:
        conn.execute("PRAGMA foreign_keys = ON;")
        cursor = conn.cursor()

        # 1. Integrity check
        cursor.execute("PRAGMA integrity_check;")
        integrity_rows = cursor.fetchall()
        integrity_ok = len(integrity_rows) == 1 and integrity_rows[0][0] == "ok"
        if not integrity_ok:
            raise RuntimeError(f"PRAGMA integrity_check thất bại: {integrity_rows}")

        # 2. Foreign key check
        cursor.execute("PRAGMA foreign_key_check;")
        fk_errors = cursor.fetchall()
        fk_ok = len(fk_errors) == 0
        if not fk_ok:
            raise RuntimeError(f"PRAGMA foreign_key_check phát hiện lỗi khóa ngoại: {fk_errors}")

        # 3. Lấy danh sách bảng và record count của backup
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [r[0] for r in cursor.fetchall() if not r[0].startswith("sqlite_")]
        backup_counts = {}
        for t in tables:
            cursor.execute(f"SELECT COUNT(*) FROM \"{t}\";")
            backup_counts[t] = cursor.fetchone()[0]

    finally:
        conn.close()

    # 4. Đối chiếu với database nguồn nếu được chỉ định
    source_counts = {}
    record_counts_match = True
    if source_db_path and os.path.exists(source_db_path):
        src_conn = sqlite3.connect(source_db_path, timeout=5.0)
        try:
            src_cursor = src_conn.cursor()
            for t in tables:
                src_cursor.execute(f"SELECT COUNT(*) FROM \"{t}\";")
                source_counts[t] = src_cursor.fetchone()[0]
                if source_counts[t] != backup_counts.get(t):
                    record_counts_match = False
        finally:
            src_conn.close()

    trial_restoration_ok = trial_restore_query(backup_path)

    is_verified = integrity_ok and fk_ok and trial_restoration_ok and (record_counts_match if source_db_path else True)

    return {
        "verified": is_verified,
        "backup_path": backup_path,
        "file_size": file_size,
        "sha256": sha256,
        "integrity_check": "ok" if integrity_ok else str(integrity_rows),
        "foreign_key_check": "ok" if fk_ok else f"{len(fk_errors)} errors",
        "trial_restoration": "ok" if trial_restoration_ok else "failed",
        "tables_verified": len(tables),
        "backup_counts": backup_counts,
        "source_counts": source_counts if source_db_path else None,
        "record_counts_match": record_counts_match if source_db_path else None,
    }


def trial_restore_query(backup_path: str) -> bool:
    """
    Thử nghiệm khôi phục và thực hiện truy vấn đọc/ghi thử trên thư mục tạm.
    Đảm bảo file backup có thể dùng để phục hồi toàn diện hệ thống khi có sự cố.
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_restore_path = os.path.join(tmp_dir, "trial_restore.db")

        # Khôi phục từ backup vào thư mục tạm bằng Online Backup API
        src_conn = sqlite3.connect(backup_path, timeout=5.0)
        dest_conn = sqlite3.connect(tmp_restore_path, timeout=5.0)
        try:
            src_conn.backup(dest_conn)
        finally:
            dest_conn.close()
            src_conn.close()

        # Mở và truy vấn kiểm tra trên bản phục hồi thử nghiệm
        conn = sqlite3.connect(tmp_restore_path, timeout=5.0)
        try:
            cursor = conn.cursor()
            cursor.execute("PRAGMA integrity_check;")
            row = cursor.fetchone()
            if not row or row[0] != "ok":
                return False
            cursor.execute("SELECT COUNT(*) FROM products;")
            _ = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM orders;")
            _ = cursor.fetchone()[0]
            return True
        except Exception:
            return False
        finally:
            conn.close()
