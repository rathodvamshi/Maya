// Modern ChatWindow Component

import React, { useRef, useEffect, useState, useCallback } from 'react';
import { motion, AnimatePresence, useInView } from 'framer-motion';
import {
  Copy,
  ThumbsUp,
  ThumbsDown,
  Volume2,
  VolumeX,
  Edit3,
  Bot,
  User,
  CheckCircle,
  XCircle,
  MoreVertical,
  Heart,
  Share,
  Bookmark,
  MessageSquare,
  Sparkles,
  Clock,
  Check
} from 'lucide-react';
import '../styles/ChatWindowNew.css';

// Animation Variants
const messageVariants = {
  hidden: {
    opacity: 0,
    y: 30,
    scale: 0.95
  },
  visible: {
    opacity: 1,
    y: 0,
    scale: 1,
    transition: {
      duration: 0.4,
      ease: "easeOut"
    }
  },
  exit: {
    opacity: 0,
    y: -20,
    scale: 0.9,
    transition: {
      duration: 0.3,
      ease: "easeIn"
    }
  }
};

const avatarVariants = {
  hidden: {
    scale: 0,
    rotate: -180
  },
  visible: {
    scale: 1,
    rotate: 0,
    transition: {
      duration: 0.5,
      ease: "backOut",
      delay: 0.1
    }
  }
};

const actionButtonVariants = {
  hidden: {
    opacity: 0,
    scale: 0.8,
    x: -10
  },
  visible: {
    opacity: 1,
    scale: 1,
    x: 0,
    transition: {
      duration: 0.3,
      ease: "easeOut"
    }
  },
  hover: {
    scale: 1.1,
    y: -2,
    transition: {
      duration: 0.2,
      ease: "easeOut"
    }
  },
  tap: {
    scale: 0.95
  }
};

const typingVariants = {
  hidden: {
    opacity: 0,
    y: 20
  },
  visible: {
    opacity: 1,
    y: 0,
    transition: {
      duration: 0.3,
      ease: "easeOut"
    }
  }
};

