// Command Palette Component for Quick Navigation and Actions
import React, { useState, useEffect, useRef, useMemo } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import '../styles/CommandPalette.css';
import { 
  Search, 
  MessageSquare, 
  CheckSquare, 
  User, 
  Plus, 
  Settings, 
  Sun, 
  Moon, 
  ArrowRight,
  Clock,
  Hash,
  Command
} from 'lucide-react';

const CommandPalette = ({ isOpen, onClose, onViewChange, searchQuery: initialQuery = '' }) => {
  // ========================
  // State Management
  // ========================
  const [query, setQuery] = useState(initialQuery);
  const [selectedIndex, setSelectedIndex] = useState(0);
  const [filteredCommands, setFilteredCommands] = useState([]);
  const [recentCommands, setRecentCommands] = useState([]);
  const [reducedMotion, setReducedMotion] = useState(false);

  // ========================
  // Refs
  // ========================
  const inputRef = useRef(null);
  const listRef = useRef(null);

  // ========================
  // Effects
  // ========================
  useEffect(() => {
    if (isOpen) {
      setQuery(initialQuery);
      inputRef.current?.focus();
      loadRecentCommands();
    }
  }, [isOpen, initialQuery]);

  useEffect(() => {
    // Check reduced motion preference
    const hasReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches ||
                            localStorage.getItem('maya-reduced-motion') === 'true';
    setReducedMotion(hasReducedMotion);
  }, []);

  // ========================
  // Commands Data
  // ========================
  const allCommands = useMemo(() => [
    // Navigation
    {
      id: 'nav-chat',
      title: 'Go to Chat',
      description: 'Switch to chat interface',
      category: 'Navigation',
      icon: <MessageSquare size={16} />,
      action: () => onViewChange('chat'),
      keywords: ['chat', 'conversation', 'talk', 'ai', 'assistant']
    },
    {
      id: 'nav-tasks',
      title: 'Go to Tasks',
      description: 'Switch to task management',
      category: 'Navigation',
      icon: <CheckSquare size={16} />,
      action: () => onViewChange('tasks'),
      keywords: ['tasks', 'todo', 'work', 'projects', 'manage']
    },
    {
      id: 'nav-profile',
      title: 'Go to Profile',
      description: 'View and edit your profile',
      category: 'Navigation',
      icon: <User size={16} />,
      action: () => onViewChange('profile'),
      keywords: ['profile', 'account', 'settings', 'user', 'me']
    },

    // Actions
    {
      id: 'action-new-chat',
      title: 'New Chat',
      description: 'Start a new conversation',
      category: 'Actions',
      icon: <Plus size={16} />,
      action: () => {
        onViewChange('chat');
        // Trigger new chat creation
        console.log('Creating new chat...');
      },
      keywords: ['new', 'chat', 'create', 'conversation', 'start']
    },
    {
      id: 'action-new-task',
      title: 'New Task',
      description: 'Create a new task',
      category: 'Actions',
      icon: <Plus size={16} />,
      action: () => {
        onViewChange('tasks');
        // Trigger new task creation
        console.log('Creating new task...');
      },
      keywords: ['new', 'task', 'create', 'todo', 'add']
    },

    // Settings
    {
      id: 'setting-theme-light',
      title: 'Switch to Light Mode',
      description: 'Change theme to light mode',
      category: 'Settings',
      icon: <Sun size={16} />,
      action: () => {
        const event = new CustomEvent('theme-change', { detail: 'light' });
        window.dispatchEvent(event);
      },
      keywords: ['light', 'theme', 'bright', 'white']
    },
    {
      id: 'setting-theme-dark',
      title: 'Switch to Dark Mode',
      description: 'Change theme to dark mode',
      category: 'Settings',
      icon: <Moon size={16} />,
      action: () => {
        const event = new CustomEvent('theme-change', { detail: 'dark' });
        window.dispatchEvent(event);
      },
      keywords: ['dark', 'theme', 'night', 'black']
    },

    // Mock chat sessions
    {
      id: 'chat-1',
      title: 'API Integration Help',
      description: 'Recent chat about API integration',
      category: 'Recent Chats',
      icon: <MessageSquare size={16} />,
      action: () => {
        onViewChange('chat');
        console.log('Opening chat session 1');
      },
      keywords: ['api', 'integration', 'help', 'chat']
    },
    {
      id: 'chat-2',
      title: 'React Components',
      description: 'Discussion about React components',
      category: 'Recent Chats',
      icon: <MessageSquare size={16} />,
      action: () => {
        onViewChange('chat');
        console.log('Opening chat session 2');
      },
      keywords: ['react', 'components', 'frontend', 'chat']
    },

    // Mock tasks
    {
      id: 'task-1',
      title: 'Implement user authentication',
      description: 'High priority task due today',
      category: 'Tasks',
      icon: <CheckSquare size={16} />,
      action: () => {
        onViewChange('tasks');
        console.log('Opening task 1');
      },
      keywords: ['authentication', 'user', 'login', 'security', 'task']
    },
    {
      id: 'task-2',
      title: 'Design database schema',
      description: 'Medium priority task',
      category: 'Tasks',
      icon: <CheckSquare size={16} />,
      action: () => {
        onViewChange('tasks');
        console.log('Opening task 2');
      },
      keywords: ['database', 'schema', 'design', 'data', 'task']
    }
  ], [onViewChange]);

  // ========================
  // Filtering Logic
  // ========================
  const searchCommands = useMemo(() => {
    if (!query.trim()) {
      // Show recent commands if no query
      const recent = recentCommands.map(recentId => 
        allCommands.find(cmd => cmd.id === recentId)
      ).filter(Boolean);
      
      // Fill remaining slots with popular commands
      const popular = allCommands.filter(cmd => 
        ['nav-chat', 'nav-tasks', 'action-new-chat', 'action-new-task'].includes(cmd.id)
      );
      
      return [...recent, ...popular.filter(cmd => !recent.some(r => r.id === cmd.id))].slice(0, 8);
    }

    const searchTerm = query.toLowerCase();
    return allCommands
      .map(command => {
        let score = 0;
        
        // Title match (highest priority)
        if (command.title.toLowerCase().includes(searchTerm)) {
          score += 100;
          if (command.title.toLowerCase().startsWith(searchTerm)) {
            score += 50;
          }
        }
        
        // Description match
        if (command.description.toLowerCase().includes(searchTerm)) {
          score += 50;
        }
        
        // Keywords match
        const keywordMatches = command.keywords.filter(keyword => 
          keyword.toLowerCase().includes(searchTerm)
        ).length;
        score += keywordMatches * 25;
        
        // Category match
        if (command.category.toLowerCase().includes(searchTerm)) {
          score += 25;
        }
        
        return { ...command, score };
      })
      .filter(command => command.score > 0)
      .sort((a, b) => b.score - a.score)
      .slice(0, 8);
  }, [query, allCommands, recentCommands]);

  useEffect(() => {
    setFilteredCommands(searchCommands);
    setSelectedIndex(0);
  }, [searchCommands]);

  // ========================
  // Recent Commands Management
  // ========================
  const loadRecentCommands = () => {
    try {
      const stored = localStorage.getItem('maya-recent-commands');
      if (stored) {
        setRecentCommands(JSON.parse(stored));
      }
    } catch (error) {
      console.error('Error loading recent commands:', error);
    }
  };

  const addToRecentCommands = (commandId) => {
    try {
      const updated = [commandId, ...recentCommands.filter(id => id !== commandId)].slice(0, 5);
      setRecentCommands(updated);
      localStorage.setItem('maya-recent-commands', JSON.stringify(updated));
    } catch (error) {
      console.error('Error saving recent commands:', error);
    }
  };

  // ========================
  // Event Handlers
  // ========================
  const handleKeyDown = (e) => {
    switch (e.key) {
      case 'ArrowDown':
        e.preventDefault();
        setSelectedIndex(prev => 
          prev < filteredCommands.length - 1 ? prev + 1 : 0
        );
        break;
      case 'ArrowUp':
        e.preventDefault();
        setSelectedIndex(prev => 
          prev > 0 ? prev - 1 : filteredCommands.length - 1
        );
        break;
      case 'Enter':
        e.preventDefault();
        if (filteredCommands[selectedIndex]) {
          executeCommand(filteredCommands[selectedIndex]);
        }
        break;
      case 'Escape':
        onClose();
        break;
      default:
        break;
    }
  };

  const executeCommand = (command) => {
    addToRecentCommands(command.id);
    command.action();
    onClose();
  };

  // ========================
  // Render Helpers
  // ========================
  const getCategoryIcon = (category) => {
    switch (category) {
      case 'Navigation':
        return <ArrowRight size={14} />;
      case 'Actions':
        return <Plus size={14} />;
      case 'Settings':
        return <Settings size={14} />;
      case 'Recent Chats':
        return <Clock size={14} />;
      case 'Tasks':
        return <Hash size={14} />;
      default:
        return <Command size={14} />;
    }
  };

  const highlightQuery = (text) => {
    if (!query.trim()) return text;
    
    const regex = new RegExp(`(${query.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')})`, 'gi');
    return text.split(regex).map((part, index) => 
      regex.test(part) ? (
        <mark key={index} className="highlight">{part}</mark>
      ) : (
        part
      )
    );
  };

  // ========================
  // Animation Variants
  // ========================
  const overlayVariants = {
    initial: { opacity: 0 },
    animate: { opacity: 1 },
    exit: { opacity: 0 }
  };

  const paletteVariants = {
    initial: { 
      opacity: 0, 
      scale: reducedMotion ? 1 : 0.9, 
      y: reducedMotion ? 0 : -20 
    },
    animate: { 
      opacity: 1, 
      scale: 1, 
      y: 0,
      transition: { 
        duration: reducedMotion ? 0 : 0.2,
        ease: [0.4, 0.0, 0.2, 1]
      }
    },
    exit: { 
      opacity: 0, 
      scale: reducedMotion ? 1 : 0.9, 
      y: reducedMotion ? 0 : -20,
      transition: { 
        duration: reducedMotion ? 0 : 0.15 
      }
    }
  };

  const itemVariants = {
    initial: { opacity: 0, x: -10 },
    animate: { opacity: 1, x: 0 },
    exit: { opacity: 0, x: -10 }
  };

  // ========================
  // Main Render
  // ========================
  return (
    <AnimatePresence>
      {isOpen && (
        <motion.div
          className="command-palette-overlay"
          variants={overlayVariants}
          initial="initial"
          animate="animate"
          exit="exit"
          onClick={onClose}
        >
          <motion.div
            className="command-palette"
            variants={paletteVariants}
            initial="initial"
            animate="animate"
            exit="exit"
            onClick={(e) => e.stopPropagation()}
          >
            {/* Header */}
            <div className="palette-header">
              <div className="search-container">
                <Search size={18} className="search-icon" />
                <input
                  ref={inputRef}
                  type="text"
                  placeholder="Type a command or search..."
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  onKeyDown={handleKeyDown}
                  className="search-input"
                />
                <div className="search-hint">
                  <kbd>↑</kbd><kbd>↓</kbd> navigate <kbd>↵</kbd> select <kbd>esc</kbd> close
                </div>
              </div>
            </div>

            {/* Results */}
            <div className="palette-body">
              {filteredCommands.length > 0 ? (
                <div className="command-list" ref={listRef}>
                  {filteredCommands.map((command, index) => (
                    <motion.div
                      key={command.id}
                      className={`command-item ${index === selectedIndex ? 'selected' : ''}`}
                      variants={itemVariants}
                      initial="initial"
                      animate="animate"
                      exit="exit"
                      transition={{ 
                        duration: reducedMotion ? 0 : 0.15, 
                        delay: reducedMotion ? 0 : index * 0.02 
                      }}
                      onClick={() => executeCommand(command)}
                      onMouseEnter={() => setSelectedIndex(index)}
                    >
                      <div className="command-icon">
                        {command.icon}
                      </div>
                      
                      <div className="command-content">
                        <div className="command-title">
                          {highlightQuery(command.title)}
                        </div>
                        <div className="command-description">
                          {highlightQuery(command.description)}
                        </div>
                      </div>
                      
                      <div className="command-meta">
                        <div className="command-category">
                          {getCategoryIcon(command.category)}
                          <span>{command.category}</span>
                        </div>
                      </div>
                    </motion.div>
                  ))}
                </div>
              ) : (
                <div className="empty-state">
                  <Search size={32} />
                  <h3>No commands found</h3>
                  <p>Try a different search term</p>
                </div>
              )}
            </div>

            {/* Footer */}
            <div className="palette-footer">
              <div className="footer-section">
                <span className="footer-label">Recent</span>
                <div className="footer-items">
                  {recentCommands.slice(0, 3).map(commandId => {
                    const command = allCommands.find(c => c.id === commandId);
                    return command ? (
                      <button
                        key={command.id}
                        className="footer-item"
                        onClick={() => executeCommand(command)}
                      >
                        {command.icon}
                        <span>{command.title}</span>
                      </button>
                    ) : null;
                  })}
                </div>
              </div>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
};

export default CommandPalette;