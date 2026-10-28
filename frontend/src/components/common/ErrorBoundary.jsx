import React from 'react';
import { AlertTriangle, RefreshCw } from 'lucide-react';

export class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, errorInfo) {
    console.error('[StoreFlow AI UI Crash Caught by ErrorBoundary]:', error, errorInfo);
  }

  handleReload = () => {
    this.setState({ hasError: false, error: null });
    window.location.reload();
  };

  render() {
    if (this.state.hasError) {
      return (
        <div
          style={{
            minHeight: '100vh',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            padding: '2rem',
            background: 'var(--bg-app)',
            color: 'var(--text-main)',
            fontFamily: 'var(--font-display)',
          }}
        >
          <div
            className="retro-card"
            style={{
              maxWidth: '560px',
              width: '100%',
              border: '2px solid var(--red-light)',
              boxShadow: '0 0 35px rgba(248, 81, 73, 0.25), var(--shadow-retro-lg)',
            }}
          >
            <div
              className="retro-card-header"
              style={{
                background: 'rgba(218, 54, 51, 0.15)',
                borderBottom: '1px solid var(--red-dark)',
              }}
            >
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.5rem',
                  color: 'var(--red-light)',
                  fontWeight: 800,
                  fontSize: '1rem',
                  fontFamily: 'var(--font-mono)',
                }}
              >
                <AlertTriangle size={20} />
                <span>STOREFLOW_AI: SYSTEM_EXCEPTION_TRAP</span>
              </div>
            </div>

            <div className="retro-card-body" style={{ padding: '1.5rem' }}>
              <div
                style={{
                  padding: '1rem',
                  background: 'var(--bg-input)',
                  border: '1px solid var(--border-default)',
                  borderRadius: 'var(--radius-sm)',
                  marginBottom: '1.25rem',
                  fontFamily: 'var(--font-mono)',
                  fontSize: '0.82rem',
                  color: 'var(--red-light)',
                  wordBreak: 'break-word',
                  whiteSpace: 'pre-wrap',
                }}
              >
                [LỖI GIAO DIỆN PHÁT SINH]: {this.state.error?.message || 'Lỗi kết xuất không xác định'}
              </div>

              <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginBottom: '1.5rem', lineHeight: 1.5 }}>
                Hệ thống đã tự động cô lập điểm crash để bảo vệ dữ liệu cục bộ. Bạn có thể thử khởi động lại phiên làm việc hoặc tải lại trang.
              </p>

              <div style={{ display: 'flex', gap: '0.75rem', justifyContent: 'flex-end' }}>
                <button
                  type="button"
                  onClick={() => this.setState({ hasError: false, error: null })}
                  className="btn btn-outline"
                >
                  Bỏ Qua Lỗi
                </button>
                <button
                  type="button"
                  onClick={this.handleReload}
                  className="btn btn-primary"
                  style={{ background: 'var(--amber-primary)', color: '#000' }}
                >
                  <RefreshCw size={15} /> Tải Lại Hệ Thống
                </button>
              </div>
            </div>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}
export default ErrorBoundary;
