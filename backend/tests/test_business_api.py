import pytest
from fastapi.testclient import TestClient
from app.main import app
from seed_data import seed_database
from app.core.database import get_db

@pytest.fixture(scope="session", autouse=True)
def setup_database():
    """Đảm bảo cơ sở dữ liệu đã có dữ liệu mẫu trước khi chạy test"""
    seed_database()

client = TestClient(app)

def get_tokens():
    """Helper lấy token cho 3 roles"""
    admin_res = client.post("/api/v1/auth/login", json={"username": "admin", "password": "Admin@123"})
    staff_res = client.post("/api/v1/auth/login", json={"username": "staff", "password": "Staff@123"})
    superadmin_res = client.post("/api/v1/auth/login", json={"username": "superadmin", "password": "SuperAdmin@123"})
    superadmin_token = superadmin_res.json()["access_token"]
    return {
        "admin": admin_res.json()["access_token"],
        "staff": staff_res.json()["access_token"],
        "superadmin": superadmin_token,
        "manager": superadmin_token
    }

# ==================== TEST 1: CATEGORIES CRUD & RBAC ====================
def test_categories_crud_and_rbac():
    import uuid
    tokens = get_tokens()
    admin_headers = {"Authorization": f"Bearer {tokens['admin']}"}
    staff_headers = {"Authorization": f"Bearer {tokens['staff']}"}

    unique_cat_code = f"CAT-RETRO-{uuid.uuid4().hex[:6].upper()}"

    # 1. Staff không được phép tạo danh mục (403)
    res = client.post(
        "/api/v1/categories",
        json={"name": "Danh mục cấm", "code": f"CAT-FORBIDDEN-{uuid.uuid4().hex[:4]}"},
        headers=staff_headers
    )
    assert res.status_code == 403

    # 2. Admin tạo danh mục thành công (200)
    res = client.post(
        "/api/v1/categories",
        json={"name": "Linh kiện PC Retro", "code": unique_cat_code, "description": "Bo mạch, chip cổ"},
        headers=admin_headers
    )
    assert res.status_code == 200
    cat_data = res.json()
    assert cat_data["code"] == unique_cat_code
    cat_id = cat_data["id"]

    # 3. Trùng mã code -> 400
    dup_res = client.post(
        "/api/v1/categories",
        json={"name": "Linh kiện trùng", "code": unique_cat_code},
        headers=admin_headers
    )
    assert dup_res.status_code == 400

    # 4. Staff xem danh sách danh mục -> 200
    list_res = client.get("/api/v1/categories", headers=staff_headers)
    assert list_res.status_code == 200
    codes = [c["code"] for c in list_res.json()]
    assert unique_cat_code in codes

# ==================== TEST 2: PRODUCTS CRUD & SEARCH/FILTER ====================
def test_products_crud_and_filter():
    import uuid
    tokens = get_tokens()
    admin_headers = {"Authorization": f"Bearer {tokens['admin']}"}
    staff_headers = {"Authorization": f"Bearer {tokens['staff']}"}
    superadmin_headers = {"Authorization": f"Bearer {tokens['superadmin']}"}

    unique_sku = f"SP-TEST-{uuid.uuid4().hex[:6].upper()}"
    prod_id = None

    try:
        # 1. Admin tạo sản phẩm mới
        prod_payload = {
            "sku": unique_sku,
            "name": "Chuột Bi Cổ Điển PS2",
            "cost_price": 50000,
            "selling_price": 120000,
            "stock_quantity": 15,
            "min_stock_alert": 3,
            "unit": "chiếc",
            "status": "active",
            "description": "Chuột bi cơ học dùng cổng PS/2 hoài niệm năm 2000"
        }
        create_res = client.post("/api/v1/products", json=prod_payload, headers=admin_headers)
        assert create_res.status_code == 200
        created_prod = create_res.json()
        assert created_prod["sku"] == unique_sku
        prod_id = created_prod["id"]

        # 2. Staff tìm kiếm sản phẩm theo tên / từ khóa
        search_res = client.get("/api/v1/products?search=Chuột Bi", headers=staff_headers)
        assert search_res.status_code == 200
        search_items = search_res.json()
        assert any(p["sku"] == unique_sku for p in search_items)

        # 3. Lọc theo khoảng giá min_price / max_price
        filter_res = client.get("/api/v1/products?min_price=100000&max_price=150000", headers=staff_headers)
        assert filter_res.status_code == 200
        assert all(100000 <= p["selling_price"] <= 150000 for p in filter_res.json())

        # 4. Staff không thể sửa giá sản phẩm (403)
        update_res = client.put(
            f"/api/v1/products/{prod_id}",
            json={"selling_price": 200000},
            headers=staff_headers
        )
        assert update_res.status_code == 403

        # 5. Dọn dẹp sản phẩm test (hard delete)
        del_res = client.delete(f"/api/v1/products/{prod_id}?hard_delete=true", headers=superadmin_headers)
        assert del_res.status_code == 200
    finally:
        # Guaranteed cleanup of any residual test SKUs in both SQLite and ChromaDB
        try:
            from app.services.rag_service import rag_service
            from app.services.visual_index_service import visual_index_service
            with get_db() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT id FROM products WHERE sku LIKE 'SP-TEST-%' OR name LIKE '%Chuột Bi%'")
                rows = cursor.fetchall()
                for r in rows:
                    tid = r["id"] if isinstance(r, dict) else r[0]
                    try:
                        rag_service.delete_single_product(tid)
                        visual_index_service.delete_single_product_visual(tid)
                    except Exception:
                        pass
                cursor.execute("DELETE FROM products WHERE sku LIKE 'SP-TEST-%' OR name LIKE '%Chuột Bi%'")
                conn.commit()
        except Exception:
            pass


