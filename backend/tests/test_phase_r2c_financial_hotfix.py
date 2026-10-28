import os
import shutil
import sqlite3
import pytest
from app.services.report_service import ReportService
from app.services.ai_service import ai_service
from app.schemas.report import DashboardSummaryResponse

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
MAIN_DB_PATH = os.path.join(BACKEND_DIR, "webstore.db")

@pytest.fixture
def isolated_v3_test_db(tmp_path, monkeypatch):
    """Tạo bản clone v3 cách ly hoàn toàn từ webstore.db chính"""
    test_db_file = tmp_path / "webstore_hotfix_test.db"
    shutil.copy2(MAIN_DB_PATH, test_db_file)
    test_db_str = str(test_db_file)
    monkeypatch.setenv("DATABASE_PATH", test_db_str)
    from app.core import config
    monkeypatch.setattr(config.settings, "DATABASE_PATH", test_db_str)
    return test_db_str

def test_01_snapshot_financial_metrics_exact_match(isolated_v3_test_db):
    """
    Kiểm tra 4 chỉ số tài chính cốt lõi trên snapshot v3:
    - total_revenue: 316,063,000 đ
    - legacy_unverified_revenue: 316,063,000 đ
    - verified_payment_revenue: 0 đ
    - Tổng giá trị đơn unverified_legacy (bao gồm hủy/chờ): 449,194,000 đ
    """
    summary = ReportService.get_dashboard_summary()
    assert summary["total_revenue"] == 316063000.0, f"Expected 316,063,000, got {summary['total_revenue']}"
    assert summary["legacy_unverified_revenue"] == 316063000.0, f"Expected 316,063,000, got {summary['legacy_unverified_revenue']}"
    assert summary["verified_payment_revenue"] == 0.0, f"Expected 0.0, got {summary['verified_payment_revenue']}"

    # Kiểm tra trực tiếp qua SQL: tổng giá trị gộp của 305 đơn unverified_legacy vẫn là 449,194,000 đ
    conn = sqlite3.connect(isolated_v3_test_db)
    cursor = conn.cursor()
    cursor.execute("SELECT COALESCE(SUM(final_amount), 0) FROM orders WHERE payment_status = 'unverified_legacy'")
    total_unverified_orders_value = float(cursor.fetchone()[0])
    assert total_unverified_orders_value == 449194000.0
    conn.close()

def test_02_only_completed_unverified_legacy_is_included(isolated_v3_test_db):
    """
    Kiểm tra độc lập từng trạng thái:
    1. Đơn completed + unverified_legacy được tính vào legacy_unverified_revenue
    2. Đơn cancelled + unverified_legacy KHÔNG được tính (58,745,000 đ bị loại bỏ)
    3. Đơn rejected + unverified_legacy KHÔNG được tính (13,735,000 đ bị loại bỏ)
    4. Đơn pending + unverified_legacy KHÔNG được tính (49,656,000 đ bị loại bỏ)
    5. Đơn processing/admin_approved + unverified_legacy KHÔNG được tính (10,995,000 đ bị loại bỏ)
    """
    conn = sqlite3.connect(isolated_v3_test_db)
    cursor = conn.cursor()

    # Thống kê trực tiếp theo từng status của đơn unverified_legacy
    cursor.execute("""
        SELECT status, COALESCE(SUM(final_amount), 0) as amt, COUNT(*) as cnt
        FROM orders
        WHERE payment_status = 'unverified_legacy'
        GROUP BY status
    """)
    breakdown = {r[0]: (float(r[1]), r[2]) for r in cursor.fetchall()}
    conn.close()

    assert breakdown["completed"][0] == 316063000.0
    assert breakdown["completed"][1] == 140
    assert breakdown["cancelled"][0] == 58745000.0
    assert breakdown["cancelled"][1] == 81
    assert breakdown["rejected"][0] == 13735000.0
    assert breakdown["rejected"][1] == 15
    assert breakdown["pending"][0] == 49656000.0
    assert breakdown["pending"][1] == 43
    assert breakdown["processing"][0] == 5325000.0
    assert breakdown["processing"][1] == 13
    assert breakdown["admin_approved"][0] == 5670000.0
    assert breakdown["admin_approved"][1] == 13

    # Tổng loại trừ: 58,745,000 + 13,735,000 + 49,656,000 + 5,325,000 + 5,670,000 = 133,131,000 đ
    excluded_amount = sum(v[0] for k, v in breakdown.items() if k != "completed")
    assert excluded_amount == 133131000.0

    # legacy_unverified_revenue CHỈ lấy đúng completed
    summary = ReportService.get_dashboard_summary()
    assert summary["legacy_unverified_revenue"] == breakdown["completed"][0]

def test_03_verified_payment_revenue_tracks_paid_orders(isolated_v3_test_db):
    """
    Kiểm tra verified_payment_revenue:
    - Khi có đơn mới mang payment_status = 'paid', verified_payment_revenue tăng tương ứng
    - Không làm sai lệch legacy_unverified_revenue
    """
    conn = sqlite3.connect(isolated_v3_test_db)
    cursor = conn.cursor()
    # Thêm một đơn mới có payment_status = 'paid' và status = 'completed'
    cursor.execute("""
        INSERT INTO orders (
            order_code, total_amount, discount_amount, final_amount,
            payment_method, payment_status, payment_status_raw, fulfillment_status,
            status, is_legacy_unverified
        ) VALUES (
            'ORD-TEST-PAID-001', 500000, 0, 500000,
            'cash', 'paid', 'paid', 'delivered',
            'completed', 0
        )
    """)
    conn.commit()
    conn.close()

    summary = ReportService.get_dashboard_summary()
    assert summary["verified_payment_revenue"] == 500000.0
    # legacy_unverified_revenue vẫn giữ nguyên 316,063,000 đ
    assert summary["legacy_unverified_revenue"] == 316063000.0
    # total_revenue tăng lên 316,563,000 đ (do thêm 1 đơn completed)
    assert summary["total_revenue"] == 316563000.0

def test_04_dashboard_summary_schema_response(isolated_v3_test_db):
    """Kiểm tra Pydantic schema DashboardSummaryResponse trả về đúng trường legacy_unverified_revenue"""
    summary = ReportService.get_dashboard_summary()
    resp = DashboardSummaryResponse(**summary)
    assert resp.total_revenue == 316063000.0
    assert resp.legacy_unverified_revenue == 316063000.0
    assert resp.verified_payment_revenue == 0.0

def test_05_ai_service_context_labels(isolated_v3_test_db, monkeypatch):
    """Kiểm tra prompt context của AI Service sử dụng nhãn chuẩn 'Doanh số đơn hoàn thành chưa đối soát'"""
    captured_context = []

    def mock_gemini(prompt):
        captured_context.append(prompt)
        return "Báo cáo thử nghiệm hoàn tất."

    monkeypatch.setattr(ai_service, "_call_gemini", mock_gemini)

    res = ai_service.generate_sales_report(period="today")
    assert len(captured_context) == 1
    prompt_text = captured_context[0]

    # Kiểm tra nhãn trong prompt AI
    assert "Doanh số đơn hoàn thành chưa đối soát: 316,063,000 VNĐ" in prompt_text
    assert "Tuyệt đối không diễn giải doanh số đơn hoàn thành chưa đối soát" in prompt_text
    assert "Doanh thu lịch sử chưa đối soát" not in prompt_text
