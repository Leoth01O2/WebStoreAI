from pydantic import BaseModel, Field
from typing import List, Optional

class PurchaseItemCreate(BaseModel):
    product_id: int = Field(..., description="ID sản phẩm cần nhập")
    quantity: int = Field(..., gt=0, description="Số lượng nhập phải > 0")
    import_price: float = Field(..., ge=0, description="Giá nhập đơn vị")

class PurchaseItemResponse(BaseModel):
    id: int
    product_id: int
    product_sku: Optional[str] = None
    product_name: Optional[str] = None
    quantity: int
    import_price: float
    subtotal: float

class PurchaseCreate(BaseModel):
    supplier_name: str = Field(..., min_length=1, description="Tên nhà cung cấp")
    note: Optional[str] = None
    items: List[PurchaseItemCreate] = Field(..., min_length=1, description="Danh sách mặt hàng nhập")

class PurchaseResponse(BaseModel):
    id: int
    receipt_code: str
    supplier_name: str
    user_id: Optional[int] = None
    user_name: Optional[str] = None
    total_amount: float
    status: str
    note: Optional[str] = None
    created_at: Optional[str] = None
    items: List[PurchaseItemResponse] = []
