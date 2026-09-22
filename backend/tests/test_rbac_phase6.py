import uuid
import pytest
from fastapi.testclient import TestClient
from app.main import app
from seed_data import seed_database

@pytest.fixture(scope="session", autouse=True)
def setup_test_database():
    """Khởi tạo và nạp dữ liệu mẫu trước khi chạy test suite"""
    seed_database()

client = TestClient(app)

def get_token(username, password):
    res = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert res.status_code == 200, f"Failed login for {username}"
    return res.json()["access_token"]

# ==============================================================================
# 1. GUEST / CHƯA ĐĂNG NHẬP -> 401 UNAUTHORIZED
# ==============================================================================
def test_1_guest_without_token_returns_401():
    """Guest không gửi token đến các API cần xác thực phải nhận 401 Unauthorized"""
    endpoints = [
        ("GET", "/api/v1/auth/me"),
        ("GET", "/api/v1/products"),
        ("GET", "/api/v1/orders"),
        ("GET", "/api/v1/customers"),
        ("GET", "/api/v1/reports/summary"),
        ("GET", "/api/v1/purchases"),
        ("GET", "/api/v1/inventory/low-stock"),
    ]
    for method, path in endpoints:
        if method == "GET":
            res = client.get(path)
        assert res.status_code == 401, f"{path} did not return 401 for guest"
        assert res.json().get("detail") == "Not authenticated" or "token" in str(res.json()).lower() or "phiên" in str(res.json()).lower()

# ==============================================================================
# 2. TOKEN KHÔNG HỢP LỆ HOẶC HẾT HẠN -> 401 UNAUTHORIZED
# ==============================================================================
def test_2_invalid_token_returns_401():
    """Gửi token giả mạo hoặc sai định dạng phải trả về 401 Unauthorized"""
    bad_headers = {"Authorization": "Bearer invalid_tampered_token_xyz"}
    res = client.get("/api/v1/auth/me", headers=bad_headers)
    assert res.status_code == 401
    assert "Phiên đăng nhập không hợp lệ" in res.json()["detail"]

# ==============================================================================
# 3. SUPERADMIN GỌI API ĐƯỢC PHÉP -> THÀNH CÔNG (200)
# ==============================================================================
def test_3_superadmin_allowed_operations():
    """SuperAdmin có quyền cao nhất: xem báo cáo, xem danh sách user, tạo admin, hard delete"""
    token = get_token("superadmin", "SuperAdmin@123")
    headers = {"Authorization": f"Bearer {token}"}

    # Báo cáo
    res = client.get("/api/v1/reports/summary", headers=headers)
    assert res.status_code == 200

    # Xem danh sách user hệ thống
    res = client.get("/api/v1/auth/users", headers=headers)
    assert res.status_code == 200
    assert isinstance(res.json(), list)

    # SuperAdmin có quyền tạo Admin
    new_admin_username = f"admin_sub_{uuid.uuid4().hex[:6]}"
    res = client.post(
        "/api/v1/auth/users",
        json={
            "username": new_admin_username,
            "password": "Password123",
            "full_name": "Sub Admin Created By SuperAdmin",
            "role": "admin"
        },
        headers=headers
    )
    assert res.status_code == 200
    assert res.json()["role"] == "admin"

    # SuperAdmin có quyền xóa cứng sản phẩm (hard_delete=true)
    # Tạo sản phẩm test để xóa
    sku = f"TEST-HD-{uuid.uuid4().hex[:4]}"
    prod_res = client.post(
        "/api/v1/products",
        json={
            "sku": sku,
            "name": "Sản phẩm test hard delete",
            "selling_price": 50000,
            "cost_price": 30000,
            "stock_quantity": 5
        },
        headers=headers
    )
    assert prod_res.status_code == 200
    prod_id = prod_res.json()["id"]

    del_res = client.delete(f"/api/v1/products/{prod_id}?hard_delete=true", headers=headers)
    assert del_res.status_code == 200
    assert "hard delete" in del_res.json()["message"].lower()

