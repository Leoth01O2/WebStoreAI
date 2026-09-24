import React, { useState, useEffect } from 'react';
import {
  FileText,
  Search,
  Eye,
  XCircle,
  Printer,
  Check,
  X,
  PackageCheck,
  CheckCircle2,
  RefreshCw,
} from 'lucide-react';
import { ordersAPI } from '../services/api';
import { useAuth } from '../context/AuthContext';
import { useToast } from '../context/ToastContext';
import { Badge, OrderStatusBadge } from '../components/ui/Badge';
import { Modal } from '../components/ui/Modal';
import { ReceiptModal } from '../components/ui/ReceiptModal';

const OrderLifecycleStepper = ({ status, rejectionReason }) => {
  const steps = [
    { key: 'pending', label: '1. Chờ duyệt', num: 1 },
    { key: 'admin_approved', label: '2. Đã duyệt', num: 2 },
    { key: 'processing', label: '3. Đang xử lý', num: 3 },
    { key: 'completed', label: '4. Hoàn thành', num: 4 },
  ];

  if (status === 'rejected') {
    return (
      <div
        style={{
          padding: '0.85rem 1rem',
          background: 'rgba(239, 68, 68, 0.08)',
          border: '1px solid var(--red-light)',
          borderRadius: 'var(--radius-xs)',
          marginBottom: '1rem',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: 'var(--red-light)', fontWeight: 700, fontSize: '0.85rem' }}>
          <span>❌ ĐƠN HÀNG ĐÃ BỊ TỪ CHỐI</span>
        </div>
        <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', marginTop: '0.35rem' }}>
          <strong>Lý do từ chối:</strong> {rejectionReason || 'Đơn hàng không được duyệt bởi Quản trị viên'}
        </div>
      </div>
    );
  }

  if (status === 'cancelled') {
    return (
      <div
        style={{
          padding: '0.85rem 1rem',
          background: 'rgba(148, 163, 184, 0.08)',
          border: '1px solid var(--border-color)',
          borderRadius: 'var(--radius-xs)',
          marginBottom: '1rem',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: 'var(--text-muted)', fontWeight: 700, fontSize: '0.85rem' }}>
          <span>🚫 ĐƠN HÀNG ĐÃ ĐƯỢC HỦY BỎ</span>
        </div>
        <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginTop: '0.35rem' }}>
          Đơn hàng đã được hủy và toàn bộ tồn kho đã được hoàn trả an toàn.
        </div>
      </div>
    );
  }

  const getStepIndex = (st) => {
    switch (st) {
      case 'pending':
        return 0;
      case 'admin_approved':
        return 1;
      case 'processing':
        return 2;
      case 'completed':
        return 3;
      default:
        return 0;
    }
  };

  const currentIndex = getStepIndex(status);

  return (
    <div
      style={{
        marginBottom: '1.25rem',
        padding: '0.85rem 1rem',
        background: 'var(--bg-input)',
        border: '1px solid var(--border-subtle)',
        borderRadius: 'var(--radius-xs)',
      }}
    >
      <div
        style={{
          fontSize: '0.72rem',
          fontWeight: 700,
          color: 'var(--text-muted)',
          marginBottom: '0.85rem',
          textTransform: 'uppercase',
          letterSpacing: '0.5px',
        }}
      >
        TIẾN TRÌNH VÒNG ĐỜI ĐƠN HÀNG:
      </div>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', position: 'relative' }}>
        {steps.map((step, idx) => {
          const isDone = idx < currentIndex || (idx === 3 && status === 'completed');
          const isActive = idx === currentIndex && status !== 'completed';

          let circleBg = 'var(--bg-surface)';
          let circleColor = 'var(--text-muted)';
          let circleBorder = '1px solid var(--border-subtle)';
          let labelColor = 'var(--text-muted)';
          let labelWeight = 500;

          if (isDone) {
            circleBg = 'var(--green-terminal)';
            circleColor = '#000';
            circleBorder = '1px solid var(--green-terminal)';
            labelColor = 'var(--green-light)';
            labelWeight = 700;
          } else if (isActive) {
            circleBg = 'var(--amber-primary)';
            circleColor = '#000';
            circleBorder = '1px solid var(--amber-primary)';
            labelColor = 'var(--amber-light)';
            labelWeight = 700;
          }

          return (
            <React.Fragment key={step.key}>
              <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', zIndex: 2, flex: 1 }}>
                <div
                  style={{
                    width: '26px',
                    height: '26px',
                    borderRadius: '50%',
                    background: circleBg,
                    color: circleColor,
                    border: circleBorder,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    fontSize: '0.75rem',
                    fontWeight: 800,
                    fontFamily: 'var(--font-mono)',
                    marginBottom: '0.35rem',
                    transition: 'all 0.2s ease',
                  }}
                >
                  {isDone ? '✓' : step.num}
                </div>
                <div
                  style={{
                    fontSize: '0.72rem',
                    color: labelColor,
                    fontWeight: labelWeight,
                    textAlign: 'center',
                    whiteSpace: 'nowrap',
                  }}
                >
                  {step.label}
                </div>
              </div>
              {idx < steps.length - 1 && (
                <div
                  style={{
                    flex: 1,
                    height: '2px',
                    background: idx < currentIndex ? 'var(--green-terminal)' : 'var(--border-subtle)',
                    margin: '0 -4px 1.2rem -4px',
                    zIndex: 1,
                    transition: 'background 0.3s ease',
                  }}
                />
              )}
            </React.Fragment>
          );
        })}
      </div>
    </div>
  );
};

