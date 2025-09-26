import axios from 'axios';

// The base URL of our FastAPI backend.
const API_URL = 'http://localhost:8000/auth/';

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
    return axios.post(API_URL + 'register', {
      email,
      password,
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
    const formData = new URLSearchParams();
    formData.append('username', email);
    formData.append('password', password);

    return axios.post(API_URL + 'login', formData, {
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
      },
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