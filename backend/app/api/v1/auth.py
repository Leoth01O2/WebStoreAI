from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from app.core.database import get_db
from app.core.security import verify_password, create_access_token, hash_password
from app.core.rbac import get_current_user, require_roles
from app.schemas.auth import LoginRequest, TokenResponse, UserResponse, UserCreate

router = APIRouter(prefix="/auth", tags=["Authentication"])

@router.post("/login", response_model=TokenResponse)
def login_json(request: LoginRequest):
    """
    Đăng nhập bằng JSON payload (dùng cho Frontend React / Postman).
    Kiểm tra username, password_hash bằng bcrypt.
    Trả về JWT Bearer token và thông tin người dùng.
    """
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, username, password_hash, full_name, role, is_active FROM users WHERE username = ?",
            (request.username,)
        )
        user = cursor.fetchone()

    if not user or not verify_password(request.password, user["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Tên đăng nhập hoặc mật khẩu không chính xác",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user["is_active"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tài khoản đã bị vô hiệu hóa"
        )

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
def login_form(form_data: OAuth2PasswordRequestForm = Depends()):
    """
    Hỗ trợ form-data cho nút 'Authorize' trên Swagger UI (/docs).
    """
    return login_json(LoginRequest(username=form_data.username, password=form_data.password))

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
