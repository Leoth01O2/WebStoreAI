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
def customer_a_headers():
    return {"Authorization": f"Bearer {get_token('customer', 'Customer@123')}"}

@pytest.fixture
def customer_b_headers():
    return {"Authorization": f"Bearer {get_token('customer2', 'Customer2@123')}"}

@pytest.fixture
def admin_headers():
    return {"Authorization": f"Bearer {get_token('admin', 'Admin@123')}"}

@pytest.fixture
def staff_headers():
    return {"Authorization": f"Bearer {get_token('staff', 'Staff@123')}"}


def get_available_product_id_and_stock(min_stock=10):
    with get_db() as conn:
        c = conn.cursor()
        c.execute("SELECT id, stock_quantity FROM products WHERE status = 'active' AND stock_quantity >= ? LIMIT 1", (min_stock,))
        prod = c.fetchone()
        assert prod is not None, "Need at least one active product with sufficient stock"
        return prod["id"], prod["stock_quantity"]


def test_1_customer_only_retrieves_own_orders(customer_a_headers, customer_b_headers):
    """
    DoD 1: Customer chỉ lấy được order của chính mình qua GET /orders.
    Customer A không bao giờ nhìn thấy đơn của Customer B trong danh sách.
    """
    # 1. Customer A lấy danh sách đơn
    res_a = client.get("/api/v1/orders", headers=customer_a_headers)
    assert res_a.status_code == 200
    orders_a = res_a.json()
    assert isinstance(orders_a, list)

    for o in orders_a:
        # Customer A có user_id=38, customer_id=1
        assert (o["user_id"] == 38 or o["customer_id"] == 1), f"Leaked order {o['id']} to Customer A"

    # 2. Customer B lấy danh sách đơn
    res_b = client.get("/api/v1/orders", headers=customer_b_headers)
    assert res_b.status_code == 200
    orders_b = res_b.json()
    assert isinstance(orders_b, list)

    for o in orders_b:
        # Customer B có user_id=39, customer_id=2
        assert (o["user_id"] == 39 or o["customer_id"] == 2), f"Leaked order {o['id']} to Customer B"


def test_2_customer_views_own_order_detail_successfully(customer_a_headers):
    """
    DoD 2: Customer xem order của mình thành công qua GET /orders/{id}.
    """
    prod_id, _ = get_available_product_id_and_stock()

    res_create = client.post("/api/v1/orders", json={
        "payment_method": "transfer",
        "note": "Customer A test detail view",
        "items": [{"product_id": prod_id, "quantity": 1}]
    }, headers=customer_a_headers)
    assert res_create.status_code == 200
    created_order = res_create.json()
    order_id = created_order["id"]

    res_detail = client.get(f"/api/v1/orders/{order_id}", headers=customer_a_headers)
    assert res_detail.status_code == 200
    detail = res_detail.json()
    assert detail["id"] == order_id
    assert detail["order_code"] == created_order["order_code"]
    assert detail["status"] == "pending"
    assert len(detail["items"]) == 1


def test_3_customer_a_view_customer_b_order_returns_403(customer_a_headers, customer_b_headers):
    """
    DoD 3: Customer A cố truy cập chi tiết đơn của Customer B -> HTTP 403 Forbidden.
    """
    prod_id, _ = get_available_product_id_and_stock()

    # Customer B tạo đơn
    res_b_create = client.post("/api/v1/orders", json={
        "payment_method": "cash",
        "note": "Private order of Customer B",
        "items": [{"product_id": prod_id, "quantity": 1}]
    }, headers=customer_b_headers)
    assert res_b_create.status_code == 200
    order_b_id = res_b_create.json()["id"]

    # Customer A cố xem đơn của Customer B -> 403
    res_idor = client.get(f"/api/v1/orders/{order_b_id}", headers=customer_a_headers)
    assert res_idor.status_code == 403
    assert "không có quyền xem thông tin hóa đơn" in res_idor.json()["detail"]


