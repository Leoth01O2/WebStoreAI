import pytest
from fastapi.testclient import TestClient
from app.main import app
from seed_data import seed_database

@pytest.fixture(scope="session", autouse=True)
def setup_test_database():
    """Khởi tạo và nạp dữ liệu mẫu trước khi chạy test suite"""
    seed_database()

client = TestClient(app)

def test_health_check():
    """Kiểm tra health endpoint hoạt động"""
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["database"] == "sqlite_wal_active"

def test_login_success_all_roles():
    """Kiểm tra đăng nhập thành công cho cả 4 vai trò: SuperAdmin, Admin, Staff, Customer"""
    test_accounts = [
        ("superadmin", "SuperAdmin@123", "superadmin"),
        ("admin", "Admin@123", "admin"),
        ("staff", "Staff@123", "staff"),
        ("customer", "Customer@123", "customer"),
    ]
    for username, password, expected_role in test_accounts:
        response = client.post("/api/v1/auth/login", json={"username": username, "password": password})
        assert response.status_code == 200, f"Đăng nhập thất bại cho user {username}"
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert data["user"]["role"] == expected_role
        assert data["user"]["username"] == username

def test_manager_role_rejected():
    """Kiểm tra role manager không còn tồn tại và không thể tạo mới user với role manager"""
    import uuid
    login_res = client.post("/api/v1/auth/login", json={"username": "admin", "password": "Admin@123"})
    admin_token = login_res.json()["access_token"]
    
    invalid_payload = {
        "username": f"legacy_mgr_{uuid.uuid4().hex[:6]}",
        "password": "Password123",
        "full_name": "Legacy Manager",
        "role": "manager"
    }
    response = client.post(
        "/api/v1/auth/users",
        json=invalid_payload,
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    # RoleEnum in Pydantic v2 returns 422 Unprocessable Entity for invalid role
    assert response.status_code == 422

def test_login_invalid_password():
    """Kiểm tra đăng nhập sai mật khẩu trả về 401 Unauthorized"""
    response = client.post("/api/v1/auth/login", json={"username": "admin", "password": "WrongPassword"})
    assert response.status_code == 401
    assert "detail" in response.json()

def test_get_current_user_profile():
    """Kiểm tra lấy thông tin cá nhân qua endpoint /me với token hợp lệ"""
    # 1. Đăng nhập lấy token
    login_res = client.post("/api/v1/auth/login", json={"username": "staff", "password": "Staff@123"})
    token = login_res.json()["access_token"]

    # 2. Gọi /me
    response = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    user = response.json()
    assert user["username"] == "staff"
    assert user["role"] == "staff"
    assert user["is_active"] is True

def test_rbac_staff_cannot_create_user():
    """Kiểm tra phân quyền: Staff gọi endpoint dành cho Admin -> nhận 403 Forbidden"""
    # Đăng nhập bằng tài khoản Staff
    login_res = client.post("/api/v1/auth/login", json={"username": "staff", "password": "Staff@123"})
    staff_token = login_res.json()["access_token"]

    # Staff cố gắng tạo user mới
    new_user_payload = {
        "username": "hacker",
        "password": "Password123",
        "full_name": "Unauthorized User",
        "role": "admin"
    }
    response = client.post(
        "/api/v1/auth/users",
        json=new_user_payload,
        headers={"Authorization": f"Bearer {staff_token}"}
    )
    assert response.status_code == 403
    assert "Quyền truy cập bị từ chối" in response.json()["detail"]

def test_rbac_admin_can_create_user():
    """Kiểm tra phân quyền: Admin gọi endpoint tạo user mới -> thành công 200"""
    import uuid
    # Đăng nhập bằng tài khoản Admin
    login_res = client.post("/api/v1/auth/login", json={"username": "admin", "password": "Admin@123"})
    admin_token = login_res.json()["access_token"]

    new_username = f"cashier_{uuid.uuid4().hex[:6]}"
    new_user_payload = {
        "username": new_username,
        "password": "Password123",
        "full_name": "Nhân Viên Mới 01",
        "role": "staff"
    }
    response = client.post(
        "/api/v1/auth/users",
        json=new_user_payload,
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert response.status_code == 200
    created = response.json()
    assert created["username"] == new_username
    assert created["role"] == "staff"

    # Xác minh đăng nhập được với tài khoản vừa tạo
    verify_login = client.post("/api/v1/auth/login", json={"username": new_username, "password": "Password123"})
    assert verify_login.status_code == 200


def test_customer2_invalid_passwords_strictly_rejected():
    """
    Regression Test:
    Bảo đảm tài khoản customer2 chỉ đăng nhập được với mật khẩu hợp lệ (Customer@123)
    và bị từ chối 401 tuyệt đối với bất kỳ mật khẩu nào khác (kể cả Customer2@123 hay mật khẩu sai).
    """
    # 1. Thử mật khẩu sai Customer2@123 -> Phải bị từ chối 401
    res_bad = client.post("/api/v1/auth/login", json={"username": "customer2", "password": "Customer2@123"})
    assert res_bad.status_code == 401
    assert "Tên đăng nhập hoặc mật khẩu không chính xác" in res_bad.json()["detail"]

    # 2. Thử mật khẩu sai ngẫu nhiên -> Phải bị từ chối 401
    res_random = client.post("/api/v1/auth/login", json={"username": "customer2", "password": "RandomInvalidPassword!@#"})
    assert res_random.status_code == 401

    # 3. Mật khẩu chuẩn trong seed_data (Customer@123) -> Phải thành công 200
    res_ok = client.post("/api/v1/auth/login", json={"username": "customer2", "password": "Customer@123"})
    assert res_ok.status_code == 200
    data = res_ok.json()
    assert "access_token" in data
    assert data["user"]["username"] == "customer2"
    assert data["user"]["role"] == "customer"