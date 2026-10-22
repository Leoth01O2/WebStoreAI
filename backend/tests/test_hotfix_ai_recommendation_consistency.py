import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from app.main import app
from app.services.rag_service import (
    rag_service,
    extract_budget_from_query,
    resolve_effective_budget,
    parse_query_requirements,
    classify_product_type,
    check_product_eligibility,
    extract_brand_from_query,
    match_product_brand,
)
from app.services.ai_service import ai_service
from app.services.ai_providers.ollama_provider import detect_repetition
from app.core.rate_limiter import ai_rate_limiter

client = TestClient(app)


@pytest.fixture(autouse=True)
def reset_rate_limiter():
    ai_rate_limiter.reset()
    yield
    ai_rate_limiter.reset()


# ==============================================================================
# TEST 1: Budget in Natural Language Query (No separate input)
# ==============================================================================
def test_01_natural_language_budget_extraction_and_recommendation():
    """1. Chuột gaming không dây dưới 700.000đ, chỉ ghi ngân sách trong câu hỏi."""
    query = "Tôi cần một con chuột gaming không dây dưới 700.000đ, cửa hàng còn mẫu nào?"
    budget = extract_budget_from_query(query)
    assert budget == 700000.0

    reqs = parse_query_requirements(query)
    assert reqs["target_type"] == "mouse"
    assert reqs["is_gaming"] is True
    assert reqs["is_wireless"] is True

    # Call AI service with provider="grounded"
    res = ai_service.recommend_products(user_query=query, budget=None, provider="grounded")
    assert res.effective_budget == 700000.0
    assert len(res.recommended_products) == 1
    assert res.recommended_products[0].sku == "SP-GAME-02"
    assert res.recommended_products[0].selling_price == 680000.0
    assert res.recommended_products[0].stock_quantity > 0


# ==============================================================================
# TEST 2: Query Budget + Separate Budget Input Combined Strictly (min rule)
# ==============================================================================
def test_02_query_budget_plus_separate_budget_input():
    """2. Cùng câu hỏi có thêm ô ngân sách 700000."""
    query = "Tôi cần một con chuột gaming không dây dưới 700.000đ, cửa hàng còn mẫu nào?"
    effective = resolve_effective_budget(query, 700000.0)
    assert effective == 700000.0

    # If separate input is stricter (650,000đ)
    strict_effective = resolve_effective_budget(query, 650000.0)
    assert strict_effective == 650000.0

    res = ai_service.recommend_products(user_query=query, budget=700000.0, provider="grounded")
    assert len(res.recommended_products) == 1
    assert res.recommended_products[0].sku == "SP-GAME-02"


# ==============================================================================
# TEST 3: Products Exceeding Budget are Excluded from Eligible
# ==============================================================================
def test_03_over_budget_products_excluded_from_eligible():
    """3. Sản phẩm vượt ngân sách không lọt vào Eligible Recommendations."""
    # Dummy candidate with price > budget
    over_budget_prod = {
        "id": 999,
        "sku": "SP-EXPENSIVE",
        "name": "Chuột Gaming Không dây Pro Esports",
        "category_name": "Gaming Gear",
        "selling_price": 1200000.0,
        "stock_quantity": 10,
        "status": "active",
        "description": "Chuột gaming không dây",
    }
    reqs = {"target_type": "mouse", "is_gaming": True, "is_wireless": True}
    is_eligible, reason = check_product_eligibility(over_budget_prod, reqs, budget_max=700000.0)
    assert is_eligible is False
    assert isinstance(reason, str)
    assert "Vượt ngân sách" in reason


