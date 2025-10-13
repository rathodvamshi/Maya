import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Moon, Sun, Bell, Lock, Globe, Key } from 'lucide-react';
import '../styles/Settings.css';

const Settings = ({ onNavigate }) => {
  const navigate = useNavigate();
  const [theme, setTheme] = useState('light');
  const [notifications, setNotifications] = useState({
    email: true,
    push: false,
    taskReminders: true,
  });
  const [showPasswordModal, setShowPasswordModal] = useState(false);
  const [passwordData, setPasswordData] = useState({
    current: '',
    new: '',
    confirm: '',
  });

  const handleSavePassword = () => {
    setShowPasswordModal(false);
    setPasswordData({
      current: '',
      new: '',
      confirm: '',
    });
  };

  return (
    <div className="settings-page">
      <div className="settings-header">
        <button className="profile-back-btn" aria-label="Go back" onClick={() => navigate(-1)}>
          <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <path d="m12 19-7-7 7-7"></path>
            <path d="M19 12H5"></path>
          </svg>
          <span className="profile-back-text">Back</span>
        </button>
        <h1>Settings</h1>
      </div>

      <div className="settings-content">
        <div className="settings-section">
          <div className="section-title">
            <div className="title-icon">
              {theme === 'light' ? <Sun size={20} /> : <Moon size={20} />}
            </div>
            <h2>Appearance</h2>
          </div>

          <div className="setting-item">
            <div className="setting-info">
              <h3>Theme</h3>
              <p>Choose your preferred theme</p>
            </div>
            <div className="theme-toggle">
              <button
                className={theme === 'light' ? 'active' : ''}
                onClick={() => setTheme('light')}
              >
                <Sun size={18} />
                Light
              </button>
              <button
                className={theme === 'dark' ? 'active' : ''}
                onClick={() => setTheme('dark')}
              >
                <Moon size={18} />
                Dark
              </button>
            </div>
          </div>
        </div>

        <div className="settings-section">
          <div className="section-title">
            <div className="title-icon">
              <Bell size={20} />
            </div>
            <h2>Notifications</h2>
          </div>

          <div className="setting-item">
            <div className="setting-info">
              <h3>Email Notifications</h3>
              <p>Receive notifications via email</p>
            </div>
            <label className="toggle-switch">
              <input
                type="checkbox"
                checked={notifications.email}
                onChange={(e) =>
                  setNotifications({ ...notifications, email: e.target.checked })
                }
              />
              <span className="slider"></span>
            </label>
          </div>

          <div className="setting-item">
            <div className="setting-info">
              <h3>Push Notifications</h3>
              <p>Receive push notifications</p>
            </div>
            <label className="toggle-switch">
              <input
                type="checkbox"
                checked={notifications.push}
                onChange={(e) =>
                  setNotifications({ ...notifications, push: e.target.checked })
                }
              />
              <span className="slider"></span>
            </label>
          </div>

          <div className="setting-item">
            <div className="setting-info">
              <h3>Task Reminders</h3>
              <p>Get reminders for pending tasks</p>
            </div>
            <label className="toggle-switch">
              <input
                type="checkbox"
                checked={notifications.taskReminders}
                onChange={(e) =>
                  setNotifications({ ...notifications, taskReminders: e.target.checked })
                }
              />
              <span className="slider"></span>
            </label>
          </div>
        </div>

        <div className="settings-section">
          <div className="section-title">
            <div className="title-icon">
              <Lock size={20} />
            </div>
            <h2>Security</h2>
          </div>

          <div className="setting-item">
            <div className="setting-info">
              <h3>Change Password</h3>
              <p>Update your account password</p>
            </div>
            <button className="action-btn" onClick={() => setShowPasswordModal(true)}>
              Change
            </button>
          </div>
        </div>

        <div className="settings-section">
          <div className="section-title">
            <div className="title-icon">
              <Key size={20} />
            </div>
            <h2>API Keys</h2>
          </div>

          <div className="setting-item">
            <div className="setting-info">
              <h3>Manage API Keys</h3>
              <p>Add and manage your AI provider API keys</p>
            </div>
            <button
              className="action-btn"
              onClick={() => onNavigate?.('api-keys')}
            >
              Manage
            </button>
          </div>
        </div>

        <div className="settings-section">
          <div className="section-title">
            <div className="title-icon">
              <Globe size={20} />
            </div>
            <h2>General</h2>
          </div>

          <div className="setting-item">
            <div className="setting-info">
              <h3>Language</h3>
              <p>Select your preferred language</p>
            </div>
            <select className="select-input">
              <option value="en">English</option>
              <option value="es">Spanish</option>
              <option value="fr">French</option>
              <option value="de">German</option>
            </select>
          </div>
        </div>
      </div>

      {showPasswordModal && (
        <div className="modal-overlay" onClick={() => setShowPasswordModal(false)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <h3>Change Password</h3>

            <div className="form-group">
              <label>Current Password</label>
              <input
                type="password"
                placeholder="Enter current password"
                value={passwordData.current}
                onChange={(e) =>
                  setPasswordData({ ...passwordData, current: e.target.value })
                }
              />
            </div>

            <div className="form-group">
              <label>New Password</label>
              <input
                type="password"
                placeholder="Enter new password"
                value={passwordData.new}
                onChange={(e) =>
                  setPasswordData({ ...passwordData, new: e.target.value })
                }
              />
            </div>

            <div className="form-group">
              <label>Confirm New Password</label>
              <input
                type="password"
                placeholder="Confirm new password"
                value={passwordData.confirm}
                onChange={(e) =>
                  setPasswordData({ ...passwordData, confirm: e.target.value })
                }
              />
            </div>

            <div className="modal-actions">
              <button
                className="btn-secondary"
                onClick={() => setShowPasswordModal(false)}
              >
                Cancel
              </button>
              <button className="btn-primary" onClick={handleSavePassword}>
                Save Password
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default Settings;
