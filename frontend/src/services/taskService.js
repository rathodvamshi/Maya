// frontend/src/services/taskService.js

import apiClient from './api';

class TaskService {
  // ======================================================
  // TASK CRUD OPERATIONS
  // ======================================================

  async getTasks(filters = {}) {
    const params = new URLSearchParams();
    
    // Apply filters
    if (filters.status) params.append('status', filters.status);
    if (filters.priority) params.append('priority', filters.priority);
    if (filters.tag) params.append('tag', filters.tag);
    if (filters.due_soon) params.append('due_soon', 'true');
    if (filters.overdue) params.append('overdue', 'true');
    if (filters.limit) params.append('limit', filters.limit);
    if (filters.offset) params.append('offset', filters.offset);

    try {
      const response = await apiClient.get(`/tasks?${params.toString()}`);
      return {
        success: true,
        data: response.data
      };
    } catch (error) {
      console.error('Error fetching tasks:', error);
      return {
        success: false,
        error: error.response?.data?.error?.message || 'Failed to fetch tasks'
      };
    }
  }

  async createTask(taskData) {
    try {
      const response = await apiClient.post('/tasks', taskData);
      return {
        success: true,
        data: response.data
      };
    } catch (error) {
      console.error('Error creating task:', error);
      return {
        success: false,
        error: error.response?.data?.error?.message || 'Failed to create task'
      };
    }
  }

  async getTask(taskId) {
    try {
      const response = await apiClient.get(`/tasks/${taskId}`);
      return {
        success: true,
        data: response.data
      };
    } catch (error) {
      console.error('Error fetching task:', error);
      return {
        success: false,
        error: error.response?.data?.error?.message || 'Failed to fetch task'
      };
    }
  }

  async updateTask(taskId, updates) {
    try {
      const response = await apiClient.put(`/tasks/${taskId}`, updates);
      return {
        success: true,
        data: response.data
      };
    } catch (error) {
      console.error('Error updating task:', error);
      return {
        success: false,
        error: error.response?.data?.error?.message || 'Failed to update task'
      };
    }
  }

  async deleteTask(taskId) {
    try {
      const response = await apiClient.delete(`/tasks/${taskId}`);
      return {
        success: true,
        data: response.data
      };
    } catch (error) {
      console.error('Error deleting task:', error);
      return {
        success: false,
        error: error.response?.data?.error?.message || 'Failed to delete task'
      };
    }
  }

  // ======================================================
  // BULK OPERATIONS
  // ======================================================

  async bulkUpdateTasks(taskIds, operation, options = {}) {
    const bulkData = {
      task_ids: taskIds,
      operation: operation,
      ...options
    };

    try {
      const response = await apiClient.post('/tasks/bulk', bulkData);
      return {
        success: true,
        data: response.data
      };
    } catch (error) {
      console.error('Error performing bulk operation:', error);
      return {
        success: false,
        error: error.response?.data?.error?.message || 'Failed to perform bulk operation'
      };
    }
  }

  async bulkDelete(taskIds) {
    return this.bulkUpdateTasks(taskIds, 'delete');
  }

  async bulkComplete(taskIds) {
    return this.bulkUpdateTasks(taskIds, 'complete');
  }

  async bulkUpdateStatus(taskIds, status) {
    return this.bulkUpdateTasks(taskIds, 'update_status', { status });
  }

  async bulkUpdatePriority(taskIds, priority) {
    return this.bulkUpdateTasks(taskIds, 'update_priority', { priority });
  }

  // ======================================================
  // TASK STATISTICS
  // ======================================================

  async getTaskStats() {
    try {
      const response = await apiClient.get('/tasks/stats/summary');
      return {
        success: true,
        data: response.data
      };
    } catch (error) {
      console.error('Error fetching task stats:', error);
      // Return fallback stats
      return {
        success: true,
        data: {
          total: 0,
          todo: 0,
          in_progress: 0,
          done: 0,
          cancelled: 0,
          overdue: 0
        }
      };
    }
  }

