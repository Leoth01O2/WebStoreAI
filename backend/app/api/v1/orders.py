from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from app.core.database import get_db
from app.core.rbac import get_current_user, require_roles, get_customer_id_for_user
from app.schemas.order import (
    OrderCreate,
    OrderResponse,
    OrderItemResponse,
    RejectOrderRequest,
    ForceActionRequest,
    ClaimOrderRequest,
    ReassignOrderRequest,
    NotifyTransferRequest,
    VerifyPaymentRequest,
    ConfirmCodPaymentRequest,
    UpdateFulfillmentRequest,
    ConfirmReturnRequest,
    RequestRefundRequest,
    ConfirmRefundRequest,
    OrderAuditLogResponse,
)
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
        cursor.execute("PRAGMA table_info(orders)")
        cols = {r["name"] if isinstance(r, dict) or hasattr(r, "keys") else r[1] for r in cursor.fetchall()}
        has_v3 = "payment_status_raw" in cols
        extra_select = ", o.payment_status_raw, o.fulfillment_status" if has_v3 else ""

        query = f"""
            SELECT o.id, o.order_code, o.customer_id, c.name as customer_name, c.phone as customer_phone,
                   o.user_id, u.full_name as user_name, o.total_amount, o.discount_amount,
                   o.final_amount, o.payment_method, o.payment_status, o.status, o.note,
                   o.assigned_to, u_assign.full_name as assigned_name,
                   o.shipping_name, o.shipping_phone, o.shipping_address, o.is_legacy_unverified,
                   o.approved_by, o.approved_at, o.processed_by, o.processed_at,
                   o.rejected_by, o.rejected_at, o.rejection_reason,
                   o.created_at{extra_select}
            FROM orders o
            LEFT JOIN customers c ON o.customer_id = c.id
            LEFT JOIN users u ON o.user_id = u.id
            LEFT JOIN users u_assign ON o.assigned_to = u_assign.id
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

        # Gắn danh sách items tóm tắt cho từng order và fallback tương thích
        for order in orders:
            if not has_v3:
                order.setdefault("payment_status_raw", order.get("payment_status"))
                order.setdefault("fulfillment_status", "delivered" if order.get("status") == "completed" else "unfulfilled")
            order.setdefault("is_legacy_unverified", 0)
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
        cursor.execute("PRAGMA table_info(orders)")
        cols = {r["name"] if isinstance(r, dict) or hasattr(r, "keys") else r[1] for r in cursor.fetchall()}
        has_v3 = "payment_status_raw" in cols
        extra_select = ", o.payment_status_raw, o.fulfillment_status" if has_v3 else ""

        cursor.execute(
            f"""SELECT o.id, o.order_code, o.customer_id, c.name as customer_name, c.phone as customer_phone,
                      o.user_id, u.full_name as user_name, o.total_amount, o.discount_amount,
                      o.final_amount, o.payment_method, o.payment_status, o.status, o.note,
                      o.assigned_to, u_assign.full_name as assigned_name,
                      o.shipping_name, o.shipping_phone, o.shipping_address, o.is_legacy_unverified,
                      o.approved_by, o.approved_at, o.processed_by, o.processed_at,
                      o.rejected_by, o.rejected_at, o.rejection_reason,
                      o.created_at{extra_select}
               FROM orders o
               LEFT JOIN customers c ON o.customer_id = c.id
               LEFT JOIN users u ON o.user_id = u.id
               LEFT JOIN users u_assign ON o.assigned_to = u_assign.id
               WHERE o.id = ?""",
            (order_id,)
        )
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Không tìm thấy hóa đơn")

        order_data = dict(row)
        if not has_v3:
            order_data.setdefault("payment_status_raw", order_data.get("payment_status"))
            order_data.setdefault("fulfillment_status", "delivered" if order_data.get("status") == "completed" else "unfulfilled")
        order_data.setdefault("is_legacy_unverified", 0)

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
                    detail="Bạn không có quyền, không thể tạo đơn hàng cho khách hàng khác (IDOR Violation)"
                )
            order_in.customer_id = own_customer_id
        order_status = "pending"
    else:
        order_status = order_in.status or "completed"

    return InventoryService.create_order(order_in, user_id=current_user["id"], status=order_status, user_role=user_role)

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

# =========================================================================
# PHASE R3: WORKFLOW EXTENSIONS (Claim, Payment, Fulfillment, Refund, Audit)
# =========================================================================

def _get_required_role(current_user: dict) -> str:
    role = current_user.get("role")
    if not isinstance(role, str) or not role:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Thông tin vai trò người dùng không hợp lệ"
        )
    return role

@router.post("/{order_id}/claim", response_model=OrderResponse, dependencies=[Depends(require_roles("staff", "admin", "superadmin"))])
def claim_order(
    order_id: int,
    claim_in: Optional[ClaimOrderRequest] = None,
    current_user: dict = Depends(get_current_user)
):
    """
    Staff / Admin nhận xử lý đơn hàng đã được Admin phê duyệt (Atomic Claim Lock):
    - Đơn phải ở trạng thái 'admin_approved' và chưa có ai nhận (assigned_to IS NULL).
    - Cập nhật nguyên tử orders.assigned_to = user_id, status = 'processing'.
    - Ghi log 'claim' vào order_audit_logs trong cùng transaction.
    - Trả HTTP 409 Conflict nếu đơn đã bị Staff khác nhận trước đó.
    """
    note = claim_in.note if claim_in else None
    return InventoryService.claim_order(
        order_id=order_id,
        user_id=current_user["id"],
        user_role=_get_required_role(current_user),
        note=note
    )

@router.post("/{order_id}/reassign", response_model=OrderResponse, dependencies=[Depends(require_roles("admin", "superadmin"))])
def reassign_order(
    order_id: int,
    reassign_in: ReassignOrderRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Admin / SuperAdmin điều chuyển đơn hàng cho Staff khác:
    - Yêu cầu lý do điều chuyển.
    - Ghi audit log 'reassign'.
    """
    return InventoryService.reassign_order(
        order_id=order_id,
        user_id=current_user["id"],
        user_role=_get_required_role(current_user),
        new_staff_id=reassign_in.new_staff_id,
        reason=reassign_in.reason
    )

