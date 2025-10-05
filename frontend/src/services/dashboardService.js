// frontend/src/services/dashboardService.js

import apiClient from './api';
import taskService from './taskService';
import profileService from './profileService';
import sessionService from './sessionService';

class DashboardService {
  // ======================================================
  // DASHBOARD DATA
  // ======================================================

  async getDashboardStats() {
    try {
      const response = await apiClient.get('/dashboard/stats');
      return {
        success: true,
        data: response.data
      };
    } catch (error) {
      console.error('Error fetching dashboard stats:', error);
      return {
        success: false,
        error: error.response?.data?.error?.message || 'Failed to fetch dashboard stats'
      };
    }
  }

  async getQuickStats() {
    try {
      const response = await apiClient.get('/dashboard/quick-stats');
      return {
        success: true,
        data: response.data
      };
    } catch (error) {
      console.error('Error fetching quick stats:', error);
      // Return fallback data instead of throwing
      return {
        success: true,
        data: {
          tasks_today: 0,
          completed_today: 0,
          active_sessions: 0,
          pending_tasks: 0,
          productivity_score: 0
        }
      };
    }
  }

  async getProductivityTrends(days = 30) {
    try {
      const response = await apiClient.get(`/dashboard/productivity-trends?days=${days}`);
      return {
        success: true,
        data: response.data
      };
    } catch (error) {
      console.error('Error fetching productivity trends:', error);
      return {
        success: false,
        error: error.response?.data?.error?.message || 'Failed to fetch productivity trends'
      };
    }
  }

  async getUpcomingTasks(limit = 10) {
    try {
      const response = await apiClient.get(`/dashboard/upcoming-tasks?limit=${limit}`);
      return {
        success: true,
        data: response.data
      };
    } catch (error) {
      console.error('Error fetching upcoming tasks:', error);
      // Return empty array as fallback
      return {
        success: true,
        data: []
      };
    }
  }

  // ======================================================
  // COMPREHENSIVE DASHBOARD DATA
  // ======================================================

  async getCompleteDashboardData() {
    try {
      // Fetch all dashboard data in parallel
      const [
        dashboardStats,
        quickStats,
        productivityTrends,
        upcomingTasks,
        taskStats,
        recentSessions
      ] = await Promise.allSettled([
        this.getDashboardStats(),
        this.getQuickStats(),
        this.getProductivityTrends(30),
        this.getUpcomingTasks(5),
        taskService.getTaskStats(),
        sessionService.getSessions({ limit: 5 })
      ]);

      // Process results and handle failures gracefully
      const result = {
        dashboardStats: dashboardStats.status === 'fulfilled' ? dashboardStats.value.data : null,
        quickStats: quickStats.status === 'fulfilled' ? quickStats.value.data : null,
        productivityTrends: productivityTrends.status === 'fulfilled' ? productivityTrends.value.data : null,
        upcomingTasks: upcomingTasks.status === 'fulfilled' ? upcomingTasks.value.data : [],
        taskStats: taskStats.status === 'fulfilled' ? taskStats.value.data : null,
        recentSessions: recentSessions.status === 'fulfilled' ? recentSessions.value.data : []
      };

      return {
        success: true,
        data: result
      };
    } catch (error) {
      console.error('Error fetching complete dashboard data:', error);
      return {
        success: false,
        error: 'Failed to fetch dashboard data'
      };
    }
  }

  // ======================================================
  // WIDGET DATA HELPERS
  // ======================================================

  async getTaskSummaryWidget() {
    const result = await taskService.getTaskStats();
    if (!result.success) return result;

    const stats = result.data;
    const total = stats.total || 0;
    const completed = stats.done || 0;
    const pending = stats.todo + stats.in_progress;
    const completionRate = total > 0 ? Math.round((completed / total) * 100) : 0;

    return {
      success: true,
      data: {
        total,
        completed,
        pending,
        overdue: stats.overdue || 0,
        completionRate,
        breakdown: {
          todo: stats.todo || 0,
          in_progress: stats.in_progress || 0,
          done: stats.done || 0,
          cancelled: stats.cancelled || 0
        }
      }
    };
  }