// Message Component
const ChatMessage = ({ message, index, onCopy, onLike, onFeedback, onSpeak, onEdit, feedbackState, copiedIndex, likedMessages, speakingIndex }) => {
  const [showActions, setShowActions] = useState(false);
  const [isHovered, setIsHovered] = useState(false);
  const [showDropdown, setShowDropdown] = useState(false);
  const messageRef = useRef(null);
  const dropdownRef = useRef(null);
  const isInView = useInView(messageRef, { once: true, margin: "-50px" });

  const isUser = message.sender === 'user';
  const isAssistant = message.sender === 'assistant';

  // Close dropdown when clicking outside
  React.useEffect(() => {
    const handleClickOutside = (event) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target)) {
        setShowDropdown(false);
      }
    };
    
    if (showDropdown) {
      document.addEventListener('mousedown', handleClickOutside);
    }
    
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [showDropdown]);

  return (
    <motion.div
      ref={messageRef}
      className={`message-wrapper ${message.sender}`}
      variants={messageVariants}
      initial="hidden"
      animate={isInView ? "visible" : "hidden"}
      exit="exit"
      layout
      onMouseEnter={() => {
        setShowActions(true);
        setIsHovered(true);
      }}
      onMouseLeave={() => {
        setShowActions(false);
        setIsHovered(false);
      }}
    >
      {/* Avatar */}
      <motion.div 
        className="avatar-container"
        variants={avatarVariants}
        initial="hidden"
        animate={isInView ? "visible" : "hidden"}
      >
        <div className={`avatar ${message.sender}`}>
          <motion.div
            animate={{
              rotate: isHovered ? [0, 5, -5, 0] : 0,
              scale: isHovered ? 1.05 : 1
            }}
            transition={{
              duration: 0.6,
              ease: "easeInOut"
            }}
          >
            {isUser ? (
              <User size={18} />
            ) : (
              <>
                <Bot size={18} />
                <motion.div
                  className="avatar-glow"
                  animate={{
                    opacity: [0.5, 1, 0.5],
                    scale: [1, 1.1, 1]
                  }}
                  transition={{
                    duration: 2,
                    repeat: Infinity,
                    ease: "easeInOut"
                  }}
                />
              </>
            )}
          </motion.div>
          
          {/* Status indicator */}
          <motion.div
            className={`status-dot ${message.sender}`}
            initial={{ scale: 0 }}
            animate={{ scale: 1 }}
            transition={{ delay: 0.5, type: "spring", bounce: 0.6 }}
          />
        </div>
        
        {/* Sender label */}
        <motion.div
          className="sender-label"
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.3 }}
        >
          {isUser ? 'You' : 'Maya AI'}
        </motion.div>
      </motion.div>

      {/* Message Content */}
      <div className="message-content">
        <motion.div 
          className={`chat-message ${message.sender}`}
          whileHover={{ scale: 1.01 }}
          transition={{ duration: 0.2 }}
        >
          <motion.div
            className="message-text"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.2, duration: 0.5 }}
          >
            {message.text}
          </motion.div>

          {/* Message decorations */}
          <div className="message-decorations">
            {isAssistant && (
              <motion.div
                className="ai-indicator"
                initial={{ opacity: 0, scale: 0 }}
                animate={{ opacity: 1, scale: 1 }}
                transition={{ delay: 0.4, type: "spring" }}
              >
                <Sparkles size={12} />
              </motion.div>
            )}
            
            <motion.div
              className="timestamp"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ delay: 0.6 }}
            >
              <Clock size={10} />
              <span>now</span>
            </motion.div>
          </div>
        </motion.div>

        {/* Action Buttons */}
        <AnimatePresence>
          {showActions && (
            <motion.div 
              className="message-actions"
              initial={{ opacity: 0, y: 10, scale: 0.9 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: 10, scale: 0.9 }}
              transition={{ duration: 0.3, staggerChildren: 0.05 }}
            >
              {/* Copy Button */}
              <motion.button
                className={`action-btn copy-btn ${copiedIndex === index ? 'active' : ''}`}
                onClick={() => onCopy(message.text, index)}
                variants={actionButtonVariants}
                whileHover="hover"
                whileTap="tap"
                title="Copy message"
              >
                {copiedIndex === index ? <Check size={14} /> : <Copy size={14} />}
              </motion.button>

              {/* Assistant-specific actions */}
              {isAssistant && (
                <>
                  {/* Like Button */}
                  <motion.button
                    className={`action-btn like-btn ${likedMessages.has(index) ? 'active' : ''}`}
                    onClick={() => onLike(index)}
                    variants={actionButtonVariants}
                    whileHover="hover"
                    whileTap="tap"
                    title="Like message"
                  >
                    <Heart size={14} />
                  </motion.button>

                  {/* Feedback Buttons */}
                  <motion.button
                    className={`action-btn feedback-btn good-btn ${feedbackState[index] === 'good' ? 'active' : ''}`}
                    onClick={() => onFeedback(index, 'good')}
                    disabled={feedbackState[index]}
                    variants={actionButtonVariants}
                    whileHover="hover"
                    whileTap="tap"
                    title="Good response"
                  >
                    <ThumbsUp size={14} />
                  </motion.button>

                  <motion.button
                    className={`action-btn feedback-btn bad-btn ${feedbackState[index] === 'bad' ? 'active' : ''}`}
                    onClick={() => onFeedback(index, 'bad')}
                    disabled={feedbackState[index]}
                    variants={actionButtonVariants}
                    whileHover="hover"
                    whileTap="tap"
                    title="Bad response"
                  >
                    <ThumbsDown size={14} />
                  </motion.button>

                  {/* Bookmark Button */}
                  <motion.button
                    className="action-btn bookmark-btn"
                    variants={actionButtonVariants}
                    whileHover="hover"
                    whileTap="tap"
                    title="Bookmark message"
                  >
                    <Bookmark size={14} />
                  </motion.button>
                </>
              )}

              {/* Speak Button */}
              <motion.button
                className={`action-btn speak-btn ${speakingIndex === index ? 'active speaking' : ''}`}
                onClick={() => onSpeak(message.text, index)}
                variants={actionButtonVariants}
                whileHover="hover"
                whileTap="tap"
                title={speakingIndex === index ? 'Stop speaking' : 'Read aloud'}
              >
                <motion.div
                  animate={speakingIndex === index ? {
                    scale: [1, 1.2, 1],
                    rotate: [0, 10, -10, 0]
                  } : {}}
                  transition={{
                    duration: 0.8,
                    repeat: speakingIndex === index ? Infinity : 0
                  }}
                >
                  {speakingIndex === index ? <VolumeX size={14} /> : <Volume2 size={14} />}
                </motion.div>
              </motion.button>

              {/* User-specific actions */}
              {isUser && (
                <motion.button
                  className="action-btn edit-btn"
                  onClick={() => onEdit(index)}
                  variants={actionButtonVariants}
                  whileHover="hover"
                  whileTap="tap"
                  title="Edit message"
                >
                  <Edit3 size={14} />
                </motion.button>
              )}

              {/* More Options */}
              <div className="more-options-container" ref={dropdownRef}>
                <motion.button
                  className="action-btn more-btn"
                  onClick={() => setShowDropdown(!showDropdown)}
                  variants={actionButtonVariants}
                  whileHover="hover"
                  whileTap="tap"
                  title="More options"
                >
                  <MoreVertical size={14} />
                </motion.button>
                
                {/* Dropdown Menu */}
                <AnimatePresence>
                  {showDropdown && (
                    <motion.div
                      className="more-options-dropdown"
                      initial={{ opacity: 0, scale: 0.9, y: -10 }}
                      animate={{ opacity: 1, scale: 1, y: 0 }}
                      exit={{ opacity: 0, scale: 0.9, y: -10 }}
                      transition={{ duration: 0.2 }}
                    >
                      <div className="dropdown-item" onClick={() => navigator.share && navigator.share({title: 'Maya AI Message', text: message.text})}>
                        <Share size={14} />
                        Share
                      </div>
                      <div className="dropdown-item">
                        <MessageSquare size={14} />
                        Quote Reply
                      </div>
                      <div className="dropdown-item">
                        <Bookmark size={14} />
                        Save Message
                      </div>
                      <div className="dropdown-item" style={{color: '#ff6b6b'}}>
                        <XCircle size={14} />
                        Report
                      </div>
                    </motion.div>
                  )}
                </AnimatePresence>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </motion.div>
  );
};

