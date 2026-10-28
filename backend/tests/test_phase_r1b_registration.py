import os
import re
import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient

from app.main import app
from app.core.config import settings
from app.core.database import get_db, get_db_transaction
from app.core.rate_limiter import register_rate_limiter, login_rate_limiter


@pytest.fixture
def client():
    # Reset cả login và register rate limiters trước mỗi test để bảo đảm tính tất định
    register_rate_limiter.reset()
    login_rate_limiter.reset()
    with TestClient(app) as test_client:
        yield test_client
    register_rate_limiter.reset()
    login_rate_limiter.reset()


def get_token(client: TestClient, username: str, password: str) -> str:
    res = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert res.status_code == 200, f"Login failed for {username}: {res.text}"
    return res.json()["access_token"]


# ===========================================================================
# 1. PUBLIC REGISTRATION & ATOMIC PROFILE CREATION
# ===========================================================================

def test_01_guest_can_register_customer_successfully(client: TestClient):
    """1. Guest có thể tự đăng ký tài khoản Khách hàng thành công (HTTP 201 Created)"""
    payload = {
        "username": "new_guest_01",
        "password": "Password@123",
        "full_name": "Nguyễn Văn Khách",
        "phone": "0981112233",
        "email": "new_guest01@example.com",
        "address": "123 Đường Số 1, Quận 1, TP.HCM"
    }
    res = client.post("/api/v1/auth/register", json=payload)
    assert res.status_code == 201, f"Đăng ký thất bại: {res.text}"
    data = res.json()

    assert data["username"] == "new_guest_01"
    assert data["full_name"] == "Nguyễn Văn Khách"
    assert data["role"] == "customer"
    assert data["phone"] == "0981112233"
    assert data["email"] == "new_guest01@example.com"
    assert data["address"] == "123 Đường Số 1, Quận 1, TP.HCM"
    assert "password_hash" not in data, "LỖ HỔNG: password_hash bị rò rỉ trong response đăng ký"
    assert "access_token" not in data, "Không được tự ý cấp JWT đặc quyền khi chưa qua login"


def test_02_new_user_has_actual_role_customer(client: TestClient):
    """2. Tài khoản mới tạo thực sự mang role 'customer' trong cơ sở dữ liệu và JWT"""
    payload = {
        "username": "new_guest_02",
        "password": "Password@123",
        "full_name": "Trần Thị Khách",
        "phone": "0982223344",
        "email": "new_guest02@example.com"
    }
    res_reg = client.post("/api/v1/auth/register", json=payload)
    assert res_reg.status_code == 201

    # Kiểm tra trong DB
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, role, is_active FROM users WHERE username = ?", ("new_guest_02",))
        user_row = cursor.fetchone()
        assert user_row is not None
        assert user_row["role"] == "customer"
        assert user_row["is_active"] == 1

    # Đăng nhập và kiểm tra JWT payload
    token = get_token(client, "new_guest_02", "Password@123")
    res_me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert res_me.status_code == 200
    assert res_me.json()["role"] == "customer"


def test_03_user_and_customer_profile_linked_accurately(client: TestClient):
    """3. Bản ghi trong users và bản ghi trong customers được liên kết chính xác qua user_id"""
    payload = {
        "username": "new_guest_03",
        "password": "Password@123",
        "full_name": "Lê Văn Khách",
        "phone": "0983334455",
        "email": "new_guest03@example.com"
    }
    res = client.post("/api/v1/auth/register", json=payload)
    assert res.status_code == 201
    data = res.json()
    user_id = data["id"]
    cust_id = data["customer_id"]

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, user_id, customer_code, group_name FROM customers WHERE id = ?", (cust_id,))
        cust_row = cursor.fetchone()
        assert cust_row is not None
        assert cust_row["user_id"] == user_id, "user_id trong bảng customers không khớp với bảng users"
        assert cust_row["group_name"] == "retail"
        assert cust_row["customer_code"].startswith("CUS-")


