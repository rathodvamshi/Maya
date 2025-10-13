import React, { useEffect, useRef, useState } from 'react';
import { useVideoPiP } from '../context/VideoPiPContext';
import videoControls from '../services/videoControlsService';

export default function VideoMiniPlayer() {
  const { pipActive, video, clear, restore, setVideo } = useVideoPiP();
  const [pos, setPos] = useState({ x: 16, y: 16 });
  const dragging = useRef(false);
  const start = useRef({ x: 0, y: 0 });
  const rootRef = useRef(null);

  useEffect(() => {
    function onMove(e) {
      if (!dragging.current) return;
      const dx = (e.touches?.[0]?.clientX ?? e.clientX) - start.current.x;
      const dy = (e.touches?.[0]?.clientY ?? e.clientY) - start.current.y;
      setPos(prev => ({ x: Math.max(8, prev.x + dx), y: Math.max(8, prev.y + dy) }));
      start.current = { x: (e.touches?.[0]?.clientX ?? e.clientX), y: (e.touches?.[0]?.clientY ?? e.clientY) };
    }
    function onUp() { dragging.current = false; }
    window.addEventListener('mousemove', onMove);
    window.addEventListener('mouseup', onUp);
    window.addEventListener('touchmove', onMove);
    window.addEventListener('touchend', onUp);
    return () => {
      window.removeEventListener('mousemove', onMove);
      window.removeEventListener('mouseup', onUp);
      window.removeEventListener('touchmove', onMove);
      window.removeEventListener('touchend', onUp);
    };
  }, []);

  if (!pipActive || !video?.videoId) return null;

  const style = {
    position: 'fixed',
    right: pos.x,
    bottom: pos.y,
    width: 320,
    maxWidth: '80vw',
    borderRadius: 12,
    overflow: 'hidden',
    border: '1px solid #e5e7eb',
    background: '#111',
    zIndex: 9999,
    boxShadow: '0 8px 24px rgba(0,0,0,0.25)'
  };
  const src = `https://www.youtube-nocookie.com/embed/${video.videoId}?rel=0&modestbranding=1&playsinline=1&autoplay=1`;

  const control = async (action) => {
    const res = await videoControls.sendControl(action, { videoId: video.videoId, title: video.title, sessionId: video.sessionId });
    if (res?.video?.videoId) {
      // swap video to next via context setter
      setVideo({ ...video, videoId: res.video.videoId, title: res.video.title });
    }
    // We could show a toast with res.response_text
  };

  return (
    <div ref={rootRef} style={style} role="dialog" aria-label="Video mini player">
      <div
        style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '6px 10px', background: '#1f2937', color: 'white', cursor: 'move' }}
        onMouseDown={(e) => { dragging.current = true; start.current = { x: e.clientX, y: e.clientY }; }}
        onTouchStart={(e) => { const t = e.touches?.[0]; dragging.current = true; start.current = { x: t.clientX, y: t.clientY }; }}
      >
        <span style={{ fontSize: 12, opacity: 0.9 }}>▷ {video.title || 'Now Playing'}</span>
        <div style={{ marginLeft: 'auto', display: 'flex', gap: 6 }}>
          <button onClick={() => control('pause')} title="Pause" style={btnStyle}>⏸️</button>
          <button onClick={() => control('replay')} title="Replay" style={btnStyle}>🔁</button>
          <button onClick={() => control('next')} title="Next" style={btnStyle}>⏭️</button>
          <button onClick={() => { clear(); }} title="Close" style={btnStyle}>✖️</button>
        </div>
      </div>
      <div style={{ width: '100%', aspectRatio: '16 / 9', background: '#000' }} onClick={restore}>
        <iframe
          title={video.title || 'Mini player'}
          src={src}
          allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share"
          referrerPolicy="strict-origin-when-cross-origin"
          allowFullScreen
          style={{ width: '100%', height: '100%', border: 0, display: 'block' }}
        />
      </div>
    </div>
  );
}

const btnStyle = {
  padding: '4px 6px',
  borderRadius: 6,
  border: '1px solid #374151',
  background: '#111827',
  color: 'white',
  cursor: 'pointer',
};