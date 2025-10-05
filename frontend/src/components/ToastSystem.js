// Toast System Component for Non-blocking Notifications
import React, { useState, useEffect, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import '../styles/ToastSystem.css';
import { 
  CheckCircle, 
  AlertCircle, 
  Info, 
  AlertTriangle, 
  X 
} from 'lucide-react';

// Toast types and their configurations
const TOAST_TYPES = {
  success: {
    icon: CheckCircle,
    className: 'success',
    defaultDuration: 4000
  },
  error: {
    icon: AlertCircle,
    className: 'error',
    defaultDuration: 6000
  },
  warning: {
    icon: AlertTriangle,
    className: 'warning',
    defaultDuration: 5000
  },
  info: {
    icon: Info,
    className: 'info',
    defaultDuration: 4000
  }
};

// Global toast state and methods
let toastId = 0;
let globalToasts = [];
let globalSetToasts = null;

// Public API for creating toasts
export const toast = {
  success: (message, options = {}) => addToast('success', message, options),
  error: (message, options = {}) => addToast('error', message, options),
  warning: (message, options = {}) => addToast('warning', message, options),
  info: (message, options = {}) => addToast('info', message, options),
  dismiss: (id) => removeToast(id),
  dismissAll: () => clearAllToasts()
};

const addToast = (type, message, options = {}) => {
  const id = ++toastId;
  const toastConfig = TOAST_TYPES[type];
  
  const newToast = {
    id,
    type,
    message,
    timestamp: Date.now(),
    duration: options.duration ?? toastConfig.defaultDuration,
    persistent: options.persistent || false,
    action: options.action || null,
    ...options
  };

  // Prevent duplicate toasts
  const isDuplicate = globalToasts.some(toast => 
    toast.message === message && toast.type === type && 
    Date.now() - toast.timestamp < 1000
  );

  if (isDuplicate) return;

  // Limit to 3 toasts maximum
  if (globalToasts.length >= 3) {
    globalToasts = globalToasts.slice(1);
  }

  globalToasts = [...globalToasts, newToast];
  
  if (globalSetToasts) {
    globalSetToasts([...globalToasts]);
  }

  // Auto-dismiss if not persistent
  if (!newToast.persistent) {
    setTimeout(() => {
      removeToast(id);
    }, newToast.duration);
  }

  return id;
};

const removeToast = (id) => {
  globalToasts = globalToasts.filter(toast => toast.id !== id);
  if (globalSetToasts) {
    globalSetToasts([...globalToasts]);
  }
};

const clearAllToasts = () => {
  globalToasts = [];
  if (globalSetToasts) {
    globalSetToasts([]);
  }
};

// Individual Toast Component
const ToastItem = ({ toast: toastData, onDismiss }) => {
  const [isVisible, setIsVisible] = useState(true);
  const [reducedMotion, setReducedMotion] = useState(false);
  const [progress, setProgress] = useState(100);

  const toastConfig = TOAST_TYPES[toastData.type];
  const Icon = toastConfig.icon;

  useEffect(() => {
    // Check reduced motion preference
    const hasReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches ||
                            localStorage.getItem('maya-reduced-motion') === 'true';
    setReducedMotion(hasReducedMotion);
  }, []);

  // Progress bar animation
  useEffect(() => {
    if (toastData.persistent) return;

    const startTime = Date.now();
    const endTime = startTime + toastData.duration;

    const updateProgress = () => {
      const now = Date.now();
      const remaining = Math.max(0, endTime - now);
      const progressPercent = (remaining / toastData.duration) * 100;
      
      setProgress(progressPercent);

      if (progressPercent > 0) {
        requestAnimationFrame(updateProgress);
      }
    };

    updateProgress();
  }, [toastData.duration, toastData.persistent]);

  const handleDismiss = () => {
    setIsVisible(false);
    setTimeout(() => {
      onDismiss(toastData.id);
    }, reducedMotion ? 0 : 150);
  };

  const handleAction = () => {
    if (toastData.action && toastData.action.callback) {
      toastData.action.callback();
      if (toastData.action.dismissOnAction !== false) {
        handleDismiss();
      }
    }
  };

  // Animation variants
  const toastVariants = {
    initial: { 
      opacity: 0, 
      x: reducedMotion ? 0 : 100, 
      scale: reducedMotion ? 1 : 0.9 
    },
    animate: { 
      opacity: 1, 
      x: 0, 
      scale: 1,
      transition: { 
        duration: reducedMotion ? 0 : 0.3,
        ease: [0.4, 0.0, 0.2, 1]
      }
    },
    exit: { 
      opacity: 0, 
      x: reducedMotion ? 0 : 100, 
      scale: reducedMotion ? 1 : 0.9,
      transition: { 
        duration: reducedMotion ? 0 : 0.2 
      }
    }
  };

  if (!isVisible) return null;

  return (
    <motion.div
      className={`toast-item ${toastConfig.className}`}
      variants={toastVariants}
      initial="initial"
      animate="animate"
      exit="exit"
      layout
      role="status"
      aria-live="polite"
      aria-atomic="true"
    >
      {/* Progress bar */}
      {!toastData.persistent && (
        <div className="toast-progress">
          <motion.div
            className="toast-progress-bar"
            initial={{ width: '100%' }}
            animate={{ width: `${progress}%` }}
            transition={{ duration: 0.1, ease: 'linear' }}
          />
        </div>
      )}

      {/* Content */}
      <div className="toast-content">
        <div className="toast-icon">
          <Icon size={20} />
        </div>
        
        <div className="toast-body">
          <div className="toast-message">
            {toastData.message}
          </div>
          
          {toastData.description && (
            <div className="toast-description">
              {toastData.description}
            </div>
          )}
        </div>

        {/* Action button */}
        {toastData.action && (
          <button
            className="toast-action"
            onClick={handleAction}
            aria-label={toastData.action.label}
          >
            {toastData.action.label}
          </button>
        )}

        {/* Dismiss button */}
        <button
          className="toast-dismiss"
          onClick={handleDismiss}
          aria-label="Dismiss notification"
        >
          <X size={16} />
        </button>
      </div>
    </motion.div>
  );
};

// Main Toast System Component
const ToastSystem = () => {
  const [toasts, setToasts] = useState([]);
  const [reducedMotion, setReducedMotion] = useState(false);

  useEffect(() => {
    // Register global setter
    globalSetToasts = setToasts;
    
    // Initialize with existing toasts
    setToasts([...globalToasts]);

    // Check reduced motion preference
    const hasReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches ||
                            localStorage.getItem('maya-reduced-motion') === 'true';
    setReducedMotion(hasReducedMotion);

    // Cleanup on unmount
    return () => {
      globalSetToasts = null;
    };
  }, []);

  const handleDismiss = useCallback((id) => {
    removeToast(id);
  }, []);

  // Container animation variants
  const containerVariants = {
    initial: {},
    animate: {
      transition: {
        staggerChildren: reducedMotion ? 0 : 0.1
      }
    }
  };

  return (
    <div className="toast-system">
      <AnimatePresence mode="popLayout">
        {toasts.length > 0 && (
          <motion.div
            className="toast-container"
            variants={containerVariants}
            initial="initial"
            animate="animate"
            exit="exit"
          >
            <AnimatePresence mode="popLayout">
              {toasts.map((toast) => (
                <ToastItem
                  key={toast.id}
                  toast={toast}
                  onDismiss={handleDismiss}
                />
              ))}
            </AnimatePresence>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
};

// Hook for using toasts in components
export const useToast = () => {
  return {
    toast,
    showSuccess: (message, options) => toast.success(message, options),
    showError: (message, options) => toast.error(message, options),
    showWarning: (message, options) => toast.warning(message, options),
    showInfo: (message, options) => toast.info(message, options),
    dismiss: toast.dismiss,
    dismissAll: toast.dismissAll
  };
};

// Demo component for testing
export const ToastDemo = () => {
  const { showSuccess, showError, showWarning, showInfo } = useToast();

  const demoToasts = [
    {
      label: 'Success',
      action: () => showSuccess('Task completed successfully!'),
      className: 'demo-success'
    },
    {
      label: 'Error',
      action: () => showError('Failed to save changes. Please try again.', {
        action: {
          label: 'Retry',
          callback: () => console.log('Retrying...'),
        }
      }),
      className: 'demo-error'
    },
    {
      label: 'Warning',
      action: () => showWarning('Your session will expire in 5 minutes.', {
        action: {
          label: 'Extend',
          callback: () => console.log('Extending session...'),
        }
      }),
      className: 'demo-warning'
    },
    {
      label: 'Info',
      action: () => showInfo('New features are available!', {
        description: 'Click to learn more about the latest updates.',
        action: {
          label: 'Learn More',
          callback: () => console.log('Opening features page...'),
        }
      }),
      className: 'demo-info'
    },
    {
      label: 'Persistent',
      action: () => showError('Critical error requires attention', {
        persistent: true,
        description: 'This notification will not auto-dismiss.'
      }),
      className: 'demo-persistent'
    }
  ];

  return (
    <div className="toast-demo">
      <h3>Toast Demo</h3>
      <div className="demo-buttons">
        {demoToasts.map((demo, index) => (
          <button
            key={index}
            className={`demo-button ${demo.className}`}
            onClick={demo.action}
          >
            {demo.label}
          </button>
        ))}
      </div>
    </div>
  );
};

export default ToastSystem;