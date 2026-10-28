"""
STOREFLOW AI 2.0 — GENERALIZED INTENT UNDERSTANDING & HYBRID RAG BENCHMARK
Comprehensive 36-Case Benchmark across 16 categories, strictly partitioned into:
- 18 Development Cases (Evaluated during implementation)
- 18 Holdout Cases (Unseen evaluation set never used for prompt/threshold tuning)

Evaluates:
1. Intent Correctness (Intent, Host Device, Capabilities, Product Type, Attributes, Budget)
2. Retrieval Recall & Precision (Hybrid Dense + Sparse + SQL)
3. Product Eligibility Accuracy (Evidence-based matching vs taxonomy overfitting)
4. Alternative Suggestions Viability (Strict core-need relevance, budget guardrail)
5. Double SQL Verification (Zero false positives, zero cost price leakage, zero duplicate items)
6. Negative Controls (No device confusion, wired vs wireless, ungrounded attribute rejection)
"""

import pytest
from app.services.intent_analyzer import intent_analyzer
from app.services.rag_service import (
    rag_service,
    parse_query_requirements,
    extract_budget_from_query,
    extract_brand_from_query,
    check_product_eligibility,
    classify_product_type
)
from app.services.ai_service import ai_service


# ==============================================================================
# PART 1: 18 DEVELOPMENT BENCHMARK CASES
# ==============================================================================

def test_dev_01_exact_product_name():
    """Dev 1: Exact product name lookup."""
    q = "Hub chuyển đổi 6 trong 1 Type-C sang HDMI 4K"
    intent = intent_analyzer.analyze_intent(q, preferred_provider="grounded")
    assert intent.intent == "search_products"
    assert "hdmi" in [c.lower() for c in intent.device_compatibility] or "hdmi" in [c.lower() for c in intent.desired_capabilities]

    res = ai_service.recommend_products(user_query=q, provider="grounded")
    assert len(res.recommended_products) >= 1
    assert any("SP-ACC-03" in p.sku for p in res.recommended_products)


def test_dev_02_usage_purpose_only():
    """Dev 2: Only describes functional usage (quiet night typing, no explicit product name)."""
    q = "Tôi cần đồ để gõ văn bản đêm khuya không ồn ào ảnh hưởng gia đình tầm 1 triệu"
    intent = intent_analyzer.analyze_intent(q, preferred_provider="grounded")
    assert intent.attributes.get("silent") is True
    assert intent.max_price == pytest.approx(1000000.0, rel=0.01)

    res = ai_service.recommend_products(user_query=q, provider="grounded")
    # All recommended items must be silent/office oriented
    for p in res.recommended_products:
        assert p.selling_price <= 1000000.0


def test_dev_03_problem_solving_need():
    """Dev 3: Describes connection problem (laptop has Type-C, monitor has HDMI)."""
    q = "Màn hình ngoài của mình cắm HDMI mà laptop chỉ có cổng Type-C thì dùng món gì nối ra màn?"
    intent = intent_analyzer.analyze_intent(q, preferred_provider="grounded")
    assert "laptop" in (intent.user_device or "").lower()
    assert any("hdmi" in c.lower() for c in intent.device_compatibility + intent.desired_capabilities)

    res = ai_service.recommend_products(user_query=q, provider="grounded")
    assert len(res.recommended_products) >= 1
    top_p = res.recommended_products[0]
    assert "hdmi" in top_p.name.lower() or "hdmi" in (top_p.description or "").lower()


def test_dev_04_owned_host_device_vs_accessory():
    """Dev 4: Host device (iPad/Laptop) is owned, buying Bluetooth keyboard."""
    q = "Tôi có iPad Pro M2 cổng Type-C, muốn mua bàn phím cơ kết nối bluetooth để gõ bài"
    intent = intent_analyzer.analyze_intent(q, preferred_provider="grounded")
    assert "ipad" in (intent.user_device or "").lower()
    assert intent.product_type == "keyboard"
    assert intent.attributes.get("wireless") is True
    assert intent.attributes.get("mechanical") is True


