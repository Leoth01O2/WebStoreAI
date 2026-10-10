import os
import sqlite3
import tempfile
import pytest

from app.models.schema import (
    run_migration_v2_r2b,
    apply_migration_step,
    is_version_applied,
    get_applied_versions
)

PRE_R2B_BACKUP_FILENAME = "webstore_backup_20261010_153257_264ba0.db"


@pytest.fixture
def clone_production_db():
    """
    Tạo bản clone của snapshot webstore.db tiền migration (Version 1) trong thư mục tạm.
    Dùng để kiểm thử toàn diện kịch bản migration R2B trên dữ liệu thật.
    Tự động dọn dẹp khi kết thúc test.
    """
    backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    source_path = os.path.join(backend_dir, "backups", PRE_R2B_BACKUP_FILENAME)
    assert os.path.exists(source_path), f"Không tìm thấy file snapshot backup tiền migration: {source_path}"

    with tempfile.TemporaryDirectory() as tmp_dir:
        clone_path = os.path.join(tmp_dir, "webstore_clone.db")

        # Sao lưu Online Backup API từ snapshot tiền migration sang bản clone
        src_conn = sqlite3.connect(source_path, timeout=10.0)
        dest_conn = sqlite3.connect(clone_path, timeout=10.0)
        try:
            src_conn.backup(dest_conn)
        finally:
            dest_conn.close()
            src_conn.close()

        yield clone_path, tmp_dir


def test_01_clone_pre_migration_state(clone_production_db):
    """1. Kiểm tra trạng thái tiền migration: 317 đơn hàng, MAX(id)=346, chưa có cột R2B"""
    clone_path, _ = clone_production_db
    conn = sqlite3.connect(clone_path)
    try:
        cursor = conn.cursor()
        count, min_id, max_id = cursor.execute("SELECT COUNT(*), MIN(id), MAX(id) FROM orders;").fetchone()
        assert count == 317, f"Số đơn hàng nguồn phải là 317, thực tế: {count}"
        assert max_id == 346, f"MAX(id) thực tế là 346 (có khoảng trống), thực tế: {max_id}"

        cols = [r[1] for r in cursor.execute("PRAGMA table_info(orders);").fetchall()]
        assert "assigned_to" not in cols
        assert "shipping_name" not in cols
        assert "shipping_phone" not in cols
        assert "shipping_address" not in cols
        assert "is_legacy_unverified" not in cols
    finally:
        conn.close()


def test_02_migration_adds_all_required_columns(clone_production_db):
    """2. Migration thêm đầy đủ 5 cột mới vào bảng orders"""
    clone_path, _ = clone_production_db
    conn = sqlite3.connect(clone_path)
    try:
        conn.execute("PRAGMA foreign_keys = ON;")
        ran = apply_migration_step(
            conn,
            version=2,
            description="R2B: Phased column expansion for orders and legacy unverified marking",
            migration_callable=run_migration_v2_r2b,
            checksum="r2b-test-v2"
        )
        conn.commit()
        assert ran is True

        cursor = conn.cursor()
        cols = {r[1]: r[2] for r in cursor.execute("PRAGMA table_info(orders);").fetchall()}
        assert "assigned_to" in cols
        assert "shipping_name" in cols
        assert "shipping_phone" in cols
        assert "shipping_address" in cols
        assert "is_legacy_unverified" in cols
    finally:
        conn.close()


def test_03_all_legacy_orders_marked_is_legacy_unverified_1(clone_production_db):
    """3. Toàn bộ chính xác 317 đơn hàng lịch sử được đánh dấu is_legacy_unverified = 1"""
    clone_path, _ = clone_production_db
    conn = sqlite3.connect(clone_path)
    try:
        conn.execute("PRAGMA foreign_keys = ON;")
        apply_migration_step(
            conn,
            version=2,
            description="R2B: Test legacy marking",
            migration_callable=run_migration_v2_r2b,
            checksum="r2b-test-v2"
        )
        conn.commit()

        cursor = conn.cursor()
        legacy_count = cursor.execute("SELECT COUNT(*) FROM orders WHERE is_legacy_unverified = 1;").fetchone()[0]
        total_count = cursor.execute("SELECT COUNT(*) FROM orders;").fetchone()[0]

        assert legacy_count == 317, f"Tất cả 317 đơn lịch sử phải có is_legacy_unverified = 1, thực tế: {legacy_count}"
        assert legacy_count == total_count
    finally:
        conn.close()


