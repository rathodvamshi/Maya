// frontend/src/services/videoControlsService.js
import apiClient from './api';

export async function sendControl(action, ctx = {}) {
  const body = {
    action,
    session_id: ctx.sessionId,
    current_video_id: ctx.videoId,
    current_title: ctx.title,
    current_context: ctx.context,
  };
  const res = await apiClient.post('/chat/video/control', body);
  return res.data; // { response_text, video?, lyrics? }
}

export default { sendControl };