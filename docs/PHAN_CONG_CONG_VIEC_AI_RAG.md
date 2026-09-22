# BẢNG PHÂN CÔNG NHIỆM VỤ CHI TIẾT: PHÁT TRIỂN HỆ THỐNG RAG & AI CHATBOT
## DỰ ÁN: STOREFLOW AI — HỆ THỐNG QUẢN LÝ BÁN HÀNG & TRỢ LÝ BÁN LẺ THÔNG MINH

> **Môn học**: Ứng dụng Trí tuệ Nhân tạo (GenAI Software Development)  
> **Tài liệu căn cứ**: `docs/PLAN.md`, `docs/RAG_ARCHITECTURE.md`, `docs/AI_DEFENSE_GUIDE.md`, `YÊU CẦU ĐỀ TÀI.docx`  
> **Phiên bản**: 1.0 — Phân bổ đều khối lượng công việc (Work Breakdown Structure - WBS)  
> **Thành viên nhóm thực hiện**:
> 1. **Ngô Trung Kiên** — Trưởng nhóm / AI & RAG Architect, Prompt Engineer, MLOps
> 2. **Phan Duy Hưng** — Thành viên / Frontend Lead, AI UI/UX Interaction & Client Integration
> 3. **Vũ Đức Đạt** — Thành viên / Backend Lead, Data Architecture, Relational Guardrail & AI Security

---

