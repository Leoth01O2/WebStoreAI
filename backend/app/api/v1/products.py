import os
import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, status
from app.core.database import get_db, get_db_transaction
from app.core.rbac import get_current_user, require_roles
from app.schemas.category import CategoryCreate, CategoryUpdate, CategoryResponse
from app.schemas.product import ProductCreate, ProductUpdate, ProductResponse, ProductPublicResponse
from app.services.rag_service import rag_service
from app.services.visual_index_service import visual_index_service

router = APIRouter(tags=["Products & Categories"])

UPLOADS_PRODUCTS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))), "uploads", "products")
os.makedirs(UPLOADS_PRODUCTS_DIR, exist_ok=True)

# ==================== PUBLIC ENDPOINTS (GUEST & STOREFRONT) ====================

@router.get("/public/categories", response_model=List[CategoryResponse])
def get_public_categories():
    """Lấy danh mục hàng hóa công khai cho Khách vãng lai (Guest) và Khách hàng (Customer)"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, code, description, created_at FROM categories ORDER BY name ASC")
        rows = cursor.fetchall()
        return [dict(r) for r in rows]

@router.get("/public/products", response_model=List[ProductPublicResponse])
def get_public_products(
    search: Optional[str] = Query(None, description="Tìm theo tên hoặc mã SKU"),
    category_id: Optional[int] = Query(None, description="Lọc theo ID nhóm hàng"),
    min_price: Optional[float] = Query(None, description="Giá bán tối thiểu"),
    max_price: Optional[float] = Query(None, description="Giá bán tối đa"),
    in_stock_only: bool = Query(False, description="Chỉ lấy sản phẩm còn hàng"),
):
    """
    Danh sách sản phẩm công khai dành cho Guest và Storefront.
    - CHỈ trả về sản phẩm đang kinh doanh (status = 'active')
    - KHÔNG lộ giá vốn (cost_price) hay thông tin nhạy cảm/nội bộ
    """
    with get_db() as conn:
        cursor = conn.cursor()
        query = """
            SELECT p.id, p.sku, p.name, p.category_id, c.name as category_name,
                   p.selling_price, p.stock_quantity,
                   p.unit, p.status, p.image_url, p.description
            FROM products p
            LEFT JOIN categories c ON p.category_id = c.id
            WHERE p.status = 'active'
        """
        params = []

        if search:
            query += " AND (p.name LIKE ? OR p.sku LIKE ? OR p.description LIKE ?)"
            s_param = f"%{search.strip()}%"
            params.extend([s_param, s_param, s_param])

        if category_id is not None:
            query += " AND p.category_id = ?"
            params.append(category_id)

        if min_price is not None:
            query += " AND p.selling_price >= ?"
            params.append(min_price)

        if max_price is not None:
            query += " AND p.selling_price <= ?"
            params.append(max_price)

        if in_stock_only:
            query += " AND p.stock_quantity > 0"

        query += " ORDER BY p.id DESC"
        cursor.execute(query, params)
        rows = cursor.fetchall()
        results = []
        for r in rows:
            d = dict(r)
            d["in_stock"] = d.get("stock_quantity", 0) > 0
            results.append(d)
        return results

@router.get("/public/products/{product_id}", response_model=ProductPublicResponse)
def get_public_product_detail(product_id: int):
    """Xem chi tiết sản phẩm công khai (status = 'active', không lộ giá vốn)"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """SELECT p.id, p.sku, p.name, p.category_id, c.name as category_name,
                      p.selling_price, p.stock_quantity,
                      p.unit, p.status, p.image_url, p.description
               FROM products p
               LEFT JOIN categories c ON p.category_id = c.id
               WHERE p.id = ? AND p.status = 'active'""",
            (product_id,)
        )
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Không tìm thấy sản phẩm hoặc sản phẩm đã ngừng bán")
        d = dict(row)
        d["in_stock"] = d.get("stock_quantity", 0) > 0
        return d

# ==================== CATEGORIES ====================


@router.get("/categories", response_model=List[CategoryResponse])
def get_categories(current_user: dict = Depends(get_current_user)):
    """Lấy danh sách tất cả các danh mục hàng hóa (Tất cả vai trò)"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, code, description, created_at FROM categories ORDER BY name ASC")
        rows = cursor.fetchall()
        return [dict(r) for r in rows]

