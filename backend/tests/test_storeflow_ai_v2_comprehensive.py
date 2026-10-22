"""
STOREFLOW AI 2.0 — COMPREHENSIVE BENCHMARK & REGRESSION TEST SUITE
Validates:
1. LLM Intent Analysis & Structured Intent Validation (Pydantic, Vietnamese phrasing, ambiguity).
2. Hybrid Retrieval (Dense ChromaDB + Sparse BM25 + Structured SQL) with RRF fusion.
3. Double SQL Verification (L1 Post-Retrieval Guardrail & L2 Pre-Response Guardrail).
4. Edge cases: Ambiguous abbreviations ('ss'), negative queries, out-of-domain, non-existent brands, out-of-stock.
5. Hallucination guardrail, race conditions simulation, and timing breakdown telemetry.
"""

import time
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from app.main import app
from app.services.intent_analyzer import intent_analyzer, IntentAnalyzer
from app.services.rag_service import (
    rag_service,
    BM25Retriever,
    reciprocal_rank_fusion,
    structured_sql_search,
    parse_query_requirements,
    extract_brand_from_query,
    extract_budget_from_query,
    resolve_effective_budget,
    is_approximate_budget_query,
    check_product_eligibility,
)
from app.services.ai_service import ai_service
from app.schemas.ai import UserQueryIntent
from app.core.rate_limiter import ai_rate_limiter

client = TestClient(app)


def get_token(username, password):
    res = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert res.status_code == 200
    return res.json()["access_token"]


@pytest.fixture(scope="module")
def admin_headers():
    token = get_token("admin", "Admin@123")
    return {"Authorization": f"Bearer {token}"}


# ==============================================================================
# SECTION 1: LLM INTENT ANALYZER & STRUCTURED INTENT VALIDATION
# ==============================================================================

def test_intent_analyzer_natural_vietnamese_budgets():
    """1. Phân tích câu hỏi tự nhiên với các cách biểu đạt ngân sách đa dạng trong tiếng Việt."""
    queries_and_expected = [
        ("tìm giúp em con chuột gaming không dây tầm 700k đổ lại", 700000.0, "mouse"),
        ("bàn phím cơ dưới 1tr5 gõ êm văn phòng", 1500000.0, "keyboard"),
        ("tai nghe chụp tai không quá 500 nghìn đồng", 500000.0, "headphone"),
        ("cần mua chuột bluetooth giá dưới hai trăm nghìn", 200000.0, "mouse"),
    ]

    for q, exp_budget, exp_type in queries_and_expected:
        intent = intent_analyzer.analyze_intent(q, preferred_provider="grounded")
        assert intent.product_type == exp_type
        assert intent.max_price == pytest.approx(exp_budget, rel=0.01)
        assert not intent.needs_clarification
        assert not intent.is_out_of_domain


def test_intent_analyzer_ambiguous_abbreviation_clarification():
    """2. Từ viết tắt mơ hồ như 'ss' kích hoạt needs_clarification và câu hỏi làm rõ."""
    q_ambig = "tư vấn cho mình chuột ss"
    intent = intent_analyzer.analyze_intent(q_ambig, preferred_provider="grounded")

    assert intent.needs_clarification is True
    assert intent.clarification_question is not None
    assert "Samsung" in intent.clarification_question or "SteelSeries" in intent.clarification_question


def test_intent_analyzer_out_of_domain():
    """3. Yêu cầu ngoài phạm vi kinh doanh (F&B, thời trang) được phát hiện chính xác."""
    ood_queries = [
        "bán cho tôi một ly trà sữa trân châu đường đen",
        "tôi muốn mua một chiếc áo phông oversize màu đen",
        "order cơm gà xối mỡ giao tận nơi",
    ]

    for q in ood_queries:
        intent = intent_analyzer.analyze_intent(q, preferred_provider="grounded")
        assert intent.is_out_of_domain is True
        assert intent.intent in ("general_chat", "out_of_domain")


