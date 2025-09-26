import React, { useRef, useEffect, useState, useCallback } from 'react';
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
  XCircle
} from 'lucide-react';
import '../styles/ChatWindow.css'; // Make sure this CSS file is imported

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

  useEffect(() => {
    if (chatWindowRef.current) {
      chatWindowRef.current.scrollTop = chatWindowRef.current.scrollHeight;
    }
  }, [messages]);

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

  // --- Actions ---
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
      message: type === 'good' ? 'Thanks for your feedback!' : 'Thanks for your feedback!',
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
      <div className="chat-window" ref={chatWindowRef}>
        {hasMoreMessages && <div ref={topElementRef} style={{ height: '1px' }} />}
        
        {messages.map((msg, index) => (
          <div key={index} className={`message-wrapper ${msg.sender}`}>
            <div className="avatar">
              {msg.sender === 'user' ? <User size={20} /> : <Bot size={20} />}
            </div>

            <div className="message-content">
              <div className={`chat-message ${msg.sender}`}>
                <p>{msg.text}</p>
              </div>

              {/* Actions below message */}
              <div className="message-actions">
                {/* Copy */}
                <button
                  className={`action-btn copy-btn ${copiedIndex === index ? 'copied' : ''}`}
                  onClick={() => copyToClipboard(msg.text, index)}
                  title="Copy message"
                >
                  <Copy size={14} />
                </button>

                {/* Assistant feedback */}
                {msg.sender === 'assistant' && (
                  <>
                    <button
                      className={`action-btn like-btn ${likedMessages.has(index) ? 'liked' : ''}`}
                      onClick={() => toggleLike(index)}
                      title="Like message"
                    >
                      <ThumbsUp size={14} />
                    </button>
                    <button
                      className={`action-btn feedback-btn good-btn ${feedbackState[index] === 'good' ? 'selected' : ''}`}
                      onClick={() => handleFeedback(index, 'good')}
                      disabled={feedbackState[index]}
                      title="Good response"
                    >
                      <ThumbsUp size={14} />
                    </button>
                    <button
                      className={`action-btn feedback-btn bad-btn ${feedbackState[index] === 'bad' ? 'selected' : ''}`}
                      onClick={() => handleFeedback(index, 'bad')}
                      disabled={feedbackState[index]}
                      title="Bad response"
                    >
                      <ThumbsDown size={14} />
                    </button>
                  </>
                )}

                {/* Speak */}
                <button
                  className={`action-btn speak-btn ${speakingIndex === index ? 'speaking' : ''}`}
                  onClick={() => toggleSpeak(msg.text, index)}
                  title={speakingIndex === index ? 'Stop speaking' : 'Read aloud'}
                >
                  {speakingIndex === index ? <VolumeX size={14} /> : <Volume2 size={14} />}
                </button>

                {/* Edit user message */}
                {msg.sender === 'user' && (
                  <button
                    className="action-btn edit-btn"
                    onClick={() => editMessage(index)}
                    title="Edit message"
                  >
                    <Edit3 size={14} />
                  </button>
                )}
              </div>
            </div>
          </div>
        ))}

        {/* Typing indicator */}
        {isLoading && (
          <div className="message-wrapper assistant">
            <div className="avatar">
              <Bot size={20} />
            </div>
            <div className="message-content">
              <div className="chat-message assistant typing">
                <div className="typing-indicator">
                  <span></span>
                  <span></span>
                  <span></span>
                </div>
                <p>AI is thinking...</p>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Notifications */}
      <div className="feedback-notifications">
        {feedbackNotifications.map((notif) => (
          <div key={notif.id} className={`feedback-notification ${notif.type}`}>
            <div className="notification-icon">
              {notif.type === 'good' ? <CheckCircle size={20} /> : <XCircle size={20} />}
            </div>
            <span className="notification-text">{notif.message}</span>
          </div>
        ))}
      </div>
    </div>
  );
};

export default ChatWindow;