@router.post("/categories", response_model=CategoryResponse, dependencies=[Depends(require_roles("admin", "superadmin"))])
def create_category(category_in: CategoryCreate, current_user: dict = Depends(get_current_user)):
    """Tạo mới danh mục (Admin, Manager)"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM categories WHERE code = ?", (category_in.code,))
        if cursor.fetchone():
            raise HTTPException(status_code=400, detail=f"Mã danh mục '{category_in.code}' đã tồn tại")

        cursor.execute(
            "INSERT INTO categories (name, code, description) VALUES (?, ?, ?)",
            (category_in.name, category_in.code, category_in.description)
        )
        new_id = cursor.lastrowid
        conn.commit()

        cursor.execute("SELECT id, name, code, description, created_at FROM categories WHERE id = ?", (new_id,))
        return dict(cursor.fetchone())

@router.put("/categories/{category_id}", response_model=CategoryResponse, dependencies=[Depends(require_roles("admin", "superadmin"))])
def update_category(category_id: int, category_in: CategoryUpdate, current_user: dict = Depends(get_current_user)):
    """Cập nhật danh mục (Admin, Manager)"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM categories WHERE id = ?", (category_id,))
        cat = cursor.fetchone()
        if not cat:
            raise HTTPException(status_code=404, detail="Không tìm thấy danh mục")

        updates = []
        params = []
        if category_in.name is not None:
            updates.append("name = ?")
            params.append(category_in.name)
        if category_in.code is not None:
            # Kiểm tra trùng code
            cursor.execute("SELECT id FROM categories WHERE code = ? AND id != ?", (category_in.code, category_id))
            if cursor.fetchone():
                raise HTTPException(status_code=400, detail="Mã danh mục đã được sử dụng")
            updates.append("code = ?")
            params.append(category_in.code)
        if category_in.description is not None:
            updates.append("description = ?")
            params.append(category_in.description)

        if updates:
            params.append(category_id)
            cursor.execute(f"UPDATE categories SET {', '.join(updates)} WHERE id = ?", params)
            conn.commit()

        cursor.execute("SELECT id, name, code, description, created_at FROM categories WHERE id = ?", (category_id,))
        return dict(cursor.fetchone())

