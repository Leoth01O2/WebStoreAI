# BỘ TÀI LIỆU HỌC TẬP & BẢO VỆ ĐỒ ÁN MÔN ỨNG DỤNG AI

> **Dự án**: StoreFlow AI — Hệ thống Quản lý Bán hàng & Trợ lý Bán lẻ RAG  
> **Môn học**: Ứng dụng Trí tuệ Nhân tạo  
> **Phân công nhiệm vụ**:
> - **Ngô Trung Kiên (Nhóm trưởng)**: AI Architecture & RAG Pipeline
> - **Phan Duy Hưng**: Frontend Engineering & AI UI Integration
> - **Vũ Đức Đạt**: Backend Engineering & SQLite Database

---

## PHẦN 1: NGÔ TRUNG KIÊN (NHÓM TRƯỞNG) — AI ARCHITECTURE & RAG PIPELINE

* **Tệp phụ trách chính**:
  - [`backend/app/services/rag_service.py`](../backend/app/services/rag_service.py)
  - [`backend/app/services/ai_service.py`](../backend/app/services/ai_service.py)
  - [`backend/app/core/prompt_loader.py`](../backend/app/core/prompt_loader.py)
  - [`backend/prompts/product_recommendation.txt`](../backend/prompts/product_recommendation.txt)
  - [`backend/prompts/system_prompt.txt`](../backend/prompts/system_prompt.txt)

---

### 1. Phân tích Khởi tạo ChromaDB, Mô hình Embedding & Collection
* **Khởi tạo ChromaDB Persistent Client** ([`rag_service.py:L26-31`](../backend/app/services/rag_service.py)):
  ```python
  self.persist_dir.mkdir(parents=True, exist_ok=True)
  self.client = chromadb.PersistentClient(path=str(self.persist_dir))
  self.collection = self.client.get_or_create_collection(
      name="storeflow_products",
      metadata={"hnsw:space": "cosine"}
  )
  ```
  - **Tên Collection**: `storeflow_products`.
  - **Mô hình Embedding thực tế**: Mã nguồn không truyền tham số `embedding_function`, do đó ChromaDB tự động sử dụng hàm mặc định `DefaultEmbeddingFunction` (`ONNXMiniLM_L6_V2`). Mô hình nền tảng là **`all-MiniLM-L6-v2`** (kích thước vector: 384 chiều) chạy trực tiếp thông qua ONNX runtime nội bộ.
  - **Độ đo khoảng cách**: Cosine Similarity (`"hnsw:space": "cosine"`).

* **Xây dựng Document Chunking cho Sản phẩm** ([`rag_service.py:L33-40`](../backend/app/services/rag_service.py)):
  ```python
  def _build_product_document(self, p: Dict[str, Any]) -> str:
      price_str = f"{int(p.get('selling_price', 0)):,} VNĐ"
      return (
          f"Mã: {p.get('sku', '')} | Tên sản phẩm: {p.get('name', '')} | "
          f"Danh mục: {p.get('category_name', '')} | Giá bán: {price_str} | "
          f"Đơn vị: {p.get('unit', 'cái')} | Mô tả & Đặc tính: {p.get('description', '')}"
      )
  ```
  - Thay vì cắt đoạn tùy ý (arbitrary text chunking), hệ thống áp dụng kỹ thuật **Entity-based Semantic Chunking**: Mỗi một bản ghi sản phẩm được tổng hợp thành một chuỗi ngữ nghĩa trọn vẹn gồm SKU, Tên, Nhóm hàng, Giá và Mô tả kỹ thuật.

---

### 2. Chi tiết Semantic Search (Top-K) & Lắp ghép Prompt gửi Gemini
* **Hàm Semantic Search Top-K** ([`rag_service.py:L123-159`](../backend/app/services/rag_service.py)):
  ```python
  def search_candidates(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
      res = self.collection.query(
          query_texts=[query],
          n_results=min(top_k, self.collection.count())
      )
  ```
  - Cơ chế: Biến đổi câu hỏi `query` của người dùng thành vector embedding, sau đó thực hiện thuật toán HNSW (Hierarchical Navigable Small World) để tính Cosine Distance với các vector sản phẩm trong ChromaDB, trả về `ids`, `metadatas`, `documents`, `distances`.

