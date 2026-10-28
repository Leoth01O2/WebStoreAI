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
    # Login as customer user
    return {"Authorization": f"Bearer {get_token('customer', 'Customer@123')}"}


def test_customer_order_created_with_pending_status(customer_headers):
    """
    DoD 1: Customer đặt đơn hàng từ xa -> Trạng thái khởi tạo bắt buộc là PENDING.
    Dù có truyền status='completed' trong payload thì backend vẫn ép về 'pending'.
    """
    # 1. Lấy thông tin 1 sản phẩm còn hàng
    with get_db() as conn:
        c = conn.cursor()
        c.execute("SELECT id, stock_quantity FROM products WHERE status = 'active' AND stock_quantity >= 5 LIMIT 1")
        prod = c.fetchone()
        prod_id = prod["id"]

    order_payload = {
        "payment_method": "transfer",
        "payment_status": "pending",
        "status": "completed",  # Cố tình truyền completed để test backend enforcement
        "note": "Đơn hàng online đặt từ xa",
        "items": [{"product_id": prod_id, "quantity": 2}]
    }

    res = client.post("/api/v1/orders", json=order_payload, headers=customer_headers)
    assert res.status_code == 200, f"Tạo đơn thất bại: {res.text}"
    order = res.json()
    assert order["status"] == "pending", "Đơn hàng của Customer bắt buộc phải ở trạng thái 'pending'"
    assert order["approved_by"] is None
    assert order["approved_at"] is None
    assert order["rejected_by"] is None
    assert order["rejected_at"] is None


def test_staff_cannot_approve_or_reject_pending_order(customer_headers, staff_headers):
    """
    DoD 2: Staff bị cấm tuyệt đối không được duyệt hoặc từ chối đơn hàng (HTTP 403 Forbidden).
    """
    # Customer tạo đơn
    with get_db() as conn:
        c = conn.cursor()
        c.execute("SELECT id FROM products WHERE status = 'active' AND stock_quantity >= 2 LIMIT 1")
        prod_id = c.fetchone()["id"]

    res_create = client.post("/api/v1/orders", json={
        "items": [{"product_id": prod_id, "quantity": 1}]
    }, headers=customer_headers)
    assert res_create.status_code == 200
    order_id = res_create.json()["id"]

    # Staff cố duyệt -> 403 Forbidden
    res_approve = client.post(f"/api/v1/orders/{order_id}/approve", headers=staff_headers)
    assert res_approve.status_code == 403, "Staff cố duyệt đơn phải trả về 403 Forbidden"

    # Staff cố từ chối -> 403 Forbidden
    res_reject = client.post(f"/api/v1/orders/{order_id}/reject", json={"reason": "Staff từ chối"}, headers=staff_headers)
    assert res_reject.status_code == 403, "Staff cố từ chối đơn phải trả về 403 Forbidden"


def test_staff_cannot_process_pending_order(customer_headers, staff_headers):
    """
    DoD 3: Staff cố thao tác xử lý trên đơn đang PENDING -> Trả về HTTP 400 Bad Request
    với thông báo 'Đơn hàng chưa được Admin duyệt'.
    """
    with get_db() as conn:
        c = conn.cursor()
        c.execute("SELECT id FROM products WHERE status = 'active' AND stock_quantity >= 2 LIMIT 1")
        prod_id = c.fetchone()["id"]

    res_create = client.post("/api/v1/orders", json={
        "items": [{"product_id": prod_id, "quantity": 1}]
    }, headers=customer_headers)
    assert res_create.status_code == 200
    order_id = res_create.json()["id"]

    # Staff cố xử lý đơn PENDING
    res_process = client.post(f"/api/v1/orders/{order_id}/process", headers=staff_headers)
    assert res_process.status_code == 400, "Xử lý đơn PENDING phải trả về 400 Bad Request"
    assert "Đơn hàng chưa được Admin duyệt" in res_process.json()["detail"]


