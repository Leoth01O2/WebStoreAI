import re
import uuid
from typing import List
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from app.core.database import get_db, get_db_transaction
from app.core.security import verify_password, create_access_token, hash_password
from app.core.rbac import get_current_user, require_roles
from app.core.rate_limiter import login_rate_limiter, register_rate_limiter
from app.schemas.auth import (
    LoginRequest,
    TokenResponse,
    UserResponse,
    UserCreate,
    CustomerRegisterRequest,
    CustomerRegisterResponse
)

router = APIRouter(prefix="/auth", tags=["Authentication"])

@router.post("/login", response_model=TokenResponse)
def login_json(request: Request, login_data: LoginRequest):
    """
    Đăng nhập bằng JSON payload (dùng cho Frontend React / Postman).
    - Bảo vệ Rate Limit chống Brute-Force: Tối đa 5 lần thử thất bại/phút cho từng cặp (IP, username).
    - Trả về HTTP 429 nếu vượt ngưỡng.
    - Kiểm tra username, password_hash bằng bcrypt.
    - Trả về JWT Bearer token và thông tin người dùng.
    """
    # 1. Kiểm tra giới hạn tần suất thử thất bại
    is_limited, retry_after = login_rate_limiter.is_rate_limited(request, login_data.username)
    if is_limited:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Quá nhiều lần đăng nhập thất bại cho tài khoản này. Vui lòng thử lại sau {retry_after} giây.",
            headers={"Retry-After": str(retry_after)}
        )

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, username, password_hash, full_name, role, is_active FROM users WHERE username = ?",
            (login_data.username,)
        )
        user = cursor.fetchone()

    if not user or not verify_password(login_data.password, user["password_hash"]):
        # Ghi nhận lần thử thất bại
        login_rate_limiter.record_failure(request, login_data.username)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Tên đăng nhập hoặc mật khẩu không chính xác",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user["is_active"]:
        login_rate_limiter.record_failure(request, login_data.username)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tài khoản đã bị vô hiệu hóa"
        )

    # Đăng nhập thành công: Xóa bộ đếm thất bại
    login_rate_limiter.record_success(request, login_data.username)

    user_data = {
        "id": user["id"],
        "username": user["username"],
        "full_name": user["full_name"],
        "role": user["role"]
    }
    access_token = create_access_token(data={"sub": str(user["id"]), "role": user["role"], "username": user["username"]})

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        user=user_data
    )

@router.post("/token", response_model=TokenResponse, include_in_schema=False)
def login_form(request: Request, form_data: OAuth2PasswordRequestForm = Depends()):
    """
    Hỗ trợ form-data cho nút 'Authorize' trên Swagger UI (/docs).
    """
    return login_json(request, LoginRequest(username=form_data.username, password=form_data.password))

