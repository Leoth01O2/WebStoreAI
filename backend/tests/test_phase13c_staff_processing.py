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
def superadmin_headers():
    return {"Authorization": f"Bearer {get_token('superadmin', 'SuperAdmin@123')}"}

@pytest.fixture
def admin_headers():
    return {"Authorization": f"Bearer {get_token('admin', 'Admin@123')}"}

@pytest.fixture
def staff_headers():
    return {"Authorization": f"Bearer {get_token('staff', 'Staff@123')}"}

@pytest.fixture
def customer_headers():
    return {"Authorization": f"Bearer {get_token('customer', 'Customer@123')}"}


def test_full_workflow_pending_to_processing_to_completed_revenue_increase(
    customer_headers, admin_headers, staff_headers, superadmin_headers
):
    """
    DoD 1: Chu trình đầy đủ:
    1. Customer tạo đơn -> PENDING (doanh thu chưa tăng).
    2. Staff thử process đơn PENDING -> 400 Bad Request ("Đơn hàng chưa được Admin duyệt").
    3. Staff thử complete đơn PENDING -> 400 Bad Request.
    4. Admin duyệt đơn -> ADMIN_APPROVED (doanh thu vẫn chưa tăng).
    5. Staff nhận xử lý đơn -> PROCESSING (doanh thu vẫn chưa tăng).
    6. Staff hoàn tất đơn -> COMPLETED.
    7. Doanh thu trong báo cáo ReportService tăng đúng bằng final_amount của đơn hàng.
    """
    # 0. Lấy doanh thu hiện tại từ SuperAdmin (được phép xem reports)
    res_rep_before = client.get("/api/v1/reports/summary", headers=superadmin_headers)
    assert res_rep_before.status_code == 200
    rev_before = res_rep_before.json()["total_revenue"]
    completed_orders_before = res_rep_before.json()["completed_orders"]

    # 1. Customer tạo đơn hàng
    with get_db() as conn:
        c = conn.cursor()
        c.execute("SELECT id, selling_price FROM products WHERE status = 'active' AND stock_quantity >= 5 LIMIT 1")
        prod = c.fetchone()
        prod_id = prod["id"]
        prod_price = float(prod["selling_price"])

    buy_qty = 2
    expected_amount = prod_price * buy_qty

    res_create = client.post("/api/v1/orders", json={
        "payment_method": "transfer",
        "items": [{"product_id": prod_id, "quantity": buy_qty}]
    }, headers=customer_headers)
    assert res_create.status_code == 200
    created_order = res_create.json()
    order_id = created_order["id"]
    assert created_order["status"] == "pending"

    # Kiểm tra doanh thu CHƯA TĂNG khi đơn PENDING
    res_rep_pending = client.get("/api/v1/reports/summary", headers=superadmin_headers)
    assert res_rep_pending.json()["total_revenue"] == rev_before

    # 2. Staff thử process đơn PENDING -> 400
    res_proc_pending = client.post(f"/api/v1/orders/{order_id}/process", headers=staff_headers)
    assert res_proc_pending.status_code == 400
    assert "Đơn hàng chưa được Admin duyệt" in res_proc_pending.json()["detail"]

    # 3. Staff thử complete đơn PENDING -> 400
    res_comp_pending = client.post(f"/api/v1/orders/{order_id}/complete", headers=staff_headers)
    assert res_comp_pending.status_code == 400

    # 4. Admin duyệt đơn -> ADMIN_APPROVED
    res_approve = client.post(f"/api/v1/orders/{order_id}/approve", headers=superadmin_headers)
    assert res_approve.status_code == 200
    assert res_approve.json()["status"] in ("confirmed", "admin_approved")

    # Kiểm tra doanh thu vẫn CHƯA TĂNG khi đơn ADMIN_APPROVED
    res_rep_approved = client.get("/api/v1/reports/summary", headers=superadmin_headers)
    assert res_rep_approved.json()["total_revenue"] == rev_before

    # 5. Staff nhận xử lý đơn -> PROCESSING
    res_proc = client.post(f"/api/v1/orders/{order_id}/process", headers=staff_headers)
    assert res_proc.status_code == 200
    proc_order = res_proc.json()
    assert proc_order["status"] == "processing"
    assert proc_order["processed_by"] is not None
    assert proc_order["processed_at"] is not None

    # Kiểm tra doanh thu vẫn CHƯA TĂNG khi đơn PROCESSING
    res_rep_proc = client.get("/api/v1/reports/summary", headers=superadmin_headers)
    assert res_rep_proc.json()["total_revenue"] == rev_before

    # 6. Staff hoàn tất đơn -> COMPLETED
    res_comp = client.post(f"/api/v1/orders/{order_id}/complete", headers=staff_headers)
    assert res_comp.status_code == 200
    comp_order = res_comp.json()
    assert comp_order["status"] == "completed"

    # 7. Doanh thu tăng đúng giá trị đơn hàng
    res_rep_after = client.get("/api/v1/reports/summary", headers=superadmin_headers)
    assert res_rep_after.status_code == 200
    rev_after = res_rep_after.json()["total_revenue"]
    completed_orders_after = res_rep_after.json()["completed_orders"]

    assert rev_after == pytest.approx(rev_before + expected_amount, 0.01)
    assert completed_orders_after == completed_orders_before + 1