def test_4_customer_cancels_own_pending_order_successfully(customer_a_headers):
    """
    DoD 4: Customer hủy own PENDING -> cancelled thành công.
    """
    prod_id, _ = get_available_product_id_and_stock()

    res_create = client.post("/api/v1/orders", json={
        "payment_method": "transfer",
        "note": "Order to be self-cancelled",
        "items": [{"product_id": prod_id, "quantity": 1}]
    }, headers=customer_a_headers)
    assert res_create.status_code == 200
    order_id = res_create.json()["id"]

    # Customer A hủy đơn PENDING của chính mình
    res_cancel = client.post(
        f"/api/v1/orders/{order_id}/customer-cancel",
        json={"reason": "Tôi muốn đổi phương thức thanh toán"},
        headers=customer_a_headers
    )
    assert res_cancel.status_code == 200
    cancelled_order = res_cancel.json()
    assert cancelled_order["status"] == "cancelled"

    # Kiểm tra trong DB
    with get_db() as conn:
        c = conn.cursor()
        c.execute("SELECT status, note FROM orders WHERE id = ?", (order_id,))
        row = c.fetchone()
        assert row["status"] == "cancelled"
        assert "[KHÁCH HỦY:" in row["note"]


def test_5_inventory_refunded_accurately_upon_customer_cancellation(customer_a_headers):
    """
    DoD 5: Inventory được hoàn trả chính xác sau khi Customer tự hủy đơn PENDING.
    """
    prod_id, stock_before = get_available_product_id_and_stock()

    qty_to_buy = 3

    # Tạo đơn -> tồn kho trừ qty_to_buy
    res_create = client.post("/api/v1/orders", json={
        "payment_method": "cash",
        "items": [{"product_id": prod_id, "quantity": qty_to_buy}]
    }, headers=customer_a_headers)
    assert res_create.status_code == 200
    order = res_create.json()
    order_id = order["id"]
    order_code = order["order_code"]

    with get_db() as conn:
        c = conn.cursor()
        c.execute("SELECT stock_quantity FROM products WHERE id = ?", (prod_id,))
        stock_after_create = c.fetchone()["stock_quantity"]
        assert stock_after_create == stock_before - qty_to_buy

    # Customer hủy đơn
    res_cancel = client.post(
        f"/api/v1/orders/{order_id}/customer-cancel",
        json={"reason": "Test hoàn tồn kho"},
        headers=customer_a_headers
    )
    assert res_cancel.status_code == 200

    # Kiểm tra tồn kho được hoàn trả chính xác bằng stock_before
    with get_db() as conn:
        c = conn.cursor()
        c.execute("SELECT stock_quantity FROM products WHERE id = ?", (prod_id,))
        stock_restored = c.fetchone()["stock_quantity"]
        assert stock_restored == stock_before

        # Kiểm tra nhật ký tồn kho có log 'return_cancel'
        c.execute(
            "SELECT change_type, reference_code, change_quantity FROM inventory_logs WHERE product_id = ? AND reference_code = ? ORDER BY id DESC LIMIT 1",
            (prod_id, order_code)
        )
        log_entry = c.fetchone()
        assert log_entry is not None
        assert log_entry["change_type"] == "return_cancel"
        assert log_entry["change_quantity"] == qty_to_buy


def test_6_idempotency_cancelled_order_no_double_stock_return(customer_a_headers):
    """
    DoD 6: Hủy lại cancelled order không được hoàn kho lần hai (Idempotency).
    """
    prod_id, stock_start = get_available_product_id_and_stock()

    res_create = client.post("/api/v1/orders", json={
        "items": [{"product_id": prod_id, "quantity": 2}]
    }, headers=customer_a_headers)
    order_id = res_create.json()["id"]

    # Lần 1: hủy thành công
    res_cancel_1 = client.post(f"/api/v1/orders/{order_id}/customer-cancel", headers=customer_a_headers)
    assert res_cancel_1.status_code == 200

    # Tồn kho hiện tại
    with get_db() as conn:
        c = conn.cursor()
        c.execute("SELECT stock_quantity FROM products WHERE id = ?", (prod_id,))
        stock_after_first_cancel = c.fetchone()["stock_quantity"]
        assert stock_after_first_cancel == stock_start

    # Lần 2: gọi lại cancel trên đơn đã cancelled -> 400 Bad Request
    res_cancel_2 = client.post(f"/api/v1/orders/{order_id}/customer-cancel", headers=customer_a_headers)
    assert res_cancel_2.status_code == 400
    assert "đã được hủy trước đó" in res_cancel_2.json()["detail"]

    # Kiểm tra tồn kho không bị cộng thêm lần 2
    with get_db() as conn:
        c = conn.cursor()
        c.execute("SELECT stock_quantity FROM products WHERE id = ?", (prod_id,))
        stock_final = c.fetchone()["stock_quantity"]
        assert stock_final == stock_start, "Lỗi: Tồn kho bị hoàn trả lần thứ hai!"


