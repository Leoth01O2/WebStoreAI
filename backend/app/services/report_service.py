import io
import datetime
from typing import List, Dict, Any, Optional
import pandas as pd
from app.core.database import get_db

class ReportService:

    @staticmethod
    def get_dashboard_summary() -> Dict[str, Any]:
        """Tổng hợp các chỉ số điều hành cốt lõi từ SQLite (Source of Truth)"""
        with get_db() as conn:
            cursor = conn.cursor()

            # Tổng doanh thu từ các đơn hàng completed
            cursor.execute("SELECT COALESCE(SUM(final_amount), 0) as total FROM orders WHERE status = 'completed'")
            total_revenue = float(cursor.fetchone()["total"])

            # Doanh thu hôm nay
            cursor.execute(
                "SELECT COALESCE(SUM(final_amount), 0) as total FROM orders WHERE status = 'completed' AND DATE(created_at) = DATE('now')"
            )
            today_revenue = float(cursor.fetchone()["total"])

            # Doanh thu tuần này (7 ngày gần nhất)
            cursor.execute(
                "SELECT COALESCE(SUM(final_amount), 0) as total FROM orders WHERE status = 'completed' AND DATE(created_at) >= DATE('now', '-6 days')"
            )
            week_revenue = float(cursor.fetchone()["total"])

            # Doanh thu tháng này (từ đầu tháng đến nay)
            cursor.execute(
                "SELECT COALESCE(SUM(final_amount), 0) as total FROM orders WHERE status = 'completed' AND strftime('%Y-%m', created_at) = strftime('%Y-%m', 'now')"
            )
            month_revenue = float(cursor.fetchone()["total"])

            # Số lượng đơn hàng
            cursor.execute("SELECT COUNT(*) as cnt FROM orders")
            total_orders = cursor.fetchone()["cnt"]

            cursor.execute("SELECT COUNT(*) as cnt FROM orders WHERE DATE(created_at) = DATE('now')")
            today_orders = cursor.fetchone()["cnt"]

            cursor.execute("SELECT COUNT(*) as cnt FROM orders WHERE status = 'completed'")
            completed_orders = cursor.fetchone()["cnt"]

            cursor.execute("SELECT COUNT(*) as cnt FROM orders WHERE status = 'cancelled'")
            cancelled_orders = cursor.fetchone()["cnt"]

            # Tổng số sản phẩm và số lượng chạm ngưỡng cảnh báo
            cursor.execute("SELECT COUNT(*) as cnt FROM products")
            total_products = cursor.fetchone()["cnt"]

            cursor.execute(
                "SELECT COUNT(*) as cnt FROM products WHERE stock_quantity <= min_stock_alert AND status = 'active'"
            )
            low_stock_count = cursor.fetchone()["cnt"]

            # Phân định doanh thu: Hoàn tất (A), Đã đối soát xác minh (B), Lịch sử chưa đối soát (C)
            cursor.execute("PRAGMA table_info(orders)")
            order_cols = {r["name"] if isinstance(r, dict) or hasattr(r, "keys") else r[1] for r in cursor.fetchall()}
            if "payment_status_raw" in order_cols:
                cursor.execute("SELECT COALESCE(SUM(final_amount), 0) as total FROM orders WHERE payment_status = 'paid'")
                verified_payment_revenue = float(cursor.fetchone()["total"])
                cursor.execute(
                    "SELECT COALESCE(SUM(final_amount), 0) as total FROM orders WHERE status = 'completed' AND payment_status = 'unverified_legacy'"
                )
                legacy_unverified_revenue = float(cursor.fetchone()["total"])
            else:
                verified_payment_revenue = 0.0
                if "is_legacy_unverified" in order_cols:
                    cursor.execute(
                        "SELECT COALESCE(SUM(final_amount), 0) as total FROM orders WHERE status = 'completed' AND is_legacy_unverified = 1"
                    )
                    legacy_unverified_revenue = float(cursor.fetchone()["total"])
                else:
                    legacy_unverified_revenue = total_revenue
            # Khách hàng
            cursor.execute("SELECT COUNT(*) as cnt FROM customers")
            total_customers = cursor.fetchone()["cnt"]

            return {
                "total_revenue": total_revenue,
                "verified_payment_revenue": verified_payment_revenue,
                "legacy_unverified_revenue": legacy_unverified_revenue,
                "today_revenue": today_revenue,
                "week_revenue": week_revenue,
                "month_revenue": month_revenue,
                "total_orders": total_orders,
                "today_orders": today_orders,
                "completed_orders": completed_orders,
                "cancelled_orders": cancelled_orders,
                "total_products": total_products,
                "low_stock_count": low_stock_count,
                "total_customers": total_customers
            }

    @staticmethod
    def get_revenue_trend(days: int = 7) -> List[Dict[str, Any]]:
        """Xu hướng doanh thu theo ngày trong N ngày gần nhất"""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """SELECT DATE(created_at) as date, 
                          COALESCE(SUM(final_amount), 0) as revenue,
                          COUNT(id) as order_count
                   FROM orders
                   WHERE status = 'completed' AND DATE(created_at) >= DATE('now', ?)
                   GROUP BY DATE(created_at)
                   ORDER BY DATE(created_at) ASC""",
                (f"-{days} days",)
            )
            rows = cursor.fetchall()
            return [
                {
                    "date": r["date"],
                    "revenue": float(r["revenue"]),
                    "order_count": r["order_count"]
                }
                for r in rows
            ]

    @staticmethod
    def get_top_products(limit: int = 5) -> List[Dict[str, Any]]:
        """Top sản phẩm bán chạy nhất dựa trên các đơn hàng completed"""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """SELECT p.id as product_id, p.sku, p.name, c.name as category_name,
                          COALESCE(SUM(oi.quantity), 0) as total_quantity_sold,
                          COALESCE(SUM(oi.subtotal), 0) as total_revenue
                   FROM order_items oi
                   JOIN orders o ON oi.order_id = o.id
                   JOIN products p ON oi.product_id = p.id
                   LEFT JOIN categories c ON p.category_id = c.id
                   WHERE o.status = 'completed'
                   GROUP BY p.id
                   ORDER BY total_quantity_sold DESC, total_revenue DESC
                   LIMIT ?""",
                (limit,)
            )
            rows = cursor.fetchall()
            return [
                {
                    "product_id": r["product_id"],
                    "sku": r["sku"],
                    "name": r["name"],
                    "product_sku": r["sku"],
                    "product_name": r["name"],
                    "category_name": r["category_name"],
                    "total_quantity_sold": r["total_quantity_sold"],
                    "total_revenue": float(r["total_revenue"])
                }
                for r in rows
            ]

    @staticmethod
    def get_low_stock_products() -> List[Dict[str, Any]]:
        """Danh sách các sản phẩm đang chạm hoặc dưới ngưỡng cảnh báo hết hàng"""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """SELECT p.id as product_id, p.sku, p.name, c.name as category_name,
                          p.stock_quantity, p.min_stock_alert, p.unit
                   FROM products p
                   LEFT JOIN categories c ON p.category_id = c.id
                   WHERE p.stock_quantity <= p.min_stock_alert AND p.status = 'active'
                   ORDER BY p.stock_quantity ASC"""
            )
            rows = cursor.fetchall()
            return [
                {
                    "product_id": r["product_id"],
                    "sku": r["sku"],
                    "name": r["name"],
                    "category_name": r["category_name"],
                    "stock_quantity": r["stock_quantity"],
                    "min_stock_alert": r["min_stock_alert"],
                    "unit": r["unit"]
                }
                for r in rows
            ]

    @staticmethod
    def export_orders_df() -> pd.DataFrame:
        """Trích xuất danh sách hóa đơn bán hàng thành DataFrame phục vụ xuất file"""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """SELECT o.order_code as 'Mã Hóa Đơn',
                          o.created_at as 'Thời Gian',
                          COALESCE(c.name, 'Khách Vãng Lai') as 'Khách Hàng',
                          COALESCE(c.phone, '') as 'SĐT',
                          u.full_name as 'Thu Ngân',
                          o.total_amount as 'Tiền Hàng',
                          o.discount_amount as 'Giảm Giá',
                          o.final_amount as 'Thực Thu',
                          o.payment_method as 'Hình Thức',
                          o.status as 'Trạng Thái',
                          COALESCE(o.note, '') as 'Ghi Chú'
                   FROM orders o
                   LEFT JOIN customers c ON o.customer_id = c.id
                   LEFT JOIN users u ON o.user_id = u.id
                   ORDER BY o.created_at DESC"""
            )
            rows = cursor.fetchall()
            data = [dict(r) for r in rows]
            return pd.DataFrame(data)

    @staticmethod
    def export_orders_csv() -> str:
        """Xuất danh sách hóa đơn dạng CSV (UTF-8 có BOM để mở tiếng Việt trên Excel không lỗi font)"""
        df = ReportService.export_orders_df()
        return df.to_csv(index=False, encoding="utf-8-sig")

    @staticmethod
    def export_orders_excel() -> io.BytesIO:
        """Xuất danh sách hóa đơn dạng file Excel (.xlsx)"""
        df = ReportService.export_orders_df()
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:  # type: ignore[arg-type]
            df.to_excel(writer, index=False, sheet_name="Danh Sách Hóa Đơn")
        output.seek(0)
        return output
