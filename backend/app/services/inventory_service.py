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
    def create_order(order_in: OrderCreate, user_id: int) -> Dict[str, Any]:
        """
        Nghiệp vụ Bán hàng POS Atomic:
        1. BEGIN IMMEDIATE khóa ghi SQLite.
        2. Kiểm tra từng mặt hàng: tồn kho, trạng thái active.
        3. Nếu thiếu hàng -> ROLLBACK ngay lập tức và raise 400.
        4. Tạo order, order_items.
        5. Trừ stock_quantity, ghi inventory_logs (change_type='sale').
        6. Cập nhật total_spent của khách hàng (nếu có).
        7. COMMIT transaction.
        """
        if not order_in.items:
            raise HTTPException(status_code=400, detail="Đơn hàng phải có ít nhất một sản phẩm")

        order_code = _generate_code("HD")
        created_at = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

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
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"Không tìm thấy sản phẩm với ID {item.product_id}"
                    )

                if product["status"] != "active":
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Sản phẩm '{product['name']}' (SKU: {product['sku']}) hiện đang ngừng kinh doanh"
                    )

                if product["stock_quantity"] < item.quantity:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
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

            # 2. Tạo bản ghi Hóa đơn (Order)
            cursor.execute(
                """INSERT INTO orders (
                    order_code, customer_id, user_id, total_amount,
                    discount_amount, final_amount, payment_method, payment_status, status, note, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'completed', ?, ?)""",
                (
                    order_code, order_in.customer_id, user_id, total_amount,
                    order_in.discount_amount, final_amount, order_in.payment_method,
                    payment_status, order_in.note, created_at
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

            # 4. Cập nhật tổng chi tiêu của khách hàng nếu có
            if order_in.customer_id:
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
                "status": "completed",
                "note": order_in.note,
                "created_at": created_at,
                "items": result_items
            }

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
