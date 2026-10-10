from pydantic import BaseModel, Field
from typing import Optional

def mask_email(email: Optional[str]) -> Optional[str]:
    """
    Che giấu email an toàn: ví dụ 'an.nguyen@example.com' -> 'a***@example.com'
    """
    if not email or not email.strip():
        return None
    email = email.strip()
    if "@" not in email:
        return "***"
    username, domain = email.split("@", 1)
    if len(username) <= 1:
        masked_user = f"{username}***"
    else:
        masked_user = f"{username[0]}***"
    return f"{masked_user}@{domain}"

class CustomerBase(BaseModel):
    customer_code: str = Field(..., min_length=1, max_length=50, description="Mã khách hàng duy nhất")
    name: str = Field(..., min_length=1, max_length=100, description="Họ và tên khách hàng")
    phone: Optional[str] = Field(None, max_length=20, description="Số điện thoại")
    email: Optional[str] = Field(None, max_length=100, description="Email")
    address: Optional[str] = None
    group_name: str = Field("retail", description="Nhóm khách hàng: retail, vip, wholesale")

class CustomerCreate(CustomerBase):
    pass

class CustomerUpdate(BaseModel):
    customer_code: Optional[str] = None
    name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    group_name: Optional[str] = None

class CustomerResponse(CustomerBase):
    id: int
    user_id: Optional[int] = None
    total_spent: float = 0.0
    created_at: Optional[str] = None

class CustomerAdminResponse(CustomerResponse):
    """Schema đầy đủ cho Admin & SuperAdmin"""
    pass

class CustomerStaffResponse(BaseModel):
    """
    Schema che giấu dữ liệu (Data Masking) cho Staff tại quầy POS:
    - Chỉ chứa các trường cần thiết: id, customer_code, name, phone, group_name, total_spent, created_at.
    - email: Đã được mask dạng 'a***@domain.com'.
    - address: Luôn là None (không lộ địa chỉ chi tiết/số nhà).
    - user_id: Tuyệt đối không trả về ID người dùng nội bộ.
    """
    id: int
    customer_code: str
    name: str
    phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    group_name: str = "retail"
    total_spent: float = 0.0
    created_at: Optional[str] = None

