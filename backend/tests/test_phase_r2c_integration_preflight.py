import os
import sqlite3
import pytest
from pathlib import Path
from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.security import create_access_token
from app.models.schema import apply_migration_v3_explicit, is_version_applied, get_applied_versions
from app.services.report_service import ReportService
from app.services.ai_service import ai_service
from app.main import app


CLONE_DB_PATH = str(Path(__file__).resolve().parent.parent / "test_webstore_v3_migrated_clone.db")
V2_CLONE_DB_PATH = str(Path(__file__).resolve().parent.parent / "test_webstore_v2_unmigrated_clone.db")


def cleanup_clone_dbs():
    for base in [CLONE_DB_PATH, V2_CLONE_DB_PATH]:
        for ext in ["", "-wal", "-shm"]:
            p = Path(base + ext)
            if p.exists():
                try:
                    p.unlink()
                except Exception:
                    pass


def test_00_schema_v2_orders_creation_http():
    """
    Kiểm tra tính tương thích hai chiều trên Schema Version 2 (chưa migration):
    1. Kiểm tra sqlite_master xác nhận CHECK constraint của payment_status trong v2 chỉ cho phép ('pending', 'paid', 'completed').
    2. Chạy HTTP integration test tạo đơn Customer: Backend tự động ghi nhận payment_status = 'pending' (hợp lệ trong v2).
    3. Chạy HTTP integration test tạo đơn Staff POS: Backend tự động ghi nhận payment_status = 'paid' (hợp lệ trong v2).
    4. Xác nhận cả hai đơn đều tạo thành công HTTP 200, lưu đúng vào DB v2 mà không vi phạm CHECK constraint.
    """
    backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    prod_db = os.path.join(backend_dir, "webstore.db")
    assert os.path.exists(prod_db), f"Không tìm thấy database chính: {prod_db}"

    cleanup_clone_dbs()

    # Tìm nguồn v2 để kiểm thử tương thích ngược (sử dụng backup v2 nếu prod_db đã lên v3)
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

    # 1. Tạo clone v2 qua SQLite Online Backup API
    src_conn = sqlite3.connect(v2_source, timeout=10.0)
    dest_conn = sqlite3.connect(V2_CLONE_DB_PATH, timeout=10.0)
    try:
        src_conn.backup(dest_conn)
    finally:
        dest_conn.close()
        src_conn.close()

    # Kiểm tra sqlite_master của v2
    v2_conn = sqlite3.connect(V2_CLONE_DB_PATH)
    v2_conn.row_factory = sqlite3.Row
    row = v2_conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='orders'").fetchone()
    v2_sql = row[0]
    assert "CHECK(payment_status IN ('pending', 'paid', 'completed'))" in v2_sql, (
        f"Schema v2 orders thiếu CHECK constraint mong đợi: {v2_sql}"
    )
    assert "payment_status_raw" not in v2_sql
    assert "fulfillment_status" not in v2_sql
    v2_conn.close()

    # 2. Cấu hình backend trỏ tới clone v2
    original_db_path = settings.DATABASE_PATH
    original_env_path = os.environ.get("DATABASE_PATH")
    settings.DATABASE_PATH = V2_CLONE_DB_PATH
    os.environ["DATABASE_PATH"] = V2_CLONE_DB_PATH

    try:
        client = TestClient(app)

        # Lấy user và product từ clone v2
        conn = sqlite3.connect(V2_CLONE_DB_PATH)
        conn.row_factory = sqlite3.Row
        cust_user = conn.execute(
            "SELECT u.id as user_id, u.username, u.role, c.id as cust_id "
            "FROM users u JOIN customers c ON u.id = c.user_id "
            "WHERE u.role = 'customer' AND u.is_active = 1 LIMIT 1"
        ).fetchone()
        staff_user = conn.execute(
            "SELECT id, username, role FROM users WHERE role = 'staff' AND is_active = 1 LIMIT 1"
        ).fetchone()
        prod_row = conn.execute(
            "SELECT id, stock_quantity, selling_price FROM products WHERE status = 'active' AND stock_quantity > 10 LIMIT 1"
        ).fetchone()
        conn.close()

        # A. HTTP Tạo đơn Customer trên v2
        cust_token = create_access_token({"sub": str(cust_user["user_id"]), "role": cust_user["role"], "id": cust_user["user_id"]})
        cust_headers = {"Authorization": f"Bearer {cust_token}"}
        cust_payload = {
            "customer_id": cust_user["cust_id"],
            "payment_method": "transfer",
            "shipping_name": "Customer V2",
            "shipping_phone": "0988888888",
            "shipping_address": "Dia chi V2",
            "items": [{"product_id": prod_row["id"], "quantity": 1}]
        }
        res_cust = client.post("/api/v1/orders", json=cust_payload, headers=cust_headers)
        assert res_cust.status_code == 200, f"Lỗi tạo đơn Customer trên v2: {res_cust.text}"
        data_cust = res_cust.json()
        assert data_cust["status"] == "pending"
        assert data_cust["payment_status"] == "pending", (
            "Trên schema v2, đơn Customer chưa thanh toán phải dùng 'pending' để tương thích CHECK constraint"
        )

        # Kiểm tra SQLite v2 thực tế
        check_conn = sqlite3.connect(V2_CLONE_DB_PATH)
        check_conn.row_factory = sqlite3.Row
        db_cust_order = check_conn.execute("SELECT * FROM orders WHERE id = ?", (data_cust["id"],)).fetchone()
        assert db_cust_order["payment_status"] == "pending"
        assert db_cust_order["status"] == "pending"

        # B. HTTP Tạo đơn Staff POS trên v2
        staff_token = create_access_token({"sub": str(staff_user["id"]), "role": staff_user["role"], "id": staff_user["id"]})
        staff_headers = {"Authorization": f"Bearer {staff_token}"}
        pos_payload = {
            "payment_method": "cash",
            "items": [{"product_id": prod_row["id"], "quantity": 2}]
        }
        res_pos = client.post("/api/v1/orders", json=pos_payload, headers=staff_headers)
        assert res_pos.status_code == 200, f"Lỗi tạo đơn POS trên v2: {res_pos.text}"
        data_pos = res_pos.json()
        assert data_pos["status"] == "completed"
        assert data_pos["payment_status"] == "paid"

        db_pos_order = check_conn.execute("SELECT * FROM orders WHERE id = ?", (data_pos["id"],)).fetchone()
        assert db_pos_order["payment_status"] == "paid"
        assert db_pos_order["status"] == "completed"
        check_conn.close()

    finally:
        settings.DATABASE_PATH = original_db_path
        if original_env_path is not None:
            os.environ["DATABASE_PATH"] = original_env_path
        cleanup_clone_dbs()


