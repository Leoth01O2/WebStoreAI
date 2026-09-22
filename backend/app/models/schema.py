import sys
from app.core.database import get_db

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    getattr(sys.stdout, "reconfigure")(encoding="utf-8")
if sys.stderr and hasattr(sys.stderr, "reconfigure"):
    getattr(sys.stderr, "reconfigure")(encoding="utf-8")

SCHEMA_SQL = """
-- 1. Bảng Người dùng & Phân quyền
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    full_name TEXT NOT NULL,
    role TEXT NOT NULL CHECK(role IN ('superadmin', 'admin', 'staff', 'customer')),
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 2. Bảng Danh mục / Nhóm hàng
CREATE TABLE IF NOT EXISTS categories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    code TEXT UNIQUE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 3. Bảng Sản phẩm
CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sku TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    category_id INTEGER REFERENCES categories(id) ON DELETE SET NULL,
    cost_price REAL NOT NULL DEFAULT 0,
    selling_price REAL NOT NULL DEFAULT 0,
    stock_quantity INTEGER NOT NULL DEFAULT 0,
    min_stock_alert INTEGER NOT NULL DEFAULT 5,
    unit TEXT NOT NULL DEFAULT 'cái',
    status TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active', 'inactive')),
    image_url TEXT,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 4. Bảng Khách hàng
CREATE TABLE IF NOT EXISTS customers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_code TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    phone TEXT,
    email TEXT,
    address TEXT,
    group_name TEXT NOT NULL DEFAULT 'retail' CHECK(group_name IN ('retail', 'vip', 'wholesale')),
    total_spent REAL NOT NULL DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 5. Bảng Hóa đơn bán hàng (Orders)
CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_code TEXT UNIQUE NOT NULL,
    customer_id INTEGER REFERENCES customers(id) ON DELETE SET NULL,
    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    total_amount REAL NOT NULL DEFAULT 0,
    discount_amount REAL NOT NULL DEFAULT 0,
    final_amount REAL NOT NULL DEFAULT 0,
    payment_method TEXT NOT NULL DEFAULT 'cash' CHECK(payment_method IN ('cash', 'transfer', 'card')),
    payment_status TEXT NOT NULL DEFAULT 'completed' CHECK(payment_status IN ('pending', 'paid', 'completed')),
    status TEXT NOT NULL DEFAULT 'completed' CHECK(status IN ('completed', 'cancelled')),
    note TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 6. Bảng Chi tiết hóa đơn bán hàng (Order Items)
CREATE TABLE IF NOT EXISTS order_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id INTEGER NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    product_id INTEGER NOT NULL REFERENCES products(id),
    quantity INTEGER NOT NULL CHECK(quantity > 0),
    unit_price REAL NOT NULL,
    subtotal REAL NOT NULL
);

-- 7. Bảng Phiếu nhập hàng (Purchase Receipts)
CREATE TABLE IF NOT EXISTS purchase_receipts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    receipt_code TEXT UNIQUE NOT NULL,
    supplier_name TEXT NOT NULL,
    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    total_amount REAL NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'completed' CHECK(status IN ('completed', 'cancelled')),
    note TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 8. Bảng Chi tiết phiếu nhập hàng (Purchase Items)
CREATE TABLE IF NOT EXISTS purchase_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    receipt_id INTEGER NOT NULL REFERENCES purchase_receipts(id) ON DELETE CASCADE,
    product_id INTEGER NOT NULL REFERENCES products(id),
    quantity INTEGER NOT NULL CHECK(quantity > 0),
    import_price REAL NOT NULL,
    subtotal REAL NOT NULL
);

-- 9. Bảng Nhật ký xuất - nhập - tồn (Inventory Logs)
CREATE TABLE IF NOT EXISTS inventory_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER NOT NULL REFERENCES products(id),
    change_type TEXT NOT NULL CHECK(change_type IN ('import', 'sale', 'return_cancel', 'adjustment')),
    reference_code TEXT,
    quantity_before INTEGER NOT NULL,
    change_quantity INTEGER NOT NULL,
    quantity_after INTEGER NOT NULL,
    note TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 10. Bảng Nhật ký truy vấn AI (AI Audit Logs)
CREATE TABLE IF NOT EXISTS ai_audit_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    feature TEXT NOT NULL CHECK(feature IN ('recommendation', 'sales_report', 'sales_qa')),
    query_text TEXT NOT NULL,
    response_summary TEXT,
    latency_ms INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 11. Bảng Thông tin thị giác sản phẩm (Product Visual Metadata phục vụ Image Search)
CREATE TABLE IF NOT EXISTS product_visual_metadata (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER UNIQUE NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    image_path TEXT NOT NULL,
    product_type TEXT NOT NULL,
    dominant_color TEXT,
    shape_form TEXT,
    material TEXT,
    visible_features TEXT,
    visual_description TEXT,
    search_keywords TEXT,
    visual_embedding TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Tạo Index để tối ưu truy vấn
CREATE INDEX IF NOT EXISTS idx_products_sku ON products(sku);
CREATE INDEX IF NOT EXISTS idx_products_category ON products(category_id);
CREATE INDEX IF NOT EXISTS idx_products_status ON products(status);
CREATE INDEX IF NOT EXISTS idx_orders_code ON orders(order_code);
CREATE INDEX IF NOT EXISTS idx_orders_created ON orders(created_at);
CREATE INDEX IF NOT EXISTS idx_order_items_order ON order_items(order_id);
CREATE INDEX IF NOT EXISTS idx_inventory_logs_product ON inventory_logs(product_id);
CREATE INDEX IF NOT EXISTS idx_customers_phone ON customers(phone);
CREATE INDEX IF NOT EXISTS idx_visual_metadata_product ON product_visual_metadata(product_id);
CREATE INDEX IF NOT EXISTS idx_visual_metadata_type ON product_visual_metadata(product_type);
"""

def init_db():
    """Khởi tạo toàn bộ schema cơ sở dữ liệu nếu chưa tồn tại và chạy migrate an toàn"""
    with get_db() as conn:
        conn.executescript(SCHEMA_SQL)
        cursor = conn.cursor()
        
        # Migration kiểm tra cột image_url trong bảng products
        cursor.execute("PRAGMA table_info(products)")
        product_cols = [row["name"] for row in cursor.fetchall()]
        if "image_url" not in product_cols:
            cursor.execute("ALTER TABLE products ADD COLUMN image_url TEXT")
            conn.commit()
            print("[DB Migration] Added column 'image_url' to products table.")

        # Migration kiểm tra cột payment_status trong bảng orders
        cursor.execute("PRAGMA table_info(orders)")
        order_cols = [row["name"] for row in cursor.fetchall()]
        if "payment_status" not in order_cols:
            cursor.execute("ALTER TABLE orders ADD COLUMN payment_status TEXT NOT NULL DEFAULT 'completed'")
            conn.commit()
            print("[DB Migration] Added column 'payment_status' to orders table.")

    print("[DB] Database schema initialized successfully.")

if __name__ == "__main__":
    init_db()

