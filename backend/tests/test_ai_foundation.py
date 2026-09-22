import pytest
from pathlib import Path

from app.core.config import settings, BASE_DIR
from app.core.prompt_loader import prompt_loader, PromptLoader
from app.schemas.ai import (
    ProductRecommendRequest,
    ProductRecommendResponse,
    RecommendedProductItem,
    SalesReportRequest,
    SalesReportResponse,
    SalesQARequest,
    SalesQAResponse
)


def test_prompts_files_exist():
    """Verify that all 4 required prompt files exist in backend/prompts/ and are non-empty."""
    prompts_dir = BASE_DIR / "prompts"
    assert prompts_dir.exists(), "prompts directory must exist"

    required_files = [
        "system_prompt.txt",
        "product_recommendation.txt",
        "sales_report.txt",
        "sales_qa.txt"
    ]

    for filename in required_files:
        filepath = prompts_dir / filename
        assert filepath.exists(), f"Prompt file {filename} is missing"
        content = filepath.read_text(encoding="utf-8").strip()
        assert len(content) > 50, f"Prompt file {filename} appears too short or empty"


def test_prompt_loader_methods():
    """Test loading, caching, and formatting of prompt templates."""
    loader = PromptLoader()

    # System prompt
    sys_prompt = loader.get_system_prompt()
    assert "StoreFlow AI" in sys_prompt
    assert "GROUNDING" in sys_prompt

    # Recommendation template formatting
    rec_prompt = loader.format_prompt(
        "product_recommendation",
        verified_products_context="- SP001: Chuột không dây (150,000 VND)",
        user_query="Tìm chuột máy tính văn phòng",
        budget_info="Dưới 300.000 đ"
    )
    assert "SP001" in rec_prompt
    assert "Tìm chuột máy tính văn phòng" in rec_prompt
    assert "Dưới 300.000 đ" in rec_prompt

    # Sales report template formatting
    report_prompt = loader.format_prompt(
        "sales_report",
        sales_data_context="Tổng doanh thu: 50,000,000 VND, 10 đơn hàng",
        report_period="Tháng này",
        additional_notes="Tập trung vào nhóm Laptop"
    )
    assert "50,000,000 VND" in report_prompt
    assert "Tháng này" in report_prompt

    # Sales QA template formatting
    qa_prompt = loader.format_prompt(
        "sales_qa",
        verified_context="Sản phẩm bán chạy nhất: Bàn phím cơ DareU",
        user_query="Mặt hàng nào bán chạy nhất tuần qua?"
    )
    assert "DareU" in qa_prompt
    assert "Mặt hàng nào bán chạy nhất" in qa_prompt


def test_prompt_loader_errors():
    """Verify error handling for missing files and missing placeholders."""
    loader = PromptLoader()

    with pytest.raises(FileNotFoundError):
        loader.get_template("non_existent_prompt_file")

    with pytest.raises(ValueError):
        # Missing required kwargs
        loader.format_prompt("product_recommendation", user_query="test")


def test_ai_schemas():
    """Verify that AI Pydantic schemas validate correctly."""
    # Recommendation request
    req = ProductRecommendRequest(query="Laptop gaming", budget=25000000, limit=3)
    assert req.query == "Laptop gaming"
    assert req.budget == 25000000
    assert req.limit == 3

    # Recommendation response
    item = RecommendedProductItem(
        id=1,
        product_id=1,
        sku="LAP001",
        name="Laptop Dell XPS",
        selling_price=30000000,
        stock_quantity=5,
        unit="chiếc",
        image_url="https://example.com/laptop.png",
        status="active",
        category_name="Laptop"
    )
    assert item.id == 1
    assert item.image_url == "https://example.com/laptop.png"
    assert item.status == "active"

    res = ProductRecommendResponse(
        ai_response="Gợi ý Laptop Dell XPS",
        recommended_products=[item],
        query="Laptop",
        total_candidates_found=1
    )
    assert len(res.recommended_products) == 1
    assert res.recommended_products[0].id == 1
    assert res.recommended_products[0].image_url == "https://example.com/laptop.png"
    assert res.is_fallback is False

    # Sales report request/response
    rep_req = SalesReportRequest(period="7_days")
    assert rep_req.period == "7_days"
    rep_res = SalesReportResponse(
        ai_analysis="Doanh thu tăng trưởng tốt",
        period="7_days",
        total_revenue=15000000,
        total_orders=12,
        low_stock_count=2,
        top_selling_products=[{"name": "Chuột", "sold": 10}]
    )
    assert rep_res.total_revenue == 15000000

    # Sales QA
    qa_req = SalesQARequest(query="Doanh thu hôm nay bao nhiêu?")
    qa_res = SalesQAResponse(answer="Hôm nay đạt 5,000,000 VND", query=qa_req.query, context_type="sql")
    assert qa_res.context_type == "sql"


def test_gemini_config_and_sdk_initialization():
    """Verify Gemini SDK configuration and client initialization."""
    assert settings.GEMINI_MODEL in ["gemini-3.6-flash", "gemini-1.5-flash", "gemini-2.5-flash"], (
        f"Unexpected default model: {settings.GEMINI_MODEL}"
    )

    # API key is configured
    assert settings.GEMINI_API_KEY, "GEMINI_API_KEY should not be empty in test environment"

    # Initialize Google GenAI client cleanly
    from google import genai
    client = genai.Client(api_key=settings.GEMINI_API_KEY)
    assert client is not None