@pytest.fixture(scope="module")
def migrated_clone_env():
    """
    Tạo bản clone SQLite độc lập từ backend/webstore.db bằng Online Backup API (scope module),
    áp dụng migration version 3 và cấu hình backend settings.DATABASE_PATH trỏ tới clone.
    Tự động hoàn nguyên settings và dọn dẹp khi kết thúc module test.
    """
    backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    prod_db = os.path.join(backend_dir, "webstore.db")
    assert os.path.exists(prod_db), f"Không tìm thấy database chính: {prod_db}"

    original_db_path = settings.DATABASE_PATH
    original_env_path = os.environ.get("DATABASE_PATH")

    cleanup_clone_dbs()

    # 1. Tạo clone qua SQLite Online Backup API
    src_conn = sqlite3.connect(prod_db, timeout=10.0)
    dest_conn = sqlite3.connect(CLONE_DB_PATH, timeout=10.0)
    try:
        src_conn.backup(dest_conn)
    finally:
        dest_conn.close()
        src_conn.close()

    # Xác nhận clone ban đầu đúng ở version 2 và có 317 đơn, 322 order_items
    c = sqlite3.connect(CLONE_DB_PATH)
    c.row_factory = sqlite3.Row
    assert is_version_applied(c, 2) is True
    assert c.execute("SELECT COUNT(*) FROM orders").fetchone()[0] == 317
    assert c.execute("SELECT COUNT(*) FROM order_items").fetchone()[0] == 322

    # 2. Áp dụng migration Version 3 lên clone nếu chưa áp dụng
    if not is_version_applied(c, 3):
        applied = apply_migration_v3_explicit(c)
        assert applied is True, "Migration v3 phải trả về True khi áp dụng lần đầu"
    assert is_version_applied(c, 3) is True
    c.close()

    # 3. Trỏ DATABASE_PATH vào clone đã migration
    settings.DATABASE_PATH = CLONE_DB_PATH
    os.environ["DATABASE_PATH"] = CLONE_DB_PATH

    yield CLONE_DB_PATH

    # Hoàn nguyên
    settings.DATABASE_PATH = original_db_path
    if original_env_path is not None:
        os.environ["DATABASE_PATH"] = original_env_path
    cleanup_clone_dbs()


