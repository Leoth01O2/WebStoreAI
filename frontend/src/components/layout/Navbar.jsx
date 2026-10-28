import React, { useState, useEffect } from 'react';
import {
  ShoppingCart,
  Package,
  Users,
  FileText,
  Truck,
  BarChart3,
  LogOut,
  LogIn,
  AlertTriangle,
  Clock,
  Sparkles,
  Menu,
  X,
  Cpu,
  ShieldCheck,
} from 'lucide-react';
import { useAuth } from '../../context/AuthContext';
import { RoleBadge } from '../ui/Badge';
import { inventoryAPI, ordersAPI, aiAPI } from '../../services/api';
import { ThemeToggle } from './ThemeToggle';

export const Navbar = ({ activeTab, onSelectTab }) => {
  const { user, logout, isAdmin } = useAuth();
  const [time, setTime] = useState(new Date().toLocaleTimeString('vi-VN'));
  const [lowStockCount, setLowStockCount] = useState(0);
  const [workflowCounts, setWorkflowCounts] = useState(null);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [aiEngineStatus, setAiEngineStatus] = useState(null);

  // Digital clock update
  useEffect(() => {
    const timer = setInterval(() => {
      setTime(new Date().toLocaleTimeString('vi-VN'));
    }, 1000);
    return () => clearInterval(timer);
  }, []);

  // Check workflow counts for operational badges
  useEffect(() => {
    if (!user) {
      setWorkflowCounts(null);
      return;
    }
    const checkWorkflowCounts = async () => {
      try {
        const counts = await ordersAPI.getWorkflowCounts();
        setWorkflowCounts(counts);
      } catch {
        // Silently ignore if unauthorized or network error
      }
    };

    checkWorkflowCounts();

    const handleWorkflowUpdated = () => {
      checkWorkflowCounts();
    };

    window.addEventListener('workflow-updated', handleWorkflowUpdated);

    const handleFocus = () => {
      if (document.visibilityState === 'visible') {
        checkWorkflowCounts();
      }
    };
    window.addEventListener('focus', handleFocus);

    const interval = setInterval(() => {
      if (document.visibilityState === 'visible') {
        checkWorkflowCounts();
      }
    }, 30000);

    return () => {
      clearInterval(interval);
      window.removeEventListener('workflow-updated', handleWorkflowUpdated);
      window.removeEventListener('focus', handleFocus);
    };
  }, [user]);

  // Check low stock count
  useEffect(() => {
    if (!user || user?.role === 'customer') return;
    const checkLowStock = async () => {
      try {
        const alerts = await inventoryAPI.getLowStockAlerts();
        setLowStockCount(alerts.length);
      } catch {
        // Silently ignore if not authorized or network error
      }
    };
    checkLowStock();
    const interval = setInterval(checkLowStock, 60000);
    return () => clearInterval(interval);
  }, [user]);

  // Check AI Engine Status for display
  useEffect(() => {
    let isMounted = true;
    const checkAI = async () => {
      try {
        const info = await aiAPI.getProviders();
        if (!isMounted) return;
        if (info?.providers?.ollama?.available) {
          setAiEngineStatus({
            label: 'Ollama GPU',
            shortLabel: 'Ollama',
            type: 'local',
            title: 'Ollama Local GPU: Qwen 2.5 1.5B (RTX 3050) - Chi phí $0'
          });
        } else if (info?.providers?.gemini?.available) {
          setAiEngineStatus({
            label: 'Gemini Cloud',
            shortLabel: 'Gemini',
            type: 'cloud',
            title: 'Google Gemini Cloud AI'
          });
        } else {
          setAiEngineStatus({
            label: 'SQLite RAG',
            shortLabel: 'SQLite',
            type: 'safe',
            title: 'Chế độ tra cứu trực tiếp SQLite'
          });
        }
      } catch {
        if (isMounted) setAiEngineStatus({ label: 'Safe Fallback', type: 'safe', title: 'Chế độ tra cứu an toàn' });
      }
    };
    checkAI();
    return () => { isMounted = false; };
  }, []);

  const getWorkflowBadge = () => {
    if (!user || !workflowCounts) return null;
    const role = user.role;
    if (role === 'superadmin') {
      const pending = workflowCounts.pending_count || 0;
      if (pending > 0) {
        return {
          label: `Đơn chờ Chủ shop duyệt: ${pending}`,
          shortLabel: `${pending}`,
          type: 'danger',
          count: pending,
        };
      }
    } else if (role === 'staff') {
      const approved = workflowCounts.approved_count || 0;
      if (approved > 0) {
        return {
          label: `Đơn đã duyệt cần xuất hóa đơn: ${approved}`,
          shortLabel: `${approved}`,
          type: 'success',
          count: approved,
        };
      }
    } else if (role === 'customer') {
      const pending = workflowCounts.my_pending_count || 0;
      const processing = workflowCounts.my_processing_count || 0;
      const total = pending + processing;
      if (total > 0) {
        return {
          label: `Đơn của tôi: ${pending} chờ duyệt, ${processing} đang xử lý`,
          shortLabel: `${total}`,
          type: 'warning',
          count: total,
        };
      }
    }
    return null;
  };

  const navItems = [
    {
      id: 'pos',
      label: !user ? 'Cửa Hàng' : (user?.role === 'customer' ? 'Mua Hàng' : 'POS Bán Hàng'),
      icon: ShoppingCart,
      roles: ['superadmin', 'staff', 'customer', 'guest'],
    },
    {
      id: 'products',
      label: user?.role === 'admin' ? 'Sản Phẩm (Read-Only)' : 'Sản Phẩm',
      icon: Package,
      roles: ['superadmin', 'admin'],
    },
    {
      id: 'orders',
      label: user?.role === 'customer' ? 'Đơn Hàng Của Tôi' : 'Hóa Đơn',
      icon: FileText,
      roles: ['superadmin', 'staff', 'customer'],
    },
    {
      id: 'customers',
      label: 'Khách Hàng',
      icon: Users,
      roles: ['superadmin', 'staff'],
    },
    {
      id: 'purchases',
      label: 'Nhập Hàng',
      icon: Truck,
      roles: ['superadmin'],
    },
    {
      id: 'dashboard',
      label: 'Doanh Thu',
      icon: BarChart3,
      roles: ['superadmin'],
    },
    {
      id: 'admin',
      label: user?.role === 'admin' ? 'Hạ Tầng & Hệ Thống' : 'Hệ Thống',
      icon: ShieldCheck,
      roles: ['superadmin', 'admin'],
    },
    {
      id: 'ai',
      label: 'AI Assistant',
      icon: Sparkles,
      roles: ['superadmin', 'admin', 'staff', 'customer', 'guest'],
    },
  ];


  const currentRole = user?.role || 'guest';
  const visibleNavItems = navItems.filter((item) =>
    item.roles.includes(currentRole)
  );


  const handleSelectTab = (tabId) => {
    onSelectTab(tabId);
    setMobileMenuOpen(false);
  };

  return (
    <>
      <header className="retro-navbar">
        <div className="nav-left-section">
          {/* Mobile Hamburger Button */}
          <button
            className="mobile-menu-toggle"
            onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
            aria-label="Toggle navigation menu"
          >
            {mobileMenuOpen ? <X size={20} /> : <Menu size={20} />}
          </button>

          <div className="nav-brand" onClick={() => handleSelectTab(user?.role === 'admin' ? 'admin' : 'pos')} style={{ cursor: 'pointer' }}>
            <span className="brand-dot" />
            <span>STOREFLOW<span style={{ color: 'var(--green-terminal)' }}>_AI</span></span>
          </div>

          {/* Desktop Navigation Links */}
          <nav className="nav-links">
            {visibleNavItems.map((item) => {
              const Icon = item.icon;
              const isActive = activeTab === item.id;
              const orderBadge = item.id === 'orders' ? getWorkflowBadge() : null;
              return (
                <button
                  key={item.id}
                  onClick={() => handleSelectTab(item.id)}
                  className={`nav-item ${isActive ? 'active' : ''} ${orderBadge ? 'has-badge' : ''}`}
                >
                  <Icon size={16} />
                  <span>{item.label}</span>
                  {orderBadge && (
                    <span
                      className={`badge ${orderBadge.type === 'danger' ? 'badge-red' : orderBadge.type === 'success' ? 'badge-green' : 'badge-amber'}`}
                      style={{
                        marginLeft: '0.35rem',
                        fontSize: '0.68rem',
                        padding: '0.1rem 0.45rem',
                        borderRadius: '999px',
                        fontWeight: 700,
                        fontFamily: 'var(--font-mono)',
                        boxShadow: orderBadge.type === 'danger' ? '0 0 8px rgba(239, 68, 68, 0.4)' : 'none',
                        whiteSpace: 'nowrap',
                      }}
                      title={orderBadge.label}
                    >
                      {orderBadge.shortLabel}
                    </span>
                  )}
                </button>
              );
            })}
          </nav>
        </div>

        {/* Desktop User Section */}
        <div className="nav-user">
          {user && lowStockCount > 0 && (
            <button
              onClick={() => handleSelectTab('products')}
              className="badge badge-amber nav-alert-btn"
              style={{ cursor: 'pointer', border: '1px solid var(--amber-primary)' }}
              title={`${lowStockCount} sản phẩm sắp hết hàng`}
            >
              <AlertTriangle size={13} />
              <span className="nav-alert-text">CẢNH BÁO</span>
              <span className="nav-alert-count">({lowStockCount})</span>
            </button>
          )}

          {aiEngineStatus && (
            <div
              onClick={() => handleSelectTab('ai')}
              className={`badge ${aiEngineStatus.type === 'local' ? 'badge-green' : aiEngineStatus.type === 'cloud' ? 'badge-blue' : 'badge-amber'} nav-ai-status-badge`}
              style={{
                cursor: 'pointer',
                fontSize: '0.68rem',
                padding: '0.2rem 0.5rem',
                display: 'inline-flex',
                alignItems: 'center',
                gap: '4px',
                fontFamily: 'var(--font-mono)',
                borderRadius: '999px',
                border: '1px solid var(--border-default)',
                flexShrink: 0,
                whiteSpace: 'nowrap',
              }}
              title={aiEngineStatus.title}
            >
              <Cpu size={12} />
              <span className="ai-status-full">{aiEngineStatus.label}</span>
              <span className="ai-status-short">{aiEngineStatus.shortLabel}</span>
            </div>
          )}

          <ThemeToggle />

          <div className="clock-display">
            <Clock size={12} style={{ display: 'inline', marginRight: '4px' }} />
            {time}
          </div>

          {user ? (
            <>
              <div className="user-profile-badge" title={user?.full_name}>
                <span className="user-full-name">{user?.full_name}</span>
                <RoleBadge role={user?.role} short />
              </div>

              <button
                onClick={logout}
                className="btn btn-outline btn-sm logout-btn"
                title="Đăng xuất"
                style={{ borderColor: 'var(--border-subtle)' }}
              >
                <LogOut size={14} />
                <span className="logout-text">Thoát</span>
              </button>
            </>
          ) : (
            <button
              onClick={() => handleSelectTab('login')}
              className="btn btn-primary btn-sm login-btn"
            >
              <LogIn size={14} />
              <span>Đăng Nhập</span>
            </button>
          )}
        </div>
      </header>


      {/* Mobile Drawer Menu */}
      {mobileMenuOpen && (
        <div className="mobile-nav-backdrop" onClick={() => setMobileMenuOpen(false)}>
          <div className="mobile-nav-drawer" onClick={(e) => e.stopPropagation()}>
            <div className="mobile-drawer-header">
              <div className="nav-brand">
                <span className="brand-dot" />
                <span>STOREFLOW<span style={{ color: 'var(--green-terminal)' }}>_AI</span></span>
              </div>
              <button
                onClick={() => setMobileMenuOpen(false)}
                className="btn btn-outline btn-icon btn-sm"
                style={{ border: 'none' }}
              >
                <X size={18} />
              </button>
            </div>

            {user ? (
              <div className="mobile-user-card">
                <div style={{ fontWeight: 600, color: 'var(--text-primary)' }}>{user?.full_name}</div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '4px' }}>
                  <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>@{user?.username}</span>
                  <RoleBadge role={user?.role} />
                </div>
                <div style={{ fontSize: '0.75rem', color: 'var(--amber-light)', marginTop: '6px', fontFamily: 'var(--font-mono)' }}>
                  <Clock size={11} style={{ display: 'inline', marginRight: '4px' }} />
                  {time}
                </div>
              </div>
            ) : (
              <div className="mobile-user-card" style={{ textAlign: 'center' }}>
                <div style={{ fontWeight: 600, color: 'var(--text-primary)' }}>Khách vãng lai (Guest)</div>
                <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '4px' }}>Duyệt xem sản phẩm công khai</div>
                <button
                  onClick={() => handleSelectTab('login')}
                  className="btn btn-primary btn-sm"
                  style={{ width: '100%', marginTop: '0.75rem', justifyContent: 'center' }}
                >
                  <LogIn size={14} /> Đăng Nhập Hệ Thống
                </button>
              </div>
            )}
            
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                padding: '0.65rem 0.85rem',
                margin: '0.75rem 0',
                background: 'var(--bg-input)',
                border: '1px solid var(--border-subtle)',
                borderRadius: 'var(--radius-xs)',
              }}
            >
              <span style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-secondary)' }}>
                GIAO DIỆN
              </span>
              <ThemeToggle showLabel />
            </div>

            {aiEngineStatus && (
              <div
                onClick={() => handleSelectTab('ai')}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  padding: '0.65rem 0.85rem',
                  marginBottom: '0.75rem',
                  background: 'var(--bg-input)',
                  border: '1px solid var(--border-subtle)',
                  borderRadius: 'var(--radius-xs)',
                  cursor: 'pointer',
                }}
                title={aiEngineStatus.title}
              >
                <span style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-secondary)', display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <Cpu size={14} color="var(--green-terminal)" /> AI ENGINE
                </span>
                <span className={`badge ${aiEngineStatus.type === 'local' ? 'badge-green' : aiEngineStatus.type === 'cloud' ? 'badge-blue' : 'badge-amber'}`} style={{ fontSize: '0.72rem' }}>
                  {aiEngineStatus.label}
                </span>
              </div>
            )}

            {user && lowStockCount > 0 && (
              <button
                onClick={() => handleSelectTab('products')}
                className="badge badge-amber"
                style={{ width: '100%', margin: '0.5rem 0 0.75rem', padding: '0.6rem', justifyContent: 'center', cursor: 'pointer' }}
              >
                <AlertTriangle size={15} />
                <span>{lowStockCount} SẢN PHẨM CẦN NHẬP KHO</span>
              </button>
            )}

            <nav className="mobile-nav-list">
              {visibleNavItems.map((item) => {
                const Icon = item.icon;
                const isActive = activeTab === item.id;
                const orderBadge = item.id === 'orders' ? getWorkflowBadge() : null;
                return (
                  <button
                    key={item.id}
                    onClick={() => handleSelectTab(item.id)}
                    className={`mobile-nav-item ${isActive ? 'active' : ''}`}
                  >
                    <Icon size={18} />
                    <span>{item.label}</span>
                    {orderBadge && (
                      <span
                        className={`badge ${orderBadge.type === 'danger' ? 'badge-red' : orderBadge.type === 'success' ? 'badge-green' : 'badge-amber'}`}
                        style={{
                          marginLeft: 'auto',
                          fontSize: '0.68rem',
                          padding: '0.1rem 0.45rem',
                          borderRadius: '999px',
                          fontWeight: 700,
                          fontFamily: 'var(--font-mono)',
                        }}
                        title={orderBadge.label}
                      >
                        {orderBadge.shortLabel}
                      </span>
                    )}
                  </button>
                );
              })}
            </nav>

            {user && (
              <div style={{ marginTop: 'auto', paddingTop: '1rem', borderTop: '1px solid var(--border-subtle)' }}>
                <button
                  onClick={logout}
                  className="btn btn-outline btn-sm"
                  style={{ width: '100%', color: 'var(--red-light)', borderColor: 'var(--border-subtle)', justifyContent: 'center' }}
                >
                  <LogOut size={16} />
                  <span>Đăng Xuất Tài Khoản</span>
                </button>
              </div>
            )}
          </div>
        </div>
      )}

    </>
  );
};

