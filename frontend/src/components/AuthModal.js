import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { 
    X, 
    Mail, 
    Lock, 
    User, 
    Eye, 
    EyeOff, 
    CheckCircle, 
    Chrome,
    Facebook,
    Apple
} from 'lucide-react';
import authService from '../services/auth';
import '../styles/AuthModal.css';

const AuthModal = ({ isOpen, onClose, onAuthSuccess, initialMode = 'signin' }) => {
    const [activeTab, setActiveTab] = useState(initialMode);
    const [showPassword, setShowPassword] = useState(false);
    const [showConfirmPassword, setShowConfirmPassword] = useState(false);
    const [isLoading, setIsLoading] = useState(false);
    const [message, setMessage] = useState('');
    const [messageType, setMessageType] = useState('');

    const [formData, setFormData] = useState({
        name: '',
        email: '',
        password: '',
        confirmPassword: ''
    });

    const [fieldValidation, setFieldValidation] = useState({
        name: false,
        email: false,
        password: false,
        confirmPassword: false
    });

    // Validation functions
    const validateEmail = (email) => {
        const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        return emailRegex.test(email);
    };

    const validatePassword = (password) => {
        return password.length >= 6;
    };

    const validateName = (name) => {
        return name.trim().length >= 2;
    };

    const validateConfirmPassword = (password, confirmPassword) => {
        return password === confirmPassword && password.length >= 6;
    };

    // Real-time validation
    useEffect(() => {
        setFieldValidation({
            name: validateName(formData.name),
            email: validateEmail(formData.email),
            password: validatePassword(formData.password),
            confirmPassword: validateConfirmPassword(formData.password, formData.confirmPassword)
        });
    }, [formData]);

    const handleInputChange = (e) => {
        const { name, value } = e.target;
        setFormData(prev => ({
            ...prev,
            [name]: value
        }));
    };

    const handleSubmit = async (e) => {
        e.preventDefault();
        setIsLoading(true);
        setMessage('');

        try {
            if (activeTab === 'signin') {
                const response = await authService.login(formData.email, formData.password);
                
                // Store tokens and get user data
                authService.storeTokens(response.data);
                const user = authService.getCurrentUser();
                
                setMessage('Login successful! Redirecting to dashboard...');
                setMessageType('success');
                setTimeout(() => {
                    onAuthSuccess && onAuthSuccess(user);
                    onClose();
                    // Redirect to dashboard
                    window.location.href = '/dashboard';
                }, 1000);
            } else {
                // Sign up logic
                if (formData.password !== formData.confirmPassword) {
                    setMessage('Passwords do not match');
                    setMessageType('error');
                    return;
                }

                const response = await authService.register(formData.email, formData.password);
                
                setMessage('Registration successful! Please login to continue...');
                setMessageType('success');
                
                // Clear form data
                setFormData({
                    name: '',
                    email: formData.email, // Keep email for easier login
                    password: '',
                    confirmPassword: ''
                });
                
                // Slide to login tab after successful registration
                setTimeout(() => {
                    setActiveTab('signin');
                    setMessage('');
                    setMessageType('');
                }, 2000);
            }
        } catch (error) {
            console.error('Auth error:', error);
            setMessage(error.response?.data?.detail || 'An error occurred. Please try again.');
            setMessageType('error');
        } finally {
            setIsLoading(false);
        }
    };

    const handleTabSwitch = (tab) => {
        setActiveTab(tab);
        setFormData({
            name: '',
            email: '',
            password: '',
            confirmPassword: ''
        });
        setMessage('');
        setMessageType('');
    };

    const handleSocialLogin = (provider) => {
        console.log(`Social login with ${provider}`);
        // Implement social login logic here
    };

    if (!isOpen) return null;

    return (
        <AnimatePresence>
            {isOpen && (
                <motion.div
                    className="auth-modal-overlay"
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    exit={{ opacity: 0 }}
                    transition={{ duration: 0.3 }}
                    onClick={(e) => e.target === e.currentTarget && onClose()}
                >
                    <motion.div
                        className="auth-modal-container"
                        initial={{ opacity: 0, scale: 0.8, y: 50 }}
                        animate={{ opacity: 1, scale: 1, y: 0 }}
                        exit={{ opacity: 0, scale: 0.8, y: 50 }}
                        transition={{ 
                            duration: 0.5, 
                            type: "spring", 
                            stiffness: 100, 
                            damping: 15 
                        }}
                    >
                        {/* Close Button */}
                        <button
                            className="auth-modal-close"
                            onClick={onClose}
                            type="button"
                        >
                            <X size={20} />
                        </button>

                        {/* Header */}
                        <div className="auth-modal-header">
                            <h2 className="auth-modal-title">Welcome Back</h2>
                            <p className="auth-modal-subtitle">Hey buddy, Please enter your details</p>
                        </div>

                        {/* Tab Switcher */}
                        <div className="auth-tabs">
                            <button
                                className={`auth-tab ${activeTab === 'signin' ? 'active' : ''}`}
                                onClick={() => handleTabSwitch('signin')}
                            >
                                Sign In
                            </button>
                            <button
                                className={`auth-tab ${activeTab === 'signup' ? 'active' : ''}`}
                                onClick={() => handleTabSwitch('signup')}
                            >
                                Sign Up
                            </button>
                        </div>

                        {/* Form */}
                        <form onSubmit={handleSubmit} className="auth-form">
                            {activeTab === 'signup' && (
                                <div className="auth-input-group">
                                    <div className="auth-input-wrapper">
                                        <User className="auth-input-icon" size={18} />
                                        <input
                                            type="text"
                                            name="name"
                                            value={formData.name}
                                            onChange={handleInputChange}
                                            placeholder="Full Name"
                                            className="auth-input"
                                            required
                                        />
                                        {fieldValidation.name && (
                                            <CheckCircle className="auth-validation-icon" size={18} />
                                        )}
                                    </div>
                                </div>
                            )}

                            <div className="auth-input-group">
                                <div className="auth-input-wrapper">
                                    <Mail className="auth-input-icon" size={18} />
                                    <input
                                        type="email"
                                        name="email"
                                        value={formData.email}
                                        onChange={handleInputChange}
                                        placeholder="Email"
                                        className="auth-input"
                                        required
                                    />
                                    {fieldValidation.email && (
                                        <CheckCircle className="auth-validation-icon" size={18} />
                                    )}
                                </div>
                            </div>

                            <div className="auth-input-group">
                                <div className="auth-input-wrapper">
                                    <Lock className="auth-input-icon" size={18} />
                                    <input
                                        type={showPassword ? "text" : "password"}
                                        name="password"
                                        value={formData.password}
                                        onChange={handleInputChange}
                                        placeholder="Password"
                                        className="auth-input"
                                        required
                                    />
                                    <button
                                        type="button"
                                        className="auth-password-toggle"
                                        onClick={() => setShowPassword(!showPassword)}
                                    >
                                        {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
                                    </button>
                                    {fieldValidation.password && (
                                        <CheckCircle className="auth-validation-icon" size={18} />
                                    )}
                                </div>
                            </div>

                            {activeTab === 'signup' && (
                                <div className="auth-input-group">
                                    <div className="auth-input-wrapper">
                                        <Lock className="auth-input-icon" size={18} />
                                        <input
                                            type={showConfirmPassword ? "text" : "password"}
                                            name="confirmPassword"
                                            value={formData.confirmPassword}
                                            onChange={handleInputChange}
                                            placeholder="Confirm Password"
                                            className="auth-input"
                                            required
                                        />
                                        <button
                                            type="button"
                                            className="auth-password-toggle"
                                            onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                                        >
                                            {showConfirmPassword ? <EyeOff size={18} /> : <Eye size={18} />}
                                        </button>
                                        {fieldValidation.confirmPassword && (
                                            <CheckCircle className="auth-validation-icon" size={18} />
                                        )}
                                    </div>
                                </div>
                            )}

                            {/* Message Display */}
                            {message && (
                                <motion.div
                                    className={`auth-message ${messageType}`}
                                    initial={{ opacity: 0, y: -10 }}
                                    animate={{ opacity: 1, y: 0 }}
                                    transition={{ duration: 0.3 }}
                                >
                                    {message}
                                </motion.div>
                            )}

                            {/* Submit Button */}
                            <button
                                type="submit"
                                className="auth-submit-btn"
                                disabled={isLoading}
                            >
                                {isLoading ? (
                                    <div className="auth-spinner"></div>
                                ) : (
                                    'Continue'
                                )}
                            </button>
                        </form>

                        {/* Divider */}
                        <div className="auth-divider">
                            <span>Or continue with</span>
                        </div>

                        {/* Social Login */}
                        <div className="auth-social-login">
                            <button
                                className="auth-social-btn"
                                onClick={() => handleSocialLogin('google')}
                            >
                                <Chrome size={20} />
                            </button>
                            <button
                                className="auth-social-btn"
                                onClick={() => handleSocialLogin('facebook')}
                            >
                                <Facebook size={20} />
                            </button>
                            <button
                                className="auth-social-btn"
                                onClick={() => handleSocialLogin('apple')}
                            >
                                <Apple size={20} />
                            </button>
                        </div>
                    </motion.div>
                </motion.div>
            )}
        </AnimatePresence>
    );
};

export default AuthModal;