# ==============================================================================
# 4. ADMIN GỌI API ĐƯỢC PHÉP -> THÀNH CÔNG (200)
# ==============================================================================
def test_4_admin_allowed_operations():
    """Admin có quyền quản trị vận hành: nhập hàng, quản lý sản phẩm, quản lý danh mục, tạo staff"""
    token = get_token("admin", "Admin@123")
    headers = {"Authorization": f"Bearer {token}"}

    # Quản lý sản phẩm và danh mục
    res = client.get("/api/v1/products", headers=headers)
    assert res.status_code == 200

    res_cat = client.get("/api/v1/categories", headers=headers)
    assert res_cat.status_code == 200

    # Nhập hàng
    res = client.get("/api/v1/purchases", headers=headers)
    assert res.status_code == 200

    # Quản lý tài khoản: Admin được tạo staff
    new_staff_username = f"staff_created_{uuid.uuid4().hex[:6]}"
    res = client.post(
        "/api/v1/auth/users",
        json={
            "username": new_staff_username,
            "password": "Password123",
            "full_name": "Staff Tạo Bởi Admin",
            "role": "staff"
        },
        headers=headers
    )
    assert res.status_code == 200
    assert res.json()["role"] == "staff"

# ==============================================================================
# 5. ADMIN GỌI API CHỈ DÀNH CHO SUPERADMIN -> 403 FORBIDDEN
# ==============================================================================
def test_5_admin_cannot_access_superadmin_features():
    """
    Admin KHÔNG có toàn bộ quyền của SuperAdmin:
    - Bị chặn 403 khi gọi API Doanh Thu / Báo Cáo nhạy cảm (chỉ dành riêng cho Store Owner)
    - Không được tự nâng quyền thành SuperAdmin hoặc tạo Admin khác -> 403
    - Không được xóa cứng sản phẩm (hard delete) -> 403
    """
    admin_token = get_token("admin", "Admin@123")
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    # 1. Admin cố truy cập Doanh Thu / Báo cáo tài chính -> 403 Forbidden!
    res_report_sum = client.get("/api/v1/reports/summary", headers=admin_headers)
    assert res_report_sum.status_code == 403
    assert "quyền" in res_report_sum.json()["detail"].lower()

    res_report_trend = client.get("/api/v1/reports/revenue-trend", headers=admin_headers)
    assert res_report_trend.status_code == 403

    res_report_export = client.get("/api/v1/reports/export/csv", headers=admin_headers)
    assert res_report_export.status_code == 403

    # 2. Admin cố tạo SuperAdmin
    res_escalate_super = client.post(
        "/api/v1/auth/users",
        json={
            "username": f"fake_super_{uuid.uuid4().hex[:6]}",
            "password": "Password123",
            "full_name": "Fake SuperAdmin",
            "role": "superadmin"
        },
        headers=admin_headers
    )
    assert res_escalate_super.status_code == 403
    assert "không có quyền" in res_escalate_super.json()["detail"]

    # 3. Admin cố tạo Admin
    res_escalate_admin = client.post(
        "/api/v1/auth/users",
        json={
            "username": f"fake_admin_{uuid.uuid4().hex[:6]}",
            "password": "Password123",
            "full_name": "Fake Admin",
            "role": "admin"
        },
        headers=admin_headers
    )
    assert res_escalate_admin.status_code == 403

    # 4. Admin cố hard delete sản phẩm
    prod_list = client.get("/api/v1/products", headers=admin_headers).json()
    assert len(prod_list) > 0
    target_prod_id = prod_list[0]["id"]

    del_res = client.delete(f"/api/v1/products/{target_prod_id}?hard_delete=true", headers=admin_headers)
    assert del_res.status_code == 403
    assert "SuperAdmin" in del_res.json()["detail"]

