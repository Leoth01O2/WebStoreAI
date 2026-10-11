import React, { useState, useEffect } from 'react';
import { Users, Search, Plus, Edit2, Phone, Mail, MapPin, ShieldCheck } from 'lucide-react';
import { customersAPI } from '../services/api';
import { useAuth } from '../context/AuthContext';
import { useToast } from '../context/ToastContext';
import { Badge } from '../components/ui/Badge';
import { Modal } from '../components/ui/Modal';

export const CustomersPage = () => {
  const { user, isAdmin, isSuperAdmin } = useAuth();
  const canManage = isAdmin || isSuperAdmin;
  const isStaff = user?.role === 'staff';
  const { addToast } = useToast();

  const [customers, setCustomers] = useState([]);
  const [loading, setLoading] = useState(true);

  // Filters
  const [search, setSearch] = useState('');
  const [groupFilter, setGroupFilter] = useState('');

  // Modals
  const [showModal, setShowModal] = useState(false);
  const [editingCustomer, setEditingCustomer] = useState(null);
  const [customerForm, setCustomerForm] = useState({
    customer_code: '',
    name: '',
    phone: '',
    email: '',
    address: '',
    group_name: 'retail',
  });

  const loadCustomers = async () => {
    try {
      setLoading(true);
      const data = await customersAPI.getCustomers({
        search: search || undefined,
        group_name: groupFilter || undefined,
      });
      setCustomers(data);
    } catch (err) {
      addToast(err.message, 'error');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadCustomers();
  }, [search, groupFilter]);

  const handleOpenAdd = () => {
    setEditingCustomer(null);
    setCustomerForm({
      customer_code: `CUS-${Date.now().toString().slice(-4)}`,
      name: '',
      phone: '',
      email: '',
      address: '',
      group_name: 'retail',
    });
    setShowModal(true);
  };

  const handleOpenEdit = (cust) => {
    setEditingCustomer(cust);
    setCustomerForm({
      customer_code: cust.customer_code,
      name: cust.name,
      phone: cust.phone || '',
      email: cust.email || '',
      address: cust.address || '',
      group_name: cust.group_name || 'retail',
    });
    setShowModal(true);
  };

  const handleSave = async (e) => {
    e.preventDefault();
    try {
      if (editingCustomer) {
        await customersAPI.updateCustomer(editingCustomer.id, customerForm);
        addToast(`Cập nhật thông tin khách hàng "${customerForm.name}" thành công!`, 'success');
      } else {
        await customersAPI.createCustomer(customerForm);
        addToast(`Thêm mới khách hàng "${customerForm.name}" thành công!`, 'success');
      }
      setShowModal(false);
      loadCustomers();
    } catch (err) {
      addToast(err.message, 'error');
    }
  };

  const formatVND = (val) => Number(val || 0).toLocaleString('vi-VN') + ' đ';

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
      {/* Filters & Action Bar */}
      <div className="retro-card">
        <div className="retro-card-header">
          <div className="retro-card-title">
            <Users size={18} />
            <span>QUẢN LÝ KHÁCH HÀNG ({customers.length} KHÁCH)</span>
            {isStaff && (
              <span
                className="badge badge-blue"
                style={{
                  fontSize: '0.68rem',
                  marginLeft: '0.5rem',
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '4px',
                  fontFamily: 'var(--font-mono)',
                }}
                title="Dữ liệu cá nhân (email, địa chỉ) đã được che giấu tự động từ backend"
              >
                <ShieldCheck size={12} /> PII ĐÃ BẢO MẬT
              </span>
            )}
          </div>

          {canManage && (
            <button onClick={handleOpenAdd} className="btn btn-primary btn-sm">
              <Plus size={15} /> Thêm Khách Hàng
            </button>
          )}
        </div>

        <div style={{ padding: '0.85rem 1.25rem', display: 'flex', flexWrap: 'wrap', gap: '0.75rem', alignItems: 'center', background: 'var(--bg-input)' }}>
          <div className="input-with-icon" style={{ minWidth: 'min(100%, 200px)', flex: '1 1 200px' }}>
            <Search size={15} />
            <input
              type="text"
              className="form-control font-mono"
              placeholder="Tìm theo tên, SĐT hoặc mã khách hàng..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </div>

          <select
            className="form-control"
            style={{ flex: '1 1 160px', minWidth: '140px' }}
            value={groupFilter}
            onChange={(e) => setGroupFilter(e.target.value)}
          >
            <option value="">-- Tất cả nhóm khách --</option>
            <option value="vip">Khách VIP</option>
            <option value="retail">Khách lẻ (Retail)</option>
            <option value="wholesale">Khách buôn (Wholesale)</option>
          </select>

          {(search || groupFilter) && (
            <button
              className="btn btn-outline btn-sm"
              onClick={() => {
                setSearch('');
                setGroupFilter('');
              }}
            >
              Đặt lại
            </button>
          )}
        </div>
      </div>

      {/* Customers Table */}
      <div className="table-responsive">
        <table className="retro-table">
          <thead>
            <tr>
              <th>MÃ KHÁCH</th>
              <th>HỌ VÀ TÊN</th>
              <th>SỐ ĐIỆN THOẠI</th>
              <th>EMAIL & ĐỊA CHỈ</th>
              <th style={{ textAlign: 'center' }}>PHÂN NHÓM</th>
              <th style={{ textAlign: 'right' }}>TỔNG CHI TIÊU</th>
              <th style={{ textAlign: 'center' }}>THAO TÁC</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan={7} style={{ textAlign: 'center', padding: '2rem' }}>
                  Đang tải danh sách khách hàng...
                </td>
              </tr>
            ) : customers.length === 0 ? (
              <tr>
                <td colSpan={7} style={{ textAlign: 'center', padding: '2rem', color: 'var(--text-muted)' }}>
                  Không tìm thấy khách hàng nào phù hợp.
                </td>
              </tr>
            ) : (
              customers.map((c) => (
                <tr key={c.id}>
                  <td className="font-mono" style={{ fontWeight: 600, color: 'var(--blue-light)' }}>
                    {c.customer_code}
                  </td>
                  <td style={{ fontWeight: 600 }}>{c.name}</td>
                  <td className="font-mono" style={{ color: 'var(--green-light)' }}>
                    {c.phone ? (
                      <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.3rem' }}>
                        <Phone size={12} /> {c.phone}
                      </span>
                    ) : '—'}
                  </td>
                  <td>
                    {c.email ? (
                      <div style={{ fontSize: '0.78rem', color: 'var(--text-secondary)' }}>
                        <Mail size={12} style={{ display: 'inline', marginRight: '4px' }} />
                        {c.email}
                      </div>
                    ) : null}
                    {c.address ? (
                      <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>
                        <MapPin size={11} style={{ display: 'inline', marginRight: '4px' }} />
                        {c.address}
                      </div>
                    ) : (
                      isStaff ? (
                        <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', fontStyle: 'italic' }}>
                          [Địa chỉ đã bảo mật]
                        </div>
                      ) : null
                    )}
                    {!c.email && !c.address && !isStaff && '—'}
                  </td>
                  <td style={{ textAlign: 'center' }}>
                    {c.group_name === 'vip' ? (
                      <Badge variant="amber">VIP</Badge>
                    ) : c.group_name === 'wholesale' ? (
                      <Badge variant="blue">Buôn</Badge>
                    ) : (
                      <Badge variant="green">Lẻ</Badge>
                    )}
                  </td>
                  <td className="currency" style={{ textAlign: 'right', fontWeight: 700, color: 'var(--amber-primary)' }}>
                    {formatVND(c.total_spent)}
                  </td>
                  <td style={{ textAlign: 'center' }}>
                    {canManage ? (
                      <button
                        onClick={() => handleOpenEdit(c)}
                        className="btn btn-outline btn-icon btn-sm"
                        title="Sửa thông tin khách hàng"
                      >
                        <Edit2 size={13} />
                      </button>
                    ) : (
                      <span className="badge badge-muted" style={{ fontSize: '0.68rem' }}>
                        Chỉ xem
                      </span>
                    )}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* CREATE / EDIT CUSTOMER MODAL */}
      <Modal
        isOpen={showModal}
        onClose={() => setShowModal(false)}
        title={editingCustomer ? 'CẬP NHẬT THÔNG TIN KHÁCH HÀNG' : 'THÊM MỚI KHÁCH HÀNG'}
        maxWidth="480px"
      >
        <form onSubmit={handleSave}>
          <div className="form-grid-2">
            <div className="form-group">
              <label className="form-label">Mã khách hàng (*)</label>
              <input
                type="text"
                required
                className="form-control font-mono"
                value={customerForm.customer_code}
                onChange={(e) => setCustomerForm({ ...customerForm, customer_code: e.target.value })}
              />
            </div>
            <div className="form-group">
              <label className="form-label">Phân nhóm</label>
              <select
                className="form-control"
                value={customerForm.group_name}
                onChange={(e) => setCustomerForm({ ...customerForm, group_name: e.target.value })}
              >
                <option value="retail">Khách lẻ (Retail)</option>
                <option value="vip">Khách VIP</option>
                <option value="wholesale">Khách buôn (Wholesale)</option>
              </select>
            </div>
          </div>

          <div className="form-group">
            <label className="form-label">Họ và tên (*)</label>
            <input
              type="text"
              required
              className="form-control"
              value={customerForm.name}
              onChange={(e) => setCustomerForm({ ...customerForm, name: e.target.value })}
            />
          </div>

          <div className="form-grid-2">
            <div className="form-group">
              <label className="form-label">Số điện thoại (*)</label>
              <input
                type="tel"
                required
                className="form-control font-mono"
                value={customerForm.phone}
                onChange={(e) => setCustomerForm({ ...customerForm, phone: e.target.value })}
              />
            </div>
            <div className="form-group">
              <label className="form-label">Email</label>
              <input
                type="email"
                className="form-control"
                value={customerForm.email}
                onChange={(e) => setCustomerForm({ ...customerForm, email: e.target.value })}
              />
            </div>
          </div>

          <div className="form-group">
            <label className="form-label">Địa chỉ</label>
            <input
              type="text"
              className="form-control"
              value={customerForm.address}
              onChange={(e) => setCustomerForm({ ...customerForm, address: e.target.value })}
            />
          </div>

          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.5rem', marginTop: '1.25rem' }}>
            <button type="button" onClick={() => setShowModal(false)} className="btn btn-outline">
              Hủy
            </button>
            <button type="submit" className="btn btn-primary">
              {editingCustomer ? 'Lưu Thay Đổi' : 'Tạo Khách Hàng'}
            </button>
          </div>
        </form>
      </Modal>
    </div>
  );
};
