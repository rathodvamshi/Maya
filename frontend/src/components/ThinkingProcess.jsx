import React, { useEffect, useRef, useState } from 'react';
import PropTypes from 'prop-types';
import '../styles/ThinkingProcess.css';

/**
 * ThinkingProcess
 * Animated multi-stage cognitive pipeline visualization.
 */
const DEFAULT_STEPS = [
  '💭 Thinking...',
  '🔄 Sending to Backend...',
  '🧩 Extracting Intent & Entities (NLU Stage)...',
  '🧠 Injecting into LLM (Reasoning Engine)...',
  '⚡ Searching in Short-Term Memory...',
  '🗂️ Searching in Long-Term Memory...',
  '🌐 Searching in Semantic Memory...',
  '🔍 Querying External API: {api}...',
  '🗣️ Passing to NLG (Natural Language Generation)...',
  '✨ Generating Response...',
  '🚀 Finalizing Output...'
];

const randomize = (min, max) => Math.floor(Math.random() * (max - min + 1)) + min;

const ThinkingProcess = ({
  apiName = 'YouTube API',
  onComplete,
  minDelay = 350,
  maxDelay = 650,
  enablePulse = true,
  developerMode = false,
  cancelRef,
  loop = true,
  variant = 'overlay', // 'overlay' | 'inline'
  className = '',
  showElapsed = true,
  startTime,
}) => {
  const [index, setIndex] = useState(0);
  const [cycles, setCycles] = useState(0);
  const [stopped, setStopped] = useState(false);
  const timeoutRef = useRef(null);

  const steps = DEFAULT_STEPS.map(s => s.replace('{api}', apiName));

  useEffect(() => {
    if (stopped) return;
    // If loop is disabled, finish after one pass
    const atEnd = index >= steps.length;
    if (atEnd) {
      if (loop) {
        setCycles(c => c + 1);
        setIndex(0); // restart immediately (fast feel)
      } else {
        setStopped(true);
        onComplete?.();
        return;
      }
    }
    const delay = randomize(minDelay, maxDelay);
    timeoutRef.current = setTimeout(() => {
      setIndex(i => i + 1);
    }, delay);
    return () => clearTimeout(timeoutRef.current);
  }, [index, loop, steps.length, minDelay, maxDelay, onComplete, stopped]);

  // Allow external cancellation (e.g., once backend response begins streaming)
  useEffect(() => {
    if (cancelRef) {
      cancelRef.current = () => {
        clearTimeout(timeoutRef.current);
        setStopped(true);
        onComplete?.();
      };
    }
  }, [cancelRef, onComplete]);

  const effectiveIndex = Math.min(index, steps.length - 1);
  const current = steps[effectiveIndex];
  const progress = loop ? undefined : (index / steps.length) * 100;
  const [elapsed, setElapsed] = useState(0);

  // Track elapsed seconds (updates every 200ms for smoother display)
  useEffect(() => {
    if (!showElapsed) return;
    const base = startTime || Date.now();
    const id = setInterval(() => {
      setElapsed(((Date.now() - base) / 1000));
    }, 200);
    return () => clearInterval(id);
  }, [showElapsed, startTime]);

  if (variant === 'inline') {
    return (
      <div className={`thinking-inline message ai ${className}`.trim()} role="status" aria-live="polite">
        <div className="message-bubble thinking-inline-bubble">
          <div className="thinking-inline-wrap">
            <div key={current} className="thinking-line-anim">
              <span className="thinking-gradient-text inline-text">{current}</span>
            </div>
            <div className="thinking-dots-flow sm" aria-hidden="true">
              <span /> <span /> <span />
            </div>
            <div className="thinking-progress-bar thin">
              <div
                className={"thinking-progress-fill" + (loop ? ' indeterminate' : '')}
                style={!loop ? { width: `${progress}%` } : undefined}
              />
            </div>
            {developerMode && (
              <div className="thinking-dev-info">
                Step {effectiveIndex + 1} / {steps.length} {loop ? `(cycles: ${cycles})` : ''}
              </div>
            )}
            {showElapsed && (
              <div className="thinking-elapsed" aria-label={`Elapsed processing time ${elapsed.toFixed(1)} seconds`}>
                {elapsed.toFixed(1)}s
              </div>
            )}
          </div>
        </div>
      </div>
    );
  }

  return (
      <div className="thinking-overlay" role="status" aria-live="assertive">
        <div className="thinking-core">
          {enablePulse && <div className="neural-pulse" />}
          <div className="thinking-text-wrap">
            <div key={current} className="thinking-line-anim">
              <span className="thinking-gradient-text">{current}</span>
            </div>
            <div className="thinking-dots-flow" aria-hidden="true">
              <span /> <span /> <span />
            </div>
            <div className="thinking-progress-bar">
              <div
                className={"thinking-progress-fill" + (loop ? ' indeterminate' : '')}
                style={!loop ? { width: `${progress}%` } : undefined}
              />
            </div>
            {developerMode && (
              <div className="thinking-dev-info">
                Step {effectiveIndex + 1} / {steps.length} {loop ? `(cycles: ${cycles})` : ''}
              </div>
            )}
          </div>
        </div>
      </div>
  );
};

ThinkingProcess.propTypes = {
  apiName: PropTypes.string,
  onComplete: PropTypes.func,
  minDelay: PropTypes.number,
  maxDelay: PropTypes.number,
  enablePulse: PropTypes.bool,
  developerMode: PropTypes.bool,
  cancelRef: PropTypes.object,
  loop: PropTypes.bool,
  variant: PropTypes.oneOf(['overlay','inline']),
  className: PropTypes.string,
  showElapsed: PropTypes.bool,
  startTime: PropTypes.number,
};

export default ThinkingProcess;
