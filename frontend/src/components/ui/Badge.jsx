import React from 'react';

export const Badge = ({ children, variant = 'muted', className = '' }) => {
  return (
    <span className={`badge badge-${variant} ${className}`}>
      {children}
    </span>
  );
};

export const StockBadge = ({ stock, minAlert = 5, status = 'active' }) => {
  if (status !== 'active') {
    return <Badge variant="muted">Ngừng bán</Badge>;
  }
  if (stock <= 0) {
    return <Badge variant="red">Hết hàng (0)</Badge>;
  }
  if (stock <= minAlert) {
    return <Badge variant="amber">Sắp hết ({stock})</Badge>;
  }
  return <Badge variant="green">Còn {stock}</Badge>;
};

export const RoleBadge = ({ role }) => {
  switch (role) {
    case 'superadmin':
      return <Badge variant="blue">Chủ Cửa Hàng (SuperAdmin)</Badge>;
    case 'admin':
      return <Badge variant="amber">Quản Trị Viên (Admin)</Badge>;
    case 'staff':
      return <Badge variant="green">Thu Ngân / Nhân Viên</Badge>;
    case 'customer':
      return <Badge variant="muted">Khách Hàng</Badge>;
    default:
      return <Badge variant="muted">{role}</Badge>;
  }
};

export const ORDER_STATUS_CONFIG = {
  pending: { label: 'Chờ duyệt', variant: 'amber' },
  admin_approved: { label: 'Đã duyệt', variant: 'blue' },
  processing: { label: 'Đang xử lý', variant: 'amber' },
  completed: { label: 'Hoàn thành', variant: 'green' },
  rejected: { label: 'Đã từ chối', variant: 'red' },
  cancelled: { label: 'Đã hủy', variant: 'red' },
};

export const OrderStatusBadge = ({ status }) => {
  const config = ORDER_STATUS_CONFIG[status] || {
    label: status || 'Chưa xác định',
    variant: 'muted',
  };
  return <Badge variant={config.variant}>{config.label}</Badge>;
};

export const PAYMENT_STATUS_CONFIG = {
  unpaid: { label: 'Chưa thanh toán', variant: 'amber' },
  pending_verification: { label: 'Chờ xác minh', variant: 'blue' },
  paid: { label: 'Đã thanh toán', variant: 'green' },
  refund_pending: { label: 'Chờ hoàn tiền', variant: 'amber' },
  refunded: { label: 'Đã hoàn tiền', variant: 'red' },
  unverified_legacy: { label: 'Lịch sử chưa đối soát', variant: 'muted' },
  pending: { label: 'Chờ thanh toán', variant: 'amber' },
  completed: { label: 'Đã thanh toán', variant: 'green' },
};

export const PaymentStatusBadge = ({ status }) => {
  const config = PAYMENT_STATUS_CONFIG[status] || {
    label: status || 'Chưa xác định',
    variant: 'muted',
  };
  return <Badge variant={config.variant}>{config.label}</Badge>;
};

export const FULFILLMENT_STATUS_CONFIG = {
  unfulfilled: { label: 'Chưa giao hàng', variant: 'amber' },
  packing: { label: 'Đang đóng gói', variant: 'blue' },
  shipping: { label: 'Đang giao hàng', variant: 'blue' },
  delivered: { label: 'Đã giao hàng', variant: 'green' },
  delivery_failed: { label: 'Giao thất bại', variant: 'red' },
  returned_to_inventory: { label: 'Đã nhập lại kho', variant: 'muted' },
  legacy_unknown: { label: 'Lịch sử chưa rõ', variant: 'muted' },
};

export const FulfillmentStatusBadge = ({ status }) => {
  const config = FULFILLMENT_STATUS_CONFIG[status] || {
    label: status || 'Chưa xác định',
    variant: 'muted',
  };
  return <Badge variant={config.variant}>{config.label}</Badge>;
};

