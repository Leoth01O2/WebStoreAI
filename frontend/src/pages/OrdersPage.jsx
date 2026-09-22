import React, { useState, useEffect } from 'react';
import {
  FileText,
  Search,
  Eye,
  XCircle,
  Printer,
  Calendar,
  Filter,
} from 'lucide-react';
import { ordersAPI } from '../services/api';
import { useAuth } from '../context/AuthContext';
import { useToast } from '../context/ToastContext';
import { Badge } from '../components/ui/Badge';
import { Modal } from '../components/ui/Modal';
import { ReceiptModal } from '../components/ui/ReceiptModal';

export const OrdersPage = () => {
  const { isAdmin, isSuperAdmin, isManager } = useAuth();
  const { addToast } = useToast();
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

  const handleCancelOrder = async (e) => {
    e.preventDefault();
    if (!cancellingOrder) return;
    setSubmittingCancel(true);
    try {
      await ordersAPI.cancelOrder(cancellingOrder.id, cancelReason);
      addToast(`Đã hủy hóa đơn ${cancellingOrder.order_code} và hoàn trả tồn kho thành công!`, 'success');
      setCancellingOrder(null);
      setViewingOrder(null);
      loadOrders();
    } catch (err) {
      addToast(err.message, 'error');
    } finally {
      setSubmittingCancel(false);
    }
  };

  const formatVND = (val) => Number(val || 0).toLocaleString('vi-VN') + ' đ';

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
      {/* Filters bar */}
      <div className="retro-card">
        <div className="retro-card-header">
          <div className="retro-card-title">
            <FileText size={18} />
            <span>QUẢN LÝ HÓA ĐƠN BÁN HÀNG ({orders.length} ĐƠN)</span>
          </div>
        </div>

        <div style={{ padding: '0.85rem 1.25rem', display: 'flex', flexWrap: 'wrap', gap: '0.75rem', alignItems: 'center', background: 'var(--bg-input)' }}>
          <div className="input-with-icon" style={{ minWidth: '220px', flex: 1 }}>
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
            style={{ width: '160px' }}
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
          >
            <option value="">-- Tất cả trạng thái --</option>
            <option value="completed">Đã hoàn thành</option>
            <option value="cancelled">Đã hủy bỏ</option>
          </select>

          <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
            <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Từ ngày:</span>
            <input
              type="date"
              className="form-control font-mono"
              style={{ width: '135px', padding: '0.35rem' }}
              value={startDate}
              onChange={(e) => setStartDate(e.target.value)}
            />
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
            <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Đến ngày:</span>
            <input
              type="date"
              className="form-control font-mono"
              style={{ width: '135px', padding: '0.35rem' }}
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

      {/* Orders Table */}
      <div className="table-responsive">
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
                  <td className="currency" style={{ textAlign: 'right', fontWeight: 700, color: o.status === 'cancelled' ? 'var(--text-muted)' : 'var(--green-terminal)' }}>
                    {formatVND(o.final_amount)}
                  </td>
                  <td style={{ textAlign: 'center' }}>
                    <Badge variant={o.status === 'completed' ? 'green' : 'red'}>
                      {o.status === 'completed' ? 'Hoàn thành' : 'Đã hủy'}
                    </Badge>
                  </td>
                  <td style={{ textAlign: 'center' }}>
                    <div style={{ display: 'flex', justifyContent: 'center', gap: '0.35rem' }}>
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
                    </div>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* VIEW ORDER DETAIL MODAL */}
      <Modal
        isOpen={!!viewingOrder}
        onClose={() => setViewingOrder(null)}
        title={`CHI TIẾT HÓA ĐƠN #${viewingOrder?.order_code}`}
        maxWidth="600px"
        footer={
          <>
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
            <button onClick={() => setViewingOrder(null)} className="btn btn-primary">
              Đóng
            </button>
          </>
        }
      >
        {viewingOrder && (
          <div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.6rem', marginBottom: '1rem', fontSize: '0.85rem' }}>
              <div><strong>Mã HĐ:</strong> <span className="font-mono">{viewingOrder.order_code}</span></div>
              <div><strong>Thời gian:</strong> {new Date(viewingOrder.created_at).toLocaleString('vi-VN')}</div>
              <div><strong>Khách hàng:</strong> {viewingOrder.customer_name || 'Khách vãng lai'}</div>
              <div><strong>Thu ngân:</strong> {viewingOrder.user_name || '—'}</div>
              <div><strong>Phương thức:</strong> {viewingOrder.payment_method.toUpperCase()}</div>
              <div>
                <strong>Trạng thái:</strong>{' '}
                <Badge variant={viewingOrder.status === 'completed' ? 'green' : 'red'}>
                  {viewingOrder.status === 'completed' ? 'Đã hoàn tất' : 'Đã hủy'}
                </Badge>
              </div>
            </div>

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

      {/* RECEIPT MODAL */}
      <ReceiptModal
        isOpen={!!receiptOrder}
        onClose={() => setReceiptOrder(null)}
        order={receiptOrder}
      />
    </div>
  );
};