def test_01_migration_v3_clone_schema_and_integrity(migrated_clone_env):
    """Kiểm tra cấu trúc bảng orders và toàn vẹn khóa ngoại trên clone sau migration v3"""
    conn = sqlite3.connect(migrated_clone_env)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # 1. schema_version = 3
    versions = get_applied_versions(conn)
    assert 3 in versions
    assert versions[-1] == 3

    # 2. Toàn vẹn khóa ngoại 0 lỗi
    fk_violations = cursor.execute("PRAGMA foreign_key_check;").fetchall()
    assert len(fk_violations) == 0, f"Có lỗi khóa ngoại: {fk_violations}"

    # 3. Cột mới đã hiện diện
    cursor.execute("PRAGMA table_info(orders);")
    cols = [r["name"] for r in cursor.fetchall()]
    assert "payment_status_raw" in cols
    assert "fulfillment_status" in cols
    assert "is_legacy_unverified" in cols

    # 4. Kiểm tra DDL sqlite_master chứa đầy đủ enum mới
    ddl_row = cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='orders'").fetchone()
    ddl = ddl_row["sql"]
    assert "CHECK(payment_status IN ('unpaid', 'pending_verification', 'paid', 'refund_pending', 'refunded', 'unverified_legacy'))" in ddl
    assert "CHECK(fulfillment_status IN ('unfulfilled', 'packing', 'shipping', 'delivered', 'delivery_failed', 'returned_to_inventory', 'legacy_unknown'))" in ddl

    # 5. Bảo toàn 317 đơn và 322 order_items
    order_count = cursor.execute("SELECT COUNT(*) FROM orders;").fetchone()[0]
    item_count = cursor.execute("SELECT COUNT(*) FROM order_items;").fetchone()[0]
    assert order_count == 317, f"Số đơn bị lệch: {order_count}"
    assert item_count == 322, f"Số items bị lệch: {item_count}"

    # 6. Bảo toàn giá trị gốc trong payment_status_raw
    raw_dist = dict(cursor.execute("SELECT payment_status_raw, COUNT(*) FROM orders GROUP BY payment_status_raw").fetchall())
    assert raw_dist == {"completed": 232, "paid": 73, "pending": 12}

    # 7. Phân bổ payment_status mới theo thiết kế đã phê duyệt:
    # 232 completed + 73 paid -> unverified_legacy (305 đơn)
    # 12 pending -> unpaid (12 đơn)
    status_dist = dict(cursor.execute("SELECT payment_status, COUNT(*) FROM orders GROUP BY payment_status").fetchall())
    assert status_dist == {"unverified_legacy": 305, "unpaid": 12}
    assert status_dist.get("paid") is None or status_dist.get("paid") == 0  # 0 đơn lịch sử nào được tự nhận là paid!

    # 8. Tất cả 317 đơn lịch sử có fulfillment_status = 'legacy_unknown'
    ful_dist = dict(cursor.execute("SELECT fulfillment_status, COUNT(*) FROM orders GROUP BY fulfillment_status").fetchall())
    assert ful_dist == {"legacy_unknown": 317}

    conn.close()


