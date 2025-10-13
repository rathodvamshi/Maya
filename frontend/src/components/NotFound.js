import React from 'react';
import { Home, ArrowLeftCircle } from 'lucide-react';
import { Link } from 'react-router-dom';
import '../styles/NotFound.css';

const NotFound = () => {
  return (
    <div className="notfound-page">
      <div className="notfound-content">
        <div className="notfound-status">404</div>
        <h1 className="notfound-title">Page Not Found</h1>
        <p className="notfound-subtitle">The page you are looking for has been moved, removed, or never existed.</p>
        <div className="notfound-actions">
          <Link to="/" className="nf-btn primary"><Home size={18} /> Go Home</Link>
          <button className="nf-btn ghost" onClick={() => window.history.back()}><ArrowLeftCircle size={18} /> Go Back</button>
        </div>
      </div>
      <div className="notfound-glow" />
    </div>
  );
};

export default NotFound;