def test_admin_approve_workflow(customer_headers, admin_headers, staff_headers, superadmin_headers):
    """
    DoD 4: SuperAdmin duyệt đơn PENDING thành công (Admin bị chặn 403):
    - Admin cố duyệt -> 403 Forbidden
    - SuperAdmin duyệt -> Status chuyển sang confirmed / admin_approved
    - Ghi nhận approved_by và approved_at
    - Sau khi duyệt, Staff có thể nhận xử lý (status chuyển sang PROCESSING)
    - Không thể duyệt lại đơn đã duyệt (400 Bad Request)
    """
    with get_db() as conn:
        c = conn.cursor()
        c.execute("SELECT id FROM products WHERE status = 'active' AND stock_quantity >= 2 LIMIT 1")
        prod_id = c.fetchone()["id"]

    # Customer tạo đơn
    res_create = client.post("/api/v1/orders", json={
        "items": [{"product_id": prod_id, "quantity": 1}]
    }, headers=customer_headers)
    order_id = res_create.json()["id"]

    # Admin cố duyệt đơn -> 403 Forbidden
    res_admin_app = client.post(f"/api/v1/orders/{order_id}/approve", headers=admin_headers)
    assert res_admin_app.status_code == 403

    # SuperAdmin duyệt đơn
    res_approve = client.post(f"/api/v1/orders/{order_id}/approve", headers=superadmin_headers)
    assert res_approve.status_code == 200, f"SuperAdmin duyệt đơn thất bại: {res_approve.text}"
    approved_order = res_approve.json()
    assert approved_order["status"] in ("confirmed", "admin_approved")
    assert approved_order["approved_by"] is not None
    assert approved_order["approved_at"] is not None

    # Thử duyệt lại lần 2 -> 400 Bad Request
    res_reapprove = client.post(f"/api/v1/orders/{order_id}/approve", headers=superadmin_headers)
    assert res_reapprove.status_code == 400
    assert "pending" in res_reapprove.json()["detail"]

    # Staff nhận xử lý đơn đã được duyệt -> 200 OK (status: processing)
    res_process = client.post(f"/api/v1/orders/{order_id}/process", headers=staff_headers)
    assert res_process.status_code == 200
    assert res_process.json()["status"] == "processing"
    assert res_process.json()["processed_by"] is not None
    assert res_process.json()["processed_at"] is not None