# ==================== TEST 3: CUSTOMERS ====================
def test_customers_crud():
    import uuid
    tokens = get_tokens()
    staff_headers = {"Authorization": f"Bearer {tokens['staff']}"}

    unique_cust_code = f"KH-TEST-{uuid.uuid4().hex[:6].upper()}"
    unique_phone = f"09{uuid.uuid4().int % 100000000:08d}"

    cust_payload = {
        "customer_code": unique_cust_code,
        "name": "Đặng Thị Thảo",
        "phone": unique_phone,
        "email": f"thao.{uuid.uuid4().hex[:4]}@test.vn",
        "address": "99 Phố Huế, Hà Nội",
        "group_name": "vip"
    }
    res = client.post("/api/v1/customers", json=cust_payload, headers=staff_headers)
    assert res.status_code == 200
    cust = res.json()
    assert cust["customer_code"] == unique_cust_code

    # Tìm kiếm theo SĐT
    search_res = client.get(f"/api/v1/customers?search={unique_phone}", headers=staff_headers)
    assert search_res.status_code == 200
    assert len(search_res.json()) >= 1
    assert search_res.json()[0]["name"] == "Đặng Thị Thảo"

# ==================== TEST 4: ATOMIC POS ORDER CREATION ====================
def test_order_creation_atomic_stock_deduction():
    tokens = get_tokens()
    staff_headers = {"Authorization": f"Bearer {tokens['staff']}"}

    # Đảm bảo SP-AUDIO-01 có đủ tồn kho ban đầu cho test
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, stock_quantity, selling_price FROM products WHERE sku = 'SP-AUDIO-01'")
        prod = cursor.fetchone()
        prod_id = prod["id"]
        initial_stock = prod["stock_quantity"]
        if initial_stock < 5:
            cursor.execute("UPDATE products SET stock_quantity = 20 WHERE id = ?", (prod_id,))
            conn.commit()
            initial_stock = 20
        unit_price = prod["selling_price"]

    buy_qty = 2
    discount = 50000
    expected_total = buy_qty * unit_price
    expected_final = expected_total - discount

    order_payload = {
        "customer_id": 1,
        "discount_amount": discount,
        "payment_method": "cash",
        "note": "Đơn test POS trừ kho atomic",
        "items": [
            {"product_id": prod_id, "quantity": buy_qty}
        ]
    }

    # Thực hiện tạo đơn hàng POS
    res = client.post("/api/v1/orders", json=order_payload, headers=staff_headers)
    assert res.status_code == 200
    order_data = res.json()
    assert order_data["status"] == "completed"
    assert order_data["total_amount"] == expected_total
    assert order_data["final_amount"] == expected_final
    assert len(order_data["items"]) == 1
    order_id = order_data["id"]

    # Xác minh trong database: Tồn kho phải bị trừ chính xác `buy_qty`
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT stock_quantity FROM products WHERE id = ?", (prod_id,))
        new_stock = cursor.fetchone()["stock_quantity"]
        assert new_stock == initial_stock - buy_qty

        # Xác minh nhật ký inventory_logs ghi nhận change_type = 'sale'
        cursor.execute(
            "SELECT * FROM inventory_logs WHERE reference_code = ? AND product_id = ?",
            (order_data["order_code"], prod_id)
        )
        log = cursor.fetchone()
        assert log is not None
        assert log["change_type"] == "sale"
        assert log["change_quantity"] == -buy_qty
        assert log["quantity_after"] == new_stock