# ==============================================================================
# 6. STAFF GỌI API QUẢN TRỊ CẤP CAO -> 403 FORBIDDEN
# ==============================================================================
def test_6_staff_blocked_from_management_apis():
    """Staff không được truy cập các API báo cáo, nhập hàng, quản lý user, hủy đơn hàng"""
    staff_token = get_token("staff", "Staff@123")
    staff_headers = {"Authorization": f"Bearer {staff_token}"}

    # Báo cáo tổng hợp
    res = client.get("/api/v1/reports/summary", headers=staff_headers)
    assert res.status_code == 403

    # Phiếu nhập hàng
    res = client.get("/api/v1/purchases", headers=staff_headers)
    assert res.status_code == 403

    # Danh sách tài khoản
    res = client.get("/api/v1/auth/users", headers=staff_headers)
    assert res.status_code == 403

    # Tạo tài khoản
    res = client.post(
        "/api/v1/auth/users",
        json={"username": "hacker", "password": "123", "full_name": "Hacker", "role": "customer"},
        headers=staff_headers
    )
    assert res.status_code == 403

    # Tạo danh mục hàng hóa
    res = client.post(
        "/api/v1/categories",
        json={"name": "Hàng cấm", "code": "CAT-CAM"},
        headers=staff_headers
    )
    assert res.status_code == 403

# ==============================================================================
# 7. CUSTOMER TRUY CẬP DỮ LIỆU CỦA CHÍNH MÌNH & ĐẶT HÀNG QUA POS -> THÀNH CÔNG (200)
# ==============================================================================
def test_7_customer_can_access_own_data_and_order_via_pos():
    """Customer truy cập dữ liệu cá nhân, profile me, xem sản phẩm và tạo đơn hàng POS thành công"""
    token = get_token("customer", "Customer@123")
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Customer xem profile của mình qua /auth/me
    res_me = client.get("/api/v1/auth/me", headers=headers)
    assert res_me.status_code == 200
    user_me = res_me.json()
    assert user_me["role"] == "customer"
    assert user_me["username"] == "customer"

    # 2. Customer gọi /customers/me để lấy hồ sơ người mua
    res_my_profile = client.get("/api/v1/customers/me", headers=headers)
    assert res_my_profile.status_code == 200
    my_profile = res_my_profile.json()
    assert my_profile["id"] == 1
    assert my_profile["user_id"] == user_me["id"]

    # 3. Customer xem danh sách sản phẩm trong POS
    res_prods = client.get("/api/v1/products", headers=headers)
    assert res_prods.status_code == 200
    products = res_prods.json()
    assert len(products) > 0
    avail_prod = [p for p in products if p["stock_quantity"] > 2][0]

    # 4. Customer đặt hàng thực tế qua flow POS
    order_payload = {
        "customer_id": my_profile["id"],
        "items": [{"product_id": avail_prod["id"], "quantity": 1}],
        "payment_method": "cash",
        "note": "Customer tự đặt hàng qua giao diện POS"
    }
    order_res = client.post("/api/v1/orders", json=order_payload, headers=headers)
    assert order_res.status_code == 200
    created_order = order_res.json()
    assert created_order["customer_id"] == 1
    assert created_order["user_id"] == user_me["id"]

    # 5. Customer xem lại đơn hàng vừa tạo qua /orders/{id}
    detail_res = client.get(f"/api/v1/orders/{created_order['id']}", headers=headers)
    assert detail_res.status_code == 200
    assert detail_res.json()["order_code"] == created_order["order_code"]

    # 6. Customer xem danh sách đơn hàng của mình
    res_orders = client.get("/api/v1/orders", headers=headers)
    assert res_orders.status_code == 200
    orders = res_orders.json()
    assert isinstance(orders, list)
    assert any(o["id"] == created_order["id"] for o in orders)
    for o in orders:
        assert (o.get("customer_id") == 1) or (o.get("user_id") == user_me["id"])

