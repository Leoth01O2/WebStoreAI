from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Product Recommendation Schemas
# ---------------------------------------------------------------------------
class ProductRecommendRequest(BaseModel):
    query: str = Field(..., min_length=2, max_length=4000, description="Customer request or preference query")
    budget: Optional[float] = Field(None, ge=0, description="Optional maximum budget in VND")
    limit: int = Field(5, ge=1, le=20, description="Maximum number of candidates to retrieve")


class RecommendedProductItem(BaseModel):
    id: Optional[int] = None
    product_id: int
    sku: str
    name: str
    selling_price: float
    stock_quantity: int
    unit: Optional[str] = "cái"
    category_name: Optional[str] = None
    description: Optional[str] = None
    image_url: Optional[str] = None
    status: Optional[str] = "active"
    relevance_score: Optional[float] = None


class ProductRecommendResponse(BaseModel):
    ai_response: str
    recommended_products: List[RecommendedProductItem]
    query: str
    total_candidates_found: int
    is_fallback: bool = False


# ---------------------------------------------------------------------------
# Sales Report Schemas
# ---------------------------------------------------------------------------
class SalesReportRequest(BaseModel):
    period: str = Field(default="this_month", description="Report period: today, 7_days, 30_days, this_month, all_time")
    additional_notes: Optional[str] = Field(default=None, max_length=1000, description="Optional notes or focus areas")


class SalesReportResponse(BaseModel):
    ai_analysis: str
    period: str
    total_revenue: float
    total_orders: int
    low_stock_count: int
    top_selling_products: List[Dict[str, Any]]
    is_fallback: bool = False


# ---------------------------------------------------------------------------
# Sales QA Schemas
# ---------------------------------------------------------------------------
class SalesQARequest(BaseModel):
    query: str = Field(..., min_length=2, max_length=4000, description="Natural language question")



class SalesQAResponse(BaseModel):
    answer: str
    query: str
    context_type: str = Field("hybrid", description="Source of context: sql, rag, or hybrid")
    is_fallback: bool = False


# ---------------------------------------------------------------------------
# AI Audit Log Schemas
# ---------------------------------------------------------------------------
class AIAuditLogResponse(BaseModel):
    id: int
    user_id: Optional[int] = None
    username: Optional[str] = None
    feature: str
    query_text: str
    response_summary: Optional[str] = None
    latency_ms: Optional[int] = None
    created_at: str


# ---------------------------------------------------------------------------
# Image Search Schemas (Phase 12D)
# ---------------------------------------------------------------------------
class ImageSearchQueryFeatures(BaseModel):
    product_type: str = Field(..., description="Chủng loại sản phẩm nhận diện được (headphone, keyboard, mouse...)")
    dominant_color: Optional[str] = Field(None, description="Màu sắc chủ đạo nhận diện được")
    shape_form: Optional[str] = Field(None, description="Kiểu dáng hình học hoặc form factor")
    material: Optional[str] = Field(None, description="Chất liệu nhận diện được")
    visible_features: Optional[List[str]] = Field(default_factory=list, description="Các đặc tính nhìn thấy rõ ràng")
    description: Optional[str] = Field(None, description="Mô tả trực quan của ảnh tìm kiếm")


class ImageSearchResultItem(BaseModel):
    product_id: int
    sku: str
    name: str
    category_id: Optional[int] = None
    category_name: Optional[str] = None
    selling_price: float
    stock_quantity: int
    in_stock: bool
    status: str
    image_url: Optional[str] = None
    description: Optional[str] = None
    # Relationship Classification & Grounding
    relationship: str = Field(..., description="Phân loại quan hệ: match, similar, related, none")
    reason: str = Field(..., description="Giải thích lý do phân loại dựa trên đối chiếu đặc trưng")
    score: float = Field(..., description="Điểm tương đồng kết hợp (0.0 đến 1.0)")
    attr_matches: Optional[List[str]] = Field(default_factory=list, description="Danh sách các thuộc tính khớp trực quan")


class ImageSearchResponse(BaseModel):
    query_features: ImageSearchQueryFeatures
    results: List[ImageSearchResultItem]
    total_candidates_found: int
    execution_time_ms: int
    is_fallback: bool = False
    is_non_product: bool = Field(False, description="True khi ảnh không chứa sản phẩm công nghệ/văn phòng")
    non_product_reason: Optional[str] = Field(None, description="Lý do xác định ảnh không phải sản phẩm")

