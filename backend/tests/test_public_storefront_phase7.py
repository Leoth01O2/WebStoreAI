import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def get_token(username, password):
    res = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert res.status_code == 200, f"Login failed for {username}"
    return res.json()["access_token"]

# ==============================================================================
# 1. GUEST / PUBLIC STOREFRONT ACCESS
# ==============================================================================

def test_guest_can_access_public_categories_without_token():
    """Guest có thể xem danh mục hàng hóa công khai mà không cần token"""
    res = client.get("/api/v1/public/categories")
    assert res.status_code == 200
    cats = res.json()
    assert isinstance(cats, list)
    assert len(cats) > 0
    first_cat = cats[0]
    assert "id" in first_cat
    assert "name" in first_cat
    assert "code" in first_cat

def test_guest_can_access_public_products_without_token():
    """Guest có thể xem danh sách sản phẩm công khai mà không cần token"""
    res = client.get("/api/v1/public/products")
    assert res.status_code == 200
    products = res.json()
    assert isinstance(products, list)
    assert len(products) > 0
    for p in products:
        # Chỉ trả sản phẩm active
        assert p["status"] == "active"
        # Không được để lộ giá vốn hoặc thông tin nội bộ
        assert "cost_price" not in p, f"Security leak: cost_price found in product {p['sku']}"
        assert "min_stock_alert" not in p, f"Security leak: min_stock_alert found in product {p['sku']}"
        # Phải có các trường cần thiết cho người mua
        assert "selling_price" in p
        assert "name" in p
        assert "sku" in p
        assert "in_stock" in p

def test_guest_can_view_public_product_detail():
    """Guest có thể xem chi tiết 1 sản phẩm công khai mà không cần token"""
    list_res = client.get("/api/v1/public/products")
    assert list_res.status_code == 200
    first_id = list_res.json()[0]["id"]

    detail_res = client.get(f"/api/v1/public/products/{first_id}")
    assert detail_res.status_code == 200
    prod = detail_res.json()
    assert prod["id"] == first_id
    assert prod["status"] == "active"
    assert "cost_price" not in prod
    assert "min_stock_alert" not in prod

def test_guest_cannot_access_internal_management_apis():
    """Guest bị chặn 401 Unauthorized khi gọi các API quản trị nội bộ"""
    protected_endpoints = [
        ("GET", "/api/v1/products"),
        ("POST", "/api/v1/products"),
        ("GET", "/api/v1/orders"),
        ("GET", "/api/v1/customers"),
        ("GET", "/api/v1/reports/summary"),
        ("GET", "/api/v1/reports/revenue-trend"),
        ("GET", "/api/v1/purchases"),
        ("GET", "/api/v1/inventory/low-stock"),
        ("GET", "/api/v1/auth/users"),
    ]
    for method, path in protected_endpoints:
        if method == "GET":
            res = client.get(path)
        elif method == "POST":
            res = client.post(path, json={})
        assert res.status_code == 401, f"Guest called {path} and did not get 401"

# ==============================================================================
# 2. CUSTOMER POS & ORDER PLACEMENT
# ==============================================================================

def test_customer_can_order_via_pos_flow():
    """Customer đăng nhập có thể xem sản phẩm public và tạo order thật"""
    cust_token = get_token("customer", "Customer@123")
    cust_headers = {"Authorization": f"Bearer {cust_token}"}

    # 1. Customer xem catalog qua public API
    pub_res = client.get("/api/v1/public/products")
    assert pub_res.status_code == 200
    prods = pub_res.json()
    in_stock_prods = [p for p in prods if p["stock_quantity"] > 0]
    assert len(in_stock_prods) > 0
    target_prod = in_stock_prods[0]

    # 2. Customer lấy hồ sơ của chính mình
    me_cust = client.get("/api/v1/customers/me", headers=cust_headers)
    assert me_cust.status_code == 200
    customer_profile = me_cust.json()

    # 3. Customer tạo đơn hàng thật qua POS
    order_payload = {
        "customer_id": customer_profile["id"],
        "discount_amount": 0,
        "payment_method": "cash",
        "payment_status": "completed",
        "note": "Đơn hàng test từ Customer Storefront POS Phase 7",
        "items": [
            {
                "product_id": target_prod["id"],
                "quantity": 1
            }
        ]
    }
    order_res = client.post("/api/v1/orders", json=order_payload, headers=cust_headers)
    assert order_res.status_code == 200
    order_data = order_res.json()
    assert order_data["customer_id"] == customer_profile["id"]
    assert order_data["total_amount"] > 0

    # 4. Customer xem lại đơn hàng của mình
    my_orders = client.get("/api/v1/orders", headers=cust_headers)
    assert my_orders.status_code == 200
    assert any(o["order_code"] == order_data["order_code"] for o in my_orders.json())

# ==============================================================================
# 3. INTERNAL ROLES PRESERVED
# ==============================================================================

def test_admin_still_blocked_from_reports():
    """Admin vẫn bị chặn 403 Forbidden khi truy cập doanh thu/báo cáo"""
    admin_token = get_token("admin", "Admin@123")
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    res = client.get("/api/v1/reports/summary", headers=admin_headers)
    assert res.status_code == 403

def test_superadmin_has_full_access():
    """SuperAdmin vẫn có toàn quyền truy cập báo cáo doanh thu"""
    super_token = get_token("superadmin", "SuperAdmin@123")
    super_headers = {"Authorization": f"Bearer {super_token}"}
    res = client.get("/api/v1/reports/summary", headers=super_headers)
    assert res.status_code == 200
