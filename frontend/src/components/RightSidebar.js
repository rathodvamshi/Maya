import React from 'react';
import '../styles/RightSidebar.css';

const RightSidebar = ({
  currentUserEmail,
  pendingTasks = [],
  completedTasks = [],
  handleOpenModal,
  handleMarkAsDone,
  handleClearChat
}) => (
  <aside className="right-sidebar">
    <div className="sidebar-icons">
      <div className="sidebar-icon" title="User Profile">
        {/* SVG icon */}
        <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path>
          <circle cx="12" cy="7" r="4"></circle>
        </svg>
      </div>
      <div className="sidebar-icon" title="Tasks">
        <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
          <polyline points="14,2 14,8 20,8"></polyline>
          <line x1="16" y1="13" x2="8" y2="13"></line>
          <line x1="16" y1="17" x2="8" y2="17"></line>
          <polyline points="10,9 9,10 7,8"></polyline>
        </svg>
  <span className="task-count">{pendingTasks ? pendingTasks.length : 0}</span>
      </div>
      <div className="sidebar-icon clear-icon" title="Clear Chat" onClick={handleClearChat}>
        <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <polyline points="3 6 5 6 21 6"></polyline>
          <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
          <line x1="10" y1="11" x2="10" y2="17"></line>
          <line x1="14" y1="11" x2="14" y2="17"></line>
        </svg>
      </div>
    </div>
    <div className="sidebar-content">
      <div className="sidebar-section">
        <h3 className="sidebar-title">User Profile</h3>
        <p className="user-email">{currentUserEmail || 'Loading...'}</p>
      </div>
      <div className="sidebar-section">
        <div className="sidebar-title">
          <h3>Upcoming Tasks ({pendingTasks ? pendingTasks.length : 0})</h3>
          <button onClick={() => handleOpenModal()} className="add-task-btn-icon" title="Add new task">+</button>
        </div>
        <div className="task-list-container">
          <ul className="task-list">
            {pendingTasks && pendingTasks.length > 0 ? (
              pendingTasks.map(task => (
                <li key={task.id} className="task-item">
                  <div className="task-details">
                    <span className="task-content">{task.content}</span>
                    <span className="task-due-date">{task.due_date}</span>
                  </div>
                  <div className="task-actions">
                    <button onClick={() => handleOpenModal(task)} className="edit-btn" title="Edit task">
                      <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M17 3a2.828 2.828 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5L17 3z"></path></svg>
                    </button>
                    <button onClick={() => handleMarkAsDone(task.id)} className="delete-btn" title="Mark as done">
                      <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="20 6 9 17 4 12"></polyline></svg>
                    </button>
                  </div>
                </li>
              ))
            ) : (
              <li className="no-tasks">No pending tasks.</li>
            )}
          </ul>
        </div>
      </div>
      <div className="sidebar-section">
        <h3 className="sidebar-title">Completed Tasks</h3>
        <div className="task-list-container">
          <ul className="task-list completed-tasks">
            {completedTasks && completedTasks.length > 0 ? (
              completedTasks.map(task => (
                <li key={task.id} className="task-item completed">
                  <span className="task-content">{task.content}</span>
                </li>
              ))
            ) : (
              <li className="no-tasks">No completed tasks yet.</li>
            )}
          </ul>
        </div>
      </div>
    </div>
  </aside>
);

export default RightSidebar;
