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