# ==================== TEST 5: ATOMIC TRANSACTION ROLLBACK ON INSUFFICIENT STOCK ====================
def test_order_creation_insufficient_stock_rollback():
    tokens = get_tokens()
    staff_headers = {"Authorization": f"Bearer {tokens['staff']}"}

    # Lấy sản phẩm có số lượng tồn kho nhất định
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, stock_quantity FROM products WHERE sku = 'SP-AUDIO-02'")
        prod = cursor.fetchone()
        prod_id = prod["id"]
        current_stock = prod["stock_quantity"]

    # Cố gắng mua vượt quá số lượng tồn kho (current_stock + 100)
    over_qty = current_stock + 100
    order_payload = {
        "items": [
            {"product_id": prod_id, "quantity": over_qty}
        ]
    }

    res = client.post("/api/v1/orders", json=order_payload, headers=staff_headers)
    assert res.status_code == 400
    assert "không đủ số lượng tồn kho" in res.json()["detail"]

    # Kiểm tra tính toàn vẹn: Tồn kho KHÔNG được phép thay đổi
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT stock_quantity FROM products WHERE id = ?", (prod_id,))
        stock_after = cursor.fetchone()["stock_quantity"]
        assert stock_after == current_stock, "Tồn kho bị biến động dù transaction đã rollback!"

# ==================== TEST 6: ORDER CANCELLATION RESTORES STOCK ATOMICALLY ====================
def test_order_cancellation_restores_stock():
    tokens = get_tokens()
    staff_headers = {"Authorization": f"Bearer {tokens['staff']}"}
    manager_headers = {"Authorization": f"Bearer {tokens['manager']}"}

    # 1. Tạo đơn hàng 3 chiếc SP-OFFICE-02
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, stock_quantity FROM products WHERE sku = 'SP-OFFICE-02'")
        prod = cursor.fetchone()
        prod_id = prod["id"]
        stock_before_order = prod["stock_quantity"]

    order_res = client.post(
        "/api/v1/orders",
        json={"items": [{"product_id": prod_id, "quantity": 3}], "customer_id": 1},
        headers=staff_headers
    )
    assert order_res.status_code == 200
    order_data = order_res.json()
    order_id = order_data["id"]

    # Kiểm tra tồn kho đã bị trừ 3
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT stock_quantity FROM products WHERE id = ?", (prod_id,))
        assert cursor.fetchone()["stock_quantity"] == stock_before_order - 3

    # 2. Staff thử hủy đơn -> 403 Forbidden
    staff_cancel = client.post(f"/api/v1/orders/{order_id}/cancel", headers=staff_headers)
    assert staff_cancel.status_code == 403

    # 3. Manager hủy đơn -> 200 OK
    cancel_res = client.post(
        f"/api/v1/orders/{order_id}/cancel",
        json={"reason": "Khách đổi mẫu khác"},
        headers=manager_headers
    )
    assert cancel_res.status_code == 200
    assert cancel_res.json()["status"] == "cancelled"

    # 4. Kiểm tra tồn kho ĐÃ ĐƯỢC HOÀN TRẢ đầy đủ 3 chiếc
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT stock_quantity FROM products WHERE id = ?", (prod_id,))
        stock_after_cancel = cursor.fetchone()["stock_quantity"]
        assert stock_after_cancel == stock_before_order

        # Kiểm tra nhật ký xuất nhập tồn có dòng return_cancel
        cursor.execute(
            "SELECT * FROM inventory_logs WHERE reference_code = ? AND change_type = 'return_cancel'",
            (order_data["order_code"],)
        )
        cancel_log = cursor.fetchone()
        assert cancel_log is not None
        assert cancel_log["change_quantity"] == 3

    # 5. Hủy lại đơn đã hủy -> 400 Bad Request
    re_cancel = client.post(f"/api/v1/orders/{order_id}/cancel", headers=manager_headers)
    assert re_cancel.status_code == 400