def test_04_duplicate_username_returns_409(client: TestClient):
    """4. Đăng ký trùng username phải trả về HTTP 409 Conflict"""
    payload = {
        "username": "duplicate_user_test",
        "password": "Password@123",
        "full_name": "Người Dùng A",
        "phone": "0984445566",
        "email": "new_dup_a@example.com"
    }
    res1 = client.post("/api/v1/auth/register", json=payload)
    assert res1.status_code == 201

    # Đăng ký lại cùng username với phone/email khác
    payload2 = {
        "username": "duplicate_user_test",
        "password": "Password@123",
        "full_name": "Người Dùng B",
        "phone": "0984445567",
        "email": "new_dup_b@example.com"
    }
    res2 = client.post("/api/v1/auth/register", json=payload2)
    assert res2.status_code == 409
    assert "Tên đăng nhập" in res2.json()["detail"]


def test_05_duplicate_phone_or_email_returns_409(client: TestClient):
    """5. Đăng ký trùng phone hoặc email đã có trong bảng customers phải trả về HTTP 409 Conflict"""
    # 5a. Trùng số điện thoại của khách hàng đã có trong database seed (KH-001 có phone 0987654321)
    payload_dup_seeded_phone = {
        "username": "dup_phone_seeded_user",
        "password": "Password@123",
        "full_name": "Người Trùng Số",
        "phone": "0987654321",  # Phone đã có sẵn từ KH-001
        "email": "unique_email_123@example.com"
    }
    res_dup_seeded = client.post("/api/v1/auth/register", json=payload_dup_seeded_phone)
    assert res_dup_seeded.status_code == 409
    assert "số điện thoại" in res_dup_seeded.json()["detail"].lower()

    # 5b. Trùng email của khách hàng đã có trong database seed (KH-001 có email an.nguyen@example.com)
    payload_dup_seeded_email = {
        "username": "dup_email_seeded_user",
        "password": "Password@123",
        "full_name": "Người Trùng Email",
        "phone": "0985559988",
        "email": "an.nguyen@example.com"  # Email đã có sẵn từ KH-001
    }
    res_dup_email = client.post("/api/v1/auth/register", json=payload_dup_seeded_email)
    assert res_dup_email.status_code == 409
    assert "email" in res_dup_email.json()["detail"].lower()


def test_06_privilege_escalation_role_payload_rejected(client: TestClient):
    """6. Gửi role admin/superadmin/staff trong payload đăng ký phải bị từ chối dứt khoát"""
    for malicious_role in ["admin", "superadmin", "staff", "manager", "root"]:
        payload = {
            "username": f"hacker_{malicious_role}",
            "password": "Password@123",
            "full_name": "Hacker",
            "phone": "0986667788",
            "email": f"hacker_{malicious_role}@example.com",
            "role": malicious_role
        }
        res = client.post("/api/v1/auth/register", json=payload)
        assert res.status_code in (400, 422), f"LỖ HỔNG: Client gửi role={malicious_role} không bị từ chối!"
        assert "vai trò" in res.json()["detail"].lower() or "role" in res.json()["detail"].lower()


def test_07_cannot_set_internal_admin_fields(client: TestClient):
    """7. Client không được phép tự chỉ định user_id, customer_id hoặc is_active"""
    for bad_field, bad_val in [("user_id", 1), ("customer_id", 1), ("is_active", False)]:
        payload = {
            "username": f"tamper_{bad_field}",
            "password": "Password@123",
            "full_name": "Tamper Test",
            "phone": "0987778899",
            "email": f"tamper_{bad_field}@example.com",
            bad_field: bad_val
        }
        res = client.post("/api/v1/auth/register", json=payload)
        assert res.status_code in (400, 422), f"LỖ HỔNG: Client truyền {bad_field} nhưng không bị chặn!"