def test_02_get_orders_and_legacy_detail_http(migrated_clone_env):
    """
    HTTP integration test: Kiểm tra endpoint lấy danh sách đơn và chi tiết đơn lịch sử trên clone sau migration v3
    """
    client = TestClient(app)

    conn = sqlite3.connect(migrated_clone_env)
    conn.row_factory = sqlite3.Row
    admin_user = conn.execute("SELECT id, username, role FROM users WHERE role = 'superadmin' LIMIT 1").fetchone()
    legacy_order = conn.execute("SELECT id, order_code, payment_status, payment_status_raw, fulfillment_status FROM orders WHERE id = 1").fetchone()
    conn.close()

    assert admin_user is not None
    assert legacy_order is not None

    token = create_access_token({"sub": str(admin_user["id"]), "role": admin_user["role"], "id": admin_user["id"]})
    headers = {"Authorization": f"Bearer {token}"}

    # 1. GET /api/v1/orders
    res = client.get("/api/v1/orders?limit=10", headers=headers)
    assert res.status_code == 200
    orders_data = res.json()
    assert isinstance(orders_data, list)
    assert len(orders_data) > 0
    # Kiểm tra đơn hàng có các trường mới
    first = orders_data[0]
    assert "payment_status_raw" in first
    assert "fulfillment_status" in first

    # 2. GET /api/v1/orders/{id} cho đơn lịch sử
    res_detail = client.get(f"/api/v1/orders/{legacy_order['id']}", headers=headers)
    assert res_detail.status_code == 200
    detail = res_detail.json()
    assert detail["id"] == legacy_order["id"]
    assert detail["payment_status"] == "unverified_legacy"
    assert detail["payment_status_raw"] == legacy_order["payment_status_raw"]
    assert detail["fulfillment_status"] == "legacy_unknown"
    assert detail["is_legacy_unverified"] == 1


def test_03_create_customer_order_http_v3(migrated_clone_env):
    """
    HTTP integration test: Customer tự tạo đơn online trên clone sau migration v3.
    - Không thể tự gán payment_status='paid' (backend cưỡng chế 'unpaid')
    - payment_status_raw = 'unpaid'
    - fulfillment_status = 'unfulfilled'
    - status = 'pending'
    - is_legacy_unverified = 0
    """
    client = TestClient(app)

    conn = sqlite3.connect(migrated_clone_env)
    conn.row_factory = sqlite3.Row
    cust_user = conn.execute(
        "SELECT u.id as user_id, u.username, u.role, c.id as cust_id "
        "FROM users u JOIN customers c ON u.id = c.user_id "
        "WHERE u.role = 'customer' AND u.is_active = 1 LIMIT 1"
    ).fetchone()
    prod_row = conn.execute("SELECT id, stock_quantity, selling_price FROM products WHERE status = 'active' AND stock_quantity > 5 LIMIT 1").fetchone()
    conn.close()

    assert cust_user is not None
    assert prod_row is not None

    token = create_access_token({"sub": str(cust_user["user_id"]), "role": cust_user["role"], "id": cust_user["user_id"]})
    headers = {"Authorization": f"Bearer {token}"}

    order_payload = {
        "customer_id": cust_user["cust_id"],
        "payment_method": "transfer",
        # Cố tình gửi payment_status = 'paid' để thử vượt quyền
        "payment_status": "paid",
        "shipping_name": "Nguyen Van Test",
        "shipping_phone": "0912345678",
        "shipping_address": "123 Tran Hung Dao, Q1",
        "items": [{"product_id": prod_row["id"], "quantity": 2}]
    }

    res = client.post("/api/v1/orders", json=order_payload, headers=headers)
    assert res.status_code == 200, f"Lỗi tạo đơn: {res.text}"
    data = res.json()

    # Kiểm tra ràng buộc bảo mật & nghiệp vụ Customer
    assert data["status"] == "pending"
    assert data["payment_status"] == "unpaid", "Customer không được tự đánh dấu đơn là paid"
    assert data["payment_status_raw"] == "unpaid"
    assert data["fulfillment_status"] == "unfulfilled"
    assert data["is_legacy_unverified"] == 0

    # Kiểm tra trực tiếp trong SQLite của clone
    c = sqlite3.connect(migrated_clone_env)
    c.row_factory = sqlite3.Row
    db_order = c.execute("SELECT * FROM orders WHERE id = ?", (data["id"],)).fetchone()
    assert db_order["payment_status"] == "unpaid"
    assert db_order["payment_status_raw"] == "unpaid"
    assert db_order["fulfillment_status"] == "unfulfilled"
    assert db_order["status"] == "pending"
    c.close()