# ==================== TEST 7: PURCHASE RECEIPT INCREASES STOCK ====================
def test_purchase_receipt_increases_stock():
    tokens = get_tokens()
    manager_headers = {"Authorization": f"Bearer {tokens['manager']}"}

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, stock_quantity, cost_price FROM products WHERE sku = 'SP-SMART-01'")
        prod = cursor.fetchone()
        prod_id = prod["id"]
        stock_before = prod["stock_quantity"]

    import_qty = 10
    new_import_price = 330000

    purchase_payload = {
        "supplier_name": "Công ty Cổ phần Thiết bị Chiếu sáng Ánh Sao",
        "note": "Nhập thêm 10 đèn chống cận",
        "items": [
            {"product_id": prod_id, "quantity": import_qty, "import_price": new_import_price}
        ]
    }

    res = client.post("/api/v1/purchases", json=purchase_payload, headers=manager_headers)
    assert res.status_code == 200
    purchase_data = res.json()
    assert purchase_data["status"] == "completed"
    assert purchase_data["total_amount"] == import_qty * new_import_price

    # Kiểm tra tồn kho tăng chính xác và giá vốn được cập nhật
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT stock_quantity, cost_price FROM products WHERE id = ?", (prod_id,))
        updated_prod = cursor.fetchone()
        assert updated_prod["stock_quantity"] == stock_before + import_qty
        assert updated_prod["cost_price"] == new_import_price

# ==================== TEST 8: REPORTS & ANALYTICS SQL AGGREGATION ====================
def test_reports_and_export():
    tokens = get_tokens()
    manager_headers = {"Authorization": f"Bearer {tokens['manager']}"}
    staff_headers = {"Authorization": f"Bearer {tokens['staff']}"}

    # 1. Staff và Admin không được truy cập dashboard báo cáo doanh thu (403)
    assert client.get("/api/v1/reports/summary", headers=staff_headers).status_code == 403
    admin_headers = {"Authorization": f"Bearer {tokens['admin']}"}
    assert client.get("/api/v1/reports/summary", headers=admin_headers).status_code == 403

    # 2. Manager xem tổng quan điều hành -> 200
    summary_res = client.get("/api/v1/reports/summary", headers=manager_headers)
    assert summary_res.status_code == 200
    summary = summary_res.json()
    assert "total_revenue" in summary
    assert summary["total_revenue"] > 0
    assert summary["total_orders"] > 0
    assert summary["completed_orders"] >= 1

    # 3. Biểu đồ doanh thu theo ngày
    trend_res = client.get("/api/v1/reports/revenue-trend?days=7", headers=manager_headers)
    assert trend_res.status_code == 200
    assert isinstance(trend_res.json(), list)

    # 4. Top sản phẩm bán chạy
    top_res = client.get("/api/v1/reports/top-products?limit=5", headers=manager_headers)
    assert top_res.status_code == 200
    assert isinstance(top_res.json(), list)

    # 5. Xuất báo cáo CSV
    csv_res = client.get("/api/v1/reports/export/csv", headers=manager_headers)
    assert csv_res.status_code == 200
    assert "text/csv" in csv_res.headers["content-type"]
    assert "Mã Hóa Đơn" in csv_res.text

    # 6. Xuất báo cáo Excel
    excel_res = client.get("/api/v1/reports/export/excel", headers=manager_headers)
    assert excel_res.status_code == 200
    assert "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" in excel_res.headers["content-type"]
    assert len(excel_res.content) > 1000

# ==================== TEST 9: INVENTORY LOGS & LOW STOCK ALERTS ====================
def test_inventory_logs_and_alerts():
    tokens = get_tokens()
    manager_headers = {"Authorization": f"Bearer {tokens['manager']}"}
    staff_headers = {"Authorization": f"Bearer {tokens['staff']}"}

    # 1. Xem nhật ký biến động kho
    logs_res = client.get("/api/v1/inventory/logs", headers=manager_headers)
    assert logs_res.status_code == 200
    logs = logs_res.json()
    assert len(logs) > 0
    assert any(log["change_type"] in ["sale", "import", "return_cancel"] for log in logs)

    # 2. Cảnh báo sản phẩm sắp hết hàng (Staff và Manager đều xem được)
    low_res = client.get("/api/v1/inventory/low-stock", headers=staff_headers)
    assert low_res.status_code == 200
    low_items = low_res.json()
    assert all(item["stock_quantity"] <= item["min_stock_alert"] for item in low_items)