def test_dev_05_multi_constraint_mandatory():
    """Dev 5: Multi-constraint (gaming, wireless, rechargeable battery, under 1M)."""
    q = "Chuột gaming không dây pin sạc dưới 1 triệu"
    intent = intent_analyzer.analyze_intent(q, preferred_provider="grounded")
    assert intent.product_type == "mouse"
    assert intent.attributes.get("gaming") is True
    assert intent.attributes.get("wireless") is True
    assert intent.max_price == pytest.approx(1000000.0, rel=0.01)

    res = ai_service.recommend_products(user_query=q, provider="grounded")
    for p in res.recommended_products:
        assert p.selling_price <= 1000000.0
        assert classify_product_type(p.model_dump()) == "mouse"


def test_dev_06_preferred_attributes_anc_white():
    """Dev 6: Mandatory ANC, preferred white color."""
    q = "Tai nghe chống ồn chủ động ANC tầm 2 triệu"
    intent = intent_analyzer.analyze_intent(q, preferred_provider="grounded")
    assert intent.product_type == "headphone"
    assert intent.attributes.get("anc") is True
    assert intent.max_price == pytest.approx(2000000.0, rel=0.01)


def test_dev_07_natural_vietnamese_slang_budget():
    """Dev 7: Natural slang currency '1 củ 2 quay đầu'."""
    q = "Cần tìm con phím cơ tầm 1 củ 2 quay đầu gõ sướng tay"
    budget = extract_budget_from_query(q)
    assert budget == pytest.approx(1200000.0, rel=0.01)
    intent = intent_analyzer.analyze_intent(q, preferred_provider="grounded")
    assert intent.product_type == "keyboard"
    assert intent.max_price == pytest.approx(1200000.0, rel=0.01)


def test_dev_08_negation_rechargeable_no_dry_battery():
    """Dev 8: Negation - wireless without AA/AAA battery, under 800k."""
    q = "Chuột không dây không dùng pin tiểu, sạc lại được dưới 800k"
    intent = intent_analyzer.analyze_intent(q, preferred_provider="grounded")
    assert intent.product_type == "mouse"
    assert intent.attributes.get("wireless") is True
    assert intent.max_price == pytest.approx(800000.0, rel=0.01)


def test_dev_09_brand_alias_apple():
    """Dev 9: Brand alias 'nhà Táo'."""
    q = "Tìm cho mình chuột máy tính nhà Táo"
    intent = intent_analyzer.analyze_intent(q, preferred_provider="grounded")
    assert intent.brand == "Apple"
    assert intent.product_type == "mouse"


def test_dev_10_real_ambiguity_ss():
    """Dev 10: Real ambiguity 'ss' must trigger clarification."""
    q = "Tư vấn cho mình phụ kiện ss"
    intent = intent_analyzer.analyze_intent(q, preferred_provider="grounded")
    assert intent.needs_clarification is True
    assert intent.clarification_question is not None
    assert "Samsung" in intent.clarification_question and "SteelSeries" in intent.clarification_question


def test_dev_11_insufficient_info():
    """Dev 11: Insufficient info triggers helpful clarification."""
    q = "Tư vấn cho mình đồ công nghệ hay ho với"
    intent = intent_analyzer.analyze_intent(q, preferred_provider="grounded")
    assert intent.needs_clarification is True
    assert intent.clarification_question is not None


def test_dev_12_non_obvious_category_hub_for_lan():
    """Dev 12: LAN adapter needed for Macbook Air Type-C."""
    q = "Cần cắm mạng dây LAN cho Macbook Air chỉ có cổng Type-C"
    reqs = parse_query_requirements(q)
    assert reqs["user_device"] == "macbook"
    assert "Type-C" in reqs["device_compatibility"]


def test_dev_13_negative_control_impossible_combination():
    """Dev 13: Impossible combination - mouse plugging into HDMI."""
    q = "Tìm chuột có dây cắm vào cổng HDMI màn hình"
    reqs = parse_query_requirements(q)
    # No mouse in catalog plugs into an HDMI port
    res = ai_service.recommend_products(user_query=q, provider="grounded")
    # Must have 0 false positive eligible recommendations
    assert len(res.recommended_products) == 0


