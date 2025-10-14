// Modern Tasks Interface with Kanban, Bulk Actions, and Enhanced UX
import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import '../styles/TasksInterface.css';
import taskService from '../services/taskService';
import { 
  Plus, 
  Search, 
  Filter, 
  Calendar, 
  Tag, 
  Check, 
  Clock, 
  MoreHorizontal,
  Edit3,
  Trash2,
  CheckSquare,
  Square,
  ChevronDown,
  LayoutGrid,
  List,
  AlertCircle,
  CheckCircle2,
  Circle
} from 'lucide-react';

const TasksInterface = () => {
  // ========================
  // State Management
  // ========================
  const [tasks, setTasks] = useState([]);
  const [loading, setLoading] = useState(false);
  const [viewMode, setViewMode] = useState('split'); // 'split', 'kanban', 'list'
  const [filterState, setFilterState] = useState({
    search: '',
    priority: 'all',
    status: 'all',
    tag: 'all',
    dateRange: 'all'
  });
  const [activeFilters, setActiveFilters] = useState({
    status: null,
    priority: null,
    tags: [],
    dueSoon: false,
    overdue: false
  });
  const [bulkSelectMode, setBulkSelectMode] = useState(false);
  const [selectedTasks, setSelectedTasks] = useState(new Set());
  const [showQuickAdd, setShowQuickAdd] = useState(false);
  const [quickAddText, setQuickAddText] = useState('');
  const [quickAddPriority, setQuickAddPriority] = useState('medium');
  const [sortBy, setSortBy] = useState('created');
  const [sortOrder, setSortOrder] = useState('desc');
  const [expandedGroups, setExpandedGroups] = useState(new Set(['today', 'thisWeek', 'later']));
  const [showOtpModal, setShowOtpModal] = useState(false);
  const [otpTask, setOtpTask] = useState(null);
  const [otpCode, setOtpCode] = useState('');
  const [showRescheduleModal, setShowRescheduleModal] = useState(false);
  const [rescheduleTask, setRescheduleTask] = useState(null);
  const [newDueDate, setNewDueDate] = useState('');

  // ========================
  // Effects
  // ========================
  useEffect(() => {
    loadTasks();
    
    // Load preferences
    const savedViewMode = localStorage.getItem('maya-tasks-view-mode') || 'split';
    const savedKanbanEnabled = localStorage.getItem('maya-tasks-kanban-enabled') === 'true';
    
    setViewMode(savedViewMode);
    
    // Check reduced motion preference
    const hasReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches ||
                            localStorage.getItem('maya-reduced-motion') === 'true';
    setReducedMotion(hasReducedMotion);
  }, []);

  // ========================
  // Data Loading & Management
  // ========================
  const loadTasks = async () => {
    try {
      setLoading(true);
      
      // Build filters for API call
      const filters = {
        status: activeFilters.status,
        priority: activeFilters.priority,
        tag: activeFilters.tags.length > 0 ? activeFilters.tags[0] : undefined,
        due_soon: activeFilters.dueSoon,
        overdue: activeFilters.overdue,
        limit: 100
      };

      const result = await taskService.getTasks(filters);
      
      if (result.success) {
        setTasks(result.data);
      } else {
        console.error('Failed to load tasks:', result.error);
        // Show error notification
        if (window.addNotification) {
          window.addNotification({
            type: 'error',
            title: 'Failed to Load Tasks',
            message: result.error || 'Unable to fetch tasks from server'
          });
        }
      }
    } catch (error) {
      console.error('Error loading tasks:', error);
      if (window.addNotification) {
        window.addNotification({
          type: 'error',
          title: 'Network Error',
          message: 'Unable to connect to server'
        });
      }
    } finally {
      setLoading(false);
    }
  };

  // ========================
  // Task CRUD Operations
  // ========================
  
  const createTask = async (taskData) => {
    try {
      const result = await taskService.createTask(taskData);
      if (result.success) {
        await loadTasks(); // Reload tasks
        if (window.addNotification) {
          window.addNotification({
            type: 'success',
            title: 'Task Created',
            message: `Task "${taskData.title}" created successfully`
          });
        }
        return result.data;
      } else {
        throw new Error(result.error);
      }
    } catch (error) {
      console.error('Error creating task:', error);
      if (window.addNotification) {
        window.addNotification({
          type: 'error',
          title: 'Failed to Create Task',
          message: error.message || 'Unable to create task'
        });
      }
      throw error;
    }
  };

  const updateTask = async (taskId, updates) => {
    try {
      const result = await taskService.updateTask(taskId, updates);
      if (result.success) {
        await loadTasks(); // Reload tasks
        if (window.addNotification) {
          window.addNotification({
            type: 'success',
            title: 'Task Updated',
            message: 'Task updated successfully'
          });
        }
        return result.data;
      } else {
        throw new Error(result.error);
      }
    } catch (error) {
      console.error('Error updating task:', error);
      if (window.addNotification) {
        window.addNotification({
          type: 'error',
          title: 'Failed to Update Task',
          message: error.message || 'Unable to update task'
        });
      }
      throw error;
    }
  };

  const deleteTask = async (taskId) => {
    try {
      const result = await taskService.deleteTask(taskId);
      if (result.success) {
        await loadTasks(); // Reload tasks
        if (window.addNotification) {
          window.addNotification({
            type: 'success',
            title: 'Task Deleted',
            message: 'Task deleted successfully'
          });
        }
      } else {
        throw new Error(result.error);
      }
    } catch (error) {
      console.error('Error deleting task:', error);
      if (window.addNotification) {
        window.addNotification({
          type: 'error',
          title: 'Failed to Delete Task',
          message: error.message || 'Unable to delete task'
        });
      }
      throw error;
    }
  };

  // ========================
  // Computed Values
  // ========================
  const taskCounts = useMemo(() => {
    const pending = tasks.filter(t => t.status !== 'done').length;
    const completed = tasks.filter(t => t.status === 'done').length;
    const overdue = tasks.filter(t => 
      t.status !== 'done' && 
      t.due_date && 
      new Date(t.due_date) < new Date()
    ).length;
    
    return { pending, completed, overdue, total: tasks.length };
  }, [tasks]);

  const progressPercentage = useMemo(() => {
    if (taskCounts.total === 0) return 0;
    return Math.round((taskCounts.completed / taskCounts.total) * 100);
  }, [taskCounts]);

  const filteredTasks = useMemo(() => {
    return tasks.filter(task => {
      // Search filter
      if (filterState.search && 
          !task.title.toLowerCase().includes(filterState.search.toLowerCase()) &&
          !task.description?.toLowerCase().includes(filterState.search.toLowerCase())) {
        return false;
      }

      // Priority filter
      if (filterState.priority !== 'all' && task.priority !== filterState.priority) {
        return false;
      }

      // Status filter
      if (filterState.status !== 'all') {
        if (filterState.status === 'pending' && task.status === 'done') return false;
        if (filterState.status === 'completed' && task.status !== 'done') return false;
      }

      // Tag filter
      if (filterState.tag !== 'all' && !task.tags.includes(filterState.tag)) {
        return false;
      }

      return true;
    });
  }, [tasks, filterState]);

  const groupedTasks = useMemo(() => {
    const pending = filteredTasks.filter(t => t.status !== 'done');
    const completed = filteredTasks.filter(t => t.status === 'done');
    
    const today = new Date();
    const tomorrow = new Date(today.getTime() + 86400000);
    const nextWeek = new Date(today.getTime() + 604800000);

    const groupedPending = {
      overdue: pending.filter(t => t.due_date && new Date(t.due_date) < today),
      today: pending.filter(t => {
        if (!t.due_date) return false;
        const due = new Date(t.due_date);
        return due >= today && due < tomorrow;
      }),
      thisWeek: pending.filter(t => {
        if (!t.due_date) return false;
        const due = new Date(t.due_date);
        return due >= tomorrow && due < nextWeek;
      }),
      later: pending.filter(t => t.due_date && new Date(t.due_date) >= nextWeek)
    };

    return { ...groupedPending, completed };
  }, [filteredTasks]);

  const allTags = useMemo(() => {
    const tagSet = new Set();
    tasks.forEach(task => task.tags.forEach(tag => tagSet.add(tag)));
    return Array.from(tagSet);
  }, [tasks]);

  // ========================
  // Handlers
  // ========================
  const handleQuickAdd = async () => {
    if (!quickAddText.trim()) return;

    try {
      const taskData = {
        title: quickAddText.trim(),
        description: '',
        status: 'pending',
        priority: quickAddPriority,
        due_date: new Date(Date.now() + 86400000).toISOString() // Tomorrow by default
      };

      await createTask(taskData);
      setQuickAddText('');
      setShowQuickAdd(false);
    } catch (error) {
      console.error('Error creating quick task:', error);
    }
  };

  const handleTaskToggle = async (taskId) => {
    const task = tasks.find(t => t._id === taskId);
    if (!task) return;
    
    const newStatus = task.status === 'done' ? 'pending' : 'done';
    await updateTask(taskId, { 
      status: newStatus,
      completed_at: newStatus === 'done' ? new Date().toISOString() : null
    });
  };

  const handleTaskDelete = async (taskId) => {
    if (window.confirm('Are you sure you want to delete this task?')) {
      try {
        await deleteTask(taskId);
        setSelectedTasks(prev => {
          const newSet = new Set(prev);
          newSet.delete(taskId);
          return newSet;
        });
      } catch (error) {
        console.error('Error deleting task:', error);
      }
    }
  };

  const handleTaskSnooze = async (taskId, preset) => {
    const snoozeTime = {
      '1d': 86400000,
      '3d': 259200000,
      '1w': 604800000
    };

    try {
      const newDueDate = new Date(Date.now() + snoozeTime[preset]).toISOString();
      await updateTask(taskId, { 
        due_date: newDueDate,
        status: 'pending' // Reset to pending when snoozed
      });
    } catch (error) {
      console.error('Error snoozing task:', error);
    }
  };

  const handleOtpVerification = async (taskId) => {
    const task = tasks.find(t => t._id === taskId);
    if (!task) return;
    
    setOtpTask(task);
    setShowOtpModal(true);
  };

  const verifyOtp = async () => {
    if (!otpCode.trim() || !otpTask) return;

    try {
      const result = await taskService.verifyOtp(otpTask._id, otpCode);
      if (result.success) {
        if (window.addNotification) {
          window.addNotification({
            type: 'success',
            title: 'OTP Verified',
            message: 'Task reminder verified successfully!'
          });
        }
        setShowOtpModal(false);
        setOtpCode('');
        setOtpTask(null);
        await loadTasks(); // Refresh tasks
      } else {
        if (window.addNotification) {
          window.addNotification({
            type: 'error',
            title: 'Invalid OTP',
            message: result.error || 'Please check your OTP and try again'
          });
        }
      }
    } catch (error) {
      console.error('Error verifying OTP:', error);
      if (window.addNotification) {
        window.addNotification({
          type: 'error',
          title: 'Verification Failed',
          message: 'Unable to verify OTP. Please try again.'
        });
      }
    }
  };

  const handleReschedule = async (taskId) => {
    const task = tasks.find(t => t._id === taskId);
    if (!task) return;
    
    setRescheduleTask(task);
    setNewDueDate(task.due_date ? new Date(task.due_date).toISOString().slice(0, 16) : '');
    setShowRescheduleModal(true);
  };

  const rescheduleTaskConfirm = async () => {
    if (!newDueDate || !rescheduleTask) return;

    try {
      const result = await taskService.rescheduleTask(rescheduleTask._id, {
        due_date: new Date(newDueDate).toISOString()
      });
      
      if (result.success) {
        if (window.addNotification) {
          window.addNotification({
            type: 'success',
            title: 'Task Rescheduled',
            message: 'Task has been rescheduled successfully!'
          });
        }
        setShowRescheduleModal(false);
        setNewDueDate('');
        setRescheduleTask(null);
        await loadTasks(); // Refresh tasks
      } else {
        throw new Error(result.error);
      }
    } catch (error) {
      console.error('Error rescheduling task:', error);
      if (window.addNotification) {
        window.addNotification({
          type: 'error',
          title: 'Reschedule Failed',
          message: error.message || 'Unable to reschedule task. Please try again.'
        });
      }
    }
  };

  const handleBulkAction = async (action) => {
    const taskIds = Array.from(selectedTasks);
    
    try {
      switch (action) {
        case 'complete':
          // Bulk update tasks to completed
          for (const taskId of taskIds) {
            await updateTask(taskId, { 
              status: 'done', 
              completed_at: new Date().toISOString() 
            });
          }
          break;
        case 'delete':
          if (window.confirm(`Are you sure you want to delete ${taskIds.length} tasks?`)) {
            for (const taskId of taskIds) {
              await deleteTask(taskId);
            }
          }
          break;
        case 'snooze':
          const snoozeDate = new Date(Date.now() + 86400000).toISOString();
          for (const taskId of taskIds) {
            await updateTask(taskId, { 
              due_date: snoozeDate,
              status: 'pending'
            });
          }
          break;
        default:
          break;
      }
    } catch (error) {
      console.error('Error performing bulk action:', error);
    }
    
    setSelectedTasks(new Set());
    setBulkSelectMode(false);
  };

  const handleTaskSelect = (taskId, selected) => {
    setSelectedTasks(prev => {
      const newSet = new Set(prev);
      if (selected) {
        newSet.add(taskId);
      } else {
        newSet.delete(taskId);
      }
      return newSet;
    });
  };

  const handleSelectAll = (tasks, selected) => {
    setSelectedTasks(prev => {
      const newSet = new Set(prev);
      tasks.forEach(task => {
        if (selected) {
          newSet.add(task._id);
        } else {
          newSet.delete(task._id);
        }
      });
      return newSet;
    });
  };

  const toggleViewMode = () => {
    const modes = ['split', 'kanban', 'list'];
    const currentIndex = modes.indexOf(viewMode);
    const nextMode = modes[(currentIndex + 1) % modes.length];
    setViewMode(nextMode);
    localStorage.setItem('maya-tasks-view-mode', nextMode);
  };

  // ========================
  // Components
  // ========================
  const TaskCard = ({ task, showCheckbox = false }) => {
    const isSelected = selectedTasks.has(task._id);
    const isOverdue = task.status !== 'done' && task.due_date && new Date(task.due_date) < new Date();
    
    const priorityColors = {
      low: 'var(--color-success)',
      medium: 'var(--color-warn)',
      high: 'var(--color-danger)'
    };

    return (
      <motion.div
        className={`task-card ${task.status === 'done' ? 'completed' : ''} ${isSelected ? 'selected' : ''} ${isOverdue ? 'overdue' : ''}`}
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        exit={{ opacity: 0, y: -20 }}
        transition={{ duration: reducedMotion ? 0 : 0.2 }}
        layout
      >
        <div className="task-header">
          {showCheckbox && (
            <label className="task-checkbox">
              <input
                type="checkbox"
                checked={isSelected}
                onChange={(e) => handleTaskSelect(task._id, e.target.checked)}
              />
              <span className="checkmark"></span>
            </label>
          )}

          <button
            className="task-complete-button"
            onClick={() => handleTaskToggle(task._id)}
            aria-label={task.status === 'done' ? 'Mark as incomplete' : 'Mark as complete'}
          >
            {task.status === 'done' ? (
              <CheckCircle2 className="completed-icon" size={20} />
            ) : (
              <Circle className="pending-icon" size={20} />
            )}
          </button>

          <div
            className="task-priority"
            style={{ backgroundColor: priorityColors[task.priority] }}
            title={`${task.priority} priority`}
          />
        </div>

        <div className="task-content">
          <h3 className="task-title">{task.title}</h3>
          {task.description && (
            <p className="task-description">{task.description}</p>
          )}

          <div className="task-meta">
            {task.due_date && (
              <div className="task-due-date">
                <Calendar size={14} />
                <span className={isOverdue ? 'overdue' : ''}>
                  {new Date(task.due_date).toLocaleDateString()}
                </span>
              </div>
            )}

            {task.tags.length > 0 && (
              <div className="task-tags">
                {task.tags.slice(0, 3).map(tag => (
                  <span key={tag} className="task-tag">
                    {tag}
                  </span>
                ))}
                {task.tags.length > 3 && (
                  <span className="task-tag-more">+{task.tags.length - 3}</span>
                )}
              </div>
            )}
          </div>

          {task.snoozed && (
            <div className="task-snoozed">
              <Clock size={12} />
              <span>Snoozed until {new Date(task.snoozeUntil).toLocaleDateString()}</span>
            </div>
          )}
        </div>

        <div className="task-actions">
          <button
            className="task-action-button"
            onClick={() => console.log('Edit task:', task._id)}
            title="Edit task"
          >
            <Edit3 size={16} />
          </button>

          <button
            className="task-action-button"
            onClick={() => handleReschedule(task._id)}
            title="Reschedule task"
          >
            <Calendar size={16} />
          </button>

          <div className="task-snooze-dropdown">
            <button className="task-action-button" title="Snooze task">
              <Clock size={16} />
            </button>
            <div className="snooze-menu">
              <button onClick={() => handleTaskSnooze(task._id, '1d')}>1 Day</button>
              <button onClick={() => handleTaskSnooze(task._id, '3d')}>3 Days</button>
              <button onClick={() => handleTaskSnooze(task._id, '1w')}>1 Week</button>
            </div>
          </div>

          {task.metadata?.otp_verified_at ? (
            <button
              className="task-action-button success"
              title="OTP Verified"
              disabled
            >
              <CheckCircle2 size={16} />
            </button>
          ) : (
            <button
              className="task-action-button"
              onClick={() => handleOtpVerification(task._id)}
              title="Verify OTP"
            >
              <Check size={16} />
            </button>
          )}

          <button
            className="task-action-button danger"
            onClick={() => handleTaskDelete(task._id)}
            title="Delete task"
          >
            <Trash2 size={16} />
          </button>
        </div>
      </motion.div>
    );
  };

  const TaskGroup = ({ title, tasks, icon, collapsible = true }) => {
    const isExpanded = expandedGroups.has(title.toLowerCase().replace(' ', ''));
    const groupTasks = tasks || [];
    const allSelected = groupTasks.length > 0 && groupTasks.every(task => selectedTasks.has(task._id));
    const someSelected = groupTasks.some(task => selectedTasks.has(task._id));

    const toggleGroup = () => {
      if (!collapsible) return;
      
      setExpandedGroups(prev => {
        const newSet = new Set(prev);
        const key = title.toLowerCase().replace(' ', '');
        if (newSet.has(key)) {
          newSet.delete(key);
        } else {
          newSet.add(key);
        }
        return newSet;
      });
    };

    return (
      <div className="task-group">
        <div className="task-group-header">
          <button
            className="task-group-toggle"
            onClick={toggleGroup}
            disabled={!collapsible}
          >
            {collapsible && (
              <ChevronDown 
                className={`group-chevron ${isExpanded ? 'expanded' : ''}`} 
                size={16} 
              />
            )}
            {icon}
            <span className="group-title">{title}</span>
            <span className="group-count">({groupTasks.length})</span>
          </button>

          {bulkSelectMode && groupTasks.length > 0 && (
            <label className="group-checkbox">
              <input
                type="checkbox"
                checked={allSelected}
                ref={input => {
                  if (input) input.indeterminate = someSelected && !allSelected;
                }}
                onChange={(e) => handleSelectAll(groupTasks, e.target.checked)}
              />
              <span className="checkmark"></span>
            </label>
          )}
        </div>

        <AnimatePresence>
          {isExpanded && (
            <motion.div
              className="task-group-content"
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: 'auto' }}
              exit={{ opacity: 0, height: 0 }}
              transition={{ duration: reducedMotion ? 0 : 0.3 }}
            >
              {groupTasks.map(task => (
                <TaskCard
                  key={task._id}
                  task={task}
                  showCheckbox={bulkSelectMode}
                />
              ))}
              
              {groupTasks.length === 0 && (
                <div className="empty-group">
                  <p>No tasks in this group</p>
                </div>
              )}
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    );
  };

  // ========================
  // Main Render
  // ========================
  return (
    <div className="tasks-interface modern-tasks">
      {/* Header */}
      <div className="tasks-header">
        <div className="tasks-title">
          <h1>Tasks</h1>
          <div className="tasks-stats">
            <span className="stat">
              <span className="stat-value">{taskCounts.pending}</span>
              <span className="stat-label">Pending</span>
            </span>
            <span className="stat">
              <span className="stat-value">{taskCounts.completed}</span>
              <span className="stat-label">Completed</span>
            </span>
            {taskCounts.overdue > 0 && (
              <span className="stat overdue">
                <span className="stat-value">{taskCounts.overdue}</span>
                <span className="stat-label">Overdue</span>
              </span>
            )}
          </div>
        </div>

        <div className="tasks-controls">
          <button
            className="control-button"
            onClick={() => setBulkSelectMode(!bulkSelectMode)}
            title={bulkSelectMode ? 'Exit bulk select' : 'Bulk select'}
          >
            <CheckSquare size={20} />
          </button>

          <button
            className="control-button"
            onClick={toggleViewMode}
            title="Change view mode"
          >
            {viewMode === 'split' ? <List size={20} /> : <LayoutGrid size={20} />}
          </button>

          <button
            className="control-button primary"
            onClick={() => setShowQuickAdd(true)}
            title="Add new task"
          >
            <Plus size={20} />
          </button>
        </div>
      </div>

      {/* Progress Bar */}
      <div className="tasks-progress">
        <div className="progress-bar">
          <motion.div
            className="progress-fill"
            initial={{ width: 0 }}
            animate={{ width: `${progressPercentage}%` }}
            transition={{ duration: reducedMotion ? 0 : 0.5 }}
          />
        </div>
        <span className="progress-text">
          {progressPercentage}% Complete ({taskCounts.completed}/{taskCounts.total})
        </span>
      </div>

      {/* Filters */}
      <div className="tasks-filters">
        <div className="filter-search">
          <Search size={16} />
          <input
            type="text"
            placeholder="Search tasks..."
            value={filterState.search}
            onChange={(e) => setFilterState(prev => ({ ...prev, search: e.target.value }))}
          />
        </div>

        <select
          value={filterState.priority}
          onChange={(e) => setFilterState(prev => ({ ...prev, priority: e.target.value }))}
        >
          <option value="all">All Priorities</option>
          <option value="high">High Priority</option>
          <option value="medium">Medium Priority</option>
          <option value="low">Low Priority</option>
        </select>

        <select
          value={filterState.tag}
          onChange={(e) => setFilterState(prev => ({ ...prev, tag: e.target.value }))}
        >
          <option value="all">All Tags</option>
          {allTags.map(tag => (
            <option key={tag} value={tag}>{tag}</option>
          ))}
        </select>

        <select
          value={filterState.status}
          onChange={(e) => setFilterState(prev => ({ ...prev, status: e.target.value }))}
        >
          <option value="all">All Tasks</option>
          <option value="pending">Pending</option>
          <option value="completed">Completed</option>
        </select>
      </div>

      {/* Quick Add */}
      <AnimatePresence>
        {showQuickAdd && (
          <motion.div
            className="quick-add-container"
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: reducedMotion ? 0 : 0.3 }}
          >
            <div className="quick-add-form">
              <input
                type="text"
                placeholder="Task title..."
                value={quickAddText}
                onChange={(e) => setQuickAddText(e.target.value)}
                onKeyPress={(e) => e.key === 'Enter' && handleQuickAdd()}
                autoFocus
              />
              <select
                value={quickAddPriority}
                onChange={(e) => setQuickAddPriority(e.target.value)}
              >
                <option value="low">Low</option>
                <option value="medium">Medium</option>
                <option value="high">High</option>
              </select>
              <button onClick={handleQuickAdd} disabled={!quickAddText.trim()}>
                Add
              </button>
              <button onClick={() => setShowQuickAdd(false)}>
                Cancel
              </button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Bulk Actions */}
      <AnimatePresence>
        {bulkSelectMode && selectedTasks.size > 0 && (
          <motion.div
            className="bulk-actions"
            initial={{ opacity: 0, y: -20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -20 }}
            transition={{ duration: reducedMotion ? 0 : 0.2 }}
          >
            <span className="bulk-count">{selectedTasks.size} selected</span>
            <div className="bulk-buttons">
              <button onClick={() => handleBulkAction('complete')}>
                <Check size={16} />
                Complete
              </button>
              <button onClick={() => handleBulkAction('snooze')}>
                <Clock size={16} />
                Snooze
              </button>
              <button onClick={() => handleBulkAction('delete')} className="danger">
                <Trash2 size={16} />
                Delete
              </button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Tasks Content */}
      <div className={`tasks-content ${viewMode}`}>
        {viewMode === 'split' && (
          <div className="split-view">
            <div className="pending-column">
              <h2>Pending Tasks</h2>
              <TaskGroup
                title="Overdue"
                tasks={groupedTasks.overdue}
                icon={<AlertCircle size={16} className="text-danger" />}
              />
              <TaskGroup
                title="Today"
                tasks={groupedTasks.today}
                icon={<Calendar size={16} className="text-warn" />}
              />
              <TaskGroup
                title="This Week"
                tasks={groupedTasks.thisWeek}
                icon={<Clock size={16} className="text-info" />}
              />
              <TaskGroup
                title="Later"
                tasks={groupedTasks.later}
                icon={<Circle size={16} className="text-muted" />}
              />
            </div>

            <div className="completed-column">
              <TaskGroup
                title="Completed"
                tasks={groupedTasks.completed}
                icon={<CheckCircle2 size={16} className="text-success" />}
              />
            </div>
          </div>
        )}

        {viewMode === 'list' && (
          <div className="list-view">
            {filteredTasks.map(task => (
              <TaskCard
                key={task._id}
                task={task}
                showCheckbox={bulkSelectMode}
              />
            ))}
          </div>
        )}

        {viewMode === 'kanban' && (
          <div className="kanban-view">
            <div className="kanban-column">
              <h3>To Do</h3>
              {filteredTasks.filter(t => t.status === 'pending' || t.status === 'in_progress').map(task => (
                <TaskCard
                  key={task._id}
                  task={task}
                  showCheckbox={bulkSelectMode}
                />
              ))}
            </div>
            <div className="kanban-column">
              <h3>In Progress</h3>
              {filteredTasks.filter(t => t.status === 'in_progress').map(task => (
                <TaskCard
                  key={task._id}
                  task={task}
                  showCheckbox={bulkSelectMode}
                />
              ))}
            </div>
            <div className="kanban-column">
              <h3>Done</h3>
              {filteredTasks.filter(t => t.status === 'done').map(task => (
                <TaskCard
                  key={task._id}
                  task={task}
                  showCheckbox={bulkSelectMode}
                />
              ))}
            </div>
          </div>
        )}
      </div>

      {/* OTP Verification Modal */}
      <AnimatePresence>
        {showOtpModal && (
          <motion.div
            className="modal-overlay"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={() => setShowOtpModal(false)}
          >
            <motion.div
              className="modal-content"
              initial={{ opacity: 0, scale: 0.9 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.9 }}
              onClick={(e) => e.stopPropagation()}
            >
              <h3>Verify Task Reminder</h3>
              <p>Please enter the OTP you received for: <strong>{otpTask?.title}</strong></p>
              <input
                type="text"
                placeholder="Enter 6-digit OTP"
                value={otpCode}
                onChange={(e) => setOtpCode(e.target.value)}
                maxLength={6}
                autoFocus
              />
              <div className="modal-actions">
                <button onClick={verifyOtp} disabled={!otpCode.trim()}>
                  Verify
                </button>
                <button onClick={() => setShowOtpModal(false)}>
                  Cancel
                </button>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Reschedule Modal */}
      <AnimatePresence>
        {showRescheduleModal && (
          <motion.div
            className="modal-overlay"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={() => setShowRescheduleModal(false)}
          >
            <motion.div
              className="modal-content"
              initial={{ opacity: 0, scale: 0.9 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.9 }}
              onClick={(e) => e.stopPropagation()}
            >
              <h3>Reschedule Task</h3>
              <p>Reschedule: <strong>{rescheduleTask?.title}</strong></p>
              <input
                type="datetime-local"
                value={newDueDate}
                onChange={(e) => setNewDueDate(e.target.value)}
              />
              <div className="modal-actions">
                <button onClick={rescheduleTaskConfirm} disabled={!newDueDate}>
                  Reschedule
                </button>
                <button onClick={() => setShowRescheduleModal(false)}>
                  Cancel
                </button>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
};

export default TasksInterface;