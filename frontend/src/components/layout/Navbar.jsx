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
} from 'lucide-react';
import { useAuth } from '../../context/AuthContext';
import { RoleBadge } from '../ui/Badge';
import { inventoryAPI } from '../../services/api';
import { ThemeToggle } from './ThemeToggle';

export const Navbar = ({ activeTab, onSelectTab }) => {
  const { user, logout, isAdmin, isManager } = useAuth();
  const [time, setTime] = useState(new Date().toLocaleTimeString('vi-VN'));
  const [lowStockCount, setLowStockCount] = useState(0);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  // Digital clock update
  useEffect(() => {
    const timer = setInterval(() => {
      setTime(new Date().toLocaleTimeString('vi-VN'));
    }, 1000);
    return () => clearInterval(timer);
  }, []);

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

  const navItems = [
    {
      id: 'pos',
      label: !user ? 'Cửa Hàng (Storefront)' : (user?.role === 'customer' ? 'Mua Hàng (POS)' : 'POS Bán Hàng'),
      icon: ShoppingCart,
      roles: ['superadmin', 'admin', 'manager', 'staff', 'customer', 'guest'],
    },
    { id: 'products', label: 'Sản Phẩm & Kho', icon: Package, roles: ['superadmin', 'admin', 'manager'] },
    { id: 'orders', label: user?.role === 'customer' ? 'Đơn Hàng Của Tôi' : 'Hóa Đơn', icon: FileText, roles: ['superadmin', 'admin', 'manager', 'staff', 'customer'] },
    { id: 'customers', label: 'Khách Hàng', icon: Users, roles: ['superadmin', 'admin', 'manager'] },
    { id: 'purchases', label: 'Nhập Hàng', icon: Truck, roles: ['superadmin', 'admin', 'manager'] },
    { id: 'dashboard', label: 'Doanh Thu', icon: BarChart3, roles: ['superadmin', 'manager'] },
    { id: 'ai', label: 'AI Assistant', icon: Sparkles, roles: ['superadmin', 'admin', 'manager', 'staff', 'customer', 'guest'] },
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
        <div style={{ display: 'flex', alignItems: 'center', gap: '1.25rem' }}>
          {/* Mobile Hamburger Button */}
          <button
            className="mobile-menu-toggle"
            onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
            aria-label="Toggle navigation menu"
            style={{
              display: 'none',
              background: 'transparent',
              border: '1px solid var(--border-color)',
              color: 'var(--text-primary)',
              borderRadius: '4px',
              padding: '0.4rem',
              cursor: 'pointer',
            }}
          >
            {mobileMenuOpen ? <X size={20} /> : <Menu size={20} />}
          </button>

          <div className="nav-brand" onClick={() => handleSelectTab('pos')} style={{ cursor: 'pointer' }}>
            <span className="brand-dot" />
            <span>STOREFLOW<span style={{ color: 'var(--green-terminal)' }}>_AI</span></span>
          </div>

          {/* Desktop Navigation Links */}
          <nav className="nav-links">
            {visibleNavItems.map((item) => {
              const Icon = item.icon;
              const isActive = activeTab === item.id;
              return (
                <button
                  key={item.id}
                  onClick={() => handleSelectTab(item.id)}
                  className={`nav-item ${isActive ? 'active' : ''}`}
                >
                  <Icon size={16} />
                  <span>{item.label}</span>
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
              style={{ cursor: 'pointer', border: '1px solid var(--amber-primary)', padding: '0.3rem 0.6rem' }}
              title={`${lowStockCount} sản phẩm sắp hết hàng`}
            >
              <AlertTriangle size={14} />
              <span>CẢNH BÁO ({lowStockCount})</span>
            </button>
          )}

          <ThemeToggle />

          <div className="clock-display">
            <Clock size={12} style={{ display: 'inline', marginRight: '4px' }} />
            {time}
          </div>

          {user ? (
            <>
              <div className="user-profile-badge" style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <span style={{ fontWeight: 600, fontSize: '0.85rem' }}>{user?.full_name}</span>
                <RoleBadge role={user?.role} />
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
              style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', padding: '0.35rem 0.85rem' }}
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
                return (
                  <button
                    key={item.id}
                    onClick={() => handleSelectTab(item.id)}
                    className={`mobile-nav-item ${isActive ? 'active' : ''}`}
                  >
                    <Icon size={18} />
                    <span>{item.label}</span>
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

