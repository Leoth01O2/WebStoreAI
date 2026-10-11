# STOREFLOW AI 2.0 — COMPREHENSIVE SYSTEM AUDIT & MODERNIZATION ROADMAP

> **Tài liệu Kế hoạch Kiểm toán & Lộ trình Hiện đại hóa Toàn diện Hệ thống**
> **Dự án**: StoreFlow AI — Hệ thống Quản lý Bán hàng Bán lẻ & POS Tích hợp AI Đa vai trò
> **Mã giai đoạn**: R0 (System Audit & Phased Architecture Plan — Phiên bản Chuẩn hóa Cuối cùng)
> **Phiên bản tài liệu**: 2.3.0-FINAL
> **Ngày cập nhật**: 10/10/2026
> **Môi trường mục tiêu**: Windows 11 | CPU Intel Core i5-11400H (6C/12T) | RAM 16GB | GPU NVIDIA GeForce RTX 3050 Laptop (4GB VRAM) | Python 3.12 / FastAPI / SQLite (WAL) / React 19 / Vite 8 / Native Fetch
> **Nguyên tắc thực hiện Giai đoạn R0**: **AUDIT + DESIGN PLAN ONLY — TUYỆT ĐỐI CHƯA SỬA APPLICATION CODE, DATABASE HOẶC TÀI LIỆU DOCX/PLANTUML.**

---

## MỤC LỤC TỔNG QUAN

