import React, { useState, useEffect } from 'react';
import {
  ShieldCheck,
  Users,
  Cpu,
  RefreshCw,
  Search,
  UserPlus,
  CheckCircle,
  XCircle,
  Activity,
  Layers,
  Sparkles,
  Server,
  Database,
  Lock,
  Unlock,
  Key
} from 'lucide-react';
import { authAPI, aiAPI } from '../services/api';
import { useAuth } from '../context/AuthContext';
import { useToast } from '../context/ToastContext';
import { Badge, RoleBadge } from '../components/ui/Badge';
import { Modal } from '../components/ui/Modal';

export const AdminPage = () => {
  const { user, isSuperAdmin, isAdmin } = useAuth();
  const { addToast } = useToast();

  const [activeSubTab, setActiveSubTab] = useState('users');

  // Users State
  const [users, setUsers] = useState([]);
  const [loadingUsers, setLoadingUsers] = useState(false);
  const [searchUser, setSearchUser] = useState('');
  const [roleFilter, setRoleFilter] = useState('');
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [createForm, setCreateForm] = useState({
    username: '',
    password: '',
    full_name: '',
    role: 'staff',
  });
  const [submittingUser, setSubmittingUser] = useState(false);

  // AI & Tech State
  const [providersOverview, setProvidersOverview] = useState(null);
  const [aiLogs, setAiLogs] = useState([]);
  const [loadingAi, setLoadingAi] = useState(false);
  const [syncingVector, setSyncingVector] = useState(false);
  const [syncingVisuals, setSyncingVisuals] = useState(false);

  // Load Users
  const loadUsers = async () => {
    try {
      setLoadingUsers(true);
      const data = await authAPI.getUsers();
      setUsers(Array.isArray(data) ? data : []);
    } catch (err) {
      addToast(err.message, 'error');
    } finally {
      setLoadingUsers(false);
    }
  };

  // Load AI Providers & Logs
  const loadAiData = async () => {
    try {
      setLoadingAi(true);
      const [provData, logsData] = await Promise.all([
        aiAPI.getProviders().catch(() => null),
        aiAPI.getLogs(50).catch(() => []),
      ]);
      setProvidersOverview(provData);
      setAiLogs(Array.isArray(logsData) ? logsData : []);
    } catch (err) {
      addToast(err.message, 'error');
    } finally {
      setLoadingAi(false);
    }
  };

  useEffect(() => {
    if (activeSubTab === 'users') {
      loadUsers();
    } else {
      loadAiData();
    }
  }, [activeSubTab]);

  // Handle Toggle User Status
  const handleToggleStatus = async (targetUser) => {
    const newStatus = !targetUser.is_active;
    const actionText = newStatus ? 'kích hoạt' : 'khóa';
    if (!window.confirm(`Bạn có chắc chắn muốn ${actionText} tài khoản "${targetUser.username}"?`)) {
      return;
    }

    try {
      await authAPI.updateUserStatus(targetUser.id, newStatus);
      addToast(`Đã ${actionText} tài khoản "${targetUser.username}" thành công!`, 'success');
      loadUsers();
    } catch (err) {
      addToast(err.message, 'error');
    }
  };

  // Handle Create User
  const handleCreateUser = async (e) => {
    e.preventDefault();
    if (!createForm.username || !createForm.password || !createForm.full_name) {
      addToast('Vui lòng điền đầy đủ thông tin bắt buộc', 'warning');
      return;
    }

    try {
      setSubmittingUser(true);
      await authAPI.createUser(createForm);
      addToast(`Tạo mới tài khoản "${createForm.username}" thành công!`, 'success');
      setShowCreateModal(false);
      setCreateForm({
        username: '',
        password: '',
        full_name: '',
        role: 'staff',
      });
      loadUsers();
    } catch (err) {
      addToast(err.message, 'error');
    } finally {
      setSubmittingUser(false);
    }
  };

  // Handle Sync Vector DB
  const handleSyncVector = async () => {
    try {
      setSyncingVector(true);
      const res = await aiAPI.syncVectorIndex();
      addToast(res?.message || 'Đồng bộ hóa Vector DB (RAG) thành công!', 'success');
      loadAiData();
    } catch (err) {
      addToast(err.message, 'error');
    } finally {
      setSyncingVector(false);
    }
  };

  // Handle Sync Visuals
  const handleSyncVisuals = async () => {
    try {
      setSyncingVisuals(true);
      const res = await aiAPI.syncVisuals();
      addToast(res?.message || 'Đồng bộ CLIP Visual Embeddings thành công!', 'success');
      loadAiData();
    } catch (err) {
      addToast(err.message, 'error');
    } finally {
      setSyncingVisuals(false);
    }
  };

  // Filtered Users
  const filteredUsers = users.filter((u) => {
    const matchSearch =
      !searchUser ||
      u.username?.toLowerCase().includes(searchUser.toLowerCase()) ||
      u.full_name?.toLowerCase().includes(searchUser.toLowerCase());
    const matchRole = !roleFilter || u.role === roleFilter;
    return matchSearch && matchRole;
  });

  const getLogBadgeVariant = (action) => {
    if (!action) return 'muted';
    const act = action.toLowerCase();
    if (act.includes('recommend')) return 'blue';
    if (act.includes('qa') || act.includes('sales')) return 'amber';
    if (act.includes('report')) return 'green';
    if (act.includes('search') || act.includes('image')) return 'purple';
    return 'muted';
  };

  const getProviderBadge = (provider) => {
    if (!provider) return <Badge variant="muted">System</Badge>;
    const p = provider.toLowerCase();
    if (p.includes('ollama')) return <Badge variant="green">Ollama Local</Badge>;
    if (p.includes('gemini')) return <Badge variant="blue">Gemini Cloud</Badge>;
    if (p.includes('clip')) return <Badge variant="purple">CLIP ViT</Badge>;
    if (p.includes('sqlite') || p.includes('grounded')) return <Badge variant="amber">SQLite</Badge>;
    return <Badge variant="muted">{provider}</Badge>;
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
      {/* Top Header Card with Sub-Tab Switcher */}
      <div className="retro-card">
        <div className="retro-card-header" style={{ flexWrap: 'wrap', gap: '0.75rem' }}>
          <div className="retro-card-title">
            <ShieldCheck size={20} style={{ color: 'var(--blue-cyber)' }} />
            <span>BẢNG ĐIỀU HÀNH KỸ THUẬT & HỆ THỐNG</span>
            <span
              className="badge badge-blue"
              style={{
                fontSize: '0.68rem',
                marginLeft: '0.35rem',
                display: 'inline-flex',
                alignItems: 'center',
                gap: '4px',
                fontFamily: 'var(--font-mono)',
              }}
            >
              ADMIN PORTAL
            </span>
          </div>

          <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
            <button
              onClick={() => setActiveSubTab('users')}
              className={`btn btn-sm ${activeSubTab === 'users' ? 'btn-primary' : 'btn-outline'}`}
            >
              <Users size={14} /> Tài Khoản Người Dùng ({users.length})
            </button>
            <button
              onClick={() => setActiveSubTab('ai_tech')}
              className={`btn btn-sm ${activeSubTab === 'ai_tech' ? 'btn-primary' : 'btn-outline'}`}
            >
              <Cpu size={14} /> Hạ Tầng AI & Audit Logs
            </button>
          </div>
        </div>
      </div>

      {/* =========================================================================
          SUB-TAB 1: QUẢN TRỊ TÀI KHOẢN NGƯỜI DÙNG (USERS)
         ========================================================================= */}
      {activeSubTab === 'users' && (
        <>
          {/* User Metrics Grid */}
          <div className="kpi-grid" style={{ marginBottom: 0 }}>
            {/* KPI 1: Tổng Users */}
            <div className="kpi-card kpi-blue">
              <div className="kpi-icon-box">
                <Users size={22} />
              </div>
              <div className="kpi-info">
                <span className="kpi-label">Tổng Tài Khoản</span>
                <span className="kpi-value">{users.length}</span>
                <span className="kpi-sub">
                  {users.filter((u) => u.is_active).length} đang hoạt động
                </span>
              </div>
            </div>

            {/* KPI 2: Thu Ngân Staff */}
            <div className="kpi-card kpi-green">
              <div className="kpi-icon-box">
                <Key size={22} />
              </div>
              <div className="kpi-info">
                <span className="kpi-label">Thu Ngân (Staff)</span>
                <span className="kpi-value">{users.filter((u) => u.role === 'staff').length}</span>
                <span className="kpi-sub">Nhân viên bán hàng POS</span>
              </div>
            </div>

            {/* KPI 3: Khách Hàng Customer */}
            <div className="kpi-card kpi-amber">
              <div className="kpi-icon-box">
                <Users size={22} />
              </div>
              <div className="kpi-info">
                <span className="kpi-label">Khách Hàng (Customer)</span>
                <span className="kpi-value">{users.filter((u) => u.role === 'customer').length}</span>
                <span className="kpi-sub">Đặt hàng trực tuyến</span>
              </div>
            </div>

            {/* KPI 4: Quản Trị Kỹ Thuật */}
            <div className="kpi-card kpi-purple">
              <div className="kpi-icon-box">
                <Server size={22} />
              </div>
              <div className="kpi-info">
                <span className="kpi-label">Quản Trị Hệ Thống</span>
                <span className="kpi-value">
                  {users.filter((u) => u.role === 'admin' || u.role === 'superadmin').length}
                </span>
                <span className="kpi-sub">
                  1 SuperAdmin, {users.filter((u) => u.role === 'admin').length} Dev Admin
                </span>
              </div>
            </div>
          </div>

          {/* User Management Card with Toolbar & Table */}
          <div className="retro-card">
            {/* Filter & Action Toolbar */}
            <div
              style={{
                padding: '0.85rem 1.25rem',
                display: 'flex',
                flexWrap: 'wrap',
                gap: '0.75rem',
                alignItems: 'center',
                background: 'var(--bg-input)',
                borderBottom: '1px solid var(--border-subtle)',
              }}
            >
              <div className="input-with-icon" style={{ minWidth: 'min(100%, 260px)', flex: '1 1 260px' }}>
                <Search size={15} />
                <input
                  type="text"
                  className="form-control font-mono"
                  placeholder="Tìm theo username hoặc họ tên..."
                  value={searchUser}
                  onChange={(e) => setSearchUser(e.target.value)}
                />
              </div>

              <select
                className="form-control font-mono"
                style={{ flex: '0 0 auto', minWidth: '160px' }}
                value={roleFilter}
                onChange={(e) => setRoleFilter(e.target.value)}
              >
                <option value="">Tất cả vai trò</option>
                <option value="superadmin">Chủ Shop (SuperAdmin)</option>
                <option value="admin">Quản Trị (Admin Dev)</option>
                <option value="staff">Thu Ngân (Staff)</option>
                <option value="customer">Khách Hàng (Customer)</option>
              </select>

              <div style={{ marginLeft: 'auto', display: 'flex', gap: '0.5rem' }}>
                <button onClick={() => setShowCreateModal(true)} className="btn btn-primary btn-sm">
                  <UserPlus size={15} /> Thêm Tài Khoản Mới
                </button>
              </div>
            </div>

            {/* Users Data Table */}
            <div className="table-responsive">
              <table className="retro-table">
                <thead>
                  <tr>
                    <th style={{ width: '70px' }}>ID</th>
                    <th>TÊN ĐĂNG NHẬP</th>
                    <th>HỌ VÀ TÊN</th>
                    <th style={{ textAlign: 'center' }}>VAI TRÒ (ROLE)</th>
                    <th style={{ textAlign: 'center' }}>TRẠNG THÁI</th>
                    <th>NGÀY TẠO</th>
                    <th style={{ textAlign: 'center', width: '170px' }}>THAO TÁC</th>
                  </tr>
                </thead>
                <tbody>
                  {loadingUsers ? (
                    <tr>
                      <td colSpan={7} style={{ textAlign: 'center', padding: '2.5rem' }}>
                        <RefreshCw size={20} className="spin" style={{ display: 'inline', marginRight: '8px' }} />
                        Đang tải danh sách tài khoản người dùng...
                      </td>
                    </tr>
                  ) : filteredUsers.length === 0 ? (
                    <tr>
                      <td colSpan={7} style={{ textAlign: 'center', padding: '2.5rem', color: 'var(--text-muted)' }}>
                        Không tìm thấy tài khoản người dùng nào phù hợp.
                      </td>
                    </tr>
                  ) : (
                    filteredUsers.map((u) => {
                      const isSelf = u.id === user?.id;
                      const isSuper = u.role === 'superadmin';
                      // Tuyệt đối không cho phép tự khóa tài khoản của chính mình (isSelf)
                      const canToggle = !isSelf && (isSuperAdmin || (!isSuper && isAdmin));

                      return (
                        <tr key={u.id}>
                          <td className="font-mono" style={{ color: 'var(--text-muted)' }}>
                            #{u.id}
                          </td>
                          <td className="font-mono" style={{ fontWeight: 700, color: 'var(--blue-light)' }}>
                            {u.username}
                            {isSelf && (
                              <span
                                className="badge badge-blue"
                                style={{ fontSize: '0.62rem', marginLeft: '6px' }}
                              >
                                BẠN
                              </span>
                            )}
                          </td>
                          <td style={{ fontWeight: 600 }}>{u.full_name || '—'}</td>
                          <td style={{ textAlign: 'center' }}>
                            <RoleBadge role={u.role} />
                          </td>
                          <td style={{ textAlign: 'center' }}>
                            {u.is_active ? (
                              <span
                                className="badge badge-green"
                                style={{ display: 'inline-flex', alignItems: 'center', gap: '4px' }}
                              >
                                <CheckCircle size={11} /> Hoạt động
                              </span>
                            ) : (
                              <span
                                className="badge badge-red"
                                style={{ display: 'inline-flex', alignItems: 'center', gap: '4px' }}
                              >
                                <XCircle size={11} /> Đã khóa
                              </span>
                            )}
                          </td>
                          <td className="font-mono" style={{ fontSize: '0.78rem', color: 'var(--text-secondary)' }}>
                            {u.created_at ? new Date(u.created_at).toLocaleString('vi-VN') : '—'}
                          </td>
                          <td style={{ textAlign: 'center' }}>
                            {canToggle ? (
                              <button
                                onClick={() => handleToggleStatus(u)}
                                className={`btn btn-sm ${u.is_active ? 'btn-outline' : 'btn-primary'}`}
                                style={
                                  u.is_active
                                    ? { color: 'var(--red-light)', borderColor: 'rgba(248,81,73,0.4)' }
                                    : { background: 'var(--green-terminal)', borderColor: 'var(--green-dark)', color: '#0a0e13' }
                                }
                                title={u.is_active ? 'Khóa tài khoản này' : 'Mở khóa tài khoản này'}
                              >
                                {u.is_active ? (
                                  <>
                                    <Lock size={13} /> Khóa Tài Khoản
                                  </>
                                ) : (
                                  <>
                                    <Unlock size={13} /> Kích Hoạt
                                  </>
                                )}
                              </button>
                            ) : (
                              <span style={{ fontSize: '0.74rem', color: 'var(--text-muted)', fontStyle: 'italic' }}>
                                {isSelf ? 'Tài khoản của bạn' : 'Không có quyền'}
                              </span>
                            )}
                          </td>
                        </tr>
                      );
                    })
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}

      {/* =========================================================================
          SUB-TAB 2: HẠ TẦNG AI & AUDIT TRAIL
         ========================================================================= */}
      {activeSubTab === 'ai_tech' && (
        <>
          {/* Section 1: AI Provider Status Cards */}
          <div className="retro-card">
            <div className="retro-card-header">
              <div className="retro-card-title">
                <Server size={18} style={{ color: 'var(--green-terminal)' }} />
                <span>HẠ TẦNG & MÔ HÌNH AI (AI ENGINES)</span>
              </div>
              <span className="badge badge-green" style={{ fontSize: '0.7rem' }}>
                HỆ THỐNG ĐANG HOẠT ĐỘNG
              </span>
            </div>
            <div className="retro-card-body" style={{ padding: '1rem' }}>
              <div className="kpi-grid" style={{ marginBottom: 0 }}>
                {/* Provider 1: Ollama Local GPU */}
                <div className="kpi-card kpi-green">
                  <div className="kpi-icon-box">
                    <Cpu size={24} />
                  </div>
                  <div className="kpi-info">
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '0.5rem' }}>
                      <span className="kpi-label">Ollama Local Engine</span>
                      <span className="badge badge-green" style={{ fontSize: '0.62rem' }}>GPU Active</span>
                    </div>
                    <span className="kpi-value" style={{ fontSize: '1.05rem', color: 'var(--green-light)' }}>
                      Qwen 2.5 (1.5B)
                    </span>
                    <span className="kpi-sub">RTX 3050 (4GB) • Offline • Chi phí $0</span>
                  </div>
                </div>

                {/* Provider 2: Google Gemini Cloud */}
                <div className="kpi-card kpi-blue">
                  <div className="kpi-icon-box">
                    <Sparkles size={24} />
                  </div>
                  <div className="kpi-info">
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '0.5rem' }}>
                      <span className="kpi-label">Google Gemini Cloud</span>
                      <span className="badge badge-blue" style={{ fontSize: '0.62rem' }}>Fallback Ready</span>
                    </div>
                    <span className="kpi-value" style={{ fontSize: '1.05rem', color: 'var(--blue-light)' }}>
                      Gemini 2.5 Flash / Pro
                    </span>
                    <span className="kpi-sub">Tự động kích hoạt khi Local bận/tắt</span>
                  </div>
                </div>

                {/* Provider 3: CLIP Visual Search */}
                <div className="kpi-card kpi-purple">
                  <div className="kpi-icon-box">
                    <Layers size={24} />
                  </div>
                  <div className="kpi-info">
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '0.5rem' }}>
                      <span className="kpi-label">CLIP Visual Search</span>
                      <span className="badge badge-purple" style={{ fontSize: '0.62rem' }}>512-dim Vector</span>
                    </div>
                    <span className="kpi-value" style={{ fontSize: '1.05rem', color: 'var(--purple-neon)' }}>
                      ViT-B/32 Neural Net
                    </span>
                    <span className="kpi-sub">Tìm kiếm sản phẩm bằng tải ảnh</span>
                  </div>
                </div>

                {/* Provider 4: Hybrid RAG & Vector Index */}
                <div className="kpi-card kpi-amber">
                  <div className="kpi-icon-box">
                    <Database size={24} />
                  </div>
                  <div className="kpi-info">
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '0.5rem' }}>
                      <span className="kpi-label">Hybrid RAG & Stock Guard</span>
                      <span className="badge badge-amber" style={{ fontSize: '0.62rem' }}>Realtime</span>
                    </div>
                    <span className="kpi-value" style={{ fontSize: '1.05rem', color: 'var(--amber-primary)' }}>
                      ChromaDB + SQLite
                    </span>
                    <span className="kpi-sub">Chặn 100% tư vấn hàng hết tồn kho</span>
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Section 2: Synchronizations / Điều phối chỉ mục */}
          <div className="retro-card">
            <div className="retro-card-header">
              <div className="retro-card-title">
                <RefreshCw size={18} style={{ color: 'var(--amber-primary)' }} />
                <span>ĐIỀU PHỐI & ĐỒNG BỘ CHỈ MỤC TÌM KIẾM AI</span>
              </div>
            </div>
            <div className="retro-card-body">
              <p style={{ color: 'var(--text-secondary)', fontSize: '0.85rem', lineHeight: '1.5', margin: 0, marginBottom: '1rem' }}>
                Thực hiện nạp lại chỉ mục tìm kiếm ngữ nghĩa RAG (ChromaDB Vector Store) và đối soát vector đặc trưng hình ảnh
                (CLIP ViT-B/32) khi có cập nhật lớn về danh mục hoặc thêm mới sản phẩm hàng loạt.
              </p>

              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.75rem' }}>
                <button
                  onClick={handleSyncVector}
                  disabled={syncingVector}
                  className="btn btn-primary btn-sm"
                  style={{ minWidth: '220px' }}
                >
                  <Database size={15} className={syncingVector ? 'spin' : ''} />
                  {syncingVector ? 'Đang đồng bộ Vector DB...' : 'Đồng Bộ Hóa Vector DB (RAG)'}
                </button>

                <button
                  onClick={handleSyncVisuals}
                  disabled={syncingVisuals}
                  className="btn btn-outline btn-sm"
                  style={{ minWidth: '220px' }}
                >
                  <Layers size={15} className={syncingVisuals ? 'spin' : ''} />
                  {syncingVisuals ? 'Đang trích xuất đặc trưng ảnh...' : 'Đồng Bộ CLIP Visual Index'}
                </button>
              </div>
            </div>
          </div>

          {/* Section 3: AI Audit Logs Table */}
          <div className="retro-card">
            <div className="retro-card-header">
              <div className="retro-card-title">
                <Activity size={18} style={{ color: 'var(--blue-cyber)' }} />
                <span>NHẬT KÝ TRUY VẤN AI (AUDIT TRAIL)</span>
              </div>
              <button onClick={loadAiData} disabled={loadingAi} className="btn btn-outline btn-sm">
                <RefreshCw size={13} className={loadingAi ? 'spin' : ''} /> Làm Mới Logs
              </button>
            </div>

            <div className="table-responsive" style={{ maxHeight: '420px', overflowY: 'auto' }}>
              <table className="retro-table">
                <thead style={{ position: 'sticky', top: 0, zIndex: 10 }}>
                  <tr>
                    <th style={{ width: '130px' }}>THỜI GIAN</th>
                    <th style={{ width: '150px' }}>HÀNH ĐỘNG</th>
                    <th style={{ width: '130px' }}>PROVIDER</th>
                    <th>CÂU TRUY VẤN (QUERY / PROMPT)</th>
                    <th style={{ textAlign: 'center', width: '110px' }}>KẾT QUẢ</th>
                  </tr>
                </thead>
                <tbody>
                  {aiLogs.length === 0 ? (
                    <tr>
                      <td colSpan={5} style={{ textAlign: 'center', padding: '2.5rem', color: 'var(--text-muted)' }}>
                        Chưa có bản ghi nhật ký truy vấn AI nào.
                      </td>
                    </tr>
                  ) : (
                    aiLogs.map((log, idx) => (
                      <tr key={idx}>
                        <td className="font-mono" style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>
                          {log.created_at ? new Date(log.created_at).toLocaleTimeString('vi-VN') : '—'}
                        </td>
                        <td>
                          <Badge variant={getLogBadgeVariant(log.action || log.endpoint)}>
                            {log.action || log.endpoint || 'QUERY'}
                          </Badge>
                        </td>
                        <td>{getProviderBadge(log.provider)}</td>
                        <td
                          className="font-mono"
                          style={{
                            fontSize: '0.8rem',
                            color: 'var(--text-primary)',
                            maxWidth: '380px',
                            whiteSpace: 'nowrap',
                            overflow: 'hidden',
                            textOverflow: 'ellipsis',
                          }}
                          title={log.prompt || log.query || ''}
                        >
                          {log.prompt || log.query || '—'}
                        </td>
                        <td style={{ textAlign: 'center' }}>
                          <span className="badge badge-green" style={{ fontSize: '0.65rem' }}>
                            <CheckCircle size={10} /> THÀNH CÔNG
                          </span>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}

      {/* =========================================================================
          MODAL: THÊM TÀI KHOẢN NGƯỜI DÙNG MỚI
         ========================================================================= */}
      <Modal
        isOpen={showCreateModal}
        onClose={() => setShowCreateModal(false)}
        title="THÊM MỚI TÀI KHOẢN NGƯỜI DÙNG"
        maxWidth="500px"
      >
        <form onSubmit={handleCreateUser}>
          <div className="form-group">
            <label className="form-label">Tên Đăng Nhập (Username) *</label>
            <input
              type="text"
              required
              className="form-control font-mono"
              placeholder="Ví dụ: thu_ngan_02"
              value={createForm.username}
              onChange={(e) => setCreateForm({ ...createForm, username: e.target.value })}
            />
          </div>

          <div className="form-group">
            <label className="form-label">Họ và Tên Đầy Đủ *</label>
            <input
              type="text"
              required
              className="form-control"
              placeholder="Ví dụ: Nguyễn Thị Mai"
              value={createForm.full_name}
              onChange={(e) => setCreateForm({ ...createForm, full_name: e.target.value })}
            />
          </div>

          <div className="form-group">
            <label className="form-label">Mật Khẩu Khởi Tạo *</label>
            <input
              type="password"
              required
              className="form-control font-mono"
              placeholder="Tối thiểu 6 ký tự"
              value={createForm.password}
              onChange={(e) => setCreateForm({ ...createForm, password: e.target.value })}
            />
          </div>

          <div className="form-group">
            <label className="form-label">Phân Quyền Vai Trò (Role) *</label>
            <select
              className="form-control font-mono"
              value={createForm.role}
              onChange={(e) => setCreateForm({ ...createForm, role: e.target.value })}
            >
              <option value="staff">Thu Ngân (Staff)</option>
              <option value="customer">Khách Hàng (Customer)</option>
              {isSuperAdmin && <option value="admin">Quản Trị Kỹ Thuật (Admin Dev)</option>}
            </select>
            <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)', marginTop: '0.25rem' }}>
              Admin kỹ thuật chỉ được tạo tài khoản Thu Ngân hoặc Khách Hàng. Chỉ Chủ Shop (SuperAdmin) mới có quyền tạo
              Admin.
            </div>
          </div>

          <div
            style={{
              display: 'flex',
              justifyContent: 'flex-end',
              gap: '0.5rem',
              marginTop: '1.25rem',
              paddingTop: '0.85rem',
              borderTop: '1px solid var(--border-subtle)',
            }}
          >
            <button
              type="button"
              onClick={() => setShowCreateModal(false)}
              className="btn btn-outline btn-sm"
            >
              Hủy
            </button>
            <button
              type="submit"
              disabled={submittingUser}
              className="btn btn-primary btn-sm"
            >
              {submittingUser ? 'Đang tạo...' : 'Xác Nhận Tạo Tài Khoản'}
            </button>
          </div>
        </form>
      </Modal>
    </div>
  );
};
