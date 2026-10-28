import os
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.core.config import Settings, validate_boot_safety
from app.core.rate_limiter import login_rate_limiter


@pytest.fixture
def client():
    # Reset login rate limiter before each test to guarantee determinism
    login_rate_limiter.reset()
    with TestClient(app) as test_client:
        yield test_client
    login_rate_limiter.reset()


def get_token(client: TestClient, username: str, password: str) -> str:
    res = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert res.status_code == 200, f"Login failed for {username}: {res.text}"
    return res.json()["access_token"]


# ===========================================================================
# 1. BẢO VỆ GIÁ VỐN SẢN PHẨM (COST_PRICE PROTECTION)
# ===========================================================================

def test_customer_cannot_read_cost_price(client: TestClient):
    """1. Customer tuyệt đối KHÔNG nhận được trường cost_price trong JSON response"""
    token = get_token(client, "customer", "Customer@123")
    headers = {"Authorization": f"Bearer {token}"}

    # Danh sách sản phẩm
    res_list = client.get("/api/v1/products", headers=headers)
    assert res_list.status_code == 200
    products = res_list.json()
    assert len(products) > 0, "Phải có sản phẩm trong database test"
    for p in products:
        assert "cost_price" not in p, f"LỖ HỔNG: cost_price bị rò rỉ cho Customer trong sản phẩm {p.get('sku')}"
        # Đảm bảo các trường kinh doanh thiết yếu vẫn hiển thị bình thường
        assert "selling_price" in p
        assert "stock_quantity" in p
        assert "name" in p
        assert "sku" in p

    # Chi tiết sản phẩm
    prod_id = products[0]["id"]
    res_detail = client.get(f"/api/v1/products/{prod_id}", headers=headers)
    assert res_detail.status_code == 200
    detail = res_detail.json()
    assert "cost_price" not in detail, "LỖ HỔNG: cost_price bị rò rỉ cho Customer trong chi tiết sản phẩm"
    assert detail["selling_price"] > 0


def test_staff_cannot_read_cost_price(client: TestClient):
    """2. Staff (Thu ngân/Kho) tuyệt đối KHÔNG nhận được trường cost_price trong JSON response"""
    token = get_token(client, "staff", "Staff@123")
    headers = {"Authorization": f"Bearer {token}"}

    # Danh sách sản phẩm qua /products
    res_list = client.get("/api/v1/products", headers=headers)
    assert res_list.status_code == 200
    products = res_list.json()
    assert len(products) > 0
    for p in products:
        assert "cost_price" not in p, f"LỖ HỔNG: cost_price bị rò rỉ cho Staff trong sản phẩm {p.get('sku')}"

    # Chi tiết sản phẩm
    prod_id = products[0]["id"]
    res_detail = client.get(f"/api/v1/products/{prod_id}", headers=headers)
    assert res_detail.status_code == 200
    detail = res_detail.json()
    assert "cost_price" not in detail, "LỖ HỔNG: cost_price bị rò rỉ cho Staff trong chi tiết sản phẩm"


def test_guest_cannot_read_cost_price(client: TestClient):
    """3. Guest (chưa đăng nhập) chỉ nhận dữ liệu công khai, tuyệt đối không có cost_price"""
    # Endpoint /public/products
    res_pub = client.get("/api/v1/public/products")
    assert res_pub.status_code == 200
    for p in res_pub.json():
        assert "cost_price" not in p, "LỖ HỔNG: cost_price bị rò rỉ trên /public/products"

    # Endpoint /public/products/{id}
    first_id = res_pub.json()[0]["id"]
    res_pub_detail = client.get(f"/api/v1/public/products/{first_id}")
    assert res_pub_detail.status_code == 200
    assert "cost_price" not in res_pub_detail.json()

    # Endpoint /products không gửi header Authorization (Guest)
    res_no_auth = client.get("/api/v1/products")
    assert res_no_auth.status_code in (200, 401)
    if res_no_auth.status_code == 200:
        for p in res_no_auth.json():
            assert "cost_price" not in p, "LỖ HỔNG: cost_price bị rò rỉ cho Guest trên /products"


def test_admin_and_superadmin_can_read_cost_price(client: TestClient):
    """4. Admin và SuperAdmin giữ quyền xem giá vốn hợp lệ phục vụ kế toán & nhập hàng"""
    for role, user, pwd in [
        ("admin", "admin", "Admin@123"),
        ("superadmin", "superadmin", "SuperAdmin@123"),
    ]:
        token = get_token(client, user, pwd)
        headers = {"Authorization": f"Bearer {token}"}

        # Danh sách sản phẩm
        res = client.get("/api/v1/products", headers=headers)
        assert res.status_code == 200
        products = res.json()
        assert len(products) > 0
        has_cost_price = all("cost_price" in p for p in products)
        assert has_cost_price, f"{role.upper()} phải xem được cost_price trong danh sách sản phẩm"

        # Chi tiết sản phẩm
        prod_id = products[0]["id"]
        res_detail = client.get(f"/api/v1/products/{prod_id}", headers=headers)
        assert res_detail.status_code == 200
        detail = res_detail.json()
        assert "cost_price" in detail, f"{role.upper()} phải xem được cost_price trong chi tiết sản phẩm"
        assert isinstance(detail["cost_price"], (int, float))