@router.delete("/categories/{category_id}", dependencies=[Depends(require_roles("admin", "superadmin"))])
def delete_category(category_id: int, current_user: dict = Depends(get_current_user)):
    """Xóa danh mục (Admin, Manager)"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM categories WHERE id = ?", (category_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Không tìm thấy danh mục")

        cursor.execute("DELETE FROM categories WHERE id = ?", (category_id,))
        conn.commit()
        return {"message": "Đã xóa danh mục thành công"}

# ==================== PRODUCTS ====================

@router.post("/products/upload-image", dependencies=[Depends(require_roles("admin", "superadmin"))])
async def upload_product_image(
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user)
):
    """Upload ảnh sản phẩm lên server nội bộ (Admin, Manager)"""
    allowed_types = ["image/jpeg", "image/png", "image/webp", "image/gif"]
    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Định dạng không hợp lệ. Chỉ chấp nhận file ảnh JPEG, PNG, WebP hoặc GIF"
        )

    contents = await file.read()
    if len(contents) > 5 * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Dung lượng file ảnh vượt quá 5MB"
        )

    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in [".jpg", ".jpeg", ".png", ".webp", ".gif"]:
        ext = ".png" if file.content_type == "image/png" else ".jpg"

    unique_filename = f"prod_{uuid.uuid4().hex[:12]}{ext}"
    target_path = os.path.join(UPLOADS_PRODUCTS_DIR, unique_filename)

    with open(target_path, "wb") as f:
        f.write(contents)

    return {"image_url": f"/uploads/products/{unique_filename}"}

@router.get("/products", response_model=List[ProductResponse])
def get_products(
    search: Optional[str] = Query(None, description="Tìm theo tên hoặc mã SKU"),
    category_id: Optional[int] = Query(None, description="Lọc theo ID nhóm hàng"),
    status: Optional[str] = Query(None, description="Lọc theo trạng thái: active, inactive"),
    min_price: Optional[float] = Query(None, description="Giá bán tối thiểu"),
    max_price: Optional[float] = Query(None, description="Giá bán tối đa"),
    low_stock_only: bool = Query(False, description="Chỉ lấy sản phẩm sắp hết hàng"),
    in_stock_only: bool = Query(False, description="Chỉ lấy sản phẩm còn hàng trong kho"),
    current_user: dict = Depends(get_current_user)
):
    """
    Danh sách sản phẩm có tìm kiếm, lọc đa tiêu chí (Tất cả vai trò: Admin, Staff, Manager)
    """
    with get_db() as conn:
        cursor = conn.cursor()
        query = """
            SELECT p.id, p.sku, p.name, p.category_id, c.name as category_name,
                   p.cost_price, p.selling_price, p.stock_quantity, p.min_stock_alert,
                   p.unit, p.status, p.image_url, p.description, p.created_at, p.updated_at
            FROM products p
            LEFT JOIN categories c ON p.category_id = c.id
            WHERE 1=1
        """
        params = []

        if search:
            query += " AND (p.name LIKE ? OR p.sku LIKE ? OR p.description LIKE ?)"
            s_param = f"%{search.strip()}%"
            params.extend([s_param, s_param, s_param])

        if category_id is not None:
            query += " AND p.category_id = ?"
            params.append(category_id)

        if status:
            query += " AND p.status = ?"
            params.append(status)

        if min_price is not None:
            query += " AND p.selling_price >= ?"
            params.append(min_price)

        if max_price is not None:
            query += " AND p.selling_price <= ?"
            params.append(max_price)

        if low_stock_only:
            query += " AND p.stock_quantity <= p.min_stock_alert AND p.status = 'active'"

        if in_stock_only:
            query += " AND p.stock_quantity > 0 AND p.status = 'active'"

        query += " ORDER BY p.id DESC"
        cursor.execute(query, params)
        rows = cursor.fetchall()
        return [dict(r) for r in rows]

@router.get("/products/{product_id}", response_model=ProductResponse)
def get_product_detail(product_id: int, current_user: dict = Depends(get_current_user)):
    """Xem chi tiết thông tin một sản phẩm"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """SELECT p.id, p.sku, p.name, p.category_id, c.name as category_name,
                      p.cost_price, p.selling_price, p.stock_quantity, p.min_stock_alert,
                      p.unit, p.status, p.image_url, p.description, p.created_at, p.updated_at
               FROM products p
               LEFT JOIN categories c ON p.category_id = c.id
               WHERE p.id = ?""",
            (product_id,)
        )
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Không tìm thấy sản phẩm")
        return dict(row)

@router.post("/products", response_model=ProductResponse, dependencies=[Depends(require_roles("admin", "superadmin"))])
def create_product(product_in: ProductCreate, current_user: dict = Depends(get_current_user)):
    """Tạo sản phẩm mới (Admin, Manager)"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM products WHERE sku = ?", (product_in.sku,))
        if cursor.fetchone():
            raise HTTPException(status_code=400, detail=f"Mã SKU '{product_in.sku}' đã tồn tại")

        cursor.execute(
            """INSERT INTO products (
                sku, name, category_id, cost_price, selling_price,
                stock_quantity, min_stock_alert, unit, status, image_url, description
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                product_in.sku, product_in.name, product_in.category_id,
                product_in.cost_price, product_in.selling_price, product_in.stock_quantity,
                product_in.min_stock_alert, product_in.unit, product_in.status,
                product_in.image_url, product_in.description
            )
        )
        new_id = cursor.lastrowid
        conn.commit()

        # Đồng bộ vector sang ChromaDB
        try:
            if new_id is not None:
                rag_service.upsert_single_product(new_id)
                visual_index_service.sync_single_product_visual(new_id)
        except Exception:
            pass

        cursor.execute(
            """SELECT p.id, p.sku, p.name, p.category_id, c.name as category_name,
                      p.cost_price, p.selling_price, p.stock_quantity, p.min_stock_alert,
                      p.unit, p.status, p.image_url, p.description, p.created_at, p.updated_at
               FROM products p
               LEFT JOIN categories c ON p.category_id = c.id
               WHERE p.id = ?""",
            (new_id,)
        )
        return dict(cursor.fetchone())

@router.put("/products/{product_id}", response_model=ProductResponse, dependencies=[Depends(require_roles("admin", "superadmin"))])
def update_product(product_id: int, product_in: ProductUpdate, current_user: dict = Depends(get_current_user)):
    """Cập nhật thông tin sản phẩm (Admin, Manager)"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM products WHERE id = ?", (product_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Không tìm thấy sản phẩm")

        updates = []
        params = []
        for field, value in product_in.model_dump(exclude_unset=True).items():
            if field == "sku":
                cursor.execute("SELECT id FROM products WHERE sku = ? AND id != ?", (value, product_id))
                if cursor.fetchone():
                    raise HTTPException(status_code=400, detail=f"Mã SKU '{value}' đã được sử dụng")
            updates.append(f"{field} = ?")
            params.append(value)

        if updates:
            updates.append("updated_at = CURRENT_TIMESTAMP")
            params.append(product_id)
            cursor.execute(f"UPDATE products SET {', '.join(updates)} WHERE id = ?", params)
            conn.commit()

            # Đồng bộ vector sang ChromaDB
            try:
                rag_service.upsert_single_product(product_id)
                visual_index_service.sync_single_product_visual(product_id)
            except Exception:
                pass

        cursor.execute(
            """SELECT p.id, p.sku, p.name, p.category_id, c.name as category_name,
                      p.cost_price, p.selling_price, p.stock_quantity, p.min_stock_alert,
                      p.unit, p.status, p.image_url, p.description, p.created_at, p.updated_at
               FROM products p
               LEFT JOIN categories c ON p.category_id = c.id
               WHERE p.id = ?""",
            (product_id,)
        )
        return dict(cursor.fetchone())

@router.delete("/products/{product_id}", dependencies=[Depends(require_roles("admin", "superadmin"))])
def delete_product(
    product_id: int,
    hard_delete: bool = Query(False, description="Xóa cứng (bỏ qua lịch sử hóa đơn)"),
    current_user: dict = Depends(get_current_user)
):
    """
    Xóa sản phẩm (Admin, Manager).
    - Mặc định (hard_delete=false): Nếu đã có hóa đơn liên quan thì chuyển status='inactive' (soft delete).
    - hard_delete=true: Xóa vĩnh viễn bất kể lịch sử (dùng cho admin dọn dẹp dữ liệu).
    """
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM products WHERE id = ?", (product_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Không tìm thấy sản phẩm")

        if hard_delete:
            if current_user.get("role") != "superadmin":
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Chỉ SuperAdmin mới có quyền xóa cứng (hard delete) sản phẩm vĩnh viễn"
                )
            # Hard delete: xóa vĩnh viễn — KHÔNG reassign FK (dùng khi dọn duplicate)
            # order_items.product_id có thể trở thành dangling; cân nhắc dùng script cleanup thay thế.
            cursor.execute("DELETE FROM products WHERE id = ?", (product_id,))
            conn.commit()
            try:
                rag_service.delete_single_product(product_id)
                visual_index_service.delete_single_product_visual(product_id)
            except Exception:
                pass
            return {"message": "Đã xóa cứng sản phẩm vĩnh viễn (hard delete)"}

        # Soft delete mặc định: kiểm tra hóa đơn
        cursor.execute("SELECT id FROM order_items WHERE product_id = ? LIMIT 1", (product_id,))
        if cursor.fetchone():
            cursor.execute("UPDATE products SET status = 'inactive', updated_at = CURRENT_TIMESTAMP WHERE id = ?", (product_id,))
            conn.commit()
            try:
                rag_service.upsert_single_product(product_id)
                visual_index_service.sync_single_product_visual(product_id)
            except Exception:
                pass
            return {"message": "Sản phẩm đã có lịch sử bán hàng nên được chuyển sang trạng thái ngừng kinh doanh (inactive)"}

        cursor.execute("DELETE FROM products WHERE id = ?", (product_id,))
        conn.commit()
        try:
            rag_service.delete_single_product(product_id)
            visual_index_service.delete_single_product_visual(product_id)
        except Exception:
            pass
        return {"message": "Đã xóa sản phẩm vĩnh viễn"}

