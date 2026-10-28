from __future__ import annotations
import sys
import os
import sqlite3
from typing import Any, Callable
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
    description TEXT,
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
    brand TEXT,
    product_type TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 4. Bảng Khách hàng
CREATE TABLE IF NOT EXISTS customers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
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
    status TEXT NOT NULL DEFAULT 'completed' CHECK(status IN ('pending', 'confirmed', 'admin_approved', 'processing', 'completed', 'rejected', 'cancelled')),
    note TEXT,
    approved_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
    approved_at TIMESTAMP,
    processed_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
    processed_at TIMESTAMP,
    rejected_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
    rejected_at TIMESTAMP,
    rejection_reason TEXT,
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

-- 12. Bảng Nhật ký thao tác ngoại lệ đơn hàng (Order Audit Logs - Phase 13E)
CREATE TABLE IF NOT EXISTS order_audit_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id INTEGER NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    action TEXT NOT NULL,
    previous_status TEXT NOT NULL,
    resulting_status TEXT NOT NULL,
    performed_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
    reason TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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
CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status);
CREATE INDEX IF NOT EXISTS idx_visual_metadata_product ON product_visual_metadata(product_id);
CREATE INDEX IF NOT EXISTS idx_visual_metadata_type ON product_visual_metadata(product_type);
CREATE INDEX IF NOT EXISTS idx_order_audit_order_id ON order_audit_logs(order_id);
"""

def init_db():
    """Khởi tạo toàn bộ schema cơ sở dữ liệu nếu chưa tồn tại và chạy migrate an toàn"""
    with get_db() as conn:
        conn.executescript(SCHEMA_SQL)
        cursor = conn.cursor()
        
        # Migration kiểm tra cột description trong bảng categories
        cursor.execute("PRAGMA table_info(categories)")
        cat_cols = [row["name"] for row in cursor.fetchall()]
        if "description" not in cat_cols:
            cursor.execute("ALTER TABLE categories ADD COLUMN description TEXT")
            conn.commit()
            print("[DB Migration] Added column 'description' to categories table.")

        # Migration kiểm tra cột user_id trong bảng customers
        cursor.execute("PRAGMA table_info(customers)")
        cust_cols = [row["name"] for row in cursor.fetchall()]
        if "user_id" not in cust_cols:
            cursor.execute("ALTER TABLE customers ADD COLUMN user_id INTEGER REFERENCES users(id) ON DELETE SET NULL")
            conn.commit()
            print("[DB Migration] Added column 'user_id' to customers table.")

        # Migration kiểm tra cột image_url trong bảng products
        cursor.execute("PRAGMA table_info(products)")
        product_cols = [row["name"] for row in cursor.fetchall()]
        if "image_url" not in product_cols:
            cursor.execute("ALTER TABLE products ADD COLUMN image_url TEXT")
            conn.commit()
            print("[DB Migration] Added column 'image_url' to products table.")

        # Migration kiểm tra cột brand và product_type trong bảng products
        cursor.execute("PRAGMA table_info(products)")
        product_cols = [row["name"] for row in cursor.fetchall()]
        if "brand" not in product_cols:
            cursor.execute("ALTER TABLE products ADD COLUMN brand TEXT")
            conn.commit()
            print("[DB Migration] Added column 'brand' to products table.")
        if "product_type" not in product_cols:
            cursor.execute("ALTER TABLE products ADD COLUMN product_type TEXT")
            conn.commit()
            print("[DB Migration] Added column 'product_type' to products table.")

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_products_brand ON products(brand)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_products_product_type ON products(product_type)")
        conn.commit()

        # Idempotent category check: 'Laptop & Máy tính' (CAT-LAPTOP)
        cursor.execute("SELECT id FROM categories WHERE code = 'CAT-LAPTOP' OR name = 'Laptop & Máy tính'")
        laptop_cat_row = cursor.fetchone()
        if not laptop_cat_row:
            cursor.execute(
                "INSERT INTO categories (name, code, description) VALUES (?, ?, ?)",
                ("Laptop & Máy tính", "CAT-LAPTOP", "Máy tính xách tay, MacBook, Ultrabook và linh kiện máy tính")
            )
            conn.commit()
            cursor.execute("SELECT id FROM categories WHERE code = 'CAT-LAPTOP'")
            laptop_cat_id = cursor.fetchone()[0]
            print("[DB Migration] Added category 'Laptop & Máy tính' (CAT-LAPTOP).")
        else:
            laptop_cat_id = laptop_cat_row["id"] if isinstance(laptop_cat_row, dict) or hasattr(laptop_cat_row, "keys") else laptop_cat_row[0]

        SEED_MAP = {
            "SP-AUDIO-01": ("RetroSound", "headphone"),
            "SP-AUDIO-02": ("RetroSound", "speaker"),
            "SP-AUDIO-03": ("Monitor Studio", "headphone"),
            "SP-AUDIO-04": ("M1 Audio", "headphone"),
            "SP-AUDIO-05": ("RunFree", "headphone"),
            "SP-OFFICE-01": ("Retro Typewriter", "keyboard"),
            "SP-OFFICE-02": ("Silent M3", "mouse"),
            "SP-OFFICE-03": ("Slim Multi-Device", "keyboard"),
            "SP-OFFICE-04": ("Basic Office", "mouse"),
            "SP-OFFICE-05": ("PU Leather", "mousepad"),
            "SP-SMART-01": ("Edison", "lamp"),
            "SP-SMART-02": ("Ceramic", "diffuser"),
            "SP-SMART-03": ("Nixie", "clock"),
            "SP-SMART-04": ("Smart Scale", "smart_scale"),
            "SP-SMART-05": ("Turbine", "fan"),
            "SP-ACC-01": ("Retro Robot", "charger"),
            "SP-ACC-02": ("Anker", "cable"),
            "SP-ACC-03": ("Orico", "hub_adapter"),
            "SP-ACC-04": ("Cyberpunk", "powerbank"),
            "SP-ACC-05": ("Orico", "stand"),
            "SP-GAME-01": ("G200", "headphone"),
            "SP-GAME-02": ("Ultralight", "mouse"),
            "SP-GAME-03": ("Hall Effect", "gamepad"),
            "SP-GAME-04": ("RGB Pad", "mousepad"),
            "SP-GAME-05": ("CoolerMaster", "cooler"),
        }

        # Populate brand & product_type for existing catalog products if NULL or inaccurate
        cursor.execute("SELECT id, sku, name, description, category_id, brand, product_type FROM products")
        unlabeled = cursor.fetchall()
        for p in unlabeled:
            pid = p["id"] if isinstance(p, dict) or hasattr(p, "keys") else p[0]
            p_sku = (p["sku"] if isinstance(p, dict) or hasattr(p, "keys") else p[1]) or ""
            p_name = (p["name"] if isinstance(p, dict) or hasattr(p, "keys") else p[2]) or ""
            p_desc = (p["description"] if isinstance(p, dict) or hasattr(p, "keys") else p[3]) or ""
            cur_b = p["brand"] if isinstance(p, dict) or hasattr(p, "keys") else p[5]
            cur_pt = p["product_type"] if isinstance(p, dict) or hasattr(p, "keys") else p[6]
            name_desc = f"{p_name} {p_desc}".lower()

            b_val = None
            pt_val = None

            if p_sku in SEED_MAP:
                b_val, pt_val = SEED_MAP[p_sku]
            else:
                if "apple" in name_desc or "macbook" in name_desc:
                    b_val = "Apple"
                elif "sony" in name_desc or "playstation" in name_desc:
                    b_val = "Sony"
                elif "logitech" in name_desc or "logi" in name_desc:
                    b_val = "Logitech"
                elif "razer" in name_desc:
                    b_val = "Razer"
                elif "corsair" in name_desc:
                    b_val = "Corsair"
                elif "keychron" in name_desc:
                    b_val = "Keychron"
                elif "retrosound" in name_desc:
                    b_val = "RetroSound"
                elif "anker" in name_desc:
                    b_val = "Anker"
                elif "asus" in name_desc:
                    b_val = "Asus"

                if any(k in name_desc for k in ["lót chuột", "pad chuột", "bàn di chuột"]):
                    pt_val = "mousepad"
                elif any(k in name_desc for k in ["giá đỡ", "stand", "chân đế", "kê laptop"]):
                    pt_val = "stand"
                elif any(k in name_desc for k in ["tản nhiệt", "cooler", "đế tản nhiệt"]):
                    pt_val = "cooler"
                elif any(k in name_desc for k in ["hub", "chuyển đổi"]):
                    pt_val = "hub_adapter"
                elif any(k in name_desc for k in ["củ sạc", "cốc sạc"]):
                    pt_val = "charger"
                elif any(k in name_desc for k in ["dây cáp", "cáp sạc"]):
                    pt_val = "cable"
                elif any(k in name_desc for k in ["pin dự phòng", "sạc dự phòng", "powerbank"]):
                    pt_val = "powerbank"
                elif any(k in name_desc for k in ["macbook", "máy tính xách tay"]) or ("laptop" in p_name.lower()):
                    pt_val = "laptop"
                elif any(k in name_desc for k in ["chuột", "mouse"]):
                    pt_val = "mouse"
                elif any(k in name_desc for k in ["bàn phím", "keyboard", "phím cơ"]):
                    pt_val = "keyboard"
                elif any(k in name_desc for k in ["tai nghe", "headphone", "earbuds", "micro"]):
                    pt_val = "headphone"
                elif any(k in name_desc for k in ["loa", "speaker"]):
                    pt_val = "speaker"
                elif any(k in name_desc for k in ["tay cầm", "gamepad"]):
                    pt_val = "gamepad"

            updates = []
            params = []
            if b_val and not cur_b:
                updates.append("brand = ?")
                params.append(b_val)
            if pt_val and (not cur_pt or (p_sku == "SP-ACC-01" and cur_pt == "laptop")):
                updates.append("product_type = ?")
                params.append(pt_val)
            if pt_val == "laptop" and laptop_cat_id:
                updates.append("category_id = ?")
                params.append(laptop_cat_id)

            if updates:
                params.append(pid)
                cursor.execute(f"UPDATE products SET {', '.join(updates)} WHERE id = ?", params)
        conn.commit()

        # Migration kiểm tra cột payment_status trong bảng orders
        cursor.execute("PRAGMA table_info(orders)")
        order_cols = [row["name"] for row in cursor.fetchall()]
        if "payment_status" not in order_cols:
            cursor.execute("ALTER TABLE orders ADD COLUMN payment_status TEXT NOT NULL DEFAULT 'completed'")
            conn.commit()
            print("[DB Migration] Added column 'payment_status' to orders table.")

        # PHASE 13A: Migration các cột workflow cho bảng orders nếu chưa có
        cursor.execute("PRAGMA table_info(orders)")
        order_cols = [row["name"] for row in cursor.fetchall()]
        new_order_cols = {
            "approved_by": "INTEGER REFERENCES users(id) ON DELETE SET NULL",
            "approved_at": "TIMESTAMP",
            "processed_by": "INTEGER REFERENCES users(id) ON DELETE SET NULL",
            "processed_at": "TIMESTAMP",
            "rejected_by": "INTEGER REFERENCES users(id) ON DELETE SET NULL",
            "rejected_at": "TIMESTAMP",
            "rejection_reason": "TEXT",
        }
        for col_name, col_def in new_order_cols.items():
            if col_name not in order_cols:
                cursor.execute(f"ALTER TABLE orders ADD COLUMN {col_name} {col_def}")
                conn.commit()
                print(f"[DB Migration] Added column '{col_name}' to orders table.")

        # PHASE 13A: Nâng cấp ràng buộc CHECK(status) của bảng orders để hỗ trợ workflow đa bước
        cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='orders'")
        orders_sql_row = cursor.fetchone()
        if orders_sql_row and "('completed', 'cancelled')" in orders_sql_row["sql"]:
            print("[DB Migration] Upgrading orders table CHECK constraint to multi-state workflow...")
            conn.execute("PRAGMA foreign_keys = OFF")
            conn.execute("BEGIN TRANSACTION")
            
            cursor.execute("PRAGMA table_info(orders)")
            existing_cols = [r["name"] for r in cursor.fetchall()]
            cols_str = ", ".join(existing_cols)
            
            conn.execute("""
            CREATE TABLE orders_workflow_migrated (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_code TEXT UNIQUE NOT NULL,
                customer_id INTEGER REFERENCES customers(id) ON DELETE SET NULL,
                user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
                total_amount REAL NOT NULL DEFAULT 0,
                discount_amount REAL NOT NULL DEFAULT 0,
                final_amount REAL NOT NULL DEFAULT 0,
                payment_method TEXT NOT NULL DEFAULT 'cash' CHECK(payment_method IN ('cash', 'transfer', 'card')),
                payment_status TEXT NOT NULL DEFAULT 'completed' CHECK(payment_status IN ('pending', 'paid', 'completed')),
                status TEXT NOT NULL DEFAULT 'completed' CHECK(status IN ('pending', 'confirmed', 'admin_approved', 'processing', 'completed', 'rejected', 'cancelled')),
                note TEXT,
                approved_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
                approved_at TIMESTAMP,
                processed_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
                processed_at TIMESTAMP,
                rejected_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
                rejected_at TIMESTAMP,
                rejection_reason TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """)
            
            conn.execute(f"INSERT INTO orders_workflow_migrated ({cols_str}) SELECT {cols_str} FROM orders")
            conn.execute("DROP TABLE orders")
            conn.execute("ALTER TABLE orders_workflow_migrated RENAME TO orders")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_orders_code ON orders(order_code)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_orders_created ON orders(created_at)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status)")
            conn.execute("COMMIT")
            conn.execute("PRAGMA foreign_keys = ON")
            print("[DB Migration] Upgraded orders table CHECK constraint successfully.")

        # PHASE R2A: Khởi tạo bảng quản lý phiên bản migration (schema_version)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS schema_version (
            version INTEGER PRIMARY KEY,
            description TEXT NOT NULL,
            applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            checksum TEXT
        );
        """)
        conn.commit()

        # Đánh dấu phiên bản cơ sở (Baseline version 1) nếu chưa có
        cursor.execute("SELECT version FROM schema_version WHERE version = 1")
        if not cursor.fetchone():
            cursor.execute(
                "INSERT INTO schema_version (version, description, checksum) VALUES (1, 'R2A: Initial schema versioning baseline', 'r2a-baseline-v1')"
            )
            conn.commit()
            print("[DB Migration] Initialized schema version 1 (R2A baseline).")

        # PHASE R2B: Migration Version 2 - Phased Column Expansion cho orders
        if not is_version_applied(conn, 2):
            apply_migration_step(
                conn,
                version=2,
                description="R2B: Phased column expansion for orders and legacy unverified marking",
                migration_callable=run_migration_v2_r2b,
                checksum="r2b-column-expansion-v2"
            )
            conn.commit()
            print("[DB Migration] Applied schema version 2 (R2B column expansion).")

        # PHASE R2C: Migration Version 3 - Chạy khi có ENABLE_MIGRATION_V3=1 hoặc trong môi trường test
        if os.environ.get("ENABLE_MIGRATION_V3") == "1" or os.environ.get("APP_ENV") == "testing":
            if not is_version_applied(conn, 3):
                apply_migration_v3_explicit(conn)
                print("[DB Migration] Applied schema version 3 (R2C payment & fulfillment status).")

    print("[DB] Database schema initialized successfully.")

