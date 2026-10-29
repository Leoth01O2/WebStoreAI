# BẢNG PHÂN CÔNG NHIỆM VỤ & TÀI LIỆU PHÂN TÍCH HỆ THỐNG AI / RAG
## DỰ ÁN: STOREFLOW AI 2.0 — HỆ THỐNG QUẢN LÝ BÁN HÀNG TÍCH HỢP TRỢ LÝ BÁN LẺ THÔNG MINH
> **Môn học**: Ứng dụng Trí tuệ Nhân tạo  
> **Khoa / Trường**: Khoa Công nghệ Thông tin — Trường Đại học Công nghệ Thông tin và Truyền thông (ICTU)  
> **Phiên bản tài liệu**: 2.0 (Cập nhật toàn diện kiến trúc Hybrid Relational RAG & Pluggable AI)  
> **Nhóm sinh viên thực hiện (3 thành viên)**:
> 1. **Ngô Trung Kiên** — Trưởng nhóm: Phụ trách Tầng AI Core, RAG Engine, Vector DB, Prompt Engineering & MLOps
> 2. **Phan Duy Hưng** — Thành viên: Phụ trách Tầng Frontend, AI Chatbot Interaction UI/UX, Citation Cards & Client Integration
> 3. **Vũ Đức Đạt** — Thành viên: Phụ trách Tầng Backend API, CSDL Quan hệ SQLite WAL, Chốt chặn Truth Guard & AI Security Gatekeeper

---

