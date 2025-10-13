import React from 'react';

export default function SelectionActionBar({ x, y, onHighlight, onMiniAgent }) {
  return (
    <div className="highlight-popover" style={{ left: x, top: y }} role="toolbar" aria-label="Selection actions">
      <button className="palette-remove" title="Highlight" aria-label="Highlight" onClick={onHighlight}>
        ✏️
      </button>
      <button className="palette-remove" title="Mini Agent" aria-label="Open Mini Agent" onClick={onMiniAgent}>
        🤖
      </button>
    </div>
  );
}
