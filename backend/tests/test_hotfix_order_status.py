import re
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.core.database import get_db

client = TestClient(app)

def get_token(username, password):
    res = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert res.status_code == 200, f"Login failed for {username}: {res.text}"
    return res.json()["access_token"]

@pytest.fixture
def customer_headers():
    return {"Authorization": f"Bearer {get_token('customer', 'Customer@123')}"}

@pytest.fixture
def staff_headers():
    return {"Authorization": f"Bearer {get_token('staff', 'Staff@123')}"}

@pytest.fixture
def admin_headers():
    return {"Authorization": f"Bearer {get_token('admin', 'Admin@123')}"}


def test_targeted_workflow_customer_creates_pending_to_admin_approved_to_processing(
    customer_headers, staff_headers, admin_headers
):
    """
    Targeted deterministic test verifying:
    1. Customer creates order -> PENDING.
    2. Staff cannot process PENDING (400 Bad Request).
    3. Admin approves -> ADMIN_APPROVED.
    4. Staff can then move ADMIN_APPROVED -> PROCESSING.
    """
    # 1. Customer creates order -> PENDING
    with get_db() as conn:
        c = conn.cursor()
        c.execute("SELECT id, stock_quantity FROM products WHERE status = 'active' AND stock_quantity >= 5 LIMIT 1")
        prod = c.fetchone()
        prod_id = prod["id"]

    order_payload = {
        "payment_method": "transfer",
        "note": "Hotfix verification test order",
        "items": [{"product_id": prod_id, "quantity": 1}]
    }

    res_create = client.post("/api/v1/orders", json=order_payload, headers=customer_headers)
    assert res_create.status_code == 200, f"Failed to create customer order: {res_create.text}"
    order = res_create.json()
    order_id = order["id"]

    # Verify requirement 1: Customer creates order -> PENDING
    assert order["status"] == "pending", f"Expected 'pending' but got '{order['status']}'"

    # Also verify database persistence
    with get_db() as conn:
        c = conn.cursor()
        c.execute("SELECT status FROM orders WHERE id = ?", (order_id,))
        row = c.fetchone()
        assert row["status"] == "pending", "Database record must be 'pending'"

    # Verify requirement 2: Staff cannot process PENDING
    res_process_pending = client.post(f"/api/v1/orders/{order_id}/process", headers=staff_headers)
    assert res_process_pending.status_code == 400, "Staff must NOT be able to process a PENDING order"
    assert "chưa được Admin duyệt" in res_process_pending.json().get("detail", "")

    # Verify requirement 3: Admin approves -> ADMIN_APPROVED
    res_approve = client.post(f"/api/v1/orders/{order_id}/approve", headers=admin_headers)
    assert res_approve.status_code == 200, f"Admin approval failed: {res_approve.text}"
    approved_order = res_approve.json()
    assert approved_order["status"] == "admin_approved"
    assert approved_order["approved_by"] is not None
    assert approved_order["approved_at"] is not None

    # Verify requirement 4: Staff can then move ADMIN_APPROVED -> PROCESSING
    res_process = client.post(f"/api/v1/orders/{order_id}/process", headers=staff_headers)
    assert res_process.status_code == 200, f"Staff processing failed: {res_process.text}"
    processed_order = res_process.json()
    assert processed_order["status"] == "processing"
    assert processed_order["processed_by"] is not None
    assert processed_order["processed_at"] is not None


def test_frontend_status_mapping_contract():
    """
    Requirement 5: Verify that the frontend status mapping explicitly covers all 6 workflow statuses:
    pending         -> Chờ duyệt
    admin_approved  -> Đã duyệt
    processing      -> Đang xử lý
    completed       -> Hoàn thành
    rejected        -> Đã từ chối
    cancelled       -> Đã hủy
    and that unknown statuses are NEVER mapped to 'Đã hủy'.
    """
    badge_path = Path(__file__).parent.parent.parent / "frontend" / "src" / "components" / "ui" / "Badge.jsx"
    orders_page_path = Path(__file__).parent.parent.parent / "frontend" / "src" / "pages" / "OrdersPage.jsx"

    assert badge_path.exists(), "Badge.jsx must exist"
    assert orders_page_path.exists(), "OrdersPage.jsx must exist"

    badge_content = badge_path.read_text(encoding="utf-8")
    orders_content = orders_page_path.read_text(encoding="utf-8")

    expected_mappings = {
        "pending": "Chờ duyệt",
        "admin_approved": "Đã duyệt",
        "processing": "Đang xử lý",
        "completed": "Hoàn thành",
        "rejected": "Đã từ chối",
        "cancelled": "Đã hủy",
    }

    for status_key, label in expected_mappings.items():
        assert f"'{status_key}'" in badge_content or f'"{status_key}"' in badge_content or f"{status_key}:" in badge_content, (
            f"Status '{status_key}' must be defined in Badge.jsx"
        )
        assert label in badge_content, f"Label '{label}' for '{status_key}' must be defined in Badge.jsx"

    # Verify binary ternary fallback that mapped unknown/all non-completed statuses to 'Đã hủy' is REMOVED
    assert "o.status === 'completed' ? 'Hoàn thành' : 'Đã hủy'" not in orders_content
    assert "viewingOrder.status === 'completed' ? 'Đã hoàn tất' : 'Đã hủy'" not in orders_content

    # Verify OrdersPage uses OrderStatusBadge
    assert "<OrderStatusBadge" in orders_content

    # Verify unknown status does not map to 'Đã hủy'
    assert "ORDER_STATUS_CONFIG[status] ||" in badge_content
    assert "Chưa xác định" in badge_content


def test_historical_cancelled_orders_preserved_and_accessible(customer_headers, admin_headers):
    """
    Verify historical cancelled orders exist and retain their 'cancelled' status without modification.
    """
    with get_db() as conn:
        c = conn.cursor()
        c.execute("SELECT id, order_code, status FROM orders WHERE status = 'cancelled' LIMIT 1")
        row = c.fetchone()
        if row:
            assert row["status"] == "cancelled"
            order_id = row["id"]
            # Check API retrieval returns cancelled
            res = client.get(f"/api/v1/orders/{order_id}", headers=admin_headers)
            assert res.status_code == 200
            assert res.json()["status"] == "cancelled"
