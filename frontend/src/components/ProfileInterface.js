// Modern Profile Interface with Inline Editing and Security Features
import React, { useState, useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import '../styles/ProfileInterface.css';
import { 
  ArrowLeft, 
  Edit3, 
  Save, 
  X, 
  Copy, 
  Eye, 
  EyeOff, 
  Key, 
  Shield, 
  Activity, 
  Calendar, 
  MapPin, 
  Mail, 
  User, 
  Camera,
  Settings,
  Lock,
  Trash2,
  Plus,
  Check,
  AlertTriangle
} from 'lucide-react';
import authService from '../services/auth';
import profileService from '../services/profileService';

const ProfileInterface = () => {
  // ========================
  // State Management
  // ========================
  const [user, setUser] = useState(null);
  const [editingField, setEditingField] = useState(null);
  const [editValues, setEditValues] = useState({});
  const [apiKeys, setApiKeys] = useState([]);
  const [showNewKeyForm, setShowNewKeyForm] = useState(false);
  const [newKeyLabel, setNewKeyLabel] = useState('');
  const [generatedKey, setGeneratedKey] = useState(null);
  const [securityLog, setSecurityLog] = useState([]);
  const [activityData, setActivityData] = useState([]);
  const [stats, setStats] = useState({});
  const [showKeyValue, setShowKeyValue] = useState({});
  const [reducedMotion, setReducedMotion] = useState(false);
  const [isLoading, setIsLoading] = useState(true);

  // ========================
  // Refs
  // ========================
  const fileInputRef = useRef(null);
  const editInputRefs = useRef({});

  // ========================
  // Effects
  // ========================
  useEffect(() => {
    loadUserData();
    loadApiKeys();
    loadSecurityLog();
    loadActivityData();
    loadStats();

    // Check reduced motion preference
    const hasReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches ||
                            localStorage.getItem('maya-reduced-motion') === 'true';
    setReducedMotion(hasReducedMotion);
  }, []);

  // Focus on edit input when editing starts
  useEffect(() => {
    if (editingField && editInputRefs.current[editingField]) {
      editInputRefs.current[editingField].focus();
    }
  }, [editingField]);

  // ========================
  // Data Loading
  // ========================
  const loadUserData = async () => {
    try {
      setIsLoading(true);
      const result = await profileService.getProfile();
      
      if (result.success) {
        const userData = result.data;
        setUser(userData);
        setEditValues({
          name: userData.name || '',
          email: userData.email || '',
          role: userData.role || '',
          location: userData.location || '',
          bio: userData.bio || ''
        });
      } else {
        console.error('Failed to load profile:', result.error);
        // Show error notification
        if (window.addNotification) {
          window.addNotification({
            type: 'error',
            title: 'Failed to Load Profile',
            message: result.error || 'Unable to fetch profile data'
          });
        }
      }
    } catch (error) {
      console.error('Error loading user data:', error);
      if (window.addNotification) {
        window.addNotification({
          type: 'error',
          title: 'Network Error',
          message: 'Unable to connect to server'
        });
      }
    } finally {
      setIsLoading(false);
    }
  };

  const loadApiKeys = async () => {
    try {
      const result = await profileService.getApiKeys();
      
      if (result.success) {
        setApiKeys(result.data);
      } else {
        console.error('Failed to load API keys:', result.error);
        if (window.addNotification) {
          window.addNotification({
            type: 'error',
            title: 'Failed to Load API Keys',
            message: result.error || 'Unable to fetch API keys'
          });
        }
      }
    } catch (error) {
      console.error('Error loading API keys:', error);
      if (window.addNotification) {
        window.addNotification({
          type: 'error',
          title: 'Network Error',
          message: 'Unable to load API keys'
        });
      }
    }
  };

  const loadSecurityLog = async () => {
    try {
      const result = await profileService.getSecurityEvents();
      
      if (result.success) {
        setSecurityLog(result.data);
      } else {
        console.error('Failed to load security log:', result.error);
        if (window.addNotification) {
          window.addNotification({
            type: 'error',
            title: 'Failed to Load Security Log',
            message: result.error || 'Unable to fetch security events'
          });
        }
      }
    } catch (error) {
      console.error('Error loading security log:', error);
      if (window.addNotification) {
        window.addNotification({
          type: 'error',
          title: 'Network Error',
          message: 'Unable to load security log'
        });
      }
    }
  };

  const loadActivityData = async () => {
    try {
      const result = await profileService.getActivityLog();
      
      if (result.success) {
        setActivityData(result.data);
      } else {
        console.error('Failed to load activity data:', result.error);
        if (window.addNotification) {
          window.addNotification({
            type: 'error',
            title: 'Failed to Load Activity Data',
            message: result.error || 'Unable to fetch activity data'
          });
        }
      }
    } catch (error) {
      console.error('Error loading activity data:', error);
      if (window.addNotification) {
        window.addNotification({
          type: 'error',
          title: 'Network Error',
          message: 'Unable to load activity data'
        });
      }
    }
  };

  const loadStats = async () => {
    try {
      const result = await profileService.getStats();
      
      if (result.success) {
        setStats(result.data);
      } else {
        console.error('Failed to load stats:', result.error);
        if (window.addNotification) {
          window.addNotification({
            type: 'error',
            title: 'Failed to Load Statistics',
            message: result.error || 'Unable to fetch statistics'
          });
        }
      }
    } catch (error) {
      console.error('Error loading stats:', error);
      if (window.addNotification) {
        window.addNotification({
          type: 'error',
          title: 'Network Error',
          message: 'Unable to load statistics'
        });
      }
    }
  };

  // ========================
  // Handlers
  // ========================
  const handleEditStart = (field) => {
    setEditingField(field);
  };

  const handleEditSave = async (field) => {
    try {
      const updateData = { [field]: editValues[field] };
      const result = await profileService.updateProfile(updateData);
      
      if (result.success) {
        // Update local user data
        const updatedUser = { ...user, [field]: editValues[field] };
        setUser(updatedUser);
        setEditingField(null);
        
        if (window.addNotification) {
          window.addNotification({
            type: 'success',
            title: 'Profile Updated',
            message: `${field} updated successfully`
          });
        }
      } else {
        console.error('Failed to update profile:', result.error);
        if (window.addNotification) {
          window.addNotification({
            type: 'error',
            title: 'Update Failed',
            message: result.error || 'Unable to update profile'
          });
        }
      }
    } catch (error) {
      console.error('Error saving profile:', error);
      if (window.addNotification) {
        window.addNotification({
          type: 'error',
          title: 'Network Error',
          message: 'Unable to save changes'
        });
      }
    }
  };

  const handleEditCancel = (field) => {
    setEditValues(prev => ({ ...prev, [field]: user[field] }));
    setEditingField(null);
  };

  const handleAvatarChange = (event) => {
    const file = event.target.files[0];
    if (file) {
      const reader = new FileReader();
      reader.onload = (e) => {
        setUser(prev => ({ ...prev, avatar: e.target.result }));
        // Here you would upload the file to your server
      };
      reader.readAsDataURL(file);
    }
  };

  const handleGenerateApiKey = async () => {
    if (!newKeyLabel.trim()) return;

    try {
      const result = await profileService.createApiKey({
        label: newKeyLabel.trim()
      });

      if (result.success) {
        const newKey = result.data;
        await loadApiKeys(); // Reload API keys list
        setGeneratedKey(newKey.key);
        setNewKeyLabel('');
        setShowNewKeyForm(false);

        // Show the key once
        setShowKeyValue(prev => ({ ...prev, [newKey._id]: true }));
        
        // Hide after 30 seconds for security
        setTimeout(() => {
          setShowKeyValue(prev => ({ ...prev, [newKey._id]: false }));
        }, 30000);

        if (window.addNotification) {
          window.addNotification({
            type: 'success',
            title: 'API Key Created',
            message: 'New API key generated successfully'
          });
        }
      } else {
        console.error('Failed to create API key:', result.error);
        if (window.addNotification) {
          window.addNotification({
            type: 'error',
            title: 'Failed to Create API Key',
            message: result.error || 'Unable to generate API key'
          });
        }
      }
    } catch (error) {
      console.error('Error generating API key:', error);
      if (window.addNotification) {
        window.addNotification({
          type: 'error',
          title: 'Network Error',
          message: 'Unable to create API key'
        });
      }
    }
  };

  const handleRevokeApiKey = async (keyId) => {
    if (window.confirm('Are you sure you want to revoke this API key? This action cannot be undone.')) {
      try {
        const result = await profileService.deleteApiKey(keyId);
        
        if (result.success) {
          await loadApiKeys(); // Reload API keys list
          if (window.addNotification) {
            window.addNotification({
              type: 'success',
              title: 'API Key Revoked',
              message: 'API key has been revoked successfully'
            });
          }
        } else {
          console.error('Failed to revoke API key:', result.error);
          if (window.addNotification) {
            window.addNotification({
              type: 'error',
              title: 'Failed to Revoke API Key',
              message: result.error || 'Unable to revoke API key'
            });
          }
        }
      } catch (error) {
        console.error('Error revoking API key:', error);
        if (window.addNotification) {
          window.addNotification({
            type: 'error',
            title: 'Network Error',
            message: 'Unable to revoke API key'
          });
        }
      }
    }
  };

  const copyToClipboard = (text) => {
    navigator.clipboard.writeText(text);
    console.log('Copied to clipboard');
  };

  const toggleKeyVisibility = (keyId) => {
    setShowKeyValue(prev => ({ ...prev, [keyId]: !prev[keyId] }));
  };

  // ========================
  // Render Components
  // ========================
  const renderEditableField = (field, label, value, type = 'text', multiline = false) => {
    const isEditing = editingField === field;

    return (
      <div className="profile-field">
        <label className="field-label">{label}</label>
        
        {isEditing ? (
          <div className="field-edit-container">
            {multiline ? (
              <textarea
                ref={el => editInputRefs.current[field] = el}
                value={editValues[field] || ''}
                onChange={(e) => setEditValues(prev => ({ ...prev, [field]: e.target.value }))}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    handleEditSave(field);
                  } else if (e.key === 'Escape') {
                    handleEditCancel(field);
                  }
                }}
                rows={3}
                className="field-input"
              />
            ) : (
              <input
                ref={el => editInputRefs.current[field] = el}
                type={type}
                value={editValues[field] || ''}
                onChange={(e) => setEditValues(prev => ({ ...prev, [field]: e.target.value }))}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') {
                    handleEditSave(field);
                  } else if (e.key === 'Escape') {
                    handleEditCancel(field);
                  }
                }}
                className="field-input"
              />
            )}
            
            <div className="field-actions">
              <button
                className="field-action-button save"
                onClick={() => handleEditSave(field)}
                title="Save (Enter)"
              >
                <Save size={14} />
              </button>
              <button
                className="field-action-button cancel"
                onClick={() => handleEditCancel(field)}
                title="Cancel (Esc)"
              >
                <X size={14} />
              </button>
            </div>
          </div>
        ) : (
          <div className="field-display-container">
            <span className="field-value">{value || 'Not set'}</span>
            <button
              className="field-edit-button"
              onClick={() => handleEditStart(field)}
              title={`Edit ${label.toLowerCase()}`}
            >
              <Edit3 size={14} />
            </button>
          </div>
        )}
      </div>
    );
  };

  const renderStatsCard = (title, value, subtitle, icon) => (
    <motion.div
      className="stats-card"
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: reducedMotion ? 0 : 0.3 }}
    >
      <div className="stats-icon">{icon}</div>
      <div className="stats-content">
        <div className="stats-value">{value}</div>
        <div className="stats-title">{title}</div>
        {subtitle && <div className="stats-subtitle">{subtitle}</div>}
      </div>
    </motion.div>
  );

  // ========================
  // Main Render
  // ========================
  if (isLoading) {
    return (
      <div className="profile-loading">
        <div className="loading-spinner" />
        <span>Loading profile...</span>
      </div>
    );
  }

  return (
    <div className="profile-interface">
      {/* Header */}
      <div className="profile-header">
        <button className="back-button" onClick={() => window.history.back()}>
          <ArrowLeft size={20} />
          <span>Back</span>
        </button>
        <h1>Profile</h1>
      </div>

      <div className="profile-content">
        {/* Profile Card */}
        <motion.div
          className="profile-card"
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: reducedMotion ? 0 : 0.4 }}
        >
          <div className="profile-avatar-section">
            <div className="avatar-container">
              {user.avatar ? (
                <img src={user.avatar} alt={user.name} className="profile-avatar" />
              ) : (
                <div className="profile-avatar-placeholder">
                  {user.name?.split(' ').map(n => n[0]).join('') || 'U'}
                </div>
              )}
              <button
                className="avatar-edit-button"
                onClick={() => fileInputRef.current?.click()}
                title="Change avatar"
              >
                <Camera size={16} />
              </button>
              <input
                ref={fileInputRef}
                type="file"
                accept="image/*"
                onChange={handleAvatarChange}
                style={{ display: 'none' }}
              />
            </div>
            
            <div className="profile-basic-info">
              <h2>{user.name}</h2>
              <p className="profile-email">{user.email}</p>
              <p className="profile-joined">
                Member since {new Date(user.joinedDate).toLocaleDateString()}
              </p>
            </div>
          </div>

          {/* Editable Fields */}
          <div className="profile-fields">
            {renderEditableField('name', 'Full Name', user.name)}
            {renderEditableField('email', 'Email Address', user.email, 'email')}
            {renderEditableField('role', 'Role', user.role)}
            {renderEditableField('location', 'Location', user.location)}
            {renderEditableField('bio', 'Bio', user.bio, 'text', true)}
          </div>
        </motion.div>

        {/* Stats */}
        <motion.div
          className="profile-stats"
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: reducedMotion ? 0 : 0.4, delay: 0.1 }}
        >
          <h3>Statistics</h3>
          <div className="stats-grid">
            {renderStatsCard(
              'Total Chats',
              stats.totalChats,
              'AI conversations',
              <Activity size={20} />
            )}
            {renderStatsCard(
              'Tasks Completed',
              `${stats.completedTasks}/${stats.totalTasks}`,
              `${Math.round((stats.completedTasks / stats.totalTasks) * 100)}% completion rate`,
              <Check size={20} />
            )}
            {renderStatsCard(
              'Active Streak',
              `${stats.streakDays} days`,
              'Keep it up!',
              <Calendar size={20} />
            )}
            {renderStatsCard(
              'Last Active',
              stats.lastActiveTime,
              `Avg session: ${stats.averageSessionLength}`,
              <Activity size={20} />
            )}
          </div>
        </motion.div>

        {/* API Keys Management */}
        <motion.div
          className="api-keys-section"
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: reducedMotion ? 0 : 0.4, delay: 0.2 }}
        >
          <div className="section-header">
            <h3>API Keys</h3>
            <button
              className="add-key-button"
              onClick={() => setShowNewKeyForm(true)}
            >
              <Plus size={16} />
              <span>Generate New Key</span>
            </button>
          </div>

          {/* New Key Form */}
          <AnimatePresence>
            {showNewKeyForm && (
              <motion.div
                className="new-key-form"
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: 'auto' }}
                exit={{ opacity: 0, height: 0 }}
                transition={{ duration: reducedMotion ? 0 : 0.3 }}
              >
                <input
                  type="text"
                  placeholder="Key label (e.g., 'Production API')"
                  value={newKeyLabel}
                  onChange={(e) => setNewKeyLabel(e.target.value)}
                  onKeyPress={(e) => e.key === 'Enter' && handleGenerateApiKey()}
                />
                <div className="form-actions">
                  <button onClick={handleGenerateApiKey} disabled={!newKeyLabel.trim()}>
                    Generate
                  </button>
                  <button onClick={() => setShowNewKeyForm(false)}>
                    Cancel
                  </button>
                </div>
              </motion.div>
            )}
          </AnimatePresence>

          {/* Generated Key Alert */}
          <AnimatePresence>
            {generatedKey && (
              <motion.div
                className="generated-key-alert"
                initial={{ opacity: 0, y: -10 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -10 }}
                transition={{ duration: reducedMotion ? 0 : 0.3 }}
              >
                <AlertTriangle size={16} />
                <div>
                  <strong>Important:</strong> This is the only time you'll see this key. 
                  Make sure to copy it now.
                </div>
                <button onClick={() => setGeneratedKey(null)}>
                  <X size={16} />
                </button>
              </motion.div>
            )}
          </AnimatePresence>

          {/* API Keys List */}
          <div className="api-keys-list">
            {apiKeys.map((apiKey) => (
              <motion.div
                key={apiKey._id}
                className="api-key-item"
                initial={{ opacity: 0, x: -20 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -20 }}
                transition={{ duration: reducedMotion ? 0 : 0.2 }}
              >
                <div className="key-info">
                  <div className="key-label">{apiKey.label}</div>
                  <div className="key-details">
                    <span>Created: {apiKey.created}</span>
                    {apiKey.lastUsed && (
                      <span>Last used: {apiKey.lastUsed}</span>
                    )}
                  </div>
                </div>

                <div className="key-value">
                  {showKeyValue[apiKey._id] ? (
                    <code className="key-display">{apiKey.key}</code>
                  ) : (
                    <code className="key-display">
                      {apiKey.key.substring(0, 8)}{'*'.repeat(20)}{apiKey.key.substring(-4)}
                    </code>
                  )}
                </div>

                <div className="key-actions">
                  <button
                    onClick={() => toggleKeyVisibility(apiKey._id)}
                    title={showKeyValue[apiKey._id] ? 'Hide key' : 'Show key'}
                  >
                    {showKeyValue[apiKey._id] ? <EyeOff size={16} /> : <Eye size={16} />}
                  </button>
                  <button
                    onClick={() => copyToClipboard(apiKey.key)}
                    title="Copy key"
                  >
                    <Copy size={16} />
                  </button>
                  <button
                    onClick={() => handleRevokeApiKey(apiKey._id)}
                    className="danger"
                    title="Revoke key"
                  >
                    <Trash2 size={16} />
                  </button>
                </div>
              </motion.div>
            ))}

            {apiKeys.length === 0 && (
              <div className="empty-state">
                <Key size={32} />
                <p>No API keys generated yet</p>
                <span>Generate your first API key to get started</span>
              </div>
            )}
          </div>
        </motion.div>

        {/* Recent Activity */}
        <motion.div
          className="activity-section"
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: reducedMotion ? 0 : 0.4, delay: 0.3 }}
        >
          <h3>Recent Activity</h3>
          <div className="activity-list">
            {activityData.slice(0, 5).map((activity) => (
              <div key={activity._id} className="activity-item">
                <div className="activity-icon">
                  <Activity size={16} />
                </div>
                <div className="activity-content">
                  <div className="activity-description">{activity.description}</div>
                  <div className="activity-timestamp">
                    {activity.timestamp.toLocaleString()}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </motion.div>

        {/* Security Log */}
        <motion.div
          className="security-section"
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: reducedMotion ? 0 : 0.4, delay: 0.4 }}
        >
          <h3>Security Log</h3>
          <div className="security-list">
            {securityLog.slice(0, 10).map((entry) => (
              <div 
                key={entry._id} 
                className={`security-item ${entry.status}`}
              >
                <div className="security-icon">
                  {entry.status === 'success' ? (
                    <Shield size={16} />
                  ) : (
                    <AlertTriangle size={16} />
                  )}
                </div>
                <div className="security-content">
                  <div className="security-event">{entry.event}</div>
                  <div className="security-details">
                    <span>{entry.timestamp.toLocaleString()}</span>
                    <span>{entry.ip}</span>
                    <span>{entry.location}</span>
                    <span>{entry.device}</span>
                  </div>
                </div>
                <div className={`security-status ${entry.status}`}>
                  {entry.status}
                </div>
              </div>
            ))}
          </div>
        </motion.div>
      </div>
    </div>
  );
};

export default ProfileInterface;