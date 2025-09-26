// Demo file to test the new LandingPage
import React from 'react';
import LandingPage from './components/LandingPage';
import './styles/variables.css';
import './styles/LandingPage.css';
import './styles/AuthModal.css';

function LandingPageDemo() {
    return (
        <div style={{ 
            minHeight: '100vh',
            fontFamily: 'Inter, -apple-system, BlinkMacSystemFont, sans-serif'
        }}>
            <LandingPage />
        </div>
    );
}

export default LandingPageDemo;