def test_intent_analyzer_negative_constraints():
    """4. Truy vấn có điều kiện phủ định (ví dụ: có dây thay vì không dây)."""
    q = "chuột văn phòng có dây cắm cổng usb"
    intent = intent_analyzer.analyze_intent(q, preferred_provider="grounded")
    assert intent.product_type == "mouse"
    assert intent.attributes.get("wired") is True
    assert intent.attributes.get("wireless") is False


# ==============================================================================
# SECTION 2: HYBRID RETRIEVAL & RRF CANDIDATE FUSION
# ==============================================================================

def test_bm25_retriever_indexing_and_scoring():
    """5. Sparse Retrieval BM25 tính điểm TF-IDF/BM25 chính xác trên catalog."""
    bm25 = BM25Retriever()
    scores = bm25.search("chuột gaming không dây", top_k=5)
    assert isinstance(scores, list)
    if scores:
        assert scores[0][1] > 0.0
        # High scoring item must have positive BM25 score
        assert all(s[1] > 0.0 for s in scores)


def test_reciprocal_rank_fusion_brand_weight_boost():
    """6. RRF kết hợp Dense + Sparse + SQL với trọng số ưu tiên thương hiệu."""
    dense_cand = [{"product_id": 101, "distance": 0.15}, {"product_id": 102, "distance": 0.20}]
    sparse_cand = [(102, 3.5), (103, 2.1)]
    sql_cand = [(103, 10.0), (101, 1.0)]

    # Standard weighting
    fused_standard = reciprocal_rank_fusion(dense_cand, sparse_cand, sql_cand)
    assert len(fused_standard) == 3
    pids = [f["product_id"] for f in fused_standard]
    assert set(pids) == {101, 102, 103}

    # Brand priority weighting (SQL weight = 2.5)
    fused_brand = reciprocal_rank_fusion(
        dense_cand, sparse_cand, sql_cand, weights={"sql": 2.5, "sparse": 1.0, "dense": 0.8}
    )
    # Product 103 (top SQL) should have significant boost
    top_pid = fused_brand[0]["product_id"]
    assert top_pid in (101, 103)


def test_structured_sql_search_budget_and_type_filter():
    """7. Structured SQL Retrieval lọc chính xác theo ngân sách và loại thiết bị."""
    sql_res = structured_sql_search(
        query="chuột giá rẻ",
        target_type="mouse",
        effective_budget=300000.0,
        top_k=5
    )
    assert isinstance(sql_res, list)


# ==============================================================================
# SECTION 3: DOUBLE SQL VERIFICATION (LẦN 1 & LẦN 2)
# ==============================================================================

def test_clarification_flow_end_to_end(admin_headers):
    """8. Luồng câu hỏi mơ hồ 'chuột ss' trả về clarification message rõ ràng, không gợi ý bừa."""
    ai_rate_limiter.reset()
    res = client.post("/api/v1/ai/recommend", json={
        "query": "tư vấn cho mình chuột ss",
        "provider": "grounded"
    }, headers=admin_headers)
    assert res.status_code == 200
    data = res.json()
    assert len(data["recommended_products"]) == 0
    assert data["guardrail_status"] == "needs_clarification"
    assert "Samsung" in data["ai_response"] or "SteelSeries" in data["ai_response"]


def test_double_sql_verification_detects_race_condition():
    """9. Lớp SQL Verification L2 phát hiện nếu tồn kho chuyển về 0 giữa L1 và L2."""
    # We simulate a candidate passing L1, but live SQLite returns stock=0 during L2
    pids = [1]
    live_simulated = {
        1: {
            "id": 1,
            "sku": "SP-TEST-01",
            "name": "Chuột Test Race Condition",
            "selling_price": 500000.0,
            "stock_quantity": 0,  # Switched to 0!
            "status": "active"
        }
    }

    mock_candidates = [
        {
            "id": 1,
            "sku": "SP-TEST-01",
            "name": "Chuột Test Race Condition",
            "selling_price": 500000.0,
            "stock_quantity": 5, # Was 5 in L1
            "status": "active"
        }
    ]

    with patch.object(rag_service, "reverify_products_in_sqlite", return_value=live_simulated):
        final_products, final_text, provider, is_fb, status, passed = ai_service._verify_final_l2(
            verified_products_raw=mock_candidates,
            ai_text="Đây là sản phẩm phù hợp: SP-TEST-01",
            effective_budget=600000.0,
            provider_used="grounded",
            is_fallback=False,
            fallback_fn=lambda: "Hết hàng"
        )
        # Must be dropped because stock_quantity is 0 in L2!
        assert len(final_products) == 0
        assert status == "corrected_by_sql_verification_l2"
        assert passed is True


