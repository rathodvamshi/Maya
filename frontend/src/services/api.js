// frontend/src/services/api.js

import axios from 'axios';
import authService from './auth';

// Centralized Axios instance
// Convention: REACT_APP_API_URL should be the root server origin WITHOUT trailing slash or /api.
// We append '/api' here exactly once. This prevents accidental double '/api/api' when services also prefix.
// Backwards compatibility: if user already included '/api' we avoid duplicating it.
const RAW_BASE = (process.env.REACT_APP_API_URL || 'http://localhost:8000').replace(/\/$/, '');
const API_BASE = RAW_BASE.endsWith('/api') ? RAW_BASE : `${RAW_BASE}/api`;

const apiClient = axios.create({
  baseURL: API_BASE,
  headers: {
    'Content-Type': 'application/json',
  },
  withCredentials: false,
});

if (process.env.NODE_ENV === 'development') {
  // eslint-disable-next-line no-console
  console.log('[api] baseURL =', API_BASE);
}

// Inject Bearer token automatically
apiClient.interceptors.request.use(
  (config) => {
    const user = authService.getCurrentUser();
    if (user?.access_token) {
      config.headers.Authorization = `Bearer ${user.access_token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

export default apiClient;

// Global 401 handler to improve DX when tokens expire or are missing
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    const status = error?.response?.status;
    if (status === 401) {
      try {
        // If unauthorized, clear stale tokens so user can re-auth
        authService.logout?.();
        // Optionally, emit a global event for the app to show login
        if (typeof window !== 'undefined') {
          const evt = new CustomEvent('maya:auth:unauthorized');
          window.dispatchEvent(evt);
        }
      } catch {}
    }
    return Promise.reject(error);
  }
);
