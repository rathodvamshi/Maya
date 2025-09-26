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
    return apiClient.post('/api/chat/new', { message: firstMessage });
  },

  /**
   * Sends a message to an existing chat session.
   * @param {string} sessionId - ID of the chat session to continue.
   * @param {string} message - The user's message.
   * @returns {Promise<AxiosResponse>} Resolves with { response_text } from AI.
   */
  sendMessage(sessionId, message) {
    if (sessionId) {
      // Continue existing session
      return apiClient.post(`/api/chat/${sessionId}`, { message });
    }
    // Default route for generic chat
    return apiClient.post('/api/chat/', { message });
  },

  /**
   * Retrieves the latest chat history for the current user.
   * @returns {Promise<AxiosResponse>} Resolves with an array of messages.
   */
  getHistory() {
    return apiClient.get('/api/chat/history');
  },

  /**
   * Clears all chat history for the current user.
   * @returns {Promise<AxiosResponse>} Resolves with a status message.
   */
  clearHistory() {
    return apiClient.delete('/api/chat/history/clear');
  },

  // ----------------------------
  // Task Management
  // ----------------------------

  /**
   * Fetches all pending tasks for the current user.
   * @returns {Promise<AxiosResponse>} Resolves with an array of tasks.
   */
  getTasks() {
    return apiClient.get('/api/chat/tasks');
  },

  /**
   * Fetches recently completed tasks for the current user.
   * @returns {Promise<AxiosResponse>} Resolves with an array of tasks.
   */
  getTaskHistory() {
    return apiClient.get('/api/chat/tasks/history');
  },

  /**
   * Creates a new task.
   * @param {string} content - The task content.
   * @param {string} dueDate - Task due date in 'YYYY-MM-DD HH:mm' format.
   * @returns {Promise<AxiosResponse>} Resolves with created task ID.
   */
  createTask(content, dueDate) {
    return apiClient.post('/api/chat/tasks', { content, due_date: dueDate });
  },

  /**
   * Updates an existing task with new content or due date.
   * @param {string} taskId - The ID of the task to update.
   * @param {object} taskData - Fields to update, e.g., { content, due_date }.
   * @returns {Promise<AxiosResponse>} Resolves with status of update.
   */
  updateTask(taskId, taskData) {
    return apiClient.put(`/api/chat/tasks/${taskId}`, taskData);
  },

  /**
   * Marks a specific task as done.
   * @param {string} taskId - The ID of the task to mark complete.
   * @returns {Promise<AxiosResponse>} Resolves with status of completion.
   */
  markTaskAsDone(taskId) {
    return apiClient.put(`/api/chat/tasks/${taskId}/done`);
  },
};

export default chatService;
