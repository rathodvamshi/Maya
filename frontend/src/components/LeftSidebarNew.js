// Modern LeftSidebar Component

import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { 
  Plus, 
  MessageSquare, 
  Trash2, 
  ChevronRight, 
  Sparkles, 
  Clock, 
  Star,
  Menu,
  X,
  History,
  Bookmark,
  Zap
} from 'lucide-react';
import '../styles/LeftSidebarNew.css';

// Animation Variants
const sidebarVariants = {
  expanded: {
    width: 320,
    transition: {
      duration: 0.4,
      ease: "easeOut",
      staggerChildren: 0.05
    }
  },
  collapsed: {
    width: 80,
    transition: {
      duration: 0.3,
      ease: "easeIn"
    }
  }
};

const contentVariants = {
  expanded: {
    opacity: 1,
    x: 0,
    transition: {
      duration: 0.3,
      delay: 0.1,
      ease: "easeOut"
    }
  },
  collapsed: {
    opacity: 0,
    x: -20,
    transition: {
      duration: 0.2,
      ease: "easeIn"
    }
  }
};

const sessionVariants = {
  hidden: {
    opacity: 0,
    x: -30,
    scale: 0.95
  },
  visible: {
    opacity: 1,
    x: 0,
    scale: 1,
    transition: {
      duration: 0.3,
      ease: "easeOut"
    }
  },
  exit: {
    opacity: 0,
    x: -20,
    scale: 0.9,
    transition: {
      duration: 0.2,
      ease: "easeIn"
    }
  }
};

const buttonHoverVariants = {
  hover: {
    scale: 1.02,
    y: -1,
    transition: {
      duration: 0.2,
      ease: "easeOut"
    }
  },
  tap: {
    scale: 0.98,
    y: 0
  }
};

const SessionItem = ({ session, activeSessionId, onSelectSession, onDeleteSession, isExpanded }) => {
  const [isHovered, setIsHovered] = useState(false);

  const handleDelete = (e) => {
    e.stopPropagation();
    if (window.confirm('Are you sure you want to delete this chat session?')) {
      onDeleteSession(session.id);
    }
  };

  return (
    <motion.li
      className={`session-item ${session.id === activeSessionId ? 'active' : ''}`}
      variants={sessionVariants}
      initial="hidden"
      animate="visible"
      exit="exit"
      layout
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
      onClick={() => onSelectSession(session.id)}
      whileHover={{ scale: 1.02, x: 8 }}
      whileTap={{ scale: 0.98 }}
    >
      <div className="session-main">
        <motion.div 
          className="session-icon-wrapper"
          animate={{ 
            scale: isHovered ? 1.1 : 1,
            rotate: isHovered ? 5 : 0 
          }}
          transition={{ duration: 0.2 }}
        >
          <MessageSquare size={18} className="session-icon" />
          {session.isStarred && (
            <motion.div
              className="star-badge"
              initial={{ scale: 0, rotate: -180 }}
              animate={{ scale: 1, rotate: 0 }}
              transition={{ delay: 0.2 }}
            >
              <Star size={12} className="star-icon" />
            </motion.div>
          )}
        </motion.div>

        <AnimatePresence>
          {isExpanded && (
            <motion.div 
              className="session-content"
              variants={contentVariants}
              initial="collapsed"
              animate="expanded"
              exit="collapsed"
            >
              <span className="session-title">{session.title || 'Untitled Chat'}</span>
              <span className="session-timestamp">{session.timestamp || 'Just now'}</span>
            </motion.div>
          )}
        </AnimatePresence>

        <AnimatePresence>
          {isExpanded && (
            <motion.button
              className="delete-session-btn"
              title="Delete Session"
              onClick={handleDelete}
              initial={{ opacity: 0, scale: 0.8 }}
              animate={{ 
                opacity: isHovered ? 1 : 0.6,
                scale: isHovered ? 1.1 : 1
              }}
              exit={{ opacity: 0, scale: 0.8 }}
              whileHover={{ scale: 1.2, rotate: 10 }}
              whileTap={{ scale: 0.9 }}
            >
              <Trash2 size={14} />
            </motion.button>
          )}
        </AnimatePresence>
      </div>

      {/* Active indicator */}
      {session.id === activeSessionId && (
        <motion.div
          className="active-indicator"
          layoutId="activeIndicator"
          transition={{ duration: 0.3, ease: "easeOut" }}
        />
      )}
    </motion.li>
  );
};

