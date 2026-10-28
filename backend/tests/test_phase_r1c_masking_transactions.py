import os
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.core.config import settings
from app.core.database import get_db, get_db_transaction
from app.core.rate_limiter import register_rate_limiter, login_rate_limiter


@pytest.fixture
def client():
    register_rate_limiter.reset()
    login_rate_limiter.reset()
    with TestClient(app) as test_client:
        yield test_client
    register_rate_limiter.reset()
    login_rate_limiter.reset()


def get_token(client: TestClient, username: str, password: str = None) -> str:
    if password is None:
        passwords = {
            "superadmin": "SuperAdmin@123",
            "admin": "Admin@123",
            "staff": "Staff@123",
            "customer": "Customer@123",
            "customer2": "Customer@123",
        }
        password = passwords.get(username, "Password@123")
    res = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert res.status_code == 200, f"Login failed for {username}: {res.text}"
    return res.json()["access_token"]


# ===========================================================================
# 1. BACKEND DATA MASKING CHO STAFF & ADMIN ACCESS
# ===========================================================================

def test_01_staff_get_customers_success_when_authorized(client: TestClient):
    """1. Staff GET /api/v1/customers thành công khi có token hợp lệ (HTTP 200)"""
    token = get_token(client, "staff")
    res = client.get("/api/v1/customers", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200, f"Staff không gọi được customers: {res.text}"
    data = res.json()
    assert isinstance(data, list)
    assert len(data) > 0, "Danh sách khách hàng không được rỗng"


def test_02_staff_response_does_not_contain_full_email(client: TestClient):
    """2. Staff response không chứa email đầy đủ (email bị mask thành 'x***@domain')"""
    token = get_token(client, "staff")
    res = client.get("/api/v1/customers", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    customers = res.json()

    for cus in customers:
        email = cus.get("email")
        if email:
            # Email phải chứa '***' và không được hiển thị nguyên vẹn tiền tố
            assert "***" in email, f"LỖ HỔNG PII: Email của khách không được mask: {email}"
            assert not email.startswith("an.nguyen@"), f"Lộ email đầy đủ: {email}"


def test_03_staff_response_does_not_contain_detailed_address(client: TestClient):
    """3. Staff response không chứa địa chỉ chi tiết (address là None để tránh lộ số nhà)"""
    token = get_token(client, "staff")
    res = client.get("/api/v1/customers", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    customers = res.json()

    for cus in customers:
        address = cus.get("address")
        assert address is None, f"LỖ HỔNG PII: Địa chỉ chi tiết bị rò rỉ cho Staff: {address}"


def test_04_staff_cannot_get_full_pii_via_detail_endpoint(client: TestClient):
    """4. Staff không thể lấy PII đầy đủ qua endpoint chi tiết GET /api/v1/customers/{id}"""
    # Lấy ID của một khách hàng có địa chỉ và email trong DB
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, email, address FROM customers WHERE email IS NOT NULL AND address IS NOT NULL LIMIT 1")
        row = cursor.fetchone()
        assert row is not None
        cus_id, raw_email, raw_address = row["id"], row["email"], row["address"]

    token = get_token(client, "staff")
    res = client.get(f"/api/v1/customers/{cus_id}", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    detail = res.json()

    assert detail.get("address") is None, f"LỖ HỔNG: Staff xem chi tiết thấy địa chỉ: {detail.get('address')}"
    if detail.get("email"):
        assert "***" in detail["email"], f"LỖ HỔNG: Staff xem chi tiết thấy email gốc: {detail.get('email')}"
        assert detail["email"] != raw_email, f"Lộ email gốc: {raw_email}"
    assert detail.get("user_id") is None, "LỖ HỔNG: Staff xem chi tiết thấy user_id nội bộ"


def test_05_staff_search_endpoint_does_not_leak_forbidden_pii(client: TestClient):
    """5. Staff không nhận được PII bị cấm qua endpoint tìm kiếm (Query param ?search=...)"""
    token = get_token(client, "staff")
    res = client.get("/api/v1/customers?search=Nguyen", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    results = res.json()

    for cus in results:
        assert cus.get("address") is None, "Địa chỉ chi tiết bị lộ khi search"
        if cus.get("email"):
            assert "***" in cus["email"], "Email không được mask khi search"
        assert cus.get("user_id") is None, "user_id bị lộ khi search"


def test_06_admin_receives_full_management_data(client: TestClient):
    """6. Admin nhận dữ liệu quản trị đầy đủ (email gốc, địa chỉ gốc, user_id)"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, email, address FROM customers WHERE email IS NOT NULL AND address IS NOT NULL LIMIT 1")
        row = cursor.fetchone()
        cus_id, raw_email, raw_address = row["id"], row["email"], row["address"]

    token = get_token(client, "admin")
    res = client.get(f"/api/v1/customers/{cus_id}", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    detail = res.json()

    assert detail.get("email") == raw_email, "Admin không nhận được email đầy đủ"
    assert detail.get("address") == raw_address, "Admin không nhận được địa chỉ đầy đủ"
    assert "user_id" in detail, "Admin thiếu trường user_id trong hồ sơ"


def test_07_superadmin_receives_full_management_data(client: TestClient):
    """7. SuperAdmin nhận dữ liệu quản trị đầy đủ phù hợp quyền cao nhất"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, email, address FROM customers WHERE email IS NOT NULL AND address IS NOT NULL LIMIT 1")
        row = cursor.fetchone()
        cus_id, raw_email, raw_address = row["id"], row["email"], row["address"]

    token = get_token(client, "superadmin")
    res = client.get(f"/api/v1/customers/{cus_id}", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    detail = res.json()

    assert detail.get("email") == raw_email, "SuperAdmin không nhận được email đầy đủ"
    assert detail.get("address") == raw_address, "SuperAdmin không nhận được địa chỉ đầy đủ"


def test_08_customer_cannot_read_other_customer_profiles(client: TestClient):
    """8. Customer không đọc được hồ sơ người khác (403 IDOR & 403 List customers)"""
    # Tạo hoặc lấy Customer 1
    token_cus = get_token(client, "customer")

    # 1. Customer cố đọc danh sách khách hàng toàn hệ thống -> 403 Forbidden
    res_list = client.get("/api/v1/customers", headers={"Authorization": f"Bearer {token_cus}"})
    assert res_list.status_code == 403, f"Customer không được phép xem danh sách khách hàng: {res_list.status_code}"

    # 2. Customer cố đọc chi tiết một khách hàng khác qua ID -> 403 Forbidden
    with get_db() as conn:
        cursor = conn.cursor()
        # Tìm ID của khách hàng khác (không gắn với tài khoản 'customer')
        cursor.execute("SELECT c.id FROM customers c JOIN users u ON u.username != 'customer' AND c.user_id = u.id LIMIT 1")
        row = cursor.fetchone()
        other_cus_id = row["id"] if row else 99999

    res_detail = client.get(f"/api/v1/customers/{other_cus_id}", headers={"Authorization": f"Bearer {token_cus}"})
    assert res_detail.status_code == 403, f"IDOR Vulnerability: Customer đọc được hồ sơ người khác: {res_detail.text}"

    # 3. Customer đọc hồ sơ của chính mình qua /me -> 200 OK đầy đủ
    res_me = client.get("/api/v1/customers/me", headers={"Authorization": f"Bearer {token_cus}"})
    assert res_me.status_code == 200, f"Customer không xem được hồ sơ của mình: {res_me.text}"


def test_09_guest_blocked_from_accessing_customer_data(client: TestClient):
    """9. Guest (chưa xác thực) bị từ chối truy cập toàn bộ dữ liệu khách hàng (401 Unauthorized)"""
    res_list = client.get("/api/v1/customers")
    assert res_list.status_code == 401

    res_detail = client.get("/api/v1/customers/1")
    assert res_detail.status_code == 401

    res_me = client.get("/api/v1/customers/me")
    assert res_me.status_code == 401


# ===========================================================================
# 2. DML NORMALIZATION & TRANSACTION SAFETY — PRODUCTS.PY
# ===========================================================================

def test_10_create_category_success_with_transaction(client: TestClient):
    """10. Tạo Category thành công qua giao dịch DML chuẩn hóa"""
    token = get_token(client, "admin")
    payload = {
        "name": "Danh Mục R1C Test",
        "code": "CAT-R1C-01",
        "description": "Category created during Phase R1C test"
    }
    res = client.post("/api/v1/categories", json=payload, headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200, f"Tạo category thất bại: {res.text}"
    data = res.json()
    assert data["code"] == "CAT-R1C-01"
    assert data["name"] == "Danh Mục R1C Test"

    # Kiểm tra tồn tại thực tế trong DB
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, name FROM categories WHERE code = ?", ("CAT-R1C-01",))
        row = cursor.fetchone()
        assert row is not None
        assert row["name"] == "Danh Mục R1C Test"


def test_11_update_category_success_with_transaction(client: TestClient):
    """11. Sửa Category thành công qua giao dịch DML atomic"""
    token = get_token(client, "admin")
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM categories WHERE code = 'CAT-R1C-01'")
        cat_id = cursor.fetchone()["id"]

    update_payload = {
        "name": "Danh Mục R1C Đã Cập Nhật",
        "description": "Updated description"
    }
    res = client.put(f"/api/v1/categories/{cat_id}", json=update_payload, headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200, f"Cập nhật category thất bại: {res.text}"
    assert res.json()["name"] == "Danh Mục R1C Đã Cập Nhật"


def test_12_create_product_success_with_transaction(client: TestClient):
    """12. Tạo Product thành công với DML transaction nguyên tử"""
    token = get_token(client, "admin")
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM categories WHERE code = 'CAT-R1C-01'")
        cat_id = cursor.fetchone()["id"]

    payload = {
        "sku": "PROD-R1C-01",
        "name": "Sản Phẩm Test R1C",
        "category_id": cat_id,
        "cost_price": 50000.0,
        "selling_price": 85000.0,
        "stock_quantity": 20,
        "min_stock_alert": 5,
        "unit": "cái",
        "status": "active",
        "description": "Sản phẩm test Phase R1C"
    }
    res = client.post("/api/v1/products", json=payload, headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200, f"Tạo sản phẩm thất bại: {res.text}"
    data = res.json()
    assert data["sku"] == "PROD-R1C-01"
    assert data["selling_price"] == 85000.0


def test_13_update_product_success_with_transaction(client: TestClient):
    """13. Sửa Product thành công qua transaction get_db_transaction()"""
    token = get_token(client, "admin")
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM products WHERE sku = 'PROD-R1C-01'")
        prod_id = cursor.fetchone()["id"]

    update_payload = {
        "selling_price": 95000.0,
        "stock_quantity": 25
    }
    res = client.put(f"/api/v1/products/{prod_id}", json=update_payload, headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200, f"Cập nhật sản phẩm thất bại: {res.text}"
    data = res.json()
    assert data["selling_price"] == 95000.0
    assert data["stock_quantity"] == 25


def test_14_rollback_on_error_during_write_transaction(client: TestClient):
    """14. Giao dịch ghi lỗi được tự động rollback, không để lại dữ liệu dở dang"""
    token = get_token(client, "admin")

    # Thử tạo sản phẩm với SKU trùng PROD-R1C-01
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM categories LIMIT 1")
        cat_id = cursor.fetchone()["id"]
        cursor.execute("SELECT COUNT(*) as cnt FROM products")
        count_before = cursor.fetchone()["cnt"]

    duplicate_payload = {
        "sku": "PROD-R1C-01",  # Trùng SKU
        "name": "Sản Phẩm Duplicate",
        "category_id": cat_id,
        "cost_price": 10000.0,
        "selling_price": 20000.0,
        "stock_quantity": 10,
        "min_stock_alert": 2,
        "unit": "cái",
        "status": "active"
    }
    res = client.post("/api/v1/products", json=duplicate_payload, headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 400, "Phải từ chối SKU trùng"
    assert "đã tồn tại" in res.text

    # Xác nhận số lượng sản phẩm trong DB không tăng (không bị partial write)
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) as cnt FROM products")
        count_after = cursor.fetchone()["cnt"]
        assert count_after == count_before, "Lỗi Rollback: Số sản phẩm bị thay đổi dù transaction bị hủy"


def test_15_no_partial_write_on_multi_step_failure():
    """15. Kiểm tra trực tiếp get_db_transaction(): Rollback toàn bộ khi bước sau phát sinh lỗi"""
    sku_unique = "ATOMIC-TEST-FAIL"

    with pytest.raises(RuntimeError):
        with get_db_transaction() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO categories (name, code, description) VALUES (?, ?, ?)",
                ("Cat Atomic Test", "CAT-FAIL-01", "desc")
            )
            cat_id = cursor.lastrowid
            cursor.execute(
                """INSERT INTO products (sku, name, category_id, cost_price, selling_price, stock_quantity)
                   VALUES (?, ?, ?, 10, 20, 5)""",
                (sku_unique, "Atomic Prod", cat_id)
            )
            # Cố tình ném Exception giả lập sự cố hệ thống giữa transaction
            raise RuntimeError("Mô phỏng sự cố giữa giao dịch nhiều bước")

    # Xác nhận cả category lẫn product đều bị rollback sạch sẽ
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM categories WHERE code = 'CAT-FAIL-01'")
        assert cursor.fetchone() is None, "Category không được rollback"
        cursor.execute("SELECT id FROM products WHERE sku = ?", (sku_unique,))
        assert cursor.fetchone() is None, "Product không được rollback, phát sinh partial write"


def test_16_foreign_key_constraints_enforced_and_preserved(client: TestClient):
    """16. Ràng buộc khóa ngoại được bảo toàn (tạo product với category_id không tồn tại bị 400; xóa category đang có sản phẩm bị 400)"""
    token = get_token(client, "admin")

    # 1. Tạo sản phẩm với category_id không tồn tại
    invalid_cat_payload = {
        "sku": "PROD-FK-TEST",
        "name": "FK Test Product",
        "category_id": 999999,  # Không tồn tại
        "cost_price": 10000.0,
        "selling_price": 20000.0,
        "stock_quantity": 10,
        "min_stock_alert": 2,
        "unit": "cái",
        "status": "active"
    }
    res = client.post("/api/v1/products", json=invalid_cat_payload, headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 400, f"Phải từ chối category_id không tồn tại: {res.text}"
    assert "không tồn tại" in res.text

    # 2. Xóa danh mục đang chứa sản phẩm PROD-R1C-01 -> Phải bị từ chối 400
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM categories WHERE code = 'CAT-R1C-01'")
        cat_id = cursor.fetchone()["id"]

    res_del = client.delete(f"/api/v1/categories/{cat_id}", headers={"Authorization": f"Bearer {token}"})
    assert res_del.status_code == 400, f"Phải từ chối xóa danh mục đang có sản phẩm: {res_del.text}"
    assert "Không thể xóa danh mục đang có sản phẩm" in res_del.text


def test_17_no_test_data_in_production_database():
    """17. Cơ sở dữ liệu webstore.db gốc hoàn toàn không bị ghi bất kỳ dữ liệu test nào"""
    backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    prod_db_path = os.path.join(backend_dir, "webstore.db")
    if os.path.exists(prod_db_path):
        import sqlite3
        conn = sqlite3.connect(prod_db_path)
        cursor = conn.cursor()

        # Kiểm tra không có dữ liệu test của R1C trong webstore.db
        cursor.execute("SELECT id FROM categories WHERE code LIKE 'CAT-R1C%'")
        assert cursor.fetchone() is None, "Dữ liệu test category lọt vào webstore.db"

        cursor.execute("SELECT id FROM products WHERE sku LIKE 'PROD-R1C%'")
        assert cursor.fetchone() is None, "Dữ liệu test product lọt vào webstore.db"
        conn.close()
