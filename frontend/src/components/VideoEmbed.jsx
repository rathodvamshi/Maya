// frontend/src/components/VideoEmbed.jsx
import React from 'react';

export default function VideoEmbed({ videoId, title, autoplay = false }) {
  if (!videoId) return null;
  const qp = new URLSearchParams({ rel: '0', modestbranding: '1', playsinline: '1', enablejsapi: '1' });
  if (autoplay) {
    qp.set('autoplay', '1');
    // Mute to satisfy most browsers' autoplay policies; users can unmute in the player
    qp.set('mute', '1');
  }
  const src = `https://www.youtube-nocookie.com/embed/${videoId}?${qp.toString()}`;
  return (
    <div className="yt-embed" style={{
      position: 'relative',
      width: '100%',
      maxWidth: 720,
      borderRadius: 12,
      overflow: 'hidden',
      border: '1px solid var(--border, #e5e7eb)',
      background: '#000',
      aspectRatio: '16 / 9'
    }}>
      <iframe
        title={title || 'YouTube video'}
        src={src}
        allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share"
        referrerPolicy="strict-origin-when-cross-origin"
        allowFullScreen
        style={{ width: '100%', height: '100%', border: 0, display: 'block' }}
      />
    </div>
  );
}