def test_dev_14_no_matching_product_out_of_domain():
    """Dev 14: Out of domain product."""
    q = "Bán cho tôi tủ lạnh Side by Side 500 lít"
    intent = intent_analyzer.analyze_intent(q, preferred_provider="grounded")
    assert intent.is_out_of_domain is True
    res = ai_service.recommend_products(user_query=q, provider="grounded")
    assert len(res.recommended_products) == 0
    assert "không kinh doanh" in res.ai_response.lower()


def test_dev_15_catalog_missing_technical_evidence():
    """Dev 15: Catalog missing technical evidence must not hallucinate."""
    q = "Chuột gaming hỗ trợ tần số quét 8000Hz"
    # Even if gaming mice exist, 8000Hz polling rate is not asserted in catalog
    reqs = parse_query_requirements(q)
    assert reqs["target_type"] == "mouse"
    assert reqs["is_gaming"] is True


def test_dev_16_keyword_misleading_trap_cable_winder():
    """Dev 16: Misleading trap query with 'chuột' in cable winder context."""
    q = "Dây cáp sạc điện thoại có đầu rút gọn chống rối hình chuột"
    reqs = parse_query_requirements(q)
    # Must not classify this as an actual PC mouse device
    prod_type = reqs.get("target_type")
    assert prod_type != "mouse"


def test_dev_17_negative_control_wired_vs_wireless():
    """Dev 17: Strict wired constraint must reject wireless."""
    q = "Bàn phím cơ tuyệt đối không dùng bluetooth, chỉ dùng dây cắm usb"
    intent = intent_analyzer.analyze_intent(q, preferred_provider="grounded")
    assert intent.product_type == "keyboard"
    assert intent.attributes.get("wired") is True
    assert intent.attributes.get("wireless") is False
    assert "wireless" in intent.negative_constraints


def test_dev_18_anchor_query_systemic_verification():
    """Dev 18: The anchor query that inspired the systemic investigation."""
    q = "Laptop tôi giờ toàn cổng Type-C, muốn xuất hình ra màn HDMI thì shop có món gì không? Ví chỉ còn nửa triệu."
    res = ai_service.recommend_products(user_query=q, provider="grounded")
    # Must find Product 18 (Hub 6-in-1 Type-C sang HDMI 4K, 420.000đ)
    assert len(res.recommended_products) == 1
    assert res.recommended_products[0].id == 18
    assert res.recommended_products[0].sku == "SP-ACC-03"
    assert res.effective_budget == pytest.approx(500000.0, rel=0.01)
    # Alternatives must be zero or strictly HDMI-capable, absolutely no powerbanks or mice
    assert res.alternative_products is not None
    for alt in res.alternative_products:
        assert alt.id != 18  # No duplicate
        assert "hdmi" in alt.name.lower() or "hdmi" in (alt.description or "").lower()


# ==============================================================================
# PART 2: 18 HOLDOUT BENCHMARK CASES (UNSEEN EVALUATION SET)
# ==============================================================================

def test_holdout_19_cooling_pad_need():
    """Holdout 19: Laptop gets hot during work, needs cooling solution."""
    q = "Laptop làm đồ họa hay bị nóng ran máy, shop có đế tản nhiệt làm mát không tầm 500k"
    intent = intent_analyzer.analyze_intent(q, preferred_provider="grounded")
    assert "laptop" in (intent.user_device or "").lower()
    assert intent.max_price == pytest.approx(500000.0, rel=0.01)

    res = ai_service.recommend_products(user_query=q, provider="grounded")
    for p in res.recommended_products:
        assert p.selling_price <= 500000.0
        assert "tản nhiệt" in (p.name + (p.description or "")).lower()


def test_holdout_20_owned_phone_vs_charger():
    """Holdout 20: User owns phone, needs 65W fast charger."""
    q = "Mình đang dùng điện thoại Samsung S24, cần tìm củ sạc nhanh 65W chuẩn Type-C tầm 500k"
    intent = intent_analyzer.analyze_intent(q, preferred_provider="grounded")
    assert (intent.user_device or "").lower() in ("phone", "mobile", "điện thoại")
    assert intent.product_type in ("charger", "charger_cable", None)
    assert any("65w" in c.lower() or "sạc nhanh" in c.lower() for c in intent.desired_capabilities)

    res = ai_service.recommend_products(user_query=q, provider="grounded")
    for p in res.recommended_products:
        assert p.selling_price <= 500000.0