def test_08_malformed_input_rejected_by_validation(client: TestClient):
    """8. Request sai định dạng (username ngắn/kí tự đặc biệt, password ngắn, phone/email sai) bị từ chối"""
    # Username quá ngắn
    res = client.post("/api/v1/auth/register", json={
        "username": "ab",
        "password": "Password@123",
        "full_name": "Test",
        "phone": "0911111111",
        "email": "test@example.com"
    })
    assert res.status_code in (400, 422)

    # Username chứa ký tự đặc biệt nguy hiểm
    res = client.post("/api/v1/auth/register", json={
        "username": "user<script>",
        "password": "Password@123",
        "full_name": "Test",
        "phone": "0911111111",
        "email": "test@example.com"
    })
    assert res.status_code in (400, 422)

    # Password quá ngắn (< 6 ký tự)
    res = client.post("/api/v1/auth/register", json={
        "username": "user_short_pwd",
        "password": "123",
        "full_name": "Test",
        "phone": "0911111111",
        "email": "test@example.com"
    })
    assert res.status_code in (400, 422)

    # Phone không đúng định dạng VN (chữ cái hoặc thiếu số)
    res = client.post("/api/v1/auth/register", json={
        "username": "user_bad_phone",
        "password": "Password@123",
        "full_name": "Test",
        "phone": "12345",
        "email": "test@example.com"
    })
    assert res.status_code in (400, 422)

    # Email sai định dạng
    res = client.post("/api/v1/auth/register", json={
        "username": "user_bad_email",
        "password": "Password@123",
        "full_name": "Test",
        "phone": "0911111111",
        "email": "invalid_email_format"
    })
    assert res.status_code in (400, 422)


def test_09_registration_rate_limiting_triggers_429(client: TestClient):
    """9. Registration rate limit: Tối đa 3 lượt đăng ký / IP / 10 phút, lượt thứ 4 trả HTTP 429"""
    register_rate_limiter.reset()

    # Thực hiện 3 lượt đăng ký thành công
    for i in range(1, 4):
        payload = {
            "username": f"rate_limit_user_{i}",
            "password": "Password@123",
            "full_name": f"User {i}",
            "phone": f"091230000{i}",
            "email": f"ratelimit_{i}@example.com"
        }
        res = client.post("/api/v1/auth/register", json=payload)
        assert res.status_code == 201, f"Lượt đăng ký thứ {i} phải thành công"

    # Lượt thứ 4 từ cùng client IP phải bị chặn HTTP 429 Too Many Requests
    payload_4 = {
        "username": "rate_limit_user_4",
        "password": "Password@123",
        "full_name": "User 4",
        "phone": "0912300004",
        "email": "ratelimit_4@example.com"
    }
    res_blocked = client.post("/api/v1/auth/register", json=payload_4)
    assert res_blocked.status_code == 429, "Lượt thứ 4 phải trả về HTTP 429 Too Many Requests"
    assert "Retry-After" in res_blocked.headers


def test_10_atomic_rollback_when_profile_creation_fails(client: TestClient):
    """10. Tính nguyên tử: Nếu bước tạo Customer profile gặp sự cố, User insert phải được ROLLBACK hoàn toàn"""
    register_rate_limiter.reset()

    # Thử đăng ký với email đã có sẵn của user khác (an.nguyen@example.com từ KH-001)
    res = client.post("/api/v1/auth/register", json={
        "username": "rollback_test_user",
        "password": "Password@123",
        "full_name": "Rollback Test",
        "phone": "0989998877",
        "email": "an.nguyen@example.com"  # Email này đã tồn tại trong database
    })
    assert res.status_code == 409

    # Xác nhận username rollback_test_user KHÔNG HỀ tồn tại trong users
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM users WHERE username = 'rollback_test_user'")
        assert cursor.fetchone() is None, "LỖ HỔNG ATOMICITY: User vẫn bị tạo dở dang dù đăng ký thất bại!"


# ===========================================================================
# 2. ANTI-IDOR TRONG CREATE ORDER
# ===========================================================================

def test_11_customer_creates_own_order_status_is_pending(client: TestClient):
    """11. Customer tạo đơn hàng: customer_id được gán tự động chính chủ và trạng thái bắt buộc là 'pending'"""
    # Lấy sản phẩm còn tồn kho (> 0)
    res_prod = client.get("/api/v1/public/products")
    in_stock_products = [p for p in res_prod.json() if p.get("stock_quantity", 0) > 0]
    assert len(in_stock_products) > 0, "Phải có ít nhất 1 sản phẩm còn tồn kho"
    prod_id = in_stock_products[0]["id"]

    token = get_token(client, "customer", "Customer@123")
    headers = {"Authorization": f"Bearer {token}"}

    order_payload = {
        "payment_method": "transfer",
        "items": [{"product_id": prod_id, "quantity": 1}],
        "status": "completed"  # Cố tình gửi 'completed' để kiểm tra xem có bị ghi đè không
    }
    res_order = client.post("/api/v1/orders", json=order_payload, headers=headers)
    assert res_order.status_code == 200, f"Tạo đơn thất bại: {res_order.text}"
    order_data = res_order.json()

    # Trạng thái bắt buộc phải là pending
    assert order_data["status"] == "pending", "LỖ HỔNG: Đơn của Customer không được khởi tạo ở trạng thái pending!"

    # Customer ID phải được gán chính xác theo profile của customer
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM customers WHERE user_id = (SELECT id FROM users WHERE username = 'customer')")
        expected_cust_id = cursor.fetchone()["id"]
        assert order_data["customer_id"] == expected_cust_id


