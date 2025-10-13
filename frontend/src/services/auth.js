import axios from 'axios';

// Resolve backend base from env; default to localhost, and prefer /api/auth endpoints.
// If the provided env already ends with /api, don't double-append.
const RAW_BASE = (process.env.REACT_APP_API_URL || 'http://localhost:8000').replace(/\/$/, '');
const API_BASE = RAW_BASE.endsWith('/api') ? RAW_BASE : `${RAW_BASE}/api`;
const API_AUTH = `${API_BASE}/auth/`;
// Legacy fallback (older backends expose /auth/* without /api prefix)
const LEGACY_AUTH = `${RAW_BASE}/auth/`;

/**
 * A service object for handling authentication-related API calls.
 */
const authService = {
  /**
   * Registers a new user.
   * @param {string} email - The user's email.
   * @param {string} password - The user's password.
   * @returns {Promise} - The Axios promise for the API call.
   */
  register(email, password) {
    // Prefer modern route
    return axios.post(API_AUTH + 'register', {
      email,
      password,
    }).catch(async (err) => {
      // Fallback to legacy path transparently
      try {
        return await axios.post(LEGACY_AUTH + 'register', { email, password });
      } catch (e) {
        throw err; // propagate original error if legacy also fails
      }
    });
  },

  /**
   * Logs in a user.
   * Note: FastAPI's OAuth2PasswordRequestForm expects form data, not JSON.
   * @param {string} email - The user's email (as 'username').
   * @param {string} password - The user's password.
   * @returns {Promise} - The Axios promise for the API call.
   */
  login(email, password) {
    const payload = { email, password };
    // Try modern route first
    const doPost = (base) => axios.post(base + 'login', payload, {
      headers: {
        'Content-Type': 'application/json',
      },
    });
    return doPost(API_AUTH).catch(async (err) => {
      try {
        // Fallback to legacy route
        return await doPost(LEGACY_AUTH);
      } catch (e) {
        throw err;
      }
    });
  },

  /**
   * Updates the user's profile.
   * @param {object} data - The profile data to update (e.g., { name, email }).
   * @returns {Promise} - The Axios promise for the API call.
   */
  updateProfile(data) {
    const user = JSON.parse(localStorage.getItem('user')) || {};
    const updatedUser = { ...user, ...data };
    localStorage.setItem('user', JSON.stringify(updatedUser));
    // Mock API call; replace with actual endpoint if available
    return Promise.resolve({ data: updatedUser });
  },

  /**
   * Stores the user's tokens in localStorage.
   * @param {object} tokens - The token object from the API response.
   */
  storeTokens(tokens) {
    localStorage.setItem('user', JSON.stringify(tokens));
  },

  /**
   * Retrieves the user's tokens from localStorage.
   * @returns {object | null} - The stored token object or null.
   */
  getCurrentUser() {
    return JSON.parse(localStorage.getItem('user'));
  },

  /**
   * Removes the user's tokens from localStorage.
   */
  logout() {
    localStorage.removeItem('user');
  },
};

export default authService;