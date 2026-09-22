import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
import json
import chromadb

from app.core.config import settings, BASE_DIR
from app.core.database import get_db_connection

logger = logging.getLogger("storeflow.visual_index")
if not logger.handlers:
    logging.basicConfig(level=logging.INFO)


def normalize_device_type(ptype: Optional[str]) -> str:
    """
    Normalizes free-form or extracted device type into a canonical category token.
    Prevents false substring overlaps (e.g., 'mouse' in 'mousepad').
    """
    if not ptype:
        return "accessory"
    raw = str(ptype).lower().strip().replace("-", "_").replace(" ", "_")
    # Substring / keyword checks in strict precedence order (mousepad before mouse, etc.)
    if any(k in raw for k in ["mousepad", "mouse_pad", "desk_mat", "ban_di_chuot", "lot_chuot", "pad"]):
        return "mousepad"
    if any(k in raw for k in ["mouse", "chuot"]):
        return "mouse"
    if any(k in raw for k in ["keyboard", "ban_phim"]):
        return "keyboard"
    if any(k in raw for k in ["headphone", "headset", "tai_nghe", "earbuds", "earphone"]):
        return "headphone"
    if any(k in raw for k in ["controller", "gamepad", "tay_cam"]):
        return "game_controller"
    if any(k in raw for k in ["speaker", "loa"]):
        return "speaker"
    if any(k in raw for k in ["charger", "cu_sac", "adapter"]):
        return "charger"
    if any(k in raw for k in ["cable", "cap_sac", "day_sac"]):
        return "cable"
    if any(k in raw for k in ["laptop_stand", "gia_do"]):
        return "laptop_stand"
    if any(k in raw for k in ["cooling_pad", "de_tan_nhiet"]):
        return "cooling_pad"
    if any(k in raw for k in ["clock", "dong_ho"]):
        return "clock"
    if any(k in raw for k in ["lamp", "den"]):
        return "lamp"
    if any(k in raw for k in ["diffuser", "may_xong"]):
        return "diffuser"
    if any(k in raw for k in ["smart_scale", "can_dien_tu", "can_suc_khoe"]):
        return "smart_scale"
    if any(k in raw for k in ["fan", "quat"]):
        return "fan"
    return raw


