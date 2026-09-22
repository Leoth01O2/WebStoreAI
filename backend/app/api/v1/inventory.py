from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from app.core.database import get_db
from app.core.rbac import get_current_user, require_roles
from app.schemas.report import InventoryLogResponse, LowStockAlertItem
from app.services.report_service import ReportService

router = APIRouter(prefix="/inventory", tags=["Inventory & Logs"])

@router.get("/logs", response_model=List[InventoryLogResponse], dependencies=[Depends(require_roles("admin", "superadmin"))])
def get_inventory_logs(
    product_id: Optional[int] = Query(None, description="Lọc theo ID sản phẩm"),
    change_type: Optional[str] = Query(None, description="Lọc theo loại: import, sale, return_cancel, adjustment"),
    reference_code: Optional[str] = Query(None, description="Tìm theo mã hóa đơn hoặc phiếu nhập"),
    current_user: dict = Depends(get_current_user)
):
    """Xem nhật ký biến động kho (Admin, Manager)"""
    with get_db() as conn:
        cursor = conn.cursor()
        query = """
            SELECT il.id, il.product_id, p.sku as product_sku, p.name as product_name,
                   il.change_type, il.reference_code, il.quantity_before,
                   il.change_quantity, il.quantity_after, il.note, il.created_at
            FROM inventory_logs il
            JOIN products p ON il.product_id = p.id
            WHERE 1=1
        """
        params = []

        if product_id is not None:
            query += " AND il.product_id = ?"
            params.append(product_id)

        if change_type:
            query += " AND il.change_type = ?"
            params.append(change_type)

        if reference_code:
            query += " AND il.reference_code LIKE ?"
            params.append(f"%{reference_code.strip()}%")

        query += " ORDER BY il.id DESC LIMIT 100"
        cursor.execute(query, params)
        rows = cursor.fetchall()
        return [dict(r) for r in rows]

@router.get("/low-stock", response_model=List[LowStockAlertItem], dependencies=[Depends(require_roles("staff", "admin", "superadmin"))])
def get_low_stock_alerts(current_user: dict = Depends(get_current_user)):
    """Lấy danh sách sản phẩm chạm ngưỡng tồn kho thấp (Staff, Admin, SuperAdmin)"""
    return ReportService.get_low_stock_products()
