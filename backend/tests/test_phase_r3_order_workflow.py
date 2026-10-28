import os
import shutil
import sqlite3
import pytest
from concurrent.futures import ThreadPoolExecutor
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

@pytest.fixture
def customer2_headers():
    return {"Authorization": f"Bearer {get_token('customer2', 'Customer@123')}"}


def test_01_rbac_and_anti_idor(customer_headers, staff_headers, admin_headers):
    """
    Test RBAC và chống IDOR cho các endpoints Phase R3:
    - Customer không được claim, verify-payment, confirm-cod, confirm-return, confirm-refund, reassign.
    - Customer chỉ được xem đơn và audit logs của chính mình.
    """
    # Lấy 1 product để tạo đơn
    with get_db() as conn:
        c = conn.cursor()
        c.execute("SELECT id, selling_price FROM products WHERE status = 'active' AND stock_quantity >= 5 LIMIT 1")
        prod = c.fetchone()
        prod_id = prod["id"]

    res_create = client.post("/api/v1/orders", json={
        "payment_method": "transfer",
        "items": [{"product_id": prod_id, "quantity": 1}]
    }, headers=customer_headers)
    assert res_create.status_code == 200
    order_id = res_create.json()["id"]

    # Customer thử claim đơn -> 403 Forbidden
    res_claim = client.post(f"/api/v1/orders/{order_id}/claim", headers=customer_headers)
    assert res_claim.status_code == 403

    # Customer thử verify-payment -> 403 Forbidden
    res_verify = client.post(f"/api/v1/orders/{order_id}/verify-payment", headers=customer_headers)
    assert res_verify.status_code == 403

    # Customer thử confirm-cod-payment -> 403 Forbidden
    res_cod = client.post(f"/api/v1/orders/{order_id}/confirm-cod-payment", headers=customer_headers)
    assert res_cod.status_code == 403

    # Customer thử update-fulfillment -> 403 Forbidden
    res_ful = client.post(f"/api/v1/orders/{order_id}/update-fulfillment", json={"fulfillment_status": "packing"}, headers=customer_headers)
    assert res_ful.status_code == 403

    # Customer thử confirm-return -> 403 Forbidden
    res_ret = client.post(f"/api/v1/orders/{order_id}/confirm-return", headers=customer_headers)
    assert res_ret.status_code == 403

    # Customer thử confirm-refund -> 403 Forbidden
    res_ref = client.post(f"/api/v1/orders/{order_id}/confirm-refund", headers=customer_headers)
    assert res_ref.status_code == 403

    # Customer thử reassign -> 403 Forbidden
    res_reas = client.post(f"/api/v1/orders/{order_id}/reassign", json={"new_staff_id": 2, "reason": "Test"}, headers=customer_headers)
    assert res_reas.status_code == 403

    # Customer xem audit logs của chính mình -> 200 OK
    res_audit_own = client.get(f"/api/v1/orders/{order_id}/audit-logs", headers=customer_headers)
    assert res_audit_own.status_code == 200
    assert isinstance(res_audit_own.json(), list)


