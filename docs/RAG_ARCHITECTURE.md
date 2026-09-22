# BÁO CÁO PHÂN TÍCH KIẾN TRÚC RAG (RETRIEVAL-AUGMENTED GENERATION) & LUỒNG DỮ LIỆU STOREFLOW AI

> **Dự án**: StoreFlow AI - Hệ thống Quản lý Bán hàng & Trợ lý AI Thông minh  
> **Tài liệu tham chiếu**: Codebase Backend (`app/services/rag_service.py`, `app/services/ai_service.py`), Prompts (`prompts/`), Database SQLite (`webstore.db`) & ChromaDB (`chroma_data/`)

---

## 1. MÔ HÌNH EMBEDDING & VECTOR DB (CHROMADB)

### 1.1. Tên chính xác của mô hình Embedding
- Trong [`rag_service.py`](../backend/app/services/rag_service.py):
  ```python
  self.persist_dir.mkdir(parents=True, exist_ok=True)
  self.client = chromadb.PersistentClient(path=str(self.persist_dir))
  self.collection = self.client.get_or_create_collection(
      name="storeflow_products",
      metadata={"hnsw:space": "cosine"}
  )
  ```
- Khởi tạo `get_or_create_collection()` không truyền tham số `embedding_function` tùy biến.
- Theo cơ chế mặc định của thư viện `chromadb` (xem [`requirements.txt`](../backend/requirements.txt)), ChromaDB sử dụng mô hình embedding mặc định: **`all-MiniLM-L6-v2`** (chạy qua ONNX runtime: `ONNXMiniLM_L6_V2`) với độ đo khoảng cách Cosine (`metadata={"hnsw:space": "cosine"}`).

### 1.2. Tên Collection thực tế trong ChromaDB
- Tên Collection chính xác được đặt cố định là: **`storeflow_products`** (dòng 29 trong [`rag_service.py`](../backend/app/services/rag_service.py)).

### 1.3. Thời điểm Indexing / Sync dữ liệu từ SQLite sang ChromaDB
Hệ thống kích hoạt đồng bộ hóa dữ liệu tại **3 thời điểm**:
1. **Khi Server FastAPI khởi động (Server Startup Lifespan)**:
   - Trong `lifespan` tại [`main.py`](../backend/app/main.py): nếu `rag_service.collection.count() == 0`, hệ thống tự động gọi `rag_service.sync_all_products()`.
   - Ngay cả khi thực hiện tìm kiếm qua `search_candidates()`, nếu vector index rỗng cũng có cơ chế tự động kích hoạt `sync_all_products()`.
2. **Khi thao tác CRUD Sản phẩm trong SQLite**:
   - *Thêm sản phẩm mới* (`POST /api/v1/products`): gọi `rag_service.upsert_single_product(new_id)` ([`products.py:L228-233`](../backend/app/api/v1/products.py)).
   - *Cập nhật sản phẩm* (`PUT /api/v1/products/{id}`): gọi `rag_service.upsert_single_product(product_id)` ([`products.py:L271-275`](../backend/app/api/v1/products.py)).
   - *Xóa sản phẩm* (`DELETE /api/v1/products/{id}`):
     - Nếu xóa cứng: gọi `rag_service.delete_single_product(product_id)` ([`products.py:L310-313`](../backend/app/api/v1/products.py)).
     - Nếu xóa mềm (chuyển trạng thái `inactive` do đã có lịch sử hóa đơn): gọi `rag_service.upsert_single_product(product_id)` ([`products.py:L321-324`](../backend/app/api/v1/products.py)).
3. **Chạy qua API Endpoint đồng bộ thủ công**:
   - Endpoint `POST /api/v1/ai/sync-index` ([`ai.py:L96-111`](../backend/app/api/v1/ai.py)) cho phép Quản trị viên (Admin) ép quét lại toàn bộ bảng `products` từ SQLite và nạp lại vào ChromaDB.

---

## 2. QUY TRÌNH RETRIEVAL & SQLITE GUARDRAIL

### 2.1. Hàm xử lý Semantic Search lấy Top-K ứng viên
- Hàm **`search_candidates(query: str, top_k: int = 5)`** trong [`rag_service.py:L123-159`](../backend/app/services/rag_service.py).
- Cơ chế xử lý:
  - Kiểm tra số lượng bản ghi trong collection.
  - Gọi phương thức `self.collection.query(query_texts=[query], n_results=n_results)`.
  - Bóc tách kết quả trả về danh sách ứng viên (candidate items) gồm: `product_id`, `metadata`, `document`, `distance`.

