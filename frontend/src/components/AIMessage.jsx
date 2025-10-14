

// React component that renders an AI chat message and adds interactive highlighting, annotations (notes), selection action bar, and mini‑agent thread integration with persistence.



import React, { useEffect, useRef, useState, useCallback, forwardRef, useImperativeHandle } from 'react';
// Removed unused action icons; ChatWindow hosts the actions toolbar now
import { createPortal } from 'react-dom';
import highlightService from '../services/highlightService';
import '../styles/ChatWindow.css';
import '../styles/highlight.css';
import SelectionActionBar from './SelectionActionBar';
import MiniAgentPanel from './MiniAgentPanel';
import miniAgentService from '../services/miniAgentService';

const COLORS = [
  { key: 'yellow', className: 'highlight-yellow', color: '#fff176' },
  { key: 'green', className: 'highlight-green', color: '#a5d6a7' },
  { key: 'blue', className: 'highlight-blue', color: '#81d4fa' },
  { key: 'red', className: 'highlight-red', color: '#ff8a80' },
  { key: 'purple', className: 'highlight-purple', color: '#b39ddb' },
  { key: 'orange', className: 'highlight-orange', color: '#ffcc80' },
];

function within(node, container) {
  if (!node) return false;
  let n = node.nodeType === Node.TEXT_NODE ? node.parentNode : node;
  while (n) {
    if (n === container) return true;
    n = n.parentNode;
  }
  return false;
}

function computeAbsoluteOffsets(root, range) {
  // Compute absolute offsets by walking text nodes in order
  let start = 0;
  let end = 0;
  let sawStart = false;
  let sawEnd = false;
  let acc = 0;
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, null);
  let node;
  while ((node = walker.nextNode())) {
    const len = node.nodeValue ? node.nodeValue.length : 0;
    if (!sawStart && node === range.startContainer) {
      start = acc + (range.startOffset || 0);
      sawStart = true;
    }
    if (!sawEnd && node === range.endContainer) {
      end = acc + (range.endOffset || 0);
      sawEnd = true;
    }
    acc += len;
    if (sawStart && sawEnd) break;
  }
  if (!sawEnd) {
    // Fallback: derive end from selection text length
    const len = (range.toString() || '').length;
    end = start + len;
  }
  if (end < start) end = start;
  return { startOffset: start, endOffset: end };
}

function wrapSelection(range, colorClass) {
  const span = document.createElement('span');
  span.className = `highlight ${colorClass}`;
  span.setAttribute('data-color', colorClass);
  span.style.transition = 'background-color 150ms ease';
  try {
    range.surroundContents(span);
  } catch (e) {
    // If range splits non-text nodes, use extract/insert
    const frag = range.extractContents();
    span.appendChild(frag);
    range.insertNode(span);
  }
  return span;
}

// ---- Safe DOM helpers to avoid null parent insertBefore errors ----
function safeUnwrap(node) {
  if (!node) return;
  const parent = node.parentNode;
  if (!parent) return;
  while (node.firstChild) {
    try { parent.insertBefore(node.firstChild, node); } catch { break; }
  }
  if (node.parentNode === parent) {
    try { parent.removeChild(node); } catch {}
  }
}

function insertAfter(parent, newNode, refNode) {
  if (!parent || !newNode) return;
  try {
    if (refNode && refNode.parentNode === parent) {
      if (refNode.nextSibling) parent.insertBefore(newNode, refNode.nextSibling);
      else parent.appendChild(newNode);
    } else {
      parent.appendChild(newNode);
    }
  } catch {}
}

const Popover = ({ x, y, onPick, onRemove, below }) => {
  return (
    <div className={`highlight-popover${below ? ' below' : ''}`} style={{ left: x, top: y }}>
      {COLORS.map((c) => (
        <button
          key={c.key}
          className={`palette-dot ${c.className}`}
          title={c.key}
          onClick={() => onPick(c.className)}
        />
      ))}
      <button className="palette-remove" title="Remove highlight" onClick={onRemove}>🗑</button>
    </div>
  );
};

