// frontend/src/services/chatService.js

import apiClient from './api';

/**
 * chatService
 * ------------
 * Handles all chat-related API interactions:
 * - Starting new sessions
 * - Sending messages
 * - Retrieving chat history
 * - Task management (create, update, complete)
 */
const chatService = {
  /**
   * Starts a brand new chat session.
   * @param {string} firstMessage - The user's first message in the new session.
   * @returns {Promise<AxiosResponse>} Resolves with { session_id, response_text }.
   */
  startNewChat(firstMessage) {
    // Try primary chat route; on 404 or 5xx, fallback to sessions flow without duplicating the user message
    return apiClient.post('/chat/new', { message: firstMessage }).catch(async (err) => {
      const status = err?.response?.status;
      if (status === 404 || (typeof status === 'number' && status >= 500)) {
        try {
          // Create an empty session first to avoid double-saving the initial user message
          const createRes = await apiClient.post('/sessions/new');
          const sid = createRes?.data?.id || createRes?.data?.session_id || createRes?.data?._id;
          if (!sid) throw err;
          try {
            // Ask backend to generate a reply via sessions chat endpoint
            const chatRes = await apiClient.post(`/sessions/${sid}/chat`, { message: firstMessage });
            const reply = chatRes?.data?.response_text || chatRes?.data?.text || chatRes?.data?.message || '';
            return { data: { session_id: sid, response_text: reply } };
          } catch (inner) {
            // Best-effort cleanup to prevent orphan empty sessions
            try { await apiClient.delete(`/sessions/${sid}`); } catch {}
            throw inner;
          }
        } catch (e) {
          throw err;
        }
      }
      throw err;
    });
  },

  /**
   * Sends a message to an existing chat session.
   * @param {string} sessionId - ID of the chat session to continue.
   * @param {string} message - The user's message.
   * @returns {Promise<AxiosResponse>} Resolves with { response_text, video?, video_intent? } from AI.
   */
  sendMessage(sessionId, message) {
    if (sessionId) {
      // Continue existing session (correct endpoint)
      return apiClient.post(`/chat/${sessionId}/continue`, { message }).catch(async (err) => {
        const status = err?.response?.status;
        // Fallback to sessions chat endpoint on 404 (not found) or 5xx (server-side issues)
        if (status === 404 || (typeof status === 'number' && status >= 500)) {
          // Fallback to sessions chat endpoint
          const res = await apiClient.post(`/sessions/${sessionId}/chat`, { message });
          // Normalize to { response_text }
          const reply = res?.data?.response_text || res?.data?.text || res?.data?.message || '';
          return { data: { response_text: reply } };
        }
        throw err;
      });
    }
    // No generic root chat route; start a new session instead
    return apiClient.post('/chat/new', { message });
  },

  /**
   * Retrieves the latest chat history for the current user.
   * @returns {Promise<AxiosResponse>} Resolves with an array of messages.
   */
  getHistory() {
  return apiClient.get('/chat/history');
  },

  /**
   * Clears all chat history for the current user.
   * @returns {Promise<AxiosResponse>} Resolves with a status message.
   */
  clearHistory() {
  return apiClient.delete('/chat/history/clear');
  },

  /**
   * Fetches all chat sessions for the current user.
   * @returns {Promise<AxiosResponse>} Resolves with an array of chat sessions.
   */
  getSessions() {
    return apiClient.get('/sessions/');
  },

  /**
   * Deletes a specific chat session.
   * @param {string} sessionId - The ID of the session to delete.
   * @returns {Promise<AxiosResponse>} Resolves with deletion status.
   */
  deleteSession(sessionId) {
    return apiClient.delete(`/sessions/${sessionId}`);
  },

  /**
   * Updates the title of a specific chat session.
   * @param {string} sessionId - The ID of the session to update.
   * @param {string} title - The new title for the session.
   * @returns {Promise<AxiosResponse>} Resolves with update status.
   */
  updateSessionTitle(sessionId, title) {
    return apiClient.put(`/sessions/${sessionId}/title`, { title });
  },

  /**
   * Pins or unpins a session.
   * @param {string} sessionId
   * @param {boolean} pinned - Desired pinned state
   */
  setSessionPinned(sessionId, pinned) {
    return apiClient.put(`/sessions/${sessionId}/pin`, { pinned });
  },

  /**
   * Marks a session as saved (or unsaved) so user can keep important chats.
   * @param {string} sessionId
   * @param {boolean} saved - Desired saved state
   */
  setSessionSaved(sessionId, saved) {
    return apiClient.put(`/sessions/${sessionId}/save`, { saved });
  },

  /**
   * Calls the resilient multi-provider orchestrator and returns a unified JSON.
   * @param {string} prompt
   * @returns {Promise<AxiosResponse<{response?: string, provider_used?: string, error?: string}>>}
   */
  generateJSON(prompt) {
    return apiClient.post('/chat/generate-json', { prompt });
  },

  /**
   * Retrieves the complete message history for a specific session.
   * @param {string} sessionId - The ID of the session to get history for.
   * @param {number} limit - Maximum number of messages to retrieve (optional).
   * @param {number} offset - Number of messages to skip for pagination (optional).
   * @returns {Promise<AxiosResponse>} Resolves with session message history.
   */
  getSessionHistory(sessionId, limitOrOptions = 30, offset = 0) {
    // Support both (id, limit, offset) and (id, { limit, offset, before })
    let limit = 30;
    if (typeof limitOrOptions === 'number') {
      limit = limitOrOptions;
    } else if (limitOrOptions && typeof limitOrOptions === 'object') {
      if (typeof limitOrOptions.limit === 'number') limit = limitOrOptions.limit;
      if (typeof limitOrOptions.offset === 'number') offset = limitOrOptions.offset;
      // 'before' is not supported server-side; could be mapped in future
    }

    const params = new URLSearchParams();
    if (limit) params.append('limit', limit.toString());
    if (offset) params.append('offset', offset.toString());

    const queryString = params.toString();
    const url = `/sessions/${sessionId}/history${queryString ? `?${queryString}` : ''}`;

    return apiClient.get(url);
  },

  /**
   * Generates an automatic title for a session based on its content.
   * @param {string} sessionId - The ID of the session to generate title for.
   * @returns {Promise<AxiosResponse>} Resolves with generated title.
   */
  generateSessionTitle(sessionId) {
    return apiClient.post(`/sessions/${sessionId}/generate-title`);
  },

  // ----------------------------
  // Task Management
  // ----------------------------

  /**
   * Fetches all pending tasks for the current user.
   * @returns {Promise<AxiosResponse>} Resolves with an array of tasks.
   */
  getTasks() {
  return apiClient.get('/chat/tasks');
  },

  /**
   * Fetches recently completed tasks for the current user.
   * @returns {Promise<AxiosResponse>} Resolves with an array of tasks.
   */
  getTaskHistory() {
  return apiClient.get('/chat/tasks/history');
  },

  /**
   * Creates a new task.
   * @param {string} content - The task content.
   * @param {string} dueDate - Task due date in 'YYYY-MM-DD HH:mm' format.
   * @returns {Promise<AxiosResponse>} Resolves with created task ID.
   */
  createTask(content, dueDate) {
  return apiClient.post('/chat/tasks', { content, due_date: dueDate });
  },

  /**
   * Updates an existing task with new content or due date.
   * @param {string} taskId - The ID of the task to update.
   * @param {object} taskData - Fields to update, e.g., { content, due_date }.
   * @returns {Promise<AxiosResponse>} Resolves with status of update.
   */
  updateTask(taskId, taskData) {
  return apiClient.put(`/chat/tasks/${taskId}`, taskData);
  },

  /**
   * Marks a specific task as done.
   * @param {string} taskId - The ID of the task to mark complete.
   * @returns {Promise<AxiosResponse>} Resolves with status of completion.
   */
  markTaskAsDone(taskId) {
  return apiClient.put(`/chat/tasks/${taskId}/done`);
  },

  // ----------------------------
  // Feedback Management
  // ----------------------------

  /**
   * Submits feedback for a specific message.
   * @param {string} sessionId - The session ID where the message was sent.
   * @param {Array} chatHistory - The chat history at the time of feedback.
   * @param {Object} ratedMessage - The specific message being rated.
   * @param {string} rating - Either 'good' or 'bad'.
   * @returns {Promise<AxiosResponse>} Resolves with feedback submission status.
   */
  submitFeedback(sessionId, chatHistory, ratedMessage, rating) {
    return apiClient.post('/feedback/', {
      sessionId,
      chatHistory,
      ratedMessage,
      rating
    });
  },

  /**
   * Submits a fact correction.
   * @param {string} factId - The ID of the fact to correct.
   * @param {string} correction - The corrected value.
   * @param {string} userId - The user ID providing the correction.
   * @returns {Promise<AxiosResponse>} Resolves with correction submission status.
   */
  submitFactCorrection(factId, correction, userId) {
    return apiClient.post('/feedback/correction', {
      fact_id: factId,
      correction,
      user_id: userId
    });
  },
};

export default chatService;
