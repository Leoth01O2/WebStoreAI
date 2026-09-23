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


def get_available_product_id_and_stock(min_stock=10):
    with get_db() as conn:
        c = conn.cursor()
        c.execute("SELECT id, stock_quantity FROM products WHERE status = 'active' AND stock_quantity >= ? LIMIT 1", (min_stock,))
        prod = c.fetchone()
        assert prod is not None, "Need at least one active product with sufficient stock"
        return prod["id"], prod["stock_quantity"]


def test_1_admin_calling_force_action_returns_403(admin_headers, customer_headers):
    """
    DoD 1: Admin bị cấm tuyệt đối không được gọi force-action (403 Forbidden).
    """
    prod_id, _ = get_available_product_id_and_stock()
    res_create = client.post("/api/v1/orders", json={
        "items": [{"product_id": prod_id, "quantity": 1}]
    }, headers=customer_headers)
    assert res_create.status_code == 200
    order_id = res_create.json()["id"]

    res = client.post(f"/api/v1/orders/{order_id}/force-action", json={
        "action": "force_cancel",
        "reason": "Admin cố can thiệp ngoại lệ trái phép"
    }, headers=admin_headers)
    assert res.status_code == 403


def test_2_staff_calling_force_action_returns_403(staff_headers, customer_headers):
    """
    DoD 2: Staff bị cấm tuyệt đối không được gọi force-action (403 Forbidden).
    """
    prod_id, _ = get_available_product_id_and_stock()
    res_create = client.post("/api/v1/orders", json={
        "items": [{"product_id": prod_id, "quantity": 1}]
    }, headers=customer_headers)
    order_id = res_create.json()["id"]

    res = client.post(f"/api/v1/orders/{order_id}/force-action", json={
        "action": "force_cancel",
        "reason": "Staff cố can thiệp ngoại lệ"
    }, headers=staff_headers)
    assert res.status_code == 403


def test_3_customer_calling_force_action_returns_403(customer_headers):
    """
    DoD 3: Customer bị cấm tuyệt đối không được gọi force-action (403 Forbidden).
    """
    prod_id, _ = get_available_product_id_and_stock()
    res_create = client.post("/api/v1/orders", json={
        "items": [{"product_id": prod_id, "quantity": 1}]
    }, headers=customer_headers)
    order_id = res_create.json()["id"]

    res = client.post(f"/api/v1/orders/{order_id}/force-action", json={
        "action": "force_cancel",
        "reason": "Customer cố can thiệp ngoại lệ"
    }, headers=customer_headers)
    assert res.status_code == 403


def test_4_superadmin_force_cancel_valid_order_succeeds(superadmin_headers, customer_headers):
    """
    DoD 4: SuperAdmin thực hiện force_cancel thành công trên đơn hợp lệ.
    """
    prod_id, stock_before = get_available_product_id_and_stock()
    res_create = client.post("/api/v1/orders", json={
        "items": [{"product_id": prod_id, "quantity": 2}]
    }, headers=customer_headers)
    order = res_create.json()
    order_id = order["id"]

    # SuperAdmin force cancel
    res = client.post(f"/api/v1/orders/{order_id}/force-action", json={
        "action": "force_cancel",
        "reason": "Khách hàng khiếu nại tranh chấp thanh toán ngân hàng"
    }, headers=superadmin_headers)
    assert res.status_code == 200
    cancelled_order = res.json()
    assert cancelled_order["status"] == "cancelled"
    assert "FORCE_CANCEL by SuperAdmin" in cancelled_order["note"]

    # Kiểm tra tồn kho được hoàn trả
    with get_db() as conn:
        c = conn.cursor()
        c.execute("SELECT stock_quantity FROM products WHERE id = ?", (prod_id,))
        assert c.fetchone()["stock_quantity"] == stock_before


def test_5_force_cancel_idempotency_no_double_refund(superadmin_headers, customer_headers):
    """
    DoD 5: Gọi force_cancel lại trên đơn đã cancelled bị chặn 400, không hoàn kho lần 2.
    """
    prod_id, stock_before = get_available_product_id_and_stock()
    res_create = client.post("/api/v1/orders", json={
        "items": [{"product_id": prod_id, "quantity": 1}]
    }, headers=customer_headers)
    order_id = res_create.json()["id"]

    # Lần 1: hủy thành công
    res1 = client.post(f"/api/v1/orders/{order_id}/force-action", json={
        "action": "force_cancel",
        "reason": "Hủy lần 1"
    }, headers=superadmin_headers)
    assert res1.status_code == 200

    # Lần 2: gọi lại force_cancel -> 400
    res2 = client.post(f"/api/v1/orders/{order_id}/force-action", json={
        "action": "force_cancel",
        "reason": "Hủy lần 2"
    }, headers=superadmin_headers)
    assert res2.status_code == 400
    assert "đã ở trạng thái 'cancelled'" in res2.json()["detail"]

    # Tồn kho không bị nhân đôi
    with get_db() as conn:
        c = conn.cursor()
        c.execute("SELECT stock_quantity FROM products WHERE id = ?", (prod_id,))
        assert c.fetchone()["stock_quantity"] == stock_before


