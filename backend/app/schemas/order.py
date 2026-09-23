from pydantic import BaseModel, Field
from typing import List, Optional, Literal

ORDER_STATUSES = (
    "pending",
    "admin_approved",
    "processing",
    "completed",
    "rejected",
    "cancelled",
)

OrderStatus = Literal[
    "pending",
    "admin_approved",
    "processing",
    "completed",
    "rejected",
    "cancelled",
]

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
    status: Optional[str] = Field("completed", description="Trạng thái đơn hàng: pending, admin_approved, processing, completed, rejected, cancelled")
    note: Optional[str] = None
    items: List[OrderItemCreate] = Field(..., min_length=1, description="Danh sách mặt hàng mua")

class RejectOrderRequest(BaseModel):
    reason: Optional[str] = Field("Đơn hàng bị Admin từ chối", description="Lý do từ chối đơn hàng")

class ForceActionRequest(BaseModel):
    action: str = Field(..., description="Thao tác ngoại lệ: force_cancel, reopen_rejected, override_status")
    reason: str = Field(..., min_length=1, description="Lý do bắt buộc cho thao tác ngoại lệ")
    target_status: Optional[str] = Field(None, description="Trạng thái đích khi sử dụng action override_status")

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
    approved_by: Optional[int] = None
    approved_at: Optional[str] = None
    processed_by: Optional[int] = None
    processed_at: Optional[str] = None
    rejected_by: Optional[int] = None
    rejected_at: Optional[str] = None
    rejection_reason: Optional[str] = None
    created_at: Optional[str] = None
    items: List[OrderItemResponse] = []
