from pydantic import BaseModel, Field
from typing import Optional, Literal
from enum import Enum
from datetime import datetime

class RoleEnum(str, Enum):
    SUPERADMIN = "superadmin"
    ADMIN = "admin"
    STAFF = "staff"
    CUSTOMER = "customer"

class LoginRequest(BaseModel):
    username: str = Field(..., description="Tên đăng nhập")
    password: str = Field(..., description="Mật khẩu")

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict

class UserResponse(BaseModel):
    id: int
    username: str
    full_name: str
    role: str
    is_active: bool
    created_at: Optional[str] = None

class UserCreate(BaseModel):
    username: str
    password: str
    full_name: str
    role: RoleEnum = RoleEnum.STAFF

class CustomerRegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=30, description="Tên đăng nhập (3-30 ký tự, chữ/số/gạch dưới)")
    password: str = Field(..., min_length=6, max_length=128, description="Mật khẩu bảo mật (6-128 ký tự)")
    full_name: str = Field(..., min_length=1, max_length=100, description="Họ và tên khách hàng")
    phone: str = Field(..., min_length=9, max_length=15, description="Số điện thoại di động Việt Nam (10 số)")
    email: str = Field(..., min_length=5, max_length=100, description="Địa chỉ email hợp lệ")
    address: Optional[str] = Field(None, max_length=255, description="Địa chỉ giao hàng (tùy chọn)")
    
    # Anti-Tampering fields (nếu client gửi, backend sẽ kiểm tra và từ chối)
    role: Optional[str] = Field(None, description="Client không được phép tự chỉ định vai trò")
    user_id: Optional[int] = Field(None, description="Trường quản trị nội bộ")
    customer_id: Optional[int] = Field(None, description="Trường quản trị nội bộ")
    is_active: Optional[bool] = Field(None, description="Trường quản trị nội bộ")

class CustomerRegisterResponse(BaseModel):
    id: int
    username: str
    full_name: str
    role: str = "customer"
    customer_id: int
    customer_code: str
    phone: str
    email: str
    address: Optional[str] = None
    created_at: Optional[str] = None

