import React, { useState, useEffect } from 'react';
import {
  TrendingUp,
  DollarSign,
  ShoppingCart,
  AlertTriangle,
  Download,
  FileSpreadsheet,
  FileText,
  Calendar,
  Layers,
  ArrowRight,
} from 'lucide-react';
import { reportsAPI, inventoryAPI } from '../services/api';
import { useToast } from '../context/ToastContext';
import { RetroChart } from '../components/ui/RetroChart';
import { StockBadge, Badge } from '../components/ui/Badge';

export const DashboardPage = ({ onNavigate }) => {
  const { addToast } = useToast();

  const [summary, setSummary] = useState(null);
  const [revenueTrend, setRevenueTrend] = useState([]);
  const [trendDays, setTrendDays] = useState(7);
  const [topProducts, setTopProducts] = useState([]);
  const [lowStockList, setLowStockList] = useState([]);
  const [loading, setLoading] = useState(true);
  const [exporting, setExporting] = useState(false);

  const loadDashboard = async () => {
    try {
      setLoading(true);
      const [sumData, trendData, topData, alerts] = await Promise.all([
        reportsAPI.getSummary(),
        reportsAPI.getRevenueTrend(trendDays),
        reportsAPI.getTopProducts(5),
        inventoryAPI.getLowStockAlerts(),
      ]);
      setSummary(sumData);
      setRevenueTrend(trendData);
      setTopProducts(topData);
      setLowStockList(alerts);
    } catch (err) {
      addToast(err.message, 'error');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadDashboard();
  }, [trendDays]);

  const handleExportCSV = async () => {
    setExporting(true);
    try {
      const blob = await reportsAPI.exportCSV();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `danh_sach_hoa_don_${new Date().toISOString().slice(0, 10)}.csv`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
      addToast('Tải file báo cáo CSV thành công!', 'success');
    } catch (err) {
      addToast(err.message || 'Lỗi xuất file CSV', 'error');
    } finally {
      setExporting(false);
    }
  };

  const handleExportExcel = async () => {
    setExporting(true);
    try {
      const blob = await reportsAPI.exportExcel();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `danh_sach_hoa_don_${new Date().toISOString().slice(0, 10)}.xlsx`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
      addToast('Tải file báo cáo Excel (.xlsx) thành công!', 'success');
    } catch (err) {
      addToast(err.message || 'Lỗi xuất file Excel', 'error');
    } finally {
      setExporting(false);
    }
  };

  const formatVND = (val) => Number(val || 0).toLocaleString('vi-VN') + ' đ';

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
      {/* Top Action Bar */}
      <div className="retro-card">
        <div className="retro-card-header">
          <div className="retro-card-title">
            <TrendingUp size={18} />
            <span>TRUNG TÂM ĐIỀU HÀNH & BÁO CÁO DOANH THU THỰC TẾ</span>
          </div>

          <div style={{ display: 'flex', gap: '0.5rem' }}>
            <button
              onClick={handleExportCSV}
              disabled={exporting}
              className="btn btn-outline btn-sm"
              title="Tải danh sách đơn hàng CSV"
            >
              <FileText size={14} /> Xuất CSV
            </button>
            <button
              onClick={handleExportExcel}
              disabled={exporting}
              className="btn btn-primary btn-sm"
              title="Tải danh sách hóa đơn Excel"
            >
              <FileSpreadsheet size={14} /> Xuất Excel (.xlsx)
            </button>
          </div>
        </div>
      </div>

      {/* KPI METRIC CARDS */}
      <div className="kpi-grid">
        {/* KPI 1: Doanh thu hôm nay */}
        <div className="kpi-card kpi-amber">
          <div className="kpi-icon-box">
            <DollarSign size={24} />
          </div>
          <div className="kpi-info">
            <span className="kpi-label">Doanh Thu Hôm Nay</span>
            <span className="kpi-value">{formatVND(summary?.today_revenue)}</span>
            <span className="kpi-sub">
              {summary?.today_orders || 0} đơn hàng hôm nay
            </span>
          </div>
        </div>

        {/* KPI 2: Doanh thu tháng này */}
        <div className="kpi-card kpi-green">
          <div className="kpi-icon-box">
            <TrendingUp size={24} />
          </div>
          <div className="kpi-info">
            <span className="kpi-label">Doanh Thu Tháng Này</span>
            <span className="kpi-value">{formatVND(summary?.month_revenue)}</span>
            <span className="kpi-sub">
              Tuần này: {formatVND(summary?.week_revenue)} ({summary?.completed_orders || 0} đơn hoàn tất)
            </span>
          </div>
        </div>

        {/* KPI 3: Doanh thu thực nhận */}
        <div className="kpi-card kpi-blue">
          <div className="kpi-icon-box">
            <ShoppingCart size={24} />
          </div>
          <div className="kpi-info">
            <span className="kpi-label">Thực Thu Đã Xác Minh</span>
            <span className="kpi-value">{formatVND(summary?.verified_payment_revenue)}</span>
            <span className="kpi-sub">
              Tổng đơn: {summary?.total_orders || 0} ({summary?.completed_orders || 0} hoàn thành)
            </span>
          </div>
        </div>

        {/* KPI 4: Cảnh báo tồn kho */}
        <div className="kpi-card kpi-red">
          <div className="kpi-icon-box">
            <AlertTriangle size={24} />
          </div>
          <div className="kpi-info">
            <span className="kpi-label">Cảnh Báo Tồn Kho</span>
            <span className="kpi-value" style={{ color: 'var(--red-light)' }}>
              {summary?.low_stock_count || 0}
            </span>
            <span className="kpi-sub">
              Mặt hàng chạm ngưỡng cảnh báo
            </span>
          </div>
        </div>
      </div>

      {/* FINANCIAL DATA AUDIT & DISTINCTION BANNER */}
      <div
        className="retro-card"
        style={{
          borderLeft: '4px solid var(--amber-primary)',
          background: 'var(--bg-card)',
        }}
      >
        <div style={{ padding: '0.85rem 1.25rem', display: 'flex', flexWrap: 'wrap', justifyContent: 'space-between', alignItems: 'center', gap: '1rem' }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontWeight: 700, fontSize: '0.88rem', color: 'var(--amber-primary)', fontFamily: 'var(--font-mono)' }}>
              <span>⚖️ ĐỐI SOÁT TÀI CHÍNH & DOANH THU THỰC TẾ</span>
            </div>
            <div style={{ fontSize: '0.78rem', color: 'var(--text-secondary)', marginTop: '0.25rem' }}>
              Bóc tách rõ ràng giữa tiền mặt/ngân hàng thực nhận và doanh số 317 đơn lịch sử chưa qua đối soát sao kê.
            </div>
          </div>

          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.75rem', alignItems: 'center' }}>
            <div style={{ padding: '0.45rem 0.85rem', background: 'var(--bg-input)', border: '1px solid var(--border-subtle)', borderRadius: 'var(--radius-xs)' }}>
              <div style={{ fontSize: '0.68rem', color: 'var(--green-light)', fontWeight: 600 }}>THỰC NHẬN ĐÃ ĐỐI SOÁT (PAID)</div>
              <div style={{ fontSize: '1rem', fontWeight: 700, color: 'var(--green-terminal)', fontFamily: 'var(--font-mono)' }}>
                {formatVND(summary?.verified_payment_revenue)}
              </div>
            </div>

            <div style={{ padding: '0.45rem 0.85rem', background: 'var(--bg-input)', border: '1px solid var(--border-subtle)', borderRadius: 'var(--radius-xs)' }}>
              <div style={{ fontSize: '0.68rem', color: 'var(--text-muted)', fontWeight: 600 }}>LỊCH SỬ CHƯA ĐỐI SOÁT (LEGACY)</div>
              <div style={{ fontSize: '1rem', fontWeight: 700, color: 'var(--text-secondary)', fontFamily: 'var(--font-mono)' }}>
                {formatVND(summary?.legacy_unverified_revenue)}
              </div>
            </div>

            <div style={{ padding: '0.45rem 0.85rem', background: 'var(--bg-input)', border: '1px solid var(--border-subtle)', borderRadius: 'var(--radius-xs)' }}>
              <div style={{ fontSize: '0.68rem', color: 'var(--amber-light)', fontWeight: 600 }}>TỔNG GHI NHẬN SỔ SÁCH</div>
              <div style={{ fontSize: '1rem', fontWeight: 700, color: 'var(--amber-primary)', fontFamily: 'var(--font-mono)' }}>
                {formatVND(summary?.total_revenue)}
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* REVENUE TREND CHART */}
      <div className="retro-card">
        <div className="retro-card-header">
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontWeight: 700, color: 'var(--green-terminal)', fontFamily: 'var(--font-mono)' }}>
            <Calendar size={16} />
            <span>BIỂU ĐỒ BIẾN ĐỘNG DOANH THU THỰC TẾ (SQL DATA)</span>
          </div>

          <div style={{ display: 'flex', gap: '0.35rem' }}>
            <button
              onClick={() => setTrendDays(7)}
              className={`btn btn-sm ${trendDays === 7 ? 'btn-primary' : 'btn-outline'}`}
            >
              7 Ngày
            </button>
            <button
              onClick={() => setTrendDays(14)}
              className={`btn btn-sm ${trendDays === 14 ? 'btn-primary' : 'btn-outline'}`}
            >
              14 Ngày
            </button>
            <button
              onClick={() => setTrendDays(30)}
              className={`btn btn-sm ${trendDays === 30 ? 'btn-primary' : 'btn-outline'}`}
            >
              30 Ngày
            </button>
          </div>
        </div>

        <div className="retro-card-body" style={{ padding: '1rem' }}>
          <RetroChart data={revenueTrend} height={260} />
        </div>
      </div>

      {/* TWO COLUMNS: TOP SELLING PRODUCTS & LOW STOCK ALERTS */}
      <div className="dashboard-two-col-grid">
        {/* Column 1: Top Selling Products */}
        <div className="retro-card">
          <div className="retro-card-header">
            <span className="retro-card-title">
              <Layers size={16} /> TOP 5 MẶT HÀNG BÁN CHẠY NHẤT
            </span>
          </div>
          <div className="table-responsive" style={{ border: 'none' }}>
            <table className="retro-table">
              <thead>
                <tr>
                  <th>SẢN PHẨM</th>
                  <th style={{ textAlign: 'center' }}>ĐÃ BÁN</th>
                  <th style={{ textAlign: 'right' }}>DOANH THU</th>
                </tr>
              </thead>
              <tbody>
                {topProducts.length === 0 ? (
                  <tr>
                    <td colSpan={3} style={{ textAlign: 'center', padding: '1.5rem', color: 'var(--text-muted)' }}>
                      Chưa có dữ liệu bán hàng.
                    </td>
                  </tr>
                ) : (
                  topProducts.map((p, idx) => (
                    <tr key={p.product_id}>
                      <td>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                          <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--amber-primary)', fontWeight: 800 }}>
                            #{idx + 1}
                          </span>
                          <div>
                            <div style={{ fontWeight: 600 }}>{p.name || p.product_name}</div>
                            <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
                              {(p.sku || p.product_sku) ? `${p.sku || p.product_sku}` : ''}{p.category_name ? ` | ${p.category_name}` : ''}
                            </div>
                          </div>
                        </div>
                      </td>
                      <td style={{ textAlign: 'center', fontFamily: 'var(--font-mono)', fontWeight: 700, color: 'var(--green-light)' }}>
                        {p.total_quantity_sold}
                      </td>
                      <td className="currency" style={{ textAlign: 'right', fontWeight: 700, color: 'var(--amber-light)' }}>
                        {formatVND(p.total_revenue)}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>

        {/* Column 2: Low Stock List */}
        <div className="retro-card">
          <div className="retro-card-header">
            <span className="retro-card-title" style={{ color: 'var(--red-light)' }}>
              <AlertTriangle size={16} /> DANH SÁCH CẦN NHẬP KHO GẤP
            </span>
            {onNavigate && (
              <button
                onClick={() => onNavigate('purchases')}
                className="btn btn-outline btn-sm"
                style={{ borderColor: 'var(--border-subtle)', fontSize: '0.72rem' }}
              >
                Nhập kho ngay <ArrowRight size={12} />
              </button>
            )}
          </div>
          <div className="table-responsive" style={{ border: 'none' }}>
            <table className="retro-table">
              <thead>
                <tr>
                  <th>MẶT HÀNG</th>
                  <th style={{ textAlign: 'center' }}>TỒN HIỆN TẠI</th>
                  <th style={{ textAlign: 'center' }}>NGƯỠNG BÁO</th>
                </tr>
              </thead>
              <tbody>
                {lowStockList.length === 0 ? (
                  <tr>
                    <td colSpan={3} style={{ textAlign: 'center', padding: '1.5rem', color: 'var(--green-light)' }}>
                      Tất cả các mặt hàng đều ở mức an toàn!
                    </td>
                  </tr>
                ) : (
                  lowStockList.map((item) => (
                    <tr key={item.id}>
                      <td>
                        <div style={{ fontWeight: 600 }}>{item.name}</div>
                        <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
                          {item.sku}
                        </div>
                      </td>
                      <td style={{ textAlign: 'center' }}>
                        <StockBadge stock={item.stock_quantity} minAlert={item.min_stock_alert} />
                      </td>
                      <td style={{ textAlign: 'center', fontFamily: 'var(--font-mono)', color: 'var(--text-secondary)' }}>
                        {item.min_stock_alert}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
};
