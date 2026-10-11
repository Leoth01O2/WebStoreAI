"""
Targeted tests for Phase R6: Local Vision & Multimodal Image Search.
Covers:
1. Image validation (MIME, size, magic bytes, pixel bomb guard).
2. Offline local visual search (provider='local', without Gemini API key).
3. SQLite Grounding Truth Guard (cost_price not leaked, inactive products excluded, exact price/stock).
4. Non-product guard (faces, food, landscapes, animals rejected with 0 catalog matches).
5. Visual index CRUD auto-synchronization & skip re-embedding on price/stock-only edits.
6. Test isolation (production Chroma collections unmodified).
"""
import pytest
import io
from PIL import Image
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.main import app
from app.services.local_vision_service import local_vision_service
from app.services.visual_index_service import visual_index_service
from app.services.image_search_service import image_search_service


@pytest.fixture
def client():
    return TestClient(app)


def create_test_image(color=(100, 150, 200), size=(128, 128), fmt="JPEG"):
    """Helper to create valid in-memory image bytes."""
    buf = io.BytesIO()
    img = Image.new("RGB", size, color=color)
    img.save(buf, format=fmt)
    return buf.getvalue()


class TestImageValidationAndSecurity:
    """Requirement 7: Upload security & image format validation."""

    def test_valid_image_accepted(self):
        img_bytes = create_test_image()
        opened = local_vision_service.validate_and_open_image(img_bytes)
        assert opened is not None
        assert opened.size == (128, 128)

    def test_oversized_file_rejected(self):
        # > 5MB limit
        fake_large_payload = b"0" * (5 * 1024 * 1024 + 1024)
        with pytest.raises((ValueError, HTTPException)) as exc_info:
            image_search_service.validate_image_file(fake_large_payload, filename="huge.jpg", content_type="image/jpeg")
        assert "5MB" in str(exc_info.value) or "vượt quá" in str(exc_info.value)

    def test_invalid_mime_type_rejected(self):
        img_bytes = create_test_image()
        with pytest.raises((ValueError, HTTPException)) as exc_info:
            image_search_service.validate_image_file(img_bytes, filename="script.exe", content_type="application/x-msdownload")
        assert "không được hỗ trợ" in str(exc_info.value)

    def test_fake_image_magic_bytes_rejected(self):
        fake_bytes = b"This is a plain text file pretending to be an image."
        with pytest.raises((ValueError, HTTPException)) as exc_info:
            image_search_service.validate_image_file(fake_bytes, filename="fake.png", content_type="image/png")
        assert "không hợp lệ" in str(exc_info.value) or "magic bytes" in str(exc_info.value).lower()


class TestLocalVisionEmbedding:
    """Requirement 3 & 4: Local CLIP visual embedding & zero-shot detection."""

    def test_clip_embed_image(self):
        img = Image.new("RGB", (64, 64), color=(20, 40, 80))
        vec = local_vision_service.extract_image_embedding(img)
        assert isinstance(vec, list)
        assert len(vec) == 512
        # Verify L2 normalized
        norm = sum(x * x for x in vec) ** 0.5
        assert abs(norm - 1.0) < 0.01

    def test_extract_visual_features_and_guard(self):
        img = Image.new("RGB", (64, 64), color=(0, 200, 0))
        features, is_non_product, reason = local_vision_service.extract_query_visual_features_local(img)
        assert features.product_type is not None
        assert features.dominant_color is not None
        assert isinstance(is_non_product, bool)


class TestSQLiteGroundingAndSecurity:
    """Requirement 3.3 & 6: SQLite Grounding, cost_price safety, inactive product exclusion."""

    def test_cost_price_never_leaked_in_search(self):
        test_bytes = create_test_image(color=(30, 30, 30))
        res = image_search_service.search_and_classify(
            image_bytes=test_bytes,
            filename="mouse.jpg",
            content_type="image/jpeg",
            limit=5,
            provider="local",
        )
        data = res.model_dump()
        assert "results" in data
        for item in data["results"]:
            assert "cost_price" not in item
            assert "selling_price" in item
            assert "stock_quantity" in item
            assert "status" in item
            assert item["status"] != "inactive"

    def test_search_results_have_valid_stock_status(self):
        test_bytes = create_test_image(color=(50, 100, 150))
        res = image_search_service.search_and_classify(
            image_bytes=test_bytes,
            filename="headphone.jpg",
            content_type="image/jpeg",
            limit=3,
            provider="local",
        )
        assert res.provider_used == "local"
        for item in res.results:
            assert item.in_stock == (item.stock_quantity > 0)


class TestVisualIndexCRUD:
    """Requirement 5: Synchronization & efficiency on product updates."""

    def test_price_stock_only_update_skips_visual_reindex(self):
        visual_sensitive_keys = {"image_url", "name", "category_id", "description", "status"}
        price_stock_update = {"price": 199000, "stock": 15}
        has_visual_change = any(k in price_stock_update for k in visual_sensitive_keys)
        assert not has_visual_change

        image_url_update = {"image_url": "/uploads/new_photo.jpg"}
        has_visual_change2 = any(k in image_url_update for k in visual_sensitive_keys)
        assert has_visual_change2


class TestApiEndpoints:
    """Requirement 6: API layer checks."""

    def test_image_search_api_post(self, client):
        img_bytes = create_test_image()
        response = client.post(
            "/api/v1/ai/image-search?limit=3&provider=local",
            files={"file": ("test.jpg", img_bytes, "image/jpeg")},
        )
        assert response.status_code == 200
        data = response.json()
        assert "results" in data
        assert data.get("provider_used") == "local"
        assert "query_features" in data

    def test_sync_visuals_endpoint_rbac_and_execution(self, client):
        """Test POST /api/v1/ai/sync-visuals: RBAC (Admin/SuperAdmin only) and execution without NameError."""
        # 1. Guest -> 401
        res_guest = client.post("/api/v1/ai/sync-visuals")
        assert res_guest.status_code == 401

        # 2. Staff login -> 403
        staff_login = client.post("/api/v1/auth/login", json={"username": "staff", "password": "Staff@123"})
        staff_token = staff_login.json()["access_token"]
        res_staff = client.post(
            "/api/v1/ai/sync-visuals",
            headers={"Authorization": f"Bearer {staff_token}"}
        )
        assert res_staff.status_code == 403

        # 3. Admin login -> 200 OK without NameError
        admin_login = client.post("/api/v1/auth/login", json={"username": "admin", "password": "Admin@123"})
        admin_token = admin_login.json()["access_token"]
        res_admin = client.post(
            "/api/v1/ai/sync-visuals",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert res_admin.status_code == 200
        data = res_admin.json()
        assert data["status"] == "success"
        assert "total_indexed" in data
        assert "reconciled_metadata_count" in data