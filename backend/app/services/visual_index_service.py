import logging
from pathlib import Path
from typing import List, Dict, Any, Optional, Set, Sequence, cast
import json
import chromadb
from chromadb.api.models.Collection import Collection
from PIL import Image

from app.core.config import settings, BASE_DIR
from app.core.database import get_db_connection, get_db_transaction
from app.services.local_vision_service import local_vision_service

logger = logging.getLogger("storeflow.visual_index")
if not logger.handlers:
    logging.basicConfig(level=logging.INFO)


def normalize_device_type(ptype: Optional[str]) -> str:
    """
    Normalizes free-form or extracted device type into a canonical category token.
    Prevents false substring overlaps (e.g. 'gamepad' -> 'game_controller', 'cooling_pad' -> 'cooling_pad',
    'hub_adapter' -> 'hub_adapter', 'mousepad' -> 'mousepad').
    """
    if not ptype:
        return "accessory"
    raw = str(ptype).lower().strip().replace("-", "_").replace(" ", "_")

    # Direct canonical token matches
    canonical_tokens = {
        "mousepad": "mousepad",
        "mouse_pad": "mousepad",
        "desk_mat": "mousepad",
        "deskmat": "mousepad",
        "lot_chuot": "mousepad",
        "ban_di_chuot": "mousepad",
        "cooling_pad": "cooling_pad",
        "de_tan_nhiet": "cooling_pad",
        "gamepad": "game_controller",
        "game_controller": "game_controller",
        "controller": "game_controller",
        "tay_cam": "game_controller",
        "mouse": "mouse",
        "chuot": "mouse",
        "keyboard": "keyboard",
        "ban_phim": "keyboard",
        "headphone": "headphone",
        "headset": "headphone",
        "tai_nghe": "headphone",
        "earbuds": "earbuds",
        "earphone": "earbuds",
        "tws": "earbuds",
        "in_ear": "earbuds",
        "speaker": "speaker",
        "loa": "speaker",
        "microphone": "microphone",
        "mic": "microphone",
        "micro": "microphone",
        "hub_adapter": "hub_adapter",
        "hub": "hub_adapter",
        "docking": "hub_adapter",
        "dongle": "hub_adapter",
        "charger": "charger",
        "cu_sac": "charger",
        "wall_charger": "charger",
        "cable": "cable",
        "cap_sac": "cable",
        "day_sac": "cable",
        "power_bank": "power_bank",
        "pin_du_phong": "power_bank",
        "sac_du_phong": "power_bank",
        "laptop_stand": "laptop_stand",
        "gia_do": "laptop_stand",
        "lamp": "lamp",
        "den": "lamp",
        "clock": "clock",
        "dong_ho": "clock",
        "diffuser": "diffuser",
        "may_xong": "diffuser",
        "smart_scale": "smart_scale",
        "can_dien_tu": "smart_scale",
        "fan": "fan",
        "quat": "fan",
    }
    if raw in canonical_tokens:
        return canonical_tokens[raw]

    # Precedence order matching for compound words / phrases:
    if any(k in raw for k in ["cooling_pad", "de_tan_nhiet"]):
        return "cooling_pad"
    if any(k in raw for k in ["mousepad", "mouse_pad", "desk_mat", "ban_di_chuot", "lot_chuot"]):
        return "mousepad"
    if any(k in raw for k in ["gamepad", "tay_cam", "controller", "joystick"]):
        return "game_controller"
    if any(k in raw for k in ["hub", "dongle", "docking"]):
        return "hub_adapter"
    if any(k in raw for k in ["laptop_stand", "gia_do"]):
        return "laptop_stand"
    if any(k in raw for k in ["power_bank", "pin_du_phong", "sac_du_phong"]):
        return "power_bank"
    if any(k in raw for k in ["earbuds", "earphone", "in_ear", "tws"]):
        return "earbuds"
    if any(k in raw for k in ["headphone", "headset"]):
        return "headphone"
    if any(k in raw for k in ["smart_scale", "can_dien_tu", "can_suc_khoe"]):
        return "smart_scale"
    if any(k in raw for k in ["diffuser", "may_xong", "may_phun_suong"]):
        return "diffuser"
    if any(k in raw for k in ["cu_sac", "charger"]) and "hub" not in raw:
        return "charger"
    if any(k in raw for k in ["cable", "cap_sac", "day_sac"]):
        return "cable"
    if any(k in raw for k in ["ban_phim", "keyboard"]):
        return "keyboard"
    if any(k in raw for k in ["chuot", "mouse"]) and "mousepad" not in raw and "pad" not in raw:
        return "mouse"
    if any(k in raw for k in ["loa", "speaker"]):
        return "speaker"
    if any(k in raw for k in ["microphone", "micro"]):
        return "microphone"
    if any(k in raw for k in ["dong_ho", "clock"]):
        return "clock"
    if any(k in raw for k in ["den", "lamp"]):
        return "lamp"
    if any(k in raw for k in ["quat", "fan"]):
        return "fan"

    return raw


