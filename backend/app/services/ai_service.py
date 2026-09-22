import time
import json
from typing import List, Dict, Any, Optional
from google import genai
from google.genai import types

from app.core.config import settings
from app.core.database import get_db_connection
from app.core.prompt_loader import prompt_loader
from app.core.rate_limiter import ai_rate_limiter
from app.services.rag_service import rag_service
from app.services.report_service import ReportService
from app.schemas.ai import (
    ProductRecommendResponse,
    RecommendedProductItem,
    SalesReportResponse,
    SalesQAResponse,
    AIAuditLogResponse
)


class AIService:
    """
    AI Orchestration Layer for StoreFlow AI.
    Coordinates ChromaDB vector candidate retrieval, SQLite stock verification guard,
    PromptLoader templates, Google Gemini 3.6 Flash generation, graceful fallbacks,
    output secret sanitization, and audit logging in SQLite.
    """

    def __init__(self):
        self._client: Optional[genai.Client] = None

    @property
    def client(self) -> genai.Client:
        if self._client is None:
            self._client = genai.Client(api_key=settings.GEMINI_API_KEY)
        return self._client

    def _call_gemini(self, prompt: str, system_instruction: Optional[str] = None) -> str:
        """Helper to invoke Gemini with system instruction, standard config, and output sanitization."""
        sys_inst = system_instruction or prompt_loader.get_system_prompt()
        config = types.GenerateContentConfig(
            system_instruction=sys_inst,
            temperature=0.3,
            max_output_tokens=2048,
        )
        response = self.client.models.generate_content(
            model=settings.GEMINI_MODEL,
            contents=prompt,
            config=config
        )
        raw_text = response.text or ""
        return ai_rate_limiter.sanitize_output(raw_text)


    def _record_audit_log(
        self,
        feature: str,
        query_text: str,
        response_summary: str,
        latency_ms: int,
        user_id: Optional[int] = None
    ) -> None:
        """Logs all AI requests into ai_audit_logs SQLite table."""
        try:
            with get_db_connection() as conn:
                c = conn.cursor()
                c.execute("""
                    INSERT INTO ai_audit_logs (user_id, feature, query_text, response_summary, latency_ms)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    user_id,
                    feature,
                    query_text[:500],
                    response_summary[:1000],
                    latency_ms
                ))
                conn.commit()
        except Exception:
            # Audit log failure should never disrupt the user experience
            pass

    def recommend_products(
        self,
        user_query: str,
        budget: Optional[float] = None,
        limit: int = 5,
        user_id: Optional[int] = None,
        user_role: str = "guest"
    ) -> ProductRecommendResponse:
        """
        AI Product Recommendation with Hybrid RAG & Strict SQLite Stock Guard.
        Accessible to all roles (Guest, Customer, Staff, Admin, SuperAdmin).
        Guarantees that no out-of-stock items are ever recommended, and no internal cost/profit data is leaked.
        """
        start_time = time.time()
        budget_val = budget if budget is not None and budget > 0 else None

        # 1. RAG Candidate Retrieval & SQLite Stock Verification Guard
        rag_context = rag_service.get_grounded_recommendation_context(
            query=user_query,
            top_k=limit,
            budget_max=budget_val
        )

        verified_products_raw = rag_context["products"]
        context_text = rag_context["context_text"]
        budget_str = f"{int(budget_val):,} VNĐ" if budget_val else "Không giới hạn (linh hoạt theo chất lượng)"

        # 2. Format Prompt from external template
        prompt = prompt_loader.format_prompt(
            "product_recommendation",
            verified_products_context=context_text,
            user_query=user_query,
            budget_info=budget_str
        )

        # 3. Call Gemini with Fallback
        is_fallback = False
        try:
            ai_text = self._call_gemini(prompt)
        except Exception:
            is_fallback = True
            # Graceful rule-based fallback
            if verified_products_raw:
                lines = [
                    f"**StoreFlow AI — Gợi ý sản phẩm phù hợp** *(Chế độ tra cứu trực tiếp từ kho hàng)*:\n",
                    f"Dựa trên yêu cầu: *\"{user_query}\"* (Ngân sách: {budget_str}), các sản phẩm khả dụng trong kho gồm:\n"
                ]
                for p in verified_products_raw:
                    lines.append(
                        f"- **{p['name']}** (Mã: `{p['sku']}`)\n"
                        f"  - Giá bán: **{int(p['selling_price']):,} đ** | Còn tồn: **{p['stock_quantity']} {p['unit']}**\n"
                        f"  - Đặc tính: {p['description'] or 'Chính hãng'}\n"
                    )
                lines.append("\n*Lưu ý: Quý khách có thể chọn sản phẩm để tạo đơn hàng hoặc thêm vào giỏ hàng.*")
                ai_text = "\n".join(lines)
            else:
                ai_text = (
                    f"Rất tiếc, hiện tại kho hàng chưa có sản phẩm nào phù hợp với yêu cầu: *\"{user_query}\"* "
                    f"hoặc các sản phẩm tương ứng tạm thời đã hết hàng. Vui lòng thử tìm kiếm với từ khóa khác hoặc điều chỉnh mức ngân sách."
                )

        latency = int((time.time() - start_time) * 1000)

        # 4. Map structured products
        recommended_items = [
            RecommendedProductItem(
                id=p["id"],
                product_id=p["id"],
                sku=p["sku"],
                name=p["name"],
                category_name=p.get("category_name") or "",
                selling_price=float(p["selling_price"]),
                stock_quantity=int(p["stock_quantity"]),
                unit=p.get("unit") or "cái",
                description=p.get("description") or "",
                image_url=p.get("image_url") or "",
                status=p.get("status") or "active"
            )
            for p in verified_products_raw
        ]

        # 5. Record audit log
        self._record_audit_log(
            feature="recommendation",
            query_text=f"[{user_role.upper()}] Q: {user_query} | Budget: {budget_str}",
            response_summary=ai_text[:300],
            latency_ms=latency,
            user_id=user_id
        )

        return ProductRecommendResponse(
            ai_response=ai_text,
            recommended_products=recommended_items,
            query=user_query,
            total_candidates_found=len(recommended_items),
            is_fallback=is_fallback
        )

    def generate_sales_report(
        self,
        period: str = "month",
        user_id: Optional[int] = None,
        user_role: str = "superadmin"
    ) -> SalesReportResponse:
        """
        Generates an executive AI sales & inventory report grounded entirely in SQLite analytics.
        Strictly restricted to SuperAdmin (Store Owner).
        """
        if user_role != "superadmin":
            raise PermissionError("Chỉ Chủ cửa hàng (SuperAdmin) mới có quyền tạo Báo cáo Doanh thu AI.")

        start_time = time.time()

        # 1. Fetch real analytics from ReportService
        summary = ReportService.get_dashboard_summary()
        top_products = ReportService.get_top_products(limit=5)
        low_stock_list = ReportService.get_low_stock_products()

        # Build period label
        period_names = {
            "today": "Hôm nay",
            "7_days": "7 ngày gần nhất",
            "week": "Tuần này",
            "month": "Tháng này",
            "all": "Toàn thời gian"
        }
        period_label = period_names.get(period, f"Kỳ phân tích ({period})")

        # Context construction
        top_str_lines = []
        for idx, item in enumerate(top_products, start=1):
            top_str_lines.append(
                f"  {idx}. {item['name']} (Mã: {item['sku']}) - Đã bán: {item['total_quantity_sold']} cái - Doanh thu: {int(item['total_revenue']):,} đ"
            )
        top_text = "\n".join(top_str_lines) if top_str_lines else "  Chưa có dữ liệu bán hàng."

        low_str_lines = []
        for idx, item in enumerate(low_stock_list, start=1):
            low_str_lines.append(
                f"  {idx}. {item['name']} (Mã: {item['sku']}) - Tồn kho: {item['stock_quantity']} (Ngưỡng báo động: {item['min_stock_alert']})"
            )
        low_stock_text = "\n".join(low_str_lines) if low_str_lines else "  Tồn kho an toàn, không có sản phẩm nào chạm ngưỡng báo động."

        sales_data_context = (
            f"TỔNG KẾT DOANH THU & HOẠT ĐỘNG BÁN HÀNG TỪ CƠ SỞ DỮ LIỆU SQL:\n"
            f"- Tổng doanh thu tích lũy toàn thời gian: {int(summary['total_revenue']):,} VNĐ\n"
            f"- Doanh thu hôm nay: {int(summary['today_revenue']):,} VNĐ\n"
            f"- Doanh thu 7 ngày gần nhất: {int(summary.get('week_revenue', 0)):,} VNĐ\n"
            f"- Doanh thu tháng này: {int(summary.get('month_revenue', 0)):,} VNĐ\n"
            f"- Tổng số đơn hàng hoàn tất: {summary['total_orders']}\n"
            f"- Số sản phẩm cần nhập hàng gấp: {summary['low_stock_count']} mặt hàng\n\n"
            f"TOP 5 SẢN PHẨM BÁN CHẠY NHẤT:\n{top_text}\n\n"
            f"DANH SÁCH SẢN PHẨM CẦN NHẬP HÀNG GẤP:\n{low_stock_text}"
        )

        prompt = prompt_loader.format_prompt(
            "sales_report",
            sales_data_context=sales_data_context,
            report_period=period_label,
            additional_notes="Dữ liệu trích xuất từ database bán hàng thực tế StoreFlow AI."
        )

        # 2. Call Gemini with Fallback
        is_fallback = False
        try:
            ai_analysis = self._call_gemini(prompt)
        except Exception:
            is_fallback = True
            ai_analysis = (
                f"### Báo cáo Doanh thu & Tình hình Kinh doanh ({period_label})\n\n"
                f"**1. Tổng quan Doanh thu:**\n"
                f"- Doanh thu hôm nay: **{int(summary['today_revenue']):,} VNĐ**\n"
                f"- Doanh thu tuần này: **{int(summary.get('week_revenue', 0)):,} VNĐ**\n"
                f"- Doanh thu tháng này: **{int(summary.get('month_revenue', 0)):,} VNĐ**\n"
                f"- Tổng số đơn hàng đã hoàn tất: **{summary['total_orders']}** đơn hàng.\n\n"
                f"**2. Mặt hàng bán chạy nhất:**\n{top_text}\n\n"
                f"**3. Tình trạng Kho & Cảnh báo:**\n"
                f"- Hiện có **{summary['low_stock_count']}** mặt hàng đang ở mức báo động cần nhập hàng gấp.\n"
                f"{low_stock_text}\n\n"
                f"**4. Đề xuất hành động:**\n"
                f"- Ưu tiên lập phiếu nhập hàng cho các sản phẩm trong danh sách cảnh báo.\n"
                f"- Tiếp tục duy trì nguồn hàng dồi dào cho các sản phẩm nằm trong top 5 bán chạy."
            )

        latency = int((time.time() - start_time) * 1000)

        self._record_audit_log(
            feature="sales_report",
            query_text=f"Kỳ báo cáo: {period_label}",
            response_summary=ai_analysis[:300],
            latency_ms=latency,
            user_id=user_id
        )

        return SalesReportResponse(
            ai_analysis=ai_analysis,
            period=period,
            total_revenue=float(summary["total_revenue"]),
            total_orders=int(summary["total_orders"]),
            low_stock_count=int(summary["low_stock_count"]),
            top_selling_products=top_products,
            is_fallback=is_fallback
        )

    def answer_sales_qa(
        self,
        question: str,
        user_id: Optional[int] = None,
        user_role: str = "guest",
        user_full_name: Optional[str] = None
    ) -> SalesQAResponse:
        """
        Role-Aware AI Assistant & Q&A Orchestrator.
        Enforces strict backend data boundaries across roles:
          - SuperAdmin: Full access to financial analytics, revenue SQL facts, restocking recommendations.
          - Admin: System and product assistance. Denied sensitive store revenue/owner data.
          - Staff: POS assistance, product lookup, operational stock. Denied revenue/financial metrics.
          - Customer: Product consultation, shopping help, OWN order history (via authenticated customer_id).
                      Denied other customers' data, store revenue, internal management data.
          - Guest: Public product info, prices, descriptions, consultation. Denied revenue, internal logs, customer data.
        """
        start_time = time.time()
        role = (user_role or "guest").lower()
        q_lower = question.lower().strip()

        # ==================== 1. PROMPT INJECTION & SYSTEM SECRETS GUARD ====================
        injection_keywords = [
            "ignore previous instructions", "ignore all instructions", "ignore prompt",
            "forget all previous instructions", "forget instructions", "forget previous",
            "bỏ qua hướng dẫn", "bỏ qua câu lệnh", "quên hết chỉ dẫn", "quên hết hướng dẫn",
            "reveal system prompt", "show system prompt", "tiết lộ system prompt", "câu lệnh hệ thống",
            "reveal prompt", "in ra prompt", "show prompt template",
            "api key", "gemini_api_key", "secret key", "database password", "mật khẩu db",
            "act as admin", "act as superadmin", "you are now superadmin", "you are now admin", "you are now",
            "đóng vai admin", "đóng vai superadmin", "giả làm chủ shop",
            "bypass role", "override permission", "bỏ qua phân quyền",
            "drop table", "dump database", "select * from users"
        ]
        if any(kw in q_lower for kw in injection_keywords):
            safe_refusal = (
                "**StoreFlow AI — Thông báo an toàn hệ thống**:\n\n"
                "Yêu cầu của bạn đã bị từ chối do vi phạm quy tắc an toàn bảo mật. "
                "StoreFlow AI không được phép tiết lộ câu lệnh hệ thống (system prompt), mã khóa API, "
                "mật khẩu cơ sở dữ liệu hoặc thay đổi vai trò ngoài phân quyền được xác thực tại Backend."
            )
            latency = int((time.time() - start_time) * 1000)
            self._record_audit_log("sales_qa_injection_blocked", question, safe_refusal[:300], latency, user_id)
            return SalesQAResponse(
                answer=safe_refusal,
                query=question,
                context_type="security_guard",
                is_fallback=True
            )

        # ==================== 2. INTENT DETECTION & PERMISSION GATEKEEPING ====================
        revenue_keywords = [
            "doanh thu", "lợi nhuận", "tiền bán hàng", "báo cáo tài chính", "doanh số",
            "thu nhập cửa hàng", "tiền lãi", "revenue", "profit", "sales report",
            "báo cáo bán hàng", "tổng tiền bán", "tiền thu được", "bán được bao nhiêu tiền",
            "kế hoạch nhập hàng", "cần nhập thêm gì", "restock"
        ]
        is_revenue_query = any(kw in q_lower for kw in revenue_keywords)

        customer_order_keywords = [
            "đơn hàng của tôi", "lịch sử mua hàng của tôi", "đơn mua của tôi",
            "hóa đơn của tôi", "tra cứu đơn hàng của tôi", "my orders", "đơn hàng gần nhất của tôi"
        ]
        is_customer_order_query = any(kw in q_lower for kw in customer_order_keywords)

        customer_list_keywords = [
            "danh sách khách hàng", "số điện thoại khách hàng", "thông tin khách hàng",
            "danh sách user", "tất cả khách hàng", "all customers", "danh sách người dùng",
            "danh sách số điện thoại", "toàn bộ khách hàng"
        ]
        is_customer_list_query = any(kw in q_lower for kw in customer_list_keywords) or (
            ("khách hàng" in q_lower or "customer" in q_lower or "người dùng" in q_lower or "user" in q_lower) and
            any(k in q_lower for k in ["danh sách", "toàn bộ", "tất cả", "số điện thoại", "phone", "thông tin", "list", "all"])
        )

        # --- GATE A: REVENUE & FINANCIAL DATA ---
        if is_revenue_query:
            if role != "superadmin":
                # Backend Permission Enforcement: Deny non-SuperAdmin roles immediately without querying SQL revenue
                role_rejections = {
                    "guest": (
                        "🔒 **Thông báo phân quyền (Guest)**:\n\n"
                        "Bạn đang sử dụng hệ thống với tư cách **Khách vãng lai (Guest)**. "
                        "Dữ liệu doanh thu, lợi nhuận và số liệu kinh doanh là thông tin nội bộ bảo mật, "
                        "chỉ dành riêng cho **Chủ cửa hàng (SuperAdmin)**.\n\n"
                        "👉 Bạn có thể hỏi tôi thông tin về các sản phẩm, giá bán hoặc tư vấn thiết bị phù hợp!"
                    ),
                    "customer": (
                        "🔒 **Thông báo phân quyền (Customer)**:\n\n"
                        "Tài khoản **Khách hàng** không có quyền truy cập dữ liệu doanh thu và số liệu kinh doanh nội bộ của cửa hàng.\n\n"
                        "👉 Bạn có thể hỏi tôi tư vấn sản phẩm hoặc hỏi về lịch sử đơn hàng của chính bạn (ví dụ: *\"Đơn hàng của tôi gần đây thế nào?\"*)."
                    ),
                    "staff": (
                        "🔒 **Thông báo phân quyền (Staff)**:\n\n"
                        "Tài khoản **Nhân viên (Staff)** không có quyền xem dữ liệu doanh thu và báo cáo tài chính của cửa hàng theo chính sách bảo mật RBAC.\n\n"
                        "👉 Bạn có thể tra cứu thông tin sản phẩm và kiểm tra số lượng tồn kho để hỗ trợ bán hàng tại quầy POS."
                    ),
                    "admin": (
                        "🔒 **Thông báo phân quyền (Admin)**:\n\n"
                        "Tài khoản **Quản trị viên kỹ thuật (Admin)** không có quyền truy cập dữ liệu doanh thu và báo cáo tài chính kinh doanh của Chủ cửa hàng (SuperAdmin) theo chính sách RBAC.\n\n"
                        "👉 Quyền hạn của Admin bao gồm các tác vụ kỹ thuật như đồng bộ Vector DB và theo dõi nhật ký kiểm toán AI."
                    ),
                }
                refusal_msg = role_rejections.get(role, role_rejections["guest"])
                latency = int((time.time() - start_time) * 1000)
                self._record_audit_log("sales_qa_perm_denied", question, refusal_msg[:300], latency, user_id)
                return SalesQAResponse(
                    answer=refusal_msg,
                    query=question,
                    context_type="rbac_guard",
                    is_fallback=True
                )

            # ROLE IS SUPERADMIN -> Retrieve factual SQLite revenue analytics
            with get_db_connection() as conn:
                c = conn.cursor()
                c.execute("SELECT COUNT(*) as total_prod, SUM(stock_quantity) as total_stock FROM products WHERE status = 'active'")
                prod_stat = dict(c.fetchone())

                c.execute("""
                    SELECT c.name as category_name, COUNT(p.id) as product_count, SUM(p.stock_quantity) as cat_stock
                    FROM categories c
                    LEFT JOIN products p ON c.id = p.category_id AND p.status = 'active'
                    GROUP BY c.id
                """)
                category_stats = [dict(r) for r in c.fetchall()]

                c.execute("SELECT COUNT(*) as total_cust FROM customers")
                cust_count = c.fetchone()["total_cust"]

            summary = ReportService.get_dashboard_summary()

            cat_lines = [
                f"  - {cs['category_name']}: {cs['product_count']} mặt hàng (Tổng tồn: {cs['cat_stock'] or 0} cái)"
                for cs in category_stats
            ]

            verified_context = (
                f"THÔNG TIN THỐNG KÊ VẬN HÀNH CỬA HÀNG STOREFLOW AI (SQL TRUTH - DÀNH CHO SUPERADMIN):\n"
                f"- Người yêu cầu: {user_full_name or 'Chủ cửa hàng'} (Vai trò: SuperAdmin)\n"
                f"- Tổng số sản phẩm đang kinh doanh: {prod_stat['total_prod']} mặt hàng\n"
                f"- Tổng tồn kho hàng hóa toàn cửa hàng: {prod_stat['total_stock']} sản phẩm\n"
                f"- Phân bố hàng hóa theo danh mục:\n" + "\n".join(cat_lines) + "\n"
                f"- Tổng số khách hàng đã lưu trong hệ thống: {cust_count} khách hàng\n"
                f"- Doanh thu hôm nay: {int(summary['today_revenue']):,} đ\n"
                f"- Doanh thu tuần này: {int(summary.get('week_revenue', 0)):,} đ\n"
                f"- Doanh thu tháng này: {int(summary.get('month_revenue', 0)):,} đ\n"
                f"- Tổng doanh thu tích lũy: {int(summary['total_revenue']):,} đ\n"
                f"- Số đơn hàng đã xử lý: {summary['total_orders']}\n"
                f"- Số lượng sản phẩm sắp hết hàng cần lưu ý: {summary['low_stock_count']} sản phẩm"
            )

            prompt = prompt_loader.format_prompt(
                "sales_qa",
                verified_context=verified_context,
                user_query=question
            )

            is_fallback = False
            try:
                answer = self._call_gemini(prompt)
            except Exception:
                is_fallback = True
                answer = (
                    f"**Báo cáo tài chính & vận hành StoreFlow AI (SuperAdmin):**\n\n"
                    f"- Doanh thu tháng này hiện đạt **{int(summary.get('month_revenue', 0)):,} đ** qua **{summary['total_orders']}** đơn hàng hoàn tất.\n"
                    f"- Doanh thu hôm nay: **{int(summary['today_revenue']):,} đ** | Tuần này: **{int(summary.get('week_revenue', 0)):,} đ**.\n"
                    f"- Cửa hàng đang quản lý **{prod_stat['total_prod']}** mặt hàng kinh doanh với tổng cộng **{prod_stat['total_stock']}** sản phẩm trong kho.\n"
                    f"- Hiện có **{summary['low_stock_count']}** mặt hàng đang ở mức tồn kho thấp cần kiểm tra nhập thêm.\n"
                    f"*(Dữ liệu trích xuất chính xác 100% từ SQLite)*"
                )

            latency = int((time.time() - start_time) * 1000)
            self._record_audit_log("sales_qa_revenue", question, answer[:300], latency, user_id)
            return SalesQAResponse(
                answer=answer,
                query=question,
                context_type="superadmin_sql_facts",
                is_fallback=is_fallback
            )

        # --- GATE B: CUSTOMER ORDERS Q&A ---
        if is_customer_order_query:
            if role == "guest":
                msg = (
                    "🔒 **Tra cứu đơn hàng**:\n\n"
                    "Bạn đang sử dụng hệ thống với tư cách **Khách vãng lai (Guest)**. "
                    "Vui lòng **Đăng nhập** tài khoản Khách hàng để xem lịch sử và tiến độ các đơn hàng của bạn."
                )
                return SalesQAResponse(answer=msg, query=question, context_type="guest_guard", is_fallback=True)

            if role == "customer":
                # Deterministically look up only this customer's orders from SQLite using authenticated user_id
                with get_db_connection() as conn:
                    c = conn.cursor()
                    c.execute("SELECT id, customer_code, name, phone FROM customers WHERE user_id = ?", (user_id,))
                    cust_row = c.fetchone()
                    if not cust_row:
                        orders_text = "Hệ thống chưa tìm thấy hồ sơ khách hàng liên kết với tài khoản đăng nhập của bạn."
                    else:
                        cust_id = cust_row["id"]
                        c.execute("""
                            SELECT o.id, o.order_code, o.final_amount, o.payment_status, o.status, o.created_at,
                                   GROUP_CONCAT(p.name || ' (x' || oi.quantity || ')', '; ') as items
                            FROM orders o
                            LEFT JOIN order_items oi ON o.id = oi.order_id
                            LEFT JOIN products p ON oi.product_id = p.id
                            WHERE o.customer_id = ?
                            GROUP BY o.id
                            ORDER BY o.created_at DESC
                            LIMIT 5
                        """, (cust_id,))
                        rows = [dict(r) for r in c.fetchall()]
                        if not rows:
                            orders_text = f"Khách hàng {cust_row['name']} hiện chưa có đơn hàng nào trong hệ thống."
                        else:
                            lines = [f"Danh sách 5 đơn hàng gần nhất của bạn ({cust_row['name']}):"]
                            for r in rows:
                                status_vn = "Hoàn tất" if r["status"] == "completed" else "Đã hủy" if r["status"] == "cancelled" else r["status"]
                                pay_vn = "Đã thanh toán" if r["payment_status"] == "paid" else "Chưa thanh toán"
                                lines.append(
                                    f"- Đơn **{r['order_code']}** ({r['created_at'][:19]}): "
                                    f"Tổng tiền **{int(r['final_amount']):,} đ** | Trạng thái: **{status_vn}** ({pay_vn})\n"
                                    f"  Sản phẩm: {r['items'] or 'Không có thông tin chi tiết'}"
                                )
                            orders_text = "\n".join(lines)

                cust_context = (
                    f"THÔNG TIN ĐƠN HÀNG CỦA KHÁCH HÀNG (TRÍCH XUẤT TỪ SQL THEO TOKEN):\n"
                    f"{orders_text}"
                )

                prompt = (
                    f"{prompt_loader.get_system_prompt()}\n\n"
                    f"[NHIỆM VỤ]: Trả lời câu hỏi của khách hàng về đơn hàng của họ dựa trên dữ liệu sau:\n"
                    f"{cust_context}\n\n"
                    f"[CÂU HỎI CỦA KHÁCH HÀNG]: {question}\n\n"
                    f"Hãy trả lời rõ ràng, lịch sự, tóm tắt các đơn hàng của khách hàng."
                )

                try:
                    answer = self._call_gemini(prompt)
                except Exception:
                    answer = orders_text

                latency = int((time.time() - start_time) * 1000)
                self._record_audit_log("customer_orders_qa", question, answer[:300], latency, user_id)
                return SalesQAResponse(answer=answer, query=question, context_type="customer_sql_orders", is_fallback=False)

        # --- GATE C: CUSTOMER LIST / PRIVATE DATA ATTEMPT ---
        if is_customer_list_query and role not in ("superadmin", "admin"):
            refusal_msg = (
                "🔒 **Bảo mật dữ liệu cá nhân**:\n\n"
                "Danh sách khách hàng và thông tin cá nhân (số điện thoại, địa chỉ) là dữ liệu bảo mật "
                "theo chính sách quyền riêng tư. Bạn không có quyền truy cập dữ liệu này."
            )
            return SalesQAResponse(answer=refusal_msg, query=question, context_type="privacy_guard", is_fallback=True)

        # --- GATE D: PRODUCT CONSULTATION / PRODUCT LOOKUP (Available for ALL roles) ---
        # Fetch relevant products via ChromaDB candidate retrieval + SQLite verification guard
        rag_ctx = rag_service.get_grounded_recommendation_context(query=question, top_k=5)
        product_context = rag_ctx["context_text"]

        verified_context = (
            f"THÔNG TIN SẢN PHẨM KHẢ DỤNG TẠI CỬA HÀNG (SQL TRUTH):\n"
            f"{product_context}\n\n"
            f"VAI TRÒ NGƯỜI HỎI: {role.upper()} ({user_full_name or 'Khách vãng lai'})\n"
        )

        prompt = (
            f"{prompt_loader.get_system_prompt()}\n\n"
            f"[NHIỆM VỤ]: Bạn đang hỗ trợ trả lời câu hỏi của {user_full_name or 'khách hàng'} (Vai trò: {role}) "
            f"về sản phẩm, giá bán, cấu hình và tính năng tại cửa hàng.\n\n"
            f"[DỮ LIỆU SẢN PHẨM XÁC THỰC TỪ KHO]:\n{verified_context}\n\n"
            f"[CÂU HỎI]: {question}\n\n"
            f"QUY TẮC:\n"
            f"1. CHỈ sử dụng dữ liệu trong Context sản phẩm ở trên. Không tự bịa thông số, giá hoặc tình trạng kho.\n"
            f"2. Nếu không tìm thấy thông tin sản phẩm trong context, hãy thông báo lịch sự rằng cửa hàng chưa có mặt hàng này.\n"
            f"3. Trình bày rõ ràng, thân thiện."
        )

        is_fallback = False
        try:
            answer = self._call_gemini(prompt)
        except Exception:
            is_fallback = True
            prods = rag_ctx.get("products", [])
            if prods:
                p_lines = [
                    f"- **{p['name']}** (Mã: `{p['sku']}`): Giá **{int(p['selling_price']):,} đ** | Còn tồn: **{p['stock_quantity']} {p['unit']}**\n  {p['description'] or ''}"
                    for p in prods
                ]
                answer = (
                    f"**StoreFlow AI — Thông tin sản phẩm liên quan**:\n\n" +
                    "\n".join(p_lines)
                )
            else:
                answer = (
                    f"Xin lỗi, hiện tại tôi chưa tìm thấy thông tin sản phẩm phù hợp với câu hỏi: *\"{question}\"*. "
                    f"Quý khách vui lòng thử tìm kiếm với tên sản phẩm hoặc danh mục cụ thể hơn."
                )

        latency = int((time.time() - start_time) * 1000)
        self._record_audit_log(
            feature="sales_qa_product",
            query_text=f"[{role.upper()}] {question}",
            response_summary=answer[:300],
            latency_ms=latency,
            user_id=user_id
        )

        return SalesQAResponse(
            answer=answer,
            query=question,
            context_type="hybrid_product_rag",
            is_fallback=is_fallback
        )

    def get_audit_logs(self, limit: int = 50) -> List[AIAuditLogResponse]:
        """Retrieves recent AI interaction logs for auditing and monitoring."""
        with get_db_connection() as conn:
            c = conn.cursor()
            c.execute("""
                SELECT l.id, l.user_id, u.username, l.feature, l.query_text,
                       l.response_summary, l.latency_ms, l.created_at
                FROM ai_audit_logs l
                LEFT JOIN users u ON l.user_id = u.id
                ORDER BY l.id DESC
                LIMIT ?
            """, (limit,))
            rows = c.fetchall()

        return [
            AIAuditLogResponse(
                id=r["id"],
                user_id=r["user_id"],
                username=r["username"] or "Khách (Guest)",
                feature=r["feature"],
                query_text=r["query_text"],
                response_summary=r["response_summary"],
                latency_ms=r["latency_ms"],
                created_at=str(r["created_at"])
            )
            for r in rows
        ]



# Global singleton instance
ai_service = AIService()
