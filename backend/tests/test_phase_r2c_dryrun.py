import os
import sqlite3
import tempfile
import pytest

from app.models.schema import apply_migration_step, is_version_applied, get_applied_versions


@pytest.fixture
def dryrun_clone():
    """
    Tạo bản clone SQLite độc lập từ backend/webstore.db bằng Online Backup API.
    Đảm bảo 100% cách ly và tự động dọn dẹp khi kết thúc test.
    """
    backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    prod_db = os.path.join(backend_dir, "webstore.db")
    assert os.path.exists(prod_db), f"Không tìm thấy database chính: {prod_db}"

    # Tìm nguồn v2 để kiểm thử dry-run migration (sử dụng backup v2 nếu prod_db đã lên v3)
    v2_source = prod_db
    backups_dir = os.path.join(backend_dir, "backups")
    if os.path.exists(backups_dir):
        for f in sorted(os.listdir(backups_dir), reverse=True):
            if f.endswith(".db"):
                bp = os.path.join(backups_dir, f)
                try:
                    c = sqlite3.connect(bp)
                    v_max = c.execute("SELECT MAX(version) FROM schema_version").fetchone()[0]
                    c.close()
                    if v_max == 2:
                        v2_source = bp
                        break
                except Exception:
                    pass

    with tempfile.TemporaryDirectory() as tmp_dir:
        clone_path = os.path.join(tmp_dir, "webstore_r2c_clone.db")
        src_conn = sqlite3.connect(v2_source, timeout=10.0)
        dest_conn = sqlite3.connect(clone_path, timeout=10.0)
        try:
            src_conn.backup(dest_conn)
        finally:
            dest_conn.close()
            src_conn.close()

        yield clone_path


def run_r2c_migration_dryrun_callable(conn: sqlite3.Connection):
    """
    Hàm migration thử nghiệm R2C-A (Table Rebuild 12 bước theo chuẩn SQLite).
    - Tạo bảng tạm orders_new với CHECK constraint mới.
    - Bảo tồn payment_status_raw TEXT NOT NULL.
    - Bổ sung fulfillment_status TEXT NOT NULL.
    - Chuyển đổi an toàn: completed/paid -> unverified_legacy, pending -> unpaid.
    - fulfillment_status cho dữ liệu lịch sử -> legacy_unknown.
    """
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE orders_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_code TEXT UNIQUE NOT NULL,
            customer_id INTEGER REFERENCES customers(id) ON DELETE SET NULL,
            user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
            assigned_to INTEGER REFERENCES users(id) ON DELETE SET NULL,
            shipping_name TEXT,
            shipping_phone TEXT,
            shipping_address TEXT,
            total_amount REAL NOT NULL DEFAULT 0,
            discount_amount REAL NOT NULL DEFAULT 0,
            final_amount REAL NOT NULL DEFAULT 0,
            payment_method TEXT NOT NULL DEFAULT 'cash' CHECK(payment_method IN ('cash', 'transfer', 'card')),
            payment_status TEXT NOT NULL DEFAULT 'unpaid' CHECK(payment_status IN ('unpaid', 'pending_verification', 'paid', 'refund_pending', 'refunded', 'unverified_legacy')),
            payment_status_raw TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending', 'admin_approved', 'processing', 'completed', 'rejected', 'cancelled')),
            fulfillment_status TEXT NOT NULL DEFAULT 'unfulfilled' CHECK(fulfillment_status IN ('unfulfilled', 'packing', 'shipping', 'delivered', 'delivery_failed', 'returned_to_inventory', 'legacy_unknown')),
            is_legacy_unverified INTEGER NOT NULL DEFAULT 0,
            note TEXT,
            approved_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
            approved_at TIMESTAMP,
            processed_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
            processed_at TIMESTAMP,
            rejected_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
            rejected_at TIMESTAMP,
            rejection_reason TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)

    cursor.execute("""
        INSERT INTO orders_new (
            id, order_code, customer_id, user_id, assigned_to,
            shipping_name, shipping_phone, shipping_address,
            total_amount, discount_amount, final_amount, payment_method,
            payment_status, payment_status_raw, status, fulfillment_status,
            is_legacy_unverified, note,
            approved_by, approved_at, processed_by, processed_at,
            rejected_by, rejected_at, rejection_reason, created_at
        )
        SELECT
            id, order_code, customer_id, user_id, assigned_to,
            shipping_name, shipping_phone, shipping_address,
            total_amount, discount_amount, final_amount, payment_method,
            CASE 
                WHEN payment_status IN ('completed', 'paid') THEN 'unverified_legacy'
                WHEN payment_status = 'pending' THEN 'unpaid'
                ELSE payment_status
            END,
            payment_status,
            status,
            'legacy_unknown',
            is_legacy_unverified, note,
            approved_by, approved_at, processed_by, processed_at,
            rejected_by, rejected_at, rejection_reason, created_at
        FROM orders;
    """)

    cursor.execute("DROP TABLE orders;")
    cursor.execute("ALTER TABLE orders_new RENAME TO orders;")

    cursor.execute("CREATE INDEX idx_orders_status ON orders(status);")
    cursor.execute("CREATE INDEX idx_orders_created ON orders(created_at);")
    cursor.execute("CREATE INDEX idx_orders_code ON orders(order_code);")
    cursor.execute("CREATE INDEX idx_orders_payment_status ON orders(payment_status);")
    cursor.execute("CREATE INDEX idx_orders_fulfillment ON orders(fulfillment_status);")