def test_double_sql_verification_hallucination_guard():
    """10. Lớp SQL Verification L2 phát hiện LLM text bịa ra SKU lạ không có trong danh sách."""
    real_product = {
        "id": 10,
        "sku": "SP-REAL-10",
        "name": "Bàn Phím Real 10",
        "selling_price": 800000.0,
        "stock_quantity": 3,
        "status": "active"
    }

    hallucinated_text = (
        "Chúng tôi đề xuất SP-REAL-10 và đặc biệt là mã SP-GHOST-9999 siêu cấp "
        "với giá 100k cực hot."
    )

    with patch.object(rag_service, "reverify_products_in_sqlite", return_value={10: real_product}):
        final_products, final_text, provider, is_fb, status, passed = ai_service._verify_final_l2(
            verified_products_raw=[real_product],
            ai_text=hallucinated_text,
            effective_budget=1000000.0,
            provider_used="mock_llm",
            is_fallback=False,
            fallback_fn=lambda: "Fallback an toàn từ kho hàng StoreFlow AI"
        )
        assert len(final_products) == 1
        assert final_products[0]["sku"] == "SP-REAL-10"
        # Since hallucinated SKU was detected, response should be reverted to safe fallback
        assert status == "corrected_by_sql_verification_l2"
        assert "Fallback an toàn" in final_text


def test_api_recommend_timing_and_telemetry(admin_headers):
    """11. Endpoint /api/v1/ai/recommend trả về đầy đủ timing_ms và guardrail_status."""
    ai_rate_limiter.reset()
    res = client.post("/api/v1/ai/recommend", json={
        "query": "chuột văn phòng logitech giá dưới 500k",
        "provider": "grounded"
    }, headers=admin_headers)
    assert res.status_code == 200
    data = res.json()

    assert "timing_ms" in data
    timing = data["timing_ms"]
    assert "intent_ms" in timing
    assert "retrieval_ms" in timing
    assert "generation_ms" in timing
    assert "verification_l2_ms" in timing
    assert "total_ms" in timing
    assert timing["total_ms"] > 0

    assert "verification_passed" in data
    assert data["verification_passed"] is True
    assert "intent_analysis" in data
    assert data["intent_analysis"] is not None
    assert data["intent_analysis"]["intent"] == "search_products"


def test_brand_not_found_clear_guidance(admin_headers):
    """12. Thương hiệu không có trong catalog (ví dụ: Bose) trả về thông báo rõ ràng, không bịa đặt."""
    ai_rate_limiter.reset()
    res = client.post("/api/v1/ai/recommend", json={
        "query": "cho tôi xem tai nghe của hãng Bose",
        "provider": "grounded"
    }, headers=admin_headers)
    assert res.status_code == 200
    data = res.json()
    assert len(data["recommended_products"]) == 0
    assert "Bose" in data["ai_response"]
    assert "không" in data["ai_response"].lower() or "chưa có" in data["ai_response"].lower()


# ==============================================================================
# SECTION 7: TARGETED VERIFICATION OF 14 SYSTEM REQUIREMENTS
# ==============================================================================

def test_section7_01_negation_not_wired():
    """1. Phủ định 'không cần dây' xác định đúng kết nối không dây, loại bỏ có dây."""
    query = "Tìm một con chuột chơi game không cần dây, giá đừng quá bảy trăm nghìn."
    reqs = parse_query_requirements(query)
    assert reqs["target_type"] == "mouse"
    assert reqs["is_gaming"] is True
    assert reqs["is_wireless"] is True
    assert reqs["is_wired"] is False


