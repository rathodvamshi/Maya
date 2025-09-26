// Modern Dashboard Component

import React, { useEffect, useReducer, useCallback, useMemo } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { MessageSquare, Sparkles, Activity, Layers, Zap } from 'lucide-react';
import chatService from '../services/chatService';
import sessionService from '../services/sessionService';
import authService from '../services/auth';
import '../styles/DashboardNew.css';

import ChatWindowNew from './ChatWindowNew';
import RightSidebarNew from './RightSidebarNew';
import LeftSidebarNew from './LeftSidebarNew';
import LoadingSpinnerNew from './LoadingSpinnerNew';
import ErrorDisplay from './ErrorDisplay';
import ChatSkeletonLoader from './ChatSkeletonLoader';

// --- The Reducer and Custom Hook sections remain completely the same ---
const initialState = {
  messages: [],
  sessions: [],
  activeSessionId: null,
  input: '',
  status: 'idle', 
  error: null,
  currentUserEmail: '',
  pendingTasks: [],
  currentPage: 1,
  hasMoreMessages: true,
};

function chatReducer(state, action) {
  switch (action.type) {
    case 'INITIAL_LOAD_START':
      return { ...state, status: 'pageLoading' };
    case 'INITIAL_LOAD_SUCCESS':
      return { ...state, status: 'idle', sessions: action.payload.sessions, messages: [action.payload.initialMessage] };
    case 'INITIAL_LOAD_ERROR':
      return { ...state, status: 'error', error: action.payload };
    
    case 'SELECT_SESSION_START':
      return { ...state, status: 'sessionLoading', activeSessionId: action.payload, messages: [], currentPage: 1, hasMoreMessages: true };
    case 'SELECT_SESSION_SUCCESS':
      return { ...state, status: 'idle', messages: action.payload.messages || [], hasMoreMessages: action.payload.hasMore };
    case 'SELECT_SESSION_ERROR':
      return { ...state, status: 'error', error: action.payload };

    case 'SEND_MESSAGE_START':
      return { ...state, status: 'loading', input: '', messages: [...state.messages, action.payload.userMessage] };
    case 'SEND_MESSAGE_SUCCESS':
      return { ...state, status: 'idle', messages: [...state.messages, action.payload.assistantMessage] };
    case 'SEND_MESSAGE_ERROR':
      return { ...state, status: 'error', error: action.payload, messages: [...state.messages, { sender: 'assistant', text: 'Sorry, an error occurred.' }] };
    
    case 'NEW_SESSION_CREATED':
      return { ...state, activeSessionId: action.payload.sessionId, sessions: action.payload.updatedSessions };

    case 'NEW_CHAT':
      return { ...state, activeSessionId: null, messages: action.payload, status: 'idle' };

    case 'UPDATE_SESSIONS':
      return { ...state, sessions: action.payload };
    
    case 'SET_INPUT':
      return { ...state, input: action.payload };

    case 'SET_USER_EMAIL':
      return { ...state, currentUserEmail: action.payload };
      
    default:
      throw new Error(`Unhandled action type: ${action.type}`);
  }
}

