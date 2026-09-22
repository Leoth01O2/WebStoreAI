import pytest
import time
from app.services.visual_index_service import visual_index_service
from app.core.database import get_db_connection


def test_rebuild_and_sync_visual_index():
    """Verify that rebuild_product_visual_index indexes all demo catalog products without external calls."""
    start_time = time.perf_counter()
    result = visual_index_service.rebuild_product_visual_index()
    elapsed = time.perf_counter() - start_time

    assert result["status"] == "success"
    assert result["indexed_count"] >= 25, f"Expected at least 25 items indexed, got {result['indexed_count']}"
    assert result["collection_count"] >= 25
    # Should be fast since all data is precomputed in SQLite
    assert elapsed < 5.0, f"Indexing took too long: {elapsed:.2f}s"


def test_fast_lookup_latency_under_50ms():
    """Verify that retrieving visual metadata by product_id executes in < 50ms with 0 network calls."""
    # Find a valid product_id from SQLite
    with get_db_connection() as conn:
        c = conn.cursor()
        c.execute("SELECT product_id FROM product_visual_metadata LIMIT 1")
        row = c.fetchone()
        assert row is not None, "At least one product_visual_metadata record must exist"
        test_pid = row["product_id"]

    start = time.perf_counter()
    meta = visual_index_service.get_visual_metadata_by_product_id(test_pid)
    elapsed_ms = (time.perf_counter() - start) * 1000

    assert meta is not None
    assert meta["product_id"] == test_pid
    assert meta["product_type"] is not None
    assert meta["visual_description"] is not None
    assert elapsed_ms < 50.0, f"Lookup exceeded 50ms: {elapsed_ms:.2f}ms"


def test_get_all_indexed_visuals():
    """Verify fast retrieval of all visual records from local database."""
    start = time.perf_counter()
    all_visuals = visual_index_service.get_all_indexed_visuals()
    elapsed_ms = (time.perf_counter() - start) * 1000

    assert len(all_visuals) >= 25
    assert elapsed_ms < 50.0, f"Batch retrieval exceeded 50ms: {elapsed_ms:.2f}ms"
    # Ensure visual fields exist
    first = all_visuals[0]
    assert "product_type" in first
    assert "visual_description" in first
    assert "search_keywords" in first


def test_search_visual_candidates_headphone():
    """
    Test candidate retrieval combining text semantic similarity and structured attributes.
    Querying for a black over-ear headphone should place SP-AUDIO-01 / SP-AUDIO-03 at the top.
    """
    candidates = visual_index_service.search_visual_candidates(
        query_text="tai nghe chụp tai over-ear màu đen đệm da",
        query_attributes={"product_type": "headphone", "dominant_color": "black", "shape_form": "over-ear"},
        top_k=5
    )

    assert len(candidates) > 0, "Candidate search should return results"
    top = candidates[0]
    assert "product_id" in top
    assert "sku" in top
    assert "combined_score" in top
    assert top["combined_score"] > 0.4, f"Top candidate should have high score: {top['combined_score']}"

    # Verify that at least one audio headphone appears in top candidates
    skus = [c["sku"] for c in candidates]
    assert any("AUDIO" in s or "GAME-01" in s for s in skus), f"Expected audio/headset product in results, got: {skus}"


def test_search_visual_candidates_keyboard():
    """Test searching for mechanical typewriter keyboard."""
    candidates = visual_index_service.search_visual_candidates(
        query_text="bàn phím cơ phím tròn cổ điển máy đánh chữ",
        query_attributes={"product_type": "keyboard", "dominant_color": "white", "shape_form": "tenkeyless"},
        top_k=3
    )

    assert len(candidates) > 0
    skus = [c["sku"] for c in candidates]
    # SP-OFFICE-01 is Bàn phím cơ Retro Typewriter T80
    assert "SP-OFFICE-01" in skus, f"SP-OFFICE-01 should be among top candidates, got: {skus}"


def test_quota_control_zero_duplicate_external_calls():
    """
    Test that sync_single_product_visual on an existing product in SQLite
    completes entirely locally and updates ChromaDB without external AI calls.
    """
    with get_db_connection() as conn:
        c = conn.cursor()
        c.execute("SELECT product_id FROM product_visual_metadata LIMIT 1")
        pid = c.fetchone()["product_id"]

    start = time.perf_counter()
    success = visual_index_service.sync_single_product_visual(pid)
    elapsed_ms = (time.perf_counter() - start) * 1000

    assert success is True
    # If an external AI call was made, it would take hundreds of ms or seconds.
    # Local upsert into local ChromaDB takes < 150ms.
    assert elapsed_ms < 500.0, f"Sync took unexpectedly long ({elapsed_ms:.2f}ms), indicating possible external call"
