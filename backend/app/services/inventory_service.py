import datetime
import uuid
from typing import Optional, List, Dict, Any
from fastapi import HTTPException, status
from app.core.database import get_db_transaction, get_db
from app.schemas.order import OrderCreate
from app.schemas.purchase import PurchaseCreate

def _generate_code(prefix: str) -> str:
    """Tạo mã chứng từ duy nhất theo định dạng PREFIX-YYYYMMDD-XXXX"""
    today_str = datetime.datetime.now().strftime("%Y%m%d")
    short_uuid = uuid.uuid4().hex[:4].upper()
    return f"{prefix}-{today_str}-{short_uuid}"

class InventoryService:

    @staticmethod
    def _get_order_detail_by_id(cursor, order_id: int) -> Optional[Dict[str, Any]]:
        cursor.execute("PRAGMA table_info(orders)")
        cols = {r["name"] if isinstance(r, dict) or hasattr(r, "keys") else r[1] for r in cursor.fetchall()}
        has_v3 = "payment_status_raw" in cols

        extra_cols = ", o.payment_status_raw, o.fulfillment_status" if has_v3 else ""
        cursor.execute(
            f"""SELECT o.id, o.order_code, o.customer_id, c.name as customer_name, c.phone as customer_phone,
                      o.user_id, u.full_name as user_name, o.total_amount, o.discount_amount,
                      o.final_amount, o.payment_method, o.payment_status, o.status, o.note,
                      o.assigned_to, u_assign.full_name as assigned_name,
                      o.shipping_name, o.shipping_phone, o.shipping_address, o.is_legacy_unverified,
                      o.approved_by, o.approved_at, o.processed_by, o.processed_at,
                      o.rejected_by, o.rejected_at, o.rejection_reason,
                      o.created_at{extra_cols}
               FROM orders o
               LEFT JOIN customers c ON o.customer_id = c.id
               LEFT JOIN users u ON o.user_id = u.id
               LEFT JOIN users u_assign ON o.assigned_to = u_assign.id
               WHERE o.id = ?""",
            (order_id,)
        )
        row = cursor.fetchone()
        if not row:
            return None
        order_dict = dict(row)
        if not has_v3:
            order_dict["payment_status_raw"] = order_dict.get("payment_status")
            order_dict["fulfillment_status"] = "delivered" if order_dict.get("status") == "completed" else "unfulfilled"
        order_dict.setdefault("is_legacy_unverified", 0)

        cursor.execute(
            """SELECT oi.id, oi.product_id, p.sku as product_sku, p.name as product_name,
                      p.image_url, oi.quantity, oi.unit_price, oi.subtotal
               FROM order_items oi
               JOIN products p ON oi.product_id = p.id
               WHERE oi.order_id = ?""",
            (order_id,)
        )
        order_dict["items"] = [dict(item) for item in cursor.fetchall()]
        return order_dict

    @staticmethod
    def _require_order_detail_by_id(cursor, order_id: int) -> Dict[str, Any]:
        order = InventoryService._get_order_detail_by_id(cursor, order_id)
        if not order:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Không tìm thấy thông tin đơn hàng ID {order_id} sau khi xử lý"
            )
        return order

    @staticmethod
    def create_order(order_in: OrderCreate, user_id: int, status: Optional[str] = None, user_role: Optional[str] = None) -> Dict[str, Any]:
        """
        Nghiệp vụ Bán hàng POS Atomic:
        1. BEGIN IMMEDIATE khóa ghi SQLite.
        2. Kiểm tra từng mặt hàng: tồn kho, trạng thái active.
        3. Nếu thiếu hàng -> ROLLBACK ngay lập tức và raise 400.
        4. Tạo order, order_items.
        5. Trừ stock_quantity, ghi inventory_logs (change_type='sale').
        6. Cập nhật total_spent của khách hàng (nếu có và status == completed).
        7. COMMIT transaction.
        """
        if not order_in.items:
            raise HTTPException(status_code=400, detail="Đơn hàng phải có ít nhất một sản phẩm")

        order_code = _generate_code("HD")
        created_at = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        order_status = status or getattr(order_in, "status", None) or "completed"

        with get_db_transaction() as conn:
            cursor = conn.cursor()

            # 1. Thu thập và kiểm tra toàn bộ sản phẩm
            total_amount = 0.0
            order_items_to_create = []

            for item in order_in.items:
                cursor.execute(
                    "SELECT id, sku, name, selling_price, stock_quantity, status, image_url FROM products WHERE id = ?",
                    (item.product_id,)
                )
                product = cursor.fetchone()

                if not product:
                    raise HTTPException(
                        status_code=404,
                        detail=f"Không tìm thấy sản phẩm với ID {item.product_id}"
                    )

                if product["status"] != "active":
                    raise HTTPException(
                        status_code=400,
                        detail=f"Sản phẩm '{product['name']}' (SKU: {product['sku']}) hiện đang ngừng kinh doanh"
                    )

                if product["stock_quantity"] < item.quantity:
                    raise HTTPException(
                        status_code=400,
                        detail=(
                            f"Sản phẩm '{product['name']}' không đủ số lượng tồn kho. "
                            f"Tồn hiện tại: {product['stock_quantity']}, yêu cầu: {item.quantity}."
                        )
                    )

                unit_price = float(product["selling_price"])
                subtotal = unit_price * item.quantity
                total_amount += subtotal

                order_items_to_create.append({
                    "product_id": product["id"],
                    "sku": product["sku"],
                    "name": product["name"],
                    "image_url": product["image_url"],
                    "quantity": item.quantity,
                    "unit_price": unit_price,
                    "subtotal": subtotal,
                    "stock_before": product["stock_quantity"]
                })

            final_amount = max(0.0, total_amount - order_in.discount_amount)

            # Kiểm tra schema version 3 qua PRAGMA table_info
            cursor.execute("PRAGMA table_info(orders)")
            cols = {r["name"] if isinstance(r, dict) or hasattr(r, "keys") else r[1] for r in cursor.fetchall()}
            has_v3 = "payment_status_raw" in cols

            # Phân định luồng Customer vs POS Counter
            is_customer = (user_role == "customer") or (order_status == "pending")

            if is_customer:
                order_status = "pending"
                # Customer KHÔNG được tự gửi paid, refunded, unverified_legacy
                if has_v3:
                    payment_status = "unpaid"
                    payment_status_raw = "unpaid"
                    fulfillment_status = "unfulfilled"
                else:
                    payment_status = "pending"
                    payment_status_raw = "pending"
                    fulfillment_status = "unfulfilled"
            else:
                # POS Counter Sale
                order_status = status or getattr(order_in, "status", None) or "completed"
                if order_status == "completed":
                    # Đơn POS hoàn tất tại quầy: tiền đã nhận tại quầy, hàng đã giao
                    payment_status = "paid"
                    payment_status_raw = "paid"
                    fulfillment_status = "delivered"
                else:
                    payment_status = "unpaid" if has_v3 else "pending"
                    payment_status_raw = payment_status
                    fulfillment_status = "unfulfilled"

            # Bảo vệ chống Mass Assignment: assigned_to luôn NULL khi tạo đơn mới
            # is_legacy_unverified luôn 0 cho mọi đơn mới tạo
            shipping_name = getattr(order_in, "shipping_name", None)
            shipping_phone = getattr(order_in, "shipping_phone", None)
            shipping_address = getattr(order_in, "shipping_address", None)

            # 2. Tạo bản ghi Hóa đơn (Order)
            if has_v3:
                cursor.execute(
                    """INSERT INTO orders (
                        order_code, customer_id, user_id, assigned_to, shipping_name,
                        shipping_phone, shipping_address, is_legacy_unverified, total_amount,
                        discount_amount, final_amount, payment_method, payment_status,
                        payment_status_raw, fulfillment_status, status, note, created_at
                    ) VALUES (?, ?, ?, NULL, ?, ?, ?, 0, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        order_code, order_in.customer_id, user_id, shipping_name,
                        shipping_phone, shipping_address, total_amount,
                        order_in.discount_amount, final_amount, order_in.payment_method,
                        payment_status, payment_status_raw, fulfillment_status,
                        order_status, order_in.note, created_at
                    )
                )
            else:
                cursor.execute(
                    """INSERT INTO orders (
                        order_code, customer_id, user_id, assigned_to, shipping_name,
                        shipping_phone, shipping_address, is_legacy_unverified, total_amount,
                        discount_amount, final_amount, payment_method, payment_status, status, note, created_at
                    ) VALUES (?, ?, ?, NULL, ?, ?, ?, 0, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        order_code, order_in.customer_id, user_id, shipping_name,
                        shipping_phone, shipping_address, total_amount,
                        order_in.discount_amount, final_amount, order_in.payment_method,
                        payment_status, order_status, order_in.note, created_at
                    )
                )
            order_id = cursor.lastrowid

            # 3. Tạo chi tiết đơn hàng, trừ tồn kho và ghi nhật ký xuất nhập tồn
            result_items = []
            for item in order_items_to_create:
                cursor.execute(
                    """INSERT INTO order_items (order_id, product_id, quantity, unit_price, subtotal)
                       VALUES (?, ?, ?, ?, ?)""",
                    (order_id, item["product_id"], item["quantity"], item["unit_price"], item["subtotal"])
                )
                item_id = cursor.lastrowid

                # Trừ tồn kho trong SQLite
                new_stock = item["stock_before"] - item["quantity"]
                cursor.execute(
                    "UPDATE products SET stock_quantity = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                    (new_stock, item["product_id"])
                )

                # Ghi nhật ký inventory_logs
                cursor.execute(
                    """INSERT INTO inventory_logs (
                        product_id, change_type, reference_code,
                        quantity_before, change_quantity, quantity_after, note, created_at
                    ) VALUES (?, 'sale', ?, ?, ?, ?, ?, ?)""",
                    (
                        item["product_id"], order_code, item["stock_before"],
                        -item["quantity"], new_stock, f"Bán hàng đơn {order_code}", created_at
                    )
                )

                result_items.append({
                    "id": item_id,
                    "product_id": item["product_id"],
                    "product_sku": item["sku"],
                    "product_name": item["name"],
                    "image_url": item["image_url"],
                    "quantity": item["quantity"],
                    "unit_price": item["unit_price"],
                    "subtotal": item["subtotal"]
                })

            # 4. Cập nhật tổng chi tiêu của khách hàng nếu đơn hoàn tất (completed)
            if order_in.customer_id and order_status == "completed":
                cursor.execute(
                    "UPDATE customers SET total_spent = total_spent + ? WHERE id = ?",
                    (final_amount, order_in.customer_id)
                )

            # Lấy thông tin khách hàng và người lập đơn
            customer_name, customer_phone = None, None
            if order_in.customer_id:
                cursor.execute("SELECT name, phone FROM customers WHERE id = ?", (order_in.customer_id,))
                c_row = cursor.fetchone()
                if c_row:
                    customer_name, customer_phone = c_row["name"], c_row["phone"]

            cursor.execute("SELECT full_name FROM users WHERE id = ?", (user_id,))
            u_row = cursor.fetchone()
            user_name = u_row["full_name"] if u_row else None

            return {
                "id": order_id,
                "order_code": order_code,
                "customer_id": order_in.customer_id,
                "customer_name": customer_name,
                "customer_phone": customer_phone,
                "user_id": user_id,
                "user_name": user_name,
                "total_amount": total_amount,
                "discount_amount": order_in.discount_amount,
                "final_amount": final_amount,
                "payment_method": order_in.payment_method,
                "payment_status": payment_status,
                "payment_status_raw": payment_status_raw,
                "fulfillment_status": fulfillment_status,
                "status": order_status,
                "note": order_in.note,
                "approved_by": None,
                "approved_at": None,
                "processed_by": None,
                "processed_at": None,
                "rejected_by": None,
                "rejected_at": None,
                "rejection_reason": None,
                "assigned_to": None,
                "assigned_name": None,
                "shipping_name": shipping_name,
                "shipping_phone": shipping_phone,
                "shipping_address": shipping_address,
                "is_legacy_unverified": 0,
                "created_at": created_at,
                "items": result_items
            }

    @staticmethod
    def approve_order(order_id: int, user_id: int) -> Dict[str, Any]:
        """
        Duyệt đơn hàng của Admin (Atomic Transaction):
        1. Kiểm tra đơn hàng tồn tại.
        2. Bắt buộc trạng thái hiện tại là 'pending'. Nếu không -> HTTPException(400).
        3. Cập nhật status = 'admin_approved', approved_by = user_id, approved_at = now_str.
        """
        with get_db_transaction() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM orders WHERE id = ?", (order_id,))
            order = cursor.fetchone()
            if not order:
                raise HTTPException(status_code=404, detail="Không tìm thấy đơn hàng cần duyệt")

            if order["status"] != "pending":
                raise HTTPException(
                    status_code=400,
                    detail=f"Chỉ có thể duyệt đơn hàng đang ở trạng thái 'pending' (trạng thái hiện tại: '{order['status']}')"
                )

            now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            cursor.execute(
                """UPDATE orders
                   SET status = 'admin_approved',
                       approved_by = ?,
                       approved_at = ?
                   WHERE id = ?""",
                (user_id, now_str, order_id)
            )

            updated_order = InventoryService._require_order_detail_by_id(cursor, order_id)
            return updated_order

    @staticmethod
    def reject_order(order_id: int, user_id: int, reason: Optional[str] = None) -> Dict[str, Any]:
        """
        Từ chối đơn hàng của Admin (Atomic Transaction):
        1. Kiểm tra đơn hàng tồn tại.
        2. Bắt buộc trạng thái hiện tại là 'pending'. Nếu không -> HTTPException(400).
        3. Tự động hoàn trả tồn kho cho từng sản phẩm trong order_items.
        4. Ghi nhật ký xuất nhập tồn 'return_cancel' vào inventory_logs.
        5. Cập nhật status = 'rejected', rejected_by = user_id, rejected_at = now_str, rejection_reason = reason.
        """
        with get_db_transaction() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM orders WHERE id = ?", (order_id,))
            order = cursor.fetchone()
            if not order:
                raise HTTPException(status_code=404, detail="Không tìm thấy đơn hàng cần từ chối")

            if order["status"] != "pending":
                raise HTTPException(
                    status_code=400,
                    detail=f"Chỉ có thể từ chối đơn hàng đang ở trạng thái 'pending' (trạng thái hiện tại: '{order['status']}')"
                )

            order_code = order["order_code"]
            now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            rejection_text = reason or "Đơn hàng bị Admin từ chối"

            # Hoàn trả tồn kho tự động
            cursor.execute("SELECT product_id, quantity FROM order_items WHERE order_id = ?", (order_id,))
            items = cursor.fetchall()
            for item in items:
                p_id = item["product_id"]
                qty = item["quantity"]

                cursor.execute("SELECT stock_quantity FROM products WHERE id = ?", (p_id,))
                prod = cursor.fetchone()
                if prod:
                    stock_before = prod["stock_quantity"]
                    stock_after = stock_before + qty

                    cursor.execute(
                        "UPDATE products SET stock_quantity = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                        (stock_after, p_id)
                    )

                    cursor.execute(
                        """INSERT INTO inventory_logs (
                            product_id, change_type, reference_code,
                            quantity_before, change_quantity, quantity_after, note, created_at
                        ) VALUES (?, 'return_cancel', ?, ?, ?, ?, ?, ?)""",
                        (
                            p_id, order_code, stock_before, qty,
                            stock_after, f"Hoàn tồn do từ chối đơn hàng {order_code}: {rejection_text}", now_str
                        )
                    )

            # Cập nhật trạng thái và thông tin từ chối
            cursor.execute(
                """UPDATE orders
                   SET status = 'rejected',
                       rejected_by = ?,
                       rejected_at = ?,
                       rejection_reason = ?
                   WHERE id = ?""",
                (user_id, now_str, rejection_text, order_id)
            )

            updated_order = InventoryService._require_order_detail_by_id(cursor, order_id)
            return updated_order

    @staticmethod
    def process_order(order_id: int, user_id: int) -> Dict[str, Any]:
        """
        Nhận xử lý đơn hàng (Staff/Admin/SuperAdmin):
        1. Kiểm tra đơn hàng tồn tại.
        2. Nếu đơn đang 'pending' -> 400 'Đơn hàng chưa được Admin duyệt'.
        3. Nếu đơn không phải 'admin_approved' -> 400.
        4. Chuyển status = 'processing', processed_by = user_id, processed_at = now_str.
        """
        with get_db_transaction() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM orders WHERE id = ?", (order_id,))
            order = cursor.fetchone()
            if not order:
                raise HTTPException(status_code=404, detail="Không tìm thấy đơn hàng cần xử lý")

            if order["status"] == "pending":
                raise HTTPException(status_code=400, detail="Đơn hàng chưa được Admin duyệt")

            if order["status"] != "admin_approved":
                raise HTTPException(
                    status_code=400,
                    detail=f"Chỉ có thể xử lý đơn hàng đã được Admin duyệt (trạng thái hiện tại: '{order['status']}')"
                )

            now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            cursor.execute(
                """UPDATE orders
                   SET status = 'processing',
                       processed_by = ?,
                       processed_at = ?
                   WHERE id = ?""",
                (user_id, now_str, order_id)
            )

            updated_order = InventoryService._require_order_detail_by_id(cursor, order_id)
            return updated_order

    @staticmethod
    def complete_order(order_id: int, user_id: int) -> Dict[str, Any]:
        """
        Hoàn tất đơn hàng (Staff/Admin/SuperAdmin):
        1. Kiểm tra đơn hàng tồn tại.
        2. Nếu đơn đang 'pending' -> 400 'Đơn hàng chưa được Admin duyệt, không thể hoàn tất'.
        3. Bắt buộc trạng thái hiện tại là 'processing' hoặc 'admin_approved' (nếu không -> 400).
        4. Chuyển status = 'completed'. Cập nhật processed_by, processed_at nếu chưa có.
        5. Cập nhật total_spent của khách hàng (nếu có customer_id).
        """
        with get_db_transaction() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM orders WHERE id = ?", (order_id,))
            order = cursor.fetchone()
            if not order:
                raise HTTPException(status_code=404, detail="Không tìm thấy đơn hàng cần hoàn tất")

            if order["status"] == "pending":
                raise HTTPException(
                    status_code=400,
                    detail="Đơn hàng chưa được Admin duyệt, không thể hoàn tất"
                )

            if order["status"] not in ("processing", "admin_approved"):
                raise HTTPException(
                    status_code=400,
                    detail=f"Chỉ có thể hoàn tất đơn hàng đang ở trạng thái 'processing' hoặc 'admin_approved' (trạng thái hiện tại: '{order['status']}')"
                )

            now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            cursor.execute(
                """UPDATE orders
                   SET status = 'completed',
                       processed_by = COALESCE(processed_by, ?),
                       processed_at = COALESCE(processed_at, ?)
                   WHERE id = ?""",
                (user_id, now_str, order_id)
            )

            # Cập nhật tổng chi tiêu của khách hàng
            if order["customer_id"]:
                cursor.execute(
                    "UPDATE customers SET total_spent = total_spent + ? WHERE id = ?",
                    (float(order["final_amount"]), order["customer_id"])
                )

            updated_order = InventoryService._require_order_detail_by_id(cursor, order_id)
            return updated_order

    @staticmethod
    def cancel_order(order_id: int, user_id: int, cancel_reason: Optional[str] = None) -> Dict[str, Any]:
        """
        Nghiệp vụ Hủy hóa đơn Atomic:
        1. Kiểm tra đơn hàng tồn tại và trạng thái 'completed'.
        2. Hoàn trả tồn kho cho từng sản phẩm trong order_items.
        3. Ghi log 'return_cancel' vào inventory_logs.
        4. Giảm total_spent của khách hàng (nếu có).
        5. Đổi trạng thái đơn hàng sang 'cancelled'.
        """
        with get_db_transaction() as conn:
            cursor = conn.cursor()

            cursor.execute("SELECT * FROM orders WHERE id = ?", (order_id,))
            order = cursor.fetchone()

            if not order:
                raise HTTPException(status_code=404, detail="Không tìm thấy hóa đơn cần hủy")

            if order["status"] == "cancelled":
                raise HTTPException(status_code=400, detail="Hóa đơn này đã được hủy trước đó")

            order_code = order["order_code"]
            final_amount = float(order["final_amount"])
            customer_id = order["customer_id"]
            now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            # Lấy danh sách mặt hàng cần hoàn kho
            cursor.execute("SELECT product_id, quantity FROM order_items WHERE order_id = ?", (order_id,))
            items = cursor.fetchall()

            for item in items:
                p_id = item["product_id"]
                qty = item["quantity"]

                cursor.execute("SELECT stock_quantity FROM products WHERE id = ?", (p_id,))
                prod = cursor.fetchone()
                if prod:
                    stock_before = prod["stock_quantity"]
                    stock_after = stock_before + qty

                    cursor.execute(
                        "UPDATE products SET stock_quantity = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                        (stock_after, p_id)
                    )

                    cursor.execute(
                        """INSERT INTO inventory_logs (
                            product_id, change_type, reference_code,
                            quantity_before, change_quantity, quantity_after, note, created_at
                        ) VALUES (?, 'return_cancel', ?, ?, ?, ?, ?, ?)""",
                        (
                            p_id, order_code, stock_before, qty,
                            stock_after, f"Hoàn tồn do hủy hóa đơn {order_code}", now_str
                        )
                    )

            # Cập nhật trạng thái đơn hàng
            reason_note = f" (Lý do: {cancel_reason})" if cancel_reason else ""
            updated_note = (order["note"] or "") + f" [ĐÃ HỦY{reason_note}]"
            cursor.execute(
                "UPDATE orders SET status = 'cancelled', note = ? WHERE id = ?",
                (updated_note.strip(), order_id)
            )

            # Giảm total_spent của khách hàng
            if customer_id:
                cursor.execute(
                    "UPDATE customers SET total_spent = MAX(0, total_spent - ?) WHERE id = ?",
                    (final_amount, customer_id)
                )

            return {
                "id": order_id,
                "order_code": order_code,
                "status": "cancelled",
                "message": f"Hóa đơn {order_code} đã được hủy thành công. Đã hoàn trả toàn bộ số lượng tồn kho."
            }

    @staticmethod
    def customer_cancel_order(
        order_id: int,
        user_id: int,
        own_customer_id: Optional[int] = None,
        reason: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Nghiệp vụ Customer tự hủy đơn hàng Atomic (Phase 13D):
        1. Kiểm tra đơn hàng tồn tại (404 nếu không tìm thấy).
        2. Kiểm tra quyền sở hữu Anti-IDOR: order phải thuộc về user_id hoặc own_customer_id (403 nếu không khớp).
        3. Kiểm tra trạng thái hiện tại:
           - Nếu 'cancelled': 400 "Đơn hàng này đã được hủy trước đó" (Idempotency).
           - Nếu 'rejected': 400 "Đơn hàng đã bị từ chối trước đó, không thể hủy".
           - Nếu 'admin_approved', 'processing', 'completed': 400
             f"Đơn hàng đang ở trạng thái '{order['status']}' và đã được tiếp nhận xử lý. Vui lòng liên hệ cửa hàng để được hỗ trợ."
           - Nếu != 'pending': 400 "Chỉ có thể tự hủy đơn hàng khi đang ở trạng thái 'Chờ duyệt' (pending)".
        4. Hoàn trả toàn bộ số lượng tồn kho của các mặt hàng trong đơn.
        5. Ghi log 'return_cancel' vào inventory_logs.
        6. Đổi trạng thái đơn hàng sang 'cancelled'.
        7. Trả về chi tiết đơn hàng đã cập nhật (OrderResponse format).
        """
        with get_db_transaction() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM orders WHERE id = ?", (order_id,))
            order = cursor.fetchone()

            if not order:
                raise HTTPException(status_code=404, detail="Không tìm thấy đơn hàng cần hủy")

            # Anti-IDOR: xác thực quyền sở hữu của Customer
            is_own = (order["user_id"] == user_id) or (
                own_customer_id is not None and order["customer_id"] == own_customer_id
            )
            if not is_own:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Bạn không có quyền thao tác trên đơn hàng của khách hàng khác"
                )

            current_status = order["status"]
            if current_status == "cancelled":
                raise HTTPException(status_code=400, detail="Đơn hàng này đã được hủy trước đó")
            if current_status == "rejected":
                raise HTTPException(status_code=400, detail="Đơn hàng đã bị từ chối trước đó, không thể hủy")
            if current_status in ("admin_approved", "processing", "completed"):
                raise HTTPException(
                    status_code=400,
                    detail=f"Đơn hàng đang ở trạng thái '{current_status}' và đã được tiếp nhận xử lý. Vui lòng liên hệ cửa hàng để được hỗ trợ."
                )
            if current_status != "pending":
                raise HTTPException(
                    status_code=400,
                    detail="Chỉ có thể tự hủy đơn hàng khi đang ở trạng thái 'Chờ duyệt' (pending)"
                )

            order_code = order["order_code"]
            now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            cancel_text = (reason.strip() if reason and reason.strip() else "Khách hàng tự hủy đơn online")

            # Hoàn trả tồn kho cho từng sản phẩm trong order_items
            cursor.execute("SELECT product_id, quantity FROM order_items WHERE order_id = ?", (order_id,))
            items = cursor.fetchall()
            for item in items:
                p_id = item["product_id"]
                qty = item["quantity"]

                cursor.execute("SELECT stock_quantity FROM products WHERE id = ?", (p_id,))
                prod = cursor.fetchone()
                if prod:
                    stock_before = prod["stock_quantity"]
                    stock_after = stock_before + qty

                    cursor.execute(
                        "UPDATE products SET stock_quantity = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                        (stock_after, p_id)
                    )

                    cursor.execute(
                        """INSERT INTO inventory_logs (
                            product_id, change_type, reference_code,
                            quantity_before, change_quantity, quantity_after, note, created_at
                        ) VALUES (?, 'return_cancel', ?, ?, ?, ?, ?, ?)""",
                        (
                            p_id, order_code, stock_before, qty,
                            stock_after, f"Hoàn tồn do khách hủy đơn {order_code}: {cancel_text}", now_str
                        )
                    )

            # Cập nhật ghi chú và trạng thái đơn hàng
            existing_note = order["note"] or ""
            cancellation_note = f"[KHÁCH HỦY: {cancel_text}]"
            updated_note = f"{existing_note} {cancellation_note}".strip()

            cursor.execute(
                "UPDATE orders SET status = 'cancelled', note = ? WHERE id = ?",
                (updated_note, order_id)
            )

            updated_order = InventoryService._require_order_detail_by_id(cursor, order_id)
            return updated_order

    @staticmethod
    def superadmin_force_action(
        order_id: int,
        user_id: int,
        action: str,
        reason: str,
        target_status: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Nghiệp vụ Thao tác ngoại lệ SuperAdmin (Phase 13E):
        - Endpoint độc quyền cho SuperAdmin (Chủ cửa hàng).
        - Hỗ trợ 3 action:
          1. 'force_cancel': Hủy khẩn cấp, hoàn tồn kho, hoàn total_spent nếu đã completed, ngăn chặn double refund.
          2. 'reopen_rejected': Mở lại đơn bị từ chối về pending, kiểm tra tồn kho đủ trước khi trừ giữ chỗ, từ chối 400 nếu thiếu hàng.
          3. 'override_status': Chuyển trạng thái ngoại lệ theo whitelist an toàn, xử lý total_spent nhất quán, chặn override từ cancelled/rejected.
        - Toàn bộ thao tác thực hiện trong SQLite atomic transaction và ghi nhận audit trail vào order_audit_logs.
        """
        VALID_ACTIONS = ("force_cancel", "reopen_rejected", "override_status")
        if action not in VALID_ACTIONS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Hành động ngoại lệ '{action}' không hợp lệ. Chỉ chấp nhận: {', '.join(VALID_ACTIONS)}"
            )

        if not reason or not reason.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Lý do thực hiện thao tác ngoại lệ là bắt buộc"
            )

        clean_reason = reason.strip()

        with get_db_transaction() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM orders WHERE id = ?", (order_id,))
            order = cursor.fetchone()

            if not order:
                raise HTTPException(status_code=404, detail="Không tìm thấy đơn hàng cần xử lý ngoại lệ")

            current_status = order["status"]
            order_code = order["order_code"]
            final_amount = float(order["final_amount"])
            customer_id = order["customer_id"]
            now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            # -------------------------------------------------------------
            # ACTION 1: force_cancel
            # -------------------------------------------------------------
            if action == "force_cancel":
                if current_status == "cancelled":
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Đơn hàng này đã ở trạng thái 'cancelled' trước đó"
                    )
                if current_status == "rejected":
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Đơn hàng đã bị từ chối trước đó, không thể hủy. Sử dụng reopen_rejected nếu cần mở lại."
                    )

                # Hoàn trả tồn kho cho các sản phẩm
                cursor.execute("SELECT product_id, quantity FROM order_items WHERE order_id = ?", (order_id,))
                items = cursor.fetchall()
                for item in items:
                    p_id = item["product_id"]
                    qty = item["quantity"]
                    cursor.execute("SELECT stock_quantity FROM products WHERE id = ?", (p_id,))
                    prod = cursor.fetchone()
                    if prod:
                        stock_before = prod["stock_quantity"]
                        stock_after = stock_before + qty
                        cursor.execute(
                            "UPDATE products SET stock_quantity = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                            (stock_after, p_id)
                        )
                        cursor.execute(
                            """INSERT INTO inventory_logs (
                                product_id, change_type, reference_code,
                                quantity_before, change_quantity, quantity_after, note, created_at
                            ) VALUES (?, 'return_cancel', ?, ?, ?, ?, ?, ?)""",
                            (
                                p_id, order_code, stock_before, qty,
                                stock_after, f"SuperAdmin force_cancel đơn {order_code}: {clean_reason}", now_str
                            )
                        )

                # Nếu đơn đã completed, hoàn lại total_spent cho khách
                if current_status == "completed" and customer_id:
                    cursor.execute(
                        "UPDATE customers SET total_spent = MAX(0, total_spent - ?) WHERE id = ?",
                        (final_amount, customer_id)
                    )

                resulting_status = "cancelled"
                existing_note = order["note"] or ""
                updated_note = f"{existing_note} [FORCE_CANCEL by SuperAdmin: {clean_reason}]".strip()

                cursor.execute(
                    "UPDATE orders SET status = ?, note = ? WHERE id = ?",
                    (resulting_status, updated_note, order_id)
                )

            # -------------------------------------------------------------
            # ACTION 2: reopen_rejected
            # -------------------------------------------------------------
            elif action == "reopen_rejected":
                if current_status != "rejected":
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Chỉ có thể reopen đơn hàng đang ở trạng thái 'rejected' (trạng thái hiện tại: '{current_status}')"
                    )

                cursor.execute("SELECT product_id, quantity FROM order_items WHERE order_id = ?", (order_id,))
                items = cursor.fetchall()

                # Kiểm tra đủ tồn kho trước khi reopen
                for item in items:
                    p_id = item["product_id"]
                    qty = item["quantity"]
                    cursor.execute("SELECT name, stock_quantity FROM products WHERE id = ?", (p_id,))
                    prod = cursor.fetchone()
                    if not prod:
                        raise HTTPException(
                            status_code=status.HTTP_404_NOT_FOUND,
                            detail=f"Sản phẩm ID {p_id} không còn tồn tại trong hệ thống"
                        )
                    if prod["stock_quantity"] < qty:
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail=(
                                f"Không thể mở lại đơn hàng: Sản phẩm '{prod['name']}' không đủ tồn kho "
                                f"(hiện còn {prod['stock_quantity']}, cần {qty})"
                            )
                        )

                # Trừ lại tồn kho giữ chỗ cho đơn
                for item in items:
                    p_id = item["product_id"]
                    qty = item["quantity"]
                    cursor.execute("SELECT stock_quantity FROM products WHERE id = ?", (p_id,))
                    prod = cursor.fetchone()
                    stock_before = prod["stock_quantity"]
                    stock_after = stock_before - qty
                    cursor.execute(
                        "UPDATE products SET stock_quantity = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                        (stock_after, p_id)
                    )
                    cursor.execute(
                        """INSERT INTO inventory_logs (
                            product_id, change_type, reference_code,
                            quantity_before, change_quantity, quantity_after, note, created_at
                        ) VALUES (?, 'sale', ?, ?, ?, ?, ?, ?)""",
                        (
                            p_id, order_code, stock_before, qty,
                            stock_after, f"Giữ chỗ tồn kho khi SuperAdmin reopen đơn {order_code}", now_str
                        )
                    )

                resulting_status = "pending"
                existing_note = order["note"] or ""
                updated_note = f"{existing_note} [REOPEN by SuperAdmin: {clean_reason}]".strip()

                cursor.execute(
                    """UPDATE orders
                       SET status = ?,
                           rejected_by = NULL,
                           rejected_at = NULL,
                           rejection_reason = NULL,
                           note = ?
                       WHERE id = ?""",
                    (resulting_status, updated_note, order_id)
                )

            # -------------------------------------------------------------
            # ACTION 3: override_status
            # -------------------------------------------------------------
            elif action == "override_status":
                VALID_OVERRIDE_TARGETS = ("pending", "admin_approved", "processing", "completed")
                if not target_status:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Vui lòng chỉ định 'target_status' khi thực hiện override_status"
                    )

                if target_status not in VALID_OVERRIDE_TARGETS:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Trạng thái đích '{target_status}' không hợp lệ. Chỉ chấp nhận: {', '.join(VALID_OVERRIDE_TARGETS)}"
                    )

                if target_status == current_status:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Đơn hàng hiện tại đã ở trạng thái '{current_status}'"
                    )

                if current_status == "cancelled":
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Không thể override đơn hàng đã ở trạng thái 'cancelled' để bảo vệ tính nhất quán tồn kho. Vui lòng tạo đơn mới."
                    )

                if current_status == "rejected":
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Đơn hàng đang bị từ chối và tồn kho đã được hoàn. Vui lòng sử dụng action 'reopen_rejected' để kiểm tra và giữ lại tồn kho an toàn."
                    )

                # Xử lý tính toán total_spent
                if current_status == "completed" and target_status != "completed" and customer_id:
                    cursor.execute(
                        "UPDATE customers SET total_spent = MAX(0, total_spent - ?) WHERE id = ?",
                        (final_amount, customer_id)
                    )
                elif current_status != "completed" and target_status == "completed" and customer_id:
                    cursor.execute(
                        "UPDATE customers SET total_spent = total_spent + ? WHERE id = ?",
                        (final_amount, customer_id)
                    )

                resulting_status = target_status
                existing_note = order["note"] or ""
                updated_note = f"{existing_note} [OVERRIDE ({current_status}->{resulting_status}) by SuperAdmin: {clean_reason}]".strip()

                cursor.execute(
                    """UPDATE orders
                       SET status = ?,
                           processed_by = CASE WHEN ? = 'completed' THEN COALESCE(processed_by, ?) ELSE processed_by END,
                           processed_at = CASE WHEN ? = 'completed' THEN COALESCE(processed_at, ?) ELSE processed_at END,
                           note = ?
                       WHERE id = ?""",
                    (resulting_status, resulting_status, user_id, resulting_status, now_str, updated_note, order_id)
                )

            # Ghi nhận Audit Trail vào bảng order_audit_logs
            cursor.execute(
                """INSERT INTO order_audit_logs (
                    order_id, action, previous_status, resulting_status,
                    performed_by, reason, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (order_id, action, current_status, resulting_status, user_id, clean_reason, now_str)
            )

            updated_order = InventoryService._require_order_detail_by_id(cursor, order_id)
            return updated_order

    # =========================================================================
    # PHASE R3: COMPLETE ORDER WORKFLOW METHODS
    # =========================================================================

    @staticmethod
    def claim_order(order_id: int, user_id: int, user_role: str, note: Optional[str] = None) -> Dict[str, Any]:
        """
        Nghiệp vụ Tiếp nhận đơn hàng Atomic Claim Lock (Phase R3):
        - Chỉ áp dụng cho đơn đã được Admin phê duyệt ('admin_approved') và CHƯA có nhân viên nhận ('assigned_to IS NULL').
        - SQLite BEGIN IMMEDIATE khóa ghi chống Race Condition.
        - UPDATE có điều kiện nguyên tử:
          UPDATE orders SET assigned_to = ?, processed_by = ?, processed_at = ?, status = 'processing'
          WHERE id = ? AND status = 'admin_approved' AND assigned_to IS NULL
        - Nếu 2 Staff cạnh tranh nhận cùng lúc: người đến sau gặp rowcount == 0 -> trả về HTTP 409 Conflict.
        - Tuyệt đối không trừ tồn kho lần 2 (tồn kho đã giữ chỗ từ khi tạo đơn).
        - Không làm biến đổi payment_status.
        - Ghi nhật ký vào order_audit_logs ngay trong transaction.
        """
        now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        with get_db_transaction() as conn:
            cursor = conn.cursor()

            # 1. Thực hiện atomic conditional update
            cursor.execute(
                """UPDATE orders
                   SET assigned_to = ?,
                       processed_by = COALESCE(processed_by, ?),
                       processed_at = COALESCE(processed_at, ?),
                       status = 'processing'
                   WHERE id = ? AND status = 'admin_approved' AND assigned_to IS NULL""",
                (user_id, user_id, now_str, order_id)
            )

            if cursor.rowcount == 0:
                # Điều tra nguyên nhân thất bại
                cursor.execute("SELECT id, order_code, status, assigned_to FROM orders WHERE id = ?", (order_id,))
                order = cursor.fetchone()
                if not order:
                    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy đơn hàng cần tiếp nhận")

                if order["status"] in ("cancelled", "rejected", "completed"):
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Không thể tiếp nhận đơn hàng đã '{order['status']}'"
                    )

                if order["assigned_to"] is not None:
                    if order["assigned_to"] == user_id and order["status"] == "processing":
                        # Idempotency: Nhân viên hiện tại đã nhận đơn này trước đó và đơn đang xử lý
                        return InventoryService._require_order_detail_by_id(cursor, order_id)
                    if order["assigned_to"] != user_id:
                        cursor.execute("SELECT full_name FROM users WHERE id = ?", (order["assigned_to"],))
                        assigned_user = cursor.fetchone()
                        assigned_name = assigned_user["full_name"] if assigned_user else f"ID {order['assigned_to']}"
                        raise HTTPException(
                            status_code=status.HTTP_409_CONFLICT,
                            detail=f"Đơn hàng {order['order_code']} đã được nhân viên khác ({assigned_name}) tiếp nhận xử lý trước đó (Claim Conflict)"
                        )

                if order["status"] != "admin_approved":
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Chỉ có thể tiếp nhận đơn hàng đã được Admin duyệt (trạng thái hiện tại: '{order['status']}')"
                    )

            # 2. Ghi Audit Log vào order_audit_logs
            claim_reason = note.strip() if note and note.strip() else "Nhân viên tiếp nhận đơn hàng đã duyệt"
            cursor.execute(
                """INSERT INTO order_audit_logs (
                    order_id, action, previous_status, resulting_status,
                    performed_by, reason, created_at
                ) VALUES (?, 'claim_order', 'admin_approved', 'processing', ?, ?, ?)""",
                (order_id, user_id, claim_reason, now_str)
            )

            updated_order = InventoryService._require_order_detail_by_id(cursor, order_id)
            return updated_order

    @staticmethod
    def reassign_order(order_id: int, user_id: int, user_role: str, new_staff_id: int, reason: str) -> Dict[str, Any]:
        """
        Điều chuyển nhân viên phụ trách đơn hàng (Admin/SuperAdmin only):
        - Bắt buộc nhập lý do điều chuyển.
        - Ghi vết kiểm toán vào order_audit_logs.
        """
        if not reason or not reason.strip():
            raise HTTPException(status_code=400, detail="Lý do điều chuyển nhân viên phụ trách là bắt buộc")

        clean_reason = reason.strip()
        now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        with get_db_transaction() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, order_code, status, assigned_to FROM orders WHERE id = ?", (order_id,))
            order = cursor.fetchone()
            if not order:
                raise HTTPException(status_code=404, detail="Không tìm thấy đơn hàng cần điều chuyển")

            if order["status"] in ("cancelled", "rejected"):
                raise HTTPException(
                    status_code=400,
                    detail=f"Không thể điều chuyển đơn hàng đã '{order['status']}'"
                )

            # Xác thực nhân viên mới
            cursor.execute("SELECT id, full_name, role FROM users WHERE id = ?", (new_staff_id,))
            new_staff = cursor.fetchone()
            if not new_staff or new_staff["role"] not in ("staff", "admin", "superadmin", "manager"):
                raise HTTPException(status_code=400, detail=f"Nhân viên mới (ID: {new_staff_id}) không tồn tại hoặc không có vai trò xử lý đơn")

            old_assigned_to = order["assigned_to"]
            cursor.execute(
                """UPDATE orders
                   SET assigned_to = ?,
                       processed_by = ?
                   WHERE id = ?""",
                (new_staff_id, new_staff_id, order_id)
            )

            audit_reason = f"Điều chuyển từ NV ID {old_assigned_to or 'Chưa gán'} sang {new_staff['full_name']} (ID {new_staff_id}): {clean_reason}"
            cursor.execute(
                """INSERT INTO order_audit_logs (
                    order_id, action, previous_status, resulting_status,
                    performed_by, reason, created_at
                ) VALUES (?, 'reassign_order', ?, ?, ?, ?, ?)""",
                (order_id, order["status"], order["status"], user_id, audit_reason, now_str)
            )

            return InventoryService._require_order_detail_by_id(cursor, order_id)

    @staticmethod
    def notify_transfer(
        order_id: int,
        user_id: int,
        user_role: str,
        transfer_ref: Optional[str] = None,
        bank_name: Optional[str] = None,
        note: Optional[str] = None,
        own_customer_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Khách hàng / Nhân viên thông báo đã chuyển khoản thanh toán:
        - Customer chỉ có thể thông báo cho đơn của chính mình (chống IDOR).
        - Chuyển payment_status sang 'pending_verification'.
        - Tuyệt đối không tự ý đánh dấu 'paid'.
        - Ghi vết kiểm toán vào order_audit_logs.
        """
        now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        with get_db_transaction() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM orders WHERE id = ?", (order_id,))
            order = cursor.fetchone()
            if not order:
                raise HTTPException(status_code=404, detail="Không tìm thấy đơn hàng cần thông báo thanh toán")

            # Anti-IDOR: Nếu là customer, bắt buộc phải sở hữu đơn
            if user_role == "customer":
                is_own = (order["user_id"] == user_id) or (
                    own_customer_id is not None and order["customer_id"] == own_customer_id
                )
                if not is_own:
                    raise HTTPException(status_code=403, detail="Bạn không có quyền thao tác trên đơn hàng của người khác")

            if order["status"] in ("cancelled", "rejected"):
                raise HTTPException(
                    status_code=400,
                    detail=f"Không thể thông báo thanh toán cho đơn hàng đã '{order['status']}'"
                )

            current_payment = order["payment_status"]
            if current_payment == "paid":
                raise HTTPException(status_code=400, detail="Đơn hàng này đã được xác nhận thanh toán trước đó")
            if current_payment in ("refund_pending", "refunded"):
                raise HTTPException(status_code=400, detail="Đơn hàng đang trong quy trình hoàn tiền, không thể báo thanh toán")

            ref_str = transfer_ref.strip() if transfer_ref and transfer_ref.strip() else "Chưa cung cấp mã"
            bank_str = bank_name.strip() if bank_name and bank_name.strip() else "Chưa cung cấp ngân hàng"
            notify_info = f"[THÔNG BÁO CHUYỂN KHOẢN: Mã GD={ref_str}, Ngân hàng={bank_str}]"
            existing_note = order["note"] or ""
            updated_note = f"{existing_note} {notify_info}".strip()

            cursor.execute(
                """UPDATE orders
                   SET payment_status = 'pending_verification',
                       payment_status_raw = 'pending_verification',
                       note = ?
                   WHERE id = ?""",
                (updated_note, order_id)
            )

            audit_reason = f"Khách/Nhân viên thông báo chuyển tiền: Ref={ref_str}, Ngân hàng={bank_str}. Ghi chú: {note or 'N/A'}"
            cursor.execute(
                """INSERT INTO order_audit_logs (
                    order_id, action, previous_status, resulting_status,
                    performed_by, reason, created_at
                ) VALUES (?, 'notify_transfer', ?, 'pending_verification', ?, ?, ?)""",
                (order_id, current_payment, user_id, audit_reason, now_str)
            )

            return InventoryService._require_order_detail_by_id(cursor, order_id)

    @staticmethod
    def verify_payment(
        order_id: int,
        user_id: int,
        user_role: str,
        verified_ref: Optional[str] = None,
        note: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Admin/SuperAdmin xác minh tiền chuyển khoản thực nhận (Đối soát ngân hàng):
        - Chỉ Admin / SuperAdmin mới có thẩm quyền đối soát và xác nhận 'paid'.
        - Yêu cầu chứng từ đối soát đáng tin cậy (sao kê ngân hàng/biến động số dư).
        - Ghi nhận payment_status = 'paid'.
        - Ghi audit trail chi tiết vào order_audit_logs.
        """
        now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        with get_db_transaction() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM orders WHERE id = ?", (order_id,))
            order = cursor.fetchone()
            if not order:
                raise HTTPException(status_code=404, detail="Không tìm thấy đơn hàng cần xác minh thanh toán")

            if order["status"] in ("cancelled", "rejected"):
                raise HTTPException(status_code=400, detail=f"Không thể xác minh thanh toán cho đơn hàng đã '{order['status']}'")

            current_payment = order["payment_status"]
            if current_payment == "paid":
                # Idempotency
                return InventoryService._require_order_detail_by_id(cursor, order_id)

            ref_str = verified_ref.strip() if verified_ref and verified_ref.strip() else "Đối soát thủ công Admin"
            cursor.execute(
                """UPDATE orders
                   SET payment_status = 'paid',
                       payment_status_raw = 'paid'
                   WHERE id = ?""",
                (order_id,)
            )

            audit_reason = f"Admin đối soát và xác nhận tiền thực thu thành công. Mã đối soát/sao kê: {ref_str}. Ghi chú: {note or 'N/A'}"
            cursor.execute(
                """INSERT INTO order_audit_logs (
                    order_id, action, previous_status, resulting_status,
                    performed_by, reason, created_at
                ) VALUES (?, 'verify_payment', ?, 'paid', ?, ?, ?)""",
                (order_id, current_payment, user_id, audit_reason, now_str)
            )

            return InventoryService._require_order_detail_by_id(cursor, order_id)

    @staticmethod
    def confirm_cod_payment(
        order_id: int,
        user_id: int,
        user_role: str,
        note: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Xác nhận đã thu tiền mặt COD (Staff/Admin/SuperAdmin):
        - Bắt buộc payment_method == 'cash'.
        - Bắt buộc payment_status == 'unpaid'.
        - Chuyển sang 'paid' kèm audit log.
        """
        now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        with get_db_transaction() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM orders WHERE id = ?", (order_id,))
            order = cursor.fetchone()
            if not order:
                raise HTTPException(status_code=404, detail="Không tìm thấy đơn hàng cần xác nhận thu tiền COD")

            if order["payment_method"] != "cash":
                raise HTTPException(
                    status_code=400,
                    detail=f"Đơn hàng có phương thức thanh toán '{order['payment_method']}', không phải tiền mặt COD"
                )

            current_payment = order["payment_status"]
            if current_payment == "paid":
                return InventoryService._require_order_detail_by_id(cursor, order_id)

            cursor.execute(
                """UPDATE orders
                   SET payment_status = 'paid',
                       payment_status_raw = 'paid'
                   WHERE id = ?""",
                (order_id,)
            )

            audit_reason = f"Xác nhận đã thu tiền mặt COD thực tế từ khách hàng/shipper. Ghi chú: {note or 'N/A'}"
            cursor.execute(
                """INSERT INTO order_audit_logs (
                    order_id, action, previous_status, resulting_status,
                    performed_by, reason, created_at
                ) VALUES (?, 'confirm_cod_payment', ?, 'paid', ?, ?, ?)""",
                (order_id, current_payment, user_id, audit_reason, now_str)
            )

            return InventoryService._require_order_detail_by_id(cursor, order_id)

    @staticmethod
    def update_fulfillment(
        order_id: int,
        user_id: int,
        user_role: str,
        fulfillment_status: str,
        note: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Cập nhật trạng thái giao vận Fulfillment (Staff/Admin/SuperAdmin):
        - Enum: unfulfilled, packing, shipping, delivered, delivery_failed, returned_to_inventory, legacy_unknown.
        - Quy tắc chuyển đổi:
          + unfulfilled -> packing
          + packing -> shipping
          + shipping -> delivered HOẶC delivery_failed
        - ĐẶC BIỆT: 'delivery_failed' TUYỆT ĐỐI KHÔNG tự động hoàn kho (hàng còn đang trên đường hoàn về kho).
        - Ghi nhận chi tiết vào order_audit_logs.
        """
        VALID_FULFILLMENTS = ("unfulfilled", "packing", "shipping", "delivered", "delivery_failed", "returned_to_inventory")
        if fulfillment_status not in VALID_FULFILLMENTS:
            raise HTTPException(
                status_code=400,
                detail=f"Trạng thái giao vận '{fulfillment_status}' không hợp lệ. Chỉ chấp nhận: {', '.join(VALID_FULFILLMENTS)}"
            )

        now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        with get_db_transaction() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM orders WHERE id = ?", (order_id,))
            order = cursor.fetchone()
            if not order:
                raise HTTPException(status_code=404, detail="Không tìm thấy đơn hàng cần cập nhật vận chuyển")

            if order["status"] in ("cancelled", "rejected"):
                raise HTTPException(
                    status_code=400,
                    detail=f"Không thể cập nhật vận chuyển cho đơn hàng đã '{order['status']}'"
                )

            current_f = order["fulfillment_status"] or "unfulfilled"
            if current_f == fulfillment_status:
                return InventoryService._require_order_detail_by_id(cursor, order_id)

            # Kiểm tra ma trận chuyển trạng thái hợp lệ
            ALLOWED_TRANSITIONS = {
                "unfulfilled": ["packing", "shipping"],
                "packing": ["shipping", "unfulfilled"],
                "shipping": ["delivered", "delivery_failed"],
                "delivery_failed": ["shipping", "returned_to_inventory"],
                "delivered": [],
                "returned_to_inventory": [],
                "legacy_unknown": ["unfulfilled", "packing", "shipping", "delivered"]
            }

            allowed_targets = ALLOWED_TRANSITIONS.get(current_f, [])
            if fulfillment_status not in allowed_targets and user_role not in ("admin", "superadmin"):
                raise HTTPException(
                    status_code=400,
                    detail=f"Không thể chuyển trạng thái giao vận từ '{current_f}' sang '{fulfillment_status}'. Các trạng thái hợp lệ: {', '.join(allowed_targets) or 'Không còn'}"
                )

            cursor.execute(
                """UPDATE orders
                   SET fulfillment_status = ?
                   WHERE id = ?""",
                (fulfillment_status, order_id)
            )

            audit_reason = f"Cập nhật tiến độ giao vận từ '{current_f}' sang '{fulfillment_status}'. Ghi chú: {note or 'N/A'}"
            cursor.execute(
                """INSERT INTO order_audit_logs (
                    order_id, action, previous_status, resulting_status,
                    performed_by, reason, created_at
                ) VALUES (?, 'update_fulfillment', ?, ?, ?, ?, ?)""",
                (order_id, current_f, fulfillment_status, user_id, audit_reason, now_str)
            )

            return InventoryService._require_order_detail_by_id(cursor, order_id)

    @staticmethod
    def confirm_return(
        order_id: int,
        user_id: int,
        user_role: str,
        reason: Optional[str] = None,
        note: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Thủ kho xác nhận nhập lại hàng hoàn vật lý (Staff/Admin/SuperAdmin):
        - Điều kiện tiên quyết: Đơn hàng giao thất bại ('delivery_failed') hoặc đã hủy.
        - CHỐNG CỘNG TỒN KHO 2 LẦN (Idempotency Guard):
          + Kiểm tra fulfillment_status: nếu đã là 'returned_to_inventory' -> từ chối 400.
          + Kiểm tra inventory_logs: nếu đã có bản ghi 'return_cancel' cho đơn này -> từ chối 400.
        - Tăng lại stock_quantity và ghi log 'return_cancel'.
        - Chuyển fulfillment_status sang 'returned_to_inventory' và status sang 'cancelled' nếu chưa hủy.
        - Hoàn tiền độc lập: KHÔNG tự động gán refunded (tiền do kế toán đối soát riêng).
        """
        now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        with get_db_transaction() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM orders WHERE id = ?", (order_id,))
            order = cursor.fetchone()
            if not order:
                raise HTTPException(status_code=404, detail="Không tìm thấy đơn hàng cần nhập lại kho")

            current_f = order["fulfillment_status"] or "unfulfilled"
            order_code = order["order_code"]

            # Idempotency Check 1: Không nhập lại kho nếu đã ở trạng thái returned_to_inventory
            if current_f == "returned_to_inventory":
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Hàng của đơn {order_code} đã được nhập lại kho trước đó (đã xác nhận 'returned_to_inventory')"
                )

            # Kiểm tra trạng thái vận chuyển hợp lệ để nhập kho: Bắt buộc đã xác nhận hàng quay lại (delivery_failed hoặc cancelled)
            if current_f != "delivery_failed" and order["status"] not in ("cancelled", "rejected"):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Chỉ có thể xác nhận nhập lại hàng hoàn khi đơn ở trạng thái 'delivery_failed' hoặc 'cancelled' (hiện tại: fulfillment='{current_f}', status='{order['status']}')"
                )

            # Idempotency Check 2: Kiểm tra nhật ký inventory_logs đã từng hoàn tồn chưa
            cursor.execute(
                "SELECT id FROM inventory_logs WHERE reference_code = ? AND change_type = 'return_cancel'",
                (order_code,)
            )
            existing_return = cursor.fetchone()
            if existing_return:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Đơn hàng {order_code} đã có giao dịch hoàn trả tồn kho trong hệ thống (chống cộng tồn 2 lần)"
                )

            # Atomic conditional update guard: Đổi trạng thái sang returned_to_inventory trước khi cộng kho
            new_status = "cancelled" if order["status"] != "cancelled" else order["status"]
            cursor.execute(
                """UPDATE orders
                   SET fulfillment_status = 'returned_to_inventory',
                       status = ?
                   WHERE id = ? AND fulfillment_status != 'returned_to_inventory'""",
                (new_status, order_id)
            )
            if cursor.rowcount == 0:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Đơn hàng {order_code} đã được nhập lại kho trước đó (Idempotency Guard)"
                )

            clean_reason = reason.strip() if reason and reason.strip() else "Giao hàng thất bại và thủ kho đã nhận lại bưu kiện vật lý"

            # Hoàn trả tồn kho cho từng sản phẩm
            cursor.execute("SELECT product_id, quantity FROM order_items WHERE order_id = ?", (order_id,))
            items = cursor.fetchall()
            for item in items:
                p_id = item["product_id"]
                qty = item["quantity"]

                cursor.execute("SELECT stock_quantity FROM products WHERE id = ?", (p_id,))
                prod = cursor.fetchone()
                if prod:
                    stock_before = prod["stock_quantity"]
                    stock_after = stock_before + qty

                    cursor.execute(
                        "UPDATE products SET stock_quantity = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                        (stock_after, p_id)
                    )

                    cursor.execute(
                        """INSERT INTO inventory_logs (
                            product_id, change_type, reference_code,
                            quantity_before, change_quantity, quantity_after, note, created_at
                        ) VALUES (?, 'return_cancel', ?, ?, ?, ?, ?, ?)""",
                        (
                            p_id, order_code, stock_before, qty,
                            stock_after, f"Nhập lại kho hàng hoàn đơn {order_code}: {clean_reason}", now_str
                        )
                    )

            audit_reason = f"Thủ kho xác nhận đã nhận lại hàng hoàn vật lý: {clean_reason}. Ghi chú: {note or 'N/A'}"
            cursor.execute(
                """INSERT INTO order_audit_logs (
                    order_id, action, previous_status, resulting_status,
                    performed_by, reason, created_at
                ) VALUES (?, 'confirm_return', ?, 'returned_to_inventory', ?, ?, ?)""",
                (order_id, current_f, user_id, audit_reason, now_str)
            )

            return InventoryService._require_order_detail_by_id(cursor, order_id)

    @staticmethod
    def request_refund(
        order_id: int,
        user_id: int,
        user_role: str,
        reason: str,
        own_customer_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Yêu cầu hoàn tiền (Staff/Admin/SuperAdmin hoặc Customer sở hữu đơn):
        - Điều kiện: Đơn hàng đã thu tiền thực tế ('payment_status == paid').
        - Chuyển payment_status sang 'refund_pending'.
        - Độc lập hoàn toàn với tồn kho: KHÔNG tự ý nhập kho hoặc thay đổi fulfillment.
        - Ghi nhận vào order_audit_logs.
        """
        if not reason or not reason.strip():
            raise HTTPException(status_code=400, detail="Lý do yêu cầu hoàn tiền là bắt buộc")

        clean_reason = reason.strip()
        now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        with get_db_transaction() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM orders WHERE id = ?", (order_id,))
            order = cursor.fetchone()
            if not order:
                raise HTTPException(status_code=404, detail="Không tìm thấy đơn hàng cần yêu cầu hoàn tiền")

            # Anti-IDOR nếu là customer
            if user_role == "customer":
                is_own = (order["user_id"] == user_id) or (
                    own_customer_id is not None and order["customer_id"] == own_customer_id
                )
                if not is_own:
                    raise HTTPException(status_code=403, detail="Bạn không có quyền yêu cầu hoàn tiền cho đơn hàng của người khác")

            current_payment = order["payment_status"]
            if current_payment == "refund_pending":
                return InventoryService._require_order_detail_by_id(cursor, order_id)
            if current_payment == "refunded":
                raise HTTPException(status_code=400, detail="Đơn hàng này đã được hoàn tiền trước đó")
            if current_payment != "paid":
                raise HTTPException(
                    status_code=400,
                    detail=f"Chỉ có thể yêu cầu hoàn tiền cho đơn hàng đã thanh toán thành công (hiện tại: '{current_payment}')"
                )

            cursor.execute(
                """UPDATE orders
                   SET payment_status = 'refund_pending',
                       payment_status_raw = 'refund_pending'
                   WHERE id = ?""",
                (order_id,)
            )

            audit_reason = f"Yêu cầu hoàn tiền: {clean_reason}"
            cursor.execute(
                """INSERT INTO order_audit_logs (
                    order_id, action, previous_status, resulting_status,
                    performed_by, reason, created_at
                ) VALUES (?, 'request_refund', 'paid', 'refund_pending', ?, ?, ?)""",
                (order_id, user_id, audit_reason, now_str)
            )

            return InventoryService._require_order_detail_by_id(cursor, order_id)

    @staticmethod
    def confirm_refund(
        order_id: int,
        user_id: int,
        user_role: str,
        refund_ref: Optional[str] = None,
        reason: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Admin/SuperAdmin xác nhận đã hoàn tiền thực tế cho khách:
        - Điều kiện: payment_status đang ở 'refund_pending' (hoặc 'paid').
        - Chuyển payment_status sang 'refunded'.
        - Giảm total_spent của khách hàng tương ứng (nếu trước đó đã cộng khi completed).
        - Độc lập với tồn kho: KHÔNG tự ý hoàn kho.
        - Ghi nhận chi tiết vào order_audit_logs.
        """
        now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        with get_db_transaction() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM orders WHERE id = ?", (order_id,))
            order = cursor.fetchone()
            if not order:
                raise HTTPException(status_code=404, detail="Không tìm thấy đơn hàng cần xác nhận hoàn tiền")

            current_payment = order["payment_status"]
            if current_payment == "refunded":
                # Idempotency
                return InventoryService._require_order_detail_by_id(cursor, order_id)

            if current_payment not in ("refund_pending", "paid"):
                raise HTTPException(
                    status_code=400,
                    detail=f"Chỉ có thể hoàn tiền cho đơn đang ở trạng thái 'refund_pending' hoặc 'paid' (hiện tại: '{current_payment}')"
                )

            final_amount = float(order["final_amount"])
            customer_id = order["customer_id"]

            cursor.execute(
                """UPDATE orders
                   SET payment_status = 'refunded',
                       payment_status_raw = 'refunded'
                   WHERE id = ?""",
                (order_id,)
            )

            # Cập nhật giảm total_spent nếu đơn hàng đã từng hoàn tất
            if customer_id and order["status"] == "completed":
                cursor.execute(
                    "UPDATE customers SET total_spent = MAX(0, total_spent - ?) WHERE id = ?",
                    (final_amount, customer_id)
                )

            ref_str = refund_ref.strip() if refund_ref and refund_ref.strip() else "Ủy nhiệm chi / Tiền mặt"
            clean_reason = reason.strip() if reason and reason.strip() else "Admin xác nhận đã hoàn tiền thành công cho khách hàng"
            audit_reason = f"Xác nhận hoàn tiền thực tế (Ref={ref_str}): {clean_reason}"

            cursor.execute(
                """INSERT INTO order_audit_logs (
                    order_id, action, previous_status, resulting_status,
                    performed_by, reason, created_at
                ) VALUES (?, 'confirm_refund', ?, 'refunded', ?, ?, ?)""",
                (order_id, current_payment, user_id, audit_reason, now_str)
            )

            return InventoryService._require_order_detail_by_id(cursor, order_id)

    @staticmethod
    def get_order_audit_logs(
        order_id: int,
        user_id: int,
        user_role: str,
        own_customer_id: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Truy vấn toàn bộ diễn biến lịch sử audit trail của đơn hàng:
        - Customer: chỉ xem audit logs của đơn hàng do chính mình sở hữu (Anti-IDOR).
        - Staff / Admin / SuperAdmin: xem toàn bộ diễn biến.
        """
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, user_id, customer_id FROM orders WHERE id = ?", (order_id,))
            order = cursor.fetchone()
            if not order:
                raise HTTPException(status_code=404, detail="Không tìm thấy đơn hàng")

            if user_role == "customer":
                is_own = (order["user_id"] == user_id) or (
                    own_customer_id is not None and order["customer_id"] == own_customer_id
                )
                if not is_own:
                    raise HTTPException(status_code=403, detail="Bạn không có quyền xem nhật ký đơn hàng của người khác")

            cursor.execute(
                """SELECT oal.id, oal.order_id, oal.action, oal.previous_status, oal.resulting_status,
                          oal.performed_by, u.full_name as performer_name, oal.reason, oal.created_at
                   FROM order_audit_logs oal
                   LEFT JOIN users u ON oal.performed_by = u.id
                   WHERE oal.order_id = ?
                   ORDER BY oal.id ASC""",
                (order_id,)
            )
            logs = [dict(r) for r in cursor.fetchall()]
            return logs



    @staticmethod
    def create_purchase(purchase_in: PurchaseCreate, user_id: int) -> Dict[str, Any]:
        """
        Nghiệp vụ Nhập hàng Atomic:
        1. Tạo phiếu nhập (purchase_receipts).
        2. Tạo các chi tiết (purchase_items).
        3. Tăng tồn kho và cập nhật giá vốn (cost_price) mới nhất.
        4. Ghi log 'import' vào inventory_logs.
        """
        if not purchase_in.items:
            raise HTTPException(status_code=400, detail="Phiếu nhập hàng phải có ít nhất một mặt hàng")

        receipt_code = _generate_code("PN")
        created_at = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        with get_db_transaction() as conn:
            cursor = conn.cursor()

            total_amount = sum(item.quantity * item.import_price for item in purchase_in.items)

            cursor.execute(
                """INSERT INTO purchase_receipts (
                    receipt_code, supplier_name, user_id, total_amount, status, note, created_at
                ) VALUES (?, ?, ?, ?, 'completed', ?, ?)""",
                (receipt_code, purchase_in.supplier_name, user_id, total_amount, purchase_in.note, created_at)
            )
            receipt_id = cursor.lastrowid

            result_items = []
            for item in purchase_in.items:
                cursor.execute(
                    "SELECT id, sku, name, stock_quantity FROM products WHERE id = ?",
                    (item.product_id,)
                )
                prod = cursor.fetchone()
                if not prod:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"Không tìm thấy sản phẩm với ID {item.product_id}"
                    )

                subtotal = item.quantity * item.import_price
                cursor.execute(
                    """INSERT INTO purchase_items (receipt_id, product_id, quantity, import_price, subtotal)
                       VALUES (?, ?, ?, ?, ?)""",
                    (receipt_id, item.product_id, item.quantity, item.import_price, subtotal)
                )
                p_item_id = cursor.lastrowid

                # Tăng tồn kho và cập nhật cost_price
                stock_before = prod["stock_quantity"]
                stock_after = stock_before + item.quantity

                cursor.execute(
                    """UPDATE products SET 
                        stock_quantity = ?, cost_price = ?, updated_at = CURRENT_TIMESTAMP 
                       WHERE id = ?""",
                    (stock_after, item.import_price, item.product_id)
                )

                # Ghi log nhập hàng
                cursor.execute(
                    """INSERT INTO inventory_logs (
                        product_id, change_type, reference_code,
                        quantity_before, change_quantity, quantity_after, note, created_at
                    ) VALUES (?, 'import', ?, ?, ?, ?, ?, ?)""",
                    (
                        item.product_id, receipt_code, stock_before,
                        item.quantity, stock_after, f"Nhập hàng phiếu {receipt_code}", created_at
                    )
                )

                result_items.append({
                    "id": p_item_id,
                    "product_id": item.product_id,
                    "product_sku": prod["sku"],
                    "product_name": prod["name"],
                    "quantity": item.quantity,
                    "import_price": item.import_price,
                    "subtotal": subtotal
                })

            cursor.execute("SELECT full_name FROM users WHERE id = ?", (user_id,))
            u_row = cursor.fetchone()
            user_name = u_row["full_name"] if u_row else None

            return {
                "id": receipt_id,
                "receipt_code": receipt_code,
                "supplier_name": purchase_in.supplier_name,
                "user_id": user_id,
                "user_name": user_name,
                "total_amount": total_amount,
                "status": "completed",
                "note": purchase_in.note,
                "created_at": created_at,
                "items": result_items
            }
