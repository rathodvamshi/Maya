
// Yes. It provides the modal UI for sign in and sign up, handling form validation, calling authService to log in/register, and showing social login buttons.

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
import RegisterNew from './RegisterNew';
import ForgotPasswordEmbed from './ForgotPasswordEmbed';
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

    // Compact password criteria (no height jump)
    const passwordMeetsAll = (() => {
        const pw = formData.password || '';
        const lengthOK = pw.length >= 8;
        const upperOK = /[A-Z]/.test(pw);
        const numberOK = /\d/.test(pw);
        const specialOK = /[^A-Za-z0-9]/.test(pw);
        return lengthOK && upperOK && numberOK && specialOK;
    })();

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
            const apiMsg = error.response?.data?.error?.message || error.response?.data?.detail;
            setMessage(apiMsg || 'An error occurred. Please try again.');
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

    const handleForgotPassword = () => {
        setActiveTab('forgot');
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
                        initial={{ opacity: 0, y: 20 }}
                        animate={{ opacity: 1, y: 0 }}
                        exit={{ opacity: 0, y: 20 }}
                        transition={{ duration: 0.25, ease: 'easeOut' }}
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
                            <h2 className="auth-modal-title">{
                                activeTab === 'signin' ? 'Welcome Back' : activeTab === 'signup' ? 'Create Account' : 'Reset Password'
                            }</h2>
                            <p className="auth-modal-subtitle">
                                {activeTab === 'signin' && 'Hey buddy, Please enter your details'}
                                {activeTab === 'signup' && 'Hey buddy, Please enter your details to get started'}
                                {activeTab === 'forgot' && 'We\'ll send a 4-digit OTP to your email to verify it'}
                            </p>
                        </div>

                        {/* Tab Switcher */}
                        {activeTab !== 'forgot' && (
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
                        )}

                        {/* Form / Embedded Multi-step Signup & Forgot with smooth slide */}
                        <div className="auth-tab-panels">
                        <AnimatePresence mode="wait" initial={false}>
                        {activeTab === 'signin' ? (
                            <motion.form
                                key="signin"
                                onSubmit={handleSubmit}
                                className="auth-form"
                                initial={{ x: -20, opacity: 0 }}
                                animate={{ x: 0, opacity: 1 }}
                                exit={{ x: 20, opacity: 0 }}
                                transition={{ duration: 0.25, ease: 'easeOut' }}
                            >
                                <div className="auth-input-group">
                                    <div className="auth-input-wrapper">
                                        <Mail className="auth-input-icon" size={18} />
                                        <input
                                            type="email"
                                            name="email"
                                            value={formData.email}
                                            onChange={handleInputChange}
                                            placeholder="Email"
                                            autoComplete="username"
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
                                            autoComplete="current-password"
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
                                    {formData.password && (
                                        <div className={`password-criteria ${passwordMeetsAll ? 'ok' : ''}`}>
                                            Meets all criteria: 8+ characters, uppercase, number, and special character.
                                        </div>
                                    )}
                                </div>
                                <div className="auth-form-meta">
                                    <button
                                        type="button"
                                        className="link-button forgot-link"
                                        onClick={handleForgotPassword}
                                    >
                                        Forgot Password?
                                    </button>
                                </div>
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
                                <button
                                    type="submit"
                                    className="auth-submit-btn"
                                    disabled={isLoading}
                                >
                                    {isLoading ? <div className="auth-spinner"></div> : 'Continue'}
                                </button>
                            </motion.form>
                        ) : activeTab === 'signup' ? (
                            <motion.div
                                key="signup"
                                className="auth-form embedded-register"
                                initial={{ x: 20, opacity: 0 }}
                                animate={{ x: 0, opacity: 1 }}
                                exit={{ x: -20, opacity: 0 }}
                                transition={{ duration: 0.25, ease: 'easeOut' }}
                            >
                                <RegisterNew 
                                    embed 
                                    onNavigate={(view) => {
                                        if(view === 'signin') setActiveTab('signin');
                                        if(view === 'forgot-password') setActiveTab('forgot');
                                    }} 
                                    onRegister={() => {
                                        setMessage('Registration successful! Please login to continue...');
                                        setMessageType('success');
                                        setTimeout(()=>{
                                            setActiveTab('signin');
                                            setMessage('');
                                            setMessageType('');
                                        },1500);
                                    }}
                                />
                            </motion.div>
                        ) : (
                            <motion.div
                                key="forgot"
                                className="auth-form embedded-forgot"
                                initial={{ x: 20, opacity: 0 }}
                                animate={{ x: 0, opacity: 1 }}
                                exit={{ x: -20, opacity: 0 }}
                                transition={{ duration: 0.25, ease: 'easeOut' }}
                            >
                                {/* Inline Forgot Password flow */}
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
                                {/* Lightweight inline component to match modal styles */}
                                <ForgotPasswordEmbed onBack={()=> setActiveTab('signin')} />
                            </motion.div>
                        )}
                        </AnimatePresence>
                        </div>

                        {activeTab === 'signin' && (
                            <>
                                <div className="auth-divider">
                                    <span>Or continue with</span>
                                </div>
                                <div className="auth-social-login">
                                    <button className="auth-social-btn" onClick={() => handleSocialLogin('google')}>
                                        <Chrome size={20} />
                                    </button>
                                    <button className="auth-social-btn" onClick={() => handleSocialLogin('facebook')}>
                                        <Facebook size={20} />
                                    </button>
                                    <button className="auth-social-btn" onClick={() => handleSocialLogin('apple')}>
                                        <Apple size={20} />
                                    </button>
                                </div>
                            </>
                        )}
                    </motion.div>
                </motion.div>
            )}
        </AnimatePresence>
    );
};

export default AuthModal;