// Typing Indicator Component
const TypingIndicator = () => (
  <motion.div
    className="message-wrapper assistant typing-wrapper"
    variants={typingVariants}
    initial="hidden"
    animate="visible"
    exit="hidden"
  >
    <motion.div 
      className="avatar-container"
      variants={avatarVariants}
      initial="hidden"
      animate="visible"
    >
      <div className="avatar assistant">
        <motion.div
          animate={{
            rotate: [0, 360],
            scale: [1, 1.1, 1]
          }}
          transition={{
            duration: 2,
            repeat: Infinity,
            ease: "easeInOut"
          }}
        >
          <Bot size={18} />
        </motion.div>
        <motion.div
          className="avatar-glow typing"
          animate={{
            opacity: [0.3, 1, 0.3],
            scale: [1, 1.2, 1]
          }}
          transition={{
            duration: 1.5,
            repeat: Infinity,
            ease: "easeInOut"
          }}
        />
      </div>
      <div className="sender-label">Maya AI</div>
    </motion.div>

    <div className="message-content">
      <motion.div 
        className="chat-message assistant typing"
        initial={{ scale: 0.9, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        transition={{ duration: 0.3 }}
      >
        <div className="typing-content">
          <div className="typing-indicator">
            <motion.span
              animate={{ y: [0, -8, 0] }}
              transition={{ duration: 0.6, repeat: Infinity, delay: 0 }}
            />
            <motion.span
              animate={{ y: [0, -8, 0] }}
              transition={{ duration: 0.6, repeat: Infinity, delay: 0.2 }}
            />
            <motion.span
              animate={{ y: [0, -8, 0] }}
              transition={{ duration: 0.6, repeat: Infinity, delay: 0.4 }}
            />
          </div>
          <motion.p
            className="typing-text"
            animate={{ opacity: [0.7, 1, 0.7] }}
            transition={{ duration: 1.5, repeat: Infinity }}
          >
            Maya is thinking...
          </motion.p>
        </div>
      </motion.div>
    </div>
  </motion.div>
);

// Notification Component
const FeedbackNotification = ({ notification, onClose }) => (
  <motion.div
    className={`feedback-notification ${notification.type}`}
    initial={{ opacity: 0, x: 50, scale: 0.9 }}
    animate={{ opacity: 1, x: 0, scale: 1 }}
    exit={{ opacity: 0, x: 50, scale: 0.9 }}
    transition={{ duration: 0.3, ease: "easeOut" }}
    layout
  >
    <motion.div 
      className="notification-icon"
      initial={{ rotate: -180, scale: 0 }}
      animate={{ rotate: 0, scale: 1 }}
      transition={{ delay: 0.1, type: "spring", bounce: 0.6 }}
    >
      {notification.type === 'good' ? <CheckCircle size={20} /> : <XCircle size={20} />}
    </motion.div>
    <motion.span 
      className="notification-text"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ delay: 0.2 }}
    >
      {notification.message}
    </motion.span>
    <motion.div
      className="notification-progress"
      initial={{ width: "100%" }}
      animate={{ width: "0%" }}
      transition={{ duration: 3, ease: "linear" }}
    />
  </motion.div>
);

