import React, { useState, useEffect } from 'react';
import {
  Truck,
  History,
  Plus,
  Search,
  Eye,
  Trash2,
  Calendar,
  Layers,
  ArrowUpRight,
  ArrowDownLeft,
  RotateCcw,
} from 'lucide-react';
import { purchasesAPI, inventoryAPI, productsAPI } from '../services/api';
import { useToast } from '../context/ToastContext';
import { Badge } from '../components/ui/Badge';
import { Modal } from '../components/ui/Modal';

export const PurchasesPage = () => {
  const { addToast } = useToast();

  const [activeTab, setActiveTab] = useState('receipts'); // 'receipts' | 'logs'

  // Purchases list
  const [purchases, setPurchases] = useState([]);
  const [logs, setLogs] = useState([]);
  const [products, setProducts] = useState([]);
  const [loading, setLoading] = useState(true);

  // Modals
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [viewingReceipt, setViewingReceipt] = useState(null);

  // New Purchase Form
  const [supplierName, setSupplierName] = useState('');
  const [note, setNote] = useState('');
  const [purchaseItems, setPurchaseItems] = useState([
    { product_id: '', quantity: 1, import_price: 0 },
  ]);
  const [submitting, setSubmitting] = useState(false);

  // Logs filters
  const [logTypeFilter, setLogTypeFilter] = useState('');
  const [logRefSearch, setLogRefSearch] = useState('');

  const loadData = async () => {
    try {
      setLoading(true);
      if (activeTab === 'receipts') {
        const [receiptData, prods] = await Promise.all([
          purchasesAPI.getPurchases(),
          productsAPI.getProducts(),
        ]);
        setPurchases(receiptData);
        setProducts(prods);
      } else {
        const logData = await inventoryAPI.getLogs({
          change_type: logTypeFilter || undefined,
          reference_code: logRefSearch || undefined,
        });
        setLogs(logData);
      }
    } catch (err) {
      addToast(err.message, 'error');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, [activeTab, logTypeFilter, logRefSearch]);

  const handleAddItemRow = () => {
    setPurchaseItems((prev) => [
      ...prev,
      { product_id: products[0]?.id || '', quantity: 1, import_price: products[0]?.cost_price || 0 },
    ]);
  };

  const handleRemoveItemRow = (idx) => {
    setPurchaseItems((prev) => prev.filter((_, i) => i !== idx));
  };

  const handleItemChange = (index, field, value) => {
    setPurchaseItems((prev) => {
      const updated = [...prev];
      updated[index][field] = value;

      // Auto fill default cost_price when product changed
      if (field === 'product_id') {
        const prod = products.find((p) => p.id === Number(value));
        if (prod) {
          updated[index].import_price = prod.cost_price;
        }
      }
      return updated;
    });
  };

  const handleCreatePurchase = async (e) => {
    e.preventDefault();
    if (!supplierName.trim()) {
      addToast('Vui lòng nhập tên nhà cung cấp', 'warning');
      return;
    }

    if (purchaseItems.length === 0 || purchaseItems.some((i) => !i.product_id || i.quantity <= 0)) {
      addToast('Vui lòng chọn sản phẩm và số lượng nhập hợp lệ', 'warning');
      return;
    }

    setSubmitting(true);
    try {
      const payload = {
        supplier_name: supplierName.trim(),
        note: note || null,
        items: purchaseItems.map((item) => ({
          product_id: Number(item.product_id),
          quantity: Number(item.quantity),
          import_price: Number(item.import_price),
        })),
      };

      const res = await purchasesAPI.createPurchase(payload);
      addToast(`Tạo phiếu nhập ${res.receipt_code} và tăng tồn kho thành công!`, 'success');
      setShowCreateModal(false);
      setSupplierName('');
      setNote('');
      setPurchaseItems([{ product_id: '', quantity: 1, import_price: 0 }]);
      loadData();
    } catch (err) {
      addToast(err.message, 'error');
    } finally {
      setSubmitting(false);
    }
  };

  const formatVND = (val) => Number(val || 0).toLocaleString('vi-VN') + ' đ';

  const totalReceiptCost = purchaseItems.reduce(
    (sum, item) => sum + Number(item.quantity || 0) * Number(item.import_price || 0),
    0
  );

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
      {/* Tab Switcher & Top Action */}
      <div className="retro-card">
        <div className="retro-card-header">
          <div style={{ display: 'flex', gap: '0.5rem' }}>
            <button
              onClick={() => setActiveTab('receipts')}
              className={`btn btn-sm ${activeTab === 'receipts' ? 'btn-primary' : 'btn-outline'}`}
            >
              <Truck size={15} /> Phiếu Nhập Hàng ({purchases.length})
            </button>
            <button
              onClick={() => setActiveTab('logs')}
              className={`btn btn-sm ${activeTab === 'logs' ? 'btn-primary' : 'btn-outline'}`}
            >
              <History size={15} /> Nhật Ký Biến Động Kho (Logs)
            </button>
          </div>

          {activeTab === 'receipts' && (
            <button
              onClick={() => {
                if (products.length > 0) {
                  setPurchaseItems([
                    { product_id: products[0].id, quantity: 5, import_price: products[0].cost_price },
                  ]);
                }
                setShowCreateModal(true);
              }}
              className="btn btn-primary btn-sm"
            >
              <Plus size={15} /> Lập Phiếu Nhập Hàng Mới
            </button>
          )}
        </div>

        {/* Logs Filter Bar */}
        {activeTab === 'logs' && (
          <div style={{ padding: '0.85rem 1.25rem', display: 'flex', flexWrap: 'wrap', gap: '0.75rem', alignItems: 'center', background: 'var(--bg-input)' }}>
            <div className="input-with-icon" style={{ minWidth: '220px', flex: 1 }}>
              <Search size={15} />
              <input
                type="text"
                className="form-control font-mono"
                placeholder="Tìm theo mã đơn hoặc mã phiếu nhập..."
                value={logRefSearch}
                onChange={(e) => setLogRefSearch(e.target.value)}
              />
            </div>

            <select
              className="form-control"
              style={{ width: '200px' }}
              value={logTypeFilter}
              onChange={(e) => setLogTypeFilter(e.target.value)}
            >
              <option value="">-- Tất cả loại biến động --</option>
              <option value="import">Nhập hàng (Import)</option>
              <option value="sale">Bán hàng POS (Sale)</option>
              <option value="return_cancel">Hoàn kho do hủy đơn (Return)</option>
            </select>

            {(logRefSearch || logTypeFilter) && (
              <button
                className="btn btn-outline btn-sm"
                onClick={() => {
                  setLogRefSearch('');
                  setLogTypeFilter('');
                }}
              >
                Đặt lại
              </button>
            )}
          </div>
        )}
      </div>

      {/* PURCHASE RECEIPTS TABLE */}
      {activeTab === 'receipts' && (
        <div className="table-responsive">
          <table className="retro-table">
            <thead>
              <tr>
                <th>MÃ PHIẾU</th>
                <th>THỜI GIAN NHẬP</th>
                <th>NHÀ CUNG CẤP</th>
                <th>NGƯỜI LẬP</th>
                <th style={{ textAlign: 'right' }}>TỔNG TIỀN NHẬP</th>
                <th style={{ textAlign: 'center' }}>TRẠNG THÁI</th>
                <th style={{ textAlign: 'center' }}>CHI TIẾT</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan={7} style={{ textAlign: 'center', padding: '2rem' }}>
                    Đang nạp danh sách phiếu nhập kho...
                  </td>
                </tr>
              ) : purchases.length === 0 ? (
                <tr>
                  <td colSpan={7} style={{ textAlign: 'center', padding: '2rem', color: 'var(--text-muted)' }}>
                    Chưa có phiếu nhập hàng nào. Bấm "+ Lập phiếu nhập hàng mới" để tạo.
                  </td>
                </tr>
              ) : (
                purchases.map((r) => (
                  <tr key={r.id}>
                    <td className="font-mono" style={{ fontWeight: 700, color: 'var(--amber-primary)' }}>
                      {r.receipt_code}
                    </td>
                    <td className="font-mono" style={{ fontSize: '0.78rem', color: 'var(--text-secondary)' }}>
                      {r.created_at ? new Date(r.created_at).toLocaleString('vi-VN') : '—'}
                    </td>
                    <td style={{ fontWeight: 600 }}>{r.supplier_name}</td>
                    <td>{r.user_name || '—'}</td>
                    <td className="currency" style={{ textAlign: 'right', fontWeight: 700, color: 'var(--blue-light)' }}>
                      {formatVND(r.total_amount)}
                    </td>
                    <td style={{ textAlign: 'center' }}>
                      <Badge variant="green">Đã nhập kho</Badge>
                    </td>
                    <td style={{ textAlign: 'center' }}>
                      <button
                        onClick={() => setViewingReceipt(r)}
                        className="btn btn-outline btn-icon btn-sm"
                        title="Xem danh sách sản phẩm nhập"
                      >
                        <Eye size={13} />
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      )}

      {/* INVENTORY AUDIT LOGS TABLE */}
      {activeTab === 'logs' && (
        <div className="table-responsive">
          <table className="retro-table">
            <thead>
              <tr>
                <th>THỜI GIAN</th>
                <th>MẶT HÀNG</th>
                <th>LOẠI BIẾN ĐỘNG</th>
                <th>MÃ THAM CHIẾU</th>
                <th style={{ textAlign: 'center' }}>TỒN TRƯỚC</th>
                <th style={{ textAlign: 'center' }}>BIẾN ĐỘNG</th>
                <th style={{ textAlign: 'center' }}>TỒN SAU</th>
                <th>GHI CHÚ</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan={8} style={{ textAlign: 'center', padding: '2rem' }}>
                    Đang nạp dữ liệu nhật ký kho...
                  </td>
                </tr>
              ) : logs.length === 0 ? (
                <tr>
                  <td colSpan={8} style={{ textAlign: 'center', padding: '2rem', color: 'var(--text-muted)' }}>
                    Không có bản ghi nhật ký biến động kho nào phù hợp.
                  </td>
                </tr>
              ) : (
                logs.map((l) => {
                  const isPositive = l.change_quantity > 0;
                  return (
                    <tr key={l.id}>
                      <td className="font-mono" style={{ fontSize: '0.78rem', color: 'var(--text-secondary)' }}>
                        {l.created_at ? new Date(l.created_at).toLocaleString('vi-VN') : '—'}
                      </td>
                      <td>
                        <div style={{ fontWeight: 600 }}>{l.product_name}</div>
                        <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
                          {l.product_sku}
                        </div>
                      </td>
                      <td>
                        {l.change_type === 'import' && (
                          <span className="badge badge-blue">
                            <ArrowDownLeft size={12} /> Nhập hàng
                          </span>
                        )}
                        {l.change_type === 'sale' && (
                          <span className="badge badge-amber">
                            <ArrowUpRight size={12} /> Bán hàng POS
                          </span>
                        )}
                        {l.change_type === 'return_cancel' && (
                          <span className="badge badge-green">
                            <RotateCcw size={12} /> Hoàn hủy đơn
                          </span>
                        )}
                      </td>
                      <td className="font-mono" style={{ fontWeight: 600, color: 'var(--text-primary)' }}>
                        {l.reference_code || '—'}
                      </td>
                      <td className="font-mono" style={{ textAlign: 'center' }}>{l.quantity_before}</td>
                      <td
                        className="font-mono"
                        style={{
                          textAlign: 'center',
                          fontWeight: 700,
                          color: isPositive ? 'var(--green-terminal)' : 'var(--red-light)',
                        }}
                      >
                        {isPositive ? `+${l.change_quantity}` : l.change_quantity}
                      </td>
                      <td className="font-mono" style={{ textAlign: 'center', fontWeight: 700 }}>
                        {l.quantity_after}
                      </td>
                      <td style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>
                        {l.note || '—'}
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      )}

      {/* CREATE PURCHASE RECEIPT MODAL */}
      <Modal
        isOpen={showCreateModal}
        onClose={() => setShowCreateModal(false)}
        title="LẬP PHIẾU NHẬP HÀNG MỚI"
        maxWidth="680px"
      >
        <form onSubmit={handleCreatePurchase}>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem' }}>
            <div className="form-group">
              <label className="form-label">Nhà cung cấp (*)</label>
              <input
                type="text"
                required
                className="form-control"
                placeholder="Tên nhà cung cấp / Tổng kho phân phối..."
                value={supplierName}
                onChange={(e) => setSupplierName(e.target.value)}
              />
            </div>
            <div className="form-group">
              <label className="form-label">Ghi chú phiếu nhập</label>
              <input
                type="text"
                className="form-control"
                placeholder="Số hợp đồng, ghi chú đợt hàng..."
                value={note}
                onChange={(e) => setNote(e.target.value)}
              />
            </div>
          </div>

          <div style={{ marginTop: '0.5rem', marginBottom: '0.5rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ fontSize: '0.82rem', fontWeight: 700, color: 'var(--amber-primary)', textTransform: 'uppercase' }}>
              DANH SÁCH MẶT HÀNG NHẬP KHO:
            </span>
            <button
              type="button"
              onClick={handleAddItemRow}
              className="btn btn-outline btn-sm"
            >
              <Plus size={13} /> Thêm dòng
            </button>
          </div>

          <div style={{ maxHeight: '250px', overflowY: 'auto', border: '1px solid var(--border-subtle)', borderRadius: 'var(--radius-xs)', padding: '0.5rem', background: 'var(--bg-input)' }}>
            {purchaseItems.map((item, idx) => (
              <div
                key={idx}
                style={{
                  display: 'grid',
                  gridTemplateColumns: '2fr 1fr 1.2fr auto',
                  gap: '0.5rem',
                  alignItems: 'center',
                  marginBottom: '0.5rem',
                  background: 'var(--bg-card)',
                  padding: '0.4rem',
                  borderRadius: 'var(--radius-xs)',
                  border: '1px solid var(--border-subtle)',
                }}
              >
                <select
                  className="form-control"
                  style={{ fontSize: '0.8rem' }}
                  required
                  value={item.product_id}
                  onChange={(e) => handleItemChange(idx, 'product_id', e.target.value)}
                >
                  <option value="">-- Chọn sản phẩm --</option>
                  {products.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.name} ({p.sku})
                    </option>
                  ))}
                </select>

                <input
                  type="number"
                  min="1"
                  required
                  placeholder="Số lượng"
                  className="form-control font-mono"
                  style={{ fontSize: '0.8rem', textAlign: 'center' }}
                  value={item.quantity}
                  onChange={(e) => handleItemChange(idx, 'quantity', e.target.value)}
                />

                <input
                  type="number"
                  min="0"
                  step="1000"
                  required
                  placeholder="Giá nhập"
                  className="form-control font-mono"
                  style={{ fontSize: '0.8rem', textAlign: 'right' }}
                  value={item.import_price}
                  onChange={(e) => handleItemChange(idx, 'import_price', e.target.value)}
                />

                {purchaseItems.length > 1 && (
                  <button
                    type="button"
                    onClick={() => handleRemoveItemRow(idx)}
                    className="btn btn-outline btn-icon btn-sm"
                    style={{ width: '28px', height: '28px', border: 'none', color: 'var(--red-light)' }}
                  >
                    <Trash2 size={13} />
                  </button>
                )}
              </div>
            ))}
          </div>

          <div style={{ marginTop: '0.75rem', textAlign: 'right', fontSize: '1rem', fontWeight: 700, color: 'var(--blue-light)' }}>
            Tổng giá trị nhập kho: <span className="font-mono">{formatVND(totalReceiptCost)}</span>
          </div>

          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.5rem', marginTop: '1.25rem' }}>
            <button type="button" onClick={() => setShowCreateModal(false)} className="btn btn-outline">
              Hủy
            </button>
            <button type="submit" className="btn btn-primary" disabled={submitting}>
              {submitting ? 'Đang cập nhật kho...' : 'Lưu & Tăng Tồn Kho'}
            </button>
          </div>
        </form>
      </Modal>

      {/* VIEW RECEIPT DETAIL MODAL */}
      <Modal
        isOpen={!!viewingReceipt}
        onClose={() => setViewingReceipt(null)}
        title={`CHI TIẾT PHIẾU NHẬP #${viewingReceipt?.receipt_code}`}
        maxWidth="580px"
      >
        {viewingReceipt && (
          <div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.6rem', marginBottom: '1rem', fontSize: '0.85rem' }}>
              <div><strong>Mã phiếu:</strong> <span className="font-mono">{viewingReceipt.receipt_code}</span></div>
              <div><strong>Thời gian:</strong> {new Date(viewingReceipt.created_at).toLocaleString('vi-VN')}</div>
              <div><strong>Nhà cung cấp:</strong> {viewingReceipt.supplier_name}</div>
              <div><strong>Người nhập:</strong> {viewingReceipt.user_name || '—'}</div>
            </div>

            {viewingReceipt.note && (
              <div style={{ padding: '0.5rem', background: 'var(--bg-input)', border: '1px solid var(--border-subtle)', borderRadius: 'var(--radius-xs)', marginBottom: '1rem', fontSize: '0.8rem' }}>
                <strong>Ghi chú:</strong> {viewingReceipt.note}
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
                  <th style={{ textAlign: 'right' }}>Giá nhập</th>
                  <th style={{ textAlign: 'right' }}>Thành tiền</th>
                </tr>
              </thead>
              <tbody>
                {(viewingReceipt.items || []).map((item, idx) => (
                  <tr key={idx}>
                    <td>
                      <div>{item.product_name}</div>
                      <div style={{ fontSize: '0.68rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>{item.product_sku}</div>
                    </td>
                    <td style={{ textAlign: 'center', fontFamily: 'var(--font-mono)', fontWeight: 600 }}>{item.quantity}</td>
                    <td style={{ textAlign: 'right', fontFamily: 'var(--font-mono)' }}>{formatVND(item.import_price)}</td>
                    <td style={{ textAlign: 'right', fontFamily: 'var(--font-mono)', fontWeight: 700, color: 'var(--blue-light)' }}>{formatVND(item.subtotal)}</td>
                  </tr>
                ))}
              </tbody>
            </table>

            <div style={{ marginTop: '1rem', textAlign: 'right', fontSize: '1.15rem', fontWeight: 800, color: 'var(--blue-light)' }}>
              Tổng tiền phiếu nhập: <span className="font-mono">{formatVND(viewingReceipt.total_amount)}</span>
            </div>

            <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: '1.25rem' }}>
              <button onClick={() => setViewingReceipt(null)} className="btn btn-primary">
                Đóng
              </button>
            </div>
          </div>
        )}
      </Modal>
    </div>
  );
};
