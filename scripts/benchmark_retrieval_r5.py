"""
scripts/benchmark_retrieval_r5.py — R5 Retrieval Quality & Zero-Hallucination Benchmark
Evaluates the dense vector retrieval + SQLite truth guard pipeline on 10 realistic queries.
"""
import sys
import os
from pathlib import Path

# Fix terminal encoding on Windows
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if sys.stderr and hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

# Setup python path to import app modules
CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent
BACKEND_DIR = PROJECT_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.services.rag_service import rag_service

# The exact 10 realistic evaluation queries for Phase R5
BENCHMARK_QUERIES = [
    {
        "id": "Q_NEW_01",
        "category": "Natural Language & Intent",
        "query": "Cần một con chuột không dây pin trâu dùng văn phòng cả ngày",
        "budget": 1000000,
        "expected_domain": "in_domain",
        "min_expected_matches": 1
    },
    {
        "id": "Q_NEW_02",
        "category": "Multi-Condition with Budget",
        "query": "Tìm bàn phím cơ gõ êm có đèn LED giá dưới 1 triệu",
        "budget": 1000000,
        "expected_domain": "in_domain",
        "min_expected_matches": 1
    },
    {
        "id": "Q_NEW_03",
        "category": "Near-Name / Non-Catalog Product",
        "query": "chuot logitec g502",
        "budget": None,
        "expected_domain": "in_domain",
        # Store catalog has NO Logitech G502 -> returning 0 matches guarantees Zero-Hallucination (FAR=0%)
        "expected_zero_match": True
    },
    {
        "id": "Q_NEW_04",
        "category": "Non-Existent / Out-of-Domain",
        "query": "Mua máy giặt Electrolux inverter 9kg",
        "budget": 10000000,
        "expected_domain": "out_of_domain",
        "expected_zero_match": True
    },
    {
        "id": "Q_NEW_05",
        "category": "Out-of-Stock Explicit Check",
        "query": "chuột gaming razer deathadder v3",
        "budget": None,
        "expected_domain": "in_domain",
        "min_expected_matches": 1 # Resolves to gaming mice in catalog or flags OOS
    },
    {
        "id": "Q_NEW_06",
        "category": "Ultra Low Budget Restriction",
        "query": "Cáp sạc nhanh điện thoại giá học sinh sinh viên dưới 100k",
        "budget": 100000,
        "expected_domain": "in_domain",
        # Lowest cable in store is 110,000đ -> budget filter correctly prunes to 0
        "expected_zero_match": True
    },
    {
        "id": "Q_NEW_07",
        "category": "Office Setup Consultation",
        "query": "Bộ giá đỡ laptop và hub chuyển đổi cổng USB Type-C cho macbook",
        "budget": 1500000,
        "expected_domain": "in_domain",
        "min_expected_matches": 1
    },
    {
        "id": "Q_NEW_08",
        "category": "Audio & Acoustics",
        "query": "Tai nghe bluetooth chụp tai chống ồn chủ động nghe nhạc",
        "budget": 3000000,
        "expected_domain": "in_domain",
        "min_expected_matches": 1
    },
    {
        "id": "Q_NEW_09",
        "category": "Mobile Charging Powerbank",
        "query": "Sạc dự phòng dung lượng cao sạc nhanh cho iphone",
        "budget": 1000000,
        "expected_domain": "in_domain",
        "min_expected_matches": 1
    },
    {
        "id": "Q_NEW_10",
        "category": "Gaming Gear Hall Effect",
        "query": "Tay cầm chơi game tay cầm fifa có cần analog hall effect chống trôi",
        "budget": 1000000,
        "expected_domain": "in_domain",
        "min_expected_matches": 1
    }
]

def run_benchmark():
    print("=== RETRIEVAL BENCHMARK: 10 REALISTIC QUERIES (STOREFLOW AI 2.0 - R5) ===")
    passed = 0
    total = len(BENCHMARK_QUERIES)

    for item in BENCHMARK_QUERIES:
        res = rag_service.get_grounded_recommendation_context(
            query=item["query"],
            top_k=3,
            budget_max=item["budget"]
        )
        status = res.get("status")
        matched_products = res.get("products", [])
        num_matches = len(matched_products)

        # Standardized Evaluation Criteria:
        # 1. Out-of-domain queries must yield out_of_domain status or 0 matches
        # 2. Queries expecting 0 matches (non-catalog products or budget underflow) must return exactly 0 matches
        # 3. In-catalog product queries must return >= min_expected_matches without OOD false positives
        if item.get("expected_domain") == "out_of_domain":
            is_ok = (status == "out_of_domain" or num_matches == 0)
        elif item.get("expected_zero_match"):
            is_ok = (num_matches == 0)
        else:
            is_ok = (num_matches >= item.get("min_expected_matches", 1) and status != "out_of_domain")

        if is_ok:
            passed += 1
            mark = "PASS"
        else:
            mark = "FAIL"

        print(f"[{mark}] {item['id']} ({item['category']}):")
        print(f"       Query: '{item['query']}'")
        print(f"       Budget: {item['budget']} | Status: {status} | Matches: {num_matches}")
        for p in matched_products:
            price = p.get('selling_price') or p.get('price', 0)
            print(f"         -> [{p['id']}] {p['name']} | Giá: {price:,.0f}đ | Tồn: {p.get('stock_quantity', 0)}")

    score_pct = (passed / total) * 100
    print(f"\nFinal Retrieval Score on 10 Queries: {passed}/{total} ({score_pct:.1f}%)")
    return passed, total

if __name__ == "__main__":
    passed, total = run_benchmark()
    sys.exit(0 if passed == total else 1)