def test_staff_filter_admin_approved_orders(customer_headers, admin_headers, staff_headers, superadmin_headers):
    """
    DoD 2: Bộ lọc status=admin_approved giúp Staff chỉ lấy danh sách các đơn đã được Admin duyệt.
    """
    # Tạo 1 đơn mới và duyệt nó
    with get_db() as conn:
        c = conn.cursor()
        c.execute("SELECT id FROM products WHERE status = 'active' AND stock_quantity >= 2 LIMIT 1")
        prod_id = c.fetchone()["id"]

    res_create = client.post("/api/v1/orders", json={
        "items": [{"product_id": prod_id, "quantity": 1}]
    }, headers=customer_headers)
    order_id = res_create.json()["id"]

    client.post(f"/api/v1/orders/{order_id}/approve", headers=superadmin_headers)

    # Staff lọc các đơn admin_approved
    res_filter = client.get("/api/v1/orders?status=admin_approved", headers=staff_headers)
    assert res_filter.status_code == 200
    orders = res_filter.json()
    assert len(orders) > 0
    for o in orders:
        assert o["status"] in ("confirmed", "admin_approved")
    assert any(o["id"] == order_id for o in orders)


def test_direct_complete_from_admin_approved(customer_headers, admin_headers, staff_headers, superadmin_headers):
    """
    DoD 3: Cho phép hoàn tất trực tiếp từ ADMIN_APPROVED -> COMPLETED
    (phù hợp trường hợp xử lý nhanh không qua giai đoạn đóng gói).
    """
    with get_db() as conn:
        c = conn.cursor()
        c.execute("SELECT id FROM products WHERE status = 'active' AND stock_quantity >= 2 LIMIT 1")
        prod_id = c.fetchone()["id"]

    res_create = client.post("/api/v1/orders", json={
        "items": [{"product_id": prod_id, "quantity": 1}]
    }, headers=customer_headers)
    order_id = res_create.json()["id"]

    client.post(f"/api/v1/orders/{order_id}/approve", headers=superadmin_headers)

    # Complete trực tiếp từ admin_approved
    res_comp = client.post(f"/api/v1/orders/{order_id}/complete", headers=staff_headers)
    assert res_comp.status_code == 200
    assert res_comp.json()["status"] == "completed"
    assert res_comp.json()["processed_by"] is not None


def test_invalid_status_transitions_rejected(customer_headers, admin_headers, staff_headers, superadmin_headers):
    """
    DoD 4: Mọi hành động sai thứ tự trạng thái đều bị backend từ chối:
    - Thử complete đơn đã REJECTED -> 400 Bad Request.
    - Thử process đơn đã REJECTED -> 400 Bad Request.
    - Thử complete đơn đã COMPLETED -> 400 Bad Request.
    - Thử process đơn đã COMPLETED -> 400 Bad Request.
    """
    with get_db() as conn:
        c = conn.cursor()
        c.execute("SELECT id FROM products WHERE status = 'active' AND stock_quantity >= 2 LIMIT 1")
        prod_id = c.fetchone()["id"]

    # 1. Tạo và từ chối 1 đơn
    res_create = client.post("/api/v1/orders", json={
        "items": [{"product_id": prod_id, "quantity": 1}]
    }, headers=customer_headers)
    rejected_order_id = res_create.json()["id"]

    client.post(f"/api/v1/orders/{rejected_order_id}/reject", json={"reason": "Test"}, headers=superadmin_headers)

    # Thử complete đơn REJECTED -> 400
    res_comp_rej = client.post(f"/api/v1/orders/{rejected_order_id}/complete", headers=staff_headers)
    assert res_comp_rej.status_code == 400
    assert "rejected" in res_comp_rej.json()["detail"] or "cancelled" in res_comp_rej.json()["detail"] or "Chỉ có thể hoàn tất" in res_comp_rej.json()["detail"]

    # Thử process đơn REJECTED -> 400
    res_proc_rej = client.post(f"/api/v1/orders/{rejected_order_id}/process", headers=staff_headers)
    assert res_proc_rej.status_code == 400

    # 2. Tạo, duyệt, và complete 1 đơn
    res_create2 = client.post("/api/v1/orders", json={
        "items": [{"product_id": prod_id, "quantity": 1}]
    }, headers=customer_headers)
    completed_order_id = res_create2.json()["id"]
    client.post(f"/api/v1/orders/{completed_order_id}/approve", headers=superadmin_headers)
    client.post(f"/api/v1/orders/{completed_order_id}/complete", headers=staff_headers)

    # Thử complete lại đơn đã COMPLETED -> 400
    res_recomp = client.post(f"/api/v1/orders/{completed_order_id}/complete", headers=staff_headers)
    assert res_recomp.status_code == 400

    # Thử process lại đơn đã COMPLETED -> 400
    res_reproc = client.post(f"/api/v1/orders/{completed_order_id}/process", headers=staff_headers)
    assert res_reproc.status_code == 400


def test_customer_cannot_call_complete(customer_headers):
    """
    DoD 5: Customer bị chặn 403 Forbidden khi cố tình gọi endpoint /complete.
    """
    res = client.post("/api/v1/orders/1/complete", headers=customer_headers)
    assert res.status_code == 403
