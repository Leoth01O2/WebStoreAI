import React, { useState, useEffect } from 'react';
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

function AppContent() {
  const { isAuthenticated, loading, user, isAdmin, isSuperAdmin } = useAuth();
  const [activeTab, setActiveTab] = useState('pos');

  // RBAC safety check: if user role changes or lacks permission for current tab
  useEffect(() => {
    if (!isAuthenticated) {
      if (activeTab !== 'pos' && activeTab !== 'login' && activeTab !== 'ai') {
        setActiveTab('pos');
      }
    } else {
      if (activeTab === 'login') {
        setActiveTab(user?.role === 'admin' ? 'admin' : 'pos');
      }
      if (user?.role === 'admin') {
        const forbiddenForAdmin = ['pos', 'orders', 'customers', 'purchases', 'dashboard'];
        if (forbiddenForAdmin.includes(activeTab)) {
          setActiveTab('admin');
        }
      } else if (user?.role === 'staff') {
        const forbiddenForStaff = ['products', 'purchases', 'dashboard', 'admin'];
        if (forbiddenForStaff.includes(activeTab)) {
          setActiveTab('pos');
        }
      } else if (user?.role === 'customer') {
        const forbiddenForCustomer = ['products', 'purchases', 'dashboard', 'customers', 'admin'];
        if (forbiddenForCustomer.includes(activeTab)) {
          setActiveTab('pos');
        }
      }
    }
  }, [isAuthenticated, user, activeTab]);

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
    return <LoginPage onBack={() => setActiveTab('pos')} />;
  }

  const renderActivePage = () => {
    if (!isAuthenticated) {
      if (activeTab === 'ai') {
        return <AiAssistantPage onNavigate={setActiveTab} />;
      }
      return <PosPage onNavigate={setActiveTab} />;
    }

    switch (activeTab) {
      case 'pos':
        if (user?.role === 'admin') return <AdminPage />;
        return <PosPage onNavigate={setActiveTab} />;
      case 'products':
        if (user?.role === 'customer' || user?.role === 'staff') return <PosPage onNavigate={setActiveTab} />;
        return <ProductsPage />;
      case 'orders':
        if (user?.role === 'admin') return <AdminPage />;
        return <OrdersPage />;
      case 'customers':
        if (user?.role === 'customer' || user?.role === 'admin') return <PosPage onNavigate={setActiveTab} />;
        return <CustomersPage />;
      case 'purchases':
        if (!isSuperAdmin) return <PosPage onNavigate={setActiveTab} />;
        return <PurchasesPage />;
      case 'dashboard':
        if (!isSuperAdmin) return <PosPage onNavigate={setActiveTab} />;
        return <DashboardPage onNavigate={setActiveTab} />;
      case 'admin':
        if (!isAdmin && !isSuperAdmin) return <PosPage onNavigate={setActiveTab} />;
        return <AdminPage />;
      case 'ai':
        return <AiAssistantPage onNavigate={setActiveTab} />;
      default:
        return user?.role === 'admin' ? <AdminPage /> : <PosPage onNavigate={setActiveTab} />;
    }
  };

  return (
    <div className="app-container">
      <Navbar activeTab={activeTab} onSelectTab={setActiveTab} />
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
