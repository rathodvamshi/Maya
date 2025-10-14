import React, { useEffect, useState } from 'react';
import Sidebar from './Sidebar';
import ChatWindow from './ChatWindow';
import '../styles/ChatLayout.css';

const ChatLayout = ({ onNavigate, onLogout, initialChatId }) => {
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [activeChatId, setActiveChatId] = useState(() => {
    try {
      return initialChatId || localStorage.getItem('maya_active_session_id') || '';
    } catch {
      return initialChatId || '';
    }
  });
  const [isMobile, setIsMobile] = useState(() => typeof window !== 'undefined' ? window.innerWidth <= 768 : false);

  useEffect(() => {
    const onResize = () => setIsMobile(window.innerWidth <= 768);
    window.addEventListener('resize', onResize);
    return () => window.removeEventListener('resize', onResize);
  }, []);

  // Keep ChatLayout in sync when parent (e.g., ModernDashboard) selects a session
  useEffect(() => {
    if (initialChatId && initialChatId !== activeChatId) {
      setActiveChatId(initialChatId);
    }
  }, [initialChatId]);

  // Persist last active chat id for reload restoration
  useEffect(() => {
    try {
      if (activeChatId) localStorage.setItem('maya_active_session_id', activeChatId);
      else localStorage.removeItem('maya_active_session_id');
    } catch {}
  }, [activeChatId]);

  // Stay in sync with global active-session changes without reload
  useEffect(() => {
    const onActive = (e) => {
      const id = e?.detail?.id;
      if (id && id !== activeChatId) setActiveChatId(id);
    };
    try { window.addEventListener('maya:active-session', onActive); } catch {}
    return () => { try { window.removeEventListener('maya:active-session', onActive); } catch {} };
  }, [activeChatId]);

  const handleNewChat = () => setActiveChatId('');

  const chatAreaClass = isMobile
    ? 'chat-main-area full-width'
    : `chat-main-area ${sidebarOpen ? 'sidebar-open' : 'sidebar-closed'}`;

  return (
    <div className="chat-layout-root">
      <Sidebar
        isOpen={sidebarOpen}
        onToggle={() => setSidebarOpen(o => !o)}
        mobile={isMobile}
        onRequestClose={() => setSidebarOpen(false)}
        onNewChat={handleNewChat}
        onSelectChat={id => setActiveChatId(id)}
        onNavigate={onNavigate}
        onLogout={onLogout}
      />
      <div className={chatAreaClass}>
        <ChatWindow chatId={activeChatId} onToggleSidebar={() => setSidebarOpen(o => !o)} />
      </div>
    </div>
  );
};

export default ChatLayout;
