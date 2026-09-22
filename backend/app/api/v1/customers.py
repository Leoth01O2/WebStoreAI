from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from app.core.database import get_db
from app.core.rbac import get_current_user, require_roles, get_customer_id_for_user
from app.schemas.customer import CustomerCreate, CustomerUpdate, CustomerResponse

router = APIRouter(prefix="/customers", tags=["Customers"])

@router.get("", response_model=List[CustomerResponse], dependencies=[Depends(require_roles("staff", "admin", "superadmin"))])
def get_customers(
    search: Optional[str] = Query(None, description="Tìm theo tên hoặc số điện thoại"),
    group_name: Optional[str] = Query(None, description="Lọc theo nhóm khách hàng: retail, vip, wholesale"),
    current_user: dict = Depends(get_current_user)
):
    """
    Lấy danh sách khách hàng (Chỉ dành cho Staff, Admin, SuperAdmin).
    Customer không được phép xem danh sách khách hàng khác (403 Forbidden).
    """
    with get_db() as conn:
        cursor = conn.cursor()
        query = "SELECT id, user_id, customer_code, name, phone, email, address, group_name, total_spent, created_at FROM customers WHERE 1=1"
        params = []

        if search:
            query += " AND (name LIKE ? OR phone LIKE ? OR customer_code LIKE ?)"
            s_param = f"%{search.strip()}%"
            params.extend([s_param, s_param, s_param])

        if group_name:
            query += " AND group_name = ?"
            params.append(group_name)

        query += " ORDER BY total_spent DESC, id DESC"
        cursor.execute(query, params)
        rows = cursor.fetchall()
        return [dict(r) for r in rows]

@router.get("/me", response_model=CustomerResponse)
def get_my_customer_profile(current_user: dict = Depends(get_current_user)):
    """
    Lấy thông tin hồ sơ khách hàng của tài khoản đang đăng nhập.
    Nếu chưa có, tự động tạo một hồ sơ khách hàng gắn với tài khoản này.
    """
    with get_db() as conn:
        cursor = conn.cursor()
        own_id = get_customer_id_for_user(conn, current_user)
        if not own_id:
            # Tự động tạo hồ sơ khách hàng cho tài khoản nếu chưa có
            code = f"CUS-{current_user['id']:04d}"
            cursor.execute(
                """INSERT INTO customers (user_id, customer_code, name, phone, email, address, group_name, total_spent)
                   VALUES (?, ?, ?, ?, ?, ?, 'retail', 0.0)""",
                (current_user["id"], code, current_user.get("full_name") or current_user["username"], "", "", "")
            )
            own_id = cursor.lastrowid
            conn.commit()

        cursor.execute(
            "SELECT id, user_id, customer_code, name, phone, email, address, group_name, total_spent, created_at FROM customers WHERE id = ?",
            (own_id,)
        )
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Không tìm thấy hồ sơ khách hàng")
        return dict(row)

@router.get("/{customer_id}", response_model=CustomerResponse)
def get_customer_detail(customer_id: int, current_user: dict = Depends(get_current_user)):
    """
    Xem chi tiết thông tin khách hàng:
    - Staff / Admin / SuperAdmin: được xem bất kỳ khách hàng nào.
    - Customer: CHỈ được xem thông tin của chính mình. Truy cập ID của người khác -> 403 Forbidden (Chống IDOR).
    """
    with get_db() as conn:
        cursor = conn.cursor()

        # Kiểm tra IDOR nếu user là Customer
        if current_user.get("role") == "customer":
            own_customer_id = get_customer_id_for_user(conn, current_user)
            if not own_customer_id or own_customer_id != customer_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Bạn không có quyền truy cập thông tin của khách hàng khác"
                )

        cursor.execute(
            "SELECT id, user_id, customer_code, name, phone, email, address, group_name, total_spent, created_at FROM customers WHERE id = ?",
            (customer_id,)
        )
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Không tìm thấy khách hàng")
        return dict(row)

@router.post("", response_model=CustomerResponse, dependencies=[Depends(require_roles("staff", "admin", "superadmin"))])
def create_customer(customer_in: CustomerCreate, current_user: dict = Depends(get_current_user)):
    """Tạo khách hàng mới (Chỉ dành cho Staff, Admin, SuperAdmin)"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM customers WHERE customer_code = ?", (customer_in.customer_code,))
        if cursor.fetchone():
            raise HTTPException(status_code=400, detail=f"Mã khách hàng '{customer_in.customer_code}' đã tồn tại")

        cursor.execute(
            """INSERT INTO customers (customer_code, name, phone, email, address, group_name, total_spent)
               VALUES (?, ?, ?, ?, ?, ?, 0.0)""",
            (
                customer_in.customer_code, customer_in.name, customer_in.phone,
                customer_in.email, customer_in.address, customer_in.group_name
            )
        )
        new_id = cursor.lastrowid
        conn.commit()

        cursor.execute(
            "SELECT id, user_id, customer_code, name, phone, email, address, group_name, total_spent, created_at FROM customers WHERE id = ?",
            (new_id,)
        )
        return dict(cursor.fetchone())

@router.put("/{customer_id}", response_model=CustomerResponse)
def update_customer(customer_id: int, customer_in: CustomerUpdate, current_user: dict = Depends(get_current_user)):
    """
    Cập nhật thông tin khách hàng:
    - Staff / Admin / SuperAdmin: có thể sửa thông tin khách hàng.
    - Customer: CHỈ sửa thông tin của chính mình (Chống IDOR -> 403). Không được đổi group_name hay customer_code.
    """
    with get_db() as conn:
        cursor = conn.cursor()

        # Kiểm tra IDOR nếu role là Customer
        if current_user.get("role") == "customer":
            own_customer_id = get_customer_id_for_user(conn, current_user)
            if not own_customer_id or own_customer_id != customer_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Bạn không có quyền sửa thông tin của khách hàng khác"
                )

        cursor.execute("SELECT * FROM customers WHERE id = ?", (customer_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Không tìm thấy khách hàng")

        updates = []
        params = []
        update_data = customer_in.model_dump(exclude_unset=True)

        # Nếu là Customer, không cho phép thay đổi group_name hoặc customer_code
        if current_user.get("role") == "customer":
            update_data.pop("group_name", None)
            update_data.pop("customer_code", None)

        for field, value in update_data.items():
            if field == "customer_code":
                cursor.execute("SELECT id FROM customers WHERE customer_code = ? AND id != ?", (value, customer_id))
                if cursor.fetchone():
                    raise HTTPException(status_code=400, detail="Mã khách hàng đã được sử dụng")
            updates.append(f"{field} = ?")
            params.append(value)

        if updates:
            params.append(customer_id)
            cursor.execute(f"UPDATE customers SET {', '.join(updates)} WHERE id = ?", params)
            conn.commit()

        cursor.execute(
            "SELECT id, user_id, customer_code, name, phone, email, address, group_name, total_spent, created_at FROM customers WHERE id = ?",
            (customer_id,)
        )
        return dict(cursor.fetchone())
