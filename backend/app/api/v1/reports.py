from typing import List
from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response, StreamingResponse
from app.core.rbac import get_current_user, require_roles
from app.schemas.report import DashboardSummaryResponse, RevenueTrendItem, TopProductItem
from app.services.report_service import ReportService

router = APIRouter(prefix="/reports", tags=["Reports & Analytics"])

@router.get("/summary", response_model=DashboardSummaryResponse, dependencies=[Depends(require_roles("superadmin"))])
def get_summary(current_user: dict = Depends(get_current_user)):
    """Lấy số liệu tổng quan điều hành (Chỉ dành riêng cho SuperAdmin - Chủ cửa hàng)"""
    return ReportService.get_dashboard_summary()

@router.get("/revenue-trend", response_model=List[RevenueTrendItem], dependencies=[Depends(require_roles("superadmin"))])
def get_revenue_trend(days: int = Query(7, ge=1, le=90), current_user: dict = Depends(get_current_user)):
    """Biểu đồ doanh thu theo ngày (Chỉ dành riêng cho SuperAdmin - Chủ cửa hàng)"""
    return ReportService.get_revenue_trend(days=days)

@router.get("/top-products", response_model=List[TopProductItem], dependencies=[Depends(require_roles("superadmin"))])
def get_top_products(limit: int = Query(5, ge=1, le=50), current_user: dict = Depends(get_current_user)):
    """Top các mặt hàng bán chạy nhất (Chỉ dành riêng cho SuperAdmin - Chủ cửa hàng)"""
    return ReportService.get_top_products(limit=limit)

@router.get("/export/csv", dependencies=[Depends(require_roles("superadmin"))])
def export_orders_csv(current_user: dict = Depends(get_current_user)):
    """Xuất danh sách hóa đơn ra file CSV tải về (Chỉ dành riêng cho SuperAdmin - Chủ cửa hàng)"""
    csv_content = ReportService.export_orders_csv()
    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=danh_sach_hoa_don.csv"}
    )

@router.get("/export/excel", dependencies=[Depends(require_roles("superadmin"))])
def export_orders_excel(current_user: dict = Depends(get_current_user)):
    """Xuất danh sách hóa đơn ra file Excel (.xlsx) tải về (Chỉ dành riêng cho SuperAdmin - Chủ cửa hàng)"""
    excel_stream = ReportService.export_orders_excel()
    return StreamingResponse(
        excel_stream,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=danh_sach_hoa_don.xlsx"}
    )