* **Kỹ thuật Oversampling & Lắp ghép Prompt** ([`ai_service.py:L95-111`](../backend/app/services/ai_service.py)):
  ```python
  # 1. Trích xuất pool ứng viên rộng hơn (top_k * 3, min 10) để bù đắp sản phẩm hết hàng
  rag_context = rag_service.get_grounded_recommendation_context(
      query=user_query, top_k=limit, budget_max=budget_val
  )
  # 2. Format Prompt từ file khuôn mẫu độc lập
  prompt = prompt_loader.format_prompt(
      "product_recommendation",
      verified_products_context=rag_context["context_text"],
      user_query=user_query,
      budget_info=budget_str
  )
  # 3. Gửi sang Gemini 3.6 Flash với System Instruction
  ai_text = self._call_gemini(prompt)
  ```
  - Context truyền sang Gemini là chuỗi danh sách sản phẩm **đã được lọc sạch 100% qua SQLite** (chỉ còn các mặt hàng thực sự còn tồn kho > 0).

---

### 3. Bộ 5 câu hỏi vấn đáp RAG/Vector DB Giảng viên hay hỏi nhất

#### Câu 1: "Tại sao nhóm em không dùng trực tiếp câu truy vấn SQL LIKE để tìm sản phẩm mà phải dùng thêm ChromaDB?"
* **Trả lời**:  
  "Thưa Thầy/Cô, tìm kiếm SQL `LIKE` chỉ so khớp từ khóa chính xác (Keyword Matching). Nếu khách hàng nhập *'bàn phím gõ êm văn phòng không ồn'* trong khi sản phẩm lưu tên là *'Bàn phím cơ Silent Switch'* thì SQL LIKE sẽ không tìm thấy. ChromaDB sử dụng mô hình embedding biến văn bản thành vector ngữ nghĩa trong không gian đa chiều, giúp tìm ra các sản phẩm có ý nghĩa tương đương ngay cả khi không trùng từ khóa."

#### Câu 2: "Tại sao nhóm không đưa trực tiếp kết quả Top-K từ ChromaDB vào Prompt cho Gemini mà phải qua hàm `get_grounded_recommendation_context`?"
* **Trả lời**:  
  "Dạ, đây chính là **kiến trúc Hybrid RAG kết hợp Relational Guardrail** tại hàm `get_grounded_recommendation_context` trong file `rag_service.py`. Vector DB chỉ lưu trữ ngữ nghĩa tĩnh, nếu vừa có đơn hàng mua hết sản phẩm tại quầy thì dữ liệu vector có thể chưa kịp cập nhật hoặc embedding vẫn cho điểm cao. Nếu đưa thẳng vào LLM sẽ gây ra hiện tượng **Hallucination (Ảo giác)** tư vấn hàng đã hết. Do đó, hệ thống buộc phải truy vấn lại SQLite kiểm tra `stock_quantity > 0` và `status = 'active'` trước khi nạp vào Prompt."

#### Câu 3: "Mô hình Embedding đang chạy là gì? Chạy local hay qua Cloud API? Tốn phí không?"
* **Trả lời**:  
  "Dạ, mô hình embedding là **`all-MiniLM-L6-v2`** chạy **hoàn toàn Offline / Local** thông qua thư viện ChromaDB và ONNX Runtime tích hợp sẵn ở Backend. Quá trình vector hóa không phụ thuộc API ngoài, không mất phí và có độ trễ cực thấp (khoảng 10-20ms)."

#### Câu 4: "Khi LLM Gemini bị mất mạng hoặc hết Quota API thì hệ thống xử lý như thế nào?"
* **Trả lời**:  
  "Trong hàm `recommend_products` tại `ai_service.py:L117-138`, nhóm cài đặt khối `try...except` với cơ chế **Rule-based Graceful Fallback**: Nếu API Gemini trả về Exception, hệ thống đánh dấu cờ `is_fallback = True` và tự động dùng dữ liệu sản phẩm đã xác thực từ SQLite để định dạng câu trả lời văn bản cho người dùng, đảm bảo trải nghiệm bán hàng không bị gián đoạn."