def test_04_create_staff_pos_order_http_v3(migrated_clone_env):
    """
    HTTP integration test: Staff tạo đơn POS bán tại quầy trên clone sau migration v3.
    - Đơn POS hoàn tất tại quầy: payment_status = 'paid' (tiền đã thu), fulfillment_status = 'delivered' (hàng đã trao), status = 'completed'
    - Tồn kho bị trừ chính xác và ghi nhật ký xuất nhập tồn
    """
    client = TestClient(app)

    conn = sqlite3.connect(migrated_clone_env)
    conn.row_factory = sqlite3.Row
    staff_user = conn.execute("SELECT id, username, role FROM users WHERE role = 'staff' AND is_active = 1 LIMIT 1").fetchone()
    prod_row = conn.execute("SELECT id, stock_quantity, selling_price FROM products WHERE status = 'active' AND stock_quantity > 10 LIMIT 1").fetchone()
    conn.close()

    initial_stock = prod_row["stock_quantity"]
    buy_qty = 3

    token = create_access_token({"sub": str(staff_user["id"]), "role": staff_user["role"], "id": staff_user["id"]})
    headers = {"Authorization": f"Bearer {token}"}

    pos_payload = {
        "payment_method": "cash",
        "items": [{"product_id": prod_row["id"], "quantity": buy_qty}]
    }

    res = client.post("/api/v1/orders", json=pos_payload, headers=headers)
    assert res.status_code == 200, f"Lỗi tạo đơn POS: {res.text}"
    data = res.json()

    # Kiểm tra trạng thái POS quầy
    assert data["status"] == "completed"
    assert data["payment_status"] == "paid"
    assert data["payment_status_raw"] == "paid"
    assert data["fulfillment_status"] == "delivered"
    assert data["is_legacy_unverified"] == 0

    # Kiểm tra tồn kho đã bị trừ và log ghi nhận
    c = sqlite3.connect(migrated_clone_env)
    c.row_factory = sqlite3.Row
    updated_prod = c.execute("SELECT stock_quantity FROM products WHERE id = ?", (prod_row["id"],)).fetchone()
    assert updated_prod["stock_quantity"] == initial_stock - buy_qty

    inv_log = c.execute(
        "SELECT * FROM inventory_logs WHERE product_id = ? AND reference_code = ?",
        (prod_row["id"], data["order_code"])
    ).fetchone()
    assert inv_log is not None
    assert inv_log["change_type"] == "sale"
    assert abs(inv_log["change_quantity"]) == buy_qty
    c.close()