def run_migration_v2_r2b(conn) -> None:
    """
    PHASE R2B: Bổ sung an toàn các cột mới cho bảng orders và đánh dấu đơn hàng lịch sử.
    Quy tắc an toàn:
    - Snapshot tập ID đơn hàng thực tế tồn tại tại thời điểm migration (không dùng COUNT hay id <= 317).
    - Bổ sung các cột nếu chưa có:
        + assigned_to INTEGER REFERENCES users(id)
        + shipping_name TEXT
        + shipping_phone TEXT
        + shipping_address TEXT
        + is_legacy_unverified INTEGER NOT NULL DEFAULT 0
    - Đánh dấu is_legacy_unverified = 1 cho đúng tập ID lịch sử đã snapshot.
    - Tuyệt đối không sửa payment_status.
    - Tuyệt đối không xóa hay rebuild bảng orders.
    """
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(orders);")
    current_cols = [r["name"] if isinstance(r, dict) or hasattr(r, "keys") else r[1] for r in cursor.fetchall()]

    # 1. Snapshot chính xác tập ID các đơn hàng hiện hữu tại thời điểm migration
    cursor.execute("SELECT id FROM orders;")
    legacy_ids = [r[0] for r in cursor.fetchall()]

    # 2. Bổ sung các cột nếu chưa có
    columns_to_add = [
        ("assigned_to", "INTEGER REFERENCES users(id)"),
        ("shipping_name", "TEXT"),
        ("shipping_phone", "TEXT"),
        ("shipping_address", "TEXT"),
        ("is_legacy_unverified", "INTEGER NOT NULL DEFAULT 0"),
    ]
    for col_name, col_def in columns_to_add:
        if col_name not in current_cols:
            conn.execute(f"ALTER TABLE orders ADD COLUMN {col_name} {col_def};")

    # 3. Đánh dấu is_legacy_unverified = 1 cho chính xác tập đơn hàng lịch sử đã snapshot
    if legacy_ids:
        batch_size = 500
        for i in range(0, len(legacy_ids), batch_size):
            batch = legacy_ids[i:i + batch_size]
            placeholders = ",".join("?" for _ in batch)
            conn.execute(
                f"UPDATE orders SET is_legacy_unverified = 1 WHERE id IN ({placeholders});",
                batch
            )