#### Câu 5: "Oversampling trong bước Retrieval ở đây nghĩa là gì và tại sao lại nhân 3 (`top_k * 3`)?"
* **Trả lời**:  
  "Dạ, nếu người dùng muốn lấy 5 sản phẩm (`top_k = 5`), nếu ta chỉ lấy đúng 5 sản phẩm từ ChromaDB thì rất có thể trong 5 sản phẩm đó có 2-3 sản phẩm đã hết hàng trong kho. Sau khi qua bộ lọc SQLite ta chỉ còn 2 sản phẩm, không đủ nhu cầu. Do đó tại `rag_service.py:L176`, nhóm oversample lấy `max(top_k * 3, 10)` tức 15 ứng viên, sau đó lọc tồn kho rồi cắt đúng 5 sản phẩm hợp lệ đầu tiên theo thứ tự độ tương đồng giảm dần."

---

### 4. Danh sách 5 thuật ngữ AI cốt lõi cần học thuộc lòng
1. **RAG (Retrieval-Augmented Generation)**: Kỹ thuật kết hợp giữa việc truy xuất dữ liệu thực tế (Retrieval) và mô hình ngôn ngữ lớn (Generation) để câu trả lời chính xác, cập nhật và không bị ảo giác.
2. **Vector Embedding**: Biểu diễn ngữ nghĩa của văn bản dưới dạng một chuỗi số thực trong không gian đa chiều (ở đây là không gian 384 chiều).
3. **Cosine Similarity**: Độ đo góc giữa 2 vector trong không gian đa chiều để xác định mức độ tương đồng ngữ nghĩa giữa câu truy vấn và sản phẩm.
4. **Hallucination (Ảo giác AI)**: Hiện tượng LLM tự bịa ra thông tin không có thật. Dự án triệt tiêu ảo giác bằng SQLite Guardrail.
5. **Prompt Engineering & System Instruction**: Kỹ thuật thiết kế khuôn mẫu chỉ thị hệ thống để ép LLM tuân thủ nguyên tắc (không tư vấn ngoài danh mục, giữ văn phong lịch sự, trích dẫn giá và SKU rõ ràng).

---

## PHẦN 2: PHAN DUY HƯNG — FRONTEND ENGINEERING & AI UI INTEGRATION

* **Tệp phụ trách chính**:
  - [`frontend/src/pages/AiAssistantPage.jsx`](../frontend/src/pages/AiAssistantPage.jsx)
  - [`frontend/src/services/api.js`](../frontend/src/services/api.js)
  - [`frontend/src/components/ui/Badge.jsx`](../frontend/src/components/ui/Badge.jsx)
  - [`frontend/src/index.css`](../frontend/src/index.css)

---

### 1. Luồng Gửi/Nhận Dữ liệu giữa React Frontend & API Backend
* **Hàm gọi API trong `api.js`** ([`api.js:L253-257`](../frontend/src/services/api.js)):
  ```javascript
  export const aiAPI = {
    recommend: (query, budget = null, limit = 5) =>
      request('/ai/recommend', {
        method: 'POST',
        body: JSON.stringify({ query, budget: budget ? Number(budget) : null, limit: Number(limit) || 5 }),
      }),
  ```
  - Sử dụng hàm wrapper `request()` tự động đính kèm Header `Authorization: Bearer <token>` lấy từ `localStorage`.
* **Luồng kích hoạt từ UI** ([`AiAssistantPage.jsx:L52-67`](../frontend/src/pages/AiAssistantPage.jsx)):
  - Người dùng bấm Submit form hoặc bấm vào các nút gợi ý nhanh `quickRecQueries`.
  - `handleRecommendSubmit`: Bật cờ `setRecLoading(true)`, gọi `aiAPI.recommend(...)`, nhận JSON response và lưu vào state `setRecResult(data)`. Khối `finally` tắt `setRecLoading(false)`.

---

### 2. Xử lý State React & Render 2 Cột (Markdown Text & Product Cards)
* **Quản lý State**:
  - `recQuery`: Chuỗi tìm kiếm nhập từ ô input.
  - `recBudget`: Ngân sách tối đa của khách hàng.
  - `recLoading`: Trạng thái boolean quản lý Skeleton / Loading Spinner phong cách Retro CRT.
  - `recResult`: Chứa object trả về từ Backend gồm: `{ ai_response, recommended_products, is_fallback, total_candidates_found }`.

