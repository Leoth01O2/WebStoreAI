import React, { useState, useEffect, useMemo } from 'react';
import {
  Search,
  ShoppingCart,
  Trash2,
  Plus,
  Minus,
  CreditCard,
  Banknote,
  QrCode,
  UserPlus,
  RotateCcw,
  CheckCircle2,
  AlertCircle,
  ShieldCheck,
  Smartphone,
  X,
  Radio,
  Info,
  LogIn,
} from 'lucide-react';
import { productsAPI, customersAPI, ordersAPI } from '../services/api';
import { StockBadge } from '../components/ui/Badge';
import { Modal } from '../components/ui/Modal';
import { ReceiptModal } from '../components/ui/ReceiptModal';
import { useToast } from '../context/ToastContext';
import { useAuth } from '../context/AuthContext';
import ProductImage from '../components/common/ProductImage';

export const PosPage = ({ onNavigate }) => {
  const { addToast } = useToast();
  const { user } = useAuth();
  const isGuest = !user;
  const isCustomer = user?.role === 'customer';

  const [products, setProducts] = useState([]);
  const [categories, setCategories] = useState([]);
  const [customers, setCustomers] = useState([]);
  const [selectedCategory, setSelectedCategory] = useState(null);
  const [searchKeyword, setSearchKeyword] = useState('');
  const [loading, setLoading] = useState(true);
  const [detailProduct, setDetailProduct] = useState(null);


  // Cart State
  const [cart, setCart] = useState([]);
  const [selectedCustomer, setSelectedCustomer] = useState(null);
  const [myProfile, setMyProfile] = useState(null);
  const [discountAmount, setDiscountAmount] = useState(0);
  const [paymentMethod, setPaymentMethod] = useState('cash'); // cash, transfer, card
  const [cashGiven, setCashGiven] = useState('');
  const [orderNote, setOrderNote] = useState('');
  const [submitting, setSubmitting] = useState(false);

  // Staff Confirmation states for non-cash payments
  const [transferConfirmed, setTransferConfirmed] = useState(false);
  const [cardConfirmed, setCardConfirmed] = useState(false);

  // Mobile Cart Drawer State
  const [mobileCartOpen, setMobileCartOpen] = useState(false);

  // Product Click Animation feedback
  const [recentlyAddedId, setRecentlyAddedId] = useState(null);

  // Completed Order for Receipt Modal
  const [completedOrder, setCompletedOrder] = useState(null);
  const [showReceiptModal, setShowReceiptModal] = useState(false);
  const [showGuestModal, setShowGuestModal] = useState(false);

  // Quick Add Customer Modal
  const [showCustomerModal, setShowCustomerModal] = useState(false);
  const [newCustomer, setNewCustomer] = useState({
    customer_code: '',
    name: '',
    phone: '',
    email: '',
    address: '',
    group_name: 'retail',
  });

  const loadData = async () => {
    try {
      setLoading(true);
      if (isGuest) {
        const [prods, cats] = await Promise.all([
          productsAPI.getPublicProducts({ in_stock_only: false }),
          productsAPI.getPublicCategories(),
        ]);
        setProducts(prods);
        setCategories(cats);
        setSelectedCustomer(null);
        setCustomers([]);
      } else if (isCustomer) {
        const [prods, cats, myCust] = await Promise.all([
          productsAPI.getPublicProducts({ in_stock_only: false }),
          productsAPI.getPublicCategories(),
          customersAPI.getMyProfile().catch(() => null),
        ]);
        setProducts(prods);
        setCategories(cats);
        if (myCust) {
          setMyProfile(myCust);
          setSelectedCustomer(myCust);
        }
      } else {
        const [prods, cats, custs] = await Promise.all([
          productsAPI.getProducts({ in_stock_only: false }),
          productsAPI.getCategories(),
          customersAPI.getCustomers(),
        ]);
        setProducts(prods);
        setCategories(cats);
        setCustomers(custs);
      }
    } catch (err) {
      addToast(err.message, 'error');
    } finally {
      setLoading(false);
    }
  };


  useEffect(() => {
    loadData();
  }, []);

  // Reset confirmation when switching payment method
  const handleSelectPaymentMethod = (method) => {
    setPaymentMethod(method);
    setTransferConfirmed(false);
    setCardConfirmed(false);
  };

  // Filter products by search and category
  const filteredProducts = useMemo(() => {
    return products.filter((p) => {
      const matchCat = selectedCategory ? p.category_id === selectedCategory : true;
      const matchSearch = searchKeyword
        ? p.name.toLowerCase().includes(searchKeyword.toLowerCase()) ||
        p.sku.toLowerCase().includes(searchKeyword.toLowerCase())
        : true;
      return matchCat && matchSearch;
    });
  }, [products, selectedCategory, searchKeyword]);

  // Cart calculations
  const subtotal = useMemo(() => {
    return cart.reduce((sum, item) => sum + item.product.selling_price * item.quantity, 0);
  }, [cart]);

  const finalAmount = Math.max(0, subtotal - Number(discountAmount || 0));

  const changeDue = useMemo(() => {
    if (paymentMethod !== 'cash') return 0;
    const given = Number(cashGiven || 0);
    return Math.max(0, given - finalAmount);
  }, [cashGiven, finalAmount, paymentMethod]);

  // Add product to cart
  const addToCart = (product) => {
    if (product.status !== 'active' || product.stock_quantity <= 0) {
      addToast(`Sản phẩm "${product.name}" hiện đã hết hàng hoặc ngừng kinh doanh!`, 'warning');
      return;
    }

    const existingItem = cart.find((item) => item.product.id === product.id);
    if (existingItem && existingItem.quantity >= product.stock_quantity) {
      addToast(`Không thể thêm. Tồn kho chỉ còn ${product.stock_quantity} sản phẩm!`, 'warning');
      return;
    }

    // Trigger visual click feedback
    setRecentlyAddedId(product.id);
    setTimeout(() => setRecentlyAddedId(null), 300);

    setCart((prev) => {
      const existing = prev.find((item) => item.product.id === product.id);
      if (existing) {
        if (existing.quantity >= product.stock_quantity) {
          return prev;
        }
        return prev.map((item) =>
          item.product.id === product.id ? { ...item, quantity: item.quantity + 1 } : item
        );
      }
      return [...prev, { product, quantity: 1 }];
    });
  };

  // Update quantity in cart
  const updateQuantity = (productId, delta) => {
    const existingItem = cart.find((item) => item.product.id === productId);
    if (!existingItem) return;

    if (delta > 0 && existingItem.quantity + delta > existingItem.product.stock_quantity) {
      addToast(`Tồn kho chỉ còn ${existingItem.product.stock_quantity} sản phẩm!`, 'warning');
      return;
    }

    setCart((prev) => {
      return prev
        .map((item) => {
          if (item.product.id === productId) {
            const newQty = item.quantity + delta;
            if (newQty <= 0) return null;
            if (newQty > item.product.stock_quantity) {
              return item;
            }
            return { ...item, quantity: newQty };
          }
          return item;
        })
        .filter(Boolean);
    });
  };

  const removeFromCart = (productId) => {
    setCart((prev) => prev.filter((item) => item.product.id !== productId));
  };

  const clearCart = () => {
    setCart([]);
    setDiscountAmount(0);
    setCashGiven('');
    setOrderNote('');
    setSelectedCustomer(isCustomer ? myProfile : null);
    setTransferConfirmed(false);
    setCardConfirmed(false);
  };

  // Validate checkout readiness based on payment flow
  const isCheckoutReady = useMemo(() => {
    if (cart.length === 0 || submitting) return false;
    if (isGuest) return true;
    if (paymentMethod === 'cash') {
      if (!isCustomer && cashGiven && Number(cashGiven) < finalAmount) return false;
      return true;
    }
    if (paymentMethod === 'transfer') {
      return transferConfirmed;
    }
    if (paymentMethod === 'card') {
      return cardConfirmed;
    }
    return false;
  }, [cart.length, submitting, paymentMethod, cashGiven, finalAmount, transferConfirmed, cardConfirmed, isCustomer, isGuest]);

  // Checkout process
  const handleCheckout = async () => {
    if (cart.length === 0) {
      addToast('Giỏ hàng đang trống!', 'warning');
      return;
    }

    if (isGuest) {
      setShowGuestModal(true);
      return;
    }

    if (!isCustomer && paymentMethod === 'cash' && cashGiven && Number(cashGiven) < finalAmount) {
      addToast('Số tiền khách đưa chưa đủ!', 'warning');
      return;
    }

    if (paymentMethod === 'transfer' && !transferConfirmed) {
      addToast('Vui lòng kiểm tra tài khoản và nhấn xác nhận đã chuyển khoản trước khi hoàn tất!', 'warning');
      return;
    }

    if (paymentMethod === 'card' && !cardConfirmed) {
      addToast('Vui lòng xác nhận thanh toán thẻ trước khi hoàn tất!', 'warning');
      return;
    }

    setSubmitting(true);
    try {
      const orderPayload = {
        customer_id: selectedCustomer ? selectedCustomer.id : (isCustomer && myProfile ? myProfile.id : null),
        discount_amount: isCustomer ? 0 : Number(discountAmount || 0),
        payment_method: paymentMethod,
        payment_status: isCustomer ? (paymentMethod === 'transfer' ? 'pending_verification' : 'unpaid') : 'paid',
        note: orderNote || null,
        items: cart.map((item) => ({
          product_id: item.product.id,
          quantity: item.quantity,
        })),
      };

      const created = await ordersAPI.createOrder(orderPayload);

      // Attach client cash given for receipt display
      created.cash_given = paymentMethod === 'cash' ? (Number(cashGiven) || finalAmount) : finalAmount;

      setCompletedOrder(created);
      setShowReceiptModal(true);
      setMobileCartOpen(false);
      addToast(isCustomer ? `Đặt hàng thành công! Mã đơn: ${created.order_code}` : `Đơn hàng ${created.order_code} đã thanh toán thành công!`, 'success');

      // Refresh product stock in real time
      const prods = (isCustomer || isGuest)
        ? await productsAPI.getPublicProducts({ in_stock_only: false })
        : await productsAPI.getProducts({ in_stock_only: false });
      setProducts(prods);


      clearCart();
    } catch (err) {
      addToast(err.message || 'Lỗi thanh toán đơn hàng', 'error');
    } finally {
      setSubmitting(false);
    }
  };

  // Keyboard shortcut (F2 to checkout)
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === 'F2') {
        e.preventDefault();
        if (isCheckoutReady) {
          handleCheckout();
        } else {
          addToast('Vui lòng hoàn tất điều kiện thanh toán trước khi bấm F2!', 'warning');
        }
      } else if (e.key === 'F4') {
        e.preventDefault();
        clearCart();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isCheckoutReady, cart, selectedCustomer, discountAmount, paymentMethod, cashGiven, orderNote, transferConfirmed, cardConfirmed]);

  // Handle Quick Add Customer
  const handleCreateCustomer = async (e) => {
    e.preventDefault();
    if (!newCustomer.name || !newCustomer.phone) {
      addToast('Vui lòng nhập tên và số điện thoại khách hàng', 'warning');
      return;
    }
    try {
      const code = newCustomer.customer_code || `CUS-${Date.now().toString().slice(-4)}`;
      const created = await customersAPI.createCustomer({
        ...newCustomer,
        customer_code: code,
      });
      setCustomers((prev) => [created, ...prev]);
      setSelectedCustomer(created);
      setShowCustomerModal(false);
      setNewCustomer({
        customer_code: '',
        name: '',
        phone: '',
        email: '',
        address: '',
        group_name: 'retail',
      });
      addToast(`Đã thêm khách hàng "${created.name}"`, 'success');
    } catch (err) {
      addToast(err.message, 'error');
    }
  };

  const formatVND = (val) => Number(val || 0).toLocaleString('vi-VN') + ' đ';

  const [transferMemo] = useState(() => `SF-POS${Math.floor(1000 + Math.random() * 9000)}`);

  return (
    <div className="pos-container">
      {/* LEFT COLUMN: PRODUCT CATALOG */}
      <div className="pos-catalog">
        <div className="pos-catalog-header">
          <div className="pos-search-row">
            <div className="input-with-icon" style={{ flex: 1 }}>
              <Search size={16} />
              <input
                type="text"
                className="form-control font-mono"
                placeholder="Tìm sản phẩm theo tên hoặc mã SKU..."
                value={searchKeyword}
                onChange={(e) => setSearchKeyword(e.target.value)}
              />
            </div>
            {searchKeyword && (
              <button
                className="btn btn-outline btn-sm"
                onClick={() => setSearchKeyword('')}
              >
                Xóa
              </button>
            )}
          </div>

          {/* Category Filter Pills */}
          <div className="category-pills">
            <button
              className={`category-pill ${selectedCategory === null ? 'active' : ''}`}
              onClick={() => setSelectedCategory(null)}
            >
              Tất cả ({products.length})
            </button>
            {categories.map((cat) => (
              <button
                key={cat.id}
                className={`category-pill ${selectedCategory === cat.id ? 'active' : ''}`}
                onClick={() => setSelectedCategory(cat.id)}
              >
                {cat.name}
              </button>
            ))}
          </div>
        </div>

        {/* Product Grid */}
        <div className="product-grid">
          {loading ? (
            <div style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-muted)' }}>
              Đang tải danh mục hàng hóa...
            </div>
          ) : filteredProducts.length === 0 ? (
            <div style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-muted)' }}>
              Không tìm thấy sản phẩm phù hợp.
            </div>
          ) : (
            filteredProducts.map((prod) => {
              const isOutOfStock = prod.stock_quantity <= 0 || prod.status !== 'active';
              const isRecentlyAdded = recentlyAddedId === prod.id;

              return (
                <div
                  key={prod.id}
                  className={`product-card ${isOutOfStock ? 'out-of-stock' : ''} ${isRecentlyAdded ? 'card-click-active' : ''}`}
                  onClick={() => !isOutOfStock && addToCart(prod)}
                  title={isOutOfStock ? `${prod.name} (Hết hàng)` : `Bấm để thêm ${prod.name} vào giỏ`}
                >
                  {/* Product Card Image Container */}
                  <div className="product-card-img-box" style={{ position: 'relative' }}>
                    <ProductImage
                      src={prod.image_url}
                      alt={prod.name}
                      style={{ width: '100%', height: '100%' }}
                    />
                    <button
                      type="button"
                      className="btn btn-outline btn-icon btn-sm product-detail-overlay-btn"
                      style={{
                        position: 'absolute',
                        top: '6px',
                        right: '6px',
                        width: '26px',
                        height: '26px',
                        padding: 0,
                        background: 'rgba(10, 14, 19, 0.85)',
                        borderColor: 'var(--border-subtle)',
                        color: 'var(--amber-primary)',
                        zIndex: 2,
                      }}
                      onClick={(e) => {
                        e.stopPropagation();
                        setDetailProduct(prod);
                      }}
                      title="Xem chi tiết sản phẩm"
                    >
                      <Info size={13} />
                    </button>
                    {isOutOfStock && (
                      <div className="out-of-stock-overlay">
                        <span>HẾT HÀNG</span>
                      </div>
                    )}
                  </div>

                  {/* Product Details Hierarchy: Name -> Price -> Stock/SKU */}
                  <div className="product-card-body">
                    <div className="product-name" title={prod.name}>
                      {prod.name}
                    </div>

                    <div className="product-price-row">
                      <span className="product-price">{formatVND(prod.selling_price)}</span>
                    </div>

                    <div className="product-footer">
                      <span className="product-sku">{prod.sku}</span>
                      <StockBadge stock={prod.stock_quantity} minAlert={prod.min_stock_alert} status={prod.status} />
                    </div>
                  </div>
                </div>
              );
            })
          )}
        </div>
      </div>

      {/* RIGHT COLUMN: POS CART & CHECKOUT (Desktop Sidebar & Mobile Drawer) */}
      <div className={`pos-cart ${mobileCartOpen ? 'mobile-open' : ''}`}>
        <div className="pos-cart-header">
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontWeight: 700, color: 'var(--amber-primary)' }}>
            <ShoppingCart size={18} />
            <span>{isGuest ? 'GIỎ HÀNG' : (isCustomer ? 'GIỎ HÀNG CỦA BẠN' : 'GIỎ HÀNG BÁN HÀNG')}</span>
            <span className="badge badge-amber">{cart.reduce((s, i) => s + i.quantity, 0)} món</span>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
            {cart.length > 0 && (
              <button
                onClick={clearCart}
                className="btn btn-outline btn-sm"
                title="Xóa toàn bộ giỏ hàng (F4)"
                style={{ color: 'var(--red-light)', borderColor: 'var(--border-subtle)' }}
              >
                <RotateCcw size={13} /> Xóa giỏ
              </button>
            )}
            {/* Mobile Close Drawer Button */}
            <button
              onClick={() => setMobileCartOpen(false)}
              className="btn btn-outline btn-icon btn-sm mobile-cart-close"
              title="Đóng giỏ hàng"
            >
              <X size={16} />
            </button>
          </div>
        </div>

        {/* Customer Selector Bar */}
        {isGuest ? (
          <div style={{ padding: '0.65rem 0.85rem', background: 'var(--bg-input)', borderBottom: '1px solid var(--border-subtle)', display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
            <div style={{ fontSize: '0.82rem', color: 'var(--text-secondary)', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <span style={{ color: 'var(--amber-primary)', fontWeight: 600 }}>👤 Khách mua:</span>
              <span style={{ color: 'var(--text-muted)' }}>Khách vãng lai (Chưa đăng nhập)</span>
            </div>
          </div>
        ) : isCustomer ? (
          <div style={{ padding: '0.65rem 0.85rem', background: 'var(--bg-input)', borderBottom: '1px solid var(--border-subtle)', display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
            <div style={{ fontSize: '0.82rem', color: 'var(--text-secondary)', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <span style={{ color: 'var(--amber-primary)', fontWeight: 600 }}>👤 Người mua:</span>
              <span style={{ color: 'var(--text-primary)', fontWeight: 500 }}>
                {selectedCustomer ? `${selectedCustomer.name} (${selectedCustomer.phone || selectedCustomer.customer_code})` : (user?.full_name || user?.username)}
              </span>
            </div>
          </div>
        ) : (
          <div style={{ padding: '0.65rem 0.85rem', background: 'var(--bg-input)', borderBottom: '1px solid var(--border-subtle)', display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
            <select
              className="form-control"
              style={{ flex: 1, fontSize: '0.8rem', padding: '0.4rem 0.6rem' }}
              value={selectedCustomer ? selectedCustomer.id : ''}
              onChange={(e) => {
                const custId = Number(e.target.value);
                const found = customers.find((c) => c.id === custId);
                setSelectedCustomer(found || null);
              }}
            >
              <option value="">Khách vãng lai / Khách lẻ</option>
              {customers.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name} - {c.phone} ({c.group_name.toUpperCase()})
                </option>
              ))}
            </select>
            <button
              onClick={() => setShowCustomerModal(true)}
              className="btn btn-outline btn-sm"
              title="Thêm khách hàng mới"
              style={{ padding: '0.4rem 0.6rem' }}
            >
              <UserPlus size={15} />
            </button>
          </div>
        )}


        {/* Cart Item Rows */}
        <div className="pos-cart-items">
          {cart.length === 0 ? (
            <div style={{ margin: 'auto', textAlign: 'center', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
              <ShoppingCart size={36} style={{ margin: '0 auto 0.5rem', opacity: 0.3 }} />
              <div>[GIỎ HÀNG TRỐNG]</div>
              <div style={{ fontSize: '0.75rem', marginTop: '0.2rem' }}>Chọn sản phẩm bên trái để bắt đầu tính tiền</div>
            </div>
          ) : (
            cart.map((item) => (
              <div key={item.product.id} className="cart-item-row">
                {/* Cart Item Thumbnail & Info */}
                <div className="cart-item-info">
                  <div className="cart-item-thumb">
                    <ProductImage
                      src={item.product.image_url}
                      alt={item.product.name}
                      style={{ width: '100%', height: '100%' }}
                    />
                  </div>
                  <div className="cart-item-details">
                    <div className="cart-item-name" title={item.product.name}>
                      {item.product.name}
                    </div>
                    <div className="cart-item-meta">
                      {item.product.sku} | {formatVND(item.product.selling_price)}
                    </div>
                  </div>
                </div>

                {/* Quantity Controls */}
                <div className="cart-qty-control">
                  <button
                    type="button"
                    className="cart-qty-btn cart-qty-minus"
                    onClick={() => updateQuantity(item.product.id, -1)}
                    aria-label="Giảm 1"
                  >
                    <Minus size={12} />
                  </button>
                  <span className="cart-qty-val">{item.quantity}</span>
                  <button
                    type="button"
                    className="cart-qty-btn cart-qty-plus"
                    onClick={() => updateQuantity(item.product.id, 1)}
                    aria-label="Tăng 1"
                  >
                    <Plus size={12} />
                  </button>
                </div>

                {/* Subtotal */}
                <div className="cart-item-subtotal">
                  {formatVND(item.product.selling_price * item.quantity)}
                </div>

                {/* Remove Button */}
                <button
                  type="button"
                  onClick={() => removeFromCart(item.product.id)}
                  className="cart-item-remove-btn"
                  title="Xóa khỏi giỏ"
                  aria-label="Xóa khỏi giỏ"
                >
                  <Trash2 size={13} />
                </button>
              </div>
            ))
          )}
        </div>

        {/* POS Cart Summary & Checkout */}
        <div className="pos-cart-summary">
          <div className="summary-row">
            <span style={{ color: 'var(--text-secondary)' }}>Tạm tính:</span>
            <span className="currency">{formatVND(subtotal)}</span>
          </div>

          {!isCustomer && !isGuest && (
            <div className="summary-row" style={{ alignItems: 'center' }}>
              <span style={{ color: 'var(--text-secondary)' }}>Chiết khấu (VNĐ):</span>
              <input
                type="number"
                min="0"
                step="1000"
                className="form-control font-mono"
                style={{ width: '130px', padding: '0.25rem 0.5rem', textAlign: 'right', fontSize: '0.82rem' }}
                value={discountAmount}
                onChange={(e) => setDiscountAmount(e.target.value)}
              />
            </div>
          )}

          <div className="summary-row total">
            <span>THANH TOÁN:</span>
            <span className="currency" style={{ fontSize: '1.3rem' }}>{formatVND(finalAmount)}</span>
          </div>

          {/* Payment Method Selector */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '0.35rem', marginTop: '0.3rem' }}>
            <button
              className={`btn btn-sm ${paymentMethod === 'cash' ? 'btn-primary' : 'btn-outline'}`}
              onClick={() => handleSelectPaymentMethod('cash')}
            >
              <Banknote size={14} /> Tiền mặt
            </button>
            <button
              className={`btn btn-sm ${paymentMethod === 'transfer' ? 'btn-primary' : 'btn-outline'}`}
              onClick={() => handleSelectPaymentMethod('transfer')}
            >
              <QrCode size={14} /> C.Khoản
            </button>
            <button
              className={`btn btn-sm ${paymentMethod === 'card' ? 'btn-primary' : 'btn-outline'}`}
              onClick={() => handleSelectPaymentMethod('card')}
            >
              <CreditCard size={14} /> Quẹt thẻ
            </button>
          </div>

          {/* METHOD 1: CASH PAYMENT FLOW */}
          {paymentMethod === 'cash' && !isCustomer && !isGuest && (
            <div style={{ marginTop: '0.5rem' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.3rem' }}>
                <span style={{ fontSize: '0.78rem', color: 'var(--text-secondary)' }}>Tiền khách đưa:</span>
                <input
                  type="number"
                  min="0"
                  step="10000"
                  placeholder={String(finalAmount)}
                  className="form-control font-mono"
                  style={{ width: '130px', padding: '0.25rem 0.5rem', textAlign: 'right', fontSize: '0.82rem' }}
                  value={cashGiven}
                  onChange={(e) => setCashGiven(e.target.value)}
                />
              </div>

              {/* Cash Presets */}
              <div className="cash-presets">
                <button
                  type="button"
                  className="cash-preset-btn"
                  onClick={() => setCashGiven(String(finalAmount))}
                >
                  Đủ tiền
                </button>
                <button
                  type="button"
                  className="cash-preset-btn"
                  onClick={() => setCashGiven(String(Math.ceil(finalAmount / 50000) * 50000 || 50000))}
                >
                  Làm tròn 50k
                </button>
                <button
                  type="button"
                  className="cash-preset-btn"
                  onClick={() => setCashGiven(String(Math.ceil(finalAmount / 100000) * 100000 || 100000))}
                >
                  Làm tròn 100k
                </button>
                <button
                  type="button"
                  className="cash-preset-btn"
                  onClick={() => setCashGiven(String(Math.ceil(finalAmount / 500000) * 500000 || 500000))}
                >
                  500k
                </button>
              </div>

              {cashGiven && Number(cashGiven) >= finalAmount && (
                <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: '0.4rem', fontSize: '0.85rem' }}>
                  <span style={{ color: 'var(--green-light)', fontWeight: 600 }}>Tiền thừa trả khách:</span>
                  <span className="currency" style={{ color: 'var(--green-light)', fontWeight: 700 }}>
                    {formatVND(changeDue)}
                  </span>
                </div>
              )}
            </div>
          )}

          {paymentMethod === 'cash' && (isCustomer || isGuest) && (
            <div style={{ marginTop: '0.5rem', padding: '0.5rem', background: 'var(--bg-input)', border: '1px solid var(--border-subtle)', borderRadius: '4px', fontSize: '0.78rem', color: 'var(--text-secondary)' }}>
              💵 Thanh toán tiền mặt khi nhận hàng (COD).
            </div>
          )}

          {/* METHOD 2: BANK TRANSFER FLOW (MBBank, VietQR & Confirmation) */}
          {paymentMethod === 'transfer' && (
            <div className="payment-flow-box" style={{ marginTop: '0.6rem', padding: '0.75rem', background: 'var(--bg-input)', border: '1px solid var(--border-default)', borderRadius: '6px' }}>
              <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'flex-start' }}>
                {/* VietQR Demo Code */}
                <div style={{ width: '80px', height: '80px', flexShrink: 0, background: '#ffffff', borderRadius: '4px', padding: '4px', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center' }}>
                  <QrCode size={64} color="#000000" />
                  <span style={{ fontSize: '0.55rem', color: '#000', fontWeight: 700 }}>VIETQR</span>
                </div>

                {/* Transfer Information */}
                <div style={{ flex: 1, fontSize: '0.78rem', lineHeight: '1.4' }}>
                  <div style={{ color: 'var(--text-muted)', fontSize: '0.7rem' }}>NGÂN HÀNG:</div>
                  <div style={{ fontWeight: 700, color: 'var(--blue-light)' }}>MBBank (Quân Đội)</div>

                  <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: '2px' }}>
                    <span style={{ color: 'var(--text-muted)' }}>STK:</span>
                    <span className="font-mono" style={{ fontWeight: 700, color: 'var(--amber-primary)' }}>0987654321</span>
                  </div>

                  <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: '2px' }}>
                    <span style={{ color: 'var(--text-muted)' }}>Chủ TK:</span>
                    <span style={{ fontWeight: 600 }}>STOREFLOW TECH AI</span>
                  </div>

                  <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: '2px' }}>
                    <span style={{ color: 'var(--text-muted)' }}>Nội dung:</span>
                    <span className="font-mono" style={{ color: 'var(--green-terminal)', fontWeight: 600 }}>{transferMemo}</span>
                  </div>
                </div>
              </div>

              {/* Confirmation Toggle */}
              <div style={{ marginTop: '0.65rem', paddingTop: '0.5rem', borderTop: '1px dashed var(--border-subtle)' }}>
                {transferConfirmed ? (
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', background: 'rgba(16, 185, 129, 0.15)', border: '1px solid var(--green-terminal)', padding: '0.45rem 0.6rem', borderRadius: '4px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', color: 'var(--green-terminal)', fontSize: '0.8rem', fontWeight: 600 }}>
                      <CheckCircle2 size={16} />
                      <span>{isCustomer ? 'ĐÃ XÁC NHẬN CHUYỂN KHOẢN' : 'ĐÃ XÁC NHẬN TIỀN VỀ TÀI KHOẢN'}</span>
                    </div>
                    <button
                      type="button"
                      onClick={() => setTransferConfirmed(false)}
                      className="btn btn-outline btn-xs"
                      style={{ fontSize: '0.68rem', padding: '0.15rem 0.4rem' }}
                    >
                      Hủy
                    </button>
                  </div>
                ) : (
                  <div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem', color: 'var(--amber-light)', fontSize: '0.72rem', marginBottom: '0.4rem' }}>
                      <AlertCircle size={13} />
                      <span>{isCustomer ? 'Quét mã QR chuyển khoản rồi bấm nút xác nhận:' : 'Thu ngân kiểm tra biến động số dư trước khi bấm xác nhận:'}</span>
                    </div>
                    <button
                      type="button"
                      onClick={() => setTransferConfirmed(true)}
                      className="btn btn-outline btn-sm"
                      style={{ width: '100%', borderColor: 'var(--amber-primary)', color: 'var(--amber-primary)', fontWeight: 600, fontSize: '0.82rem', justifyContent: 'center' }}
                    >
                      <ShieldCheck size={15} />
                      <span>{isCustomer ? '[ TÔI ĐÃ CHUYỂN KHOẢN XONG ]' : '[ XÁC NHẬN ĐÃ NHẬN ĐỦ TIỀN ]'}</span>
                    </button>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* METHOD 3: CARD POS TERMINAL FLOW */}
          {paymentMethod === 'card' && (
            <div className="payment-flow-box" style={{ marginTop: '0.6rem', padding: '0.75rem', background: 'var(--bg-input)', border: '1px solid var(--border-default)', borderRadius: '6px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem' }}>
                <div style={{ width: '40px', height: '40px', borderRadius: '6px', background: 'rgba(59, 130, 246, 0.15)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--blue-light)', flexShrink: 0 }}>
                  <Smartphone size={22} className="pulse-slow" />
                </div>
                <div style={{ flex: 1 }}>
                  <div style={{ fontWeight: 600, fontSize: '0.82rem', color: 'var(--text-primary)' }}>
                    MÁY QUẸT THẺ POS VĂN PHÒNG
                  </div>
                  <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>
                    Cà thẻ / Chạm NFC / Thẻ chip: <span className="currency" style={{ color: 'var(--green-terminal)', fontWeight: 700 }}>{formatVND(finalAmount)}</span>
                  </div>
                </div>
              </div>

              {/* Confirmation Toggle */}
              <div style={{ marginTop: '0.65rem', paddingTop: '0.5rem', borderTop: '1px dashed var(--border-subtle)' }}>
                {cardConfirmed ? (
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', background: 'rgba(16, 185, 129, 0.15)', border: '1px solid var(--green-terminal)', padding: '0.45rem 0.6rem', borderRadius: '4px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', color: 'var(--green-terminal)', fontSize: '0.8rem', fontWeight: 600 }}>
                      <CheckCircle2 size={16} />
                      <span>{isCustomer ? 'ĐÃ XÁC NHẬN THANH TOÁN THẺ' : 'ĐÃ QUẸT THẺ THÀNH CÔNG (POS ĐÃ IN BILL)'}</span>
                    </div>
                    <button
                      type="button"
                      onClick={() => setCardConfirmed(false)}
                      className="btn btn-outline btn-xs"
                      style={{ fontSize: '0.68rem', padding: '0.15rem 0.4rem' }}
                    >
                      Hủy
                    </button>
                  </div>
                ) : (
                  <div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem', color: 'var(--blue-light)', fontSize: '0.72rem', marginBottom: '0.4rem' }}>
                      <Radio size={13} className="spin-slow" />
                      <span>{isCustomer ? 'Vui lòng thanh toán thẻ trên thiết bị rồi bấm xác nhận:' : 'Đang chờ khách quẹt thẻ trên thiết bị POS...'}</span>
                    </div>
                    <button
                      type="button"
                      onClick={() => setCardConfirmed(true)}
                      className="btn btn-outline btn-sm"
                      style={{ width: '100%', borderColor: 'var(--blue-light)', color: 'var(--blue-light)', fontWeight: 600, fontSize: '0.82rem', justifyContent: 'center' }}
                    >
                      <CreditCard size={15} />
                      <span>{isCustomer ? '[ TÔI ĐÃ THANH TOÁN THẺ XONG ]' : '[ XÁC NHẬN ĐÃ THANH TOÁN THẺ XONG ]'}</span>
                    </button>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Big Checkout Button */}
          <button
            onClick={handleCheckout}
            disabled={!isCheckoutReady}
            className={`btn btn-lg ${isCheckoutReady ? 'btn-success' : 'btn-outline'}`}
            style={{
              marginTop: '0.65rem',
              width: '100%',
              fontSize: '1rem',
              letterSpacing: '0.04em',
              fontWeight: 700,
              opacity: isCheckoutReady ? 1 : 0.5,
              cursor: isCheckoutReady ? 'pointer' : 'not-allowed',
            }}
          >
            {submitting
              ? (isCustomer ? 'ĐANG XỬ LÝ ĐẶT HÀNG...' : 'ĐANG XỬ LÝ GIAO DỊCH...')
              : isGuest
                ? '🔒 ĐĂNG NHẬP ĐỂ ĐẶT HÀNG'
                : !isCheckoutReady && paymentMethod === 'transfer'
                  ? 'CHỜ XÁC NHẬN CHUYỂN KHOẢN...'
                  : !isCheckoutReady && paymentMethod === 'card'
                    ? 'CHỜ KẾT QUẢ TỪ MÁY POS...'
                    : isCustomer
                      ? 'XÁC NHẬN ĐẶT HÀNG'
                      : 'HOÀN TẤT & IN HÓA ĐƠN (F2)'}
          </button>
        </div>
      </div>

      {/* MOBILE BOTTOM FLOATING CART BAR (Only on screen <= 1024px) */}
      <div className="mobile-pos-cart-bar">
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
          <div className="mobile-cart-icon-badge">
            <ShoppingCart size={18} />
            <span className="mobile-cart-count">{cart.reduce((s, i) => s + i.quantity, 0)}</span>
          </div>
          <div>
            <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>TỔNG CỘNG</div>
            <div className="currency" style={{ fontWeight: 700, color: 'var(--green-terminal)', fontSize: '0.95rem' }}>
              {formatVND(finalAmount)}
            </div>
          </div>
        </div>

        <button
          onClick={() => setMobileCartOpen(true)}
          className="btn btn-primary btn-sm"
          style={{ padding: '0.5rem 0.9rem', fontSize: '0.82rem' }}
        >
          <span>Xem Giỏ Hàng</span>
        </button>
      </div>

      {/* Backdrop for Mobile Cart Drawer */}
      {mobileCartOpen && (
        <div
          className="mobile-cart-backdrop"
          onClick={() => setMobileCartOpen(false)}
        />
      )}

      {/* Quick Add Customer Modal */}
      {!isCustomer && !isGuest && (
        <Modal
          isOpen={showCustomerModal}
          onClose={() => setShowCustomerModal(false)}
          title="THÊM NHANH KHÁCH HÀNG"
          maxWidth="440px"
        >
          <form onSubmit={handleCreateCustomer}>
            <div className="form-group">
              <label className="form-label">Họ và tên (*)</label>
              <input
                type="text"
                required
                className="form-control"
                value={newCustomer.name}
                onChange={(e) => setNewCustomer({ ...newCustomer, name: e.target.value })}
                placeholder="Nguyễn Văn A"
              />
            </div>

            <div className="form-group">
              <label className="form-label">Số điện thoại (*)</label>
              <input
                type="tel"
                required
                className="form-control font-mono"
                value={newCustomer.phone}
                onChange={(e) => setNewCustomer({ ...newCustomer, phone: e.target.value })}
                placeholder="0987654321"
              />
            </div>

            <div className="form-group">
              <label className="form-label">Phân nhóm khách</label>
              <select
                className="form-control"
                value={newCustomer.group_name}
                onChange={(e) => setNewCustomer({ ...newCustomer, group_name: e.target.value })}
              >
                <option value="retail">Khách lẻ (Retail)</option>
                <option value="vip">Khách VIP</option>
                <option value="wholesale">Khách buôn (Wholesale)</option>
              </select>
            </div>

            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.5rem', marginTop: '1rem' }}>
              <button type="button" onClick={() => setShowCustomerModal(false)} className="btn btn-outline">
                Hủy
              </button>
              <button type="submit" className="btn btn-primary">
                Lưu & Chọn Ngay
              </button>
            </div>
          </form>
        </Modal>
      )}

      {/* Product Detail Modal */}
      {detailProduct && (
        <Modal
          isOpen={true}
          onClose={() => setDetailProduct(null)}
          title={`CHI TIẾT: ${detailProduct.name}`}
          maxWidth="560px"
        >
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
            <div style={{ width: '100%', height: '220px', borderRadius: '4px', overflow: 'hidden', border: '1px solid var(--border-subtle)' }}>
              <ProductImage
                src={detailProduct.image_url}
                alt={detailProduct.name}
                style={{ width: '100%', height: '100%' }}
              />
            </div>

            <div>
              <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>MÃ SKU: {detailProduct.sku}</div>
              <h3 style={{ fontSize: '1.2rem', color: 'var(--text-primary)', marginTop: '0.25rem', marginBottom: '0.35rem' }}>{detailProduct.name}</h3>
              {detailProduct.category_name && (
                <span className="badge badge-blue">{detailProduct.category_name}</span>
              )}
            </div>

            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', background: 'var(--bg-input)', padding: '0.75rem 1rem', borderRadius: '4px' }}>
              <div>
                <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>Giá niêm yết:</div>
                <div style={{ fontSize: '1.35rem', fontWeight: 800, color: 'var(--amber-primary)', fontFamily: 'var(--font-mono)' }}>
                  {formatVND(detailProduct.selling_price)}
                </div>
              </div>
              <div style={{ textAlign: 'right' }}>
                <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>Tình trạng:</div>
                <StockBadge stock={detailProduct.stock_quantity} minAlert={0} status={detailProduct.status} />
              </div>
            </div>

            {detailProduct.description && (
              <div>
                <div style={{ fontSize: '0.78rem', color: 'var(--text-secondary)', marginBottom: '0.3rem' }}>Mô tả sản phẩm:</div>
                <div style={{ fontSize: '0.82rem', color: 'var(--text-primary)', background: 'var(--bg-card)', padding: '0.65rem 0.85rem', borderRadius: '4px', border: '1px solid var(--border-subtle)', lineHeight: 1.5 }}>
                  {detailProduct.description}
                </div>
              </div>
            )}

            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.5rem', marginTop: '0.5rem' }}>
              <button
                type="button"
                className="btn btn-outline"
                onClick={() => setDetailProduct(null)}
              >
                Đóng
              </button>
              {detailProduct.stock_quantity > 0 ? (
                <button
                  type="button"
                  className="btn btn-primary"
                  onClick={() => {
                    addToCart(detailProduct);
                    setDetailProduct(null);
                  }}
                >
                  <ShoppingCart size={15} /> Thêm Vào Giỏ Hàng
                </button>
              ) : (
                <button type="button" className="btn btn-outline" disabled>
                  Tạm Hết Hàng
                </button>
              )}
            </div>
          </div>
        </Modal>
      )}

      {/* Guest Login Required Modal */}
      <Modal
        isOpen={showGuestModal}
        onClose={() => setShowGuestModal(false)}
        title="YÊU CẦU ĐĂNG NHẬP / ĐĂNG KÝ"
        maxWidth="460px"
      >
        <div style={{ textAlign: 'center', padding: '0.5rem 0' }}>
          <div style={{ fontSize: '1.8rem', marginBottom: '0.5rem' }}>🔐</div>
          <h4 style={{ color: 'var(--amber-primary)', marginBottom: '0.5rem' }}>
            DÀNH CHO KHÁCH HÀNG THÀNH VIÊN
          </h4>
          <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', lineHeight: 1.5, marginBottom: '1.25rem' }}>
            Bạn đang xem sản phẩm với vai trò Khách vãng lai. Vui lòng đăng nhập hoặc tạo tài khoản thành viên để hoàn tất đơn hàng, lưu lại lịch sử mua sắm và theo dõi trạng thái giao hàng.
          </p>
          <div style={{ display: 'flex', gap: '0.75rem', justifyContent: 'center' }}>
            <button
              type="button"
              className="btn btn-outline"
              onClick={() => setShowGuestModal(false)}
            >
              Tiếp tục xem sản phẩm
            </button>
            <button
              type="button"
              className="btn btn-primary"
              onClick={() => {
                setShowGuestModal(false);
                if (onNavigate) onNavigate('login');
              }}
            >
              <LogIn size={15} /> Đăng Nhập / Đăng Ký
            </button>
          </div>
        </div>
      </Modal>

      {/* Printable Receipt Modal */}
      <ReceiptModal
        isOpen={showReceiptModal}
        onClose={() => setShowReceiptModal(false)}
        order={completedOrder}
        onNewOrder={() => setShowReceiptModal(false)}
      />
    </div>
  );
};