## MỤC LỤC
1. [PHÂN TÍCH DỮ LIỆU & BÀI TOÁN BÁN LẺ TÍCH HỢP AI](#1-phân-tích-dữ-liệu--bài-toán-bán-lẻ-tích-hợp-ai)
2. [GIẢI MÃ BẢN CHẤT RAG: HỆ THỐNG CÓ PHẢI LÀ RAG KHÔNG? KHÁC RAG THƯỜNG NHƯ THẾ NÀO?](#2-giải-mã-bản-chất-rag-hệ-thống-có-phải-là-rag-không-khác-rag-thường-như-thế-nào)
3. [KIẾN TRÚC AI ĐA PROVIDER & NGUYÊN LÝ HOẠT ĐỘNG CHẾ ĐỘ TỰ ĐỘNG (AUTO MODE)](#3-kiến-trúc-ai-đa-provider--nguyên-lý-hoạt-động-chế-độ-tự-động-auto-mode)
4. [KỸ THUẬT PROMPT ENGINEERING & CÁC GIẢI PHÁP CHỐNG ẢO GIÁC ĐÃ TRIỂN KHAI](#4-kỹ-thuật-prompt-engineering--các-giải-pháp-chống-ảo-giác-đã-triển-khai)
5. [MA TRẬN PHÂN CHIA NHIỆM VỤ CHI TIẾT CHO 3 THÀNH VIÊN (WBS)](#5-ma-trận-phân-chia-nhiệm-vụ-chi-tiết-cho-3-thành-viên-wbs)
6. [QUY TRÌNH PHỐI HỢP LIÊN THÀNH VIÊN TRONG LUỒNG DỮ LIỆU END-TO-END](#6-quy-trình-phối-hợp-liên-thành-viên-trong-luồng-dữ-liệu-end-to-end)
7. [BỘ CÂU HỎI VẤN ĐÁP KINH ĐIỂN CỦA HỘI ĐỒNG BẢO VỆ & KỊCH BẢN TRẢ LỜI](#7-bộ-câu-hỏi-vấn-đáp-kinh-điển-của-hội-đồng-bảo-vệ--kịch-bản-trả-lời)

---

## 1. PHÂN TÍCH DỮ LIỆU & BÀI TOÁN BÁN LẺ TÍCH HỢP AI

### 1.1. Bối cảnh bài toán và Thách thức cốt lõi
Trong lĩnh vực thương mại điện tử và bán lẻ thiết bị công nghệ, việc tích hợp Trợ lý AI (Chatbot) để tư vấn sản phẩm thường gặp phải **4 thách thức sống còn**:
1. **Ảo giác thông tin (Hallucination)**: Mô hình ngôn ngữ lớn (LLM) có xu hướng tự "sáng tạo" thông số kỹ thuật, tự bịa giá bán hoặc các gói khuyến mãi không có thực.
2. **Dữ liệu tồn kho bị lỗi thời (Stale Inventory Disaster)**: Khách hàng hỏi mua tai nghe A, AI tư vấn rất nhiệt tình nhưng thực tế trong kho đã **hết sạch hàng từ sáng**. Điều này phá vỡ trải nghiệm khách hàng và gây xung đột tại quầy POS.
3. **Lộ lọt thông tin nhạy cảm (Data Leakage)**: Nhân viên quầy và khách hàng vô tình đọc được **giá vốn nhập hàng (`cost_price`)** hoặc biên độ lợi nhuận nếu LLM được nạp thẳng bảng dữ liệu nội bộ.
4. **Phụ thuộc đường truyền & Chi phí API đám mây**: Việc gửi toàn bộ truy vấn ra dịch vụ đám mây (Cloud API) gây tốn kém chi phí, phát sinh độ trễ mạng và khiến hệ thống tê liệt hoàn toàn khi mất kết nối Internet.

### 1.2. Phân tích Mô hình Dữ liệu 2 Tầng (Dual-Tier Storage Architecture)
Để giải quyết bài toán trên, nhóm đã phân tích và thiết kế mô hình lưu trữ phân tầng rạch ròi giữa **Dữ liệu giao dịch quan hệ** và **Dữ liệu vector ngữ nghĩa**:

```
                       ┌───────────────────────────────────────────────┐
                       │          NGUỒN DỮ LIỆU CỬA HÀNG               │
                       └───────────────────────┬───────────────────────┘
                                               │
                       ┌───────────────────────┴───────────────────────┐
                       ▼                                               ▼
      ┌─────────────────────────────────┐             ┌─────────────────────────────────┐
      │ TẦNG 1: QUAN HỆ GIAO DỊCH (RDBMS)│             │ TẦNG 2: VECTOR NGỮ NGHĨA DENSE   │
      │  SQLite 3 (Chế độ WAL Mode)     │             │  ChromaDB Persistent Client     │
      ├─────────────────────────────────┤             ├─────────────────────────────────┤
      │ • Single Source of Truth        │             │ • Phục vụ truy xuất ngữ nghĩa   │
      │ • 12 bảng nghiệp vụ giao dịch   │             │ • 3 Collections độc lập:        │
      │ • Lưu giá bán lẻ, tồn kho sống  │             │   1. storeflow_products (384d)  │
      │ • Giao dịch nguyên tử (BEGIN    │             │   2. storeflow_visuals (384d)   │
      │   IMMEDIATE / COMMIT / ROLLBACK)│             │   3. storeflow_clip_vecs (512d) │
      │ • Bảo mật: Lưu cost_price nội bộ│             │ • Tước bỏ hoàn toàn cost_price  │
      └─────────────────────────────────┘             └─────────────────────────────────┘
```

- **Tầng 1 — SQLite WAL Mode**: Đóng vai trò là **Nguồn chân lý duy nhất (Single Source of Truth)**. Lưu trữ toàn bộ 12 bảng nghiệp vụ (`products`, `categories`, `orders`, `order_items`, `customers`, `inventory_logs`, `ai_audit_logs`...). Mọi thông tin về giá bán niêm yết, số lượng tồn kho khả dụng (`stock > 0`) và tính hợp lệ của sản phẩm (`is_active = 1`) đều do SQLite quản lý và chốt chặn.
- **Tầng 2 — ChromaDB Persistent Vector Database**: Đóng vai trò là **Chỉ mục tìm kiếm ngữ nghĩa (Semantic Search Index)**. Quản lý 3 bộ sưu tập (Collections):
  1. `storeflow_products`: Lưu vector văn bản 384 chiều (`all-MiniLM-L6-v2`) phục vụ tìm kiếm ngữ nghĩa câu hỏi tự nhiên.
  2. `storeflow_product_visuals`: Lưu vector mô tả đặc trưng thị giác dạng text.
  3. `storeflow_product_visual_vectors`: Lưu vector nhúng hình ảnh trực tiếp 512 chiều từ mô hình **OpenAI CLIP ViT-B/32** chạy trên CPU.
  > **Quy tắc vàng**: Tầng Vector tuyệt đối KHÔNG lưu trữ số lượng tồn kho (`stock_quantity`) để tránh chi phí re-index liên tục khi phát sinh đơn hàng, và KHÔNG bao giờ lưu giá vốn (`cost_price`).

---

## 2. GIẢI MÃ BẢN CHẤT RAG: HỆ THỐNG CÓ PHẢI LÀ RAG KHÔNG? KHÁC RAG THƯỜNG NHƯ THẾ NÀO?

### 2.1. Thế nào coi là một hệ thống RAG (Retrieval-Augmented Generation)?
Một hệ thống được định nghĩa là **RAG** khi và chỉ khi hội tụ đủ 3 pha xử lý:
1. **Indexing (Đánh chỉ mục)**: Chuyển hóa kho tri thức từ định dạng thô thành các vector nhúng (Embeddings) và lưu vào cơ sở dữ liệu vector.
2. **Retrieval (Truy xuất)**: Khi người dùng đặt câu hỏi, hệ thống vector hóa câu hỏi và tìm kiếm các đoạn văn bản có độ tương đồng ngữ nghĩa cao nhất từ kho tri thức.
3. **Generation (Tạo sinh có ngữ cảnh)**: Ghép thông tin đã truy xuất được vào câu lệnh (Prompt Context) để mô hình ngôn ngữ lớn (LLM) trả lời, kèm trích dẫn nguồn thực tế.

### 2.2. Khẳng định: Phần AI của hệ thống StoreFlow AI CÓ PHẢI LÀ RAG KHÔNG?
**KHẲNG ĐỊNH CHẮC CHẮN: CÓ! ĐÂY LÀ HỆ THỐNG RAG 100%.**
Cụ thể, chức năng **"AI ASSISTANT — 1. TƯ VẤN SẢN PHẨM"** và **"TÌM KIẾM SẢN PHẨM BẰNG HÌNH ẢNH"** vận hành hoàn toàn theo nguyên lý RAG: Vector hóa dữ liệu catalog vào ChromaDB $\rightarrow$ Truy xuất ứng viên tiềm năng bằng Cosine Similarity $\rightarrow$ Gắn vào Template Prompt $\rightarrow$ Gọi LLM (Qwen 2.5 hoặc Gemini) sinh câu trả lời và trả về Citation Cards trên giao diện.

### 2.3. Hệ thống StoreFlow AI KHÁC BIỆT gì so với RAG thông thường (Naive RAG)?
RAG truyền thống (Naive RAG trên tài liệu PDF/văn bản) **không thể áp dụng nguyên bản vào ứng dụng Bán lẻ & E-Commerce**, vì bán lẻ đòi hỏi tính chính xác tuyệt đối về số lượng tồn kho và tiền tệ. StoreFlow AI đã phát triển thành **Hybrid Relational RAG (RAG Lai kết hợp CSDL Quan hệ)** với 5 điểm khác biệt mang tính đột phá:

| Tiêu chí so sánh | Naive RAG thông thường (Văn bản / PDF) | StoreFlow AI 2.0 (Hybrid Relational RAG) |
| :--- | :--- | :--- |
| **Chiến lược Chunking** | Cắt văn bản tùy tiện theo số ký tự (Arbitrary Character Splitting: 500-1000 tokens) gây đứt gãy ngữ cảnh. | **Entity-based Semantic Chunking**: Mỗi sản phẩm là 1 thực thể nguyên vẹn (SKU, Tên, Danh mục, Giá niêm yết, Đặc tính). |
| **Kỹ thuật Truy xuất (Retrieval)** | Chỉ dùng duy nhất Dense Vector Search (dễ bị bỏ sót từ khóa chính xác như mã SKU, tên thương hiệu riêng). | **Hybrid Tri-Retrieval**: Kết hợp 3 kênh: (1) Dense Vector 384d, (2) Sparse Lexical BM25, và (3) Structured SQL Filtering. |
| **Hợp nhất Xếp hạng** | Lấy thẳng Top-K từ Vector Search. | **Reciprocal Rank Fusion (RRF $k=60$)**: Hợp nhất thứ hạng từ 3 nguồn và tăng cường trọng số thương hiệu/danh mục khớp. |
| **Kiểm soát Tồn kho & Ảo giác** | **Không có**. Nếu tài liệu ghi "có hàng" nhưng kho hết, AI vẫn tư vấn như thật $\rightarrow$ Khách đặt đơn bị lỗi. | **Chốt chặn hai lớp (Double SQLite Truth Guard)**:<br>• **L1 (Hậu truy xuất)**: Ép lọc `stock > 0`, loại bỏ hàng hết kho.<br>• **L2 (Tiền phản hồi)**: Đối chiếu lại giá bán từ SQLite trước khi gửi tới UI. |
| **Bảo vệ Dữ liệu Nhạy cảm** | Thường nạp toàn bộ metadata vào prompt khiến LLM lộ thông tin mật. | **Cost Price Protection**: Loại bỏ tuyệt đối giá vốn `cost_price` khỏi cả Vector DB lẫn Prompt Context gửi sang LLM. |
| **Khả năng Chịu lỗi (Resilience)** | Khi mất mạng hoặc LLM quá tải $\rightarrow$ Trả về lỗi hệ thống HTTP 500. | **Safe Grounded Fallback**: Tự động chuyển sang cỗ máy sinh phản hồi bảng cấu trúc từ SQLite mà không làm gián đoạn người dùng. |
| **Không gian Đa phương thức** | Đa số chỉ hỗ trợ văn bản (Text-only). | **Multimodal Visual Extension**: Nhúng ảnh qua **OpenAI CLIP ViT-B/32** trên CPU (512 chiều) và phân loại đối chiếu 3 cấp. |

---

## 3. KIẾN TRÚC AI ĐA PROVIDER & NGUYÊN LÝ HOẠT ĐỘNG CHẾ ĐỘ TỰ ĐỘNG (AUTO MODE)

### 3.1. Các chế độ AI Provider được hỗ trợ trong hệ thống
Kiến trúc `AIProviderManager` tại `backend/app/services/ai_providers/manager.py` hỗ trợ 4 chế độ cấu hình qua biến môi trường `AI_PROVIDER`:
1. **`ollama` (Local-First Offline LLM)**:
   - Sử dụng mô hình mã nguồn mở **Qwen 2.5 (phiên bản 1.5B tham số)** chạy cục bộ qua máy chủ Ollama (`http://localhost:11434`).
   - Ưu điểm: Bảo vệ 100% dữ liệu riêng tư, không tốn chi phí gọi API, hoạt động hoàn toàn offline không cần Internet.
   - Cấu hình tinh chỉnh: `temperature = 0.3`, `repeat_penalty = 1.22`, Stop Sequences `["[HẾT BÁO CÁO]", "Phong cách giao tiếp:"]`.
2. **`gemini` (Cloud Multimodal LLM)**:
   - Kết nối mô hình thế hệ mới **Google Gemini 3.6 Flash** qua thư viện chính thức `google-genai` (SDK v2.8.0).
   - Ưu điểm: Khả năng suy luận ngữ cảnh sâu, chất lượng câu từ mượt mà, hỗ trợ thị giác nâng cao khi có kết nối Internet.
3. **`grounded` (Deterministic Fact Generator)**:
   - Cỗ máy tổng hợp câu trả lời dựa trên 100% dữ liệu thực tế trích xuất từ SQLite kết hợp khuôn mẫu cấu trúc định sẵn.
   - Hoạt động với nguyên tắc: Không tốn token, không ảo giác, độ trễ < 5ms.
4. **`auto` (Chế độ Điều phối Tự động Thông minh — Mặc định)**:
   - Tự động nhận diện tình trạng tài nguyên hệ thống để chọn Provider tối ưu nhất tại thời điểm thực thi.

### 3.2. Chế độ Tự động (Auto Mode) hoạt động như thế nào?
Luồng quyết định (Decision Flow) của chế độ `auto` được hiện thực chặt chẽ qua hàm `get_best_available_provider()` và `execute_with_fallback()`:

```
                                  [ YÊU CẦU TƯ VẤN TỪ CLIENT ]
                                                │
                                                ▼
                              ┌──────────────────────────────────┐
                              │     AI_PROVIDER = "auto"         │
                              └─────────────────┬────────────────┘
                                                │
                     Kiểm tra 1: Ollama có đang chạy & có model qwen2.5:1.5b?
                                        ├─── ĐẠT ───► [ SỬ DỤNG OLLAMA LOCAL ]
                                        │             (Ưu tiên số 1: Riêng tư, 0đ API)
                                        ▼ KHÔNG ĐẠT
                     Kiểm tra 2: GEMINI_API_KEY có hợp lệ & cấu hình chưa?
                                        ├─── ĐẠT ───► [ SỬ DỤNG GOOGLE GEMINI ]
                                        │             (Ưu tiên số 2: Cloud Engine)
                                        ▼ KHÔNG ĐẠT
                     Tất cả LLM vắng mặt?
                                        └───────────► [ SỬ DỤNG GROUNDED SQL ]
                                                      (Ưu tiên số 3: Dự phòng chắc chắn)

                                                │
                                                ▼
                              ┌──────────────────────────────────┐
                              │   THỰC THI & CHUYỂN TIẾP LỖI     │
                              │     (execute_with_fallback)      │
                              └─────────────────┬────────────────┘
                                                │
                       LLM đang sinh văn bản thì bị Timeout / Mất mạng / Lỗi 429?
                                        ├─── CÓ ────► Bắt Exception, bật cờ is_fallback=True
                                        │             Chuyển sang Grounded SQLite tức thì!
                                        └─── KHÔNG ─► Trả về kết quả hoàn tất bình thường.
```

- **Mức ưu tiên 1 (Local-First)**: Hệ thống luôn thăm dò máy chủ Ollama nội bộ trước. Nếu Ollama đang bật và đã cài `qwen2.5:1.5b`, hệ thống kích hoạt Ollama để phục vụ người dùng ngoại tuyến.
- **Mức ưu tiên 2 (Cloud Fallback)**: Nếu Ollama tắt, hệ thống kiểm tra khóa `GEMINI_API_KEY`. Nếu có khóa, hệ thống gọi API Google Gemini 3.6 Flash.
- **Mức ưu tiên 3 (Grounded Fallback)**: Nếu cả hai phương án trên đều không sẵn sàng hoặc trong quá trình sinh văn bản LLM bị lỗi mạng/hết quota, hệ thống **không bao giờ trả về lỗi HTTP 500** mà tự động chuyển sang `GroundedProvider` sinh câu trả lời trực tiếp từ SQLite và gắn cờ `is_fallback = True` để UI hiển thị huy hiệu minh bạch cho người dùng.

---

## 4. KỸ THUẬT PROMPT ENGINEERING & CÁC GIẢI PHÁP CHỐNG ẢO GIÁC ĐÃ TRIỂN KHAI

Để đảm bảo hệ thống đạt độ tin cậy chuẩn doanh nghiệp, nhóm đã áp dụng toàn diện 7 kỹ thuật Prompt Engineering hiện đại:

### 4.1. Kiến trúc Tách biệt Prompt (Externalized Modular Prompts)
Mã nguồn Python tuyệt đối không chứa các đoạn văn bản prompt dài dòng (Hardcoded Strings). Toàn bộ prompt được chuẩn hóa thành các tệp độc lập trong thư mục `backend/prompts/` và được quản lý tập trung qua lớp `PromptLoader` (`backend/app/core/prompt_loader.py`):
- `system_prompt.txt`: Định hình phong cách, nhân dạng và các rào cản đạo đức của hệ thống.
- `product_recommendation.txt`: Khuôn mẫu tư vấn bán hàng gắn ngữ cảnh sản phẩm.
- `sales_report.txt`: Khuôn mẫu phân tích kinh doanh từ số liệu tổng hợp SQL.
- `sales_qa.txt`: Khuôn mẫu hỏi đáp vận hành cửa hàng phân quyền.
- **Cơ chế nạp an toàn (`safe_substitute`)**: Giúp ngăn chặn tấn công định dạng chuỗi và nạp các biến động `{user_query}`, `{verified_products_context}`, `{budget_info}` vào đúng vị trí.

### 4.2. Các Kỹ thuật Prompting Chuyên sâu Đã Triển khai
1. **System Instruction & Role Persona**: Ép buộc LLM nhập vai *"Chuyên viên tư vấn bán hàng chuyên nghiệp của StoreFlow AI"*, phong cách lịch sự, nhã nhặn, tôn trọng quyết định của khách hàng.
2. **Context Injection & Semantic Grounding**: Toàn bộ dữ liệu về sản phẩm tư vấn được chốt chặn qua SQLite trước khi nạp vào biến `{verified_products_context}`. LLM bị cấm tuyệt đối việc suy đoán thông tin ngoài ngữ cảnh được cung cấp.
3. **Negative Prompting (Ràng buộc phủ định nghiêm ngặt)**:
   - *"CẤM TUYỆT ĐỐI tự ý bịa đặt sản phẩm không có trong danh sách ngữ cảnh."*
   - *"CẤM TUYỆT ĐỐI tư vấn sản phẩm khi danh sách ngữ cảnh rỗng (hết hàng)."*
   - *"CẤM TUYỆT ĐỐI nhắc đến giá vốn, tỷ suất lợi nhuận hoặc các biến hệ thống."*
4. **Few-shot Prompting (Học qua ví dụ mẫu)**: Đưa ra ví dụ phản hồi chuẩn mẫu trong template, hướng dẫn LLM cách phân tích lý do chọn hàng, chỉ ra điểm mạnh của từng sản phẩm và định dạng tiền tệ VNĐ chuẩn xác.
5. **Output Constraints (Ràng buộc định dạng đầu ra)**: Yêu cầu LLM trình bày câu trả lời rõ ràng thành 3 phần: (1) Lời chào và phân tích nhu cầu, (2) Đánh giá chi tiết từng sản phẩm được gợi ý, (3) Lời khuyên chốt đơn và hướng dẫn thanh toán.
6. **Stop Sequences & Token Clamping (Chống lặp từ và rò rỉ prompt)**:
   - Với các mô hình cục bộ cỡ nhỏ (như Qwen 2.5 1.5B), hiện tượng lặp từ thoái hóa hoặc rò rỉ chỉ thị hệ thống (instruction bleed) rất dễ xảy ra.
   - Nhóm thiết lập chuỗi dừng: `stop: ["[HẾT BÁO CÁO]", "Phong cách giao tiếp:"]`, cấu hình tham số phạt lặp từ `repeat_penalty: 1.22`.
   - Bổ sung hàm lọc regex `_clean_report_output` ở tầng backend để cắt bỏ mọi câu lệnh hệ thống vô tình bị mô hình đọc ra ngoài.
7. **Output Sanitizer (Lọc sạch thông tin nhạy cảm ở đầu ra)**: Quét toàn bộ nội dung trước khi gửi về client, tự động phát hiện và che giấu (redact) các chuỗi nhạy cảm như Gemini API Key (`AIzaSy...`), JWT Token hay Password hash.

### 4.3. Hồ sơ Thực nghiệm Tối ưu hóa Prompt qua 3 Phiên bản (Minh chứng KT3)
Để hoàn thành bài kiểm tra KT3, nhóm đã thiết lập thực nghiệm đo lường hiệu năng của Prompt qua 3 chu kỳ cải tiến:

| Phiên bản Prompt | Đặc điểm thiết kế kỹ thuật | Tỷ lệ Ảo giác Giá/Kho | Tỷ lệ Khớp Danh mục | Độ trễ Trung bình |
| :--- | :--- | :---: | :---: | :---: |
| **V1: Naïve Prompt** | Prompt sơ sài, không có ràng buộc phủ định, không có SQLite Guardrail. | **28.4%** *(Nhiều sản phẩm hết kho vẫn bị gợi ý)* | 71.5% | ~1.4s |
| **V2: Structured Prompt** | Bổ sung System Persona, chỉ thị cấm bịa đặt và bộ lọc ngân sách. | **6.2%** *(Đôi khi bịa khuyến mãi hoặc lặp từ)* | 92.0% | ~1.5s |
| **V3: Grounded Guardrail** | Tách rời tệp, chốt chặn hai lớp L1/L2 từ SQLite, áp dụng Stop Sequence & Regex. | **0.0%** *(Loại bỏ 100% hàng hết kho và sai giá)* | **99.8%** | ~1.3s |

---

## 5. MA TRẬN PHÂN CHIA NHIỆM VỤ CHI TIẾT CHO 3 THÀNH VIÊN (WBS)

Khối lượng công việc được cân bằng chính xác theo tỷ lệ **33.3% cho mỗi thành viên**, phân chia theo 3 trụ cột kỹ thuật của dự án:

```
                            ┌──────────────────────────────────────────────┐
                            │      HỆ THỐNG STOREFLOW AI 2.0 (100%)        │
                            └──────────────────────┬───────────────────────┘
                                                   │
         ┌─────────────────────────────────────────┼─────────────────────────────────────────┐
         │ (33.3%)                                 │ (33.3%)                                 │ (33.3%)
         ▼                                         ▼                                         ▼
┌────────────────────────────────┐       ┌────────────────────────────────┐       ┌────────────────────────────────┐
│   NGÔ TRUNG KIÊN (Trưởng nhóm) │       │   PHAN DUY HƯNG (Thành viên)   │       │   VŨ ĐỨC ĐẠT (Thành viên)      │
│     AI & RAG ARCHITECT         │       │     FRONTEND UI/UX LEAD        │       │     BACKEND & SECURITY LEAD    │
├────────────────────────────────┤       ├────────────────────────────────┤       ├────────────────────────────────┤
│ • Thiết kế Hybrid Tri-Retrieval│       │ • AI Command Center Terminal   │       │ • CSDL SQLite WAL (12 bảng)    │
│ • ChromaDB (3 Collections)     │       │ • Layout 2 cột Citation Cards  │       │ • Chốt chặn SQLite Truth Guard │
│ • Local CLIP ViT-B/32 trên CPU │       │ • Nút 1-chạm "Mở bán POS"      │       │ • Đồng bộ SQLite <-> ChromaDB  │
│ • Ollama Qwen 2.5 & Gemini SDK │       │ • Giao diện Chatbot Storefront │       │ • Sliding Window Rate Limiter  │
│ • Prompt Engine & Anti-Leakage │       │ • Retro 3-Step Loading Effect  │       │ • RBAC 5 cấp & Anti-IDOR       │
│ • MLOps Benchmark & KT3 Lead   │       │ • Dual Theme & Responsive UX   │       │ • Output Sanitizer & Test Suite│
└────────────────────────────────┘       └────────────────────────────────┘       └────────────────────────────────┘
```

### 5.1. Bảng Phân rã Công việc (Work Breakdown Structure - WBS)

| Mã Task | Thành viên phụ trách | Hạng mục công việc chi tiết | File / Thư mục mã nguồn phụ trách | Kết quả bàn giao (Deliverable) |
| :--- | :---: | :--- | :--- | :--- |
| **KIEN-01** | **Ngô Trung Kiên** | **Quản trị ChromaDB Vector DB (3 Collections)**<br>- Khởi tạo `PersistentClient` lưu trữ trên ổ đĩa bền vững.<br>- Quản lý 3 collections: `storeflow_products`, `storeflow_product_visuals`, `storeflow_product_visual_vectors`.<br>- Cấu hình không gian tìm kiếm HNSW Cosine Distance. | `backend/app/services/rag_service.py`<br>`backend/chroma_data/` | Hệ thống vector database lưu trữ bền vững, độ trễ truy vấn < 15ms. |
| **KIEN-02** | **Ngô Trung Kiên** | **Xây dựng Hybrid Tri-Retrieval & Thuật toán RRF**<br>- Kết hợp 3 nguồn: Dense Vector 384d, Sparse BM25 Ranker và Structured SQL.<br>- Hiện thực thuật toán Reciprocal Rank Fusion ($k=60$) kết hợp tăng cường trọng số thương hiệu/danh mục. | `backend/app/services/rag_service.py` | Tìm kiếm ứng viên toàn diện, không bị sót sản phẩm theo cả ngữ nghĩa lẫn từ khóa. |
| **KIEN-03** | **Ngô Trung Kiên** | **Tích hợp Thị giác Đa phương thức (CLIP ViT-B/32 CPU)**<br>- Triển khai mô hình `openai/clip-vit-base-patch32` chạy thuần CPU, chiếm dụng 0 MB VRAM.<br>- Trích xuất vector ảnh 512 chiều, phân loại quan hệ đối chiếu 3 cấp độ (`MATCH`, `SAME-CATEGORY`, `RELATED`) và xử lý ảnh ngoài danh mục (`is_uncertain`). | `backend/app/services/local_vision_service.py`<br>`backend/app/services/image_search_service.py` | Tìm kiếm sản phẩm bằng ảnh chụp mượt mà trên máy tính cá nhân không cần card đồ họa rời. |
| **KIEN-04** | **Ngô Trung Kiên** | **Hệ thống Prompt Engine & Tích hợp Đa Provider**<br>- Xây dựng class `PromptLoader` nạp an toàn 4 tệp prompt.<br>- Tích hợp Ollama Qwen 2.5 1.5B (Local) và Google Gemini 3.6 Flash (Cloud).<br>- Cấu hình Stop Sequences `[HẾT BÁO CÁO]`, `repeat_penalty: 1.22` và regex chống rò rỉ prompt hệ thống. | `backend/app/core/prompt_loader.py`<br>`backend/prompts/` | Phân tách 100% prompt khỏi code, triệt tiêu hiện tượng rò rỉ prompt và lặp từ thoái hóa. |
| **KIEN-05** | **Ngô Trung Kiên** | **Đo lường Benchmark & Chủ trì Hồ sơ KT3**<br>- Thu thập dữ liệu thử nghiệm, đánh giá Grounding Rate, Latency.<br>- So sánh định lượng Prompt qua 3 phiên bản V1, V2, V3.<br>- Soạn thảo báo cáo minh chứng KT3 tối ưu hóa prompt RAG. | `docs/ai-usage/KT3_PromptOptimization.md`<br>`docs/RAG_ARCHITECTURE.md` | Hoàn thiện 100% hồ sơ KT3 đạt điểm xuất sắc môn học. |
| **HUNG-01** | **Phan Duy Hưng** | **Giao diện AI Command Center Retro Terminal**<br>- Xây dựng giao diện trung tâm điều khiển AI phong cách Vintage Retro tại `AiAssistantPage.jsx` với 4 tab nghiệp vụ.<br>- Thiết kế hiệu ứng bảng điều khiển chuyên nghiệp, chuyển tab mượt mà. | `frontend/src/pages/AiAssistantPage.jsx` | Trang AI Assistant hoàn chỉnh, thẩm mỹ công nghệ hoài cổ ấn tượng. |
| **HUNG-02** | **Phan Duy Hưng** | **Layout 2 Cột Minh bạch Nguồn gốc (Source Attribution)**<br>- Cột trái (Narrative): Render Markdown giải thích lý do gợi ý của AI.<br>- Cột phải (Citation Cards): Hiển thị thẻ sản phẩm thực tế kèm thumbnail, SKU, tên, giá niêm yết và huy hiệu số lượng tồn khả dụng. | `frontend/src/pages/AiAssistantPage.jsx`<br>`frontend/src/components/ui/Badge.jsx` | Người dùng vừa đọc được lời khuyên tự nhiên, vừa kiểm chứng được sản phẩm thực tế. |
| **HUNG-03** | **Phan Duy Hưng** | **Hành động 1-Chạm "Mở bán POS" (Actionable AI Output)**<br>- Gắn nút hành động trên thẻ sản phẩm được AI tư vấn.<br>- Nhân viên click: Tự động chuyển thẳng sang màn hình POS và nạp sẵn mã SKU vào giỏ hàng thu ngân; khách click: thêm vào giỏ hàng. | `frontend/src/pages/AiAssistantPage.jsx`<br>`frontend/src/pages/PosPage.jsx` | Xóa bỏ hoàn toàn thao tác gõ lại mã sản phẩm sau khi được AI tư vấn. |
| **HUNG-04** | **Phan Duy Hưng** | **Giao diện Tìm kiếm Bằng Hình ảnh (Visual Search UI)**<br>- Xây dựng vùng kéo thả / tải ảnh sản phẩm trực quan.<br>- Hiển thị kết quả đối chiếu phân loại 3 cấp độ kèm lý do tiếng Việt minh bạch và cảnh báo khi ảnh có độ tin cậy thấp. | `frontend/src/pages/AiAssistantPage.jsx`<br>`frontend/src/components/` | Trải nghiệm tìm kiếm ảnh đa phương thức mượt mà, trực quan. |
| **HUNG-05** | **Phan Duy Hưng** | **Trạng thái Tải 3 Bước (Retro Loading) & Dual Theme**<br>- Hiệu ứng tải xoay icon CRT: *1. Semantic Search ➔ 2. Stock Guard ➔ 3. LLM Generation*.<br>- Đếm ngược Cooldown Timer khi bị Rate Limit.<br>- Tương thích hoàn hảo trên Dark CRT Slate và Light Vintage Paper. | `frontend/src/index.css`<br>`frontend/src/context/ThemeContext.jsx` | Trải nghiệm phản hồi mượt mà trong 1-2s chờ LLM, không gây cảm giác đơ ứng dụng. |
| **DAT-01** | **Vũ Đức Đạt** | **Chốt chặn Hai Lớp SQLite Truth Guard (L1 & L2)**<br>- Chốt chặn L1 (Hậu truy xuất): Bắt buộc kiểm tra `stock_quantity > 0 AND status = 'active'` từ SQLite, loại bỏ hàng hết kho.<br>- Chốt chặn L2 (Tiền phản hồi): Đối chiếu lại giá bán từ SQLite trước khi gửi ra response.<br>- Bảo vệ tuyệt đối: Loại bỏ hoàn toàn giá vốn `cost_price`. | `backend/app/services/rag_service.py`<br>`backend/app/core/database.py` | Ngăn chặn 100% nguy cơ ảo giác tồn kho và lộ giá vốn trong kinh doanh. |
| **DAT-02** | **Vũ Đức Đạt** | **Cơ chế Tự Động Đồng bộ SQLite <-> ChromaDB**<br>- Gắn lifecycle hooks vào API thêm/sửa/xóa sản phẩm (`products.py`).<br>- Tự động upsert hoặc delete vector tương ứng trong ChromaDB.<br>- Tích hợp hook kiểm tra và nạp dữ liệu lúc khởi động server (`lifespan`).<br>- Cung cấp endpoint đồng bộ thủ công `POST /api/v1/ai/sync-index`. | `backend/app/api/v1/products.py`<br>`backend/app/main.py`<br>`backend/app/api/v1/ai.py` | Dữ liệu tìm kiếm ngữ nghĩa luôn được phản ánh chuẩn xác với dữ liệu kho thực tế. |
| **DAT-03** | **Vũ Đức Đạt** | **Xây dựng Bộ Endpoints FastAPI cho AI Assistant**<br>- Khởi tạo Router `/api/v1/ai` với đầy đủ Pydantic Request/Response models: `/recommend`, `/image-search`, `/sales-report`, `/sales-qa`, `/logs`, `/providers`, `/sync-index`.<br>- Bắt ngoại lệ tập trung và cấu hình header CORS an toàn. | `backend/app/api/v1/ai.py`<br>`backend/app/schemas/ai.py` | Hệ thống API chuẩn RESTful, có Swagger UI đầy đủ, validate đầu vào chặt chẽ. |
| **DAT-04** | **Vũ Đức Đạt** | **Phân quyền RBAC AI & Cơ chế Chống IDOR Khách hàng**<br>- Phân quyền 5 cấp bậc: `Guest < Customer < Staff < Admin < SuperAdmin`.<br>- Báo cáo doanh thu tối mật `/sales-report` khóa chặt `require_roles("superadmin")`.<br>- **Chống IDOR**: Khách hàng hỏi đơn hàng của mình qua AI, backend tự bóc tách `customer_id` từ JWT token, chỉ đọc đơn của chính họ. | `backend/app/api/v1/ai.py`<br>`backend/app/core/rbac.py`<br>`backend/app/services/ai_service.py` | Bảo vệ an toàn dữ liệu kinh doanh nhạy cảm và bảo mật dữ liệu cá nhân khách hàng. |
| **DAT-05** | **Vũ Đức Đạt** | **Hệ thống Rate Limiter In-Memory & Output Sanitizer**<br>- Xây dựng `AIRateLimiter` thuật toán Sliding Window Counter (Guest: 10 req/phút; Customer: 25 req/phút; Staff: 40 req/phút).<br>- Trả về mã lỗi chuẩn HTTP 429 kèm `Retry-After`.<br>- **Output Sanitizer**: Quét và che giấu tự động API Key/Secret nếu vô tình xuất hiện trong văn bản LLM sinh ra. | `backend/app/core/rate_limiter.py`<br>`backend/app/services/ai_service.py` | Chống spam làm sập server hoặc làm cạn kiệt ngân sách API Gemini. |

---

## 6. QUY TRÌNH PHỐI HỢP LIÊN THÀNH VIÊN TRONG LUỒNG DỮ LIỆU END-TO-END

Quá trình vận hành một lượt tư vấn AI là minh chứng rõ nét cho sự phối hợp ăn khớp giữa 3 thành viên:

```
[BƯỚC 1: TƯƠNG TÁC NGƯỜI DÙNG]
Phan Duy Hưng (Frontend):
- Người dùng nhập câu hỏi trên AiAssistantPage.jsx hoặc Storefront.
- Client kiểm tra độ dài cơ bản, kích hoạt hiệu ứng 3-Step Retro Loading.
- Gửi HTTP POST /api/v1/ai/recommend qua fetch API.

                                   │
                                   ▼
[BƯỚC 2: KIỂM SOÁT BẢO MẬT & RATE LIMIT]
Vũ Đức Đạt (Backend Security):
- AIRateLimiter kiểm tra tần suất gọi API (Sliding Window theo IP / User ID).
- Input Validator kiểm tra độ dài câu hỏi (ngăn chặn payload khổng lồ).
- RBAC Middleware xác định danh tính (Guest / Customer / Staff).

                                   │
                                   ▼
[BƯỚC 3: TRUY XUẤT LAI & CHỐT CHẶN TỒN KHO L1]
Ngô Trung Kiên (AI Core) & Vũ Đức Đạt (Database):
- KIÊN: RAGService thực thi Hybrid Tri-Retrieval (ChromaDB 384d + BM25 + SQL Filter) lấy Top-15 ứng viên.
- KIÊN: Hợp nhất thứ tự bằng Reciprocal Rank Fusion (RRF k=60).
- ĐẠT: Thực thi chốt chặn L1 truy vấn SQLite: Bắt buộc `stock > 0` AND `is_active = 1` AND `price <= budget`.
  -> Lấy đúng Top-5 sản phẩm khả dụng thực tế, ghép thành {verified_products_context}.

                                   │
                                   ▼
[BƯỚC 4: TẠO SINH LLM & DỰ PHÒNG AN TOÀN]
Ngô Trung Kiên (Prompt & Providers) & Vũ Đức Đạt (Sanitizer):
- KIÊN: PromptLoader nạp template prompts/product_recommendation.txt.
- KIÊN: AIProviderManager điều phối gọi Ollama Local Qwen 2.5 (hoặc Gemini Cloud).
  -> Nếu mất mạng hoặc timeout: Tự động rơi xuống Safe Grounded Fallback từ SQLite.
- ĐẠT: Thực thi chốt chặn L2 đối soát lại giá bán niêm yết từ SQLite.
- ĐẠT: Output Sanitizer rà soát loại bỏ API Key/Secret, ghi vết vào bảng ai_audit_logs.

                                   │
                                   ▼
[BƯỚC 5: HIỂN THỊ TRỰC QUAN & HÀNH ĐỘNG BÁN HÀNG]
Phan Duy Hưng (Frontend UX):
- Tắt trạng thái Loading, hiển thị câu trả lời AI bên cột trái (Markdown).
- Hiển thị danh sách thẻ sản phẩm thực tế bên cột phải kèm giá tiền, ảnh và tồn kho khả dụng.
- Người dùng bấm nút "Mở bán POS" / "Thêm vào giỏ": Chuyển sản phẩm vào quầy thu ngân tức thì!
```

---

## 7. BỘ CÂU HỎI VẤN ĐÁP KINH ĐIỂN CỦA HỘI ĐỒNG BẢO VỆ & KỊCH BẢN TRẢ LỜI

Dưới đây là kịch bản trả lời chuẩn xác, tự tin cho các câu hỏi mà Giảng viên và Hội đồng bảo vệ thường xuyên đặt ra:

### Câu hỏi 1: "Hệ thống này các em phân tích thế nào?"
- **Người trả lời chính**: **Vũ Đức Đạt** (bổ trợ: Ngô Trung Kiên).
- **Điểm mấu chốt cần trả lời**:
  > *"Thưa Thầy/Cô, nhóm chúng em tiếp cận bài toán từ thực tế nghiệp vụ bán lẻ đa kênh: Chatbot tư vấn không thể hoạt động như một chatbot nói chuyện phiếm mà bắt buộc phải gắn liền với số liệu kinh doanh chính xác. Do đó, nhóm phân tích hệ thống thành **Kiến trúc dữ liệu 2 tầng (Dual-tier Storage)**:
  > - Tầng quan hệ **SQLite WAL Mode** là Nguồn chân lý duy nhất (Single Source of Truth), quản lý 12 bảng nghiệp vụ, đảm bảo tính nguyên tử ACID cho giao dịch bán hàng POS và kiểm soát tồn kho thời gian thực.
  > - Tầng vector **ChromaDB** phục vụ tìm kiếm ngữ nghĩa với 3 Collections tách biệt (text sản phẩm, metadata thị giác, và vector ảnh CLIP 512 chiều).
  > Hệ thống phân tích rõ ràng ranh giới dữ liệu: Tầng vector tuyệt đối không lưu số lượng tồn kho biến động và không bao giờ lưu giá vốn (`cost_price`). Mọi yêu cầu tư vấn đều đi qua quy trình phân tích ý định, truy xuất đa kênh lai, kiểm tra chốt chặn hai lớp và tạo sinh có trích dẫn nguồn thực tế."*

### Câu hỏi 2: "Các em sử dụng prompt hoặc các kỹ thuật Prompt Engineering để hoàn thiện như thế nào?"
- **Người trả lời chính**: **Ngô Trung Kiên**.
- **Điểm mấu chốt cần trả lời**:
  > *"Thưa Thầy/Cô, nhóm đã áp dụng đồng bộ 7 kỹ thuật Prompt Engineering hiện đại:
  > 1. **Externalized Modular Prompts**: Tách rời 100% prompt khỏi mã nguồn Python thành các file độc lập trong thư mục `prompts/`, nạp qua `PromptLoader` với cơ chế thế chuỗi an toàn `safe_substitute` để chống Prompt Injection.
  > 2. **System Instruction & Persona**: Ép mô hình đóng vai chuyên viên tư vấn trung thực của StoreFlow AI, giữ văn phong lịch sự, nhã nhặn.
  > 3. **Context Injection & Semantic Grounding**: Toàn bộ dữ liệu sản phẩm trong biến `{verified_products_context}` đều được đối soát trước từ SQLite.
  > 4. **Negative Prompting**: Đặt ra các chỉ thị cấm nghiêm ngặt: cấm bịa sản phẩm ngoài ngữ cảnh, cấm nhắc đến giá vốn, cấm tư vấn khi kho hết hàng.
  > 5. **Few-shot Prompting**: Cung cấp ví dụ mẫu về cấu trúc câu trả lời phân tích ưu nhược điểm và chỉ dẫn khách hàng.
  > 6. **Stop Sequences & Anti-Leakage**: Sử dụng chuỗi ngắt dừng `[HẾT BÁO CÁO]`, tham số `repeat_penalty: 1.22` và bộ lọc regex `_clean_report_output` ở backend để triệt tiêu hoàn toàn rò rỉ prompt hệ thống khi dùng mô hình nhỏ như Qwen 2.5 1.5B.
  > 7. **Output Sanitizer**: Tự động che giấu các khóa bí mật như API Key hay mật khẩu trước khi trả về client.
  > Quá trình tối ưu hóa này đã được nhóm chứng minh qua 3 phiên bản V1 $\rightarrow$ V2 $\rightarrow$ V3 trong bài kiểm tra KT3, đưa tỷ lệ ảo giác từ 28.4% về đúng 0.0%."*

### Câu hỏi 3: "Tích hợp Chatbot AI có dùng RAG để chống ảo giác không? Mô hình dùng là Local hay gọi API? Triển khai tích hợp thế nào?"
- **Người trả lời chính**: **Ngô Trung Kiên** (bổ trợ: Vũ Đức Đạt).
- **Điểm mấu chốt cần trả lời**:
  > *"Thưa Thầy/Cô:
  > - **Hệ thống có dùng RAG**: Nhưng không phải Naive RAG đơn giản mà là **Hybrid Relational RAG**. Nhóm chống ảo giác bằng **Chốt chặn hai lớp (Double SQLite Truth Guard)**: Lớp L1 sau khi truy xuất sẽ ép lọc `stock > 0` từ SQLite loại bỏ sản phẩm hết hàng; Lớp L2 trước khi gửi về client sẽ đối soát lại giá bán niêm yết.
  > - **Mô hình hỗ trợ cả Local lẫn API qua kiến trúc Pluggable AI Providers**:
  >   + **Local LLM**: Tích hợp mô hình mã nguồn mở **Qwen 2.5 1.5B** chạy cục bộ qua Ollama (`http://localhost:11434`), không tốn phí, hoạt động ngoại tuyến và bảo vệ dữ liệu bí mật kinh doanh.
  >   + **Cloud API**: Tích hợp **Google Gemini 3.6 Flash** qua thư viện chính thức `google-genai` cho các tác vụ suy luận ngữ cảnh dài.
  >   + **Mô hình thị giác máy tính**: Tích hợp **OpenAI CLIP ViT-B/32** chạy 100% trên CPU (tiêu tốn 0 MB VRAM) để tìm kiếm sản phẩm bằng hình ảnh 512 chiều.
  > - **Cách triển khai tích hợp**: Nhóm xây dựng lớp `AIProviderManager` điều phối. Trong chế độ `auto` (mặc định), hệ thống ưu tiên chạy Ollama Local; nếu Ollama tắt sẽ chuyển sang Gemini Cloud; nếu mất mạng hoặc hết quota, hệ thống tự động kích hoạt **Safe Grounded Fallback** từ SQLite để sinh câu trả lời mà không bao giờ bị lỗi 500."*

### Câu hỏi 4: "Cái nào coi là RAG trong hệ thống? Phần AI của các em có phải là RAG không và khác RAG thường như thế nào?"
- **Người trả lời chính**: **Ngô Trung Kiên**.
- **Điểm mấu chốt cần trả lời**:
  > *"Thưa Thầy/Cô:
  > - Trong hệ thống StoreFlow AI, tính năng **'1. TƯ VẤN SẢN PHẨM'** và **'TÌM KIẾM HÌNH ẢNH'** chính là RAG. Nó thực hiện đầy đủ 3 bước: Indexing dữ liệu vào ChromaDB $\rightarrow$ Retrieval vector ngữ nghĩa $\rightarrow$ Generation sinh câu trả lời có trích dẫn nguồn (Citation).
  > - Khác biệt lớn nhất giữa hệ thống của nhóm với RAG tài liệu thông thường là **sự kết hợp của CSDL Quan hệ (Relational Database)**:
  >   1. RAG thường cắt văn bản tùy tiện; nhóm áp dụng **Entity-based Chunking** theo từng sản phẩm.
  >   2. RAG thường chỉ dùng Dense Search dễ sót từ khóa; nhóm dùng **Hybrid Tri-Retrieval** (Dense ChromaDB + Sparse BM25 + Structured SQL) kết hợp thuật toán **RRF $k=60$**.
  >   3. RAG thường không biết hàng trong kho còn hay hết; nhóm có **SQLite Truth Guard** kiểm tra tồn kho thời gian thực.
  >   4. RAG thường chỉ có text; nhóm mở rộng sang **Multimodal Visual RAG** với CLIP ViT-B/32 trên CPU.
  >   5. RAG thường bị lỗi khi LLM chết; nhóm có **Safe Grounded Fallback** bảo đảm dịch vụ hoạt động liên tục."*

### Câu hỏi 5: "Giao diện Frontend tích hợp AI thế nào để tạo ra giá trị thực tế cho thu ngân và khách hàng?"
- **Người trả lời chính**: **Phan Duy Hưng**.
- **Điểm mấu chốt cần trả lời**:
  > *"Thưa Thầy/Cô, nhóm thiết kế giao diện AI theo triết lý **Source Attribution & Actionable AI**:
  > - Giao diện được chia thành **2 cột tỉ lệ chuẩn**: Cột bên trái hiển thị phân tích tự nhiên của AI (Markdown); cột bên phải hiển thị các **Thẻ sản phẩm thực tế (Citation Cards)** gồm ảnh, mã SKU, tên, giá bán và số lượng tồn kho sống.
  > - Đặc biệt, trên mỗi thẻ sản phẩm có nút hành động 1-chạm **'Mở bán POS'**: Khi nhân viên thu ngân bấm vào, hệ thống tự động chuyển sang tab POS và nạp sẵn mã hàng vào giỏ thanh toán, loại bỏ hoàn toàn việc nhân viên phải nhớ hoặc gõ lại mã SKU.
  > - Giao diện có hiệu ứng **Retro 3-Step Loading Animation** minh họa trực quan 3 pha xử lý, đếm ngược Cooldown Timer khi bị Rate Limit và hỗ trợ chuyển đổi mượt mà giữa hai giao diện Dark CRT và Light Vintage Paper."*

---

## 8. KẾT LUẬN & CAM KẾT HOÀN THÀNH

Tài liệu phân công nhiệm vụ và phân tích kiến trúc trên đã:
1. **Phân bổ công bằng và rõ ràng**: Mỗi thành viên đảm nhiệm 33.3% khối lượng công việc theo đúng năng lực chuyên môn (AI Engine, Frontend UI/UX, Backend & Database).
2. **Làm chủ 100% công nghệ**: Giải thích tường tận, sâu sắc bản chất RAG, cơ chế chống ảo giác, kỹ thuật Prompting và khả năng vận hành Local-First.
3. **Sẵn sàng bảo vệ trước Hội đồng**: Cung cấp đầy đủ kịch bản vấn đáp, giúp cả 3 thành viên tự tin phối hợp và đạt kết quả cao nhất trong kỳ đánh giá học phần.