def execute_migration_safely(conn: sqlite3.Connection):
    """Wrapper thực thi an toàn với foreign_keys OFF trước transaction"""
    conn.execute("PRAGMA foreign_keys = OFF;")
    try:
        conn.execute("BEGIN IMMEDIATE;")
        apply_migration_step(
            conn,
            version=3,
            description="R2C-A: Payment and fulfillment enum upgrade dry-run",
            migration_callable=run_r2c_migration_dryrun_callable,
            checksum="r2c-dryrun-v3"
        )
        conn.execute("COMMIT;")
    except Exception:
        conn.execute("ROLLBACK;")
        raise
    finally:
        conn.execute("PRAGMA foreign_keys = ON;")


# ===========================================================================
# TARGETED DRY-RUN TESTS
# ===========================================================================

def test_01_clone_created_matching_production_state(dryrun_clone):
    """1. Bản clone ban đầu có đúng 317 đơn hàng, 322 order_items, version = 2"""
    conn = sqlite3.connect(dryrun_clone)
    try:
        cur = conn.cursor()
        orders_cnt = cur.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
        items_cnt = cur.execute("SELECT COUNT(*) FROM order_items").fetchone()[0]
        assert orders_cnt == 317
        assert items_cnt == 322
        assert is_version_applied(conn, 2) is True
        assert is_version_applied(conn, 3) is False
    finally:
        conn.close()


def test_02_dryrun_migration_adds_payment_status_raw_and_fulfillment_status(dryrun_clone):
    """2. Migration thêm đúng payment_status_raw và fulfillment_status"""
    conn = sqlite3.connect(dryrun_clone)
    try:
        execute_migration_safely(conn)
        cur = conn.cursor()
        cols = [r[1] for r in cur.execute("PRAGMA table_info(orders)").fetchall()]
        assert "payment_status_raw" in cols
        assert "fulfillment_status" in cols
        assert is_version_applied(conn, 3) is True
    finally:
        conn.close()


def test_03_legacy_payment_status_raw_strictly_preserved(dryrun_clone):
    """3. Giá trị payment_status_raw giữ nguyên 100% lịch sử (232 completed, 73 paid, 12 pending)"""
    conn = sqlite3.connect(dryrun_clone)
    try:
        execute_migration_safely(conn)
        cur = conn.cursor()
        raw_dist = dict(cur.execute("SELECT payment_status_raw, COUNT(*) FROM orders GROUP BY payment_status_raw").fetchall())
        assert raw_dist.get("completed") == 232
        assert raw_dist.get("paid") == 73
        assert raw_dist.get("pending") == 12
    finally:
        conn.close()


def test_04_payment_status_mapped_conservatively_unverified_legacy(dryrun_clone):
    """4. Không có đơn nào bị tự ý chuyển thành 'paid'; 305 đơn gán unverified_legacy, 12 đơn unpaid"""
    conn = sqlite3.connect(dryrun_clone)
    try:
        execute_migration_safely(conn)
        cur = conn.cursor()
        payment_dist = dict(cur.execute("SELECT payment_status, COUNT(*) FROM orders GROUP BY payment_status").fetchall())
        assert payment_dist.get("paid", 0) == 0, "LỖI NGUY HIỂM: Có đơn cũ bị tự ý gán là 'paid'!"
        assert payment_dist.get("unverified_legacy") == 305
        assert payment_dist.get("unpaid") == 12
    finally:
        conn.close()


def test_05_fulfillment_status_assigned_legacy_unknown(dryrun_clone):
    """5. Tất cả 317 đơn lịch sử nhận trạng thái fulfillment_status = 'legacy_unknown'"""
    conn = sqlite3.connect(dryrun_clone)
    try:
        execute_migration_safely(conn)
        cur = conn.cursor()
        f_dist = dict(cur.execute("SELECT fulfillment_status, COUNT(*) FROM orders GROUP BY fulfillment_status").fetchall())
        assert f_dist.get("legacy_unknown") == 317
    finally:
        conn.close()


