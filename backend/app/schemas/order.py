from pydantic import BaseModel, Field
from typing import List, Optional, Literal

ORDER_STATUSES = (
    "pending",
    "confirmed",
    "admin_approved",
    "processing",
    "completed",
    "rejected",
    "cancelled",
)

OrderStatus = Literal[
    "pending",
    "confirmed",
    "admin_approved",
    "processing",
    "completed",
    "rejected",
    "cancelled",
]

PAYMENT_STATUSES = (
    "unpaid",
    "pending_verification",
    "paid",
    "refund_pending",
    "refunded",
    "unverified_legacy",
)

PaymentStatus = Literal[
    "unpaid",
    "pending_verification",
    "paid",
    "refund_pending",
    "refunded",
    "unverified_legacy",
]

FULFILLMENT_STATUSES = (
    "unfulfilled",
    "packing",
    "shipping",
    "delivered",
    "delivery_failed",
    "returned_to_inventory",
    "legacy_unknown",
)

FulfillmentStatus = Literal[
    "unfulfilled",
    "packing",
    "shipping",
    "delivered",
    "delivery_failed",
    "returned_to_inventory",
    "legacy_unknown",
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
    shipping_name: Optional[str] = Field(None, description="Tên người nhận hàng")
    shipping_phone: Optional[str] = Field(None, description="Số điện thoại người nhận")
    shipping_address: Optional[str] = Field(None, description="Địa chỉ giao hàng")
    discount_amount: float = Field(0.0, ge=0, description="Số tiền giảm giá")
    payment_method: str = Field("cash", description="Phương thức: cash, transfer, card")
    payment_status: Optional[str] = Field(None, description="Trạng thái thanh toán (Backend sẽ chuẩn hóa theo vai trò)")
    status: Optional[str] = Field(None, description="Trạng thái đơn hàng (Khách hàng tạo luôn là pending, POS quầy là completed)")
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
    assigned_to: Optional[int] = None
    assigned_name: Optional[str] = None
    shipping_name: Optional[str] = None
    shipping_phone: Optional[str] = None
    shipping_address: Optional[str] = None
    is_legacy_unverified: int = 0
    total_amount: float
    discount_amount: float
    final_amount: float
    payment_method: str
    payment_status: str = "unpaid"
    payment_status_raw: Optional[str] = None
    fulfillment_status: Optional[str] = None
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

# --- PHASE R3 REQUEST / RESPONSE SCHEMAS ---

class ClaimOrderRequest(BaseModel):
    note: Optional[str] = Field(None, description="Ghi chú khi tiếp nhận đơn hàng")

class ReassignOrderRequest(BaseModel):
    new_staff_id: int = Field(..., description="ID của nhân viên mới được giao xử lý đơn")
    reason: str = Field(..., min_length=1, description="Lý do điều chuyển nhân viên xử lý đơn")

class NotifyTransferRequest(BaseModel):
    transfer_ref: Optional[str] = Field(None, description="Mã giao dịch / mã tham chiếu chuyển khoản")
    transfer_reference: Optional[str] = Field(None, description="Mã giao dịch / mã tham chiếu chuyển khoản")
    bank_name: Optional[str] = Field(None, description="Tên ngân hàng chuyển khoản")
    note: Optional[str] = Field(None, description="Ghi chú chuyển khoản từ khách hàng hoặc nhân viên")

class VerifyPaymentRequest(BaseModel):
    verified_ref: Optional[str] = Field(None, description="Mã đối soát sao kê ngân hàng đã xác minh")
    verified_reference: Optional[str] = Field(None, description="Mã đối soát sao kê ngân hàng đã xác minh")
    note: Optional[str] = Field(None, description="Ghi chú xác minh đối soát của Admin")

class ConfirmCodPaymentRequest(BaseModel):
    note: Optional[str] = Field(None, description="Ghi chú xác nhận thu tiền mặt COD")

class UpdateFulfillmentRequest(BaseModel):
    fulfillment_status: FulfillmentStatus = Field(..., description="Trạng thái giao vận mới: packing, shipping, delivered, delivery_failed")
    note: Optional[str] = Field(None, description="Ghi chú tiến độ vận chuyển")

class ConfirmReturnRequest(BaseModel):
    reason: Optional[str] = Field("Khách từ chối nhận / giao thất bại và đã nhận lại bưu kiện", description="Lý do xác nhận nhập lại kho")
    note: Optional[str] = Field(None, description="Ghi chú của thủ kho khi nhận lại hàng vật lý")

class RequestRefundRequest(BaseModel):
    reason: str = Field(..., min_length=1, description="Lý do yêu cầu hoàn tiền")

class ConfirmRefundRequest(BaseModel):
    refund_ref: Optional[str] = Field(None, description="Mã giao dịch hoàn tiền ngân hàng / phiếu chi tiền mặt")
    refund_reference: Optional[str] = Field(None, description="Mã giao dịch hoàn tiền ngân hàng / phiếu chi tiền mặt")
    reason: Optional[str] = Field("Đã hoàn tiền cho khách qua sao kê / tiền mặt", description="Ghi chú xác nhận hoàn tiền")

class OrderAuditLogResponse(BaseModel):
    id: int
    order_id: int
    action: str
    previous_status: str
    resulting_status: str
    performed_by: Optional[int] = None
    performer_name: Optional[str] = None
    performer_role: Optional[str] = None
    reason: str
    created_at: Optional[str] = None

