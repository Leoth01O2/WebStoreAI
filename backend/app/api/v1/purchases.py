from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from app.core.database import get_db
from app.core.rbac import get_current_user, require_roles
from app.schemas.purchase import PurchaseCreate, PurchaseResponse
from app.services.inventory_service import InventoryService

router = APIRouter(prefix="/purchases", tags=["Purchases & Import"])

@router.get("", response_model=List[PurchaseResponse], dependencies=[Depends(require_roles("admin", "superadmin"))])
def get_purchases(current_user: dict = Depends(get_current_user)):
    """Lấy danh sách các phiếu nhập hàng (Admin, Manager)"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """SELECT pr.id, pr.receipt_code, pr.supplier_name, pr.user_id,
                      u.full_name as user_name, pr.total_amount, pr.status, pr.note, pr.created_at
               FROM purchase_receipts pr
               LEFT JOIN users u ON pr.user_id = u.id
               ORDER BY pr.id DESC"""
        )
        receipts = [dict(r) for r in cursor.fetchall()]

        for receipt in receipts:
            cursor.execute(
                """SELECT pi.id, pi.product_id, p.sku as product_sku, p.name as product_name,
                          pi.quantity, pi.import_price, pi.subtotal
                   FROM purchase_items pi
                   JOIN products p ON pi.product_id = p.id
                   WHERE pi.receipt_id = ?""",
                (receipt["id"],)
            )
            receipt["items"] = [dict(item) for item in cursor.fetchall()]

        return receipts

@router.get("/{purchase_id}", response_model=PurchaseResponse, dependencies=[Depends(require_roles("admin", "superadmin"))])
def get_purchase_detail(purchase_id: int, current_user: dict = Depends(get_current_user)):
    """Xem chi tiết một phiếu nhập hàng kèm danh sách sản phẩm (Admin, Manager)"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """SELECT pr.id, pr.receipt_code, pr.supplier_name, pr.user_id,
                      u.full_name as user_name, pr.total_amount, pr.status, pr.note, pr.created_at
               FROM purchase_receipts pr
               LEFT JOIN users u ON pr.user_id = u.id
               WHERE pr.id = ?""",
            (purchase_id,)
        )
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Không tìm thấy phiếu nhập hàng")

        receipt_data = dict(row)
        cursor.execute(
            """SELECT pi.id, pi.product_id, p.sku as product_sku, p.name as product_name,
                      pi.quantity, pi.import_price, pi.subtotal
               FROM purchase_items pi
               JOIN products p ON pi.product_id = p.id
               WHERE pi.receipt_id = ?""",
            (purchase_id,)
        )
        receipt_data["items"] = [dict(item) for item in cursor.fetchall()]
        return receipt_data

@router.post("", response_model=PurchaseResponse, dependencies=[Depends(require_roles("admin", "superadmin"))])
def create_purchase(purchase_in: PurchaseCreate, current_user: dict = Depends(get_current_user)):
    """
    Tạo phiếu nhập hàng và tự động cập nhật số lượng tồn kho và giá vốn (Admin, Manager):
    - Tăng tồn kho tương ứng
    - Cập nhật giá vốn cost_price
    - Ghi log 'import' vào inventory_logs
    """
    return InventoryService.create_purchase(purchase_in, user_id=current_user["id"])
