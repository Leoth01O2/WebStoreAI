# STOREFLOW AI 2.0 — HƯỚNG DẪN VẬN HÀNH & KỊCH BẢN BẢO VỆ ĐỒ ÁN (DEMO GUIDE)

> **Tài liệu bàn giao giai đoạn R8 — Final Integration & Project Delivery**
> **Phiên bản hệ thống:** StoreFlow AI 2.0 (Refactor v2)
> **Mục tiêu:** Cung cấp kịch bản thực hành trực quan từng bước cho Hội đồng chấm thi / Giảng viên hướng dẫn, minh chứng trọn vẹn các năng lực kỹ thuật: Phân quyền RBAC 5 vai trò, Vòng đời đơn hàng 3 trạng thái độc lập, Local Text AI (Ollama Qwen 2.5 1.5B), Local Vision AI (CLIP ViT-B/32), SQLite Grounding chống ảo giác và Kiểm toán bóc tách doanh thu thực tế.

---

## I. MÔI TRƯỜNG & HƯỚNG DẪN KHỞI ĐỘNG HỆ THỐNG

### 1. Yêu cầu phần cứng & Môi trường đề xuất
- **Hệ điều hành:** Windows 10/11 (hoặc Linux Ubuntu 22.04+).
- **Phần cứng mục tiêu:** Laptop Core i5 (thế hệ 11+), 16GB RAM, Card đồ họa rời 4GB VRAM (GTX 1650 / RTX 3050 Laptop).
- **Môi trường phần mềm:**
  - Python 3.12 (trong thư mục `backend/.venv`).
  - Node.js 18+ (khuyên dùng Node.js 20+).
  - Ollama (cài đặt tại `D:\Ollama` hoặc đường dẫn hệ thống).
  - Cache Weights CLIP: `D:\huggingface_cache` (~577MB).

---

### 2. Khởi động 3 thành phần hệ thống (3 Terminal độc lập)

#### Bước 1: Khởi động Ollama Local (Mô hình Qwen 2.5 1.5B)
Mở Terminal 1 (PowerShell):
```powershell
# Chạy script cấu hình an toàn models tại ổ D
.\scripts\start_ollama.ps1
# Hoặc chạy lệnh trực tiếp:
# $env:OLLAMA_MODELS="D:\Ollama\models"; ollama serve
```
*Kiểm tra trạng thái:* Mở trình duyệt truy cập `http://localhost:11434` hiển thị `Ollama is running`.

#### Bước 2: Khởi động Backend FastAPI
Mở Terminal 2 (PowerShell tại thư mục gốc dự án):
```powershell
cd backend
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```
*Kiểm tra trạng thái:* Truy cập Swagger UI tại `http://localhost:8000/docs`.

#### Bước 3: Khởi động Frontend Vite
Mở Terminal 3 (PowerShell tại thư mục gốc dự án):
```powershell
cd frontend
npm run dev
```
*Truy cập giao diện chính:* Mở trình duyệt tại `http://localhost:5173`.

---

## II. DANH MỤC TÀI KHOẢN THỬ NGHIỆM ĐỒ ÁN (DEMO ACCOUNTS)

| Vai trò (Role) | Tên đăng nhập | Mật khẩu mẫu | Phạm vi quyền hạn thực tế |
| :--- | :--- | :--- | :--- |
| **Guest** | *(Không cần đăng nhập)* | *(Trống)* | Xem catalog sản phẩm, tìm kiếm từ khóa, tìm bằng ảnh CLIP, chat tư vấn công khai, thêm giỏ tạm POS. |
| **Customer** | `khachhang1` | `Customer@123` | Đăng ký mới, đặt hàng cá nhân, theo dõi đơn của chính mình, bảo vệ chống IDOR (không xem được đơn người khác). |
| **Staff** | `staff` | `Staff@123` | Bán hàng POS, tra cứu khách hàng (PII đã che mờ `a***@email`), Claim đơn đã duyệt, cập nhật giao vận, thu tiền COD. |
| **Admin** | `admin` | `Admin@123` | CRUD sản phẩm/danh mục, duyệt/từ chối đơn, xác minh đối soát chuyển khoản ngân hàng, xem đầy đủ PII khách hàng, quản lý kho. |
| **SuperAdmin** | `superadmin` | `SuperAdmin@123` | Toàn quyền hệ thống, can thiệp ngoại lệ (Force Cancel, Reopen, Reassign nhân viên) có lý do bắt buộc và ghi audit log. |

---

