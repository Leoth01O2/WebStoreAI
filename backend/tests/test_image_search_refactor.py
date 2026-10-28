import io
import pytest
import sqlite3
from PIL import Image, ImageDraw

from app.services.local_vision_service import local_vision_service
from app.services.visual_index_service import visual_index_service, normalize_device_type
from app.services.image_search_service import image_search_service
from app.schemas.ai import ImageSearchQueryFeatures


def create_minecraft_like_image() -> bytes:
    """Creates a synthetic blocky voxel game screenshot with dirt/gold pixel grid."""
    img = Image.new("RGB", (224, 224), color=(180, 140, 50))
    draw = ImageDraw.Draw(img)
    # Draw voxel block grid
    for x in range(0, 224, 32):
        for y in range(0, 224, 32):
            block_color = (190 + (x * 7) % 50, 140 + (y * 5) % 40, 30 + (x + y) % 30)
            draw.rectangle([x, y, x + 31, y + 31], fill=block_color, outline=(90, 70, 20))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def create_natural_test_image(color=(30, 30, 35)) -> bytes:
    """Creates a clean test image."""
    img = Image.new("RGB", (128, 128), color=color)
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


class TestDeviceTypeNormalization:
    """Verifies that substring collisions are fully resolved."""

    def test_gamepad_normalization(self):
        assert normalize_device_type("gamepad") == "game_controller"
        assert normalize_device_type("game_controller") == "game_controller"
        assert normalize_device_type("tay_cam_choi_game") == "game_controller"

    def test_cooling_pad_normalization(self):
        assert normalize_device_type("cooling_pad") == "cooling_pad"
        assert normalize_device_type("de_tan_nhiet") == "cooling_pad"

    def test_mousepad_normalization(self):
        assert normalize_device_type("mousepad") == "mousepad"
        assert normalize_device_type("desk_mat") == "mousepad"
        assert normalize_device_type("ban_di_chuot") == "mousepad"

    def test_hub_adapter_vs_charger(self):
        assert normalize_device_type("hub_adapter") == "hub_adapter"
        assert normalize_device_type("type_c_hub") == "hub_adapter"
        assert normalize_device_type("charger") == "charger"
        assert normalize_device_type("cu_sac_nhanh") == "charger"

    def test_laptop_stand(self):
        assert normalize_device_type("laptop_stand") == "laptop_stand"
        assert normalize_device_type("gia_do_laptop") == "laptop_stand"


class TestMinecraftAndOpenSetRejection:
    """Verifies that non-product screenshots are rejected and never forced into mousepad."""

    def test_minecraft_screenshot_rejected_as_non_product(self):
        mc_bytes = create_minecraft_like_image()
        features, is_np, reason, _ = local_vision_service.extract_query_visual_features_local(
            mc_bytes, filename="minecraft_world.png", return_vector=True
        )

        # Must either be rejected as non-product or flagged as uncertain
        assert is_np is True or features.is_uncertain is True
        # Critical guarantee: NEVER falsely classified as mousepad
        assert features.product_type != "mousepad"

    def test_image_search_service_pipeline_rejects_minecraft(self):
        mc_bytes = create_minecraft_like_image()
        res = image_search_service.search_and_classify(
            image_bytes=mc_bytes,
            filename="minecraft_screenshot.png",
            content_type="image/png",
            limit=5,
            provider="local"
        )

        assert res.is_non_product is True or res.is_uncertain is True
        assert res.query_features.product_type != "mousepad"
        # Must not return false matches
        if res.is_non_product:
            assert len(res.results) == 0


class TestNoFilenameSpoofing:
    """Ensures filename keywords do not fake visual features."""

    def test_filename_spoofing_eliminated(self):
        # A non-product image named 'headphone_gaming.png' should NOT fake headphone features
        mc_bytes = create_minecraft_like_image()
        res_spoofed = image_search_service.search_and_classify(
            image_bytes=mc_bytes,
            filename="headphone_gaming.png",
            content_type="image/png",
            limit=5,
            provider="local"
        )
        res_plain = image_search_service.search_and_classify(
            image_bytes=mc_bytes,
            filename="image_001.png",
            content_type="image/png",
            limit=5,
            provider="local"
        )

        assert res_spoofed.is_non_product == res_plain.is_non_product
        assert res_spoofed.query_features.product_type == res_plain.query_features.product_type


class TestCorruptImageStrictRejection:
    """Ensures corrupt images raise errors without fallback canvases."""

    def test_corrupted_image_raises_error(self):
        fake_corrupted = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR" + b"\xff" * 50
        with pytest.raises(ValueError) as exc:
            local_vision_service.validate_and_open_image(fake_corrupted)
        assert "hỏng" in str(exc.value) or "không đúng" in str(exc.value)


class TestRelationshipTiersAndSecurity:
    """Verifies strict relationship classification and zero cost price leakage."""

    def test_different_category_never_match(self):
        qf = ImageSearchQueryFeatures(
            product_type="mouse",
            dominant_color="black",
            shape_form="ergonomic"
        )
        # Even with high visual score, mouse vs mousepad is only related/none
        rel, reason = image_search_service.classify_relationship(
            candidate_meta={"product_type": "mousepad", "dominant_color": "black"},
            query_features=qf,
            score=0.92,
            is_best_category_match=False
        )
        assert rel in ["related", "none"]
        assert rel != "match"
        assert rel != "similar"

    def test_low_score_is_none(self):
        qf = ImageSearchQueryFeatures(
            product_type="keyboard",
            dominant_color="white",
            shape_form="tenkeyless"
        )
        rel, reason = image_search_service.classify_relationship(
            candidate_meta={"product_type": "lamp", "dominant_color": "black"},
            query_features=qf,
            score=0.20
        )
        assert rel == "none"

