// Inline Agent API Service
// Provides backend integration for inline AI chat, highlights, saved snippets.
// Falls back gracefully to local simulation if backend unreachable.

const BASE_URL = process.env.REACT_APP_INLINE_AI_BASE_URL || '';

// Mini-agent session management (kept separate from any main agent session logic)
const MINI_SESSION_LS_KEY = 'maya_inline_mini_session_id_v1';

export function getOrCreateMiniSessionId() {
  let id = localStorage.getItem(MINI_SESSION_LS_KEY);
  if (!id) {
    id = 'mini_' + Date.now().toString(36) + '_' + Math.random().toString(36).slice(2, 10);
    try { localStorage.setItem(MINI_SESSION_LS_KEY, id); } catch {}
  }
  return id;
}

async function safeFetch(url, options) {
  try {
    const res = await fetch(url, options);
    if (!res.ok) throw new Error('HTTP ' + res.status);
    return await res.json();
  } catch (e) {
    console.warn('[inlineAgentApi] Falling back (', url, '):', e.message);
    return null; // caller handles fallback
  }
}

export async function fetchThread(messageId, threadKey) {
  if (!BASE_URL) return null;
  return await safeFetch(`${BASE_URL}/api/inline_ai_threads?message_id=${encodeURIComponent(messageId)}&thread_key=${encodeURIComponent(threadKey)}`);
}

export async function createThread(payload) {
  if (!BASE_URL) return null;
  return await safeFetch(`${BASE_URL}/api/inline_ai_threads`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  });
}

export async function addThreadMessage(threadId, message) {
  if (!BASE_URL) return null;
  return await safeFetch(`${BASE_URL}/api/inline_ai_threads/${threadId}/messages`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(message)
  });
}

/**
 * Generate AI reply for mini-agent only.
 * Returns an object: { ok: boolean, reply?: string, error?: string, errorType?: string }
 * errorType examples: 'SERVICE_UNAVAILABLE', 'BACKEND_ERROR'
 */
export async function generateAIReply(userText, context, { sessionId, agent = 'mini' } = {}) {
  const sid = sessionId || getOrCreateMiniSessionId();
  if (BASE_URL) {
    const res = await safeFetch(`${BASE_URL}/api/inline_ai/generate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ prompt: userText, context, session_id: sid, agent })
    });
    if (!res) {
      return { ok: false, errorType: 'SERVICE_UNAVAILABLE', error: 'All AI services are currently unavailable. Please try again later.' };
    }
    if (res.error) {
      return { ok: false, errorType: 'BACKEND_ERROR', error: res.error || 'Unexpected backend error' };
    }
    if (res.reply) {
      return { ok: true, reply: res.reply, sessionId: sid };
    }
    return { ok: false, errorType: 'NO_REPLY', error: 'No reply returned.' };
  }
  // Fallback local mock (offline dev mode)
  await new Promise(r => setTimeout(r, 400 + Math.random() * 300));
  return { ok: true, reply: `Inline AI: ${userText.length > 220 ? userText.slice(0,220) + '…' : userText}` , sessionId: sid };
}

// Local persistence helpers (threads & highlights)
// Separate local thread storage key for mini agent only
const LS_THREADS_KEY = 'maya_inline_threads_v1_mini';

export function loadLocalThreads() {
  try { return JSON.parse(localStorage.getItem(LS_THREADS_KEY)) || {}; } catch { return {}; }
}
export function saveLocalThreads(data) {
  try { localStorage.setItem(LS_THREADS_KEY, JSON.stringify(data)); } catch {}
}

export function threadKeyFromSelection(messageId, selectedText) {
  const sid = getOrCreateMiniSessionId();
  return `${sid}::${messageId || 'unknown'}::${(selectedText||'').slice(0,64)}`;
}

// New per-message (multi-snippet) thread key (does NOT depend on snippet text)
export function threadKeyForMessage(messageId) {
  const sid = getOrCreateMiniSessionId();
  return `${sid}::${messageId || 'unknown'}`;
}

// Get structured thread for a message: { snippets: [{id,text}], messages: [...] }
export function loadMessageThread(messageId) {
  const all = loadLocalThreads();
  return all[threadKeyForMessage(messageId)] || null;
}

export function saveMessageThread(messageId, thread) {
  const all = loadLocalThreads();
  all[threadKeyForMessage(messageId)] = thread;
  saveLocalThreads(all);
}

export function addOrGetSnippet(thread, text) {
  if (!thread.snippets) thread.snippets = [];
  const existing = thread.snippets.find(s => s.text === text);
  if (existing) return existing;
  const snippet = { id: 'snip_' + Date.now().toString(36) + '_' + Math.random().toString(36).slice(2,7), text };
  thread.snippets.push(snippet);
  return snippet;
}

export function ensureMessageThread(messageId) {
  const existing = loadMessageThread(messageId);
  if (existing) return existing;
  return { snippets: [], messages: [] };
}