const useChatManager = ({ state, dispatch }) => {
    const initialMessage = useMemo(
        () => ({ sender: 'assistant', text: 'Hello! How can I assist you today?' }),
        []
      );
    
      const loadSessions = useCallback(async () => {
        try {
          const response = await sessionService.getSessions();
          dispatch({ type: 'UPDATE_SESSIONS', payload: response.data });
          return response.data;
        } catch (err) {
          console.error("Failed to load sessions:", err);
          throw new Error("Could not load sessions.");
        }
      }, [dispatch]);
    
      const loadInitialData = useCallback(async () => {
        dispatch({ type: 'INITIAL_LOAD_START' });
        try {
          const sessions = await loadSessions();
          dispatch({ type: 'INITIAL_LOAD_SUCCESS', payload: { sessions, initialMessage } });
        } catch (err) {
          dispatch({ type: 'INITIAL_LOAD_ERROR', payload: err.message });
        }
      }, [dispatch, loadSessions, initialMessage]);
    
      const handleSelectSession = useCallback(async (sessionId) => {
        if (!sessionId || sessionId === state.activeSessionId) return;
        dispatch({ type: 'SELECT_SESSION_START', payload: sessionId });
        try {
          const response = await sessionService.getSessionMessages(sessionId, 1);
          const hasMore = (response.data.messages?.length || 0) < response.data.totalMessages;
          dispatch({ type: 'SELECT_SESSION_SUCCESS', payload: { messages: response.data.messages, hasMore } });
        } catch (err) {
          console.error("Failed to load session:", err);
          dispatch({ type: 'SELECT_SESSION_ERROR', payload: 'Could not load chat history.' });
        }
      }, [state.activeSessionId, dispatch]);
    
      const handleNewChat = useCallback(() => {
        dispatch({ type: 'NEW_CHAT', payload: [initialMessage] });
      }, [dispatch, initialMessage]);
    
      const handleDeleteSession = useCallback(async (sessionId) => {
        try {
          await sessionService.deleteSession(sessionId);
          if (state.activeSessionId === sessionId) {
            handleNewChat();
          }
          await loadSessions();
        } catch (err) {
          dispatch({ type: 'INITIAL_LOAD_ERROR', payload: 'Could not delete the session.' });
        }
      }, [state.activeSessionId, dispatch, loadSessions, handleNewChat]);
    
      const handleSendMessage = useCallback(async (e) => {
        e.preventDefault();
        if (!state.input.trim() || state.status === 'loading') return;
    
        const userMessage = { sender: 'user', text: state.input };
        dispatch({ type: 'SEND_MESSAGE_START', payload: { userMessage } });
        
        try {
          if (!state.activeSessionId) {
            const newChatResponse = await chatService.startNewChat(userMessage.text);
            const assistantMessage = { sender: 'assistant', text: newChatResponse.data.response_text };
            const updatedSessions = await loadSessions();
            dispatch({ type: 'NEW_SESSION_CREATED', payload: { sessionId: newChatResponse.data.session_id, updatedSessions } });
            dispatch({ type: 'SEND_MESSAGE_SUCCESS', payload: { assistantMessage } });
          } else {
            const continueChatResponse = await chatService.sendMessage(state.activeSessionId, userMessage.text);
            const assistantMessage = { sender: 'assistant', text: continueChatResponse.data.response_text };
            dispatch({ type: 'SEND_MESSAGE_SUCCESS', payload: { assistantMessage } });
          }
        } catch (error) {
          console.error("Error sending message:", error);
          dispatch({ type: 'SEND_MESSAGE_ERROR', payload: error.message });
        }
      }, [state.activeSessionId, state.input, state.status, dispatch, loadSessions]);
      
      return useMemo(() => ({
        loadInitialData,
        handleSelectSession,
        handleNewChat,
        handleDeleteSession,
        handleSendMessage,
      }), [loadInitialData, handleSelectSession, handleNewChat, handleDeleteSession, handleSendMessage]);
};

// Page Transition Variants
const pageVariants = {
  initial: { 
    opacity: 0, 
    y: 20,
    scale: 0.98
  },
  in: { 
    opacity: 1, 
    y: 0,
    scale: 1,
    transition: {
      duration: 0.6,
      ease: "easeOut"
    }
  },
  out: { 
    opacity: 0, 
    y: -20,
    scale: 1.02,
    transition: {
      duration: 0.3,
      ease: "easeIn"
    }
  }
};

// Main Content Animation
const mainContentVariants = {
  hidden: {
    opacity: 0,
    x: 50,
    scale: 0.95
  },
  visible: {
    opacity: 1,
    x: 0,
    scale: 1,
    transition: {
      duration: 0.8,
      ease: "easeOut",
      staggerChildren: 0.1
    }
  }
};

// Chat Input Animation
const inputVariants = {
  hidden: {
    opacity: 0,
    y: 30
  },
  visible: {
    opacity: 1,
    y: 0,
    transition: {
      duration: 0.5,
      ease: "easeOut"
    }
  }
};