def test_product_filtering_endpoints_do_not_leak_sensitive_fields(client: TestClient):
    """5. Endpoint danh sách khi tìm kiếm/lọc đa tiêu chí không rò rỉ cost_price cho Staff/Customer"""
    token = get_token(client, "staff", "Staff@123")
    headers = {"Authorization": f"Bearer {token}"}

    # Tìm kiếm theo tên
    res = client.get("/api/v1/products?search=tai", headers=headers)
    assert res.status_code == 200
    for p in res.json():
        assert "cost_price" not in p

    # Lọc theo khoảng giá
    res_price = client.get("/api/v1/products?min_price=100000&max_price=2000000", headers=headers)
    assert res_price.status_code == 200
    for p in res_price.json():
        assert "cost_price" not in p


# ===========================================================================
# 2. PRODUCTION SECRET_KEY BOOT SAFETY
# ===========================================================================

def test_production_rejects_boot_on_invalid_or_default_secret_key():
    """6. Môi trường Production bắt buộc từ chối boot khi SECRET_KEY mặc định, rỗng hoặc quá ngắn"""
    # Case 1: Dùng dev key mặc định
    with pytest.raises(RuntimeError) as exc_info:
        s = Settings(
            APP_ENV="production",
            SECRET_KEY="storeflow_dev_secret_key_super_secure_change_in_production_2026"
        )
        validate_boot_safety(s)
    assert "default development SECRET_KEY is still in use" in str(exc_info.value)

    # Case 2: SECRET_KEY rỗng
    with pytest.raises(RuntimeError) as exc_info:
        s = Settings(APP_ENV="production", SECRET_KEY="")
        validate_boot_safety(s)
    assert "SECRET_KEY is empty" in str(exc_info.value)

    # Case 3: SECRET_KEY quá ngắn (< 32 ký tự)
    with pytest.raises(RuntimeError) as exc_info:
        s = Settings(APP_ENV="production", SECRET_KEY="too_short_secret_key_123")
        validate_boot_safety(s)
    assert "Production SECRET_KEY is too short" in str(exc_info.value)


def test_development_boots_normally_with_valid_dev_config():
    """7. Môi trường Development/Testing boot bình thường với cấu hình dev hợp lệ"""
    # Dev mode với dev key
    s_dev = Settings(
        APP_ENV="development",
        SECRET_KEY="storeflow_dev_secret_key_super_secure_change_in_production_2026"
    )
    validate_boot_safety(s_dev)  # Không được raise ngoại lệ

    # Testing mode
    s_test = Settings(APP_ENV="testing", SECRET_KEY="any_test_key")
    validate_boot_safety(s_test)  # Không được raise ngoại lệ

    # Production mode với key mạnh đạt chuẩn (>= 32 ký tự)
    s_prod_valid = Settings(
        APP_ENV="production",
        SECRET_KEY="a_very_strong_cryptographically_secure_production_secret_key_2026_9999"
    )
    validate_boot_safety(s_prod_valid)  # Không được raise ngoại lệ


# ===========================================================================
# 3. LOGIN RATE LIMITING & BRUTE-FORCE PROTECTION
# ===========================================================================

def test_login_rate_limiting_triggers_429(client: TestClient):
    """8. Đăng nhập sai 5 lần liên tiếp sẽ bị khóa (HTTP 429) ở lần thứ 6"""
    login_rate_limiter.reset()

    # Thử sai 5 lần cho tài khoản "staff"
    for i in range(5):
        res = client.post("/api/v1/auth/login", json={"username": "staff", "password": "WrongPassword@999"})
        assert res.status_code == 401, f"Lần thử thứ {i+1} phải trả về 401 Unauthorized"

    # Lần thử thứ 6 phải bị chặn với HTTP 429 Too Many Requests
    res_blocked = client.post("/api/v1/auth/login", json={"username": "staff", "password": "WrongPassword@999"})
    assert res_blocked.status_code == 429, "Lần thử thứ 6 phải trả về HTTP 429 Too Many Requests"
    assert "Quá nhiều lần đăng nhập thất bại" in res_blocked.json()["detail"]
    assert "Retry-After" in res_blocked.headers

    # Đảm bảo chống khóa nhầm: Tài khoản khác "customer" từ cùng client IP VẪN ĐƯỢC THỬ BÌNH THƯỜNG
    res_other = client.post("/api/v1/auth/login", json={"username": "customer", "password": "WrongPassword@999"})
    assert res_other.status_code == 401, "Tài khoản khác không được bị khóa nhầm do dùng chung IP"


def test_valid_login_still_works_normally_and_resets_failed_counter(client: TestClient):
    """9. Đăng nhập hợp lệ hoạt động bình thường và tự động xóa bộ đếm thất bại"""
    login_rate_limiter.reset()

    # Thử sai 2 lần
    for _ in range(2):
        res_fail = client.post("/api/v1/auth/login", json={"username": "admin", "password": "WrongPassword@111"})
        assert res_fail.status_code == 401

    # Đăng nhập đúng mật khẩu ở lần thứ 3 -> Thành công 200 OK
    res_success = client.post("/api/v1/auth/login", json={"username": "admin", "password": "Admin@123"})
    assert res_success.status_code == 200
    assert "access_token" in res_success.json()

    # Bộ đếm phải được xóa -> Thử sai lại từ đầu không bị cộng dồn thành 429
    res_fail_new = client.post("/api/v1/auth/login", json={"username": "admin", "password": "WrongPassword@111"})
    assert res_fail_new.status_code == 401