## III. KỊCH BẢN THUYẾT TRÌNH VÀ THỰC HÀNH TỪNG BƯỚC (DEMO SCENARIOS)

### Kịch bản 1: Trải nghiệm Khách vãng lai (Guest) & Tìm kiếm Đa phương thức
1. **Mở trình duyệt ở chế độ Ẩn danh (Incognito)** tại `http://localhost:5173`.
2. **Khám phá sản phẩm:** Xem danh sách 30 sản phẩm công khai với font hiển thị tiếng Việt **Be Vietnam Pro** và phong cách **Modern Retro**.
3. **Lọc & Tìm kiếm từ khóa:** Gõ `"chuột gaming"` hoặc lọc danh mục `"Phụ kiện"` $\rightarrow$ Danh sách cập nhật tức thì.
4. **Tìm kiếm bằng hình ảnh (CLIP ViT-B/32 Local Vision):**
   - Vào tab **Trợ lý AI** $\rightarrow$ chọn tính năng **Tìm kiếm bằng hình ảnh**.
   - Kéo thả hoặc chọn một file ảnh tai nghe hoặc chuột.
   - Nhấn **Tìm kiếm** $\rightarrow$ Hệ thống phản hồi trong ~60–80ms trên CPU, hiển thị thẻ sản phẩm tương đồng nhất kèm % độ khớp hình ảnh và trạng thái còn hàng.
5. **Thử nghiệm thêm hàng vào giỏ và bấm thanh toán:**
   - Vào trang POS hoặc Chi tiết sản phẩm, thêm 1 sản phẩm vào giỏ.
   - Nhấn nút **Thanh toán** $\rightarrow$ Hệ thống hiển thị **Modal Guest Checkout Prompt** yêu cầu đăng nhập hoặc đăng ký tài khoản mới để lưu vết đơn hàng.

---

### Kịch bản 2: Khách hàng Tự Đăng ký & Đặt hàng chống IDOR
1. **Tự Đăng ký:**
   - Tại màn hình Đăng nhập, bấm chuyển sang tab **`[ĐĂNG KÝ MỚI]`**.
   - Nhập thông tin:
     - Username: `khachhang_demo`
     - Mật khẩu: `Demo@1234`
     - Họ và tên: `Nguyễn Văn Demo`
     - SĐT: `0987654321` (Chuẩn định dạng 10 số VN)
     - Email: `demo.customer@example.com`
     - Địa chỉ: `123 Đường Số 1, Quận 1, TP.HCM`
   - Bấm **Tạo tài khoản** $\rightarrow$ Hệ thống gọi `POST /api/v1/auth/register` (khóa cứng role `customer`), thông báo thành công và tự động điền username để đăng nhập.
2. **Đặt hàng:**
   - Đăng nhập với `khachhang_demo`.
   - Vào mục POS / Catalog, chọn 1 sản phẩm (ví dụ: *Tai nghe gaming DareU*), chọn phương thức **Chuyển khoản**.
   - Bấm **Thanh toán (F2)** $\rightarrow$ Đơn hàng khởi tạo với mã `SF-POS...`, trạng thái đơn là `pending` (Chờ duyệt), thanh toán `unpaid` (Chưa thanh toán).
3. **Kiểm tra chống IDOR:**
   - Khách hàng chỉ thấy đơn của chính mình trong tab **Đơn Hàng Của Tôi**.
   - Thử sửa mã ID đơn trên URL hoặc API sang đơn của khách khác $\rightarrow$ Backend trả về lỗi `HTTP 403 Forbidden` ngay lập tức.

---

### Kịch bản 3: Quy trình Quản trị & Xử lý Đơn hàng (Staff & Admin)
1. **Admin duyệt đơn:**
   - Đăng xuất, đăng nhập với tài khoản `admin`.
   - Vào trang **Đơn hàng**, lọc tab **Chờ duyệt (`pending`)** $\rightarrow$ Thấy đơn mới của `khachhang_demo`.
   - Bấm **Phê duyệt đơn** $\rightarrow$ Đơn chuyển sang trạng thái `admin_approved`.