# ==============================================================================
# TEST 4: Matching Price but Wrong Product Type Excluded
# ==============================================================================
def test_04_wrong_type_accessories_excluded_from_eligible():
    """4. Sản phẩm đúng giá nhưng sai loại bị loại khỏi Eligible Recommendations."""
    mousepad_prod = {
        "id": 888,
        "sku": "SP-GAME-04",
        "name": "Tấm lót chuột Led RGB Gaming Speed",
        "category_name": "Gaming Gear",
        "selling_price": 210000.0,
        "stock_quantity": 25,
        "status": "active",
        "description": "Bàn di chuột gaming đèn LED RGB",
    }
    cooler_prod = {
        "id": 889,
        "sku": "SP-GAME-05",
        "name": "Đế tản nhiệt Laptop Gaming 6 Quạt LED",
        "category_name": "Gaming Gear",
        "selling_price": 310000.0,
        "stock_quantity": 18,
        "status": "active",
        "description": "Đế tản nhiệt laptop",
    }
    office_mouse_prod = {
        "id": 890,
        "sku": "SP-OFFICE-02",
        "name": "Chuột không dây Công thái học Silent M3",
        "category_name": "Chuột & Bàn phím",
        "selling_price": 320000.0,
        "stock_quantity": 35,
        "status": "active",
        "description": "Chuột không dây văn phòng",
    }

    reqs = {"target_type": "mouse", "is_gaming": True, "is_wireless": True}

    # Mousepad must be rejected because target_type is mouse
    is_el_pad, reason_pad = check_product_eligibility(mousepad_prod, reqs, budget_max=700000.0)
    assert is_el_pad is False
    assert isinstance(reason_pad, str)
    assert "Không đúng loại" in reason_pad

    # Cooler must be rejected
    is_el_cool, reason_cool = check_product_eligibility(cooler_prod, reqs, budget_max=700000.0)
    assert is_el_cool is False

    # Office mouse rejected because not gaming
    is_el_off, reason_off = check_product_eligibility(office_mouse_prod, reqs, budget_max=700000.0)
    assert is_el_off is False
    assert isinstance(reason_off, str)
    assert "Không phải sản phẩm dòng Gaming" in reason_off


# ==============================================================================
# TEST 5: Out of Stock Products are Excluded
# ==============================================================================
def test_05_out_of_stock_products_excluded():
    """5. Sản phẩm hết hàng không được tư vấn là còn hàng."""
    oos_prod = {
        "id": 777,
        "sku": "SP-GAME-OOS",
        "name": "Chuột Gaming Không dây Siêu nhẹ",
        "category_name": "Gaming Gear",
        "selling_price": 500000.0,
        "stock_quantity": 0,
        "status": "active",
        "description": "Chuột gaming không dây",
    }
    reqs = {"target_type": "mouse", "is_gaming": True, "is_wireless": True}
    is_eligible, reason = check_product_eligibility(oos_prod, reqs, budget_max=700000.0)
    assert is_eligible is False
    assert isinstance(reason, str)
    assert "hết hàng" in reason


# ==============================================================================
# TEST 6: No Matching Product Case
# ==============================================================================
def test_06_no_matching_product_handled_gracefully():
    """6. Không có sản phẩm phù hợp."""
    # Mouse under 100,000 gaming wireless
    res = ai_service.recommend_products(
        user_query="Chuột gaming không dây dưới 100.000đ",
        budget=100000.0,
        provider="grounded"
    )
    assert len(res.recommended_products) == 0
    assert "chưa có sản phẩm nào" in res.ai_response or "KHÔNG TÌM THẤY" in res.ai_response


# ==============================================================================
# TEST 7: Out-of-Domain Query (e.g. Máy giặt)
# ==============================================================================
def test_07_out_of_domain_query():
    """7. Câu hỏi ngoài danh mục như máy giặt."""
    res = ai_service.recommend_products(
        user_query="Cửa hàng có bán máy giặt Inverter Electrolux không?",
        provider="grounded"
    )
    assert len(res.recommended_products) == 0
    assert "không kinh doanh" in res.ai_response.lower()


# ==============================================================================
# TEST 8: Repetition Loop Detection
# ==============================================================================
def test_08_repetition_loop_detection():
    """8. Ollama không được sinh đoạn văn lặp hàng chục lần."""
    loop_text = "Chuột Gaming Không dây Siêu nhẹ 55g là sản phẩm tuyệt vời. " * 15
    assert detect_repetition(loop_text) is True

    normal_text = "Chuột Gaming Không dây Siêu nhẹ 55g có trọng lượng nhẹ, mắt đọc quang học chuẩn gaming và kết nối 2.4GHz ổn định."
    assert detect_repetition(normal_text) is False


# ==============================================================================
# TEST 9: LLM Output Contradiction Detection Triggers Fallback
# ==============================================================================
def test_09_llm_contradiction_detection():
    """9. LLM kết luận trái với danh sách eligible phải bị phát hiện và xử lý."""
    verified = [{"id": 1, "sku": "SP-GAME-02", "name": "Chuột Gaming Không dây", "stock_quantity": 12, "selling_price": 680000}]

    contradicting_text = "Rất tiếc hiện tại cửa hàng không có sản phẩm nào phù hợp với yêu cầu của bạn."
    assert ai_service._contradicts_verified_products(contradicting_text, verified) is True

    valid_text = "Dựa trên yêu cầu của bạn, cửa hàng có mẫu Chuột Gaming Không dây Siêu nhẹ 55g (SP-GAME-02) giá 680.000đ còn 12 chiếc."
    assert ai_service._contradicts_verified_products(valid_text, verified) is False


