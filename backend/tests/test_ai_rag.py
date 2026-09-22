import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient

from app.main import app
from app.services.rag_service import rag_service
from app.services.ai_service import ai_service
from app.core.database import get_db_connection

client = TestClient(app)

from app.core.rate_limiter import ai_rate_limiter

@pytest.fixture(autouse=True)
def reset_rate_limiter():
    ai_rate_limiter.reset()
    yield
    ai_rate_limiter.reset()

def get_token(username, password):
    res = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert res.status_code == 200
    return res.json()["access_token"]


@pytest.fixture(scope="module")
def admin_headers():
    token = get_token("admin", "Admin@123")
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="module")
def staff_headers():
    token = get_token("staff", "Staff@123")
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="module")
def manager_headers():
    token = get_token("superadmin", "SuperAdmin@123")
    return {"Authorization": f"Bearer {token}"}


def test_chromadb_sync_and_candidate_search():
    """Verify that ChromaDB indexes products and returns semantic search results."""
    count = rag_service.sync_all_products()
    assert count > 0, "Should index at least one product"

    candidates = rag_service.search_candidates("tai nghe âm thanh sống động", top_k=3)
    assert len(candidates) > 0
    assert "product_id" in candidates[0]
    assert "metadata" in candidates[0]


def test_sqlite_post_retrieval_verification_guard():
    """
    CRITICAL TEST: Ensure the SQLite Post-Retrieval Verification Guard strictly eliminates
    any product with stock_quantity <= 0 or status != 'active'.
    """
    # 1. Identify or insert an out-of-stock product
    with get_db_connection() as conn:
        c = conn.cursor()
        c.execute("SELECT id, name, stock_quantity FROM products WHERE stock_quantity <= 0 LIMIT 1")
        row = c.fetchone()
        if not row:
            # Create a temporary zero-stock product
            c.execute("""
                INSERT INTO products (sku, name, category_id, cost_price, selling_price, stock_quantity, min_stock_alert, unit, status, description)
                VALUES ('TEST-OOS-01', 'Sản phẩm thử nghiệm hết hàng tuyệt đối', 1, 10000, 20000, 0, 5, 'cái', 'active', 'Hàng test out of stock')
            """)
            conn.commit()
            oos_id = c.lastrowid
            assert oos_id is not None
            oos_name = 'Sản phẩm thử nghiệm hết hàng tuyệt đối'
            rag_service.upsert_single_product(oos_id)
        else:
            oos_id = row["id"]
            oos_name = row["name"]

    # 2. Query context searching specifically for this product
    context_res = rag_service.get_grounded_recommendation_context(oos_name, top_k=5)

    # 3. Verify that the out-of-stock product is NEVER in verified_products
    verified_ids = [p["id"] for p in context_res["products"]]
    assert oos_id not in verified_ids, f"Out-of-stock product ID {oos_id} leaked into verified products context!"

    # 4. Verify all verified products have stock > 0 and status == 'active'
    for p in context_res["products"]:
        assert p["stock_quantity"] > 0, f"Product {p['name']} has stock {p['stock_quantity']} <= 0"
        assert p["status"] == "active"


def test_recommend_endpoint_accessible_by_all_roles(admin_headers, staff_headers, manager_headers):
    """
    Verify that /api/v1/ai/recommend is accessible by Admin, Staff, and Manager.
    """
    payload = {"query": "Bàn phím cơ văn phòng gõ êm", "budget": 1500000, "limit": 3}

    # Staff call
    res_staff = client.post("/api/v1/ai/recommend", json=payload, headers=staff_headers)
    assert res_staff.status_code == 200
    data_staff = res_staff.json()
    assert "ai_response" in data_staff
    assert "recommended_products" in data_staff
    for p in data_staff["recommended_products"]:
        assert p["stock_quantity"] > 0

    # Manager call
    res_mgr = client.post("/api/v1/ai/recommend", json=payload, headers=manager_headers)
    assert res_mgr.status_code == 200

    # Admin call
    res_admin = client.post("/api/v1/ai/recommend", json=payload, headers=admin_headers)
    assert res_admin.status_code == 200