export const OrdersPage = () => {
  const { user, isAdmin, isSuperAdmin, isManager } = useAuth();
  const { addToast } = useToast();
  const isCustomer = user?.role === 'customer';
  const canCancel = isAdmin || isSuperAdmin || isManager;

  const [orders, setOrders] = useState([]);
  const [loading, setLoading] = useState(true);

  // Filters
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');

  // Modals
  const [viewingOrder, setViewingOrder] = useState(null);
  const [receiptOrder, setReceiptOrder] = useState(null);
  const [cancellingOrder, setCancellingOrder] = useState(null);
  const [cancelReason, setCancelReason] = useState('Khách hàng đổi ý / Trả hàng');
  const [submittingCancel, setSubmittingCancel] = useState(false);

  // Customer self-cancel states
  const [customerCancellingOrder, setCustomerCancellingOrder] = useState(null);
  const [customerCancelReason, setCustomerCancelReason] = useState('Khách hàng đổi ý / không còn nhu cầu');
  const [submittingCustomerCancel, setSubmittingCustomerCancel] = useState(false);

  // SuperAdmin Force-Action States
  const [forceActionModal, setForceActionModal] = useState(null);
  const [forceActionReason, setForceActionReason] = useState('');
  const [forceActionTargetStatus, setForceActionTargetStatus] = useState('processing');
  const [submittingForceAction, setSubmittingForceAction] = useState(false);

  // Workflow Real-Time Indicators (Phase 13F)
  const [workflowCounts, setWorkflowCounts] = useState(null);
  const [refreshing, setRefreshing] = useState(false);
  const [rejectingOrder, setRejectingOrder] = useState(null);
  const [rejectReason, setRejectReason] = useState('Đơn hàng bị Admin từ chối');
  const [submittingReject, setSubmittingReject] = useState(false);

  const fetchWorkflowCounts = async () => {
    if (!user) return;
    try {
      const counts = await ordersAPI.getWorkflowCounts();
      setWorkflowCounts(counts);
    } catch {
      // Silently ignore if unauthorized or network error
    }
  };

  const loadOrders = async () => {
    try {
      setLoading(true);
      const data = await ordersAPI.getOrders({
        search: search || undefined,
        status: statusFilter || undefined,
        start_date: startDate || undefined,
        end_date: endDate || undefined,
      });
      setOrders(data);
    } catch (err) {
      addToast(err.message, 'error');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadOrders();
  }, [search, statusFilter, startDate, endDate]);

  // Gentle Polling (30-60s) & Event-driven synchronization
  useEffect(() => {
    fetchWorkflowCounts();

    const handleWorkflowEvent = () => {
      fetchWorkflowCounts();
      loadOrders();
    };

    window.addEventListener('workflow-updated', handleWorkflowEvent);

    const handleFocus = () => {
      if (document.visibilityState === 'visible') {
        fetchWorkflowCounts();
        loadOrders();
      }
    };
    window.addEventListener('focus', handleFocus);

    const interval = setInterval(() => {
      if (document.visibilityState === 'visible') {
        fetchWorkflowCounts();
        loadOrders();
      }
    }, 30000); // 30s gentle polling

    return () => {
      clearInterval(interval);
      window.removeEventListener('workflow-updated', handleWorkflowEvent);
      window.removeEventListener('focus', handleFocus);
    };
  }, [user]);

  const handleManualRefresh = async () => {
    setRefreshing(true);
    try {
      await Promise.all([loadOrders(), fetchWorkflowCounts()]);
      addToast('Đã làm mới dữ liệu đơn hàng thành công!', 'info');
    } catch (err) {
      addToast(err.message || 'Lỗi khi làm mới dữ liệu', 'error');
    } finally {
      setRefreshing(false);
    }
  };

  const handleApproveOrder = async (order) => {
    try {
      await ordersAPI.approveOrder(order.id);
      addToast(`Đã duyệt đơn hàng #${order.order_code} thành công!`, 'success');
      window.dispatchEvent(new CustomEvent('workflow-updated'));
      loadOrders();
      fetchWorkflowCounts();
      if (viewingOrder?.id === order.id) {
        setViewingOrder((prev) => ({ ...prev, status: 'admin_approved' }));
      }
    } catch (err) {
      addToast(err.message || 'Lỗi khi duyệt đơn hàng', 'error');
    }
  };

  const handleRejectOrder = async (e) => {
    e.preventDefault();
    if (!rejectingOrder || !rejectReason.trim()) return;
    setSubmittingReject(true);
    try {
      await ordersAPI.rejectOrder(rejectingOrder.id, rejectReason.trim());
      addToast(`Đã từ chối đơn hàng #${rejectingOrder.order_code}. Tồn kho đã được hoàn trả!`, 'success');
      setRejectingOrder(null);
      setRejectReason('Đơn hàng bị Admin từ chối');
      window.dispatchEvent(new CustomEvent('workflow-updated'));
      loadOrders();
      fetchWorkflowCounts();
      if (viewingOrder?.id === rejectingOrder.id) {
        setViewingOrder((prev) => ({ ...prev, status: 'rejected', rejection_reason: rejectReason.trim() }));
      }
    } catch (err) {
      addToast(err.message || 'Lỗi khi từ chối đơn hàng', 'error');
    } finally {
      setSubmittingReject(false);
    }
  };

  const handleProcessOrder = async (order) => {
    try {
      await ordersAPI.processOrder(order.id);
      addToast(`Đã nhận xử lý đơn hàng #${order.order_code}!`, 'success');
      window.dispatchEvent(new CustomEvent('workflow-updated'));
      loadOrders();
      fetchWorkflowCounts();
      if (viewingOrder?.id === order.id) {
        setViewingOrder((prev) => ({ ...prev, status: 'processing' }));
      }
    } catch (err) {
      addToast(err.message || 'Lỗi khi nhận xử lý đơn hàng', 'error');
    }
  };

  const handleCompleteOrder = async (order) => {
    try {
      await ordersAPI.completeOrder(order.id);
      addToast(`Đơn hàng #${order.order_code} đã hoàn tất thành công! Doanh thu đã được ghi nhận.`, 'success');
      window.dispatchEvent(new CustomEvent('workflow-updated'));
      loadOrders();
      fetchWorkflowCounts();
      if (viewingOrder?.id === order.id) {
        setViewingOrder((prev) => ({ ...prev, status: 'completed' }));
      }
    } catch (err) {
      addToast(err.message || 'Lỗi khi hoàn tất đơn hàng', 'error');
    }
  };

  const handleCancelOrder = async (e) => {
    e.preventDefault();
    if (!cancellingOrder) return;
    setSubmittingCancel(true);
    try {
      await ordersAPI.cancelOrder(cancellingOrder.id, cancelReason);
      addToast(`Đã hủy hóa đơn ${cancellingOrder.order_code} và hoàn trả tồn kho thành công!`, 'success');
      setCancellingOrder(null);
      setViewingOrder(null);
      window.dispatchEvent(new CustomEvent('workflow-updated'));
      loadOrders();
      fetchWorkflowCounts();
    } catch (err) {
      addToast(err.message, 'error');
    } finally {
      setSubmittingCancel(false);
    }
  };

  const handleCustomerCancel = async (e) => {
    e.preventDefault();
    if (!customerCancellingOrder) return;
    setSubmittingCustomerCancel(true);
    try {
      await ordersAPI.customerCancelOrder(customerCancellingOrder.id, customerCancelReason);
      addToast(`Đã hủy đơn hàng ${customerCancellingOrder.order_code} thành công! Tồn kho đã được hoàn trả.`, 'success');
      setCustomerCancellingOrder(null);
      setViewingOrder(null);
      window.dispatchEvent(new CustomEvent('workflow-updated'));
      loadOrders();
      fetchWorkflowCounts();
    } catch (err) {
      addToast(err.message || 'Lỗi khi hủy đơn hàng', 'error');
    } finally {
      setSubmittingCustomerCancel(false);
    }
  };

  const handleSuperAdminForceAction = async (e) => {
    e.preventDefault();
    if (!forceActionModal || !forceActionReason.trim()) return;
    setSubmittingForceAction(true);
    try {
      const payload = {
        action: forceActionModal.action,
        reason: forceActionReason.trim(),
        target_status: forceActionModal.action === 'override_status' ? forceActionTargetStatus : undefined,
      };
      const updated = await ordersAPI.forceAction(forceActionModal.order.id, payload);
      addToast(`Đã thực hiện thao tác ngoại lệ '${forceActionModal.action}' trên đơn ${forceActionModal.order.order_code} thành công!`, 'success');
      setForceActionModal(null);
      setForceActionReason('');
      setViewingOrder(updated);
      window.dispatchEvent(new CustomEvent('workflow-updated'));
      loadOrders();
      fetchWorkflowCounts();
    } catch (err) {
      addToast(err.message || 'Lỗi khi thực hiện thao tác ngoại lệ', 'error');
    } finally {
      setSubmittingForceAction(false);
    }
  };

  const getTabs = () => {
    let pendingCount = 0;
    let approvedCount = 0;
    let processingCount = 0;

    if (isCustomer) {
      pendingCount = workflowCounts?.my_pending_count || 0;
      processingCount = workflowCounts?.my_processing_count || 0;
    } else if (user?.role === 'staff') {
      approvedCount = workflowCounts?.approved_count || 0;
      processingCount = workflowCounts?.processing_count || 0;
    } else {
      // admin, superadmin, manager
      pendingCount = workflowCounts?.pending_count || 0;
      approvedCount = workflowCounts?.approved_count || 0;
      processingCount = workflowCounts?.processing_count || 0;
    }

    return [
      { id: '', label: 'Tất cả' },
      { id: 'pending', label: 'Chờ duyệt', count: pendingCount, color: 'var(--amber-primary)' },
      { id: 'admin_approved', label: 'Đã duyệt', count: approvedCount, color: 'var(--green-terminal)' },
      { id: 'processing', label: 'Đang xử lý', count: processingCount, color: 'var(--blue-light)' },
      { id: 'completed', label: 'Hoàn thành' },
      { id: 'cancelled,rejected', label: 'Đã hủy / Từ chối' },
    ];
  };

  const formatVND = (val) => Number(val || 0).toLocaleString('vi-VN') + ' đ';

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
      {/* Filters bar */}
      <div className="retro-card">
        <div className="retro-card-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '0.5rem' }}>
          <div className="retro-card-title">
            <FileText size={18} />
            <span>{isCustomer ? `ĐƠN HÀNG CỦA TÔI (${orders.length} ĐƠN)` : `QUẢN LÝ HÓA ĐƠN BÁN HÀNG (${orders.length} ĐƠN)`}</span>
          </div>
          <button
            className="btn btn-outline btn-sm"
            onClick={handleManualRefresh}
            disabled={refreshing || loading}
            style={{ display: 'inline-flex', alignItems: 'center', gap: '0.4rem', fontSize: '0.78rem' }}
            title="Làm mới dữ liệu đơn hàng"
          >
            <RefreshCw size={13} className={refreshing || loading ? 'spin-animation' : ''} />
            <span>{refreshing ? 'Đang cập nhật...' : 'Làm mới dữ liệu'}</span>
          </button>
        </div>

        {/* Status Tabs (Phase 13F) */}
        <div style={{ padding: '0.75rem 1.25rem', borderBottom: '1px solid var(--border-subtle)', background: 'var(--bg-surface)' }}>
          <div style={{ display: 'flex', gap: '0.4rem', flexWrap: 'wrap', alignItems: 'center' }}>
            {getTabs().map((tab) => {
              const isActive = statusFilter === tab.id;
              return (
                <button
                  key={tab.id || 'all'}
                  onClick={() => setStatusFilter(tab.id)}
                  className={`btn btn-sm ${isActive ? 'btn-primary' : 'btn-outline'}`}
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: '0.45rem',
                    padding: '0.35rem 0.75rem',
                    fontSize: '0.78rem',
                    borderColor: isActive ? 'var(--green-terminal)' : 'var(--border-subtle)',
                  }}
                >
                  <span>{tab.label}</span>
                  {tab.count !== undefined && tab.count > 0 && (
                    <span
                      style={{
                        padding: '0.05rem 0.4rem',
                        borderRadius: '999px',
                        fontSize: '0.68rem',
                        fontWeight: 800,
                        fontFamily: 'var(--font-mono)',
                        background: isActive ? '#000' : 'var(--bg-input)',
                        color: isActive ? 'var(--green-terminal)' : (tab.color || 'var(--text-primary)'),
                        border: `1px solid ${tab.color || 'var(--border-subtle)'}`,
                      }}
                    >
                      {tab.count}
                    </span>
                  )}
                </button>
              );
            })}
          </div>
        </div>

        <div style={{ padding: '0.85rem 1.25rem', display: 'flex', flexWrap: 'wrap', gap: '0.75rem', alignItems: 'center', background: 'var(--bg-input)' }}>
          <div className="input-with-icon" style={{ minWidth: 'min(100%, 200px)', flex: '1 1 200px' }}>
            <Search size={15} />
            <input
              type="text"
              className="form-control font-mono"
              placeholder="Tìm mã đơn, tên hoặc SĐT khách..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </div>

          <select
            className="form-control"
            style={{ flex: '1 1 140px', minWidth: '120px' }}
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
          >
            <option value="">-- Tất cả trạng thái --</option>
            <option value="pending">Chờ duyệt</option>
            <option value="admin_approved">Đã duyệt</option>
            <option value="processing">Đang xử lý</option>
            <option value="completed">Hoàn thành</option>
            <option value="rejected">Đã từ chối</option>
            <option value="cancelled">Đã hủy</option>
          </select>

          <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem', flex: '1 1 130px' }}>
            <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', whiteSpace: 'nowrap' }}>Từ ngày:</span>
            <input
              type="date"
              className="form-control font-mono"
              style={{ width: '100%', minWidth: '110px', padding: '0.35rem' }}
              value={startDate}
              onChange={(e) => setStartDate(e.target.value)}
            />
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem', flex: '1 1 130px' }}>
            <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', whiteSpace: 'nowrap' }}>Đến ngày:</span>
            <input
              type="date"
              className="form-control font-mono"
              style={{ width: '100%', minWidth: '110px', padding: '0.35rem' }}
              value={endDate}
              onChange={(e) => setEndDate(e.target.value)}
            />
          </div>

          {(search || statusFilter || startDate || endDate) && (
            <button
              className="btn btn-outline btn-sm"
              onClick={() => {
                setSearch('');
                setStatusFilter('');
                setStartDate('');
                setEndDate('');
              }}
            >
              Đặt lại
            </button>
          )}
        </div>
      </div>

      {/* Desktop Orders Table */}
      <div className="table-responsive orders-desktop-view">
        <table className="retro-table">
          <thead>
            <tr>
              <th>MÃ HÓA ĐƠN</th>
              <th>THỜI GIAN</th>
              <th>KHÁCH HÀNG</th>
              <th>NGƯỜI BÁN</th>
              <th>HÌNH THỨC</th>
              <th style={{ textAlign: 'right' }}>TỔNG TIỀN</th>
              <th style={{ textAlign: 'center' }}>TRẠNG THÁI</th>
              <th style={{ textAlign: 'center' }}>THAO TÁC</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan={8} style={{ textAlign: 'center', padding: '2rem' }}>
                  Đang tải danh sách hóa đơn...
                </td>
              </tr>
            ) : orders.length === 0 ? (
              <tr>
                <td colSpan={8} style={{ textAlign: 'center', padding: '2rem', color: 'var(--text-muted)' }}>
                  Không tìm thấy hóa đơn nào phù hợp.
                </td>
              </tr>
            ) : (
              orders.map((o) => (
                <tr key={o.id}>
                  <td className="font-mono" style={{ fontWeight: 700, color: 'var(--amber-primary)' }}>
                    {o.order_code}
                  </td>
                  <td className="font-mono" style={{ fontSize: '0.78rem', color: 'var(--text-secondary)' }}>
                    {o.created_at ? new Date(o.created_at).toLocaleString('vi-VN') : '—'}
                  </td>
                  <td>
                    <div style={{ fontWeight: 600 }}>{o.customer_name || 'Khách vãng lai'}</div>
                    {o.customer_phone && (
                      <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
                        {o.customer_phone}
                      </div>
                    )}
                  </td>
                  <td>{o.user_name || '—'}</td>
                  <td>
                    <span className="badge badge-muted">
                      {o.payment_method === 'cash' ? 'Tiền mặt' : o.payment_method === 'transfer' ? 'C.Khoản' : 'Thẻ'}
                    </span>
                  </td>
                  <td className="currency" style={{ textAlign: 'right', fontWeight: 700, color: (o.status === 'cancelled' || o.status === 'rejected') ? 'var(--text-muted)' : 'var(--green-terminal)' }}>
                    {formatVND(o.final_amount)}
                  </td>
                  <td style={{ textAlign: 'center' }}>
                    <OrderStatusBadge status={o.status} />
                  </td>
                  <td style={{ textAlign: 'center' }}>
                    <div style={{ display: 'flex', justifyContent: 'center', gap: '0.35rem', flexWrap: 'wrap' }}>
                      {/* Admin/SuperAdmin Quick Actions */}
                      {(isAdmin || isSuperAdmin) && o.status === 'pending' && (
                        <>
                          <button
                            onClick={() => handleApproveOrder(o)}
                            className="btn btn-outline btn-icon btn-sm"
                            style={{ color: 'var(--green-terminal)', borderColor: 'var(--green-terminal)' }}
                            title="Duyệt đơn hàng"
                          >
                            <Check size={13} />
                          </button>
                          <button
                            onClick={() => setRejectingOrder(o)}
                            className="btn btn-outline btn-icon btn-sm"
                            style={{ color: 'var(--red-light)', borderColor: 'var(--red-light)' }}
                            title="Từ chối đơn hàng"
                          >
                            <X size={13} />
                          </button>
                        </>
                      )}

                      {/* Staff/Admin Quick Actions */}
                      {(user?.role === 'staff' || isAdmin || isSuperAdmin) && o.status === 'admin_approved' && (
                        <button
                          onClick={() => handleProcessOrder(o)}
                          className="btn btn-outline btn-icon btn-sm"
                          style={{ color: 'var(--amber-primary)', borderColor: 'var(--amber-primary)' }}
                          title="Nhận xử lý đơn hàng"
                        >
                          <PackageCheck size={13} />
                        </button>
                      )}

                      {(user?.role === 'staff' || isAdmin || isSuperAdmin) && o.status === 'processing' && (
                        <button
                          onClick={() => handleCompleteOrder(o)}
                          className="btn btn-outline btn-icon btn-sm"
                          style={{ color: 'var(--green-terminal)', borderColor: 'var(--green-terminal)' }}
                          title="Hoàn tất đơn hàng"
                        >
                          <CheckCircle2 size={13} />
                        </button>
                      )}

                      <button
                        onClick={() => setViewingOrder(o)}
                        className="btn btn-outline btn-icon btn-sm"
                        title="Xem chi tiết đơn"
                      >
                        <Eye size={13} />
                      </button>
                      <button
                        onClick={() => setReceiptOrder(o)}
                        className="btn btn-outline btn-icon btn-sm"
                        title="In lại hóa đơn"
                      >
                        <Printer size={13} />
                      </button>
                      {canCancel && o.status === 'completed' && (
                        <button
                          onClick={() => setCancellingOrder(o)}
                          className="btn btn-outline btn-icon btn-sm"
                          style={{ color: 'var(--red-light)' }}
                          title="Hủy hóa đơn & hoàn kho"
                        >
                          <XCircle size={13} />
                        </button>
                      )}
                      {isCustomer && o.status === 'pending' && (
                        <button
                          onClick={() => setCustomerCancellingOrder(o)}
                          className="btn btn-outline btn-icon btn-sm"
                          style={{ color: 'var(--red-light)' }}
                          title="Hủy đơn hàng"
                        >
                          <XCircle size={13} />
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Mobile Card List View (Visible on screens <= 768px) */}
      <div className="orders-mobile-card-list">
        {loading ? (
          <div style={{ textAlign: 'center', padding: '2rem', color: 'var(--text-muted)' }}>
            Đang tải danh sách hóa đơn...
          </div>
        ) : orders.length === 0 ? (
          <div style={{ textAlign: 'center', padding: '2rem', color: 'var(--text-muted)' }}>
            Không tìm thấy hóa đơn nào phù hợp.
          </div>
        ) : (
          orders.map((o) => (
            <div key={o.id} className="order-mobile-card">
              <div className="order-card-header">
                <div>
                  <span className="font-mono" style={{ fontWeight: 700, color: 'var(--amber-primary)', fontSize: '0.95rem' }}>
                    {o.order_code}
                  </span>
                  <div style={{ fontSize: '0.74rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)', marginTop: '2px' }}>
                    {o.created_at ? new Date(o.created_at).toLocaleString('vi-VN') : '—'}
                  </div>
                </div>
                <OrderStatusBadge status={o.status} />
              </div>

              <div className="order-card-row">
                <span style={{ color: 'var(--text-muted)' }}>Khách hàng:</span>
                <span style={{ fontWeight: 600, color: 'var(--text-primary)' }}>
                  {o.customer_name || 'Khách vãng lai'}
                  {o.customer_phone && ` (${o.customer_phone})`}
                </span>
              </div>

              <div className="order-card-row">
                <span style={{ color: 'var(--text-muted)' }}>Hình thức:</span>
                <span className="badge badge-muted">
                  {o.payment_method === 'cash' ? 'Tiền mặt' : o.payment_method === 'transfer' ? 'C.Khoản' : 'Thẻ'}
                </span>
              </div>

              <div className="order-card-row" style={{ paddingTop: '0.25rem' }}>
                <span style={{ color: 'var(--text-muted)', fontWeight: 600 }}>Tổng tiền:</span>
                <span className="currency" style={{ fontSize: '1rem', fontWeight: 800, color: (o.status === 'cancelled' || o.status === 'rejected') ? 'var(--text-muted)' : 'var(--green-terminal)' }}>
                  {formatVND(o.final_amount)}
                </span>
              </div>

              {/* Action buttons with minimum 40px touch targets */}
              <div className="order-card-actions">
                {(isAdmin || isSuperAdmin) && o.status === 'pending' && (
                  <>
                    <button
                      onClick={() => handleApproveOrder(o)}
                      className="btn btn-outline btn-sm"
                      style={{ color: 'var(--green-terminal)', borderColor: 'var(--green-terminal)' }}
                    >
                      <Check size={14} /> Duyệt đơn
                    </button>
                    <button
                      onClick={() => setRejectingOrder(o)}
                      className="btn btn-outline btn-sm"
                      style={{ color: 'var(--red-light)', borderColor: 'var(--red-light)' }}
                    >
                      <X size={14} /> Từ chối
                    </button>
                  </>
                )}

                {(user?.role === 'staff' || isAdmin || isSuperAdmin) && o.status === 'admin_approved' && (
                  <button
                    onClick={() => handleProcessOrder(o)}
                    className="btn btn-outline btn-sm"
                    style={{ color: 'var(--amber-primary)', borderColor: 'var(--amber-primary)', width: '100%', flex: '1 1 100%' }}
                  >
                    <PackageCheck size={15} /> Nhận xử lý đơn
                  </button>
                )}

                {(user?.role === 'staff' || isAdmin || isSuperAdmin) && o.status === 'processing' && (
                  <button
                    onClick={() => handleCompleteOrder(o)}
                    className="btn btn-outline btn-sm"
                    style={{ color: 'var(--green-terminal)', borderColor: 'var(--green-terminal)', width: '100%', flex: '1 1 100%' }}
                  >
                    <CheckCircle2 size={15} /> Hoàn tất đơn
                  </button>
                )}

                <button
                  onClick={() => setViewingOrder(o)}
                  className="btn btn-outline btn-sm"
                >
                  <Eye size={14} /> Chi tiết
                </button>

                <button
                  onClick={() => setReceiptOrder(o)}
                  className="btn btn-outline btn-sm"
                >
                  <Printer size={14} /> In phiếu
                </button>

                {canCancel && o.status === 'completed' && (
                  <button
                    onClick={() => setCancellingOrder(o)}
                    className="btn btn-outline btn-sm"
                    style={{ color: 'var(--red-light)', borderColor: 'var(--border-subtle)' }}
                  >
                    <XCircle size={14} /> Hủy & hoàn kho
                  </button>
                )}

                {isCustomer && o.status === 'pending' && (
                  <button
                    onClick={() => setCustomerCancellingOrder(o)}
                    className="btn btn-outline btn-sm"
                    style={{ color: 'var(--red-light)', borderColor: 'var(--border-subtle)', width: '100%', flex: '1 1 100%' }}
                  >
                    <XCircle size={14} /> Hủy đơn hàng
                  </button>
                )}
              </div>
            </div>
          ))
        )}
      </div>

      {/* VIEW ORDER DETAIL MODAL */}
      <Modal
        isOpen={!!viewingOrder}
        onClose={() => setViewingOrder(null)}
        title={`CHI TIẾT HÓA ĐƠN #${viewingOrder?.order_code}`}
        maxWidth="600px"
        footer={
          <>
            {/* Quick Actions in Detail Modal */}
            {(isAdmin || isSuperAdmin) && viewingOrder?.status === 'pending' && (
              <>
                <button
                  onClick={() => handleApproveOrder(viewingOrder)}
                  className="btn btn-primary"
                  style={{ background: 'var(--green-terminal)', color: '#000' }}
                >
                  <Check size={15} /> Duyệt Đơn
                </button>
                <button
                  onClick={() => setRejectingOrder(viewingOrder)}
                  className="btn btn-danger"
                >
                  <X size={15} /> Từ Chối Đơn
                </button>
              </>
            )}

            {(user?.role === 'staff' || isAdmin || isSuperAdmin) && viewingOrder?.status === 'admin_approved' && (
              <button
                onClick={() => handleProcessOrder(viewingOrder)}
                className="btn btn-primary"
                style={{ background: 'var(--amber-primary)', color: '#000' }}
              >
                <PackageCheck size={15} /> Nhận Xử Lý Đơn
              </button>
            )}

            {(user?.role === 'staff' || isAdmin || isSuperAdmin) && viewingOrder?.status === 'processing' && (
              <button
                onClick={() => handleCompleteOrder(viewingOrder)}
                className="btn btn-primary"
                style={{ background: 'var(--green-terminal)', color: '#000' }}
              >
                <CheckCircle2 size={15} /> Hoàn Tất Đơn Hàng
              </button>
            )}

            <button
              onClick={() => {
                setReceiptOrder(viewingOrder);
              }}
              className="btn btn-outline"
            >
              <Printer size={15} /> In Hóa Đơn
            </button>
            {canCancel && viewingOrder?.status === 'completed' && (
              <button
                onClick={() => setCancellingOrder(viewingOrder)}
                className="btn btn-danger"
              >
                <XCircle size={15} /> Hủy Đơn & Hoàn Tồn Kho
              </button>
            )}
            {isCustomer && viewingOrder?.status === 'pending' && (
              <button
                onClick={() => setCustomerCancellingOrder(viewingOrder)}
                className="btn btn-danger"
              >
                <XCircle size={15} /> Hủy Đơn Hàng
              </button>
            )}
            <button onClick={() => setViewingOrder(null)} className="btn btn-primary">
              Đóng
            </button>
          </>
        }
      >
        {viewingOrder && (
          <div>
            <OrderLifecycleStepper
              status={viewingOrder.status}
              rejectionReason={viewingOrder.rejection_reason}
            />

            <div className="form-grid-2" style={{ gap: '0.6rem', marginBottom: '1rem', fontSize: '0.85rem' }}>
              <div><strong>Mã HĐ:</strong> <span className="font-mono">{viewingOrder.order_code}</span></div>
              <div><strong>Thời gian:</strong> {new Date(viewingOrder.created_at).toLocaleString('vi-VN')}</div>
              <div><strong>Khách hàng:</strong> {viewingOrder.customer_name || 'Khách vãng lai'}</div>
              <div><strong>Thu ngân:</strong> {viewingOrder.user_name || '—'}</div>
              <div><strong>Phương thức:</strong> {viewingOrder.payment_method.toUpperCase()}</div>
              <div>
                <strong>Trạng thái:</strong>{' '}
                <OrderStatusBadge status={viewingOrder.status} />
              </div>
            </div>

            {viewingOrder.rejection_reason && (
              <div style={{ padding: '0.5rem', background: 'rgba(239, 68, 68, 0.1)', border: '1px solid var(--red-light)', borderRadius: 'var(--radius-xs)', marginBottom: '1rem', fontSize: '0.8rem', color: 'var(--red-light)' }}>
                <strong>Lý do từ chối:</strong> {viewingOrder.rejection_reason}
              </div>
            )}

            {viewingOrder.note && (
              <div style={{ padding: '0.5rem', background: 'var(--bg-input)', border: '1px solid var(--border-subtle)', borderRadius: 'var(--radius-xs)', marginBottom: '1rem', fontSize: '0.8rem' }}>
                <strong>Ghi chú:</strong> {viewingOrder.note}
              </div>
            )}

            <div style={{ fontWeight: 700, marginBottom: '0.4rem', color: 'var(--amber-primary)', fontSize: '0.85rem' }}>
              DANH SÁCH MẶT HÀNG:
            </div>
            <table className="retro-table" style={{ fontSize: '0.8rem' }}>
              <thead>
                <tr>
                  <th>Sản phẩm</th>
                  <th style={{ textAlign: 'center' }}>SL</th>
                  <th style={{ textAlign: 'right' }}>Đơn giá</th>
                  <th style={{ textAlign: 'right' }}>Thành tiền</th>
                </tr>
              </thead>
              <tbody>
                {(viewingOrder.items || []).map((item, idx) => (
                  <tr key={idx}>
                    <td>
                      <div>{item.product_name}</div>
                      <div style={{ fontSize: '0.68rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>{item.product_sku}</div>
                    </td>
                    <td style={{ textAlign: 'center', fontFamily: 'var(--font-mono)', fontWeight: 600 }}>{item.quantity}</td>
                    <td style={{ textAlign: 'right', fontFamily: 'var(--font-mono)' }}>{formatVND(item.unit_price)}</td>
                    <td style={{ textAlign: 'right', fontFamily: 'var(--font-mono)', fontWeight: 700, color: 'var(--green-terminal)' }}>{formatVND(item.subtotal)}</td>
                  </tr>
                ))}
              </tbody>
            </table>

            <div style={{ marginTop: '1rem', textAlign: 'right', display: 'flex', flexDirection: 'column', gap: '0.3rem' }}>
              <div>Tổng tiền hàng: <span className="font-mono">{formatVND(viewingOrder.total_amount)}</span></div>
              {viewingOrder.discount_amount > 0 && (
                <div style={{ color: 'var(--red-light)' }}>Chiết khấu: <span className="font-mono">-{formatVND(viewingOrder.discount_amount)}</span></div>
              )}
              <div style={{ fontSize: '1.15rem', fontWeight: 800, color: 'var(--amber-primary)' }}>
                Tổng thanh toán: <span className="font-mono">{formatVND(viewingOrder.final_amount)}</span>
              </div>
            </div>

            {isSuperAdmin && (
              <div
                style={{
                  marginTop: '1.25rem',
                  padding: '0.85rem 1rem',
                  background: 'rgba(245, 158, 11, 0.05)',
                  border: '1px dashed var(--amber-primary)',
                  borderRadius: 'var(--radius-xs)',
                }}
              >
                <div style={{ fontSize: '0.75rem', fontWeight: 800, color: 'var(--amber-primary)', marginBottom: '0.6rem', display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
                  <span>⚡ THAO TÁC NGOẠI LỆ (CHỦ CỬA HÀNG - SUPERADMIN)</span>
                </div>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem' }}>
                  {viewingOrder.status !== 'cancelled' && viewingOrder.status !== 'rejected' && (
                    <button
                      type="button"
                      onClick={() => {
                        setForceActionModal({ order: viewingOrder, action: 'force_cancel' });
                        setForceActionReason('');
                      }}
                      className="btn btn-outline btn-sm"
                      style={{ color: 'var(--red-light)', borderColor: 'var(--red-light)' }}
                    >
                      Hủy Khẩn Cấp (Force Cancel)
                    </button>
                  )}
                  {viewingOrder.status === 'rejected' && (
                    <button
                      type="button"
                      onClick={() => {
                        setForceActionModal({ order: viewingOrder, action: 'reopen_rejected' });
                        setForceActionReason('Mở lại đơn bị từ chối');
                      }}
                      className="btn btn-outline btn-sm"
                      style={{ color: 'var(--green-light)', borderColor: 'var(--green-terminal)' }}
                    >
                      Mở Lại Đơn (Reopen)
                    </button>
                  )}
                  {viewingOrder.status !== 'cancelled' && (
                    <button
                      type="button"
                      onClick={() => {
                        setForceActionModal({ order: viewingOrder, action: 'override_status' });
                        setForceActionReason('');
                        setForceActionTargetStatus('processing');
                      }}
                      className="btn btn-outline btn-sm"
                      style={{ color: 'var(--amber-primary)', borderColor: 'var(--amber-primary)' }}
                    >
                      Chuyển Trạng Thái (Override)
                    </button>
                  )}
                </div>
              </div>
            )}
          </div>
        )}
      </Modal>

      {/* CONFIRM CANCEL ORDER MODAL */}
      <Modal
        isOpen={!!cancellingOrder}
        onClose={() => setCancellingOrder(null)}
        title="XÁC NHẬN HỦY HÓA ĐƠN BÁN HÀNG"
        maxWidth="460px"
      >
        <form onSubmit={handleCancelOrder}>
          <div style={{ color: 'var(--red-light)', marginBottom: '1rem', fontSize: '0.85rem', lineHeight: '1.4' }}>
            ⚠️ <strong>CẢNH BÁO:</strong> Khi hủy đơn hàng <strong>{cancellingOrder?.order_code}</strong>, toàn bộ số lượng các sản phẩm trong đơn sẽ được <strong>hoàn trả về kho ngay lập tức</strong> thông qua SQLite Atomic Transaction.
          </div>

          <div className="form-group">
            <label className="form-label">Lý do hủy đơn</label>
            <textarea
              className="form-control"
              rows={3}
              required
              value={cancelReason}
              onChange={(e) => setCancelReason(e.target.value)}
              placeholder="Nhập lý do trả hàng / hủy đơn..."
            />
          </div>

          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.5rem', marginTop: '1rem' }}>
            <button type="button" onClick={() => setCancellingOrder(null)} className="btn btn-outline">
              Đóng
            </button>
            <button type="submit" className="btn btn-danger" disabled={submittingCancel}>
              {submittingCancel ? 'Đang hoàn kho...' : 'Xác Nhận Hủy Đơn & Hoàn Tồn'}
            </button>
          </div>
        </form>
      </Modal>

      {/* CONFIRM CUSTOMER CANCEL ORDER MODAL */}
      <Modal
        isOpen={!!customerCancellingOrder}
        onClose={() => setCustomerCancellingOrder(null)}
        title="XÁC NHẬN HỦY ĐƠN HÀNG"
        maxWidth="460px"
      >
        <form onSubmit={handleCustomerCancel}>
          <div style={{ color: 'var(--text-secondary)', marginBottom: '1rem', fontSize: '0.85rem', lineHeight: '1.4' }}>
            Bạn có chắc chắn muốn hủy đơn hàng <strong className="font-mono" style={{ color: 'var(--amber-primary)' }}>{customerCancellingOrder?.order_code}</strong>?
            <br />
            Sau khi hủy, đơn hàng sẽ chuyển sang trạng thái <strong>ĐÃ HỦY</strong> và các mặt hàng sẽ được giải phóng hoàn trả về tồn kho.
          </div>

          <div className="form-group">
            <label className="form-label">Lý do hủy đơn (tùy chọn)</label>
            <textarea
              className="form-control"
              rows={2}
              value={customerCancelReason}
              onChange={(e) => setCustomerCancelReason(e.target.value)}
              placeholder="Nhập lý do hủy đơn nếu có..."
            />
          </div>

          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.5rem', marginTop: '1rem' }}>
            <button type="button" onClick={() => setCustomerCancellingOrder(null)} className="btn btn-outline">
              Quay lại
            </button>
            <button type="submit" className="btn btn-danger" disabled={submittingCustomerCancel}>
              {submittingCustomerCancel ? 'Đang hủy đơn...' : 'Xác Nhận Hủy Đơn'}
            </button>
          </div>
        </form>
      </Modal>

      {/* SUPERADMIN FORCE ACTION MODAL */}
      <Modal
        isOpen={!!forceActionModal}
        onClose={() => setForceActionModal(null)}
        title={`XỬ LÝ NGOẠI LỆ: ${forceActionModal?.action?.toUpperCase()}`}
        maxWidth="500px"
      >
        <form onSubmit={handleSuperAdminForceAction}>
          <div style={{ fontSize: '0.85rem', marginBottom: '1rem', color: 'var(--text-secondary)', lineHeight: '1.4' }}>
            Đơn hàng: <strong className="font-mono" style={{ color: 'var(--amber-primary)' }}>{forceActionModal?.order?.order_code}</strong>
            <br />
            Trạng thái hiện tại: <strong className="font-mono">{forceActionModal?.order?.status}</strong>
          </div>

          {forceActionModal?.action === 'override_status' && (
            <div className="form-group" style={{ marginBottom: '1rem' }}>
              <label className="form-label">Trạng thái chuyển đổi mong muốn</label>
              <select
                className="form-control"
                value={forceActionTargetStatus}
                onChange={(e) => setForceActionTargetStatus(e.target.value)}
              >
                <option value="pending">pending (Chờ duyệt)</option>
                <option value="admin_approved">admin_approved (Đã duyệt)</option>
                <option value="processing">processing (Đang xử lý)</option>
                <option value="completed">completed (Hoàn thành)</option>
              </select>
            </div>
          )}

          {forceActionModal?.action === 'reopen_rejected' && (
            <div style={{ padding: '0.6rem', background: 'rgba(34, 197, 94, 0.08)', border: '1px solid var(--green-terminal)', borderRadius: 'var(--radius-xs)', marginBottom: '1rem', fontSize: '0.8rem', color: 'var(--green-light)' }}>
              ℹ️ Đơn hàng sẽ được chuyển về <strong>pending</strong> và tồn kho các sản phẩm trong đơn sẽ được tự động kiểm tra và trừ giữ chỗ an toàn.
            </div>
          )}

          {forceActionModal?.action === 'force_cancel' && (
            <div style={{ padding: '0.6rem', background: 'rgba(239, 68, 68, 0.08)', border: '1px solid var(--red-light)', borderRadius: 'var(--radius-xs)', marginBottom: '1rem', fontSize: '0.8rem', color: 'var(--red-light)' }}>
              ⚠️ Đơn hàng sẽ chuyển sang <strong>cancelled</strong>, toàn bộ tồn kho sẽ được hoàn trả nguyên vẹn và doanh thu (nếu có) sẽ được hoàn lại.
            </div>
          )}

          <div className="form-group">
            <label className="form-label">Lý do can thiệp ngoại lệ (Bắt buộc)</label>
            <textarea
              className="form-control"
              rows={3}
              required
              value={forceActionReason}
              onChange={(e) => setForceActionReason(e.target.value)}
              placeholder="Nhập lý do can thiệp để lưu vết kiểm toán..."
            />
          </div>

          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.5rem', marginTop: '1.25rem' }}>
            <button type="button" onClick={() => setForceActionModal(null)} className="btn btn-outline">
              Hủy bỏ
            </button>
            <button type="submit" className="btn btn-primary" disabled={submittingForceAction || !forceActionReason.trim()}>
              {submittingForceAction ? 'Đang thực hiện...' : 'Xác Nhận Can Thiệp'}
            </button>
          </div>
        </form>
      </Modal>

      {/* REJECT ORDER MODAL (Phase 13F) */}
      <Modal
        isOpen={!!rejectingOrder}
        onClose={() => {
          setRejectingOrder(null);
          setRejectReason('Đơn hàng bị Admin từ chối');
        }}
        title={`TỪ CHỐI ĐƠN HÀNG #${rejectingOrder?.order_code}`}
        maxWidth="480px"
      >
        <form onSubmit={handleRejectOrder}>
          <div style={{ color: 'var(--text-secondary)', marginBottom: '1rem', fontSize: '0.85rem', lineHeight: '1.4' }}>
            Xác nhận từ chối đơn hàng <strong className="font-mono" style={{ color: 'var(--amber-primary)' }}>{rejectingOrder?.order_code}</strong>?
            <br />
            Sau khi từ chối, đơn hàng sẽ chuyển sang trạng thái <strong>TỪ CHỐI (REJECTED)</strong> và toàn bộ tồn kho đã giữ chỗ sẽ được tự động hoàn trả an toàn.
          </div>

          <div className="form-group" style={{ marginBottom: '1rem' }}>
            <label className="form-label" style={{ fontWeight: 600 }}>Lý do từ chối (Bắt buộc)</label>
            <textarea
              className="form-control"
              rows={3}
              required
              value={rejectReason}
              onChange={(e) => setRejectReason(e.target.value)}
              placeholder="Nhập lý do từ chối đơn hàng..."
            />
          </div>

          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.5rem', marginTop: '1.25rem' }}>
            <button
              type="button"
              onClick={() => {
                setRejectingOrder(null);
                setRejectReason('Đơn hàng bị Admin từ chối');
              }}
              className="btn btn-outline"
            >
              Hủy bỏ
            </button>
            <button
              type="submit"
              className="btn btn-danger"
              disabled={submittingReject || !rejectReason.trim()}
            >
              {submittingReject ? 'Đang từ chối...' : 'Xác Nhận Từ Chối'}
            </button>
          </div>
        </form>
      </Modal>

      {/* RECEIPT MODAL */}
      <ReceiptModal
        isOpen={!!receiptOrder}
        onClose={() => setReceiptOrder(null)}
        order={receiptOrder}
      />
    </div>
  );
};