// Loading States Component
const LoadingStates = ({ status, error, onRetry }) => {
  if (status === 'pageLoading') {
    return (
      <motion.div 
        className="dashboard-loading"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
      >
        <div className="loading-content">
          <LoadingSpinnerNew size="lg" />
          <motion.div
            className="loading-text"
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.3 }}
          >
            <h3>Initializing Maya</h3>
            <p>Setting up your workspace...</p>
          </motion.div>
        </div>
      </motion.div>
    );
  }

  if (status === 'error') {
    return (
      <motion.div 
        className="dashboard-error"
        initial={{ opacity: 0, scale: 0.9 }}
        animate={{ opacity: 1, scale: 1 }}
        exit={{ opacity: 0, scale: 0.9 }}
      >
        <ErrorDisplay message={error} onRetry={onRetry} />
      </motion.div>
    );
  }

  return null;
};

// Activity Indicator Component
const ActivityIndicator = ({ status, sessions }) => (
  <motion.div 
    className="activity-indicator"
    initial={{ opacity: 0, x: -20 }}
    animate={{ opacity: 1, x: 0 }}
    transition={{ delay: 0.8 }}
  >
    <div className="activity-items">
      <div className="activity-item">
        <Activity size={14} />
        <span className="activity-text">
          {status === 'loading' ? 'Processing...' : 'Ready'}
        </span>
        <div className={`activity-dot ${status === 'loading' ? 'active' : 'idle'}`} />
      </div>
      <div className="activity-item">
        <MessageSquare size={14} />
        <span className="activity-text">{sessions.length} Sessions</span>
      </div>
      <div className="activity-item">
        <Layers size={14} />
        <span className="activity-text">Maya AI</span>
      </div>
    </div>
  </motion.div>
);

// ==================================================
// 🔹 Main Dashboard Component
// ==================================================

