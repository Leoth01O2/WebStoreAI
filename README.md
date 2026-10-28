# STOREFLOW AI 2.0 — SMART RETAIL & VINTAGE POS MANAGEMENT

> **Đồ án học phần môn 'Ứng dụng trí tuệ nhân tạo' (StoreFlow AI 2.0):** Hệ thống Quản lý Bán hàng & Điểm bán lẻ (POS) thông minh tích hợp Trí tuệ Nhân tạo Local-First Đa phương thức (Qwen 2.5 1.5B & CLIP ViT-B/32).

---

## ⚡ TỔNG QUAN HỆ THỐNG

StoreFlow AI 2.0 là hệ thống quản lý bán hàng kết hợp phong cách thiết kế **Vintage POS / Modern Retro** với kiến trúc phần mềm hiện đại và trí tuệ nhân tạo cục bộ:
- **Frontend:** React 19, Vite 8.2.2, Be Vietnam Pro typography, tối ưu cảm ứng di động $\ge 44\text{px}$, Crash Trap ErrorBoundary.
- **Backend:** Python 3.12, FastAPI, Pydantic v2, kiến trúc dịch vụ phân tầng.
- **Cơ sở dữ liệu:** SQLite WAL mode với 317 đơn hàng lịch sử và 30 sản phẩm catalog nguyên vẹn, Schema Version 3.
- **Cơ sở dữ liệu Vector:** ChromaDB Persistent Client với 3 collections (`storeflow_products`, `storeflow_product_visuals`, `storeflow_product_visual_vectors`).
- **Text AI:** Ollama Local Qwen 2.5 1.5B (GPU) kết hợp cơ chế tự phục hồi Safe Grounded Fallback (SQL + Rule Engine).
- **Vision AI:** OpenAI CLIP ViT-B/32 chạy 100% trên CPU (0 MB VRAM) tìm kiếm sản phẩm bằng hình ảnh đa phương thức.
- **Phân quyền RBAC:** 5 vai trò phân định rạch ròi (`Guest`, `Customer`, `Staff`, `Admin`, `SuperAdmin`).
- **Bảo mật Dữ liệu:** PII Data Masking cho Staff tại quầy POS, khóa cứng chống IDOR, bảo vệ tuyệt đối giá vốn `cost_price`.

---

## 🛠️ CÀI ĐẶT LẦN ĐẦU KHI CLONE TỪ GITHUB

### 1. Yêu cầu môi trường tiên quyết
- **Python:** 3.10 – 3.12 (khuyên dùng Python 3.12)
- **Node.js:** Phiên bản 18+ & npm
- **Ollama:** Tải và cài đặt từ [ollama.com](https://ollama.com)

---

### 2. Thiết lập từng thành phần (Chỉ làm 1 lần duy nhất)

#### Bước 1: Setup Backend
Mở Terminal 1 tại thư mục gốc của dự án:
```powershell
cd backend

# 1. Tạo môi trường ảo
python -m venv .venv

# 2. Kích hoạt môi trường ảo (Windows PowerShell)
.\.venv\Scripts\Activate.ps1
# Nếu gặp lỗi ExecutionPolicy, chạy: Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass

# 3. Cài đặt thư viện
pip install -r requirements.txt

# 4. Tạo file cấu hình môi trường từ template mẫu
Copy-Item .env.example .env

# 5. Khởi tạo Database và nạp dữ liệu mẫu (sản phẩm, tài khoản, đơn hàng)
python seed_data.py
```

#### Bước 2: Setup Ollama (AI Cục Bộ)
Mở Terminal 2:
```powershell
# Tải mô hình Qwen 2.5 1.5B (chỉ cần tải 1 lần đầu)
ollama pull qwen2.5:1.5b

# Khởi chạy dịch vụ Ollama
ollama serve
```

#### Bước 3: Setup Frontend
Mở Terminal 3:
```powershell
cd frontend
npm install
```

---

## 🚀 HƯỚNG DẪN KHỞI ĐỘNG HỆ THỐNG (CÁC LẦN MỞ SAU)

### Cách 1: Khởi động tự động 1-Click (Khuyên dùng)
Tại thư mục gốc dự án:
- **Nhấp đúp chuột vào file `start_dev.bat`** (hoặc chạy file `start_dev.ps1` trong PowerShell).
- File sẽ tự động bật 3 cửa sổ dịch vụ (Ollama, Backend, Frontend) cùng lúc.

---

### Cách 2: Khởi động thủ công (3 Terminal)

#### Terminal 1: Ollama AI
```powershell
ollama serve
```

#### Terminal 2: Backend FastAPI
```powershell
cd backend
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```
*Tài liệu API Swagger:* `http://localhost:8000/docs`

#### Terminal 3: Frontend React
```powershell
cd frontend
npm run dev
```
*Giao diện StoreFlow AI:* `http://localhost:5173`

---

## 👥 TÀI KHOẢN THỬ NGHIỆM HỆ THỐNG

| Vai trò (Role) | Tên đăng nhập | Mật khẩu | Chức năng chính |
| :--- | :--- | :--- | :--- |
| **Guest** | *(Khách vãng lai)* | *(Trống)* | Xem catalog sản phẩm, tìm kiếm ảnh CLIP, chat tư vấn AI, giỏ hàng tạm. |
| **Customer** | `khachhang1` | `Customer@123` | Đăng ký mới, đặt hàng cá nhân, theo dõi đơn riêng, chống IDOR. |
| **Staff** | `staff` | `Staff@123` | POS bán hàng, tra cứu khách hàng PII Masked, claim đơn, giao vận, COD. |
| **Admin** | `admin` | `Admin@123` | CRUD sản phẩm, duyệt đơn, đối soát chuyển khoản ngân hàng, xem Dashboard. |
| **SuperAdmin** | `superadmin` | `SuperAdmin@123` | Toàn quyền, can thiệp ngoại lệ (Force Cancel/Reopen) có lý do & audit log. |

---

## 📚 TÀI LIỆU DỰ ÁN CHI TIẾT

- **Kịch bản Báo cáo Học phần / Demo (Demo Guide):** [docs/R8_DEMO_GUIDE.md](docs/R8_DEMO_GUIDE.md)
- **Báo cáo Nghiệm thu Kỹ thuật R8:** [docs/R8_FINAL_QA_REPORT.md](docs/R8_FINAL_QA_REPORT.md)
- **Lộ trình Tái cấu trúc R0 – R8:** [docs/REFACTOR_ROADMAP.md](docs/REFACTOR_ROADMAP.md)
- **Kiến trúc RAG & Grounding:** [docs/RAG_ARCHITECTURE.md](docs/RAG_ARCHITECTURE.md)
- **Cẩm nang Bảo vệ AI:** [docs/AI_DEFENSE_GUIDE.md](docs/AI_DEFENSE_GUIDE.md)
