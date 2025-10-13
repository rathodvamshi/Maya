
// Yes. It shows an animated “AI is thinking” progress sequence while the app waits for the model’s reply, giving users visual feedback that processing steps are happening.


// AI Thinking/Processing Indicator Component
import React, { useState, useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { 
  Send, 
  Brain, 
  RefreshCw, 
  FolderOpen, 
  Search, 
  Sparkles,
  MessageSquare,
  Check 
} from 'lucide-react';

const PROCESSING_STEPS = [
  {
    id: 'sending',
    icon: Send,
    text: 'Sending request to server...',
    duration: 800,
    color: '#3b82f6'
  },
  {
    id: 'nlu',
    icon: Brain,
    text: 'Extracting intent & entities...',
    duration: 900,
    color: '#8b5cf6'
  },
  {
    id: 'dialogue',
    icon: RefreshCw,
    text: 'Dialogue Manager deciding next step...',
    duration: 700,
    color: '#06b6d4'
  },
  {
    id: 'memory',
    icon: FolderOpen,
    text: 'Checking short-term memory...',
    duration: 600,
    color: '#10b981'
  },
  {
    id: 'retrieval',
    icon: Search,
    text: 'Retrieving external knowledge...',
    duration: 800,
    color: '#f59e0b'
  },
  {
    id: 'generation',
    icon: Sparkles,
    text: 'Composing AI response...',
    duration: 1000,
    color: '#ef4444'
  },
  {
    id: 'streaming',
    icon: MessageSquare,
    text: 'Streaming reply...',
    duration: 500,
    color: '#22c55e'
  }
];

const AIThinkingIndicator = ({ 
  isActive = false, 
  onComplete, 
  fastMode = true,
  showDetails = false,
  enableSounds = false 
}) => {
  const [currentStep, setCurrentStep] = useState(0);
  const [completedSteps, setCompletedSteps] = useState(new Set());
  const [isVisible, setIsVisible] = useState(false);
  const timeoutRef = useRef(null);
  const startTimeRef = useRef(null);

  // Speed multiplier for fast processing
  const speedMultiplier = fastMode ? 0.4 : 1;

  useEffect(() => {
    if (isActive) {
      setIsVisible(true);
      setCurrentStep(0);
      setCompletedSteps(new Set());
      startTimeRef.current = Date.now();
      processNextStep(0);
    } else {
      setIsVisible(false);
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
      }
    }

    return () => {
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
      }
    };
  }, [isActive]);

  const processNextStep = (stepIndex) => {
    if (stepIndex >= PROCESSING_STEPS.length) {
      // All steps complete - mark final completion but stay visible until parent hides
      setCompletedSteps(prev => new Set([...prev, PROCESSING_STEPS.length - 1]));
      
      if (enableSounds) {
        // Optional: Play a subtle completion sound
        try {
          const audioContext = new (window.AudioContext || window.webkitAudioContext)();
          const oscillator = audioContext.createOscillator();
          const gainNode = audioContext.createGain();
          
          oscillator.connect(gainNode);
          gainNode.connect(audioContext.destination);
          
          oscillator.frequency.value = 800;
          oscillator.type = 'sine';
          gainNode.gain.value = 0.1;
          
          oscillator.start();
          oscillator.stop(audioContext.currentTime + 0.1);
        } catch (error) {
          // Silent fail if audio not supported
        }
      }
      
      // Signal completion but don't auto-hide
      onComplete?.();
      return;
    }

    const step = PROCESSING_STEPS[stepIndex];
    const duration = step.duration * speedMultiplier;

    timeoutRef.current = setTimeout(() => {
      // Mark current step as completed
      setCompletedSteps(prev => new Set([...prev, stepIndex]));
      
      // Move to next step after a brief pause
      setTimeout(() => {
        if (stepIndex < PROCESSING_STEPS.length - 1) {
          setCurrentStep(stepIndex + 1);
          processNextStep(stepIndex + 1);
        } else {
          // Final step - wait for external completion signal
          setCompletedSteps(prev => new Set([...prev, stepIndex]));
          // Don't auto-hide - wait for parent to call onComplete or set isActive to false
        }
      }, 150);
    }, duration);
  };

  if (!isVisible) return null;

  const currentStepData = PROCESSING_STEPS[currentStep];
  const progress = ((currentStep + 1) / PROCESSING_STEPS.length) * 100;

  return (
    <motion.div
      className="ai-thinking-indicator"
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -10 }}
      transition={{ duration: 0.2 }}
    >
      <div className="thinking-container">
        {/* Progress bar */}
        <div className="thinking-progress-bar">
          <motion.div
            className="thinking-progress-fill"
            initial={{ width: 0 }}
            animate={{ width: `${progress}%` }}
            transition={{ duration: 0.3, ease: "easeOut" }}
          />
        </div>

        {/* Current step */}
        <AnimatePresence mode="wait">
          <motion.div
            key={currentStep}
            className="thinking-step"
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: -20 }}
            transition={{ duration: 0.2 }}
          >
            <div className="thinking-step-content">
              <motion.div
                className={`thinking-icon ${currentStepData.id === 'generation' ? 'sparkle' : ''}`}
                style={{ color: currentStepData.color }}
                animate={{ 
                  rotate: currentStepData.id === 'dialogue' ? 360 : 0,
                  scale: currentStepData.id === 'generation' ? [1, 1.1, 1] : 1
                }}
                transition={{ 
                  duration: currentStepData.id === 'dialogue' ? 2 : 
                           currentStepData.id === 'generation' ? 1 : 0,
                  repeat: currentStepData.id === 'dialogue' || currentStepData.id === 'generation' ? Infinity : 0,
                  ease: "linear"
                }}
              >
                <currentStepData.icon size={18} />
              </motion.div>
              
              <motion.span
                className="thinking-text"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ duration: 0.3, delay: 0.1 }}
              >
                {currentStepData.text}
              </motion.span>

              {/* Completion checkmark */}
              <AnimatePresence>
                {completedSteps.has(currentStep) && (
                  <motion.div
                    className="thinking-check"
                    initial={{ scale: 0, opacity: 0 }}
                    animate={{ scale: 1, opacity: 1 }}
                    exit={{ scale: 0, opacity: 0 }}
                    transition={{ duration: 0.2 }}
                  >
                    <Check size={14} />
                  </motion.div>
                )}
              </AnimatePresence>
            </div>

            {/* Animated dots for active step */}
            {!completedSteps.has(currentStep) && (
              <div className="thinking-dots">
                <motion.span
                  animate={{ opacity: [0.3, 1, 0.3] }}
                  transition={{ duration: 0.8, repeat: Infinity, delay: 0 }}
                >
                  •
                </motion.span>
                <motion.span
                  animate={{ opacity: [0.3, 1, 0.3] }}
                  transition={{ duration: 0.8, repeat: Infinity, delay: 0.2 }}
                >
                  •
                </motion.span>
                <motion.span
                  animate={{ opacity: [0.3, 1, 0.3] }}
                  transition={{ duration: 0.8, repeat: Infinity, delay: 0.4 }}
                >
                  •
                </motion.span>
              </div>
            )}
          </motion.div>
        </AnimatePresence>

        {/* Optional detailed view */}
        {showDetails && (
          <div className="thinking-details">
            {PROCESSING_STEPS.map((step, index) => (
              <div
                key={step.id}
                className={`thinking-detail-step ${
                  index < currentStep ? 'completed' : 
                  index === currentStep ? 'active' : 'pending'
                }`}
              >
                <step.icon size={12} />
                <span>{step.text}</span>
                {completedSteps.has(index) && <Check size={10} />}
              </div>
            ))}
          </div>
        )}

        {/* Subtle glow effect */}
        <motion.div
          className="thinking-glow"
          animate={{ 
            opacity: [0.3, 0.7, 0.3],
            scale: [0.95, 1.05, 0.95]
          }}
          transition={{ 
            duration: 2, 
            repeat: Infinity, 
            ease: "easeInOut" 
          }}
        />
      </div>
    </motion.div>
  );
};

export default AIThinkingIndicator;