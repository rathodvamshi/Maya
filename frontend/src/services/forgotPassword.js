import apiClient from './api';

// Shared with signup endpoints
export const sendOtp = (email) => apiClient.post('/auth/send-otp', { email });
export const verifyOtp = (email, otp) => apiClient.post('/auth/verify-otp', { email, otp });
export const updatePassword = (email, password) => apiClient.post('/auth/update-password', { email, password });

export default { sendOtp, verifyOtp, updatePassword };
