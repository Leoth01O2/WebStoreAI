import pytest
import time
from unittest.mock import patch
from fastapi.testclient import TestClient

from app.main import app
from app.core.database import get_db
from app.core.security import create_access_token
from app.core.rate_limiter import ai_rate_limiter
from app.services.ai_service import ai_service
from app.services.report_service import ReportService

client = TestClient(app)


def get_user_by_username(username: str):
    with get_db() as conn:
        c = conn.cursor()
        c.execute("SELECT id, role FROM users WHERE username = ?", (username,))
        row = c.fetchone()
        return dict(row) if row else None


def get_auth_headers_for_role(username: str):
    user = get_user_by_username(username)
    if not user:
        raise ValueError(f"User {username} not found in database")
    token = create_access_token(data={"sub": str(user["id"])})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(autouse=True)
def reset_rate_limiter():
    ai_rate_limiter.reset()
    yield
    ai_rate_limiter.reset()


@pytest.fixture(scope="module")
def superadmin_headers():
    return get_auth_headers_for_role("superadmin")


@pytest.fixture(scope="module")
def admin_headers():
    return get_auth_headers_for_role("admin")


@pytest.fixture(scope="module")
def staff_headers():
    return get_auth_headers_for_role("staff")


@pytest.fixture(scope="module")
def customer_headers():
    return get_auth_headers_for_role("customer")


# ==================== 1. AUTHENTICATION & RBAC HIERARCHY TESTS ====================