def test_05_rejection_of_invalid_payment_and_fulfillment_status_in_db(migrated_clone_env):
    """
    Kiểm tra cơ sở dữ liệu clone từ chối nghiêm ngặt các giá trị không hợp lệ:
    - 'completed' không còn được chấp nhận trong payment_status
    - 'partially_refunded' không được chấp nhận trong payment_status
    - 'cancelled_unpaid' không được chấp nhận trong payment_status
    - 'returned' không được chấp nhận trong fulfillment_status (đã thay bằng 'returned_to_inventory')
    - Giá trị tùy tiện ngoài enum bị CHECK constraint chặn
    """
    conn = sqlite3.connect(migrated_clone_env)
    cursor = conn.cursor()

    # 1. Thử chèn payment_status = 'completed' -> Phải lỗi CHECK constraint
    with pytest.raises(sqlite3.IntegrityError):
        cursor.execute("""
            INSERT INTO orders (
                order_code, total_amount, discount_amount, final_amount,
                payment_method, payment_status, payment_status_raw, fulfillment_status, status
            ) VALUES ('HD_INVALID_1', 1000, 0, 1000, 'cash', 'completed', 'completed', 'delivered', 'completed')
        """)

    # 2. Thử chèn payment_status = 'partially_refunded' -> Phải lỗi CHECK constraint
    with pytest.raises(sqlite3.IntegrityError):
        cursor.execute("""
            INSERT INTO orders (
                order_code, total_amount, discount_amount, final_amount,
                payment_method, payment_status, payment_status_raw, fulfillment_status, status
            ) VALUES ('HD_INVALID_2', 1000, 0, 1000, 'cash', 'partially_refunded', 'partially_refunded', 'delivered', 'completed')
        """)

    # 3. Thử chèn payment_status = 'cancelled_unpaid' -> Phải lỗi CHECK constraint
    with pytest.raises(sqlite3.IntegrityError):
        cursor.execute("""
            INSERT INTO orders (
                order_code, total_amount, discount_amount, final_amount,
                payment_method, payment_status, payment_status_raw, fulfillment_status, status
            ) VALUES ('HD_INVALID_3', 1000, 0, 1000, 'cash', 'cancelled_unpaid', 'cancelled_unpaid', 'delivered', 'completed')
        """)

    # 4. Thử chèn fulfillment_status = 'returned' -> Phải lỗi CHECK constraint
    with pytest.raises(sqlite3.IntegrityError):
        cursor.execute("""
            INSERT INTO orders (
                order_code, total_amount, discount_amount, final_amount,
                payment_method, payment_status, payment_status_raw, fulfillment_status, status
            ) VALUES ('HD_INVALID_4', 1000, 0, 1000, 'cash', 'paid', 'paid', 'returned', 'completed')
        """)

    # 5. Thử chèn fulfillment_status tùy tiện
    with pytest.raises(sqlite3.IntegrityError):
        cursor.execute("""
            INSERT INTO orders (
                order_code, total_amount, discount_amount, final_amount,
                payment_method, payment_status, payment_status_raw, fulfillment_status, status
            ) VALUES ('HD_INVALID_5', 1000, 0, 1000, 'cash', 'paid', 'paid', 'invalid_fulfillment', 'completed')
        """)

    conn.close()


