import React, { useState } from 'react';
import { ShieldCheck, User, Lock, ArrowRight, ArrowLeft, Terminal } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { useToast } from '../context/ToastContext';
import { ThemeToggle } from '../components/layout/ThemeToggle';

export const LoginPage = ({ onBack }) => {
  const { login } = useAuth();
  const { addToast } = useToast();


  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleLogin = async (e) => {
    if (e) e.preventDefault();
    if (!username.trim() || !password) {
      setError('Vui lòng nhập đầy đủ tên đăng nhập và mật khẩu');
      return;
    }

    setLoading(true);
    setError('');

    try {
      const user = await login(username.trim(), password);
      addToast(`Chào mừng ${user.full_name} (${user.role.toUpperCase()}) đăng nhập thành công!`, 'success');
    } catch (err) {
      setError(err.message || 'Đăng nhập thất bại. Kiểm tra lại thông tin.');
    } finally {
      setLoading(false);
    }
  };

  const handleQuickDemo = (demoUser, demoPass) => {
    setUsername(demoUser);
    setPassword(demoPass);
    setError('');
  };

  return (
    <div
      style={{
        minHeight: '100vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '1.5rem',
        background: 'radial-gradient(circle at center, var(--bg-panel) 0%, var(--bg-app) 100%)',
      }}
    >
      <div
        className="retro-card"
        style={{
          width: '100%',
          maxWidth: '460px',
          border: '2px solid var(--border-highlight)',
          boxShadow: '0 0 30px rgba(0, 0, 0, 0.5), var(--shadow-retro-lg)',
        }}
      >
        <div className="retro-card-header" style={{ justifyContent: 'center', flexDirection: 'column', gap: '0.4rem', textAlign: 'center', padding: '1.25rem 1rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: 'var(--amber-primary)', fontWeight: 800, fontSize: '1.3rem', fontFamily: 'var(--font-mono)' }}>
            <Terminal size={24} />
            <span>STOREFLOW_AI v1.0</span>
          </div>
          <div style={{ fontSize: '0.78rem', color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
            Hệ thống Quản lý Bán hàng & POS Retro-Futuristic
          </div>
        </div>

        <div className="retro-card-body" style={{ padding: '1.5rem' }}>
          <div style={{ display: 'flex', justifyContent: onBack ? 'space-between' : 'flex-end', alignItems: 'center', marginBottom: '1.2rem', gap: '0.5rem' }}>
            {onBack ? (
              <button
                type="button"
                onClick={onBack}
                className="btn btn-outline btn-sm"
                style={{ display: 'inline-flex', alignItems: 'center', gap: '0.4rem', borderColor: 'var(--border-subtle)', fontSize: '0.8rem' }}
              >
                <ArrowLeft size={14} /> Quay lại xem sản phẩm
              </button>
            ) : null}
            <ThemeToggle showLabel />
          </div>

          {error && (
            <div
              className="badge badge-red"
              style={{
                width: '100%',
                padding: '0.6rem 0.8rem',
                marginBottom: '1rem',
                fontSize: '0.8rem',
                justifyContent: 'center',
                whiteSpace: 'normal',
                textAlign: 'center',
              }}
            >
              [LỖI] {error}
            </div>
          )}

          <form onSubmit={handleLogin}>
            <div className="form-group">
              <label className="form-label">Tài khoản (Username)</label>
              <div className="input-with-icon">
                <User size={16} />
                <input
                  type="text"
                  className="form-control font-mono"
                  placeholder="superadmin / admin / staff / customer"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  autoFocus
                />
              </div>
            </div>

            <div className="form-group" style={{ marginBottom: '1.25rem' }}>
              <label className="form-label">Mật khẩu (Password)</label>
              <div className="input-with-icon">
                <Lock size={16} />
                <input
                  type="password"
                  className="form-control font-mono"
                  placeholder="Nhập mật khẩu..."
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                />
              </div>
            </div>

            <button
              type="submit"
              className="btn btn-primary"
              style={{ width: '100%', padding: '0.75rem' }}
              disabled={loading}
            >
              {loading ? 'Đang xác thực...' : 'ĐĂNG NHẬP VÀO HỆ THỐNG'} <ArrowRight size={16} />
            </button>
          </form>

          {/* Quick Demo Logins */}
          <div style={{ marginTop: '1.5rem', paddingTop: '1.25rem', borderTop: '1px dashed var(--border-default)' }}>
            <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '0.6rem', textAlign: 'center', fontFamily: 'var(--font-mono)' }}>
              ⚡ CHỌN NHANH TÀI KHOẢN DEMO
            </div>
            <div className="login-demo-grid">
              <button
                type="button"
                className="btn btn-outline btn-sm"
                onClick={() => handleQuickDemo('superadmin', 'SuperAdmin@123')}
                style={{ flexDirection: 'column', padding: '0.4rem 0.15rem' }}
              >
                <span style={{ color: 'var(--blue-cyber)', fontWeight: 'bold', fontSize: '0.75rem' }}>SUPERADMIN</span>
                <span style={{ fontSize: '0.62rem', color: 'var(--text-muted)' }}>Chủ shop</span>
              </button>

              <button
                type="button"
                className="btn btn-outline btn-sm"
                onClick={() => handleQuickDemo('admin', 'Admin@123')}
                style={{ flexDirection: 'column', padding: '0.4rem 0.15rem' }}
              >
                <span style={{ color: 'var(--amber-primary)', fontWeight: 'bold', fontSize: '0.75rem' }}>ADMIN</span>
                <span style={{ fontSize: '0.62rem', color: 'var(--text-muted)' }}>Quản trị</span>
              </button>

              <button
                type="button"
                className="btn btn-outline btn-sm"
                onClick={() => handleQuickDemo('staff', 'Staff@123')}
                style={{ flexDirection: 'column', padding: '0.4rem 0.15rem' }}
              >
                <span style={{ color: 'var(--green-terminal)', fontWeight: 'bold', fontSize: '0.75rem' }}>STAFF</span>
                <span style={{ fontSize: '0.62rem', color: 'var(--text-muted)' }}>Thu ngân</span>
              </button>

              <button
                type="button"
                className="btn btn-outline btn-sm"
                onClick={() => handleQuickDemo('customer', 'Customer@123')}
                style={{ flexDirection: 'column', padding: '0.4rem 0.15rem' }}
              >
                <span style={{ color: 'var(--text-muted)', fontWeight: 'bold', fontSize: '0.75rem' }}>CUSTOMER</span>
                <span style={{ fontSize: '0.62rem', color: 'var(--text-muted)' }}>Khách mua</span>
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
