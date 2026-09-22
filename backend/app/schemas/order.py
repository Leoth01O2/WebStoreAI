from pydantic import BaseModel, Field
from typing import List, Optional

class OrderItemCreate(BaseModel):
    product_id: int = Field(..., description="ID sản phẩm")
    quantity: int = Field(..., gt=0, description="Số lượng mua phải lớn hơn 0")

class OrderItemResponse(BaseModel):
    id: int
    product_id: int
    product_sku: Optional[str] = None
    product_name: Optional[str] = None
    image_url: Optional[str] = None
    quantity: int
    unit_price: float
    subtotal: float

class OrderCreate(BaseModel):
    customer_id: Optional[int] = Field(None, description="ID khách hàng (nếu có)")
    discount_amount: float = Field(0.0, ge=0, description="Số tiền giảm giá")
    payment_method: str = Field("cash", description="Phương thức: cash, transfer, card")
    payment_status: Optional[str] = Field("completed", description="Trạng thái thanh toán: pending, paid, completed")
    note: Optional[str] = None
    items: List[OrderItemCreate] = Field(..., min_length=1, description="Danh sách mặt hàng mua")

class OrderResponse(BaseModel):
    id: int
    order_code: str
    customer_id: Optional[int] = None
    customer_name: Optional[str] = None
    customer_phone: Optional[str] = None
    user_id: Optional[int] = None
    user_name: Optional[str] = None
    total_amount: float
    discount_amount: float
    final_amount: float
    payment_method: str
    payment_status: str = "completed"
    status: str
    note: Optional[str] = None
    created_at: Optional[str] = None
    items: List[OrderItemResponse] = []
