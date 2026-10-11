import React, { useState, useRef, useEffect } from 'react';
import {
  Sparkles,
  Bot,
  Search,
  TrendingUp,
  RefreshCw,
  ShoppingCart,
  ShieldCheck,
  Cpu,
  Terminal,
  Camera,
  Upload,
  Image as ImageIcon,
  X,
  Layers,
  CheckCircle,
  AlertCircle,
  Info,
} from 'lucide-react';
import { aiAPI } from '../services/api';
import { useAuth } from '../context/AuthContext';
import { useToast } from '../context/ToastContext';
import { StockBadge, Badge } from '../components/ui/Badge';
import MarkdownRenderer from '../components/common/MarkdownRenderer';
import ProductCard from '../components/common/ProductCard';
import ProductImage from '../components/common/ProductImage';

export const AiAssistantPage = ({ onNavigate }) => {
  const { user } = useAuth();
  const { addToast } = useToast();

  const isSuperAdmin = user?.role === 'superadmin';
  const isAdmin = user?.role === 'admin' || user?.role === 'superadmin';

  // Active sub-tab: 'recommend' (Tư vấn sản phẩm) | 'image-search' (Tìm kiếm bằng hình ảnh) | 'report' (Phân tích doanh thu AI)
  const [activeTab, setActiveTab] = useState('recommend');

  // --- AI PROVIDER STATE (PHASE R5) ---
  const [providersInfo, setProvidersInfo] = useState(null);
  const [selectedProvider, setSelectedProvider] = useState('auto'); // 'auto' | 'ollama' | 'gemini' | 'grounded'

  const fetchProviders = async () => {
    try {
      const res = await aiAPI.getProviders();
      setProvidersInfo(res);
    } catch (err) {
      console.warn('Không thể tải danh sách AI providers:', err);
    }
  };

  useEffect(() => {
    fetchProviders();
  }, []);

  // --- TAB 1: PRODUCT RECOMMENDATION STATE ---
  const [recQuery, setRecQuery] = useState('');
  const [recBudget, setRecBudget] = useState('');
  const [recLoading, setRecLoading] = useState(false);
  const [recResult, setRecResult] = useState(null);

  // --- TAB 2: IMAGE SEARCH STATE (PHASE R6) ---
  const [selectedFile, setSelectedFile] = useState(null);
  const [previewUrl, setPreviewUrl] = useState(null);
  const [dragActive, setDragActive] = useState(false);
  const [imgSearchLoading, setImgSearchLoading] = useState(false);
  const [imgSearchResult, setImgSearchResult] = useState(null);
  const [selectedProductDetail, setSelectedProductDetail] = useState(null);
  const [visionProvider, setVisionProvider] = useState('local');
  const fileInputRef = useRef(null);

  const handleFileChange = (file) => {
    if (!file) return;
    const validTypes = ['image/jpeg', 'image/png', 'image/webp'];
    if (!validTypes.includes(file.type)) {
      addToast('Chỉ chấp nhận file ảnh định dạng JPG, PNG hoặc WebP', 'warning');
      return;
    }
    if (file.size > 5 * 1024 * 1024) {
      addToast('Dung lượng ảnh không được vượt quá 5MB', 'warning');
      return;
    }
    setSelectedFile(file);
    const url = URL.createObjectURL(file);
    setPreviewUrl(url);
    setImgSearchResult(null);
  };

  const handleDrag = (e) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true);
    } else if (e.type === 'dragleave') {
      setDragActive(false);
    }
  };

  const handleDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleFileChange(e.dataTransfer.files[0]);
    }
  };

  const handleClearImage = () => {
    setSelectedFile(null);
    if (previewUrl) {
      URL.revokeObjectURL(previewUrl);
      setPreviewUrl(null);
    }
    setImgSearchResult(null);
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  const handleImageSearchSubmit = async (fileToSubmit = selectedFile, chosenProvider = visionProvider) => {
    const file = fileToSubmit || selectedFile;
    if (!file) {
      addToast('Vui lòng chọn hoặc kéo thả một file ảnh để tìm kiếm', 'warning');
      return;
    }
    try {
      setImgSearchLoading(true);
      const data = await aiAPI.imageSearch(file, 6, chosenProvider);

      // Quota Exceeded Guard: nếu hết token/quota Gemini API
      if (data.is_quota_exceeded) {
        setImgSearchResult({ ...data, results: [] });
        addToast(data.error_message || 'Hạn ngạch AI (Gemini Quota 429) đã hết. Không thể phân tích ảnh!', 'error');
        return;
      }

      // Non-product guard: nếu backend phát hiện ảnh không phải sản phẩm
      if (data.is_non_product) {
        setImgSearchResult({ ...data, results: [] });
        addToast('Ảnh không chứa sản phẩm — không có kết quả để hiển thị', 'warning');
        return;
      }

      const mappedResults = (data.results || []).map((item) => ({
        ...item,
        id: item.product_id || item.id,
        price: item.selling_price ?? item.price ?? 0,
        match_reason: item.reason || item.match_reason || '',
        relationship: (item.relationship || '').toUpperCase(),
      }));
      setImgSearchResult({ ...data, results: mappedResults });
      addToast(`Tìm thấy ${mappedResults.length} sản phẩm đối chiếu`, 'success');
    } catch (err) {
      addToast(err.message, 'error');
    } finally {
      setImgSearchLoading(false);
    }
  };

  const handleQuickPreset = (presetName, color, labelText) => {
    try {
      const canvas = document.createElement('canvas');
      canvas.width = 120;
      canvas.height = 120;
      const ctx = canvas.getContext('2d');
      ctx.fillStyle = color;
      ctx.fillRect(0, 0, 120, 120);
      ctx.fillStyle = '#f59e0b';
      ctx.font = 'bold 12px monospace';
      ctx.fillText(labelText, 8, 64);

      canvas.toBlob((blob) => {
        if (!blob) return;
        const file = new File([blob], `${presetName}.png`, { type: 'image/png' });
        setSelectedFile(file);
        if (previewUrl) URL.revokeObjectURL(previewUrl);
        setPreviewUrl(URL.createObjectURL(file));
        handleImageSearchSubmit(file);
      }, 'image/png');
    } catch (err) {
      addToast('Không thể tạo ảnh mẫu: ' + err.message, 'error');
    }
  };


  // Quick preset queries
  const quickRecQueries = [
    { label: 'Bàn phím cơ văn phòng', query: 'Bàn phím cơ văn phòng gõ êm giá hợp lý', budget: '1500000' },
    { label: 'Tai nghe chống ồn', query: 'Tai nghe bluetooth chống ồn pin trâu', budget: '2000000' },
    { label: 'Chuột gaming cao cấp', query: 'Chuột gaming nhạy LED RGB', budget: '1000000' },
    { label: 'Thiết bị mạng & Router', query: 'Router wifi chuẩn tốc độ cao', budget: '1200000' },
    { label: 'Phụ kiện dưới 500k', query: 'Phụ kiện máy tính giá rẻ chất lượng', budget: '500000' },
  ];

  const handleRecommendSubmit = async (e) => {
    if (e) e.preventDefault();
    if (!recQuery.trim()) {
      addToast('Vui lòng nhập nhu cầu sản phẩm cần tìm kiếm', 'warning');
      return;
    }
    try {
      setRecLoading(true);
      const provParam = selectedProvider === 'auto' ? null : selectedProvider;
      const data = await aiAPI.recommend(recQuery.trim(), recBudget || null, 5, provParam);
      setRecResult(data);
    } catch (err) {
      addToast(err.message, 'error');
    } finally {
      setRecLoading(false);
    }
  };

  // --- TAB 2: SALES REPORT STATE ---
  const [repPeriod, setRepPeriod] = useState('month'); // 'today' | '7_days' | 'month' | 'all'
  const [repLoading, setRepLoading] = useState(false);
  const [repResult, setRepResult] = useState(null);

  const handleGenerateReport = async (period = repPeriod) => {
    try {
      setRepLoading(true);
      setRepPeriod(period);
      const provParam = selectedProvider === 'auto' ? null : selectedProvider;
      const data = await aiAPI.generateSalesReport(period, provParam);
      setRepResult(data);
    } catch (err) {
      addToast(err.message, 'error');
    } finally {
      setRepLoading(false);
    }
  };



  // --- SYNC VECTOR INDEX (Admin only) ---
  const [syncingIndex, setSyncingIndex] = useState(false);
  const handleSyncIndex = async () => {
    try {
      setSyncingIndex(true);
      const res = await aiAPI.syncVectorIndex();
      addToast(res.message, 'success');
    } catch (err) {
      addToast(err.message, 'error');
    } finally {
      setSyncingIndex(false);
    }
  };

  const formatVND = (amount) => {
    return new Intl.NumberFormat('vi-VN', { style: 'currency', currency: 'VND' }).format(amount || 0);
  };

  const renderRelationshipBadge = (rel, prod = null) => {
    const norm = String(rel || prod?.relationship || '').toUpperCase().trim();
    const hasSqliteData = Boolean(
      prod?.sku &&
      ((prod?.stock_quantity !== undefined && prod?.stock_quantity !== null) ||
       prod?.selling_price !== undefined ||
       prod?.price !== undefined)
    );

    switch (norm) {
      case 'MATCH':
        return (
          <span
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '4px',
              fontSize: '0.75rem',
              padding: '2px 8px',
              borderRadius: '3px',
              background: 'rgba(57, 211, 83, 0.15)',
              color: 'var(--accent-green)',
              border: '1px solid rgba(57, 211, 83, 0.4)',
              fontFamily: 'var(--font-mono)',
              fontWeight: 700,
            }}
          >
            <CheckCircle size={12} /> [ KHỚP SẢN PHẨM ]
          </span>
        );
      case 'SIMILAR':
        return (
          <span
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '4px',
              fontSize: '0.75rem',
              padding: '2px 8px',
              borderRadius: '3px',
              background: 'rgba(0, 229, 255, 0.15)',
              color: 'var(--accent-cyan)',
              border: '1px solid rgba(0, 229, 255, 0.4)',
              fontFamily: 'var(--font-mono)',
              fontWeight: 700,
            }}
          >
            <Layers size={12} /> [ SẢN PHẨM TƯƠNG TỰ ]
          </span>
        );
      case 'RELATED':
        return (
          <span
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '4px',
              fontSize: '0.75rem',
              padding: '2px 8px',
              borderRadius: '3px',
              background: 'rgba(255, 180, 84, 0.15)',
              color: 'var(--accent-amber)',
              border: '1px solid rgba(255, 180, 84, 0.4)',
              fontFamily: 'var(--font-mono)',
              fontWeight: 700,
            }}
          >
            <Info size={12} /> [ SẢN PHẨM LIÊN QUAN ]
          </span>
        );
      default:
        if (hasSqliteData || (prod && prod.sku)) {
          return (
            <span
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '4px',
                fontSize: '0.75rem',
                padding: '2px 8px',
                borderRadius: '3px',
                background: 'rgba(57, 211, 83, 0.15)',
                color: 'var(--accent-green)',
                border: '1px solid rgba(57, 211, 83, 0.4)',
                fontFamily: 'var(--font-mono)',
                fontWeight: 700,
              }}
            >
              <CheckCircle size={12} /> [ ĐÃ ĐỐI CHIẾU ]
            </span>
          );
        }
        return (
          <span
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '4px',
              fontSize: '0.75rem',
              padding: '2px 8px',
              borderRadius: '3px',
              background: 'rgba(248, 81, 73, 0.15)',
              color: 'var(--accent-red, #f85149)',
              border: '1px solid rgba(248, 81, 73, 0.4)',
              fontFamily: 'var(--font-mono)',
              fontWeight: 700,
            }}
          >
            <AlertCircle size={12} /> [ KHÔNG TÌM THẤY ]
          </span>
        );
    }
  };

  return (
    <div style={{ padding: 'clamp(0.65rem, 2.5vw, 1.5rem)', maxWidth: '1440px', margin: '0 auto' }}>
      {/* Top Banner / System Status */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          background: 'var(--panel-bg)',
          border: '1px solid var(--border-color)',
          boxShadow: 'var(--shadow-retro)',
          padding: '1rem 1.25rem',
          borderRadius: '4px',
          marginBottom: '1.5rem',
          flexWrap: 'wrap',
          gap: '1rem',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.85rem' }}>
          <div
            style={{
              width: '42px',
              height: '42px',
              borderRadius: '4px',
              background: 'rgba(255, 180, 84, 0.15)',
              border: '1px solid var(--accent-amber)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: 'var(--accent-amber)',
            }}
          >
            <Bot size={24} />
          </div>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <h1 style={{ fontSize: '1.25rem', margin: 0, fontWeight: 700, letterSpacing: '-0.02em' }}>
                StoreFlow AI Command Center
              </h1>
              <span
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '4px',
                  fontSize: '0.75rem',
                  padding: '2px 8px',
                  borderRadius: '3px',
                  background: 'rgba(57, 211, 83, 0.15)',
                  color: 'var(--accent-green)',
                  border: '1px solid rgba(57, 211, 83, 0.4)',
                  fontFamily: 'var(--font-mono)',
                  fontWeight: 600,
                }}
              >
                <span
                  style={{
                    width: '6px',
                    height: '6px',
                    borderRadius: '50%',
                    background: 'var(--accent-green)',
                    boxShadow: '0 0 6px var(--accent-green)',
                  }}
                />
                RETRIEVAL & GROUNDING ONLINE
              </span>
            </div>
            <div style={{ fontSize: '0.82rem', color: 'var(--text-muted)', marginTop: '2px', display: 'flex', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap' }}>
              <span>
                Active Engine:{' '}
                <strong style={{
                  color: providersInfo?.active_provider === 'ollama' ? 'var(--accent-cyan)' :
                         providersInfo?.active_provider === 'gemini' ? 'var(--accent-green)' : 'var(--accent-amber)',
                  fontFamily: 'var(--font-mono)'
                }}>
                  {providersInfo?.active_provider === 'ollama'
                    ? `Ollama Local (${providersInfo.providers?.ollama?.model || 'qwen2.5:1.5b'})`
                    : providersInfo?.active_provider === 'gemini'
                    ? `Google Gemini (${providersInfo.providers?.gemini?.model || '3.6-flash'})`
                    : 'Grounded Direct Lookup (SQLite WAL)'}
                </strong>
              </span>
              <span>|</span>
              <span>Index: <span style={{ color: 'var(--accent-amber)', fontFamily: 'var(--font-mono)' }}>ChromaDB Persistent</span></span>
              <span>|</span>
              <span>Guard: <span style={{ color: 'var(--accent-green)', fontFamily: 'var(--font-mono)' }}>SQLite WAL Guard</span></span>
            </div>
          </div>
        </div>

        <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'center', flexWrap: 'wrap' }}>
          {/* AI Provider Switcher (Phase R5) */}
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '0.4rem',
              background: 'rgba(0, 0, 0, 0.25)',
              padding: '0.35rem 0.65rem',
              borderRadius: '4px',
              border: '1px solid var(--border-color)',
              fontSize: '0.8rem',
            }}
          >
            <Cpu size={14} style={{ color: 'var(--accent-cyan)' }} />
            <span style={{ color: 'var(--text-muted)', fontWeight: 600 }}>Provider:</span>
            <select
              value={selectedProvider}
              onChange={(e) => setSelectedProvider(e.target.value)}
              style={{
                background: 'var(--panel-bg)',
                color: 'var(--text-primary)',
                border: '1px solid var(--border-color)',
                borderRadius: '3px',
                padding: '2px 6px',
                fontSize: '0.78rem',
                fontFamily: 'var(--font-mono)',
                cursor: 'pointer',
              }}
              title="Chọn AI Provider xử lý (Local Ollama, Cloud Gemini hoặc Grounded Fallback)"
            >
              <option value="auto">
                Tự động ({providersInfo?.active_provider ? providersInfo.active_provider.toUpperCase() : 'MẶC ĐỊNH'})
              </option>
              <option value="ollama" disabled={providersInfo && !providersInfo.providers?.ollama?.available}>
                Ollama Local {providersInfo?.providers?.ollama?.available ? '🟢 (Khả dụng)' : '🔴 (Chưa chạy)'}
              </option>
              <option value="gemini" disabled={providersInfo && !providersInfo.providers?.gemini?.available}>
                Gemini Cloud {providersInfo?.providers?.gemini?.available ? '🟢 (Khả dụng)' : '🔴 (Thiếu Key)'}
              </option>
              <option value="grounded">Grounded Fallback 🟢 (SQLite thuần)</option>
            </select>
          </div>

          {isAdmin && (
            <button
              onClick={handleSyncIndex}
              disabled={syncingIndex}
              className="btn btn-secondary"
              style={{ fontSize: '0.82rem', padding: '0.45rem 0.85rem' }}
              title="Đồng bộ lại toàn bộ sản phẩm từ SQLite sang Vector Database"
            >
              <RefreshCw size={14} className={syncingIndex ? 'spin-animation' : ''} />
              {syncingIndex ? 'Đang index...' : 'Re-index ChromaDB'}
            </button>
          )}
          <div
            style={{
              fontSize: '0.8rem',
              color: 'var(--text-muted)',
              borderLeft: '1px solid var(--border-color)',
              paddingLeft: '0.75rem',
              fontFamily: 'var(--font-mono)',
            }}
          >
            User: <strong style={{ color: 'var(--text-primary)' }}>{user ? `${user.username} (${user.role?.toUpperCase()})` : 'Khách vãng lai (GUEST)'}</strong>
          </div>
        </div>
      </div>

      {/* Ollama Not Ready Warning Banner */}
      {selectedProvider === 'ollama' && providersInfo && !providersInfo.providers?.ollama?.available && (
        <div
          style={{
            marginBottom: '1rem',
            padding: '0.75rem 1rem',
            background: 'rgba(239, 68, 68, 0.1)',
            border: '1px solid rgba(239, 68, 68, 0.3)',
            borderRadius: '4px',
            display: 'flex',
            alignItems: 'center',
            gap: '0.6rem',
            fontSize: '0.85rem',
            color: 'var(--accent-red)',
          }}
        >
          <AlertCircle size={18} />
          <div>
            <strong>Ollama Local Service chưa khởi động hoặc chưa tải model:</strong> Dịch vụ chưa sẵn sàng tại <code>http://127.0.0.1:11434</code>. Hệ thống sẽ tự động fallback sang chế độ tra cứu SQLite Grounded để bảo đảm không gián đoạn giao dịch.
          </div>
        </div>
      )}

      {/* Navigation Tabs */}
      <div
        style={{
          display: 'flex',
          gap: '0.5rem',
          borderBottom: '2px solid var(--border-color)',
          marginBottom: '1.5rem',
          overflowX: 'auto',
        }}
      >
        <button
          onClick={() => setActiveTab('recommend')}
          className={`tab-btn ${activeTab === 'recommend' ? 'active' : ''}`}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '0.5rem',
            padding: '0.65rem 1.25rem',
            background: activeTab === 'recommend' ? 'var(--panel-bg)' : 'transparent',
            border: '1px solid',
            borderColor: activeTab === 'recommend' ? 'var(--accent-amber) var(--border-color) transparent var(--border-color)' : 'transparent',
            borderTopWidth: activeTab === 'recommend' ? '2px' : '1px',
            color: activeTab === 'recommend' ? 'var(--accent-amber)' : 'var(--text-muted)',
            cursor: 'pointer',
            fontWeight: 600,
            fontSize: '0.9rem',
            fontFamily: 'var(--font-mono)',
            borderRadius: '4px 4px 0 0',
          }}
        >
          <Sparkles size={16} />
          1. TƯ VẤN SẢN PHẨM (RAG)
        </button>

        <button
          onClick={() => setActiveTab('image-search')}
          className={`tab-btn ${activeTab === 'image-search' ? 'active' : ''}`}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '0.5rem',
            padding: '0.65rem 1.25rem',
            background: activeTab === 'image-search' ? 'var(--panel-bg)' : 'transparent',
            border: '1px solid',
            borderColor: activeTab === 'image-search' ? 'var(--accent-cyan) var(--border-color) transparent var(--border-color)' : 'transparent',
            borderTopWidth: activeTab === 'image-search' ? '2px' : '1px',
            color: activeTab === 'image-search' ? 'var(--accent-cyan)' : 'var(--text-muted)',
            cursor: 'pointer',
            fontWeight: 600,
            fontSize: '0.9rem',
            fontFamily: 'var(--font-mono)',
            borderRadius: '4px 4px 0 0',
          }}
        >
          <Camera size={16} />
          2. TÌM KIẾM BẰNG HÌNH ẢNH
        </button>

        {isSuperAdmin && (
          <button
            onClick={() => {
              setActiveTab('report');
              if (!repResult) handleGenerateReport('month');
            }}
            className={`tab-btn ${activeTab === 'report' ? 'active' : ''}`}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '0.5rem',
              padding: '0.65rem 1.25rem',
              background: activeTab === 'report' ? 'var(--panel-bg)' : 'transparent',
              border: '1px solid',
              borderColor: activeTab === 'report' ? 'var(--accent-green) var(--border-color) transparent var(--border-color)' : 'transparent',
              borderTopWidth: activeTab === 'report' ? '2px' : '1px',
              color: activeTab === 'report' ? 'var(--accent-green)' : 'var(--text-muted)',
              cursor: 'pointer',
              fontWeight: 600,
              fontSize: '0.9rem',
              fontFamily: 'var(--font-mono)',
              borderRadius: '4px 4px 0 0',
            }}
          >
            <TrendingUp size={16} />
            3. PHÂN TÍCH DOANH THU AI
          </button>
        )}
      </div>

      {/* ========================================================================= */}
      {/* TAB 1: PRODUCT RECOMMENDATION (RAG)                                      */}
      {/* ========================================================================= */}
      {activeTab === 'recommend' && (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr', gap: '1.5rem' }}>
          {/* Query Formulation Form */}
          <div
            style={{
              background: 'var(--panel-bg)',
              border: '1px solid var(--border-color)',
              boxShadow: 'var(--shadow-retro)',
              borderRadius: '4px',
              padding: '1.25rem',
            }}
          >
            <div style={{ marginBottom: '1rem' }}>
              <h2 style={{ fontSize: '1.1rem', margin: '0 0 0.25rem 0', color: 'var(--accent-amber)', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <Sparkles size={18} />
                Tư vấn sản phẩm thông minh & Kiểm tra tồn kho thời gian thực
              </h2>
              <p style={{ margin: 0, fontSize: '0.85rem', color: 'var(--text-muted)' }}>
                Sử dụng Vector Semantic Search trích xuất ứng viên từ ChromaDB kết hợp chốt chặn SQLite đảm bảo{' '}
                <strong style={{ color: 'var(--accent-green)' }}>100% sản phẩm được tư vấn đều còn hàng</strong>.
              </p>
            </div>

            <form onSubmit={handleRecommendSubmit}>
              <div className="ai-query-grid">
                <div>
                  <label style={{ display: 'block', fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '0.35rem' }}>
                    Yêu cầu / Nhu cầu khách hàng:
                  </label>
                  <div style={{ position: 'relative' }}>
                    <Search size={16} style={{ position: 'absolute', left: '10px', top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)' }} />
                    <input
                      type="text"
                      className="input"
                      placeholder="Ví dụ: Tìm bàn phím cơ gõ êm cho dân văn phòng, tai nghe bluetooth chống ồn..."
                      value={recQuery}
                      onChange={(e) => setRecQuery(e.target.value)}
                      style={{ paddingLeft: '32px', width: '100%' }}
                    />
                  </div>
                </div>

                <div>
                  <label style={{ display: 'block', fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '0.35rem' }}>
                    Ngân sách tối đa (VND, tùy chọn):
                  </label>
                  <input
                    type="number"
                    className="input"
                    placeholder="Không giới hạn"
                    value={recBudget}
                    onChange={(e) => setRecBudget(e.target.value)}
                    style={{ width: '100%' }}
                  />
                </div>

                <button
                  type="submit"
                  className="btn btn-primary"
                  disabled={recLoading}
                  style={{
                    height: '38px',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '0.5rem',
                    padding: '0 1.25rem',
                    whiteSpace: 'nowrap',
                  }}
                >
                  <Sparkles size={16} />
                  {recLoading ? 'Đang truy vấn...' : 'Tư vấn ngay'}
                </button>
              </div>
            </form>

            {/* Quick Prompts Chips */}
            <div style={{ marginTop: '0.85rem', display: 'flex', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap' }}>
              <span style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>Gợi ý nhanh:</span>
              {quickRecQueries.map((item, idx) => (
                <button
                  key={idx}
                  type="button"
                  onClick={() => {
                    setRecQuery(item.query);
                    setRecBudget(item.budget);
                  }}
                  style={{
                    background: 'rgba(255, 255, 255, 0.04)',
                    border: '1px solid var(--border-color)',
                    color: 'var(--text-secondary)',
                    borderRadius: '3px',
                    padding: '3px 8px',
                    fontSize: '0.76rem',
                    cursor: 'pointer',
                    fontFamily: 'var(--font-mono)',
                  }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.borderColor = 'var(--accent-amber)';
                    e.currentTarget.style.color = 'var(--accent-amber)';
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.borderColor = 'var(--border-color)';
                    e.currentTarget.style.color = 'var(--text-secondary)';
                  }}
                >
                  + {item.label}
                </button>
              ))}
            </div>
          </div>

          {/* Results Display */}
          {recLoading && (
            <div
              style={{
                background: 'var(--panel-bg)',
                border: '1px dashed var(--accent-amber)',
                borderRadius: '4px',
                padding: '2.5rem',
                textAlign: 'center',
                color: 'var(--accent-amber)',
                fontFamily: 'var(--font-mono)',
              }}
            >
              <div style={{ display: 'inline-block', marginBottom: '0.75rem' }}>
                <Bot size={36} className="spin-animation" />
              </div>
              <div style={{ fontSize: '1rem', fontWeight: 600 }}>StoreFlow AI đang xử lý truy vấn sản phẩm...</div>
              <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginTop: '0.35rem' }}>
                1. Dense Vector ChromaDB Top-K ➔ 2. Lexical Reranking & SQLite Stock Guard ➔ 3. AI Generation ({selectedProvider === 'ollama' ? 'Ollama Local' : selectedProvider === 'gemini' ? 'Gemini Cloud' : 'Active Provider'})
              </div>
            </div>
          )}

          {!recLoading && recResult && (
            <div className="ai-results-split">
              {/* Left Column: AI Text Explanation in CRT Terminal style */}
              <div
                style={{
                  background: 'var(--panel-bg)',
                  border: '1px solid var(--border-color)',
                  borderRadius: '4px',
                  boxShadow: 'var(--shadow-retro)',
                  display: 'flex',
                  flexDirection: 'column',
                }}
              >
                <div
                  style={{
                    padding: '0.75rem 1rem',
                    borderBottom: '1px solid var(--border-color)',
                    background: 'rgba(0, 0, 0, 0.25)',
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: 'var(--accent-amber)', fontWeight: 600, fontSize: '0.85rem' }}>
                    <Terminal size={16} />
                    PHÂN TÍCH TƯ VẤN CỦA TRỢ LÝ AI
                  </div>
                  {recResult.is_fallback || recResult.provider === 'grounded' ? (
                    <Badge variant="warning">Chế độ tra cứu trực tiếp SQLite</Badge>
                  ) : recResult.provider === 'ollama' ? (
                    <Badge variant="blue">Ollama Local (Qwen 2.5 1.5B GPU)</Badge>
                  ) : (
                    <Badge variant="success">Gemini 3.6 Flash Grounded</Badge>
                  )}
                </div>

                <div
                  style={{
                    padding: '1.25rem',
                    lineHeight: '1.6',
                    fontSize: '0.9rem',
                    color: 'var(--text-primary)',
                    fontFamily: 'var(--font-sans)',
                  }}
                >
                  <MarkdownRenderer
                    content={recResult.ai_response}
                    products={recResult.recommended_products}
                    onViewProduct={(prod) => setSelectedProductDetail(prod)}
                    onSelectProduct={(prod) => {
                      if (onNavigate) {
                        onNavigate('pos');
                        addToast(`Đã chuyển tới POS. Mã sản phẩm: ${prod.sku}`, 'info');
                      }
                    }}
                  />

                  {/* Grounded Action Banner directing user to verified products in the right column */}
                  {recResult.recommended_products && recResult.recommended_products.length > 0 && (
                    <div
                      style={{
                        marginTop: '1.5rem',
                        padding: '0.85rem 1.15rem',
                        background: 'rgba(57, 211, 83, 0.08)',
                        border: '1px solid rgba(57, 211, 83, 0.3)',
                        borderRadius: '4px',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                        gap: '0.75rem',
                        flexWrap: 'wrap',
                      }}
                    >
                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.83rem', color: 'var(--accent-green)', fontWeight: 600 }}>
                        <ShieldCheck size={16} />
                        <span>Đã đối chiếu <strong>{recResult.recommended_products.length} sản phẩm</strong> còn hàng trong kho SQLite (danh sách chi tiết ở cột bên phải).</span>
                      </div>
                      <span style={{ fontSize: '0.76rem', color: 'var(--accent-amber)', fontFamily: 'var(--font-mono)', fontWeight: 600 }}>
                        👉 Chọn sản phẩm ở cột phải để Mở bán POS / Thêm giỏ hàng
                      </span>
                    </div>
                  )}
                </div>
              </div>

              {/* Right Column: Verified Product Cards (With 1-click POS Add) */}
              <div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.75rem' }}>
                  <h3 style={{ fontSize: '0.95rem', margin: 0, fontWeight: 700, color: 'var(--text-primary)' }}>
                    Sản phẩm khả dụng ({recResult.recommended_products.length})
                  </h3>
                  <span style={{ fontSize: '0.75rem', color: 'var(--accent-green)', display: 'flex', alignItems: 'center', gap: '4px', fontFamily: 'var(--font-mono)' }}>
                    <ShieldCheck size={14} /> Tồn kho xác thực &gt; 0
                  </span>
                </div>

                {recResult.recommended_products.length === 0 ? (
                  <div
                    style={{
                      background: 'var(--panel-bg)',
                      border: '1px solid var(--border-color)',
                      borderRadius: '4px',
                      padding: '2rem',
                      textAlign: 'center',
                      color: 'var(--text-muted)',
                    }}
                  >
                    Không tìm thấy sản phẩm nào còn hàng khớp với yêu cầu.
                  </div>
                ) : (
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr', gap: '1rem' }}>
                    {recResult.recommended_products.map((p) => (
                      <ProductCard
                        key={p.product_id || p.id || p.sku}
                        product={p}
                        onViewDetail={(prod) => setSelectedProductDetail(prod)}
                        onSelect={(prod) => {
                          if (onNavigate) {
                            onNavigate('pos');
                            addToast(`Đã chuyển tới POS. Mã sản phẩm: ${prod.sku}`, 'info');
                          }
                        }}
                        actionLabel={user?.role === 'customer' ? 'Thêm giỏ / POS' : 'Mở bán POS'}
                      />
                    ))}
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      )}

      {/* ========================================================================= */}
      {/* TAB 2: IMAGE SEARCH & VISUAL MATCHING (PHASE 12E)                         */}
      {/* ========================================================================= */}
      {activeTab === 'image-search' && (
        <div>
          {/* Top Banner & Upload Section */}
          <div
            style={{
              background: 'var(--panel-bg)',
              border: '1px solid var(--border-color)',
              boxShadow: 'var(--shadow-retro)',
              borderRadius: '4px',
              padding: '1.25rem',
              marginBottom: '1.5rem',
            }}
          >
            <div style={{ marginBottom: '1rem' }}>
              <h2
                style={{
                  fontSize: '1.1rem',
                  margin: '0 0 0.25rem 0',
                  color: 'var(--accent-cyan)',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.5rem',
                }}
              >
                <Camera size={18} />
                Tìm kiếm Sản phẩm Bằng Hình ảnh (AI Visual Match Engine)
              </h2>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '0.75rem', marginTop: '0.4rem' }}>
                <p style={{ margin: 0, fontSize: '0.85rem', color: 'var(--text-muted)' }}>
                  Tải lên ảnh mẫu hoặc ảnh chụp sản phẩm → Trích xuất đặc trưng thị giác → Tra cứu tương đồng ChromaDB → Đối chiếu tồn kho & giá bán thực tế từ SQLite.
                </p>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', background: 'rgba(0,0,0,0.25)', padding: '4px 10px', borderRadius: '4px', border: '1px solid var(--border-color)' }}>
                  <span style={{ fontSize: '0.78rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>Chế độ AI:</span>
                  <select
                    value={visionProvider}
                    onChange={(e) => setVisionProvider(e.target.value)}
                    style={{
                      background: 'var(--panel-bg)',
                      color: visionProvider === 'local' ? 'var(--accent-cyan)' : 'var(--accent-amber)',
                      border: '1px solid var(--border-color)',
                      borderRadius: '3px',
                      fontSize: '0.78rem',
                      fontWeight: 600,
                      padding: '2px 8px',
                      cursor: 'pointer'
                    }}
                  >
                    <option value="local">🖥️ Local Vision (CLIP Offline, 0% Cloud)</option>
                    <option value="gemini">☁️ Gemini Cloud Vision (Google AI)</option>
                  </select>
                </div>
              </div>
            </div>

            <div className="ai-image-search-split">
              {/* Drag and Drop Zone */}
              <div>
                <input
                  type="file"
                  ref={fileInputRef}
                  onChange={(e) => e.target.files && handleFileChange(e.target.files[0])}
                  accept="image/jpeg,image/png,image/webp"
                  style={{ display: 'none' }}
                />

                <div
                  onDragEnter={handleDrag}
                  onDragLeave={handleDrag}
                  onDragOver={handleDrag}
                  onDrop={handleDrop}
                  onClick={() => fileInputRef.current && fileInputRef.current.click()}
                  style={{
                    border: `2px dashed ${dragActive ? 'var(--accent-cyan)' : 'var(--border-color)'}`,
                    borderRadius: '6px',
                    padding: '1.5rem',
                    textAlign: 'center',
                    background: dragActive ? 'rgba(0, 229, 255, 0.05)' : 'rgba(0, 0, 0, 0.15)',
                    cursor: 'pointer',
                    transition: 'all 0.2s ease',
                    minHeight: '160px',
                    display: 'flex',
                    flexDirection: 'column',
                    alignItems: 'center',
                    justifyContent: 'center',
                  }}
                >
                  <Upload size={32} style={{ color: dragActive ? 'var(--accent-cyan)' : 'var(--text-muted)', marginBottom: '0.5rem' }} />
                  <div style={{ fontSize: '0.9rem', fontWeight: 600, color: 'var(--text-primary)' }}>
                    Kéo & thả ảnh vào đây hoặc bấm để tải lên
                  </div>
                  <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)', marginTop: '0.25rem' }}>
                    Hỗ trợ PNG, JPG, WebP (Tối đa 5MB)
                  </div>
                </div>

                {/* Quick Presets */}
                <div style={{ marginTop: '0.85rem' }}>
                  <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)', marginBottom: '0.4rem', fontFamily: 'var(--font-mono)' }}>
                    Thử nhanh với ảnh mẫu sinh tự động:
                  </div>
                  <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
                    <button
                      type="button"
                      onClick={() => handleQuickPreset('ban_phim_co', '#0f172a', 'KEYBOARD')}
                      className="btn btn-secondary"
                      style={{ fontSize: '0.75rem', padding: '0.3rem 0.6rem' }}
                    >
                      ⌨️ Bàn phím cơ
                    </button>
                    <button
                      type="button"
                      onClick={() => handleQuickPreset('tai_nghe', '#1e1b4b', 'HEADPHONE')}
                      className="btn btn-secondary"
                      style={{ fontSize: '0.75rem', padding: '0.3rem 0.6rem' }}
                    >
                      🎧 Tai nghe
                    </button>
                    <button
                      type="button"
                      onClick={() => handleQuickPreset('chuot_gaming', '#14532d', 'MOUSE')}
                      className="btn btn-secondary"
                      style={{ fontSize: '0.75rem', padding: '0.3rem 0.6rem' }}
                    >
                      🖱️ Chuột gaming
                    </button>
                  </div>
                </div>
              </div>

              {/* Image Preview & Submit Action */}
              <div
                style={{
                  border: '1px solid var(--border-color)',
                  borderRadius: '6px',
                  background: 'rgba(0, 0, 0, 0.2)',
                  padding: '1rem',
                  display: 'flex',
                  flexDirection: 'column',
                  justifyContent: 'space-between',
                }}
              >
                <div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
                    <span style={{ fontSize: '0.82rem', fontWeight: 600, color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
                      [ PREVIEW HÌNH ẢNH ]
                    </span>
                    {previewUrl && (
                      <button
                        type="button"
                        onClick={handleClearImage}
                        className="btn btn-secondary"
                        style={{ padding: '2px 6px', fontSize: '0.72rem', display: 'flex', alignItems: 'center', gap: '3px' }}
                        title="Xóa ảnh hiện tại"
                      >
                        <X size={12} /> Hủy ảnh
                      </button>
                    )}
                  </div>

                  {previewUrl ? (
                    <div style={{ display: 'flex', gap: '1rem', alignItems: 'center' }}>
                      <div
                        style={{
                          width: '110px',
                          height: '110px',
                          borderRadius: '4px',
                          border: '1px solid var(--border-color)',
                          overflow: 'hidden',
                          background: '#000',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          flexShrink: 0,
                        }}
                      >
                        <img
                          src={previewUrl}
                          alt="Truy vấn"
                          style={{ maxWidth: '100%', maxHeight: '100%', objectFit: 'contain' }}
                        />
                      </div>
                      <div style={{ fontSize: '0.82rem' }}>
                        <div style={{ fontWeight: 600, color: 'var(--text-primary)', wordBreak: 'break-all' }}>
                          {selectedFile?.name || 'Tệp ảnh tải lên'}
                        </div>
                        <div style={{ color: 'var(--text-muted)', marginTop: '2px', fontSize: '0.75rem', fontFamily: 'var(--font-mono)' }}>
                          Dung lượng: {selectedFile ? (selectedFile.size / 1024).toFixed(1) + ' KB' : 'N/A'}
                        </div>
                        <div style={{ color: 'var(--text-muted)', fontSize: '0.75rem', fontFamily: 'var(--font-mono)' }}>
                          Định dạng: {selectedFile?.type || 'image/*'}
                        </div>
                      </div>
                    </div>
                  ) : (
                    <div
                      style={{
                        height: '110px',
                        display: 'flex',
                        flexDirection: 'column',
                        alignItems: 'center',
                        justifyContent: 'center',
                        color: 'var(--text-muted)',
                        fontSize: '0.8rem',
                        border: '1px dashed rgba(255,255,255,0.1)',
                        borderRadius: '4px',
                      }}
                    >
                      <ImageIcon size={28} style={{ opacity: 0.4, marginBottom: '0.25rem' }} />
                      Chưa có hình ảnh nào được chọn
                    </div>
                  )}
                </div>

                <div style={{ marginTop: '1rem' }}>
                  <button
                    type="button"
                    onClick={() => handleImageSearchSubmit()}
                    disabled={!selectedFile || imgSearchLoading}
                    className="btn btn-primary"
                    style={{
                      width: '100%',
                      padding: '0.65rem 1rem',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      gap: '0.5rem',
                      background: 'var(--accent-cyan)',
                      borderColor: 'var(--accent-cyan)',
                      color: '#000',
                      fontWeight: 700,
                      cursor: !selectedFile || imgSearchLoading ? 'not-allowed' : 'pointer',
                      opacity: !selectedFile || imgSearchLoading ? 0.6 : 1,
                    }}
                  >
                    <Search size={16} />
                    {imgSearchLoading ? 'ĐANG QUÉT & ĐỐI CHIẾU...' : 'PHÂN TÍCH & TÌM KIẾM SẢN PHẨM'}
                  </button>
                </div>
              </div>
            </div>
          </div>

          {/* HUD Scanning Animation State */}
          {imgSearchLoading && (
            <div
              style={{
                background: 'var(--panel-bg)',
                border: '1px solid var(--accent-cyan)',
                borderRadius: '4px',
                padding: '2rem',
                textAlign: 'center',
                boxShadow: '0 0 15px rgba(0, 229, 255, 0.2)',
                marginBottom: '1.5rem',
              }}
            >
              <div style={{ display: 'inline-block', marginBottom: '0.75rem' }}>
                <Cpu size={40} className="spin-animation" style={{ color: 'var(--accent-cyan)' }} />
              </div>
              <div style={{ fontSize: '1.05rem', fontWeight: 700, color: 'var(--accent-cyan)', fontFamily: 'var(--font-mono)' }}>
                [ AI OPTICAL SCANNER ACTIVE ]
              </div>
              <div style={{ fontSize: '0.85rem', color: 'var(--text-muted)', marginTop: '0.4rem', fontFamily: 'var(--font-mono)' }}>
                1. Nhận diện đặc trưng thị giác ➔ 2. Truy xuất ChromaDB ➔ 3. Xác thực SQLite WAL ➔ 4. Phân loại MATCH/SIMILAR/RELATED
              </div>
              <div
                style={{
                  maxWidth: '400px',
                  height: '3px',
                  background: 'rgba(0, 229, 255, 0.2)',
                  borderRadius: '2px',
                  margin: '1rem auto 0 auto',
                  overflow: 'hidden',
                }}
              >
                <div
                  style={{
                    width: '60%',
                    height: '100%',
                    background: 'var(--accent-cyan)',
                    boxShadow: '0 0 8px var(--accent-cyan)',
                    animation: 'pulse 1.2s infinite ease-in-out',
                  }}
                />
              </div>
            </div>
          )}

          {/* Results Display */}
          {!imgSearchLoading && imgSearchResult && (
            <div>
              {/* Quota Exceeded Notice — Ẩn hoàn toàn sản phẩm và hiển thị cảnh báo hạn ngạch */}
              {imgSearchResult.is_quota_exceeded ? (
                <div
                  style={{
                    background: 'rgba(248, 81, 73, 0.08)',
                    border: '1px solid var(--accent-red, #f85149)',
                    borderRadius: '4px',
                    padding: '2.5rem 1.5rem',
                    textAlign: 'center',
                    boxShadow: '0 0 18px rgba(248, 81, 73, 0.15)',
                    marginBottom: '1.5rem',
                  }}
                >
                  <AlertCircle size={44} style={{ color: 'var(--accent-red, #f85149)', marginBottom: '0.85rem' }} />
                  <div style={{ fontSize: '1.1rem', fontWeight: 700, color: 'var(--accent-red, #f85149)', marginBottom: '0.5rem', fontFamily: 'var(--font-mono)' }}>
                    [ CẢNH BÁO: HẠN NGẠCH AI GEMINI ĐÃ HẾT (429 RESOURCE EXHAUSTED) ]
                  </div>
                  <div style={{ fontSize: '0.9rem', color: 'var(--text-primary)', maxWidth: '580px', margin: '0 auto', lineHeight: 1.6 }}>
                    {imgSearchResult.error_message || 'Dịch vụ AI Vision (Google AI Studio Free Tier limit 20 requests/ngày) đã sử dụng hết hạn ngạch truy vấn.'}
                  </div>
                  <div
                    style={{
                      padding: '1rem 1.25rem',
                      background: 'var(--panel-bg)',
                      border: '1px dashed rgba(248, 81, 73, 0.4)',
                      borderRadius: '4px',
                      maxWidth: '620px',
                      margin: '1.25rem auto 0',
                      textAlign: 'left',
                      fontSize: '0.82rem',
                      color: 'var(--text-muted)',
                      lineHeight: 1.6,
                    }}
                  >
                    <div style={{ fontWeight: 700, color: 'var(--accent-amber)', marginBottom: '0.4rem', display: 'flex', alignItems: 'center', gap: '6px' }}>
                      <ShieldCheck size={16} /> Nguyên tắc bảo toàn tính chân thật dữ liệu:
                    </div>
                    <div>• Hệ thống đã <strong>dừng tiến trình phân tích và KHÔNG hiển thị sản phẩm ngẫu nhiên</strong> để tránh gây hiểu lầm hoặc sai lệch dữ liệu kho hàng.</div>
                    <div style={{ marginTop: '0.4rem' }}>• <strong>Khắc phục:</strong> Vui lòng đợi hạn ngạch đặt lại vào chu kỳ tiếp theo hoặc cập nhật <code>GEMINI_API_KEY</code> mới trong tệp cấu hình <code>backend/.env</code>.</div>
                  </div>
                </div>
              ) : (
                <>
                  {/* Extracted Features Banner */}
                  {imgSearchResult.query_features && (
                    <div
                      style={{
                        background: 'var(--panel-bg)',
                        border: '1px solid var(--border-color)',
                        borderLeft: imgSearchResult.is_non_product
                          ? '4px solid var(--accent-amber)'
                          : '4px solid var(--accent-cyan)',
                        borderRadius: '4px',
                        padding: '1rem 1.25rem',
                        marginBottom: '1.5rem',
                        boxShadow: 'var(--shadow-retro)',
                      }}
                    >
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem', flexWrap: 'wrap', gap: '0.5rem' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: 'var(--accent-cyan)', fontWeight: 700, fontSize: '0.9rem', fontFamily: 'var(--font-mono)' }}>
                          <Terminal size={16} /> ĐẶC TRƯNG THỊ GIÁC TRÍCH XUẤT (AI VISUAL FEATURES)
                        </div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', fontSize: '0.78rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
                          <span style={{ padding: '2px 8px', borderRadius: '3px', background: imgSearchResult.provider_used === 'local' ? 'rgba(0, 229, 255, 0.15)' : 'rgba(255, 180, 84, 0.15)', border: `1px solid ${imgSearchResult.provider_used === 'local' ? 'var(--accent-cyan)' : 'var(--accent-amber)'}`, color: imgSearchResult.provider_used === 'local' ? 'var(--accent-cyan)' : 'var(--accent-amber)', fontWeight: 600 }}>
                            {imgSearchResult.provider_used === 'local' ? '🖥️ Local Vision (CLIP Offline)' : '☁️ Gemini Cloud Vision'}
                          </span>
                          <span>Xử lý: <strong style={{ color: 'var(--accent-cyan)' }}>{imgSearchResult.execution_time_ms}ms</strong></span>
                          <span>Ứng viên: <strong style={{ color: 'var(--accent-amber)' }}>{imgSearchResult.total_candidates_found ?? imgSearchResult.total_candidates ?? 0}</strong></span>
                        </div>
                      </div>

                      <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap', marginBottom: '0.5rem' }}>
                        <span style={{ fontSize: '0.8rem', padding: '2px 8px', borderRadius: '3px', background: 'rgba(0, 229, 255, 0.1)', border: '1px solid rgba(0, 229, 255, 0.3)', color: 'var(--accent-cyan)' }}>
                          Loại thiết bị: <strong>{imgSearchResult.query_features.product_type || 'N/A'}</strong>
                        </span>
                        <span style={{ fontSize: '0.8rem', padding: '2px 8px', borderRadius: '3px', background: 'rgba(255, 180, 84, 0.1)', border: '1px solid rgba(255, 180, 84, 0.3)', color: 'var(--accent-amber)' }}>
                          Màu sắc chủ đạo: <strong>{imgSearchResult.query_features.dominant_color || 'N/A'}</strong>
                        </span>
                        <span style={{ fontSize: '0.8rem', padding: '2px 8px', borderRadius: '3px', background: 'rgba(57, 211, 83, 0.1)', border: '1px solid rgba(57, 211, 83, 0.3)', color: 'var(--accent-green)' }}>
                          Kiểu dáng: <strong>{imgSearchResult.query_features.shape_form || 'N/A'}</strong>
                        </span>
                      </div>

                      {imgSearchResult.query_features.description && (
                        <div style={{ fontSize: '0.83rem', color: 'var(--text-primary)', fontStyle: 'italic', marginTop: '0.25rem' }}>
                          "{imgSearchResult.query_features.description}"
                        </div>
                      )}
                    </div>
                  )}

                  {/* Non-product notice — ẩn hoàn toàn phần kết quả */}
                  {imgSearchResult.is_non_product ? (
                    <div
                      style={{
                        background: 'var(--panel-bg)',
                        border: '1px solid var(--accent-amber)',
                        borderRadius: '4px',
                        padding: '2.5rem',
                        textAlign: 'center',
                        color: 'var(--text-muted)',
                      }}
                    >
                      <AlertCircle size={36} style={{ color: 'var(--accent-amber)', opacity: 0.85, marginBottom: '0.75rem' }} />
                      <div style={{ fontSize: '1rem', fontWeight: 700, color: 'var(--accent-amber)', marginBottom: '0.4rem' }}>
                        Ảnh không chứa sản phẩm
                      </div>
                      <div style={{ fontSize: '0.85rem', maxWidth: '460px', margin: '0 auto', lineHeight: 1.6 }}>
                        AI nhận diện đây không phải sản phẩm công nghệ hoặc thiết bị văn phòng.
                        Vui lòng tải lên ảnh sản phẩm rõ ràng (chuột, bàn phím, tai nghe, loa...).
                      </div>
                      {imgSearchResult.non_product_reason && (
                        <div style={{ fontSize: '0.76rem', color: 'var(--text-muted)', marginTop: '0.75rem', fontFamily: 'var(--font-mono)', opacity: 0.7 }}>
                          [{imgSearchResult.non_product_reason}]
                        </div>
                      )}
                    </div>
                  ) : (
                    <>
                      {/* Product Cards Grid */}
                      <div style={{ marginBottom: '1rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <h3 style={{ fontSize: '1rem', fontWeight: 700, margin: 0, color: 'var(--text-primary)' }}>
                          Kết quả đối chiếu kho hàng ({imgSearchResult.results?.length || 0})
                        </h3>
                        <span style={{ fontSize: '0.75rem', color: 'var(--accent-green)', display: 'flex', alignItems: 'center', gap: '4px', fontFamily: 'var(--font-mono)' }}>
                          <ShieldCheck size={14} /> SQLite Truth Guard Verified
                        </span>
                      </div>

                  {!imgSearchResult.results || imgSearchResult.results.length === 0 ? (
                    <div
                      style={{
                        background: 'var(--panel-bg)',
                        border: '1px solid var(--border-color)',
                        borderRadius: '4px',
                        padding: '2.5rem',
                        textAlign: 'center',
                        color: 'var(--text-muted)',
                      }}
                    >
                      <AlertCircle size={32} style={{ opacity: 0.5, marginBottom: '0.5rem' }} />
                      <div style={{ fontSize: '0.95rem', fontWeight: 600 }}>Không tìm thấy sản phẩm nào phù hợp</div>
                      <div style={{ fontSize: '0.82rem', marginTop: '0.25rem' }}>
                        Hãy thử tải lên một hình ảnh khác rõ ràng hơn hoặc chọn ảnh mẫu phía trên.
                      </div>
                    </div>
                  ) : (
                    <div className="ai-product-cards-grid">
                      {imgSearchResult.results.map((product) => (
                        <ProductCard
                          key={product.id || product.sku}
                          product={product}
                          showRelationship={true}
                          renderRelationshipBadge={renderRelationshipBadge}
                          onViewDetail={(p) => setSelectedProductDetail(p)}
                          onSelect={(p) => {
                            if (onNavigate) {
                              onNavigate('pos');
                              addToast(`Đã chuyển tới POS. Mã sản phẩm: ${p.sku}`, 'info');
                            }
                          }}
                          actionLabel={user?.role === 'customer' ? 'Thêm giỏ / POS' : 'Mở bán POS'}
                        />
                      ))}
                    </div>
                  )}
                </>
              )}
            </>
          )}
        </div>
          )}
        </div>
      )}

      {/* ========================================================================= */}
      {/* TAB 3: SALES REPORT INTELLIGENCE (SuperAdmin only)                       */}
      {/* ========================================================================= */}
      {activeTab === 'report' && isSuperAdmin && (
        <div>
          {/* Controls Banner */}
          <div
            style={{
              background: 'var(--panel-bg)',
              border: '1px solid var(--border-color)',
              boxShadow: 'var(--shadow-retro)',
              borderRadius: '4px',
              padding: '1.25rem',
              marginBottom: '1.5rem',
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              flexWrap: 'wrap',
              gap: '1rem',
            }}
          >
            <div>
              <h2 style={{ fontSize: '1.1rem', margin: '0 0 0.25rem 0', color: 'var(--accent-green)', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <TrendingUp size={18} />
                Báo cáo Phân tích Kinh doanh Thông minh (AI Business Intelligence)
              </h2>
              <p style={{ margin: 0, fontSize: '0.85rem', color: 'var(--text-muted)' }}>
                Đọc số liệu doanh thu thực tế, phát hiện xu hướng tăng trưởng, top sản phẩm và đề xuất kế hoạch nhập kho.
              </p>
            </div>

            <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
              <div style={{ display: 'flex', background: 'rgba(0,0,0,0.25)', borderRadius: '4px', border: '1px solid var(--border-color)', padding: '2px' }}>
                {[
                  { key: 'today', label: 'Hôm nay' },
                  { key: '7_days', label: '7 ngày' },
                  { key: 'month', label: 'Tháng này' },
                  { key: 'all', label: 'Toàn thời gian' },
                ].map((item) => (
                  <button
                    key={item.key}
                    type="button"
                    onClick={() => handleGenerateReport(item.key)}
                    style={{
                      padding: '0.35rem 0.75rem',
                      background: repPeriod === item.key ? 'var(--accent-green)' : 'transparent',
                      color: repPeriod === item.key ? '#0e1318' : 'var(--text-muted)',
                      border: 'none',
                      borderRadius: '3px',
                      fontSize: '0.8rem',
                      fontWeight: repPeriod === item.key ? 700 : 500,
                      cursor: 'pointer',
                      fontFamily: 'var(--font-mono)',
                    }}
                  >
                    {item.label}
                  </button>
                ))}
              </div>

              <button
                type="button"
                onClick={() => handleGenerateReport(repPeriod)}
                disabled={repLoading}
                className="btn btn-primary"
                style={{
                  background: 'var(--accent-green)',
                  borderColor: 'var(--accent-green)',
                  color: '#0e1318',
                  fontWeight: 700,
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.5rem',
                }}
              >
                <RefreshCw size={14} className={repLoading ? 'spin-animation' : ''} />
                {repLoading ? 'Đang phân tích...' : 'Làm mới báo cáo'}
              </button>
            </div>
          </div>

          {repLoading && (
            <div
              style={{
                background: 'var(--panel-bg)',
                border: '1px dashed var(--accent-green)',
                borderRadius: '4px',
                padding: '3rem',
                textAlign: 'center',
                color: 'var(--accent-green)',
                fontFamily: 'var(--font-mono)',
              }}
            >
              <div style={{ display: 'inline-block', marginBottom: '0.75rem' }}>
                <Cpu size={36} className="spin-animation" />
              </div>
              <div style={{ fontSize: '1.05rem', fontWeight: 600 }}>
                AI Engine ({selectedProvider === 'ollama' ? 'Ollama Local GPU' : selectedProvider === 'gemini' ? 'Gemini Cloud' : 'Multi-Provider'}) đang tổng hợp số liệu kinh doanh...
              </div>
              <div style={{ fontSize: '0.82rem', color: 'var(--text-muted)', marginTop: '0.35rem' }}>
                Trích xuất SQL Doanh thu ➔ Phân tích Top sản phẩm ➔ Phát hiện nguy cơ hết kho ➔ Đề xuất kế hoạch nhập hàng
              </div>
            </div>
          )}

          {!repLoading && repResult && (
            <div>
              {/* Highlight Metrics Cards */}
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '1rem', marginBottom: '1.5rem' }}>
                <div style={{ background: 'var(--panel-bg)', border: '1px solid var(--border-color)', borderRadius: '4px', padding: '1rem' }}>
                  <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>Tổng doanh thu tích lũy</div>
                  <div style={{ fontSize: '1.35rem', fontWeight: 700, color: 'var(--accent-green)', fontFamily: 'var(--font-mono)', marginTop: '4px' }}>
                    {formatVND(repResult.total_revenue)}
                  </div>
                </div>

                <div style={{ background: 'var(--panel-bg)', border: '1px solid var(--border-color)', borderRadius: '4px', padding: '1rem' }}>
                  <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>Số đơn hàng hoàn tất</div>
                  <div style={{ fontSize: '1.35rem', fontWeight: 700, color: 'var(--accent-cyan)', fontFamily: 'var(--font-mono)', marginTop: '4px' }}>
                    {repResult.total_orders} đơn
                  </div>
                </div>

                <div style={{ background: 'var(--panel-bg)', border: '1px solid var(--border-color)', borderRadius: '4px', padding: '1rem' }}>
                  <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>Mặt hàng báo động hết kho</div>
                  <div style={{ fontSize: '1.35rem', fontWeight: 700, color: repResult.low_stock_count > 0 ? 'var(--accent-amber)' : 'var(--accent-green)', fontFamily: 'var(--font-mono)', marginTop: '4px' }}>
                    {repResult.low_stock_count} sản phẩm
                  </div>
                </div>
              </div>

              {/* AI Report Terminal Content */}
              <div
                style={{
                  background: 'var(--panel-bg)',
                  border: '1px solid var(--border-color)',
                  boxShadow: 'var(--shadow-retro)',
                  borderRadius: '4px',
                  overflow: 'hidden',
                }}
              >
                <div
                  style={{
                    padding: '0.75rem 1.25rem',
                    background: 'rgba(0,0,0,0.3)',
                    borderBottom: '1px solid var(--border-color)',
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontWeight: 600, color: 'var(--accent-green)', fontSize: '0.9rem' }}>
                    <Terminal size={16} />
                    BÁO CÁO CHIẾN LƯỢC KINH DOANH & ĐỀ XUẤT NHẬP KHO (STOREFLOW BI)
                  </div>
                  {repResult.is_fallback || repResult.provider === 'grounded' ? (
                    <Badge variant="warning">Chế độ SQL Aggregation (Fallback)</Badge>
                  ) : repResult.provider === 'ollama' ? (
                    <Badge variant="blue">Ollama Local BI Analysis</Badge>
                  ) : (
                    <Badge variant="success">Gemini Grounded Analysis</Badge>
                  )}
                </div>

                <div
                  style={{
                    padding: '1.5rem',
                    fontSize: '0.92rem',
                    lineHeight: '1.7',
                    color: 'var(--text-primary)',
                    fontFamily: 'var(--font-sans)',
                  }}
                >
                  <MarkdownRenderer content={repResult.ai_analysis} />
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Product Detail Modal for Image Search */}
      {selectedProductDetail && (
        <div
          style={{
            position: 'fixed',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            background: 'rgba(0, 0, 0, 0.75)',
            backdropFilter: 'blur(4px)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 9999,
            padding: '1rem',
          }}
          onClick={() => setSelectedProductDetail(null)}
        >
          <div
            style={{
              background: 'var(--panel-bg)',
              border: '1px solid var(--border-color)',
              boxShadow: 'var(--shadow-retro)',
              borderRadius: '6px',
              maxWidth: '650px',
              width: '100%',
              maxHeight: '90vh',
              overflowY: 'auto',
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <div
              style={{
                padding: '0.85rem 1.25rem',
                borderBottom: '1px solid var(--border-color)',
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                background: 'rgba(0,0,0,0.2)',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                {selectedProductDetail.relationship ? (
                  <Camera size={18} style={{ color: 'var(--accent-cyan)' }} />
                ) : (
                  <Sparkles size={18} style={{ color: 'var(--accent-amber)' }} />
                )}
                <span style={{ fontWeight: 700, fontSize: '0.95rem' }}>
                  {selectedProductDetail.relationship ? 'Chi tiết đối chiếu sản phẩm' : 'Chi tiết sản phẩm khuyến nghị'}
                </span>
              </div>
              <button
                type="button"
                onClick={() => setSelectedProductDetail(null)}
                className="btn btn-secondary"
                style={{ padding: '4px 8px' }}
              >
                <X size={16} />
              </button>
            </div>

            <div style={{ padding: '1.25rem' }}>
              <div style={{ marginBottom: '1rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                {selectedProductDetail.relationship ? (
                  renderRelationshipBadge(selectedProductDetail.relationship, selectedProductDetail)
                ) : (
                  <span
                    style={{
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: '4px',
                      fontSize: '0.75rem',
                      padding: '2px 8px',
                      borderRadius: '3px',
                      background: 'rgba(57, 211, 83, 0.15)',
                      color: 'var(--accent-green)',
                      border: '1px solid rgba(57, 211, 83, 0.4)',
                      fontFamily: 'var(--font-mono)',
                      fontWeight: 700,
                    }}
                  >
                    <CheckCircle size={12} /> [ XÁC THỰC SQLITE TỒN KHO &gt; 0 ]
                  </span>
                )}
                <span style={{ fontSize: '0.8rem', fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>
                  SKU: {selectedProductDetail.sku}
                </span>
              </div>

              <h3 style={{ margin: '0 0 0.5rem 0', fontSize: '1.15rem', color: 'var(--text-primary)' }}>
                {selectedProductDetail.name}
              </h3>

              {previewUrl && selectedProductDetail.relationship ? (
                <div className="form-grid-2" style={{ gap: '1rem', margin: '1rem 0' }}>
                  {/* Uploaded Preview */}
                  <div style={{ border: '1px solid var(--border-color)', borderRadius: '4px', padding: '0.75rem', textAlign: 'center' }}>
                    <div style={{ fontSize: '0.75rem', fontFamily: 'var(--font-mono)', color: 'var(--text-muted)', marginBottom: '0.5rem' }}>
                      [ ẢNH TRUY VẤN ]
                    </div>
                    <div style={{ height: '140px', display: 'flex', alignItems: 'center', justifyContent: 'center', background: '#0a0d14', borderRadius: '4px', overflow: 'hidden' }}>
                      <img src={previewUrl} alt="Query" style={{ maxWidth: '100%', maxHeight: '100%', objectFit: 'contain' }} />
                    </div>
                  </div>

                  {/* Product in Catalog */}
                  <div style={{ border: '1px solid var(--border-color)', borderRadius: '4px', padding: '0.75rem', textAlign: 'center' }}>
                    <div style={{ fontSize: '0.75rem', fontFamily: 'var(--font-mono)', color: 'var(--text-muted)', marginBottom: '0.5rem' }}>
                      [ KHO HÀNG SQLITE ]
                    </div>
                    <div style={{ height: '140px', display: 'flex', alignItems: 'center', justifyContent: 'center', background: '#0a0d14', borderRadius: '4px', overflow: 'hidden' }}>
                      <ProductImage src={selectedProductDetail.image_url} alt={selectedProductDetail.name} style={{ width: '100%', height: '100%', objectFit: 'contain' }} />
                    </div>
                  </div>
                </div>
              ) : (
                <div style={{ border: '1px solid var(--border-color)', borderRadius: '4px', padding: '0.75rem', textAlign: 'center', margin: '1rem 0' }}>
                  <div style={{ fontSize: '0.75rem', fontFamily: 'var(--font-mono)', color: 'var(--text-muted)', marginBottom: '0.5rem' }}>
                    [ HÌNH ẢNH SẢN PHẨM (KHO HÀNG SQLITE) ]
                  </div>
                  <div style={{ height: '180px', display: 'flex', alignItems: 'center', justifyContent: 'center', background: '#0a0d14', borderRadius: '4px', overflow: 'hidden' }}>
                    <ProductImage src={selectedProductDetail.image_url} alt={selectedProductDetail.name} style={{ width: '100%', height: '100%', objectFit: 'contain' }} />
                  </div>
                </div>
              )}

              {/* Specs & SQLite Verification */}
              <div
                style={{
                  background: 'rgba(0,0,0,0.2)',
                  border: '1px solid var(--border-color)',
                  borderRadius: '4px',
                  padding: '0.85rem',
                  marginBottom: '1rem',
                }}
              >
                <div className="form-grid-2" style={{ gap: '0.75rem', fontSize: '0.85rem' }}>
                  <div>
                    <span style={{ color: 'var(--text-muted)' }}>Giá bán niêm yết: </span>
                    <strong style={{ color: 'var(--accent-amber)', fontFamily: 'var(--font-mono)' }}>
                      {formatVND(selectedProductDetail.selling_price ?? selectedProductDetail.price)}
                    </strong>
                  </div>
                  <div>
                    <span style={{ color: 'var(--text-muted)' }}>Tồn kho thực tế: </span>
                    <StockBadge stock={selectedProductDetail.stock_quantity ?? 0} status={selectedProductDetail.status || 'active'} />
                  </div>
                  <div>
                    <span style={{ color: 'var(--text-muted)' }}>Danh mục: </span>
                    <strong>{selectedProductDetail.category_name || selectedProductDetail.category || 'Công nghệ'}</strong>
                  </div>
                  <div>
                    <span style={{ color: 'var(--text-muted)' }}>Trạng thái: </span>
                    <span style={{ color: 'var(--accent-green)', fontWeight: 600 }}>Đang kinh doanh</span>
                  </div>
                </div>
              </div>

              {/* Match explanation */}
              <div
                style={{
                  padding: '0.75rem',
                  borderRadius: '4px',
                  background: selectedProductDetail.relationship ? 'rgba(0, 229, 255, 0.05)' : 'rgba(255, 180, 84, 0.05)',
                  border: `1px solid ${selectedProductDetail.relationship ? 'rgba(0, 229, 255, 0.2)' : 'rgba(255, 180, 84, 0.2)'}`,
                  fontSize: '0.82rem',
                  lineHeight: '1.5',
                  color: 'var(--text-primary)',
                }}
              >
                <div style={{ fontWeight: 600, color: selectedProductDetail.relationship ? 'var(--accent-cyan)' : 'var(--accent-amber)', marginBottom: '2px' }}>
                  {selectedProductDetail.relationship ? 'Đánh giá phân loại AI:' : 'Ghi chú đề xuất của trợ lý AI:'}
                </div>
                {selectedProductDetail.match_reason || selectedProductDetail.description || 'Sản phẩm chính hãng đã qua kiểm chứng tồn kho khả dụng từ SQLite Database.'}
              </div>

              {selectedProductDetail.description && (
                <div style={{ marginTop: '0.75rem', fontSize: '0.82rem', color: 'var(--text-muted)' }}>
                  <strong>Mô tả: </strong>{selectedProductDetail.description}
                </div>
              )}

              <div style={{ marginTop: '1.25rem', display: 'flex', justifyContent: 'flex-end', gap: '0.5rem' }}>
                <button
                  type="button"
                  onClick={() => setSelectedProductDetail(null)}
                  className="btn btn-secondary"
                >
                  Đóng
                </button>
                {onNavigate && (
                  <button
                    type="button"
                    onClick={() => {
                      const sku = selectedProductDetail.sku;
                      setSelectedProductDetail(null);
                      onNavigate('pos');
                      addToast(`Đã chuyển tới POS. Mã sản phẩm: ${sku}`, 'info');
                    }}
                    className="btn btn-primary"
                    style={{ display: 'flex', alignItems: 'center', gap: '4px' }}
                  >
                    <ShoppingCart size={15} /> Mở bán trên POS
                  </button>
                )}
              </div>
            </div>
          </div>
        </div>
      )}

    </div>
  );
};
