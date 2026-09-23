import pytest
import sqlite3
from fastapi.testclient import TestClient
from app.main import app
from app.models.schema import init_db
from app.core.database import get_db, get_db_connection
from app.schemas.order import OrderResponse, OrderCreate, OrderItemCreate, ORDER_STATUSES

client = TestClient(app)

def get_admin_token():
    res = client.post("/api/v1/auth/login", json={"username": "admin", "password": "Admin@123"})
    return res.json()["access_token"]

def test_workflow_columns_exist_in_database():
    """DoD 1: Database SQLite có đầy đủ các cột workflow mới"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(orders)")
        cols = {row["name"]: row["type"] for row in cursor.fetchall()}
        
        expected_cols = [
            "approved_by",
            "approved_at",
            "processed_by",
            "processed_at",
            "rejected_by",
            "rejected_at",
            "rejection_reason",
        ]
        for col in expected_cols:
            assert col in cols, f"Cột {col} chưa tồn tại trong bảng orders"

def test_workflow_all_statuses_allowed():
    """DoD 2: Mở rộng ràng buộc status cho phép đầy đủ 6 trạng thái workflow"""
    statuses = ["pending", "admin_approved", "processing", "completed", "rejected", "cancelled"]
    
    with get_db() as conn:
        cursor = conn.cursor()
        for idx, st in enumerate(statuses):
            code = f"TEST-WF-{st.upper()[:4]}-{idx}"
            cursor.execute(
                """INSERT INTO orders (
                    order_code, total_amount, final_amount, status, note
                ) VALUES (?, 100000, 100000, ?, 'Test workflow status')""",
                (code, st)
            )
            inserted_id = cursor.lastrowid
            
            # Đọc lại kiểm tra
            cursor.execute("SELECT status FROM orders WHERE id = ?", (inserted_id,))
            row = cursor.fetchone()
            assert row["status"] == st, f"Trạng thái {st} không khớp sau khi lưu"
            
            # Xóa bản ghi test
            cursor.execute("DELETE FROM orders WHERE id = ?", (inserted_id,))

def test_invalid_status_rejected_by_check_constraint():
    """DoD 3: Trạng thái không hợp lệ bị chặn bởi CHECK constraint"""
    with get_db() as conn:
        cursor = conn.cursor()
        with pytest.raises(sqlite3.IntegrityError):
            cursor.execute(
                """INSERT INTO orders (
                    order_code, total_amount, final_amount, status
                ) VALUES ('TEST-INVALID-ST', 50000, 50000, 'invalid_status_xyz')"""
            )

def test_historical_orders_read_via_api():
    """DoD 4: Toàn bộ đơn hàng cũ đọc bình thường qua API, không lỗi 500 hay validation error"""
    token = get_admin_token()
    headers = {"Authorization": f"Bearer {token}"}
    
    # 1. Lấy danh sách orders
    res = client.get("/api/v1/orders", headers=headers)
    assert res.status_code == 200
    orders = res.json()
    assert isinstance(orders, list)
    assert len(orders) > 0, "Phải có đơn hàng lịch sử trong database"
    
    # Kiểm tra cấu trúc bản ghi đơn hàng đầu tiên
    first_order = orders[0]
    assert "approved_by" in first_order
    assert "approved_at" in first_order
    assert "processed_by" in first_order
    assert "processed_at" in first_order
    assert "rejected_by" in first_order
    assert "rejected_at" in first_order
    assert "rejection_reason" in first_order
    assert first_order["status"] in ORDER_STATUSES

    # 2. Lấy chi tiết đơn hàng đầu tiên
    detail_res = client.get(f"/api/v1/orders/{first_order['id']}", headers=headers)
    assert detail_res.status_code == 200
    detail = detail_res.json()
    assert detail["id"] == first_order["id"]
    assert detail["order_code"] == first_order["order_code"]
    assert "approved_by" in detail

def test_pydantic_schema_validation():
    """DoD 5: Pydantic schemas validate thành công các trạng thái và trường workflow mới"""
    # Test OrderResponse với trường workflow đầy đủ
    mock_data = {
        "id": 9999,
        "order_code": "ORD-TEST-9999",
        "customer_id": 1,
        "customer_name": "Test Customer",
        "customer_phone": "0901234567",
        "user_id": 2,
        "user_name": "Test Staff",
        "total_amount": 250000.0,
        "discount_amount": 0.0,
        "final_amount": 250000.0,
        "payment_method": "cash",
        "payment_status": "completed",
        "status": "admin_approved",
        "note": "Đơn test schema",
        "approved_by": 1,
        "approved_at": "2026-09-23 10:00:00",
        "processed_by": 2,
        "processed_at": "2026-09-23 10:15:00",
        "rejected_by": None,
        "rejected_at": None,
        "rejection_reason": None,
        "created_at": "2026-09-23 09:30:00",
        "items": []
    }
    validated = OrderResponse(**mock_data)
    assert validated.status == "admin_approved"
    assert validated.approved_by == 1
    assert validated.processed_by == 2
    assert validated.rejected_by is None

def test_idempotent_migration():
    """DoD 6: Chạy init_db() nhiều lần không gây lỗi và bảo toàn toàn bộ dữ liệu"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) as cnt FROM orders")
        count_before = cursor.fetchone()["cnt"]

    # Chạy lại init_db 2 lần liên tiếp
    init_db()
    init_db()

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) as cnt FROM orders")
        count_after = cursor.fetchone()["cnt"]
        assert count_after == count_before, "Số lượng đơn hàng bị thay đổi sau khi chạy lại init_db!"
