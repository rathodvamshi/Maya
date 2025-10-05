import { useState, useCallback, useEffect, useRef } from 'react';

// Custom hook to capture text selections while ignoring interactions
// inside the inline agent UI (chat, menu, color picker, etc.).
export const useTextSelection = () => {
  const [selection, setSelection] = useState(null);
  const lastNonNull = useRef(null);

  const isInsideInlineAgent = (target) => {
    if (!target) return false;
    return !!target.closest('[data-inline-agent-ui="true"]');
  };

  const handleMouseUp = useCallback((e) => {
    // If clicking inside inline agent UI, don't clear current selection
    if (isInsideInlineAgent(e.target)) {
      return; // preserve existing selection
    }
    const currentSelection = window.getSelection();
    if (!currentSelection) return;
    const selectedText = currentSelection.toString().trim();

    if (selectedText && currentSelection.rangeCount > 0) {
      const range = currentSelection.getRangeAt(0);
      const rect = range.getBoundingClientRect();
      const stored = {
        text: selectedText,
        rect: {
          top: rect.top + window.scrollY,
          left: rect.left + window.scrollX,
          bottom: rect.bottom + window.scrollY,
          right: rect.right + window.scrollX,
        },
        range,
      };
      lastNonNull.current = stored;
      setSelection(stored);
    } else {
      // Clear selection only if there is no prior active usage (e.g., chat open will manage separately)
      setSelection(null);
    }
  }, []);

  useEffect(() => {
    document.addEventListener('mouseup', handleMouseUp);
    return () => {
      document.removeEventListener('mouseup', handleMouseUp);
    };
  }, [handleMouseUp]);

  return selection;
};
