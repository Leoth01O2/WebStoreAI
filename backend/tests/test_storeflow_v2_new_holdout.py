"""
STOREFLOW AI 2.0 — NEW INDEPENDENT HOLDOUT EVALUATION SUITE
This test suite consists of 6 brand new, unseen queries designed to evaluate:
1. Lexical and semantic generalization on natural Vietnamese needs.
2. Capability-based retrieval without keyword matching.
3. Peripheral/host device decoupling (TV HDMI, night shift silent click, etc.).
4. Strict factual consistency (zero hallucination, zero out-of-domain products).

CRITICAL:
These tests are executed against test_webstore.db and scratch/test_chroma_data.
They are evaluated as-is without modifying business logic to game the results.
"""

import pytest
from app.services.intent_analyzer import intent_analyzer
from app.services.rag_service import rag_service
from app.services.ai_service import ai_service


def test_new_holdout_01_silent_mouse_night_shift():
    """NH 1: User works night shift, needs silent mouse that doesn't click loudly, ~300k."""
    q = "Mình làm ca đêm cần chuột bấm không kêu tiếng lách cách để không phiền phòng trọ, giá tầm ba trăm"
    intent = intent_analyzer.analyze_intent(q, preferred_provider="grounded")
    assert intent.product_type == "mouse"
    assert intent.max_price == pytest.approx(300000.0, rel=0.01)

    res = ai_service.recommend_products(user_query=q, provider="grounded")
    # Should find silent mouse (ID 7 - Chuột không dây Silent M3) either as primary or viable alternative
    all_items = res.recommended_products + (res.alternative_products or [])
    assert any("silent" in item.name.lower() or "silent" in (item.description or "").lower() for item in all_items)
    # Never recommend irrelevant products like speakers or nixie clocks
    for item in all_items:
        assert item.id in (7, 9, 22)  # Strictly mice devices


def test_new_holdout_02_stand_ergonomic_neck_strain():
    """NH 2: Functional capability: neck strain -> elevate laptop -> laptop stand under 400k."""
    q = "Ngồi làm việc cúi nhiều hay mỏi cổ, có chân đế nào nâng máy tính cao lên tầm bốn trăm ngàn không"
    intent = intent_analyzer.analyze_intent(q, preferred_provider="grounded")
    assert any("máy tính" in d.lower() or "laptop" in d.lower() for d in [intent.user_device or ""] + intent.desired_capabilities)

    res = ai_service.recommend_products(user_query=q, provider="grounded")
    # Must find Product 20 (Giá đỡ laptop Hợp kim nhôm, 290.000đ)
    assert len(res.recommended_products) >= 1
    assert any(p.id == 20 for p in res.recommended_products)
    assert all(p.selling_price <= 400000.0 for p in res.recommended_products)


def test_new_holdout_03_out_of_domain_fashion():
    """NH 3: Query for clothing / fashion must be recognized as out of domain."""
    q = "Shop có bán áo thun polo nam phong cách tối giản không"
    intent = intent_analyzer.analyze_intent(q, preferred_provider="grounded")
    res = ai_service.recommend_products(user_query=q, provider="grounded")

    assert len(res.recommended_products) == 0
    assert len(res.alternative_products or []) == 0
    # Must state store does not sell this category
    assert any(k in res.ai_response.lower() for k in ["không kinh doanh", "không có", "chuyên cung cấp", "thiết bị"])


def test_new_holdout_04_device_not_product_tv_hdmi():
    """NH 4: Host device TV HDMI + phone Type-C -> output to HDMI screen under 500k."""
    q = "Tivi nhà mình có cổng HDMI, muốn cắm nối từ điện thoại Type-C sang tivi xem phim thì mua cái gì khoảng 500k"
    res = ai_service.recommend_products(user_query=q, provider="grounded")

    # Must find Product 18 (Hub 6 trong 1 Type-C sang HDMI 4K, 420.000đ)
    assert len(res.recommended_products) >= 1
    assert any(p.id == 18 for p in res.recommended_products)
    assert res.recommended_products[0].sku == "SP-ACC-03"

    # Alternatives must never include non-video accessories like powerbanks or mice
    for alt in (res.alternative_products or []):
        assert alt.id != 18
        assert "hdmi" in alt.name.lower() or "hdmi" in (alt.description or "").lower()


def test_new_holdout_05_fast_charger_laptop_phone():
    """NH 5: Multi-device high power charger under 500k."""
    q = "Cần tìm củ sạc đa năng công suất cao cắm được cả laptop và điện thoại dưới 500k"
    intent = intent_analyzer.analyze_intent(q, preferred_provider="grounded")
    assert intent.max_price == pytest.approx(500000.0, rel=0.01)

    res = ai_service.recommend_products(user_query=q, provider="grounded")
    # Must find Product 16 (Củ sạc nhanh GaN 65W Retro Robot, 480.000đ)
    assert len(res.recommended_products) >= 1
    assert any(p.id == 16 for p in res.recommended_products)
    assert res.recommended_products[0].sku == "SP-ACC-01"


def test_new_holdout_06_nonexistent_brand_unambiguous():
    """NH 6: Brand Sennheiser not carried in store catalog."""
    q = "Tư vấn tai nghe Sennheiser chính hãng tầm 1 triệu"
    intent = intent_analyzer.analyze_intent(q, preferred_provider="grounded")
    assert intent.brand == "Sennheiser"

    res = ai_service.recommend_products(user_query=q, provider="grounded")
    # Must have 0 eligible products for non-existent brand Sennheiser
    assert len(res.recommended_products) == 0
    # Must clearly explain Sennheiser is not in catalog
    assert "sennheiser" in res.ai_response.lower()
