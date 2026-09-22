import React, { useState, useEffect } from 'react';
import { AuthProvider, useAuth } from './context/AuthContext';
import { ToastProvider } from './context/ToastContext';
import { ThemeProvider } from './context/ThemeContext';
import { Navbar } from './components/layout/Navbar';
import { LoginPage } from './pages/LoginPage';
import { PosPage } from './pages/PosPage';
import { ProductsPage } from './pages/ProductsPage';
import { OrdersPage } from './pages/OrdersPage';
import { PurchasesPage } from './pages/PurchasesPage';
import { CustomersPage } from './pages/CustomersPage';
import { DashboardPage } from './pages/DashboardPage';
import { AiAssistantPage } from './pages/AiAssistantPage';

function AppContent() {
  const { isAuthenticated, loading, user, isAdmin, isSuperAdmin, isManager } = useAuth();
  const [activeTab, setActiveTab] = useState('pos');

  // RBAC safety check: if user role changes or lacks permission for current tab
  useEffect(() => {
    if (!isAuthenticated) {
      if (activeTab !== 'pos' && activeTab !== 'login' && activeTab !== 'ai') {
        setActiveTab('pos');
      }
    } else {
      if (activeTab === 'login') {
        setActiveTab('pos');
      }
      if (user?.role === 'admin' && activeTab === 'dashboard') {
        setActiveTab('pos');
      }
      if (user?.role === 'staff' && (activeTab === 'purchases' || activeTab === 'dashboard' || activeTab === 'customers' || activeTab === 'products')) {
        setActiveTab('pos');
      }
      if (user?.role === 'customer' && (activeTab === 'products' || activeTab === 'purchases' || activeTab === 'dashboard' || activeTab === 'customers')) {
        setActiveTab('pos');
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
        return <PosPage onNavigate={setActiveTab} />;
      case 'products':
        if (user?.role === 'customer') return <PosPage onNavigate={setActiveTab} />;
        return <ProductsPage />;
      case 'orders':
        return <OrdersPage />;
      case 'customers':
        if (user?.role === 'customer') return <PosPage onNavigate={setActiveTab} />;
        return <CustomersPage />;
      case 'purchases':
        if (!isAdmin && !isSuperAdmin && !isManager) return <PosPage onNavigate={setActiveTab} />;
        return <PurchasesPage />;
      case 'dashboard':
        if (!isSuperAdmin && !isManager) return <PosPage onNavigate={setActiveTab} />;
        return <DashboardPage onNavigate={setActiveTab} />;
      case 'ai':
        return <AiAssistantPage onNavigate={setActiveTab} />;
      default:
        return <PosPage onNavigate={setActiveTab} />;
    }
  };



  return (
    <div className="app-container">
      <Navbar activeTab={activeTab} onSelectTab={setActiveTab} />
      <main className="main-content">
        {renderActivePage()}
      </main>
    </div>
  );
}

export default function App() {
  return (
    <ThemeProvider>
      <ToastProvider>
        <AuthProvider>
          <AppContent />
        </AuthProvider>
      </ToastProvider>
    </ThemeProvider>
  );
}