def run_migration_v3_r2c(conn: sqlite3.Connection, old_seq: int | None = None) -> None:
    """
    PHASE R2C: 12-step rebuild an toàn cho bảng orders với enum trạng thái thanh toán và giao vận mới.
    Quy tắc an toàn:
    - Bảo toàn 317 đơn lịch sử: 232 completed + 73 paid -> unverified_legacy (305 đơn); 12 pending -> unpaid.
    - Giữ nguyên toàn bộ giá trị payment_status lịch sử sang payment_status_raw (232 completed, 73 paid, 12 pending).
    - Toàn bộ 317 đơn lịch sử có fulfillment_status = 'legacy_unknown'.
    - Không sửa đổi orders.status, tổng tiền, chiết khấu, ID hay liên kết dữ liệu.
    - Bảo tồn AUTOINCREMENT / sqlite_sequence.
    - Tái tạo toàn bộ Index và Unique Constraints.
    """
    cursor = conn.cursor()
    target_seq: int | None = old_seq
    if target_seq is None:
        seq_row = cursor.execute("SELECT seq FROM sqlite_sequence WHERE name = 'orders'").fetchone()
        if seq_row is not None:
            raw_seq = seq_row["seq"] if isinstance(seq_row, dict) or hasattr(seq_row, "keys") else seq_row[0]
            if raw_seq is not None:
                target_seq = int(raw_seq)

    conn.execute("""
    CREATE TABLE orders_new (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_code TEXT UNIQUE NOT NULL,
        customer_id INTEGER REFERENCES customers(id) ON DELETE SET NULL,
        user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
        total_amount REAL NOT NULL DEFAULT 0,
        discount_amount REAL NOT NULL DEFAULT 0,
        final_amount REAL NOT NULL DEFAULT 0,
        payment_method TEXT NOT NULL DEFAULT 'cash' CHECK(payment_method IN ('cash', 'transfer', 'card')),
        payment_status TEXT NOT NULL DEFAULT 'unpaid' CHECK(payment_status IN ('unpaid', 'pending_verification', 'paid', 'refund_pending', 'refunded', 'unverified_legacy')),
        payment_status_raw TEXT NOT NULL DEFAULT 'unpaid',
        fulfillment_status TEXT NOT NULL DEFAULT 'unfulfilled' CHECK(fulfillment_status IN ('unfulfilled', 'packing', 'shipping', 'delivered', 'delivery_failed', 'returned_to_inventory', 'legacy_unknown')),
        status TEXT NOT NULL DEFAULT 'completed' CHECK(status IN ('pending', 'confirmed', 'admin_approved', 'processing', 'completed', 'rejected', 'cancelled')),
        note TEXT,
        approved_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
        approved_at TIMESTAMP,
        processed_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
        processed_at TIMESTAMP,
        rejected_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
        rejected_at TIMESTAMP,
        rejection_reason TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        assigned_to INTEGER REFERENCES users(id),
        shipping_name TEXT,
        shipping_phone TEXT,
        shipping_address TEXT,
        is_legacy_unverified INTEGER NOT NULL DEFAULT 0
    );
    """)

    conn.execute("""
    INSERT INTO orders_new (
        id, order_code, customer_id, user_id, total_amount, discount_amount, final_amount,
        payment_method, payment_status, payment_status_raw, fulfillment_status, status,
        note, approved_by, approved_at, processed_by, processed_at, rejected_by, rejected_at,
        rejection_reason, created_at, assigned_to, shipping_name, shipping_phone,
        shipping_address, is_legacy_unverified
    )
    SELECT
        id, order_code, customer_id, user_id, total_amount, discount_amount, final_amount,
        payment_method,
        CASE
            WHEN is_legacy_unverified = 1 AND payment_status IN ('completed', 'paid') THEN 'unverified_legacy'
            WHEN is_legacy_unverified = 1 AND payment_status IN ('pending', 'unpaid') THEN 'unpaid'
            WHEN payment_status = 'completed' THEN 'paid'
            WHEN payment_status IN ('pending', 'unpaid') THEN 'unpaid'
            ELSE payment_status
        END AS payment_status,
        COALESCE(payment_status, 'unknown') AS payment_status_raw,
        CASE
            WHEN is_legacy_unverified = 1 THEN 'legacy_unknown'
            WHEN status = 'completed' THEN 'delivered'
            ELSE 'unfulfilled'
        END AS fulfillment_status,
        status,
        note, approved_by, approved_at, processed_by, processed_at, rejected_by, rejected_at,
        rejection_reason, created_at, assigned_to, shipping_name, shipping_phone,
        shipping_address, is_legacy_unverified
    FROM orders;
    """)

    conn.execute("DROP TABLE orders;")
    conn.execute("ALTER TABLE orders_new RENAME TO orders;")

    if target_seq is not None:
        if cursor.execute("SELECT 1 FROM sqlite_sequence WHERE name = 'orders'").fetchone():
            cursor.execute("UPDATE sqlite_sequence SET seq = ? WHERE name = 'orders'", (target_seq,))
        else:
            cursor.execute("INSERT INTO sqlite_sequence (name, seq) VALUES ('orders', ?)", (target_seq,))

    conn.execute("CREATE INDEX IF NOT EXISTS idx_orders_code ON orders(order_code);")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_orders_created ON orders(created_at);")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status);")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_orders_customer_id ON orders(customer_id);")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_orders_user_id ON orders(user_id);")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_orders_payment_status ON orders(payment_status);")