def test_12_customer_a_sending_customer_id_of_b_rejected_403(client: TestClient):
    """12. Customer A gửi customer_id của Customer B trong payload phải bị từ chối HTTP 403 Forbidden"""
    res_prod = client.get("/api/v1/public/products")
    in_stock_products = [p for p in res_prod.json() if p.get("stock_quantity", 0) > 0]
    prod_id = in_stock_products[0]["id"]

    # Đăng nhập bằng tài khoản "customer"
    token_a = get_token(client, "customer", "Customer@123")
    headers_a = {"Authorization": f"Bearer {token_a}"}

    # Tìm customer_id của customer2
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM customers WHERE user_id = (SELECT id FROM users WHERE username = 'customer2')")
        cust_b_row = cursor.fetchone()
        assert cust_b_row is not None
        cust_b_id = cust_b_row["id"]

    # Customer A cố tình chèn customer_id của Customer B
    malicious_payload = {
        "customer_id": cust_b_id,
        "payment_method": "cash",
        "items": [{"product_id": prod_id, "quantity": 1}]
    }
    res = client.post("/api/v1/orders", json=malicious_payload, headers=headers_a)
    assert res.status_code == 403, f"LỖ HỔNG IDOR: Customer A gửi customer_id={cust_b_id} nhưng không bị chặn 403!"
    assert "IDOR" in res.json()["detail"] or "khách hàng khác" in res.json()["detail"].lower()


def test_13_customer_without_profile_cannot_impersonate_others(client: TestClient):
    """13. Customer không có hồ sơ liên kết hợp lệ không thể mạo danh ID người khác để tạo đơn (trả 400)"""
    res_prod = client.get("/api/v1/public/products")
    in_stock_products = [p for p in res_prod.json() if p.get("stock_quantity", 0) > 0]
    prod_id = in_stock_products[0]["id"]

    # Tạo một user role customer mồ côi (không có customer profile)
    with get_db_transaction() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM users WHERE username = 'orphan_customer'")
        if not cursor.fetchone():
            from app.core.security import hash_password
            cursor.execute(
                "INSERT INTO users (username, password_hash, full_name, role) VALUES ('orphan_customer', ?, 'Orphan', 'customer')",
                (hash_password("Password@123"),)
            )

    token_orphan = get_token(client, "orphan_customer", "Password@123")
    headers_orphan = {"Authorization": f"Bearer {token_orphan}"}

    # Thử tạo đơn mượn customer_id=1
    res = client.post("/api/v1/orders", json={
        "customer_id": 1,
        "payment_method": "cash",
        "items": [{"product_id": prod_id, "quantity": 1}]
    }, headers=headers_orphan)

    assert res.status_code == 400, "Customer không có hồ sơ liên kết phải bị chặn 400 Bad Request"
    assert "hồ sơ khách hàng" in res.json()["detail"].lower()


# ===========================================================================
# 3. KIỂM TRA TÍNH TOÀN VẸN CƠ SỞ DỮ LIỆU
# ===========================================================================

def test_14_no_test_data_in_production_database():
    """14. Đảm bảo toàn bộ quá trình test KHÔNG ghi dữ liệu vào backend/webstore.db"""
    backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    prod_db_path = os.path.join(backend_dir, "webstore.db")

    assert os.path.exists(prod_db_path), "File webstore.db gốc phải tồn tại"
    # Kiểm tra DATABASE_PATH hiện tại của settings đang trỏ vào test DB
    assert "test" in settings.DATABASE_PATH.lower(), "settings.DATABASE_PATH phải trỏ vào test database"