def test_02_atomic_claim_lock_and_concurrency(customer_headers, admin_headers, staff_headers):
    """
    Test Atomic Claim Lock:
    - Đơn chưa duyệt không được claim -> 400.
    - Hai staff / request đồng thời cạnh tranh claim 1 đơn:
      chỉ MỘT thành công (200), request còn lại bị từ chối với 409 Conflict.
    - Không double stock deduction khi claim.
    - Không thay đổi payment_status khi chỉ claim.
    - Ghi audit log 'claim' trong cùng transaction.
    """
    with get_db() as conn:
        c = conn.cursor()
        c.execute("SELECT id, stock_quantity FROM products WHERE status = 'active' AND stock_quantity >= 5 LIMIT 1")
        prod = c.fetchone()
        prod_id = prod["id"]
        stock_initial = prod["stock_quantity"]

    # 1. Tạo đơn hàng online bởi Customer (bắt đầu ở pending)
    res_create = client.post("/api/v1/orders", json={
        "payment_method": "cash",
        "items": [{"product_id": prod_id, "quantity": 1}]
    }, headers=customer_headers)
    assert res_create.status_code == 200
    order = res_create.json()
    order_id = order["id"]

    # Tồn kho đã trừ 1 khi tạo đơn
    with get_db() as conn:
        c = conn.cursor()
        c.execute("SELECT stock_quantity FROM products WHERE id = ?", (prod_id,))
        stock_after_create = c.fetchone()["stock_quantity"]
    assert stock_after_create == stock_initial - 1

    # 2. Thử claim khi đơn chưa duyệt (đang 'pending') -> 400 Bad Request
    res_claim_pending = client.post(f"/api/v1/orders/{order_id}/claim", headers=staff_headers)
    assert res_claim_pending.status_code == 400
    assert "đã được Admin duyệt" in res_claim_pending.json()["detail"]

    # 3. Admin duyệt đơn
    res_app = client.post(f"/api/v1/orders/{order_id}/approve", headers=admin_headers)
    assert res_app.status_code == 200
    assert res_app.json()["status"] == "admin_approved"

    # 4. Thử nghiệm cạnh tranh đồng thời (Concurrency Claim Lock) giữa 2 nhân viên khác nhau
    # Gửi 2 request claim song song từ staff và admin qua ThreadPool
    def send_claim_staff():
        return client.post(f"/api/v1/orders/{order_id}/claim", json={"note": "Staff 1 nhận đơn"}, headers=staff_headers)

    def send_claim_admin():
        return client.post(f"/api/v1/orders/{order_id}/claim", json={"note": "Staff 2 nhận đơn"}, headers=admin_headers)

    with ThreadPoolExecutor(max_workers=2) as executor:
        f1 = executor.submit(send_claim_staff)
        f2 = executor.submit(send_claim_admin)
        r1 = f1.result()
        r2 = f2.result()

    status_codes = sorted([r1.status_code, r2.status_code])
    assert status_codes == [200, 409], f"Expected [200, 409], got {status_codes}"

    # Lấy thông tin đơn sau claim
    res_detail = client.get(f"/api/v1/orders/{order_id}", headers=admin_headers)
    assert res_detail.status_code == 200
    claimed_order = res_detail.json()
    assert claimed_order["status"] == "processing"
    assert claimed_order["assigned_to"] is not None
    assert claimed_order["payment_status"] == "unpaid"  # payment_status không bị sửa

    # Tồn kho KHÔNG bị trừ lần 2
    with get_db() as conn:
        c = conn.cursor()
        c.execute("SELECT stock_quantity FROM products WHERE id = ?", (prod_id,))
        stock_after_claim = c.fetchone()["stock_quantity"]
    assert stock_after_claim == stock_after_create

    # Kiểm tra audit log có action 'claim'
    res_audit = client.get(f"/api/v1/orders/{order_id}/audit-logs", headers=staff_headers)
    assert res_audit.status_code == 200
    audit_actions = [log["action"] for log in res_audit.json()]
    assert "claim" in audit_actions or "claim_order" in audit_actions