# ==============================================================================
# TEST 10: Grounded Fallback Adheres to Strict Filters
# ==============================================================================
def test_10_grounded_fallback_strict_filtering():
    """10. Kết quả Grounded Fallback tuân thủ cùng điều kiện lọc."""
    res = ai_service.recommend_products(
        user_query="Tôi cần một con chuột gaming không dây dưới 700.000đ",
        budget=700000.0,
        provider="grounded"
    )
    assert res.is_fallback is True
    assert res.provider == "grounded"
    assert len(res.recommended_products) == 1
    assert res.recommended_products[0].sku == "SP-GAME-02"


# ==============================================================================
# TEST 11: Frontend/API Level Strict Separation
# ==============================================================================
def test_11_api_response_strict_separation():
    """11. API chỉ trả về sản phẩm eligible trong recommended_products, alternatives tách riêng."""
    res = client.post("/api/v1/ai/recommend", json={
        "query": "Tôi cần một con chuột gaming không dây dưới 700.000đ, cửa hàng còn mẫu nào?",
        "budget": 700000.0,
        "limit": 5,
        "provider": "grounded"
    })
    assert res.status_code == 200
    data = res.json()
    assert len(data["recommended_products"]) == 1
    assert data["recommended_products"][0]["sku"] == "SP-GAME-02"
    assert data["total_candidates_found"] == 1
    assert "alternative_products" in data


# ==============================================================================
# TEST 12: No Cost Price or Confidential Internal Data Leaks to Guest
# ==============================================================================
def test_12_no_cost_price_leak_to_guest():
    """12. Không rò rỉ giá vốn hay dữ liệu nội bộ cho Guest."""
    res = client.post("/api/v1/ai/recommend", json={
        "query": "Chuột gaming không dây",
        "budget": 1000000.0,
        "limit": 5,
        "provider": "grounded"
    })
    assert res.status_code == 200
    data = res.json()
    for prod in data["recommended_products"]:
        assert "cost_price" not in prod
        assert "profit" not in prod
        assert "supplier" not in prod
    for alt in data.get("alternative_products", []):
        assert "cost_price" not in alt


# ==============================================================================
# TEST 13 & 14: Safe Handling of category_name = None (Regression for HTTP 500)
# ==============================================================================
def test_13_null_category_name_unit_handling():
    """13. classify_product_type và check_product_eligibility xử lý an toàn khi category_name là None."""
    prod_null_cat = {
        "id": 9991,
        "sku": "SP-NULL-CAT",
        "name": "Chuột Gaming Không dây RGB Special",
        "category_name": None,
        "selling_price": 500000.0,
        "stock_quantity": 10,
        "status": "active",
        "description": None,
    }
    # Phải phân loại thành "mouse" an toàn, không được ném AttributeError
    p_type = classify_product_type(prod_null_cat)
    assert p_type == "mouse"

    reqs = {"target_type": "mouse", "is_gaming": True, "is_wireless": True}
    is_eligible, reason = check_product_eligibility(prod_null_cat, reqs, budget_max=700000.0)
    assert is_eligible is True
    assert reason is None


def test_14_rag_context_and_api_recommend_with_null_category_name():
    """14. Endpoint /api/v1/ai/recommend xử lý trơn tru không lỗi HTTP 500 khi candidate có category_name = None."""
    fake_candidate = [{"product_id": 9992, "distance": 0.22}]
    fake_row = {
        "id": 9992,
        "sku": "SP-TEST-NULL-02",
        "name": "Chuột Gaming Không dây Zero",
        "category_id": None,
        "category_name": None,
        "selling_price": 620000.0,
        "stock_quantity": 5,
        "unit": "cái",
        "status": "active",
        "description": None,
        "image_url": None
    }

    with patch.object(rag_service, "search_candidates", return_value=fake_candidate), \
         patch("app.services.rag_service.get_db_connection") as mock_db:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [fake_row]
        mock_conn.cursor.return_value = mock_cursor
        mock_conn.__enter__.return_value = mock_conn
        mock_db.return_value = mock_conn

        res = client.post("/api/v1/ai/recommend", json={
            "query": "Tôi cần một con chuột gaming không dây dưới 700.000đ",
            "budget": 700000.0,
            "provider": "grounded"
        })
        assert res.status_code == 200
        data = res.json()
        assert len(data["recommended_products"]) == 1
        assert data["recommended_products"][0]["sku"] == "SP-TEST-NULL-02"
        assert data["recommended_products"][0]["category_name"] == ""
        assert "StoreFlow AI" in data["ai_response"]