def test_6_superadmin_reopen_rejected_order_succeeds(superadmin_headers, admin_headers, customer_headers):
    """
    DoD 6: SuperAdmin reopen đơn bị Admin rejected thành công, chuyển về pending.
    """
    prod_id, _ = get_available_product_id_and_stock()
    res_create = client.post("/api/v1/orders", json={
        "items": [{"product_id": prod_id, "quantity": 2}]
    }, headers=customer_headers)
    order_id = res_create.json()["id"]

    # Admin từ chối đơn
    res_rej = client.post(f"/api/v1/orders/{order_id}/reject", json={
        "reason": "Admin từ chối do nhầm lẫn thông tin giao hàng"
    }, headers=admin_headers)
    assert res_rej.status_code == 200
    assert res_rej.json()["status"] == "rejected"

    # SuperAdmin xem xét lại và reopen
    res_reopen = client.post(f"/api/v1/orders/{order_id}/force-action", json={
        "action": "reopen_rejected",
        "reason": "Khách hàng đã đính chính địa chỉ giao hàng hợp lệ"
    }, headers=superadmin_headers)
    assert res_reopen.status_code == 200
    reopened_order = res_reopen.json()
    assert reopened_order["status"] == "pending"
    assert reopened_order["rejected_by"] is None
    assert reopened_order["rejection_reason"] is None
    assert "REOPEN by SuperAdmin" in reopened_order["note"]


def test_7_reopen_rejected_correctly_rededucts_inventory(superadmin_headers, admin_headers, customer_headers):
    """
    DoD 7: Reopen đơn kiểm tra và trừ giữ chỗ tồn kho chính xác trong inventory_logs.
    """
    prod_id, stock_initial = get_available_product_id_and_stock()
    qty = 3

    # Tạo đơn -> tồn kho = stock_initial - qty
    res_create = client.post("/api/v1/orders", json={
        "items": [{"product_id": prod_id, "quantity": qty}]
    }, headers=customer_headers)
    order_id = res_create.json()["id"]
    order_code = res_create.json()["order_code"]

    # Admin reject -> tồn kho được hoàn trả về stock_initial
    client.post(f"/api/v1/orders/{order_id}/reject", headers=admin_headers)
    with get_db() as conn:
        c = conn.cursor()
        c.execute("SELECT stock_quantity FROM products WHERE id = ?", (prod_id,))
        assert c.fetchone()["stock_quantity"] == stock_initial

    # SuperAdmin reopen -> tồn kho phải được trừ giữ chỗ lại = stock_initial - qty
    res_reopen = client.post(f"/api/v1/orders/{order_id}/force-action", json={
        "action": "reopen_rejected",
        "reason": "Xác minh lại thông tin"
    }, headers=superadmin_headers)
    assert res_reopen.status_code == 200

    with get_db() as conn:
        c = conn.cursor()
        c.execute("SELECT stock_quantity FROM products WHERE id = ?", (prod_id,))
        assert c.fetchone()["stock_quantity"] == stock_initial - qty

        # Kiểm tra log kho có ghi log giữ chỗ
        c.execute(
            "SELECT change_type, reference_code FROM inventory_logs WHERE product_id = ? AND reference_code = ? ORDER BY id DESC LIMIT 1",
            (prod_id, order_code)
        )
        log_entry = c.fetchone()
        assert log_entry["change_type"] == "sale"


def test_8_reopen_rejected_blocked_when_stock_insufficient(superadmin_headers, admin_headers, customer_headers):
    """
    DoD 8: Reopen bị từ chối an toàn với HTTP 400 nếu tồn kho hiện tại không đủ.
    """
    prod_id, stock_now = get_available_product_id_and_stock()
    qty = 5

    res_create = client.post("/api/v1/orders", json={
        "items": [{"product_id": prod_id, "quantity": qty}]
    }, headers=customer_headers)
    order_id = res_create.json()["id"]

    # Admin reject -> tồn kho hoàn lại
    client.post(f"/api/v1/orders/{order_id}/reject", headers=admin_headers)

    # Giả lập tình huống hàng trong kho bị bán hết sạch (stock_quantity = 0)
    with get_db() as conn:
        c = conn.cursor()
        c.execute("UPDATE products SET stock_quantity = 0 WHERE id = ?", (prod_id,))

    # SuperAdmin cố reopen khi kho đã hết hàng -> phải bị chặn 400
    res_reopen = client.post(f"/api/v1/orders/{order_id}/force-action", json={
        "action": "reopen_rejected",
        "reason": "Cố reopen khi kho hết hàng"
    }, headers=superadmin_headers)
    assert res_reopen.status_code == 400
    assert "không đủ tồn kho" in res_reopen.json()["detail"]

    # Phục hồi tồn kho ban đầu cho test
    with get_db() as conn:
        c = conn.cursor()
        c.execute("UPDATE products SET stock_quantity = ? WHERE id = ?", (stock_now, prod_id))


