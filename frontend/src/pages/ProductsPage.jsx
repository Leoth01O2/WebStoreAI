import React, { useState, useEffect, useRef } from 'react';
import {
  Package,
  FolderTree,
  Plus,
  Search,
  Edit2,
  Trash2,
  AlertTriangle,
  Filter,
  CheckCircle2,
  Upload,
  Image as ImageIcon,
  Loader2,
  X,
} from 'lucide-react';
import { productsAPI } from '../services/api';
import { useAuth } from '../context/AuthContext';
import { useToast } from '../context/ToastContext';
import { StockBadge, Badge } from '../components/ui/Badge';
import { Modal } from '../components/ui/Modal';
import ProductImage from '../components/common/ProductImage';

export const ProductsPage = () => {
  const { isAdmin, isSuperAdmin, isManager } = useAuth();
  const { addToast } = useToast();
  const canManage = isAdmin || isSuperAdmin || isManager;

  const [activeTab, setActiveTab] = useState('products'); // 'products' | 'categories'

  // Products state
  const [products, setProducts] = useState([]);
  const [categories, setCategories] = useState([]);
  const [loading, setLoading] = useState(true);

  // Filters
  const [search, setSearch] = useState('');
  const [categoryFilter, setCategoryFilter] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [lowStockFilter, setLowStockFilter] = useState(false);

  // Product Modal State
  const [showProductModal, setShowProductModal] = useState(false);
  const [editingProduct, setEditingProduct] = useState(null);
  const [uploadingImage, setUploadingImage] = useState(false);
  const [imageInputMode, setImageInputMode] = useState('url'); // 'url' | 'upload'
  const fileInputRef = useRef(null);

  const [productForm, setProductForm] = useState({
    sku: '',
    name: '',
    category_id: '',
    cost_price: 0,
    selling_price: 0,
    stock_quantity: 0,
    min_stock_alert: 5,
    unit: 'cái',
    status: 'active',
    image_url: '',
    description: '',
  });

  // Category Modal State
  const [showCategoryModal, setShowCategoryModal] = useState(false);
  const [editingCategory, setEditingCategory] = useState(null);
  const [categoryForm, setCategoryForm] = useState({
    name: '',
    code: '',
    description: '',
  });

  const loadData = async () => {
    try {
      setLoading(true);
      const [prods, cats] = await Promise.all([
        productsAPI.getProducts({
          search: search || undefined,
          category_id: categoryFilter || undefined,
          status: statusFilter || undefined,
          low_stock_only: lowStockFilter || undefined,
        }),
        productsAPI.getCategories(),
      ]);
      setProducts(prods);
      setCategories(cats);
    } catch (err) {
      addToast(err.message, 'error');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, [search, categoryFilter, statusFilter, lowStockFilter]);

  // Product CRUD
  const handleOpenAddProduct = () => {
    setEditingProduct(null);
    setImageInputMode('url');
    setProductForm({
      sku: `SKU-${Date.now().toString().slice(-6)}`,
      name: '',
      category_id: categories[0]?.id || '',
      cost_price: 0,
      selling_price: 0,
      stock_quantity: 0,
      min_stock_alert: 5,
      unit: 'cái',
      status: 'active',
      image_url: '',
      description: '',
    });
    setShowProductModal(true);
  };

  const handleOpenEditProduct = (prod) => {
    setEditingProduct(prod);
    setImageInputMode(prod.image_url && prod.image_url.startsWith('/uploads') ? 'upload' : 'url');
    setProductForm({
      sku: prod.sku,
      name: prod.name,
      category_id: prod.category_id || '',
      cost_price: prod.cost_price,
      selling_price: prod.selling_price,
      stock_quantity: prod.stock_quantity,
      min_stock_alert: prod.min_stock_alert,
      unit: prod.unit || 'cái',
      status: prod.status,
      image_url: prod.image_url || '',
      description: prod.description || '',
    });
    setShowProductModal(true);
  };

  const handleImageUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;

    if (!file.type.startsWith('image/')) {
      addToast('Vui lòng chọn file hình ảnh (JPEG, PNG, WebP, GIF)', 'error');
      return;
    }

    if (file.size > 5 * 1024 * 1024) {
      addToast('Dung lượng ảnh vượt quá 5MB', 'error');
      return;
    }

    try {
      setUploadingImage(true);
      const res = await productsAPI.uploadProductImage(file);
      setProductForm((prev) => ({ ...prev, image_url: res.image_url }));
      addToast('Đã tải ảnh lên máy chủ thành công', 'success');
    } catch (err) {
      addToast(err.message || 'Không thể tải ảnh lên', 'error');
    } finally {
      setUploadingImage(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  const handleSaveProduct = async (e) => {
    e.preventDefault();
    try {
      const payload = {
        ...productForm,
        category_id: productForm.category_id ? Number(productForm.category_id) : null,
        cost_price: Number(productForm.cost_price),
        selling_price: Number(productForm.selling_price),
        stock_quantity: Number(productForm.stock_quantity),
        min_stock_alert: Number(productForm.min_stock_alert),
      };

      if (editingProduct) {
        await productsAPI.updateProduct(editingProduct.id, payload);
        addToast(`Đã cập nhật sản phẩm "${payload.name}"`, 'success');
      } else {
        await productsAPI.createProduct(payload);
        addToast(`Đã tạo mới sản phẩm "${payload.name}"`, 'success');
      }
      setShowProductModal(false);
      loadData();
    } catch (err) {
      addToast(err.message, 'error');
    }
  };

  const handleDeleteProduct = async (id, name) => {
    if (!window.confirm(`Bạn có chắc chắn muốn xóa sản phẩm "${name}"?`)) return;
    try {
      await productsAPI.deleteProduct(id);
      addToast(`Đã xóa sản phẩm "${name}"`, 'success');
      loadData();
    } catch (err) {
      addToast(err.message, 'error');
    }
  };

  // Category CRUD
  const handleOpenAddCategory = () => {
    setEditingCategory(null);
    setCategoryForm({
      name: '',
      code: `CAT-${Date.now().toString().slice(-4)}`,
      description: '',
    });
    setShowCategoryModal(true);
  };

  const handleOpenEditCategory = (cat) => {
    setEditingCategory(cat);
    setCategoryForm({
      name: cat.name,
      code: cat.code,
      description: cat.description || '',
    });
    setShowCategoryModal(true);
  };

  const handleSaveCategory = async (e) => {
    e.preventDefault();
    try {
      if (editingCategory) {
        await productsAPI.updateCategory(editingCategory.id, categoryForm);
        addToast(`Đã cập nhật nhóm hàng "${categoryForm.name}"`, 'success');
      } else {
        await productsAPI.createCategory(categoryForm);
        addToast(`Đã tạo nhóm hàng "${categoryForm.name}"`, 'success');
      }
      setShowCategoryModal(false);
      loadData();
    } catch (err) {
      addToast(err.message, 'error');
    }
  };

  const handleDeleteCategory = async (id, name) => {
    if (!window.confirm(`Xóa nhóm hàng "${name}"? Các sản phẩm thuộc nhóm này có thể bị ảnh hưởng.`)) return;
    try {
      await productsAPI.deleteCategory(id);
      addToast(`Đã xóa nhóm hàng "${name}"`, 'success');
      loadData();
    } catch (err) {
      addToast(err.message, 'error');
    }
  };

  const formatVND = (val) => Number(val || 0).toLocaleString('vi-VN') + ' đ';

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
      {/* Top Navigation & Action Header */}
      <div className="retro-card">
        <div className="retro-card-header">
          <div style={{ display: 'flex', gap: '0.5rem' }}>
            <button
              onClick={() => setActiveTab('products')}
              className={`btn btn-sm ${activeTab === 'products' ? 'btn-primary' : 'btn-outline'}`}
            >
              <Package size={15} /> Danh Sách Hàng Hóa ({products.length})
            </button>
            <button
              onClick={() => setActiveTab('categories')}
              className={`btn btn-sm ${activeTab === 'categories' ? 'btn-primary' : 'btn-outline'}`}
            >
              <FolderTree size={15} /> Nhóm Hàng ({categories.length})
            </button>
          </div>

          <div>
            {canManage && activeTab === 'products' && (
              <button onClick={handleOpenAddProduct} className="btn btn-primary btn-sm">
                <Plus size={15} /> Thêm Sản Phẩm Mới
              </button>
            )}
            {canManage && activeTab === 'categories' && (
              <button onClick={handleOpenAddCategory} className="btn btn-primary btn-sm">
                <Plus size={15} /> Thêm Nhóm Hàng
              </button>
            )}
          </div>
        </div>

        {/* Filters for Products */}
        {activeTab === 'products' && (
          <div style={{ padding: '0.85rem 1.25rem', display: 'flex', flexWrap: 'wrap', gap: '0.75rem', alignItems: 'center', background: 'var(--bg-input)' }}>
            <div className="input-with-icon" style={{ minWidth: 'min(100%, 200px)', flex: '1 1 200px' }}>
              <Search size={15} />
              <input
                type="text"
                className="form-control font-mono"
                placeholder="Tìm theo tên hoặc SKU..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
              />
            </div>

            <select
              className="form-control"
              style={{ flex: '1 1 160px', minWidth: '140px' }}
              value={categoryFilter}
              onChange={(e) => setCategoryFilter(e.target.value)}
            >
              <option value="">-- Tất cả nhóm hàng --</option>
              {categories.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </select>

            <select
              className="form-control"
              style={{ width: '150px' }}
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
            >
              <option value="">-- Trạng thái --</option>
              <option value="active">Đang kinh doanh</option>
              <option value="inactive">Ngừng kinh doanh</option>
            </select>

            <label style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', cursor: 'pointer', fontSize: '0.85rem', color: 'var(--amber-light)', fontFamily: 'var(--font-mono)' }}>
              <input
                type="checkbox"
                checked={lowStockFilter}
                onChange={(e) => setLowStockFilter(e.target.checked)}
                style={{ accentColor: 'var(--amber-primary)' }}
              />
              <AlertTriangle size={14} /> Chỉ xem hàng sắp hết
            </label>
          </div>
        )}
      </div>

      {/* PRODUCTS TABLE */}
      {activeTab === 'products' && (
        <div className="table-responsive">
          <table className="retro-table">
            <thead>
              <tr>
                <th style={{ width: '52px', textAlign: 'center' }}>ẢNH</th>
                <th>MÃ SKU</th>
                <th>TÊN MẶT HÀNG</th>
                <th>NHÓM HÀNG</th>
                {canManage && <th style={{ textAlign: 'right' }}>GIÁ VỐN</th>}
                <th style={{ textAlign: 'right' }}>GIÁ BÁN</th>
                <th style={{ textAlign: 'center' }}>TỒN KHO</th>
                <th style={{ textAlign: 'center' }}>TRẠNG THÁI</th>
                {canManage && <th style={{ textAlign: 'center' }}>THAO TÁC</th>}
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan={canManage ? 9 : 7} style={{ textAlign: 'center', padding: '2rem' }}>
                    Đang nạp danh mục hàng hóa từ SQLite...
                  </td>
                </tr>
              ) : products.length === 0 ? (
                <tr>
                  <td colSpan={canManage ? 9 : 7} style={{ textAlign: 'center', padding: '2rem', color: 'var(--text-muted)' }}>
                    Không có sản phẩm nào phù hợp với điều kiện tìm kiếm.
                  </td>
                </tr>
              ) : (
                products.map((p) => (
                  <tr key={p.id}>
                    <td style={{ textAlign: 'center', verticalAlign: 'middle', padding: '0.4rem' }}>
                      <ProductImage
                        src={p.image_url}
                        alt={p.name}
                        style={{ width: '42px', height: '42px', borderRadius: '6px', margin: '0 auto' }}
                      />
                    </td>
                    <td className="font-mono" style={{ fontWeight: 600, color: 'var(--blue-light)' }}>
                      {p.sku}
                    </td>
                    <td>
                      <div style={{ fontWeight: 600 }}>{p.name}</div>
                      {p.description && (
                        <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)', maxWidth: '280px', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                          {p.description}
                        </div>
                      )}
                    </td>
                    <td>
                      <span className="badge badge-muted">{p.category_name || 'Khác'}</span>
                    </td>
                    {canManage && (
                      <td className="currency" style={{ textAlign: 'right', color: 'var(--text-secondary)' }}>
                        {formatVND(p.cost_price)}
                      </td>
                    )}
                    <td className="currency" style={{ textAlign: 'right', color: 'var(--green-terminal)', fontWeight: 700 }}>
                      {formatVND(p.selling_price)}
                    </td>
                    <td style={{ textAlign: 'center' }}>
                      <StockBadge stock={p.stock_quantity} minAlert={p.min_stock_alert} status={p.status} />
                    </td>
                    <td style={{ textAlign: 'center' }}>
                      <Badge variant={p.status === 'active' ? 'green' : 'red'}>
                        {p.status === 'active' ? 'Kinh doanh' : 'Khóa'}
                      </Badge>
                    </td>
                    {canManage && (
                      <td style={{ textAlign: 'center' }}>
                        <div style={{ display: 'flex', justifyContent: 'center', gap: '0.35rem' }}>
                          <button
                            onClick={() => handleOpenEditProduct(p)}
                            className="btn btn-outline btn-icon btn-sm"
                            title="Sửa thông tin"
                          >
                            <Edit2 size={13} />
                          </button>
                          <button
                            onClick={() => handleDeleteProduct(p.id, p.name)}
                            className="btn btn-outline btn-icon btn-sm"
                            style={{ color: 'var(--red-light)' }}
                            title="Xóa sản phẩm"
                          >
                            <Trash2 size={13} />
                          </button>
                        </div>
                      </td>
                    )}
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      )}

      {/* CATEGORIES TABLE */}
      {activeTab === 'categories' && (
        <div className="table-responsive">
          <table className="retro-table">
            <thead>
              <tr>
                <th>MÃ NHÓM</th>
                <th>TÊN NHÓM HÀNG</th>
                <th>MÔ TẢ</th>
                {canManage && <th style={{ textAlign: 'center' }}>THAO TÁC</th>}
              </tr>
            </thead>
            <tbody>
              {categories.map((c) => (
                <tr key={c.id}>
                  <td className="font-mono" style={{ fontWeight: 600, color: 'var(--amber-primary)' }}>
                    {c.code}
                  </td>
                  <td style={{ fontWeight: 600 }}>{c.name}</td>
                  <td style={{ color: 'var(--text-secondary)' }}>{c.description || '—'}</td>
                  {canManage && (
                    <td style={{ textAlign: 'center' }}>
                      <div style={{ display: 'flex', justifyContent: 'center', gap: '0.35rem' }}>
                        <button
                          onClick={() => handleOpenEditCategory(c)}
                          className="btn btn-outline btn-icon btn-sm"
                          title="Sửa"
                        >
                          <Edit2 size={13} />
                        </button>
                        <button
                          onClick={() => handleDeleteCategory(c.id, c.name)}
                          className="btn btn-outline btn-icon btn-sm"
                          style={{ color: 'var(--red-light)' }}
                          title="Xóa"
                        >
                          <Trash2 size={13} />
                        </button>
                      </div>
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* CREATE / EDIT PRODUCT MODAL */}
      <Modal
        isOpen={showProductModal}
        onClose={() => setShowProductModal(false)}
        title={editingProduct ? 'CẬP NHẬT THÔNG TIN SẢN PHẨM' : 'THÊM SẢN PHẨM MỚI'}
        maxWidth="580px"
      >
        <form onSubmit={handleSaveProduct}>
          <div className="form-grid-2">
            <div className="form-group">
              <label className="form-label">Mã SKU (*)</label>
              <input
                type="text"
                required
                className="form-control font-mono"
                value={productForm.sku}
                onChange={(e) => setProductForm({ ...productForm, sku: e.target.value })}
              />
            </div>
            <div className="form-group">
              <label className="form-label">Nhóm hàng</label>
              <select
                className="form-control"
                value={productForm.category_id}
                onChange={(e) => setProductForm({ ...productForm, category_id: e.target.value })}
              >
                <option value="">-- Chọn danh mục --</option>
                {categories.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <div className="form-group">
            <label className="form-label">Tên sản phẩm (*)</label>
            <input
              type="text"
              required
              className="form-control"
              value={productForm.name}
              onChange={(e) => setProductForm({ ...productForm, name: e.target.value })}
            />
          </div>

          <div className="form-grid-2">
            <div className="form-group">
              <label className="form-label">Giá vốn nhập kho (VNĐ)</label>
              <input
                type="number"
                min="0"
                step="1000"
                className="form-control font-mono"
                value={productForm.cost_price}
                onChange={(e) => setProductForm({ ...productForm, cost_price: e.target.value })}
              />
            </div>
            <div className="form-group">
              <label className="form-label">Giá bán niêm yết (VNĐ) (*)</label>
              <input
                type="number"
                min="0"
                step="1000"
                required
                className="form-control font-mono"
                value={productForm.selling_price}
                onChange={(e) => setProductForm({ ...productForm, selling_price: e.target.value })}
              />
            </div>
          </div>

          <div className="form-grid-3">
            <div className="form-group">
              <label className="form-label">Tồn kho ban đầu</label>
              <input
                type="number"
                min="0"
                className="form-control font-mono"
                value={productForm.stock_quantity}
                onChange={(e) => setProductForm({ ...productForm, stock_quantity: e.target.value })}
              />
            </div>
            <div className="form-group">
              <label className="form-label">Cảnh báo khi dưới</label>
              <input
                type="number"
                min="0"
                className="form-control font-mono"
                value={productForm.min_stock_alert}
                onChange={(e) => setProductForm({ ...productForm, min_stock_alert: e.target.value })}
              />
            </div>
            <div className="form-group">
              <label className="form-label">Đơn vị tính</label>
              <input
                type="text"
                className="form-control"
                value={productForm.unit}
                onChange={(e) => setProductForm({ ...productForm, unit: e.target.value })}
              />
            </div>
          </div>

          <div className="form-group">
            <label className="form-label">Trạng thái kinh doanh</label>
            <select
              className="form-control"
              value={productForm.status}
              onChange={(e) => setProductForm({ ...productForm, status: e.target.value })}
            >
              <option value="active">Đang kinh doanh (Active)</option>
              <option value="inactive">Ngừng kinh doanh (Inactive)</option>
            </select>
          </div>

          {/* Hình ảnh sản phẩm */}
          <div className="form-group" style={{ background: 'var(--bg-input)', padding: '0.85rem', borderRadius: '6px', border: '1px solid var(--border-default)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.6rem' }}>
              <label className="form-label" style={{ marginBottom: 0, display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                <ImageIcon size={15} color="var(--amber-primary)" /> Hình ảnh sản phẩm
              </label>
              <div style={{ display: 'flex', gap: '0.35rem' }}>
                <button
                  type="button"
                  onClick={() => setImageInputMode('url')}
                  className={`btn btn-xs ${imageInputMode === 'url' ? 'btn-primary' : 'btn-outline'}`}
                  style={{ padding: '0.2rem 0.5rem', fontSize: '0.72rem' }}
                >
                  Nhập URL
                </button>
                <button
                  type="button"
                  onClick={() => setImageInputMode('upload')}
                  className={`btn btn-xs ${imageInputMode === 'upload' ? 'btn-primary' : 'btn-outline'}`}
                  style={{ padding: '0.2rem 0.5rem', fontSize: '0.72rem' }}
                >
                  <Upload size={11} /> Tải file lên
                </button>
              </div>
            </div>

            <div style={{ display: 'flex', gap: '0.85rem', alignItems: 'center' }}>
              <div style={{ width: '68px', height: '68px', flexShrink: 0, borderRadius: '6px', border: '1px solid var(--border-color)', overflow: 'hidden' }}>
                <ProductImage
                  src={productForm.image_url}
                  alt={productForm.name || 'Preview'}
                  style={{ width: '100%', height: '100%' }}
                />
              </div>

              <div style={{ flex: 1 }}>
                {imageInputMode === 'url' ? (
                  <div>
                    <div style={{ display: 'flex', gap: '0.35rem' }}>
                      <input
                        type="url"
                        className="form-control font-mono"
                        placeholder="https://images.unsplash.com/... hoặc link ảnh"
                        value={productForm.image_url}
                        onChange={(e) => setProductForm({ ...productForm, image_url: e.target.value })}
                        style={{ fontSize: '0.82rem' }}
                      />
                      {productForm.image_url && (
                        <button
                          type="button"
                          onClick={() => setProductForm({ ...productForm, image_url: '' })}
                          className="btn btn-outline btn-icon btn-sm"
                          title="Xóa URL ảnh"
                        >
                          <X size={14} />
                        </button>
                      )}
                    </div>
                    <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginTop: '0.3rem' }}>
                      Nhập trực tiếp đường link ảnh công khai (HTTPS) để hiển thị.
                    </div>
                  </div>
                ) : (
                  <div>
                    <input
                      type="file"
                      ref={fileInputRef}
                      accept="image/jpeg,image/png,image/webp,image/gif"
                      onChange={handleImageUpload}
                      style={{ display: 'none' }}
                      id="product-image-upload"
                    />
                    <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
                      <label
                        htmlFor="product-image-upload"
                        className="btn btn-outline btn-sm"
                        style={{ cursor: uploadingImage ? 'not-allowed' : 'pointer', display: 'inline-flex', alignItems: 'center', gap: '0.4rem' }}
                      >
                        {uploadingImage ? <Loader2 size={13} className="spin" /> : <Upload size={13} />}
                        {uploadingImage ? 'Đang tải ảnh...' : 'Chọn file từ máy tính'}
                      </label>
                      {productForm.image_url && (
                        <button
                          type="button"
                          onClick={() => setProductForm({ ...productForm, image_url: '' })}
                          className="btn btn-outline btn-xs"
                          style={{ color: 'var(--red-light)' }}
                        >
                          Gỡ ảnh
                        </button>
                      )}
                    </div>
                    <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginTop: '0.3rem' }}>
                      Hỗ trợ JPEG, PNG, WebP, GIF (tối đa 5MB). File lưu tại máy chủ StoreFlow.
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>

          <div className="form-group">
            <label className="form-label">Mô tả đặc tính / Thông số sản phẩm</label>
            <textarea
              className="form-control"
              rows={3}
              value={productForm.description}
              onChange={(e) => setProductForm({ ...productForm, description: e.target.value })}
              placeholder="Thông số kỹ thuật, bảo hành, tính năng nổi bật..."
            />
          </div>

          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.5rem', marginTop: '1rem' }}>
            <button type="button" onClick={() => setShowProductModal(false)} className="btn btn-outline">
              Hủy bỏ
            </button>
            <button type="submit" className="btn btn-primary">
              {editingProduct ? 'Lưu Thay Đổi' : 'Tạo Sản Phẩm'}
            </button>
          </div>
        </form>
      </Modal>

      {/* CREATE / EDIT CATEGORY MODAL */}
      <Modal
        isOpen={showCategoryModal}
        onClose={() => setShowCategoryModal(false)}
        title={editingCategory ? 'CẬP NHẬT NHÓM HÀNG' : 'THÊM MỚI NHÓM HÀNG'}
        maxWidth="440px"
      >
        <form onSubmit={handleSaveCategory}>
          <div className="form-group">
            <label className="form-label">Mã nhóm (*)</label>
            <input
              type="text"
              required
              className="form-control font-mono"
              value={categoryForm.code}
              onChange={(e) => setCategoryForm({ ...categoryForm, code: e.target.value })}
            />
          </div>

          <div className="form-group">
            <label className="form-label">Tên nhóm hàng (*)</label>
            <input
              type="text"
              required
              className="form-control"
              value={categoryForm.name}
              onChange={(e) => setCategoryForm({ ...categoryForm, name: e.target.value })}
            />
          </div>

          <div className="form-group">
            <label className="form-label">Mô tả</label>
            <textarea
              className="form-control"
              rows={2}
              value={categoryForm.description}
              onChange={(e) => setCategoryForm({ ...categoryForm, description: e.target.value })}
            />
          </div>

          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.5rem', marginTop: '1rem' }}>
            <button type="button" onClick={() => setShowCategoryModal(false)} className="btn btn-outline">
              Hủy
            </button>
            <button type="submit" className="btn btn-primary">
              Lưu Danh Mục
            </button>
          </div>
        </form>
      </Modal>
    </div>
  );
};
