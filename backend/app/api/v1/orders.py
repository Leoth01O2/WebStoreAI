from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from app.core.database import get_db
from app.core.rbac import get_current_user, require_roles, get_customer_id_for_user
from app.schemas.order import OrderCreate, OrderResponse, OrderItemResponse, RejectOrderRequest, ForceActionRequest
from app.services.inventory_service import InventoryService

router = APIRouter(prefix="/orders", tags=["Orders & POS"])

class CancelOrderRequest(BaseModel):
    reason: Optional[str] = "Khách hàng yêu cầu trả hàng / đổi ý"

@router.get("", response_model=List[OrderResponse])
def get_orders(
    status: Optional[str] = Query(None, description="Lọc theo trạng thái: pending, admin_approved, processing, completed, rejected, cancelled"),
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
                   o.final_amount, o.payment_method, o.payment_status, o.status, o.note,
                   o.assigned_to, o.shipping_name, o.shipping_phone, o.shipping_address, o.is_legacy_unverified,
                   o.approved_by, o.approved_at, o.processed_by, o.processed_at,
                   o.rejected_by, o.rejected_at, o.rejection_reason,
                   o.created_at
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
            if "," in status:
                stat_list = [s.strip() for s in status.split(",") if s.strip()]
                placeholders = ",".join("?" for _ in stat_list)
                query += f" AND o.status IN ({placeholders})"
                params.extend(stat_list)
            else:
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

@router.get("/workflow-counts")
def get_workflow_counts(current_user: dict = Depends(get_current_user)):
    """
    Trả về số lượng đơn hàng theo từng trạng thái phục vụ các chỉ số luồng vận hành (Phase 13F):
    - Admin / SuperAdmin / Manager: pending_count, approved_count, processing_count
    - Staff: approved_count, processing_count
    - Customer: my_pending_count, my_processing_count (Chống IDOR - chỉ tính đơn của chính mình)
    """
    user_role = current_user.get("role")
    with get_db() as conn:
        cursor = conn.cursor()

        if user_role in ("admin", "superadmin", "manager"):
            cursor.execute("""
                SELECT status, COUNT(*) as cnt
                FROM orders
                WHERE status IN ('pending', 'admin_approved', 'processing')
                GROUP BY status
            """)
            counts = {row["status"]: row["cnt"] for row in cursor.fetchall()}
            return {
                "pending_count": counts.get("pending", 0),
                "approved_count": counts.get("admin_approved", 0),
                "processing_count": counts.get("processing", 0),
            }

        elif user_role == "staff":
            cursor.execute("""
                SELECT status, COUNT(*) as cnt
                FROM orders
                WHERE status IN ('admin_approved', 'processing')
                GROUP BY status
            """)
            counts = {row["status"]: row["cnt"] for row in cursor.fetchall()}
            return {
                "approved_count": counts.get("admin_approved", 0),
                "processing_count": counts.get("processing", 0),
            }

        elif user_role == "customer":
            own_customer_id = get_customer_id_for_user(conn, current_user)
            if own_customer_id:
                cursor.execute("""
                    SELECT status, COUNT(*) as cnt
                    FROM orders
                    WHERE (user_id = ? OR customer_id = ?)
                      AND status IN ('pending', 'admin_approved', 'processing')
                    GROUP BY status
                """, (current_user["id"], own_customer_id))
            else:
                cursor.execute("""
                    SELECT status, COUNT(*) as cnt
                    FROM orders
                    WHERE user_id = ?
                      AND status IN ('pending', 'admin_approved', 'processing')
                    GROUP BY status
                """, (current_user["id"],))

            counts = {row["status"]: row["cnt"] for row in cursor.fetchall()}
            return {
                "my_pending_count": counts.get("pending", 0),
                "my_processing_count": counts.get("processing", 0),
            }

        return {}

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
                      o.final_amount, o.payment_method, o.payment_status, o.status, o.note,
                      o.assigned_to, o.shipping_name, o.shipping_phone, o.shipping_address, o.is_legacy_unverified,
                      o.approved_by, o.approved_at, o.processed_by, o.processed_at,
                      o.rejected_by, o.rejected_at, o.rejection_reason,
                      o.created_at
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
    - Khách hàng (Customer):
        + Bắt buộc phải có hồ sơ customers liên kết với current_user.
        + Tự động gán customer_id chính chủ từ cơ sở dữ liệu.
        + Nếu client cố tình gửi customer_id khác -> từ chối HTTP 403 Forbidden (Anti-IDOR).
        + Không có hồ sơ hợp lệ -> từ chối HTTP 400 Bad Request, không được mượn ID người khác.
        + Khởi tạo bắt buộc ở trạng thái PENDING.
    - Staff / Admin / SuperAdmin lập tại quầy POS:
        + Hỗ trợ tạo đơn khách lẻ hoặc chọn khách hàng tại quầy.
        + Mặc định trạng thái COMPLETED.
    - Tự động trừ tồn kho (giữ chỗ) trong transaction nguyên tử.
    """
    user_role = current_user.get("role")
    if user_role == "customer":
        with get_db() as conn:
            own_customer_id = get_customer_id_for_user(conn, current_user)
            if not own_customer_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Tài khoản chưa có hồ sơ khách hàng liên kết hợp lệ để tạo đơn. Vui lòng liên hệ quản trị viên."
                )
            if order_in.customer_id is not None and order_in.customer_id != own_customer_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Bạn không có quyền tạo đơn hàng cho khách hàng khác (IDOR Violation)"
                )
            order_in.customer_id = own_customer_id
        order_status = "pending"
    else:
        order_status = order_in.status or "completed"

    return InventoryService.create_order(order_in, user_id=current_user["id"], status=order_status)

@router.post("/{order_id}/approve", response_model=OrderResponse, dependencies=[Depends(require_roles("admin", "superadmin"))])
def approve_order(
    order_id: int,
    current_user: dict = Depends(get_current_user)
):
    """
    Duyệt đơn hàng PENDING (Admin, SuperAdmin only):
    - Bắt buộc đơn hàng phải ở trạng thái PENDING (nếu không -> 400 Bad Request)
    - Chuyển trạng thái sang ADMIN_APPROVED
    - Ghi nhận approved_by và approved_at
    """
    return InventoryService.approve_order(order_id, user_id=current_user["id"])

@router.post("/{order_id}/reject", response_model=OrderResponse, dependencies=[Depends(require_roles("admin", "superadmin"))])
def reject_order(
    order_id: int,
    reject_in: Optional[RejectOrderRequest] = None,
    current_user: dict = Depends(get_current_user)
):
    """
    Từ chối đơn hàng PENDING (Admin, SuperAdmin only):
    - Bắt buộc đơn hàng phải ở trạng thái PENDING (nếu không -> 400 Bad Request)
    - Nhận body { reason: "..." }
    - Chuyển trạng thái sang REJECTED
    - Ghi nhận rejected_by, rejected_at, rejection_reason
    - Hoàn trả số lượng tồn kho tự động trong SQLite Atomic Transaction (return_cancel)
    """
    reason = reject_in.reason if reject_in and reject_in.reason else "Đơn hàng bị Admin từ chối"
    return InventoryService.reject_order(order_id, user_id=current_user["id"], reason=reason)

@router.post("/{order_id}/process", response_model=OrderResponse, dependencies=[Depends(require_roles("staff", "admin", "superadmin"))])
def process_order(
    order_id: int,
    current_user: dict = Depends(get_current_user)
):
    """
    Staff/Admin nhận xử lý đơn hàng đã được Admin duyệt:
    - Nếu đơn đang PENDING -> Trả về 400 Bad Request ("Đơn hàng chưa được Admin duyệt")
    - Bắt buộc trạng thái hiện tại là ADMIN_APPROVED
    - Chuyển trạng thái sang PROCESSING
    - Ghi nhận processed_by, processed_at
    """
    return InventoryService.process_order(order_id, user_id=current_user["id"])

@router.post("/{order_id}/complete", response_model=OrderResponse, dependencies=[Depends(require_roles("staff", "admin", "superadmin"))])
def complete_order(
    order_id: int,
    current_user: dict = Depends(get_current_user)
):
    """
    Staff/Admin hoàn tất đơn hàng:
    - Bắt buộc trạng thái hiện tại là PROCESSING hoặc ADMIN_APPROVED
    - Nếu đơn đang PENDING -> Trả về 400 Bad Request
    - Chuyển trạng thái sang COMPLETED
    - Cập nhật tổng chi tiêu của khách hàng (total_spent)
    - Doanh thu đơn hàng sẽ được tính vào báo cáo doanh thu thực tế
    """
    return InventoryService.complete_order(order_id, user_id=current_user["id"])

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

class CustomerCancelRequest(BaseModel):
    reason: Optional[str] = "Khách hàng tự hủy đơn online"

@router.post("/{order_id}/customer-cancel", response_model=OrderResponse, dependencies=[Depends(require_roles("customer"))])
def customer_cancel_order(
    order_id: int,
    cancel_in: Optional[CustomerCancelRequest] = None,
    current_user: dict = Depends(get_current_user)
):
    """
    Khách hàng (Customer) tự hủy đơn hàng online (Phase 13D):
    - Chỉ cho phép Customer sở hữu đơn thực hiện (Anti-IDOR).
    - Chỉ cho phép khi đơn hàng đang ở trạng thái PENDING.
    - Nếu đơn đã duyệt (admin_approved, processing, completed) -> Trả lỗi 400 hướng dẫn liên hệ cửa hàng.
    - Hoàn trả số lượng tồn kho tự động trong SQLite Atomic Transaction.
    """
    with get_db() as conn:
        own_customer_id = get_customer_id_for_user(conn, current_user)

    reason = cancel_in.reason if cancel_in and cancel_in.reason else "Khách hàng tự hủy đơn online"
    return InventoryService.customer_cancel_order(
        order_id=order_id,
        user_id=current_user["id"],
        own_customer_id=own_customer_id,
        reason=reason
    )

@router.post("/{order_id}/force-action", response_model=OrderResponse, dependencies=[Depends(require_roles("superadmin"))])
def superadmin_force_action(
    order_id: int,
    action_in: ForceActionRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Thao tác ngoại lệ trên đơn hàng (Chỉ dành riêng cho SuperAdmin - Chủ cửa hàng):
    - Hỗ trợ: force_cancel, reopen_rejected, override_status.
    - Bắt buộc nhập lý do can thiệp ngoại lệ.
    - Tự động ghi vết kiểm toán vào order_audit_logs.
    """
    return InventoryService.superadmin_force_action(
        order_id=order_id,
        user_id=current_user["id"],
        action=action_in.action,
        reason=action_in.reason,
        target_status=action_in.target_status
    )


