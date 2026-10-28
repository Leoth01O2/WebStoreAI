from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Product Recommendation Schemas
# ---------------------------------------------------------------------------
class ProductRecommendRequest(BaseModel):
    query: str = Field(..., min_length=2, max_length=4000, description="Customer request or preference query")
    budget: Optional[float] = Field(None, ge=0, description="Optional maximum budget in VND")
    limit: int = Field(5, ge=1, le=20, description="Maximum number of candidates to retrieve")
    provider: Optional[str] = Field(None, description="Optional AI provider: 'ollama', 'gemini', or 'grounded'")


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
    match_reason: Optional[str] = None


class UserQueryIntent(BaseModel):
    intent: str = Field(default="search_products", description="Intent type: search_products, check_brand, check_stock, compare_products, out_of_domain, general_inquiry")
    brand: Optional[str] = Field(default=None, description="Explicit target brand requested e.g. Apple, Sony, Logitech")
    product_type: Optional[str] = Field(default=None, description="Explicit target product class if user named one (e.g. mouse, keyboard, headphone, hub). Must be null if user only describes a function or host device.")
    user_device: Optional[str] = Field(default=None, description="Host device user already owns or connects to, e.g. 'laptop Type-C', 'iPhone 15', 'PC'")
    desired_capabilities: List[str] = Field(default_factory=list, description="Desired functional capabilities, e.g. ['xuất hình ra màn HDMI', 'sạc nhanh', 'nghe nhạc', 'chơi game', 'chống ồn']")
    device_compatibility: List[str] = Field(default_factory=list, description="Required ports or protocols, e.g. ['Type-C', 'HDMI', 'Bluetooth', 'USB-A']")
    required_attributes: List[str] = Field(default_factory=list, description="Mandatory constraints, e.g. ['wireless', 'mechanical', 'silent', 'anc']")
    preferred_attributes: List[str] = Field(default_factory=list, description="Nice-to-have preferences")
    negative_constraints: List[str] = Field(default_factory=list, description="Features explicitly NOT wanted, e.g. ['wired', 'rgb']")
    attributes: Dict[str, Any] = Field(default_factory=dict, description="Backwards-compatible dict of boolean flags e.g. gaming, wireless, wired, mechanical, silent, anc, ergonomic")
    min_price: Optional[float] = Field(default=None, ge=0, description="Minimum budget constraint in VND")
    max_price: Optional[float] = Field(default=None, ge=0, description="Maximum budget constraint in VND")
    needs_clarification: bool = Field(default=False, description="True if query is ambiguous or vague, requiring user clarification")
    clarification_question: Optional[str] = Field(default=None, description="Clarification question to present to the user")
    is_out_of_domain: bool = Field(default=False, description="True if query is out of tech/retail store catalog domain")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="Confidence score of intent extraction")
    source: str = Field(default="rule_based", description="Analyzer source: 'llm_ollama', 'llm_gemini', or 'rule_based'")


class ProductRecommendResponse(BaseModel):
    ai_response: str
    recommended_products: List[RecommendedProductItem]
    alternative_products: Optional[List[RecommendedProductItem]] = []
    effective_budget: Optional[float] = None
    query: str
    total_candidates_found: int
    is_fallback: bool = False
    provider: Optional[str] = Field("grounded", description="Active AI provider: 'ollama', 'gemini', or 'grounded'")
    requested_provider: Optional[str] = Field(None, description="Provider requested by user/client")
    intent_provider_used: Optional[str] = Field("grounded", description="Provider used for intent understanding")
    generation_provider_used: Optional[str] = Field("grounded", description="Provider used for text generation")
    fallback_reason: Optional[str] = Field(None, description="Reason why fallback occurred, if any")
    intent_analysis: Optional[UserQueryIntent] = Field(default=None, description="Structured intent analysis from LLM / Rule-based engine")
    timing_ms: Optional[Dict[str, int]] = Field(default=None, description="Latency breakdown in milliseconds")
    verification_passed: bool = Field(default=True, description="Whether Double SQL verification passed")
    guardrail_status: Optional[str] = Field(default="verified", description="Guardrail outcome: verified, corrected, or fallback")


# ---------------------------------------------------------------------------
# Sales Report Schemas
# ---------------------------------------------------------------------------
class SalesReportRequest(BaseModel):
    period: str = Field(default="this_month", description="Report period: today, 7_days, 30_days, this_month, all_time")
    additional_notes: Optional[str] = Field(default=None, max_length=1000, description="Optional notes or focus areas")
    provider: Optional[str] = Field(None, description="Optional AI provider: 'ollama', 'gemini', or 'grounded'")


class SalesReportResponse(BaseModel):
    ai_analysis: str
    period: str
    total_revenue: float
    total_orders: int
    low_stock_count: int
    top_selling_products: List[Dict[str, Any]]
    is_fallback: bool = False
    provider: Optional[str] = Field("grounded", description="Active AI provider: 'ollama', 'gemini', or 'grounded'")


# ---------------------------------------------------------------------------
# Sales QA Schemas
# ---------------------------------------------------------------------------
class SalesQARequest(BaseModel):
    query: str = Field(..., min_length=2, max_length=4000, description="Natural language question")
    provider: Optional[str] = Field(None, description="Optional AI provider: 'ollama', 'gemini', or 'grounded'")



class SalesQAResponse(BaseModel):
    answer: str
    query: str
    context_type: str = Field("hybrid", description="Source of context: sql, rag, or hybrid")
    is_fallback: bool = False
    provider: Optional[str] = Field("grounded", description="Active AI provider: 'ollama', 'gemini', or 'grounded'")


# ---------------------------------------------------------------------------
# AI Provider Status Schemas (Phase R5)
# ---------------------------------------------------------------------------
class AIProviderDetail(BaseModel):
    provider: str
    available: bool
    status: str
    model: str
    details: Dict[str, Any] = Field(default_factory=dict)


class AIProvidersStatusResponse(BaseModel):
    active_provider: str
    configured_mode: str
    providers: Dict[str, AIProviderDetail]


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
    product_type: Optional[str] = Field(None, description="Chủng loại sản phẩm nhận diện được (headphone, keyboard, mouse...)")
    dominant_color: Optional[str] = Field(None, description="Màu sắc chủ đạo nhận diện được")
    shape_form: Optional[str] = Field(None, description="Kiểu dáng hình học hoặc form factor")
    material: Optional[str] = Field(None, description="Chất liệu nhận diện được")
    visible_features: Optional[List[str]] = Field(default_factory=list, description="Các đặc tính nhìn thấy rõ ràng")
    description: Optional[str] = Field(None, description="Mô tả trực quan của ảnh tìm kiếm")
    confidence: Optional[float] = Field(None, description="Độ tin cậy của phân loại chủng loại")
    is_uncertain: bool = Field(False, description="True khi phân loại chủng loại không đạt ngưỡng tin cậy")
    is_non_product: bool = Field(False, description="True khi ảnh được xác định là phi sản phẩm")


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
    is_uncertain: bool = Field(False, description="True khi mức độ chắc chắn nhận diện loại thiết bị thấp")
    uncertainty_reason: Optional[str] = Field(None, description="Lý do mức độ chắc chắn thấp hoặc không chắc chắn")
    is_quota_exceeded: bool = Field(False, description="True khi gặp lỗi 429 Quota Exceeded từ AI Provider")
    error_message: Optional[str] = Field(None, description="Thông báo lỗi chi tiết khi AI gặp sự cố")
    provider_used: Optional[str] = Field("local", description="AI Provider thực tế được sử dụng: 'local' hoặc 'gemini'")


