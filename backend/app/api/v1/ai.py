from typing import List, Optional
from fastapi import APIRouter, Depends, Query, HTTPException, status, UploadFile, File

from app.core.rbac import get_current_user, get_current_user_optional, require_roles
from app.core.rate_limiter import enforce_ai_rate_limit, ai_rate_limiter
from app.schemas.ai import (
    ProductRecommendRequest,
    ProductRecommendResponse,
    SalesReportRequest,
    SalesReportResponse,
    SalesQARequest,
    SalesQAResponse,
    AIAuditLogResponse,
    ImageSearchResponse
)
from app.services.ai_service import ai_service
from app.services.rag_service import rag_service
from app.services.image_search_service import image_search_service

router = APIRouter(prefix="/ai", tags=["AI & Hybrid RAG Assistant"])



@router.post(
    "/recommend",
    response_model=ProductRecommendResponse,
    summary="AI Tư vấn Sản phẩm (Chỉ tư vấn hàng còn tồn kho - Công khai cho Guest & Khách hàng)"
)
def recommend_products(
    request: ProductRecommendRequest,
    current_user: Optional[dict] = Depends(enforce_ai_rate_limit)
):
    """
    Tư vấn sản phẩm thông minh dựa trên nhu cầu và ngân sách của khách hàng.
    Áp dụng kiến trúc Hybrid RAG: ChromaDB Top-K + Chốt chặn SQLite loại bỏ 100% hàng hết tồn kho.
    Phân quyền: Hỗ trợ Khách vãng lai (Guest), Khách hàng (Customer), Nhân viên (Staff), Admin và SuperAdmin.
    Bảo vệ: Rate Limiting & Giới hạn độ dài input theo vai trò.
    """
    is_valid, length_err = ai_rate_limiter.validate_input_length(request.query, current_user)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=length_err
        )

    user_id = current_user.get("id") if current_user else None
    user_role = current_user.get("role", "guest") if current_user else "guest"
    return ai_service.recommend_products(
        user_query=request.query,
        budget=request.budget,
        limit=request.limit or 5,
        user_id=user_id,
        user_role=user_role
    )


@router.post(
    "/sales-report",
    response_model=SalesReportResponse,
    summary="AI Phân tích & Sinh Báo cáo Doanh thu (SuperAdmin only)"
)
def generate_sales_report(
    request: SalesReportRequest,
    current_user: dict = Depends(require_roles("superadmin")),
    _rate_limit_check: Optional[dict] = Depends(enforce_ai_rate_limit)
):
    """
    Sinh báo cáo phân tích hoạt động kinh doanh, nhận xét doanh thu và đề xuất kế hoạch nhập kho.
    Số liệu lấy chính xác 100% từ SQLite aggregations.
    Phân quyền: Dành riêng cho Chủ cửa hàng (SuperAdmin). Các vai trò Admin, Staff, Customer, Guest bị chặn HTTP 403.
    """
    return ai_service.generate_sales_report(
        period=request.period or "month",
        user_id=current_user.get("id"),
        user_role=current_user.get("role", "superadmin")
    )


@router.post(
    "/sales-qa",
    response_model=SalesQAResponse,
    summary="AI Trợ lý Hỏi đáp & Tư vấn Hệ thống (Phân định phạm vi dữ liệu theo Role)"
)
def answer_sales_qa(
    request: SalesQARequest,
    current_user: Optional[dict] = Depends(enforce_ai_rate_limit)
):
    """
    Trợ lý hỏi đáp tự nhiên StoreFlow AI.
    Phạm vi dữ liệu được enforce nghiêm ngặt tại Backend:
      - SuperAdmin: Báo cáo tài chính, doanh thu thực tế, tồn kho và đề xuất nhập hàng.
      - Admin: Hỗ trợ kỹ thuật hệ thống, danh mục, sản phẩm. Bị chặn truy cập doanh thu/tài chính.
      - Staff: Hỗ trợ bán hàng tại quầy POS, tra cứu thông tin sản phẩm và tồn kho khả dụng.
      - Customer: Tư vấn mua hàng, tra cứu lịch sử đơn hàng của chính mình (qua authenticated customer_id).
      - Guest: Tư vấn sản phẩm công khai, giá niêm yết, thông số kỹ thuật.
    Bảo vệ: Rate Limiting & Giới hạn độ dài câu hỏi theo vai trò.
    """
    is_valid, length_err = ai_rate_limiter.validate_input_length(request.query, current_user)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=length_err
        )

    user_id = current_user.get("id") if current_user else None
    user_role = current_user.get("role", "guest") if current_user else "guest"
    user_full_name = current_user.get("full_name") if current_user else None

    return ai_service.answer_sales_qa(
        question=request.query,
        user_id=user_id,
        user_role=user_role,
        user_full_name=user_full_name
    )



@router.get(
    "/logs",
    response_model=List[AIAuditLogResponse],
    summary="Lịch sử Truy vấn & Kiểm toán AI (Admin/SuperAdmin only)"
)
def get_ai_audit_logs(
    limit: int = Query(50, ge=1, le=200),
    current_user: dict = Depends(require_roles("admin", "superadmin"))
):
    """
    Xem nhật ký kiểm toán AI (thời gian latency, người hỏi, câu hỏi, tóm tắt phản hồi).
    """
    return ai_service.get_audit_logs(limit=limit)


@router.post(
    "/sync-index",
    summary="Đồng bộ lại toàn bộ sản phẩm vào Vector DB ChromaDB (Admin/SuperAdmin only)"
)
def sync_vector_index(
    current_user: dict = Depends(require_roles("admin", "superadmin"))
):
    """
    Buộc quét lại toàn bộ danh mục sản phẩm từ SQLite và nạp lại vào ChromaDB.
    """
    count = rag_service.sync_all_products()
    return {
        "status": "success",
        "message": f"Đã đồng bộ thành công {count} sản phẩm vào ChromaDB",
        "total_indexed": count
    }


@router.post(
    "/image-search",
    response_model=ImageSearchResponse,
    summary="Tìm kiếm sản phẩm bằng hình ảnh (Công khai cho Guest, Customer, Staff, Admin, SuperAdmin)"
)
async def image_search(
    file: UploadFile = File(..., description="File ảnh sản phẩm cần tìm kiếm (JPG, PNG, WebP <= 5MB)"),
    limit: int = Query(5, ge=1, le=20, description="Số lượng sản phẩm tối đa trả về"),
    current_user: Optional[dict] = Depends(enforce_ai_rate_limit)
):
    """
    Tìm kiếm sản phẩm thực tế trong kho bằng hình ảnh tải lên.
    Luồng xử lý (Phase 12D):
    1. Validation: Kiểm tra mime-type, dung lượng (<= 5MB) và tính toàn vẹn file ảnh.
    2. Feature Extraction: Trích xuất đặc trưng hình ảnh (chủng loại, màu sắc, kiểu dáng, mô tả).
    3. Candidate Retrieval: Truy vấn Top-K từ Visual Index có sẵn (Zero bulk Vision API call).
    4. SQLite Truth Guard: Xác minh giá bán thực tế, số lượng tồn kho và trạng thái trực tiếp từ SQLite.
    5. Relationship Classification: Phân loại 4 mức độ (Match, Similar, Related, None) có lý do đối chiếu.
    """
    contents = await file.read()
    user_id = current_user.get("id") if current_user else None

    return image_search_service.search_and_classify(
        image_bytes=contents,
        filename=file.filename or "uploaded_image.jpg",
        content_type=file.content_type,
        limit=limit,
        user_id=user_id
    )