* **Layout chia 2 cột đối xứng (Source Attribution & Citation)** ([`AiAssistantPage.jsx:L545-680`](../frontend/src/pages/AiAssistantPage.jsx)):
  - **Cột trái (60% - `1.4fr`)**: Hiển thị toàn văn phân tích của AI qua `recResult.ai_response`. Có Badge hiển thị `Gemini 3.6 Flash Grounded` hoặc `Chế độ tra cứu trực tiếp` nếu fallback.
  - **Cột phải (40% - `1fr`)**: Danh sách thẻ sản phẩm (`recResult.recommended_products.map((p) => ...)`):
    - Hiển thị SKU, Tên, Danh mục, Mô tả ngắn, Giá tiền nổi bật (`formatVND(p.selling_price)`).
    - `StockBadge`: Huy hiệu tồn kho thời gian thực (`quantity={p.stock_quantity}`).
    - Nút **"Mở bán POS"** (`onNavigate('pos')`): Cho phép nhân viên thu ngân bấm 1 chạm chuyển thẳng sang màn hình tạo hóa đơn bán hàng cho khách.

---

### 3. Bộ 5 câu hỏi vấn đáp Frontend & AI UX Giảng viên hay hỏi nhất

#### Câu 1: "Làm thế nào Frontend phân biệt được câu trả lời được sinh từ Gemini hay câu trả lời dự phòng (Fallback) khi rớt mạng?"
* **Trả lời**:  
  "Dạ, trong API response trả về có trường boolean `is_fallback`. Tại dòng 571 file `AiAssistantPage.jsx`, Frontend kiểm tra `recResult.is_fallback`: nếu `false` sẽ render Badge màu xanh lục *'Gemini 3.6 Flash Grounded'*, còn nếu `true` sẽ render Badge màu vàng cảnh báo *'Chế độ tra cứu trực tiếp'* để người dùng minh bạch về nguồn gốc dữ liệu."

#### Câu 2: "Tại sao ở giao diện tư vấn sản phẩm lại tách riêng văn bản AI một bên và thẻ sản phẩm một bên thay vì gộp chung vào 1 khung chat?"
* **Trả lời**:  
  "Dạ, đây là chuẩn thiết kế **Source Attribution / Citation UI** trong các ứng dụng AI thương mại:
  - Khung văn bản bên trái giúp khách hàng đọc hiểu lý do vì sao sản phẩm phù hợp với nhu cầu.
  - Khung thẻ sản phẩm bên phải cung cấp dữ liệu cấu trúc (ảnh, giá, số lượng tồn thực tế) và quan trọng nhất là có nút **Actionable Button (Mở bán POS)** giúp nhân viên tạo đơn ngay lập tức mà không cần gõ lại mã SKU."

#### Câu 3: "Trong lúc Gemini đang suy nghĩ (mất khoảng 1-2 giây), Frontend làm gì để người dùng không cảm thấy ứng dụng bị đơ?"
* **Trả lời**:  
  "Tại dòng 522 file `AiAssistantPage.jsx`, em dùng state `recLoading`. Khi `true`, màn hình hiển thị khối thông báo với icon Bot xoay tròn (`spin-animation`) kèm mô tả trực quan 3 bước xử lý: *1. Semantic Search ChromaDB ➔ 2. SQLite Stock Guard ➔ 3. Gemini Generation*, mang lại cảm giác chuyên nghiệp theo phong cách Terminal."

#### Câu 4: "Làm thế nào để chặn người dùng nhập rỗng hoặc spam bấm nút gửi liên tục?"
* **Trả lời**:  
  "Tại hàm `handleRecommendSubmit` (`AiAssistantPage.jsx:L54`), em kiểm tra `if (!recQuery.trim())` và gọi `addToast` cảnh báo, đồng thời nút bấm được disable khi `recLoading === true` để ngăn chặn gửi nhiều request trùng lặp."

