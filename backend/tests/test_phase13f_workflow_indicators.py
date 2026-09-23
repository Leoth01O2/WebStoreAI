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


def test_1_admin_workflow_counts_returns_pending_approved_processing(admin_headers):
    """
    DoD 1: Admin gọi GET /orders/workflow-counts nhận cấu trúc { pending_count, approved_count, processing_count }
    """
    res = client.get("/api/v1/orders/workflow-counts", headers=admin_headers)
    assert res.status_code == 200, res.text
    data = res.json()
    assert "pending_count" in data
    assert "approved_count" in data
    assert "processing_count" in data
    assert isinstance(data["pending_count"], int)
    assert isinstance(data["approved_count"], int)
    assert isinstance(data["processing_count"], int)


def test_2_superadmin_workflow_counts_matches_admin_system_scope(superadmin_headers):
    """
    DoD 2: SuperAdmin gọi GET /orders/workflow-counts nhận toàn bộ các chỉ số của hệ thống.
    """
    res = client.get("/api/v1/orders/workflow-counts", headers=superadmin_headers)
    assert res.status_code == 200, res.text
    data = res.json()
    assert "pending_count" in data
    assert "approved_count" in data
    assert "processing_count" in data


def test_3_staff_workflow_counts_returns_approved_and_processing_only(staff_headers):
    """
    DoD 3: Staff gọi GET /orders/workflow-counts chỉ nhận approved_count và processing_count.
    """
    res = client.get("/api/v1/orders/workflow-counts", headers=staff_headers)
    assert res.status_code == 200, res.text
    data = res.json()
    assert "approved_count" in data
    assert "processing_count" in data
    # Staff không quản lý pending approvals
    assert "pending_count" not in data


def test_4_customer_workflow_counts_returns_my_counts_only(customer_headers):
    """
    DoD 4: Customer gọi GET /orders/workflow-counts chỉ nhận my_pending_count và my_processing_count.
    """
    res = client.get("/api/v1/orders/workflow-counts", headers=customer_headers)
    assert res.status_code == 200, res.text
    data = res.json()
    assert "my_pending_count" in data
    assert "my_processing_count" in data
    assert "pending_count" not in data
    assert "approved_count" not in data


def test_5_customer_workflow_counts_anti_idor_no_leak_of_other_customers(customer_headers, admin_headers):
    """
    DoD 5: Customer counts bảo vệ Anti-IDOR tuyệt đối, không đếm đơn của Customer khác.
    """
    # Lấy count ban đầu của customer
    res_before = client.get("/api/v1/orders/workflow-counts", headers=customer_headers)
    before_pending = res_before.json()["my_pending_count"]

    # Đăng nhập một customer khác hoặc tạo đơn thuộc user khác
    token_admin = get_token("admin", "Admin@123")
    prod_id, _ = get_available_product_id_and_stock()

    # Tạo đơn của customer hiện tại
    res_c_order = client.post("/api/v1/orders", json={
        "items": [{"product_id": prod_id, "quantity": 1}]
    }, headers=customer_headers)
    assert res_c_order.status_code == 200

    # Sau khi tạo, count của customer tăng 1
    res_after = client.get("/api/v1/orders/workflow-counts", headers=customer_headers)
    after_pending = res_after.json()["my_pending_count"]
    assert after_pending == before_pending + 1

    # Tạo đơn bởi POS (Admin) cho khách khác
    client.post("/api/v1/orders", json={
        "items": [{"product_id": prod_id, "quantity": 1}],
        "status": "pending"
    }, headers=admin_headers)

    # Customer xem lại counts: Không được tính thêm đơn của Admin/khách khác
    res_recheck = client.get("/api/v1/orders/workflow-counts", headers=customer_headers)
    assert res_recheck.json()["my_pending_count"] == after_pending


def test_6_unauthenticated_call_to_workflow_counts_returns_401():
    """
    DoD 6: Gọi /orders/workflow-counts không có token nhận 401 Unauthorized.
    """
    res = client.get("/api/v1/orders/workflow-counts")
    assert res.status_code == 401


def test_7_end_to_end_customer_create_to_admin_approve_updates_counts(customer_headers, admin_headers, staff_headers):
    """
    DoD 7: End-to-end: Customer tạo pending -> Admin count tăng -> Admin duyệt -> Admin approved tăng, Staff count tăng.
    """
    prod_id, _ = get_available_product_id_and_stock()

    # Lấy mốc count ban đầu
    admin_init = client.get("/api/v1/orders/workflow-counts", headers=admin_headers).json()
    staff_init = client.get("/api/v1/orders/workflow-counts", headers=staff_headers).json()

    # 1. Customer tạo đơn
    res_create = client.post("/api/v1/orders", json={
        "items": [{"product_id": prod_id, "quantity": 1}]
    }, headers=customer_headers)
    assert res_create.status_code == 200
    order = res_create.json()
    assert order["status"] == "pending"

    # Kiểm tra Admin count: pending tăng 1
    admin_after_create = client.get("/api/v1/orders/workflow-counts", headers=admin_headers).json()
    assert admin_after_create["pending_count"] == admin_init["pending_count"] + 1

    # 2. Admin duyệt đơn
    res_approve = client.post(f"/api/v1/orders/{order['id']}/approve", headers=admin_headers)
    assert res_approve.status_code == 200
    assert res_approve.json()["status"] == "admin_approved"

    # Kiểm tra Admin count: pending giảm 1, approved tăng 1
    admin_after_approve = client.get("/api/v1/orders/workflow-counts", headers=admin_headers).json()
    assert admin_after_approve["pending_count"] == admin_init["pending_count"]
    assert admin_after_approve["approved_count"] == admin_init["approved_count"] + 1

    # Kiểm tra Staff count: approved tăng 1
    staff_after_approve = client.get("/api/v1/orders/workflow-counts", headers=staff_headers).json()
    assert staff_after_approve["approved_count"] == staff_init["approved_count"] + 1