def test_7_customer_cannot_cancel_admin_approved_order(customer_a_headers, admin_headers):
    """
    DoD 7: Customer không tự hủy được đơn đã ADMIN_APPROVED.
    Trả về lỗi rõ ràng và yêu cầu liên hệ cửa hàng.
    """
    prod_id, _ = get_available_product_id_and_stock()

    res_create = client.post("/api/v1/orders", json={
        "items": [{"product_id": prod_id, "quantity": 1}]
    }, headers=customer_a_headers)
    order_id = res_create.json()["id"]

    # Admin duyệt đơn
    res_appr = client.post(f"/api/v1/orders/{order_id}/approve", headers=admin_headers)
    assert res_appr.status_code == 200
    assert res_appr.json()["status"] == "admin_approved"

    # Customer cố hủy đơn đã duyệt -> 400
    res_cancel = client.post(f"/api/v1/orders/{order_id}/customer-cancel", headers=customer_a_headers)
    assert res_cancel.status_code == 400
    detail = res_cancel.json()["detail"]
    assert "admin_approved" in detail
    assert "liên hệ cửa hàng" in detail


def test_8_customer_cannot_cancel_processing_order(customer_a_headers, admin_headers, staff_headers):
    """
    DoD 8: Customer không tự hủy được đơn đang PROCESSING.
    """
    prod_id, _ = get_available_product_id_and_stock()

    res_create = client.post("/api/v1/orders", json={
        "items": [{"product_id": prod_id, "quantity": 1}]
    }, headers=customer_a_headers)
    order_id = res_create.json()["id"]

    # Admin duyệt
    client.post(f"/api/v1/orders/{order_id}/approve", headers=admin_headers)
    # Staff xử lý
    res_proc = client.post(f"/api/v1/orders/{order_id}/process", headers=staff_headers)
    assert res_proc.status_code == 200
    assert res_proc.json()["status"] == "processing"

    # Customer cố hủy đơn đang xử lý -> 400
    res_cancel = client.post(f"/api/v1/orders/{order_id}/customer-cancel", headers=customer_a_headers)
    assert res_cancel.status_code == 400
    assert "processing" in res_cancel.json()["detail"]
    assert "liên hệ cửa hàng" in res_cancel.json()["detail"]


def test_9_customer_cannot_cancel_completed_order(customer_a_headers, admin_headers, staff_headers):
    """
    DoD 9: Customer không tự hủy được đơn đã COMPLETED.
    """
    prod_id, _ = get_available_product_id_and_stock()

    res_create = client.post("/api/v1/orders", json={
        "items": [{"product_id": prod_id, "quantity": 1}]
    }, headers=customer_a_headers)
    order_id = res_create.json()["id"]

    # Admin duyệt -> Staff hoàn tất
    client.post(f"/api/v1/orders/{order_id}/approve", headers=admin_headers)
    client.post(f"/api/v1/orders/{order_id}/process", headers=staff_headers)
    res_comp = client.post(f"/api/v1/orders/{order_id}/complete", headers=staff_headers)
    assert res_comp.status_code == 200
    assert res_comp.json()["status"] == "completed"

    # Customer cố hủy đơn đã hoàn thành -> 400
    res_cancel = client.post(f"/api/v1/orders/{order_id}/customer-cancel", headers=customer_a_headers)
    assert res_cancel.status_code == 400
    assert "completed" in res_cancel.json()["detail"]


def test_10_customer_a_cannot_cancel_customer_b_order_returns_403(customer_a_headers, customer_b_headers):
    """
    DoD 10: Customer A cố hủy đơn PENDING của Customer B -> 403 Forbidden (Anti-IDOR).
    """
    prod_id, _ = get_available_product_id_and_stock()

    # Customer B tạo đơn PENDING
    res_b = client.post("/api/v1/orders", json={
        "items": [{"product_id": prod_id, "quantity": 1}]
    }, headers=customer_b_headers)
    assert res_b.status_code == 200
    order_b_id = res_b.json()["id"]

    # Customer A cố gửi request hủy đơn của Customer B
    res_idor_cancel = client.post(f"/api/v1/orders/{order_b_id}/customer-cancel", headers=customer_a_headers)
    assert res_idor_cancel.status_code == 403
    assert "không có quyền thao tác trên đơn hàng của khách hàng khác" in res_idor_cancel.json()["detail"]