2. **Staff nhận đơn & Bảo mật PII:**
   - Đăng xuất, đăng nhập với tài khoản `staff`.
   - Vào menu **Khách hàng**: Thấy huy hiệu màu xanh `[PII ĐÃ BẢO MẬT]`. Email của khách hàng hiển thị dạng `d***@example.com`, địa chỉ nhà riêng bị ẩn hoàn toàn để bảo vệ quyền riêng tư.
   - Vào menu **Đơn hàng**, tab **Đã duyệt (`admin_approved`)**.
   - Bấm nút **Nhận đơn (Claim)** $\rightarrow$ Đơn được gán cho Staff này và chuyển sang `processing`. Thử mở tab ẩn danh khác với Staff thứ hai bấm nhận đơn cùng lúc $\rightarrow$ Hệ thống kích hoạt cơ chế *Atomic Claim Lock*, báo lỗi `HTTP 409 Đơn đã được nhân viên khác nhận`.
3. **Cập nhật Giao vận (Fulfillment):**
   - Staff bấm **Đóng gói (`packing`)** $\rightarrow$ **Đang giao hàng (`shipping`)** $\rightarrow$ **Đã giao (`delivered`)**.
4. **Đối soát Thanh toán Chuyển khoản (Admin Only):**
   - Staff không có quyền duyệt chuyển khoản ngân hàng.
   - Đăng nhập lại `admin`. Vào chi tiết đơn, kiểm tra mã đối soát ngân hàng $\rightarrow$ Bấm **Xác nhận đã nhận chuyển khoản** $\rightarrow$ `payment_status` chuyển từ `pending_verification` sang `paid`.
   - Đơn hàng đủ điều kiện chuyển thành **Hoàn thành (`completed`)**.

---

### Kịch bản 4: Trợ lý AI Thông minh (SQLite Grounding & Local LLM Failover)
1. **Demo Tư vấn dựa trên dữ liệu thật (Grounding):**
   - Vào trang **Trợ lý AI**.
   - Hỏi: *"Shop có tai nghe nào chống ồn dưới 1 triệu còn hàng không?"*
   - Quan sát câu trả lời:
     - Badge Provider hiển thị `Ollama Local (GPU) (Qwen 2.5 1.5B)`.
     - Phản hồi bằng tiếng Việt chuẩn mực, chỉ gợi ý các mẫu tai nghe **thực tế có trong kho** với tồn kho $> 0$ và đúng giá bán lẻ.
     - Tuyệt đối không bịa đặt sản phẩm ngoài danh mục và không làm lộ giá vốn `cost_price`.
2. **Demo Cơ chế Chống Hallucination & Failover (Tắt Ollama):**
   - Mở Terminal tắt tiến trình Ollama (`Ctrl + C` tại Terminal 1).
   - Đặt lại câu hỏi trên giao diện AI Assistant.
   - Quan sát:
     - Hệ thống không bị treo hoặc crash màn hình trắng.
     - Tự động kích hoạt cơ chế **Safe Grounded Fallback (SQL + Rule Engine)**.
     - Badge Provider chuyển sang màu vàng `Chế độ Tra cứu Trực tiếp (An toàn)`.
     - Trả về danh sách sản phẩm khớp chính xác từ cơ sở dữ liệu SQLite một cách trung thực.

---

### Kịch bản 5: Bảng điều hành Dashboard & Kiểm toán Doanh thu
1. **Đăng nhập với tài khoản `admin`.**
2. **Vào trang Dashboard:**
   - Quan sát **Banner Kiểm toán Tài chính (Financial Audit Banner)** được thiết kế nổi bật:
     - **THỰC NHẬN ĐÃ ĐỐI SOÁT (PAID):** Chỉ tính trên các đơn có dòng tiền thực tế qua sao kê ngân hàng hoặc COD đã nộp quỹ.
     - **LỊCH SỬ CHƯA ĐỐI SOÁT (LEGACY):** **316.063.000 ₫** (phản ánh 140 đơn hoàn tất lịch sử chưa qua đối soát biên lai).
     - **TỔNG GHI NHẬN SỔ SÁCH:** **316.063.000 ₫**.
   - Minh chứng tính trung thực học thuật: Hệ thống **không đánh đồng doanh số sổ sách cũ thành tiền thực thu**, bảo vệ tính liêm chính của báo cáo tài chính.
3. **Xuất báo cáo:** Bấm nút **Xuất CSV** hoặc **Xuất Excel (.xlsx)** để tải file dữ liệu đối soát tức thì.

---

## IV. BẢO TOÀN DỮ LIỆU & AN TOÀN TRƯỚC KHI THI
- Tuyệt đối không xóa file `backend/webstore.db` hoặc thư mục `backend/chroma_data`.
- Sau khi chạy các kịch bản demo trên môi trường test, cơ sở dữ liệu production chính luôn bảo toàn nguyên vẹn **317 đơn lịch sử** và **30 sản phẩm catalog**.