### 2.2. Logic chốt chặn (Guardrail) bằng SQLite
- Nằm ở file [`backend/app/services/rag_service.py`](../backend/app/services/rag_service.py), hàm **`get_grounded_recommendation_context(self, query: str, top_k: int = 5, budget_max: Optional[float] = None)`** (dòng 161 - 243).
- Các bước thực thi nghiêm ngặt:
  1. **Lấy tập ứng viên mở rộng (Oversampling)**: Lấy `top_k * 3` (tối thiểu 10) ứng viên từ ChromaDB để dự trù trường hợp một số sản phẩm đã hết hàng.
  2. **Truy vấn SQLite tức thời**:
     ```sql
     SELECT p.id, p.sku, p.name, p.category_id, c.name as category_name,
            p.selling_price, p.stock_quantity, p.unit, p.status, p.description
     FROM products p
     LEFT JOIN categories c ON p.category_id = c.id
     WHERE p.id IN (?, ?, ...)
     ```
  3. **Bộ lọc Chốt chặn (Deterministic Guardrail)**:
     ```python
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
             out_of_stock_excluded.append(p_data)
     ```
  4. **Loại bỏ 100% ảo giác**: Sản phẩm nào hết tồn kho (`stock_quantity <= 0`) hoặc ngưng kinh doanh (`status != 'active'`) đều bị loại bỏ ngay lập tức và tuyệt đối không xuất hiện trong ngữ cảnh (Context) gửi sang AI.
  5. **Dự phòng tìm kiếm trực tiếp (SQL Fallback)**: Nếu ChromaDB trả về 0 kết quả, hàm `_fallback_sqlite_search` ([`rag_service.py:L244-295`](../backend/app/services/rag_service.py)) được kích hoạt để tìm kiếm trực tiếp bằng câu lệnh `LIKE` trên SQLite với cùng điều kiện tồn kho.

---

## 3. TÍCH HỢP LLM (GEMINI) & PROMPTING

### 3.1. Cấu hình Gemini API & Nguồn đọc `GEMINI_API_KEY`
- **File cấu hình**: [`backend/app/core/config.py`](../backend/app/core/config.py).
  - Sử dụng `pydantic-settings` tự động nạp từ file **`backend/.env`** (hoặc biến môi trường hệ thống).
  - Các thiết lập cốt lõi:
    ```python
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-3.6-flash"
    ```
- **Khởi tạo SDK Client**: Trong [`backend/app/services/ai_service.py:L33-36`](../backend/app/services/ai_service.py):
  ```python
  self._client = genai.Client(api_key=settings.GEMINI_API_KEY)
  ```

### 3.2. Vị trí Prompt Template gửi kèm ngữ cảnh (Context)
- Hệ thống phân tách hoàn toàn mã nguồn (Code) và khuôn mẫu câu lệnh (Prompt) thông qua class `PromptLoader` tại [`backend/app/core/prompt_loader.py`](../backend/app/core/prompt_loader.py).
- **Thư mục lưu trữ template**: [`backend/prompts/`](../backend/prompts/)
  - **`product_recommendation.txt`**: Khuôn mẫu prompt tư vấn RAG, chứa các biến chèn động:
    - `{verified_products_context}`: Dữ liệu sản phẩm đã được xác thực qua SQLite.
    - `{user_query}`: Nhu cầu thực tế của khách hàng.
    - `{budget_info}`: Ngân sách dự kiến.
  - **`system_prompt.txt`**: Định nghĩa nhân dạng, phong cách và nguyên tắc bảo mật của StoreFlow AI.
  - **`sales_report.txt`**: Khuôn mẫu sinh báo cáo doanh thu.
  - **`sales_qa.txt`**: Khuôn mẫu hỏi đáp số liệu vận hành cửa hàng.

---

## 4. LUỒNG DỮ LIỆU END-TO-END