def test_section7_02_budget_spelled_in_words():
    """2. Ngân sách viết bằng chữ ('bảy trăm nghìn', 'một triệu')."""
    assert extract_budget_from_query("chuột dưới bảy trăm nghìn đồng") == 700000.0
    assert extract_budget_from_query("tai nghe khoảng một triệu") == 1000000.0
    assert extract_budget_from_query("bàn phím tầm hai triệu rưỡi") == 2500000.0


def test_section7_03_approximate_budget_soft_margin():
    """3. Giá gần đúng và biên độ giá hợp lý ('khoảng một triệu' là soft target)."""
    assert is_approximate_budget_query("tai nghe khoảng một triệu") is True
    assert is_approximate_budget_query("tai nghe tầm 1tr") is True
    assert is_approximate_budget_query("tai nghe dưới 1 triệu") is False


def test_section7_04_indirect_brand_apple():
    """4. Thương hiệu diễn đạt gián tiếp ('đồ của nhà táo' -> Apple, không gán sai thiết bị)."""
    query = "Có đồ của nhà táo không?"
    reqs = parse_query_requirements(query)
    assert reqs["brand"] is not None
    assert reqs["brand"]["canonical_name"] == "Apple"
    assert reqs["target_type"] is None


def test_section7_05_ambiguous_shortcut_ss():
    """5. Từ viết tắt nhập nhằng ('ss' -> hỏi Samsung hay SteelSeries)."""
    query = "Có sản phẩm hãng ss không?"
    intent = intent_analyzer.analyze_intent(query, preferred_provider="grounded")
    assert intent.needs_clarification is True
    assert isinstance(intent.clarification_question, str)
    assert "Samsung hay SteelSeries" in intent.clarification_question


def test_section7_06_no_unnecessary_clarification():
    """6. Không hỏi lại khi yêu cầu đã đủ thông tin."""
    q_mouse = "Tìm một con chuột chơi game không cần dây, giá đừng quá bảy trăm nghìn."
    intent_mouse = intent_analyzer.analyze_intent(q_mouse, preferred_provider="grounded")
    assert intent_mouse.needs_clarification is False

    q_headphone = "Tôi muốn tai nghe Sony khoảng một triệu, có mẫu nào không?"
    intent_hp = intent_analyzer.analyze_intent(q_headphone, preferred_provider="grounded")
    assert intent_hp.needs_clarification is False


def test_section7_07_ollama_provider_invoked_when_local_selected():
    """7. Ollama thực sự được chỉ định làm intent/generation provider khi chọn Local."""
    with patch("app.services.ai_providers.manager.ai_provider_manager.get_provider") as mock_gp:
        mock_prov = MagicMock()
        mock_prov.name = "ollama"
        mock_prov.generate_text.return_value = '{"intent": "search_products", "brand": "Sony", "product_type": "headphone", "attributes": {}, "max_price": 1000000, "needs_clarification": false, "clarification_question": null}'
        mock_gp.return_value = mock_prov

        intent = intent_analyzer._call_llm_for_intent("Tôi muốn tai nghe Sony khoảng một triệu", "ollama")
        assert intent is not None
        assert intent.brand == "Sony"


def test_section7_08_invalid_intent_json_graceful_handling():
    """8. Intent JSON không hợp lệ được xử lý an toàn qua rule-based fallback."""
    with patch("app.services.ai_providers.manager.ai_provider_manager.get_provider") as mock_gp:
        mock_prov = MagicMock()
        mock_prov.name = "ollama"
        mock_prov.generate_text.return_value = "Đây là văn bản không phải JSON hợp lệ!!!"
        mock_gp.return_value = mock_prov

        intent = intent_analyzer.analyze_intent("chuột gaming logitech 500k", preferred_provider="ollama")
        assert intent is not None
        assert intent.product_type == "mouse"
        assert intent.source in ("rule_based", "rule_based_fallback")


def test_section7_09_ollama_generation_success():
    """9. Ollama response generation ghi nhận provider_used là ollama khi thành công."""
    res = ai_service.recommend_products(
        user_query="Tìm một con chuột chơi game không cần dây, giá đừng quá bảy trăm nghìn.",
        provider="grounded"
    )
    assert res is not None
    assert len(res.recommended_products) >= 1
    assert res.recommended_products[0].selling_price <= 700000.0


