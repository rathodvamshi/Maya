import React, { useState, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { Eye, EyeOff, ArrowRight, Sparkles, Shield, CheckCircle, AlertCircle } from 'lucide-react';
import authService from '../services/auth';
import LoadingSpinner from './LoadingSpinner';
import AuthNavbar from './AuthNavbar';
import '../styles/variables.css';
import '../styles/LoginNew.css';

const Login = ({ onAuthSuccess }) => {
    const navigate = useNavigate();
    const [formData, setFormData] = useState({
        email: '',
        password: ''
    });
    const [formState, setFormState] = useState({
        message: '',
        messageType: '', // 'success', 'error', 'info'
        showPassword: false,
        isLoading: false,
        errors: {
            email: '',
            password: ''
        }
    });
    const [fieldTouched, setFieldTouched] = useState({
        email: false,
        password: false
    });

    // Validation functions
    const validateEmail = (email) => {
        const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        if (!email) return 'Email is required';
        if (!emailRegex.test(email)) return 'Please enter a valid email address';
        return '';
    };

    const validatePassword = (password) => {
        if (!password) return 'Password is required';
        if (password.length < 6) return 'Password must be at least 6 characters';
        return '';
    };

    // Form validation on field change
    useEffect(() => {
        if (fieldTouched.email) {
            setFormState(prev => ({
                ...prev,
                errors: { ...prev.errors, email: validateEmail(formData.email) }
            }));
        }
    }, [formData.email, fieldTouched.email]);

    useEffect(() => {
        if (fieldTouched.password) {
            setFormState(prev => ({
                ...prev,
                errors: { ...prev.errors, password: validatePassword(formData.password) }
            }));
        }
    }, [formData.password, fieldTouched.password]);

    // Handle input changes
    const handleInputChange = (field, value) => {
        setFormData(prev => ({ ...prev, [field]: value }));
        
        // Clear message when user starts typing
        if (formState.message) {
            setFormState(prev => ({ ...prev, message: '', messageType: '' }));
        }
    };

    const handleInputBlur = (field) => {
        setFieldTouched(prev => ({ ...prev, [field]: true }));
    };

    const handleLogin = async (e) => {
        e.preventDefault();
        
        // Validate all fields
        const emailError = validateEmail(formData.email);
        const passwordError = validatePassword(formData.password);
        
        if (emailError || passwordError) {
            setFormState(prev => ({
                ...prev,
                errors: { email: emailError, password: passwordError },
                message: 'Please correct the errors below',
                messageType: 'error'
            }));
            setFieldTouched({ email: true, password: true });
            return;
        }

        setFormState(prev => ({ ...prev, isLoading: true, message: '', messageType: '' }));
        
        try {
            const response = await authService.login(formData.email, formData.password);
            if (response.data.access_token) {
                authService.storeTokens({ ...response.data, email: formData.email });
                
                setFormState(prev => ({
                    ...prev,
                    message: 'Login successful! Redirecting...',
                    messageType: 'success'
                }));
                
                if (onAuthSuccess) {
                    onAuthSuccess({ ...response.data, email: formData.email });
                }
                
                // Navigate to dashboard after a brief delay
                setTimeout(() => {
                    navigate('/dashboard');
                }, 1000);
            }
        } catch (error) {
            const resMessage =
                (error.response &&
                    error.response.data &&
                    error.response.data.detail) ||
                error.message ||
                error.toString();
                
            setFormState(prev => ({
                ...prev,
                message: resMessage,
                messageType: 'error'
            }));
        } finally {
            setFormState(prev => ({ ...prev, isLoading: false }));
        }
    };

    const togglePasswordVisibility = () => {
        setFormState(prev => ({ ...prev, showPassword: !prev.showPassword }));
    };

    return (
        <>
            <AuthNavbar title="Maya" showBack={true} backUrl="/" />
            <div className="login-screen">
            <div className="login-background">
                <div className="floating-shapes">
                    <motion.div 
                        className="shape shape-1"
                        animate={{ 
                            y: [0, -20, 0],
                            rotate: [0, 180, 360]
                        }}
                        transition={{ 
                            duration: 20,
                            repeat: Infinity,
                            ease: "linear"
                        }}
                    />
                    <motion.div 
                        className="shape shape-2"
                        animate={{ 
                            y: [0, 15, 0],
                            rotate: [0, -180, -360]
                        }}
                        transition={{ 
                            duration: 25,
                            repeat: Infinity,
                            ease: "linear"
                        }}
                    />
                    <motion.div 
                        className="shape shape-3"
                        animate={{ 
                            y: [0, -10, 0],
                            rotate: [0, 90, 180]
                        }}
                        transition={{ 
                            duration: 30,
                            repeat: Infinity,
                            ease: "linear"
                        }}
                    />
                    <motion.div 
                        className="shape shape-4"
                        animate={{ 
                            y: [0, 25, 0],
                            rotate: [0, -90, -180]
                        }}
                        transition={{ 
                            duration: 22,
                            repeat: Infinity,
                            ease: "linear"
                        }}
                    />
                </div>
            </div>
            
            <motion.div 
                className="login-container"
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.6, ease: "easeOut" }}
            >
                <motion.div 
                    className="login-header"
                    initial={{ opacity: 0, y: -10 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.5, delay: 0.2 }}
                >
                    <div className="logo-wrapper">
                        <motion.div
                            whileHover={{ rotate: 360, scale: 1.1 }}
                            transition={{ duration: 0.6 }}
                        >
                            <Shield className="logo-icon" size={32} />
                        </motion.div>
                        <motion.div
                            animate={{ rotate: [0, 10, -10, 0] }}
                            transition={{ duration: 2, repeat: Infinity }}
                        >
                            <Sparkles className="sparkle-icon" size={16} />
                        </motion.div>
                    </div>
                    <h1 className="login-title">Welcome Back</h1>
                    <p className="login-subtitle">Sign in to your account to continue your journey</p>
                </motion.div>

                <motion.form 
                    onSubmit={handleLogin} 
                    className="login-form"
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    transition={{ duration: 0.5, delay: 0.3 }}
                >
                    {formState.message && (
                        <motion.div 
                            className={`form-message ${formState.messageType}`}
                            initial={{ opacity: 0, y: -10 }}
                            animate={{ opacity: 1, y: 0 }}
                            exit={{ opacity: 0, y: -10 }}
                        >
                            {formState.messageType === 'success' ? (
                                <CheckCircle size={16} />
                            ) : (
                                <AlertCircle size={16} />
                            )}
                            <span>{formState.message}</span>
                        </motion.div>
                    )}

                    <motion.div 
                        className="form-group"
                        initial={{ opacity: 0, x: -20 }}
                        animate={{ opacity: 1, x: 0 }}
                        transition={{ duration: 0.4, delay: 0.4 }}
                    >
                        <label htmlFor="email" className="form-label">
                            Email Address
                        </label>
                        <div className={`input-wrapper ${formState.errors.email ? 'error' : ''} ${formData.email && !formState.errors.email ? 'valid' : ''}`}>
                            <input
                                id="email"
                                name="email"
                                type="email"
                                autoComplete="email"
                                className="form-input"
                                value={formData.email}
                                onChange={(e) => handleInputChange('email', e.target.value)}
                                onBlur={() => handleInputBlur('email')}
                                placeholder="Enter your email address"
                                disabled={formState.isLoading}
                                aria-invalid={!!formState.errors.email}
                                aria-describedby={formState.errors.email ? "email-error" : undefined}
                            />
                        </div>
                        {formState.errors.email && (
                            <motion.span 
                                className="field-error"
                                id="email-error"
                                initial={{ opacity: 0, height: 0 }}
                                animate={{ opacity: 1, height: "auto" }}
                                exit={{ opacity: 0, height: 0 }}
                            >
                                {formState.errors.email}
                            </motion.span>
                        )}
                    </motion.div>

                    <motion.div 
                        className="form-group"
                        initial={{ opacity: 0, x: -20 }}
                        animate={{ opacity: 1, x: 0 }}
                        transition={{ duration: 0.4, delay: 0.5 }}
                    >
                        <label htmlFor="password" className="form-label">
                            Password
                        </label>
                        <div className={`input-wrapper ${formState.errors.password ? 'error' : ''} ${formData.password && !formState.errors.password ? 'valid' : ''}`}>
                            <input
                                id="password"
                                name="password"
                                type={formState.showPassword ? 'text' : 'password'}
                                autoComplete="current-password"
                                className="form-input"
                                value={formData.password}
                                onChange={(e) => handleInputChange('password', e.target.value)}
                                onBlur={() => handleInputBlur('password')}
                                placeholder="Enter your password"
                                disabled={formState.isLoading}
                                aria-invalid={!!formState.errors.password}
                                aria-describedby={formState.errors.password ? "password-error" : undefined}
                            />
                            <motion.button
                                type="button"
                                className="password-toggle"
                                onClick={togglePasswordVisibility}
                                disabled={formState.isLoading}
                                whileHover={{ scale: 1.1 }}
                                whileTap={{ scale: 0.9 }}
                            >
                                {formState.showPassword ? <EyeOff size={20} /> : <Eye size={20} />}
                            </motion.button>
                        </div>
                        {formState.errors.password && (
                            <motion.span 
                                className="field-error"
                                id="password-error"
                                initial={{ opacity: 0, height: 0 }}
                                animate={{ opacity: 1, height: "auto" }}
                                exit={{ opacity: 0, height: 0 }}
                            >
                                {formState.errors.password}
                            </motion.span>
                        )}
                    </motion.div>

                    <motion.div 
                        className="form-extras"
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        transition={{ duration: 0.4, delay: 0.6 }}
                    >
                        <div className="remember-me">
                            <input
                                id="remember"
                                type="checkbox"
                                className="checkbox"
                            />
                            <label htmlFor="remember" className="checkbox-label">
                                Remember me
                            </label>
                        </div>
                        <Link to="/forgot-password" className="forgot-password">
                            Forgot password?
                        </Link>
                    </motion.div>

                    <motion.button 
                        type="submit" 
                        className={`login-button ${formState.isLoading ? 'loading' : ''}`}
                        disabled={formState.isLoading}
                        initial={{ opacity: 0, y: 10 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ duration: 0.4, delay: 0.7 }}
                        whileHover={{ scale: 1.02 }}
                        whileTap={{ scale: 0.98 }}
                    >
                        {formState.isLoading ? (
                            <LoadingSpinner size="sm" />
                        ) : (
                            <>
                                <span className="button-text">Sign In</span>
                                <ArrowRight className="button-icon" size={20} />
                            </>
                        )}
                    </motion.button>
                </motion.form>

                <motion.div 
                    className="login-footer"
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    transition={{ duration: 0.5, delay: 0.8 }}
                >
                    <p className="signup-prompt">
                        Don't have an account? 
                        <Link to="/register" className="signup-link">
                            Create one now
                        </Link>
                    </p>
                </motion.div>

                <motion.div 
                    className="social-login"
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    transition={{ duration: 0.5, delay: 0.9 }}
                >
                    <div className="divider">
                        <span className="divider-text">Or continue with</span>
                    </div>
                    <div className="social-buttons">
                        <motion.button 
                            className="social-button google"
                            whileHover={{ scale: 1.05 }}
                            whileTap={{ scale: 0.95 }}
                        >
                            <svg width="20" height="20" viewBox="0 0 24 24">
                                <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>
                                <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
                                <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/>
                                <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/>
                            </svg>
                            Google
                        </motion.button>
                        <motion.button 
                            className="social-button github"
                            whileHover={{ scale: 1.05 }}
                            whileTap={{ scale: 0.95 }}
                        >
                            <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
                                <path d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.905 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57A12.02 12.02 0 0 0 24 12c0-6.63-5.37-12-12-12z"/>
                            </svg>
                            GitHub
                        </motion.button>
                    </div>
                </motion.div>
            </motion.div>
        </div>
        </>
    );
};

export default Login;