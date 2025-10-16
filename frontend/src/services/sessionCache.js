// frontend/src/services/sessionCache.js
// Lightweight in-memory + sessionStorage-backed cache for session messages
// Provides fast instant switching between sessions and survives component remounts.

const STORAGE_KEY = 'maya_session_cache_v1';
const DEFAULT_TTL_MS = 10 * 60 * 1000; // 10 minutes
const MAX_SESSIONS = 15; // keep last 15 sessions in cache

function now() { return Date.now(); }

function safeParse(json) {
  try { return JSON.parse(json); } catch { return null; }
}

function loadStore() {
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY);
    const parsed = safeParse(raw);
    if (parsed && typeof parsed === 'object' && parsed.entries) return parsed;
  } catch {}
  return { entries: {}, order: [] }; // entries: sid -> { ts, messages, total, hasMore, limit, offset }
}

function saveStore(store) {
  try { sessionStorage.setItem(STORAGE_KEY, JSON.stringify(store)); } catch {}
}

function prune(store) {
  const o = store.order || [];
  if (o.length > MAX_SESSIONS) {
    const drop = o.slice(MAX_SESSIONS);
    drop.forEach(id => { delete store.entries[id]; });
    store.order = o.slice(0, MAX_SESSIONS);
  }
}

const mem = {
  entries: new Map(), // sid -> { ts, messages, total, hasMore, limit, offset }
  ttl: DEFAULT_TTL_MS,
};

// Hydrate memory from sessionStorage on first import
(() => {
  const store = loadStore();
  const nowTs = now();
  Object.entries(store.entries).forEach(([sid, val]) => {
    if (val && typeof val.ts === 'number' && (nowTs - val.ts) < DEFAULT_TTL_MS) {
      mem.entries.set(sid, val);
    }
  });
})();

function persist() {
  const store = { entries: {}, order: [] };
  const nowTs = now();
  for (const [sid, val] of mem.entries.entries()) {
    if ((nowTs - (val.ts || 0)) < mem.ttl) {
      store.entries[sid] = val;
      store.order.push(sid);
    }
  }
  // Most recent first
  store.order.sort((a, b) => (store.entries[b].ts || 0) - (store.entries[a].ts || 0));
  prune(store);
  saveStore(store);
}

const sessionCache = {
  setTTL(ms) {
    if (typeof ms === 'number' && ms > 0) mem.ttl = ms;
  },

  get(sessionId) {
    if (!sessionId) return null;
    const rec = mem.entries.get(sessionId);
    if (!rec) return null;
    if ((now() - (rec.ts || 0)) > mem.ttl) {
      mem.entries.delete(sessionId);
      persist();
      return null;
    }
    return rec;
  },

  set(sessionId, payload) {
    if (!sessionId || !payload) return;
    const rec = {
      ts: now(),
      messages: Array.isArray(payload.messages) ? payload.messages : [],
      total: typeof payload.total === 'number' ? payload.total : undefined,
      hasMore: !!payload.hasMore,
      limit: typeof payload.limit === 'number' ? payload.limit : undefined,
      offset: typeof payload.offset === 'number' ? payload.offset : undefined,
    };
    mem.entries.set(sessionId, rec);
    persist();
  },

  // Merge older messages at the beginning (for lazy load) while keeping order
  prepend(sessionId, olderMessages, newOffset) {
    const rec = mem.entries.get(sessionId) || { ts: now(), messages: [] };
    const existing = Array.isArray(rec.messages) ? rec.messages : [];
    const merged = Array.isArray(olderMessages) ? [...olderMessages, ...existing] : existing;
    mem.entries.set(sessionId, {
      ...rec,
      ts: now(),
      messages: merged,
      offset: typeof newOffset === 'number' ? newOffset : rec.offset,
    });
    persist();
  },

  // Append new messages at the end (e.g., after sending)
  append(sessionId, newMessages) {
    const rec = mem.entries.get(sessionId) || { ts: now(), messages: [] };
    const existing = Array.isArray(rec.messages) ? rec.messages : [];
    const merged = Array.isArray(newMessages) ? [...existing, ...newMessages] : existing;
    mem.entries.set(sessionId, { ...rec, ts: now(), messages: merged });
    persist();
  },

  has(sessionId) { return !!this.get(sessionId); },

  clear(sessionId) {
    if (sessionId) {
      mem.entries.delete(sessionId);
    } else {
      mem.entries.clear();
    }
    persist();
  }
};

export default sessionCache;