def test_8_staff_process_and_complete_workflow_and_revenue_verification(customer_headers, admin_headers, staff_headers, superadmin_headers):
    """
    DoD 8: Staff process -> processing_count tăng -> complete -> completed -> Doanh thu ghi nhận ở SuperAdmin.
    """
    prod_id, _ = get_available_product_id_and_stock()

    # Tạo & duyệt đơn
    res_create = client.post("/api/v1/orders", json={
        "items": [{"product_id": prod_id, "quantity": 1}]
    }, headers=customer_headers)
    order_id = res_create.json()["id"]
    order_amount = res_create.json()["final_amount"]
    client.post(f"/api/v1/orders/{order_id}/approve", headers=admin_headers)

    # 1. Staff nhận xử lý
    res_process = client.post(f"/api/v1/orders/{order_id}/process", headers=staff_headers)
    assert res_process.status_code == 200
    assert res_process.json()["status"] == "processing"

    # 2. Staff hoàn tất đơn
    res_complete = client.post(f"/api/v1/orders/{order_id}/complete", headers=staff_headers)
    assert res_complete.status_code == 200
    assert res_complete.json()["status"] == "completed"

    # Doanh thu SuperAdmin ghi nhận đơn completed
    rep_res = client.get("/api/v1/reports/summary", headers=superadmin_headers)
    assert rep_res.status_code == 200
    assert rep_res.json()["total_revenue"] >= order_amount


def test_9_admin_reject_workflow_and_counts_decrement(customer_headers, admin_headers):
    """
    DoD 9: Admin từ chối đơn pending -> trạng thái rejected, pending_count giảm, kho được hoàn.
    """
    prod_id, initial_stock = get_available_product_id_and_stock()

    # Customer tạo đơn (kho bị trừ giữ chỗ 1)
    res_create = client.post("/api/v1/orders", json={
        "items": [{"product_id": prod_id, "quantity": 1}]
    }, headers=customer_headers)
    order_id = res_create.json()["id"]

    admin_before_reject = client.get("/api/v1/orders/workflow-counts", headers=admin_headers).json()

    # Admin từ chối đơn
    res_reject = client.post(f"/api/v1/orders/{order_id}/reject", json={
        "reason": "Sản phẩm tạm thời ngưng cung cấp"
    }, headers=admin_headers)
    assert res_reject.status_code == 200
    assert res_reject.json()["status"] == "rejected"
    assert res_reject.json()["rejection_reason"] == "Sản phẩm tạm thời ngưng cung cấp"

    # Kiểm tra pending count giảm 1
    admin_after_reject = client.get("/api/v1/orders/workflow-counts", headers=admin_headers).json()
    assert admin_after_reject["pending_count"] == admin_before_reject["pending_count"] - 1

    # Kiểm tra kho được hoàn trả nguyên vẹn
    with get_db() as conn:
        c = conn.cursor()
        c.execute("SELECT stock_quantity FROM products WHERE id = ?", (prod_id,))
        final_stock = c.fetchone()["stock_quantity"]
        assert final_stock == initial_stock


def test_10_staff_cannot_approve_or_reject_returns_403(customer_headers, staff_headers):
    """
    DoD 10: Staff cố gọi approve hoặc reject nhận 403 Forbidden.
    """
    prod_id, _ = get_available_product_id_and_stock()
    res_create = client.post("/api/v1/orders", json={
        "items": [{"product_id": prod_id, "quantity": 1}]
    }, headers=customer_headers)
    order_id = res_create.json()["id"]

    res_app = client.post(f"/api/v1/orders/{order_id}/approve", headers=staff_headers)
    assert res_app.status_code == 403

    res_rej = client.post(f"/api/v1/orders/{order_id}/reject", json={"reason": "Lỗi"}, headers=staff_headers)
    assert res_rej.status_code == 403


def test_11_customer_cannot_process_or_complete_returns_403(customer_headers, admin_headers):
    """
    DoD 11: Customer cố gọi process hoặc complete nhận 403 Forbidden.
    """
    prod_id, _ = get_available_product_id_and_stock()
    res_create = client.post("/api/v1/orders", json={
        "items": [{"product_id": prod_id, "quantity": 1}]
    }, headers=customer_headers)
    order_id = res_create.json()["id"]
    client.post(f"/api/v1/orders/{order_id}/approve", headers=admin_headers)

    res_proc = client.post(f"/api/v1/orders/{order_id}/process", headers=customer_headers)
    assert res_proc.status_code == 403

    res_comp = client.post(f"/api/v1/orders/{order_id}/complete", headers=customer_headers)
    assert res_comp.status_code == 403


def test_12_admin_still_forbidden_from_revenue_reports_returns_403(admin_headers):
    """
    DoD 12: Admin tiếp tục bị cấm tuyệt đối truy cập báo cáo tài chính (403 Forbidden).
    """
    res = client.get("/api/v1/reports/summary", headers=admin_headers)
    assert res.status_code == 403


def test_13_status_filter_comma_separated_works(admin_headers):
    """
    DoD 13: Tab 'Đã hủy / Từ chối' lọc qua status=cancelled,rejected trả về đúng các đơn có status tương ứng.
    """
    res = client.get("/api/v1/orders?status=cancelled,rejected", headers=admin_headers)
    assert res.status_code == 200
    orders = res.json()
    for o in orders:
        assert o["status"] in ("cancelled", "rejected"), f"Unexpected status: {o['status']}"
