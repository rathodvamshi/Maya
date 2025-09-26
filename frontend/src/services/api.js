// frontend/src/services/api.js

import axios from 'axios';
import authService from './auth';

// Create a new Axios instance for authenticated API calls
const apiClient = axios.create({
  baseURL: 'http://localhost:8000', // Your backend base URL
  headers: {
    'Content-Type': 'application/json',
  },
});

// Use an interceptor to automatically add the auth token to every request
apiClient.interceptors.request.use(
  (config) => {
    const user = authService.getCurrentUser();
    if (user && user.access_token) {
      // The backend expects the token in the 'Authorization' header
      config.headers['Authorization'] = 'Bearer ' + user.access_token;
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

export default apiClient;
