import pytest
import sqlite3
from pathlib import Path
from pydantic import ValidationError

from app.schemas.product import (
    ProductVisualMetadataCreate,
    ProductVisualMetadataUpdate,
    ProductVisualMetadataResponse
)
from app.models.schema import SCHEMA_SQL
from app.core.config import settings


def test_pydantic_schema_validation():
    """Test validation rules of ProductVisualMetadata Pydantic models."""
    # 1. Valid create
    valid_data = {
        "product_id": 1,
        "image_path": "https://example.com/item.jpg",
        "product_type": "headphone",
        "dominant_color": "black",
        "shape_form": "over-ear",
        "material": "plastic, leather",
        "visible_features": '["soft earcups", "folding hinge"]',
        "visual_description": "Black over-ear headphones with soft leather earcups.",
        "search_keywords": "headphone, bluetooth, black",
    }
    model = ProductVisualMetadataCreate(**valid_data)
    assert model.product_id == 1
    assert model.product_type == "headphone"
    assert model.dominant_color == "black"

    # 2. Missing required fields (product_type)
    with pytest.raises(ValidationError):
        ProductVisualMetadataCreate(
            product_id=1,
            image_path="https://example.com/item.jpg",
            product_type=""
        )

    # 3. Missing required field (product_id)
    with pytest.raises(ValidationError):
        ProductVisualMetadataCreate(
            image_path="https://example.com/item.jpg",
            product_type="headphone"
        )

    # 4. Update schema allows partial fields
    update_model = ProductVisualMetadataUpdate(dominant_color="white")
    assert update_model.dominant_color == "white"
    assert update_model.product_type is None

    # 5. Response schema serialization
    response_data = {
        "id": 10,
        "product_id": 1,
        "image_path": "https://example.com/item.jpg",
        "product_type": "headphone",
        "dominant_color": "black",
        "created_at": "2026-09-22 15:00:00",
        "updated_at": "2026-09-22 15:00:00"
    }
    response_model = ProductVisualMetadataResponse(**response_data)
    assert response_model.id == 10
    assert response_model.product_id == 1


def test_sqlite_visual_metadata_constraints():
    """Test SQLite schema constraints: table creation, UNIQUE product_id, CASCADE deletion, and indexes."""
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.executescript(SCHEMA_SQL)
    cursor = conn.cursor()

    # Create dummy category and product
    cursor.execute("INSERT INTO categories (name, code) VALUES ('Audio', 'CAT-AUD')")
    cat_id = cursor.lastrowid

    cursor.execute(
        """INSERT INTO products (sku, name, category_id, cost_price, selling_price, stock_quantity)
           VALUES ('TEST-01', 'Test Headphone', ?, 100, 150, 10)""",
        (cat_id,)
    )
    product_id = cursor.lastrowid

    # Insert visual metadata
    cursor.execute(
        """INSERT INTO product_visual_metadata (
            product_id, image_path, product_type, dominant_color, shape_form, visual_description
        ) VALUES (?, ?, ?, ?, ?, ?)""",
        (product_id, "https://example.com/test.jpg", "headphone", "black", "over-ear", "Description test")
    )
    conn.commit()

    # 1. UNIQUE constraint check on product_id
    with pytest.raises(sqlite3.IntegrityError):
        cursor.execute(
            """INSERT INTO product_visual_metadata (
                product_id, image_path, product_type
            ) VALUES (?, ?, ?)""",
            (product_id, "https://example.com/test2.jpg", "speaker")
        )

    # 2. Verify indexes exist
    cursor.execute("PRAGMA index_list('product_visual_metadata')")
    indexes = [row[1] for row in cursor.fetchall()]
    assert "idx_visual_metadata_product" in indexes
    assert "idx_visual_metadata_type" in indexes

    # 3. Test CASCADE deletion
    cursor.execute("DELETE FROM products WHERE id = ?", (product_id,))
    conn.commit()

    cursor.execute("SELECT COUNT(*) FROM product_visual_metadata WHERE product_id = ?", (product_id,))
    assert cursor.fetchone()[0] == 0, "Visual metadata must be deleted when the parent product is deleted (ON DELETE CASCADE)"

    conn.close()


def test_demo_products_have_visual_metadata():
    """Verify that all 25 demo catalog products in webstore.db have visual metadata populated."""
    db_path = Path(settings.DATABASE_PATH)
    if not db_path.exists():
        pytest.skip("webstore.db not found on disk")

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Query visual metadata joined with products for the 25 demo products
    cursor.execute("""
        SELECT p.sku, v.product_type, v.visual_description, v.search_keywords
        FROM products p
        JOIN product_visual_metadata v ON p.id = v.product_id
        WHERE p.sku LIKE 'SP-%' AND p.sku NOT LIKE 'SP-TEST%'
    """)
    demo_meta_rows = cursor.fetchall()
    assert len(demo_meta_rows) == 25, f"Expected 25 demo products with visual metadata, got {len(demo_meta_rows)}"

    # Verify visual description and keywords are non-empty for all 25 demo records
    for row in demo_meta_rows:
        assert row["product_type"], f"product_type missing for SKU {row['sku']}"
        assert row["visual_description"], f"visual_description missing for SKU {row['sku']}"
        assert row["search_keywords"], f"search_keywords missing for SKU {row['sku']}"

    conn.close()