1. **Frontend**: Người dùng nhập nhu cầu tư vấn & ngân sách tại giao diện [`AiAssistantPage.jsx`](../frontend/src/pages/AiAssistantPage.jsx). Hàm `handleSearchRec` gọi phương thức `aiAPI.recommend()` tại [`frontend/src/services/api.js`](../frontend/src/services/api.js).
2. **FastAPI Endpoint**: Gửi request `POST /api/v1/ai/recommend` kèm JWT Token. API Controller tiếp nhận tại [`ai.py:L20-39`](../backend/app/api/v1/ai.py), thẩm định phân quyền RBAC (`admin`, `staff`, `manager`).
3. **Retrieval & Guardrail**: `AIService.recommend_products()` gọi `RAGService.get_grounded_recommendation_context()`:
   - **ChromaDB**: Thực hiện Semantic Search trên vector space để lấy Top-15 IDs ứng viên tương đồng nhất.
   - **SQLite**: Truy vấn bảng `products` kiểm tra chốt chặn `stock_quantity > 0`, `status = 'active'`, và giá `<= budget`. Thu được Top-5 sản phẩm khả dụng thực tế, ghép thành chuỗi văn bản `verified_products_context`.
4. **Prompt Assembly**: `PromptLoader` nạp file [`prompts/product_recommendation.txt`](../backend/prompts/product_recommendation.txt) và định dạng với ngữ cảnh đã xác thực.
5. **Gemini Generation & Fallback**: `AIService._call_gemini()` gọi model `gemini-3.6-flash`. Nếu API gặp sự cố hoặc timeout, hệ thống tự động chuyển sang chế độ **Rule-based Fallback** tự sinh phản hồi từ dữ liệu SQLite đã kiểm chứng, không để đứt gãy luồng người dùng.
6. **Audit Logging & Response**: Ghi nhận vết kiểm toán vào bảng SQLite `ai_audit_logs` (thời gian phản hồi, người dùng, nội dung), trả về JSON `ProductRecommendResponse` gồm văn bản phản hồi và mảng cấu trúc sản phẩm.
7. **Frontend Render**: [`AiAssistantPage.jsx`](../frontend/src/pages/AiAssistantPage.jsx) nhận dữ liệu, hiển thị câu trả lời AI bằng Markdown cùng danh sách thẻ sản phẩm trực quan (hình ảnh, giá tiền, số lượng tồn khả dụng, nút bấm thêm trực tiếp vào giỏ hàng POS).

---

## 5. ĐỐI CHIẾU MÔ HÌNH 3 PHASE CỦA RAG TRONG BÀI TOÁN

Kiến trúc trong dự án tuân thủ đầy đủ mô hình 3 Phase tiêu chuẩn của RAG, đồng thời bổ sung **Deterministic Relational Guardrail** đặc thù cho bài toán Bán lẻ / E-Commerce:

```
[Phase 1: Indexing]
  SQLite Products (Name, SKU, Description, Category, Price)
        ↓
  _build_product_document() (Chuẩn hóa & ghép chuỗi thuộc tính)
        ↓
  Embedding (Mặc định ChromaDB: all-MiniLM-L6-v2)
        ↓
  Vector Database (ChromaDB Collection: "storeflow_products")
  (Đồng bộ tại: Server Startup, CRUD Sản phẩm, hoặc API /sync-index)

                                |
                                v

[Phase 2: Retrieval & Guardrail]
  User Query & Budget
        ↓
  ChromaDB Cosine Similarity Search -> Oversampled Top-(K*3) Candidates
        ↓
  [Chốt chặn SQLite Guardrail]: Lọc `status = 'active'` AND `stock_quantity > 0` AND `<= budget`
  (Loại bỏ 100% rủi ro tư vấn sản phẩm hết hàng hoặc ảo giác tồn kho)
        ↓
  Re-ordered Context (Duy trì thứ tự ưu tiên theo Semantic Rank)

                                |
                                v

[Phase 3: Generation & Grounding]
  External Template (prompts/product_recommendation.txt) + Verified Products Context
        ↓
  Google Gemini (gemini-3.6-flash) [Có Rule-based Fallback khi mất kết nối]
        ↓
  Answer with Citation (SKU, giá bán, số lượng tồn khả dụng) + Thẻ sản phẩm UI
```

### So sánh điểm khác biệt với RAG thông thường:
- **RAG tài liệu thông thường**: Text Chunking tùy ý -> Top-K Vector Search -> Re-ranking -> LLM Context.
- **RAG StoreFlow AI (Hybrid Relational RAG)**: Entity-based Chunking -> Top-K Candidate Search -> **SQLite Guardrail (Single Source of Truth)** -> Grounded Context -> LLM Generation. Cơ chế này đảm bảo dữ liệu bán lẻ (tồn kho và giá) luôn chính xác theo thời gian thực.
