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
    case 'manager':
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