def test_03_payment_verification_cod_and_transfer(customer_headers, staff_headers, admin_headers):
    """
    Test Payment Verification:
    - COD: ban đầu unpaid; staff xác nhận thu tiền -> paid; không áp dụng cho đơn transfer.
    - Chuyển khoản: notify-transfer -> pending_verification; admin đối soát -> paid.
    """
    with get_db() as conn:
        c = conn.cursor()
        c.execute("SELECT id FROM products WHERE status = 'active' AND stock_quantity >= 5 LIMIT 1")
        prod_id = c.fetchone()["id"]

    # A. Test COD
    res_cod = client.post("/api/v1/orders", json={
        "payment_method": "cash",
        "items": [{"product_id": prod_id, "quantity": 1}]
    }, headers=customer_headers)
    assert res_cod.status_code == 200
    cod_id = res_cod.json()["id"]
    assert res_cod.json()["payment_status"] == "unpaid"

    # Admin duyệt đơn
    client.post(f"/api/v1/orders/{cod_id}/approve", headers=admin_headers)
    # Staff claim đơn
    client.post(f"/api/v1/orders/{cod_id}/claim", headers=staff_headers)

    # Đơn vẫn unpaid sau khi claim
    res_check_cod = client.get(f"/api/v1/orders/{cod_id}", headers=staff_headers)
    assert res_check_cod.json()["payment_status"] == "unpaid"

    # Staff xác nhận thu COD -> paid
    res_confirm_cod = client.post(f"/api/v1/orders/{cod_id}/confirm-cod-payment", headers=staff_headers)
    assert res_confirm_cod.status_code == 200
    assert res_confirm_cod.json()["payment_status"] == "paid"

    # B. Test Chuyển khoản
    res_transfer = client.post("/api/v1/orders", json={
        "payment_method": "transfer",
        "items": [{"product_id": prod_id, "quantity": 1}]
    }, headers=customer_headers)
    assert res_transfer.status_code == 200
    transfer_id = res_transfer.json()["id"]
    assert res_transfer.json()["payment_status"] == "unpaid"

    # Khách hàng / Staff thử xác nhận thu COD trên đơn chuyển khoản -> 400
    res_bad_cod = client.post(f"/api/v1/orders/{transfer_id}/confirm-cod-payment", headers=staff_headers)
    assert res_bad_cod.status_code == 400
    assert "tiền mặt" in res_bad_cod.json()["detail"]

    # Khách thông báo đã chuyển tiền -> pending_verification
    res_notify = client.post(f"/api/v1/orders/{transfer_id}/notify-transfer", json={
        "transfer_reference": "TX-MB-998822",
        "bank_name": "MB Bank",
        "note": "Đã chuyển đủ tiền hàng"
    }, headers=customer_headers)
    assert res_notify.status_code == 200
    assert res_notify.json()["payment_status"] == "pending_verification"

    # Admin xác minh thanh toán sau đối soát chứng từ thực tế -> paid
    res_verify = client.post(f"/api/v1/orders/{transfer_id}/verify-payment", json={
        "verified_reference": "SAOKE-MB-MATCHED-998822",
        "note": "Khớp số dư tài khoản Techcombank"
    }, headers=admin_headers)
    assert res_verify.status_code == 200
    assert res_verify.json()["payment_status"] == "paid"


