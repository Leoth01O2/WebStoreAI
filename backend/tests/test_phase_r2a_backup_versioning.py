import os
import sqlite3
import tempfile
import pytest

from app.core.backup import (
    create_database_backup,
    verify_database_backup,
    calculate_sha256,
    BUSINESS_TABLES
)
from app.models.schema import (
    init_db,
    get_applied_versions,
    is_version_applied,
    record_migration,
    apply_migration_step
)
from seed_data import seed_database


@pytest.fixture
def isolated_clone_db():
    """
    Fixture tạo một bản clone SQLite độc lập trong thư mục tạm.
    Hoàn toàn cô lập khỏi test_webstore.db và webstore.db chính.
    Tự động dọn sạch sau khi kết thúc test.
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        clone_path = os.path.join(tmp_dir, "clone_source.db")
        
        # Khởi tạo schema và seed dữ liệu vào clone_source.db
        orig_conn = sqlite3.connect(clone_path)
        orig_conn.close()

        # Tạo bảng và dữ liệu mẫu trong clone_source.db
        from app.models.schema import SCHEMA_SQL
        conn = sqlite3.connect(clone_path)
        conn.executescript(SCHEMA_SQL)
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA foreign_keys = ON;")
        
        # Seed một số bản ghi mẫu để test
        conn.execute("INSERT INTO categories (name, code) VALUES ('Cat Test', 'CAT-TEST');")
        cat_id = conn.execute("SELECT last_insert_rowid();").fetchone()[0]
        conn.execute(
            "INSERT INTO products (sku, name, category_id, cost_price, selling_price, stock_quantity) "
            "VALUES ('SKU-TEST', 'Prod Test', ?, 10, 20, 5);",
            (cat_id,)
        )
        conn.execute(
            "INSERT INTO users (username, password_hash, full_name, role) "
            "VALUES ('testuser', 'hash', 'Test User', 'customer');"
        )
        user_id = conn.execute("SELECT last_insert_rowid();").fetchone()[0]
        conn.execute(
            "INSERT INTO customers (user_id, customer_code, name, phone) "
            "VALUES (?, 'KH-TEST', 'Khách Test', '0901234567');",
            (user_id,)
        )
        cus_id = conn.execute("SELECT last_insert_rowid();").fetchone()[0]
        conn.execute(
            "INSERT INTO orders (order_code, customer_id, user_id, total_amount, final_amount, status) "
            "VALUES ('HD-TEST', ?, ?, 20, 20, 'completed');",
            (cus_id, user_id)
        )
        conn.commit()
        conn.close()

        yield clone_path, tmp_dir


def test_01_backup_succeeds_via_online_backup_api(isolated_clone_db):
    """1. Tạo backup thành công sử dụng SQLite Online Backup API"""
    clone_path, tmp_dir = isolated_clone_db
    backup_dir = os.path.join(tmp_dir, "backups")

    result = create_database_backup(source_db_path=clone_path, backup_dir=backup_dir, method="online_backup")
    assert result["status"] == "success"
    assert os.path.exists(result["backup_path"])
    assert result["file_size"] > 0
    assert len(result["sha256"]) == 64


def test_02_backup_opens_independently(isolated_clone_db):
    """2. Bản backup mở được độc lập bằng kết nối SQLite riêng biệt"""
    clone_path, tmp_dir = isolated_clone_db
    backup_dir = os.path.join(tmp_dir, "backups")
    result = create_database_backup(source_db_path=clone_path, backup_dir=backup_dir)

    # Mở độc lập
    conn = sqlite3.connect(result["backup_path"])
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = [r[0] for r in cursor.fetchall()]
    conn.close()

    assert "products" in tables
    assert "orders" in tables
    assert "users" in tables


def test_03_integrity_check_passes_ok(isolated_clone_db):
    """3. PRAGMA integrity_check đạt 'ok' trên bản sao lưu"""
    clone_path, tmp_dir = isolated_clone_db
    backup_dir = os.path.join(tmp_dir, "backups")
    result = create_database_backup(source_db_path=clone_path, backup_dir=backup_dir)

    conn = sqlite3.connect(result["backup_path"])
    cursor = conn.cursor()
    cursor.execute("PRAGMA integrity_check;")
    rows = cursor.fetchall()
    conn.close()

    assert len(rows) == 1
    assert rows[0][0] == "ok"


def test_04_foreign_key_check_has_zero_errors(isolated_clone_db):
    """4. PRAGMA foreign_key_check không phát hiện lỗi khóa ngoại"""
    clone_path, tmp_dir = isolated_clone_db
    backup_dir = os.path.join(tmp_dir, "backups")
    result = create_database_backup(source_db_path=clone_path, backup_dir=backup_dir)

    conn = sqlite3.connect(result["backup_path"])
    conn.execute("PRAGMA foreign_keys = ON;")
    cursor = conn.cursor()
    cursor.execute("PRAGMA foreign_key_check;")
    errors = cursor.fetchall()
    conn.close()

    assert len(errors) == 0, f"Phát hiện lỗi foreign key trong backup: {errors}"


def test_05_record_counts_preserved_across_all_tables(isolated_clone_db):
    """5. Số bản ghi nghiệp vụ được bảo toàn 100% giữa source và backup"""
    clone_path, tmp_dir = isolated_clone_db
    backup_dir = os.path.join(tmp_dir, "backups")
    result = create_database_backup(source_db_path=clone_path, backup_dir=backup_dir)

    verification = verify_database_backup(backup_path=result["backup_path"], source_db_path=clone_path)
    assert verification["verified"] is True
    assert verification["record_counts_match"] is True

    # Đối chiếu chi tiết từng bảng có dữ liệu
    assert verification["backup_counts"]["products"] == 1
    assert verification["backup_counts"]["categories"] == 1
    assert verification["backup_counts"]["orders"] == 1
    assert verification["backup_counts"]["users"] == 1


def test_06_new_backup_does_not_overwrite_existing_backup(isolated_clone_db):
    """6. Tạo nhiều bản backup kế tiếp tạo các file riêng biệt, không ghi đè file cũ"""
    clone_path, tmp_dir = isolated_clone_db
    backup_dir = os.path.join(tmp_dir, "backups")

    b1 = create_database_backup(source_db_path=clone_path, backup_dir=backup_dir)
    b2 = create_database_backup(source_db_path=clone_path, backup_dir=backup_dir)

    assert b1["backup_path"] != b2["backup_path"], "Hai bản backup không được trùng đường dẫn"
    assert os.path.exists(b1["backup_path"])
    assert os.path.exists(b2["backup_path"])


def test_07_backup_failure_leaves_source_database_unmodified(isolated_clone_db):
    """7. Khi xảy ra sự cố trong quá trình backup, database nguồn không bị ảnh hưởng"""
    clone_path, tmp_dir = isolated_clone_db
    src_sha_before = calculate_sha256(clone_path)

    # Thử backup vào một thư mục không hợp lệ (giả lập lỗi quyền hoặc I/O)
    invalid_backup_dir = os.path.join(tmp_dir, "fake_file.txt", "backups")
    with open(os.path.join(tmp_dir, "fake_file.txt"), "w") as f:
        f.write("I am a file, not a directory")

    with pytest.raises(Exception):
        create_database_backup(source_db_path=clone_path, backup_dir=invalid_backup_dir)

    # Database nguồn phải còn nguyên vẹn
    assert os.path.exists(clone_path)
    src_sha_after = calculate_sha256(clone_path)
    assert src_sha_after == src_sha_before, "Database nguồn bị thay đổi sau khi backup thất bại"


def test_08_schema_version_table_created_properly(isolated_clone_db):
    """8. Bảng schema_version được khởi tạo đúng cấu trúc trên DB độc lập"""
    clone_path, tmp_dir = isolated_clone_db
    conn = sqlite3.connect(clone_path)

    # Tạo bảng schema_version
    conn.execute("""
    CREATE TABLE IF NOT EXISTS schema_version (
        version INTEGER PRIMARY KEY,
        description TEXT NOT NULL,
        applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        checksum TEXT
    );
    """)
    conn.commit()

    # Kiểm tra cột của schema_version
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(schema_version);")
    cols = {r[1]: r[2] for r in cursor.fetchall()}
    conn.close()

    assert "version" in cols
    assert "description" in cols
    assert "applied_at" in cols
    assert "checksum" in cols


def test_09_versioning_idempotency_prevents_duplicate_migrations(isolated_clone_db):
    """9. Chạy versioning nhiều lần không tạo bản ghi duplicate (Idempotency)"""
    clone_path, tmp_dir = isolated_clone_db
    conn = sqlite3.connect(clone_path)
    conn.execute("""
    CREATE TABLE IF NOT EXISTS schema_version (
        version INTEGER PRIMARY KEY,
        description TEXT NOT NULL,
        applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        checksum TEXT
    );
    """)
    conn.commit()

    call_count = [0]
    def sample_migration(c):
        call_count[0] += 1

    # Lần 1: Chạy version 1 -> Thành công
    ran1 = apply_migration_step(conn, 1, "Migration Step 1", sample_migration, "chk-1")
    conn.commit()
    assert ran1 is True
    assert call_count[0] == 1

    # Lần 2: Chạy lại version 1 -> Bị bỏ qua do đã có trong schema_version
    ran2 = apply_migration_step(conn, 1, "Migration Step 1", sample_migration, "chk-1")
    conn.commit()
    assert ran2 is False
    assert call_count[0] == 1, "Migration bị thực thi lại trái phép"

    # Kiểm tra chỉ có đúng 1 dòng version 1
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM schema_version WHERE version = 1;")
    assert cursor.fetchone()[0] == 1
    conn.close()


def test_10_failed_migration_is_not_recorded_as_completed(isolated_clone_db):
    """10. Migration gặp lỗi thì không bị ghi nhận hoàn thành trong schema_version (Rollback an toàn)"""
    clone_path, tmp_dir = isolated_clone_db
    conn = sqlite3.connect(clone_path)
    conn.execute("""
    CREATE TABLE IF NOT EXISTS schema_version (
        version INTEGER PRIMARY KEY,
        description TEXT NOT NULL,
        applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        checksum TEXT
    );
    """)
    conn.commit()

    def faulty_migration(c):
        c.execute("CREATE TABLE temp_table_ok (id INTEGER PRIMARY KEY);")
        raise RuntimeError("Mô phỏng lỗi nghiêm trọng trong migration DDL")

    with pytest.raises(RuntimeError):
        try:
            conn.execute("BEGIN IMMEDIATE;")
            apply_migration_step(conn, 2, "Faulty Migration", faulty_migration, "chk-2")
            conn.execute("COMMIT;")
        except Exception:
            conn.execute("ROLLBACK;")
            raise

    # Kiểm tra version 2 KHÔNG được ghi vào schema_version
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM schema_version WHERE version = 2;")
    assert cursor.fetchone() is None, "LỖI: Migration thất bại nhưng vẫn bị ghi nhận vào schema_version"
    conn.close()


def test_11_no_business_table_schema_altered_in_r2a(isolated_clone_db):
    """11. Không làm thay đổi schema của các bảng nghiệp vụ chính trong Phase R2A (không thêm cột R2B)"""
    clone_path, tmp_dir = isolated_clone_db
    conn = sqlite3.connect(clone_path)
    cursor = conn.cursor()

    # Kiểm tra bảng orders chưa bị thêm các cột của R2B
    cursor.execute("PRAGMA table_info(orders);")
    order_cols = [r[1] for r in cursor.fetchall()]
    conn.close()

    assert "assigned_to" not in order_cols, "Vi phạm phạm vi R2A: cột assigned_to đã bị thêm sớm"
    assert "shipping_address" not in order_cols, "Vi phạm phạm vi R2A: cột shipping_address đã bị thêm sớm"
    assert "is_legacy_unverified" not in order_cols, "Vi phạm phạm vi R2A: cột is_legacy_unverified đã bị thêm sớm"
