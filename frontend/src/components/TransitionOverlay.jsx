import React, { useEffect, useState } from 'react';
import { useLocation } from 'react-router-dom';
import { AnimatePresence, motion, useReducedMotion } from 'framer-motion';

// A subtle, non-blocking shimmer/blur overlay shown briefly on route changes
export default function TransitionOverlay() {
  const location = useLocation();
  const [show, setShow] = useState(false);
  const prefersReduced = useReducedMotion();

  useEffect(() => {
    // Briefly show during route change; cancel quickly if user navigates fast
    setShow(true);
    const hide = setTimeout(() => setShow(false), prefersReduced ? 120 : 220);
    return () => clearTimeout(hide);
  }, [location.pathname, prefersReduced]);

  return (
    <AnimatePresence>
      {show && (
        <motion.div
          className="route-transition-overlay"
          initial={{ opacity: 0 }}
          animate={{ opacity: prefersReduced ? 0 : 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.18 }}
          aria-hidden
        >
          {!prefersReduced && <div className="route-transition-shimmer" />}
        </motion.div>
      )}
    </AnimatePresence>
  );
}