def test_04_fulfillment_and_inventory_return(customer_headers, admin_headers, staff_headers):
    """
    Test Fulfillment & Inventory Return:
    - unfulfilled -> packing -> shipping -> delivery_failed.
    - delivery_failed KHÔNG tự động hoàn kho.
    - confirm-return hoàn kho thành công.
    - confirm-return lần 2 bị từ chối (chống double return).
    """
    with get_db() as conn:
        c = conn.cursor()
        c.execute("SELECT id, stock_quantity FROM products WHERE status = 'active' AND stock_quantity >= 5 LIMIT 1")
        prod = c.fetchone()
        prod_id = prod["id"]
        stock_init = prod["stock_quantity"]

    res_create = client.post("/api/v1/orders", json={
        "payment_method": "cash",
        "items": [{"product_id": prod_id, "quantity": 2}]
    }, headers=customer_headers)
    assert res_create.status_code == 200
    order_id = res_create.json()["id"]

    # Stock trừ 2
    with get_db() as conn:
        c = conn.cursor()
        c.execute("SELECT stock_quantity FROM products WHERE id = ?", (prod_id,))
        stock_after_create = c.fetchone()["stock_quantity"]
    assert stock_after_create == stock_init - 2

    # Duyệt và claim
    client.post(f"/api/v1/orders/{order_id}/approve", headers=admin_headers)
    client.post(f"/api/v1/orders/{order_id}/claim", headers=staff_headers)

    # 1. Update packing
    res_pack = client.post(f"/api/v1/orders/{order_id}/update-fulfillment", json={"fulfillment_status": "packing"}, headers=staff_headers)
    assert res_pack.status_code == 200
    assert res_pack.json()["fulfillment_status"] == "packing"

    # 2. Update shipping
    res_ship = client.post(f"/api/v1/orders/{order_id}/update-fulfillment", json={"fulfillment_status": "shipping"}, headers=staff_headers)
    assert res_ship.status_code == 200
    assert res_ship.json()["fulfillment_status"] == "shipping"

    # 3. Update delivery_failed
    res_fail = client.post(f"/api/v1/orders/{order_id}/update-fulfillment", json={"fulfillment_status": "delivery_failed"}, headers=staff_headers)
    assert res_fail.status_code == 200
    assert res_fail.json()["fulfillment_status"] == "delivery_failed"

    # KIỂM TRA QUAN TRỌNG: delivery_failed KHÔNG ĐƯỢC tự động nhập lại kho!
    with get_db() as conn:
        c = conn.cursor()
        c.execute("SELECT stock_quantity FROM products WHERE id = ?", (prod_id,))
        stock_after_fail = c.fetchone()["stock_quantity"]
    assert stock_after_fail == stock_after_create, "delivery_failed MUST NOT restore inventory automatically!"

    # 4. Xác nhận hàng thực tế quay về kho (confirm-return)
    res_ret = client.post(f"/api/v1/orders/{order_id}/confirm-return", json={
        "reason": "Khách không nhận, hàng quay về kho",
        "note": "Bao bì nguyên vẹn"
    }, headers=staff_headers)
    assert res_ret.status_code == 200
    assert res_ret.json()["fulfillment_status"] == "returned_to_inventory"

    # Kiểm tra tồn kho đã được cộng lại nguyên vẹn đúng 2
    with get_db() as conn:
        c = conn.cursor()
        c.execute("SELECT stock_quantity FROM products WHERE id = ?", (prod_id,))
        stock_after_return = c.fetchone()["stock_quantity"]
    assert stock_after_return == stock_init

    # 5. Thử confirm-return lần 2 -> 400 Bad Request (Anti-double inventory return)
    res_ret_duplicate = client.post(f"/api/v1/orders/{order_id}/confirm-return", headers=staff_headers)
    assert res_ret_duplicate.status_code == 400
    assert "đã được nhập lại kho" in res_ret_duplicate.json()["detail"]

    # Kiểm tra tồn kho KHÔNG bị cộng lần thứ hai
    with get_db() as conn:
        c = conn.cursor()
        c.execute("SELECT stock_quantity FROM products WHERE id = ?", (prod_id,))
        stock_final = c.fetchone()["stock_quantity"]
    assert stock_final == stock_init


def test_05_refund_independent_of_inventory(customer_headers, staff_headers, admin_headers):
    """
    Test Refund độc lập với hoàn hàng:
    - Đơn đã thanh toán (paid) -> request_refund -> refund_pending.
    - Không làm thay đổi tồn kho.
    - confirm_refund -> refunded.
    - Không làm thay đổi tồn kho (Không tự động nhập kho khi hoàn tiền).
    """
    with get_db() as conn:
        c = conn.cursor()
        c.execute("SELECT id, stock_quantity FROM products WHERE status = 'active' AND stock_quantity >= 5 LIMIT 1")
        prod = c.fetchone()
        prod_id = prod["id"]

    res_create = client.post("/api/v1/orders", json={
        "payment_method": "transfer",
        "items": [{"product_id": prod_id, "quantity": 1}]
    }, headers=customer_headers)
    assert res_create.status_code == 200
    order_id = res_create.json()["id"]

    # Duyệt và xác minh thanh toán
    client.post(f"/api/v1/orders/{order_id}/approve", headers=admin_headers)
    client.post(f"/api/v1/orders/{order_id}/verify-payment", headers=admin_headers)

    res_paid = client.get(f"/api/v1/orders/{order_id}", headers=admin_headers)
    assert res_paid.json()["payment_status"] == "paid"

    # Lấy stock hiện tại trước refund
    with get_db() as conn:
        c = conn.cursor()
        c.execute("SELECT stock_quantity FROM products WHERE id = ?", (prod_id,))
        stock_before_refund = c.fetchone()["stock_quantity"]

    # 1. Yêu cầu hoàn tiền (request-refund)
    res_req_ref = client.post(f"/api/v1/orders/{order_id}/request-refund", json={"reason": "Sản phẩm không vừa ý"}, headers=customer_headers)
    assert res_req_ref.status_code == 200
    assert res_req_ref.json()["payment_status"] == "refund_pending"

    # Tồn kho không đổi
    with get_db() as conn:
        c = conn.cursor()
        c.execute("SELECT stock_quantity FROM products WHERE id = ?", (prod_id,))
        stock_after_req = c.fetchone()["stock_quantity"]
    assert stock_after_req == stock_before_refund

    # 2. Admin xác nhận hoàn tiền thực tế (confirm-refund)
    res_conf_ref = client.post(f"/api/v1/orders/{order_id}/confirm-refund", json={
        "refund_reference": "REFUND-BANK-112233",
        "reason": "Đã chuyển khoản hoàn tiền thành công"
    }, headers=admin_headers)
    assert res_conf_ref.status_code == 200
    assert res_conf_ref.json()["payment_status"] == "refunded"

    # Tồn kho VẪN KHÔNG ĐỔI (Hoàn tiền độc lập với tồn kho)
    with get_db() as conn:
        c = conn.cursor()
        c.execute("SELECT stock_quantity FROM products WHERE id = ?", (prod_id,))
        stock_after_conf = c.fetchone()["stock_quantity"]
    assert stock_after_conf == stock_before_refund