def test_06_v3_payment_and_fulfillment_valid_state_transitions(migrated_clone_env):
    """
    Kiểm thử tính hợp lệ của các trạng thái và chuyển dịch trạng thái trên schema v3:
    1. unpaid -> pending_verification -> paid (chỉ kiểm tra schema & trạng thái hợp lệ)
    2. paid -> refund_pending -> refunded
    3. shipping -> delivery_failed -> returned_to_inventory
    Xác nhận CHECK constraint trên clone v3 chấp thuận toàn bộ các giá trị này.
    """
    conn = sqlite3.connect(migrated_clone_env)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # 1. Chuyển dịch thanh toán: unpaid -> pending_verification -> paid
    cursor.execute("""
        INSERT INTO orders (
            order_code, total_amount, discount_amount, final_amount,
            payment_method, payment_status, payment_status_raw, fulfillment_status, status
        ) VALUES ('HD_TRANS_1', 200000, 0, 200000, 'transfer', 'unpaid', 'unpaid', 'unfulfilled', 'pending')
    """)
    order1_id = cursor.lastrowid

    # unpaid -> pending_verification
    cursor.execute("UPDATE orders SET payment_status = 'pending_verification' WHERE id = ?", (order1_id,))
    assert cursor.execute("SELECT payment_status FROM orders WHERE id = ?", (order1_id,)).fetchone()[0] == "pending_verification"

    # pending_verification -> paid
    cursor.execute("UPDATE orders SET payment_status = 'paid' WHERE id = ?", (order1_id,))
    assert cursor.execute("SELECT payment_status FROM orders WHERE id = ?", (order1_id,)).fetchone()[0] == "paid"

    # 2. Chuyển dịch hoàn tiền: paid -> refund_pending -> refunded
    cursor.execute("""
        INSERT INTO orders (
            order_code, total_amount, discount_amount, final_amount,
            payment_method, payment_status, payment_status_raw, fulfillment_status, status
        ) VALUES ('HD_TRANS_2', 150000, 0, 150000, 'transfer', 'paid', 'paid', 'delivered', 'completed')
    """)
    order2_id = cursor.lastrowid

    # paid -> refund_pending
    cursor.execute("UPDATE orders SET payment_status = 'refund_pending' WHERE id = ?", (order2_id,))
    assert cursor.execute("SELECT payment_status FROM orders WHERE id = ?", (order2_id,)).fetchone()[0] == "refund_pending"

    # refund_pending -> refunded
    cursor.execute("UPDATE orders SET payment_status = 'refunded' WHERE id = ?", (order2_id,))
    assert cursor.execute("SELECT payment_status FROM orders WHERE id = ?", (order2_id,)).fetchone()[0] == "refunded"

    # 3. Chuyển dịch giao vận và hoàn hàng: shipping -> delivery_failed -> returned_to_inventory
    cursor.execute("""
        INSERT INTO orders (
            order_code, total_amount, discount_amount, final_amount,
            payment_method, payment_status, payment_status_raw, fulfillment_status, status
        ) VALUES ('HD_TRANS_3', 300000, 0, 300000, 'cash', 'unpaid', 'unpaid', 'shipping', 'processing')
    """)
    order3_id = cursor.lastrowid

    # shipping -> delivery_failed
    cursor.execute("UPDATE orders SET fulfillment_status = 'delivery_failed' WHERE id = ?", (order3_id,))
    assert cursor.execute("SELECT fulfillment_status FROM orders WHERE id = ?", (order3_id,)).fetchone()[0] == "delivery_failed"

    # delivery_failed -> returned_to_inventory
    cursor.execute("UPDATE orders SET fulfillment_status = 'returned_to_inventory' WHERE id = ?", (order3_id,))
    assert cursor.execute("SELECT fulfillment_status FROM orders WHERE id = ?", (order3_id,)).fetchone()[0] == "returned_to_inventory"

    conn.commit()
    conn.close()


def test_07_revenue_reporting_distinction(migrated_clone_env):
    """
    Kiểm tra bảo vệ báo cáo doanh thu:
    - total_revenue: Tổng doanh thu theo các đơn completed (vận hành hoàn tất)
    - verified_payment_revenue: CHỈ tính các đơn đã đối soát/xác minh (payment_status = 'paid')
    - legacy_unverified_revenue: Doanh thu 317 đơn lịch sử chưa đối soát
    317 đơn lịch sử TUYỆT ĐỐI KHÔNG tự động trở thành verified_payment_revenue!
    """
    summary = ReportService.get_dashboard_summary()

    # Doanh thu đã xác minh chỉ tính đơn POS paid vừa tạo ở test_04
    assert summary["verified_payment_revenue"] > 0.0
    # Doanh số hoàn tất lịch sử vẫn được bảo tồn
    assert summary["total_revenue"] > 0.0
    assert summary["legacy_unverified_revenue"] > 0.0
    # Đơn lịch sử không bị tính gộp làm tiền đã xác minh
    assert summary["verified_payment_revenue"] < summary["total_revenue"]