const AIMessage = forwardRef(function AIMessage({ sessionId, message, onUpdated, onIndicatorsChange }, ref) {
  const containerRef = useRef(null);
  const [popover, setPopover] = useState(null); // {x,y, targetSpan}
  const [saveTimer, setSaveTimer] = useState(null);
  const [trigger, setTrigger] = useState(null); // {x,y}
  const textNodesRef = useRef([]);
  const [actionBar, setActionBar] = useState(null); // {x,y,parentMessageId,selectedText}
  const [miniThread, setMiniThread] = useState(null);
  const [miniOpen, setMiniOpen] = useState(false);
  const [hasMini, setHasMini] = useState(false);
  const [hasHighlights, setHasHighlights] = useState(Boolean((message?.highlights||[]).length));
  const [hlPanel, setHlPanel] = useState(null); // {x,y}
  const [hasSelection, setHasSelection] = useState(false);
  const [savedHint, setSavedHint] = useState(null); // {x,y,text}
  // Inline toolbar (copy/speak/feedback/share) removed; those are handled by ChatWindow

  const rIC = (cb) => {
    try {
      if (typeof window !== 'undefined' && 'requestIdleCallback' in window) {
        // @ts-ignore
        return window.requestIdleCallback(cb);
      }
    } catch {}
    return setTimeout(cb, 0);
  };

  // Render content (prefer annotatedHtml)
  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    if (message.annotatedHtml) {
      el.innerHTML = message.annotatedHtml;
    } else {
      el.textContent = message.content || message.text || '';
    }
    // message id attribute for lookup
    try { el.closest && el.closest('.message')?.setAttribute('data-message-id', message.id); } catch {}
    // Build text node cache for offset mapping
    const nodes = [];
    const walker = document.createTreeWalker(el, NodeFilter.SHOW_TEXT, null);
    let n;
    while ((n = walker.nextNode())) nodes.push(n);
    textNodesRef.current = nodes;
  }, [message.annotatedHtml, message.content, message.text]);

  // Check if a mini thread exists for pinned icon
  useEffect(() => {
    let cancel = false;
    (async () => {
      try {
        if (!message?.id) return;
        const res = await miniAgentService.getThreadByMessage(message.id);
        if (!cancel) setHasMini(Boolean(res?.data?.exists));
      } catch {}
    })();
    return () => { cancel = true; };
  }, [message?.id]);

  // Notify parent when indicators change (avoid effect loop from changing callback identity)
  const onIndicatorsChangeRef = useRef(onIndicatorsChange);
  useEffect(() => { onIndicatorsChangeRef.current = onIndicatorsChange; }, [onIndicatorsChange]);
  const prevFlagsRef = useRef({ hasMini: undefined, hasHighlights: undefined, id: undefined });
  useEffect(() => {
    const flags = { hasMini, hasHighlights };
    const id = message?.id;
    const prev = prevFlagsRef.current;
    const changed = prev.hasMini !== flags.hasMini || prev.hasHighlights !== flags.hasHighlights || prev.id !== id;
    if (changed) {
      prevFlagsRef.current = { ...flags, id };
      try { onIndicatorsChangeRef.current?.(id, flags); } catch {}
    }
  }, [hasMini, hasHighlights, message?.id]);

  // On mount, if no annotatedHtml but we have ids, fetch latest annotations to persist across refresh
  useEffect(() => {
    const el = containerRef.current;
    if (!el || !sessionId || !message?.id) return;
    if (message.annotatedHtml) return; // already present
    // Only try backend annotations when we have a persisted Mongo ObjectId
    try {
      const isObjectId = /^[a-fA-F0-9]{24}$/.test(String(message.id));
      if (!isObjectId) return;
    } catch {}
    let cancelled = false;
    (async () => {
      try {
        const res = await highlightService.getMessage(sessionId, message.id);
        const data = res?.data;
        if (data && data.annotatedHtml && !cancelled) {
          el.innerHTML = data.annotatedHtml;
          onUpdated?.({ annotatedHtml: data.annotatedHtml, highlights: data.highlights || [] });
          setHasHighlights(Boolean((data.highlights||[]).length));
          // refresh text node cache
          const nodes = [];
          const walker = document.createTreeWalker(el, NodeFilter.SHOW_TEXT, null);
          let n;
          while ((n = walker.nextNode())) nodes.push(n);
          textNodesRef.current = nodes;
          try {
            const key = `maya:anno:${sessionId}:${message.id}`;
            localStorage.setItem(key, JSON.stringify({ annotatedHtml: data.annotatedHtml, highlights: data.highlights || [] }));
          } catch {}
        } else if (!cancelled) {
          // Fallback: try localStorage
          try {
            const key = `maya:anno:${sessionId}:${message.id}`;
            const raw = localStorage.getItem(key);
            if (raw) {
              const cached = JSON.parse(raw);
              if (cached?.annotatedHtml) {
                el.innerHTML = cached.annotatedHtml;
                onUpdated?.({ annotatedHtml: cached.annotatedHtml, highlights: cached.highlights || [] });
                setHasHighlights(Boolean((cached.highlights||[]).length));
                const nodes = [];
                const walker = document.createTreeWalker(el, NodeFilter.SHOW_TEXT, null);
                let n;
                while ((n = walker.nextNode())) nodes.push(n);
                textNodesRef.current = nodes;
              }
            }
          } catch {}
        }
      } catch (e) {
        // Fallback to localStorage if backend fetch fails
        try {
          const key = `maya:anno:${sessionId}:${message.id}`;
          const raw = localStorage.getItem(key);
          if (raw) {
            const cached = JSON.parse(raw);
            if (cached?.annotatedHtml) {
              el.innerHTML = cached.annotatedHtml;
              onUpdated?.({ annotatedHtml: cached.annotatedHtml, highlights: cached.highlights || [] });
              setHasHighlights(Boolean((cached.highlights||[]).length));
              const nodes = [];
              const walker = document.createTreeWalker(el, NodeFilter.SHOW_TEXT, null);
              let n;
              while ((n = walker.nextNode())) nodes.push(n);
              textNodesRef.current = nodes;
            }
          }
        } catch {}
      }
    })();
    return () => { cancelled = true; };
  }, [sessionId, message?.id]);

  // Close/reposition on scroll/resize/outside-click/selection change and Esc
  useEffect(() => {
    const handleGlobalClose = (e) => {
      const t = e?.target;
      if (t && t.closest) {
        const insidePopover = t.closest('.highlight-popover');
        if (insidePopover) return;
      }
      setPopover(null);
      setActionBar(null);
    };
    const handleScrollOrResize = () => {
      // Positions go stale; close UI
      setPopover(null);
      setActionBar(null);
    };
    const handleKeydown = (e) => {
      if (e.key === 'Escape') {
        setPopover(null);
        setActionBar(null);
      }
    };
    const handleSelectionChange = () => {
      const sel = window.getSelection();
      if (!sel || sel.isCollapsed) {
        setActionBar(null);
        setHasSelection(false);
        // keep popover only if hovering an existing span
      }
    };
    document.addEventListener('mousedown', handleGlobalClose);
    document.addEventListener('touchstart', handleGlobalClose, { passive: true });
    window.addEventListener('scroll', handleScrollOrResize, true);
    window.addEventListener('resize', handleScrollOrResize);
    document.addEventListener('keydown', handleKeydown);
    document.addEventListener('selectionchange', handleSelectionChange);
    return () => {
      document.removeEventListener('mousedown', handleGlobalClose);
      document.removeEventListener('touchstart', handleGlobalClose);
      window.removeEventListener('scroll', handleScrollOrResize, true);
      window.removeEventListener('resize', handleScrollOrResize);
      document.removeEventListener('keydown', handleKeydown);
      document.removeEventListener('selectionchange', handleSelectionChange);
    };
  }, []);

  const scheduleSave = useCallback(() => {
    if (saveTimer) window.clearTimeout(saveTimer);
    const t = window.setTimeout(async () => {
      const el = containerRef.current;
      if (!el) return;
      const annotatedHtml = el.innerHTML;
      const spans = Array.from(el.querySelectorAll('span.highlight'));
      const highlights = spans.map((s, idx) => ({
        id: s.getAttribute('data-highlight-id') || `${idx}`,
        color: s.getAttribute('data-color') || '',
        startOffset: parseInt(s.getAttribute('data-start') || '0', 10),
        endOffset: parseInt(s.getAttribute('data-end') || '0', 10),
        selectedText: s.textContent || '',
        note: s.getAttribute('data-note') || undefined,
        createdAt: new Date().toISOString(),
      }));
      try {
        await highlightService.updateMessage(sessionId, message.id, {
          annotatedHtml,
          highlights,
        });
        // Re-fetch from backend to ensure we have the sanitized, persisted HTML
        try {
          const res = await highlightService.getMessage(sessionId, message.id);
          const data = res?.data;
          if (data?.annotatedHtml && containerRef.current) {
            containerRef.current.innerHTML = data.annotatedHtml;
            onUpdated?.({ annotatedHtml: data.annotatedHtml, highlights: data.highlights || highlights });
            setHasHighlights(Boolean((data.highlights||highlights||[]).length));
            // refresh text nodes cache
            const el2 = containerRef.current;
            const nodes = [];
            const walker = document.createTreeWalker(el2, NodeFilter.SHOW_TEXT, null);
            let n;
            while ((n = walker.nextNode())) nodes.push(n);
            textNodesRef.current = nodes;
          } else {
            onUpdated?.({ annotatedHtml, highlights });
          }
        } catch {
          onUpdated?.({ annotatedHtml, highlights });
          setHasHighlights(Boolean((highlights||[]).length));
        }
        try {
          const key = `maya:anno:${sessionId}:${message.id}`;
          rIC(() => {
            try { localStorage.setItem(key, JSON.stringify({ annotatedHtml, highlights })); } catch {}
          });
        } catch {}
        // Show a subtle saved hint near the message
        try {
          const rect = containerRef.current?.getBoundingClientRect?.();
          if (rect) setSavedHint({ x: rect.right - 12, y: rect.bottom + 8, text: 'Saved' });
          setTimeout(() => setSavedHint(null), 1200);
        } catch {}
      } catch (e) {
        // Network or server issue: fallback to localStorage
        try {
          const key = `maya:anno:${sessionId}:${message.id}`;
          rIC(() => {
            try { localStorage.setItem(key, JSON.stringify({ annotatedHtml, highlights })); } catch {}
          });
          onUpdated?.({ annotatedHtml, highlights });
          setHasHighlights(Boolean((highlights||[]).length));
          // Indicate offline save
          try {
            const rect = containerRef.current?.getBoundingClientRect?.();
            if (rect) setSavedHint({ x: rect.right - 12, y: rect.bottom + 8, text: 'Saved offline' });
            setTimeout(() => setSavedHint(null), 1400);
          } catch {}
        } catch {}
      }
    }, 800);
    setSaveTimer(t);
  }, [sessionId, message.id, onUpdated, saveTimer]);

  const openPaletteNearSelection = useCallback((target) => {
    const rect = target.getBoundingClientRect();
    let x = rect.left + rect.width / 2;
    let y = rect.top; // we'll translate popover above via CSS
    // Clamp to viewport with small margins
    const vw = Math.max(document.documentElement.clientWidth || 0, window.innerWidth || 0);
    const vh = Math.max(document.documentElement.clientHeight || 0, window.innerHeight || 0);
    const margin = 12;
    x = Math.min(vw - margin, Math.max(margin, x));
    y = Math.min(vh - margin, Math.max(margin, y));
    setPopover({ x, y, targetSpan: target });
  }, []);

  const openPaletteAt = useCallback((x, y, targetSpan = null) => {
    const vw = Math.max(document.documentElement.clientWidth || 0, window.innerWidth || 0);
    const vh = Math.max(document.documentElement.clientHeight || 0, window.innerHeight || 0);
    const margin = 12;
    const cx = Math.min(vw - margin, Math.max(margin, x));
    // Decide whether to render palette below selection when near the top edge
    const topClamp = Math.max(margin, Math.min(vh - margin, y));
    const cy = topClamp;
    const nearTop = topClamp < 64; // heuristic threshold
    setPopover({ x: cx, y: cy, targetSpan, below: nearTop });
  }, []);

  // Expose imperative method so ChatWindow can open the Highlights panel from its action bar
  useImperativeHandle(ref, () => ({
    openHighlightsAt: (x, y) => {
      // If coords not provided, default near the top-left of the message bubble
      let px = x, py = y;
      if ((px == null || py == null) && containerRef.current) {
        try {
          const rect = containerRef.current.getBoundingClientRect();
          px = rect.left + 16;
          py = rect.top + 32;
        } catch {}
      }
      const vw = Math.max(document.documentElement.clientWidth || 0, window.innerWidth || 0);
      const vh = Math.max(document.documentElement.clientHeight || 0, window.innerHeight || 0);
      const margin = 12;
      const cx = Math.min(vw - margin, Math.max(margin, px || 0));
      const cy = Math.min(vh - margin, Math.max(margin, (py || 0)));
      setHlPanel({ x: cx, y: cy });
    },
    openMiniAgent: async () => {
      try {
        const ensured = await miniAgentService.ensureThread(message.id);
        const thread = ensured?.data || {};
        setMiniThread(thread);
        setMiniOpen(true);
        setHasMini(true);
      } catch {}
    }
  }), []);

  const onMouseUp = useCallback(() => {
    const root = containerRef.current;
    if (!root) return;
    const sel = window.getSelection();
    if (!sel || sel.rangeCount === 0) return;
    const range = sel.getRangeAt(0);
    if (!range || sel.toString().trim().length === 0) {
      setPopover(null);
      setActionBar(null);
      return;
    }
    if (!within(range.commonAncestorContainer, root)) {
      setPopover(null);
      setActionBar(null);
      return;
    }
    // Show a small trigger icon above the selection; palette opens on hover/click
    let rect = range.getBoundingClientRect();
    if ((!rect || (rect.width === 0 && rect.height === 0)) && typeof range.getClientRects === 'function') {
      const first = range.getClientRects?.()[0];
      if (first) rect = first;
    }
    let x = rect.left + rect.width / 2;
    let y = rect.top; // action bar rendered above via CSS
    const vw = Math.max(document.documentElement.clientWidth || 0, window.innerWidth || 0);
    const vh = Math.max(document.documentElement.clientHeight || 0, window.innerHeight || 0);
    const margin = 12;
    x = Math.min(vw - margin, Math.max(margin, x));
    y = Math.min(vh - margin, Math.max(margin, y));
    setActionBar({ x, y, parentMessageId: message.id, selectedText: sel.toString() });
    setHasSelection(true);
    const offs = computeAbsoluteOffsets(root, range);

    // Attach temp data to remember range for apply
    root._pendingRange = range; // eslint-disable-line no-underscore-dangle
    root._pendingOffsets = { startOffset: offs.startOffset, endOffset: offs.endOffset }; // eslint-disable-line no-underscore-dangle
  }, []);

  // Helper: create a DOM Range from absolute offsets within root's text content
  const rangeFromOffsets = (root, start, end) => {
    const r = document.createRange();
    const nodes = textNodesRef.current && textNodesRef.current.length ? textNodesRef.current : (() => {
      const arr = [];
      const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, null);
      let n; while ((n = walker.nextNode())) arr.push(n);
      textNodesRef.current = arr; return arr;
    })();
    let acc = 0;
    let started = false;
    for (const node of nodes) {
      const len = node.nodeValue?.length || 0;
      if (!started && acc + len >= start) {
        r.setStart(node, Math.max(0, start - acc));
        started = true;
      }
      if (started && acc + len >= end) {
        r.setEnd(node, Math.max(0, end - acc));
        break;
      }
      acc += len;
    }
    return r;
  };

  const applyColor = useCallback((colorClass) => {
    const root = containerRef.current;
    if (!root) return;
    // If we're recoloring an existing span
    const t = popover?.targetSpan;
    if (t && t.nodeType === 1 && t.classList && t.classList.contains('highlight')) {
      t.className = `highlight ${colorClass}`;
      t.setAttribute('data-color', colorClass);
      scheduleSave();
      setPopover(null);
      setTrigger(null);
      return;
    }
    // Prefer stored absolute offsets to avoid issues if selection collapsed
    let startOffset, endOffset;
    if (root._pendingOffsets) { // eslint-disable-line no-underscore-dangle
      ({ startOffset, endOffset } = root._pendingOffsets); // eslint-disable-line no-underscore-dangle
    } else if (root._pendingRange) { // eslint-disable-line no-underscore-dangle
      const tmp = computeAbsoluteOffsets(root, root._pendingRange); // eslint-disable-line no-underscore-dangle
      startOffset = tmp.startOffset; endOffset = tmp.endOffset;
    } else {
      return;
    }
    // Normalize overlaps with existing highlights to avoid nesting
    const spans = Array.from(root.querySelectorAll('span.highlight'));
    for (const s of spans) {
      const sStart = parseInt(s.getAttribute('data-start') || '0', 10);
      const sEnd = parseInt(s.getAttribute('data-end') || '0', 10);
      const overlaps = Math.max(0, Math.min(endOffset, sEnd) - Math.max(startOffset, sStart)) > 0;
      if (!overlaps) continue;
      const text = s.textContent || '';
      if (startOffset <= sStart && sEnd <= endOffset) {
        // selection fully covers existing span -> unwrap safely
        safeUnwrap(s);
      } else if (startOffset <= sStart && endOffset < sEnd) {
        // trim left portion
        const cut = endOffset - sStart; if (cut > 0 && cut < text.length) {
          s.textContent = text.slice(cut);
          s.setAttribute('data-start', String(endOffset));
        }
      } else if (sStart < startOffset && sEnd <= endOffset) {
        // trim right portion
        const keep = startOffset - sStart; if (keep > 0 && keep <= text.length) {
          s.textContent = text.slice(0, keep);
          s.setAttribute('data-end', String(startOffset));
        }
      } else if (sStart < startOffset && endOffset < sEnd) {
        // split into left (keep), middle (removed), right (keep)
        const leftLen = startOffset - sStart;
        const rightStart = endOffset - sStart;
        const leftText = text.slice(0, leftLen);
        const rightText = text.slice(rightStart);
        const origColor = s.getAttribute('data-color') || '';
        const parent = s.parentNode;
        // left stays in s
        s.textContent = leftText;
        s.setAttribute('data-end', String(startOffset));
        // insert middle (plain)
        const midNode = document.createTextNode(text.slice(leftLen, rightStart));
        insertAfter(parent, midNode, s);
        // create right span
        const rightSpan = document.createElement('span');
        rightSpan.className = `highlight ${origColor}`.trim();
        rightSpan.setAttribute('data-color', origColor);
        rightSpan.setAttribute('data-start', String(endOffset));
        rightSpan.setAttribute('data-end', String(sEnd));
        rightSpan.textContent = rightText;
        insertAfter(parent, rightSpan, midNode);
      }
    }
    // Recompute text nodes cache after edits
    {
      const nodes = [];
      const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, null);
      let n; while ((n = walker.nextNode())) nodes.push(n);
      textNodesRef.current = nodes;
    }
    // Recreate range from absolute offsets (DOM changed above)
  const freshRange = rangeFromOffsets(root, startOffset, endOffset);
    const span = wrapSelection(freshRange, colorClass);
    const id = `${Date.now()}`;
    span.setAttribute('data-highlight-id', id);
    span.setAttribute('data-color', colorClass);
    span.setAttribute('data-start', String(startOffset));
    span.setAttribute('data-end', String(endOffset));
    scheduleSave();
    setPopover(null);
    setTrigger(null);
    const sel = window.getSelection();
    sel?.removeAllRanges();
  }, [scheduleSave, popover]);

  const removeHighlight = useCallback(() => {
    const root = containerRef.current;
    if (!root) return;
    const target = popover?.targetSpan;
    if (target && target.nodeType === 1 && target.classList && target.classList.contains('highlight')) {
      safeUnwrap(target);
      scheduleSave();
      setPopover(null);
      setTrigger(null);
      setHasHighlights(!!root.querySelector('span.highlight'));
      return;
    }
    // If no explicit targetSpan, remove highlights overlapping the current selection range
    const range = root._pendingRange; // eslint-disable-line no-underscore-dangle
    if (range) {
      const { startOffset, endOffset } = computeAbsoluteOffsets(root, range);
      const spans = Array.from(root.querySelectorAll('span.highlight'));
      for (const s of spans) {
        const sStart = parseInt(s.getAttribute('data-start') || '0', 10);
        const sEnd = parseInt(s.getAttribute('data-end') || '0', 10);
        const overlaps = Math.max(0, Math.min(endOffset, sEnd) - Math.max(startOffset, sStart)) > 0;
        if (!overlaps) continue;
        const text = s.textContent || '';
        if (startOffset <= sStart && sEnd <= endOffset) {
          // selection fully covers span -> unwrap safely
          safeUnwrap(s);
        } else if (startOffset <= sStart && endOffset < sEnd) {
          // trim left
          const cut = endOffset - sStart; if (cut > 0 && cut < text.length) {
            s.textContent = text.slice(cut);
            s.setAttribute('data-start', String(endOffset));
          }
        } else if (sStart < startOffset && sEnd <= endOffset) {
          // trim right
          const keep = startOffset - sStart; if (keep > 0 && keep <= text.length) {
            s.textContent = text.slice(0, keep);
            s.setAttribute('data-end', String(startOffset));
          }
        } else if (sStart < startOffset && endOffset < sEnd) {
          // split into left, remove middle, keep right
          const leftLen = startOffset - sStart;
          const rightStart = endOffset - sStart;
          const leftText = text.slice(0, leftLen);
          const rightText = text.slice(rightStart);
          const origColor = s.getAttribute('data-color') || '';
          const parent = s.parentNode;
          s.textContent = leftText;
          s.setAttribute('data-end', String(startOffset));
          const rightSpan = document.createElement('span');
          rightSpan.className = `highlight ${origColor}`.trim();
          rightSpan.setAttribute('data-color', origColor);
          rightSpan.setAttribute('data-start', String(endOffset));
          rightSpan.setAttribute('data-end', String(sEnd));
          rightSpan.textContent = rightText;
          insertAfter(parent, rightSpan, s);
          // Insert removed middle as plain text node between left and right
          const midNode = document.createTextNode(text.slice(leftLen, rightStart));
          parent && parent.insertBefore && parent.insertBefore(midNode, rightSpan);
        }
      }
      // refresh text nodes cache
      const nodes = [];
      const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, null);
      let n; while ((n = walker.nextNode())) nodes.push(n);
      textNodesRef.current = nodes;
      scheduleSave();
      setHasHighlights(!!root.querySelector('span.highlight'));
    }
    setPopover(null);
    setTrigger(null);
  }, [popover, scheduleSave]);

  const onMouseOver = useCallback((e) => {
    const root = containerRef.current;
    if (!root) return;
    const t = e.target;
    if (t && t.classList && t.classList.contains('highlight')) {
      openPaletteNearSelection(t);
    }
  }, [openPaletteNearSelection]);

  const openPaletteForCurrentSelection = useCallback(() => {
    const root = containerRef.current; if (!root) return;
    const sel = window.getSelection();
    if (!sel || sel.rangeCount === 0 || sel.isCollapsed) return;
    const range = sel.getRangeAt(0);
    if (!within(range.commonAncestorContainer, root)) return;
    let rect = range.getBoundingClientRect();
    if ((!rect || (rect.width === 0 && rect.height === 0)) && typeof range.getClientRects === 'function') {
      const first = range.getClientRects?.()[0];
      if (first) rect = first;
    }
    const vw = Math.max(document.documentElement.clientWidth || 0, window.innerWidth || 0);
    const vh = Math.max(document.documentElement.clientHeight || 0, window.innerHeight || 0);
    const margin = 12;
    const x = Math.min(vw - margin, Math.max(margin, rect.left + rect.width / 2));
    const y = Math.min(vh - margin, Math.max(margin, rect.top));
    openPaletteAt(x, y);
  }, [openPaletteAt]);

  return (
    <div className="ai-message" onMouseUp={onMouseUp} onMouseOver={onMouseOver}>
      <div ref={containerRef} className="ai-message-content" />
      {actionBar && createPortal(
        <SelectionActionBar
          x={actionBar.x}
          y={actionBar.y}
          onHighlight={() => openPaletteAt(actionBar.x, actionBar.y)}
          onMiniAgent={async () => {
            try {
              const ensured = await miniAgentService.ensureThread(actionBar.parentMessageId);
              const thread = ensured?.data || {};
              setMiniThread(thread);
              setMiniOpen(true);
              setHasMini(true);
            } catch {}
            setActionBar(null);
          }}
        />,
        document.body
      )}
      {popover && createPortal(
        <div role="dialog" aria-label="Highlight palette">
          <Popover x={popover.x} y={popover.y} below={!!popover.below} onPick={applyColor} onRemove={removeHighlight} />
        </div>,
        document.body
      )}
      {miniOpen && miniThread && createPortal(
        <MiniAgentPanel
          thread={miniThread}
          selectedText={actionBar?.selectedText || ''}
          onClose={() => setMiniOpen(false)}
        />,
        document.body
      )}
      {hlPanel && createPortal(
        <HighlightsPanel
          x={hlPanel.x}
          y={hlPanel.y}
          rootRef={containerRef}
          onClose={() => setHlPanel(null)}
          onChange={() => { scheduleSave(); /* update indicator */ setHasHighlights(!!containerRef.current?.querySelector('span.highlight')); }}
        />,
        document.body
      )}
      {savedHint && createPortal(
        <div className="hl-saved-hint" role="status" aria-live="polite" style={{ left: savedHint.x, top: savedHint.y }}>
          <span className="tick">✔</span>
          <span className="text">{savedHint.text}</span>
        </div>,
        document.body
      )}
      {/* Inline message actions row moved to ChatWindow */}
    </div>
  );
});

