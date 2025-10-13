import { Book, MessageCircle, Keyboard, Zap, Shield, Settings as SettingsIcon } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import '../styles/Help.css';

const Help = () => {
  const navigate = useNavigate();
  const sections = [
    {
      icon: <MessageCircle size={24} />,
      title: 'Getting Started',
      items: [
        'Click "New Chat" to start a conversation with MAYA',
        'Type your message or use voice input',
        'Attach files, images, or documents using the + button',
        'Use the microphone icon for voice commands',
      ],
    },
    {
      icon: <Keyboard size={24} />,
      title: 'Keyboard Shortcuts',
      items: [
        'Enter - Send message',
        'Shift + Enter - New line in message',
        'Ctrl/Cmd + K - New chat',
        'Ctrl/Cmd + S - Save conversation',
      ],
    },
    {
      icon: <Zap size={24} />,
      title: 'Features',
      items: [
        'Context Retention - MAYA remembers your conversation history',
        'Smart Learning - Adapts to your communication style',
        'Task Management - Create and track tasks from conversations',
        'Multi-modal Input - Text, voice, images, and file support',
      ],
    },
    {
      icon: <Shield size={24} />,
      title: 'Privacy & Security',
      items: [
        'All conversations are encrypted end-to-end',
        'You control your data and can delete it anytime',
        'Memory management allows selective data deletion',
        'No data sharing with third parties',
      ],
    },
    {
      icon: <SettingsIcon size={24} />,
      title: 'Customization',
      items: [
        'Choose between light and dark themes',
        'Manage notification preferences',
        'Add your own API keys for extended usage',
        'Set language preferences',
      ],
    },
    {
      icon: <Book size={24} />,
      title: 'Tips & Tricks',
      items: [
        'Be specific in your questions for better responses',
        'Use the edit feature to refine your messages',
        'Save important conversations for future reference',
        'Create tasks directly from chat to stay organized',
      ],
    },
  ];

  return (
    <div className="help-page">
      <button className="profile-back-btn" aria-label="Go back" onClick={() => navigate(-1)}>
        <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <path d="m12 19-7-7 7-7"></path>
          <path d="M19 12H5"></path>
        </svg>
        <span className="profile-back-text">Back</span>
      </button>
      <div className="help-header">
        <h1>Help & Documentation</h1>
        <p>Learn how to make the most of MAYA</p>
      </div>

      <div className="help-content">
        {sections.map((section, index) => (
          <div key={index} className="help-section">
            <div className="help-section-header">
              <div className="help-icon">{section.icon}</div>
              <h2>{section.title}</h2>
            </div>
            <ul className="help-list">
              {section.items.map((item, idx) => (
                <li key={idx}>{item}</li>
              ))}
            </ul>
          </div>
        ))}

        <div className="help-footer">
          <div className="help-card">
            <h3>Need More Help?</h3>
            <p>
              If you have questions or need assistance, feel free to reach out to our support team.
            </p>
            <button className="contact-btn">Contact Support</button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Help;