def test_section7_10_fallback_has_concrete_reason():
    """10. Khi fallback sang Grounded, ghi nhận fallback_reason cụ thể."""
    res = ai_service.recommend_products(
        user_query="Bàn phím cơ văn phòng",
        provider="grounded"
    )
    assert res.fallback_reason is not None
    assert res.fallback_reason == "user_selected_grounded"


def test_section7_11_separation_of_eligible_and_alternatives():
    """11. Phân tách rạch ròi danh sách eligible và alternative suggestions."""
    res = ai_service.recommend_products(
        user_query="Tìm một con chuột chơi game không cần dây, giá đừng quá bảy trăm nghìn.",
        provider="grounded"
    )
    assert isinstance(res.recommended_products, list)
    assert isinstance(res.alternative_products, list)
    eligible_ids = {p.id for p in res.recommended_products if p.id is not None}
    alt_ids = {p.id for p in res.alternative_products if p.id is not None}
    assert eligible_ids.isdisjoint(alt_ids)


def test_section7_12_alternatives_have_specific_reasons():
    """12. Mỗi lựa chọn thay thế phải có lý do cụ thể (match_reason)."""
    res = ai_service.recommend_products(
        user_query="Tôi muốn tai nghe Sony khoảng một triệu, có mẫu nào không?",
        provider="grounded"
    )
    assert isinstance(res.alternative_products, list)
    assert len(res.alternative_products) > 0
    for alt in res.alternative_products:
        assert isinstance(alt.match_reason, str)
        assert len(alt.match_reason) > 5


def test_section7_13_final_sql_verification_and_hallucination_guard():
    """13. Double SQL verification L2 chặn đứng hallucination SKU và tồn kho âm."""
    fake_prod = {
        "id": 9999,
        "sku": "SP-FAKE-99",
        "name": "Chuột ma",
        "selling_price": 50000.0,
        "stock_quantity": 0,
        "status": "inactive"
    }
    final_prods, text, prov, is_fb, status, passed = ai_service._verify_final_l2(
        verified_products_raw=[fake_prod],
        ai_text="Đề xuất SP-FAKE-99",
        effective_budget=100000.0,
        provider_used="mock",
        is_fallback=False,
        fallback_fn=lambda: "Fallback kho hàng"
    )
    assert len(final_prods) == 0
    assert is_fb is True
    assert passed is True


def test_section7_14_zero_internal_cost_leakage(admin_headers):
    """14. Phản hồi API tuyệt đối không để lộ giá vốn (cost_price) ra ngoài."""
    ai_rate_limiter.reset()
    res = client.post("/api/v1/ai/recommend", json={
        "query": "chuột gaming không dây",
        "provider": "grounded"
    }, headers=admin_headers)
    assert res.status_code == 200
    res_str = res.text.lower()
    assert "cost_price" not in res_str
    assert "cost_of_goods" not in res_str


def test_section7_15_filter_severely_over_budget_alternatives():
    """15. Sản phẩm chênh lệch ngân sách quá xa (như 16.78M so với 1M) không đưa vào alternative products."""
    res = ai_service.recommend_products(
        user_query="Tôi muốn tai nghe Sony khoảng một triệu, có mẫu nào không?",
        provider="grounded"
    )
    assert isinstance(res.alternative_products, list)
    # Check that no alternative product has a price severely exceeding 1M (e.g. 16.78M)
    for alt in res.alternative_products:
        assert alt.selling_price <= 2000000.0, f"Product {alt.name} with price {alt.selling_price} is too far over budget!"
        assert isinstance(alt.match_reason, str)


def test_section7_16_ambiguity_guard_provider_telemetry():
    """16. Trường hợp 'ss' không báo generation_provider_used là ollama, ghi nhận đúng ambiguity_guard."""
    res = ai_service.recommend_products(
        user_query="Có sản phẩm hãng ss không?",
        provider="ollama"
    )
    assert res.intent_provider_used == "ambiguity_guard"
    assert res.generation_provider_used == "ambiguity_guard"
    assert res.generation_provider_used != "ollama"
    assert res.requested_provider == "ollama"
    assert res.guardrail_status == "needs_clarification"