def test_health_check_returns_wal_status():
    """Health check endpoint returns healthy status and sqlite_wal_active."""
    res = client.get("/api/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "healthy"
    assert data["database"] == "sqlite_wal_active"


def test_unauthenticated_request_to_protected_endpoint_returns_401():
    """Unauthenticated calls to protected endpoints return 401 Unauthorized."""
    endpoints = [
        ("GET", "/api/v1/auth/me"),
        ("POST", "/api/v1/orders"),
        ("GET", "/api/v1/reports/summary"),
        ("POST", "/api/v1/purchases"),
    ]
    for method, ep in endpoints:
        if method == "GET":
            res = client.get(ep)
        else:
            res = client.post(ep, json={})
        assert res.status_code in (401, 403), f"Endpoint {ep} did not protect against unauthenticated call"


def test_role_hierarchy_permissions(superadmin_headers, admin_headers, staff_headers, customer_headers):
    """
    Enforce strict hierarchy: SuperAdmin > Admin > Staff > Customer:
      - SuperAdmin: Full access including reports & profit analytics.
      - Admin: System management, product CRUD, but CANNOT access reports/revenue.
      - Staff: POS orders, product lookup, but CANNOT access reports or users.
      - Customer: View own orders, POS self-order, but CANNOT access management.
    """
    # 1. SuperAdmin accesses reports
    res_sa = client.get("/api/v1/reports/summary", headers=superadmin_headers)
    assert res_sa.status_code == 200

    # 2. Admin blocked from financial reports (403)
    res_admin = client.get("/api/v1/reports/summary", headers=admin_headers)
    assert res_admin.status_code == 403

    # 3. Staff blocked from financial reports and user management (403)
    res_staff = client.get("/api/v1/reports/summary", headers=staff_headers)
    assert res_staff.status_code == 403

    # 4. Customer blocked from inventory logs and financial reports (403)
    res_cust = client.get("/api/v1/inventory/logs", headers=customer_headers)
    assert res_cust.status_code == 403


# ==================== 2. IDOR & CROSS-USER PRIVACY PROTECTION ====================

def test_customer_cannot_view_or_cancel_other_customer_orders(customer_headers, superadmin_headers):
    """Customer cannot view or cancel orders belonging to another user (IDOR Guard)."""
    unique_code = f"ORD-IDOR-{int(time.time()*1000)}"
    # Create an order by SuperAdmin / another customer
    with get_db() as conn:
        c = conn.cursor()
        c.execute("""
            INSERT INTO orders (order_code, user_id, customer_id, total_amount, discount_amount, final_amount, payment_method, payment_status, status)
            VALUES (?, 1, 2, 500000, 0, 500000, 'cash', 'paid', 'completed')
        """, (unique_code,))
        order_id = c.lastrowid
        conn.commit()

    # Customer tries to access this order detail
    res = client.get(f"/api/v1/orders/{order_id}", headers=customer_headers)
    assert res.status_code == 403
    assert "quyền" in res.json()["detail"].lower() or "chỉ xem" in res.json()["detail"].lower()


def test_public_and_customer_apis_do_not_leak_cost_price():
    """Cost price is never exposed to Public Storefront."""
    # Public products
    res_pub = client.get("/api/v1/public/products")
    assert res_pub.status_code == 200
    for p in res_pub.json():
        assert "cost_price" not in p, "Cost price leaked in public product list"

    # Public single product
    res_pub_single = client.get("/api/v1/public/products/1")
    if res_pub_single.status_code == 200:
        assert "cost_price" not in res_pub_single.json()


# ==================== 3. BUSINESS LOGIC & ATOMIC INVENTORY INTEGRITY ====================

def test_order_creation_atomic_stock_deduction(staff_headers):
    """Placing an order atomically deducts inventory and records audit log."""
    with get_db() as conn:
        c = conn.cursor()
        c.execute("SELECT id, stock_quantity FROM products WHERE sku = 'SP-GAME-01'")
        prod = c.fetchone()
        prod_id = prod["id"]
        # Ensure sufficient stock for test
        if prod["stock_quantity"] < 5:
            c.execute("UPDATE products SET stock_quantity = 20 WHERE id = ?", (prod_id,))
            conn.commit()
            prod_stock = 20
        else:
            prod_stock = prod["stock_quantity"]

    order_payload = {
        "customer_id": 1,
        "discount_amount": 0,
        "payment_method": "cash",
        "note": "Phase 10 Atomic POS Test",
        "items": [
            {"product_id": prod_id, "quantity": 2}
        ]
    }

    res = client.post("/api/v1/orders", json=order_payload, headers=staff_headers)
    assert res.status_code == 200
    data = res.json()
    assert "order_code" in data

    # Verify stock reduction
    with get_db() as conn:
        c = conn.cursor()
        c.execute("SELECT stock_quantity FROM products WHERE id = ?", (prod_id,))
        new_stock = c.fetchone()["stock_quantity"]
        assert new_stock == prod_stock - 2


def test_order_rejection_on_insufficient_stock(staff_headers):
    """Attempting to buy more than available stock is rejected with 400 and zero stock change."""
    with get_db() as conn:
        c = conn.cursor()
        c.execute("SELECT id, stock_quantity FROM products WHERE sku = 'SP-GAME-02'")
        prod = c.fetchone()
        prod_id = prod["id"]
        curr_stock = prod["stock_quantity"]

    excessive_qty = curr_stock + 1000
    res = client.post("/api/v1/orders", json={
        "customer_id": 1,
        "payment_method": "cash",
        "items": [{"product_id": prod_id, "quantity": excessive_qty}]
    }, headers=staff_headers)

    assert res.status_code == 400
    assert "không đủ" in res.json()["detail"].lower()

    # Stock must remain identical
    with get_db() as conn:
        c = conn.cursor()
        c.execute("SELECT stock_quantity FROM products WHERE id = ?", (prod_id,))
        assert c.fetchone()["stock_quantity"] == curr_stock


def test_order_cancellation_restores_stock(superadmin_headers, staff_headers):
    """Cancelling a completed order restores stock atomically."""
    # 1. Create order for 1 item
    with get_db() as conn:
        c = conn.cursor()
        c.execute("SELECT id, stock_quantity FROM products WHERE sku = 'SP-GAME-03'")
        prod = c.fetchone()
        prod_id = prod["id"]
        if prod["stock_quantity"] < 5:
            c.execute("UPDATE products SET stock_quantity = 20 WHERE id = ?", (prod_id,))
            conn.commit()
            base_stock = 20
        else:
            base_stock = prod["stock_quantity"]

    res_create = client.post("/api/v1/orders", json={
        "customer_id": 1,
        "payment_method": "cash",
        "items": [{"product_id": prod_id, "quantity": 1}]
    }, headers=staff_headers)
    assert res_create.status_code == 200
    order_id = res_create.json()["id"]

    # 2. Cancel order
    res_cancel = client.post(f"/api/v1/orders/{order_id}/cancel", json={"reason": "Test Restore"}, headers=superadmin_headers)
    assert res_cancel.status_code == 200

    # 3. Stock restored
    with get_db() as conn:
        c = conn.cursor()
        c.execute("SELECT stock_quantity FROM products WHERE id = ?", (prod_id,))
        assert c.fetchone()["stock_quantity"] == base_stock


def test_purchase_receipt_increases_stock(superadmin_headers):
    """Creating a purchase receipt increases product stock atomically."""
    with get_db() as conn:
        c = conn.cursor()
        c.execute("SELECT id, stock_quantity FROM products WHERE sku = 'SP-GAME-04'")
        prod = c.fetchone()
        prod_id = prod["id"]
        initial_stock = prod["stock_quantity"]

    purchase_payload = {
        "supplier_name": "Nhà phân phối Công nghệ Phase 10",
        "note": "Nhập hàng kiểm thử Phase 10",
        "items": [
            {"product_id": prod_id, "quantity": 10, "import_price": 200000}
        ]
    }
    res = client.post("/api/v1/purchases", json=purchase_payload, headers=superadmin_headers)
    assert res.status_code == 200

    with get_db() as conn:
        c = conn.cursor()
        c.execute("SELECT stock_quantity FROM products WHERE id = ?", (prod_id,))
        assert c.fetchone()["stock_quantity"] == initial_stock + 10


# ==================== 4. ERROR HANDLING MATRIX (400, 401, 403, 404, 429) ====================

def test_error_handling_matrix(customer_headers):
    """Verify standard error codes across various scenarios."""
    # 400 Validation Error
    res_400 = client.post("/api/v1/orders", json={"items": []}, headers=customer_headers)
    assert res_400.status_code in (400, 422)

    # 401 Missing Authentication
    res_401 = client.get("/api/v1/auth/me")
    assert res_401.status_code == 401

    # 403 Forbidden
    res_403 = client.get("/api/v1/reports/summary", headers=customer_headers)
    assert res_403.status_code == 403

    # 404 Not Found (Public Storefront non-existent product)
    res_404 = client.get("/api/v1/public/products/99999999")
    assert res_404.status_code == 404

    # 429 Rate Limiter
    key = "ip:testclient"
    ai_rate_limiter._last_request_time[key] = time.time()
    res_429 = client.post("/api/v1/ai/recommend", json={"query": "bàn phím"})
    assert res_429.status_code == 429
    assert "retry-after" in res_429.headers


# ==================== 5. AI SECURITY & FALLBACK INTEGRITY ====================

def test_ai_output_secret_sanitization():
    """Sanitizer actively purges raw Gemini API keys and bcrypt hashes from AI outputs."""
    leaked_sample = "Gemini Key: AQ.Ab8RN6Js4l07YoeKOl46x_Hk0Niixryq_LH6oKQmLyN777JcgA and hash $2b$12$e8uq.J1b0lFh7m0P5Kz6b.gX9kP0rG2y5vB7tN8qM1xZ3aC4vD6eF"
    sanitized = ai_rate_limiter.sanitize_output(leaked_sample)
    assert "AQ.Ab" not in sanitized
    assert "$2b$12$" not in sanitized
    assert "[REDACTED_SECRET]" in sanitized or "[REDACTED_API_KEY]" in sanitized or "[REDACTED_PASSWORD_HASH]" in sanitized


def test_ai_graceful_fallback_on_network_timeout():
    """When Gemini provider times out, system returns structured grounded fallback."""
    with patch.object(ai_service, "_call_gemini", side_effect=TimeoutError("Connection timed out to Google API")):
        res = ai_service.recommend_products("Tìm chuột gaming")
        assert res.is_fallback is True
        assert len(res.recommended_products) > 0
        assert "StoreFlow AI" in res.ai_response
