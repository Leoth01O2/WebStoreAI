import os
from pathlib import Path
from typing import List, Dict, Any, Optional
import chromadb

from app.core.config import settings, BASE_DIR
from app.core.database import get_db_connection


class RAGService:
    """
    RAG & Vector Retrieval Service using persistent ChromaDB with SQLite Post-Retrieval Verification Guard.
    Ensures that recommendations only ever include products that are active and strictly in-stock.
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

    def _build_product_document(self, p: Dict[str, Any]) -> str:
        """Constructs a descriptive semantic text chunk for product indexing."""
        price_str = f"{int(p.get('selling_price', 0)):,} VNĐ"
        return (
            f"Mã: {p.get('sku', '')} | Tên sản phẩm: {p.get('name', '')} | "
            f"Danh mục: {p.get('category_name', '')} | Giá bán: {price_str} | "
            f"Đơn vị: {p.get('unit', 'cái')} | Mô tả & Đặc tính: {p.get('description', '')}"
        )

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

    def search_candidates(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """
        Executes semantic search over ChromaDB index and returns Top-K candidate products.
        """
        total_indexed = self.collection.count()
        if total_indexed == 0:
            # Auto-sync if collection is currently empty
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
        budget_max: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Crucial Hybrid RAG Pipeline with SQLite Post-Retrieval Verification Guard:
        1. Queries ChromaDB for candidates (requests top_k * 3 candidates to absorb out-of-stock items).
        2. Queries SQLite to strictly verify `status = 'active'` AND `stock_quantity > 0`.
        3. Filters by optional `budget_max`.
        4. Sorts by original semantic relevance order.
        5. Assembles grounded context string for Gemini prompt.
        """
        # Fetch larger pool of semantic candidates
        raw_candidates = self.search_candidates(query, top_k=max(top_k * 3, 10))
        if not raw_candidates:
            # Fallback to direct SQLite search if ChromaDB has no match
            return self._fallback_sqlite_search(query, top_k, budget_max)

        candidate_pids = [c["product_id"] for c in raw_candidates]
        placeholders = ",".join("?" for _ in candidate_pids)

        with get_db_connection() as conn:
            c = conn.cursor()
            # Fetch candidate products directly from SQLite
            c.execute(f"""
                SELECT p.id, p.sku, p.name, p.category_id, c.name as category_name,
                       p.selling_price, p.stock_quantity, p.unit, p.status, p.description, p.image_url
                FROM products p
                LEFT JOIN categories c ON p.category_id = c.id
                WHERE p.id IN ({placeholders})
            """, candidate_pids)
            all_candidate_rows = {r["id"]: dict(r) for r in c.fetchall()}

        verified_products: List[Dict[str, Any]] = []
        out_of_stock_excluded: List[Dict[str, Any]] = []

        # Maintain semantic rank ordering
        for pid in candidate_pids:
            p_data = all_candidate_rows.get(pid)
            if not p_data:
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

        context_lines = []
        if verified_products:
            context_lines.append("DANH SÁCH SẢN PHẨM KHẢ DỤNG TẠI CỬA HÀNG (ĐÃ XÁC THỰC TỒN KHO THỰC TẾ TRONG SQL):")
            for idx, vp in enumerate(verified_products, start=1):
                price_fmt = f"{int(vp['selling_price']):,} đ"
                context_lines.append(
                    f"{idx}. [ID {vp['id']}] {vp['name']} (Mã SKU: {vp['sku']})\n"
                    f"   - Nhóm hàng: {vp['category_name']}\n"
                    f"   - Giá bán: {price_fmt}\n"
                    f"   - Tồn kho khả dụng: {vp['stock_quantity']} {vp['unit']} (CÒN HÀNG TRONG KHO)\n"
                    f"   - Mô tả / Thông số: {vp['description'] or 'Đang cập nhật'}"
                )
        else:
            context_lines.append("KHÔNG TÌM THẤY SẢN PHẨM NÀO CÒN HÀNG PHÙ HỢP VỚI TIÊU CHÍ VÀ NGÂN SÁCH YÊU CẦU.")

        return {
            "products": verified_products,
            "context_text": "\n\n".join(context_lines),
            "out_of_stock_excluded": out_of_stock_excluded,
            "total_verified": len(verified_products),
        }

    def _fallback_sqlite_search(
        self,
        query: str,
        top_k: int = 5,
        budget_max: Optional[float] = None
    ) -> Dict[str, Any]:
        """Fallback direct SQL keyword search if vector search returns zero results."""
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
                context_lines.append(
                    f"{idx}. [ID {vp['id']}] {vp['name']} (Mã SKU: {vp['sku']})\n"
                    f"   - Nhóm hàng: {vp['category_name']}\n"
                    f"   - Giá bán: {price_fmt}\n"
                    f"   - Tồn kho: {vp['stock_quantity']} {vp['unit']}\n"
                    f"   - Mô tả: {vp['description'] or 'Đang cập nhật'}"
                )
        else:
            context_lines.append("KHÔNG CÓ SẢN PHẨM PHÙ HỢP CÒN TỒN KHO TRONG HỆ THỐNG.")

        return {
            "products": rows,
            "context_text": "\n\n".join(context_lines),
            "out_of_stock_excluded": [],
            "total_verified": len(rows),
        }


# Global singleton instance
rag_service = RAGService()