  async getChatSummaryWidget() {
    const result = await profileService.getUserStats();
    if (!result.success) return result;

    const stats = result.data;
    return {
      success: true,
      data: {
        totalChats: stats.total_chats || 0,
        totalMessages: stats.total_messages || 0,
        activeSessions: stats.active_sessions || 0,
        avgSessionLength: stats.avg_session_length || 0
      }
    };
  }

  async getProductivityWidget(days = 7) {
    const result = await this.getProductivityTrends(days);
    if (!result.success) return result;

    const trends = result.data;
    const completedByDay = trends.completed_by_day || {};
    const createdByDay = trends.created_by_day || {};

    // Calculate totals for the period
    const totalCompleted = Object.values(completedByDay).reduce((sum, count) => sum + count, 0);
    const totalCreated = Object.values(createdByDay).reduce((sum, count) => sum + count, 0);

    // Calculate daily averages
    const avgCompleted = totalCompleted / days;
    const avgCreated = totalCreated / days;

    // Calculate trend (compare first half vs second half of period)
    const halfPeriod = Math.floor(days / 2);
    const dates = Object.keys(completedByDay).sort();
    const firstHalf = dates.slice(0, halfPeriod);
    const secondHalf = dates.slice(-halfPeriod);

    const firstHalfCompleted = firstHalf.reduce((sum, date) => sum + (completedByDay[date] || 0), 0);
    const secondHalfCompleted = secondHalf.reduce((sum, date) => sum + (completedByDay[date] || 0), 0);

    const trend = secondHalfCompleted > firstHalfCompleted ? 'up' : 
                  secondHalfCompleted < firstHalfCompleted ? 'down' : 'stable';

    return {
      success: true,
      data: {
        totalCompleted,
        totalCreated,
        avgCompleted: Math.round(avgCompleted * 10) / 10,
        avgCreated: Math.round(avgCreated * 10) / 10,
        trend,
        chartData: {
          completed: completedByDay,
          created: createdByDay
        },
        period: days
      }
    };
  }

  // ======================================================
  // NOTIFICATION HELPERS
  // ======================================================

  async getImportantNotifications() {
    try {
      const [taskStats, upcomingTasks, quickStats] = await Promise.all([
        taskService.getTaskStats(),
        this.getUpcomingTasks(10),
        this.getQuickStats()
      ]);

      const notifications = [];

      // Overdue tasks notification
      if (taskStats.success && taskStats.data.overdue > 0) {
        notifications.push({
          id: 'overdue-tasks',
          type: 'warning',
          title: 'Overdue Tasks',
          message: `You have ${taskStats.data.overdue} overdue task${taskStats.data.overdue > 1 ? 's' : ''}`,
          action: 'View Tasks',
          priority: 'high'
        });
      }

      // Due today notification
      if (upcomingTasks.success) {
        const dueToday = upcomingTasks.data.filter(task => {
          const dueDate = new Date(task.due_date);
          const today = new Date();
          return dueDate.toDateString() === today.toDateString();
        });

        if (dueToday.length > 0) {
          notifications.push({
            id: 'due-today',
            type: 'info',
            title: 'Tasks Due Today',
            message: `${dueToday.length} task${dueToday.length > 1 ? 's' : ''} due today`,
            action: 'View Tasks',
            priority: 'medium'
          });
        }
      }

      // Productivity milestone
      if (quickStats.success && quickStats.data.tasks_completed_today >= 5) {
        notifications.push({
          id: 'productivity-milestone',
          type: 'success',
          title: 'Great Progress!',
          message: `You've completed ${quickStats.data.tasks_completed_today} tasks today`,
          priority: 'low'
        });
      }

      return {
        success: true,
        data: notifications.sort((a, b) => {
          const priorityOrder = { high: 3, medium: 2, low: 1 };
          return priorityOrder[b.priority] - priorityOrder[a.priority];
        })
      };
    } catch (error) {
      console.error('Error fetching notifications:', error);
      return {
        success: false,
        error: 'Failed to fetch notifications'
      };
    }
  }