@router.post("/{order_id}/notify-transfer", response_model=OrderResponse)
def notify_transfer(
    order_id: int,
    transfer_in: Optional[NotifyTransferRequest] = None,
    current_user: dict = Depends(get_current_user)
):
    """
    Khách hàng / Nhân viên thông báo đã chuyển khoản:
    - Chuyển payment_status sang 'pending_verification'.
    - Không tự đánh dấu paid khi chỉ gửi thông báo/ảnh chụp.
    - Anti-IDOR: Khách hàng chỉ được thông báo trên đơn của mình.
    """
    own_customer_id = None
    role = _get_required_role(current_user)
    if role == "customer":
        with get_db() as conn:
            own_customer_id = get_customer_id_for_user(conn, current_user)

    ref = (getattr(transfer_in, "transfer_ref", None) or getattr(transfer_in, "transfer_reference", None)) if transfer_in else None
    bank = transfer_in.bank_name if transfer_in else None
    note = transfer_in.note if transfer_in else None

    return InventoryService.notify_transfer(
        order_id=order_id,
        user_id=current_user["id"],
        user_role=role,
        transfer_ref=ref,
        bank_name=bank,
        note=note,
        own_customer_id=own_customer_id
    )

@router.post("/{order_id}/verify-payment", response_model=OrderResponse, dependencies=[Depends(require_roles("admin", "superadmin"))])
def verify_payment(
    order_id: int,
    verify_in: Optional[VerifyPaymentRequest] = None,
    current_user: dict = Depends(get_current_user)
):
    """
    Admin / SuperAdmin xác minh thanh toán chuyển khoản:
    - Yêu cầu đối soát chứng từ thực tế.
    - Chuyển payment_status sang 'paid'.
    - Ghi audit log 'verify_payment'.
    """
    ref = (getattr(verify_in, "verified_ref", None) or getattr(verify_in, "verified_reference", None)) if verify_in else None
    note = verify_in.note if verify_in else None
    return InventoryService.verify_payment(
        order_id=order_id,
        user_id=current_user["id"],
        user_role=_get_required_role(current_user),
        verified_ref=ref,
        note=note
    )

@router.post("/{order_id}/confirm-cod-payment", response_model=OrderResponse, dependencies=[Depends(require_roles("staff", "admin", "superadmin"))])
def confirm_cod_payment(
    order_id: int,
    cod_in: Optional[ConfirmCodPaymentRequest] = None,
    current_user: dict = Depends(get_current_user)
):
    """
    Xác nhận thực tế đã thu tiền mặt COD từ khách/đơn vị vận chuyển:
    - Chuyển payment_status từ 'unpaid' -> 'paid'.
    - Ghi audit log 'confirm_cod'.
    """
    note = cod_in.note if cod_in else None
    return InventoryService.confirm_cod_payment(
        order_id=order_id,
        user_id=current_user["id"],
        user_role=_get_required_role(current_user),
        note=note
    )

