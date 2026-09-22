from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from app.core.database import get_db
from app.core.rbac import get_current_user, require_roles, get_customer_id_for_user
from app.schemas.order import OrderCreate, OrderResponse, OrderItemResponse
from app.services.inventory_service import InventoryService

router = APIRouter(prefix="/orders", tags=["Orders & POS"])

class CancelOrderRequest(BaseModel):
    reason: Optional[str] = "Khách hàng yêu cầu trả hàng / đổi ý"

@router.get("", response_model=List[OrderResponse])
def get_orders(
    status: Optional[str] = Query(None, description="Lọc theo trạng thái: completed, cancelled"),
    search: Optional[str] = Query(None, description="Tìm theo mã đơn hàng hoặc tên khách hàng"),
    start_date: Optional[str] = Query(None, description="Từ ngày (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="Đến ngày (YYYY-MM-DD)"),
    current_user: dict = Depends(get_current_user)
):
    """
    Lấy danh sách các hóa đơn bán hàng có lọc và tìm kiếm:
    - Staff / Admin / SuperAdmin: xem toàn bộ hóa đơn của cửa hàng.
    - Customer: CHỈ xem các đơn hàng của chính mình (chống rò rỉ dữ liệu / IDOR).
    """
    with get_db() as conn:
        cursor = conn.cursor()
        query = """
            SELECT o.id, o.order_code, o.customer_id, c.name as customer_name, c.phone as customer_phone,
                   o.user_id, u.full_name as user_name, o.total_amount, o.discount_amount,
                   o.final_amount, o.payment_method, o.payment_status, o.status, o.note, o.created_at
            FROM orders o
            LEFT JOIN customers c ON o.customer_id = c.id
            LEFT JOIN users u ON o.user_id = u.id
            WHERE 1=1
        """
        params = []

        # Enforce quyền riêng tư: Customer chỉ xem đơn hàng của mình
        if current_user.get("role") == "customer":
            own_customer_id = get_customer_id_for_user(conn, current_user)
            if own_customer_id:
                query += " AND (o.user_id = ? OR o.customer_id = ?)"
                params.extend([current_user["id"], own_customer_id])
            else:
                query += " AND o.user_id = ?"
                params.append(current_user["id"])

        if status:
            query += " AND o.status = ?"
            params.append(status)

        if search:
            query += " AND (o.order_code LIKE ? OR c.name LIKE ? OR c.phone LIKE ?)"
            s_param = f"%{search.strip()}%"
            params.extend([s_param, s_param, s_param])

        if start_date:
            query += " AND DATE(o.created_at) >= DATE(?)"
            params.append(start_date)

        if end_date:
            query += " AND DATE(o.created_at) <= DATE(?)"
            params.append(end_date)

        query += " ORDER BY o.id DESC"
        cursor.execute(query, params)
        orders = [dict(r) for r in cursor.fetchall()]

        # Gắn danh sách items tóm tắt cho từng order
        for order in orders:
            cursor.execute(
                """SELECT oi.id, oi.product_id, p.sku as product_sku, p.name as product_name,
                          p.image_url, oi.quantity, oi.unit_price, oi.subtotal
                   FROM order_items oi
                   JOIN products p ON oi.product_id = p.id
                   WHERE oi.order_id = ?""",
                (order["id"],)
            )
            order["items"] = [dict(item) for item in cursor.fetchall()]

        return orders

@router.get("/{order_id}", response_model=OrderResponse)
def get_order_detail(order_id: int, current_user: dict = Depends(get_current_user)):
    """
    Xem chi tiết một hóa đơn bán hàng:
    - Staff / Admin / SuperAdmin: xem chi tiết hóa đơn.
    - Customer: CHỈ xem hóa đơn của chính mình. Truy cập hóa đơn của người khác -> 403 Forbidden (Chống IDOR).
    """
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """SELECT o.id, o.order_code, o.customer_id, c.name as customer_name, c.phone as customer_phone,
                      o.user_id, u.full_name as user_name, o.total_amount, o.discount_amount,
                      o.final_amount, o.payment_method, o.payment_status, o.status, o.note, o.created_at
               FROM orders o
               LEFT JOIN customers c ON o.customer_id = c.id
               LEFT JOIN users u ON o.user_id = u.id
               WHERE o.id = ?""",
            (order_id,)
        )
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Không tìm thấy hóa đơn")

        order_data = dict(row)

        # Chống IDOR: Khách hàng không được xem hóa đơn của người khác
        if current_user.get("role") == "customer":
            own_customer_id = get_customer_id_for_user(conn, current_user)
            is_own_order = (order_data.get("user_id") == current_user["id"]) or (
                own_customer_id is not None and order_data.get("customer_id") == own_customer_id
            )
            if not is_own_order:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Bạn không có quyền xem thông tin hóa đơn của khách hàng khác"
                )

        cursor.execute(
            """SELECT oi.id, oi.product_id, p.sku as product_sku, p.name as product_name,
                      p.image_url, oi.quantity, oi.unit_price, oi.subtotal
               FROM order_items oi
               JOIN products p ON oi.product_id = p.id
               WHERE oi.order_id = ?""",
            (order_id,)
        )
        order_data["items"] = [dict(item) for item in cursor.fetchall()]
        return order_data

@router.post("", response_model=OrderResponse)
def create_order(order_in: OrderCreate, current_user: dict = Depends(get_current_user)):
    """
    Tạo hóa đơn bán hàng POS mới (Atomic Transaction):
    - Khách hàng (Customer): không được mạo danh customer_id của người khác (Anti-IDOR).
    - Tự động trừ tồn kho
    - Ghi log xuất nhập tồn
    - Cập nhật tổng chi tiêu của khách
    - Rollback toàn bộ nếu có lỗi hoặc không đủ tồn kho
    """
    if current_user.get("role") == "customer":
        with get_db() as conn:
            own_customer_id = get_customer_id_for_user(conn, current_user)
            if order_in.customer_id and own_customer_id and order_in.customer_id != own_customer_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Bạn không thể tạo đơn hàng cho khách hàng khác"
                )
            if not order_in.customer_id and own_customer_id:
                order_in.customer_id = own_customer_id

    return InventoryService.create_order(order_in, user_id=current_user["id"])

@router.post("/{order_id}/cancel", dependencies=[Depends(require_roles("admin", "superadmin"))])
def cancel_order(
    order_id: int,
    cancel_in: Optional[CancelOrderRequest] = None,
    current_user: dict = Depends(get_current_user)
):
    """
    Hủy hóa đơn bán hàng (Admin, SuperAdmin only):
    - Tự động hoàn trả số lượng tồn kho nguyên vẹn
    - Ghi log 'return_cancel' vào inventory_logs
    - Trừ lại số tiền chi tiêu của khách hàng
    """
    reason = cancel_in.reason if cancel_in else None
    return InventoryService.cancel_order(order_id, user_id=current_user["id"], cancel_reason=reason)
