// frontend/src/services/sessionService.js

import apiClient from './api'; // Import the configured Axios instance

const sessionService = {
  /**
   * Fetches all chat sessions for the logged-in user.
   * @returns {Promise<AxiosResponse<any>>} A promise that resolves to the API response.
   */
  getSessions: () => {
  return apiClient.get('/sessions/');
  },

  /**
   * Fetches the full message history for a specific session.
   * @param {string} sessionId The ID of the session to fetch.
   * @returns {Promise<AxiosResponse<any>>} A promise containing the session details.
   */
  getSessionMessages: (sessionId, opts = {}) => {
  let limit = 50, offset = 0;
  let signal = undefined;
  if (typeof opts === 'number') {
    limit = opts;
  } else if (opts && typeof opts === 'object') {
    if (typeof opts.limit === 'number') limit = opts.limit;
    if (typeof opts.offset === 'number') offset = opts.offset;
    if (opts.signal) signal = opts.signal;
  }
  return apiClient
    .get(`/sessions/${sessionId}/history`, { params: { limit, offset }, ...(signal ? { signal } : {}) })
    .then((res) => {
      // Normalize to legacy shape expected by some components: { messages, totalMessages }
      try {
        const data = res?.data || {};
        const normalized = {
          messages: Array.isArray(data.messages) ? data.messages : [],
          totalMessages: typeof data.total === 'number' ? data.total : (data.totalMessages || 0),
          has_more: !!data.has_more,
          updatedAt: data.updatedAt || null,
          source: data.source || 'mongo',
        };
        return { ...res, data: normalized };
      } catch {
        return res;
      }
    });
  },

  /**
   * Creates a new chat session with the provided messages.
   * @param {Array<object>} messages The array of message objects to save.
   * @returns {Promise<AxiosResponse<any>>} A promise that resolves to the new session info.
   */
  createSession: (messages) => {
  return apiClient.post('/sessions/', messages);
  },

  /**
   * Creates a new empty session titled 'New Chat'.
   */
  createEmpty: () => {
  return apiClient.post('/sessions/new');
  },

  /**
   * Deletes a specific chat session.
   * @param {string} sessionId The ID of the session to delete.
   * @returns {Promise<AxiosResponse<any>>} A promise that resolves on successful deletion.
   */
  deleteSession: (sessionId) => {
  return apiClient.delete(`/sessions/${sessionId}`);
  },
};

export default sessionService;