// Empty State Component
const EmptyState = () => (
  <motion.div
    className="empty-state"
    initial={{ opacity: 0, y: 20 }}
    animate={{ opacity: 1, y: 0 }}
    transition={{ duration: 0.6, ease: "easeOut" }}
  >
    <motion.div
      className="empty-icon"
      animate={{
        y: [0, -10, 0],
        rotate: [0, 5, -5, 0]
      }}
      transition={{
        duration: 4,
        repeat: Infinity,
        ease: "easeInOut"
      }}
    >
      <MessageSquare size={48} />
      <motion.div
        className="sparkle-1"
        animate={{
          opacity: [0, 1, 0],
          scale: [0.8, 1.2, 0.8],
          rotate: [0, 180, 360]
        }}
        transition={{
          duration: 2,
          repeat: Infinity,
          ease: "easeInOut"
        }}
      >
        <Sparkles size={16} />
      </motion.div>
      <motion.div
        className="sparkle-2"
        animate={{
          opacity: [0, 1, 0],
          scale: [1, 0.8, 1],
          rotate: [360, 180, 0]
        }}
        transition={{
          duration: 3,
          repeat: Infinity,
          ease: "easeInOut",
          delay: 1
        }}
      >
        <Sparkles size={12} />
      </motion.div>
    </motion.div>
    <motion.div
      className="empty-content"
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.3 }}
    >
      <h3>Welcome to Maya AI</h3>
      <p>Start a conversation to unlock the power of AI assistance</p>
    </motion.div>
  </motion.div>
);

