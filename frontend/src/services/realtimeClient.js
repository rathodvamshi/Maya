// frontend/src/services/realtimeClient.js

import apiClient from './api';

const TRANSPORT = (process.env.REACT_APP_REALTIME_TRANSPORT || 'off').toLowerCase();
let source = null;
let listeners = new Map();
let started = false;

function dispatch(event) {
  const type = event?.type;
  const payload = event?.payload;
  const list = listeners.get(type);
  if (Array.isArray(list)) {
    list.forEach(fn => {
      try { fn(payload, event); } catch {}
    });
  }
  // Also rebroadcast via window/BroadcastChannel for existing flows
  try {
    if (type?.startsWith('task.')) {
      window.dispatchEvent(new CustomEvent('maya:tasks-updated'));
      try { const bc = new BroadcastChannel('maya_tasks'); bc.postMessage({ type, payload, ts: Date.now() }); bc.close?.(); } catch {}
    }
    if (type === 'session.updated') {
      window.dispatchEvent(new CustomEvent('maya:sessions:refresh'));
      try { const bc = new BroadcastChannel('maya_sessions'); bc.postMessage({ type, payload, ts: Date.now() }); bc.close?.(); } catch {}
    }
  } catch {}
}

export function on(type, handler) {
  const arr = listeners.get(type) || [];
  arr.push(handler);
  listeners.set(type, arr);
  return () => {
    const cur = listeners.get(type) || [];
    listeners.set(type, cur.filter(fn => fn !== handler));
  };
}

export function start() {
  if (started || TRANSPORT !== 'sse') return;
  started = true;
  try {
    // Use plain EventSource with same-origin cookies; apiClient.baseURL ends with /api
    const base = apiClient.defaults.baseURL || '';
    const url = `${base}/realtime/stream`;
    source = new EventSource(url, { withCredentials: false });
    const handler = (ev) => {
      try {
        const data = ev?.data ? JSON.parse(ev.data) : null;
        if (data) dispatch(data);
      } catch {}
    };
    source.addEventListener('message.appended', handler);
    source.addEventListener('session.updated', handler);
    source.addEventListener('task.created', handler);
    source.addEventListener('task.updated', handler);
    source.addEventListener('task.deleted', handler);
    source.addEventListener('task.bulk_updated', handler);
    source.addEventListener('task.bulk_deleted', handler);
    source.addEventListener('ping', () => {});
    source.onerror = () => {
      // Let browser auto-reconnect; if it closes, attempt a manual restart after a delay
      try { source.close(); } catch {}
      source = null;
      started = false;
      setTimeout(() => { try { start(); } catch {} }, 1500);
    };
  } catch {
    started = false;
  }
}

export function stop() {
  try { source?.close?.(); } catch {}
  source = null;
  started = false;
}

const realtimeClient = { start, stop, on };
export default realtimeClient;