const Dashboard = () => {
  const [state, dispatch] = useReducer(chatReducer, initialState);
  const handlers = useChatManager({ state, dispatch });
  
  const { 
    status, error, sessions, activeSessionId, 
    messages, input, currentUserEmail, pendingTasks 
  } = state;

  useEffect(() => {
    const user = authService.getCurrentUser();
    if (user?.access_token) {
      try {
        const tokenData = JSON.parse(atob(user.access_token.split('.')[1]));
        dispatch({ type: 'SET_USER_EMAIL', payload: tokenData.sub });
      } catch (e) { 
        console.error("Failed to decode token:", e); 
      }
    }
    handlers.loadInitialData();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Show loading/error states
  if (status === 'pageLoading' || status === 'error') {
    return <LoadingStates status={status} error={error} onRetry={handlers.loadInitialData} />;
  }

  return (
    <motion.div 
      className="dashboard-screen"
      variants={pageVariants}
      initial="initial"
      animate="in"
      exit="out"
    >
      {/* Animated Background */}
      <div className="dashboard-background">
        <div className="gradient-orb orb-1" />
        <div className="gradient-orb orb-2" />
        <div className="gradient-orb orb-3" />
      </div>

      {/* Floating Elements */}
      <div className="floating-elements">
        <motion.div 
          className="floating-element element-1"
          animate={{ 
            y: [0, -20, 0],
            rotate: [0, 5, -5, 0]
          }}
          transition={{ 
            duration: 8,
            repeat: Infinity,
            ease: "easeInOut"
          }}
        >
          <Sparkles size={16} />
        </motion.div>
        <motion.div 
          className="floating-element element-2"
          animate={{ 
            y: [0, 15, 0],
            x: [0, 10, 0]
          }}
          transition={{ 
            duration: 6,
            repeat: Infinity,
            ease: "easeInOut"
          }}
        >
          <Zap size={14} />
        </motion.div>
      </div>

      <div className="dashboard-container">
        {/* Left Sidebar */}
        <motion.div
          className="sidebar-wrapper left"
          initial={{ x: -100, opacity: 0 }}
          animate={{ x: 0, opacity: 1 }}
          transition={{ duration: 0.6, delay: 0.2 }}
        >
          <LeftSidebarNew
            sessions={sessions}
            activeSessionId={activeSessionId}
            onNewChat={handlers.handleNewChat}
            onSelectSession={handlers.handleSelectSession}
            onDeleteSession={handlers.handleDeleteSession}
          />
        </motion.div>

        {/* Main Content Area */}
        <motion.main 
          className="dashboard-main"
          variants={mainContentVariants}
          initial="hidden"
          animate="visible"
        >
          {/* Header Section */}
          <motion.div 
            className="dashboard-header"
            variants={inputVariants}
          >
            <div className="header-content">
              <div className="header-title">
                <MessageSquare className="header-icon" size={24} />
                <h1>Maya AI Assistant</h1>
              </div>
              <ActivityIndicator status={status} sessions={sessions} />
            </div>
          </motion.div>

          {/* Chat Content */}
          <motion.div 
            className="chat-content"
            variants={inputVariants}
          >
            <AnimatePresence mode="wait">
              {status === 'sessionLoading' ? (
                <motion.div
                  key="skeleton"
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  exit={{ opacity: 0 }}
                  className="chat-skeleton-wrapper"
                >
                  <ChatSkeletonLoader />
                </motion.div>
              ) : (
                <motion.div
                  key="chat"
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -20 }}
                  transition={{ duration: 0.4 }}
                  className="chat-window-wrapper"
                >
                  <ChatWindowNew
                    messages={messages}
                    isLoading={status === 'loading'}
                    activeSessionId={activeSessionId}
                  />
                </motion.div>
              )}
            </AnimatePresence>
          </motion.div>

          {/* Chat Input Area */}
          <motion.div 
            className="chat-input-section"
            variants={inputVariants}
          >
            <motion.form 
              className="chat-input-form" 
              onSubmit={handlers.handleSendMessage}
              whileTap={{ scale: 0.98 }}
            >
              <div className="input-container">
                <motion.input
                  type="text"
                  className="chat-input"
                  placeholder="Type your message here..."
                  value={input}
                  onChange={(e) => dispatch({ type: 'SET_INPUT', payload: e.target.value })}
                  disabled={status === 'loading'}
                  whileFocus={{ scale: 1.02 }}
                  transition={{ duration: 0.2 }}
                />
                <motion.button 
                  type="submit" 
                  className={`send-button ${status === 'loading' ? 'loading' : ''}`}
                  disabled={status === 'loading'}
                  whileHover={{ scale: 1.05 }}
                  whileTap={{ scale: 0.95 }}
                >
                  <AnimatePresence mode="wait">
                    {status === 'loading' ? (
                      <motion.div
                        key="loading"
                        initial={{ opacity: 0, rotate: -90 }}
                        animate={{ opacity: 1, rotate: 0 }}
                        exit={{ opacity: 0, rotate: 90 }}
                        className="button-content"
                      >
                        <LoadingSpinnerNew size="sm" />
                        <span>Sending</span>
                      </motion.div>
                    ) : (
                      <motion.div
                        key="send"
                        initial={{ opacity: 0, x: -10 }}
                        animate={{ opacity: 1, x: 0 }}
                        exit={{ opacity: 0, x: 10 }}
                        className="button-content"
                      >
                        <Zap size={16} />
                        <span>Send</span>
                      </motion.div>
                    )}
                  </AnimatePresence>
                </motion.button>
              </div>
            </motion.form>
          </motion.div>
        </motion.main>

        {/* Right Sidebar */}
        <motion.div
          className="sidebar-wrapper right"
          initial={{ x: 100, opacity: 0 }}
          animate={{ x: 0, opacity: 1 }}
          transition={{ duration: 0.6, delay: 0.4 }}
        >
          <RightSidebarNew 
            currentUserEmail={currentUserEmail} 
            pendingTasks={pendingTasks} 
          />
        </motion.div>
      </div>
    </motion.div>
  );
};

export default Dashboard;