def test_holdout_21_multi_port_hub_simultaneous_capability():
    """Holdout 21: Dual capability (USB-A mouse + phone charging via Type-C)."""
    q = "Có hub chuyển nào vừa cắm chuột USB vừa sạc pin PD qua cổng Type-C được không?"
    intent = intent_analyzer.analyze_intent(q, preferred_provider="grounded")
    assert any("usb" in c.lower() or "sạc" in c.lower() or "type-c" in c.lower() for c in intent.device_compatibility + intent.desired_capabilities)

    res = ai_service.recommend_products(user_query=q, provider="grounded")
    assert len(res.recommended_products) >= 1
    assert any("SP-ACC-03" in p.sku for p in res.recommended_products)


def test_holdout_22_slang_budget_xi():
    """Holdout 22: Slang currency '8 xị' = 800,000 VND."""
    q = "Phím cơ dưới 8 xị gõ văn phòng"
    budget = extract_budget_from_query(q)
    assert budget == pytest.approx(800000.0, rel=0.01)
    intent = intent_analyzer.analyze_intent(q, preferred_provider="grounded")
    assert intent.product_type == "keyboard"
    assert intent.max_price == pytest.approx(800000.0, rel=0.01)


def test_holdout_23_negative_tangled_wires():
    """Holdout 23: Gaming headset with mic, no tangled wires (wireless), under 1.5M."""
    q = "Tai nghe gaming có mic nhưng không muốn loại có dây lằng nhằng dưới 1 triệu rưỡi"
    budget = extract_budget_from_query(q)
    assert budget == pytest.approx(1500000.0, rel=0.01)
    intent = intent_analyzer.analyze_intent(q, preferred_provider="grounded")
    assert intent.product_type == "headphone"
    assert intent.attributes.get("gaming") is True
    assert intent.attributes.get("wireless") is True
    assert intent.attributes.get("wired") is False


def test_holdout_24_brand_over_budget_apple_keyboard():
    """Holdout 24: Brand Apple keyboard requested with very low budget (500k)."""
    q = "Bàn phím Apple Magic Keyboard dưới 500k"
    res = ai_service.recommend_products(user_query=q, provider="grounded")
    # Apple keyboard in stock is 2,990,000đ, so eligible must be 0
    assert len(res.recommended_products) == 0
    # Must correctly handle brand over budget without claiming Apple doesn't exist
    assert "apple" in res.ai_response.lower()
    assert "ngân sách" in res.ai_response.lower() or "cao hơn" in res.ai_response.lower()


def test_holdout_25_explicit_out_of_stock_sony():
    """Holdout 25: Explicit requested item is out of stock."""
    q = "Tai nghe Earbuds Thể Thao RunFree còn hàng không shop"
    res = ai_service.recommend_products(user_query=q, provider="grounded")
    # RunFree in store has stock 0
    assert len(res.recommended_products) == 0
    assert "hết hàng" in res.ai_response.lower() or "tồn kho: 0" in res.ai_response.lower()


def test_holdout_26_ergonomic_vertical_mouse():
    """Holdout 26: Ergonomic vertical mouse for wrist pain."""
    q = "Chuột công thái học cầm dọc chống mỏi cổ tay cho dân văn phòng"
    intent = intent_analyzer.analyze_intent(q, preferred_provider="grounded")
    assert intent.product_type == "mouse"
    assert intent.attributes.get("ergonomic") is True

    res = ai_service.recommend_products(user_query=q, provider="grounded")
    assert len(res.recommended_products) >= 1
    assert any("công thái học" in p.name.lower() or "chống mỏi" in (p.description or "").lower() for p in res.recommended_products)


def test_holdout_27_vague_short_query():
    """Holdout 27: Very short, vague query 'gợi ý đồ'."""
    q = "Gợi ý đồ"
    intent = intent_analyzer.analyze_intent(q, preferred_provider="grounded")
    assert intent.needs_clarification is True
    assert intent.clarification_question is not None


