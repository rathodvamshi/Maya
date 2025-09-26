// frontend/src/services/feedbackService.js

import apiClient from './api'; // Import the configured Axios instance

const feedbackService = {
  /**
   * Submits feedback for a specific AI message.
   * @param {object} feedbackData The data to send.
   * @param {string} feedbackData.sessionId The ID of the current chat session.
   * @param {Array<object>} feedbackData.chatHistory The conversation history up to the rated message.
   * @param {object} feedbackData.ratedMessage The specific message being rated.
   * @param {string} feedbackData.rating The rating ('good' or 'bad').
   * @returns {Promise<AxiosResponse<any>>}
   */
  submitFeedback: (feedbackData) => {
    return apiClient.post('/api/feedback/', feedbackData);
  },
};

export default feedbackService;