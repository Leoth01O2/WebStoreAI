import pytest
import requests

VITE_URL = "http://127.0.0.1:5173"
BACKEND_URL = "http://127.0.0.1:8000"

@pytest.fixture(autouse=True, scope="module")
def check_vite_running():
    try:
        res = requests.get(VITE_URL, timeout=1)
        if res.status_code != 200:
            pytest.skip("Vite dev server is not running on http://127.0.0.1:5173 - skipping live E2E server tests")
    except Exception:
        pytest.skip("Vite dev server is not running on http://127.0.0.1:5173 - skipping live E2E server tests")

    # Safety Guard: Ensure backend server is running in testing environment or using test database
    try:
        health = requests.get(f"{BACKEND_URL}/api/health", timeout=1).json()
        if health.get("environment") != "testing":
            # Read-only tests are fine, but tests that write orders/purchases must be guarded
            pass
    except Exception:
        pass

def test_frontend_serves_html():
    res = requests.get(VITE_URL, timeout=5)
    res.encoding = 'utf-8'
    assert res.status_code == 200
    assert "StoreFlow AI" in res.text
    assert "JetBrains" in res.text
    assert '<div id="root"></div>' in res.text

def test_vite_proxy_to_backend():
    res = requests.get(f"{VITE_URL}/api/health", timeout=5)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "healthy"
    assert data["database"] == "sqlite_wal_active"

def test_full_staff_pos_e2e_flow():
    # Production Safety Guard
    try:
        health = requests.get(f"{BACKEND_URL}/api/health", timeout=2).json()
        if health.get("environment") != "testing":
            pytest.skip("Skipping write operations against non-testing environment")
    except Exception:
        pytest.skip("Cannot verify backend environment safety")

    # 1. Staff Login
    login_res = requests.post(f"{VITE_URL}/api/v1/auth/login", json={
        "username": "staff",
        "password": "Staff@123"
    }, timeout=5)
    assert login_res.status_code == 200
    login_data = login_res.json()
    token = login_data["access_token"]
    assert login_data["user"]["role"] == "staff"

    headers = {"Authorization": f"Bearer {token}"}

    # 2. Get Products to sell
    prods_res = requests.get(f"{VITE_URL}/api/v1/products?in_stock_only=true", headers=headers, timeout=5)
    assert prods_res.status_code == 200
    products = prods_res.json()
    assert len(products) > 0

    target_prod = next(p for p in products if p["stock_quantity"] >= 2)
    initial_stock = target_prod["stock_quantity"]

    # 3. Create POS Order (Sell 2 items)
    order_payload = {
        "customer_id": None,
        "discount_amount": 10000.0,
        "payment_method": "cash",
        "note": "E2E Automated POS Sale",
        "items": [
            {"product_id": target_prod["id"], "quantity": 2}
        ]
    }
    order_res = requests.post(f"{VITE_URL}/api/v1/orders", json=order_payload, headers=headers, timeout=5)
    assert order_res.status_code == 200
    order_data = order_res.json()
    assert order_data["status"] == "completed"
    assert order_data["final_amount"] == (target_prod["selling_price"] * 2) - 10000.0

    # 4. Verify Stock was deducted in SQLite
    updated_prod_res = requests.get(f"{VITE_URL}/api/v1/products/{target_prod['id']}", headers=headers, timeout=5)
    assert updated_prod_res.status_code == 200
    assert updated_prod_res.json()["stock_quantity"] == initial_stock - 2

    # 5. Verify Staff CANNOT access Manager reports (RBAC backend protection)
    report_res = requests.get(f"{VITE_URL}/api/v1/reports/summary", headers=headers, timeout=5)
    assert report_res.status_code == 403

def test_manager_analytics_and_order_cancel_flow():
    # Production Safety Guard
    try:
        health = requests.get(f"{BACKEND_URL}/api/health", timeout=2).json()
        if health.get("environment") != "testing":
            pytest.skip("Skipping write operations against non-testing environment")
    except Exception:
        pytest.skip("Cannot verify backend environment safety")

    # 1. Manager Login
    login_res = requests.post(f"{VITE_URL}/api/v1/auth/login", json={
        "username": "superadmin",
        "password": "SuperAdmin@123"
    }, timeout=5)
    assert login_res.status_code == 200
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Manager accesses Dashboard Summary
    summary_res = requests.get(f"{VITE_URL}/api/v1/reports/summary", headers=headers, timeout=5)
    assert summary_res.status_code == 200
    summary = summary_res.json()
    assert summary["today_revenue"] > 0
    assert summary["completed_orders"] > 0

    # 3. Manager accesses Revenue Trend
    trend_res = requests.get(f"{VITE_URL}/api/v1/reports/revenue-trend?days=7", headers=headers, timeout=5)
    assert trend_res.status_code == 200
    assert len(trend_res.json()) > 0

    # 4. Manager exports CSV and Excel
    csv_res = requests.get(f"{VITE_URL}/api/v1/reports/export/csv", headers=headers, timeout=5)
    assert csv_res.status_code == 200
    assert "Mã Hóa Đơn" in csv_res.text

    excel_res = requests.get(f"{VITE_URL}/api/v1/reports/export/excel", headers=headers, timeout=5)
    assert excel_res.status_code == 200
    assert len(excel_res.content) > 1000  # Valid binary excel sheet

    # 5. Manager creates a purchase receipt (increases stock)
    prods = requests.get(f"{VITE_URL}/api/v1/products", headers=headers, timeout=5).json()
    test_prod = prods[0]
    initial_stock = test_prod["stock_quantity"]

    purchase_payload = {
        "supplier_name": "Kho Tổng E2E Test",
        "note": "Nhập hàng tự động",
        "items": [
            {"product_id": test_prod["id"], "quantity": 10, "import_price": test_prod["cost_price"]}
        ]
    }
    purch_res = requests.post(f"{VITE_URL}/api/v1/purchases", json=purchase_payload, headers=headers, timeout=5)
    assert purch_res.status_code == 200

    # Check stock increased by 10
    updated_prod = requests.get(f"{VITE_URL}/api/v1/products/{test_prod['id']}", headers=headers, timeout=5).json()
    assert updated_prod["stock_quantity"] == initial_stock + 10
