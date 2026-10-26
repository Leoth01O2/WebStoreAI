"""
Test StoreFlow AI 2.0 — Comprehensive Ollama Consultation Quality Suite
Validates that:
1. Small models (Qwen 2.5 1.5B) or grounded pipelines do not recommend irrelevant products.
2. Category constraints (typing -> keyboard, charger vs cable, mousepad vs mouse) are strictly enforced in code.
3. Negative constraints (no dry battery, no wire) are verified before products reach the LLM or user.
4. When 0 eligible products exist, no fake SKUs or phantom models are hallucinated.
5. Alternatives strictly match the target product type.
6. Intent extraction does not leak few-shot prompt examples.
7. End-to-end recommendation returns verified in-stock products only.
"""

import pytest
import re
from app.services.intent_analyzer import intent_analyzer
from app.services.rag_service import rag_service, parse_query_requirements, check_product_eligibility
from app.services.ai_service import ai_service
from app.core.database import get_db_connection


def test_typing_need_product_type_mapping_and_no_unrelated_gadgets():
    """Typing/word processing queries must map to keyboard, rejecting smart devices or mousepads."""
    queries = [
        "Tôi cần tìm thiết bị để gõ bài tập văn bản soạn thảo nhanh",
        "Có đồ gì để gõ văn bản êm tay không shop",
        "Tư vấn mình thiết bị đánh máy và gõ code văn phòng",
    ]
    for q in queries:
        intent = intent_analyzer.analyze_intent(q, preferred_provider="grounded")
        assert intent.product_type == "keyboard", f"Failed for query: {q}"
        
        ctx = rag_service.get_grounded_recommendation_context(q)
        for p in ctx["products"]:
            cat_l = str(p.get("category_name") or "").lower()
            name_l = str(p.get("name") or "").lower()
            # Must not be smart clock, fan, lamp or mousepad
            assert not any(bad in name_l for bad in ["đồng hồ", "quạt", "lót chuột", "pad chuột", "cân điện tử"])
            assert "phím" in name_l or "keyboard" in name_l or "phím" in cat_l


def test_charger_query_excludes_cables():
    """Users asking for a charger (củ sạc, cốc sạc) must NEVER receive charging cables."""
    q = "Tìm củ sạc nhanh Type-C cho điện thoại và máy tính"
    reqs = parse_query_requirements(q)
    assert reqs.get("target_type") == "charger"

    ctx = rag_service.get_grounded_recommendation_context(q)
    for p in ctx["products"]:
        sku = p.get("sku")
        name_l = (p.get("name") or "").lower()
        # Ensure cable product SP-ACC-02 is excluded
        assert sku != "SP-ACC-02", "Charging cable was incorrectly classified as eligible charger!"
        assert "cáp" not in name_l or "củ" in name_l, f"Product {sku} ({name_l}) appears to be a cable, not a charger"


def test_dry_battery_negative_constraint_strictly_enforced():
    """Rechargeable mouse request strictly forbidding dry battery (pin tiểu/pin AA)."""
    q = "Chuột không dây dùng pin sạc type c, tuyệt đối không dùng pin tiểu"
    intent = intent_analyzer.analyze_intent(q, preferred_provider="grounded")
    assert any("pin" in n.lower() for n in intent.negative_constraints)

    # Candidate products: one rechargeable, one using dry battery
    prod_rechargeable = {
        "id": 901,
        "name": "Chuột không dây Silent Pro Sạc Type-C",
        "description": "Chuột văn phòng pin sạc Lithium qua cổng Type-C tiện lợi",
        "selling_price": 300000,
        "stock_quantity": 10,
        "status": "active",
        "category_name": "Chuột máy tính"
    }
    prod_dry_battery = {
        "id": 902,
        "name": "Chuột không dây Office AA",
        "description": "Sử dụng 1 viên pin tiểu AA, thời lượng pin 12 tháng",
        "selling_price": 250000,
        "stock_quantity": 5,
        "status": "active",
        "category_name": "Chuột máy tính"
    }

    reqs = parse_query_requirements(q)
    el_rechargeable, _ = check_product_eligibility(prod_rechargeable, reqs, 500000)
    el_dry, reason_dry = check_product_eligibility(prod_dry_battery, reqs, 500000)

    assert el_rechargeable is True
    assert el_dry is False
    assert "pin tiểu" in reason_dry.lower() or "pin" in reason_dry.lower()


