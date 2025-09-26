// frontend/src/components/ChatSkeletonLoader.jsx

import React from 'react';
import '../styles/ChatWindow.css'; // We can reuse styles
import '../styles/SkeletonLoader.css'; // We will create this new CSS file

const ChatSkeletonLoader = () => (
  <div className="chat-window">
    {/* Skeleton for an AI message */}
    <div className="message-wrapper assistant">
      <div className="avatar skeleton"></div>
      <div className="message-content">
        <div className="chat-message skeleton skeleton-text"></div>
        <div className="chat-message skeleton skeleton-text-short"></div>
      </div>
    </div>
    {/* Skeleton for a User message */}
    <div className="message-wrapper user">
      <div className="avatar skeleton"></div>
      <div className="message-content">
        <div className="chat-message skeleton skeleton-text"></div>
      </div>
    </div>
    <div className="message-wrapper assistant">
      <div className="avatar skeleton"></div>
      <div className="message-content">
        <div className="chat-message skeleton skeleton-text-medium"></div>
      </div>
    </div>
  </div>
);

export default ChatSkeletonLoader;