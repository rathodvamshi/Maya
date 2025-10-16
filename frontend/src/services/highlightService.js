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
    // Avoid calling backend if ids are obviously invalid; prevents 404 noise
    try {
      const isOid = (v) => typeof v === 'string' && /^[a-f\d]{24}$/i.test(v);
      if (!isOid(sessionId) || !isOid(messageId)) {
        return Promise.resolve({ data: null });
      }
    } catch {}
    return apiClient.get(`/annotations/sessions/${sessionId}/messages/${messageId}`);
  },
};

export default highlightService;
