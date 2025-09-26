// Demo file to test AuthModal functionality
import React, { useState } from 'react';
import AuthModal from './components/AuthModal';
import './styles/variables.css';
import './styles/AuthModal.css';

function AuthModalDemo() {
    const [authModal, setAuthModal] = useState({ isOpen: false, mode: 'signin' });

    const handleAuthSuccess = (user) => {
        console.log('Authentication successful!', user);
        setAuthModal({ isOpen: false, mode: 'signin' });
    };

    const closeAuthModal = () => {
        setAuthModal({ isOpen: false, mode: 'signin' });
    };

    return (
        <div style={{ 
            minHeight: '100vh', 
            background: 'linear-gradient(135deg, #0f0f0f 0%, #1a1a1a 50%, #262626 100%)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontFamily: 'Inter, sans-serif'
        }}>
            <div style={{ textAlign: 'center' }}>
                <h1 style={{ color: '#ffffff', marginBottom: '2rem' }}>
                    Maya Authentication Demo
                </h1>
                <div style={{ display: 'flex', gap: '1rem', justifyContent: 'center' }}>
                    <button 
                        onClick={() => setAuthModal({ isOpen: true, mode: 'signin' })}
                        style={{
                            padding: '12px 24px',
                            background: '#3b82f6',
                            color: '#ffffff',
                            border: 'none',
                            borderRadius: '8px',
                            cursor: 'pointer',
                            fontWeight: '600',
                            fontSize: '16px'
                        }}
                    >
                        Open Sign In Modal
                    </button>
                    <button 
                        onClick={() => setAuthModal({ isOpen: true, mode: 'signup' })}
                        style={{
                            padding: '12px 24px',
                            background: 'rgba(59, 130, 246, 0.2)',
                            color: '#3b82f6',
                            border: '1px solid #3b82f6',
                            borderRadius: '8px',
                            cursor: 'pointer',
                            fontWeight: '600',
                            fontSize: '16px'
                        }}
                    >
                        Open Sign Up Modal
                    </button>
                </div>
            </div>

            <AuthModal
                isOpen={authModal.isOpen}
                onClose={closeAuthModal}
                onAuthSuccess={handleAuthSuccess}
                initialMode={authModal.mode}
            />
        </div>
    );
}

export default AuthModalDemo;