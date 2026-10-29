# BÁO CÁO PHÂN TÍCH KIẾN TRÚC HYBRID RELATIONAL RAG & LUỒNG DỮ LIỆU STOREFLOW AI 2.0

> **Dự án**: StoreFlow AI 2.0 — Hệ thống Quản lý Bán hàng & Trợ lý Bán lẻ Thông minh  
> **Môn học**: Ứng dụng Trí tuệ Nhân tạo  
> **Tài liệu tham chiếu mã nguồn**:
> - `backend/app/services/rag_service.py` (Hybrid Retrieval, BM25, RRF, SQLite Truth Guard)
> - `backend/app/services/ai_service.py` (Orchestration & Business Logic)
> - `backend/app/services/ai_providers/` (Pluggable Provider Architecture & Fallback)
> - `backend/app/services/local_vision_service.py` (OpenAI CLIP ViT-B/32 on CPU)
> - `backend/app/services/image_search_service.py` (Multimodal Visual Search & Match Engine)
> - `backend/prompts/*.txt` (Externalized Prompt Engineering Templates)

---

## MỤC LỤC
1. [BẢN CHẤT RAG TRONG STOREFLOW AI: ĐỊNH NGHĨA & SO SÁNH KHÁC BIỆT](#1-bản-chất-rag-trong-storeflow-ai-định-nghĩa--so-sánh-khác-biệt)
2. [MÔ HÌNH NHÚNG (EMBEDDING) & VECTOR DATABASE (CHROMADB)](#2-mô-hình-nhúng-embedding--vector-database-chromadb)
3. [QUY TRÌNH TRUY XUẤT ĐA KÊNH LAI (HYBRID TRI-RETRIEVAL) & THUẬT TOÁN RRF](#3-quy-trình-truy-xuất-đa-kênh-lai-hybrid-tri-retrieval--thuật-toán-rrf)
4. [CHỐT CHẶN CHÂN LÝ HAI LỚP (DOUBLE SQLITE TRUTH GUARD) & BẢO VỆ GIÁ VỐN](#4-chốt-chặn-chân-lý-hai-lớp-double-sqlite-truth-guard--bảo-vệ-giá-vốn)
5. [KIẾN TRÚC PLUGGABLE AI PROVIDERS & NGUYÊN LÝ HOẠT ĐỘNG CHẾ ĐỘ AUTO](#5-kiến-trúc-pluggable-ai-providers--nguyên-lý-hoạt-động-chế-độ-auto)
6. [HỆ THỐNG PROMPT ENGINEERING & CƠ CHẾ CHỐNG RÒ RỈ PROMPT (ANTI-LEAKAGE)](#6-hệ-thống-prompt-engineering--cơ-chế-chống-rò-rỉ-prompt-anti-leakage)
7. [MỞ RỘNG RAG ĐA PHƯƠNG THỨC: TÌM KIẾM HÌNH ẢNH (MULTIMODAL VISUAL RAG)](#7-mở-rộng-rag-đa-phương-thức-tìm-kiếm-hình-ảnh-multimodal-visual-rag)
8. [LUỒNG DỮ LIỆU ĐIỀU HỢP TỔNG THỂ END-TO-END](#8-luồng-dữ-liệu-điều-hợp-tổng-thể-end-to-end)

---

## 1. BẢN CHẤT RAG TRONG STOREFLOW AI: ĐỊNH NGHĨA & SO SÁNH KHÁC BIỆT

### 1.1. Cái nào được coi là RAG trong hệ thống? Phần AI có phải là RAG không?
**KHẲNG ĐỊNH: CÓ! Phân hệ "AI ASSISTANT — 1. TƯ VẤN SẢN PHẨM" và "TÌM KIẾM BẰNG HÌNH ẢNH" của StoreFlow AI là một hệ thống RAG (Retrieval-Augmented Generation) chuẩn mực.**

Theo định nghĩa khoa học, một hệ thống là RAG khi và chỉ khi nó kết hợp giữa:
1. **Retrieval**: Tìm kiếm thông tin liên quan từ kho dữ liệu bên ngoài (External Grounded Data) dựa trên câu hỏi của người dùng.
2. **Augmentation**: Bổ sung thông tin vừa tìm được vào ngữ cảnh (Prompt Context).
3. **Generation**: Đưa toàn bộ ngữ cảnh vào mô hình ngôn ngữ lớn (LLM) để sinh câu trả lời tự nhiên có trích dẫn nguồn thực tế.

Trong StoreFlow AI:
- Khi người dùng hỏi: *"Tư vấn cho tôi chuột không dây pin trâu làm việc văn phòng tầm 300k"*.
- Hệ thống **không bao giờ** để LLM tự bịa câu trả lời từ trí nhớ của nó.
- Hệ thống kích hoạt module truy xuất lai tìm kiếm ứng viên từ ChromaDB và BM25 $\rightarrow$ Đối soát dữ liệu tồn kho sống từ SQLite $\rightarrow$ Nạp sản phẩm khả dụng vào template prompt `{verified_products_context}` $\rightarrow$ Gọi LLM sinh văn bản tư vấn và trả về thẻ sản phẩm (Citation Cards) có thể bấm mở bán POS trực tiếp.

### 1.2. StoreFlow AI KHÁC BIỆT gì so với RAG văn bản thông thường (Naive Text RAG)?

```
[ NAIVE RAG TRUYỀN THỐNG TRÊN VĂN BẢN / PDF ]
Văn bản dài ──► Cắt đoạn tùy tiện (Chunking) ──► Dense Vector Search ──► Nạp thẳng vào LLM ──► Sinh câu trả lời
(Nhược điểm trong bán lẻ: Bị sót từ khóa chính xác, không biết kho hết hàng, ảo giác giá bán, lộ giá vốn)

                                       VS

[ STOREFLOW AI 2.0: HYBRID RELATIONAL RAG ]
Catalog Sản phẩm ──► Entity-based Chunking ──► HYBRID TRI-RETRIEVAL (Dense 384d + BM25 + Structured SQL)
                                                                 │
                                                                 ▼
                                                  Reciprocal Rank Fusion (RRF k=60)
                                                                 │
                                                                 ▼
                                      CHỐT CHẶN L1: SQLite Truth Guard (stock > 0 & Ẩn giá vốn)
                                                                 │
                                                                 ▼
                                      PLUGGABLE LLM (Ollama Local Qwen 2.5 / Gemini / Safe Fallback)
                                                                 │
                                                                 ▼
                                      CHỐT CHẶN L2: Pre-response Check (Đối soát lại giá trước khi gửi)
                                                                 │
                                                                 ▼
                                      Citation Cards + Nút 1-chạm "Mở bán POS"
```

| Tiêu chí | RAG Văn bản Thông thường (Naive RAG) | StoreFlow AI 2.0 (Hybrid Relational RAG) |
| :--- | :--- | :--- |
| **Đơn vị phân mảnh (Chunking)** | Cắt nhỏ văn bản tùy ý theo số ký tự/token (500-1000 tokens) gây đứt gãy thông tin sản phẩm. | **Entity-based Semantic Chunking**: Mỗi sản phẩm là 1 thực thể trọn vẹn (SKU, Tên, Danh mục, Giá niêm yết, Đơn vị tính, Mô tả). |
| **Kỹ thuật Truy xuất** | Chỉ dựa vào Dense Vector Search (dễ bị bỏ sót mã SKU, tên model hoặc thương hiệu đặc thù). | **Hybrid Tri-Retrieval**: Kết hợp 3 luồng: (1) Dense Vector 384d, (2) In-memory BM25, và (3) Structured SQL Filtering. |
| **Hợp nhất Xếp hạng** | Không có (lấy thẳng Top-K từ vector DB). | **Reciprocal Rank Fusion (RRF $k=60$)**: Hợp nhất thứ hạng từ 3 nguồn và tăng cường điểm cho thương hiệu/danh mục khớp. |
| **Kiểm soát Tồn kho Thời gian thực** | **Không có**. Dễ xảy ra thảm họa: AI tư vấn rất nhiệt tình nhưng trong kho thực tế đã **hết hàng**. | **Chốt chặn L1 (Post-retrieval Truth Guard)**: Truy vấn trực tiếp SQLite, loại bỏ 100% sản phẩm có `stock <= 0` hoặc `is_active = 0`. |
| **Bảo vệ Bí mật Kinh doanh** | Đưa toàn bộ metadata vào prompt, dễ bị người dùng bẫy hỏi ra giá nhập hàng. | **Cost Price Protection**: Loại bỏ hoàn toàn giá vốn `cost_price` khỏi cả Vector DB lẫn context gửi sang LLM. |
| **Đối soát Đầu ra (Double Check)** | Tin tưởng hoàn toàn vào văn bản LLM sinh ra. | **Chốt chặn L2 (Pre-response Response Check)**: Đối chiếu lại giá bán trong văn bản LLM với giá niêm yết SQLite trước khi trả về client. |
| **Chịu lỗi & Dự phòng (Fault Tolerance)**| Mất kết nối API / Hết Quota $\rightarrow$ Trả về lỗi hệ thống HTTP 500. | **Safe Grounded Fallback**: Tự động chuyển sang cỗ máy sinh bảng dữ liệu cấu trúc từ SQLite mà không làm gián đoạn người dùng. |
| **Khả năng Đa phương thức** | Đa số chỉ hỗ trợ tìm kiếm bằng câu chữ (Text-only). | **Multimodal Image Search**: Nhúng ảnh qua mô hình **OpenAI CLIP ViT-B/32** chạy trên CPU (512 chiều) và phân loại đối chiếu 3 cấp. |

---

## 2. MÔ HÌNH NHÚNG (EMBEDDING) & VECTOR DATABASE (CHROMADB)

### 2.1. Tên chính xác của mô hình Embedding
- **Trong tầng Text RAG (`rag_service.py`)**: Hệ thống sử dụng mô hình mã nguồn mở tiêu chuẩn **`all-MiniLM-L6-v2`** (chạy qua ONNX Runtime cục bộ của thư viện `chromadb`), tạo ra các vector nhúng **384 chiều** với hàm đo khoảng cách **Cosine** (`metadata={"hnsw:space": "cosine"}`).
- **Trong tầng Multimodal Vision RAG (`local_vision_service.py`)**: Hệ thống sử dụng mô hình thị giác đối chiếu **`openai/clip-vit-base-patch32`** chạy trực tiếp trên CPU (tiêu tốn **0 MB VRAM**), tạo ra không gian vector đặc trưng thị giác **512 chiều chuẩn hóa L2**.

### 2.2. Danh mục 3 Collections độc lập trong ChromaDB
Hệ thống duy trì kết nối bền vững (`chromadb.PersistentClient`) tại thư mục `backend/chroma_data` với 3 bộ sưu tập biệt lập:
1. **`storeflow_products`**: Lưu trữ vector văn bản 384 chiều của toàn bộ sản phẩm catalog. Phục vụ tìm kiếm ngữ nghĩa văn bản cho trợ lý tư vấn bán hàng.
2. **`storeflow_product_visuals`**: Lưu trữ vector mô tả đặc tính thị giác dạng text (màu sắc, kiểu dáng, chất liệu) phục vụ đối soát tương thích metadata.
3. **`storeflow_product_visual_vectors`**: Lưu trữ trực tiếp các vector nhúng ảnh **512 chiều** trích xuất từ CLIP. Phục vụ tìm kiếm sản phẩm bằng hình ảnh đa phương thức (Multimodal Image-to-Product Search).

### 2.3. Cơ chế Tự phục hồi & Đồng bộ Dữ liệu (Lifecycle Sync Hooks)
Dữ liệu giữa SQLite và ChromaDB được tự động đồng bộ tại **3 thời điểm vàng**:
1. **Khi Server FastAPI khởi động (`lifespan` tại `main.py`)**:
   - Tự động kiểm tra số lượng bản ghi: nếu `collection.count() == 0`, tự động quét SQLite và nạp toàn bộ vào ChromaDB.
   - Hàm `auto_heal_if_needed()` tự động phát hiện các bản ghi lệch pha (mồ côi trong ChromaDB hoặc thiếu trong SQLite) để tự sửa chữa.
2. **Khi phát sinh thao tác CRUD Sản phẩm trong SQLite (`products.py`)**:
   - Thêm sản phẩm mới (`POST /products`): Kích hoạt `rag_service.upsert_single_product(new_id)`.
   - Cập nhật sản phẩm (`PUT /products/{id}`): Tự động re-embed và cập nhật vector.
   - Xóa sản phẩm (`DELETE /products/{id}`): Xóa vector nếu hard delete, cập nhật metadata nếu soft delete (`is_active = 0`).
3. **Đồng bộ thủ công qua API Endpoint Quản trị**:
   - `POST /api/v1/ai/sync-index`: Đồng bộ lại toàn bộ sản phẩm vào Text Collection.
   - `POST /api/v1/ai/sync-visuals`: Đồng bộ lại toàn bộ đặc trưng thị giác vào Visual Vector Collection.

---

## 3. QUY TRÌNH TRUY XUẤT ĐA KÊNH LAI (HYBRID TRI-RETRIEVAL) & THUẬT TOÁN RRF

Khi người dùng nhập câu hỏi, hệ thống kích hoạt cơ chế **Hybrid Tri-Retrieval** tại `backend/app/services/rag_service.py:L1680-1790`:

```
                                      [ CÂU HỎI NGƯỜI DÙNG: "chuột văn phòng silent dưới 400k" ]
                                                                 │
                                                                 ▼
                                                  ┌──────────────────────────────┐
                                                  │       INTENT ANALYZER        │
                                                  │ (Bóc tách Ngân sách & Ý định)│
                                                  └──────────────┬───────────────┘
                                                                 │
                                ┌────────────────────────────────┼────────────────────────────────┐
                                │                                │                                │
                                ▼                                ▼                                ▼
                ┌──────────────────────────────┐ ┌──────────────────────────────┐ ┌──────────────────────────────┐
                │ LUỒNG 1: DENSE VECTOR SEARCH │ │ LUỒNG 2: SPARSE LEXICAL BM25 │ │ LUỒNG 3: STRUCTURED SQL     │
                │  ChromaDB (Cosine Similarity)│ │  In-memory BM25 Okapi Ranker │ │  SQLite (Category/Brand Match│
                │  Lấy Top-15 IDs theo ngữ nghĩa│ │  Lấy Top-15 IDs theo từ khóa│ │  Lấy Top-10 IDs theo bộ lọc  │
                └──────────────┬───────────────┘ └──────────────┬───────────────┘ └──────────────┬───────────────┘
                                │                                │                                │
                                └────────────────────────────────┼────────────────────────────────┘
                                                                 │
                                                                 ▼
                                            ┌──────────────────────────────────────────┐
                                            │ RECIPROCAL RANK FUSION (RRF k=60)        │
                                            │ Hợp nhất thứ hạng + Tăng cường trọng số  │
                                            └────────────────────┬─────────────────────┘
                                                                 │
                                                                 ▼
                                            [ DANH SÁCH ỨNG VIÊN ĐÃ XẾP HẠNG TỐI ƯU ]
```

### 3.1. Chi tiết 3 Kênh Truy xuất
1. **Luồng 1 — Dense Vector Retrieval (ChromaDB)**: Chuyển câu hỏi thành vector 384 chiều, tìm kiếm theo khoảng cách Cosine với ngưỡng chặn tối thiểu `distance <= 0.55` để loại trừ các sản phẩm hoàn toàn không liên quan.
2. **Luồng 2 — Sparse Lexical Retrieval (BM25 Okapi)**: Lớp `BM25Retriever` được khởi tạo sẵn trong bộ nhớ RAM từ danh mục SQLite. Tính toán điểm số khớp từ khóa chính xác (mã model, đặc tính công nghệ như "silent", "bluetooth", "công thái học").
3. **Luồng 3 — Structured SQL Retrieval**: Bóc tách thực thể danh mục hoặc khoảng giá từ câu hỏi, thực thi câu lệnh SQL trực tiếp `SELECT id FROM products WHERE status = 'active'` để bổ sung các ứng viên khớp danh mục cứng.

### 3.2. Thuật toán Reciprocal Rank Fusion (RRF)
Hệ thống kết hợp thứ hạng từ 3 nguồn thông qua công thức toán học RRF:

$$RRF\_score(d) = \sum_{s \in \{\text{dense}, \text{sparse}, \text{sql}\}} \frac{w_s}{k + \text{rank}_s(d)}$$

- Tham số làm mượt: $k = 60$ (chuẩn quốc tế giúp cân bằng giữa ứng viên xếp đầu và ứng viên ở giữa danh sách).
- Trọng số các nguồn: $w_{\text{dense}} = 1.0$, $w_{\text{sparse}} = 1.0$, $w_{\text{sql}} = 1.0$.
- **Cơ chế Boost điểm**: Nếu sản phẩm khớp trực tiếp với danh mục được người dùng chỉ định, điểm số được nhân hệ số tăng cường $1.25\times$.

---

## 4. CHỐT CHẶN CHÂN LÝ HAI LỚP (DOUBLE SQLITE TRUTH GUARD) & BẢO VỆ GIÁ VỐN

Khác với các hệ thống RAG thông thường chỉ tìm kiếm rồi gửi thẳng vào LLM, StoreFlow AI áp dụng **Quy trình Chốt chặn Hai lớp nghiêm ngặt (Double SQL Verification)**:

```
[ KẾT QUẢ RRF ] ──► [ CHỐT CHẶN L1: POST-RETRIEVAL ] ──► [ PROMPT TO LLM ] ──► [ CHỐT CHẶN L2: PRE-RESPONSE ] ──► [ FRONTEND UI ]
                     - Kiểm tra stock_quantity > 0                              - Đối soát lại giá bán
                     - Kiểm tra status == 'active'                              - Bổ sung huy hiệu kho sống
                     - Kiểm tra price <= budget                                 - Kiểm tra tính nhất quán
                     - Loại bỏ hoàn toàn cost_price
```

### 4.1. Chốt chặn Lớp 1 (L1 Post-Retrieval Truth Guard)
Nằm trong hàm `get_grounded_recommendation_context()` tại `rag_service.py:L1680-1760`:
- **Nguyên lý Oversampling**: Hệ thống luôn lấy số lượng ứng viên gấp 3 lần nhu cầu (`top_k * 3`, tối thiểu 10) từ kết quả RRF.
- **Truy vấn SQLite tức thời**:
  ```sql
  SELECT p.id, p.sku, p.name, p.category_id, c.name as category_name,
         p.selling_price, p.stock_quantity, p.unit, p.status, p.description
  FROM products p
  LEFT JOIN categories c ON p.category_id = c.id
  WHERE p.id IN (?, ?, ...)
  ```
- **Bộ lọc loại trừ 100%**:
  - Sản phẩm có `stock_quantity <= 0`: Bị loại bỏ ngay lập tức, đưa vào danh sách `out_of_stock_excluded`.
  - Sản phẩm có `status != 'active'`: Bị loại bỏ.
  - Sản phẩm có `selling_price > budget_max`: Bị loại bỏ nếu người dùng có yêu cầu trần ngân sách.
- **Bảo vệ Giá vốn (Cost Price Stripping)**: Trường `cost_price` hoàn toàn bị loại bỏ khỏi câu lệnh `SELECT`, đảm bảo LLM không bao giờ "nhìn thấy" giá nhập hàng của cửa hàng.
- Kết quả thu được: Đúng Top-K sản phẩm thực sự khả dụng trong kho, ghép thành chuỗi văn bản `{verified_products_context}`.

### 4.2. Chốt chặn Lớp 2 (L2 Pre-Response Response Check)
Nằm trong hàm `_audit_and_enforce_response_truth()` tại `rag_service.py:L1860-1920`:
- Sau khi LLM sinh câu trả lời bằng văn bản, chốt chặn L2 sẽ quét lại toàn bộ nội dung câu trả lời.
- Đối chiếu lại giá bán và tên sản phẩm trong câu chữ với dữ liệu gốc của SQLite.
- Nếu LLM tự ý thay đổi giá bán hoặc viết sai thông số kỹ thuật cốt lõi, chốt chặn L2 sẽ tự động ghi đè hoặc đính kèm thẻ sản phẩm chuẩn xác từ SQLite vào trường `suggested_products` gửi về cho giao diện Frontend.

---

## 5. KIẾN TRÚC PLUGGABLE AI PROVIDERS & NGUYÊN LÝ HOẠT ĐỘNG CHẾ ĐỘ AUTO

Hệ thống thiết kế tầng giao tiếp AI theo mẫu thiết kế **Strategy & Orchestration Pattern** thông qua class `AIProviderManager` (`backend/app/services/ai_providers/manager.py`):

```
                                  ┌───────────────────────────────────┐
                                  │         AIProviderManager         │
                                  └─────────────────┬─────────────────┘
                                                    │
                 ┌──────────────────────────────────┼──────────────────────────────────┐
                 │                                  │                                  │
                 ▼                                  ▼                                  ▼
  ┌───────────────────────────────┐  ┌───────────────────────────────┐  ┌───────────────────────────────┐
  │         OllamaProvider        │  │         GeminiProvider        │  │        GroundedProvider       │
  ├───────────────────────────────┤  ├───────────────────────────────┤  ├───────────────────────────────┤
  │ • Qwen 2.5 1.5B (Local GPU/CPU│  │ • Google Gemini 3.6 Flash     │  │ • Deterministic SQL Generator │
  │ • http://localhost:11434      │  │ • google-genai SDK v2.8.0     │  │ • 100% SQLite Grounded Facts  │
  │ • 0đ chi phí, hoàn toàn riêng │  │ • Suy luận đám mây nâng cao   │  │ • Zero-cost, Zero-Quota       │
  │   tư, vận hành ngoại tuyến    │  │ • Cần API Key & Internet      │  │ • Fallback tự động khi mất LLM│
  └───────────────────────────────┘  └───────────────────────────────┘  └───────────────────────────────┘
```

### 5.1. Luồng Quyết định của Chế độ Tự động (`AI_PROVIDER="auto"`)
1. **Kiểm tra 1 (Local First)**: Kiểm tra máy chủ Ollama cục bộ qua phương thức `is_service_running()` và `is_model_installed()`. Nếu Ollama đang chạy tại cổng 11434 và đã tải model `qwen2.5:1.5b` $\rightarrow$ Kích hoạt `OllamaProvider`.
2. **Kiểm tra 2 (Cloud Backup)**: Nếu Ollama tắt hoặc model chưa tải, kiểm tra hàm `is_configured()` của Gemini. Nếu biến `GEMINI_API_KEY` hợp lệ $\rightarrow$ Kích hoạt `GeminiProvider`.
3. **Kiểm tra 3 (Emergency Fallback)**: Nếu cả hai phương án trên đều vắng mặt $\rightarrow$ Tự động kích hoạt `GroundedProvider`.

### 5.2. Cơ chế Tự phục hồi Thông minh (`execute_with_fallback`)
- Khi gọi LLM chính (Ollama hoặc Gemini): Hệ thống giới hạn thời gian chờ (`timeout = 60s`).
- Nếu trong lúc sinh văn bản xảy ra sự cố (đứt cáp quang, Gemini trả mã lỗi 429 Quota Exceeded, hoặc Ollama bị tràn RAM):
  - Khối `try...except` tại `manager.py:L114-118` bắt ngoại lệ ngay lập tức.
  - Ghi log cảnh báo: `Provider generation failed, falling back to Grounded SQLite`.
  - Tự động kích hoạt `fallback_fn` sinh bảng câu trả lời từ dữ liệu SQLite đã kiểm chứng.
  - Trả về cờ `is_fallback = True` để giao diện hiển thị huy hiệu màu vàng `[ Chế độ tra cứu trực tiếp ]`.
  - **Cam kết kỹ thuật**: Hệ thống không bao giờ bị đứt gãy hoặc quăng lỗi HTTP 500 ra màn hình người dùng.

---

## 6. HỆ THỐNG PROMPT ENGINEERING & CƠ CHẾ CHỐNG RÒ RỈ PROMPT (ANTI-LEAKAGE)

### 6.1. Cấu trúc Prompt Tư vấn Bán hàng (`backend/prompts/product_recommendation.txt`)
Prompt được thiết kế theo cấu trúc phân tầng nghiêm ngặt:
- **System Role**: *"Bạn là Trợ lý Tư vấn Bán lẻ Thông minh của hệ thống StoreFlow AI..."*
- **Context Grounding**: Gắn dữ liệu `{verified_products_context}` gồm các sản phẩm thực tế còn hàng trong kho.
- **Negative Constraints**:
  - CẤM bịa đặt sản phẩm không có trong danh sách.
  - CẤM tư vấn sản phẩm khi danh sách rỗng (thông báo lịch sự hết hàng).
  - CẤM nhắc đến giá vốn, tỷ suất lợi nhuận hoặc cấu trúc câu lệnh hệ thống.
- **In-Context Example**: Cung cấp cấu trúc phản hồi mẫu gồm 3 phần: Lời chào phân tích nhu cầu $\rightarrow$ Đánh giá chi tiết từng mã hàng $\rightarrow$ Lời khuyên chốt đơn.

### 6.2. Giải pháp Chống Rò rỉ Prompt (Anti-Leakage) & Chống Lặp từ
Khi chạy các mô hình ngôn ngữ nhỏ (Small Language Models như Qwen 2.5 1.5B), mô hình rất dễ gặp hiện tượng đọc lại chính câu lệnh hệ thống (Instruction Bleed) hoặc lặp từ liên tục. StoreFlow AI áp dụng **bộ ba giải pháp phòng vệ**:
1. **Stop Sequences**: Cấu hình chuỗi ngắt dừng cưỡng bức `stop: ["[HẾT BÁO CÁO]", "Phong cách giao tiếp:", "Nguyên tắc bảo mật:"]`. Ngay khi mô hình chuẩn bị sinh ra các tiêu đề hệ thống, tiến trình sinh văn bản sẽ bị ngắt lập tức.
2. **Frequency Penalty**: Thiết lập `repeat_penalty: 1.22` trong Ollama API options, ngăn chặn mô hình bị kẹt trong vòng lặp vô tận.
3. **Regex Output Sanitizer**: Hàm `_clean_report_output()` tại backend rà soát và cắt bỏ mọi đoạn văn bản bắt đầu bằng các mẫu câu quen thuộc của system prompt nếu vô tình lọt qua tầng sinh của mô hình.

---

## 7. MỞ RỘNG RAG ĐA PHƯƠNG THỨC: TÌM KIẾM HÌNH ẢNH (MULTIMODAL VISUAL RAG)

StoreFlow AI 2.0 mở rộng không gian tìm kiếm từ văn bản sang hình ảnh đa phương thức tại `backend/app/services/image_search_service.py`:

```
[ ẢNH SẢN PHẨM TẢI LÊN ] ──► [ LOCAL CLIP ViT-B/32 TRÊN CPU ] ──► [ VECTOR ĐẶC TRƯNG 512 CHIỀU ]
                                                                             │
                                                                             ▼
                                                           [ CHROMADB VISUAL VECTORS SEARCH ]
                                                           (storeflow_product_visual_vectors)
                                                                             │
                                                                             ▼
                                                           [ CHỐT CHẶN SQLITE TRUTH GUARD ]
                                                           (Bổ sung giá lẻ & tồn kho sống)
                                                                             │
                                                                             ▼
                                                           [ DYNAMIC VISUAL MATCH ENGINE ]
                                                           - Cấp 1: [SẢN PHẨM TƯƠNG TỰ] (>= 0.45)
                                                           - Cấp 2: [CÙNG NHÓM HÀNG]
                                                           - Cấp 3: [SẢN PHẨM LIÊN QUAN] (>= 0.35)
                                                           - Ngoại lệ: [Ảnh ngoài danh mục]
```

### 7.1. Trích xuất Đặc trưng bằng Local CLIP ViT-B/32 (Chạy trên CPU)
- Hệ thống sử dụng mô hình `openai/clip-vit-base-patch32` qua thư viện `transformers` và `torch`.
- **Tối ưu hóa phần cứng**: Mô hình chạy hoàn toàn trên CPU (`device='cpu'`), chiếm dụng **0 MB VRAM** card đồ họa và sinh vector 512 chiều chuẩn hóa trong thời gian 60 - 80ms/ảnh.
- Vector ảnh được so khớp độ tương đồng Cosine trực tiếp với bộ sưu tập `storeflow_product_visual_vectors` trong ChromaDB.

### 7.2. Động cơ Đối chiếu Thị giác Động (Dynamic Visual Match Engine)
Kết quả so khớp được phân cấp thành 3 bậc quan hệ logic kèm lý do đối chiếu tiếng Việt:
1. **`[ SẢN PHẨM TƯƠNG TỰ ]` (SIMILAR / MATCH)**: Cùng loại thiết bị và có điểm tương đồng thị giác cao (Score $\ge 0.45$).
2. **`[ CÙNG NHÓM HÀNG ]` (SAME-CATEGORY)**: Cùng danh mục ngành hàng nhưng khác biệt về màu sắc hoặc kiểu dáng.
3. **`[ SẢN PHẨM LIÊN QUAN ]` (RELATED)**: Khác danh mục trực tiếp nhưng thuộc hệ sinh thái phụ kiện đi kèm (ví dụ: tìm sạc điện thoại $\rightarrow$ gợi ý dock sạc đa năng; Score $\ge 0.35$).

### 7.3. Xử lý Ảnh ngoài Danh mục (Out-of-Domain / Low-Confidence Rejection)
- Khác với các hệ thống thị giác thông thường luôn cố ép mọi ảnh đầu vào thành một sản phẩm có trong kho, StoreFlow AI thiết lập cơ chế nhận diện ranh giới dữ liệu:
- Khi người dùng tải lên ảnh chụp màn hình game (ví dụ: ảnh gameplay Minecraft), ảnh phong cảnh, hoặc điểm số tương đồng $< 0.35$:
  - Hệ thống tự động kích hoạt cờ `is_uncertain = True` hoặc trả về trạng thái từ chối gợi ý.
  - Phản hồi minh bạch cho người dùng: Thông báo ảnh chụp không thuộc bất kỳ nhóm hàng công nghệ nào trong danh mục cửa hàng, tránh việc tư vấn sai lệch gây hiểu lầm.

---

## 8. LUỒNG DỮ LIỆU ĐIỀU HỢP TỔNG THỂ END-TO-END

Quy trình hoàn chỉnh từ lúc người dùng đặt câu hỏi đến khi sản phẩm xuất hiện trên giỏ hàng POS:

1. **Frontend Request**: Người dùng gõ câu hỏi tư vấn tại `AiAssistantPage.jsx`. Giao diện kích hoạt hiệu ứng 3 bước `Retro CRT Loading`, gửi HTTP POST `/api/v1/ai/recommend`.
2. **Security & Rate Limiter Gate**: Lớp `AIRateLimiter` kiểm tra tần suất gọi API theo vai trò (Sliding Window Counter). `InputLengthValidator` kiểm tra độ dài câu hỏi ngăn chặn tấn công từ chối dịch vụ.
3. **Intent Analysis**: `intent_analyzer.py` phân tích ý định, bóc tách ngân sách tối đa và từ khóa trọng tâm.
4. **Hybrid Tri-Retrieval**: `rag_service.py` truy vấn song song: ChromaDB (Dense), BM25 (Sparse) và SQLite (SQL Filtering), sau đó hợp nhất qua thuật toán Reciprocal Rank Fusion (RRF $k=60$).
5. **Chốt chặn L1 (Post-Retrieval)**: Truy vấn tức thời SQLite, loại bỏ 100% sản phẩm có `stock <= 0` hoặc ngưng bán, tước bỏ hoàn toàn giá vốn `cost_price`.
6. **Prompt Assembly**: `PromptLoader` nạp `prompts/product_recommendation.txt` và chèn danh sách sản phẩm khả dụng vào biến `{verified_products_context}`.
7. **Pluggable Generation & Fallback**: `AIProviderManager` điều phối gọi Ollama Local Qwen 2.5 (hoặc Gemini Cloud). Nếu gặp sự cố, tự động chuyển sang `GroundedProvider` sinh bảng dữ liệu từ SQLite.
8. **Chốt chặn L2 & Sanitizer**: Đối soát lại giá bán trong câu trả lời từ SQLite. `OutputSanitizer` lọc sạch các khóa bí mật. Ghi vết giao dịch vào bảng `ai_audit_logs`.
9. **Frontend Actionable Render**: `AiAssistantPage.jsx` hiển thị câu trả lời AI bằng Markdown bên cột trái và hiển thị danh sách thẻ sản phẩm thực tế bên cột phải. Người dùng bấm nút **"Mở bán POS"** để nạp thẳng mã hàng vào quầy thu ngân tức thì!