def test_sales_report_rbac_enforcement(staff_headers, manager_headers):
    """
    Verify that /api/v1/ai/sales-report:
    - Allows Manager
    - BLOCKS Staff with HTTP 403 Forbidden
    """
    payload = {"period": "month"}

    # Staff MUST be forbidden
    res_staff = client.post("/api/v1/ai/sales-report", json=payload, headers=staff_headers)
    assert res_staff.status_code == 403, f"Staff should be blocked from sales-report, got {res_staff.status_code}"

    # Manager is allowed
    res_mgr = client.post("/api/v1/ai/sales-report", json=payload, headers=manager_headers)
    assert res_mgr.status_code == 200
    data_mgr = res_mgr.json()
    assert "ai_analysis" in data_mgr
    assert "total_revenue" in data_mgr
    assert data_mgr["total_revenue"] >= 0
    assert "total_orders" in data_mgr


def test_sales_qa_rbac_enforcement(staff_headers, manager_headers):
    """
    Verify that /api/v1/ai/sales-qa:
    - Allows Manager (SuperAdmin) with full factual analytics
    - For Staff asking business revenue, backend returns safe RBAC permission refusal
    """
    # Staff asking revenue -> backend denies revenue data safely
    res_staff = client.post("/api/v1/ai/sales-qa", json={"query": "Doanh thu hôm nay là bao nhiêu?"}, headers=staff_headers)
    assert res_staff.status_code == 200
    assert "Nhân viên (Staff) không có quyền" in res_staff.json()["answer"] or "không có quyền" in res_staff.json()["answer"]
    assert res_staff.json()["context_type"] == "rbac_guard"

    # Manager (SuperAdmin) is allowed
    res_mgr = client.post("/api/v1/ai/sales-qa", json={"query": "Doanh thu hôm nay là bao nhiêu?"}, headers=manager_headers)
    assert res_mgr.status_code == 200
    data_mgr = res_mgr.json()
    assert "answer" in data_mgr
    assert data_mgr["context_type"] == "superadmin_sql_facts"



def test_ai_audit_logs_and_rbac(staff_headers, manager_headers):
    """
    Verify that /api/v1/ai/logs:
    - Blocks Staff with 403
    - Allows Manager and returns logged AI transactions
    """
    res_staff = client.get("/api/v1/ai/logs", headers=staff_headers)
    assert res_staff.status_code == 403

    res_mgr = client.get("/api/v1/ai/logs", headers=manager_headers)
    assert res_mgr.status_code == 200
    logs = res_mgr.json()
    assert isinstance(logs, list)
    assert len(logs) > 0
    assert "feature" in logs[0]
    assert "latency_ms" in logs[0]


def test_ai_graceful_fallback_when_gemini_fails():
    """
    Verify that if the Gemini API call fails or times out,
    the system DOES NOT crash with 500 error, but returns a clean, structured fallback response.
    """
    with patch.object(ai_service, "_call_gemini", side_effect=Exception("API connection timeout")):
        # 1. Test recommendation fallback
        res = ai_service.recommend_products("Chuột văn phòng", budget=500000)
        assert res.is_fallback is True
        assert "StoreFlow AI" in res.ai_response or "kho hàng" in res.ai_response
        assert len(res.recommended_products) > 0

        # 2. Test sales report fallback
        rep = ai_service.generate_sales_report("month")
        assert rep.is_fallback is True
        assert "Báo cáo Doanh thu" in rep.ai_analysis
        assert rep.total_revenue >= 0

        # 3. Test sales QA fallback
        qa = ai_service.answer_sales_qa("Số lượng hàng tồn kho là bao nhiêu?")
        assert qa.is_fallback is True
        assert "StoreFlow AI" in qa.answer
