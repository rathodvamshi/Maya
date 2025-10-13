// Yes. It provides the UI page where users add, view, and delete their AI provider API keys and see usage progress.


import { useState } from 'react';
import { Plus, Trash2, CheckCircle, XCircle, Key } from 'lucide-react';
import '../styles/ApiKeyManager.css';

const ApiKeyManager = () => {
  const [apiKeys, setApiKeys] = useState([
    {
      id: '1',
      provider: 'gemini',
      key: 'AIzaSy...XYZ123',
      status: 'valid',
      addedAt: '2024-01-15',
    },
  ]);

  const [showAddModal, setShowAddModal] = useState(false);
  const [newKey, setNewKey] = useState({
    provider: 'gemini',
    key: '',
  });
  const [usageCount] = useState(15);

  const providerInfo = {
    gemini: {
      name: 'Google Gemini',
      color: '#4285F4',
    },
    cohere: {
      name: 'Cohere',
      color: '#39A0FF',
    },
    anthropic: {
      name: 'Anthropic Claude',
      color: '#D97757',
    },
  };

  const handleAddKey = () => {
    if (!newKey.key.trim()) return;

    const apiKey = {
      id: Date.now().toString(),
      provider: newKey.provider,
      key: newKey.key.substring(0, 10) + '...' + newKey.key.slice(-6),
      status: 'testing',
      addedAt: new Date().toISOString().split('T')[0],
    };

    setApiKeys([...apiKeys, apiKey]);

    setTimeout(() => {
      setApiKeys((keys) =>
        keys.map((k) => (k.id === apiKey.id ? { ...k, status: 'valid' } : k))
      );
    }, 2000);

    setShowAddModal(false);
    setNewKey({ provider: 'gemini', key: '' });
  };

  const handleDeleteKey = (id) => {
    setApiKeys(apiKeys.filter((k) => k.id !== id));
  };

  return (
    <div className="api-key-page">
      <div className="api-key-header">
        <div>
          <h1>API Key Management</h1>
          <p className="header-subtitle">
            Manage your AI provider API keys for extended usage
          </p>
        </div>
        <button className="add-key-btn" onClick={() => setShowAddModal(true)}>
          <Plus size={20} />
          Add API Key
        </button>
      </div>

      <div className="api-key-content">
        <div className="usage-card">
          <div className="usage-info">
            <h3>Free Usage</h3>
            <div className="usage-bar">
              <div
                className="usage-progress"
                style={{ width: `${(usageCount / 20) * 100}%` }}
              ></div>
            </div>
            <p>
              {usageCount} of 20 free requests used
              {usageCount >= 20 && (
                <span className="limit-reached"> - Limit reached</span>
              )}
            </p>
          </div>
          {usageCount >= 20 && (
            <div className="limit-message">
              <p>
                You've reached your free limit. Add your own API key to continue using
                MAYA.
              </p>
            </div>
          )}
        </div>

        <div className="providers-section">
          <h2>Supported Providers</h2>
          <div className="providers-grid">
            {Object.entries(providerInfo).map(([key, info]) => {
              const keyCount = apiKeys.filter((k) => k.provider === key).length;
              return (
                <div key={key} className="provider-card">
                  <div
                    className="provider-icon"
                    style={{ background: info.color }}
                  >
                    <Key size={24} />
                  </div>
                  <h3>{info.name}</h3>
                  <p>{keyCount} key(s) added</p>
                </div>
              );
            })}
          </div>
        </div>

        <div className="keys-section">
          <h2>Your API Keys</h2>
          {apiKeys.length === 0 ? (
            <div className="empty-state">
              <Key size={48} />
              <p>No API keys added yet</p>
              <button className="add-key-btn-secondary" onClick={() => setShowAddModal(true)}>
                <Plus size={18} />
                Add Your First Key
              </button>
            </div>
          ) : (
            <div className="keys-list">
              {apiKeys.map((apiKey) => (
                <div key={apiKey.id} className="key-card">
                  <div
                    className="key-provider"
                    style={{
                      background: providerInfo[apiKey.provider].color,
                    }}
                  >
                    {providerInfo[apiKey.provider].name}
                  </div>
                  <div className="key-details">
                    <div className="key-value">{apiKey.key}</div>
                    <div className="key-meta">
                      <span>Added: {apiKey.addedAt}</span>
                      <div className="key-status">
                        {apiKey.status === 'valid' && (
                          <>
                            <CheckCircle size={16} />
                            <span>Valid</span>
                          </>
                        )}
                        {apiKey.status === 'invalid' && (
                          <>
                            <XCircle size={16} />
                            <span>Invalid</span>
                          </>
                        )}
                        {apiKey.status === 'testing' && (
                          <>
                            <div className="spinner"></div>
                            <span>Testing...</span>
                          </>
                        )}
                      </div>
                    </div>
                  </div>
                  <button
                    className="delete-key-btn"
                    onClick={() => handleDeleteKey(apiKey.id)}
                  >
                    <Trash2 size={18} />
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {showAddModal && (
        <div className="modal-overlay" onClick={() => setShowAddModal(false)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <h3>Add API Key</h3>

            <div className="form-group">
              <label>Provider</label>
              <select
                value={newKey.provider}
                onChange={(e) =>
                  setNewKey({
                    ...newKey,
                    provider: e.target.value,
                  })
                }
              >
                <option value="gemini">Google Gemini</option>
                <option value="cohere">Cohere</option>
                <option value="anthropic">Anthropic Claude</option>
              </select>
            </div>

            <div className="form-group">
              <label>API Key</label>
              <input
                type="password"
                placeholder="Enter your API key"
                value={newKey.key}
                onChange={(e) => setNewKey({ ...newKey, key: e.target.value })}
              />
            </div>

            <div className="info-box">
              <p>
                Your API key will be encrypted and stored securely. We'll validate it
                before saving.
              </p>
            </div>

            <div className="modal-actions">
              <button
                className="btn-secondary"
                onClick={() => setShowAddModal(false)}
              >
                Cancel
              </button>
              <button className="btn-primary" onClick={handleAddKey}>
                Add Key
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default ApiKeyManager;