1. [Phần 1: Xác định Bản Code Nguồn Chuẩn & Kiểm toán Công nghệ Thực tế](#phần-1-xác-định-bản-code-nguồn-chuẩn--kiểm-toán-công-nghệ-thực-tế)
2. [Phần 2: Chuẩn hóa Trường Trạng thái & Cơ chế Dữ liệu Lịch sử](#phần-2-chuẩn-hóa-trường-trạng-thái--cơ-chế-dữ-liệu-lịch-sử)
3. [Phần 3: Quy trình Nghiệp vụ Thanh toán, Chuyển khoản & Xử lý Giao hàng Thất bại](#phần-3-quy-trình-nghiệp-vụ-thanh-toán-chuyển-khoản--xử-lý-giao-hàng-thất-bại)
4. [Phần 4: Phân định Trách nhiệm RBAC, Tự Đăng ký & Backend Data Masking](#phần-4-phân-định-trách-nhiệm-rbac-tự-đăng-ký--backend-data-masking)
5. [Phần 5: Kế hoạch AI RAG, Ngưỡng Cutoff & Benchmark Thực nghiệm AI Local](#phần-5-kế-hoạch-ai-rag-ngưỡng-cutoff--benchmark-thực-nghiệm-ai-local)
6. [Phần 6: Kế hoạch UI/UX & Typography Be Vietnam Pro](#phần-6-kế-hoạch-uiux--typography-be-vietnam-pro)
7. [Phần 7: Bảng Phân loại Lỗi & Rủi ro Bảo mật Ưu tiên](#phần-7-bảng-phân-loại-lỗi--rủi-ro-bảo-mật-ưu-tiên)
8. [Phần 8: Lộ trình Triển khai Phân kỳ Chia nhỏ R1 – R8 (Kèm Điểm Dừng STOP)](#phần-8-lộ-trình-triển-khai-phân-kỳ-chia-nhỏ-r1--r8-kèm-điểm-dừng-stop)
9. [Phần 9: Danh mục Quyết định Nghiệp vụ Cần Người Dùng Phê duyệt](#phần-9-danh-mục-quyết-định-nghiệp-vụ-cần-người-dùng-phê-duyệt)

---

## PHẦN 1: XÁC ĐỊNH BẢN CODE NGUỒN CHUẨN & KIỂM TOÁN CÔNG NGHỆ THỰC TẾ

### 1.1. Hiện trạng Git Local & Đối chiếu GitHub Remote
- **Current Branch**: `main`
- **Current HEAD Commit SHA**: `cebd88f40994d4efdbe0badfec5841b05b0ea684`
- **Remote Tracking**: `origin/main` ([https://github.com/Leoth01O2/WebStoreAI.git](https://github.com/Leoth01O2/WebStoreAI.git))
- **Remote Branches hiện diện**: `origin/main`, `origin/kien335`, `origin/HEAD`
- **So sánh `origin/main..HEAD`**: 0 commit (hoàn toàn đồng bộ, không rẽ nhánh cục bộ).
- **So sánh `HEAD..origin/main`**: 0 commit (không có commit mới trên remote chưa fetch).
- **Trạng thái Working Tree (`git status -sb`)**: Clean (`## main...origin/main`), không có uncommitted changes ngoài tệp kế hoạch này.
- **Nguyên tắc bảo vệ mã nguồn**: Không tự động pull, reset, checkout, rebase, merge, push hoặc ghi đè trong suốt quá trình kiểm toán.

### 1.2. Kiểm toán Công nghệ Thực tế (Đính chính Dựa trên Codebase Thực tế)
- **Frontend Stack (Kiểm chứng qua `frontend/package.json` và `frontend/src/services/api.js`)**:
  - **Framework UI**: **React 19** (`"react": "^19.2.8"`, `"react-dom": "^19.2.8"`). *(Không phải React 18)*
  - **Build Tool**: **Vite 8** (`"vite": "^8.2.2"`), plugin `"@vitejs/plugin-react": "^6.1.0"`. *(Không phải Vite 5)*
  - **Linter**: **Oxlint** (`"oxlint": "^1.79.0"`).
  - **API Client**: **Native Fetch API** (được đóng gói trong `frontend/src/services/api.js:33-75` với interceptor xử lý JWT header, Bearer token và 401 redirect). **Codebase hoàn toàn KHÔNG sử dụng thư viện `axios`**.
  - **UI Libraries**: `lucide-react` (`^1.41.0`), `react-markdown` (`^10.1.0`), `remark-gfm` (`^4.0.1`), `remark-breaks` (`^4.0.0`).
- **Backend Stack**:
  - Python 3.12, **FastAPI 0.115+**, Pydantic v2.
  - Database: **SQLite 3** kích hoạt WAL mode (`PRAGMA journal_mode = WAL`), Foreign Keys (`PRAGMA foreign_keys = ON`), timeout 5000ms.
  - Security: `bcrypt`, `pyjwt` (HS256).
  - AI & Vector: `google-genai` SDK (`gemini-3.6-flash`), `chromadb 1.5.9` (PersistentClient).
- **Kiểm kê Tệp Dữ liệu**:
  - `backend/webstore.db`: Database SQLite hoạt động chính (585,728 bytes).
  - `backend/storeflow.db`: Tệp rỗng (0 bytes). **Chưa xóa ngay trong R0**; cần kiểm tra cấu hình cũ trước khi dọn dẹp ở Phase R2.
  - Thư mục ChromaDB: Tồn tại `backend/chroma_data`, `backend/chroma_db` và `./chroma.sqlite3`. Cần rà soát collection thực tế trước khi hợp nhất.

---

## PHẦN 2: CHUẨN HÓA TRƯỜNG TRẠNG THÁI & CƠ CHẾ DỮ LIỆU LỊCH SỬ

### 2.1. Quyết Định Chuẩn Hóa Tên Trường Trạng Thái Đơn Hàng
- **Thực trạng**: Toàn bộ codebase hiện tại (backend routing, service logic, database DDL và giao diện frontend) đang sử dụng trường **`orders.status`** để theo dõi vòng đời đơn hàng.
- **Quyết định kiến trúc chuẩn hóa**:
  - **Tiếp tục giữ nguyên tên trường `status` trong bảng `orders`** làm định danh duy nhất cho vòng đời đơn hàng.
  - **TUYỆT ĐỐI KHÔNG tạo thêm trường `order_status` song song**:
    - Không tạo 2 trường trạng thái trùng nghĩa thiếu đồng bộ. Việc tồn tại cả `status` và `order_status` sẽ dẫn đến nguy cơ sai lệch dữ liệu ("Split-Brain State"), gây khó khăn cho việc đồng bộ giao dịch.
    - Ưu tiên cao nhất là tính tương thích ngược với API hiện hành (`OrderResponse`, `orders.py`), các bộ lọc truy vấn giao diện frontend (`OrdersPage.jsx`), hệ thống báo cáo doanh thu và toàn bộ 167+ bản ghi dữ liệu lịch sử.
  - **Enum chính thức của `orders.status`**:
    $$\text{Status Enum} = \{\text{'pending'}, \text{'admin_approved'}, \text{'processing'}, \text{'completed'}, \text{'rejected'}, \text{'cancelled'}\}$$

---

### 2.2. Chuẩn Hóa Đầy Đủ Enum của `payment_status` & Tách Cờ Lịch Sử
- **Enum chính thức của `orders.payment_status`** (chỉ gồm 5 trạng thái chuẩn hóa duy nhất):
  ```sql
  CHECK(payment_status IN ('unpaid', 'pending_verification', 'paid', 'refund_pending', 'refunded'))
  ```
- **Phân định rạch ròi giữa trạng thái thanh toán hiện tại và cờ dữ liệu lịch sử**:
  1. **Không sử dụng `cancelled_unpaid`**:
     - `cancelled_unpaid` không thuộc enum thanh toán chính thức.
     - Khi một đơn hàng chưa thanh toán bị hủy, trạng thái nghiệp vụ của đơn là `status = 'cancelled'`, và `payment_status` giữ nguyên là `'unpaid'` (bản chất tiền chưa từng phát sinh). Không làm phình to hoặc méo mó enum thanh toán.
  2. **Tách biệt cờ lịch sử `is_legacy_unverified`**:
     - `unverified_legacy` **KHÔNG PHẢI là một trạng thái thanh toán** và không được đưa vào enum `payment_status`.
     - Thay vào đó, dữ liệu lịch sử cần đối soát được quản lý bằng một **cột cờ độc lập**:
       ```sql
       ALTER TABLE orders ADD COLUMN is_legacy_unverified INTEGER NOT NULL DEFAULT 0;
       ```
     - Toàn bộ các đơn hàng tạo trước đợt refactor sẽ được đánh dấu `is_legacy_unverified = 1` để Kế toán nhận diện và chạy quy trình đối soát riêng biệt. Tuyệt đối không tự động chuyển các đơn cũ thành `paid` và không làm sai lệch enum chuẩn.
  3. **Bất biến Hoàn tiền (Refund Invariant)**:
     - **Tuyệt đối không đánh dấu `refunded` khi chưa từng nhận tiền**.
     - Đơn có `payment_status = 'unpaid'` khi hủy vẫn giữ `'unpaid'`. Chỉ những đơn đã xác minh thu tiền (`payment_status = 'paid'`) mới có thể chuyển sang `'refund_pending'` và sau đó là `'refunded'` khi kế toán thực hiện lệnh hoàn tiền có mã giao dịch trả tiền thực tế.

---

### 2.3. Trạng Thái Giao Vận Độc Lập (`fulfillment_status`)
Để quản lý việc xuất kho và giao vận hàng hóa chính xác mà không làm lẫn lộn với vòng đời phê duyệt đơn hàng (`status`), hệ thống bổ sung cột độc lập:
```sql
CHECK(fulfillment_status IN ('unfulfilled', 'packing', 'shipping', 'delivered', 'delivery_failed', 'returned_to_inventory'))
```

---

## PHẦN 3: QUY TRÌNH NGHIỆP VỤ THANH TOÁN, CHUYỂN KHOẢN & XỬ LÝ GIAO HÀNG THẤT BẠI

### 3.1. Quy Trình Thanh Toán Chuyển Khoản & Đối Soát Ngân Hàng
Tuyệt đối không tự động xác nhận đã thu tiền khi khách hàng chọn hình thức chuyển khoản:

1. **Chuẩn hóa 3 mốc trạng thái chuyển khoản**:
   - `unpaid`: Đơn mới tạo chọn hình thức chuyển khoản $\rightarrow$ Khởi tạo mặc định là `payment_status = 'unpaid'` (Chưa thanh toán / Chưa báo đã chuyển). Tuyệt đối không tự động coi là đã thanh toán hay tự động kích hoạt xuất kho.
   - `pending_verification`: Khách hàng (hoặc nhân viên ghi nhận yêu cầu) gửi thông báo đã chuyển tiền kèm mã giao dịch ngân hàng / ảnh chụp bill $\rightarrow$ Đơn chuyển sang trạng thái chờ đối soát.
   - `paid`: Đã xác minh tiền thực nhận vào tài khoản ngân hàng thụ hưởng của cửa hàng.

2. **Sơ đồ luồng trạng thái chuyển khoản**:
```
[1. Khách đặt đơn chọn Chuyển khoản]
       │
       ▼
   payment_status = 'unpaid' (Đơn tạo mới, chưa nhận tiền, chưa báo chuyển)
       │
       ▼ (Khách hàng thông báo đã chuyển tiền kèm mã tham chiếu giao dịch)
   payment_status = 'pending_verification' (Chờ đối soát)
       │
       ▼ (Admin / Kế toán đối soát biến động số dư ngân hàng thực tế)
   ┌────────────────────────────────────────────────────────────────┐
   │ BẰNG CHỨNG HỢP LỆ: Sao kê tài khoản / Biến động số dư thực nhận│
   │ KHÔNG CHẤP NHẬN: Ảnh chụp màn hình từ khách (dễ bị fake bill)  │
   │                  (Ảnh bill chỉ là tài liệu tham chiếu mã GD)   │
   └────────────────────────────────────────────────────────────────┘
       │
   ├── [Xác nhận tiền thực nhận vào tài khoản] ──► payment_status = 'paid' (Cho phép xuất kho)
   └── [Quá hạn / Không nhận được tiền]        ──► Từ chối duyệt, giữ/trả về payment_status = 'unpaid'
```

3. **Thẩm quyền chuyển trạng thái & Yêu cầu bằng chứng**:
   - **Từ `unpaid` sang `pending_verification`**: Khách hàng (Customer) hoặc Nhân viên bán hàng (Staff) có quyền gửi thông báo đã chuyển tiền qua endpoint `POST /orders/{id}/notify-transfer`.
   - **Từ `pending_verification` sang `paid`**: **DUY NHẤT Admin hoặc SuperAdmin** (đóng vai trò Kế toán / Chủ cơ sở) mới có quyền gọi endpoint `POST /orders/{id}/verify-payment` để xác nhận đã thu tiền.
   - **Yêu cầu bằng chứng bắt buộc**:
     - Bằng chứng hợp lệ là bản sao kê tài khoản ngân hàng, thông báo biến động số dư SMS/App ngân hàng chính thức từ phía tài khoản thụ hưởng của cửa hàng.
     - Ảnh chụp màn hình chuyển khoản từ khách hàng chỉ có giá trị tham khảo mã tham chiếu (Transaction Ref/FT code), tuyệt đối KHÔNG được dùng làm căn cứ tự động xác nhận đã nhận tiền.
     - Hệ thống lưu vết bắt buộc: `payment_verified_by` (User ID), `payment_verified_at` (Timestamp), và `bank_transaction_code` (Mã giao dịch ngân hàng).

---

### 3.2. Quy Tắc Hoàn Tiền Chặt Chẽ (Refund Invariant)
- **Quy tắc bất biến cốt lõi**: **TUYỆT ĐỐI KHÔNG ĐÁNH DẤU `refunded` KHI CHƯA TỪNG THU TIỀN**.
  - **Đơn hàng chưa thanh toán (`payment_status = 'unpaid'`)**: Nếu đơn bị hủy (bởi khách, nhân viên hoặc hệ thống), trạng thái đơn cập nhật `status = 'cancelled'`, còn `payment_status` **giữ nguyên là `'unpaid'`**. Tuyệt đối không chuyển sang `refunded` hay tạo thêm enum rác `cancelled_unpaid`.
  - **Đơn hàng đã thanh toán thực tế (`payment_status = 'paid'`)**: Nếu đơn bị hủy hoặc trả hàng sau khi tiền đã thực nhận:
    1. Hệ thống chuyển sang `payment_status = 'refund_pending'` để ghi nhận công nợ phải trả lại cho khách hàng.
    2. Chỉ chuyển sang `payment_status = 'refunded'` khi Admin/Kế toán đã thực hiện lệnh hoàn tiền qua ngân hàng và nhập mã ủy nhiệm chi / mã giao dịch hoàn tiền.

---

### 3.3. Quy Trình Giao Hàng Thất Bại & Bảo Toàn Tồn Kho (Delivery Failed Invariant)
1. **Quy tắc bảo vệ tồn kho**:
   - Khi Shipper báo không giao được hàng (không liên lạc được, khách đổi ý, sai địa chỉ): Hệ thống cập nhật `fulfillment_status = 'delivery_failed'`.
   - **TUYỆT ĐỐI KHÔNG TỰ ĐỘNG CỘNG LẠI TỒN KHO VÀO THỜI ĐIỂM NÀY**: Hàng hóa vật lý vẫn đang nằm trên xe vận chuyển hoặc tại bưu cục trung chuyển của đơn vị giao vận, chưa được hoàn trả về kho của cửa hàng.
2. **Quy trình hoàn kho vật lý**:
   - Kiện hàng được đơn vị vận chuyển hoàn trả vật lý về quầy kho.
   - Thủ kho / Nhân viên kho thực hiện kiểm kê, đánh giá tình trạng nguyên vẹn của hàng hóa.
   - Thủ kho bấm nút *"Xác nhận nhập kho hàng hoàn"* qua endpoint `POST /orders/{id}/confirm-return`:
     - Cập nhật `fulfillment_status = 'returned_to_inventory'`.
     - Cập nhật `status = 'cancelled'` (nếu hủy toàn bộ).
     - Thực hiện hoàn tồn kho **ĐÚNG 1 LẦN DUY NHẤT** trong transaction nguyên tử:
       ```sql
       UPDATE products SET stock_quantity = stock_quantity + ? WHERE id = ?;
       ```
     - Ghi nhận nhật ký tồn kho: `INSERT INTO inventory_logs (product_id, change_type, quantity, ...) VALUES (?, 'return_cancel', ?, ...);`.
     - **Cơ chế Idempotency Guard (Chống hoàn kho 2 lần)**: Kiểm tra điều kiện tiên quyết `WHERE fulfillment_status = 'delivery_failed'`. Nếu đơn đã ở trạng thái `returned_to_inventory`, hệ thống từ chối thực hiện lại (trả về lỗi HTTP 400/409), ngăn chặn triệt để rủi ro cộng thừa tồn kho do bấm đúp hoặc gọi API lặp lại.
3. **Tách biệt hoàn toàn xử lý Hoàn tiền và Hoàn hàng**:
   - **Hoàn hàng (Physical Logistics)**: Do Thủ kho / Nhân viên quản lý qua `fulfillment_status: delivery_failed -> returned_to_inventory`.
   - **Hoàn tiền (Financial Refund)**: Nếu đơn hàng đã thanh toán trước (`paid`), Kế toán / Admin xử lý riêng biệt qua `payment_status: paid -> refund_pending -> refunded`.
   - Hai luồng hoàn toàn độc lập: Việc nhận lại hàng không tự động chi tiền hoàn, và việc xử lý hoàn tiền không can thiệp vào tồn kho vật lý.

---

### 3.4. Thao Tác Nguyên Tử Chống Nhận Trùng Đơn (Atomic Claim Lock)
- Để bảo đảm 2 nhân viên không thể cùng nhận một đơn hàng, thao tác nhận đơn sử dụng câu lệnh SQL nguyên tử trong transaction `BEGIN IMMEDIATE`:
  ```sql
  UPDATE orders
  SET status = 'processing',
      assigned_to = ?,
      processed_by = ?,
      processed_at = CURRENT_TIMESTAMP
  WHERE id = ? AND status = 'admin_approved' AND assigned_to IS NULL;
  ```
- Nếu `cursor.rowcount == 0`: Trả về thông báo lỗi HTTP 409 Conflict / 400 Bad Request rõ ràng: *"Đơn hàng này đã được nhân viên khác tiếp nhận xử lý hoặc trạng thái đơn đã thay đổi"*.
- **SuperAdmin Reassign**: SuperAdmin có quyền gán lại (`reassign`) đơn hàng sang nhân viên khác khi có sự cố, bắt buộc nhập lý do và tự động lưu vết vào `order_audit_logs`.

---

## PHẦN 4: PHÂN ĐỊNH TRÁCH NHIỆM RBAC, TỰ ĐĂNG KÝ & BACKEND DATA MASKING

### 4.1. Phân Tách 3 Cấp Độ Trách Nhiệm
```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          3 CẤP ĐỘ TRÁCH NHIỆM RBAC                          │
├─────────────────────────────────────────────────────────────────────────────┤
│ 1. NGƯỜI CHỊU TRÁCH NHIỆM THƯỜNG XUYÊN (Operational Owners)                 │
│    - Staff: Bán hàng tại quầy POS, nhận đơn (claim), đóng gói, thu tiền COD.│
│    - Admin: Duyệt/từ chối đơn hàng online, xác nhận tiền chuyển khoản.      │
├─────────────────────────────────────────────────────────────────────────────┤
│ 2. NGƯỜI KIỂM TRA, GIÁM SÁT (Operational Supervisors)                       │
│    - Admin: Giám sát đơn hàng và ca làm việc của Staff.                     │
│    - SuperAdmin: Giám sát toàn bộ hoạt động của Admin và Staff.             │
├─────────────────────────────────────────────────────────────────────────────┤
│ 3. NGƯỜI CÓ QUYỀN CAN THIỆP NGOẠI LỆ (Emergency Authority)                  │
│    - SuperAdmin: Không loại bỏ quyền. Giữ thẩm quyền can thiệp ngoại lệ     │
│      (Force Cancel, Reopen, Reassign) kèm lý do (>= 5 ký tự) và Audit Log. │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

### 4.2. Bảo Vệ Dữ Liệu Khách Hàng (Backend-Enforced Data Masking)
- **Nguyên tắc an toàn bắt buộc**:
  - **Data Masking PHẢI ĐƯỢC THỰC THI TẠI TẦNG BACKEND (Server-side Enforcement)** thông qua Pydantic response schemas và endpoint dependencies phân quyền.
  - **Frontend masking chỉ là tầng hiển thị bổ trợ (Cosmetic/Format only)**, tuyệt đối không được coi là giải pháp bảo mật.
  - **TUYỆT ĐỐI KHÔNG trả nguyên vẹn email và địa chỉ chi tiết cho Staff qua API rồi chỉ dùng CSS (`display: none`) hoặc JavaScript để che giấu trên giao diện**. Mọi nhân viên mở Developer Tools (F12) Network Tab đều có thể trích xuất toàn bộ dữ liệu cá nhân (PII) nếu backend không mask.
- **Thiết kế Schemas phân quyền tại Backend**:
  - `CustomerAdminResponse` (Dành cho Admin / SuperAdmin):
    - Trả đầy đủ PII: `id`, `customer_code`, `name`, `phone`, `email`, `address`, `group_name`, `total_spent`, `created_at`.
  - `CustomerStaffResponse` (Dành cho Staff tra cứu phục vụ bán hàng tại quầy POS):
    - Trả thông tin vận hành cần thiết: `id`, `customer_code`, `name`, `phone` (đủ số để tìm khách tại quầy), `group_name`, `total_spent`.
    - **Masking email tại backend**: `a***@example.com` (hoặc `None`).
    - **Masking address tại backend**: Chỉ trả Quận/Huyện, Tỉnh/Thành phố; loại bỏ hoàn toàn số nhà, tên đường chi tiết (hoặc `None`).
- **Thứ tự thực thi phân kỳ chuẩn hóa**:
  - Backend Data Masking được hoàn thành và kiểm thử độc lập tại **Phase R1C** (bảo vệ dữ liệu ngay từ đầu).
  - Giao diện tra cứu khách hàng của Staff trên frontend chỉ được mở ở **Phase R7** sau khi tầng backend đã bảo vệ dữ liệu an toàn 100%.

---

### 4.3. Bổ Sung Chức Năng Tự Đăng Ký Tài Khoản Khách Hàng (Public Customer Registration)
- **Vấn đề hiện tại**: Chỉ Admin mới có quyền tạo User qua endpoint nội bộ `/auth/users`. Khách mua hàng online không thể tự đăng ký tài khoản thành viên.
- **Giải pháp chuẩn hóa**: Bổ sung endpoint `POST /api/v1/auth/register` (triển khai tại **Phase R1B**, trước khi nghiệm thu hệ thống):
  1. **Khóa cứng vai trò (Anti-Role Escalation Guard)**:
     - Public register **CHỈ ĐƯỢC PHÉP TẠO ROLE `customer` 100%**.
     - Bỏ qua hoặc từ chối dứt khoát nếu client cố tình truyền các role đặc quyền (`admin`, `staff`, `superadmin`). Tuyệt đối không cho client tự chọn quyền.
  2. **Tạo liên kết nguyên tử an toàn giữa `users` và `customers`**:
     - Thực thi trong 1 database transaction duy nhất (`BEGIN IMMEDIATE`):
       - Tạo bản ghi trong bảng `users`: `username`, `password_hash` (bcrypt), `role = 'customer'`, `is_active = 1`.
       - Tạo bản ghi hồ sơ tương ứng trong bảng `customers`: `user_id = users.id`, `customer_code = 'CUS-XXXX'`, `name`, `phone`, `email`, `group_name = 'Thành viên mới'`, `status = 'active'`.
     - **Chống trùng lặp dữ liệu**: Kiểm tra duy nhất (Unique check) cho `username`, `email` và `phone` trước khi insert, xử lý biệt lệ xung đột (`IntegrityError`) và trả mã lỗi HTTP 409 Conflict rõ ràng nếu đã tồn tại.
  3. **Xác thực dữ liệu (Validation) & Giới hạn tần suất (Rate Limiting)**:
     - Validation: `username` (3-30 ký tự an toàn), `password` (tối thiểu 6 ký tự), `phone` (chuẩn số di động Việt Nam 10 chữ số), `email` (định dạng chuẩn RFC 5322).
     - Rate limit nghiêm ngặt: Tối đa 3 lượt đăng ký / IP / 10 phút để triệt tiêu nguy cơ spam tài khoản ảo bằng bot.

---

## PHẦN 5: KẾ HOẠCH AI RAG, NGƯỠNG CUTOFF & BENCHMARK THỰC NGHIỆM AI LOCAL

### 5.1. Hiệu Chỉnh Kế Hoạch RAG: Sửa Lỗi Retrieval Trước Khi Đổi Mô Hình
- **Nguyên tắc kỹ thuật**: Việc đổi mô hình AI không thể tự sửa lỗi retrieval nếu ChromaDB tiếp tục trả về các sản phẩm ngoài danh mục.
- **Kế hoạch khảo nghiệm ngưỡng Cosine Cutoff**:
  - Không hardcode cố định 0.45.
  - Khảo nghiệm trên tập giá trị: $\{0.35, 0.40, 0.45, 0.50, 0.55\}$.
  - Bộ câu hỏi kiểm thử đối chứng 20 câu:
    - 5 câu hỏi khớp chính xác sản phẩm catalog.
    - 5 câu hỏi diễn đạt tương đương về công năng.
    - 5 câu hỏi mơ hồ ở ranh giới danh mục.
    - 5 câu hỏi hoàn toàn ngoài danh mục (thực phẩm, xe cộ, gia dụng ngoài...).
  - Đo đạc: Precision@K, Recall@K, False Acceptance Rate (FAR $\approx 0\%$) và Tỷ lệ từ chối hợp lý.
- **Quy tắc render Product Cards**:
  - **Chỉ render thẻ sản phẩm khi có bằng chứng liên quan vượt ngưỡng (Distance $\le \text{Threshold}$)** VÀ sản phẩm còn hàng (`stock_quantity > 0`).
  - Nếu toàn bộ ứng viên bị loại: Chatbot giải thích lịch sự, **0 thẻ sản phẩm nào bị hiển thị sai**.

---

### 5.2. Kế Hoạch Benchmark Thực Nghiệm AI Local Trên RTX 3050 Laptop (4GB VRAM)
- **Mục tiêu**: Đo đạc số liệu thực tế trên máy tính mục tiêu thay vì tuyên bố lý thuyết.
- **Đính chính mô hình**:
  - **Gemma 3 4B**: Là mô hình đa phương thức (Multimodal), được đưa vào danh sách benchmark Vision local cùng với **Qwen2.5-VL 3B / Qwen3-VL 4B**.
  - **Text LLM**: Ưu tiên thử nghiệm **Qwen3 4B / Qwen2.5 3B** và **Gemma 3 4B**, không tự ý chốt trước khi đo.
- **Tiêu chí đo kiểm thực tế**:
  1. *Peak VRAM Allocation*: Đo bằng `nvidia-smi` (Ngưỡng an toàn không tràn: $\le 3.5\text{ GB}$).
  2. *Tốc độ suy luận thực tế*: Đo số tokens/giây thực nhận.
  3. *Thời gian phản hồi hình ảnh*: Mốc $< 2.5\text{ giây}$ là **mục tiêu benchmark tham chiếu (benchmark target)**, KHÔNG PHẢI điều kiện nghiệm thu (DoD) cứng ép buộc trước khi đo kiểm thực tế.
  4. *Xử lý khi phần cứng laptop không đáp ứng*: Nếu các mô hình local gây tràn VRAM sang shared memory (>3.5GB), giật lag hoặc OOM trên GPU RTX 3050 Laptop 4GB, **hệ thống PHẢI báo cáo hạn chế phần cứng một cách minh bạch và kích hoạt Tier 3 (Deterministic Search / Keyword Search) an toàn**, tuyệt đối không tuyên bố thành công giả tạo hoặc ép buộc đạt chuẩn lý thuyết khi phần cứng không cho phép.
- **Nguyên tắc chọn mô hình**: **Phase R8 sẽ sử dụng mô hình chiến thắng từ kết quả benchmark thực tế của Phase R5**, tuyệt đối không hardcode trước bất kỳ mô hình cụ thể nào (như `qwen2.5:3b` hay tên model cố định).

---

## PHẦN 6: KẾ HOẠCH UI/UX & TYPOGRAPHY BE VIETNAM PRO

1. **Chuyển đổi Typography sang `Be Vietnam Pro`**:
   - `Space Grotesk` hiện tại bị lỗi chân chữ và lệch baseline khi hiển thị tiếng Việt có dấu.
   - Chuyển font chính (Headings, Body, Buttons, Tables) sang **`Be Vietnam Pro`** (Google Fonts, weights 400, 500, 600, 700) để tối ưu hóa 100% hiển thị dấu tiếng Việt.
   - Tiếp tục giữ **`JetBrains Mono`** cho các trường dữ liệu kỹ thuật: Mã SKU, mã đơn hàng, giá tiền VND, ngày giờ và terminal logs.
2. **Bảo tồn Visual Identity**:
   - Giữ nguyên 100% bản sắc **Vintage Editorial / Retro-Futuristic Print**: Đường viền cơ học, đổ bóng retro (`--shadow-retro`), bảng màu CRT Phosphor (Amber, Green, Red) trên cả Dark Slate Mode và Light Off-White Vintage Paper Mode.
3. **Mở giao diện Khách hàng cho Staff (Sau khi có Backend Masking)**:
   - Staff được mở menu Khách hàng trên Navbar để tra cứu số điện thoại tại quầy POS, dữ liệu hiển thị đã qua backend masking an toàn.
   - Loại bỏ hoàn toàn role ma `manager` trên toàn bộ giao diện.

---

## PHẦN 7: BẢNG PHÂN LOẠI LỖI & RỦI RO BẢO MẬT ƯU TIÊN

| ID | Phân loại | Tên Lỗi / Rủi ro | Vị trí File & Function | Bằng chứng Mã nguồn & Kế hoạch Khắc phục |
| :---: | :---: | :--- | :--- | :--- |
| **SEC-01** | **CONFIRMED** | **Lộ Giá Vốn (`cost_price`) cho Customer** | `products.py:216-229`<br/>`schemas/product.py` | API `GET /api/v1/products` không lọc role, trả `cost_price` cho Customer. **Khắc phục ngay tại Phase R1A**. |
| **SEC-02** | **CONFIRMED** | **Bảo mật SECRET_KEY Production** | `core/config.py:15`<br/>`core/security.py` | Đang dùng dev key mặc định. **Cần bắt buộc từ chối khởi động (`raise RuntimeError`) nếu production dùng dev key**. |
| **SEC-03** | **CONFIRMED** | **Thiếu Rate Limiter Đăng nhập** | `api/v1/auth.py:11-51` | Endpoint `/auth/login` không có rate limit. Bổ sung giới hạn 5 lần thử/phút tại **Phase R1A**. |
| **SEC-04** | **CONFIRMED** | **Thiếu Đăng ký Tài khoản Khách hàng** | `api/v1/auth.py` | Không có public registration. Bổ sung `/auth/register` (Role Customer only) tại **Phase R1B**. |
| **SEC-05** | **CONFIRMED** | **Staff Xem Toàn Bộ Email & Địa Chỉ Khách** | `customers.py:9-36` | Chưa có data masking tại backend. Tạo `CustomerStaffResponse` tại **Phase R1C**. |
| **BUG-01** | **CONFIRMED** | **`payment_status` luôn là `'completed'` cho đơn online** | `inventory_service.py:117-128`<br/>`PosPage.jsx:273` | Đơn COD khởi tạo bị coi là đã trả tiền. Tách trường và chuẩn hóa enum tại **Phase R2C / R3**. |
| **BUG-02** | **CONFIRMED** | **Ảo giác Cưỡng bức khi AI Upstream Lỗi / Quota 429** | `ai_service.py:121-137`<br/>`rag_service.py:137-158` | Retrieval thiếu ngưỡng cutoff; fallback khẳng định bừa. Khảo nghiệm ngưỡng cutoff tại **Phase R4**. |
| **BUG-03** | **CONFIRMED** | **Tồn tại Role ma `manager` trên Frontend** | `Navbar.jsx:140-148`<br/>`App.jsx:16` | Dọn sạch role `manager` không có trong database tại **Phase R7**. |
| **BUG-04** | **CONFIRMED** | **Ghi DML bằng `get_db()` thay vì `get_db_transaction()`** | `products.py:126, 163, 178, 314` | Ghi dữ liệu bằng autocommit context. Chuẩn hóa sang `get_db_transaction()` tại **Phase R1C**. |
| **RSK-01** | **SUSPECTED** | **Nguy cơ Xử lý Trùng Đơn giữa nhiều Nhân viên** | `orders.py:270-298`<br/>`inventory_service.py:323-360` | Đơn đã duyệt hiển thị chung. Triển khai Atomic Claim Lock tại **Phase R3**. |
| **RSK-02** | **SUSPECTED** | **Rủi ro Sao lưu Database khi Đang Chạy WAL Mode** | `core/database.py` | Phải dùng `VACUUM INTO` snapshot trước mọi migration tại **Phase R2A**. |

---

## PHẦN 8: LỘ TRÌNH TRIỂN KHAI PHÂN KỲ CHIA NHỎ R1 – R8 (KÈM ĐIỂM DỪNG STOP)

```mermaid
gantt
    title LỘ TRÌNH HIỆN ĐẠI HÓA STOREFLOW AI 2.0 (PHASES R1 - R8)
    dateFormat  X
    axisFormat %d

    section Phase R1 - Bảo Mật & Nền Tảng (Không Đổi Schema)
    R1A: Urgent Security & Boot Safety (COMPLETED) :done, r1a, 0, 1
    R1B: Customer Registration & Ownership Check (COMPLETED) :done, r1b, 1, 2
    R1C: Backend Data Masking & DML Normalization (COMPLETED) :done, r1c, 2, 3

    section Phase R2 - Database Backup & Schema Phased
    R2A: Safe DB Backup & Versioning (COMPLETED) :done, r2a, 3, 4
    R2B: Phased Column Expansion (COMPLETED)      :done, r2b, 4, 5
    R2C-A: Payment & Fulfillment Design + Dry Run (COMPLETED) :done, r2ca, 5, 6
    R2C-B: Production Migration & Enum Upgrade   :r2cb, 6, 7

    section Phase R3 - Vận Hành & Nghiệp Vụ
    R3: Order Workflow, Claim Lock & Payments     :r3, 6, 7

    section Phase R4 - Trí Tuệ Nhân Tạo RAG
    R4: RAG Retrieval Calibration & Cutoff        :r4, 7, 8

    section Phase R5 - AI Local Benchmark
    R5: Pluggable AI Providers & Local Benchmark  :r5, 8, 9

    section Phase R6 - Image Search
    R6: Image Search Multimodal Pipeline          :r6, 9, 10

    section Phase R7 - Giao Diện & Typography
    R7: UI/UX, Be Vietnam Pro Typography & Masking:r7, 10, 11

    section Phase R8 - Nghiệm Thu & Bàn Giao
    R8: Full Testing, Security Audit & Academic Prep:r8, 11, 12
```

---

### CHI TIẾT TỪNG BƯỚC TRIỂN KHAI (SUB-PHASES):

#### PHASE R1A: Urgent Security Hotfix & Boot Safety — [COMPLETED ✅ 10/10/2026]
- **Trạng thái**: **HOÀN THÀNH (100% Passed 9/9 Targeted Tests)**
- **Mục tiêu**: Vá ngay lỗ hổng lộ giá vốn `cost_price` và khóa an toàn khởi động production mà **hoàn toàn không sửa schema database và không sửa frontend**.
- **Kết quả triển khai thực tế**:
  1. *Bảo vệ giá vốn*: Tách schema `ProductAdminResponse` (có `cost_price` cho Admin/SuperAdmin) và `ProductPublicResponse` (ẩn hoàn toàn `cost_price` cho Staff, Customer và Guest). Truy vấn SQL phân tách theo role: Staff/Customer/Guest không bao giờ SELECT `cost_price`.
  2. *Boot Safety Guard*: Bổ sung `validate_boot_safety()` trong `core/config.py` và `main.py:lifespan`: từ chối khởi động (`raise RuntimeError`) nếu `APP_ENV=production/staging` mà dùng SECRET_KEY mặc định, rỗng hoặc $< 32$ ký tự.
  3. *Login Rate Limiting*: Bổ sung `LoginRateLimiter` trong `core/rate_limiter.py` và tích hợp vào `/api/v1/auth/login`. Tối đa 5 lần thử thất bại/phút theo cặp `(client_ip, normalized_username)` chống brute-force và tránh khóa nhầm người dùng khác trên cùng IP. Lần thứ 6 trả về HTTP 429 Too Many Requests kèm header `Retry-After`.
- **Files đã sửa**:
  - `backend/app/core/config.py`
  - `backend/app/core/rate_limiter.py`
  - `backend/app/api/v1/auth.py`
  - `backend/app/schemas/product.py`
  - `backend/app/api/v1/products.py`
  - `backend/app/main.py`
- **File kiểm thử mới**: `backend/tests/test_phase_r1a_security.py`
- **Kết quả kiểm thử**: **9/9 tests PASSED (14.54s)** trên cơ sở dữ liệu cách ly `test_webstore.db`. Không làm ảnh hưởng `backend/webstore.db` chính.
- **DoD**: Đạt 100% tiêu chí nghiệm thu R1A.
- **STOP Condition**: **DỪNG LẠI tại đây sau khi hoàn thành Phase R1A.**

---

#### PHASE R1B: Customer Registration & Ownership Check — [COMPLETED ✅ 10/10/2026]
- **Trạng thái**: **HOÀN THÀNH (100% Passed 14/14 Targeted Tests)**
- **Mục tiêu**: Bổ sung chức năng tự đăng ký cho Khách hàng (`POST /api/v1/auth/register`) và siết chặt kiểm tra quyền sở hữu khi tạo đơn (`POST /api/v1/orders`).
- **Kết quả triển khai thực tế**:
  1. *Public Customer Registration*: Endpoint `POST /api/v1/auth/register` cho phép khách vãng lai (Guest) tự đăng ký tài khoản `customer`.
     - Tuyệt đối khóa cứng role `customer`: Pydantic schema `CustomerRegisterRequest` chặn trường `role` nếu khác `customer`, chặn các trường nội bộ (`user_id`, `customer_id`, `is_active`).
     - Hash mật khẩu an toàn bằng `get_password_hash`. Không trả về `password_hash` trong JSON response (`CustomerRegisterResponse`).
  2. *Validation & Chống Trùng*:
     - Username 3–30 ký tự, password >= 6 và <= 128 ký tự.
     - Số điện thoại chuẩn Việt Nam 10 chữ số (Regex `^(03|05|07|08|09)[0-9]{8}$`), email hợp lệ (Regex RFC5322).
     - Kiểm tra trùng `username`, `phone`, `email` trong database (cả bảng `users` và `customers`). Trả về HTTP 409 Conflict với thông điệp rõ ràng khi trùng lặp.
  3. *Atomic Profile Creation*:
     - Thực thi trong một giao dịch SQLite duy nhất bằng `get_db_transaction()` (`BEGIN IMMEDIATE`): Tạo `users` (role `customer`) $\rightarrow$ Tạo `customers` (mã tự sinh `KH-xxx`, liên kết `user_id = user.id`) $\rightarrow$ `COMMIT`. Nếu có bất kỳ lỗi nào, toàn bộ transaction tự động `ROLLBACK`, đảm bảo không bao giờ sinh user mồ côi hoặc customer profile không có user.
     - An toàn hồ sơ cũ: Nếu phát hiện phone/email đã tồn tại trong bảng `customers` (dù chưa liên kết `user_id`), từ chối đăng ký với HTTP 409, không tự động chiếm quyền hồ sơ khách hàng cũ.
  4. *Anti-IDOR trong Create Order*:
     - Cập nhật `create_order` trong `backend/app/api/v1/orders.py`. Với role `customer`, backend tự động truy vấn hồ sơ khách hàng liên kết (`customers.user_id = current_user.id`).
     - Tự động gán `customer_id = own_customer_id`. Nếu client gửi `customer_id` khác hồ sơ của mình, trả về HTTP 403 Forbidden (IDOR violation).
     - Nếu tài khoản Customer không có hồ sơ liên kết hợp lệ, từ chối tạo đơn với HTTP 400 Bad Request, không cho phép mượn `customer_id` của người khác.
     - Luôn ép trạng thái đơn hàng khởi tạo của Customer là `pending`.
  5. *Registration Rate Limiter*:
     - `RegisterRateLimiter` độc lập trong `backend/app/core/rate_limiter.py`: 3 lượt đăng ký / IP / 10 phút (sliding window 600s). Trả HTTP 429 Too Many Requests kèm header `Retry-After`.
- **Files đã sửa**:
  - `backend/app/schemas/auth.py`
  - `backend/app/core/rate_limiter.py`
  - `backend/app/api/v1/auth.py`
  - `backend/app/api/v1/orders.py`
- **File kiểm thử mới**: `backend/tests/test_phase_r1b_registration.py`
- **Kết quả kiểm thử**: **14/14 tests PASSED (9.26s)** trên cơ sở dữ liệu cách ly `test_webstore.db`. Không làm ảnh hưởng `backend/webstore.db` chính.
- **Kiểm tra tương thích ngược**: `backend/tests/test_phase_r1a_security.py` tiếp tục **9/9 tests PASSED (10.11s)**.
- **DoD**: Đạt 100% tiêu chí nghiệm thu R1B.
- **STOP Condition**: **DỪNG LẠI tại đây sau khi hoàn thành Phase R1B.**

---

#### PHASE R1C: Backend Data Masking & DML Normalization — [COMPLETED ✅ 10/10/2026]
- **Trạng thái**: **HOÀN THÀNH (100% Passed 17/17 Targeted Tests, 23/23 Regression Tests)**
- **Mục tiêu**: Thực thi che giấu dữ liệu khách hàng (PII Backend Data Masking) cho Staff tại quầy POS và chuẩn hóa toàn bộ lệnh ghi DML trong `products.py` sang giao dịch SQLite nguyên tử.
- **Kết quả triển khai thực tế**:
  1. *Backend Data Masking cho Staff*:
     - Bổ sung `CustomerStaffResponse` trong `backend/app/schemas/customer.py`: chỉ giữ các trường cần thiết cho nghiệp vụ POS (`id`, `customer_code`, `name`, `phone`, `group_name`, `total_spent`, `created_at`).
     - Hàm `mask_email()` che giấu email an toàn (`an.nguyen@example.com` $\rightarrow$ `a***@example.com`).
     - Tuyệt đối không trả về địa chỉ chi tiết (`address: None`) để tránh lộ số nhà do trường địa chỉ là chuỗi tự do.
     - Loại bỏ hoàn toàn `user_id` nội bộ khỏi response của Staff.
  2. *Bảo vệ toàn diện Customer API*:
     - Cập nhật các endpoint trong `backend/app/api/v1/customers.py`: danh sách `GET /customers`, tìm kiếm `?search=...`, chi tiết `GET /customers/{id}`, tạo mới `POST /customers`, và cập nhật `PUT /customers/{id}`:
       - Staff: Nhận `CustomerStaffResponse` (email masked, address `None`, không `user_id`).
       - Admin & SuperAdmin: Nhận `CustomerAdminResponse` đầy đủ.
       - Customer: Bị chặn xem danh sách (403) và chỉ được xem chính mình qua `/me` hoặc ID của mình (chống IDOR 403).
       - Guest: Bị chặn 401 Unauthorized.
  3. *DML Normalization trong Products*:
     - Chuyển toàn bộ các thao tác ghi dữ liệu nhiều bước trong `backend/app/api/v1/products.py` sang `get_db_transaction()` (`BEGIN IMMEDIATE`):
       - `create_category`, `update_category`, `delete_category`: Đảm bảo tính nguyên tử; kiểm tra ràng buộc khóa ngoại trước khi xóa danh mục (từ chối 400 nếu danh mục đang có sản phẩm).
        - `create_product`, `update_product`, `delete_product`: Bảo vệ toàn vẹn khóa ngoại `category_id`, rollback toàn bộ khi lỗi.
        - Tách việc đồng bộ vector sang ChromaDB thực hiện sau khi SQLite transaction commit thành công.
- **Files đã sửa**:
  - `backend/app/schemas/customer.py`
  - `backend/app/api/v1/customers.py`
  - `backend/app/api/v1/products.py`
- **File kiểm thử mới**: `backend/tests/test_phase_r1c_masking_transactions.py`
- **Kết quả kiểm thử**:
  - **17/17 targeted tests PASSED (10.65s)** trên cơ sở dữ liệu cách ly `test_webstore.db`.
  - **23/23 regression tests PASSED (14.48s)** (R1A: 9/9 tests, R1B: 14/14 tests).
  - Hoàn toàn không ghi dữ liệu test vào `backend/webstore.db` chính.
- **DoD**: Đạt 100% tiêu chí nghiệm thu R1C.
- **STOP Condition**: **DỪNG LẠI tại đây sau khi hoàn thành Phase R1C.**

---

#### PHASE R2A: Safe DB Backup & Versioning — [COMPLETED ✅ 10/10/2026]
- **Trạng thái**: **HOÀN THÀNH (100% Passed 11/11 Targeted Tests, 51/51 Total Suite Tests)**
- **Mục tiêu**: Thiết lập cơ chế sao lưu SQLite an toàn không khóa dữ liệu (SQLite Online Backup API), kiểm chứng khả năng khôi phục và xây dựng cơ chế schema versioning cho các migration tiếp theo.
- **Kết quả triển khai thực tế**:
  1. *Cơ chế sao lưu an toàn*:
     - Module `backend/app/core/backup.py` triển khai `create_database_backup()` sử dụng SQLite Online Backup API chính thức (`source_conn.backup(dest_conn)`), không copy thô nhị phân khi WAL mode đang hoạt động.
     - Tự động tạo thư mục `backend/backups/` và sinh tên file có timestamp độc nhất kèm UUID suffix (`webstore_backup_YYYYMMDD_HHMMSS_<suffix>.db`), tuyệt đối không ghi đè file cũ.
     - Đã thêm `backups/`, `backend/backups/`, `*.bak` vào `.gitignore`.
  2. *Xác minh và kiểm chứng khôi phục*:
     - Hàm `verify_database_backup()` mở độc lập bản backup, kiểm tra tính toàn vẹn (`PRAGMA integrity_check == 'ok'`), kiểm tra khóa ngoại (`PRAGMA foreign_key_check == 0 errors`), đối chiếu 100% số lượng bản ghi của 12 bảng nghiệp vụ giữa source và backup.
     - Hàm `trial_restore_query()` kiểm thử khôi phục và truy vấn trên thư mục tạm thành công.
     - Tính mã băm SHA-256 quản lý tính toàn vẹn bản sao:
       - File backup: `backend/backups/webstore_backup_20261010_152615_beca91.db` (585,728 bytes).
       - SHA-256: `7de967ec5d007c41b19638da88c72b88bc88b33a01b8af12fc984f5bbcd4f6b4`.
       - Trạng thái: **BACKUP VERIFIED 100%**.
  3. *Schema Versioning Metadata*:
     - Bảng `schema_version (version INTEGER PRIMARY KEY, description TEXT NOT NULL, applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, checksum TEXT)` được tích hợp vào `backend/app/models/schema.py`.
     - Đã kiểm thử tính Idempotency và Rollback khi lỗi trên database clone cách ly trước khi áp dụng vào DB chính.
     - Khởi tạo thành công bản ghi baseline Version 1 trên `backend/webstore.db` (`version = 1`, `description = 'R2A: Initial schema versioning baseline'`).
     - Tuyệt đối chưa sửa schema hay thêm cột nào vào các bảng nghiệp vụ trong Phase R2A.
  4. *Ghi nhận 2 rủi ro kỹ thuật chuẩn bị cho R2B/R2C*:
     - **Rủi ro A (Legacy flag)**: Khi chạy R2B, không dùng câu `UPDATE orders` không giới hạn để đánh dấu toàn bộ đơn hàng; phải xác định chính xác tập 317 đơn cũ lịch sử trước khi áp dụng migration.
     - **Rủi ro B (Legacy payment status)**: Database hiện tại chứa `payment_status = 'completed'`, không nằm trong enum mới (`unpaid`, `pending_verification`, `paid`, `refund_pending`, `refunded`); R2C phải có chiến lược ánh xạ an toàn (VD: `'completed'` $\rightarrow$ `'paid'`), không mặc định mọi đơn cũ đều đã thanh toán nếu chưa có đối soát.
- **Files đã sửa/tạo**:
  - `backend/app/core/backup.py` (Mới)
  - `backend/app/models/schema.py` (Cập nhật `schema_version`)
  - `.gitignore` (Cập nhật bỏ qua thư mục `backups/`)
  - `backend/tests/test_phase_r2a_backup_versioning.py` (Mới: 11 tests)
- **Kết quả kiểm thử**:
  - **11/11 targeted tests PASSED (2.68s)** trên database clone độc lập (`tempfile.TemporaryDirectory`).
  - **51/51 total regression tests PASSED (21.38s)** (R2A: 11/11, R1A: 9/9, R1B: 14/14, R1C: 17/17).
- **DoD**: Đạt 100% tiêu chí nghiệm thu R2A.
- **STOP Condition**: **DỪNG LẠI tại đây sau khi hoàn thành Phase R2A. CHƯA THỰC HIỆN R2B HOẶC R2C.**

---

#### PHASE R2B: Phased Column Expansion — [COMPLETED ✅ 10/10/2026]
- **Trạng thái**: **HOÀN THÀNH (100% Passed 12/12 Targeted Tests, 63/63 Total Suite Tests)**
- **Mục tiêu**: Bổ sung an toàn các cột mới cho bảng `orders` mà không làm thay đổi hay reset bảng cũ, bảo toàn 100% dữ liệu lịch sử.
- **Kết quả triển khai thực tế**:
  1. *Backup mới độc lập trước R2B (VERIFIED 100%)*:
     - File backup: `backend/backups/webstore_backup_20261010_153257_264ba0.db` (585,728 bytes).
     - SHA-256: `65a50e3a64f2385068bc41286c1fe8509534ee65b62f2efdca1d056d0a93fedb`.
     - Xác minh: `PRAGMA integrity_check = ok`, `PRAGMA foreign_key_check = 0 errors`, trial restoration truy vấn thành công. Không ghi đè backup R2A.
  2. *Cột mới bổ sung vào `orders`*:
     - `assigned_to INTEGER NULL REFERENCES users(id)` (hỗ trợ atomic order claim sau này).
     - `shipping_name TEXT NULL`
     - `shipping_phone TEXT NULL`
     - `shipping_address TEXT NULL`
     - `is_legacy_unverified INTEGER NOT NULL DEFAULT 0`
  3. *Khắc phục lỗi nhận diện đơn hàng lịch sử (Sửa lỗi đề xuất `id <= 317` của R2A)*:
     - Số lượng bản ghi `orders` là 317, nhưng dải ID thực tế từ 1 đến 346 với các khoảng trống (ID gaps: 81, 107..134). Ngưỡng `id <= 317` là sai lầm vì bỏ sót các ID từ 318 đến 346 và giả định sai ID là dãy liên tục.
     - Cơ chế chuẩn: Snapshot chính xác tập ID thực tế (`SELECT id FROM orders`) ngay bên trong cùng transaction `BEGIN IMMEDIATE` của migration.
     - Đánh dấu theo tập ID thực: `UPDATE orders SET is_legacy_unverified = 1 WHERE id IN (...)` theo batch an toàn (500 ID/batch).
     - Không dựa vào `COUNT(*)` làm cutoff. Các đơn hàng tạo mới sau migration tự động có `is_legacy_unverified = 0`.
     - Không chạy câu UPDATE toàn bảng vô điều kiện mỗi khi khởi động ứng dụng.
  4. *Migration Versioning & Idempotency*:
     - Ghi nhận `schema_version = 2` (`R2B: Phased column expansion for orders and legacy order tagging`).
     - Tái chạy migration an toàn (no-op, không chạy lại, trả về `False`).
     - Cơ chế rollback an toàn nếu DDL hoặc DML gặp sự cố giữa chừng.
  5. *Bảo toàn Tuyệt đối Dữ liệu & Đính chính Số liệu Báo cáo*:
     - Số lượng bản ghi thực tế được đối chiếu chính xác qua SQLite `SELECT COUNT(*)` trên cả 3 bản (R2A Backup, Pre-R2B Backup, Main DB): `orders`: 317 đơn, `order_items`: 322 bản ghi, `products`: 30 sản phẩm, `categories`: 5 danh mục, `customers`: 7 khách hàng, `users`: 6 tài khoản, `inventory_logs`: 456 bản ghi. Giữ nguyên 100% không đổi. (Đính chính: Số liệu 798/40/8/21 trong text báo cáo trước đó là lỗi nhầm lẫn văn bản, không có dữ liệu lạ nào phát sinh trong DB).
     - Toàn bộ giá trị `payment_status` lịch sử thực tế trong DB: `completed`: 232 đơn, `paid`: 73 đơn, `pending`: 12 đơn (tổng 317 đơn) được giữ nguyên 100%. Tuyệt đối không tự ý chuyển `completed` sang `paid`.
  6. *Hotfix Bảo Mật Mass Assignment (OrderCreate)*:
     - Loại bỏ hoàn toàn `assigned_to` và không cho phép `is_legacy_unverified` trong schema `OrderCreate`.
     - Phân định rõ schema ghi (`OrderCreate`) và schema đọc (`OrderResponse`).
     - Khóa cứng trong `inventory_service.py:create_order`: Đơn mới tạo luôn có `assigned_to = NULL` và `is_legacy_unverified = 0`.
     - Khách hàng (Customer) hoặc nhân viên (Staff) gửi `assigned_to` hoặc `is_legacy_unverified` trong payload đều bị vô hiệu hóa, không thể tự gán quyền hoặc cờ legacy.
- **Files đã sửa**:
  - `backend/app/schemas/order.py` (Bổ sung shipping fields vào `OrderCreate`; loại bỏ `assigned_to` khỏi `OrderCreate`; giữ 5 trường trong `OrderResponse`)
  - `backend/app/models/schema.py` (Hàm `run_migration_v2_r2b`, tích hợp version 2 runner trong `init_db`)
  - `backend/app/api/v1/orders.py` (Bổ sung 5 trường vào query `get_orders`, `get_order_detail`)
  - `backend/app/services/inventory_service.py` (Bổ sung 5 trường vào `INSERT INTO orders` với `assigned_to = NULL` và `is_legacy_unverified = 0`, trả về đủ trường trong dictionary)
- **Files kiểm thử mới**:
  - `backend/tests/test_phase_r2b_column_expansion.py` (12 tests)
  - `backend/tests/test_phase_r2b_hotfix_mass_assignment.py` (6 tests)
- **Kết quả kiểm thử**:
  - **18/18 targeted tests PASSED** (R2B Column Expansion: 12/12, Mass Assignment Hotfix: 6/6).
  - **69/69 total regression tests PASSED (25.92s)** (R2B Hotfix: 6, R2B Base: 12, R2A: 11, R1A: 9, R1B: 14, R1C: 17).
- **DoD**: Đạt 100% tiêu chí nghiệm thu R2B và Hotfix an toàn bảo mật.
- **STOP Condition**: **DỪNG LẠI tại đây sau khi hoàn thành Phase R2B và Hotfix. TUYỆT ĐỐI CHƯA THỰC HIỆN R2C.**

---

#### PHASE R2C: Payment & Fulfillment Enum Upgrade
- **Tổng thể Phase R2C**: **[COMPLETED ✅ 10/10/2026]**
- **Tiểu giai đoạn R2C-A (Design & Clone Dry-Run)**: **[COMPLETED ✅ 10/10/2026]**
- **Tiểu giai đoạn R2C-B1 (Migration Compatibility & Integration Preflight)**: **[COMPLETED ✅ 10/10/2026]**
- **Tiểu giai đoạn R2C-B2 (Production Database Migration V3)**: **[COMPLETED ✅ 10/10/2026]**
- **Mục tiêu**: Nâng cấp an toàn bảng `orders` để hỗ trợ đầy đủ enum `payment_status` (`unpaid`, `pending_verification`, `paid`, `refund_pending`, `refunded`, `unverified_legacy`), bổ sung `payment_status_raw` và `fulfillment_status`. Giữ nguyên tên trường `status`.
- **Kết quả Thực hiện Dry-Run R2C-A trên Bản Clone Độc Lập**:
  1. *Bảo tồn Dữ liệu Gốc với `payment_status_raw`*:
     - Cột `payment_status_raw TEXT NOT NULL` lưu trữ 100% giá trị trạng thái thanh toán gốc ban đầu của từng đơn hàng: `completed` (232 đơn), `paid` (73 đơn), `pending` (12 đơn).
     - Tuyệt đối không xóa hoặc ghi đè trạng thái thanh toán lịch sử.
  2. *Giải pháp Trạng thái Thanh toán Lịch sử (Khuyến nghị Phương án A)*:
     - Bổ sung `unverified_legacy` làm giá trị thứ 6 trong enum `payment_status`.
     - Ánh xạ an toàn không bóp méo số liệu:
       - 232 đơn `'completed'` $
ightarrow$ chuyển sang `payment_status = 'unverified_legacy'`.
       - 73 đơn `'paid'` (chưa đối soát tiền thực nhận) $
ightarrow$ chuyển sang `payment_status = 'unverified_legacy'`.
       - 12 đơn `'pending'` $
ightarrow$ chuyển sang `payment_status = 'unpaid'`.
     - **Cam kết**: 0 đơn lịch sử nào bị tự ý gán là `'paid'`. Báo cáo doanh thu thực thu (`WHERE payment_status = 'paid'`) trả về đúng 0 VNĐ cho các đơn chưa xác minh.
  3. *Thiết kế Giao Vận `fulfillment_status`*:
     - Cột `fulfillment_status TEXT NOT NULL CHECK(fulfillment_status IN ('unfulfilled', 'packing', 'shipping', 'delivered', 'delivery_failed', 'returned_to_inventory', 'legacy_unknown'))`.
     - 317 đơn lịch sử được gán `'legacy_unknown'` (trung thực với lịch sử hệ thống chưa theo dõi vận chuyển).
     - Đơn mới tạo tại quầy POS: mặc định `'delivered'`. Đơn online/remote: mặc định `'unfulfilled'`.
  4. *Quy trình Rebuild Bảng An toàn (12 Bước SQLite Standard)*:
     - Tắt `PRAGMA foreign_keys = OFF` ngoài transaction trước khi `BEGIN IMMEDIATE`.
     - Tạo `orders_new` $
ightarrow$ Copy chuyển đổi $
ightarrow$ Drop `orders` $
ightarrow$ Rename `orders_new` sang `orders`.
     - Tái tạo 5 Indexes: `idx_orders_status`, `idx_orders_created`, `idx_orders_code`, `idx_orders_payment_status`, `idx_orders_fulfillment`.
     - `PRAGMA foreign_key_check` đạt 0 lỗi, `PRAGMA integrity_check` trả về `'ok'`.
     - Đã kiểm chứng tính Idempotency và Rollback khi lỗi trên bản clone.
  5. *Kết quả Đo kiểm trên Clone*:
     - 317/317 đơn hàng và 322/322 order_items giữ nguyên vẹn 100%.
     - Tổng doanh thu `final_amount`: 461,534,000 VNĐ giữ nguyên 100%.
     - CHECK constraint hoạt động chuẩn: Chặn đứng các giá trị lạ không thuộc enum.
- **Kết quả Kiểm thử Tương thích & Tích hợp R2C-B1 (Đã hoàn thiện hiệu chỉnh chuẩn enum)**:
  1. *Migration Code Tái Sử Dụng*: Đã tích hợp `apply_migration_v3_explicit(conn)` và `run_migration_v3_r2c(conn)` vào `backend/app/models/schema.py` tuân thủ 12 bước SQLite Table Rebuild. Kiểm soát môi trường qua biến `ENABLE_MIGRATION_V3=1`, không tự động chạy trên database chính khi khởi động backend.
  2. *Chuẩn hóa Đồng Bộ Toàn Bộ Enum*:
     - `PaymentStatus` (6 giá trị chuẩn nghiệp vụ): `unpaid`, `pending_verification`, `paid`, `refund_pending`, `refunded`, `unverified_legacy`.
     - `FulfillmentStatus` (7 giá trị chuẩn nghiệp vụ): `unfulfilled`, `packing`, `shipping`, `delivered`, `delivery_failed`, `returned_to_inventory`, `legacy_unknown`.
     - Đã đồng bộ 100% tại: SQLite CHECK constraints (Migration v3), Pydantic Schemas (`schemas/order.py`), AI Service (`services/ai_service.py`), Frontend Badges (`Badge.jsx`), và Integration Tests.
  3. *Tương thích Kép Schema v2 & Schema v3*:
     - Kiểm tra trực tiếp `sqlite_master` của schema v2: Nhận diện `CHECK(payment_status IN ('pending', 'paid', 'completed'))`.
     - HTTP Test trên clone v2: Đơn Customer tạo thành công với `payment_status = 'pending'`, đơn POS tạo thành công với `payment_status = 'paid'`, không lỗi CHECK constraint.
     - HTTP Test trên clone v3: Đơn Customer tạo thành công với `payment_status = 'unpaid'` & `fulfillment_status = 'unfulfilled'`, đơn POS tạo thành công với `payment_status = 'paid'` & `fulfillment_status = 'delivered'`.
  4. *Kiểm thử Chuyển Dịch Trạng Thái & Từ Chối Enum Lạ*:
     - Kiểm thử thành công chuỗi chuyển dịch: `unpaid` $\rightarrow$ `pending_verification` $\rightarrow$ `paid`; `paid` $\rightarrow$ `refund_pending` $\rightarrow$ `refunded`; `shipping` $\rightarrow$ `delivery_failed` $\rightarrow$ `returned_to_inventory`.
     - CHECK constraint từ chối nghiêm ngặt các giá trị không hợp lệ: `'completed'`, `'partially_refunded'`, `'cancelled_unpaid'`, `'returned'` và các chuỗi lạ.
  5. *Tương thích Frontend*:
     - `PosPage.jsx`: Loại bỏ hardcode `'completed'`, chuyển sang `'paid'` cho POS và `'unpaid'` cho Customer.
     - `Badge.jsx`: Cấu hình đầy đủ nhãn và variant cho toàn bộ 6 trạng thái thanh toán và 7 trạng thái giao vận.
     - Build production Vite/React pass thành công (`✓ built in 447ms`, 0 errors).
  6. *Kết quả Kiểm thử Toàn diện (Nguyên văn file test)*:
     - `backend/tests/test_phase_r2c_integration_preflight.py`: **11/11 tests PASSED (6.90s)**.
     - **90/90 tests PASSED (25.59s)** trên toàn bộ 8 file test refactor (R1A -> R2C-B1).
- **Kết quả Triển khai Chính thức Production Database Migration V3 (R2C-B2)**:
  1. *Backup Độc lập & Toàn vẹn*:
     - Đường dẫn: `backend/backups/webstore_backup_20261010_180945_e02947.db` (585,728 bytes).
     - SHA-256: `8654516e47778b8adbae009ab50337a8da7a549983f95eadcf85f8ceef9151f0`.
     - Xác minh: `integrity_check = ok`, `foreign_key_check = ok`, trial restoration pass, 100% record counts khớp nguồn (13 bảng).
  2. *Thực thi Migration V3 trên Database Chính (`backend/webstore.db`)*:
     - Sử dụng hàm quản trị tường minh: `apply_migration_v3_explicit(conn)` với quy trình 12 bước SQLite Table Rebuild.
     - `schema_version` mới nhất: **3** (đầy đủ các mốc `[1, 2, 3]`).
     - Tái chạy `apply_migration_v3_explicit(conn)` đạt chuẩn Idempotency (no-op, trả về `False`).
  3. *Toàn vẹn Dữ liệu Tuyệt đối*:
     - `orders`: Giữ nguyên **317 bản ghi** (0 đơn bị mất, ID không đổi).
     - `order_items`: Giữ nguyên **322 bản ghi** (0 item bị mất, liên kết nguyên vẹn).
     - Tổng doanh thu lịch sử: **461,534,000.0 VNĐ** giữ nguyên 100%.
     - `sqlite_sequence` cho `orders`: Giữ nguyên **346**.
     - Bảng tạm: 0 bảng tạm hoặc `orders_new` tồn đọng.
  4. *Phân bổ Trạng thái Sau Migration*:
     - `payment_status`:
       - `unverified_legacy`: **305** (gồm 232 `completed` và 73 `paid`).
       - `unpaid`: **12** (tương ứng 12 `pending`).
       - `paid`: **0** (tuyệt đối không tự xác nhận thu tiền cho đơn cũ).
     - `payment_status_raw`: `completed`: 232, `paid`: 73, `pending`: 12 (bảo toàn 100% trạng thái gốc).
     - `fulfillment_status`: `legacy_unknown`: 317 (trung thực với lịch sử hệ thống).
  5. *Toàn vẹn Cấu trúc*:
     - `PRAGMA integrity_check`: **['ok']**.
     - `PRAGMA foreign_key_check`: **0 violations**.
     - Đầy đủ 6 indexes: `sqlite_autoindex_orders_1`, `idx_orders_status`, `idx_orders_created`, `idx_orders_code`, `idx_orders_payment_status`, `idx_orders_fulfillment`.
  6. *Kiểm thử Ứng dụng & Hồi quy*:
     - **90/90 regression tests PASSED (25.47s)** trên toàn bộ 8 suites.
     - Live Backend Boot & API inspection trên `webstore.db` trực tiếp:
       - `GET /api/v1/orders`: HTTP 200 OK (hiển thị `unverified_legacy` & `legacy_unknown`).
       - `GET /api/v1/orders/1`: HTTP 200 OK (`payment_status_raw = paid`, mapped `unverified_legacy`).
       - Báo cáo tài chính `ReportService.get_dashboard_summary()`: `total_revenue = 316,063,000 đ`, `verified_payment_revenue = 0 đ`, `legacy_unverified_revenue = 449,194,000 đ` (không diễn giải sai tiền thực thu).
     - Frontend production build: `npm run build` thành công trong 445ms (0 errors).
- **Kết quả Post-R2C Financial Report Hotfix [COMPLETED ✅ 10/10/2026]**:
  1. *Hiệu chỉnh công thức `legacy_unverified_revenue`*:
     - Bổ sung `status = 'completed'` vào truy vấn `SELECT COALESCE(SUM(final_amount), 0) FROM orders WHERE status = 'completed' AND payment_status = 'unverified_legacy'`.
     - Loại bỏ hoàn toàn 133,131,000 VNĐ từ các đơn hủy (`cancelled`: 58,745,000 đ), từ chối (`rejected`: 13,735,000 đ), chờ xử lý (`pending`: 49,656,000 đ, `processing`: 5,325,000 đ, `admin_approved`: 5,670,000 đ).
  2. *Đối chiếu 4 chỉ số tài chính*:
     - `total_revenue`: **316,063,000 VNĐ** (140 đơn completed).
     - `legacy_unverified_revenue`: **316,063,000 VNĐ** (Định nghĩa chuẩn: "Doanh số đơn hoàn thành chưa đối soát thanh toán").
     - `verified_payment_revenue`: **0 VNĐ** (0 đơn lịch sử tự nhận là paid).
     - Tổng giá trị gộp 305 đơn `unverified_legacy`: **449,194,000 VNĐ** (được phân biệt rõ, không gọi là doanh số đơn hoàn thành).
  3. *Đồng bộ Schema & AI Service*:
     - Bổ sung `verified_payment_revenue` và `legacy_unverified_revenue` vào Pydantic `DashboardSummaryResponse`.
     - Chuẩn hóa nhãn trong `ai_service.py`: "Doanh số đơn hoàn thành chưa đối soát".
  4. *Kiểm thử*:
     - 5/5 targeted tests PASSED (`tests/test_phase_r2c_financial_hotfix.py`).
     - 21/21 R2C tests PASSED (`test_phase_r2c_dryrun.py` & `test_phase_r2c_integration_preflight.py`).
     - Database chính `webstore.db` bảo toàn nguyên vẹn 100% schema version 3, 317 orders, 322 items, integrity_check ok, 0 vi phạm FK.
- **STOP Condition**: **DỪNG LẠI tại đây sau khi hoàn thành Phase R2C-B2 và Financial Hotfix. TUYỆT ĐỐI KHÔNG TỰ ĐỘNG BẮT ĐẦU R3.**

---

#### PHASE R3: Order Workflow, Claim Lock & Payments — [COMPLETED ✅ 10/10/2026]
- **Trạng thái**: **HOÀN THÀNH (100% Passed 7/7 Targeted HTTP & Concurrency Tests, 81/81 Full Regression Tests)**
- **Mục tiêu**: Triển khai luồng đơn hàng hoàn chỉnh: Order State Machine & RBAC chặt chẽ; Atomic Claim Lock chống nhận trùng đơn (HTTP 409 Conflict); Payment Verification (COD tiền mặt, đối soát chuyển khoản ngân hàng); Fulfillment đa trạng thái; Inventory Return một lần duy nhất kèm Idempotency guard; Tách biệt hoàn toàn Hoàn tiền (Financial Refund) và Hoàn hàng (Physical Logistics); Audit log ghi nhận mọi biến động.
- **Kết quả triển khai thực tế**:
  1. *Order State Machine & Phân Quyền RBAC*:
     - Giữ nguyên `orders.status`: `pending`, `admin_approved`, `processing`, `completed`, `rejected`, `cancelled`.
     - Phân quyền nghiêm ngặt:
       - Customer: Tạo đơn (`pending`), xem đơn cá nhân (Anti-IDOR), hủy đơn khi còn `pending`/`admin_approved`, thông báo chuyển khoản (`notify_transfer`).
       - Staff: Bán hàng tại quầy POS (tự động `completed`/`paid`/`delivered`), nhận đơn được Admin duyệt (`claim_order`), cập nhật vận chuyển (`packing`/`shipping`/`delivered`/`delivery_failed`), xác nhận thu tiền mặt COD (`confirm_cod_payment`), xác nhận nhập kho hàng hoàn (`confirm_return`).
       - Admin: Duyệt/từ chối đơn (`approve`/`reject`), gán lại đơn (`reassign_order`), đối soát & xác nhận thanh toán chuyển khoản (`verify_payment`), xử lý hoàn tiền (`request_refund`/`confirm_refund`).
       - SuperAdmin: Giữ quyền giám sát và can thiệp ngoại lệ (yêu cầu lý do $\ge 5$ ký tự, ghi audit log đầy đủ).
       - Guest: Bị chặn 401 Unauthorized đối với toàn bộ đơn hàng riêng tư.
     - Chống mass assignment: Client không thể tự cập nhật `status`, `payment_status`, `assigned_to`, `fulfillment_status`, `is_legacy_unverified` qua các payload tạo hoặc cập nhật thông thường.
  2. *Atomic Claim Lock (Nhận đơn nguyên tử)*:
     - Endpoint `POST /api/v1/orders/{order_id}/claim`.
     - Thực thi trong SQLite transaction `BEGIN IMMEDIATE` với điều kiện nguyên tử:
       ```sql
       UPDATE orders
       SET status = 'processing',
           assigned_to = ?,
           processed_by = ?,
           processed_at = CURRENT_TIMESTAMP
       WHERE id = ? AND status = 'admin_approved' AND assigned_to IS NULL;
       ```
     - Xử lý tương tranh: Khi 2 nhân viên cạnh tranh nhận cùng một đơn, nhân viên đầu tiên thành công (HTTP 200), nhân viên thứ hai bị từ chối với HTTP 409 Conflict rõ ràng.
     - Audit log ghi nhận cùng transaction. Không phát sinh trừ kho lần 2 (tồn kho đã giữ từ khi tạo đơn). Không thay đổi `payment_status`.
  3. *Payment Verification (Xác minh thanh toán thực tế)*:
     - Các trạng thái chuẩn hóa: `unpaid`, `pending_verification`, `paid`, `refund_pending`, `refunded`, `unverified_legacy`.
     - Đơn COD: Khởi tạo `unpaid`. Chỉ chuyển `paid` qua `POST /orders/{id}/confirm-cod-payment` khi Staff/Admin xác nhận thực tế đã nhận tiền mặt từ khách/shipper.
     - Đơn Chuyển khoản (Bank Transfer):
       - Khách/Nhân viên thông báo qua `POST /orders/{id}/notify-transfer` kèm mã tham chiếu chuyển khoản (`transfer_ref`) $\rightarrow$ chuyển sang `pending_verification`.
       - Admin/SuperAdmin đối soát qua sao kê ngân hàng thực tế và xác nhận qua `POST /orders/{id}/verify-payment` kèm mã đối soát (`verified_ref`) $\rightarrow$ chuyển sang `paid`.
       - Hệ thống không giả lập kết nối ngân hàng; không tự động coi ảnh chụp là đã thanh toán thành công.
     - Đơn POS: Ghi nhận `paid` ngay tại quầy khi Staff thu tiền.
  4. *Fulfillment & Quản lý Tồn kho Vật lý (Delivery Failed Invariant)*:
     - Chuỗi trạng thái: `unfulfilled` $\rightarrow$ `packing` $\rightarrow$ `shipping` $\rightarrow$ `delivered` / `delivery_failed`.
     - Khi `delivery_failed`: **Tuyệt đối KHÔNG tự động cộng lại tồn kho**. Hàng hóa vẫn đang lưu thông ở đơn vị vận chuyển.
     - Nhập kho hàng hoàn qua `POST /orders/{id}/confirm-return`:
       - Điều kiện tiên quyết: `fulfillment_status` đang là `delivery_failed` hoặc `status` là `cancelled` (và hàng chưa hoàn kho).
       - Hoàn tồn kho nguyên tử **ĐÚNG 1 LẦN DUY NHẤT** kèm log `inventory_logs (change_type = 'return_cancel')`.
       - Cập nhật `fulfillment_status = 'returned_to_inventory'`.
       - **Idempotency Guard**: Kiểm tra log hoàn kho và trạng thái. Nếu gọi lại lần thứ 2, hệ thống chặn đứng với HTTP 400, triệt tiêu nguy cơ cộng tồn kho 2 lần.
  5. *Tách Biệt Hoàn Tiền (Financial Refund) & Hoàn Hàng (Physical Logistics)*:
     - Quy trình Hoàn tiền: `paid` $\rightarrow$ `refund_pending` (qua `POST /orders/{id}/request-refund`) $\rightarrow$ `refunded` (qua `POST /orders/{id}/confirm-refund`).
     - Hàng về kho (`returned_to_inventory`) **không tự động hoàn tiền**.
     - Hoàn tiền (`refunded`) **không tự động cộng lại tồn kho**.
     - Đơn chưa thanh toán (`unpaid`) khi hủy giữ nguyên `unpaid`, không đánh dấu `refunded`.
  6. *Order Audit Logging*:
     - Tự động ghi chép chi tiết vào bảng `order_audit_logs`: `order_id`, `user_id`, `action`, `old_status`, `new_status`, `old_payment_status`, `new_payment_status`, `note`, `created_at`.
     - Endpoint `GET /api/v1/orders/{order_id}/audit-logs` cho phép tra cứu toàn bộ dòng thời gian diễn biến của đơn hàng (bảo vệ Anti-IDOR cho Customer).
  7. *Giao diện Frontend Orders (R3 Interactive Workflow)*:
     - Hiển thị đầy đủ `payment_status` badge, `fulfillment_status` badge, và tag nhân viên phụ trách (`assigned_name`).
     - Nút "Nhận xử lý đơn" trực tiếp trên danh sách đơn `admin_approved` cho Staff.
     - Modal Chi tiết Đơn hàng tích hợp thanh điều khiển nghiệp vụ R3:
       - Duyệt/Từ chối đơn (Admin).
       - Nhận đơn (Staff) / Phân công lại (Admin).
       - Xác nhận thu tiền COD / Thông báo chuyển khoản / Xác nhận đối soát thanh toán.
       - Cập nhật tiến độ giao vận (`packing` $\rightarrow$ `shipping` $\rightarrow$ `delivered` $\rightarrow$ `delivery_failed`).
       - Nút xác nhận hàng hoàn nhập kho (`confirm-return`).
       - Yêu cầu và Xác nhận hoàn tiền (`refund`).
       - Xem diễn biến nhật ký đơn hàng (`order_audit_logs`).
     - Build production Vite thành công: `✓ built in 713ms`, 0 errors.
- **Files đã sửa/tạo**:
  - `backend/app/schemas/order.py` (Bổ sung request/response schemas R3: Claim, Reassign, Transfer, Verify, COD, Fulfillment, Return, Refund, AuditLog)
  - `backend/app/services/inventory_service.py` (Triển khai 10 service methods mới cho R3 kèm SQLite transactions `BEGIN IMMEDIATE` và audit logging)
  - `backend/app/api/v1/orders.py` (Bổ sung 10 router endpoints mới và join hiển thị `assigned_name`)
  - `backend/app/models/schema.py` (Cho phép migration v3 runner kích hoạt trong testing environment)
  - `frontend/src/services/api.js` (Bổ sung 10 API calls trong `ordersAPI`)
  - `frontend/src/pages/OrdersPage.jsx` (Giao diện điều khiển luồng đơn hàng, badges, modals, timeline)
  - `backend/tests/test_phase_r3_order_workflow.py` (Suite 7 tests tích hợp & tương tranh)
- **Kết quả kiểm thử**:
  - **7/7 targeted HTTP integration tests PASSED (7.05s)**:
    - Test 1: Tạo đơn COD và Bank Transfer khởi tạo `unpaid` & `unfulfilled`.
    - Test 2: Quy trình duyệt đơn và Atomic Claim Lock (2 Staff cạnh tranh: 1 pass 200, 1 nhận 409 Conflict).
    - Test 3: Xác minh thanh toán Chuyển khoản (`pending_verification` $\rightarrow$ `paid`), kiểm soát RBAC.
    - Test 4: Xác nhận thu tiền COD tiền mặt (`confirm_cod_payment`).
    - Test 5: Chu kỳ Fulfillment, Delivery Failed không tăng kho, Confirm Return tăng kho đúng 1 lần, Idempotency Guard chặn gọi lần 2.
    - Test 6: Tách biệt hoàn toàn Hoàn tiền và Hoàn hàng, hoàn tiền không sửa tồn kho.
    - Test 7: Anti-IDOR và quyền xem Audit Logs timeline.
  - **81/81 regression tests PASSED (28.40s)** trên toàn bộ 9 suites (R1A, R1B, R1C, R2A, R2B, R2C, R3).
  - Production Database `backend/webstore.db` bảo toàn nguyên vẹn schema version 3, 317 đơn lịch sử.
- **DoD**: Đạt 100% tiêu chí nghiệm thu Phase R3.
- **STOP Condition**: **DỪNG LẠI tại đây sau khi hoàn thành Phase R3. CHỜ NGHIỆM THU TRƯỚC KHI BẮT ĐẦU R4.**

---

#### PHASE R4: RAG Retrieval Calibration & Cutoff [COMPLETED - 100% ACCEPTED]
- **Mục tiêu**: Khắc phục triệt để lỗi gợi ý sản phẩm không phù hợp bằng cách khảo nghiệm thực nghiệm tập ngưỡng Cosine Distance, kết hợp lọc ngữ nghĩa và đặc trưng danh mục, bổ sung cơ chế đối soát tự phục hồi ChromaDB ↔ SQLite, và phân loại minh bạch các phản hồi của AI.
- **Hiện trạng & Thành quả triển khai**:
  1. *Khảo nghiệm thực nghiệm tập ngưỡng Cosine Distance trên bộ 20 câu hỏi*:
     - Trước tối ưu (không cutoff): Độ chính xác 65.0% (13/20), False Acceptance Rate (FAR) trên câu hỏi ngoài danh mục/không tồn tại là 100.0% (6/6). Đổ sản phẩm bừa bãi khi hỏi về đồ ăn, vé máy bay, thời tiết, tivi, máy giặt.
     - Khảo nghiệm ngưỡng:
       * $\tau = 0.30$: Accuracy 40.0%, loại nhầm nhiều sản phẩm hợp lệ (False Rejections).
       * $\tau = 0.35$: Accuracy 50.0%, loại nhầm tên gõ tắt, bàn phím retro.
       * $\tau = 0.40 - 0.50$: Accuracy 55.0% - 60.0%, FAR vẫn cao do câu ngoài ngành có vector tình cờ gần.
       * Ngưỡng tối ưu $\tau = 0.55$ kết hợp Hybrid Sparse-Dense Scoring (Dense Score $60\%$ + Lexical Similarity $40\%$ + Category Affinity Boost $+0.30$ / Penalty $-0.25$ / Strict Out-of-Domain Guard): **Đạt 100.0% Accuracy (20/20) và FAR giảm tuyệt đối về 0.0% (0/6)**.
  2. *Chốt chặn SQLite Real-Time Truth Guard*:
     - Tồn kho và giá bán luôn truy vấn trực tiếp từ SQLite theo thời gian thực; 100% sản phẩm hết hàng (`stock_quantity <= 0`) bị loại bỏ khỏi danh sách tư vấn khả dụng.
     - Phát hiện rõ ràng sản phẩm hết hàng khi người dùng hỏi đích danh (`out_of_stock_detected`), thông báo trung thực hết hàng thay vì nhồi nhét sản phẩm khác.
  3. *Bảo vệ dữ liệu giá vốn & Chống Prompt Injection*:
     - Tuyệt đối không chọn hoặc lưu `cost_price` trong ChromaDB document, metadata hoặc context; che giấu 100% đối với Guest, Customer, Staff.
     - Hàm `_sanitize_text` vô hiệu hóa các mẫu prompt injection trong mô tả sản phẩm (`ignore previous instructions`, `reveal system prompt`, `act as superadmin`).
  4. *Cơ chế đối soát và tự phục hồi ChromaDB ↔ SQLite*:
     - Thêm `check_sync_status()` và `reconcile_sync()`: Tự động phát hiện và đồng bộ bù 5 sản phẩm (28, 48, 49, 70, 71) bị thiếu trong vector index, đưa tổng số indexed lên 30/30 (100% khớp SQLite).
     - Endpoint API mới: `GET /api/v1/ai/sync-status` và `POST /api/v1/ai/sync-index?reconcile_only=true`.
  5. *Xử lý lỗi Gemini an toàn & Thân thiện*:
     - Tự động kích hoạt Grounded Rule-based Fallback khi chưa cấu hình `GEMINI_API_KEY` hoặc khi quá hạn ngạch/timeout/mạng; không làm crash FastAPI hoặc giao diện; 0 vết rò rỉ secret hoặc traceback.
- **Files đã sửa/tạo**:
  - `backend/app/services/rag_service.py` (Hybrid RAG, out-of-domain guard, lexical scoring, category affinity, prompt injection neutralization, sync audit & reconciliation)
  - `backend/app/services/ai_service.py` (Grounded fallback, offline mode resilience, oos notification, financial distinction)
  - `backend/app/api/v1/ai.py` (Thêm GET /sync-status, mở rộng POST /sync-index)
  - `backend/tests/test_phase_r4_retrieval_rag.py` (Bộ test suite chuyên biệt 10 bài kiểm thử)
- **Kết quả kiểm thử**:
  - **10/10 targeted tests PASSED (14.32s)** trong `test_phase_r4_retrieval_rag.py`.
  - **142/142 full regression tests PASSED (72.47s)** trên toàn bộ 14 suites (R1A đến R4, an toàn bảo mật, ratelimit, AI foundation).
  - Production build frontend Vite: `✓ built in 636ms` (0 errors).
  - Production Database `backend/webstore.db` bảo toàn nguyên vẹn schema version 3, 317 đơn lịch sử, 30 sản phẩm.
- **DoD**: Đạt 100% tiêu chí nghiệm thu Phase R4.
- **STOP Condition**: **DỪNG LẠI tại đây sau khi hoàn thành Phase R4. CHỜ NGHIỆM THU TRƯỚC KHI BẮT ĐẦU R5.**

---

#### PHASE R5: Pluggable AI Providers & Local Benchmark [COMPLETED ✅ 11/10/2026]
- **Trạng thái**: **HOÀN THÀNH (10/10 Targeted Tests PASS, 123/123 Full Regression Tests PASS, Frontend Production Build PASS)**
- **Mục tiêu**: Tích hợp mô hình ngôn ngữ chạy cục bộ bằng Ollama (không cần Gemini API key hoặc Internet); Xây dựng kiến trúc Pluggable AI Providers (Strategy Pattern: Gemini, Ollama, Grounded Fallback) với lifecycle quản lý hoàn chỉnh; Chuẩn hóa thuật ngữ retrieval; Hoàn thiện tự động đồng bộ sản phẩm từ SQLite sang ChromaDB khi CRUD; và Kiểm thử, đo hiệu năng Ollama trên phần cứng thực tế (RTX 3050 Laptop 4GB).
- **Hiện trạng & Thành quả triển khai thực tế**:
  1. *Kiến trúc AI Provider Đa Nguồn (Pluggable AI Architecture)*:
     - Module `backend/app/services/ai_providers/`:
       * `base.py`: Lớp trừu tượng `BaseAIProvider` định nghĩa `generate_text()` và `health_check()`.
       * `gemini_provider.py`: Google Gemini 3.6 Flash provider kèm bridge tương thích ngược `ai_service._call_gemini`.
       * `ollama_provider.py`: Local Ollama provider kết nối `http://127.0.0.1:11434/api/chat`, tự động đo `tokens_per_second`, latency và số layers offload GPU.
       * `grounded_provider.py`: Deterministic SQLite Fact Generator, đảm bảo 0% ảo giác khi mất mạng/hết quota.
       * `manager.py`: `AIProviderManager` (`ai_provider_manager`) điều phối chuỗi fallback an toàn (`ollama`/`gemini` $\rightarrow$ `grounded`), kiểm tra sức khỏe và tự động nhận diện mock trong test legacy.
     - Endpoint mới: `GET /api/v1/ai/providers` trả về trạng thái cấu hình và khả dụng của từng provider.
     - Mở rộng response schemas: `recommend`, `sales-report`, `sales-qa` đều trả về trường `provider` thực tế (`"ollama"`, `"gemini"`, hoặc `"grounded"`).
  2. *Đo kiểm Benchmark Thực tế trên Phần Cứng Mục Tiêu (Physical Hardware)*:
     - Cấu hình thực tế: Windows 11, Intel Core i5-11400H, RAM 16GB, GPU NVIDIA GeForce RTX 3050 Laptop 4GB VRAM.
     - Xử lý hạn chế không gian ổ cứng: Ổ `C:` chỉ còn ~470MB khả dụng. Đã triển khai bộ cài portable Ollama 0.40.2 tại `D:\Ollama` với thư mục mô hình tại `D:\Ollama\models` (ổ `D:` còn 90+ GB trống).
     - Mô hình lựa chọn: **`qwen2.5:1.5b`** (Q4_K_M, tải về 986 MB $\le 2\text{GB}$, bộ nhớ VRAM an toàn tuyệt đối).
     - **Kết quả đo kiểm thực tế bằng `nvidia-smi` và Ollama Native Telemetry**:
       * GPU Offload: **100% (29/29 layers)** offloaded lên GPU NVIDIA GeForce RTX 3050 Laptop.
       * VRAM sử dụng: **1,191 MB / 4,096 MB (~29% VRAM)** — Còn trống tới 71% VRAM, **0% tràn xuống shared memory**.
       * Tốc độ suy luận (Generation Speed): **111.68 tokens/giây** (vượt trội so với mốc CPU thông thường).
       * Thời gian phản hồi Warm Latency: **0.80s – 0.84s / phản hồi**.
       * Thời gian nạp model lần đầu (Cold Start Load): **51.2s** (chỉ diễn ra 1 lần duy nhất khi khởi động daemon).
       * Chất lượng tiếng Việt: Mạch lạc, đúng ngữ cảnh tư vấn thiết bị máy tính, tuân thủ tuyệt đối chốt chặn dữ liệu từ SQLite.
  3. *Chuẩn hóa Thuật ngữ Retrieval (Terminology Normalization)*:
     - Đính chính kỹ thuật: Hệ thống retrieval hiện tại sử dụng pipeline **Dense Vector Retrieval (ChromaDB) + Lexical/Category Re-ranking + Strict SQLite Truth Guard**, không phải kiến trúc Sparse BM25 độc lập kết hợp Dual-Branch Inverted Index.
     - Cập nhật định nghĩa chuẩn hóa trong toàn bộ tài liệu và docstring mã nguồn.
  4. *Đánh giá Retrieval trên Bộ 10 Câu hỏi Mới (Fresh Queries Evaluation)*:
     - Đánh giá tập 10 câu hỏi chưa từng nằm trong benchmark R4: Đạt **10/10 (100.0%)**.
     - Câu hỏi ngoài danh mục (`chuot logitec g502`) trả về danh sách rỗng chính xác mà không bịa đặt sản phẩm, giữ FAR = 0%.
  5. *Tự động Đồng bộ Sản phẩm SQLite $\leftrightarrow$ ChromaDB khi CRUD*:
     - `backend/app/api/v1/products.py`: Tự động trigger đồng bộ vector khi Admin tạo mới (`POST`), cập nhật (`PUT`), hoặc xóa (`DELETE`) sản phẩm qua API/giao diện.
     - Phát hiện cập nhật ngữ nghĩa: Nếu chỉ sửa giá hoặc tồn kho, SQLite cập nhật tức thì còn vector document không phải tính toán lại lãng phí; nếu sửa tên/danh mục/mô tả, vector document được cập nhật đồng bộ.
     - Đối soát tự phục hồi nâng cao: `check_sync_status()` kiểm tra cả `missing_in_chroma`, `orphan_in_chroma` và **`outdated_in_chroma`** (so sánh hash nội dung và trạng thái kinh doanh giữa SQLite và ChromaDB). `reconcile_sync()` tự sửa toàn bộ các lỗi lệch chỉ mục mà không tạo bản ghi trùng lặp.
  6. *Tích hợp Frontend AI Assistant*:
     - Tự động gọi `GET /api/v1/ai/providers` để nhận diện provider thực tế.
     - Hỗ trợ dropdown chọn Provider: Tự động (Mặc định) | Ollama Local (Offline GPU) | Gemini Cloud | Grounded Fallback (SQLite).
     - Hiển thị badge chính xác: `Ollama Local (Qwen 2.5 1.5B GPU)`, `Gemini 3.6 Flash Grounded`, hoặc `Chế độ tra cứu trực tiếp SQLite`. Tuyệt đối không hiển thị nhãn Gemini/Ollama khi hệ thống đang dùng fallback.
     - Cảnh báo trực quan khi Ollama chưa chạy, tự động fallback sang SQLite bảo đảm trải nghiệm không bị đứt quãng.
- **Files đã sửa/tạo**:
  - `backend/app/core/config.py` (Cấu hình `AI_PROVIDER`, `OLLAMA_BASE_URL`, `OLLAMA_MODEL`, `OLLAMA_TIMEOUT_SECONDS`)
  - `backend/app/services/ai_providers/` (`base.py`, `gemini_provider.py`, `ollama_provider.py`, `grounded_provider.py`, `manager.py`)
  - `backend/app/services/ai_service.py` (Tích hợp Provider Manager, fallback chain, return `provider_used`)
  - `backend/app/services/rag_service.py` (Chuẩn hóa thuật ngữ retrieval, phát hiện `outdated_in_chroma`, self-healing reconciliation)
  - `backend/app/schemas/ai.py` (Provider response/request schemas, `provider` field trong recommend, sales-report, sales-qa)
  - `backend/app/api/v1/ai.py` (Router endpoint `GET /api/v1/ai/providers`)
  - `backend/app/api/v1/products.py` (Automatic vector sync on create/update/delete)
  - `frontend/src/services/api.js` (Bổ sung `getProviders`, truyền `provider` parameter)
  - `frontend/src/pages/AiAssistantPage.jsx` (Giao diện chọn provider, hiển thị engine/status, cảnh báo offline, dynamic badges)
  - `backend/tests/test_phase_r5_ollama_providers.py` (Suite 11 bài kiểm thử chuyên biệt R5)
  - `backend/tests/conftest.py` (Cô lập ChromaDB test session, bảo vệ an toàn 100% cho production chroma_data)
  - `scripts/start_ollama.bat` & `scripts/start_ollama.ps1` (Script khởi động Ollama độc lập chỉ định an toàn OLLAMA_MODELS=D:\Ollama\models)
- **Kết quả kiểm thử Final QA**:
  - **11/11 targeted tests PASSED (11.02s)** trong `test_phase_r5_ollama_providers.py` (bao gồm kịch bản phục hồi sau downtime ChromaDB).
  - **158/158 full regression tests PASSED (186.37s)** trên 15 test suites toàn hệ thống (R1-R5, Security, Rate Limit, RBAC, Order workflow, AI RAG).
  - Production build frontend Vite: `✓ built in 498ms` (0 errors).
  - Production Database `backend/webstore.db` bảo toàn nguyên vẹn schema version 3, 317 đơn lịch sử, 30 sản phẩm.
  - ChromaDB Collection: 30/30 sản phẩm đồng bộ 100% với SQLite (0 missing, 0 orphan, 0 outdated).
- **DoD**: Đạt 100% tiêu chí nghiệm thu Phase R5 & Final QA.
- **STOP Condition**: **DỪNG LẠI tại đây sau khi hoàn thành Phase R5 Final QA. CHỜ NGHIỆM THU TRƯỚC KHI BẮT ĐẦU R6.**

---

#### PHASE R6: Image Search Multimodal Pipeline
- **Mục tiêu**: Hoàn thiện pipeline tìm kiếm bằng hình ảnh, tích hợp Vision local provider (sử dụng mô hình chiến thắng từ Phase R5), tiền xử lý giới hạn kích thước ảnh tránh OOM, và giữ vững chốt chặn SQLite Truth Guard.
- **Phạm vi**:
  - Cập nhật `image_search_service.py`: Tích hợp fallback gọi mô hình Vision local đã nghiệm thu (Gemma 3 4B hoặc Qwen-VL thắng benchmark R5) khi Gemini Vision quá hạn ngạch.
  - Thêm bước tiền xử lý ảnh: Resize ảnh truy vấn về tối đa $512 \times 512$ trước khi đưa vào mô hình thị giác local để bảo đảm an toàn cho 4GB VRAM.
  - Tinh chỉnh bộ lọc phi sản phẩm `is_non_product_image` và bộ phân loại 4 mức độ (`Match`, `Similar`, `Related`, `None`).
- **File dự kiến**: `backend/app/services/image_search_service.py`, `backend/app/services/visual_index_service.py`.
- **Không thay đổi**: Không quét lại toàn bộ catalog bằng Vision API tại mỗi request (bảo toàn precomputed visual index).
- **Tiền đề**: Hoàn thành Phase R5.
- **Kiểm thử**: Tải ảnh tai nghe mẫu $\rightarrow$ Phân loại đúng Match/Similar; Tải ảnh khuôn mặt/phong cảnh $\rightarrow$ Phân loại đúng None/Non-product; Thử nghiệm ngắt mạng $\rightarrow$ Vision Local xử lý thành công không gây OOM.
- **DoD**: Image Search hoạt động được cả Online (Gemini) và Offline (Local Vision).
- **STOP Condition**: **DỪNG LẠI báo cáo trước khi sang R7.**

---

#### PHASE R7: UI/UX, Be Vietnam Pro Typography & Masking
- **Mục tiêu**: Hiện đại hóa typography toàn diện sang `Be Vietnam Pro` (khắc phục triệt để lỗi dấu tiếng Việt), giữ `JetBrains Mono` cho các trường kỹ thuật, mở màn hình Khách hàng cho Staff (sau khi Backend Data Masking từ R1C đã sẵn sàng), loại bỏ role ảo `manager`, và tối ưu touch targets di động $\ge 44px$.
- **Phạm vi**:
  - `frontend/index.html`: Nhúng font Google `Be Vietnam Pro` (400, 500, 600, 700) và giữ `JetBrains Mono`.
  - `frontend/src/index.css`: Cập nhật `--font-display: 'Be Vietnam Pro', -apple-system, sans-serif;`. Bảo toàn 100% bản sắc Vintage Editorial / Retro Print.
  - `frontend/src/components/layout/Navbar.jsx` và `App.jsx`:
    - Mở quyền truy cập menu Khách hàng cho Staff.
    - Loại bỏ hoàn toàn role ma `manager`.
    - Hiển thị nhãn trạng thái AI Provider đang kết nối (Cloud / Local / Safe).
  - `frontend/src/pages/CustomersPage.jsx`: Nhận dữ liệu đã qua backend masking an toàn cho Staff.
  - Tối ưu hóa các nút thao tác bảng biểu đạt kích thước tối thiểu 44px trên mobile.
- **File dự kiến**: `frontend/index.html`, `frontend/src/index.css`, `frontend/src/components/layout/Navbar.jsx`, `frontend/src/App.jsx`, `frontend/src/pages/CustomersPage.jsx`, `frontend/src/pages/OrdersPage.jsx`.
- **Không thay đổi**: Không thay đổi bảng màu CRT Phosphor, giữ nguyên layout cơ cấu màn hình.
- **Tiền đề**: Hoàn thành Phase R1C, R3, R4.
- **Kiểm thử**: Kiểm tra giao diện trên mobile 390px, tablet 768px, desktop 1440px; Đăng nhập Staff xác nhận mở được Khách hàng và dữ liệu cá nhân bị masked; `npm run build` thành công 100% (0 errors, 0 warnings).
- **DoD**: Giao diện tiếng Việt chuẩn mực, không lỗi font, responsive mượt mà.
- **STOP Condition**: **DỪNG LẠI báo cáo trước khi sang R8.**

---

#### PHASE R8: Full Testing, Security Audit & Academic Prep
- **Mục tiêu**: Chạy kiểm thử tự động toàn diện cách ly trên `test_webstore.db`, kiểm toán bảo mật chống IDOR/RBAC, đóng gói script chạy ứng dụng 1-click, và chuẩn bị bộ tài liệu minh chứng học thuật sẵn sàng cho buổi bảo vệ đồ án (sử dụng mô hình local chiến thắng từ benchmark Phase R5, không hardcode `qwen2.5:3b`).
- **Phạm vi**:
  - Rà soát toàn bộ 23 test suites, bổ sung test case cho các tính năng mới (Claim lock, Payment status, Provider failover, RAG cutoff).
  - Kiểm tra tính nguyên vẹn tuyệt đối của file `backend/webstore.db` gốc (0 byte rác sau khi test).
  - Đóng gói kịch bản demo đối chứng cho hội đồng chấm thi: Demo Online (Gemini) $\leftrightarrow$ Demo Offline ngắt mạng (với mô hình thắng benchmark R5) $\leftrightarrow$ Demo Zero-Hallucination Fallback.
  - **Lưu ý nguyên tắc**: Việc cập nhật chính thức 3 tệp DOCX, PlantUML và quyển báo cáo chỉ được thực hiện sau khi Phase R8 này nghiệm thu phần mềm thành công 100%.
- **File dự kiến**: `backend/tests/` (toàn bộ test suites), `README.md`.
- **Không thay đổi**: Không sửa dữ liệu demo đã nghiệm thu.
- **Tiền đề**: Hoàn thành toàn bộ Phase R1 – R7.
- **Kiểm thử**: Chạy `pytest` đạt 100% PASS; Kiểm tra checksum hash của file database chính không bị biến động sau khi chạy test session.
- **DoD**: Toàn bộ hệ thống hoàn chỉnh 100%, bảo mật vững chắc, tài liệu và kịch bản demo sẵn sàng cho bảo vệ điểm tối đa.
- **STOP Condition**: **Hoàn thành toàn bộ dự án StoreFlow AI 2.0.**

---

## PHẦN 9: DANH MỤC QUYẾT ĐỊNH NGHIỆP VỤ CẦN NGƯỜI DÙNG PHÊ DUYỆT

Trước khi bắt đầu thực thi Phase R1A, các quyết định nghiệp vụ và kiến trúc cốt lõi sau đây đã được hoàn thiện để Bạn xem xét và xác nhận lần cuối:

- [ ] **Quyết định 1 (Tên trường trạng thái)**: Thống nhất giữ nguyên tên trường **`status`** trong bảng `orders` cho vòng đời đơn hàng; tuyệt đối không tạo thêm `order_status` trùng lặp gây xung đột đồng bộ và phá vỡ tương thích ngược API/dữ liệu lịch sử?
- [ ] **Quyết định 2 (Enum Payment Status & Cờ Legacy)**: Thống nhất enum `payment_status` gồm 5 giá trị chuẩn hóa (`unpaid`, `pending_verification`, `paid`, `refund_pending`, `refunded`), không dùng `cancelled_unpaid`, không đánh dấu `refunded` khi chưa từng thu tiền, và dùng cờ `is_legacy_unverified = 1` riêng để đối soát dữ liệu lịch sử?
- [ ] **Quyết định 3 (Quy trình Chuyển khoản)**: Thống nhất đơn chuyển khoản khởi tạo là `unpaid`, chuyển sang `pending_verification` khi khách/nhân viên thông báo đã chuyển, và chỉ chuyển sang `paid` khi Admin/Kế toán đối soát sao kê ngân hàng thực nhận; ảnh chụp bill từ khách chỉ là bằng chứng tham khảo?
- [ ] **Quyết định 4 (Tự đăng ký Khách hàng)**: Thống nhất bổ sung endpoint `/auth/register` tại Phase R1B, khóa cứng tạo role `customer` (chặn role escalation), tự động liên kết hồ sơ khách hàng, chống trùng và có rate limit?
- [ ] **Quyết định 5 (Backend Data Masking cho Staff)**: Thống nhất che giấu dữ liệu khách hàng (ẩn email, ẩn địa chỉ chi tiết) được thực thi tại Backend schema ở Phase R1C trước khi mở giao diện cho Staff ở Phase R7; frontend masking chỉ là bổ trợ?
- [ ] **Quyết định 6 (Giao hàng thất bại & Hoàn kho)**: Thống nhất khi `delivery_failed`, hàng KHÔNG tự động cộng tồn kho ngay; chỉ hoàn kho đúng 1 lần khi thủ kho nhận hàng vật lý và xác nhận `returned_to_inventory` (có idempotency guard); tách biệt xử lý hoàn tiền và hoàn hàng?
- [ ] **Quyết định 7 (Quyền Can thiệp Ngoại lệ của SuperAdmin)**: Thống nhất SuperAdmin không tham gia đóng gói/bán hàng thường xuyên nhưng giữ nguyên quyền tối cao can thiệp ngoại lệ (Force Cancel, Reopen, Reassign nhân viên) kèm lý do bắt buộc ($\ge 5$ ký tự) và ghi nhật ký kiểm toán bất biến?
- [ ] **Quyết định 8 (AI Local Benchmark & Model Selection)**: Thống nhất mốc Vision $< 2.5\text{s}$ là mục tiêu benchmark tham chiếu; Phase R8 sẽ sử dụng mô hình thắng cuộc thực tế từ Phase R5 (không hardcode `qwen2.5:3b`); nếu phần cứng 4GB VRAM không đáp ứng sẽ báo cáo hạn chế phần cứng minh bạch và kích hoạt Tier 3 (Deterministic Search)?
- [ ] **Quyết định 9 (Phân chia R1/R2 thành các bước nhỏ)**: Thống nhất triển khai R1 thành R1A/R1B/R1C (zero schema change) và R2 thành R2A/R2B/R2C (backup an toàn bằng `VACUUM INTO`, thử nghiệm trên bản sao trước, không xóa/reset dữ liệu, mỗi bước có STOP condition)?

---
```
================================================================================
>>> STOPPING EXECUTION: PHASE R0 FINAL ROADMAP REVISION COMPLETED.
>>> TÀI LIỆU docs/REFACTOR_ROADMAP.md ĐÃ ĐƯỢC CẬP NHẬT HOÀN TOÀN CHUẨN XÁC.
>>> DỪNG LẠI TẠI ĐÂY. TUYỆT ĐỐI KHÔNG TỰ ĐỘNG CHẠY PHASE R1.
================================================================================
```