const LeftSidebar = ({
  sessions = [],
  activeSessionId,
  onNewChat,
  onSelectSession,
  onDeleteSession,
  isExpanded = false,
  onToggleExpanded,
}) => {
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);

  const handleToggle = () => {
    if (onToggleExpanded) {
      onToggleExpanded(!isExpanded);
    }
  };

  const handleMobileToggle = () => {
    setIsMobileMenuOpen(!isMobileMenuOpen);
  };

  const handleNewChat = () => {
    onNewChat();
    // Auto-collapse on mobile after action
    if (window.innerWidth <= 768) {
      setIsMobileMenuOpen(false);
    }
  };

  const displaySessions = sessions.length > 0 ? sessions : [];

  return (
    <>
      {/* Mobile Menu Toggle */}
      <motion.button 
        className="mobile-menu-toggle"
        onClick={handleMobileToggle}
        whileHover={{ scale: 1.1 }}
        whileTap={{ scale: 0.9 }}
      >
        {isMobileMenuOpen ? <X size={20} /> : <Menu size={20} />}
      </motion.button>

      {/* Mobile Overlay */}
      <AnimatePresence>
        {isMobileMenuOpen && (
          <motion.div
            className="mobile-overlay"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={handleMobileToggle}
          />
        )}
      </AnimatePresence>

      {/* Sidebar */}
      <motion.aside 
        className={`left-sidebar ${isMobileMenuOpen ? 'mobile-open' : ''}`}
        variants={sidebarVariants}
        initial="expanded"
        animate={isExpanded ? "expanded" : "collapsed"}
        transition={{ duration: 0.4, ease: "easeOut" }}
      >
        {/* Background Glass Effect */}
        <div className="sidebar-glass-bg" />
        
        {/* Floating Particles */}
        <div className="sidebar-particles">
          <motion.div 
            className="particle particle-1"
            animate={{ 
              y: [0, -15, 0],
              opacity: [0.3, 0.6, 0.3]
            }}
            transition={{ 
              duration: 4,
              repeat: Infinity,
              ease: "easeInOut"
            }}
          />
          <motion.div 
            className="particle particle-2"
            animate={{ 
              y: [0, 20, 0],
              x: [0, 10, 0]
            }}
            transition={{ 
              duration: 6,
              repeat: Infinity,
              ease: "easeInOut"
            }}
          />
        </div>

        {/* Toggle Button */}
        <motion.button 
          className="sidebar-toggle" 
          onClick={handleToggle}
          variants={buttonHoverVariants}
          whileHover="hover"
          whileTap="tap"
        >
          <motion.div
            animate={{ rotate: isExpanded ? 180 : 0 }}
            transition={{ duration: 0.3 }}
          >
            <ChevronRight size={16} />
          </motion.div>
        </motion.button>

        {/* Header */}
        <div className="sidebar-header">
          <motion.button 
            className="new-chat-btn" 
            onClick={handleNewChat}
            variants={buttonHoverVariants}
            whileHover="hover"
            whileTap="tap"
          >
            <motion.div 
              className="btn-icon-wrapper"
              whileHover={{ rotate: 90 }}
              transition={{ duration: 0.3 }}
            >
              <Plus className="btn-icon" size={18} />
              <motion.div
                className="sparkle-wrapper"
                animate={{ 
                  rotate: [0, 180, 360],
                  scale: [1, 1.2, 1]
                }}
                transition={{ 
                  duration: 3,
                  repeat: Infinity,
                  ease: "easeInOut"
                }}
              >
                <Sparkles className="sparkle-icon" size={12} />
              </motion.div>
            </motion.div>
            <AnimatePresence>
              {isExpanded && (
                <motion.span 
                  className="btn-text"
                  variants={contentVariants}
                  initial="collapsed"
                  animate="expanded"
                  exit="collapsed"
                >
                  New Chat
                </motion.span>
              )}
            </AnimatePresence>
          </motion.button>
        </div>

        {/* Navigation */}
        <nav className="session-nav">
          <AnimatePresence>
            {isExpanded && (
              <motion.div 
                className="nav-header"
                variants={contentVariants}
                initial="collapsed"
                animate="expanded"
                exit="collapsed"
              >
                <History size={16} className="nav-icon" />
                <span className="nav-title">Recent Chats</span>
                <motion.div 
                  className="nav-badge"
                  initial={{ scale: 0 }}
                  animate={{ scale: 1 }}
                  transition={{ delay: 0.3, type: "spring", bounce: 0.6 }}
                >
                  {displaySessions.length}
                </motion.div>
              </motion.div>
            )}
          </AnimatePresence>

          <motion.ul 
            className="session-list"
            initial="hidden"
            animate="visible"
            variants={{
              visible: {
                transition: {
                  staggerChildren: 0.05,
                  delayChildren: 0.1
                }
              }
            }}
          >
            <AnimatePresence mode="popLayout">
              {displaySessions.length > 0 ? (
                displaySessions.map((session) => (
                  <SessionItem
                    key={session.id}
                    session={session}
                    activeSessionId={activeSessionId}
                    onSelectSession={onSelectSession}
                    onDeleteSession={onDeleteSession}
                    isExpanded={isExpanded}
                  />
                ))
              ) : (
                <motion.li 
                  className="no-sessions"
                  variants={sessionVariants}
                  initial="hidden"
                  animate="visible"
                  exit="exit"
                >
                  <motion.div
                    className="empty-state"
                    initial={{ scale: 0.9, opacity: 0 }}
                    animate={{ scale: 1, opacity: 1 }}
                    transition={{ delay: 0.2 }}
                  >
                    <motion.div
                      className="empty-icon-wrapper"
                      animate={{ 
                        y: [0, -5, 0],
                        rotate: [0, 5, -5, 0]
                      }}
                      transition={{ 
                        duration: 4,
                        repeat: Infinity,
                        ease: "easeInOut"
                      }}
                    >
                      <MessageSquare size={32} className="empty-icon" />
                      <Sparkles size={16} className="empty-sparkle" />
                    </motion.div>
                    <AnimatePresence>
                      {isExpanded && (
                        <motion.div
                          className="empty-text"
                          variants={contentVariants}
                          initial="collapsed"
                          animate="expanded"
                          exit="collapsed"
                        >
                          <span className="empty-title">No conversations yet</span>
                          <p className="empty-subtitle">Start a new chat to begin your Maya experience</p>
                        </motion.div>
                      )}
                    </AnimatePresence>
                  </motion.div>
                </motion.li>
              )}
            </AnimatePresence>
          </motion.ul>
        </nav>

        {/* Footer */}
        <AnimatePresence>
          {isExpanded && (
            <motion.div 
              className="sidebar-footer"
              variants={contentVariants}
              initial="collapsed"
              animate="expanded"
              exit="collapsed"
            >
              <motion.div 
                className="upgrade-prompt"
                whileHover={{ scale: 1.02, y: -2 }}
                whileTap={{ scale: 0.98 }}
              >
                <motion.div
                  animate={{ 
                    rotate: [0, 10, -10, 0],
                    scale: [1, 1.1, 1]
                  }}
                  transition={{ 
                    duration: 2,
                    repeat: Infinity,
                    ease: "easeInOut"
                  }}
                >
                  <Zap size={16} />
                </motion.div>
                <span>Upgrade to Pro</span>
                <Bookmark size={14} className="pro-badge" />
              </motion.div>
            </motion.div>
          )}
        </AnimatePresence>
      </motion.aside>
    </>
  );
};

export default LeftSidebar;