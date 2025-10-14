// frontend/src/services/userService.js

import apiClient from './api';

const userService = {
  async getMe() {
    try {
      const response = await apiClient.get('/auth/me');
      return { success: true, data: response.data };
    } catch (error) {
      return { success: false, error: error?.response?.data?.detail || error?.message || 'Failed to fetch current user' };
    }
  },
  async updateMe(payload) {
    // payload can include { username, role, hobbies }
    try {
      const response = await apiClient.patch('/auth/me', payload);
      return { success: true, data: response.data };
    } catch (error) {
      return { success: false, error: error?.response?.data?.detail || error?.message || 'Failed to update user' };
    }
  },
  async deleteMe() {
    try {
      const response = await apiClient.delete('/user/me');
      return { success: true, data: response.data };
    } catch (error) {
      return { success: false, error: error?.response?.data?.detail || error?.message || 'Failed to delete account' };
    }
  }
};

export default userService;
