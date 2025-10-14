import React, { useEffect, useRef, useState } from 'react';
import miniAgentService from '../services/miniAgentService';
import '../styles/MiniAgent.css';

export default function MiniAgentPanel({ thread, selectedText, onClose }) {
  const [messages, setMessages] = useState(thread?.messages || []);
  const [value, setValue] = useState(selectedText || '');
  const [pos, setPos] = useState(() => {
    const saved = thread?.meta?.position;
    if (saved && typeof saved.x === 'number' && typeof saved.y === 'number') return saved;
    try {
      if (typeof window !== 'undefined' && window.innerWidth <= 560) {
        const defaultW = 320; const defaultH = 380;
        const x = Math.max(8, window.innerWidth - defaultW - 8);
        const y = Math.max(8, window.innerHeight - defaultH - 80);
        return { x, y };
      }
    } catch {}
    return { x: 60, y: 80 };
  });
  const [size, setSize] = useState(thread?.meta?.size || { width: 350, height: 420 });
  const [activeSnippetId, setActiveSnippetId] = useState(null);
  const [activeSnippetText, setActiveSnippetText] = useState('');
  const [sending, setSending] = useState(false);
  const [mode, setMode] = useState(thread?.meta?.state || 'open'); // 'open' | 'min' | 'max'
  const [streaming, setStreaming] = useState(false);
  const esRef = useRef(null);
  const messagesWrapRef = useRef(null);
  const messagesEndRef = useRef(null);
  const [micOn, setMicOn] = useState(false);
  const hadStreamTokens = useRef(false);
  const dragging = useRef(false);
  const dragOffset = useRef({ x: 0, y: 0 });
  const resizing = useRef(false);
  const resizeStart = useRef({ x: 0, y: 0, w: 0, h: 0 });
  const rafId = useRef(null);
  const rootRef = useRef(null);

  useEffect(() => {
    const meta = { position: pos, size, state: mode };
    const id = thread?.mini_thread_id; if (!id) return;
    const t = setTimeout(() => miniAgentService.updateUI(id, meta), 500);
    // localStorage fallback
    try { localStorage.setItem(`mini:meta:${id}`, JSON.stringify(meta)); } catch {}
    return () => clearTimeout(t);
  }, [pos, size, mode, thread?.mini_thread_id]);

  // Hydrate meta from localStorage if server meta missing
  useEffect(() => {
    if (thread?.meta && (thread.meta.position || thread.meta.size)) return;
    try {
      const raw = localStorage.getItem(`mini:meta:${thread?.mini_thread_id}`);
      if (raw) {
        const parsed = JSON.parse(raw);
        if (parsed?.position) setPos(parsed.position);
        if (parsed?.size) setSize(parsed.size);
        if (parsed?.state) setMode(parsed.state);
      }
    } catch {}
  }, [thread?.mini_thread_id]);

  // If opening with a selected snippet of text, add it as a snippet for better context
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const text = (selectedText || '').trim();
        if (!text) return;
        const res = await miniAgentService.addSnippet(thread.mini_thread_id, text);
        if (!cancelled && res?.data?.snippet_id) {
          setActiveSnippetId(res.data.snippet_id);
          setActiveSnippetText(text);
        }
      } catch {}
    })();
    return () => { cancelled = true; };
  }, [selectedText, thread?.mini_thread_id]);

  const onMouseDown = (e) => {
    if (!rootRef.current) return;
    dragging.current = true;
    dragOffset.current = { x: e.clientX - pos.x, y: e.clientY - pos.y };
    e.preventDefault();
  };
  const onTouchStart = (e) => {
    if (!rootRef.current) return;
    const t = e.touches && e.touches[0]; if (!t) return;
    dragging.current = true;
    dragOffset.current = { x: t.clientX - pos.x, y: t.clientY - pos.y };
    e.preventDefault();
  };
  const onMouseMove = (e) => {
    if (!dragging.current && !resizing.current) return;
    if (rafId.current) cancelAnimationFrame(rafId.current);
    rafId.current = requestAnimationFrame(() => {
      if (dragging.current) {
        const nx = Math.max(0, Math.min(window.innerWidth - size.width, e.clientX - dragOffset.current.x));
        const ny = Math.max(0, Math.min(window.innerHeight - size.height, e.clientY - dragOffset.current.y));
        setPos({ x: nx, y: ny });
      } else if (resizing.current) {
        const dx = e.clientX - resizeStart.current.x;
        const dy = e.clientY - resizeStart.current.y;
        const nw = Math.max(320, Math.min(window.innerWidth - pos.x, resizeStart.current.w + dx));
        const nh = Math.max(300, Math.min(window.innerHeight - pos.y, resizeStart.current.h + dy));
        setSize({ width: nw, height: nh });
      }
    });
  };
  const onTouchMove = (e) => {
    if (!dragging.current) return;
    const t = e.touches && e.touches[0]; if (!t) return;
    if (rafId.current) cancelAnimationFrame(rafId.current);
    rafId.current = requestAnimationFrame(() => {
      const nx = Math.max(0, Math.min(window.innerWidth - size.width, t.clientX - dragOffset.current.x));
      const ny = Math.max(0, Math.min(window.innerHeight - size.height, t.clientY - dragOffset.current.y));
      setPos({ x: nx, y: ny });
    });
  };
  const onMouseUp = () => { dragging.current = false; };
  const onTouchEnd = () => { dragging.current = false; };
  useEffect(() => {
    window.addEventListener('mousemove', onMouseMove);
    window.addEventListener('mouseup', onMouseUp);
    window.addEventListener('touchmove', onTouchMove, { passive: false });
    window.addEventListener('touchend', onTouchEnd);
    return () => {
      window.removeEventListener('mousemove', onMouseMove);
      window.removeEventListener('mouseup', onMouseUp);
      window.removeEventListener('touchmove', onTouchMove);
      window.removeEventListener('touchend', onTouchEnd);
    };
  }, [size]);

  // Resize handle mousedown
  const onResizeDown = (e) => {
    resizing.current = true;
    resizeStart.current = { x: e.clientX, y: e.clientY, w: size.width, h: size.height };
    e.preventDefault();
  };
  const onResizeUp = () => { resizing.current = false; };
  useEffect(() => {
    window.addEventListener('mouseup', onResizeUp);
    return () => window.removeEventListener('mouseup', onResizeUp);
  }, []);

  // Focus textarea on mount
  const inputRef = useRef(null);
  useEffect(() => { inputRef.current?.focus(); }, []);

  // Auto-scroll to bottom when messages update or streaming progresses
  useEffect(() => {
    if (!messagesWrapRef.current) return;
    try {
      messagesWrapRef.current.scrollTop = messagesWrapRef.current.scrollHeight;
    } catch {}
  }, [messages, streaming]);

  // Keyboard handlers: Enter to send, Esc to close
  const onKeyDown = (e) => {
    if (e.key === 'Escape') { onClose(); }
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(); }
  };

  const stopStream = () => {
    setStreaming(false);
    if (esRef.current) {
      try { esRef.current.close(); } catch {}
      esRef.current = null;
    }
  };

  const send = async () => {
    const content = value.trim();
    if (!content) return;
    // ensure any previous stream is closed
    try { esRef.current && esRef.current.close(); } catch {}
    esRef.current = null;
    hadStreamTokens.current = false;
    const localUser = { mini_message_id: `u_${Date.now()}`, role: 'user', content };
    setMessages((prev) => [...prev, localUser]);
    setValue('');
    setSending(true);
    try {
      // Prefer streaming via SSE
      setStreaming(true);
      const assistantId = `a_${Date.now()}`;
      // add placeholder assistant message quickly to feel responsive
      setMessages((prev) => [...prev, { mini_message_id: assistantId, role: 'assistant', content: '' }]);
      const params = new URLSearchParams();
      params.set('content', content);
      if (activeSnippetId) params.set('snippet_id', activeSnippetId);
      // add cache-busting timestamp to avoid intermediary caches
      params.set('_t', String(Date.now()));
      // Build absolute URL with token fallback to handle SSE auth
      const RAW_BASE = (process.env.REACT_APP_API_URL || 'http://localhost:8000').replace(/\/$/, '');
      const API_BASE = RAW_BASE.endsWith('/api') ? RAW_BASE : `${RAW_BASE}/api`;
      try {
        const stored = localStorage.getItem('user');
        const tokenObj = stored ? JSON.parse(stored) : null;
        if (tokenObj?.access_token) params.set('access_token', tokenObj.access_token);
      } catch {}
      const url = `${API_BASE}/mini-agent/threads/${thread.mini_thread_id}/messages/stream?` + params.toString();
      const es = new EventSource(url);
      esRef.current = es;
      es.addEventListener('open', () => {
        // connection established
      });
      es.addEventListener('meta', (e) => {
        // could use ids from server
      });
      es.addEventListener('token', (e) => {
        const data = JSON.parse(e.data || '{}');
        const piece = data.text || '';
        if (piece) hadStreamTokens.current = true;
        setMessages((prev) => prev.map(m => m.mini_message_id === assistantId ? { ...m, content: (m.content || '') + piece } : m));
      });
      es.addEventListener('done', () => {
        stopStream();
      });
      es.addEventListener('error', async () => {
        // Fallback to non-streaming if no tokens received
        const noTokens = !hadStreamTokens.current;
        stopStream();
        if (noTokens) {
          try {
            const res = await miniAgentService.sendMessage(thread.mini_thread_id, { content, snippet_id: activeSnippetId || undefined });
            const full = res.data.assistant_text || '';
            setMessages((prev) => prev.map(m => m.mini_message_id === assistantId ? { ...m, content: full } : m));
          } catch (err) {
            setMessages((prev) => prev.map(m => m.mini_message_id === assistantId ? { ...m, content: 'Error. Try again.' } : m));
          }
        }
      });
    } catch (e) {
      // fallback minimal error bubble
      setMessages((prev) => [...prev, { mini_message_id: `err_${Date.now()}`, role: 'assistant', content: 'Error. Try again.' }]);
    } finally { setSending(false); }
  };

  // Simple mic using Web Speech API (if available)
  const recRef = useRef(null);
  const toggleMic = () => {
    try {
      const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
      if (!SpeechRecognition) { setMicOn(false); return; }
      if (micOn) {
        try { recRef.current && recRef.current.stop(); } catch {}
        setMicOn(false);
        return;
      }
      const rec = new SpeechRecognition();
      rec.lang = 'en-US';
      rec.continuous = false;
      rec.interimResults = true;
      rec.onresult = (event) => {
        let interim = '';
        let final = '';
        for (let i = event.resultIndex; i < event.results.length; ++i) {
          if (event.results[i].isFinal) final += event.results[i][0].transcript;
          else interim += event.results[i][0].transcript;
        }
        inputRef.current && (inputRef.current.value = (value + ' ' + final + interim).trim());
        setValue((v) => (v + ' ' + final + interim).trim());
      };
      rec.onend = () => setMicOn(false);
      recRef.current = rec;
      rec.start();
      setMicOn(true);
    } catch {
      setMicOn(false);
    }
  };

  useEffect(() => {
    return () => {
      // cleanup
      try { esRef.current && esRef.current.close(); } catch {}
      try { recRef.current && recRef.current.stop(); } catch {}
    };
  }, []);

  return (
    <div ref={rootRef} className="mini-agent-panel" role="dialog" aria-label="Mini Agent"
         style={{ position: 'fixed', left: mode==='max'?0:pos.x, top: mode==='max'?0:pos.y, width: mode==='max'? 'min(100vw, 1100px)': size.width, height: mode==='max'? 'min(100vh, 80vh)': size.height, zIndex: 10030 }} onKeyDown={onKeyDown}>
  <div className="mini-agent-header" onMouseDown={onMouseDown} onTouchStart={onTouchStart}>
        <div className="mini-title">
          <strong>Mini Agent</strong>
          <span className="mini-sub"> attached to this message</span>
        </div>
        <div className="mini-controls">
          <button title="Minimize" aria-label="Minimize" onClick={() => setMode((m) => (m === 'min' ? 'open' : 'min'))}>{mode === 'min' ? '▢' : '—'}</button>
          <button title="Expand" aria-label="Expand" onClick={() => setMode((m)=> (m==='max'?'open':'max'))}>{mode==='max'?'🗗':'🗖'}</button>
          <button title="Detach" aria-label="Detach" onClick={() => window.open('#mini-agent', '_blank')}>⧉</button>
          <button title="Close" aria-label="Close" onClick={onClose}>×</button>
        </div>
      </div>
      <div className="mini-body" style={{ display: mode === 'min' ? 'none' : 'flex' }}>
        {activeSnippetText && (
          <div className="mini-snippet-pill" title={activeSnippetText}>
            <span className="label">Snippet</span>
            <span className="text">{activeSnippetText.length > 70 ? activeSnippetText.slice(0,70) + '…' : activeSnippetText}</span>
          </div>
        )}
        <div ref={messagesWrapRef} className="mini-messages" aria-live="polite">
          {messages.map((m) => (
            <div key={m.mini_message_id} className={`mini-msg ${m.role}`}>
              <div className="msg-body">{m.content}</div>
              <div className="msg-actions">
                {m.role === 'assistant' ? (
                  <>
                    <button title="Copy" aria-label="Copy" onClick={() => navigator.clipboard.writeText(m.content||'')}>📋</button>
                    <button title="Share" aria-label="Share" onClick={async ()=>{
                      try {
                        if (navigator.share) await navigator.share({ text: m.content||'' });
                        else navigator.clipboard.writeText(m.content||'');
                      } catch {}
                    }}>🔗</button>
                    <button title="Feedback" aria-label="Feedback" onClick={()=>alert('Feedback modal TBD')}>💬</button>
                  </>
                ) : (
                  <>
                    <button title="Copy" aria-label="Copy" onClick={() => navigator.clipboard.writeText(m.content||'')}>📋</button>
                    <button title="Edit" aria-label="Edit" onClick={()=> setValue(m.content||'') }>✏️</button>
                  </>
                )}
              </div>
            </div>
          ))}
          {(sending || streaming) && (
            <div className="mini-msg assistant typing">
              <div className="msg-body">
                <div className="typing-dots" aria-label="Assistant is typing">
                  <span></span><span></span><span></span>
                </div>
              </div>
              <div className="msg-actions">
                <button className="mini-stop" onClick={stopStream} aria-label="Stop">■</button>
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>
        <div className="mini-input">
          <textarea ref={inputRef} aria-label="Mini agent input" value={value} onChange={(e) => setValue(e.target.value)} rows={3} placeholder="Ask a quick question about the snippet…" />
          <div className="mini-input-icons">
            <button className={`mic ${micOn?'on':''}`} title="Mic" aria-label="Mic" onClick={toggleMic}>{micOn?'🎙️':'🎤'}</button>
          </div>
          <button onClick={send} aria-label="Send" disabled={sending || streaming}>{(sending||streaming) ? 'Sending…' : 'Send'}</button>
          {(streaming) && <button className="mini-stop" onClick={stopStream} aria-label="Stop">■</button>}
        </div>
      </div>
      <div className="mini-resize-handle" onMouseDown={onResizeDown} aria-label="Resize" title="Resize" />
    </div>
  );
}