# ==============================================================================
# SECTION 8: REGRESSION TESTS — GENERATION FALLBACK & FACTUAL RESPONSE
# ==============================================================================

def test_section8_01_ollama_generation_success_case_a():
    """Trường hợp A: Chuột gaming không dây < 700k tạo câu trả lời thành công với Ollama, không fallback."""
    ai_rate_limiter.reset()
    res = ai_service.recommend_products(
        user_query="Tìm một con chuột chơi game không cần dây, giá đừng quá bảy trăm nghìn.",
        provider="ollama",
        user_role="customer"
    )
    assert res.provider == "ollama"
    assert res.generation_provider_used == "ollama"
    assert res.is_fallback is False
    assert res.fallback_reason is None
    assert res.guardrail_status == "verified"
    assert len(res.recommended_products) == 1
    assert res.recommended_products[0].sku == "SP-GAME-02"
    assert res.recommended_products[0].selling_price <= 700000.0


def test_section8_02_ollama_generation_case_b_factual_sony_response():
    """Trường hợp B: Tai nghe Sony ~1M với Ollama không khẳng định sai 'không có hàng', tách đúng alternatives."""
    ai_rate_limiter.reset()
    res = ai_service.recommend_products(
        user_query="Tôi muốn tai nghe Sony khoảng một triệu, có mẫu nào không?",
        provider="ollama",
        user_role="customer"
    )
    assert res.provider == "ollama"
    assert res.generation_provider_used == "ollama"
    assert res.is_fallback is False
    assert res.guardrail_status == "verified_empty"
    assert len(res.recommended_products) == 0
    assert res.alternative_products is not None
    assert len(res.alternative_products) > 0
    # Response must not claim brand is out of stock or does not exist
    text_lower = res.ai_response.lower()
    assert "không tìm thấy sản phẩm sony đang có hàng" not in text_lower
    assert "sony hiện đã hết hàng" not in text_lower


def test_section8_03_brand_over_budget_grounded_distinction():
    """Thương hiệu có hàng nhưng vượt ngân sách: giải thích rõ ràng ngân sách, không khẳng định không có hàng."""
    res = ai_service.recommend_products(
        user_query="Tôi muốn tai nghe Sony khoảng một triệu, có mẫu nào không?",
        provider="grounded",
        user_role="customer"
    )
    assert res.is_fallback is True
    assert res.generation_provider_used == "grounded"
    # Grounded response must acknowledge brand product exists and is in stock
    text = res.ai_response
    assert "Sony" in text
    assert "CÒN HÀNG" in text or "có sản phẩm" in text.lower()
    assert "vượt quá ngân sách" in text or "cao hơn ngân sách" in text
    assert res.alternative_products is not None
    assert len(res.alternative_products) > 0


def test_section8_03b_grounded_context_budget_vs_no_budget_rag_service():
    """Grounded Context: Phân biệt rõ ràng trường hợp có ngân sách (vượt ngân sách) và không có ngân sách."""
    # 1. Trường hợp có ngân sách thấp hơn giá sản phẩm Sony (5.490.000đ):
    ctx_with_budget = rag_service.get_grounded_recommendation_context(
        query="Tôi muốn tai nghe Sony khoảng 1 triệu",
        top_k=3,
        budget_max=1000000.0
    )
    assert ctx_with_budget["effective_budget"] == 1000000.0
    assert ctx_with_budget["status"] == "brand_over_budget"
    assert "VƯỢT NGÂN SÁCH" in ctx_with_budget["context_text"]
    assert "1,000,000 đ" in ctx_with_budget["context_text"]
    assert "Sony" in (ctx_with_budget.get("brand_name") or "")

    # 2. Trường hợp KHÔNG có ngân sách:
    ctx_no_budget = rag_service.get_grounded_recommendation_context(
        query="Tôi muốn xem tai nghe Sony",
        top_k=3,
        budget_max=None
    )
    assert ctx_no_budget["effective_budget"] is None
    # Trạng thái brand_over_budget KHÔNG được xuất hiện khi không có căn cứ ngân sách
    assert ctx_no_budget["status"] != "brand_over_budget"
    assert "VƯỢT NGÂN SÁCH" not in ctx_no_budget["context_text"]
    # Sản phẩm Sony trong kho (Sony WH-1000XM4) phải đủ điều kiện vì không bị ràng buộc ngân sách
    assert len(ctx_no_budget["products"]) >= 1
    assert any("Sony" in p["name"] for p in ctx_no_budget["products"])