class VisualIndexService:
    """
    Visual Indexing & Semantic Retrieval Service for StoreFlow AI Image Search.
    
    Architectural Principles:
    - ChromaDB stores and searches semantic embeddings of textual visual representations
      (generated via text embedding model all-MiniLM-L6-v2), NOT raw image embeddings.
    - Zero external API calls for precomputed products: products with precomputed
      visual metadata in SQLite are indexed locally without contacting external Vision API.
    - Combines structured attribute matching (product_type, dominant_color, shape_form)
      with text semantic retrieval for high-accuracy candidate extraction.
    - SQLite remains the Single Source of Truth for product business data (price, stock, status).
    """

    def __init__(self, persist_dir: Optional[str] = None):
        if persist_dir:
            self.persist_dir = Path(persist_dir)
        else:
            p = Path(settings.CHROMA_PERSIST_DIRECTORY)
            if not p.is_absolute():
                self.persist_dir = BASE_DIR / p
            else:
                self.persist_dir = p

        self.persist_dir.mkdir(parents=True, exist_ok=True)
        self.client = chromadb.PersistentClient(path=str(self.persist_dir))
        self.collection_name = "storeflow_product_visuals"
        self.collection = self.client.get_or_create_collection(
            name=self.collection_name,
            metadata={"hnsw:space": "cosine"}
        )
        logger.info(f"[VISUAL_INDEX] Initialized collection '{self.collection_name}' with {self.collection.count()} items.")

    def _build_visual_document(self, meta: Dict[str, Any], prod: Optional[Dict[str, Any]] = None) -> str:
        """
        Constructs a rich, normalized textual visual representation for ChromaDB text embedding.
        Contains visual features, colors, shapes, materials, and keywords.
        """
        features_raw = meta.get("visible_features") or ""
        features_str = features_raw
        if isinstance(features_raw, str) and features_raw.startswith("["):
            try:
                features_list = json.loads(features_raw)
                features_str = ", ".join(features_list)
            except Exception:
                features_str = features_raw

        parts = [
            f"Chủng loại thị giác: {meta.get('product_type', '')}",
            f"Màu sắc chủ đạo: {meta.get('dominant_color', '')}",
            f"Kiểu dáng hình học: {meta.get('shape_form', '')}",
            f"Chất liệu nhận diện: {meta.get('material', '')}",
            f"Đặc tính nhìn thấy: {features_str}",
            f"Mô tả trực quan: {meta.get('visual_description', '')}",
            f"Từ khóa đặc trưng: {meta.get('search_keywords', '')}"
        ]

        if prod:
            if prod.get("name"):
                parts.append(f"Tên sản phẩm: {prod['name']}")
            if prod.get("sku"):
                parts.append(f"Mã SKU: {prod['sku']}")

        return " | ".join(p for p in parts if p)

    def sync_all_visuals(self) -> int:
        """
        Synchronizes all product visual metadata from SQLite into the ChromaDB visual collection.
        Zero external network calls required (uses precomputed SQLite visual metadata).
        """
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT v.id, v.product_id, v.image_path, v.product_type, v.dominant_color,
                       v.shape_form, v.material, v.visible_features, v.visual_description,
                       v.search_keywords, p.sku, p.name, p.status, p.selling_price
                FROM product_visual_metadata v
                JOIN products p ON v.product_id = p.id
            """)
            rows = [dict(r) for r in cursor.fetchall()]

        if not rows:
            logger.warning("[VISUAL_INDEX] No product visual metadata found in SQLite to sync.")
            return 0

        documents = []
        ids = []
        metadatas = []

        for row in rows:
            doc = self._build_visual_document(row, row)
            documents.append(doc)
            ids.append(str(row["product_id"]))
            metadatas.append({
                "product_id": int(row["product_id"]),
                "sku": str(row.get("sku") or ""),
                "product_type": str(row.get("product_type") or "").lower(),
                "dominant_color": str(row.get("dominant_color") or "").lower(),
                "shape_form": str(row.get("shape_form") or "").lower(),
                "material": str(row.get("material") or "").lower(),
                "image_path": str(row.get("image_path") or ""),
                "status": str(row.get("status") or "active")
            })

        self.collection.upsert(
            ids=ids,
            documents=documents,
            metadatas=metadatas
        )

        logger.info(f"[VISUAL_INDEX] Successfully synced {len(rows)} product visual records into ChromaDB.")
        return len(rows)

    def rebuild_product_visual_index(self) -> Dict[str, Any]:
        """
        Administrative function: completely resets and rebuilds the product visual index
        from SQLite database without calling external Vision APIs.
        """
        try:
            current_count = self.collection.count()
            if current_count > 0:
                # Delete existing entries
                existing_ids = self.collection.get().get("ids", [])
                if existing_ids:
                    self.collection.delete(ids=existing_ids)
                logger.info(f"[VISUAL_INDEX] Cleared {len(existing_ids)} old records from collection.")
        except Exception as e:
            logger.warning(f"[VISUAL_INDEX] Non-fatal error while clearing collection: {e}")

        indexed_count = self.sync_all_visuals()
        return {
            "status": "success",
            "indexed_count": indexed_count,
            "collection_count": self.collection.count()
        }

    def sync_single_product_visual(self, product_id: int) -> bool:
        """
        Upserts a single product's visual metadata into ChromaDB when updated or created.
        Enforces strict quota control: skips external AI call if metadata exists in SQLite.
        """
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT v.id, v.product_id, v.image_path, v.product_type, v.dominant_color,
                       v.shape_form, v.material, v.visible_features, v.visual_description,
                       v.search_keywords, p.sku, p.name, p.status, p.selling_price
                FROM product_visual_metadata v
                JOIN products p ON v.product_id = p.id
                WHERE v.product_id = ?
            """, (product_id,))
            row = cursor.fetchone()

        if not row:
            logger.info(f"[VISUAL_INDEX] No visual metadata record found for product {product_id}. Skipping ChromaDB upsert.")
            return False

        meta = dict(row)
        doc = self._build_visual_document(meta, meta)
        self.collection.upsert(
            ids=[str(product_id)],
            documents=[doc],
            metadatas=[{
                "product_id": int(product_id),
                "sku": str(meta.get("sku") or ""),
                "product_type": str(meta.get("product_type") or "").lower(),
                "dominant_color": str(meta.get("dominant_color") or "").lower(),
                "shape_form": str(meta.get("shape_form") or "").lower(),
                "material": str(meta.get("material") or "").lower(),
                "image_path": str(meta.get("image_path") or ""),
                "status": str(meta.get("status") or "active")
            }]
        )
        logger.info(f"[VISUAL_INDEX] Upserted visual metadata for product {product_id} into ChromaDB.")
        return True

    def delete_single_product_visual(self, product_id: int) -> None:
        """Deletes a product's visual representation from ChromaDB."""
        try:
            self.collection.delete(ids=[str(product_id)])
            logger.info(f"[VISUAL_INDEX] Deleted visual record for product {product_id} from ChromaDB.")
        except Exception as e:
            logger.warning(f"[VISUAL_INDEX] Error deleting visual vector for product {product_id}: {e}")

    def get_visual_metadata_by_product_id(self, product_id: int) -> Optional[Dict[str, Any]]:
        """
        Fast lookup of a product's visual metadata from SQLite (< 50ms, zero external calls).
        """
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT v.*, p.sku, p.name, p.selling_price, p.stock_quantity, p.status
                FROM product_visual_metadata v
                JOIN products p ON v.product_id = p.id
                WHERE v.product_id = ?
            """, (product_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_all_indexed_visuals(self) -> List[Dict[str, Any]]:
        """
        Fast retrieval of all visual records from SQLite (< 50ms, zero external calls).
        """
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT v.*, p.sku, p.name, p.status, p.selling_price, p.stock_quantity
                FROM product_visual_metadata v
                JOIN products p ON v.product_id = p.id
                ORDER BY v.product_id ASC
            """)
            return [dict(r) for r in cursor.fetchall()]

    def search_visual_candidates(
        self,
        query_text: str,
        query_attributes: Optional[Dict[str, Any]] = None,
        top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Retrieves Top-K candidate products by combining:
        1. Category-aware candidate retrieval (targeted category pool + broad pool)
        2. Text semantic retrieval (ChromaDB over textual visual representations)
        3. Strict structured attribute matching (normalized product_type, dominant_color, shape_form)
        
        Zero external network calls: executed 100% locally with all-MiniLM-L6-v2 ONNX.
        """
        total_indexed = self.collection.count()
        if total_indexed == 0:
            logger.info("[VISUAL_INDEX] Collection empty, auto-syncing visual metadata...")
            self.sync_all_visuals()
            total_indexed = self.collection.count()

        if total_indexed == 0:
            return []

        q_type_raw = (query_attributes.get("product_type") or "") if query_attributes else ""
        norm_q_type = normalize_device_type(q_type_raw) if q_type_raw else ""
        q_color = (query_attributes.get("dominant_color") or "").lower() if query_attributes else ""
        q_shape = (query_attributes.get("shape_form") or "").lower() if query_attributes else ""

        fetch_k = min(max(top_k * 3, 15), total_indexed)
        all_ids: List[str] = []
        all_distances: List[float] = []
        all_metas: List[Dict[str, Any]] = []
        seen_pids = set()

        # 1. Targeted query with ChromaDB where filter when category is identified
        if norm_q_type and norm_q_type != "accessory":
            try:
                cat_results = self.collection.query(
                    query_texts=[query_text],
                    where={"product_type": norm_q_type},
                    n_results=min(top_k * 2, total_indexed)
                )
                if cat_results and cat_results.get("ids") and cat_results["ids"][0]:
                    for pid_str, dist, meta in zip(cat_results["ids"][0], cat_results["distances"][0], cat_results["metadatas"][0]):
                        if pid_str not in seen_pids:
                            seen_pids.add(pid_str)
                            all_ids.append(pid_str)
                            all_distances.append(dist)
                            all_metas.append(meta)
            except Exception as e:
                logger.warning(f"[VISUAL_INDEX] Category where query warning: {e}")

        # 2. Broad query for ecosystem accessories and complementary items
        try:
            broad_results = self.collection.query(
                query_texts=[query_text],
                n_results=fetch_k
            )
            if broad_results and broad_results.get("ids") and broad_results["ids"][0]:
                for pid_str, dist, meta in zip(broad_results["ids"][0], broad_results["distances"][0], broad_results["metadatas"][0]):
                    if pid_str not in seen_pids:
                        seen_pids.add(pid_str)
                        all_ids.append(pid_str)
                        all_distances.append(dist)
                        all_metas.append(meta)
        except Exception as e:
            logger.warning(f"[VISUAL_INDEX] Broad query warning: {e}")

        if not all_ids:
            return []

        candidates = []
        for pid_str, dist, meta in zip(all_ids, all_distances, all_metas):
            product_id = int(pid_str)
            # Cosine similarity calculation: 1.0 - distance
            semantic_similarity = max(0.0, min(1.0, 1.0 - float(dist)))

            m_type_raw = str(meta.get("product_type") or "").lower()
            norm_m_type = normalize_device_type(m_type_raw)
            m_color = str(meta.get("dominant_color") or "").lower()
            m_shape = str(meta.get("shape_form") or "").lower()

            is_category_match = bool(norm_q_type and norm_m_type and norm_q_type == norm_m_type)

            # Structured attribute matching score (0.0 to 1.0)
            attr_score = 0.0
            attr_matches = []

            # 1. Product type match: STRICT canonical equality (prevents false 'mouse' in 'mousepad')
            if is_category_match:
                attr_score += 0.50
                attr_matches.append("product_type")

            # 2. Color token overlap
            if q_color and m_color:
                q_color_tokens = [c.strip() for c in q_color.replace(",", " ").split() if len(c.strip()) > 2]
                if any(qc in m_color for qc in q_color_tokens) or any(mc in q_color for mc in m_color.replace(",", " ").split() if len(mc.strip()) > 2):
                    attr_score += 0.30
                    attr_matches.append("dominant_color")

            # 3. Shape form token overlap
            if q_shape and m_shape:
                q_shape_words = set(q_shape.replace("-", " ").replace("_", " ").split())
                m_shape_words = set(m_shape.replace("-", " ").replace("_", " ").split())
                overlap = {w for w in (q_shape_words & m_shape_words) if len(w) > 3}
                if overlap or (q_shape in m_shape or m_shape in q_shape):
                    attr_score += 0.20
                    attr_matches.append("shape_form")

            # Blended score: 65% semantic visual match + 35% exact attribute match
            if query_attributes and (q_type_raw or q_color or q_shape):
                combined_score = (0.65 * semantic_similarity) + (0.35 * attr_score)
            else:
                combined_score = semantic_similarity

            candidates.append({
                "product_id": product_id,
                "sku": meta.get("sku", ""),
                "product_type": meta.get("product_type", ""),
                "dominant_color": meta.get("dominant_color", ""),
                "shape_form": meta.get("shape_form", ""),
                "material": meta.get("material", ""),
                "image_path": meta.get("image_path", ""),
                "semantic_similarity": round(semantic_similarity, 4),
                "attribute_score": round(attr_score, 4),
                "combined_score": round(combined_score, 4),
                "is_category_match": is_category_match,
                "attr_matches": attr_matches
            })

        # Post-Processing: Category matches ALWAYS take precedence over non-category accessories,
        # then ordered by combined_score descending
        candidates.sort(
            key=lambda x: (1 if x.get("is_category_match") else 0, x["combined_score"]),
            reverse=True
        )
        return candidates[:top_k]


# Singleton instance
visual_index_service = VisualIndexService()
