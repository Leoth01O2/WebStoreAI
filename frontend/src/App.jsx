import React, { useState, useEffect, useCallback } from 'react';
import { AuthProvider, useAuth } from './context/AuthContext';
import { ToastProvider } from './context/ToastContext';
import { ThemeProvider } from './context/ThemeContext';
import { Navbar } from './components/layout/Navbar';
import { ErrorBoundary } from './components/common/ErrorBoundary';
import { LoginPage } from './pages/LoginPage';
import { PosPage } from './pages/PosPage';
import { ProductsPage } from './pages/ProductsPage';
import { OrdersPage } from './pages/OrdersPage';
import { PurchasesPage } from './pages/PurchasesPage';
import { CustomersPage } from './pages/CustomersPage';
import { DashboardPage } from './pages/DashboardPage';
import { AiAssistantPage } from './pages/AiAssistantPage';
import { AdminPage } from './pages/AdminPage';

const VALID_TABS = ['pos', 'products', 'orders', 'customers', 'purchases', 'dashboard', 'admin', 'ai', 'login'];

const getCleanHash = () => {
  if (typeof window === 'undefined') return '';
  return window.location.hash.replace(/^#\/?/, '').trim();
};

const getInitialTab = () => {
  try {
    const hash = getCleanHash();
    if (VALID_TABS.includes(hash)) {
      return hash;
    }
    const saved = localStorage.getItem('sf_active_tab');
    if (VALID_TABS.includes(saved)) {
      return saved;
    }
  } catch {
    // Ignore storage errors in restricted contexts
  }
  return 'pos';
};

function AppContent() {
  const { isAuthenticated, loading, user, isAdmin, isSuperAdmin } = useAuth();
  const [activeTab, setActiveTab] = useState(getInitialTab);

  const navigateTab = useCallback((newTab) => {
    if (!VALID_TABS.includes(newTab)) return;
    setActiveTab(newTab);
    try {
      localStorage.setItem('sf_active_tab', newTab);
    } catch {
      // Ignore
    }
    if (getCleanHash() !== newTab) {
      window.location.hash = newTab;
    }
  }, []);

  // Sync hash change from browser Back/Forward navigation
  useEffect(() => {
    const handleHashChange = () => {
      const currentHash = getCleanHash();
      if (VALID_TABS.includes(currentHash)) {
        setActiveTab((prev) => {
          if (prev !== currentHash) {
            try {
              localStorage.setItem('sf_active_tab', currentHash);
            } catch {
              // Ignore
            }
            return currentHash;
          }
          return prev;
        });
      }
    };

    window.addEventListener('hashchange', handleHashChange);
    return () => window.removeEventListener('hashchange', handleHashChange);
  }, []);

  // Ensure URL hash stays in sync with activeTab
  useEffect(() => {
    if (getCleanHash() !== activeTab) {
      window.location.hash = activeTab;
    }
  }, [activeTab]);

  // RBAC safety check: if user role changes or lacks permission for current tab
  useEffect(() => {
    if (loading) return;

    if (!isAuthenticated) {
      if (activeTab !== 'pos' && activeTab !== 'login' && activeTab !== 'ai') {
        navigateTab('pos');
      }
    } else {
      if (activeTab === 'login') {
        navigateTab(user?.role === 'admin' ? 'admin' : 'pos');
      } else if (user?.role === 'admin') {
        const forbiddenForAdmin = ['pos', 'orders', 'customers', 'purchases', 'dashboard'];
        if (forbiddenForAdmin.includes(activeTab)) {
          navigateTab('admin');
        }
      } else if (user?.role === 'staff') {
        const forbiddenForStaff = ['products', 'purchases', 'dashboard', 'admin'];
        if (forbiddenForStaff.includes(activeTab)) {
          navigateTab('pos');
        }
      } else if (user?.role === 'customer') {
        const forbiddenForCustomer = ['products', 'purchases', 'dashboard', 'customers', 'admin'];
        if (forbiddenForCustomer.includes(activeTab)) {
          navigateTab('pos');
        }
      }
    }
  }, [isAuthenticated, user, activeTab, loading, navigateTab]);

  if (loading) {
    return (
      <div
        style={{
          minHeight: '100vh',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          gap: '1rem',
          fontFamily: 'var(--font-mono)',
          color: 'var(--amber-primary)',
          background: 'var(--bg-app)',
        }}
      >
        <div style={{ fontSize: '1.5rem', fontWeight: 800 }}>⚡ STOREFLOW_AI</div>
        <div style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
          [SYSTEM_INIT] Đang khởi động hệ thống và kết nối cơ sở dữ liệu SQLite...
        </div>
      </div>
    );
  }

  // If user requested login page
  if (activeTab === 'login' && !isAuthenticated) {
    return <LoginPage onBack={() => navigateTab('pos')} />;
  }

  const renderActivePage = () => {
    if (!isAuthenticated) {
      if (activeTab === 'ai') {
        return <AiAssistantPage onNavigate={navigateTab} />;
      }
      return <PosPage onNavigate={navigateTab} />;
    }

    switch (activeTab) {
      case 'pos':
        if (user?.role === 'admin') return <AdminPage />;
        return <PosPage onNavigate={navigateTab} />;
      case 'products':
        if (user?.role === 'customer' || user?.role === 'staff') return <PosPage onNavigate={navigateTab} />;
        return <ProductsPage />;
      case 'orders':
        if (user?.role === 'admin') return <AdminPage />;
        return <OrdersPage />;
      case 'customers':
        if (user?.role === 'customer' || user?.role === 'admin') return <PosPage onNavigate={navigateTab} />;
        return <CustomersPage />;
      case 'purchases':
        if (!isSuperAdmin) return <PosPage onNavigate={navigateTab} />;
        return <PurchasesPage />;
      case 'dashboard':
        if (!isSuperAdmin) return <PosPage onNavigate={navigateTab} />;
        return <DashboardPage onNavigate={navigateTab} />;
      case 'admin':
        if (!isAdmin && !isSuperAdmin) return <PosPage onNavigate={navigateTab} />;
        return <AdminPage />;
      case 'ai':
        return <AiAssistantPage onNavigate={navigateTab} />;
      default:
        return user?.role === 'admin' ? <AdminPage /> : <PosPage onNavigate={navigateTab} />;
    }
  };

  return (
    <div className="app-container">
      <Navbar activeTab={activeTab} onSelectTab={navigateTab} />
      <main className="main-content">
        <ErrorBoundary>
          {renderActivePage()}
        </ErrorBoundary>
      </main>
    </div>
  );
}

export default function App() {
  return (
    <ErrorBoundary>
      <ThemeProvider>
        <ToastProvider>
          <AuthProvider>
            <AppContent />
          </AuthProvider>
        </ToastProvider>
      </ThemeProvider>
    </ErrorBoundary>
  );
}