def test_admin_reject_workflow_and_inventory_refund(customer_headers, admin_headers, superadmin_headers):
    """
    DoD 5: Admin từ chối đơn PENDING kèm lý do:
    - Status chuyển sang REJECTED
    - Ghi nhận rejected_by, rejected_at, rejection_reason
    - Tồn kho sản phẩm được hoàn trả tự động chính xác
    - Ghi log xuất nhập tồn return_cancel vào inventory_logs
    - Admin không thể từ chối lại đơn đã từ chối (400 Bad Request)
    """
    with get_db() as conn:
        c = conn.cursor()
        c.execute("SELECT id, stock_quantity FROM products WHERE status = 'active' AND stock_quantity >= 5 LIMIT 1")
        prod = c.fetchone()
        prod_id = prod["id"]
        stock_initial = prod["stock_quantity"]

    buy_qty = 2
    # 1. Customer tạo đơn -> kho bị trừ buy_qty
    res_create = client.post("/api/v1/orders", json={
        "items": [{"product_id": prod_id, "quantity": buy_qty}]
    }, headers=customer_headers)
    assert res_create.status_code == 200
    order_data = res_create.json()
    order_id = order_data["id"]
    order_code = order_data["order_code"]

    with get_db() as conn:
        c = conn.cursor()
        c.execute("SELECT stock_quantity FROM products WHERE id = ?", (prod_id,))
        assert c.fetchone()["stock_quantity"] == stock_initial - buy_qty, "Kho phải bị trừ sau khi Customer đặt hàng"

    # 2. Admin cố từ chối đơn -> 403 Forbidden
    rejection_reason = "Không liên lạc được với khách hàng qua số điện thoại"
    res_admin_rej = client.post(
        f"/api/v1/orders/{order_id}/reject",
        json={"reason": rejection_reason},
        headers=admin_headers
    )
    assert res_admin_rej.status_code == 403

    # SuperAdmin từ chối đơn
    res_reject = client.post(
        f"/api/v1/orders/{order_id}/reject",
        json={"reason": rejection_reason},
        headers=superadmin_headers
    )
    assert res_reject.status_code == 200, f"Từ chối đơn thất bại: {res_reject.text}"
    rejected_order = res_reject.json()
    assert rejected_order["status"] in ("rejected", "cancelled")
    assert rejected_order["rejected_by"] is not None
    assert rejected_order["rejected_at"] is not None
    assert rejected_order["rejection_reason"] == rejection_reason

    # 3. Kiểm tra tồn kho được hoàn trả chính xác
    with get_db() as conn:
        c = conn.cursor()
        c.execute("SELECT stock_quantity FROM products WHERE id = ?", (prod_id,))
        stock_restored = c.fetchone()["stock_quantity"]
        assert stock_restored == stock_initial, f"Tồn kho chưa được hoàn trả: trước={stock_initial}, sau={stock_restored}"

        # Kiểm tra nhật ký inventory_logs ghi nhận return_cancel
        c.execute(
            """SELECT * FROM inventory_logs
               WHERE product_id = ? AND reference_code = ? AND change_type = 'return_cancel'
               ORDER BY id DESC LIMIT 1""",
            (prod_id, order_code)
        )
        inv_log = c.fetchone()
        assert inv_log is not None, "Không tìm thấy bản ghi log return_cancel cho đơn hàng bị từ chối"
        assert inv_log["change_quantity"] == buy_qty
        assert rejection_reason in inv_log["note"]

    # 4. Thử từ chối lại -> 400 Bad Request
    res_rereject = client.post(
        f"/api/v1/orders/{order_id}/reject",
        json={"reason": "Thử lại"},
        headers=superadmin_headers
    )
    assert res_rereject.status_code == 400


def test_pos_direct_order_remains_completed(staff_headers):
    """
    DoD 6: Đơn bán hàng trực tiếp tại quầy POS do Nhân viên/Admin lập cho khách mua tại chỗ
    vẫn hoàn tất ngay ở trạng thái COMPLETED.
    """
    with get_db() as conn:
        c = conn.cursor()
        c.execute("SELECT id FROM products WHERE status = 'active' AND stock_quantity >= 2 LIMIT 1")
        prod_id = c.fetchone()["id"]

    pos_payload = {
        "customer_id": None,
        "payment_method": "cash",
        "payment_status": "completed",
        "status": "completed",
        "note": "Bán trực tiếp tại quầy POS",
        "items": [{"product_id": prod_id, "quantity": 1}]
    }

    res = client.post("/api/v1/orders", json=pos_payload, headers=staff_headers)
    assert res.status_code == 200
    pos_order = res.json()
    assert pos_order["status"] == "completed", "Đơn hàng POS của nhân viên lập tại chỗ phải là completed"


def test_customer_cannot_approve_reject_or_process(customer_headers):
    """
    DoD 7: Khách hàng (Customer) bị chặn 403 Forbidden nếu cố tình gọi các endpoint duyệt/từ chối/xử lý.
    """
    res_app = client.post("/api/v1/orders/1/approve", headers=customer_headers)
    assert res_app.status_code == 403

    res_rej = client.post("/api/v1/orders/1/reject", json={"reason": "Hack"}, headers=customer_headers)
    assert res_rej.status_code == 403

    res_proc = client.post("/api/v1/orders/1/process", headers=customer_headers)
    assert res_proc.status_code == 403
