import React from 'react';

const ErrorDisplay = ({ message, onRetry }) => (
  <div className="error-display">
    <p>{message}</p>
    {onRetry && (
      <button onClick={onRetry} className="retry-button">Retry</button>
    )}
  </div>
);

export default ErrorDisplay;