  // ======================================================
  // DASHBOARD PREFERENCES
  // ======================================================

  saveDashboardLayout(layout) {
    localStorage.setItem('maya_dashboard_layout', JSON.stringify(layout));
  }

  getDashboardLayout() {
    try {
      const saved = localStorage.getItem('maya_dashboard_layout');
      return saved ? JSON.parse(saved) : this.getDefaultLayout();
    } catch {
      return this.getDefaultLayout();
    }
  }

  getDefaultLayout() {
    return {
      widgets: [
        { id: 'task-summary', position: { x: 0, y: 0, w: 6, h: 4 }, enabled: true },
        { id: 'chat-summary', position: { x: 6, y: 0, w: 6, h: 4 }, enabled: true },
        { id: 'productivity', position: { x: 0, y: 4, w: 8, h: 6 }, enabled: true },
        { id: 'upcoming-tasks', position: { x: 8, y: 4, w: 4, h: 6 }, enabled: true },
        { id: 'recent-activity', position: { x: 0, y: 10, w: 12, h: 6 }, enabled: true }
      ],
      refreshInterval: 300 // 5 minutes
    };
  }

  saveDashboardPreferences(preferences) {
    localStorage.setItem('maya_dashboard_preferences', JSON.stringify(preferences));
  }

  getDashboardPreferences() {
    try {
      const saved = localStorage.getItem('maya_dashboard_preferences');
      return saved ? JSON.parse(saved) : this.getDefaultPreferences();
    } catch {
      return this.getDefaultPreferences();
    }
  }

  getDefaultPreferences() {
    return {
      autoRefresh: true,
      refreshInterval: 300, // 5 minutes
      showNotifications: true,
      compactMode: false,
      theme: 'dark'
    };
  }

  // ======================================================
  // DATA FORMATTING HELPERS
  // ======================================================

  formatChartData(data, type = 'line') {
    if (!data || typeof data !== 'object') return null;

    const dates = Object.keys(data).sort();
    const values = dates.map(date => data[date] || 0);

    return {
      labels: dates.map(date => new Date(date).toLocaleDateString('en-US', { 
        month: 'short', 
        day: 'numeric' 
      })),
      datasets: [{
        data: values,
        borderColor: type === 'completed' ? '#22c55e' : '#3b82f6',
        backgroundColor: type === 'completed' ? 'rgba(34, 197, 94, 0.1)' : 'rgba(59, 130, 246, 0.1)',
        tension: 0.4,
        fill: true
      }]
    };
  }

  calculateGrowthRate(current, previous) {
    if (previous === 0) return current > 0 ? 100 : 0;
    return Math.round(((current - previous) / previous) * 100);
  }

  formatNumber(number) {
    if (number >= 1000000) {
      return (number / 1000000).toFixed(1) + 'M';
    } else if (number >= 1000) {
      return (number / 1000).toFixed(1) + 'K';
    }
    return number.toString();
  }

  getTimeAgo(timestamp) {
    const date = new Date(timestamp);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMinutes = Math.floor(diffMs / (1000 * 60));
    const diffHours = Math.floor(diffMinutes / 60);
    const diffDays = Math.floor(diffHours / 24);

    if (diffMinutes < 1) return 'Just now';
    if (diffMinutes < 60) return `${diffMinutes}m ago`;
    if (diffHours < 24) return `${diffHours}h ago`;
    if (diffDays < 7) return `${diffDays}d ago`;
    return date.toLocaleDateString();
  }
}

const dashboardService = new DashboardService();
export default dashboardService;