def test_silent_click_office_requirement():
    """Silent click requirement must only accept products with explicit quiet/silent confirmation."""
    q = "Chuột không dây văn phòng bấm êm không kêu lách cách làm phiền người bên cạnh"
    intent = intent_analyzer.analyze_intent(q, preferred_provider="grounded")
    assert intent.attributes.get("silent") is True

    ctx = rag_service.get_grounded_recommendation_context(q)
    # Check that any eligible product has silent evidence
    for p in ctx["products"]:
        text = f"{p.get('name', '')} {p.get('description', '')}".lower()
        assert any(w in text for w in ["silent", "êm", "yên tĩnh", "không gây tiếng", "không ồn", "giảm ồn"])


def test_zero_eligible_results_in_no_hallucinated_products_or_skus():
    """When query asks for an impossible product, eligible list must be empty and response must not invent SKUs."""
    q = "Chuột chơi game không dây tích hợp máy đo huyết áp và nhiệt kế"
    ctx = rag_service.get_grounded_recommendation_context(q)
    assert len(ctx["products"]) == 0

    # Ensure empty context provides clear instruction
    empty_context_text = ctx["context_text"].lower()
    assert "không có sản phẩm" in empty_context_text or "0 sản phẩm" in empty_context_text or "không tìm thấy" in empty_context_text

    # Recommendation response should state no product found and not invent fake SKUs
    res = ai_service.recommend_products(user_query=q, provider="grounded")
    resp_text = res.ai_response or ""
    assert not re.search(r"CHUOT_\d+", resp_text)
    assert not re.search(r"SP-FAKE-\d+", resp_text)


def test_alternatives_must_match_target_category():
    """Alternative suggestions must stay strictly within the target product type."""
    q = "Bàn phím cơ không dây bluetooth dưới 200k"
    ctx = rag_service.get_grounded_recommendation_context(q)
    for alt in ctx["alternative_products"]:
        name_l = (alt.get("name") or "").lower()
        cat_l = (alt.get("category_name") or "").lower()
        # Must be keyboard, not mouse or audio
        assert "phím" in name_l or "keyboard" in name_l or "phím" in cat_l


def test_intent_sanitization_strips_prompt_leakage():
    """Intent analyzer must not leak HDMI, Type-C or laptop examples from prompt into simple audio/mouse queries."""
    simple_q = "Tìm tai nghe bluetooth chống ồn dưới 1 triệu"
    # Even if Ollama or LLM were to extract prompt examples, reconcile must purge them
    intent = intent_analyzer.analyze_intent(simple_q, preferred_provider="grounded")
    assert not any("hdmi" in cap.lower() for cap in intent.desired_capabilities)
    assert not any("type-c" in comp.lower() for comp in intent.device_compatibility)
    assert intent.product_type == "headphone"


def test_end_to_end_recommendation_verified_in_sqlite():
    """Verify that any product recommended by ai_service actually exists in SQLite and is active."""
    q = "Tai nghe chống ồn chủ động ANC tầm 2 triệu"
    res = ai_service.recommend_products(user_query=q, provider="grounded")
    recommended = res.recommended_products
    
    assert len(recommended) > 0, "Expected at least 1 verified ANC headphone recommendation"
    
    with get_db_connection() as conn:
        cursor = conn.cursor()
        for p in recommended:
            sku = p.sku
            cursor.execute("SELECT sku, name, selling_price, stock_quantity, status FROM products WHERE sku = ?", (sku,))
            row = cursor.fetchone()
            assert row is not None, f"Recommended SKU {sku} does not exist in SQLite DB!"
            assert row["status"] == "active", f"Recommended SKU {sku} is inactive!"
            assert row["stock_quantity"] > 0, f"Recommended SKU {sku} is out of stock!"
            assert row["selling_price"] <= 2000000, f"Recommended SKU {sku} price {row['selling_price']} exceeds budget 2,000,000!"
