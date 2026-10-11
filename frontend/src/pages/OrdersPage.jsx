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
  Truck,
  RotateCcw,
  History,
  DollarSign,
  CreditCard,
  UserCheck,
} from 'lucide-react';
import { ordersAPI } from '../services/api';
import { useAuth } from '../context/AuthContext';
import { useToast } from '../context/ToastContext';
import { Badge, OrderStatusBadge, PaymentStatusBadge, FulfillmentStatusBadge } from '../components/ui/Badge';
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
  const { user, isAdmin, isSuperAdmin } = useAuth();
  const { addToast } = useToast();
  const isCustomer = user?.role === 'customer';
  const canCancel = isAdmin || isSuperAdmin;

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

  // Phase R3: Workflow States (Claim, Reassign, Payment, Fulfillment, Refund, Audit)
  const [claimingOrderId, setClaimingOrderId] = useState(null);
  const [reassignModal, setReassignModal] = useState(null);
  const [submittingReassign, setSubmittingReassign] = useState(false);

  const [transferModal, setTransferModal] = useState(null);
  const [submittingTransfer, setSubmittingTransfer] = useState(false);

  const [verifyPaymentModal, setVerifyPaymentModal] = useState(null);
  const [submittingVerifyPayment, setSubmittingVerifyPayment] = useState(false);

  const [returnModal, setReturnModal] = useState(null);
  const [submittingReturn, setSubmittingReturn] = useState(false);

  const [refundModal, setRefundModal] = useState(null);
  const [submittingRefund, setSubmittingRefund] = useState(false);

  const [auditLogsModal, setAuditLogsModal] = useState(null);

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

  // --- PHASE R3 WORKFLOW HANDLERS ---
  const handleClaimOrder = async (order) => {
    setClaimingOrderId(order.id);
    try {
      const updated = await ordersAPI.claimOrder(order.id);
      addToast(`Nhận đơn hàng #${order.order_code} thành công! Đơn chuyển sang đang xử lý.`, 'success');
      window.dispatchEvent(new CustomEvent('workflow-updated'));
      loadOrders();
      fetchWorkflowCounts();
      if (viewingOrder?.id === order.id) {
        setViewingOrder(updated);
      }
    } catch (err) {
      if (err.message?.includes('409') || err.message?.includes('đã được nhân viên khác nhận')) {
        addToast(`XUNG ĐỘT (HTTP 409): Đơn hàng #${order.order_code} đã được nhân viên khác nhận trước đó!`, 'error');
      } else {
        addToast(err.message || 'Lỗi khi nhận đơn hàng', 'error');
      }
      loadOrders();
      fetchWorkflowCounts();
    } finally {
      setClaimingOrderId(null);
    }
  };

  const handleReassignOrder = async (e) => {
    e.preventDefault();
    if (!reassignModal || !reassignModal.newStaffId) return;
    setSubmittingReassign(true);
    try {
      const updated = await ordersAPI.reassignOrder(
        reassignModal.order.id,
        parseInt(reassignModal.newStaffId, 10),
        reassignModal.reason || 'Admin điều chuyển nhân viên'
      );
      addToast(`Đã điều chuyển đơn #${reassignModal.order.order_code} thành công!`, 'success');
      setReassignModal(null);
      window.dispatchEvent(new CustomEvent('workflow-updated'));
      loadOrders();
      if (viewingOrder?.id === reassignModal.order.id) {
        setViewingOrder(updated);
      }
    } catch (err) {
      addToast(err.message || 'Lỗi khi điều chuyển đơn hàng', 'error');
    } finally {
      setSubmittingReassign(false);
    }
  };

  const handleNotifyTransfer = async (e) => {
    e.preventDefault();
    if (!transferModal) return;
    setSubmittingTransfer(true);
    try {
      const updated = await ordersAPI.notifyTransfer(transferModal.order.id, {
        transfer_reference: transferModal.transferRef || undefined,
        bank_name: transferModal.bankName || undefined,
        note: transferModal.note || undefined,
      });
      addToast(`Đã gửi thông báo chuyển khoản đơn #${transferModal.order.order_code}. Đang chờ Admin xác minh!`, 'success');
      setTransferModal(null);
      window.dispatchEvent(new CustomEvent('workflow-updated'));
      loadOrders();
      if (viewingOrder?.id === transferModal.order.id) {
        setViewingOrder(updated);
      }
    } catch (err) {
      addToast(err.message || 'Lỗi khi thông báo chuyển khoản', 'error');
    } finally {
      setSubmittingTransfer(false);
    }
  };

  const handleVerifyPayment = async (e) => {
    e.preventDefault();
    if (!verifyPaymentModal) return;
    setSubmittingVerifyPayment(true);
    try {
      const updated = await ordersAPI.verifyPayment(verifyPaymentModal.order.id, {
        verified_reference: verifyPaymentModal.verifiedRef || undefined,
        note: verifyPaymentModal.note || undefined,
      });
      addToast(`Đã xác minh thanh toán cho đơn #${verifyPaymentModal.order.order_code}!`, 'success');
      setVerifyPaymentModal(null);
      window.dispatchEvent(new CustomEvent('workflow-updated'));
      loadOrders();
      if (viewingOrder?.id === verifyPaymentModal.order.id) {
        setViewingOrder(updated);
      }
    } catch (err) {
      addToast(err.message || 'Lỗi khi xác minh thanh toán', 'error');
    } finally {
      setSubmittingVerifyPayment(false);
    }
  };

  const handleConfirmCodPayment = async (order) => {
    try {
      const updated = await ordersAPI.confirmCodPayment(order.id, 'Xác nhận đã thu tiền mặt COD từ khách');
      addToast(`Đã ghi nhận thu tiền COD cho đơn #${order.order_code}!`, 'success');
      window.dispatchEvent(new CustomEvent('workflow-updated'));
      loadOrders();
      if (viewingOrder?.id === order.id) {
        setViewingOrder(updated);
      }
    } catch (err) {
      addToast(err.message || 'Lỗi khi xác nhận thanh toán COD', 'error');
    }
  };

  const handleUpdateFulfillment = async (order, targetStatus, note = null) => {
    try {
      const updated = await ordersAPI.updateFulfillment(order.id, targetStatus, note);
      addToast(`Cập nhật trạng thái giao vận: ${targetStatus} cho đơn #${order.order_code}!`, 'success');
      window.dispatchEvent(new CustomEvent('workflow-updated'));
      loadOrders();
      if (viewingOrder?.id === order.id) {
        setViewingOrder(updated);
      }
    } catch (err) {
      addToast(err.message || 'Lỗi khi cập nhật giao vận', 'error');
    }
  };

  const handleConfirmReturn = async (e) => {
    e.preventDefault();
    if (!returnModal) return;
    setSubmittingReturn(true);
    try {
      const updated = await ordersAPI.confirmReturn(
        returnModal.order.id,
        returnModal.reason || 'Hàng hoàn về kho',
        returnModal.note || undefined
      );
      addToast(`Đã xác nhận nhập lại kho đơn #${returnModal.order.order_code}. Tồn kho đã hoàn trả nguyên vẹn!`, 'success');
      setReturnModal(null);
      window.dispatchEvent(new CustomEvent('workflow-updated'));
      loadOrders();
      if (viewingOrder?.id === returnModal.order.id) {
        setViewingOrder(updated);
      }
    } catch (err) {
      addToast(err.message || 'Lỗi khi xác nhận hoàn kho', 'error');
    } finally {
      setSubmittingReturn(false);
    }
  };

  const handleRequestRefund = async (e) => {
    e.preventDefault();
    if (!refundModal) return;
    setSubmittingRefund(true);
    try {
      const updated = await ordersAPI.requestRefund(refundModal.order.id, refundModal.reason || 'Khách yêu cầu hoàn tiền');
      addToast(`Đã yêu cầu hoàn tiền cho đơn #${refundModal.order.order_code}! Đang chờ Admin phê duyệt.`, 'success');
      setRefundModal(null);
      window.dispatchEvent(new CustomEvent('workflow-updated'));
      loadOrders();
      if (viewingOrder?.id === refundModal.order.id) {
        setViewingOrder(updated);
      }
    } catch (err) {
      addToast(err.message || 'Lỗi khi yêu cầu hoàn tiền', 'error');
    } finally {
      setSubmittingRefund(false);
    }
  };

  const handleConfirmRefund = async (e) => {
    e.preventDefault();
    if (!refundModal) return;
    setSubmittingRefund(true);
    try {
      const updated = await ordersAPI.confirmRefund(
        refundModal.order.id,
        refundModal.refundRef || undefined,
        refundModal.reason || 'Đã chuyển tiền hoàn cho khách'
      );
      addToast(`Đã xác nhận hoàn tiền thực tế cho đơn #${refundModal.order.order_code}! (Không ảnh hưởng đến kho)`, 'success');
      setRefundModal(null);
      window.dispatchEvent(new CustomEvent('workflow-updated'));
      loadOrders();
      if (viewingOrder?.id === refundModal.order.id) {
        setViewingOrder(updated);
      }
    } catch (err) {
      addToast(err.message || 'Lỗi khi xác nhận hoàn tiền', 'error');
    } finally {
      setSubmittingRefund(false);
    }
  };

  const handleOpenAuditLogs = async (order) => {
    setAuditLogsModal({ order, logs: [], loading: true });
    try {
      const logs = await ordersAPI.getAuditLogs(order.id);
      setAuditLogsModal({ order, logs, loading: false });
    } catch (err) {
      addToast(err.message || 'Lỗi khi tải lịch sử kiểm toán', 'error');
      setAuditLogsModal(null);
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
              <th>NGƯỜI BÁN / PHỤ TRÁCH</th>
              <th>HÌNH THỨC & GIAO VẬN</th>
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
                  <td>
                    <div>{o.user_name || '—'}</div>
                    {o.assigned_name ? (
                      <div style={{ fontSize: '0.72rem', color: 'var(--amber-primary)', marginTop: '0.2rem', display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
                        <UserCheck size={11} /> <span>{o.assigned_name}</span>
                      </div>
                    ) : o.status === 'admin_approved' ? (
                      <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', fontStyle: 'italic', marginTop: '0.2rem' }}>
                        (Chưa có Staff nhận)
                      </div>
                    ) : null}
                  </td>
                  <td>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.2rem' }}>
                      <span className="badge badge-muted" style={{ width: 'fit-content' }}>
                        {o.payment_method === 'cash' ? 'Tiền mặt (COD)' : o.payment_method === 'transfer' ? 'Chuyển khoản' : 'Thẻ'}
                      </span>
                      {o.payment_status && (
                        <div>
                          <PaymentStatusBadge status={o.payment_status} />
                        </div>
                      )}
                      {o.fulfillment_status && (
                        <div>
                          <FulfillmentStatusBadge status={o.fulfillment_status} />
                        </div>
                      )}
                    </div>
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

                      {/* Staff/Admin Atomic Claim Lock */}
                      {(user?.role === 'staff' || isAdmin || isSuperAdmin) && o.status === 'admin_approved' && !o.assigned_to && (
                        <button
                          onClick={() => handleClaimOrder(o)}
                          disabled={claimingOrderId === o.id}
                          className="btn btn-outline btn-icon btn-sm"
                          style={{ color: 'var(--amber-primary)', borderColor: 'var(--amber-primary)' }}
                          title="Nhận đơn (Atomic Claim Lock)"
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
                        onClick={() => handleOpenAuditLogs(o)}
                        className="btn btn-outline btn-icon btn-sm"
                        title="Lịch sử / Audit log"
                      >
                        <History size={13} />
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
                <span style={{ color: 'var(--text-muted)' }}>Phụ trách:</span>
                <span style={{ fontWeight: 600, color: 'var(--text-primary)' }}>
                  {o.assigned_name ? (
                    <span style={{ color: 'var(--amber-primary)' }}>{o.assigned_name}</span>
                  ) : o.status === 'admin_approved' ? (
                    <span style={{ color: 'var(--text-muted)', fontStyle: 'italic' }}>Chưa có Staff nhận</span>
                  ) : (
                    o.user_name || '—'
                  )}
                </span>
              </div>

              <div className="order-card-row">
                <span style={{ color: 'var(--text-muted)' }}>Thanh toán & Giao vận:</span>
                <div style={{ display: 'flex', gap: '0.35rem', flexWrap: 'wrap', alignItems: 'center' }}>
                  <span className="badge badge-muted">
                    {o.payment_method === 'cash' ? 'Tiền mặt' : o.payment_method === 'transfer' ? 'C.Khoản' : 'Thẻ'}
                  </span>
                  {o.payment_status && <PaymentStatusBadge status={o.payment_status} />}
                  {o.fulfillment_status && <FulfillmentStatusBadge status={o.fulfillment_status} />}
                </div>
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

                {/* Staff/Admin Atomic Claim Lock */}
                {(user?.role === 'staff' || isAdmin || isSuperAdmin) && o.status === 'admin_approved' && !o.assigned_to && (
                  <button
                    onClick={() => handleClaimOrder(o)}
                    disabled={claimingOrderId === o.id}
                    className="btn btn-outline btn-sm"
                    style={{ color: 'var(--amber-primary)', borderColor: 'var(--amber-primary)', width: '100%', flex: '1 1 100%' }}
                  >
                    <PackageCheck size={15} /> Nhận đơn (Claim Lock)
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
                  onClick={() => handleOpenAuditLogs(o)}
                  className="btn btn-outline btn-sm"
                >
                  <History size={14} /> Lịch sử
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
              <div><strong>Người tạo:</strong> {viewingOrder.user_name || '—'}</div>
              <div>
                <strong>Staff phụ trách:</strong>{' '}
                {viewingOrder.assigned_name ? (
                  <span style={{ color: 'var(--amber-primary)', fontWeight: 600 }}>{viewingOrder.assigned_name}</span>
                ) : (
                  <span style={{ color: 'var(--text-muted)', fontStyle: 'italic' }}>Chưa phân công</span>
                )}
              </div>
              <div><strong>Hình thức:</strong> {viewingOrder.payment_method.toUpperCase()}</div>
              <div>
                <strong>Thanh toán:</strong>{' '}
                <PaymentStatusBadge status={viewingOrder.payment_status} />
              </div>
              <div>
                <strong>Giao vận:</strong>{' '}
                <FulfillmentStatusBadge status={viewingOrder.fulfillment_status} />
              </div>
              <div>
                <strong>Trạng thái đơn:</strong>{' '}
                <OrderStatusBadge status={viewingOrder.status} />
              </div>
              {viewingOrder.shipping_address && (
                <div style={{ gridColumn: 'span 2' }}>
                  <strong>Địa chỉ giao:</strong> {viewingOrder.shipping_name && `${viewingOrder.shipping_name} - `}{viewingOrder.shipping_phone && `${viewingOrder.shipping_phone}: `}{viewingOrder.shipping_address}
                </div>
              )}
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

            {/* PHASE R3 WORKFLOW PANELS */}
            <div style={{ marginTop: '1.25rem', display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
              {/* 1. Xử lý & Phân công */}
              <div style={{ padding: '0.75rem', background: 'var(--bg-input)', border: '1px solid var(--border-subtle)', borderRadius: 'var(--radius-xs)' }}>
                <div style={{ fontSize: '0.75rem', fontWeight: 700, color: 'var(--text-primary)', marginBottom: '0.5rem', display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
                  <PackageCheck size={14} style={{ color: 'var(--amber-primary)' }} />
                  <span>PHÂN CÔNG & XỬ LÝ (CLAIM & REASSIGN)</span>
                </div>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem', alignItems: 'center' }}>
                  {viewingOrder.status === 'admin_approved' && !viewingOrder.assigned_to && (user?.role === 'staff' || isAdmin || isSuperAdmin) && (
                    <button
                      type="button"
                      onClick={() => handleClaimOrder(viewingOrder)}
                      disabled={claimingOrderId === viewingOrder.id}
                      className="btn btn-primary btn-sm"
                      style={{ background: 'var(--amber-primary)', color: '#000' }}
                    >
                      <PackageCheck size={14} /> Nhận đơn xử lý (Claim Lock)
                    </button>
                  )}
                  {viewingOrder.assigned_to && (isAdmin || isSuperAdmin) && (
                    <button
                      type="button"
                      onClick={() => setReassignModal({ order: viewingOrder, newStaffId: '', reason: '' })}
                      className="btn btn-outline btn-sm"
                    >
                      <UserCheck size={14} /> Điều chuyển Staff khác
                    </button>
                  )}
                  <button
                    type="button"
                    onClick={() => handleOpenAuditLogs(viewingOrder)}
                    className="btn btn-outline btn-sm"
                  >
                    <History size={14} /> Xem Lịch Sử / Audit Log
                  </button>
                </div>
              </div>

              {/* 2. Thanh toán & Đối soát */}
              <div style={{ padding: '0.75rem', background: 'var(--bg-input)', border: '1px solid var(--border-subtle)', borderRadius: 'var(--radius-xs)' }}>
                <div style={{ fontSize: '0.75rem', fontWeight: 700, color: 'var(--text-primary)', marginBottom: '0.5rem', display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
                  <CreditCard size={14} style={{ color: 'var(--blue-light)' }} />
                  <span>XÁC MINH THANH TOÁN (PAYMENT VERIFICATION)</span>
                </div>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem', alignItems: 'center' }}>
                  {viewingOrder.payment_method === 'transfer' && viewingOrder.payment_status === 'unpaid' && (
                    <button
                      type="button"
                      onClick={() => setTransferModal({ order: viewingOrder, transferRef: '', bankName: '', note: '' })}
                      className="btn btn-outline btn-sm"
                      style={{ borderColor: 'var(--blue-light)', color: 'var(--blue-light)' }}
                    >
                      <CreditCard size={14} /> Thông báo đã chuyển khoản
                    </button>
                  )}
                  {viewingOrder.payment_status === 'pending_verification' && (isAdmin || isSuperAdmin) && (
                    <button
                      type="button"
                      onClick={() => setVerifyPaymentModal({ order: viewingOrder, verifiedRef: '', note: '' })}
                      className="btn btn-primary btn-sm"
                      style={{ background: 'var(--green-terminal)', color: '#000' }}
                    >
                      <Check size={14} /> Đối soát & Xác nhận Paid
                    </button>
                  )}
                  {viewingOrder.payment_method === 'cash' && viewingOrder.payment_status === 'unpaid' && (user?.role === 'staff' || isAdmin || isSuperAdmin) && (
                    <button
                      type="button"
                      onClick={() => handleConfirmCodPayment(viewingOrder)}
                      className="btn btn-outline btn-sm"
                      style={{ borderColor: 'var(--green-terminal)', color: 'var(--green-terminal)' }}
                    >
                      <DollarSign size={14} /> Xác nhận đã thu tiền COD
                    </button>
                  )}
                  {/* Hoàn tiền */}
                  {viewingOrder.payment_status === 'paid' && (
                    <button
                      type="button"
                      onClick={() => setRefundModal({ order: viewingOrder, mode: 'request', refundRef: '', reason: '' })}
                      className="btn btn-outline btn-sm"
                      style={{ borderColor: 'var(--amber-primary)', color: 'var(--amber-primary)' }}
                    >
                      <RotateCcw size={14} /> Yêu cầu hoàn tiền (Refund)
                    </button>
                  )}
                  {viewingOrder.payment_status === 'refund_pending' && (isAdmin || isSuperAdmin) && (
                    <button
                      type="button"
                      onClick={() => setRefundModal({ order: viewingOrder, mode: 'confirm', refundRef: '', reason: '' })}
                      className="btn btn-danger btn-sm"
                    >
                      <Check size={14} /> Xác nhận đã hoàn tiền thực tế
                    </button>
                  )}
                </div>
              </div>

              {/* 3. Giao vận & Trả hàng */}
              {(user?.role === 'staff' || isAdmin || isSuperAdmin) && (
                <div style={{ padding: '0.75rem', background: 'var(--bg-input)', border: '1px solid var(--border-subtle)', borderRadius: 'var(--radius-xs)' }}>
                  <div style={{ fontSize: '0.75rem', fontWeight: 700, color: 'var(--text-primary)', marginBottom: '0.5rem', display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
                    <Truck size={14} style={{ color: 'var(--green-terminal)' }} />
                    <span>GIAO VẬN & HOÀN HÀNG (FULFILLMENT & RETURN)</span>
                  </div>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem', alignItems: 'center' }}>
                    {(viewingOrder.fulfillment_status === 'unfulfilled' || !viewingOrder.fulfillment_status) && viewingOrder.status !== 'cancelled' && viewingOrder.status !== 'rejected' && (
                      <button
                        type="button"
                        onClick={() => handleUpdateFulfillment(viewingOrder, 'packing')}
                        className="btn btn-outline btn-sm"
                      >
                        <PackageCheck size={14} /> Bắt đầu đóng gói (Packing)
                      </button>
                    )}
                    {viewingOrder.fulfillment_status === 'packing' && (
                      <button
                        type="button"
                        onClick={() => handleUpdateFulfillment(viewingOrder, 'shipping')}
                        className="btn btn-outline btn-sm"
                        style={{ borderColor: 'var(--blue-light)', color: 'var(--blue-light)' }}
                      >
                        <Truck size={14} /> Bắt đầu vận chuyển (Shipping)
                      </button>
                    )}
                    {viewingOrder.fulfillment_status === 'shipping' && (
                      <>
                        <button
                          type="button"
                          onClick={() => handleUpdateFulfillment(viewingOrder, 'delivered')}
                          className="btn btn-primary btn-sm"
                          style={{ background: 'var(--green-terminal)', color: '#000' }}
                        >
                          <CheckCircle2 size={14} /> Giao thành công (Delivered)
                        </button>
                        <button
                          type="button"
                          onClick={() => handleUpdateFulfillment(viewingOrder, 'delivery_failed', 'Giao hàng không thành công')}
                          className="btn btn-outline btn-sm"
                          style={{ borderColor: 'var(--red-light)', color: 'var(--red-light)' }}
                        >
                          <XCircle size={14} /> Giao thất bại (Chưa nhập kho)
                        </button>
                      </>
                    )}
                    {(viewingOrder.fulfillment_status === 'delivery_failed' || viewingOrder.status === 'cancelled') && viewingOrder.fulfillment_status !== 'returned_to_inventory' && (
                      <button
                        type="button"
                        onClick={() => setReturnModal({ order: viewingOrder, reason: 'Hàng hoàn về kho an toàn', note: '' })}
                        className="btn btn-danger btn-sm"
                      >
                        <RotateCcw size={14} /> Xác nhận hàng đã về kho (Nhập lại tồn)
                      </button>
                    )}
                  </div>
                </div>
              )}
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

      {/* PHASE R3: REASSIGN ORDER MODAL */}
      <Modal
        isOpen={!!reassignModal}
        onClose={() => setReassignModal(null)}
        title={`ĐIỀU CHUYỂN ĐƠN HÀNG #${reassignModal?.order?.order_code}`}
        maxWidth="460px"
      >
        <form onSubmit={handleReassignOrder}>
          <div style={{ color: 'var(--text-secondary)', marginBottom: '1rem', fontSize: '0.85rem' }}>
            Nhân viên hiện tại: <strong>{reassignModal?.order?.assigned_name || 'Chưa phân công'}</strong>
          </div>
          <div className="form-group" style={{ marginBottom: '1rem' }}>
            <label className="form-label" style={{ fontWeight: 600 }}>ID Nhân viên mới (Bắt buộc)</label>
            <input
              type="number"
              className="form-control font-mono"
              required
              placeholder="Nhập ID nhân viên..."
              value={reassignModal?.newStaffId || ''}
              onChange={(e) => setReassignModal({ ...reassignModal, newStaffId: e.target.value })}
            />
          </div>
          <div className="form-group" style={{ marginBottom: '1rem' }}>
            <label className="form-label" style={{ fontWeight: 600 }}>Lý do điều chuyển (Bắt buộc)</label>
            <textarea
              className="form-control"
              rows={2}
              required
              placeholder="Nhập lý do điều chuyển ca / phân công lại..."
              value={reassignModal?.reason || ''}
              onChange={(e) => setReassignModal({ ...reassignModal, reason: e.target.value })}
            />
          </div>
          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.5rem', marginTop: '1.25rem' }}>
            <button type="button" onClick={() => setReassignModal(null)} className="btn btn-outline">
              Hủy
            </button>
            <button type="submit" className="btn btn-primary" disabled={submittingReassign}>
              {submittingReassign ? 'Đang điều chuyển...' : 'Xác Nhận Điều Chuyển'}
            </button>
          </div>
        </form>
      </Modal>

      {/* PHASE R3: NOTIFY TRANSFER MODAL */}
      <Modal
        isOpen={!!transferModal}
        onClose={() => setTransferModal(null)}
        title={`THÔNG BÁO CHUYỂN KHOẢN #${transferModal?.order?.order_code}`}
        maxWidth="480px"
      >
        <form onSubmit={handleNotifyTransfer}>
          <div style={{ padding: '0.6rem', background: 'rgba(59, 130, 246, 0.08)', border: '1px solid var(--blue-light)', borderRadius: 'var(--radius-xs)', marginBottom: '1rem', fontSize: '0.8rem', color: 'var(--blue-light)' }}>
            ℹ️ Sau khi thông báo, đơn hàng chuyển sang trạng thái <strong>Chờ Xác Minh (pending_verification)</strong>. Admin sẽ kiểm tra đối soát trước khi duyệt hoàn tất.
          </div>
          <div className="form-group" style={{ marginBottom: '0.85rem' }}>
            <label className="form-label" style={{ fontWeight: 600 }}>Mã giao dịch / Mã chuyển khoản</label>
            <input
              type="text"
              className="form-control font-mono"
              placeholder="VD: FT2409188828, MB98234..."
              value={transferModal?.transferRef || ''}
              onChange={(e) => setTransferModal({ ...transferModal, transferRef: e.target.value })}
            />
          </div>
          <div className="form-group" style={{ marginBottom: '0.85rem' }}>
            <label className="form-label">Tên ngân hàng chuyển</label>
            <input
              type="text"
              className="form-control"
              placeholder="VD: Vietcombank, Techcombank, MB..."
              value={transferModal?.bankName || ''}
              onChange={(e) => setTransferModal({ ...transferModal, bankName: e.target.value })}
            />
          </div>
          <div className="form-group" style={{ marginBottom: '1rem' }}>
            <label className="form-label">Ghi chú thêm</label>
            <textarea
              className="form-control"
              rows={2}
              placeholder="Ghi chú thêm cho người đối soát..."
              value={transferModal?.note || ''}
              onChange={(e) => setTransferModal({ ...transferModal, note: e.target.value })}
            />
          </div>
          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.5rem', marginTop: '1.25rem' }}>
            <button type="button" onClick={() => setTransferModal(null)} className="btn btn-outline">
              Hủy
            </button>
            <button type="submit" className="btn btn-primary" disabled={submittingTransfer}>
              {submittingTransfer ? 'Đang gửi...' : 'Gửi Thông Báo'}
            </button>
          </div>
        </form>
      </Modal>

      {/* PHASE R3: VERIFY PAYMENT MODAL */}
      <Modal
        isOpen={!!verifyPaymentModal}
        onClose={() => setVerifyPaymentModal(null)}
        title={`XÁC MINH THANH TOÁN #${verifyPaymentModal?.order?.order_code}`}
        maxWidth="480px"
      >
        <form onSubmit={handleVerifyPayment}>
          <div style={{ padding: '0.6rem', background: 'rgba(34, 197, 94, 0.08)', border: '1px solid var(--green-terminal)', borderRadius: 'var(--radius-xs)', marginBottom: '1rem', fontSize: '0.8rem', color: 'var(--green-light)' }}>
            ✓ Admin xác nhận đã kiểm tra đối soát biến động số dư thực tế trong tài khoản ngân hàng.
          </div>
          <div className="form-group" style={{ marginBottom: '0.85rem' }}>
            <label className="form-label" style={{ fontWeight: 600 }}>Mã đối soát sao kê ngân hàng</label>
            <input
              type="text"
              className="form-control font-mono"
              placeholder="VD: REF-BANK-2026-9921..."
              value={verifyPaymentModal?.verifiedRef || ''}
              onChange={(e) => setVerifyPaymentModal({ ...verifyPaymentModal, verifiedRef: e.target.value })}
            />
          </div>
          <div className="form-group" style={{ marginBottom: '1rem' }}>
            <label className="form-label">Ghi chú đối soát</label>
            <textarea
              className="form-control"
              rows={2}
              placeholder="Ghi chú xác minh thanh toán..."
              value={verifyPaymentModal?.note || ''}
              onChange={(e) => setVerifyPaymentModal({ ...verifyPaymentModal, note: e.target.value })}
            />
          </div>
          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.5rem', marginTop: '1.25rem' }}>
            <button type="button" onClick={() => setVerifyPaymentModal(null)} className="btn btn-outline">
              Hủy
            </button>
            <button type="submit" className="btn btn-primary" style={{ background: 'var(--green-terminal)', color: '#000' }} disabled={submittingVerifyPayment}>
              {submittingVerifyPayment ? 'Đang xác minh...' : 'Xác Nhận Đã Nhận Tiền (Mark Paid)'}
            </button>
          </div>
        </form>
      </Modal>

      {/* PHASE R3: RETURN TO INVENTORY MODAL */}
      <Modal
        isOpen={!!returnModal}
        onClose={() => setReturnModal(null)}
        title={`XÁC NHẬN NHẬP LẠI KHO #${returnModal?.order?.order_code}`}
        maxWidth="480px"
      >
        <form onSubmit={handleConfirmReturn}>
          <div style={{ padding: '0.6rem', background: 'rgba(239, 68, 68, 0.08)', border: '1px solid var(--red-light)', borderRadius: 'var(--radius-xs)', marginBottom: '1rem', fontSize: '0.8rem', color: 'var(--red-light)' }}>
            ⚠️ <strong>BẢO VỆ TỒN KHO:</strong> Chỉ thực hiện khi kiện hàng đã thực tế quay về kho cửa hàng và được kiểm đếm nguyên vẹn. Hệ thống có cơ chế chống cộng kho lặp hai lần.
          </div>
          <div className="form-group" style={{ marginBottom: '0.85rem' }}>
            <label className="form-label" style={{ fontWeight: 600 }}>Lý do nhập lại kho (Bắt buộc)</label>
            <input
              type="text"
              className="form-control"
              required
              placeholder="VD: Khách không nghe máy, bưu tá giao thất bại hoàn hàng..."
              value={returnModal?.reason || ''}
              onChange={(e) => setReturnModal({ ...returnModal, reason: e.target.value })}
            />
          </div>
          <div className="form-group" style={{ marginBottom: '1rem' }}>
            <label className="form-label">Ghi chú tình trạng hàng hóa</label>
            <textarea
              className="form-control"
              rows={2}
              placeholder="Tình trạng bao bì, sản phẩm nguyên vẹn..."
              value={returnModal?.note || ''}
              onChange={(e) => setReturnModal({ ...returnModal, note: e.target.value })}
            />
          </div>
          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.5rem', marginTop: '1.25rem' }}>
            <button type="button" onClick={() => setReturnModal(null)} className="btn btn-outline">
              Hủy
            </button>
            <button type="submit" className="btn btn-danger" disabled={submittingReturn}>
              {submittingReturn ? 'Đang nhập kho...' : 'Xác Nhận Nhập Lại Kho'}
            </button>
          </div>
        </form>
      </Modal>

      {/* PHASE R3: REFUND MODAL */}
      <Modal
        isOpen={!!refundModal}
        onClose={() => setRefundModal(null)}
        title={refundModal?.mode === 'confirm' ? `XÁC NHẬN HOÀN TIỀN THỰC TẾ #${refundModal?.order?.order_code}` : `YÊU CẦU HOÀN TIỀN #${refundModal?.order?.order_code}`}
        maxWidth="480px"
      >
        <form onSubmit={refundModal?.mode === 'confirm' ? handleConfirmRefund : handleRequestRefund}>
          <div style={{ padding: '0.6rem', background: 'rgba(245, 158, 11, 0.08)', border: '1px solid var(--amber-primary)', borderRadius: 'var(--radius-xs)', marginBottom: '1rem', fontSize: '0.8rem', color: 'var(--amber-primary)' }}>
            ℹ️ <strong>ĐỘC LẬP TỒN KHO:</strong> Hoàn tiền không tự động nhập lại kho và hoàn hàng không tự động hoàn tiền.
          </div>
          {refundModal?.mode === 'confirm' && (
            <div className="form-group" style={{ marginBottom: '0.85rem' }}>
              <label className="form-label">Mã giao dịch hoàn tiền (Ủy nhiệm chi / Bill chuyển khoản)</label>
              <input
                type="text"
                className="form-control font-mono"
                placeholder="VD: REFUND-TX-88392..."
                value={refundModal?.refundRef || ''}
                onChange={(e) => setRefundModal({ ...refundModal, refundRef: e.target.value })}
              />
            </div>
          )}
          <div className="form-group" style={{ marginBottom: '1rem' }}>
            <label className="form-label" style={{ fontWeight: 600 }}>Lý do hoàn tiền (Bắt buộc)</label>
            <textarea
              className="form-control"
              rows={3}
              required
              placeholder="Nhập lý do hoàn tiền..."
              value={refundModal?.reason || ''}
              onChange={(e) => setRefundModal({ ...refundModal, reason: e.target.value })}
            />
          </div>
          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.5rem', marginTop: '1.25rem' }}>
            <button type="button" onClick={() => setRefundModal(null)} className="btn btn-outline">
              Hủy
            </button>
            <button
              type="submit"
              className={`btn ${refundModal?.mode === 'confirm' ? 'btn-danger' : 'btn-primary'}`}
              disabled={submittingRefund}
            >
              {submittingRefund ? 'Đang xử lý...' : refundModal?.mode === 'confirm' ? 'Xác Nhận Đã Hoàn Tiền' : 'Gửi Yêu Cầu Hoàn Tiền'}
            </button>
          </div>
        </form>
      </Modal>

      {/* PHASE R3: AUDIT LOGS TIMELINE MODAL */}
      <Modal
        isOpen={!!auditLogsModal}
        onClose={() => setAuditLogsModal(null)}
        title={`DIỄN BIẾN & LỊCH SỬ KIỂM TOÁN #${auditLogsModal?.order?.order_code}`}
        maxWidth="640px"
        footer={
          <button onClick={() => setAuditLogsModal(null)} className="btn btn-primary">
            Đóng
          </button>
        }
      >
        {auditLogsModal && (
          <div>
            {auditLogsModal.loading ? (
              <div style={{ textAlign: 'center', padding: '2rem', color: 'var(--text-muted)' }}>
                Đang tải lịch sử kiểm toán...
              </div>
            ) : (!auditLogsModal.logs || auditLogsModal.logs.length === 0) ? (
              <div style={{ textAlign: 'center', padding: '2rem', color: 'var(--text-muted)' }}>
                Chưa có vết kiểm toán nào được ghi nhận cho đơn hàng này.
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem', maxHeight: '450px', overflowY: 'auto', paddingRight: '0.25rem' }}>
                {auditLogsModal.logs.map((log) => (
                  <div
                    key={log.id}
                    style={{
                      padding: '0.75rem',
                      background: 'var(--bg-input)',
                      border: '1px solid var(--border-subtle)',
                      borderRadius: 'var(--radius-xs)',
                      fontSize: '0.8rem',
                    }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.35rem', flexWrap: 'wrap', gap: '0.25rem' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                        <Badge variant="blue">{log.action?.toUpperCase()}</Badge>
                        <span style={{ fontWeight: 600, color: 'var(--text-primary)' }}>
                          {log.user_name || `User #${log.user_id || 'System'}`}
                        </span>
                        {log.user_role && (
                          <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>({log.user_role})</span>
                        )}
                      </div>
                      <span className="font-mono" style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>
                        {log.created_at ? new Date(log.created_at).toLocaleString('vi-VN') : ''}
                      </span>
                    </div>

                    {(log.old_status || log.new_status) && (
                      <div style={{ fontSize: '0.74rem', color: 'var(--text-secondary)', marginBottom: '0.2rem' }}>
                        Trạng thái đơn: <span className="font-mono">{log.old_status || '—'}</span> ➔ <strong className="font-mono" style={{ color: 'var(--amber-primary)' }}>{log.new_status}</strong>
                      </div>
                    )}

                    {(log.old_payment_status || log.new_payment_status) && (
                      <div style={{ fontSize: '0.74rem', color: 'var(--text-secondary)', marginBottom: '0.2rem' }}>
                        Thanh toán: <span className="font-mono">{log.old_payment_status || '—'}</span> ➔ <strong className="font-mono" style={{ color: 'var(--green-terminal)' }}>{log.new_payment_status}</strong>
                      </div>
                    )}

                    {(log.old_fulfillment_status || log.new_fulfillment_status) && (
                      <div style={{ fontSize: '0.74rem', color: 'var(--text-secondary)', marginBottom: '0.2rem' }}>
                        Giao vận: <span className="font-mono">{log.old_fulfillment_status || '—'}</span> ➔ <strong className="font-mono" style={{ color: 'var(--blue-light)' }}>{log.new_fulfillment_status}</strong>
                      </div>
                    )}

                    {log.note && (
                      <div style={{ fontSize: '0.75rem', color: 'var(--text-primary)', marginTop: '0.35rem', fontStyle: 'italic', background: 'var(--bg-surface)', padding: '0.35rem 0.5rem', borderRadius: '4px' }}>
                        "{log.note}"
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
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
