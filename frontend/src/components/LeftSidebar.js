import React, { useState } from 'react';
import { Plus, MessageSquare, Trash2, ChevronRight, Sparkles, Clock, Star } from 'lucide-react';
import '../styles/LeftSidebar.css';

const LeftSidebar = ({
  sessions = [],
  activeSessionId,
  onNewChat,
  onSelectSession,
  onDeleteSession,
}) => {
  const [isExpanded, setIsExpanded] = useState(true);
  const [, setHoveredSession] = useState(null);

  const handleDelete = (e, sessionId) => {
    e.stopPropagation();
    if (window.confirm('Are you sure you want to delete this chat session?')) {
      onDeleteSession(sessionId);
    }
  };

  const toggleSidebar = () => {
    setIsExpanded(!isExpanded);
  };

  const displaySessions = sessions.length > 0 ? sessions : [
  ];

  return (
    <aside className={`left-sidebar ${isExpanded ? 'expanded' : 'collapsed'}`}>
      {/* Toggle Button */}
      <button className="sidebar-toggle" onClick={toggleSidebar}>
        <ChevronRight className={`toggle-icon ${isExpanded ? 'rotated' : ''}`} size={16} />
      </button>

      {/* Header */}
      <div className="sidebar-header">
        <button className="new-chat-btn" onClick={onNewChat}>
          <div className="btn-icon-wrapper">
            <Plus className="btn-icon" size={18} />
            <Sparkles className="sparkle-icon" size={12} />
          </div>
          <span className="btn-text">New Chat</span>
        </button>
      </div>

      {/* Navigation */}
      <nav className="session-nav">
        <div className="nav-header">
          <Clock size={16} className="nav-icon" />
          <span className="nav-title">Recent Chats</span>
          <div className="nav-badge">{displaySessions.length}</div>
        </div>

        <ul className="session-list">
          {displaySessions.length > 0 ? (
            displaySessions.map((session) => (
              <li
                key={session.id}
                className={`session-item ${session.id === activeSessionId ? 'active' : ''}`}
                onClick={() => onSelectSession(session.id)}
                onMouseEnter={() => setHoveredSession(session.id)}
                onMouseLeave={() => setHoveredSession(null)}
              >
                <div className="session-main">
                  <div className="session-icon-wrapper">
                    <MessageSquare size={16} className="session-icon" />
                    {session.isStarred && (
                      <Star size={12} className="star-icon" />
                    )}
                  </div>

                  <div className="session-content">
                    <span className="session-title">{session.title}</span>
                    <span className="session-timestamp">{session.timestamp}</span>
                  </div>

                  <button
                    className="delete-session-btn"
                    title="Delete Session"
                    onClick={(e) => handleDelete(e, session.id)}
                  >
                    <Trash2 size={14}/>
                  </button>
                </div>

                <div className="session-glow"></div>
              </li>
            ))
          ) : (
            <li className="no-sessions">
              <MessageSquare size={24} className="empty-icon" />
              <span>No recent chats</span>
              <p>Start a conversation to see your chat history here</p>
            </li>
          )}
        </ul>
      </nav>

      {/* Footer */}
      <div className="sidebar-footer">
        <div className="upgrade-prompt">
          <Sparkles size={16} />
          <span>Upgrade to Pro</span>
        </div>
      </div>
    </aside>
  );
};

export default LeftSidebar;