@router.post("/register", response_model=CustomerRegisterResponse, status_code=status.HTTP_201_CREATED)
def register_customer(request: Request, reg_data: CustomerRegisterRequest):
    """
    Đăng ký tài khoản Khách hàng công khai (Public Customer Registration - Phase R1B).
    - Tạo nguyên tử tài khoản users (role='customer') và hồ sơ customers (group_name='retail').
    - Áp dụng Rate Limiting: 3 lượt đăng ký / IP / 10 phút.
    - Kiểm tra trùng lặp (username, phone, email) trả về HTTP 409 Conflict.
    - Chống leo thang đặc quyền (Anti-Role Escalation): Khóa cứng role='customer'.
    """
    # 1. Rate Limiting Check
    is_limited, retry_after = register_rate_limiter.is_rate_limited(request)
    if is_limited:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Quá nhiều lượt đăng ký từ địa chỉ mạng của bạn. Vui lòng thử lại sau {retry_after} giây.",
            headers={"Retry-After": str(retry_after)}
        )

    # 2. Anti-Role Escalation & Anti-Tampering Validation
    if reg_data.role is not None and reg_data.role.strip().lower() != "customer":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Đăng ký công khai chỉ cho phép tạo tài khoản Khách hàng (Customer). Không được chỉ định vai trò khác."
        )
    if reg_data.user_id is not None or reg_data.customer_id is not None or reg_data.is_active is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Không được phép tự chỉ định các trường quản trị nội bộ (user_id, customer_id, is_active)."
        )

    # 3. Format Validation
    clean_username = reg_data.username.strip()
    if not re.match(r"^[a-zA-Z0-9_]{3,30}$", clean_username):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tên đăng nhập chỉ được chứa chữ cái, chữ số và dấu gạch dưới (độ dài 3-30 ký tự)."
        )

    clean_pwd = reg_data.password
    if len(clean_pwd) < 6 or len(clean_pwd) > 128:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Mật khẩu phải từ 6 đến 128 ký tự."
        )

    clean_phone = re.sub(r"[\s\-\.]", "", reg_data.phone.strip())
    if clean_phone.startswith("+84"):
        clean_phone = "0" + clean_phone[3:]
    if not re.match(r"^0[3|5|7|8|9][0-9]{8}$", clean_phone):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Số điện thoại không hợp lệ (phải là số di động Việt Nam 10 chữ số bắt đầu bằng 03, 05, 07, 08, 09)."
        )

    clean_email = reg_data.email.strip().lower()
    if not re.match(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$", clean_email):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Địa chỉ email không đúng định dạng."
        )

    clean_full_name = reg_data.full_name.strip()
    clean_address = reg_data.address.strip() if reg_data.address else ""

    # 4. Atomic Write Transaction (BEGIN IMMEDIATE)
    with get_db_transaction() as conn:
        cursor = conn.cursor()

        # Kiểm tra trùng username
        cursor.execute("SELECT id FROM users WHERE username = ?", (clean_username,))
        if cursor.fetchone():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Tên đăng nhập '{clean_username}' đã được sử dụng."
            )

        # Kiểm tra trùng phone trong customers
        cursor.execute("SELECT id, user_id FROM customers WHERE phone = ?", (clean_phone,))
        existing_phone = cursor.fetchone()
        if existing_phone:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Số điện thoại '{clean_phone}' đã tồn tại trong hệ thống khách hàng."
            )

        # Kiểm tra trùng email trong customers
        cursor.execute("SELECT id, user_id FROM customers WHERE email = ?", (clean_email,))
        existing_email = cursor.fetchone()
        if existing_email:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Địa chỉ email '{clean_email}' đã tồn tại trong hệ thống khách hàng."
            )

        # Tạo user với role 'customer'
        pw_hash = hash_password(clean_pwd)
        cursor.execute(
            """INSERT INTO users (username, password_hash, full_name, role, is_active)
               VALUES (?, ?, ?, 'customer', 1)""",
            (clean_username, pw_hash, clean_full_name)
        )
        new_user_id = cursor.lastrowid

        # Tạo mã khách hàng không trùng lặp
        customer_code = f"CUS-U{new_user_id:04d}"
        cursor.execute("SELECT id FROM customers WHERE customer_code = ?", (customer_code,))
        if cursor.fetchone():
            customer_code = f"CUS-U{new_user_id:04d}-{uuid.uuid4().hex[:4].upper()}"

        # Tạo hồ sơ khách hàng liên kết với user_id vừa tạo
        cursor.execute(
            """INSERT INTO customers (user_id, customer_code, name, phone, email, address, group_name, total_spent)
               VALUES (?, ?, ?, ?, ?, ?, 'retail', 0.0)""",
            (new_user_id, customer_code, clean_full_name, clean_phone, clean_email, clean_address)
        )
        new_customer_id = cursor.lastrowid

        cursor.execute("SELECT created_at FROM users WHERE id = ?", (new_user_id,))
        created_at_row = cursor.fetchone()
        created_at_val = created_at_row["created_at"] if created_at_row else None

    # Ghi nhận lượt đăng ký vào rate limiter
    register_rate_limiter.record_attempt(request)

    return CustomerRegisterResponse(
        id=new_user_id,
        username=clean_username,
        full_name=clean_full_name,
        role="customer",
        customer_id=new_customer_id,
        customer_code=customer_code,
        phone=clean_phone,
        email=clean_email,
        address=clean_address,
        created_at=str(created_at_val) if created_at_val else None
    )

@router.get("/me", response_model=UserResponse)
def get_current_user_profile(current_user: dict = Depends(get_current_user)):
    """
    Lấy thông tin tài khoản hiện đang đăng nhập (Yêu cầu JWT Bearer token).
    """
    return UserResponse(
        id=current_user["id"],
        username=current_user["username"],
        full_name=current_user["full_name"],
        role=current_user["role"],
        is_active=bool(current_user["is_active"])
    )

@router.get("/users", response_model=List[UserResponse], dependencies=[Depends(require_roles("admin", "superadmin"))])
def list_users(current_user: dict = Depends(get_current_user)):
    """
    Danh sách tài khoản hệ thống (Chỉ Admin và SuperAdmin).
    Staff hoặc Customer gọi endpoint này sẽ nhận HTTP 403 Forbidden.
    """
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, username, full_name, role, is_active FROM users ORDER BY id ASC")
        rows = cursor.fetchall()
        return [
            UserResponse(
                id=r["id"],
                username=r["username"],
                full_name=r["full_name"],
                role=r["role"],
                is_active=bool(r["is_active"])
            )
            for r in rows
        ]

@router.post("/users", response_model=UserResponse, dependencies=[Depends(require_roles("admin", "superadmin"))])
def create_user_by_admin(user_in: UserCreate, current_user: dict = Depends(get_current_user)):
    """
    Tạo tài khoản mới:
    - SuperAdmin: có thể tạo tài khoản với bất kỳ role nào (superadmin, admin, staff, customer).
    - Admin: CHỈ được tạo staff hoặc customer. Không được tự nâng quyền tạo admin hoặc superadmin (Anti Role Escalation -> 403).
    """
    role_val = user_in.role.value if hasattr(user_in.role, "value") else str(user_in.role)

    # Chống Role Escalation: Admin không được tạo Admin hoặc SuperAdmin
    if current_user.get("role") == "admin" and role_val in ("admin", "superadmin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin không có quyền tạo tài khoản Admin hoặc SuperAdmin"
        )

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM users WHERE username = ?", (user_in.username,))
        if cursor.fetchone():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Tên đăng nhập '{user_in.username}' đã tồn tại"
            )

        hashed = hash_password(user_in.password)
        cursor.execute(
            "INSERT INTO users (username, password_hash, full_name, role, is_active) VALUES (?, ?, ?, ?, 1)",
            (user_in.username, hashed, user_in.full_name, role_val)
        )
        new_id = cursor.lastrowid
        conn.commit()

    return UserResponse(
        id=int(new_id or 0),
        username=user_in.username,
        full_name=user_in.full_name,
        role=role_val,
        is_active=True
    )