// Main ChatWindow Component
const ChatWindow = ({
  messages = [],
  isLoading = false,
  onFetchMore,
  hasMoreMessages = false,
  activeSessionId,
}) => {
  const chatWindowRef = useRef(null);
  const topObserver = useRef(null);
  const [copiedIndex, setCopiedIndex] = useState(null);
  const [likedMessages, setLikedMessages] = useState(new Set());
  const [speakingIndex, setSpeakingIndex] = useState(null);
  const [feedbackState, setFeedbackState] = useState({});
  const [feedbackNotifications, setFeedbackNotifications] = useState([]);

  // Auto-scroll to bottom on new messages
  useEffect(() => {
    if (chatWindowRef.current && messages.length > 0) {
      const scrollElement = chatWindowRef.current;
      const isNearBottom = scrollElement.scrollTop + scrollElement.clientHeight >= scrollElement.scrollHeight - 100;
      
      if (isNearBottom) {
        setTimeout(() => {
          scrollElement.scrollTo({
            top: scrollElement.scrollHeight,
            behavior: 'smooth'
          });
        }, 100);
      }
    }
  }, [messages]);

  // Intersection Observer for infinite scroll
  const topElementRef = useCallback(
    (node) => {
      if (!hasMoreMessages || isLoading) return;
      if (topObserver.current) topObserver.current.disconnect();

      topObserver.current = new IntersectionObserver((entries) => {
        if (entries[0].isIntersecting) {
          onFetchMore?.();
        }
      });

      if (node) topObserver.current.observe(node);
    },
    [hasMoreMessages, isLoading, onFetchMore]
  );

  // Actions
  const copyToClipboard = async (text, index) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopiedIndex(index);
      setTimeout(() => setCopiedIndex(null), 2000);
    } catch (err) {
      console.error('Failed to copy:', err);
    }
  };

  const toggleLike = (index) => {
    const newLiked = new Set(likedMessages);
    likedMessages.has(index) ? newLiked.delete(index) : newLiked.add(index);
    setLikedMessages(newLiked);
  };

  const toggleSpeak = (text, index) => {
    if (speakingIndex === index) {
      window.speechSynthesis.cancel();
      setSpeakingIndex(null);
    } else {
      window.speechSynthesis.cancel();
      const utterance = new SpeechSynthesisUtterance(text);
      utterance.onend = () => setSpeakingIndex(null);
      window.speechSynthesis.speak(utterance);
      setSpeakingIndex(index);
    }
  };

  const editMessage = (index) => {
    console.log('Edit message:', index);
  };

  const addFeedbackNotification = (type, index) => {
    const notification = {
      id: Date.now(),
      type,
      index,
      message: type === 'good' ? 'Thanks for your positive feedback!' : 'Thanks for your feedback, we\'ll improve!',
    };

    setFeedbackNotifications((prev) => [...prev, notification]);
    setTimeout(() => {
      setFeedbackNotifications((prev) =>
        prev.filter((notif) => notif.id !== notification.id)
      );
    }, 3000);
  };

  const handleFeedback = async (index, rating) => {
    if (feedbackState[index]) return;

    try {
      await new Promise((resolve) => setTimeout(resolve, 500));
      setFeedbackState((prev) => ({ ...prev, [index]: rating }));
      addFeedbackNotification(rating, index);
      console.log(`Feedback submitted for message ${index}: ${rating}`);
    } catch (error) {
      console.error('Failed to submit feedback:', error);
    }
  };

  return (
    <div className="chat-container">
      {/* Background Effects */}
      <div className="chat-background">
        <motion.div 
          className="bg-gradient bg-gradient-1"
          animate={{
            x: [0, 100, 0],
            y: [0, -50, 0],
            scale: [1, 1.1, 1]
          }}
          transition={{
            duration: 20,
            repeat: Infinity,
            ease: "easeInOut"
          }}
        />
        <motion.div 
          className="bg-gradient bg-gradient-2"
          animate={{
            x: [0, -80, 0],
            y: [0, 60, 0],
            scale: [1, 0.9, 1]
          }}
          transition={{
            duration: 15,
            repeat: Infinity,
            ease: "easeInOut"
          }}
        />
      </div>

      {/* Chat Window */}
      <div className="chat-window" ref={chatWindowRef}>
        {hasMoreMessages && (
          <div ref={topElementRef} style={{ height: '1px' }} />
        )}

        <AnimatePresence mode="popLayout">
          {messages.length === 0 ? (
            <EmptyState key="empty" />
          ) : (
            messages.map((msg, index) => (
              <ChatMessage
                key={`${activeSessionId}-${index}`}
                message={msg}
                index={index}
                onCopy={copyToClipboard}
                onLike={toggleLike}
                onFeedback={handleFeedback}
                onSpeak={toggleSpeak}
                onEdit={editMessage}
                feedbackState={feedbackState}
                copiedIndex={copiedIndex}
                likedMessages={likedMessages}
                speakingIndex={speakingIndex}
              />
            ))
          )}

          {/* Typing Indicator */}
          {isLoading && <TypingIndicator key="typing" />}
        </AnimatePresence>
      </div>

      {/* Feedback Notifications */}
      <div className="feedback-notifications">
        <AnimatePresence>
          {feedbackNotifications.map((notif) => (
            <FeedbackNotification
              key={notif.id}
              notification={notif}
              onClose={() => setFeedbackNotifications(prev =>
                prev.filter(n => n.id !== notif.id)
              )}
            />
          ))}
        </AnimatePresence>
      </div>
    </div>
  );
};

export default ChatWindow;