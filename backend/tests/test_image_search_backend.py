import pytest
import io
import sqlite3
from fastapi.testclient import TestClient

from app.main import app
from app.core.config import settings
from app.core.rate_limiter import ai_rate_limiter
from app.services.image_search_service import image_search_service
from app.schemas.ai import ImageSearchQueryFeatures

client = TestClient(app)

@pytest.fixture(autouse=True)
def reset_rate_limiter():
    ai_rate_limiter.reset()
    yield
    ai_rate_limiter.reset()

# Minimal 1x1 valid PNG bytes for testing
TINY_PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde"
    b"\x00\x00\x00\x0cIDATx\x9cc\xf8\xcf\xc0\x00\x00\x03\x01\x01\x00\xc9\xfe\x92\xef\x00\x00\x00\x00IEND\xaeB`\x82"
)


def test_image_search_valid_upload_headphone():
    """Test uploading a valid image file to POST /api/v1/ai/image-search."""
    files = {
        "file": ("test_upload.png", io.BytesIO(TINY_PNG), "image/png")
    }

    response = client.post("/api/v1/ai/image-search?limit=5", files=files)
    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"

    data = response.json()
    assert "query_features" in data
    assert "results" in data
    assert "total_candidates_found" in data
    assert "execution_time_ms" in data

    # Verify query features structure
    qf = data["query_features"]
    assert "is_uncertain" in qf or "product_type" in qf
    assert "dominant_color" in qf

    # Verify results structure if any returned
    results = data["results"]
    for top in results:
        assert "product_id" in top
        assert "sku" in top
        assert "name" in top
        assert "selling_price" in top
        assert "stock_quantity" in top
        assert "in_stock" in top
        assert "relationship" in top
        assert "reason" in top
        assert "score" in top
        assert top["relationship"] in ["match", "similar", "related", "none"]


def test_image_search_invalid_file_type():
    """Test uploading invalid file extensions (.txt, .pdf) returns HTTP 400."""
    fake_txt = io.BytesIO(b"This is a text file not an image")
    files = {
        "file": ("query_notes.txt", fake_txt, "text/plain")
    }

    response = client.post("/api/v1/ai/image-search", files=files)
    assert response.status_code == 400
    assert "không được hỗ trợ" in response.json()["detail"]

    ai_rate_limiter.reset()
    fake_pdf = io.BytesIO(b"%PDF-1.4 dummy content")
    files_pdf = {
        "file": ("document.pdf", fake_pdf, "application/pdf")
    }
    response_pdf = client.post("/api/v1/ai/image-search", files=files_pdf)
    assert response_pdf.status_code == 400


def test_image_search_empty_file():
    """Test uploading empty file returns HTTP 400."""
    empty_file = io.BytesIO(b"")
    files = {
        "file": ("empty.png", empty_file, "image/png")
    }

    response = client.post("/api/v1/ai/image-search", files=files)
    assert response.status_code == 400
    assert "rỗng" in response.json()["detail"]


def test_image_search_file_size_exceeded():
    """Test uploading file exceeding 5MB returns HTTP 400."""
    oversized = io.BytesIO(b"\x00" * (5 * 1024 * 1024 + 1024))
    files = {
        "file": ("huge_photo.jpg", oversized, "image/jpeg")
    }

    response = client.post("/api/v1/ai/image-search", files=files)
    assert response.status_code == 400
    assert "vượt quá" in response.json()["detail"]


def test_sqlite_truth_guard_verifies_price_and_stock():
    """Verify that all returned products have price and stock verified against SQLite."""
    files = {
        "file": ("vintage_keyboard.png", io.BytesIO(TINY_PNG), "image/png")
    }

    response = client.post("/api/v1/ai/image-search?limit=3", files=files)
    assert response.status_code == 200
    data = response.json()

    conn = sqlite3.connect(settings.DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    for item in data["results"]:
        cursor.execute("SELECT selling_price, stock_quantity, status FROM products WHERE id = ?", (item["product_id"],))
        db_row = cursor.fetchone()
        assert db_row is not None, f"Product {item['product_id']} does not exist in SQLite"
        # Business Truth Guard Check: values must match SQLite exactly
        assert item["selling_price"] == db_row["selling_price"], "Selling price must come directly from SQLite"
        assert item["stock_quantity"] == db_row["stock_quantity"], "Stock quantity must come directly from SQLite"
        assert item["status"] == db_row["status"], "Status must come directly from SQLite"
        assert item["in_stock"] == (db_row["stock_quantity"] > 0)

    conn.close()


def test_relationship_classification_rules():
    """Test relationship classification logic directly for MATCH, SIMILAR, RELATED, NONE."""
    qf = ImageSearchQueryFeatures(
        product_type="headphone",
        dominant_color="black",
        shape_form="over-ear"
    )

    # 1. Match: same category + is_best_category_match flag + high score
    rel, reason = image_search_service.classify_relationship(
        candidate_meta={"product_type": "headphone", "dominant_color": "black"},
        query_features=qf,
        score=0.85,
        is_best_category_match=True
    )
    assert rel == "match"
    assert "chính xác" in reason

    # 2. Similar: same category but NOT best candidate
    rel, reason = image_search_service.classify_relationship(
        candidate_meta={"product_type": "headphone", "dominant_color": "white"},
        query_features=qf,
        score=0.60,
        is_best_category_match=False
    )
    assert rel == "similar"
    assert "tương tự" in reason

    # 3. Related: different category (microphone != headphone) - strict guard
    rel, reason = image_search_service.classify_relationship(
        candidate_meta={"product_type": "microphone", "dominant_color": "black"},
        query_features=qf,
        score=0.40
    )
    assert rel == "related"
    assert "liên quan" in reason

    # 4. None: score below 0.25 AND different category
    rel, reason = image_search_service.classify_relationship(
        candidate_meta={"product_type": "smart_scale", "dominant_color": "white"},
        query_features=qf,
        score=0.20
    )
    assert rel == "none"
    assert "dưới ngưỡng" in reason

    # 5. Strict guard: mousepad MUST NOT be 'match' even at high score when query is 'mouse'
    qf_mouse = ImageSearchQueryFeatures(
        product_type="mouse",
        dominant_color="black",
        shape_form="ergonomic"
    )
    rel_pad, _ = image_search_service.classify_relationship(
        candidate_meta={"product_type": "mousepad", "dominant_color": "black"},
        query_features=qf_mouse,
        score=0.90,
        is_best_category_match=False
    )
    assert rel_pad in ["related", "none"], f"mousepad must NOT be match/similar for mouse query, got {rel_pad}"
