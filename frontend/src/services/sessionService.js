// frontend/src/services/sessionService.js

import apiClient from './api'; // Import the configured Axios instance

const sessionService = {
  /**
   * Fetches all chat sessions for the logged-in user.
   * @returns {Promise<AxiosResponse<any>>} A promise that resolves to the API response.
   */
  getSessions: () => {
    return apiClient.get('/api/sessions/');
  },

  /**
   * Fetches the full message history for a specific session.
   * @param {string} sessionId The ID of the session to fetch.
   * @returns {Promise<AxiosResponse<any>>} A promise containing the session details.
   */
  getSessionMessages: (sessionId) => {
    return apiClient.get(`/api/sessions/${sessionId}`);
  },

  /**
   * Creates a new chat session with the provided messages.
   * @param {Array<object>} messages The array of message objects to save.
   * @returns {Promise<AxiosResponse<any>>} A promise that resolves to the new session info.
   */
  createSession: (messages) => {
    return apiClient.post('/api/sessions/', messages);
  },

  /**
   * Deletes a specific chat session.
   * @param {string} sessionId The ID of the session to delete.
   * @returns {Promise<AxiosResponse<any>>} A promise that resolves on successful deletion.
   */
  deleteSession: (sessionId) => {
    return apiClient.delete(`/api/sessions/${sessionId}`);
  },
};

export default sessionService;