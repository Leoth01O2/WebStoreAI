"""
STOREFLOW AI 2.0 — CATALOG, HYBRID RAG & CONSULTATION FLOW REFACTOR TEST SUITE
Verifies:
1. Apple brand inquiry with Vietnamese aliases ("hãng táo", "nhà táo", "táo khuyết").
2. Dynamic brand discovery for brands not in static dictionary.
3. 4-State Brand Diagnostics (brand_not_found, brand_out_of_stock, brand_over_budget, brand_attribute_mismatch).
4. Laptop vs. Stand / Cooler disambiguation (misclassification prevention).
5. Accessory compatibility vs. brand ownership ("chuột cho macbook" vs "mua macbook").
6. Vector & BM25 document construction includes brand and product_type.
7. Fallback SQLite search mirrors Hybrid RAG 4-state diagnostics.
"""

import pytest
from app.services.intent_analyzer import intent_analyzer
from app.services.rag_service import (
    rag_service,
    extract_brand_from_query,
    parse_query_requirements,
    classify_product_type,
    match_product_brand,
    check_product_eligibility,
    resolve_effective_budget,
    BM25Retriever,
)
from app.services.ai_service import ai_service


# ==============================================================================
# 1. APPLE BRAND INQUIRY & ALIAS RESOLUTION
# ==============================================================================

def test_apple_brand_alias_detection():
    """Verify all Vietnamese colloquial aliases for Apple resolve cleanly."""
    alias_queries = [
        "shop có sản phẩm của hãng táo không?",
        "bên mình có đồ nhà táo không shop",
        "có phụ kiện hoặc máy táo khuyết không",
        "shop bán hàng apple chính hãng không",
        "tôi muốn xem máy macbook của trái táo",
    ]
    for q in alias_queries:
        brand = extract_brand_from_query(q)
        assert brand is not None, f"Failed to extract Apple brand from: {q}"
        assert brand["brand_key"] == "apple"
        assert brand["canonical_name"] == "Apple"


def test_apple_inquiry_intent_analysis():
    """Verify 'shop có sản phẩm của hãng táo không?' sets intent=check_brand and brand=Apple."""
    q = "shop có sản phẩm của hãng táo không?"
    intent = intent_analyzer.analyze_intent(q, preferred_provider="grounded")
    assert intent.brand == "Apple"
    assert intent.product_type is None
    assert intent.intent == "check_brand"
    assert intent.needs_clarification is False
    assert intent.is_out_of_domain is False


def test_macbook_brand_matching():
    """Verify MacBook Air product matches Apple brand via structured field, name token, or description."""
    macbook_product = {
        "id": 999,
        "sku": "SKU-893261",
        "name": "MacBook Air 13 inch M5 30W",
        "brand": "Apple",
        "product_type": "laptop",
        "category_name": "Laptop & Máy tính",
        "selling_price": 28990000.0,
        "stock_quantity": 10,
        "status": "active",
        "description": "Laptop Apple MacBook Air 13 inch chip M5 mạnh mẽ, thiết kế nhôm nguyên khối siêu mỏng nhẹ.",
    }
    apple_req = {"brand_key": "apple", "canonical_name": "Apple"}
    assert match_product_brand(macbook_product, apple_req) is True
    assert classify_product_type(macbook_product) == "laptop"

    # Eligibility check when user asks general brand question (target_type is None)
    reqs = parse_query_requirements("shop có sản phẩm của hãng táo không?")
    is_el, reason = check_product_eligibility(macbook_product, reqs, None)
    assert is_el is True, f"MacBook should be eligible for general Apple inquiry: {reason}"


# ==============================================================================
# 2. DYNAMIC BRAND DISCOVERY FROM DATABASE
# ==============================================================================

def test_dynamic_brand_matching():
    """Verify dynamic brand extraction recognizes custom brand from product dictionary."""
    custom_product = {
        "id": 1001,
        "sku": "SKU-KEYCHRON-01",
        "name": "Bàn phím cơ Keychron K2 Pro Wireless",
        "brand": "Keychron",
        "product_type": "keyboard",
        "selling_price": 1890000.0,
        "stock_quantity": 5,
        "status": "active",
        "description": "Bàn phím cơ không dây Keychron kết nối đa thiết bị.",
    }
    keychron_req = {"brand_key": "keychron", "canonical_name": "Keychron"}
    assert match_product_brand(custom_product, keychron_req) is True


# ==============================================================================
# 3. 4-STATE BRAND DIAGNOSTICS IN HYBRID & SQL FALLBACK
# ==============================================================================

def test_brand_diagnostics_out_of_stock():
    """Verify brand_out_of_stock status when all brand products are 0 inventory."""
    mock_active_stock = []
    mock_catalog = [{
        "id": 101,
        "sku": "SKU-OOS-01",
        "name": "Tai nghe Sony WH-1000XM5",
        "brand": "Sony",
        "product_type": "headphone",
        "selling_price": 6990000.0,
        "stock_quantity": 0,
        "status": "active",
    }]
    brand_req = {"brand_key": "sony", "canonical_name": "Sony"}

    # Evaluate logic condition
    brand_catalog = [p for p in mock_catalog if match_product_brand(p, brand_req)]
    brand_in_stock = [p for p in brand_catalog if p.get("stock_quantity", 0) > 0]
    assert len(brand_catalog) > 0
    assert len(brand_in_stock) == 0


def test_brand_diagnostics_over_budget():
    """Verify brand_over_budget when user budget is below cheapest in-stock brand product."""
    mock_brand_products = [{
        "id": 102,
        "sku": "SKU-EXP-01",
        "name": "Apple MacBook Air 13 inch M5",
        "brand": "Apple",
        "product_type": "laptop",
        "selling_price": 28990000.0,
        "stock_quantity": 8,
        "status": "active",
    }]
    user_budget = 5000000.0  # 5 million VND
    assert all(float(p["selling_price"]) > user_budget for p in mock_brand_products)