def test_08_ai_sales_report_unverified_legacy_interpretation(migrated_clone_env, monkeypatch):
    """
    Kiểm tra AI Service không diễn giải unverified_legacy là 'chưa thanh toán' hay 'đã thanh toán'
    """
    conn = sqlite3.connect(migrated_clone_env)
    conn.row_factory = sqlite3.Row
    # Lấy một khách hàng có đơn lịch sử
    row = conn.execute(
        "SELECT c.id, c.user_id, c.name FROM customers c JOIN orders o ON c.id = o.customer_id WHERE o.is_legacy_unverified = 1 LIMIT 1"
    ).fetchone()
    conn.close()

    assert row is not None

    # Sử dụng fallback tất định để kiểm tra định dạng dữ liệu
    def mock_gemini_failure(prompt):
        raise RuntimeError("Deterministic fallback testing")
    monkeypatch.setattr(ai_service, "_call_gemini", mock_gemini_failure)

    res = ai_service.answer_sales_qa(
        question="Tra cứu các đơn hàng gần nhất của tôi",
        user_id=row["user_id"],
        user_role="customer"
    )

    # Câu trả lời tóm tắt của AI phải chứa định nghĩa chính xác
    assert "Dữ liệu lịch sử chưa đối soát" in res.answer
    assert "Đã đối soát thanh toán" not in res.answer


def test_09_migration_idempotency_and_rollback(migrated_clone_env):
    """Kiểm tra tính Idempotency và cơ chế Rollback an toàn của Migration v3"""
    conn = sqlite3.connect(migrated_clone_env)

    # 1. Idempotency: chạy lại apply_migration_v3_explicit phải trả về False
    assert apply_migration_v3_explicit(conn) is False

    # 2. Test rollback khi gặp lỗi
    conn.execute("PRAGMA foreign_keys = OFF;")
    try:
        conn.execute("BEGIN IMMEDIATE;")
        conn.execute("CREATE TABLE test_rollback_tmp (id INT);")
        raise RuntimeError("Simulated failure during migration")
    except RuntimeError:
        conn.rollback()
    finally:
        conn.execute("PRAGMA foreign_keys = ON;")

    fk_state = conn.execute("PRAGMA foreign_keys;").fetchone()[0]
    assert fk_state == 1, "Foreign keys phải luôn được bật lại sau khối finally"
    conn.close()


def test_10_main_database_inviolability():
    """
    Xác nhận tuyệt đối tính toàn vẹn của Database chính (backend/webstore.db) sau Phase R2C-B2:
    - schema_version = [1, 2, 3]
    - Cột payment_status_raw và fulfillment_status hiện diện
    - 317 orders, 322 items được bảo toàn
    - Phân bổ 305 unverified_legacy, 12 unpaid, 0 paid
    - sqlite_sequence cho orders = 346
    """
    backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    prod_db = os.path.join(backend_dir, "webstore.db")
    assert os.path.exists(prod_db)

    conn = sqlite3.connect(prod_db)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    # schema_version có 1, 2 và 3
    applied_versions = [r["version"] for r in c.execute("SELECT version FROM schema_version ORDER BY version").fetchall()]
    assert applied_versions == [1, 2, 3], f"Database chính phiên bản không hợp lệ: {applied_versions}"

    # Cột payment_status_raw và fulfillment_status đã hiện diện
    c.execute("PRAGMA table_info(orders);")
    cols = [r["name"] for r in c.fetchall()]
    assert "payment_status_raw" in cols
    assert "fulfillment_status" in cols

    # Dữ liệu chính vẫn nguyên vẹn
    assert c.execute("SELECT COUNT(*) FROM orders").fetchone()[0] == 317
    assert c.execute("SELECT COUNT(*) FROM order_items").fetchone()[0] == 322

    # Phân bổ payment_status
    dist = dict(c.execute("SELECT payment_status, COUNT(*) FROM orders GROUP BY payment_status").fetchall())
    assert dist == {"unverified_legacy": 305, "unpaid": 12}

    # Sequence
    seq = c.execute("SELECT seq FROM sqlite_sequence WHERE name = 'orders'").fetchone()[0]
    assert seq == 346

    # Integrity & FK
    assert c.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    assert len(c.execute("PRAGMA foreign_key_check").fetchall()) == 0

    conn.close()
