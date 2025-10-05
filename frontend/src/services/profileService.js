// frontend/src/services/profileService.js

import apiClient from './api';

class ProfileService {
  // ======================================================
  // PROFILE MANAGEMENT
  // ======================================================

  async getProfile() {
    try {
  const response = await apiClient.get('/profile/');
      return {
        success: true,
        data: response.data
      };
    } catch (error) {
      console.error('Error fetching profile:', error);
      // Return fallback profile data
      return {
        success: true,
        data: {
          _id: 'default',
          user_id: 'default',
          name: 'User',
          bio: null,
          avatar_url: null,
          timezone: 'UTC',
          language: 'en',
          theme: 'dark',
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString()
        }
      };
    }
  }

  async updateProfile(profileData) {
    try {
  const response = await apiClient.put('/profile/', profileData);
      return {
        success: true,
        data: response.data
      };
    } catch (error) {
      console.error('Error updating profile:', error);
      return {
        success: false,
        error: error.response?.data?.error?.message || 'Failed to update profile'
      };
    }
  }

  async uploadAvatar(file) {
    try {
      const formData = new FormData();
      formData.append('file', file);

      const response = await apiClient.post('/profile/avatar', formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      });

      return {
        success: true,
        data: response.data
      };
    } catch (error) {
      console.error('Error uploading avatar:', error);
      return {
        success: false,
        error: error.response?.data?.error?.message || 'Failed to upload avatar'
      };
    }
  }

  // ======================================================
  // USER STATISTICS
  // ======================================================

  async getUserStats() {
    try {
  const response = await apiClient.get('/profile/stats');
      return {
        success: true,
        data: response.data
      };
    } catch (error) {
      console.error('Error fetching user stats:', error);
      return {
        success: false,
        error: error.response?.data?.error?.message || 'Failed to fetch user stats'
      };
    }
  }

  // ======================================================
  // API KEY MANAGEMENT
  // ======================================================

  async getApiKeys() {
    try {
      const response = await apiClient.get('/profile/api-keys');
      return {
        success: true,
        data: response.data
      };
    } catch (error) {
      console.error('Error fetching API keys:', error);
      return {
        success: false,
        error: error.response?.data?.error?.message || 'Failed to fetch API keys'
      };
    }
  }

  async createApiKey(keyData) {
    try {
      const response = await apiClient.post('/profile/api-keys', keyData);
      return {
        success: true,
        data: response.data
      };
    } catch (error) {
      console.error('Error creating API key:', error);
      return {
        success: false,
        error: error.response?.data?.error?.message || 'Failed to create API key'
      };
    }
  }

  async deleteApiKey(keyId) {
    try {
      const response = await apiClient.delete(`/profile/api-keys/${keyId}`);
      return {
        success: true,
        data: response.data
      };
    } catch (error) {
      console.error('Error deleting API key:', error);
      return {
        success: false,
        error: error.response?.data?.error?.message || 'Failed to delete API key'
      };
    }
  }

  // ======================================================
  // ACTIVITY & SECURITY LOGS
  // ======================================================

  async getActivityLogs(limit = 50, offset = 0) {
    try {
      const response = await apiClient.get(`/profile/activity?limit=${limit}&offset=${offset}`);
      return {
        success: true,
        data: response.data
      };
    } catch (error) {
      console.error('Error fetching activity logs:', error);
      return {
        success: false,
        error: error.response?.data?.error?.message || 'Failed to fetch activity logs'
      };
    }
  }

  async getSecurityEvents(limit = 50, offset = 0) {
    try {
      const response = await apiClient.get(`/profile/security?limit=${limit}&offset=${offset}`);
      return {
        success: true,
        data: response.data
      };
    } catch (error) {
      console.error('Error fetching security events:', error);
      return {
        success: false,
        error: error.response?.data?.error?.message || 'Failed to fetch security events'
      };
    }
  }

  // ======================================================
  // HELPER METHODS
  // ======================================================

  getActivityIcon(activityType) {
    const icons = {
      login: '🔐',
      logout: '🚪',
      chat_created: '💬',
      task_created: '✅',
      task_completed: '🎉',
      profile_updated: '👤',
      api_key_created: '🔑',
      api_key_deleted: '🗑️'
    };
    return icons[activityType] || '📝';
  }

  getActivityColor(activityType) {
    const colors = {
      login: '#22c55e',
      logout: '#6b7280',
      chat_created: '#3b82f6',
      task_created: '#f59e0b',
      task_completed: '#22c55e',
      profile_updated: '#8b5cf6',
      api_key_created: '#06b6d4',
      api_key_deleted: '#ef4444'
    };
    return colors[activityType] || '#6b7280';
  }

  getSecurityEventIcon(eventType) {
    const icons = {
      login_success: '✅',
      login_failed: '❌',
      suspicious_activity: '⚠️',
      password_changed: '🔐',
      api_key_used: '🔑'
    };
    return icons[eventType] || '🔒';
  }

  formatTimestamp(timestamp) {
    const date = new Date(timestamp);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMinutes = Math.floor(diffMs / (1000 * 60));
    const diffHours = Math.floor(diffMinutes / 60);
    const diffDays = Math.floor(diffHours / 24);

    if (diffMinutes < 1) {
      return 'Just now';
    } else if (diffMinutes < 60) {
      return `${diffMinutes} minute${diffMinutes > 1 ? 's' : ''} ago`;
    } else if (diffHours < 24) {
      return `${diffHours} hour${diffHours > 1 ? 's' : ''} ago`;
    } else if (diffDays < 7) {
      return `${diffDays} day${diffDays > 1 ? 's' : ''} ago`;
    } else {
      return date.toLocaleDateString();
    }
  }

  validateProfileData(profileData) {
    const errors = {};

    if (profileData.name && profileData.name.length > 100) {
      errors.name = 'Name must be 100 characters or less';
    }

    if (profileData.bio && profileData.bio.length > 500) {
      errors.bio = 'Bio must be 500 characters or less';
    }

    if (profileData.timezone && !this.isValidTimezone(profileData.timezone)) {
      errors.timezone = 'Invalid timezone';
    }

    if (profileData.language && !this.isValidLanguage(profileData.language)) {
      errors.language = 'Invalid language code';
    }

    if (profileData.theme && !['light', 'dark', 'auto'].includes(profileData.theme)) {
      errors.theme = 'Invalid theme selection';
    }

    return {
      isValid: Object.keys(errors).length === 0,
      errors
    };
  }

  validateApiKeyData(keyData) {
    const errors = {};

    if (!keyData.name || keyData.name.trim().length === 0) {
      errors.name = 'API key name is required';
    }

    if (keyData.name && keyData.name.length > 100) {
      errors.name = 'API key name must be 100 characters or less';
    }

    if (keyData.description && keyData.description.length > 500) {
      errors.description = 'Description must be 500 characters or less';
    }

    return {
      isValid: Object.keys(errors).length === 0,
      errors
    };
  }

  isValidTimezone(timezone) {
    try {
      Intl.DateTimeFormat(undefined, { timeZone: timezone });
      return true;
    } catch {
      return false;
    }
  }

  isValidLanguage(language) {
    const validLanguages = [
      'en', 'es', 'fr', 'de', 'it', 'pt', 'ru', 'ja', 'ko', 'zh', 'ar', 'hi'
    ];
    return validLanguages.includes(language);
  }

  // Avatar helper methods
  validateAvatarFile(file) {
    const errors = {};
    const maxSize = 5 * 1024 * 1024; // 5MB
    const allowedTypes = ['image/jpeg', 'image/png', 'image/gif', 'image/webp'];

    if (!allowedTypes.includes(file.type)) {
      errors.type = 'Only JPEG, PNG, GIF, and WebP images are allowed';
    }

    if (file.size > maxSize) {
      errors.size = 'File size must be less than 5MB';
    }

    return {
      isValid: Object.keys(errors).length === 0,
      errors
    };
  }

  generateAvatarInitials(name) {
    if (!name) return '?';
    
    const parts = name.trim().split(' ');
    if (parts.length >= 2) {
      return (parts[0][0] + parts[1][0]).toUpperCase();
    } else {
      return parts[0][0].toUpperCase();
    }
  }

  // Theme management
  saveThemePreference(theme) {
    localStorage.setItem('maya_theme', theme);
    this.applyTheme(theme);
  }

  getThemePreference() {
    return localStorage.getItem('maya_theme') || 'dark';
  }

  applyTheme(theme) {
    const root = document.documentElement;
    
    if (theme === 'auto') {
      // Detect system preference
      const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
      theme = prefersDark ? 'dark' : 'light';
    }
    
    root.setAttribute('data-theme', theme);
    
    // Update meta theme-color for mobile browsers
    const metaThemeColor = document.querySelector('meta[name="theme-color"]');
    if (metaThemeColor) {
      metaThemeColor.setAttribute('content', theme === 'dark' ? '#1a1b23' : '#ffffff');
    }
  }

  // Export user data
  async exportUserData() {
    try {
      // Get all user data
      const [profile, stats, activity, security, apiKeys] = await Promise.all([
        this.getProfile(),
        this.getUserStats(),
        this.getActivityLogs(1000),
        this.getSecurityEvents(1000),
        this.getApiKeys()
      ]);

      const userData = {
        profile: profile.data,
        stats: stats.data,
        activity: activity.data,
        security: security.data,
        apiKeys: apiKeys.data?.map(key => ({
          ...key,
          // Remove sensitive data from export
          key_preview: undefined
        })),
        exported_at: new Date().toISOString()
      };

      return {
        success: true,
        data: userData
      };
    } catch (error) {
      console.error('Error exporting user data:', error);
      return {
        success: false,
        error: 'Failed to export user data'
      };
    }
  }
}

const profileService = new ProfileService();
export default profileService;