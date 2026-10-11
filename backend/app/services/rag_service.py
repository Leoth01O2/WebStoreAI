import os
import re
import difflib
from pathlib import Path
from typing import List, Dict, Any, Optional, Set
import chromadb

from app.core.config import settings, BASE_DIR
from app.core.database import get_db_connection


# ==============================================================================
# DOMAIN DICTIONARY & OUT-OF-DOMAIN INTENT PATTERNS
# ==============================================================================

CATEGORY_KEYWORDS = {
    "Âm thanh & Tai nghe": [
        "tai nghe", "headphone", "earphone", "earbuds", "loa", "speaker", "sound", "micro", "mic",
        "âm thanh", "bluetooth", "retrosound", "chống ồn", "anc", "studio", "thu âm", "hifi", "tws"
    ],
    "Chuột & Bàn phím": [
        "chuột", "mouse", "bàn phím", "keyboard", "phím cơ", "typewriter", "lót chuột", "pad", "bàn di",
        "công thái học", "silent", "không dây", "slim", "quang"
    ],
    "Gia dụng thông minh": [
        "đèn", "lamp", "chống cận", "edison", "khuếch tán", "tinh dầu", "đồng hồ", "nixie", "clock",
        "cân", "scale", "quạt", "fan", "turbine"
    ],
    "Phụ kiện & Dây cáp": [
        "sạc", "charger", "cáp", "cable", "hub", "type-c", "hdmi", "pin", "dự phòng", "powerbank",
        "giá đỡ", "stand", "cyberpunk"
    ],
    "Gaming Gear": [
        "gaming", "game", "chơi game", "7.1", "bass", "siêu nhẹ", "tay cầm", "controller",
        "hall effect", "tản nhiệt", "cooler"
    ]
}

OUT_OF_DOMAIN_PATTERNS = [
    # Food & Beverage
    r"\b(phở|bún|cơm|bánh|pizza|trái cây|hoa quả|thức ăn|đồ ăn|nước uống|cafe|cà phê)\b",
    # Travel & Hospitality
    r"\b(vé máy bay|hàng không|khách sạn|du lịch|tour|resort)\b",
    # Weather & General Life
    r"\b(thời tiết|dự báo thời tiết|trời mưa|nhiệt độ hôm nay|bão)\b",
    # Non-catalog heavy appliances / vehicles
    r"\b(tivi|tv|máy giặt|tủ lạnh|máy sấy|máy lạnh|điều hòa|xe máy|ô tô|xe đạp|quần áo|giày dép)\b",
]

INJECTION_PATTERNS = [
    r"ignore\s+(all\s+)?(previous\s+)?instructions",
    r"forget\s+(all\s+)?(previous\s+)?instructions",
    r"bỏ\s+qua\s+(hướng\s+dẫn|câu\s+lệnh|chỉ\s+dẫn)",
    r"quên\s+(hết\s+)?(chỉ\s+dẫn|hướng\s+dẫn)",
    r"(reveal|show|tiết\s+lộ)\s+(system\s+prompt|prompt)",
    r"system\s+prompt",
    r"api\s*key",
    r"gemini_api_key",
    r"secret\s*key",
    r"act\s+as\s+(admin|superadmin)",
    r"you\s+are\s+now\s+(admin|superadmin)",
    r"cost_price",
    r"giá\s+vốn",
    r"lợi\s+nhuận"
]


