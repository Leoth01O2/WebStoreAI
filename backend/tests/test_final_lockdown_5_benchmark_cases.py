import os
import sys
import pytest
from app.services.ai_service import ai_service
from app.services.intent_analyzer import intent_analyzer
from app.services.rag_service import extract_budget_from_query, extract_brand_from_query, rag_service

def test_query_1_stand_no_cooler():
    """
    Câu 1: "Tôi muốn kê laptop lên cao cho đỡ mỏi cổ, không cần quạt tản nhiệt, chi phí dưới 300 nghìn"
    -> Ra SP-ACC-05 (290k), không bị nhầm thành laptop, không lỗi lặp.
    """
    query = "Tôi muốn kê laptop lên cao cho đỡ mỏi cổ, không cần quạt tản nhiệt, chi phí dưới 300 nghìn"
    
    # 1. Budget extraction
    budget = extract_budget_from_query(query)
    assert budget == 300000.0, f"Expected 300000.0, got {budget}"

    # 2. Intent analysis
    intent = intent_analyzer.analyze_intent(query, budget_input=None, preferred_provider="ollama")
    assert intent.product_type == "stand"
    assert "quạt tản nhiệt" in intent.negative_constraints
    assert intent.max_price == 300000.0

    # 3. AI Recommendation with Ollama
    res = ai_service.recommend_products(user_query=query, budget=None, provider="ollama")
    assert res.generation_provider_used == "ollama"
    assert res.is_fallback is False
    assert res.fallback_reason is None
    assert res.guardrail_status == "verified"
    
    # Check recommended products
    skus = [p.sku for p in res.recommended_products]
    assert "SP-ACC-05" in skus, f"Expected SP-ACC-05 in {skus}"
    assert len(res.recommended_products) >= 1
    # Check that price is accurate
    stand_p = next(p for p in res.recommended_products if p.sku == "SP-ACC-05")
    assert stand_p.selling_price == 290000.0
    assert stand_p.stock_quantity >= 14


def test_query_2_silent_mouse_wrist_pain():
    """
    Câu 2: "Làm việc văn phòng cả ngày bị đau cổ tay, tối về làm việc trong phòng ngủ sợ tiếng click chuột đánh thức con nhỏ, ngân sách 400k"
    -> Ra SP-OFFICE-02 (320k), không còn chuột rác SP-TEST-3E9749, SP-OFFICE-04 nằm ở gợi ý tham khảo.
    """
    query = "Làm việc văn phòng cả ngày bị đau cổ tay, tối về làm việc trong phòng ngủ sợ tiếng click chuột đánh thức con nhỏ, ngân sách 400k"
    
    # 1. Budget extraction
    budget = extract_budget_from_query(query)
    assert budget == 400000.0, f"Expected 400000.0, got {budget}"

    # 2. Intent analysis
    intent = intent_analyzer.analyze_intent(query, budget_input=None, preferred_provider="ollama")
    assert intent.product_type == "mouse"
    assert intent.attributes.get("silent") is True
    assert intent.attributes.get("ergonomic") is True

    # 3. AI Recommendation with Ollama
    res = ai_service.recommend_products(user_query=query, budget=None, provider="ollama")
    assert res.generation_provider_used == "ollama"
    assert res.is_fallback is False
    assert res.fallback_reason is None

    rec_skus = [p.sku for p in res.recommended_products]
    assert "SP-OFFICE-02" in rec_skus, f"Expected SP-OFFICE-02 in {rec_skus}"
    # Normal non-silent mouse should NOT be in primary recommendations
    assert "SP-OFFICE-04" not in rec_skus, f"SP-OFFICE-04 (non-silent) should not be in {rec_skus}"
    # Check test junk is gone
    assert not any("SP-TEST" in s for s in rec_skus)

    # SP-OFFICE-04 can be in alternative suggestions
    alt_skus = [p.sku for p in (res.alternative_products or [])]
    # Verify accurate price & stock
    silent_mouse = next(p for p in res.recommended_products if p.sku == "SP-OFFICE-02")
    assert silent_mouse.selling_price == 320000.0