@router.post("/{order_id}/update-fulfillment", response_model=OrderResponse, dependencies=[Depends(require_roles("staff", "admin", "superadmin"))])
def update_fulfillment(
    order_id: int,
    req: UpdateFulfillmentRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Cập nhật tiến trình đóng gói / giao vận:
    - Trạng thái hợp lệ: unfulfilled, packing, shipping, delivered, delivery_failed.
    - Giao hàng thất bại (delivery_failed) TUYỆT ĐỐI không tự động hoàn kho.
    - Ghi audit log 'update_fulfillment'.
    """
    return InventoryService.update_fulfillment(
        order_id=order_id,
        user_id=current_user["id"],
        user_role=_get_required_role(current_user),
        fulfillment_status=req.fulfillment_status,
        note=req.note
    )

@router.post("/{order_id}/confirm-return", response_model=OrderResponse, dependencies=[Depends(require_roles("staff", "admin", "superadmin"))])
def confirm_return(
    order_id: int,
    return_in: Optional[ConfirmReturnRequest] = None,
    current_user: dict = Depends(get_current_user)
):
    """
    Xác nhận hàng thực sự đã nhập lại kho (Return to inventory):
    - Chỉ cho phép sau khi delivery_failed hoặc cancelled.
    - Chỉ nhập kho MỘT lần duy nhất (idempotency check với inventory_logs).
    - Cập nhật fulfillment_status sang 'returned_to_inventory'.
    - Ghi audit log 'confirm_return'.
    """
    reason = return_in.reason if return_in else "Hàng giao không thành công quay về kho"
    note = return_in.note if return_in else None
    return InventoryService.confirm_return(
        order_id=order_id,
        user_id=current_user["id"],
        user_role=_get_required_role(current_user),
        reason=reason,
        note=note
    )

@router.post("/{order_id}/request-refund", response_model=OrderResponse)
def request_refund(
    order_id: int,
    req: Optional[RequestRefundRequest] = None,
    current_user: dict = Depends(get_current_user)
):
    """
    Yêu cầu hoàn tiền (Customer, Staff, Admin, SuperAdmin):
    - Đơn phải đang ở trạng thái payment_status 'paid'.
    - Chuyển sang 'refund_pending'.
    - Hoàn tiền độc lập với hoàn hàng: Không chạm đến tồn kho.
    - Anti-IDOR: Khách hàng chỉ yêu cầu trên đơn của mình.
    """
    own_customer_id = None
    role = _get_required_role(current_user)
    if role == "customer":
        with get_db() as conn:
            own_customer_id = get_customer_id_for_user(conn, current_user)

    reason = req.reason if req else "Khách yêu cầu hoàn tiền"
    return InventoryService.request_refund(
        order_id=order_id,
        user_id=current_user["id"],
        user_role=role,
        reason=reason,
        own_customer_id=own_customer_id
    )

@router.post("/{order_id}/confirm-refund", response_model=OrderResponse, dependencies=[Depends(require_roles("admin", "superadmin"))])
def confirm_refund(
    order_id: int,
    req: Optional[ConfirmRefundRequest] = None,
    current_user: dict = Depends(get_current_user)
):
    """
    Admin / SuperAdmin xác nhận đã hoàn tiền thực tế:
    - Chuyển payment_status sang 'refunded'.
    - Độc lập với tồn kho: Không nhập kho.
    - Điều chỉnh customer.total_spent nếu đơn đã hoàn thành trước đó.
    - Ghi audit log 'confirm_refund'.
    """
    ref = (getattr(req, "refund_ref", None) or getattr(req, "refund_reference", None)) if req else None
    reason = req.reason if req else "Đã thực hiện chuyển khoản / hoàn tiền mặt cho khách"
    return InventoryService.confirm_refund(
        order_id=order_id,
        user_id=current_user["id"],
        user_role=_get_required_role(current_user),
        refund_ref=ref,
        reason=reason
    )

@router.get("/{order_id}/audit-logs", response_model=List[OrderAuditLogResponse])
def get_order_audit_logs(
    order_id: int,
    current_user: dict = Depends(get_current_user)
):
    """
    Lấy lịch sử kiểm toán / diễn biến của đơn hàng:
    - Customer chỉ xem audit log đơn của mình (Anti-IDOR).
    - Staff, Admin, SuperAdmin xem được audit log của tất cả đơn.
    """
    own_customer_id = None
    role = _get_required_role(current_user)
    if role == "customer":
        with get_db() as conn:
            own_customer_id = get_customer_id_for_user(conn, current_user)

    return InventoryService.get_order_audit_logs(
        order_id=order_id,
        user_id=current_user["id"],
        user_role=role,
        own_customer_id=own_customer_id
    )