def test_9_override_status_valid_pipeline_transition_succeeds(superadmin_headers, admin_headers, staff_headers, customer_headers):
    """
    DoD 9: SuperAdmin override_status chuyển đổi pipeline hợp lệ (ví dụ processing -> admin_approved).
    """
    prod_id, _ = get_available_product_id_and_stock()
    res_create = client.post("/api/v1/orders", json={
        "items": [{"product_id": prod_id, "quantity": 1}]
    }, headers=customer_headers)
    order_id = res_create.json()["id"]

    # Admin duyệt -> Staff nhận xử lý (status = processing)
    client.post(f"/api/v1/orders/{order_id}/approve", headers=admin_headers)
    client.post(f"/api/v1/orders/{order_id}/process", headers=staff_headers)

    # SuperAdmin can thiệp chuyển lại về admin_approved (nhân viên nhận nhầm đơn)
    res_override = client.post(f"/api/v1/orders/{order_id}/force-action", json={
        "action": "override_status",
        "target_status": "admin_approved",
        "reason": "Nhân viên bấm nhầm nhận xử lý đơn, trả về hàng đợi duyệt cho ca sau"
    }, headers=superadmin_headers)
    assert res_override.status_code == 200
    assert res_override.json()["status"] == "admin_approved"


def test_10_override_status_invalid_dangerous_transitions_rejected(superadmin_headers, customer_headers):
    """
    DoD 10: Chặn các transition override nguy hiểm (từ cancelled, target_status không hợp lệ, trùng status).
    """
    prod_id, _ = get_available_product_id_and_stock()
    res_create = client.post("/api/v1/orders", json={
        "items": [{"product_id": prod_id, "quantity": 1}]
    }, headers=customer_headers)
    order_id = res_create.json()["id"]

    # 1. Target status không hợp lệ
    res_invalid_target = client.post(f"/api/v1/orders/{order_id}/force-action", json={
        "action": "override_status",
        "target_status": "super_vip_done",
        "reason": "Test status bậy"
    }, headers=superadmin_headers)
    assert res_invalid_target.status_code == 400

    # 2. Target status trùng current status (pending -> pending)
    res_same_target = client.post(f"/api/v1/orders/{order_id}/force-action", json={
        "action": "override_status",
        "target_status": "pending",
        "reason": "Test trùng status"
    }, headers=superadmin_headers)
    assert res_same_target.status_code == 400

    # 3. Đơn đã cancelled cố override sang status khác -> 400
    client.post(f"/api/v1/orders/{order_id}/force-action", json={
        "action": "force_cancel",
        "reason": "Hủy đơn"
    }, headers=superadmin_headers)

    res_override_from_cancelled = client.post(f"/api/v1/orders/{order_id}/force-action", json={
        "action": "override_status",
        "target_status": "completed",
        "reason": "Cố override từ cancelled"
    }, headers=superadmin_headers)
    assert res_override_from_cancelled.status_code == 400
    assert "Không thể override đơn hàng đã ở trạng thái 'cancelled'" in res_override_from_cancelled.json()["detail"]


def test_11_force_actions_generate_structured_audit_trail(superadmin_headers, customer_headers):
    """
    DoD 11: Mọi thao tác SuperAdmin force-action đều lưu vết kiểm toán vào bảng order_audit_logs.
    """
    prod_id, _ = get_available_product_id_and_stock()
    res_create = client.post("/api/v1/orders", json={
        "items": [{"product_id": prod_id, "quantity": 1}]
    }, headers=customer_headers)
    order_id = res_create.json()["id"]

    audit_reason = "Can thiệp kiểm toán hệ thống mẫu"
    res_action = client.post(f"/api/v1/orders/{order_id}/force-action", json={
        "action": "force_cancel",
        "reason": audit_reason
    }, headers=superadmin_headers)
    assert res_action.status_code == 200

    with get_db() as conn:
        c = conn.cursor()
        c.execute("SELECT * FROM order_audit_logs WHERE order_id = ? ORDER BY id DESC LIMIT 1", (order_id,))
        log = c.fetchone()
        assert log is not None
        assert log["action"] == "force_cancel"
        assert log["previous_status"] == "pending"
        assert log["resulting_status"] == "cancelled"
        assert log["reason"] == audit_reason
        assert log["performed_by"] is not None


def test_12_admin_calling_reports_summary_returns_403(admin_headers):
    """
    DoD 12: Admin bị chặn 403 Forbidden tuyệt đối khi gọi báo cáo doanh thu / tài chính.
    """
    res = client.get("/api/v1/reports/summary", headers=admin_headers)
    assert res.status_code == 403


def test_13_superadmin_calling_reports_summary_returns_200(superadmin_headers):
    """
    DoD 13: SuperAdmin độc quyền truy cập báo cáo doanh thu tài chính thành công (HTTP 200).
    """
    res = client.get("/api/v1/reports/summary", headers=superadmin_headers)
    assert res.status_code == 200
    data = res.json()
    assert "total_revenue" in data
    assert "completed_orders" in data