#### Câu 5: "Frontend có phân quyền hiển thị các tab AI như thế nào giữa Admin, Manager và Staff?"
* **Trả lời**:  
  "Dạ, em đọc thông tin quyền từ `useAuth()`: `isManagerOrAdmin = user?.role === 'admin' || user?.role === 'manager'`. Nhân viên (Staff) tại quầy chỉ được thấy Tab 1 (Tư vấn bán hàng). Còn Tab 2 (Phân tích doanh thu), Tab 3 (Hỏi đáp vận hành) và Tab 4 (Audit Logs) chỉ được render khi `isManagerOrAdmin` là `true` (`AiAssistantPage.jsx:L354-404`)."

---

### 4. Danh sách 5 thuật ngữ Frontend/Web AI cốt lõi cần học thuộc lòng
1. **Source Attribution / Grounding UI**: Giao diện hiển thị rõ ràng nguồn gốc dữ liệu đằng sau câu trả lời của AI (dưới dạng thẻ sản phẩm, link tham chiếu).
2. **Actionable AI Output**: Câu trả lời của AI không chỉ là văn bản bị động mà đi kèm các nút tương tác hành động (như nút *'Mở bán POS'*).
3. **Graceful Degradation / Fallback UI**: Kỹ thuật thiết kế giao diện giúp hệ thống tự suy giảm tính năng nhẹ nhàng khi API gặp sự cố thay vì sập toàn bộ trang.
4. **Conditional Rendering**: Kỹ thuật hiển thị các phần tử giao diện trong React dựa trên điều kiện logic (`recLoading`, `isManagerOrAdmin`, `is_fallback`).
5. **Single Page Application (SPA) State Management**: Quản lý trạng thái luồng dữ liệu cục bộ bằng React Hooks (`useState`, `useEffect`, `useRef`) bảo đảm giao diện phản hồi tức thì không cần tải lại trang.

---

## PHẦN 3: VŨ ĐỨC ĐẠT — BACKEND ENGINEERING & SQLITE DATABASE

* **Tệp phụ trách chính**:
  - [`backend/app/models/schema.py`](../backend/app/models/schema.py)
  - [`backend/app/core/database.py`](../backend/app/core/database.py)
  - [`backend/seed_data.py`](../backend/seed_data.py)
  - [`backend/app/api/v1/products.py`](../backend/app/api/v1/products.py)
  - [`backend/app/api/v1/orders.py`](../backend/app/api/v1/orders.py)

---

### 1. Phân tích Cấu trúc CSDL SQLite & Luồng chạy `seed_data.py`
* **Cấu trúc 10 bảng trong `schema.py`** ([`schema.py:L9-141`](../backend/app/models/schema.py)):
  1. `users`: Tài khoản, mật khẩu băm bcrypt, role (`admin`, `staff`, `manager`).
  2. `categories`: Danh mục nhóm hàng (`id`, `name`, `code`).
  3. `products`: Hàng hóa (`sku`, `name`, `selling_price`, `stock_quantity`, `min_stock_alert`, `status`).
  4. `customers`: Khách hàng, phân nhóm (`retail`, `vip`, `wholesale`), tổng chi tiêu.
  5. `orders` & `order_items`: Hóa đơn bán hàng POS và chi tiết mặt hàng bán.
  6. `purchase_receipts` & `purchase_items`: Phiếu nhập kho từ nhà cung cấp.
  7. `inventory_logs`: Lịch sử biến động xuất/nhập/tồn kho (`quantity_before`, `change_quantity`, `quantity_after`).
  8. `ai_audit_logs`: Bảng nhật ký kiểm toán AI (`feature`, `query_text`, `response_summary`, `latency_ms`).
  - **Tối ưu hóa Index**: Đánh chỉ mục B-Tree tại `idx_products_sku`, `idx_products_status`, `idx_orders_created` giúp tăng tốc độ truy vấn tức thì.

* **Luồng chạy của `seed_data.py`**:
  - Gọi `init_db()` để đảm bảo cấu trúc bảng đã sẵn sàng.
  - Sử dụng transaction kiểm tra nếu database trống thì seed lần lượt: 3 tài khoản mẫu mặc định $\rightarrow$ 5 danh mục hàng hóa $\rightarrow$ 25 sản phẩm thực tế (có cả sản phẩm còn hàng và sản phẩm cố tình để tồn kho = 0 để kiểm tra chốt chặn Guardrail) $\rightarrow$ Đơn hàng và phiếu nhập ban đầu.

---

