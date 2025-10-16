import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Plus, CreditCard as Edit2, Trash2, CheckCircle, Circle, X } from 'lucide-react';
import '../styles/Tasks.css';
import taskService from '../services/taskService';

const Tasks = () => {
  const navigate = useNavigate();
  const [tasks, setTasks] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  useEffect(() => {
    const fetchTasks = async () => {
      setLoading(true);
      const res = await taskService.getTasks();
      if (res.success) {
        const normalized = (Array.isArray(res.data) ? res.data : res.data?.items || []).map((t) => ({
          id: t.id || t._id || t.uuid,
          title: t.title || 'Untitled Task',
          description: t.description || '',
          status: t.status || (t.completed ? 'done' : 'todo'),
          completed: t.status ? (t.status === 'done' || t.completed === true) : !!t.completed,
          createdAt: t.created_at || t.createdAt || '',
          dueDate: t.due_date || t.dueDate || null,
        }));
        setTasks(normalized);
        setError('');
      } else {
        setError(res.error || 'Failed to load tasks');
      }
      setLoading(false);
    };
    fetchTasks();
    let bc;
    try {
      bc = new BroadcastChannel('maya_tasks');
      bc.onmessage = () => fetchTasks();
    } catch {}
    const w = () => fetchTasks();
    try { window.addEventListener('maya:tasks-updated', w); } catch {}
    return () => {
      try { window.removeEventListener('maya:tasks-updated', w); } catch {}
      try { if (bc) bc.close(); } catch {}
    };
  }, []);

  const [showModal, setShowModal] = useState(false);
  const [editingTask, setEditingTask] = useState(null);
  const [formData, setFormData] = useState({
    title: '',
    description: '',
  });

  const pendingTasks = tasks.filter((t) => !t.completed);
  const completedTasks = tasks.filter((t) => t.completed);

  const handleOpenModal = (task) => {
    if (task) {
      setEditingTask(task);
      setFormData({
        title: task.title,
        description: task.description,
      });
    } else {
      setEditingTask(null);
      setFormData({
        title: '',
        description: '',
      });
    }
    setShowModal(true);
  };

  const handleCloseModal = () => {
    setShowModal(false);
    setEditingTask(null);
    setFormData({
      title: '',
      description: '',
    });
  };

  const handleSaveTask = async () => {
    if (!formData.title.trim()) return;
    if (editingTask) {
      const res = await taskService.updateTask(editingTask.id, { title: formData.title, description: formData.description });
      if (res.success) {
        setTasks(tasks.map((t) => (t.id === editingTask.id ? {
          ...t,
          title: formData.title,
          description: formData.description
        } : t)));
        try { window.dispatchEvent(new CustomEvent('maya:tasks-updated')); } catch {}
      }
    } else {
      const res = await taskService.createTask({ title: formData.title, description: formData.description });
      if (res.success) {
        const t = res.data;
        const newTask = {
          id: t.id || t._id || t.uuid || Date.now().toString(),
          title: t.title,
          description: t.description || '',
          completed: t.status ? (t.status === 'done') : !!t.completed,
          createdAt: t.created_at || new Date().toISOString().split('T')[0],
        };
        setTasks([newTask, ...tasks]);
        try { window.dispatchEvent(new CustomEvent('maya:tasks-updated')); } catch {}
      }
    }

    handleCloseModal();
  };

  const handleToggleTask = async (taskId) => {
    const task = tasks.find((t) => t.id === taskId);
    if (!task) return;
    const res = await taskService.updateTask(taskId, { status: task.completed ? 'todo' : 'done', completed: !task.completed });
    if (res.success) {
      setTasks(tasks.map((t) => (t.id === taskId ? { ...t, completed: !t.completed } : t)));
      try { window.dispatchEvent(new CustomEvent('maya:tasks-updated')); } catch {}
    }
  };

  const handleDeleteTask = async (taskId) => {
    const res = await taskService.deleteTask(taskId);
    if (res.success) {
      setTasks(tasks.filter((t) => t.id !== taskId));
      try { window.dispatchEvent(new CustomEvent('maya:tasks-updated')); } catch {}
    }
  };

  return (
    <div className="tasks-page">
      <div className="tasks-header">
        <button className="profile-back-btn" aria-label="Go back" onClick={() => navigate(-1)}>
          <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <path d="m12 19-7-7 7-7"></path>
            <path d="M19 12H5"></path>
          </svg>
          <span className="profile-back-text">Back</span>
        </button>
        <h1>Task Management</h1>
        <button className="create-task-btn" onClick={() => handleOpenModal()}>
          <Plus size={20} />
          Create New Task
        </button>
      </div>

      <div className="tasks-content">
        {error && <div className="task-error">{error}</div>}
        {loading && <div className="task-loading">Loading tasks...</div>}
        <div className="tasks-stats">
          <div className="stat-card">
            <div className="stat-icon total">
              <Circle size={24} />
            </div>
            <div className="stat-info">
              <p className="stat-value">{tasks.length}</p>
              <p className="stat-label">Total Tasks</p>
            </div>
          </div>

          <div className="stat-card">
            <div className="stat-icon pending">
              <Circle size={24} />
            </div>
            <div className="stat-info">
              <p className="stat-value">{pendingTasks.length}</p>
              <p className="stat-label">Pending</p>
            </div>
          </div>

          <div className="stat-card">
            <div className="stat-icon completed">
              <CheckCircle size={24} />
            </div>
            <div className="stat-info">
              <p className="stat-value">{completedTasks.length}</p>
              <p className="stat-label">Completed</p>
            </div>
          </div>
        </div>

        <div className="tasks-section">
          <h2>Pending Tasks</h2>
          {pendingTasks.length === 0 ? (
            <p className="empty-state">No pending tasks</p>
          ) : (
            <div className="tasks-list">
              {pendingTasks.map((task) => (
                <div key={task.id} className="task-card">
                  <div className="task-checkbox" onClick={() => handleToggleTask(task.id)}>
                    <Circle size={20} />
                  </div>
                  <div className="task-content">
                    <h3>{task.title}</h3>
                    <p>{task.description}</p>
                    <span className="task-date">{task.dueDate ? new Date(task.dueDate).toLocaleString() : (task.createdAt || '')}</span>
                  </div>
                  <div className="task-actions">
                    <button onClick={() => handleOpenModal(task)}>
                      <Edit2 size={18} />
                    </button>
                    <button onClick={() => handleDeleteTask(task.id)}>
                      <Trash2 size={18} />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="tasks-section">
          <h2>Completed Tasks</h2>
          {completedTasks.length === 0 ? (
            <p className="empty-state">No completed tasks</p>
          ) : (
            <div className="tasks-list">
              {completedTasks.map((task) => (
                <div key={task.id} className="task-card completed">
                  <div className="task-checkbox" onClick={() => handleToggleTask(task.id)}>
                    <CheckCircle size={20} />
                  </div>
                  <div className="task-content">
                    <h3>{task.title}</h3>
                    <p>{task.description}</p>
                    <span className="task-date">{task.dueDate ? new Date(task.dueDate).toLocaleString() : (task.createdAt || '')}</span>
                  </div>
                  <div className="task-actions">
                    <button onClick={() => handleDeleteTask(task.id)}>
                      <Trash2 size={18} />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {showModal && (
        <div className="modal-overlay" onClick={handleCloseModal}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3>{editingTask ? 'Edit Task' : 'Create New Task'}</h3>
              <button className="modal-close" onClick={handleCloseModal}>
                <X size={20} />
              </button>
            </div>

            <div className="modal-body">
              <div className="form-group">
                <label>Task Title</label>
                <input
                  type="text"
                  placeholder="Enter task title"
                  value={formData.title}
                  onChange={(e) => setFormData({ ...formData, title: e.target.value })}
                />
              </div>

              <div className="form-group">
                <label>Description</label>
                <textarea
                  placeholder="Enter task description"
                  rows={4}
                  value={formData.description}
                  onChange={(e) =>
                    setFormData({ ...formData, description: e.target.value })
                  }
                />
              </div>
            </div>

            <div className="modal-footer">
              <button className="btn-secondary" onClick={handleCloseModal}>
                Cancel
              </button>
              <button className="btn-primary" onClick={handleSaveTask}>
                {editingTask ? 'Save Changes' : 'Create Task'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default Tasks;