export default AIMessage;

// Inline AskPopup component
function AskPopup({ x, y, defaultValue, onConfirm, onCancel }) {
  const [value, setValue] = useState(defaultValue || '');
  const ref = useRef(null);
  useEffect(() => { setTimeout(() => ref.current?.querySelector('textarea')?.focus(), 0); }, []);
  useEffect(() => {
    const onDoc = (e) => { if (!ref.current) return; if (!e.target.closest || !e.target.closest('.ask-popover')) onCancel?.(); };
    const onKey = (e) => { if (e.key === 'Escape') onCancel?.(); if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); onConfirm?.(value.trim()); } };
    const onSel = () => onCancel?.();
    const onWin = () => onCancel?.();
    document.addEventListener('mousedown', onDoc);
    document.addEventListener('keydown', onKey);
    document.addEventListener('selectionchange', onSel);
    window.addEventListener('scroll', onWin, true);
    window.addEventListener('resize', onWin);
    return () => {
      document.removeEventListener('mousedown', onDoc);
      document.removeEventListener('keydown', onKey);
      document.removeEventListener('selectionchange', onSel);
      window.removeEventListener('scroll', onWin, true);
      window.removeEventListener('resize', onWin);
    };
  }, [onCancel, onConfirm, value]);
  const vw = Math.max(document.documentElement.clientWidth || 0, window.innerWidth || 0);
  const margin = 12;
  const cx = Math.min(vw - margin, Math.max(margin, x));
  return (
    <div className="ask-popover" ref={ref} style={{ left: cx, top: y }} role="dialog" aria-label="Add highlight note">
      <textarea
        aria-label="Highlight text"
        value={value}
        onChange={(e) => setValue(e.target.value)}
        rows={3}
        placeholder="Edit note or keep selected text…"
      />
      <div className="ask-actions">
        <button className="ask-confirm" onClick={() => onConfirm?.(value.trim())}>Confirm</button>
        <button className="ask-cancel" onClick={() => onCancel?.()}>Cancel</button>
        <button className="ask-close" aria-label="Close" title="Close" onClick={() => onCancel?.()}>×</button>
      </div>
    </div>
  );
}