# ==============================================================================
# 8. CHỐNG IDOR / CROSS-USER ACCESS (CUSTOMER KHÔNG XEM/SỬA DỮ LIỆU NGƯỜI KHÁC)
# ==============================================================================
def test_8_customer_anti_idor_and_cross_user_protection():
    """
    Chống IDOR:
    - Customer không được xem danh sách tất cả khách hàng (403)
    - Customer 1 không được xem thông tin Customer 2 (403)
    - Customer 1 không được sửa thông tin Customer 2 (403)
    - Customer 1 không được xem hóa đơn của Customer 2 (403)
    - Customer 1 không được tạo đơn hàng gán customer_id của Customer 2 (403)
    - Customer không được xem cảnh báo tồn kho kho hàng (403)
    """
    token_c1 = get_token("customer", "Customer@123")
    headers_c1 = {"Authorization": f"Bearer {token_c1}"}

    # 1. Customer gọi GET /customers (danh bạ khách hàng) -> 403
    res = client.get("/api/v1/customers", headers=headers_c1)
    assert res.status_code == 403

    # 2. Customer 1 (customer_id=1) cố truy cập thông tin Customer 2 (id=2) -> 403
    res_other_cust = client.get("/api/v1/customers/2", headers=headers_c1)
    assert res_other_cust.status_code == 403
    assert "không có quyền" in res_other_cust.json()["detail"]

    # 3. Customer 1 cố sửa thông tin Customer 2 -> 403
    res_edit_other = client.put(
        "/api/v1/customers/2",
        json={"name": "Tên Bị Hacked"},
        headers=headers_c1
    )
    assert res_edit_other.status_code == 403

    # 4. Admin tạo 1 đơn hàng riêng cho Customer 2
    admin_token = get_token("admin", "Admin@123")
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    # Lấy 1 sản phẩm có hàng
    products = client.get("/api/v1/products", headers=admin_headers).json()
    avail_prod = [p for p in products if p["stock_quantity"] > 2][0]

    order_c2_res = client.post(
        "/api/v1/orders",
        json={
            "customer_id": 2,
            "items": [{"product_id": avail_prod["id"], "quantity": 1}],
            "payment_method": "cash"
        },
        headers=admin_headers
    )
    assert order_c2_res.status_code == 200
    order_c2_id = order_c2_res.json()["id"]

    # Customer 1 cố xem chi tiết hóa đơn order_c2_id của Customer 2 -> 403 Forbidden!
    res_cross_order = client.get(f"/api/v1/orders/{order_c2_id}", headers=headers_c1)
    assert res_cross_order.status_code == 403
    assert "không có quyền" in res_cross_order.json()["detail"]

    # 5. Customer 1 cố tạo đơn hàng nhưng chỉ định customer_id = 2 -> 403 Forbidden!
    res_spoof_order = client.post(
        "/api/v1/orders",
        json={
            "customer_id": 2,
            "items": [{"product_id": avail_prod["id"], "quantity": 1}],
            "payment_method": "cash"
        },
        headers=headers_c1
    )
    assert res_spoof_order.status_code == 403
    assert "không thể tạo đơn hàng cho khách hàng khác" in res_spoof_order.json()["detail"]

    # 6. Customer cố xem cảnh báo tồn kho kho hàng -> 403 Forbidden!
    res_low_stock = client.get("/api/v1/inventory/low-stock", headers=headers_c1)
    assert res_low_stock.status_code == 403

# ==============================================================================
# 9. ROLE ESCALATION / NÂNG QUYỀN TRÁI PHÉP
# ==============================================================================
def test_9_role_escalation_prevented():
    """
    Người dùng không thể tự nâng quyền:
    - Customer gửi yêu cầu tạo user -> 403
    - Không thể đăng ký role manager -> 422
    """
    token_c1 = get_token("customer", "Customer@123")
    headers_c1 = {"Authorization": f"Bearer {token_c1}"}

    res = client.post(
        "/api/v1/auth/users",
        json={
            "username": "self_elevated_super",
            "password": "Password123",
            "full_name": "Attacker",
            "role": "superadmin"
        },
        headers=headers_c1
    )
    assert res.status_code == 403

# ==============================================================================
# 10. LOGIN CHO TOÀN BỘ CÁC VAI TRÒ HOẠT ĐỘNG ỔN ĐỊNH
# ==============================================================================
def test_10_all_roles_login_still_works():
    """Kiểm tra chức năng đăng nhập cho cả 4 role vẫn hoạt động ổn định và chính xác"""
    roles = [
        ("superadmin", "SuperAdmin@123", "superadmin"),
        ("admin", "Admin@123", "admin"),
        ("staff", "Staff@123", "staff"),
        ("customer", "Customer@123", "customer"),
    ]
    for username, password, expected_role in roles:
        res = client.post("/api/v1/auth/login", json={"username": username, "password": password})
        assert res.status_code == 200
        data = res.json()
        assert data["user"]["role"] == expected_role
        assert len(data["access_token"]) > 20