## MỤC LỤC
1. [TỔNG QUAN HỆ THỐNG AI & KIẾN TRÚC HYBRID RAG TRONG DỰ ÁN](#1-tổng-quan-hệ-thống-ai--kiến-trúc-hybrid-rag-trong-dự-án)
2. [MA TRẬN PHÂN CHIA TRÁCH NHIỆM & CÂN BẰNG KHỐI LƯỢNG CÔNG VIỆC](#2-ma-trận-phân-chia-trách-nhiệm--cân-bằng-khối-lượng-công-việc)
3. [PHẦN 1: NGÔ TRUNG KIÊN — AI ARCHITECTURE, RAG PIPELINE & PROMPT ENGINEERING](#3-phần-1-ngô-trung-kiên--ai-architecture-rag-pipeline--prompt-engineering)
4. [PHẦN 2: PHAN DUY HƯNG — FRONTEND ENGINEERING & AI CHATBOT UI/UX INTEGRATION](#4-phần-2-phan-duy-hưng--frontend-engineering--ai-chatbot-uiux-integration)
5. [PHẦN 3: VŨ ĐỨC ĐẠT — BACKEND API, RELATIONAL GUARDRAIL & AI SECURITY GATEKEEPER](#5-phần-3-vũ-đức-đạt--backend-api-relational-guardrail--ai-security-gatekeeper)
6. [QUY TRÌNH PHỐI HỢP LIÊN THÀNH VIÊN (CROSS-FUNCTIONAL WORKFLOW)](#6-quy-trình-phối-hợp-liên-thành-viên-cross-functional-workflow)
7. [PHÂN BỔ TRÁCH NHIỆM TRONG HỒ SƠ MINH CHỨNG SDLC (KT1 - KT4)](#7-phân-bổ-trách-nhiệm-trong-hồ-sơ-minh-chứng-sdlc-kt1---kt4)
8. [KỊCH BẢN PHỐI HỢP THUYẾT TRÌNH & VẤN ĐÁP TRƯỚC HỘI ĐỒNG BẢO VỆ](#8-kịch-bản-phối-hợp-thuyết-trình--vấn-đáp-trước-hội-đồng-bảo-vệ)

---

## 1. TỔNG QUAN HỆ THỐNG AI & KIẾN TRÚC HYBRID RAG TRONG DỰ ÁN

Hệ thống StoreFlow AI không chỉ là một ứng dụng CRUD bán hàng thông thường, mà tích hợp **Trợ lý AI Bán lẻ Thông minh** sử dụng mô hình **Hybrid Relational RAG (Retrieval-Augmented Generation kết hợp Chốt chặn Cơ sở dữ liệu Quan hệ)**:

```
                  ┌─────────────────────────────────────────────────────────┐
                  │                 NGƯỜI DÙNG / TRÌNH DUYỆT                │
                  │   (Guest / Customer / Staff / Admin / SuperAdmin)       │
                  └────────────────────────────┬────────────────────────────┘
                                               │
                                               ▼
┌───────────────────────────────────────────────────────────────────────────────────────────┐
│ PHAN DUY HƯNG: FRONTEND & AI UI/UX INTERACTION LAYER                                      │
│  - AI Command Center Retro Terminal (AiAssistantPage.jsx)                                │
│  - Dual Theme Adaptation: Retro CRT Dark (#0a0e13) & Vintage Paper Light (#e6cb94)       │
│  - Source Attribution & Product Citation Cards (Ảnh, Tên, Giá, Tồn kho thực tế)           │
│  - Actionable Output: Nút 1-chạm "Mở bán POS" / "Thêm vào giỏ hàng"                      │
│  - Client-side Cooldown Feedback & In-flight Loading Animation (3-Step Indicator)         │
└──────────────────────────────────────────────┬────────────────────────────────────────────┘
                                               │ HTTP POST /api/v1/ai/* (Bearer JWT)
                                               ▼
┌───────────────────────────────────────────────────────────────────────────────────────────┐
│ VŨ ĐỨC ĐẠT: BACKEND API, RELATIONAL GUARDRAIL & SECURITY GATEKEEPER                       │
│  - FastAPI AI Router (ai.py: /recommend, /sales-report, /sales-qa, /logs, /sync-index)    │
│  - In-memory Sliding Window Rate Limiter (rate_limiter.py) chống Spam & Quota Exhaustion │
│  - Dynamic Input Length Validation & Output Sanitizer (bảo vệ Gemini API Key/Secrets)    │
│  - RBAC & Anti-IDOR: Phân vùng dữ liệu cá nhân Khách hàng & Doanh thu SuperAdmin          │
│  - Deterministic SQLite Guardrail: Chốt chặn tồn kho (stock_quantity > 0 AND active)    │
│  - AI Audit Logging (ai_audit_logs) & SQLite Life-cycle Sync Hooks                        │
└──────────────────────────────────────────────┬────────────────────────────────────────────┘
                                               │
                                               ▼
┌───────────────────────────────────────────────────────────────────────────────────────────┐
│ NGÔ TRUNG KIÊN: AI ARCHITECTURE, RAG ENGINE & PROMPT ENGINEERING                          │
│  - ChromaDB Persistent Vector Database (Collection: storeflow_products, Cosine space)     │
│  - Local Embedding Model: all-MiniLM-L6-v2 (384 dimensions qua ONNX Runtime)             │
│  - Entity-based Semantic Chunking & Oversampled Top-K Candidate Retrieval                │
│  - External Prompt Engineering System (backend/prompts/*.txt + PromptLoader)              │
│  - Google Gemini 3.6 Flash Integration (google-genai SDK v2.8.0)                         │
│  - Rule-based Graceful Fallback Engine khi mất mạng hoặc cạn kiệt Quota API               │
│  - MLOps & Benchmark: Grounding rate, Hit rate, Latency, Prompt Iteration V1-V3          │
└───────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. MA TRẬN PHÂN CHIA TRÁCH NHIỆM & CÂN BẰNG KHỐI LƯỢNG CÔNG VIỆC

Để bảo đảm tính công bằng, minh bạch và đáp ứng trọn vẹn tiêu chí đánh giá của môn học, khối lượng công việc được chia đều 33.3% cho mỗi thành viên dựa trên chuyên môn chính:

| Tiêu chí | Ngô Trung Kiên (AI / RAG / MLOps) | Phan Duy Hưng (Frontend Lead) | Vũ Đức Đạt (Backend Lead) |
| :--- | :--- | :--- | :--- |
| **Trọng tâm chuyên môn** | AI Core, Vector DB, Prompting, LLM, MLOps Benchmark | Giao diện Chatbot, UI/UX, Citation Card, Dual Theme, Actionable AI | API Controllers, SQLite Database, Security, Guardrail, Rate Limiting |
| **Phạm vi mã nguồn** | `backend/app/services/rag_service.py`<br>`backend/app/services/ai_service.py`<br>`backend/app/core/prompt_loader.py`<br>`backend/prompts/*.txt`<br>`backend/chroma_data/` | `frontend/src/pages/AiAssistantPage.jsx`<br>`frontend/src/services/api.js`<br>`frontend/src/context/ThemeContext.jsx`<br>`frontend/src/index.css`<br>`frontend/src/components/ui/Badge.jsx` | `backend/app/api/v1/ai.py`<br>`backend/app/core/rate_limiter.py`<br>`backend/app/core/rbac.py`<br>`backend/app/models/schema.py`<br>`backend/tests/test_ai_*.py` |
| **Tỷ trọng khối lượng** | **33.3%** | **33.3%** | **33.3%** |
| **Minh chứng SDLC** | Chịu trách nhiệm chính **KT3** (Tối ưu Prompt) & Tham gia KT1/KT4 | Chịu trách nhiệm chính **KT1** (Wireframe AI, UX) & **KT4** (Demo UI) | Chịu trách nhiệm chính **KT2** (API, DB, Guardrail) & **KT4** (Security) |

---

## 3. PHẦN 1: NGÔ TRUNG KIÊN — AI ARCHITECTURE, RAG PIPELINE & PROMPT ENGINEERING

### 3.1. Mục tiêu & Trách nhiệm cốt lõi
1. Thiết kế và làm chủ toàn bộ tầng **Retrieval-Augmented Generation (RAG)** của hệ thống StoreFlow AI.
2. Xây dựng và quản trị Vector Database **ChromaDB**, lựa chọn mô hình Embedding cục bộ tốc độ cao (`all-MiniLM-L6-v2`), đảm bảo độ trễ truy xuất vector < 20ms.
3. Thiết kế chiến lược **Entity-based Semantic Chunking** cho dữ liệu hàng hóa bán lẻ, tối ưu kỹ thuật **Oversampling Top-K** để phối hợp với bộ lọc Relational Guardrail.
4. Tách biệt 100% logic code và khuôn mẫu câu lệnh thông qua hệ thống **External Prompts (`backend/prompts/*.txt`)** và engine nạp an toàn `PromptLoader`.
5. Tích hợp trực tiếp với mô hình ngôn ngữ lớn **Google Gemini (`gemini-3.6-flash`)** qua thư viện chính thức `google-genai`.
6. Xây dựng cơ chế **Rule-based Graceful Fallback Engine** giúp hệ thống tự động sinh phản hồi từ dữ liệu đã xác thực khi LLM offline hoặc lỗi quota.
7. Đo lường, đánh giá định lượng hiệu năng RAG (Grounding Rate, Hit Rate, Response Latency) và lập hồ sơ tối ưu hóa Prompt qua 3 phiên bản (V1, V2, V3) cho bài kiểm tra KT3.

---

### 3.2. Bảng phân rã công việc chi tiết (Work Breakdown Structure)

| Mã Task | Hạng mục công việc chi tiết | File / Thư mục phụ trách | Kết quả bàn giao (Deliverable) |
| :--- | :--- | :--- | :--- |
| **KIEN-01** | **Khởi tạo & Cấu hình Persistent ChromaDB**<br>- Thiết lập `chromadb.PersistentClient` tại đường dẫn `backend/chroma_data`.<br>- Khởi tạo collection cố định `storeflow_products` với không gian cosine (`{"hnsw:space": "cosine"}`).<br>- Cấu hình mô hình embedding mặc định `all-MiniLM-L6-v2` chạy qua ONNX Runtime cục bộ (384 chiều, zero-cost, không cần API key ngoài). | `backend/app/services/rag_service.py` | Collection ChromaDB hoạt động ổn định, lưu trữ vector bền vững trên ổ đĩa. |
| **KIEN-02** | **Xây dựng Entity-based Semantic Chunking cho Hàng hóa**<br>- Hiện thực hàm `_build_product_document(p)`: ghép chuẩn hóa SKU, Tên, Danh mục, Giá bán định dạng VNĐ, Đơn vị tính và Mô tả chi tiết.<br>- Tránh cắt vụn văn bản (arbitrary chunking) làm mất ngữ cảnh bán lẻ.<br>- Thiết lập metadata đi kèm mỗi vector: `product_id`, `sku`, `category_id`, `category_name`, `selling_price`. | `backend/app/services/rag_service.py` | Mỗi sản phẩm được vector hóa thành 1 đơn vị ngữ nghĩa hoàn chỉnh. |
| **KIEN-03** | **Hiện thực Semantic Search & Thuật toán Oversampling Top-K**<br>- Hiện thực hàm `search_candidates(query, top_k)` sử dụng HNSW Cosine Distance.<br>- Thiết lập cơ chế **Oversampling**: Lấy tập ứng viên mở rộng `max(top_k * 3, 10)` (ví dụ: cần 5 thì lấy 15 ứng viên) để bù đắp cho các sản phẩm đã hết hàng trong kho bị bộ lọc SQLite loại bỏ.<br>- Duy trì thứ hạng tương đồng ngữ nghĩa (Semantic Ranking Order). | `backend/app/services/rag_service.py` | Trả về Top-K ứng viên có độ tương đồng ngữ nghĩa cao nhất, không bị thiếu hụt sau khi lọc tồn kho. |
| **KIEN-04** | **Kiến trúc Tách biệt Prompt (Prompt Engine)**<br>- Xây dựng class `PromptLoader` tại `backend/app/core/prompt_loader.py` tự động scan, nạp, cache và định dạng chuỗi an toàn (`safe_substitute`).<br>- Xây dựng 4 file khuôn mẫu độc lập trong thư mục `backend/prompts/`:<br>  + `system_prompt.txt`: Định hình nhân dạng trợ lý bán hàng StoreFlow, phong cách lịch sự, cấm bịa đặt.<br>  + `product_recommendation.txt`: Khuôn mẫu tư vấn bán hàng RAG gắn ngữ cảnh `{verified_products_context}`, `{user_query}`, `{budget_info}`.<br>  + `sales_report.txt`: Khuôn mẫu phân tích doanh thu chiến lược từ số liệu SQL.<br>  + `sales_qa.txt`: Khuôn mẫu trợ lý hỏi đáp vận hành cửa hàng. | `backend/app/core/prompt_loader.py`<br>`backend/prompts/` | Tách rời 100% prompt khỏi mã nguồn Python, dễ dàng chỉnh sửa và làm minh chứng so sánh. |
| **KIEN-05** | **Tích hợp Google Gemini 3.6 Flash & Exception Handling**<br>- Kết nối Google Gemini qua SDK `google.genai` v2.8.0 sử dụng model `gemini-3.6-flash`.<br>- Xây dựng hàm `_call_gemini(prompt)` nạp `system_prompt.txt` vào `system_instruction` của client.<br>- Bắt các ngoại lệ: mạng chập chờn, API timeout, HTTP 429 Quota Exceeded. | `backend/app/services/ai_service.py` | Lời gọi LLM ổn định, bảo mật API Key, phản hồi mượt mà trong 1-2 giây. |
| **KIEN-06** | **Xây dựng Rule-based Graceful Fallback Engine**<br>- Thiết kế cơ chế tự động chuyển sang chế độ dự phòng nếu Gemini gặp sự cố: đánh dấu cờ `is_fallback = True`.<br>- Tự động bóc tách danh sách sản phẩm đã xác thực từ SQLite và sinh câu trả lời cấu trúc trực quan cho người dùng mà không quăng lỗi HTTP 500.<br>- Xây dựng fallback tìm kiếm từ khóa SQL LIKE (`_fallback_sqlite_search`) khi ChromaDB rỗng. | `backend/app/services/ai_service.py`<br>`backend/app/services/rag_service.py` | Ứng dụng không bao giờ bị đứt gãy trải nghiệm người dùng kể cả khi LLM Cloud offline. |
| **KIEN-07** | **Đo lường Benchmark RAG & Hồ sơ Tối ưu Prompt (Minh chứng KT3)**<br>- Thiết lập bảng so sánh hiệu năng Prompt qua **3 phiên bản (V1, V2, V3)**:<br>  + *V1 (Naïve Prompt)*: Không quy định chặt chẽ, tỷ lệ ảo giác giá/kho 28%.<br>  + *V2 (Structured Prompt)*: Bổ sung chỉ thị loại trừ hàng hết kho, tỷ lệ ảo giác giảm xuống 6%.<br>  + *V3 (Few-shot & Grounded Guardrail)*: Ép buộc chỉ trích xuất từ `{verified_products_context}`, tỷ lệ ảo giác 0%, độ chính xác định dạng 100%.<br>- Thu thập độ trễ trung bình: Embedding ~15ms, ChromaDB retrieval ~12ms, Gemini LLM ~1.2s. | `docs/ai-usage/KT3_PromptOptimization.md`<br>`docs/RAG_ARCHITECTURE.md` | Báo cáo định lượng chuyên sâu phục vụ chấm điểm tối đa bài KT3 môn AI. |

---

## 4. PHẦN 2: PHAN DUY HƯNG — FRONTEND ENGINEERING & AI CHATBOT UI/UX INTEGRATION

### 4.1. Mục tiêu & Trách nhiệm cốt lõi
1. Xây dựng trung tâm điều khiển AI chuyên nghiệp **AI Command Center (`AiAssistantPage.jsx`)** phong cách Retro-Futuristic Terminal với 4 tab nghiệp vụ.
2. Thiết kế giao diện phản hồi 2 cột chuẩn thương mại điện tử: **Source Attribution & Product Citation Cards** (cột trái: lời khuyên AI; cột phải: thẻ sản phẩm tương tác thực tế).
3. Hiện thực tính năng **Actionable AI Output**: Tích hợp nút 1-chạm *"Mở bán POS"* hoặc *"Thêm vào giỏ hàng"*, biến lời tư vấn AI thành đơn hàng thực tế ngay lập tức.
4. Tích hợp trải nghiệm AI công khai cho **Khách vãng lai (Guest)** và **Khách mua hàng (Customer)** trên giao diện Public Storefront, đảm bảo không bắt ép đăng nhập trái quy trình.
5. Triển khai các trạng thái tương tác mượt mà: **Retro CRT 3-Step Loading Animation**, hiển thị badge minh bạch dữ liệu (`Gemini Grounded` vs `Chế độ tra cứu trực tiếp`), Client-side Cooldown Timer và Toast Notifications.
6. Đảm bảo toàn bộ thành phần UI của Chatbot thích ứng hoàn hảo với **Dual Theme System** (Dark CRT Slate và Light Vintage Paper `#e6cb94`), responsive mượt mà trên Desktop, Tablet và Mobile.

---

### 4.2. Bảng phân rã công việc chi tiết (Work Breakdown Structure)

| Mã Task | Hạng mục công việc chi tiết | File / Thư mục phụ trách | Kết quả bàn giao (Deliverable) |
| :--- | :--- | :--- | :--- |
| **HUNG-01** | **Xây dựng Giao diện AI Command Center 4 Tab**<br>- Hiện thực trang `frontend/src/pages/AiAssistantPage.jsx` theo phong cách Retro Terminal.<br>- Tab 1: Tư vấn mua hàng thông minh theo nhu cầu & ngân sách.<br>- Tab 2: Phân tích báo cáo kinh doanh & đề xuất nhập hàng.<br>- Tab 3: Khung chat hỏi đáp quản trị cửa hàng tương tác 2 chiều.<br>- Tab 4: Bảng theo dõi lịch sử kiểm toán AI (Audit Logs viewer). | `frontend/src/pages/AiAssistantPage.jsx` | Màn hình AI Assistant toàn diện, hiển thị trực quan, chuyển tab không giật lag. |
| **HUNG-02** | **Hiện thực Layout Phân tích 2 Cột (Source Attribution UI)**<br>- Thiết kế layout tỉ lệ 6:4 (`1.4fr : 1fr`):<br>  + **Cột trái (AI Narrative)**: Render Markdown giải thích lý do gợi ý sản phẩm, phân tích ưu nhược điểm dựa trên nhu cầu của khách.<br>  + **Cột phải (Citation Cards)**: Danh sách thẻ sản phẩm thực tế chứa ảnh thumbnail, SKU, tên, danh mục, giá bán nổi bật và badge tồn kho khả dụng.<br>- Thể hiện tính minh bạch: Hiển thị badge xanh `Gemini 3.6 Flash Grounded` hoặc badge vàng `Chế độ tra cứu trực tiếp` dựa vào biến `is_fallback`. | `frontend/src/pages/AiAssistantPage.jsx`<br>`frontend/src/components/ui/Badge.jsx` | Người dùng vừa đọc được lời khuyên tự nhiên, vừa kiểm chứng được nguồn gốc sản phẩm thực tế. |
| **HUNG-03** | **Actionable AI Output: Nối liền AI với POS Bán hàng**<br>- Gắn nút hành động **"Mở bán POS"** (`onNavigate('pos')`) trên từng thẻ sản phẩm AI gợi ý.<br>- Khi nhân viên click, tự động chuyển sang tab POS, tìm kiếm hoặc nạp sẵn mã SKU vào giỏ hàng thu ngân.<br>- Đối với giao diện Customer: hỗ trợ nút "Thêm vào giỏ" để đặt hàng trực tiếp. | `frontend/src/pages/AiAssistantPage.jsx`<br>`frontend/src/pages/PosPage.jsx` | Xóa bỏ rào cản thao tác: Nhân viên không phải nhớ hoặc gõ lại mã SKU sau khi nhờ AI tư vấn. |
| **HUNG-04** | **Tích hợp Public AI Chatbot cho Guest & Customer**<br>- Cho phép Khách vãng lai (Guest) mở khung chat tư vấn ngay tại Public Storefront mà không cần tài khoản.<br>- Không bị chuyển hướng sai sang trang Login khi gửi tin nhắn tư vấn.<br>- Tích hợp cụm câu hỏi gợi ý nhanh 1-chạm (`quickRecQueries`: *"Tư vấn bàn phím cơ gõ êm văn phòng"*, *"Tai nghe bluetooth pin trâu dưới 500k"*...). | `frontend/src/pages/AiAssistantPage.jsx`<br>`frontend/src/pages/PosPage.jsx` | Tăng tỷ lệ chuyển đổi khách hàng tiềm năng ngay từ lần đầu truy cập web. |
| **HUNG-05** | **Xử lý State, Retro Loading Indicator & Cooldown Feedback**<br>- Thiết kế trạng thái tải dạng **3-Step Retro Indicator**: *1. Semantic Search ChromaDB ➔ 2. SQLite Stock Guard ➔ 3. Gemini Generation* với hiệu ứng xoay icon CRT hoài cổ.<br>- Vô hiệu hóa nút gửi (`disabled`) khi đang xử lý để chống double click.<br>- Hiển thị đếm ngược thời gian chờ (Cooldown Timer) và Toast cảnh báo khi chạm giới hạn Rate Limit (HTTP 429). | `frontend/src/pages/AiAssistantPage.jsx`<br>`frontend/src/services/api.js` | Trải nghiệm người dùng chân thực, không có cảm giác màn hình bị đơ trong 1-2s chờ LLM. |
| **HUNG-06** | **Tối ưu Thẩm mỹ Dual Theme & Responsive Đa Thiết Bị**<br>- Tích hợp biến CSS đồng bộ với `ThemeContext`: Tương thích hoàn hảo cả trên Dark CRT Slate (`#0a0e13`) và Light Vintage Paper (`#e6cb94`).<br>- Đảm bảo không bị hardcode mã màu, chữ in sepia sắc nét, chống mỏi mắt.<br>- Responsive toàn diện trên mọi kích thước màn hình (Mobile 375px/430px, Tablet 768px, Desktop 1920px), không bị tràn ngang (`overflow-x: hidden`). | `frontend/src/index.css`<br>`frontend/src/pages/AiAssistantPage.jsx` | Đạt chuẩn thiết kế thẩm mỹ cao (Wow factor), sang trọng và nhất quán phong cách Retro. |
| **HUNG-07** | **Đóng gói API Client & Hồ sơ Giao diện AI (Minh chứng KT1, KT4)**<br>- Xây dựng module `aiAPI` trong `frontend/src/services/api.js`: bao gồm `recommend`, `generateSalesReport`, `salesQA`, `getAuditLogs`, `syncIndex`.<br>- Tự động gắn kèm Header JWT Bearer token và xử lý lỗi mạng tập trung.<br>- Chụp ảnh màn hình các luồng tư vấn AI, lập kịch bản thao tác mượt mà cho bài KT4 và slide thuyết trình. | `frontend/src/services/api.js`<br>`docs/ai-usage/KT1_PhanTich_ThietKe.md`<br>`docs/ai-usage/KT4_BaoCaoCuoiKy.md` | Hoàn thiện tài liệu thiết kế giao diện UI/UX và kịch bản demo sản phẩm thực tế. |

---

## 5. PHẦN 3: VŨ ĐỨC ĐẠT — BACKEND API, RELATIONAL GUARDRAIL & AI SECURITY GATEKEEPER

### 5.1. Mục tiêu & Trách nhiệm cốt lõi
1. Xây dựng toàn bộ hệ thống API Controller cho AI trên nền tảng **FastAPI + Pydantic v2** (`backend/app/api/v1/ai.py`).
2. Hiện thực trái tim của kiến trúc RAG bán lẻ: **Deterministic SQLite Relational Guardrail (`get_grounded_recommendation_context`)**, đóng vai trò Single Source of Truth kiểm tra tức thời `stock_quantity > 0` và `status = 'active'`.
3. Xây dựng cơ chế **Đồng bộ hóa dữ liệu thời gian thực giữa SQLite và ChromaDB (Life-cycle Sync Hooks)**: tự động upsert/delete vector khi thực hiện CRUD sản phẩm và cung cấp API ép đồng bộ thủ công (`/sync-index`).
4. Thiết lập hệ thống bảo vệ an ninh đa tầng cho AI: **In-memory Sliding Window Rate Limiter** chống spam/cạn kiệt quota, **Dynamic Input Length Validator** và **Output Sanitizer** tự động bóc tách che giấu API keys/secrets.
5. Enforce phân quyền **RBAC 5 cấp bậc & Chống rò rỉ dữ liệu chéo (Anti-IDOR)**: Khách hàng chỉ được hỏi dữ liệu đơn hàng của chính mình; Admin không được xem báo cáo doanh thu tối mật của SuperAdmin.
6. Thiết kế bảng CSDL kiểm toán **`ai_audit_logs`**, ghi nhận vết thời gian xử lý (latency ms), người truy vấn và nội dung hỏi đáp. Viết trọn vẹn bộ kiểm thử tự động Pytest bao phủ 100% các kịch bản AI.

---

### 5.2. Bảng phân rã công việc chi tiết (Work Breakdown Structure)

| Mã Task | Hạng mục công việc chi tiết | File / Thư mục phụ trách | Kết quả bàn giao (Deliverable) |
| :--- | :--- | :--- | :--- |
| **DAT-01** | **Xây dựng Chốt chặn Cơ sở dữ liệu (SQLite Relational Guardrail)**<br>- Hiện thực logic chốt chặn tại `backend/app/services/rag_service.py:L161-243`.<br>- Tiếp nhận danh sách Candidate IDs từ ChromaDB, thực thi truy vấn SQLite tức thời: kiểm tra điều kiện nghiêm ngặt `status = 'active' AND stock_quantity > 0` và `selling_price <= budget_max`.<br>- **Single Source of Truth**: Loại bỏ 100% nguy cơ tư vấn sản phẩm đã hết hàng hoặc đã ngừng kinh doanh, kể cả khi vector DB chưa kịp re-index. | `backend/app/services/rag_service.py`<br>`backend/app/core/database.py` | Ngăn chặn triệt để hiện tượng Hallucination về tồn kho và giá bán trong thương mại điện tử. |
| **DAT-02** | **Xây dựng Cơ chế Tự động Đồng bộ SQLite <-> ChromaDB**<br>- Gắn hooks đồng bộ tự động vào API CRUD sản phẩm (`backend/app/api/v1/products.py`):<br>  + Khi tạo mới (`POST /products`): gọi `rag_service.upsert_single_product(new_id)`.<br>  + Khi cập nhật (`PUT /products/{id}`): tự động re-embed và cập nhật vector tương ứng.<br>  + Khi xóa sản phẩm (`DELETE /products/{id}`): xóa vector nếu hard delete, cập nhật metadata nếu soft delete.<br>- Tích hợp hook tự động kiểm tra và sync toàn bộ vào `lifespan` startup của FastAPI.<br>- Xây dựng API `POST /api/v1/ai/sync-index` cho phép Admin ép nạp lại toàn bộ chỉ mục. | `backend/app/api/v1/products.py`<br>`backend/app/api/v1/ai.py`<br>`backend/app/main.py` | Dữ liệu tìm kiếm ngữ nghĩa luôn được phản ánh kịp thời với dữ liệu kho thực tế. |
| **DAT-03** | **Xây dựng Bộ Endpoints FastAPI cho AI Assistant**<br>- Khởi tạo Router `/api/v1/ai` với đầy đủ Pydantic Request/Response models:<br>  + `POST /api/v1/ai/recommend`: Tư vấn sản phẩm, hỗ trợ cả Guest, Customer và Staff.<br>  + `POST /api/v1/ai/sales-report`: Báo cáo doanh thu tài chính dựa trên SQL aggregation (`SUM`, `COUNT`), độc quyền SuperAdmin.<br>  + `POST /api/v1/ai/sales-qa`: Hỏi đáp quản trị hệ thống, tự động phân luồng dữ liệu theo quyền của user.<br>  + `GET /api/v1/ai/logs`: Xem nhật ký kiểm toán AI (Admin & SuperAdmin). | `backend/app/api/v1/ai.py`<br>`backend/app/schemas/ai.py` | Hệ thống API chuẩn RESTful, có Swagger UI đầy đủ, validate dữ liệu đầu vào chặt chẽ. |
| **DAT-04** | **Phân quyền RBAC AI & Chống IDOR Dữ liệu Khách hàng**<br>- Enforce phân quyền thứ bậc: `SuperAdmin > Admin > Staff > Customer > Guest`.<br>- Chặn 403 Forbidden đối với Admin và Staff khi cố tình gọi API báo cáo doanh thu `/sales-report`.<br>- **Chống IDOR trong AI Customer Q&A**: Khi Customer hỏi về đơn hàng của mình, backend tự động trích xuất danh tính qua JWT Token (`current_user["id"]` $\rightarrow$ `customer_id`), chỉ truy vấn các hóa đơn thuộc sở hữu của chính khách hàng đó; tuyệt đối không để LLM đọc dữ liệu đơn hàng của người khác. | `backend/app/api/v1/ai.py`<br>`backend/app/core/rbac.py`<br>`backend/app/services/ai_service.py` | Bảo vệ an toàn tuyệt đối thông tin kinh doanh nhạy cảm và dữ liệu cá nhân của người dùng. |
| **DAT-05** | **Xây dựng Bộ Rate Limiter In-Memory & Chống Tấn công DoS**<br>- Xây dựng class `AIRateLimiter` tại `backend/app/core/rate_limiter.py` dựa trên thuật toán Sliding Window Counter và Cooldown Interval:<br>  + *Guest*: 10 req/phút, thời gian nghỉ tối thiểu giữa 2 lần bấm là 1.5s.<br>  + *Customer*: 25 req/phút, cooldown 0.5s.<br>  + *Staff*: 40 req/phút; *Admin*: 60 req/phút; *SuperAdmin*: 120 req/phút.<br>- Trả về mã lỗi chuẩn **HTTP 429 Too Many Requests** kèm header `Retry-After`.<br>- Tách biệt hoàn toàn: Việc rate limit AI không làm ảnh hưởng đến tốc độ duyệt hàng trên Public Storefront. | `backend/app/core/rate_limiter.py` | Ngăn chặn nguy cơ bị spam làm cạn kiệt Quota Google Gemini API và làm chậm server. |
| **DAT-06** | **Kiểm duyệt Đầu vào (Validator) & Làm sạch Đầu ra (Sanitizer)**<br>- **Input Length Validation**: Giới hạn độ dài câu hỏi linh hoạt theo vai trò (Guest tối đa 500 ký tự, SuperAdmin tối đa 4000 ký tự), phát hiện và trả về HTTP 400 Bad Request nếu người dùng spam payload khổng lồ.<br>- **Output Sanitizer**: Quét toàn bộ văn bản sinh ra từ LLM trước khi gửi về Frontend, tự động phát hiện và che giấu (redact) nếu vô tình lộ các chuỗi nhạy cảm: `AIzaSy...` (Gemini API Key), JWT Token Secret, Password băm Bcrypt. | `backend/app/core/rate_limiter.py`<br>`backend/app/services/ai_service.py` | Loại bỏ nguy cơ rò rỉ thông tin bảo mật hệ thống qua kênh sinh ngôn ngữ của AI. |
| **DAT-07** | **Lưu vết Kiểm toán AI & Bộ Kiểm thử Tự động (Minh chứng KT2, KT4)**<br>- Khởi tạo và duy trì bảng SQLite `ai_audit_logs` (`id`, `user_id`, `feature`, `query_text`, `response_summary`, `latency_ms`, `created_at`).<br>- Viết trọn vẹn các bộ test tự động với Pytest: `test_ai_foundation.py`, `test_ai_rag.py`, `test_phase9a_access_control.py`, `test_phase9b_security_ratelimit.py`.<br>- Kiểm chứng 100% test case pass: xác thực token, kiểm tra tồn kho bằng 0 bị loại bỏ, test rate limit 429, test chặn quyền 403. | `backend/tests/`<br>`backend/app/models/schema.py`<br>`docs/ai-usage/KT2_LapTrinh_CRUD.md` | Đảm bảo tính ổn định vững chắc cho backend và cung cấp minh chứng kỹ thuật cho KT2/KT4. |

---

## 6. QUY TRÌNH PHỐI HỢP LIÊN THÀNH VIÊN (CROSS-FUNCTIONAL WORKFLOW)

Quá trình vận hành tính năng AI được kết nối chặt chẽ giữa 3 thành viên qua 5 bước tiêu chuẩn:

```
[Bước 1: Tương tác Khách hàng]
Phan Duy Hưng (Frontend):
- Người dùng gõ câu hỏi tìm kiếm trên AiAssistantPage.jsx hoặc Storefront.
- Client kiểm tra độ dài cơ bản, bật state loading 3 bước xoay icon CRT.
- Gửi HTTP POST /api/v1/ai/recommend (kèm header Authorization nếu đã đăng nhập).

                              │
                              ▼
[Bước 2: Kiểm duyệt & Chốt chặn Bảo mật]
Vũ Đức Đạt (Backend Security & Rate Limiter):
- Kiểm tra Rate Limit theo role (Guest: 10 req/min, Customer: 25 req/min). Nếu vượt ngưỡng -> HTTP 429.
- Kiểm tra độ dài câu hỏi theo role (Input Validator). Nếu vượt ngưỡng -> HTTP 400.
- Xác định danh tính người gọi (Guest hay Authenticated User).

                              │
                              ▼
[Bước 3: Truy xuất Ngữ nghĩa & Lọc tồn kho Relational Guardrail]
Ngô Trung Kiên (AI Vector) & Vũ Đức Đạt (Backend Database):
- KIÊN: rag_service.search_candidates(query, top_k=15) truy vấn ChromaDB lấy Top-15 IDs tiềm năng.
- ĐẠT: rag_service.get_grounded_recommendation_context() truy vấn SQLite bảng products:
  LỌC BẮT BUỘC: status = 'active' AND stock_quantity > 0 AND price <= budget.
- KIÊN: Lấy đúng Top-5 sản phẩm khả dụng thực tế, ghép chuỗi ngữ cảnh {verified_products_context}.

                              │
                              ▼
[Bước 4: Định dạng Prompt & Tạo sinh LLM]
Ngô Trung Kiên (Prompt & Gemini):
- Nạp template prompts/product_recommendation.txt qua PromptLoader.
- Gửi prompt hoàn chỉnh sang Google Gemini 3.6 Flash.
- Nếu LLM gặp lỗi mạng/quota: Tự động kích hoạt Rule-based Fallback từ dữ liệu SQL đã xác minh.
- ĐẠT: Output Sanitizer rà soát loại bỏ API Key/Secret, ghi log vào bảng ai_audit_logs.

                              │
                              ▼
[Bước 5: Hiển thị Trực quan & Hành động Bán hàng]
Phan Duy Hưng (Frontend UX):
- Tắt hiệu ứng loading, hiển thị lời khuyên AI bên cột trái (Markdown format).
- Hiển thị danh sách thẻ sản phẩm thực tế bên cột phải kèm giá tiền, ảnh và tồn kho khả dụng.
- Người dùng bấm nút "Mở bán POS" / "Thêm vào giỏ": Chuyển đơn hàng vào quầy thanh toán ngay lập tức!
```

---

## 7. PHÂN BỔ TRÁCH NHIỆM TRONG HỒ SƠ MINH CHỨNG SDLC (KT1 - KT4)

Theo yêu cầu môn học, nhóm phải nộp đầy đủ nhật ký ứng dụng AI qua 4 giai đoạn phát triển phần mềm tại thư mục `docs/ai-usage/`. Phân bổ cụ thể:

| Giai đoạn | Nội dung tài liệu | Phụ trách chính | Nhiệm vụ cụ thể của từng người |
| :--- | :--- | :---: | :--- |
| **KT1: Phân tích & Thiết kế** | `docs/ai-usage/KT1_PhanTich_ThietKe.md` | **Phan Duy Hưng** | - **Hưng**: Thiết kế Wireframe UI AI Command Center, sơ đồ trải nghiệm người dùng (Activity & Sequence Diagram Use Case AI Tư vấn & Hỏi đáp).<br>- **Kiên**: Thiết kế kiến trúc tổng thể Hybrid RAG, cấu trúc Vector ChromaDB.<br>- **Đạt**: Thiết kế lược đồ CSDL 10 bảng (ERD) và bảng kiểm toán `ai_audit_logs`. |
| **KT2: Lập trình & CRUD** | `docs/ai-usage/KT2_LapTrinh_CRUD.md` | **Vũ Đức Đạt** | - **Đạt**: Nhật ký prompt AI sinh mã nguồn FastAPI, SQLite Atomic Transactions (`BEGIN IMMEDIATE`), Relational Guardrail và Rate Limiter.<br>- **Kiên**: Prompt sinh cấu hình ChromaDB, ONNX runtime embedding và prompt loader.<br>- **Hưng**: Prompt sinh React components, Tailwind/Vanilla CSS tokens và API client. |
| **KT3: Tối ưu Prompt RAG** | `docs/ai-usage/KT3_PromptOptimization.md` | **Ngô Trung Kiên** | - **Kiên**: **Trách nhiệm cốt lõi bài KT3**: Xây dựng bộ hồ sơ so sánh Prompt qua 3 phiên bản (V1, V2, V3), lập bảng ma trận đánh giá tỷ lệ Grounding (chính xác), tỷ lệ loại bỏ hàng hết tồn kho, đo lường độ trễ (latency) và kiểm soát Hallucination.<br>- **Đạt**: Cung cấp dữ liệu đối soát tồn kho SQLite thực tế.<br>- **Hưng**: Chụp ảnh so sánh kết quả hiển thị trên UI giữa các phiên bản Prompt. |
| **KT4: Review, Security & Báo cáo** | `docs/ai-usage/KT4_BaoCaoCuoiKy.md` | **Toàn nhóm**<br>*(Đạt chủ trì)* | - **Đạt**: Báo cáo kiểm thử bảo mật API Key, kiểm thử phân quyền RBAC 5 cấp, chống IDOR và test phòng chống spam Rate Limit.<br>- **Kiên**: Báo cáo tổng kết kiến trúc AI, cơ chế Graceful Fallback khi offline và định hướng mở rộng mô hình đa ngôn ngữ.<br>- **Hưng**: Xây dựng kịch bản Demo hoàn chỉnh, chuẩn bị bộ Slide thuyết trình (`StoreFlowAI_Presentation_Slides.pptx`). |

---

## 8. KỊCH BẢN PHỐI HỢP THUYẾT TRÌNH & VẤN ĐÁP TRƯỚC HỘI ĐỒNG BẢO VỆ

Khi bảo vệ đồ án trước Hội đồng Giảng viên, 3 thành viên sẽ chia lượt trình bày mạch lạc và bổ trợ cho nhau:

### 8.1. Phân vai Thuyết trình (Presentation Flow)
* **Thời gian 1 (Phút 0 - 4) — Ngô Trung Kiên (Trưởng nhóm)**:
  - Giới thiệu tổng quan hệ thống StoreFlow AI và giải quyết bài toán tư vấn bán hàng thông minh.
  - Phân tích kiến trúc **Hybrid RAG 3 Phase**: Indexing (ChromaDB + `all-MiniLM-L6-v2`) $\rightarrow$ Retrieval (Oversampling Top-15) $\rightarrow$ Generation (Google Gemini 3.6 Flash).
  - Trình bày kết quả tối ưu hóa Prompt qua 3 vòng thử nghiệm (KT3) chứng minh giảm tỷ lệ ảo giác về 0%.
* **Thời gian 2 (Phút 4 - 8) — Vũ Đức Đạt (Backend Lead)**:
  - Trình bày nguyên lý **Single Source of Truth** của cơ sở dữ liệu SQLite: giải thích tại sao không tin tưởng 100% vào Vector DB mà phải có **SQLite Relational Guardrail** kiểm tra tồn kho thời gian thực.
  - Phân tích cơ chế đồng bộ tự động Life-cycle Hooks khi thêm/sửa/xóa sản phẩm.
  - Giới thiệu tầng bảo vệ bảo mật AI: Rate Limiting chống cạn kiệt Quota, Input Length Validator, Output Sanitizer và phân quyền RBAC chống xem trộm doanh thu.
* **Thời gian 3 (Phút 8 - 12) — Phan Duy Hưng (Frontend Lead)**:
  - Demo trực tiếp trên màn hình hệ thống:
    1. Thử vai trò Khách vãng lai (Guest): Gõ tìm kiếm *"Tư vấn chuột không dây yên tĩnh văn phòng tầm 300k"*.
    2. Cho Hội đồng xem kết quả 2 cột: Cột trái là lời phân tích của Gemini; cột phải là thẻ sản phẩm thực tế kèm ảnh và số lượng tồn khả dụng.
    3. Thử nghiệm sản phẩm ID 5 (cố tình để tồn kho = 0): Chứng minh AI không bao giờ tư vấn sản phẩm này nhờ chốt chặn Guardrail.
    4. Bấm nút **"Mở bán POS"** trên thẻ sản phẩm: Chứng minh sự chuyển đổi mượt mà từ AI sang quy trình thanh toán hóa đơn.
    5. Bật tắt Theme Toggle chuyển đổi giữa Retro CRT Dark Mode và Vintage Paper Light Mode (`#e6cb94`).

---

### 8.2. Danh mục Phân công Trả lời Vấn đáp của Giảng viên (Q&A Defense Matrix)

| Chủ đề câu hỏi của Giảng viên | Thành viên chịu trách nhiệm trả lời | Điểm mấu chốt kỹ thuật cần nêu bật |
| :--- | :---: | :--- |
| **"Mô hình Embedding là gì? Chạy ở đâu? Có tốn phí không?"** | **Ngô Trung Kiên** | Mô hình **`all-MiniLM-L6-v2`** (384 chiều) chạy **hoàn toàn Offline/Local** qua ONNX Runtime của ChromaDB, không tốn phí, độ trễ cực thấp (~15ms). |
| **"Tại sao không dùng SQL LIKE thông thường mà phải dùng ChromaDB?"** | **Ngô Trung Kiên** | SQL LIKE chỉ tìm kiếm từ khóa chính xác (Keyword Matching), không hiểu ngữ nghĩa. ChromaDB tìm kiếm theo khoảng cách ngữ nghĩa (Semantic Cosine Distance), hiểu được từ đồng nghĩa hoặc mô tả tính năng. |
| **"Nếu LLM Gemini bị mất mạng hoặc hết Quota thì hệ thống có bị sập không?"** | **Ngô Trung Kiên** | Hệ thống có cơ chế **Rule-based Graceful Fallback**: Bắt exception, chuyển cờ `is_fallback = True`, tự động sinh phản hồi từ dữ liệu đã xác thực của SQLite để phục vụ khách hàng bình thường. |
| **"Tại sao không lưu luôn số lượng tồn kho vào ChromaDB để tìm cho nhanh?"** | **Vũ Đức Đạt** | Vector DB không được thiết kế cho các giao dịch ghi tần suất cao (High-frequency ACID Transactions). Mỗi lần bán 1 sản phẩm mà re-index vector DB sẽ gây nghẽn I/O nghiêm trọng. Do đó, SQLite đóng vai trò Single Source of Truth kiểm tra tồn kho. |
| **"Làm sao đảm bảo khi nhiều người cùng gọi AI không bị sập server hoặc hết tiền API?"** | **Vũ Đức Đạt** | Hệ thống có bộ **In-memory Sliding Window Rate Limiter** tại `rate_limiter.py` (Guest: 10 req/min, Customer: 25 req/min...). Nếu vượt ngưỡng sẽ trả về HTTP 429 kèm Retry-After, bảo vệ server và ngân sách API. |
| **"Khách hàng có thể dùng Chatbot để hỏi xem doanh thu cửa hàng hoặc hóa đơn người khác không?"** | **Vũ Đức Đạt** | Tuyệt đối không. Backend enforce kiểm tra JWT RBAC: API báo cáo doanh thu độc quyền SuperAdmin (Admin/Staff/Guest gọi bị chặn 403); chức năng tra cứu đơn hàng của Customer có cơ chế **Anti-IDOR** chỉ truy xuất đúng hóa đơn có `customer_id` của chính họ. |
| **"Làm sao người dùng phân biệt câu trả lời của Gemini và câu trả lời dự phòng Fallback?"** | **Phan Duy Hưng** | Dựa vào trường `is_fallback` trong API: Nếu `false`, UI hiển thị Badge xanh *'Gemini 3.6 Flash Grounded'*; nếu `true`, UI hiển thị Badge vàng *'Chế độ tra cứu trực tiếp'*. |
| **"Trong 1-2 giây chờ AI suy nghĩ, giao diện có bị đơ không?"** | **Phan Duy Hưng** | Giao diện hiển thị hiệu ứng **Retro 3-Step Loading Animation** minh họa 3 bước xử lý: *Semantic Search ➔ Guardrail ➔ Gemini Generation*, đồng thời khóa nút gửi để chống double-click. |
| **"Tại sao lại thiết kế giao diện kết quả AI dạng 2 cột thay vì 1 khung chat tròn tròn thông thường?"** | **Phan Duy Hưng** | Đây là chuẩn thiết kế **Source Attribution & Actionable UI**: Cột trái giúp người dùng hiểu lý do tư vấn; cột phải cung cấp thẻ sản phẩm chuẩn xác có nút *'Mở bán POS'*, giúp nhân viên tạo đơn ngay lập tức mà không cần gõ lại mã hàng. |

---

## 9. KẾT LUẬN & CAM KẾT HOÀN THÀNH

Bảng phân công nhiệm vụ trên đảm bảo:
1. **Tính công bằng & Toàn diện**: Cả 3 thành viên đều có khối lượng công việc cân bằng (33.3% mỗi người), đảm nhiệm từ tầng Giao diện (Frontend), Tầng Nghiệp vụ & Dữ liệu (Backend & Database) đến Tầng Trí tuệ Nhân tạo chuyên sâu (AI & RAG).
2. **Đáp ứng 100% chuẩn học phần**: Phù hợp hoàn hảo với đề cương môn học *Ứng dụng Trí tuệ Nhân tạo*, đầy đủ minh chứng qua 4 bài kiểm tra (KT1, KT2, KT3, KT4) và tự tin đạt điểm xuất sắc khi bảo vệ đồ án trước Hội đồng.