class RAGService:
    """
    StoreFlow AI Retrieval & Grounding Service.
    Architecture: Dense Vector Retrieval (ChromaDB) + Lexical/Category Re-ranking + Strict SQLite Truth Guard.
    Features:
      1. Out-of-Domain Guard: blocks irrelevant queries with 0 hallucinated products.
      2. Dense Vector Retrieval (ChromaDB) with empirical cosine cutoff (0.55).
      3. Sparse / Lexical Re-ranking with category affinity boosting.
      4. Strict SQLite Post-Retrieval Verification Guard (status='active', stock_quantity > 0).
      5. Explicit Out-of-Stock Detection: alerts users when specific requested products are exhausted.
      6. Prompt Injection Neutralizer: cleans catalog text before sending to LLM.
      7. Synchronization & Reconciliation: detects and self-heals missing, orphan, and outdated vectors.
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
        self.collection = self.client.get_or_create_collection(
            name="storeflow_products",
            metadata={"hnsw:space": "cosine"}
        )
        self._sync_needed = False

    def mark_sync_needed(self) -> None:
        """Flags that an index desynchronization occurred and requires self-healing."""
        self._sync_needed = True

    def auto_heal_if_needed(self, force: bool = False) -> Dict[str, Any]:
        """
        Automatically performs self-healing reconciliation between SQLite and ChromaDB
        if flagged as out of sync or if force=True.
        """
        if not getattr(self, "_sync_needed", False) and not force:
            return {"healed": False, "reason": "in_sync"}
        try:
            status = self.check_sync_status()
            if not status.get("is_synced", True):
                heal_res = self.reconcile_sync()
                self._sync_needed = False
                return {"healed": True, "details": heal_res}
            self._sync_needed = False
            return {"healed": False, "reason": "already_synced"}
        except Exception as e:
            return {"healed": False, "error": str(e)}

    def _sanitize_text(self, text: str) -> str:
        """Neutralizes prompt injection attempts within catalog descriptions."""
        if not text:
            return ""
        clean = text
        for pattern in INJECTION_PATTERNS:
            clean = re.sub(pattern, "[REDACTED_TERM]", clean, flags=re.IGNORECASE)
        # Strip potential markdown formatting overrides
        clean = clean.replace("```", "").replace("<script>", "").replace("</script>", "")
        return clean.strip()

    def _build_product_document(self, p: Dict[str, Any]) -> str:
        """Constructs a descriptive semantic text chunk for product indexing."""
        price_str = f"{int(p.get('selling_price', 0)):,} VNĐ"
        desc_clean = self._sanitize_text(p.get("description", ""))
        return (
            f"Mã: {p.get('sku', '')} | Tên sản phẩm: {p.get('name', '')} | "
            f"Danh mục: {p.get('category_name', '')} | Giá bán: {price_str} | "
            f"Đơn vị: {p.get('unit', 'cái')} | Mô tả & Đặc tính: {desc_clean}"
        )

    # --------------------------------------------------------------------------
    # SYNCHRONIZATION & RECONCILIATION
    # --------------------------------------------------------------------------

    def sync_all_products(self) -> int:
        """
        Loads all products joined with categories from SQLite and indexes them into ChromaDB.
        Returns the number of products indexed.
        """
        with get_db_connection() as conn:
            c = conn.cursor()
            c.execute("""
                SELECT p.id, p.sku, p.name, p.category_id, c.name as category_name,
                       p.selling_price, p.stock_quantity, p.unit, p.status, p.description
                FROM products p
                LEFT JOIN categories c ON p.category_id = c.id
            """)
            rows = [dict(r) for r in c.fetchall()]

        if not rows:
            return 0

        documents = []
        ids = []
        metadatas = []

        for p in rows:
            doc = self._build_product_document(p)
            documents.append(doc)
            ids.append(str(p["id"]))
            metadatas.append({
                "product_id": int(p["id"]),
                "sku": str(p.get("sku") or ""),
                "category_id": int(p.get("category_id") or 0),
                "category_name": str(p.get("category_name") or ""),
                "selling_price": float(p.get("selling_price") or 0.0),
                "status": str(p.get("status") or "active"),
            })

        self.collection.upsert(
            ids=ids,
            documents=documents,
            metadatas=metadatas
        )
        return len(rows)

    def upsert_single_product(self, product_id: int) -> bool:
        """Upserts a single product into ChromaDB when added or updated in SQLite."""
        with get_db_connection() as conn:
            c = conn.cursor()
            c.execute("""
                SELECT p.id, p.sku, p.name, p.category_id, c.name as category_name,
                       p.selling_price, p.stock_quantity, p.unit, p.status, p.description
                FROM products p
                LEFT JOIN categories c ON p.category_id = c.id
                WHERE p.id = ?
            """, (product_id,))
            row = c.fetchone()

        if not row:
            return False

        p = dict(row)
        doc = self._build_product_document(p)
        self.collection.upsert(
            ids=[str(p["id"])],
            documents=[doc],
            metadatas=[{
                "product_id": int(p["id"]),
                "sku": str(p.get("sku") or ""),
                "category_id": int(p.get("category_id") or 0),
                "category_name": str(p.get("category_name") or ""),
                "selling_price": float(p.get("selling_price") or 0.0),
                "status": str(p.get("status") or "active"),
            }]
        )
        return True

    def delete_single_product(self, product_id: int) -> None:
        """Deletes a product vector from ChromaDB."""
        try:
            self.collection.delete(ids=[str(product_id)])
        except Exception:
            pass

    def check_sync_status(self) -> Dict[str, Any]:
        """
        Audits synchronization health between SQLite products and ChromaDB vectors.
        Identifies:
          - missing_in_chroma: Products in SQLite without a ChromaDB vector.
          - orphan_in_chroma: ChromaDB vectors whose products were deleted from SQLite.
          - outdated_in_chroma: Vectors whose document content or status is stale compared to SQLite.
        """
        with get_db_connection() as conn:
            c = conn.cursor()
            c.execute("""
                SELECT p.id, p.sku, p.name, p.category_id, c.name as category_name,
                       p.selling_price, p.stock_quantity, p.unit, p.status, p.description
                FROM products p
                LEFT JOIN categories c ON p.category_id = c.id
            """)
            sqlite_rows = {str(r["id"]): dict(r) for r in c.fetchall()}

        sqlite_ids = set(sqlite_rows.keys())

        # Include documents and metadatas to check content freshness
        chroma_res = self.collection.get(include=["documents", "metadatas"])
        chroma_ids = set(chroma_res.get("ids", []))

        missing_in_chroma = sorted([int(i) for i in (sqlite_ids - chroma_ids)])
        orphan_in_chroma = sorted([int(i) for i in (chroma_ids - sqlite_ids)])

        # Verify content freshness for products existing in both
        outdated_in_chroma = []
        chroma_docs_map = {}
        chroma_meta_map = {}
        if "documents" in chroma_res and chroma_res["documents"]:
            for idx, cid in enumerate(chroma_res.get("ids", [])):
                chroma_docs_map[cid] = chroma_res["documents"][idx] if idx < len(chroma_res["documents"]) else ""
                chroma_meta_map[cid] = chroma_res["metadatas"][idx] if (chroma_res.get("metadatas") and idx < len(chroma_res["metadatas"])) else {}

        for cid, row in sqlite_rows.items():
            if cid in chroma_docs_map:
                expected_doc = self._build_product_document(row)
                existing_doc = chroma_docs_map[cid]
                existing_meta = chroma_meta_map.get(cid, {})
                if existing_doc != expected_doc or existing_meta.get("status") != str(row.get("status") or "active"):
                    outdated_in_chroma.append(int(cid))

        outdated_in_chroma.sort()
        is_synced = len(missing_in_chroma) == 0 and len(orphan_in_chroma) == 0 and len(outdated_in_chroma) == 0

        return {
            "is_synced": is_synced,
            "sqlite_count": len(sqlite_ids),
            "chroma_count": len(chroma_ids),
            "missing_in_chroma": missing_in_chroma,
            "orphan_in_chroma": orphan_in_chroma,
            "outdated_in_chroma": outdated_in_chroma
        }

    def reconcile_sync(self) -> Dict[str, Any]:
        """
        Self-healing routine: resolves all desync anomalies between SQLite and ChromaDB.
        Upserts missing products, refreshes outdated vector documents, and purges orphan records.
        """
        status = self.check_sync_status()
        upserted_count = 0
        updated_count = 0
        deleted_count = 0

        for mid in status["missing_in_chroma"]:
            if self.upsert_single_product(mid):
                upserted_count += 1

        for oid in status.get("outdated_in_chroma", []):
            if self.upsert_single_product(oid):
                updated_count += 1

        for orph_id in status["orphan_in_chroma"]:
            self.delete_single_product(orph_id)
            deleted_count += 1

        # Double check after healing
        final_status = self.check_sync_status()
        return {
            "repaired": True,
            "upserted_count": upserted_count,
            "updated_count": updated_count,
            "deleted_count": deleted_count,
            "final_sync_status": final_status
        }

    # --------------------------------------------------------------------------
    # INTENT ANALYSIS & LEXICAL SCORING
    # --------------------------------------------------------------------------

    def is_out_of_domain(self, query: str) -> bool:
        """Detects whether a query falls outside the StoreFlow technology product domain."""
        q_clean = query.lower().strip()
        for pattern in OUT_OF_DOMAIN_PATTERNS:
            if re.search(pattern, q_clean):
                return True
        return False

    def detect_target_categories(self, query: str) -> Set[str]:
        """Identifies specific product categories explicitly implied in the query."""
        q_lower = query.lower()
        matched = set()
        for cat, kws in CATEGORY_KEYWORDS.items():
            for kw in kws:
                if kw in q_lower:
                    matched.add(cat)
                    break
        return matched

    def compute_lexical_similarity(self, query: str, product_name: str, description: str) -> float:
        """Computes lexical token overlap and fuzzy word similarity."""
        q_words = set(re.findall(r"\w+", query.lower()))
        doc_text = f"{product_name} {description}".lower()
        doc_words = set(re.findall(r"\w+", doc_text))

        if not q_words:
            return 0.0

        intersection = q_words.intersection(doc_words)
        token_score = len(intersection) / len(q_words)

        fuzzy_hits = 0
        for qw in q_words:
            if len(qw) >= 4:
                for dw in doc_words:
                    if difflib.SequenceMatcher(None, qw, dw).ratio() > 0.8:
                        fuzzy_hits += 1
                        break
        fuzzy_score = min(fuzzy_hits / len(q_words), 1.0)
        return max(token_score, fuzzy_score)

    # --------------------------------------------------------------------------
    # RETRIEVAL & GROUNDING PIPELINE
    # --------------------------------------------------------------------------

    def search_candidates(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """
        Executes semantic search over ChromaDB index and returns Top-K candidate products.
        Automatically heals index if desynchronization was flagged, or if collection is empty.
        """
        if getattr(self, "_sync_needed", False):
            self.auto_heal_if_needed()

        total_indexed = self.collection.count()
        if total_indexed == 0:
            self.sync_all_products()
            total_indexed = self.collection.count()

        if total_indexed == 0:
            return []

        n_results = min(top_k, total_indexed)
        res = self.collection.query(
            query_texts=[query],
            n_results=n_results
        )

        candidates = []
        ids_list = res.get("ids")
        if ids_list and len(ids_list) > 0:
            metadatas_list = res.get("metadatas")
            documents_list = res.get("documents")
            distances_list = res.get("distances")

            for idx, pid_str in enumerate(ids_list[0]):
                meta = metadatas_list[0][idx] if (metadatas_list and len(metadatas_list) > 0) else {}
                doc = documents_list[0][idx] if (documents_list and len(documents_list) > 0) else ""
                dist = distances_list[0][idx] if (distances_list and len(distances_list) > 0) else None
                candidates.append({
                    "product_id": int(pid_str),
                    "metadata": meta,
                    "document": doc,
                    "distance": dist,
                })
        return candidates

    def get_grounded_recommendation_context(
        self,
        query: str,
        top_k: int = 5,
        budget_max: Optional[float] = None,
        distance_cutoff: float = 0.55
    ) -> Dict[str, Any]:
        """
        Crucial Hybrid RAG Pipeline with SQLite Post-Retrieval Verification Guard:
        1. Out-of-Domain Guard: rejects queries unrelated to store catalog with 0 hallucinated products.
        2. ChromaDB Dense Search (top_k * 3 pool) with empirical distance cutoff.
        3. Sparse / Lexical Re-ranking with category affinity boosting.
        4. Strict SQLite Post-Retrieval Verification Guard (status='active', stock_quantity > 0, budget).
        5. Explicit Out-of-Stock Detection: identifies specifically requested items that are zero stock.
        6. Prompt Injection Neutralization: cleans text before assembling prompt context.
        """
        # Step 1: Out-of-Domain Guard
        if self.is_out_of_domain(query):
            return {
                "products": [],
                "context_text": "Cửa hàng StoreFlow AI hiện không kinh doanh các mặt hàng hoặc dịch vụ này. Chúng tôi chuyên cung cấp thiết bị công nghệ, phụ kiện văn phòng, âm thanh và gaming gear.",
                "out_of_stock_detected": None,
                "out_of_stock_excluded": [],
                "total_verified": 0,
                "status": "out_of_domain"
            }

        # Step 2: Dense Retrieval from ChromaDB
        raw_candidates = self.search_candidates(query, top_k=max(top_k * 3, 15))
        if not raw_candidates:
            return self._fallback_sqlite_search(query, top_k, budget_max)

        top1 = raw_candidates[0]
        top1_dist = top1.get("distance", 1.0)

        # Step 3: Fetch candidate details from SQLite
        candidate_pids = [c["product_id"] for c in raw_candidates]
        placeholders = ",".join("?" for _ in candidate_pids)

        with get_db_connection() as conn:
            c = conn.cursor()
            # Explicitly NEVER select cost_price
            c.execute(f"""
                SELECT p.id, p.sku, p.name, p.category_id, c.name as category_name,
                       p.selling_price, p.stock_quantity, p.unit, p.status, p.description, p.image_url
                FROM products p
                LEFT JOIN categories c ON p.category_id = c.id
                WHERE p.id IN ({placeholders})
            """, candidate_pids)
            all_candidate_rows = {r["id"]: dict(r) for r in c.fetchall()}

        # Step 4: Detect Target Category
        target_cats = self.detect_target_categories(query)

        # Step 5: Check if top candidate is an explicit Out-Of-Stock item requested by name
        oos_detected = None
        if top1["product_id"] in all_candidate_rows:
            top1_row = all_candidate_rows[top1["product_id"]]
            if top1_row.get("stock_quantity", 0) <= 0:
                name_words = set(re.findall(r"\w+", top1_row["name"].lower()))
                q_words = set(re.findall(r"\w+", query.lower()))
                if len(name_words.intersection(q_words)) >= 2 or top1_dist < 0.32:
                    oos_detected = top1_row

        # Step 6: Hybrid Scoring & Re-ranking
        scored_candidates = []
        for cand in raw_candidates:
            pid = cand["product_id"]
            dist = cand.get("distance", 1.0)
            row = all_candidate_rows.get(pid)
            if not row:
                continue

            dense_score = max(0.0, 1.0 - dist)
            lexical_score = self.compute_lexical_similarity(query, row["name"], row.get("description", ""))

            category_boost = 0.0
            if target_cats:
                if row.get("category_name") in target_cats:
                    category_boost = 0.30
                else:
                    category_boost = -0.25 # Penalize mismatching categories

            hybrid_score = (dense_score * 0.6) + (lexical_score * 0.4) + category_boost
            scored_candidates.append({
                "product_id": pid,
                "row": row,
                "distance": dist,
                "dense_score": dense_score,
                "lexical_score": lexical_score,
                "hybrid_score": hybrid_score
            })

        scored_candidates.sort(key=lambda x: x["hybrid_score"], reverse=True)

        verified_products: List[Dict[str, Any]] = []
        out_of_stock_excluded: List[Dict[str, Any]] = []

        for sc in scored_candidates:
            p_data = sc["row"]
            dist = sc["distance"]

            # Cutoff filter: discard if distance exceeds threshold AND lexical score is low
            if dist > distance_cutoff and sc["lexical_score"] < 0.20:
                continue

            # Strict category guard: If specific categories were detected in user query,
            # reject products from unrelated categories completely
            if target_cats and p_data.get("category_name") not in target_cats:
                continue

            # Strict guard: active and stock > 0
            if p_data.get("status") == "active" and p_data.get("stock_quantity", 0) > 0:
                if budget_max is not None and budget_max > 0:
                    if p_data.get("selling_price", 0) > budget_max:
                        continue
                verified_products.append(p_data)
                if len(verified_products) >= top_k:
                    break
            else:
                out_of_stock_excluded.append({
                    "id": p_data["id"],
                    "name": p_data["name"],
                    "sku": p_data["sku"],
                    "stock_quantity": p_data.get("stock_quantity", 0),
                    "status": p_data.get("status", "")
                })

        # If user specifically asked for an out-of-stock product, clear unrelated items
        if oos_detected and (not verified_products or top1_dist < 0.28):
            verified_products = []

        # Step 7: Assemble Grounded Context for LLM
        context_lines = []
        if oos_detected:
            context_lines.append(
                f"CẢNH BÁO TỒN KHO THỰC TẾ: Sản phẩm '{oos_detected['name']}' (Mã SKU: {oos_detected['sku']}) "
                f"hiện ĐÃ HẾT HÀNG (tồn kho: 0). Cửa hàng tạm thời không còn hàng sản phẩm này."
            )

        if verified_products:
            context_lines.append("DANH SÁCH SẢN PHẨM KHẢ DỤNG TẠI CỬA HÀNG (ĐÃ XÁC THỰC TỒN KHO THỰC TẾ TRONG SQL):")
            for idx, vp in enumerate(verified_products, start=1):
                price_fmt = f"{int(vp['selling_price']):,} đ"
                clean_desc = self._sanitize_text(vp.get('description', '') or 'Đang cập nhật')
                context_lines.append(
                    f"{idx}. [ID {vp['id']}] {vp['name']} (Mã SKU: {vp['sku']})\n"
                    f"   - Nhóm hàng: {vp['category_name']}\n"
                    f"   - Giá bán: {price_fmt}\n"
                    f"   - Tồn kho khả dụng: {vp['stock_quantity']} {vp['unit']} (CÒN HÀNG TRONG KHO)\n"
                    f"   - Mô tả / Thông số: {clean_desc}"
                )
        elif not oos_detected:
            context_lines.append("KHÔNG TÌM THẤY SẢN PHẨM NÀO CÒN HÀNG PHÙ HỢP VỚI TIÊU CHÍ VÀ NGÂN SÁCH YÊU CẦU.")

        return {
            "products": verified_products,
            "context_text": "\n\n".join(context_lines),
            "out_of_stock_detected": oos_detected,
            "out_of_stock_excluded": out_of_stock_excluded,
            "total_verified": len(verified_products),
            "status": "success" if verified_products else ("out_of_stock" if oos_detected else "empty")
        }

    def _fallback_sqlite_search(
        self,
        query: str,
        top_k: int = 5,
        budget_max: Optional[float] = None
    ) -> Dict[str, Any]:
        """Fallback direct SQL keyword search if vector search returns zero results."""
        if self.is_out_of_domain(query):
            return {
                "products": [],
                "context_text": "Cửa hàng hiện không kinh doanh các mặt hàng này.",
                "out_of_stock_detected": None,
                "out_of_stock_excluded": [],
                "total_verified": 0,
                "status": "out_of_domain"
            }

        keyword = f"%{query.strip()}%"
        with get_db_connection() as conn:
            c = conn.cursor()
            params: List[Any] = [keyword, keyword, keyword]
            budget_clause = ""
            if budget_max is not None and budget_max > 0:
                budget_clause = " AND p.selling_price <= ? "
                params.append(budget_max)
            params.append(top_k)

            c.execute(f"""
                SELECT p.id, p.sku, p.name, p.category_id, c.name as category_name,
                       p.selling_price, p.stock_quantity, p.unit, p.status, p.description, p.image_url
                FROM products p
                LEFT JOIN categories c ON p.category_id = c.id
                WHERE (p.name LIKE ? OR p.description LIKE ? OR c.name LIKE ?)
                  AND p.status = 'active'
                  AND p.stock_quantity > 0
                  {budget_clause}
                ORDER BY p.stock_quantity DESC
                LIMIT ?
            """, params)
            rows = [dict(r) for r in c.fetchall()]

        context_lines = []
        if rows:
            context_lines.append("DANH SÁCH SẢN PHẨM KHẢ DỤNG TẠI CỬA HÀNG (TRA CỨU TRỰC TIẾP SQL):")
            for idx, vp in enumerate(rows, start=1):
                price_fmt = f"{int(vp['selling_price']):,} đ"
                clean_desc = self._sanitize_text(vp.get('description', '') or 'Đang cập nhật')
                context_lines.append(
                    f"{idx}. [ID {vp['id']}] {vp['name']} (Mã SKU: {vp['sku']})\n"
                    f"   - Nhóm hàng: {vp['category_name']}\n"
                    f"   - Giá bán: {price_fmt}\n"
                    f"   - Tồn kho: {vp['stock_quantity']} {vp['unit']}\n"
                    f"   - Mô tả: {clean_desc}"
                )
        else:
            context_lines.append("KHÔNG CÓ SẢN PHẨM PHÙ HỢP CÒN TỒN KHO TRONG HỆ THỐNG.")

        return {
            "products": rows,
            "context_text": "\n\n".join(context_lines),
            "out_of_stock_detected": None,
            "out_of_stock_excluded": [],
            "total_verified": len(rows),
            "status": "success" if rows else "empty"
        }


# Global singleton instance
rag_service = RAGService()
