// Modern RightSidebar Component

import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  User,
  CheckSquare,
  Trash2,
  Plus,
  Edit3,
  Check,
  Calendar,
  Star,
  Target,
  Clock,
  Settings,
  LogOut,
  ChevronLeft,
  Trophy,
  Zap,
  Activity,
  BarChart3
} from 'lucide-react';
import '../styles/RightSidebarNew.css';

// Animation Variants
const sidebarVariants = {
  expanded: {
    width: 360,
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
    x: 20,
    transition: {
      duration: 0.2,
      ease: "easeIn"
    }
  }
};

const taskVariants = {
  hidden: {
    opacity: 0,
    y: 20,
    scale: 0.95
  },
  visible: {
    opacity: 1,
    y: 0,
    scale: 1,
    transition: {
      duration: 0.3,
      ease: "easeOut"
    }
  },
  exit: {
    opacity: 0,
    x: 20,
    scale: 0.9,
    transition: {
      duration: 0.2,
      ease: "easeIn"
    }
  }
};

const iconVariants = {
  idle: { scale: 1, rotate: 0 },
  hover: { 
    scale: 1.1, 
    rotate: 5,
    transition: { duration: 0.2 }
  },
  tap: { scale: 0.95 }
};

// Task Item Component
const TaskItem = ({ task, onEdit, onComplete, onDelete, isCompleted = false, isExpanded }) => {
  const [isHovered, setIsHovered] = useState(false);

  return (
    <motion.li
      className={`task-item ${isCompleted ? 'completed' : ''}`}
      variants={taskVariants}
      initial="hidden"
      animate="visible"
      exit="exit"
      layout
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
      whileHover={{ scale: 1.02, y: -2 }}
    >
      <div className="task-main">
        <motion.div 
          className="task-priority-indicator"
          animate={{ 
            scale: task.priority === 'high' ? [1, 1.2, 1] : 1,
            opacity: task.priority === 'high' ? [0.7, 1, 0.7] : 0.7
          }}
          transition={{ duration: 2, repeat: task.priority === 'high' ? Infinity : 0 }}
        />
        
        <motion.div 
          className="task-icon-wrapper"
          variants={iconVariants}
          animate={isHovered ? "hover" : "idle"}
        >
          {isCompleted ? (
            <Check size={16} className="task-icon completed" />
          ) : (
            <Target size={16} className="task-icon" />
          )}
        </motion.div>

        <AnimatePresence>
          {isExpanded && (
            <motion.div 
              className="task-content"
              variants={contentVariants}
              initial="collapsed"
              animate="expanded"
              exit="collapsed"
            >
              <span className="task-title">{task.content || task.title || 'Untitled Task'}</span>
              {task.due_date && (
                <div className="task-meta">
                  <Calendar size={12} />
                  <span className="task-due-date">{task.due_date}</span>
                </div>
              )}
              {task.priority && (
                <div className={`task-priority ${task.priority}`}>
                  <div className="priority-dot" />
                  <span>{task.priority.toUpperCase()}</span>
                </div>
              )}
            </motion.div>
          )}
        </AnimatePresence>

        <AnimatePresence>
          {isExpanded && !isCompleted && (
            <motion.div 
              className="task-actions"
              initial={{ opacity: 0, scale: 0.8 }}
              animate={{ 
                opacity: isHovered ? 1 : 0.6,
                scale: 1
              }}
              exit={{ opacity: 0, scale: 0.8 }}
            >
              {onEdit && (
                <motion.button
                  className="action-btn edit-btn"
                  onClick={() => onEdit(task)}
                  variants={iconVariants}
                  whileHover="hover"
                  whileTap="tap"
                  title="Edit task"
                >
                  <Edit3 size={14} />
                </motion.button>
              )}
              {onComplete && (
                <motion.button
                  className="action-btn complete-btn"
                  onClick={() => onComplete(task.id)}
                  variants={iconVariants}
                  whileHover="hover"
                  whileTap="tap"
                  title="Mark as complete"
                >
                  <Check size={14} />
                </motion.button>
              )}
              {onDelete && (
                <motion.button
                  className="action-btn delete-btn"
                  onClick={() => onDelete(task.id)}
                  variants={iconVariants}
                  whileHover="hover"
                  whileTap="tap"
                  title="Delete task"
                >
                  <Trash2 size={14} />
                </motion.button>
              )}
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </motion.li>
  );
};

// Sidebar Icon Component
const SidebarIcon = ({ icon: Icon, label, badge, isActive, onClick, isExpanded }) => (
  <motion.div
    className={`sidebar-icon ${isActive ? 'active' : ''}`}
    onClick={onClick}
    variants={iconVariants}
    initial="idle"
    whileHover="hover"
    whileTap="tap"
    title={!isExpanded ? label : ''}
  >
    <Icon size={20} />
    {badge > 0 && (
      <motion.div
        className="icon-badge"
        initial={{ scale: 0 }}
        animate={{ scale: 1 }}
        transition={{ type: "spring", bounce: 0.6 }}
      >
        {badge}
      </motion.div>
    )}
  </motion.div>
);

// Stats Card Component
const StatsCard = ({ icon: Icon, label, value, trend, color = "primary" }) => (
  <motion.div 
    className={`stats-card ${color}`}
    whileHover={{ scale: 1.02, y: -2 }}
    whileTap={{ scale: 0.98 }}
  >
    <div className="stats-icon">
      <Icon size={18} />
    </div>
    <div className="stats-content">
      <span className="stats-label">{label}</span>
      <div className="stats-value-row">
        <span className="stats-value">{value}</span>
        {trend && (
          <motion.div 
            className={`stats-trend ${trend > 0 ? 'positive' : 'negative'}`}
            initial={{ opacity: 0, x: -10 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: 0.2 }}
          >
            {trend > 0 ? '↗' : '↘'} {Math.abs(trend)}%
          </motion.div>
        )}
      </div>
    </div>
  </motion.div>
);

// Main RightSidebar Component
const RightSidebar = ({
  currentUserEmail,
  pendingTasks = [],
  completedTasks = [],
  handleOpenModal,
  handleMarkAsDone,
  handleClearChat,
  onLogout,
  isExpanded = false,
  onToggleExpanded
}) => {
  const [activeSection, setActiveSection] = useState('profile');
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);

  const handleToggle = () => {
    onToggleExpanded();
  };

  const handleMobileToggle = () => {
    setIsMobileMenuOpen(!isMobileMenuOpen);
  };

  const stats = {
    totalTasks: pendingTasks.length + completedTasks.length,
    completed: completedTasks.length,
    pending: pendingTasks.length,
    completionRate: pendingTasks.length + completedTasks.length > 0 
      ? Math.round((completedTasks.length / (pendingTasks.length + completedTasks.length)) * 100)
      : 0
  };

  return (
    <>
      {/* Mobile Overlay */}
      <AnimatePresence>
        {isMobileMenuOpen && (
          <motion.div
            className="mobile-overlay-right"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={handleMobileToggle}
          />
        )}
      </AnimatePresence>

      {/* Sidebar */}
      <motion.aside 
        className={`right-sidebar ${isMobileMenuOpen ? 'mobile-open' : ''}`}
        variants={sidebarVariants}
        initial="expanded"
        animate={isExpanded ? "expanded" : "collapsed"}
      >
        {/* Background Effects */}
        <div className="sidebar-glass-bg" />
        
        <div className="sidebar-particles">
          <motion.div 
            className="particle particle-1"
            animate={{ 
              y: [0, -20, 0],
              opacity: [0.2, 0.5, 0.2]
            }}
            transition={{ 
              duration: 5,
              repeat: Infinity,
              ease: "easeInOut"
            }}
          />
          <motion.div 
            className="particle particle-2"
            animate={{ 
              y: [0, 15, 0],
              x: [0, -10, 0]
            }}
            transition={{ 
              duration: 7,
              repeat: Infinity,
              ease: "easeInOut"
            }}
          />
        </div>

        {/* Toggle Button */}
        <motion.button 
          className="sidebar-toggle-right" 
          onClick={handleToggle}
          variants={iconVariants}
          whileHover="hover"
          whileTap="tap"
        >
          <motion.div
            animate={{ rotate: isExpanded ? 0 : 180 }}
            transition={{ duration: 0.3 }}
          >
            <ChevronLeft size={16} />
          </motion.div>
        </motion.button>

        {/* Navigation Icons */}
        <div className="sidebar-icons">
          <SidebarIcon 
            icon={User} 
            label="Profile"
            isActive={activeSection === 'profile'}
            onClick={() => setActiveSection('profile')}
            isExpanded={isExpanded}
          />
          <SidebarIcon 
            icon={CheckSquare} 
            label="Tasks"
            badge={pendingTasks.length}
            isActive={activeSection === 'tasks'}
            onClick={() => setActiveSection('tasks')}
            isExpanded={isExpanded}
          />
          <SidebarIcon 
            icon={BarChart3} 
            label="Analytics"
            isActive={activeSection === 'analytics'}
            onClick={() => setActiveSection('analytics')}
            isExpanded={isExpanded}
          />
          <SidebarIcon 
            icon={Settings} 
            label="Settings"
            isActive={activeSection === 'settings'}
            onClick={() => setActiveSection('settings')}
            isExpanded={isExpanded}
          />
        </div>

        {/* Content Area */}
        <div className="sidebar-content">
          <AnimatePresence mode="wait">
            {/* Profile Section */}
            {activeSection === 'profile' && (
              <motion.div 
                key="profile"
                className="sidebar-section"
                variants={contentVariants}
                initial="collapsed"
                animate="expanded"
                exit="collapsed"
              >
                <AnimatePresence>
                  {isExpanded && (
                    <motion.div 
                      className="profile-section"
                      variants={contentVariants}
                      initial="collapsed"
                      animate="expanded"
                      exit="collapsed"
                    >
                      <div className="profile-header">
                        <motion.div 
                          className="profile-avatar"
                          whileHover={{ scale: 1.05, rotate: 5 }}
                        >
                          <User size={24} />
                          <div className="status-dot online" />
                        </motion.div>
                        <div className="profile-info">
                          <h3 className="profile-name">Maya User</h3>
                          <p className="profile-email">{currentUserEmail || 'Loading...'}</p>
                        </div>
                      </div>
                      
                      <div className="profile-stats">
                        <StatsCard 
                          icon={Trophy}
                          label="Completed"
                          value={completedTasks.length}
                          trend={15}
                          color="success"
                        />
                        <StatsCard 
                          icon={Target}
                          label="In Progress"
                          value={pendingTasks.length}
                          color="warning"
                        />
                      </div>

                      <div className="profile-actions">
                        {onLogout && (
                          <motion.button 
                            className="logout-btn"
                            onClick={onLogout}
                            whileHover={{ scale: 1.02, y: -1 }}
                            whileTap={{ scale: 0.98 }}
                          >
                            <LogOut size={16} />
                            <span>Sign Out</span>
                          </motion.button>
                        )}
                      </div>
                    </motion.div>
                  )}
                </AnimatePresence>
              </motion.div>
            )}

            {/* Tasks Section */}
            {activeSection === 'tasks' && (
              <motion.div 
                key="tasks"
                className="sidebar-section"
                variants={contentVariants}
                initial="collapsed"
                animate="expanded"
                exit="collapsed"
              >
                <AnimatePresence>
                  {isExpanded && (
                    <motion.div 
                      className="tasks-section"
                      variants={contentVariants}
                      initial="collapsed"
                      animate="expanded"
                      exit="collapsed"
                    >
                      <div className="section-header">
                        <h3 className="section-title">
                          <CheckSquare size={18} />
                          Tasks ({pendingTasks.length})
                        </h3>
                        {handleOpenModal && (
                          <motion.button 
                            className="add-task-btn"
                            onClick={() => handleOpenModal()}
                            whileHover={{ scale: 1.05, rotate: 90 }}
                            whileTap={{ scale: 0.95 }}
                            title="Add new task"
                          >
                            <Plus size={16} />
                          </motion.button>
                        )}
                      </div>

                      {/* Pending Tasks */}
                      <div className="task-list-container">
                        <motion.ul 
                          className="task-list"
                          initial="hidden"
                          animate="visible"
                          variants={{
                            visible: {
                              transition: {
                                staggerChildren: 0.05
                              }
                            }
                          }}
                        >
                          <AnimatePresence mode="popLayout">
                            {pendingTasks.length > 0 ? (
                              pendingTasks.map((task) => (
                                <TaskItem
                                  key={task.id}
                                  task={task}
                                  onEdit={handleOpenModal}
                                  onComplete={handleMarkAsDone}
                                  isExpanded={isExpanded}
                                />
                              ))
                            ) : (
                              <motion.li 
                                className="no-tasks"
                                variants={taskVariants}
                                initial="hidden"
                                animate="visible"
                              >
                                <div className="no-tasks-content">
                                  <motion.div
                                    animate={{ y: [0, -5, 0] }}
                                    transition={{ duration: 2, repeat: Infinity }}
                                  >
                                    <Target size={32} />
                                  </motion.div>
                                  <p>No pending tasks</p>
                                  <span>Create a new task to get started</span>
                                </div>
                              </motion.li>
                            )}
                          </AnimatePresence>
                        </motion.ul>
                      </div>

                      {/* Completed Tasks */}
                      {completedTasks.length > 0 && (
                        <div className="completed-section">
                          <h4 className="completed-title">
                            <Check size={16} />
                            Completed ({completedTasks.length})
                          </h4>
                          <motion.ul 
                            className="task-list completed-tasks"
                            variants={{
                              visible: {
                                transition: {
                                  staggerChildren: 0.03
                                }
                              }
                            }}
                          >
                            <AnimatePresence>
                              {completedTasks.slice(0, 3).map((task) => (
                                <TaskItem
                                  key={task.id}
                                  task={task}
                                  isCompleted={true}
                                  isExpanded={isExpanded}
                                />
                              ))}
                            </AnimatePresence>
                          </motion.ul>
                        </div>
                      )}
                    </motion.div>
                  )}
                </AnimatePresence>
              </motion.div>
            )}

            {/* Analytics Section */}
            {activeSection === 'analytics' && (
              <motion.div 
                key="analytics"
                className="sidebar-section"
                variants={contentVariants}
                initial="collapsed"
                animate="expanded"
                exit="collapsed"
              >
                <AnimatePresence>
                  {isExpanded && (
                    <motion.div 
                      className="analytics-section"
                      variants={contentVariants}
                      initial="collapsed"
                      animate="expanded"
                      exit="collapsed"
                    >
                      <div className="section-header">
                        <h3 className="section-title">
                          <BarChart3 size={18} />
                          Analytics
                        </h3>
                      </div>

                      <div className="analytics-grid">
                        <StatsCard 
                          icon={Activity}
                          label="Completion Rate"
                          value={`${stats.completionRate}%`}
                          trend={8}
                          color="primary"
                        />
                        <StatsCard 
                          icon={Clock}
                          label="Active Time"
                          value="2.5h"
                          color="info"
                        />
                        <StatsCard 
                          icon={Star}
                          label="Streak"
                          value="7 days"
                          trend={12}
                          color="warning"
                        />
                        <StatsCard 
                          icon={Zap}
                          label="Productivity"
                          value="High"
                          trend={5}
                          color="success"
                        />
                      </div>
                    </motion.div>
                  )}
                </AnimatePresence>
              </motion.div>
            )}

            {/* Settings Section */}
            {activeSection === 'settings' && (
              <motion.div 
                key="settings"
                className="sidebar-section"
                variants={contentVariants}
                initial="collapsed"
                animate="expanded"
                exit="collapsed"
              >
                <AnimatePresence>
                  {isExpanded && (
                    <motion.div 
                      className="settings-section"
                      variants={contentVariants}
                      initial="collapsed"
                      animate="expanded"
                      exit="collapsed"
                    >
                      <div className="section-header">
                        <h3 className="section-title">
                          <Settings size={18} />
                          Settings
                        </h3>
                      </div>

                      <div className="settings-options">
                        {handleClearChat && (
                          <motion.button 
                            className="setting-item clear-chat"
                            onClick={handleClearChat}
                            whileHover={{ scale: 1.02, x: 4 }}
                            whileTap={{ scale: 0.98 }}
                          >
                            <Trash2 size={16} />
                            <span>Clear Chat History</span>
                          </motion.button>
                        )}
                      </div>
                    </motion.div>
                  )}
                </AnimatePresence>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </motion.aside>
    </>
  );
};

export default RightSidebar;