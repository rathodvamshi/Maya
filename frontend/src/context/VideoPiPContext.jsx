import React, { createContext, useCallback, useContext, useMemo, useRef, useState } from 'react';

const VideoPiPContext = createContext(null);

export function VideoPiPProvider({ children }) {
  const [pipActive, setPipActive] = useState(false);
  const [video, setVideo] = useState(null); // { videoId, title, sessionId }
  const restoreRef = useRef(null); // function to scroll back to anchor

  const activate = useCallback((payload, restoreFn) => {
    setVideo(payload);
    restoreRef.current = typeof restoreFn === 'function' ? restoreFn : null;
    setPipActive(true);
  }, []);

  const deactivate = useCallback(() => {
    setPipActive(false);
  }, []);

  const clear = useCallback(() => {
    setPipActive(false);
    setVideo(null);
    restoreRef.current = null;
  }, []);

  const restore = useCallback(() => {
    if (restoreRef.current) restoreRef.current();
  }, []);

  const value = useMemo(() => ({
    pipActive,
    video,
    setVideo,
    activate,
    deactivate,
    clear,
    restore,
  }), [pipActive, video, activate, deactivate, clear, restore]);

  return (
    <VideoPiPContext.Provider value={value}>{children}</VideoPiPContext.Provider>
  );
}

export function useVideoPiP() {
  const ctx = useContext(VideoPiPContext);
  if (!ctx) throw new Error('useVideoPiP must be used within a VideoPiPProvider');
  return ctx;
}

export default VideoPiPContext;