### 2. Logic Guardrail Kiểm tra Tồn kho & Đồng bộ sang ChromaDB
* **Logic Guardrail kiểm tra tồn kho tại Backend** ([`rag_service.py:L187-213`](../backend/app/services/rag_service.py)):
  ```sql
  SELECT p.id, p.sku, p.name, p.category_id, c.name as category_name,
         p.selling_price, p.stock_quantity, p.unit, p.status, p.description
  FROM products p
  LEFT JOIN categories c ON p.category_id = c.id
  WHERE p.id IN (?, ?, ...)
  ```
  - Code Python duyệt qua kết quả truy vấn:
  ```python
  if p_data.get("status") == "active" and p_data.get("stock_quantity", 0) > 0:
      if budget_max is not None and budget_max > 0:
          if p_data.get("selling_price", 0) > budget_max:
              continue
      verified_products.append(p_data)
  ```
  - **Single Source of Truth**: Bất kể ChromaDB trả về độ tương đồng cao đến đâu, nếu `stock_quantity <= 0` hoặc `status != 'active'`, sản phẩm bị loại bỏ ngay lập tức.

* **Logic Đồng bộ dữ liệu sang ChromaDB khi CRUD Sản phẩm** ([`products.py`](../backend/app/api/v1/products.py)):
  - **Tạo mới (POST)**: Sau khi `cursor.lastrowid` có ID mới, gọi `rag_service.upsert_single_product(new_id)` ([L231](../backend/app/api/v1/products.py)).
  - **Cập nhật (PUT)**: Sau khi lệnh `UPDATE products` thành công, gọi `rag_service.upsert_single_product(product_id)` ([L273](../backend/app/api/v1/products.py)).
  - **Xóa sản phẩm (DELETE)**:
    - Nếu xóa cứng: gọi `rag_service.delete_single_product(product_id)` ([L311](../backend/app/api/v1/products.py)).
    - Nếu xóa mềm (chuyển trạng thái `inactive` do đã có lịch sử hóa đơn): cập nhật lại metadata trong vector DB qua `rag_service.upsert_single_product(product_id)` ([L322](../backend/app/api/v1/products.py)).

---

### 3. Bộ 5 câu hỏi vấn đáp Backend & Database Giảng viên hay hỏi nhất

#### Câu 1: "SQLite là cơ sở dữ liệu dạng file, làm sao đảm bảo khi nhiều người cùng bán hàng không bị lỗi khóa (Database Locked)?"
* **Trả lời**:  
  "Dạ, trong file `database.py`, nhóm em đã kích hoạt chế độ **WAL Mode (Write-Ahead Logging)** bằng câu lệnh `PRAGMA journal_mode=WAL;` và `PRAGMA busy_timeout=5000;`. Chế độ WAL cho phép các luồng Đọc (Readers) và luồng Ghi (Writers) hoạt động đồng thời mà không chặn lẫn nhau, hoàn toàn đáp ứng tốt cho các cửa hàng bán lẻ quy mô vừa và nhỏ."

#### Câu 2: "Tại sao không cập nhật luôn số lượng tồn kho `stock_quantity` vào trong ChromaDB mỗi khi bán hàng mà lại phải dùng SQLite Guardrail?"
* **Trả lời**:  
  "Dạ, Vector DB như ChromaDB được tối ưu hóa cho phép tính khoảng cách ma trận phục vụ tìm kiếm ngữ nghĩa, **không được thiết kế để xử lý các giao dịch ghi tần suất cao (High-frequency ACID Transactions)**. Nếu mỗi lần bán 1 sản phẩm lại phải re-index vector DB thì sẽ gây thắt cổ chai hiệu năng (I/O Bottleneck). Vì vậy, mô hình chuẩn công nghiệp là: *Vector DB chỉ làm nhiệm vụ Semantic Retrieval, còn Relational DB (SQLite) giữ vai trò chốt chặn kiểm tra tồn kho thời gian thực*."