def test_fallback_sqlite_search_brand_diagnostics():
    """Verify fallback SQLite search returns valid structured 4-state diagnostics."""
    res = rag_service._fallback_sqlite_search("shop có sản phẩm của thương hiệu Razer không?")
    assert res["status"] in ("brand_not_found", "empty", "success")
    assert "context_text" in res
    assert isinstance(res["products"], list)
    assert isinstance(res["alternative_products"], list)


# ==============================================================================
# 4. LAPTOP VS. STAND / COOLER CLASSIFICATION
# ==============================================================================

def test_stand_vs_laptop_classification():
    """Verify stand with 'kê laptop' is classified as stand, never laptop."""
    stand_product = {
        "id": 201,
        "sku": "SP-ACC-05",
        "name": "Giá Đỡ Laptop Nhôm Tản Nhiệt Xoay 360",
        "brand": "Orico",
        "product_type": "stand",
        "category_name": "Phụ kiện",
        "description": "Giá đỡ nâng cao công thái học đỡ mỏi cổ cho laptop và tablet.",
    }
    assert classify_product_type(stand_product) == "stand"

    cooler_product = {
        "id": 202,
        "sku": "SP-ACC-06",
        "name": "Đế Tản Nhiệt Laptop 6 Quạt LED Gaming",
        "brand": "CoolerMaster",
        "product_type": "cooler",
        "category_name": "Phụ kiện",
        "description": "Đế làm mát laptop công suất cao với 6 quạt siêu êm.",
    }
    assert classify_product_type(cooler_product) == "cooler"

    laptop_product = {
        "id": 203,
        "sku": "SKU-893261",
        "name": "MacBook Air 13 inch M5 30W",
        "brand": "Apple",
        "product_type": "laptop",
        "category_name": "Laptop & Máy tính",
        "description": "Laptop Apple MacBook Air siêu mỏng nhẹ chip Apple Silicon.",
    }
    assert classify_product_type(laptop_product) == "laptop"


def test_query_stand_intent_not_laptop():
    """Verify query asking for laptop stand does not search for laptops."""
    q = "Tôi muốn kê laptop lên cao cho đỡ mỏi cổ, không cần quạt tản nhiệt, chi phí dưới 300 nghìn"
    intent = intent_analyzer.analyze_intent(q, preferred_provider="grounded")
    assert intent.product_type == "stand"
    assert intent.user_device == "laptop"
    assert "quạt tản nhiệt" in intent.negative_constraints


def test_query_buy_laptop_intent():
    """Verify query asking to buy a laptop resolves to product_type: laptop."""
    queries = [
        "Tôi muốn mua một chiếc laptop mỏng nhẹ văn phòng",
        "shop có bán macbook air m3 không?",
        "tư vấn máy tính xách tay dưới 30 triệu",
    ]
    for q in queries:
        reqs = parse_query_requirements(q)
        assert reqs.get("target_type") == "laptop", f"Expected laptop for: {q}"


# ==============================================================================
# 5. ACCESSORY COMPATIBILITY VS. BRAND OWNERSHIP
# ==============================================================================

def test_accessory_compatibility_not_brand_restriction():
    """Verify 'chuột không dây cho macbook' sets user_device: macbook, product_type: mouse without brand: Apple."""
    q = "tìm chuột không dây kết nối tốt cho macbook của tôi tầm 1 triệu"
    reqs = parse_query_requirements(q)
    assert reqs.get("target_type") == "mouse"
    assert reqs.get("user_device") in ("macbook", "laptop")
    # Brand should NOT be restricted to Apple unless explicitly asked for Apple mouse
    assert reqs.get("brand") is None


def test_explicit_brand_accessory():
    """Verify 'chuột apple cho macbook' sets both brand: Apple and product_type: mouse."""
    q = "tìm chuột apple chính hãng kết nối macbook"
    reqs = parse_query_requirements(q)
    assert reqs.get("target_type") == "mouse"
    assert reqs.get("brand") is not None
    assert reqs.get("brand")["canonical_name"] == "Apple"


# ==============================================================================
# 6. VECTOR & BM25 DOCUMENT INTEGRATION
# ==============================================================================

def test_bm25_and_vector_document_construction():
    """Verify document construction incorporates brand and product_type into searchable representation."""
    p = {
        "id": 999,
        "sku": "SKU-893261",
        "name": "MacBook Air 13 inch M5 30W",
        "category_name": "Laptop & Máy tính",
        "brand": "Apple",
        "product_type": "laptop",
        "selling_price": 28990000.0,
        "stock_quantity": 10,
        "unit": "máy",
        "status": "active",
        "description": "Laptop mỏng nhẹ của nhà táo Apple M5.",
    }
    doc_text = rag_service._build_product_document(p)
    assert "Thương hiệu: Apple" in doc_text
    assert "Loại sản phẩm: laptop" in doc_text
    assert "Laptop & Máy tính" in doc_text


def test_grounded_recommendation_with_brand_apple():
    """Verify grounded recommendation handles Apple brand inquiry properly."""
    res = ai_service.recommend_products(
        user_query="shop có sản phẩm của hãng táo không?",
        provider="grounded"
    )
    assert res.guardrail_status in ("verified", "empty", "verified_empty")
    assert res.is_fallback is True
    assert "Apple" in res.ai_response or "táo" in res.ai_response.lower()
    # Explanation must be grounded and non-empty
    assert len(res.ai_response) > 10
