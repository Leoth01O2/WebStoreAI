import React from 'react';
import { Printer, CheckCircle, ArrowRight } from 'lucide-react';
import { Modal } from './Modal';

export const ReceiptModal = ({ isOpen, onClose, order, onNewOrder }) => {
  if (!order) return null;

  const handlePrint = () => {
    window.print();
  };

  const formatVND = (val) => {
    return Number(val || 0).toLocaleString('vi-VN') + ' đ';
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title="HÓA ĐƠN BÁN HÀNG"
      maxWidth="480px"
      footer={
        <>
          <button onClick={handlePrint} className="btn btn-outline">
            <Printer size={16} /> In Hóa Đơn
          </button>
          <button
            onClick={() => {
              onClose();
              if (onNewOrder) onNewOrder();
            }}
            className="btn btn-primary"
          >
            Đơn Mới <ArrowRight size={16} />
          </button>
        </>
      }
    >
      <div style={{ textAlign: 'center', marginBottom: '1rem' }}>
        <CheckCircle size={36} color="var(--green-terminal)" style={{ margin: '0 auto 0.5rem' }} />
        <div style={{ color: 'var(--green-light)', fontWeight: 'bold', fontSize: '1rem' }}>
          GIAO DỊCH HOÀN TẤT & TRỪ KHO THÀNH CÔNG
        </div>
      </div>

      <div className="printable-receipt" id="print-area">
        <div className="receipt-header">
          <div className="receipt-title">STOREFLOW AI</div>
          <div style={{ fontSize: '0.75rem', marginTop: '0.2rem' }}>HỆ THỐNG QUẢN LÝ BÁN LẺ & POS THÔNG MINH</div>
          <div style={{ fontSize: '0.7rem', color: '#444' }}>Đ/c: 123 Phố Công Nghệ, TP. Hồ Chí Minh</div>
          <div style={{ fontSize: '0.7rem', marginTop: '0.4rem', fontWeight: 'bold' }}>
            HÓA ĐƠN THANH TOÁN
          </div>
        </div>

        <div style={{ fontSize: '0.75rem', lineHeight: '1.4' }}>
          <div><strong>Mã HĐ:</strong> {order.order_code}</div>
          <div><strong>Thời gian:</strong> {order.created_at ? new Date(order.created_at).toLocaleString('vi-VN') : new Date().toLocaleString('vi-VN')}</div>
          <div><strong>Thu ngân:</strong> {order.user_name || 'Nhân viên'}</div>
          <div><strong>Khách hàng:</strong> {order.customer_name || 'Khách vãng lai'} {order.customer_phone ? `(${order.customer_phone})` : ''}</div>
        </div>

        <table className="receipt-table">
          <thead>
            <tr>
              <th>Mặt hàng</th>
              <th style={{ textAlign: 'center' }}>SL</th>
              <th style={{ textAlign: 'right' }}>Đ.Giá</th>
              <th style={{ textAlign: 'right' }}>T.Tiền</th>
            </tr>
          </thead>
          <tbody>
            {(order.items || []).map((item, idx) => (
              <tr key={idx}>
                <td>
                  <div>{item.product_name || `SP #${item.product_id}`}</div>
                  <div style={{ fontSize: '0.65rem', color: '#666' }}>{item.product_sku}</div>
                </td>
                <td style={{ textAlign: 'center' }}>{item.quantity}</td>
                <td style={{ textAlign: 'right' }}>{formatVND(item.unit_price)}</td>
                <td style={{ textAlign: 'right', fontWeight: 'bold' }}>{formatVND(item.subtotal)}</td>
              </tr>
            ))}
          </tbody>
        </table>

        <div className="receipt-footer">
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.2rem' }}>
            <span>Tổng tiền hàng:</span>
            <span>{formatVND(order.total_amount)}</span>
          </div>
          {order.discount_amount > 0 && (
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.2rem', color: '#c00' }}>
              <span>Chiết khấu:</span>
              <span>-{formatVND(order.discount_amount)}</span>
            </div>
          )}
          <div style={{ display: 'flex', justifyContent: 'space-between', fontWeight: 'bold', fontSize: '1rem', margin: '0.4rem 0' }}>
            <span>THANH TOÁN:</span>
            <span>{formatVND(order.final_amount)}</span>
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.75rem' }}>
            <span>Phương thức:</span>
            <span>{order.payment_method === 'cash' ? 'Tiền mặt' : order.payment_method === 'transfer' ? 'Chuyển khoản' : 'Thẻ'}</span>
          </div>
          {order.cash_given && (
            <>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.75rem', marginTop: '0.2rem' }}>
                <span>Tiền khách đưa:</span>
                <span>{formatVND(order.cash_given)}</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.75rem', fontWeight: 'bold', marginTop: '0.2rem' }}>
                <span>Tiền thừa trả khách:</span>
                <span>{formatVND(order.cash_given - order.final_amount)}</span>
              </div>
            </>
          )}

          <div style={{ textAlign: 'center', marginTop: '1.2rem', fontSize: '0.75rem', fontStyle: 'italic' }}>
            Cảm ơn Quý khách & Hẹn gặp lại!
          </div>
        </div>
      </div>
    </Modal>
  );
};