def test_query_3_travel_powerbank():
    """
    Câu 3: "Sắp tới tôi đi du lịch vùng cao 3 ngày không có ổ cắm điện, sợ điện thoại sập nguồn, tầm 600 nghìn có món nào cứu cánh không?"
    -> Không bị chặn Domain Guard, ra SP-ACC-04 (590k - Pin sạc dự phòng 20000mAh).
    """
    query = "Sắp tới tôi đi du lịch vùng cao 3 ngày không có ổ cắm điện, sợ điện thoại sập nguồn, tầm 600 nghìn có món nào cứu cánh không?"
    
    # 1. Domain guard check: MUST NOT be out of domain!
    is_ood = rag_service.is_out_of_domain(query)
    assert is_ood is False, "Query must be in-domain!"

    # 2. Budget extraction
    budget = extract_budget_from_query(query)
    assert budget == 600000.0, f"Expected 600000.0, got {budget}"

    # 3. Intent analysis
    intent = intent_analyzer.analyze_intent(query, budget_input=None, preferred_provider="ollama")
    assert intent.is_out_of_domain is False
    assert intent.intent == "search_products"
    assert intent.product_type == "powerbank"

    # 4. AI Recommendation with Ollama
    res = ai_service.recommend_products(user_query=query, budget=None, provider="ollama")
    assert res.generation_provider_used == "ollama"
    assert res.is_fallback is False
    assert res.fallback_reason is None

    rec_skus = [p.sku for p in res.recommended_products]
    assert "SP-ACC-04" in rec_skus, f"Expected SP-ACC-04 in {rec_skus}"
    pb = next(p for p in res.recommended_products if p.sku == "SP-ACC-04")
    assert pb.selling_price == 590000.0


def test_query_4_macbook_typec_hub():
    """
    Câu 4: "MacBook của tôi mỏng quá chỉ có cổng Type-C, giờ muốn cắm thêm chuột USB và xuất hình ảnh ra màn hình rời HDMI, ngân sách 500k"
    -> Không bị báo thiếu brand Apple, ra SP-ACC-03 (420k - Hub Type-C).
    """
    query = "MacBook của tôi mỏng quá chỉ có cổng Type-C, giờ muốn cắm thêm chuột USB và xuất hình ảnh ra màn hình rời HDMI, ngân sách 500k"
    
    # 1. Brand extraction: must NOT bind Apple as requested brand
    brand = extract_brand_from_query(query)
    assert brand is None, f"Host device MacBook should not be parsed as requested brand, got {brand}"

    # 2. Budget extraction
    budget = extract_budget_from_query(query)
    assert budget == 500000.0, f"Expected 500000.0, got {budget}"

    # 3. Intent analysis
    intent = intent_analyzer.analyze_intent(query, budget_input=None, preferred_provider="ollama")
    assert intent.brand is None, f"Intent brand must be None, got {intent.brand}"
    assert intent.product_type == "hub_adapter", f"Target type must be hub_adapter, got {intent.product_type}"
    assert (intent.user_device or "").lower() == "macbook"

    # 4. AI Recommendation with Ollama
    res = ai_service.recommend_products(user_query=query, budget=None, provider="ollama")
    assert res.generation_provider_used == "ollama"
    assert res.is_fallback is False
    assert res.fallback_reason is None

    rec_skus = [p.sku for p in res.recommended_products]
    assert "SP-ACC-03" in rec_skus, f"Expected SP-ACC-03 in {rec_skus}"
    # Verify Hub price
    hub = next(p for p in res.recommended_products if p.sku == "SP-ACC-03")
    assert hub.selling_price == 420000.0


def test_query_5_low_budget_stand_zero_candidates():
    """
    Câu 5: "Tìm cho tôi giá đỡ laptop bằng nhôm xoay 360 độ nhưng giá dưới 50 nghìn thôi"
    -> Sản phẩm phù hợp (0), báo rõ không có giá đỡ dưới 50,000đ và đưa SP-ACC-05 (290,000đ) vào Gợi ý tham khảo.
    """
    query = "Tìm cho tôi giá đỡ laptop bằng nhôm xoay 360 độ nhưng giá dưới 50 nghìn thôi"
    
    # 1. Budget extraction: 360 độ must NOT be parsed as 360,000đ!
    budget = extract_budget_from_query(query)
    assert budget == 50000.0, f"Expected budget 50000.0, but got {budget}"

    # 2. Intent analysis
    intent = intent_analyzer.analyze_intent(query, budget_input=None, preferred_provider="ollama")
    assert intent.max_price == 50000.0, f"Expected max_price 50000.0, got {intent.max_price}"
    assert intent.product_type == "stand"

    # 3. AI Recommendation with Ollama
    res = ai_service.recommend_products(user_query=query, budget=None, provider="ollama")
    # Must keep Ollama badge
    assert res.generation_provider_used == "ollama"
    assert res.is_fallback is False
    assert res.fallback_reason is None

    # Zero recommended products within 50,000đ
    assert len(res.recommended_products) == 0, f"Expected 0 eligible products under 50k, got {len(res.recommended_products)}"
    assert res.total_candidates_found == 0

    # SP-ACC-05 (290k) must be present in alternative suggestions
    alt_skus = [p.sku for p in (res.alternative_products or [])]
    assert "SP-ACC-05" in alt_skus, f"Expected SP-ACC-05 in alternative_products, got {alt_skus}"

    # Text must clearly state no products match within budget and mention the alternative
    assert "Hiện tại trong kho chưa có sản phẩm nào đáp ứng" in res.ai_response or "chưa có sản phẩm nào đáp ứng" in res.ai_response
    assert "SP-ACC-05" in res.ai_response
    assert "290,000" in res.ai_response