def apply_migration_v3_explicit(conn: sqlite3.Connection) -> bool:
    """
    Chạy tường minh Migration Version 3 (chỉ khi được gọi rõ ràng).
    Quy tắc an toàn:
    - Idempotent: Nếu version 3 đã áp dụng thì bỏ qua (return False).
    - PRAGMA foreign_keys = OFF được thực thi ngoài transaction.
    - Chạy run_migration_v3_r2c trong BEGIN IMMEDIATE transaction.
    - Nếu thành công: Ghi nhận version 3 vào schema_version và commit.
    - Nếu thất bại: Rollback toàn bộ, ném exception.
    - Bắt buộc bật lại PRAGMA foreign_keys = ON trong khối finally:.
    """
    if is_version_applied(conn, 3):
        return False

    cursor = conn.cursor()
    fk_check = cursor.execute("PRAGMA foreign_key_check;").fetchall()
    if fk_check:
        raise RuntimeError(f"[Migration V3] Khóa ngoại trước migration vi phạm: {fk_check}")

    seq_row = cursor.execute("SELECT seq FROM sqlite_sequence WHERE name = 'orders'").fetchone()
    old_seq: int | None = None
    if seq_row is not None:
        raw_val = seq_row["seq"] if isinstance(seq_row, dict) or hasattr(seq_row, "keys") else seq_row[0]
        if raw_val is not None:
            old_seq = int(raw_val)

    conn.execute("PRAGMA foreign_keys = OFF;")
    try:
        conn.execute("BEGIN IMMEDIATE;")
        run_migration_v3_r2c(conn, old_seq=old_seq)
        record_migration(
            conn,
            version=3,
            description="R2C: Payment & fulfillment status migration with legacy preservation",
            checksum="r2c-payment-fulfillment-v3"
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.execute("PRAGMA foreign_keys = ON;")

    post_fk = cursor.execute("PRAGMA foreign_key_check;").fetchall()
    if post_fk:
        raise RuntimeError(f"[Migration V3] Khóa ngoại sau migration vi phạm: {post_fk}")

    return True

def get_applied_versions(conn: sqlite3.Connection) -> list[int]:
    """Lấy danh sách các phiên bản migration đã áp dụng theo thứ tự tăng dần"""
    cursor = conn.cursor()
    cursor.execute("SELECT version FROM schema_version ORDER BY version ASC")
    return [int(row["version"] if isinstance(row, dict) or hasattr(row, "keys") else row[0]) for row in cursor.fetchall()]

def is_version_applied(conn: sqlite3.Connection, version: int) -> bool:
    """Kiểm tra xem một phiên bản migration cụ thể đã được áp dụng hay chưa"""
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM schema_version WHERE version = ?", (version,))
    return cursor.fetchone() is not None

def record_migration(conn: sqlite3.Connection, version: int, description: str, checksum: str | None = None) -> None:
    """Ghi nhận một phiên bản migration đã hoàn thành vào schema_version"""
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO schema_version (version, description, checksum) VALUES (?, ?, ?)",
        (version, description, checksum)
    )

def apply_migration_step(conn: sqlite3.Connection, version: int, description: str, migration_callable: Callable[[sqlite3.Connection], Any], checksum: str | None = None) -> bool:
    """
    Thực thi an toàn một bước migration:
    - Kiểm tra Idempotency: Nếu version đã chạy thì bỏ qua (return False).
    - Chạy migration_callable(conn).
    - Nếu thành công: Ghi nhận vào schema_version và return True.
    - Nếu thất bại: Ném exception để transaction ngoài rollback toàn bộ. Không ghi nhận version.
    """
    if is_version_applied(conn, version):
        return False

    migration_callable(conn)
    record_migration(conn, version, description, checksum)
    return True

if __name__ == "__main__":
    init_db()

