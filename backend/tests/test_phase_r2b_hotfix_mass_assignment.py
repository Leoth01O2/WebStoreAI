import os
import sqlite3
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.core.config import settings
from app.core.database import get_db


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


def get_token(client: TestClient, username: str, password: str) -> str:
    res = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert res.status_code == 200, f"Login failed for {username}: {res.text}"
    return res.json()["access_token"]


def get_active_product_id():
    with get_db() as conn:
        cursor = conn.cursor()
        p = cursor.execute("SELECT id FROM products WHERE status = 'active' AND stock_quantity > 5 LIMIT 1").fetchone()
        assert p is not None, "Không tìm thấy sản phẩm active"
        return p["id"]


# ===========================================================================
# TARGETED SECURITY TESTS: MASS ASSIGNMENT & LEGACY FLAG GUARDS
# ===========================================================================

def test_01_customer_creates_order_without_internal_fields(client: TestClient):
    """1. Customer tạo đơn bình thường không truyền assigned_to / is_legacy_unverified -> Thành công"""
    token = get_token(client, "customer", "Customer@123")
    prod_id = get_active_product_id()

    payload = {
        "shipping_name": "Nguyễn Văn Nhận",
        "shipping_phone": "0987654321",
        "shipping_address": "123 Đường Test, Hà Nội",
        "payment_method": "transfer",
        "items": [{"product_id": prod_id, "quantity": 1}]
    }

    res = client.post("/api/v1/orders", json=payload, headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200, f"Tạo đơn thất bại: {res.text}"
    data = res.json()

    assert data["assigned_to"] is None, "assigned_to phải là NULL cho đơn mới"
    assert data["is_legacy_unverified"] == 0, "is_legacy_unverified phải là 0 cho đơn mới"
    assert data["shipping_name"] == "Nguyễn Văn Nhận"
    assert data["shipping_phone"] == "0987654321"
    assert data["shipping_address"] == "123 Đường Test, Hà Nội"

    # Kiểm tra trực tiếp trong SQLite
    with get_db() as conn:
        cursor = conn.cursor()
        row = cursor.execute(
            "SELECT assigned_to, is_legacy_unverified, shipping_name FROM orders WHERE id = ?",
            (data["id"],)
        ).fetchone()
        assert row["assigned_to"] is None
        assert row["is_legacy_unverified"] == 0
        assert row["shipping_name"] == "Nguyễn Văn Nhận"


def test_02_customer_sends_arbitrary_assigned_to_not_applied(client: TestClient):
    """2. Customer cố tình gửi assigned_to tùy ý -> Không được áp dụng, luôn lưu NULL"""
    token = get_token(client, "customer", "Customer@123")
    prod_id = get_active_product_id()

    # Cố tình gửi assigned_to = 99 (ID nhân viên bất kỳ)
    payload = {
        "assigned_to": 99,
        "shipping_name": "Khách Test",
        "payment_method": "cash",
        "items": [{"product_id": prod_id, "quantity": 1}]
    }

    res = client.post("/api/v1/orders", json=payload, headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200, f"Request thất bại: {res.text}"
    data = res.json()

    # Không được áp dụng giá trị 99
    assert data["assigned_to"] is None, f"LỖ HỔNG MASS ASSIGNMENT: assigned_to bị gán thành {data['assigned_to']}"

    # Kiểm tra trong SQLite
    with get_db() as conn:
        cursor = conn.cursor()
        row = cursor.execute("SELECT assigned_to FROM orders WHERE id = ?", (data["id"],)).fetchone()
        assert row["assigned_to"] is None, f"Trong DB assigned_to bị gán giá trị: {row['assigned_to']}"


def test_03_customer_sends_legacy_unverified_flag_not_applied(client: TestClient):
    """3. Customer gửi is_legacy_unverified = 1 -> Không được áp dụng, luôn lưu 0"""
    token = get_token(client, "customer", "Customer@123")
    prod_id = get_active_product_id()

    payload = {
        "is_legacy_unverified": 1,
        "shipping_name": "Khách Test 2",
        "payment_method": "cash",
        "items": [{"product_id": prod_id, "quantity": 1}]
    }

    res = client.post("/api/v1/orders", json=payload, headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200, f"Request thất bại: {res.text}"
    data = res.json()

    assert data["is_legacy_unverified"] == 0, "LỖ HỔNG: is_legacy_unverified bị client đặt thành 1"

    with get_db() as conn:
        cursor = conn.cursor()
        row = cursor.execute("SELECT is_legacy_unverified FROM orders WHERE id = ?", (data["id"],)).fetchone()
        assert row["is_legacy_unverified"] == 0


def test_04_staff_pos_order_cannot_set_legacy_flag_or_assigned_to(client: TestClient):
    """4. Staff tạo POS order gửi assigned_to và is_legacy_unverified -> Không được áp dụng"""
    token = get_token(client, "staff", "Staff@123")
    prod_id = get_active_product_id()

    payload = {
        "assigned_to": 1,  # SuperAdmin ID
        "is_legacy_unverified": 1,
        "discount_amount": 0,
        "payment_method": "cash",
        "items": [{"product_id": prod_id, "quantity": 1}]
    }

    res = client.post("/api/v1/orders", json=payload, headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200, f"Tạo đơn POS thất bại: {res.text}"
    data = res.json()

    assert data["assigned_to"] is None, "Staff tạo POS đơn mới phải có assigned_to = NULL"
    assert data["is_legacy_unverified"] == 0, "Staff tạo POS đơn mới phải có is_legacy_unverified = 0"

    with get_db() as conn:
        cursor = conn.cursor()
        row = cursor.execute(
            "SELECT assigned_to, is_legacy_unverified FROM orders WHERE id = ?",
            (data["id"],)
        ).fetchone()
        assert row["assigned_to"] is None
        assert row["is_legacy_unverified"] == 0


def test_05_legacy_orders_retain_unverified_flag():
    """5. Đơn hàng lịch sử được tạo từ trước (sau khi chạy migration) giữ nguyên cờ is_legacy_unverified = 1"""
    # Tạo một đơn hàng lịch sử giả lập và đánh dấu legacy = 1
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(orders)")
        cols = {r["name"] for r in cursor.fetchall()}
        legacy_pay_status = "unverified_legacy" if "payment_status_raw" in cols else "completed"
        cursor.execute(
            f"""INSERT INTO orders (order_code, total_amount, final_amount, payment_method, payment_status, status, is_legacy_unverified)
               VALUES ('HD-LEGACY-TEST-01', 100000, 100000, 'cash', '{legacy_pay_status}', 'completed', 1)"""
        )
        conn.commit()
        leg_id = cursor.lastrowid

        # Kiểm tra đơn lịch sử vẫn có is_legacy_unverified = 1
        row = cursor.execute("SELECT is_legacy_unverified FROM orders WHERE id = ?", (leg_id,)).fetchone()
        assert row["is_legacy_unverified"] == 1, "Đơn lịch sử phải giữ nguyên is_legacy_unverified = 1"


def test_06_old_orders_and_order_items_unaltered():
    """6. Đơn và order_items cũ không bị thay đổi dữ liệu hoặc mất mát"""
    with get_db() as conn:
        cursor = conn.cursor()
        order_cnt = cursor.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
        item_cnt = cursor.execute("SELECT COUNT(*) FROM order_items").fetchone()[0]
        assert order_cnt >= 2, "Bảng orders phải có ít nhất các đơn mẫu"
        assert item_cnt >= 2, "Bảng order_items phải có các item mẫu"
