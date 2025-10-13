// frontend/src/services/highlightService.js
import apiClient from './api';

const highlightService = {
  updateMessage(sessionId, messageId, { annotatedHtml, highlights }) {
    return apiClient.patch(`/annotations/sessions/${sessionId}/messages/${messageId}`, {
      annotatedHtml,
      highlights,
    });
  },
  getMessage(sessionId, messageId) {
    return apiClient.get(`/annotations/sessions/${sessionId}/messages/${messageId}`);
  },
};

export default highlightService;
