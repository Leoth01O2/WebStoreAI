from typing import List
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from app.core.database import get_db
from app.core.security import decode_access_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")
optional_oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)

ROLE_HIERARCHY = {
    "superadmin": 40,
    "admin": 30,
    "staff": 20,
    "customer": 10,
}

def get_current_user(token: str = Depends(oauth2_scheme)) -> dict:
    """
    Dependency lấy thông tin user hiện tại từ Bearer JWT token.
    Bảo đảm user tồn tại trong SQLite và đang hoạt động (is_active = 1).
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Phiên đăng nhập không hợp lệ hoặc đã hết hạn",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    payload = decode_access_token(token)
    if not payload:
        raise credentials_exception
    
    user_id = payload.get("sub")
    if not user_id:
        raise credentials_exception
    
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, username, full_name, role, is_active FROM users WHERE id = ?",
            (user_id,)
        )
        user = cursor.fetchone()
        
    if not user:
        raise credentials_exception
    
    if not user["is_active"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tài khoản đã bị vô hiệu hóa"
        )
        
    return dict(user)

def get_current_user_optional(token: str = Depends(optional_oauth2_scheme)) -> dict | None:
    """
    Dependency lấy thông tin user nếu có token hợp lệ.
    Nếu không có token hoặc token không hợp lệ, trả về None (Guest).
    """
    if not token:
        return None
    
    payload = decode_access_token(token)
    if not payload:
        return None
    
    user_id = payload.get("sub")
    if not user_id:
        return None
    
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, username, full_name, role, is_active FROM users WHERE id = ?",
            (user_id,)
        )
        user = cursor.fetchone()
        
    if not user or not user["is_active"]:
        return None
        
    return dict(user)

def require_roles(*allowed_roles: str):
    """
    Dependency Enforce phân quyền theo vai trò (Role-Based Access Control).
    Kiểm tra quyền trực tiếp tại Backend: Nếu role của user không nằm trong allowed_roles,
    lập tức trả về HTTP 403 Forbidden.
    """
    def role_checker(current_user: dict = Depends(get_current_user)) -> dict:
        if current_user.get("role") not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Quyền truy cập bị từ chối. Chức năng này yêu cầu quyền: {', '.join(allowed_roles)}"
            )
        return current_user
    return role_checker

def get_customer_id_for_user(conn, user: dict):
    """
    Lấy customer_id tương ứng với user trong bảng customers (thông qua user_id).
    """
    if not user:
        return None
    user_id = user.get("id")
    if not user_id:
        return None
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM customers WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    if row:
        return row["id"]
    return None

