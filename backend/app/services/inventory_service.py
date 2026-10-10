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
        cursor.execute(
            """SELECT o.id, o.order_code, o.customer_id, c.name as customer_name, c.phone as customer_phone,
                      o.user_id, u.full_name as user_name, o.total_amount, o.discount_amount,
                      o.final_amount, o.payment_method, o.payment_status, o.status, o.note,
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
            return None
        order_dict = dict(row)
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
    def create_order(order_in: OrderCreate, user_id: int, status: Optional[str] = None) -> Dict[str, Any]:
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
            payment_status = getattr(order_in, "payment_status", None) or "completed"
            # Bảo vệ chống Mass Assignment: assigned_to luôn NULL khi tạo đơn mới (chỉ gán qua claim_order có kiểm tra quyền ở R3)
            # is_legacy_unverified luôn 0 cho mọi đơn mới tạo
            shipping_name = getattr(order_in, "shipping_name", None)
            shipping_phone = getattr(order_in, "shipping_phone", None)
            shipping_address = getattr(order_in, "shipping_address", None)

            # 2. Tạo bản ghi Hóa đơn (Order)
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

            updated_order = InventoryService._get_order_detail_by_id(cursor, order_id)
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

            updated_order = InventoryService._get_order_detail_by_id(cursor, order_id)
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

            updated_order = InventoryService._get_order_detail_by_id(cursor, order_id)
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

            updated_order = InventoryService._get_order_detail_by_id(cursor, order_id)
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

            updated_order = InventoryService._get_order_detail_by_id(cursor, order_id)
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

            updated_order = InventoryService._get_order_detail_by_id(cursor, order_id)
            return updated_order



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
