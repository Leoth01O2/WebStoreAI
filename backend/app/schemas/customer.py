from pydantic import BaseModel, Field
from typing import Optional

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