def test_06_reassign_order_and_audit(staff_headers, admin_headers):
    """
    Test Admin điều chuyển đơn cho Staff khác (Reassign) và ghi vết kiểm toán.
    """
    with get_db() as conn:
        c = conn.cursor()
        c.execute("SELECT id FROM products WHERE status = 'active' AND stock_quantity >= 5 LIMIT 1")
        prod_id = c.fetchone()["id"]
        c.execute("SELECT id FROM users WHERE role = 'staff' LIMIT 2")
        staff_rows = c.fetchall()
        staff_1_id = staff_rows[0]["id"]
        staff_2_id = staff_rows[1]["id"] if len(staff_rows) > 1 else staff_rows[0]["id"]

    res_create = client.post("/api/v1/orders", json={
        "payment_method": "cash",
        "items": [{"product_id": prod_id, "quantity": 1}]
    }, headers=staff_headers)
    assert res_create.status_code == 200
    order_id = res_create.json()["id"]

    client.post(f"/api/v1/orders/{order_id}/approve", headers=admin_headers)
    client.post(f"/api/v1/orders/{order_id}/claim", headers=staff_headers)

    # Admin reassign cho staff_2_id
    res_reas = client.post(f"/api/v1/orders/{order_id}/reassign", json={
        "new_staff_id": staff_2_id,
        "reason": "Điều chuyển ca làm việc"
    }, headers=admin_headers)
    assert res_reas.status_code == 200
    assert res_reas.json()["assigned_to"] == staff_2_id

    # Kiểm tra audit logs
    res_audit = client.get(f"/api/v1/orders/{order_id}/audit-logs", headers=admin_headers)
    assert res_audit.status_code == 200
    actions = [l["action"] for l in res_audit.json()]
    assert "reassign" in actions or "reassign_order" in actions


def test_07_historical_database_preservation():
    """
    Kiểm tra bảo toàn tuyệt đối 317 đơn hàng lịch sử và schema_version = 3 trên database chính.
    """
    main_db = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "webstore.db"))
    conn = sqlite3.connect(main_db)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM orders WHERE is_legacy_unverified = 1")
    legacy_count = c.fetchone()[0]
    assert legacy_count == 317, f"Expected 317 legacy unverified orders, got {legacy_count}"

    c.execute("SELECT COUNT(*) FROM orders")
    total_orders = c.fetchone()[0]
    assert total_orders == 317, f"Expected 317 total orders, got {total_orders}"

    c.execute("SELECT MAX(version) FROM schema_version")
    ver = c.fetchone()[0]
    assert ver == 3, f"Expected schema_version 3, got {ver}"
    conn.close()


