from pydantic import BaseModel, Field
from typing import Optional

class ProductBase(BaseModel):
    sku: str = Field(..., min_length=1, max_length=50, description="Mã SKU duy nhất của sản phẩm")
    name: str = Field(..., min_length=1, max_length=255, description="Tên sản phẩm")
    category_id: Optional[int] = Field(None, description="ID danh mục hàng hóa")
    cost_price: float = Field(0.0, ge=0, description="Giá vốn/giá nhập")
    selling_price: float = Field(..., ge=0, description="Giá bán lẻ")
    stock_quantity: int = Field(0, ge=0, description="Số lượng tồn kho ban đầu")
    min_stock_alert: int = Field(5, ge=0, description="Ngưỡng cảnh báo sắp hết hàng")
    unit: str = Field("cái", description="Đơn vị tính (cái, chiếc, bộ...)")
    status: str = Field("active", description="Trạng thái: active hoặc inactive")
    image_url: Optional[str] = Field(None, description="Đường dẫn ảnh sản phẩm (upload nội bộ hoặc URL ảnh)")
    description: Optional[str] = Field(None, description="Mô tả chi tiết đặc tính kỹ thuật sản phẩm")

class ProductCreate(ProductBase):
    pass

class ProductUpdate(BaseModel):
    sku: Optional[str] = Field(None, min_length=1, max_length=50)
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    category_id: Optional[int] = None
    cost_price: Optional[float] = Field(None, ge=0)
    selling_price: Optional[float] = Field(None, ge=0)
    stock_quantity: Optional[int] = Field(None, ge=0)
    min_stock_alert: Optional[int] = Field(None, ge=0)
    unit: Optional[str] = None
    status: Optional[str] = None
    image_url: Optional[str] = None
    description: Optional[str] = None

class ProductResponse(ProductBase):
    id: int
    category_name: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

class ProductPublicResponse(BaseModel):
    id: int
    sku: str
    name: str
    category_id: Optional[int] = None
    category_name: Optional[str] = None
    selling_price: float
    stock_quantity: int
    in_stock: bool = True
    unit: str = "cái"
    status: str = "active"
    image_url: Optional[str] = None
    description: Optional[str] = None

# --- PRODUCT VISUAL METADATA SCHEMAS (PHASE 12B) ---

class ProductVisualMetadataBase(BaseModel):
    product_type: str = Field(..., min_length=1, max_length=100, description="Chủng loại sản phẩm thị giác (gaming headset, mechanical keyboard, wireless mouse...)")
    dominant_color: Optional[str] = Field(None, max_length=50, description="Màu sắc chủ đạo (black, white, rgb, grey...)")
    shape_form: Optional[str] = Field(None, max_length=100, description="Kiểu dáng hình học/form factor (over-ear, tenkeyless, ergonomic...)")
    material: Optional[str] = Field(None, max_length=100, description="Chất liệu nhận diện (plastic, aluminum, leatherette, wood...)")
    visible_features: Optional[str] = Field(None, description="Danh sách đặc tính có thể nhìn thấy (JSON string dạng mảng hoặc text)")
    visual_description: Optional[str] = Field(None, description="Đoạn văn mô tả chi tiết đặc trưng thị giác của sản phẩm")
    search_keywords: Optional[str] = Field(None, description="Từ khóa thị giác phục vụ tìm kiếm")
    visual_embedding: Optional[str] = Field(None, description="Chuỗi vector embedding trích xuất dạng text nếu có")

class ProductVisualMetadataCreate(ProductVisualMetadataBase):
    product_id: int = Field(..., description="ID sản phẩm liên kết (products.id)")
    image_path: str = Field(..., min_length=1, description="Đường dẫn hoặc URL ảnh sản phẩm")

class ProductVisualMetadataUpdate(BaseModel):
    image_path: Optional[str] = None
    product_type: Optional[str] = None
    dominant_color: Optional[str] = None
    shape_form: Optional[str] = None
    material: Optional[str] = None
    visible_features: Optional[str] = None
    visual_description: Optional[str] = None
    search_keywords: Optional[str] = None
    visual_embedding: Optional[str] = None

class ProductVisualMetadataResponse(ProductVisualMetadataBase):
    id: int
    product_id: int
    image_path: str
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