// Inline Highlights Panel
function HighlightsPanel({ x, y, rootRef, onClose, onChange }) {
  const [items, setItems] = useState([]);
  const ref = useRef(null);
  const refresh = useCallback(() => {
    const root = rootRef.current; if (!root) return;
    const spans = Array.from(root.querySelectorAll('span.highlight'));
    const mapped = spans.map((s) => ({ id: s.getAttribute('data-highlight-id'), text: s.textContent||'', note: s.getAttribute('data-note')||'' }));
    setItems(mapped);
  }, [rootRef]);
  useEffect(() => { refresh(); }, [refresh]);
  useEffect(() => {
    const onDoc = (e) => { if (!ref.current) return; if (!e.target.closest || !e.target.closest('.hl-panel')) onClose?.(); };
    document.addEventListener('mousedown', onDoc);
    return () => document.removeEventListener('mousedown', onDoc);
  }, [onClose]);
  const onDelete = (id) => {
    const root = rootRef.current; if (!root) return;
    const span = root.querySelector(`span.highlight[data-highlight-id="${CSS.escape(id)}"]`);
    if (span) { safeUnwrap(span); onChange?.(); refresh(); }
  };
  const onUpdateNote = (id, note) => {
    const root = rootRef.current; if (!root) return;
    const span = root.querySelector(`span.highlight[data-highlight-id="${CSS.escape(id)}"]`);
    if (span) { if (note) span.setAttribute('data-note', note); else span.removeAttribute('data-note'); onChange?.(); refresh(); }
  };
  const vw = Math.max(document.documentElement.clientWidth || 0, window.innerWidth || 0);
  const margin = 12; const cx = Math.min(vw - margin, Math.max(margin, x));
  return (
    <div className="hl-panel" ref={ref} style={{ left: cx, top: y }} role="dialog" aria-label="Highlights">
      <div className="hl-list">
        {items.length === 0 && <div className="hl-empty">No highlights yet.</div>}
        {items.map((it) => (
          <div className="hl-item" key={it.id}>
            <div className="hl-text" title={it.text}>{it.text.length>90?it.text.slice(0,90)+'…':it.text}</div>
            <input className="hl-note" placeholder="Note…" value={it.note} onChange={(e)=>onUpdateNote(it.id, e.target.value)} />
            <button className="hl-del" onClick={()=>onDelete(it.id)} title="Delete">🗑</button>
          </div>
        ))}
      </div>
      <div className="hl-actions"><button onClick={onClose}>Close</button></div>
    </div>
  );
}
