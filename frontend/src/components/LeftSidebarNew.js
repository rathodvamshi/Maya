// Modern LeftSidebar Component

import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { 
  Plus, 
  MessageSquare, 
  Trash2, 
  ChevronDown,
  ChevronUp,
  Sparkles, 
  Sun,
  Moon,
  Monitor,
  Menu,
  X,
  History,
  User,
  Settings,
  LogOut,
  MoreVertical
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

const dropdownVariants = {
  hidden: {
    opacity: 0,
    height: 0,
    y: -10,
    transition: {
      duration: 0.2,
      ease: "easeIn"
    }
  },
  visible: {
    opacity: 1,
    height: "auto",
    y: 0,
    transition: {
      duration: 0.3,
      ease: "easeOut"
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

// Theme Hook
const useTheme = () => {
  const [theme, setTheme] = useState(() => {
    const savedTheme = localStorage.getItem('maya-theme');
    return savedTheme || 'system';
  });

  useEffect(() => {
    const applyTheme = (newTheme) => {
      const root = document.documentElement;
      
      if (newTheme === 'system') {
        const systemTheme = window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
        root.setAttribute('data-theme', systemTheme);
      } else {
        root.setAttribute('data-theme', newTheme);
      }
    };

    applyTheme(theme);
    localStorage.setItem('maya-theme', theme);

    if (theme === 'system') {
      const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');
      const handleSystemThemeChange = (e) => {
        applyTheme('system');
      };

      mediaQuery.addEventListener('change', handleSystemThemeChange);
      return () => mediaQuery.removeEventListener('change', handleSystemThemeChange);
    }
  }, [theme]);

  return { theme, setTheme };
};

// Theme Toggle Component
const ThemeToggle = ({ theme, onThemeChange, isExpanded }) => {
  const themes = [
    { key: 'light', icon: Sun, label: 'Light' },
    { key: 'dark', icon: Moon, label: 'Dark' },
    { key: 'system', icon: Monitor, label: 'System' }
  ];

  return (
    <div className="theme-toggle-container">
      <AnimatePresence>
        {isExpanded && (
          <motion.div 
            className="theme-label"
            variants={contentVariants}
            initial="collapsed"
            animate="expanded"
            exit="collapsed"
          >
            Theme
          </motion.div>
        )}
      </AnimatePresence>
      
      <div className="theme-buttons">
        {themes.map(({ key, icon: Icon, label }) => (
          <motion.button
            key={key}
            className={`theme-btn ${theme === key ? 'active' : ''}`}
            onClick={() => onThemeChange(key)}
            title={label}
            whileHover={{ scale: 1.1, y: -1 }}
            whileTap={{ scale: 0.95 }}
          >
            <Icon size={16} />
            <AnimatePresence>
              {isExpanded && (
                <motion.span
                  className="theme-btn-text"
                  variants={contentVariants}
                  initial="collapsed"
                  animate="expanded"
                  exit="collapsed"
                >
                  {label}
                </motion.span>
              )}
            </AnimatePresence>
          </motion.button>
        ))}
      </div>
    </div>
  );
};

// Profile Component
const ProfileSection = ({ user, isExpanded, onLogout }) => {
  const [showMenu, setShowMenu] = useState(false);

  const menuItems = [
    { icon: User, label: 'Profile', action: () => console.log('Profile clicked') },
    { icon: Settings, label: 'Settings', action: () => console.log('Settings clicked') },
    { icon: LogOut, label: 'Logout', action: onLogout, variant: 'danger' }
  ];

  return (
    <div className="profile-section">
      <motion.div 
        className="profile-trigger"
        onClick={() => setShowMenu(!showMenu)}
        whileHover={{ scale: 1.02 }}
        whileTap={{ scale: 0.98 }}
      >
        <div className="profile-avatar">
          {user?.avatar ? (
            <img src={user.avatar} alt={user.username} />
          ) : (
            <div className="avatar-placeholder">
              <User size={20} />
            </div>
          )}
        </div>
        
        <AnimatePresence>
          {isExpanded && (
            <motion.div 
              className="profile-info"
              variants={contentVariants}
              initial="collapsed"
              animate="expanded"
              exit="collapsed"
            >
              <span className="profile-username">{user?.username || 'User'}</span>
              <span className="profile-status">Online</span>
            </motion.div>
          )}
        </AnimatePresence>

        <AnimatePresence>
          {isExpanded && (
            <motion.div
              className="profile-menu-trigger"
              variants={contentVariants}
              initial="collapsed"
              animate="expanded"
              exit="collapsed"
            >
              <MoreVertical size={16} />
            </motion.div>
          )}
        </AnimatePresence>
      </motion.div>

      <AnimatePresence>
        {showMenu && (
          <>
            <motion.div
              className="profile-menu-overlay"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              onClick={() => setShowMenu(false)}
            />
            <motion.div
              className="profile-menu"
              initial={{ opacity: 0, y: 10, scale: 0.95 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: 10, scale: 0.95 }}
              transition={{ duration: 0.2 }}
            >
              {menuItems.map((item, index) => (
                <motion.button
                  key={index}
                  className={`profile-menu-item ${item.variant || ''}`}
                  onClick={() => {
                    item.action();
                    setShowMenu(false);
                  }}
                  whileHover={{ backgroundColor: 'var(--glass-bg-hover)' }}
                >
                  <item.icon size={16} />
                  <span>{item.label}</span>
                </motion.button>
              ))}
            </motion.div>
          </>
        )}
      </AnimatePresence>
    </div>
  );
};

// Logout Confirmation Modal
const LogoutModal = ({ isOpen, onConfirm, onCancel }) => {
  if (!isOpen) return null;

  return (
    <AnimatePresence>
      <motion.div
        className="logout-modal-overlay"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        onClick={onCancel}
      >
        <motion.div
          className="logout-modal"
          initial={{ opacity: 0, scale: 0.95, y: 20 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          exit={{ opacity: 0, scale: 0.95, y: 20 }}
          onClick={(e) => e.stopPropagation()}
        >
          <div className="logout-modal-header">
            <h3>Confirm Logout</h3>
          </div>
          <div className="logout-modal-body">
            <p>Are you sure you want to logout? You'll need to sign in again to access your chats.</p>
          </div>
          <div className="logout-modal-actions">
            <motion.button
              className="logout-modal-btn cancel"
              onClick={onCancel}
              whileHover={{ scale: 1.02 }}
              whileTap={{ scale: 0.98 }}
            >
              Cancel
            </motion.button>
            <motion.button
              className="logout-modal-btn confirm"
              onClick={onConfirm}
              whileHover={{ scale: 1.02 }}
              whileTap={{ scale: 0.98 }}
            >
              Logout
            </motion.button>
          </div>
        </motion.div>
      </motion.div>
    </AnimatePresence>
  );
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
      whileHover={{ scale: 1.02, x: 4 }}
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
  isExpanded = true,
  onToggleExpanded,
  user = { username: 'Maya User', avatar: null }
}) => {
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);
  const [isRecentChatsExpanded, setIsRecentChatsExpanded] = useState(false);
  const [showLogoutModal, setShowLogoutModal] = useState(false);
  const { theme, setTheme } = useTheme();

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

  const handleLogout = () => {
    setShowLogoutModal(true);
  };

  const confirmLogout = () => {
    // Add your logout logic here
    console.log('User logged out');
    setShowLogoutModal(false);
    // Example: redirect to login page
    // window.location.href = '/login';
  };

  const cancelLogout = () => {
    setShowLogoutModal(false);
  };

  const toggleRecentChats = () => {
    setIsRecentChatsExpanded(!isRecentChatsExpanded);
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
          whileHover={{ scale: 1.02, y: -1 }}
          whileTap={{ scale: 0.98 }}
        >
          <motion.div
            animate={{ rotate: isExpanded ? 180 : 0 }}
            transition={{ duration: 0.3 }}
          >
            <ChevronDown size={16} />
          </motion.div>
        </motion.button>

        {/* Logo and Title Section */}
        <div className="sidebar-header">
          <motion.div 
            className="logo-section"
            whileHover={{ scale: 1.02 }}
          >
            <motion.div 
              className="logo-wrapper"
              animate={{ 
                rotate: [0, 5, -5, 0],
                scale: [1, 1.05, 1]
              }}
              transition={{ 
                duration: 6,
                repeat: Infinity,
                ease: "easeInOut"
              }}
            >
              <Sparkles className="logo-icon" size={32} />
            </motion.div>
            
            <AnimatePresence>
              {isExpanded && (
                <motion.div 
                  className="logo-text"
                  variants={contentVariants}
                  initial="collapsed"
                  animate="expanded"
                  exit="collapsed"
                >
                  <h1 className="app-title">Maya</h1>
                  <span className="app-subtitle">AI Assistant</span>
                </motion.div>
              )}
            </AnimatePresence>
          </motion.div>

          {/* New Chat Button */}
          <motion.button 
            className="new-chat-btn" 
            onClick={handleNewChat}
            whileHover={{ scale: 1.02, y: -1 }}
            whileTap={{ scale: 0.98 }}
          >
            <motion.div 
              className="btn-icon-wrapper"
              whileHover={{ rotate: 90 }}
              transition={{ duration: 0.3 }}
            >
              <Plus className="btn-icon" size={18} />
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

        {/* Recent Chats Section */}
        <div className="recent-chats-section">
          <motion.button
            className="recent-chats-trigger"
            onClick={toggleRecentChats}
            whileHover={{ scale: 1.02 }}
            whileTap={{ scale: 0.98 }}
          >
            <History size={16} className="recent-icon" />
            <AnimatePresence>
              {isExpanded && (
                <motion.span 
                  className="recent-text"
                  variants={contentVariants}
                  initial="collapsed"
                  animate="expanded"
                  exit="collapsed"
                >
                  Recent Chats
                </motion.span>
              )}
            </AnimatePresence>
            <AnimatePresence>
              {isExpanded && (
                <motion.div
                  className="recent-chevron"
                  animate={{ rotate: isRecentChatsExpanded ? 180 : 0 }}
                  transition={{ duration: 0.3 }}
                  variants={contentVariants}
                  initial="collapsed"
                  animate="expanded"
                  exit="collapsed"
                >
                  <ChevronDown size={16} />
                </motion.div>
              )}
            </AnimatePresence>
          </motion.button>

          {/* Chat History Dropdown */}
          <AnimatePresence>
            {isRecentChatsExpanded && (
              <motion.div
                className="chat-history-dropdown"
                variants={dropdownVariants}
                initial="hidden"
                animate="visible"
                exit="hidden"
              >
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
                          <MessageSquare size={24} className="empty-icon" />
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
                                <p className="empty-subtitle">Start a new chat to begin</p>
                              </motion.div>
                            )}
                          </AnimatePresence>
                        </motion.div>
                      </motion.li>
                    )}
                  </AnimatePresence>
                </motion.ul>
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        {/* Bottom Section */}
        <div className="sidebar-bottom">
          {/* Theme Toggle */}
          <ThemeToggle 
            theme={theme} 
            onThemeChange={setTheme} 
            isExpanded={isExpanded} 
          />

          {/* Profile Section */}
          <ProfileSection 
            user={user} 
            isExpanded={isExpanded} 
            onLogout={handleLogout}
          />
        </div>
      </motion.aside>

      {/* Logout Modal */}
      <LogoutModal 
        isOpen={showLogoutModal}
        onConfirm={confirmLogout}
        onCancel={cancelLogout}
      />
    </>
  );
};

export default LeftSidebar;