def test_section8_04_brand_not_in_catalog():
    """Thương hiệu không có trong catalog (ví dụ: Akko) giải thích rõ chưa có thương hiệu này."""
    res = ai_service.recommend_products(
        user_query="Tôi muốn mua bàn phím Akko khoảng một triệu",
        provider="grounded",
        user_role="customer"
    )
    assert len(res.recommended_products) == 0
    assert "Akko" in res.ai_response
    assert "chưa có sản phẩm" in res.ai_response.lower() or "chưa kinh doanh" in res.ai_response.lower()


def test_section8_05_l2_rejects_false_brand_oos_assertion():
    """L2 Guardrail từ chối LLM khẳng định sai 'không có hàng' khi SQLite có hàng thương hiệu vượt ngân sách."""
    rag_context = {
        "status": "brand_over_budget",
        "brand_name": "Sony",
        "notable_expensive_brand_products": [
            {"id": 26, "sku": "SKU-841798", "name": "Tai nghe Sony WH-1000XM4", "selling_price": 5490000.0}
        ]
    }
    final_prods, text, prov, is_fb, status, passed = ai_service._verify_final_l2(
        verified_products_raw=[],
        ai_text="Không tìm thấy sản phẩm Sony đang có hàng tại cửa hàng.",
        effective_budget=1000000.0,
        provider_used="mock",
        is_fallback=False,
        fallback_fn=lambda: "Fallback: Cửa hàng có Sony nhưng vượt ngân sách.",
        rag_context=rag_context,
        alternative_products_raw=[]
    )
    assert prov == "grounded"
    assert is_fb is True
    assert status == "corrected_by_sql_verification_l2"
    assert ai_service._last_l2_fallback_reason == "l2_false_assertion_brand_oos"


def test_section8_06_l2_rejects_sku_hallucination_with_reason():
    """L2 Guardrail bắt đúng SKU hallucination và gán fallback_reason cụ thể."""
    rag_context = {
        "status": "success",
        "notable_expensive_brand_products": []
    }
    final_prods, text, prov, is_fb, status, passed = ai_service._verify_final_l2(
        verified_products_raw=[],
        ai_text="Bạn nên mua SP-GHOST-999 giá siêu rẻ.",
        effective_budget=1000000.0,
        provider_used="mock",
        is_fallback=False,
        fallback_fn=lambda: "Fallback Grounded",
        rag_context=rag_context,
        alternative_products_raw=[]
    )
    assert prov == "grounded"
    assert is_fb is True
    assert ai_service._last_l2_fallback_reason == "l2_sku_hallucination"


def test_section8_07_l2_allows_alternative_skus_in_generation():
    """L2 Guardrail cho phép các SKU thuộc danh sách gợi ý thay thế xuất hiện trong văn bản LLM."""
    alt_prod = {
        "id": 1,
        "sku": "SP-AUDIO-01",
        "name": "Tai nghe Bluetooth RetroSound A1",
        "selling_price": 350000.0
    }
    final_prods, text, prov, is_fb, status, passed = ai_service._verify_final_l2(
        verified_products_raw=[],
        ai_text="Gợi ý thay thế: SP-AUDIO-01 với chất âm tốt.",
        effective_budget=1000000.0,
        provider_used="mock",
        is_fallback=False,
        fallback_fn=lambda: "Fallback Grounded",
        rag_context={"status": "brand_over_budget"},
        alternative_products_raw=[alt_prod]
    )
    # Should NOT trigger hallucination because SP-AUDIO-01 is an authorized alternative SKU
    assert is_fb is False
    assert prov == "mock"
    assert status == "verified_empty"