def test_04_id_gaps_handled_correctly_without_count_cutoff(clone_production_db):
    """4. Đơn hàng có ID > 317 (lên tới 346) cũng được đánh dấu đúng, chứng minh không dùng 'id <= 317'"""
    clone_path, _ = clone_production_db
    conn = sqlite3.connect(clone_path)
    try:
        conn.execute("PRAGMA foreign_keys = ON;")
        apply_migration_step(
            conn,
            version=2,
            description="R2B: Test gap handling",
            migration_callable=run_migration_v2_r2b,
            checksum="r2b-test-v2"
        )
        conn.commit()

        cursor = conn.cursor()
        high_id_unmarked = cursor.execute("SELECT COUNT(*) FROM orders WHERE id > 317 AND is_legacy_unverified = 0;").fetchone()[0]
        high_id_marked = cursor.execute("SELECT COUNT(*) FROM orders WHERE id > 317 AND is_legacy_unverified = 1;").fetchone()[0]

        assert high_id_unmarked == 0, "LỖI LỚN: Có đơn hàng ID > 317 bị bỏ sót không được đánh dấu!"
        assert high_id_marked > 0, "Phải có các đơn hàng lịch sử mang ID > 317"
    finally:
        conn.close()


def test_05_gap_simulation_standalone_database():
    """5. Thử nghiệm trên database nhân tạo có khoảng trống lớn [1, 2, 5, 1000]"""
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = os.path.join(tmp_dir, "gap_test.db")
        conn = sqlite3.connect(db_path)
        try:
            conn.execute("CREATE TABLE orders (id INTEGER PRIMARY KEY, order_code TEXT);")
            conn.execute("CREATE TABLE schema_version (version INTEGER PRIMARY KEY, description TEXT, applied_at TIMESTAMP, checksum TEXT);")
            for order_id in [1, 2, 5, 1000]:
                conn.execute("INSERT INTO orders (id, order_code) VALUES (?, ?);", (order_id, f"HD-{order_id}"))
            conn.commit()

            apply_migration_step(
                conn,
                version=2,
                description="R2B: Gap simulation",
                migration_callable=run_migration_v2_r2b,
                checksum="r2b-gap-sim"
            )
            conn.commit()

            cursor = conn.cursor()
            res_1000 = cursor.execute("SELECT is_legacy_unverified FROM orders WHERE id = 1000;").fetchone()[0]
            assert res_1000 == 1, "Đơn ID 1000 bị bỏ sót nếu dùng COUNT(*) làm ngưỡng!"
            all_marked = cursor.execute("SELECT COUNT(*) FROM orders WHERE is_legacy_unverified = 1;").fetchone()[0]
            assert all_marked == 4
        finally:
            conn.close()


def test_06_new_orders_created_post_migration_default_to_0(clone_production_db):
    """6. Đơn hàng mới tạo sau migration có mặc định is_legacy_unverified = 0"""
    clone_path, _ = clone_production_db
    conn = sqlite3.connect(clone_path)
    try:
        conn.execute("PRAGMA foreign_keys = ON;")
        apply_migration_step(
            conn,
            version=2,
            description="R2B: Apply",
            migration_callable=run_migration_v2_r2b,
            checksum="r2b-test-v2"
        )
        conn.commit()

        conn.execute(
            """INSERT INTO orders (order_code, total_amount, final_amount, payment_method, payment_status, status)
               VALUES ('NEW-ORDER-R2B', 150000, 150000, 'cash', 'pending', 'pending');"""
        )
        conn.commit()

        cursor = conn.cursor()
        cursor.execute("SELECT is_legacy_unverified FROM orders WHERE order_code = 'NEW-ORDER-R2B';")
        flag = cursor.fetchone()[0]
        assert flag == 0, f"Đơn hàng mới tạo phải có is_legacy_unverified = 0, thực tế: {flag}"
    finally:
        conn.close()


def test_07_payment_status_values_strictly_preserved(clone_production_db):
    """7. Các giá trị payment_status lịch sử ('completed', 'paid', 'pending') được giữ nguyên 100%"""
    clone_path, _ = clone_production_db
    conn = sqlite3.connect(clone_path)
    try:
        cursor = conn.cursor()
        before_counts = dict(cursor.execute("SELECT payment_status, COUNT(*) FROM orders GROUP BY payment_status;").fetchall())

        apply_migration_step(
            conn,
            version=2,
            description="R2B: Apply",
            migration_callable=run_migration_v2_r2b,
            checksum="r2b-test-v2"
        )
        conn.commit()

        after_counts = dict(cursor.execute("SELECT payment_status, COUNT(*) FROM orders GROUP BY payment_status;").fetchall())
        assert before_counts == after_counts, "payment_status đã bị thay đổi trái phép trong Phase R2B!"
        assert "completed" in after_counts, "'completed' phải được giữ nguyên để đối soát ở R2C"
    finally:
        conn.close()


def test_08_order_items_and_business_tables_preserved(clone_production_db):
    """8. Số lượng bản ghi của toàn bộ các bảng nghiệp vụ (order_items, products, etc.) không đổi"""
    clone_path, _ = clone_production_db
    conn = sqlite3.connect(clone_path)
    try:
        cursor = conn.cursor()
        tables = ["order_items", "products", "customers", "users", "categories", "inventory_logs", "purchase_receipts"]
        before = {t: cursor.execute(f"SELECT COUNT(*) FROM {t};").fetchone()[0] for t in tables}

        apply_migration_step(
            conn,
            version=2,
            description="R2B: Apply",
            migration_callable=run_migration_v2_r2b,
            checksum="r2b-test-v2"
        )
        conn.commit()

        after = {t: cursor.execute(f"SELECT COUNT(*) FROM {t};").fetchone()[0] for t in tables}
        assert before == after, f"Số lượng bản ghi bị thay đổi sau migration: before={before}, after={after}"
    finally:
        conn.close()


