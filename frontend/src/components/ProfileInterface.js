import React, { useState, useEffect, useRef, useCallback } from 'react';
import {
  User,
  MessageSquare,
  CheckCircle,
  TrendingUp,
  Trash2,
  Camera,
  ArrowLeft,
  Copy,
  Check,
  Loader2,
  Key,
  Plus,
  Plug,
  Globe2,
  CloudRain,
  Youtube,
  Brain
} from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import '../styles/ProfileInterface.css';
import profileService from '../services/profileService';
import authService from '../services/auth';
import userService from '../services/userService';

const Profile = () => {
  const navigate = useNavigate();
  // ========================
  // State
  // ========================
  const [user, setUser] = useState(null);
  // Inline editing is deprecated in favor of modal-based editing
  const [stats, setStats] = useState({});
  const [displayStats, setDisplayStats] = useState({ totalChats: 0, completedTasks: 0, usageRate: 0 });
  const statsAnimatingRef = useRef(false);
  const lastStatsRef = useRef(displayStats);
  const [globalMessage, setGlobalMessage] = useState(null); // { type:'success'|'error', text }
  // Removed editingFields/savingProfile; not used with modal-based editing
  const [apiKeys, setApiKeys] = useState([]);
  const [apiLoading, setApiLoading] = useState(false);
  const [showApiModal, setShowApiModal] = useState(false);
  const [apiModalStep, setApiModalStep] = useState(1); // 1 = provider select, 2 = key form
  const [selectedProvider, setSelectedProvider] = useState(null);
  const [newApiData, setNewApiData] = useState({ name: '', key: '', description: '' });
  const [apiError, setApiError] = useState(null);
  const [apiSaving, setApiSaving] = useState(false);
  // Removed customStats editing (unused)
  const [showProfileModal, setShowProfileModal] = useState(false);
  const [profileModalValues, setProfileModalValues] = useState({ name: '', role: '', hobbies: '' });
  const [profileModalSaving, setProfileModalSaving] = useState(false);
  const [toast, setToast] = useState(null); // { type, text }
  const [avatarUploading, setAvatarUploading] = useState(false);
  const [avatarError, setAvatarError] = useState(null);
  const [showApiDeleteModal, setShowApiDeleteModal] = useState(false);
  const [apiDeleteTarget, setApiDeleteTarget] = useState(null);
  const [apiDeleting, setApiDeleting] = useState(false);
  const [showDeleteAccount, setShowDeleteAccount] = useState(false);
  const [deletingAccount, setDeletingAccount] = useState(false);

  const roleOptions = [
    { value: 'student', label: 'Student 🎓' },
    { value: 'employee', label: 'Employee 👔' },
    { value: 'web_developer', label: 'Web Developer 💻' },
    { value: 'ai_developer', label: 'AI Developer 🤖' },
    { value: 'designer', label: 'Designer 🎨' },
    { value: 'manager', label: 'Manager 🧭' },
    { value: 'researcher', label: 'Researcher 🔬' },
    { value: 'content_creator', label: 'Content Creator ✍️' }
  ];
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [deleteType, setDeleteType] = useState('');
  const [showLogoutModal, setShowLogoutModal] = useState(false);
  // Logout handler
  const handleLogout = async () => {
    try { authService.logout(); } catch {}
    window.location.href = '/';
  };
  const fileInputRef = useRef(null);

  // ========================
  // Load Data
  // ========================
  useEffect(() => {
    const loadProfile = async () => {
      // Fetch basics from users collection (/auth/me) and profile for extras
      const [me, profile] = await Promise.all([
        userService.getMe(),
        profileService.getProfile(),
      ]);
      const meData = me.success ? (me.data || {}) : {};
      const profData = profile.success ? (profile.data || {}) : {};
      const merged = {
        ...profData,
        user_id: profData.user_id || meData.user_id,
        name: profData.name || meData.username || '',
        email: meData.email || profData.email || '',
        role: meData.role || profData.role || '',
        hobbies: Array.isArray(meData.hobbies) ? meData.hobbies : (Array.isArray(profData.hobbies) ? profData.hobbies : []),
        username: meData.username || '',
      };
      setUser(merged);
      // Inline edit values removed
    };

    const loadStats = async () => {
      const result = await profileService.getUserStats();
      if (result.success) {
        const raw = result.data || {};
        const normalized = {
          totalChats: raw.total_chats ?? raw.totalChats ?? 0,
          completedTasks: raw.completed_tasks ?? raw.completedTasks ?? 0,
          totalTasks: raw.total_tasks ?? raw.totalTasks ?? 0,
          totalMessages: raw.total_messages ?? raw.totalMessages ?? 0,
          totalUserMessages: raw.total_user_messages ?? raw.totalUserMessages ?? 0,
          usageRate: raw.usage_rate ?? raw.usageRate ?? 0,
        };
        setStats(normalized);
      }
    };

    const loadApiKeys = async () => {
      setApiLoading(true);
      const result = await profileService.getApiKeys();
      if (result.success) setApiKeys(result.data || []);
      setApiLoading(false);
    };

    loadProfile();
    loadStats();
    loadApiKeys();
    // Polling interval for live stats
    const interval = setInterval(loadStats, 15000); // 15s
    // Optional event-based refresh hooks
    const refreshEvents = ['maya:chat-updated', 'maya:tasks-updated'];
    const refreshHandler = () => loadStats();
    refreshEvents.forEach(ev => window.addEventListener(ev, refreshHandler));
    return () => {
      clearInterval(interval);
      refreshEvents.forEach(ev => window.removeEventListener(ev, refreshHandler));
    };
  }, []);

  // Animated number transition helper
  const animateStats = useCallback((from, to, duration = 600) => {
    statsAnimatingRef.current = true;
    const start = performance.now();
    const step = (now) => {
      const progress = Math.min(1, (now - start) / duration);
      const ease = 1 - Math.pow(1 - progress, 3); // easeOutCubic
      const current = {
        totalChats: Math.round(from.totalChats + (to.totalChats - from.totalChats) * ease),
        completedTasks: Math.round(from.completedTasks + (to.completedTasks - from.completedTasks) * ease),
        usageRate: from.usageRate + (to.usageRate - from.usageRate) * ease,
      };
      setDisplayStats(current);
      if (progress < 1) {
        requestAnimationFrame(step);
      } else {
        statsAnimatingRef.current = false;
        lastStatsRef.current = to;
      }
    };
    requestAnimationFrame(step);
  }, []);

  // Trigger animation when stats change
  useEffect(() => {
    if (!stats) return;
    const target = {
      totalChats: stats.totalChats || 0,
      completedTasks: stats.completedTasks || 0,
      usageRate: stats.usageRate || 0,
    };
    animateStats(lastStatsRef.current, target);
  }, [stats, animateStats]);

  // Removed unused number formatter

  // Display exact percentage from authoritative stats to avoid animation rounding drift
  const usageRateDisplay = `${Math.round(stats?.usageRate || 0)}%`;

  // Removed focus effect for inline editing

  // ========================
  // Handlers
  // ========================
  // Removed inline edit handlers

  const openProfileModal = () => {
    setProfileModalValues({
      name: (user?.name || user?.username || ''),
      role: user?.role || 'student',
      hobbies: (user?.hobbies || []).join(', '),
    });
    setShowProfileModal(true);
  };

  const closeProfileModal = () => {
    if (!profileModalSaving) setShowProfileModal(false);
  };

  const handleProfileModalSave = async () => {
    if (!user) return;
    const payload = {};
    // username is the canonical field in users collection
    if ((profileModalValues.name || '') !== (user.username || user.name || '')) payload.username = profileModalValues.name || '';
    if ((profileModalValues.role || '') !== (user.role || '')) payload.role = profileModalValues.role || '';
    const hobbiesList = (profileModalValues.hobbies || '').split(',').map(s => s.trim()).filter(Boolean);
    if (JSON.stringify(hobbiesList) !== JSON.stringify(user.hobbies || [])) payload.hobbies = hobbiesList;
    if (Object.keys(payload).length === 0) {
      setToast({ type: 'info', text: 'No changes to save.' });
      autoHideToast();
      setShowProfileModal(false);
      return;
    }
    setProfileModalSaving(true);
    // Persist to users collection via /auth/me
    const result = await userService.updateMe(payload);
    if (result.success) {
      const updated = result.data || {};
      const merged = {
        ...user,
        username: updated.username ?? payload.username ?? user.username,
        name: updated.username ?? payload.username ?? user.name,
        role: updated.role ?? payload.role ?? user.role,
        hobbies: updated.hobbies ?? payload.hobbies ?? user.hobbies,
      };
      setUser(merged);
      setToast({ type: 'success', text: 'Updated profile' });
      // Refresh stats in case role/hobbies affect analytics downstream
      try {
        const statsResult = await profileService.getUserStats();
        if (statsResult.success) {
          const raw = statsResult.data || {};
          const normalized = {
            totalChats: raw.total_chats ?? raw.totalChats ?? 0,
            completedTasks: raw.completed_tasks ?? raw.completedTasks ?? 0,
            totalTasks: raw.total_tasks ?? raw.totalTasks ?? 0,
            totalMessages: raw.total_messages ?? raw.totalMessages ?? 0,
            totalUserMessages: raw.total_user_messages ?? raw.totalUserMessages ?? 0,
            usageRate: raw.usage_rate ?? raw.usageRate ?? 0,
          };
          setStats(normalized);
        }
      } catch {}
      // Sync into authService stored user object for global usage (e.g., navbar)
      try {
        const stored = authService.getCurrentUser() || {};
        const nextStored = { ...stored };
        if (merged.name) nextStored.name = merged.name;
        if (merged.role) nextStored.role = merged.role;
        if (Array.isArray(merged.hobbies)) nextStored.hobbies = merged.hobbies;
        localStorage.setItem('user', JSON.stringify(nextStored));
      } catch (e) { /* ignore storage issues */ }
      // Broadcast custom event so other components can react without manual refresh
      try {
        window.dispatchEvent(new CustomEvent('maya:profile-updated', { detail: { updated: payload } }));
      } catch (e) { /* noop */ }
      setShowProfileModal(false);
    } else {
      setToast({ type: 'error', text: result.error || 'Update failed' });
    }
    setProfileModalSaving(false);
    autoHideToast();
  };

  const autoHideToast = () => {
    setTimeout(() => setToast(null), 2500);
  };

  // API delete handlers (added)
  const requestDeleteApi = (keyObj) => {
    setApiDeleteTarget(keyObj);
    setShowApiDeleteModal(true);
  };

  const confirmDeleteApi = async () => {
    if (!apiDeleteTarget) return;
    setApiDeleting(true);
    const keyId = apiDeleteTarget.id || apiDeleteTarget._id;
    const result = await profileService.deleteApiKey(keyId);
    if (result.success) {
      setApiKeys(prev => prev.filter(k => (k.id || k._id) !== keyId));
      setToast({ type: 'success', text: 'Deleted API key' });
    } else {
      setToast({ type: 'error', text: result.error || 'Delete failed' });
    }
    setApiDeleting(false);
    setShowApiDeleteModal(false);
    setApiDeleteTarget(null);
    autoHideToast();
  };

  // Removed global save/cancel handlers (deprecated)

  // ========================
  // API Key Management
  // ========================
  const providers = [
    { id: 'gemini', label: 'Gemini', icon: <Brain size={18} />, desc: 'Google Gemini AI' },
    { id: 'cohere', label: 'Cohere', icon: <Brain size={18} />, desc: 'Cohere NLP' },
    { id: 'anthropic', label: 'Anthropic', icon: <Brain size={18} />, desc: 'Claude / Anthropic' },
    { id: 'youtube', label: 'YouTube', icon: <Youtube size={18} />, desc: 'YouTube Data API' },
    { id: 'news', label: 'News', icon: <Globe2 size={18} />, desc: 'News API' },
    { id: 'weather', label: 'Weather', icon: <CloudRain size={18} />, desc: 'Weather API' }
  ];

  const openAddApiModal = () => {
    setShowApiModal(true);
    setApiModalStep(1);
    setSelectedProvider(null);
    setNewApiData({ name: '', key: '', description: '' });
    setApiError(null);
  };

  const handleProviderSelect = (prov) => {
    setSelectedProvider(prov);
    setApiModalStep(2);
  };

  const handleSaveApi = async () => {
    if (!selectedProvider) return;
    if (!newApiData.key.trim()) {
      setApiError('API key is required');
      return;
    }
    setApiSaving(true);
    setApiError(null);
    const payload = {
      provider: selectedProvider.id,
      external_key: newApiData.key.trim(),
      name: newApiData.name.trim() || selectedProvider.label,
      description: newApiData.description.trim() || undefined
    };
    const result = await profileService.createApiKey(payload);
    if (result.success) {
      // Construct a client-side representation since backend returns limited fields
      const preview = result.data?.key_preview || result.data?.keyPreview || '••••';
      const newKey = {
        id: crypto.randomUUID(),
        name: payload.name,
        description: payload.description,
        provider: payload.provider,
        key_preview: preview,
        created_at: new Date().toISOString(),
        is_active: true
      };
      setApiKeys(prev => [newKey, ...prev]);
      setShowApiModal(false);
      setGlobalMessage({ type: 'success', text: `${selectedProvider.label} API added.` });
    } else {
      setApiError(result.error || 'Failed to save API key');
    }
    setApiSaving(false);
  };
  // Removed unused handleDeleteApi (using modal-based delete now)

  // ========================
  // Custom Stats Editing (local only)
  // ========================
  // Removed unused custom stat change handler

  const handleAvatarChange = (event) => {
    const file = event.target.files?.[0];
    if (!file) return;
    setAvatarError(null);
    // Client-side validation
    const allowed = ['image/jpeg','image/png','image/gif','image/webp'];
    if (!allowed.includes(file.type)) {
      setToast({ type: 'error', text: 'Unsupported image type' });
      autoHideToast();
      return;
    }
    if (file.size > 5 * 1024 * 1024) { // 5MB
      setToast({ type: 'error', text: 'Image too large (max 5MB)' });
      autoHideToast();
      return;
    }
    setAvatarUploading(true);
    (async () => {
      const result = await profileService.uploadAvatar(file);
      if (result.success) {
        const avatarUrl = result.data?.avatar_url || result.data?.avatarUrl;
        if (avatarUrl) {
          setUser(prev => ({ ...prev, avatar_url: avatarUrl }));
          try {
            const stored = authService.getCurrentUser() || {};
            const merged = { ...stored, avatar_url: avatarUrl };
            localStorage.setItem('user', JSON.stringify(merged));
          } catch {}
          try {
            window.dispatchEvent(new CustomEvent('maya:profile-updated', { detail: { updated: { avatar_url: avatarUrl } } }));
          } catch {}
        }
        setToast({ type: 'success', text: 'Updated profile' });
      } else {
        setToast({ type: 'error', text: result.error || 'Avatar upload failed' });
        setAvatarError(result.error || 'Upload failed');
      }
      setAvatarUploading(false);
      autoHideToast();
    })();
  };

  const handleDelete = (type) => {
    setDeleteType(type);
    setShowDeleteModal(true);
  };

  const confirmDelete = () => {
    setShowDeleteModal(false);
    setDeleteType('');
    // TODO: call backend to delete specific memory
  };

  // ========================
  // Render Helpers
  // ========================
  const renderEditableField = (field, label, value, { icon = <User size={20} /> } = {}) => (
    <div className="info-item">
      {icon}
      <div className="info-details">
        <label>{label}</label>
        <div className="display-row"><p>{value || 'Not set'}</p></div>
      </div>
    </div>
  );

  // ========================
  // Render
  // ========================
  if (!user) return <div>Loading profile...</div>;

  return (
    <div className="profile-page">
  <div className="profile-header">
        <button
          className="profile-back-btn"
          onClick={() => navigate(-1)}
          aria-label="Go back"
        >
          <ArrowLeft size={18} />
          <span className="profile-back-text">Back</span>
        </button>
        <h1>Profile</h1>
  <div className="profile-header-actions" />
      </div>

  <div className="profile-content">
  {/* Profile Card */}
        <div className="profile-card">
          <div className="profile-avatar-section">
            <div className="avatar-wrapper">
              {user.avatar_url ? (
                <img src={user.avatar_url} alt="avatar" className="profile-avatar-large" />
              ) : (
                <div className="profile-avatar-large">
                  {user.name?.split(' ').map((n) => n[0]).join('').slice(0,2)}
                </div>
              )}
              {avatarUploading && <div className="avatar-overlay"><Loader2 size={32} className="spin" /></div>}
            </div>
            <button className="change-photo-btn" disabled={avatarUploading} onClick={() => fileInputRef.current?.click()}>
              <Camera size={16} /> {avatarUploading ? 'Uploading...' : 'Change Photo'}
            </button>
            {avatarError && <div className="field-error" style={{textAlign:'center'}}>{avatarError}</div>}
            <input
              ref={fileInputRef}
              type="file"
              accept="image/*"
              style={{ display: 'none' }}
              onChange={handleAvatarChange}
            />
          </div>

          <div className="profile-info-section">
            {globalMessage && (
              <div className={`profile-global-message ${globalMessage.type}`}>{globalMessage.text}</div>
            )}
            {renderEditableField('name', 'Username', user.username || user.name, { editable: false })}
            {renderEditableField('user_id', 'User ID', user.user_id || user._id, { editable: false, readOnly: true })}
            {/* Email purely from auth store if available */}
            <div className="info-item">
              <User size={20} />
              <div className="info-details">
                <label>Email</label>
                <div className="display-row"><p>{(authService.getCurrentUser()?.username) || (authService.getCurrentUser()?.email) || user.email || 'Not set'}</p></div>
              </div>
            </div>
            {/* Role Field (modal trigger) */}
            <div className="info-item role-item">
              <User size={20} />
              <div className="info-details">
                <label>Role</label>
                <div className="display-row"><p>{roleOptions.find(r => r.value === user.role)?.label || user.role || 'Not set'}</p></div>
              </div>
            </div>
            {/* Hobbies display */}
            <div className="info-item">
              <User size={20} />
              <div className="info-details">
                <label>Hobbies</label>
                <div className="display-row"><p>{(user.hobbies && user.hobbies.length > 0) ? user.hobbies.join(', ') : 'Not set'}</p></div>
              </div>
            </div>

            <div className="single-edit-launch dual">
              <button className="btn-primary" onClick={openProfileModal}>Edit Profile</button>
              <button className="btn-primary" onClick={openAddApiModal}><Plus size={16} /> Add API</button>
            </div>
            <div className="single-edit-launch" style={{ display: 'flex', gap: 8 }}>
              <button className="btn-danger" onClick={() => setShowDeleteAccount(true)}>
                <Trash2 size={16} /> Delete Account
              </button>
              <button className="menu-item logout" style={{ display: 'flex', alignItems: 'center', gap: 6 }} onClick={() => setShowLogoutModal(true)}>
                <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="lucide lucide-log-out" aria-hidden="true"><path d="m16 17 5-5-5-5"></path><path d="M21 12H9"></path><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"></path></svg>
                <span>Logout</span>
              </button>
            </div>
      {/* Logout Confirmation Modal */}
      {showLogoutModal && (
        <div className="modal-overlay" onClick={() => setShowLogoutModal(false)}>
          <div className="modal-content" onClick={e => e.stopPropagation()}>
            <h3>Confirm Logout</h3>
            <p>Are you sure you want to logout?</p>
            <div className="modal-actions">
              <button className="btn-secondary" onClick={() => setShowLogoutModal(false)}>Cancel</button>
              <button className="btn-danger" onClick={handleLogout}>Logout</button>
            </div>
          </div>
        </div>
      )}

            {/* Removed bulk save bar in favor of modal-based editing */}

            {/* API Keys moved here */}
            <div className="embedded-api-section">
              <h2 className="embedded-section-title">Connected APIs</h2>
              <div className="api-helper-text">Manage external API integrations you have added.</div>
              {apiLoading ? (
                <div className="api-loading">Loading APIs...</div>
              ) : (
                <div className="api-keys-list">
                  {apiKeys.length === 0 && (
                    <div className="empty-api">No APIs added yet. Click <strong>Add API</strong> to connect one.</div>
                  )}
                  {apiKeys.map(key => {
                    const provider = providers.find(p => p.id === key.provider) || { label: key.provider };
                    const masked = key.key_preview || (key.key ? key.key.replace(/.(?=.{4})/g, '*') : '••••');
                    return (
                      <div key={key.id || key._id} className="api-key-item">
                        <div className="api-key-left">
                          <div className="api-provider-icon">{provider.icon || <Plug size={14} />}</div>
                          <div className="api-key-meta">
                            <div className="api-key-name">{key.name || provider.label}</div>
                            <div className="api-key-mask">{masked}</div>
                          </div>
                        </div>
                        <div className="api-key-actions">
                          <button className="api-delete-btn" onClick={() => requestDeleteApi(key)} aria-label="Delete API Key">
                            <Trash2 size={14} />
                          </button>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          </div>
        </div>
        {/* Stats (read-only now) */}
        <div className="stats-card live">
          <div className="stats-header-row">
            <h2>Usage Statistics</h2>
            <button className="stat-refresh-btn" onClick={() => { if(!statsAnimatingRef.current) { lastStatsRef.current = displayStats; } profileService.getUserStats().then(r=>{ if(r.success){ const raw=r.data||{}; const normalized={ totalChats: raw.total_chats??0, completedTasks: raw.completed_tasks??0, totalTasks: raw.total_tasks??0, totalMessages: raw.total_messages??0, totalUserMessages: raw.total_user_messages??0, usageRate: raw.usage_rate??0 }; setStats(normalized);} }); }} aria-label="Refresh stats">↻</button>
          </div>
          <div className="stats-grid live">
            <div className="stat-item live">
              <div className="stat-top">
                <div className="stat-icon gradient-a"><MessageSquare size={20} /></div>
                <div className="stat-metric">
                  <span className="stat-value animated" data-label="Total Chats">{Number(stats.totalChats || 0).toLocaleString()}</span>
                  <span className="stat-label">Total Chats</span>
                </div>
              </div>
              <div className="stat-bar-wrapper" aria-label={`Total chats ${stats.totalChats || 0}`}> 
                <div className="stat-bar-bg"><div className="stat-bar-fill" style={{ width: (displayStats.totalChats ? 100 : 0) + '%'}} /></div>
              </div>
            </div>
            <div className="stat-item live">
              <div className="stat-top">
                <div className="stat-icon gradient-b"><CheckCircle size={20} /></div>
                <div className="stat-metric">
                  <span className="stat-value animated" data-label="Completed Tasks">{Number(stats.completedTasks || 0).toLocaleString()}</span>
                  <span className="stat-label">Completed Tasks</span>
                </div>
              </div>
              <div className="stat-bar-wrapper" aria-label={`Completed tasks ${displayStats.completedTasks}`}> 
                <div className="stat-bar-bg"><div className="stat-bar-fill alt" style={{ width: stats.totalTasks ? (displayStats.completedTasks / (stats.totalTasks||1))*100 + '%' : '0%' }} /></div>
                <div className="stat-mini-note">{stats.totalTasks ? `${displayStats.completedTasks}/${stats.totalTasks}` : '0/0'}</div>
              </div>
            </div>
            <div className="stat-item live">
              <div className="stat-top">
                <div className="stat-icon gradient-c"><TrendingUp size={20} /></div>
                <div className="stat-metric">
                  <span className="stat-value animated" data-label="Usage Rate">{usageRateDisplay}</span>
                  <span className="stat-label">Usage Rate</span>
                </div>
              </div>
              <div className="rate-ring" role="img" aria-label={`Usage rate ${usageRateDisplay}`}>
                <svg viewBox="0 0 36 36" className="ring-svg">
                  <path className="ring-bg" d="M18 2 a 16 16 0 0 1 0 32 a 16 16 0 0 1 0 -32" />
                  <path className="ring-fg" strokeDasharray={`${Math.max(0, Math.min(100, (displayStats.usageRate || 0))).toFixed(1)}, 100`} d="M18 2 a 16 16 0 0 1 0 32 a 16 16 0 0 1 0 -32" />
                </svg>
                <div className="ring-center">{Math.round(displayStats.usageRate)}%</div>
              </div>
            </div>
          </div>
        </div>

        {/* Memory Management */}
        <div className="memory-card">
          <h2>Memory Management</h2>
          <p className="memory-description">
            Manage your conversation memory and data. Deleting memory will remove stored context and preferences.
          </p>

          <div className="memory-actions">
            {['short-term', 'long-term', 'semantic', 'all'].map((type) => (
              <div key={type} className={`memory-item ${type === 'all' ? 'danger' : ''}`}>
                <div className="memory-info">
                  <h3>{type === 'all' ? 'Delete All Data' : `${type.replace('-', ' ')} Memory`}</h3>
                  <p>
                    {type === 'short-term' && 'Current conversation context'}
                    {type === 'long-term' && 'Historical conversation data'}
                    {type === 'semantic' && 'Learned preferences and patterns'}
                    {type === 'all' && 'Permanently remove all stored information'}
                  </p>
                </div>
                <button className={`delete-btn ${type === 'all' ? 'danger' : ''}`} onClick={() => handleDelete(type)}>
                  <Trash2 size={18} /> Delete
                </button>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Delete Confirmation Modal */}
      {showDeleteModal && (
        <div className="modal-overlay" onClick={() => setShowDeleteModal(false)}>
          <div className="modal-content" onClick={e => e.stopPropagation()}>
            <h3>Confirm Deletion</h3>
            <p>
              Are you sure you want to delete {deleteType === 'all' ? 'all your data' : `your ${deleteType} memory`}? This action cannot be undone.
            </p>
            <div className="modal-actions">
              <button className="btn-secondary" onClick={() => setShowDeleteModal(false)}>Cancel</button>
              <button className="btn-danger" onClick={confirmDelete}>Delete</button>
            </div>
          </div>
        </div>
      )}

      {showProfileModal && (
        <div className="modal-overlay" onClick={closeProfileModal}>
          <div className="modal-content profile-edit-modal" onClick={(e)=>e.stopPropagation()}>
            <h3>Edit Profile Details</h3>
            <div className="profile-modal-body">
              <label className="modal-field">
                <span>Username</span>
                <input
                  value={profileModalValues.name}
                  onChange={e => setProfileModalValues(v => ({ ...v, name: e.target.value }))}
                  placeholder="Enter username"
                />
              </label>
              <label className="modal-field">
                <span>Role</span>
                <select
                  value={profileModalValues.role}
                  onChange={e => setProfileModalValues(v => ({ ...v, role: e.target.value }))}
                  className="role-select"
                >
                  {roleOptions.map(opt => (
                    <option key={opt.value} value={opt.value}>{opt.label}</option>
                  ))}
                </select>
              </label>
              <label className="modal-field">
                <span>Hobbies</span>
                <input
                  value={profileModalValues.hobbies}
                  onChange={e => setProfileModalValues(v => ({ ...v, hobbies: e.target.value }))}
                  placeholder="e.g. coding, music, football"
                />
                <div style={{fontSize:12,color:'#64748b'}}>Comma-separated list</div>
              </label>
            </div>
            <div className="modal-actions">
              <button className="btn-secondary" onClick={closeProfileModal} disabled={profileModalSaving}>Cancel</button>
              <button className="btn-primary" onClick={handleProfileModalSave} disabled={profileModalSaving}>
                {profileModalSaving ? <Loader2 size={16} className="spin" /> : <Check size={16} />} Save
              </button>
            </div>
          </div>
        </div>
      )}

      {toast && (
        <div className={`profile-toast ${toast.type}`}> {toast.text} </div>
      )}

      {showApiModal && (
        <div className="modal-overlay" onClick={() => setShowApiModal(false)}>
          <div className="modal-content api-modal" onClick={(e) => e.stopPropagation()}>
            {apiModalStep === 1 && (
              <>
                <h3>Select API Provider</h3>
                <div className="provider-grid">
                  {providers.map(p => (
                    <button
                      key={p.id}
                      className="provider-card"
                      onClick={() => handleProviderSelect(p)}
                    >
                      <div className="provider-icon">{p.icon}</div>
                      <div className="provider-info">
                        <span className="provider-name">{p.label}</span>
                        <span className="provider-desc">{p.desc}</span>
                      </div>
                    </button>
                  ))}
                </div>
              </>
            )}
            {apiModalStep === 2 && selectedProvider && (
              <>
                <h3>Add {selectedProvider.label} API</h3>
                <div className="api-form">
                  <label>
                    <span>Name (optional)</span>
                    <input
                      value={newApiData.name}
                      onChange={(e) => setNewApiData(d => ({ ...d, name: e.target.value }))}
                      placeholder={`${selectedProvider.label} Key`}
                    />
                  </label>
                  <label>
                    <span>API Key</span>
                    <input
                      value={newApiData.key}
                      onChange={(e) => setNewApiData(d => ({ ...d, key: e.target.value }))}
                      placeholder="Paste your API key"
                    />
                  </label>
                  <label>
                    <span>Description (optional)</span>
                    <textarea
                      rows={3}
                      value={newApiData.description}
                      onChange={(e) => setNewApiData(d => ({ ...d, description: e.target.value }))}
                      placeholder="Short description"
                    />
                  </label>
                  {apiError && <div className="field-error" style={{ marginTop: 4 }}>{apiError}</div>}
                </div>
                <div className="modal-actions api">
                  <button className="btn-secondary" onClick={() => { setApiModalStep(1); setSelectedProvider(null); }}>Back</button>
                  <button className="btn-secondary" onClick={() => setShowApiModal(false)}>Cancel</button>
                  <button className="btn-primary" disabled={apiSaving} onClick={handleSaveApi}>
                    {apiSaving ? <Loader2 size={16} className="spin" /> : <Key size={16} />} Save
                  </button>
                </div>
              </>
            )}
          </div>
        </div>
      )}

      {showApiDeleteModal && apiDeleteTarget && (
        <div className="modal-overlay" onClick={()=> !apiDeleting && setShowApiDeleteModal(false)}>
          <div className="modal-content api-delete-modal" onClick={e=>e.stopPropagation()}>
            <h3>Delete API Key</h3>
            <p className="api-delete-text">Are you sure you want to delete <strong>{apiDeleteTarget.name || apiDeleteTarget.provider || 'this key'}</strong>? This action cannot be undone.</p>
            <div className="modal-actions">
              <button className="btn-secondary" disabled={apiDeleting} onClick={()=> setShowApiDeleteModal(false)}>Cancel</button>
              <button className="btn-danger" disabled={apiDeleting} onClick={confirmDeleteApi}>{apiDeleting ? <Loader2 size={16} className="spin" /> : <Trash2 size={16} />} Delete</button>
            </div>
          </div>
        </div>
      )}

      {showDeleteAccount && (
        <div className="modal-overlay" onClick={() => !deletingAccount && setShowDeleteAccount(false)}>
          <div className="modal-content api-delete-modal" onClick={e=>e.stopPropagation()}>
            <h3>Delete Your Account</h3>
            <p className="api-delete-text">
              This will permanently delete your account and all associated data (chats, tasks, memories, API keys, logs). This action cannot be undone.
            </p>
            <div className="modal-actions">
              <button className="btn-secondary" disabled={deletingAccount} onClick={()=> setShowDeleteAccount(false)}>Cancel</button>
              <button className="btn-danger" disabled={deletingAccount} onClick={async ()=>{
                setDeletingAccount(true);
                const res = await userService.deleteMe();
                if (res.success) {
                  setToast({ type: 'success', text: 'Account deleted' });
                  try { authService.logout(); } catch {}
                  window.location.href = '/';
                } else {
                  setToast({ type: 'error', text: res.error || 'Failed to delete account' });
                }
                setDeletingAccount(false);
                setShowDeleteAccount(false);
                autoHideToast();
              }}>
                {deletingAccount ? <Loader2 size={16} className="spin" /> : <Trash2 size={16} />} Delete
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default Profile;
