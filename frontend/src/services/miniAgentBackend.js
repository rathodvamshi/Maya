// frontend/src/services/miniAgentBackend.js
// Backend integration for Mini Inline Agent (Junior Lecturer)
// Provides: ensureMiniThread, addMiniSnippet, sendMiniMessage

const RAW_BASE = (process.env.REACT_APP_API_URL || '').replace(/\/$/, '');
const API_BASE = RAW_BASE ? (RAW_BASE.endsWith('/api') ? RAW_BASE : `${RAW_BASE}/api`) : '';
const MINI_PREFIX = '/api/mini-agent';
const THREAD_MAP_KEY = 'maya_mini_thread_map_v1';

function authHeaders() {
  const headers = { 'Content-Type': 'application/json' };
  try {
    const stored = localStorage.getItem('user');
    if (stored) {
      const u = JSON.parse(stored);
      if (u?.access_token) headers['Authorization'] = `Bearer ${u.access_token}`;
    }
  } catch {}
  return headers;
}

function loadThreadMap() {
  try { return JSON.parse(localStorage.getItem(THREAD_MAP_KEY)) || {}; } catch { return {}; }
}
function saveThreadMap(map) {
  try { localStorage.setItem(THREAD_MAP_KEY, JSON.stringify(map)); } catch {}
}

export async function ensureMiniThread(messageId) {
  if (!API_BASE) return { offline: true };
  const resp = await fetch(API_BASE + MINI_PREFIX + '/threads/ensure', {
    method: 'POST',
    headers: authHeaders(),
    body: JSON.stringify({ message_id: messageId })
  });
  if (!resp.ok) throw new Error('Failed to ensure mini thread');
  const data = await resp.json();
  const map = loadThreadMap();
  map[messageId] = { threadId: data.mini_thread_id, sessionId: data.session_id, ts: Date.now() };
  saveThreadMap(map);
  return data;
}

export async function addMiniSnippet(threadId, text) {
  if (!API_BASE) return { offline: true };
  const resp = await fetch(API_BASE + MINI_PREFIX + `/threads/${threadId}/snippets/add`, {
    method: 'POST',
    headers: authHeaders(),
    body: JSON.stringify({ text })
  });
  if (!resp.ok) throw new Error('Failed to add snippet');
  return await resp.json();
}

export async function sendMiniMessage(threadId, snippetId, content) {
  if (!API_BASE) return { offline: true };
  const resp = await fetch(API_BASE + MINI_PREFIX + `/threads/${threadId}/messages`, {
    method: 'POST',
    headers: authHeaders(),
    body: JSON.stringify({ snippet_id: snippetId, content })
  });
  if (!resp.ok) throw new Error('Mini message send failed');
  return await resp.json();
}

// SSE streaming reply (pseudo-stream): returns a controller with close() and a promise
export function streamMiniMessage(threadId, snippetId, content, { onMeta, onToken, onDone, onError } = {}) {
  if (!API_BASE || typeof EventSource === 'undefined') {
    return { unsupported: true };
  }
  const qs = new URLSearchParams({ content });
  if (snippetId) qs.set('snippet_id', snippetId);
  const url = API_BASE + MINI_PREFIX + `/threads/${threadId}/messages/stream?` + qs.toString();
  const es = new EventSource(url, { withCredentials: true });
  let closed = false;
  const close = () => { if (!closed) { es.close(); closed = true; } };
  es.addEventListener('meta', (e) => {
    try { onMeta && onMeta(JSON.parse(e.data)); } catch {}
  });
  es.addEventListener('token', (e) => {
    try { onToken && onToken(JSON.parse(e.data)); } catch {}
  });
  es.addEventListener('done', (e) => {
    try { onDone && onDone(JSON.parse(e.data)); } catch { onDone && onDone(null); }
    close();
  });
  es.addEventListener('error', (e) => {
    onError && onError(e);
    close();
  });
  return { close };
}

// Highlight persistence
export async function createMiniHighlight(messageId, text, snippetId) {
  if (!API_BASE) return { offline: true };
  const resp = await fetch(API_BASE + MINI_PREFIX + '/highlights', {
    method: 'POST',
    headers: authHeaders(),
    body: JSON.stringify({ message_id: messageId, text, snippet_id: snippetId })
  });
  if (!resp.ok) throw new Error('Failed to create highlight');
  return await resp.json();
}

export async function listMiniHighlights(messageId) {
  if (!API_BASE) return [];
  const url = API_BASE + MINI_PREFIX + '/highlights' + (messageId ? `?message_id=${encodeURIComponent(messageId)}` : '');
  const resp = await fetch(url, { headers: authHeaders() });
  if (!resp.ok) throw new Error('Failed to list highlights');
  return await resp.json();
}

// Snippet management
export async function renameMiniSnippet(threadId, snippetId, text) {
  if (!API_BASE) return { offline: true };
  const resp = await fetch(API_BASE + MINI_PREFIX + `/threads/${threadId}/snippets/${snippetId}`, {
    method: 'PATCH',
    headers: authHeaders(),
    body: JSON.stringify({ text })
  });
  if (!resp.ok) throw new Error('Rename failed');
  return await resp.json();
}

export async function deleteMiniSnippet(threadId, snippetId) {
  if (!API_BASE) return { offline: true };
  const resp = await fetch(API_BASE + MINI_PREFIX + `/threads/${threadId}/snippets/${snippetId}`, {
    method: 'DELETE',
    headers: authHeaders(),
  });
  if (!resp.ok) throw new Error('Delete failed');
  return await resp.json();
}

export async function summarizeMiniThread(threadId) {
  if (!API_BASE) return { offline: true };
  const resp = await fetch(API_BASE + MINI_PREFIX + `/threads/${threadId}/summarize`, {
    method: 'POST',
    headers: authHeaders(),
  });
  if (!resp.ok) throw new Error('Summarize failed');
  return await resp.json();
}

export function getCachedThreadInfo(messageId) {
  const map = loadThreadMap();
  return map[messageId] || null;
}