#### Câu 3: "Khi bán hàng trong POS, backend đảm bảo giao dịch trừ tồn kho và tạo hóa đơn toàn vẹn như thế nào để không bị âm kho?"
* **Trả lời**:  
  "Trong `orders.py`, nhóm sử dụng giao dịch SQLite `BEGIN IMMEDIATE`:
  1. Kiểm tra tồn kho của từng món hàng trong giỏ, nếu có món có `stock_quantity < quantity` thì lập tức `ROLLBACK` và ném lỗi HTTP 400.
  2. Tạo bản ghi trong `orders` và `order_items`.
  3. Chạy lệnh `UPDATE products SET stock_quantity = stock_quantity - :qty` và ghi nhận vết sang bảng `inventory_logs`.
  4. Nếu có bất kỳ lỗi nào xảy ra trong chuỗi, toàn bộ sẽ được rollback tự động."

#### Câu 4: "Bảng `ai_audit_logs` dùng để làm gì và lưu những thông số nào?"
* **Trả lời**:  
  "Dạ, bảng `ai_audit_logs` (`schema.py:L122-130`) dùng để giám sát và phục vụ kiểm toán hoạt động của AI theo chuẩn doanh nghiệp. Bảng lưu trữ: `user_id` (người thực hiện hỏi), `feature` (`recommendation`/`sales_report`/`sales_qa`), `query_text` (nội dung câu hỏi), `response_summary` (tóm tắt câu trả lời của AI) và `latency_ms` (thời gian phản hồi tính bằng mili-giây)."

#### Câu 5: "Nếu mạng hoặc ChromaDB bị lỗi trong lúc thêm/sửa sản phẩm thì API tạo sản phẩm có bị sập theo không?"
* **Trả lời**:  
  "Dạ không. Trong `products.py:L229-233`, lệnh đồng bộ vector được bọc trong khối `try...except`. Giao dịch lưu sản phẩm vào SQLite là ưu tiên sống còn và đã hoàn tất (commit) trước. Nếu ChromaDB gặp trục trặc, dữ liệu sản phẩm trong SQL vẫn được bảo đảm toàn vẹn và Admin có thể dùng nút `Đồng bộ lại Vector DB` (`POST /api/v1/ai/sync-index`) để bù đắp sau."

---

### 4. Danh sách 5 thuật ngữ Backend/Database cốt lõi cần học thuộc lòng
1. **Single Source of Truth (Nguồn chân lý duy nhất)**: Nguyên tắc kiến trúc quy định một hệ thống dữ liệu duy nhất (ở đây là SQLite) nắm giữ trạng thái chính xác và có giá trị quyết định cuối cùng về dữ liệu nghiệp vụ.
2. **ACID Transactions**: 4 thuộc tính đảm bảo giao dịch cơ sở dữ liệu tin cậy: Tính nguyên tử (Atomicity), Tính nhất quán (Consistency), Tính cô lập (Isolation), Tính bền vững (Durability).
3. **SQLite WAL (Write-Ahead Logging)**: Cơ chế ghi nhật ký trước giúp SQLite tăng tốc độ ghi và cho phép đọc-ghi đồng thời mà không bị khóa file.
4. **Relational Guardrail**: Chốt chặn nghiệp vụ tại tầng cơ sở dữ liệu quan hệ nhằm thẩm tra và loại bỏ các dữ liệu sai lệch trước khi nạp vào AI.
5. **Upsert (Update or Insert)**: Thao tác thêm mới bản ghi nếu chưa có, hoặc cập nhật nếu bản ghi đã tồn tại (áp dụng khi đồng bộ vector vào ChromaDB).

---

### KỊCH BẢN PHÂN VAI TRÌNH BÀY TRƯỚC HỘI ĐỒNG
- **Kiên (Nhóm trưởng)**: Mở đầu giới thiệu tổng quan kiến trúc hệ thống, sơ đồ 3 Phase RAG, cách nhúng vector `all-MiniLM-L6-v2` và cách tích hợp Google Gemini 3.6 Flash.
- **Đạt**: Tiếp nối phân tích cơ chế lưu trữ SQLite, chứng minh tính toàn vẹn dữ liệu bằng Atomic Transactions và giải thích chốt chặn Guardrail loại bỏ 100% rủi ro tư vấn hàng hết.
- **Hưng**: Demo trực tiếp trên giao diện: thử gõ câu hỏi tìm kiếm trên Web, cho Thầy/Cô xem thẻ sản phẩm đối chiếu, bấm nút "Mở bán POS" để chứng minh sự liền mạch giữa AI và nghiệp vụ bán hàng thực tế.
