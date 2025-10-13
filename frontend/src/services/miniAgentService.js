import api from './api';

const miniAgentService = {
  ensureThread(messageId) {
    return api.post('/mini-agent/threads/ensure', { message_id: messageId });
  },
  getThreadByMessage(messageId) {
    return api.get(`/mini-agent/by-message/${messageId}`);
  },
  getThread(threadId) {
    return api.get(`/mini-agent/threads/${threadId}`);
  },
  addSnippet(threadId, text) {
    return api.post(`/mini-agent/threads/${threadId}/snippets/add`, { text });
  },
  sendMessage(threadId, { snippet_id, content }) {
    return api.post(`/mini-agent/threads/${threadId}/messages`, { snippet_id, content });
  },
  updateUI(threadId, meta) {
    return api.patch(`/mini-agent/threads/${threadId}/ui`, { meta });
  },
};

export default miniAgentService;
