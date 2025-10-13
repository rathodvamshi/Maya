import apiClient from './api';

// Uses centralized api client with baseURL like http://localhost:8000/api
// so these resolve to /api/auth/* on the backend (not the dev server origin).
export const sendOtp = (email) => apiClient.post('/auth/send-otp', { email });
export const verifyOtp = (email, otp) => apiClient.post('/auth/verify-otp', { email, otp });
export const completeRegistration = (payload) => apiClient.post('/auth/complete-registration', payload);
// Updated to use new backend endpoint
export const checkEmailAvailable = (email) => apiClient.get('/user/check-email', { params: { email } });