# ==============================================================================
# TEST 15: Brand Intent Recognition & Aliases Consistency
# ==============================================================================
def test_15_brand_intent_aliases_consistency():
    """15. 'sản phẩm hãng táo' và 'hàng Apple' nhận diện nhất quán sang brand Apple, không ép device type."""
    q_tao = "sản phẩm hãng táo"
    q_apple = "hàng Apple"

    b_tao = extract_brand_from_query(q_tao)
    b_apple = extract_brand_from_query(q_apple)

    assert b_tao is not None
    assert b_tao["canonical_name"] == "Apple"

    assert b_apple is not None
    assert b_apple["canonical_name"] == "Apple"

    req_tao = parse_query_requirements(q_tao)
    req_apple = parse_query_requirements(q_apple)

    assert req_tao["brand"] is not None
    assert req_tao["brand"]["canonical_name"] == "Apple"
    assert req_tao["target_type"] is None  # Người dùng không yêu cầu loại thiết bị cụ thể

    assert req_apple["brand"] is not None
    assert req_apple["brand"]["canonical_name"] == "Apple"
    assert req_apple["target_type"] is None


# ==============================================================================
# TEST 16: Brand Apple Missing in Catalog -> 0 Eligible Products
# ==============================================================================
def test_16_brand_apple_zero_candidates_in_catalog():
    """16. Catalog không có Apple: trả về đúng 0 sản phẩm, thông báo rõ ràng không có Apple."""
    query = "sản phẩm hãng táo"
    res = ai_service.recommend_products(user_query=query, provider="grounded")

    assert len(res.recommended_products) == 0
    assert res.total_candidates_found == 0
    assert res.alternative_products is not None
    assert len(res.alternative_products) == 0  # Không tự ý gợi ý bừa phụ kiện hay sản phẩm hãng khác
    assert "Không tìm thấy sản phẩm Apple đang có hàng tại cửa hàng" in res.ai_response

    # Kiểm tra endpoint API
    res_api = client.post("/api/v1/ai/recommend", json={
        "query": query,
        "provider": "grounded"
    })
    assert res_api.status_code == 200
    data = res_api.json()
    assert len(data["recommended_products"]) == 0
    assert data.get("alternative_products") is not None
    assert len(data["alternative_products"]) == 0
    assert "Không tìm thấy sản phẩm Apple đang có hàng tại cửa hàng" in data["ai_response"]


@pytest.fixture
def seed_sony_test_product():
    from app.core.database import get_db_connection
    old_price = None
    with get_db_connection() as conn:
        c = conn.cursor()
        c.execute("SELECT id, selling_price FROM products WHERE sku = 'SKU-841798'")
        row = c.fetchone()
        if not row:
            c.execute("""
                INSERT INTO products (
                    sku, name, category_id, cost_price, selling_price,
                    stock_quantity, min_stock_alert, unit, status, description, image_url
                ) VALUES (
                    'SKU-841798', 'Tai nghe Chống ồn Không dây Sony WH-1000XM4', 1,
                    3500000, 5490000, 8, 2, 'chiếc', 'active',
                    'Tai nghe chụp tai chống ồn chủ động ANC đỉnh cao từ Sony, pin 30 giờ.', ''
                )
            """)
        else:
            old_price = row["selling_price"]
            c.execute("UPDATE products SET selling_price = 5490000, stock_quantity = 8 WHERE sku = 'SKU-841798'")
        conn.commit()
    yield
    if old_price is not None:
        with get_db_connection() as conn:
            conn.cursor().execute("UPDATE products SET selling_price = ? WHERE sku = 'SKU-841798'", (old_price,))
            conn.commit()


# ==============================================================================
# TEST 17: Brand Sony Catalog Retrieval
# ==============================================================================
def test_17_brand_sony_catalog_retrieval(seed_sony_test_product):
    """17. Truy vấn đồ Sony tìm đúng các mặt hàng Sony trong catalog (nếu có)."""
    query = "Cửa hàng có đồ của Sony không?"
    reqs = parse_query_requirements(query)
    assert reqs["brand"] is not None
    assert reqs["brand"]["canonical_name"] == "Sony"
    assert reqs["target_type"] is None

    res = ai_service.recommend_products(user_query=query, provider="grounded")
    assert len(res.recommended_products) >= 1
    for p in res.recommended_products:
        # Tất cả sản phẩm được gợi ý phải là của Sony
        assert isinstance(p.name, str)
        assert isinstance(p.description, str)
        assert "sony" in p.name.lower() or "sony" in p.description.lower()
        assert p.stock_quantity > 0
        assert p.status == "active"