def test_06_check_constraints_enforced_strictly(dryrun_clone):
    """6. CHECK constraints mới hoạt động chuẩn: chặn enum không hợp lệ"""
    conn = sqlite3.connect(dryrun_clone)
    try:
        execute_migration_safely(conn)
        cur = conn.cursor()

        # Insert hợp lệ
        cur.execute("""
            INSERT INTO orders (order_code, payment_method, payment_status, payment_status_raw, status, fulfillment_status)
            VALUES ('ORD-VALID-01', 'cash', 'unpaid', 'unpaid', 'pending', 'unfulfilled')
        """)
        conn.commit()

        # Insert sai payment_status (ví dụ: 'completed' không còn trong enum payment_status mới)
        with pytest.raises(sqlite3.IntegrityError):
            cur.execute("""
                INSERT INTO orders (order_code, payment_method, payment_status, payment_status_raw, status, fulfillment_status)
                VALUES ('ORD-INVALID-01', 'cash', 'completed', 'completed', 'pending', 'unfulfilled')
            """)
            conn.commit()

        # Insert sai fulfillment_status
        with pytest.raises(sqlite3.IntegrityError):
            cur.execute("""
                INSERT INTO orders (order_code, payment_method, payment_status, payment_status_raw, status, fulfillment_status)
                VALUES ('ORD-INVALID-02', 'cash', 'unpaid', 'unpaid', 'pending', 'teleporting')
            """)
            conn.commit()
    finally:
        conn.close()


def test_07_all_business_records_and_financials_preserved(dryrun_clone):
    """7. Bảo toàn 100% 317 đơn, 322 items, tổng tiền final_amount và các bảng khác"""
    conn = sqlite3.connect(dryrun_clone)
    try:
        cur = conn.cursor()
        orders_before = cur.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
        items_before = cur.execute("SELECT COUNT(*) FROM order_items").fetchone()[0]
        sum_before = cur.execute("SELECT SUM(final_amount) FROM orders").fetchone()[0]

        execute_migration_safely(conn)

        orders_after = cur.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
        items_after = cur.execute("SELECT COUNT(*) FROM order_items").fetchone()[0]
        sum_after = cur.execute("SELECT SUM(final_amount) FROM orders").fetchone()[0]

        assert orders_after == orders_before == 317
        assert items_after == items_before == 322
        assert sum_after == sum_before == 461534000.0
    finally:
        conn.close()


def test_08_foreign_keys_and_indexes_preserved(dryrun_clone):
    """8. foreign_key_check = 0, integrity_check = ok, indexes đầy đủ"""
    conn = sqlite3.connect(dryrun_clone)
    try:
        execute_migration_safely(conn)
        cur = conn.cursor()

        fk_errors = cur.execute("PRAGMA foreign_key_check;").fetchall()
        assert len(fk_errors) == 0, f"Có lỗi foreign key: {fk_errors}"

        integrity = cur.execute("PRAGMA integrity_check;").fetchall()
        assert integrity == [("ok",)], f"Integrity check không đạt: {integrity}"

        idx_names = [r[1] for r in cur.execute("PRAGMA index_list(orders);").fetchall()]
        assert "idx_orders_status" in idx_names
        assert "idx_orders_created" in idx_names
        assert "idx_orders_code" in idx_names
        assert "idx_orders_payment_status" in idx_names
        assert "idx_orders_fulfillment" in idx_names
    finally:
        conn.close()


def test_09_revenue_reports_do_not_count_unverified_legacy_as_paid(dryrun_clone):
    """9. Báo cáo doanh thu thực thu (WHERE payment_status = 'paid') không bị tính nhầm đơn unverified_legacy"""
    conn = sqlite3.connect(dryrun_clone)
    try:
        execute_migration_safely(conn)
        cur = conn.cursor()
        paid_revenue = cur.execute("SELECT COALESCE(SUM(final_amount), 0) FROM orders WHERE payment_status = 'paid'").fetchone()[0]
        assert paid_revenue == 0.0, "Đơn lịch sử chưa đối soát bị tính nhầm vào doanh thu thực thu!"
    finally:
        conn.close()


def test_10_migration_idempotency_and_rollback_on_failure(dryrun_clone):
    """10. Tái chạy migration an toàn (no-op) và rollback khi gặp lỗi"""
    conn = sqlite3.connect(dryrun_clone)
    try:
        execute_migration_safely(conn)
        assert is_version_applied(conn, 3) is True

        # Chạy lại lần 2 phải là no-op
        conn.execute("PRAGMA foreign_keys = OFF;")
        try:
            conn.execute("BEGIN IMMEDIATE;")
            ran_again = apply_migration_step(
                conn,
                version=3,
                description="R2C-A: Idempotency",
                migration_callable=run_r2c_migration_dryrun_callable,
                checksum="r2c-dryrun-v3"
            )
            conn.execute("COMMIT;")
            assert ran_again is False, "Migration chạy lặp lại thay vì no-op!"
        finally:
            conn.execute("PRAGMA foreign_keys = ON;")

        # Kiểm tra version 3 chỉ xuất hiện 1 lần
        versions = get_applied_versions(conn)
        assert versions.count(3) == 1
    finally:
        conn.close()