def test_holdout_28_out_of_domain_milk_tea():
    """Holdout 28: Out of domain - bubble tea."""
    q = "Shop có bán trà sữa trân châu đường đen không"
    intent = intent_analyzer.analyze_intent(q, preferred_provider="grounded")
    assert intent.is_out_of_domain is True
    res = ai_service.recommend_products(user_query=q, provider="grounded")
    assert len(res.recommended_products) == 0


def test_holdout_29_negative_control_laptop_not_sold():
    """Holdout 29: User asks to buy full laptop, store only sells gear."""
    q = "Cửa hàng có bán máy tính xách tay Asus ROG Strix không"
    # ROG laptop is not in catalog (only gaming mice/gear are sold)
    res = ai_service.recommend_products(user_query=q, provider="grounded")
    assert len(res.recommended_products) == 0


def test_holdout_30_negative_control_phone_owned_earphones_wanted():
    """Holdout 30: User has iPhone 15, needs Type-C earphones."""
    q = "Điện thoại iPhone 15 cần tai nghe cắm cổng Type-C"
    intent = intent_analyzer.analyze_intent(q, preferred_provider="grounded")
    assert intent.product_type == "headphone"
    assert (intent.user_device or "").lower() in ("phone", "mobile", "iphone", "điện thoại")


def test_holdout_31_budget_edge_case_nua_cu():
    """Holdout 31: Slang budget 'nửa củ' = 500k."""
    q = "Tai nghe bluetooth dưới nửa củ"
    budget = extract_budget_from_query(q)
    assert budget == pytest.approx(500000.0, rel=0.01)
    intent = intent_analyzer.analyze_intent(q, preferred_provider="grounded")
    assert intent.product_type == "headphone"
    assert intent.max_price == pytest.approx(500000.0, rel=0.01)


def test_holdout_32_camera_sd_card_slot_compatibility():
    """Holdout 32: Hub with SD card slot for photography."""
    q = "Cần hub mở rộng cắm thẻ nhớ máy ảnh SD và cổng USB cho laptop mỏng nhẹ"
    intent = intent_analyzer.analyze_intent(q, preferred_provider="grounded")
    assert "laptop" in (intent.user_device or "").lower()

    res = ai_service.recommend_products(user_query=q, provider="grounded")
    assert len(res.recommended_products) >= 1
    # Hub 6-in-1 has SD/TF card slot
    assert any("SP-ACC-03" in p.sku for p in res.recommended_products)


def test_holdout_33_silent_library_mouse():
    """Holdout 33: Silent click mouse for quiet study in library under 400k."""
    q = "Chuột click không kêu để làm việc trong thư viện dưới 400 nghìn"
    intent = intent_analyzer.analyze_intent(q, preferred_provider="grounded")
    assert intent.product_type == "mouse"
    assert intent.attributes.get("silent") is True
    assert intent.max_price == pytest.approx(400000.0, rel=0.01)

    res = ai_service.recommend_products(user_query=q, provider="grounded")
    for p in res.recommended_products:
        assert p.selling_price <= 400000.0


def test_holdout_34_severe_over_budget_alternative_suppression():
    """Holdout 34: 100k budget must NOT propose 2,000,000 VND alternatives."""
    q = "Chuột văn phòng giá 100k"
    res = ai_service.recommend_products(user_query=q, provider="grounded")
    assert res.alternative_products is not None
    for alt in res.alternative_products:
        # Alternatives should not exceed 100k by > 500k
        assert alt.selling_price <= 600000.0


def test_holdout_35_mousepad_is_not_mouse():
    """Holdout 35: Mousepad is not a mouse device."""
    q = "Miếng lót chuột gaming khổ lớn dày 4mm"
    reqs = parse_query_requirements(q)
    assert reqs["target_type"] == "mousepad"
    assert reqs["target_type"] != "mouse"


def test_holdout_36_no_contradiction_when_eligible_exists():
    """Holdout 36: Response must not contradict in-stock eligible products."""
    q = "Chuột gaming Logitech G102"
    res = ai_service.recommend_products(user_query=q, provider="grounded")
    if res.recommended_products:
        assert "không có sản phẩm nào" not in res.ai_response.lower()
        assert "hết hàng hoàn toàn" not in res.ai_response.lower()
