import React, { useState } from 'react';
import {
  ShieldCheck,
  User,
  Lock,
  ArrowRight,
  ArrowLeft,
  Terminal,
  UserPlus,
  LogIn,
  Phone,
  Mail,
  MapPin,
  CheckCircle2,
} from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { useToast } from '../context/ToastContext';
import { authAPI } from '../services/api';
import { ThemeToggle } from '../components/layout/ThemeToggle';

export const LoginPage = ({ onBack }) => {
  const { login } = useAuth();
  const { addToast } = useToast();

  const [mode, setMode] = useState('login'); // 'login' | 'register'

  // Login form state
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  // Register form state
  const [regForm, setRegForm] = useState({
    username: '',
    password: '',
    confirm_password: '',
    full_name: '',
    phone: '',
    email: '',
    address: '',
  });
  const [regLoading, setRegLoading] = useState(false);
  const [regError, setRegError] = useState('');

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

  const handleRegister = async (e) => {
    if (e) e.preventDefault();
    setRegError('');

    if (!regForm.username.trim() || regForm.username.length < 3) {
      setRegError('Tên đăng nhập phải từ 3 đến 30 ký tự.');
      return;
    }
    if (!regForm.password || regForm.password.length < 6) {
      setRegError('Mật khẩu bảo mật phải có ít nhất 6 ký tự.');
      return;
    }
    if (regForm.password !== regForm.confirm_password) {
      setRegError('Mật khẩu xác nhận không khớp.');
      return;
    }
    if (!regForm.full_name.trim()) {
      setRegError('Vui lòng nhập họ và tên của bạn.');
      return;
    }
    if (!regForm.phone.trim() || regForm.phone.trim().length < 9) {
      setRegError('Vui lòng nhập số điện thoại hợp lệ (10 số).');
      return;
    }
    if (!regForm.email.trim() || !regForm.email.includes('@')) {
      setRegError('Vui lòng nhập địa chỉ email hợp lệ.');
      return;
    }

    setRegLoading(true);
    try {
      const payload = {
        username: regForm.username.trim(),
        password: regForm.password,
        full_name: regForm.full_name.trim(),
        phone: regForm.phone.trim(),
        email: regForm.email.trim().toLowerCase(),
        address: regForm.address.trim() || null,
      };

      const result = await authAPI.register(payload);
      addToast(`Đăng ký thành viên "${result.full_name}" thành công! Vui lòng đăng nhập.`, 'success');

      // Auto switch to login with pre-filled username
      setUsername(result.username);
      setPassword('');
      setMode('login');
      setError('');
    } catch (err) {
      setRegError(err.message || 'Đăng ký tài khoản thất bại. Vui lòng kiểm tra lại.');
    } finally {
      setRegLoading(false);
    }
  };

  const handleQuickDemo = (demoUser, demoPass) => {
    setMode('login');
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
          maxWidth: mode === 'register' ? '540px' : '460px',
          border: '2px solid var(--border-highlight)',
          boxShadow: '0 0 30px rgba(0, 0, 0, 0.5), var(--shadow-retro-lg)',
          transition: 'max-width 0.2s ease',
        }}
      >
        <div
          className="retro-card-header"
          style={{
            justifyContent: 'center',
            flexDirection: 'column',
            gap: '0.4rem',
            textAlign: 'center',
            padding: '1.25rem 1rem',
          }}
        >
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '0.5rem',
              color: 'var(--amber-primary)',
              fontWeight: 800,
              fontSize: '1.3rem',
              fontFamily: 'var(--font-mono)',
            }}
          >
            <Terminal size={24} />
            <span>STOREFLOW_AI v2.0</span>
          </div>
          <div
            style={{
              fontSize: '0.78rem',
              color: 'var(--text-secondary)',
              textTransform: 'uppercase',
              letterSpacing: '0.06em',
            }}
          >
            Hệ thống Quản lý Bán hàng & POS Retro-Futuristic
          </div>
        </div>

        <div className="retro-card-body" style={{ padding: '1.5rem' }}>
          {/* Top back button & theme toggle */}
          <div
            style={{
              display: 'flex',
              justifyContent: onBack ? 'space-between' : 'flex-end',
              alignItems: 'center',
              marginBottom: '1rem',
              gap: '0.5rem',
            }}
          >
            {onBack ? (
              <button
                type="button"
                onClick={onBack}
                className="btn btn-outline btn-sm"
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '0.4rem',
                  borderColor: 'var(--border-subtle)',
                  fontSize: '0.8rem',
                }}
              >
                <ArrowLeft size={14} /> Quay lại xem sản phẩm
              </button>
            ) : null}
            <ThemeToggle showLabel />
          </div>

          {/* Mode Switcher Tabs */}
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: '1fr 1fr',
              gap: '0.5rem',
              marginBottom: '1.25rem',
              background: 'var(--bg-input)',
              padding: '0.35rem',
              border: '1px solid var(--border-subtle)',
              borderRadius: 'var(--radius-xs)',
            }}
          >
            <button
              type="button"
              onClick={() => {
                setMode('login');
                setError('');
              }}
              className={`btn btn-sm ${mode === 'login' ? 'btn-primary' : 'btn-outline'}`}
              style={{
                border: mode === 'login' ? 'none' : '1px solid transparent',
                fontSize: '0.8rem',
              }}
            >
              <LogIn size={14} /> ĐĂNG NHẬP
            </button>
            <button
              type="button"
              onClick={() => {
                setMode('register');
                setRegError('');
              }}
              className={`btn btn-sm ${mode === 'register' ? 'btn-primary' : 'btn-outline'}`}
              style={{
                border: mode === 'register' ? 'none' : '1px solid transparent',
                fontSize: '0.8rem',
              }}
            >
              <UserPlus size={14} /> ĐĂNG KÝ MỚI
            </button>
          </div>

          {/* ================= LOGIN FORM ================= */}
          {mode === 'login' && (
            <>
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
              <div
                style={{
                  marginTop: '1.5rem',
                  paddingTop: '1.25rem',
                  borderTop: '1px dashed var(--border-default)',
                }}
              >
                <div
                  style={{
                    fontSize: '0.75rem',
                    color: 'var(--text-muted)',
                    marginBottom: '0.6rem',
                    textAlign: 'center',
                    fontFamily: 'var(--font-mono)',
                  }}
                >
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
            </>
          )}

          {/* ================= REGISTER FORM ================= */}
          {mode === 'register' && (
            <>
              {regError && (
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
                  [LỖI ĐĂNG KÝ] {regError}
                </div>
              )}

              <form onSubmit={handleRegister}>
                <div className="form-group">
                  <label className="form-label">Họ và tên khách hàng (*)</label>
                  <input
                    type="text"
                    required
                    className="form-control"
                    placeholder="Nguyễn Văn A"
                    value={regForm.full_name}
                    onChange={(e) => setRegForm({ ...regForm, full_name: e.target.value })}
                  />
                </div>

                <div className="form-grid-2">
                  <div className="form-group">
                    <label className="form-label">Tên đăng nhập (*)</label>
                    <div className="input-with-icon">
                      <User size={15} />
                      <input
                        type="text"
                        required
                        className="form-control font-mono"
                        placeholder="min 3 ký tự"
                        value={regForm.username}
                        onChange={(e) => setRegForm({ ...regForm, username: e.target.value })}
                      />
                    </div>
                  </div>

                  <div className="form-group">
                    <label className="form-label">Số điện thoại (*)</label>
                    <div className="input-with-icon">
                      <Phone size={15} />
                      <input
                        type="tel"
                        required
                        className="form-control font-mono"
                        placeholder="0901234567"
                        value={regForm.phone}
                        onChange={(e) => setRegForm({ ...regForm, phone: e.target.value })}
                      />
                    </div>
                  </div>
                </div>

                <div className="form-group">
                  <label className="form-label">Email (*)</label>
                  <div className="input-with-icon">
                    <Mail size={15} />
                    <input
                      type="email"
                      required
                      className="form-control"
                      placeholder="email@example.com"
                      value={regForm.email}
                      onChange={(e) => setRegForm({ ...regForm, email: e.target.value })}
                    />
                  </div>
                </div>

                <div className="form-grid-2">
                  <div className="form-group">
                    <label className="form-label">Mật khẩu (*)</label>
                    <div className="input-with-icon">
                      <Lock size={15} />
                      <input
                        type="password"
                        required
                        className="form-control font-mono"
                        placeholder="Tối thiểu 6 ký tự"
                        value={regForm.password}
                        onChange={(e) => setRegForm({ ...regForm, password: e.target.value })}
                      />
                    </div>
                  </div>

                  <div className="form-group">
                    <label className="form-label">Xác nhận mật khẩu (*)</label>
                    <div className="input-with-icon">
                      <Lock size={15} />
                      <input
                        type="password"
                        required
                        className="form-control font-mono"
                        placeholder="Nhập lại mật khẩu"
                        value={regForm.confirm_password}
                        onChange={(e) => setRegForm({ ...regForm, confirm_password: e.target.value })}
                      />
                    </div>
                  </div>
                </div>

                <div className="form-group" style={{ marginBottom: '1.25rem' }}>
                  <label className="form-label">Địa chỉ nhận hàng (Tùy chọn)</label>
                  <div className="input-with-icon">
                    <MapPin size={15} />
                    <input
                      type="text"
                      className="form-control"
                      placeholder="Số nhà, đường, quận/huyện, tỉnh/thành phố"
                      value={regForm.address}
                      onChange={(e) => setRegForm({ ...regForm, address: e.target.value })}
                    />
                  </div>
                </div>

                <button
                  type="submit"
                  className="btn btn-primary"
                  style={{ width: '100%', padding: '0.75rem' }}
                  disabled={regLoading}
                >
                  {regLoading ? 'Đang tạo tài khoản...' : 'HOÀN TẤT ĐĂNG KÝ THÀNH VIÊN'} <CheckCircle2 size={16} />
                </button>
              </form>

              <div style={{ marginTop: '1rem', textAlign: 'center', fontSize: '0.78rem', color: 'var(--text-muted)' }}>
                Đã có tài khoản?{' '}
                <button
                  type="button"
                  onClick={() => {
                    setMode('login');
                    setRegError('');
                  }}
                  style={{
                    background: 'none',
                    border: 'none',
                    color: 'var(--amber-primary)',
                    fontWeight: 600,
                    cursor: 'pointer',
                    textDecoration: 'underline',
                  }}
                >
                  Đăng nhập ngay
                </button>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
};

export default LoginPage;