# ==============================================================================
# TEST 18: Brand + Device Type + Budget Combined
# ==============================================================================
def test_18_brand_device_type_and_budget_combined(seed_sony_test_product):
    """18. Truy vấn kết hợp thương hiệu + loại thiết bị + ngân sách."""
    query = "Tai nghe Sony chống ồn dưới 6.000.000đ"
    reqs = parse_query_requirements(query)
    assert reqs["brand"] is not None
    assert reqs["brand"]["canonical_name"] == "Sony"
    assert reqs["target_type"] == "headphone"
    assert reqs["is_anc"] is True

    budget = extract_budget_from_query(query)
    assert budget == 6000000.0

    res = ai_service.recommend_products(user_query=query, provider="grounded")
    assert len(res.recommended_products) >= 1
    assert res.recommended_products[0].sku == "SKU-841798"
    assert res.recommended_products[0].selling_price <= 6000000.0

    # Nếu ngân sách thấp hơn giá bán (1.000.000đ so với 5.490.000đ)
    strict_query = "Tai nghe Sony dưới 1.000.000đ"
    res_strict = ai_service.recommend_products(user_query=strict_query, provider="grounded")
    assert len(res_strict.recommended_products) == 0


# ==============================================================================
# TEST 19: Brand Only Does Not Force Arbitrary Device Type
# ==============================================================================
def test_19_brand_only_does_not_infer_device_type():
    """19. Khi câu hỏi chỉ chứa thương hiệu, không được tự suy diễn sang loại thiết bị cụ thể."""
    test_queries = [
        ("sản phẩm hãng táo", "Apple"),
        ("hàng Apple", "Apple"),
        ("Cửa hàng có đồ của Sony không?", "Sony"),
        ("Có sản phẩm Logitech nào?", "Logitech"),
    ]
    for q, expected_brand in test_queries:
        reqs = parse_query_requirements(q)
        assert reqs["brand"] is not None
        assert reqs["brand"]["canonical_name"] == expected_brand
        assert reqs["target_type"] is None, f"Query '{q}' should not infer target_type, got {reqs['target_type']}"


# ==============================================================================
# TEST 20: No Random Top-K Suggestions When Brand Not Found
# ==============================================================================
def test_20_no_random_topk_when_brand_not_found():
    """20. Không tự đề xuất Top-K ngẫu nhiên (Sony, bàn di chuột, hàng test...) khi không tìm thấy thương hiệu."""
    query = "sản phẩm hãng táo"
    res = ai_service.recommend_products(user_query=query, provider="grounded")
    assert res.recommended_products == []
    assert res.alternative_products == []

    # Kiểm tra chi tiết trong ngữ cảnh RAG
    rag_ctx = rag_service.get_grounded_recommendation_context(query)
    assert rag_ctx["status"] == "brand_not_found"
    assert rag_ctx["brand_name"] == "Apple"
    assert rag_ctx["products"] == []
    assert rag_ctx["alternative_products"] == []


# ==============================================================================
# TEST 21: Provider Consistency for Brand Filtering
# ==============================================================================
def test_21_provider_consistency_for_brand_filtering():
    """21. Gemini, Ollama, Grounded đều nhất quán trả về 0 sản phẩm phù hợp khi thương hiệu không có trong catalog."""
    query = "sản phẩm hãng táo"

    # 1. Grounded mode
    res_grounded = ai_service.recommend_products(user_query=query, provider="grounded")
    assert res_grounded.recommended_products == []
    assert res_grounded.alternative_products == []

    # 2. Ollama mode (chạy với fallback nếu không có model local thật)
    res_ollama = ai_service.recommend_products(user_query=query, provider="ollama")
    assert res_ollama.recommended_products == []
    assert res_ollama.alternative_products == []

    # 3. Gemini mode (mocked provider để kiểm tra tập sản phẩm xác minh)
    with patch("app.services.ai_providers.manager.AIProviderManager.execute_with_fallback") as mock_exec:
        mock_exec.return_value = (
            "Hiện tại StoreFlow AI chưa có sản phẩm Apple trong kho hàng.",
            "gemini",
            False,
            {}
        )
        res_gemini = ai_service.recommend_products(user_query=query, provider="gemini")
        assert res_gemini.recommended_products == []
        assert res_gemini.alternative_products == []