class VisualIndexService:
    """
    Visual Indexing & Semantic Retrieval Service for StoreFlow AI Image Search.
    
    Architectural Principles:
    - Dual ChromaDB Collections:
        1. 'storeflow_product_visual_vectors': 512-dimensional direct visual embeddings
           extracted via local CLIP (openai/clip-vit-base-patch32) on CPU.
        2. 'storeflow_product_visuals': Textual visual representations (backward compatibility).
    - Zero external API calls for indexing or local retrieval: 100% offline.
    - Resolves local catalog image files directly or multimodal visual text descriptions into
      the same 512-dim CLIP metric space.
    - SQLite remains the Single Source of Truth for product business data (price, stock, status).
    - Automatic self-healing: detects and reconciles any products missing visual metadata.
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

        # 1. Text semantic collection (384-dim)
        self.collection_name = "storeflow_product_visuals"
        self.collection: Collection = self.client.get_or_create_collection(
            name=self.collection_name,
            metadata={"hnsw:space": "cosine"}
        )

        # 2. Direct visual CLIP vectors collection (512-dim)
        self.vector_collection_name = "storeflow_product_visual_vectors"
        self.vector_collection: Collection = self.client.get_or_create_collection(
            name=self.vector_collection_name,
            metadata={"hnsw:space": "cosine"}
        )

        logger.info(
            f"[VISUAL_INDEX] Initialized collections: '{self.collection_name}' ({self.collection.count()} docs), "
            f"'{self.vector_collection_name}' ({self.vector_collection.count()} vectors)."
        )

    def _build_visual_document(self, meta: Dict[str, Any], prod: Optional[Dict[str, Any]] = None) -> str:
        """
        Constructs a rich, normalized textual visual representation for ChromaDB and CLIP text embedding.
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

    def _find_local_image_path(self, path_or_url: Optional[str]) -> Optional[Path]:
        """Resolves whether an image path points to an existing file on the local disk."""
        if not path_or_url:
            return None
        clean_path = str(path_or_url).strip()
        if clean_path.startswith("http://") or clean_path.startswith("https://") or clean_path.startswith("data:"):
            return None

        candidates = [
            BASE_DIR / clean_path.lstrip("/\\"),
            BASE_DIR / "backend" / clean_path.lstrip("/\\"),
            BASE_DIR.parent / clean_path.lstrip("/\\"),
            Path(clean_path)
        ]
        for c in candidates:
            if c.exists() and c.is_file():
                return c
        return None

    def _compute_product_vector(self, row: Dict[str, Any], doc: str) -> List[float]:
        """
        Computes 512-dimensional CLIP embedding for a product:
        - If a valid local image file exists on disk, computes visual vector directly from image pixels.
        - Otherwise, computes multimodal text vector from its rich visual description in the same space.
        """
        img_ref = row.get("image_url") or row.get("image_path")
        local_file = self._find_local_image_path(img_ref)

        if local_file:
            try:
                img = Image.open(local_file).convert("RGB")
                return local_vision_service.extract_image_embedding(img)
            except Exception as e:
                logger.warning(f"[VISUAL_INDEX] Failed to extract visual embedding from file {local_file}: {e}")

        # Multimodal text embedding in joint CLIP space
        return local_vision_service.extract_text_embedding(doc)

    def reconcile_missing_visual_metadata(self) -> int:
        """
        Self-healing routine: scans products in SQLite and automatically generates
        visual metadata records for any product that lacks an entry in product_visual_metadata.
        Prioritizes products.product_type and products.brand if available.
        """
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT p.id, p.sku, p.name, p.category_id, c.name as category_name,
                       p.image_url, p.description, p.brand, p.product_type
                FROM products p
                LEFT JOIN categories c ON p.category_id = c.id
                WHERE p.id NOT IN (SELECT product_id FROM product_visual_metadata)
            """)
            missing = [dict(r) for r in cursor.fetchall()]

        if not missing:
            return 0

        logger.info(f"[VISUAL_INDEX] Found {len(missing)} products missing visual metadata. Auto-generating records...")
        inserted_count = 0

        for prod in missing:
            p_name = prod.get("name") or ""
            p_cat = (prod.get("category_name") or "").lower()
            p_desc = prod.get("description") or ""
            img_url = prod.get("image_url") or ""
            p_type_db = prod.get("product_type")

            # 1. Prioritize explicit product_type in SQLite if available
            if p_type_db and str(p_type_db).strip():
                inferred_type = normalize_device_type(p_type_db)
            else:
                name_lower = p_name.lower()
                # Strict precedence: specific / accessory terms before base terms
                if any(k in name_lower or k in p_cat for k in ["bàn di", "lót chuột", "mousepad", "desk mat"]):
                    inferred_type = "mousepad"
                elif any(k in name_lower or k in p_cat for k in ["đế tản nhiệt", "cooling pad"]):
                    inferred_type = "cooling_pad"
                elif any(k in name_lower or k in p_cat for k in ["tay cầm", "gamepad", "controller"]):
                    inferred_type = "game_controller"
                elif any(k in name_lower or k in p_cat for k in ["giá đỡ laptop", "laptop stand", "giá đỡ"]):
                    inferred_type = "laptop_stand"
                elif any(k in name_lower or k in p_cat for k in ["pin dự phòng", "sạc dự phòng", "power bank"]):
                    inferred_type = "power_bank"
                elif any(k in name_lower or k in p_cat for k in ["hub", "dongle", "docking", "bộ chia cổng"]):
                    inferred_type = "hub_adapter"
                elif any(k in name_lower or k in p_cat for k in ["tai nghe nhét tai", "earbuds", "earphone", "tws", "in-ear"]):
                    inferred_type = "earbuds"
                elif any(k in name_lower or k in p_cat for k in ["tai nghe chụp tai", "headphone", "headset"]):
                    inferred_type = "headphone"
                elif any(k in name_lower or k in p_cat for k in ["củ sạc", "sạc nhanh", "charger"]):
                    inferred_type = "charger"
                elif any(k in name_lower or k in p_cat for k in ["cáp sạc", "dây sạc", "cable"]):
                    inferred_type = "cable"
                elif any(k in name_lower or k in p_cat for k in ["bàn phím", "keyboard"]):
                    inferred_type = "keyboard"
                elif any(k in name_lower or k in p_cat for k in ["chuột", "mouse"]) and "mousepad" not in name_lower:
                    inferred_type = "mouse"
                elif any(k in name_lower or k in p_cat for k in ["loa", "speaker"]):
                    inferred_type = "speaker"
                elif any(k in name_lower or k in p_cat for k in ["micro", "mic"]):
                    inferred_type = "microphone"
                elif any(k in name_lower or k in p_cat for k in ["đèn", "lamp"]):
                    inferred_type = "lamp"
                elif any(k in name_lower or k in p_cat for k in ["máy xông", "khuếch tán", "diffuser"]):
                    inferred_type = "diffuser"
                elif any(k in name_lower or k in p_cat for k in ["đồng hồ", "clock"]):
                    inferred_type = "clock"
                elif any(k in name_lower or k in p_cat for k in ["cân điện tử", "smart scale"]):
                    inferred_type = "smart_scale"
                elif any(k in name_lower or k in p_cat for k in ["quạt", "fan"]):
                    inferred_type = "fan"
                else:
                    inferred_type = "accessory"

            # Infer color
            name_lower = p_name.lower()
            inferred_color = "black"
            if any(k in name_lower or k in p_desc.lower() for k in ["trắng", "white", "bạc", "silver", "retro"]):
                inferred_color = "white" if "trắng" in name_lower else "silver"
            elif any(k in name_lower for k in ["gỗ", "wood", "nâu"]):
                inferred_color = "brown_wood"

            inferred_shape = "ergonomic standard"
            if inferred_type == "mouse":
                inferred_shape = "classic ergonomic contour"
            elif inferred_type == "keyboard":
                inferred_shape = "compact layout"
            elif inferred_type == "headphone":
                inferred_shape = "over-ear circular earcups"
            elif inferred_type == "earbuds":
                inferred_shape = "in-ear tws with charging case"
            elif inferred_type == "mousepad":
                inferred_shape = "flat rectangular thin surface mat"

            features_json = json.dumps([inferred_type, inferred_color, inferred_shape], ensure_ascii=False)
            visual_desc = f"{p_name} thiết kế màu {inferred_color}, chủng loại {inferred_type}. {p_desc[:120]}"
            keywords = f"{p_name}, {inferred_type}, {inferred_color}, {prod.get('sku', '')}, {prod.get('brand', '')}"

            with get_db_transaction() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO product_visual_metadata (
                        product_id, image_path, product_type, dominant_color, shape_form,
                        material, visible_features, visual_description, search_keywords
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    prod["id"], img_url, inferred_type, inferred_color, inferred_shape,
                    "composite", features_json, visual_desc, keywords
                ))
                inserted_count += 1

        logger.info(f"[VISUAL_INDEX] Successfully auto-reconciled {inserted_count} missing visual metadata rows in SQLite.")
        return inserted_count

    def rebuild_product_visual_index(self) -> Dict[str, Any]:
        """Backward-compatible rebuild and sync method."""
        count = self.sync_all_visuals()
        return {
            "status": "success",
            "indexed_count": count,
            "collection_count": self.collection.count(),
            "vector_collection_count": self.vector_collection.count()
        }

    def sync_all_visuals(self) -> int:
        """
        Synchronizes all product visual metadata from SQLite into:
        1. 'storeflow_product_visual_vectors' (512-dim CLIP vectors)
        2. 'storeflow_product_visuals' (384-dim text documents)
        Zero external network calls required (executed locally on CPU).
        """
        # Ensure any newly created products in SQLite have visual metadata records
        self.reconcile_missing_visual_metadata()

        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT v.id, v.product_id, v.image_path, v.product_type, v.dominant_color,
                       v.shape_form, v.material, v.visible_features, v.visual_description,
                       v.search_keywords, p.sku, p.name, p.status, p.selling_price, p.image_url,
                       p.brand, p.product_type as p_product_type
                FROM product_visual_metadata v
                JOIN products p ON v.product_id = p.id
            """)
            rows = [dict(r) for r in cursor.fetchall()]

        if not rows:
            logger.warning("[VISUAL_INDEX] No product visual metadata found in SQLite to sync.")
            return 0

        documents: List[str] = []
        ids: List[str] = []
        metadatas: List[Dict[str, Any]] = []
        embeddings: List[List[float]] = []

        for row in rows:
            doc = self._build_visual_document(row, row)
            vec = self._compute_product_vector(row, doc)

            documents.append(doc)
            ids.append(str(row["product_id"]))
            embeddings.append(vec)
            ptype_val = str(row.get("product_type") or row.get("p_product_type") or "").lower()
            metadatas.append({
                "product_id": int(row["product_id"]),
                "sku": str(row.get("sku") or ""),
                "brand": str(row.get("brand") or "").lower(),
                "product_type": normalize_device_type(ptype_val),
                "dominant_color": str(row.get("dominant_color") or "").lower(),
                "shape_form": str(row.get("shape_form") or "").lower(),
                "material": str(row.get("material") or "").lower(),
                "image_path": str(row.get("image_path") or row.get("image_url") or ""),
                "status": str(row.get("status") or "active")
            })

        # Upsert into text semantic collection
        self.collection.upsert(
            ids=ids,
            documents=documents,
            metadatas=metadatas
        )

        # Upsert into 512-dim visual CLIP vector collection
        self.vector_collection.upsert(
            ids=ids,
            documents=documents,
            embeddings=embeddings,
            metadatas=metadatas
        )

        logger.info(f"[VISUAL_INDEX] Successfully synced {len(rows)} product visual records into both ChromaDB collections.")
        return len(rows)

    def sync_single_product_visual(self, product_id: int) -> bool:
        """
        Upserts a single product's visual metadata into both ChromaDB collections
        when updated or created. Auto-generates metadata if not yet present in SQLite.
        """
        # Auto-reconcile if missing
        self.reconcile_missing_visual_metadata()

        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT v.id, v.product_id, v.image_path, v.product_type, v.dominant_color,
                       v.shape_form, v.material, v.visible_features, v.visual_description,
                       v.search_keywords, p.sku, p.name, p.status, p.selling_price, p.image_url,
                       p.brand, p.product_type as p_product_type
                FROM product_visual_metadata v
                JOIN products p ON v.product_id = p.id
                WHERE v.product_id = ?
            """, (product_id,))
            row = cursor.fetchone()

        if not row:
            logger.info(f"[VISUAL_INDEX] No visual metadata record found for product {product_id}. Skipping ChromaDB upsert.")
            return False

        meta = dict(row)
        # Keep image_path aligned with current products.image_url if updated
        if meta.get("image_url") and meta.get("image_url") != meta.get("image_path"):
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "UPDATE product_visual_metadata SET image_path = ? WHERE product_id = ?",
                    (meta["image_url"], product_id)
                )
                conn.commit()
            meta["image_path"] = meta["image_url"]

        doc = self._build_visual_document(meta, meta)
        vec = self._compute_product_vector(meta, doc)

        ptype_val = str(meta.get("product_type") or meta.get("p_product_type") or "").lower()
        meta_dict = {
            "product_id": int(product_id),
            "sku": str(meta.get("sku") or ""),
            "brand": str(meta.get("brand") or "").lower(),
            "product_type": normalize_device_type(ptype_val),
            "dominant_color": str(meta.get("dominant_color") or "").lower(),
            "shape_form": str(meta.get("shape_form") or "").lower(),
            "material": str(meta.get("material") or "").lower(),
            "image_path": str(meta.get("image_path") or meta.get("image_url") or ""),
            "status": str(meta.get("status") or "active")
        }

        self.collection.upsert(
            ids=[str(product_id)],
            documents=[doc],
            metadatas=[meta_dict]
        )

        self.vector_collection.upsert(
            ids=[str(product_id)],
            documents=[doc],
            embeddings=[vec],
            metadatas=[meta_dict]
        )

        logger.info(f"[VISUAL_INDEX] Upserted visual metadata for product {product_id} into both ChromaDB collections.")
        return True

    def delete_single_product_visual(self, product_id: int) -> None:
        """Deletes a product's visual representation from both ChromaDB collections."""
        try:
            self.collection.delete(ids=[str(product_id)])
            self.vector_collection.delete(ids=[str(product_id)])
            logger.info(f"[VISUAL_INDEX] Deleted visual record for product {product_id} from ChromaDB collections.")
        except Exception as e:
            logger.warning(f"[VISUAL_INDEX] Error deleting visual vector for product {product_id}: {e}")

    def get_visual_metadata_by_product_id(self, product_id: int) -> Optional[Dict[str, Any]]:
        """Fast lookup of a product's visual metadata from SQLite (< 50ms, zero external calls)."""
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
        """Fast retrieval of all visual records from SQLite (< 50ms, zero external calls)."""
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
        query_vector: Optional[List[float]] = None,
        query_text: str = "",
        query_attributes: Optional[Dict[str, Any]] = None,
        top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Retrieves Top-K candidate products by combining:
        1. Direct 512-dim visual vector search (CLIP) or text semantic retrieval
        2. Strict structured attribute matching (normalized product_type, dominant_color, shape_form)
        3. Priority filtering for exact category matches
        
        Zero external network calls: executed 100% locally.
        """
        # Auto-heal if collection is empty
        total_vectors = self.vector_collection.count()
        if total_vectors == 0:
            logger.info("[VISUAL_INDEX] Vector collection empty, auto-syncing visual metadata...")
            self.sync_all_visuals()
            total_vectors = self.vector_collection.count()

        if total_vectors == 0:
            return []

        q_type_raw = (query_attributes.get("product_type") or "") if query_attributes else ""
        norm_q_type = normalize_device_type(q_type_raw) if q_type_raw else ""
        q_color = (query_attributes.get("dominant_color") or "").lower() if query_attributes else ""
        q_shape = (query_attributes.get("shape_form") or "").lower() if query_attributes else ""
        is_uncertain = bool(query_attributes.get("is_uncertain")) if query_attributes else False

        fetch_k = min(max(top_k * 3, 15), total_vectors)
        all_ids: List[str] = []
        all_distances: List[float] = []
        all_metas: List[Dict[str, Any]] = []
        seen_pids: Set[str] = set()

        def _collect_query_matches(res: Optional[Dict[str, Any]]) -> None:
            if not res:
                return
            r_ids = res.get("ids")
            r_dists = res.get("distances")
            r_metas = res.get("metadatas")
            if r_ids and r_dists and r_metas and len(r_ids) > 0 and len(r_dists) > 0 and len(r_metas) > 0:
                ids_0 = r_ids[0]
                dists_0 = r_dists[0]
                metas_0 = r_metas[0]
                if ids_0 and dists_0 and metas_0:
                    for pid_str, dist, meta in zip(ids_0, dists_0, metas_0):
                        if pid_str not in seen_pids:
                            seen_pids.add(pid_str)
                            all_ids.append(pid_str)
                            all_distances.append(float(dist))
                            all_metas.append(meta or {})

        # If 512-dim CLIP query vector is provided, search the visual vector collection
        if query_vector is not None:
            # 1. Broad vector query across all products is the PRIMARY metric-space retrieval
            try:
                broad_results = self.vector_collection.query(
                    query_embeddings=[query_vector],
                    n_results=fetch_k
                )
                _collect_query_matches(broad_results)
            except Exception as e:
                logger.warning(f"[VISUAL_INDEX] Broad vector query warning: {e}")

            # 2. Targeted query with category filter ONLY when confident (not uncertain)
            if not is_uncertain and norm_q_type and norm_q_type != "accessory":
                try:
                    cat_results = self.vector_collection.query(
                        query_embeddings=[query_vector],
                        where={"product_type": norm_q_type},
                        n_results=min(top_k * 2, total_vectors)
                    )
                    _collect_query_matches(cat_results)
                except Exception as e:
                    logger.warning(f"[VISUAL_INDEX] Vector category query warning: {e}")

        else:
            # Fallback to text query on self.collection
            try:
                broad_results = self.collection.query(
                    query_texts=[query_text],
                    n_results=fetch_k
                )
                _collect_query_matches(broad_results)
            except Exception as e:
                logger.warning(f"[VISUAL_INDEX] Broad text query warning: {e}")

            if not is_uncertain and norm_q_type and norm_q_type != "accessory":
                try:
                    cat_results = self.collection.query(
                        query_texts=[query_text],
                        where={"product_type": norm_q_type},
                        n_results=min(top_k * 2, self.collection.count())
                    )
                    _collect_query_matches(cat_results)
                except Exception as e:
                    logger.warning(f"[VISUAL_INDEX] Text category query warning: {e}")

        if not all_ids:
            return []

        candidates: List[Dict[str, Any]] = []
        for pid_str, dist, meta in zip(all_ids, all_distances, all_metas):
            product_id = int(pid_str)
            # Cosine similarity calculation: 1.0 - distance
            semantic_similarity = max(0.0, min(1.0, 1.0 - float(dist)))

            m_type_raw = str(meta.get("product_type") or "").lower()
            norm_m_type = normalize_device_type(m_type_raw)
            m_color = str(meta.get("dominant_color") or "").lower()
            m_shape = str(meta.get("shape_form") or "").lower()

            is_category_match = bool(not is_uncertain and norm_q_type and norm_m_type and norm_q_type == norm_m_type)

            # Structured attribute matching score (0.0 to 1.0)
            attr_score = 0.0
            attr_matches: List[str] = []

            if not is_uncertain and (norm_q_type or q_color or q_shape):
                # 1. Product type match: STRICT canonical equality
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

                # Blended score: 80% direct visual vector match + 20% exact attribute match
                combined_score = (0.80 * semantic_similarity) + (0.20 * attr_score)
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

        # Ranked with category priority when confident, then combined_score descending
        if not is_uncertain and norm_q_type:
            candidates.sort(
                key=lambda x: (1 if x["is_category_match"] else 0, x["combined_score"]),
                reverse=True
            )
        else:
            candidates.sort(
                key=lambda x: x["combined_score"],
                reverse=True
            )
        return candidates[:top_k]


# Singleton instance
visual_index_service = VisualIndexService()