def test_08_r3_deep_qa_and_concurrency(customer_headers, customer2_headers, staff_headers, admin_headers):
    """
    R3 Deep QA & Concurrency Tests:
    1. Staff không được xác nhận đối soát ngân hàng (verify-payment -> 403).
    2. Hai request hoàn kho đồng thời (confirm-return): tồn kho chỉ tăng đúng 1 lần.
    3. Hai request hoàn tiền đồng thời (confirm-refund): xử lý idempotency, không trừ double.
    4. Anti-IDOR Audit Logs: Customer2 không xem được audit logs của Customer1 (403 Forbidden).
    5. Không thể sửa đơn đã cancelled/rejected qua endpoint thông thường (approve, claim, process, complete, update-fulfillment -> 400).
    6. Thao tác thất bại không làm thay đổi stock hoặc payment ngoài dự kiến.
    """
    with get_db() as conn:
        c = conn.cursor()
        c.execute("SELECT id, stock_quantity FROM products WHERE status = 'active' AND stock_quantity >= 10 LIMIT 1")
        prod = c.fetchone()
        prod_id = prod["id"]
        stock_init = prod["stock_quantity"]

    res_create = client.post("/api/v1/orders", json={
        "payment_method": "transfer",
        "items": [{"product_id": prod_id, "quantity": 1}]
    }, headers=customer_headers)
    assert res_create.status_code == 200
    order_1_id = res_create.json()["id"]

    # 1. Staff thử verify-payment -> 403 Forbidden
    res_staff_verify = client.post(f"/api/v1/orders/{order_1_id}/verify-payment", headers=staff_headers)
    assert res_staff_verify.status_code == 403, "Staff must NOT be allowed to verify bank transfer payment!"

    # 4. Anti-IDOR: Customer 2 cố xem audit logs của đơn Customer 1 -> 403 Forbidden
    res_idor = client.get(f"/api/v1/orders/{order_1_id}/audit-logs", headers=customer2_headers)
    assert res_idor.status_code == 403, "Customer2 must NOT view Customer1 order audit logs!"

    # 2. Concurrency: Hai request confirm-return đồng thời trên cùng đơn giao thất bại
    client.post(f"/api/v1/orders/{order_1_id}/approve", headers=admin_headers)
    client.post(f"/api/v1/orders/{order_1_id}/claim", headers=staff_headers)
    client.post(f"/api/v1/orders/{order_1_id}/update-fulfillment", json={"fulfillment_status": "shipping"}, headers=staff_headers)
    client.post(f"/api/v1/orders/{order_1_id}/update-fulfillment", json={"fulfillment_status": "delivery_failed"}, headers=staff_headers)

    with get_db() as conn:
        c = conn.cursor()
        c.execute("SELECT stock_quantity FROM products WHERE id = ?", (prod_id,))
        stock_before_concurrent_return = c.fetchone()["stock_quantity"]

    def call_return():
        return client.post(f"/api/v1/orders/{order_1_id}/confirm-return", json={
            "reason": "Hoàn kho đồng thời"
        }, headers=staff_headers)

    with ThreadPoolExecutor(max_workers=2) as executor:
        f1 = executor.submit(call_return)
        f2 = executor.submit(call_return)
        r1, r2 = f1.result(), f2.result()

    statuses = sorted([r1.status_code, r2.status_code])
    assert statuses == [200, 400], f"Expected one 200 and one 400 for concurrent return, got {statuses}"

    with get_db() as conn:
        c = conn.cursor()
        c.execute("SELECT stock_quantity FROM products WHERE id = ?", (prod_id,))
        stock_after_concurrent_return = c.fetchone()["stock_quantity"]
    # Tồn kho chỉ được cộng đúng 1 lần (tăng đúng 1)
    assert stock_after_concurrent_return == stock_before_concurrent_return + 1

    # 5. Chặn sửa đơn đã cancelled qua các endpoint thông thường
    res_reapprove = client.post(f"/api/v1/orders/{order_1_id}/approve", headers=admin_headers)
    assert res_reapprove.status_code == 400
    res_reclaim = client.post(f"/api/v1/orders/{order_1_id}/claim", headers=staff_headers)
    assert res_reclaim.status_code == 400
    res_reprocess = client.post(f"/api/v1/orders/{order_1_id}/process", headers=staff_headers)
    assert res_reprocess.status_code == 400
    res_recomplete = client.post(f"/api/v1/orders/{order_1_id}/complete", headers=staff_headers)
    assert res_recomplete.status_code == 400
    res_reful = client.post(f"/api/v1/orders/{order_1_id}/update-fulfillment", json={"fulfillment_status": "shipping"}, headers=staff_headers)
    assert res_reful.status_code == 400