  async getPriorityStats() {
    try {
      const response = await apiClient.get('/tasks/stats/priority');
      return {
        success: true,
        data: response.data
      };
    } catch (error) {
      console.error('Error fetching priority stats:', error);
      return {
        success: false,
        error: error.response?.data?.error?.message || 'Failed to fetch priority stats'
      };
    }
  }

  async getUserTags() {
    try {
      const response = await apiClient.get('/tasks/tags');
      return {
        success: true,
        data: response.data
      };
    } catch (error) {
      console.error('Error fetching user tags:', error);
      return {
        success: false,
        error: error.response?.data?.error?.message || 'Failed to fetch tags'
      };
    }
  }

  // ======================================================
  // HELPER METHODS
  // ======================================================

  getPriorityColor(priority) {
    const colors = {
      low: '#22c55e',      // green
      medium: '#f59e0b',   // amber
      high: '#ef4444',     // red
      urgent: '#dc2626'    // dark red
    };
    return colors[priority] || colors.medium;
  }

  getStatusColor(status) {
    const colors = {
      todo: '#6b7280',        // gray
      in_progress: '#3b82f6', // blue
      done: '#22c55e',        // green
      cancelled: '#ef4444'    // red
    };
    return colors[status] || colors.todo;
  }

  getPriorityIcon(priority) {
    const icons = {
      low: '↓',
      medium: '→',
      high: '↑',
      urgent: '‼️'
    };
    return icons[priority] || icons.medium;
  }

  formatDueDate(dueDate) {
    if (!dueDate) return null;
    
    const date = new Date(dueDate);
    const now = new Date();
    const diffMs = date.getTime() - now.getTime();
    const diffDays = Math.ceil(diffMs / (1000 * 60 * 60 * 24));
    
    if (diffDays < 0) {
      return {
        text: `${Math.abs(diffDays)} days overdue`,
        color: '#ef4444',
        urgent: true
      };
    } else if (diffDays === 0) {
      return {
        text: 'Due today',
        color: '#f59e0b',
        urgent: true
      };
    } else if (diffDays === 1) {
      return {
        text: 'Due tomorrow',
        color: '#f59e0b',
        urgent: false
      };
    } else if (diffDays <= 7) {
      return {
        text: `Due in ${diffDays} days`,
        color: '#3b82f6',
        urgent: false
      };
    } else {
      return {
        text: date.toLocaleDateString(),
        color: '#6b7280',
        urgent: false
      };
    }
  }

  // Local storage helpers for task filters and preferences
  saveTaskFilters(filters) {
    localStorage.setItem('maya_task_filters', JSON.stringify(filters));
  }

  getTaskFilters() {
    try {
      const saved = localStorage.getItem('maya_task_filters');
      return saved ? JSON.parse(saved) : {};
    } catch {
      return {};
    }
  }

  saveTaskView(view) {
    localStorage.setItem('maya_task_view', view);
  }

  getTaskView() {
    return localStorage.getItem('maya_task_view') || 'list';
  }

  // Task validation
  validateTask(taskData) {
    const errors = {};
    
    if (!taskData.title || taskData.title.trim().length === 0) {
      errors.title = 'Title is required';
    }
    
    if (taskData.title && taskData.title.length > 200) {
      errors.title = 'Title must be 200 characters or less';
    }
    
    if (taskData.description && taskData.description.length > 1000) {
      errors.description = 'Description must be 1000 characters or less';
    }
    
    if (taskData.due_date) {
      const dueDate = new Date(taskData.due_date);
      if (isNaN(dueDate.getTime())) {
        errors.due_date = 'Invalid due date';
      }
    }
    
    if (taskData.tags && taskData.tags.length > 10) {
      errors.tags = 'Maximum 10 tags allowed';
    }
    
    return {
      isValid: Object.keys(errors).length === 0,
      errors
    };
  }
}

const taskService = new TaskService();
export default taskService;