def test_09_foreign_key_and_integrity_checks_pass(clone_production_db):
    """9. PRAGMA integrity_check và foreign_key_check đạt ok sau migration"""
    clone_path, _ = clone_production_db
    conn = sqlite3.connect(clone_path)
    try:
        conn.execute("PRAGMA foreign_keys = ON;")
        apply_migration_step(
            conn,
            version=2,
            description="R2B: Apply",
            migration_callable=run_migration_v2_r2b,
            checksum="r2b-test-v2"
        )
        conn.commit()

        cursor = conn.cursor()
        integrity = cursor.execute("PRAGMA integrity_check;").fetchall()
        fk_errors = cursor.execute("PRAGMA foreign_key_check;").fetchall()

        assert integrity == [("ok",)], f"Integrity check thất bại: {integrity}"
        assert len(fk_errors) == 0, f"Foreign key check có lỗi: {fk_errors}"
    finally:
        conn.close()


def test_10_indexes_and_constraints_preserved(clone_production_db):
    """10. Các index hiện có của bảng orders vẫn tồn tại đầy đủ"""
    clone_path, _ = clone_production_db
    conn = sqlite3.connect(clone_path)
    try:
        apply_migration_step(
            conn,
            version=2,
            description="R2B: Apply",
            migration_callable=run_migration_v2_r2b,
            checksum="r2b-test-v2"
        )
        conn.commit()

        cursor = conn.cursor()
        indexes = [r[0] for r in cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='orders';").fetchall()]
        assert "idx_orders_code" in indexes
        assert "idx_orders_created" in indexes
        assert "idx_orders_status" in indexes
    finally:
        conn.close()


def test_11_migration_idempotency_rerun_is_noop(clone_production_db):
    """11. Chạy lại migration Version 2 không thay đổi dữ liệu (Idempotency - No-op)"""
    clone_path, _ = clone_production_db
    conn = sqlite3.connect(clone_path)
    try:
        ran1 = apply_migration_step(
            conn,
            version=2,
            description="R2B: Idempotency",
            migration_callable=run_migration_v2_r2b,
            checksum="r2b-idem"
        )
        conn.commit()
        assert ran1 is True

        conn.execute(
            """INSERT INTO orders (order_code, total_amount, final_amount, payment_method, payment_status, status)
               VALUES ('NEW-AFTER-MIG', 50000, 50000, 'cash', 'pending', 'pending');"""
        )
        conn.commit()

        ran2 = apply_migration_step(
            conn,
            version=2,
            description="R2B: Idempotency",
            migration_callable=run_migration_v2_r2b,
            checksum="r2b-idem"
        )
        conn.commit()
        assert ran2 is False

        cursor = conn.cursor()
        new_flag = cursor.execute("SELECT is_legacy_unverified FROM orders WHERE order_code = 'NEW-AFTER-MIG';").fetchone()[0]
        versions = get_applied_versions(conn)

        assert new_flag == 0, "Idempotency thất bại: đơn mới bị đánh dấu nhầm khi migration chạy lặp!"
        assert versions.count(2) == 1, "Phiên bản 2 bị duplicate trong schema_version!"
    finally:
        conn.close()


def test_12_migration_rollback_on_failure():
    """12. Nếu migration thất bại giữa chừng, transaction rollback hoàn toàn và schema_version không lưu version 2"""
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = os.path.join(tmp_dir, "rollback_test.db")
        conn = sqlite3.connect(db_path)
        try:
            conn.execute("CREATE TABLE orders (id INTEGER PRIMARY KEY, order_code TEXT);")
            conn.execute("CREATE TABLE schema_version (version INTEGER PRIMARY KEY, description TEXT, applied_at TIMESTAMP, checksum TEXT);")
            conn.commit()

            def faulty_r2b(c):
                c.execute("ALTER TABLE orders ADD COLUMN assigned_to INTEGER;")
                raise RuntimeError("Giả lập lỗi disk I/O giữa chừng khi cập nhật orders")

            with pytest.raises(RuntimeError):
                try:
                    conn.execute("BEGIN IMMEDIATE;")
                    apply_migration_step(
                        conn,
                        version=2,
                        description="Faulty R2B",
                        migration_callable=faulty_r2b,
                        checksum="faulty"
                    )
                    conn.execute("COMMIT;")
                except Exception:
                    conn.execute("ROLLBACK;")
                    raise

            cursor = conn.cursor()
            assert is_version_applied(conn, 2) is False
        finally:
            conn.close()
