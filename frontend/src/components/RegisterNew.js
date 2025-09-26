import React, { useState, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { Mail, Lock, Eye, EyeOff, UserPlus, Sparkles, Shield, CheckCircle, AlertCircle } from 'lucide-react';
import authService from '../services/auth';
import LoadingSpinner from './LoadingSpinner';
import '../styles/variables.css';
import '../styles/RegisterNew.css';

const Register = ({ onAuthSuccess }) => {
    const navigate = useNavigate();
    const [formData, setFormData] = useState({
        email: '',
        password: '',
        confirmPassword: ''
    });
    const [formState, setFormState] = useState({
        message: '',
        messageType: '', // 'success', 'error', 'info'
        successful: false,
        isLoading: false,
        showPassword: false,
        showConfirmPassword: false,
        errors: {
            email: '',
            password: '',
            confirmPassword: ''
        }
    });
    const [fieldTouched, setFieldTouched] = useState({
        email: false,
        password: false,
        confirmPassword: false
    });
    const [passwordStrength, setPasswordStrength] = useState({ score: 0, feedback: [] });

    // Validation functions
    const validateEmail = (email) => {
        const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        if (!email) return 'Email is required';
        if (!emailRegex.test(email)) return 'Please enter a valid email address';
        return '';
    };

    const validatePassword = (password) => {
        if (!password) return 'Password is required';
        if (password.length < 8) return 'Password must be at least 8 characters';
        return '';
    };

    const validateConfirmPassword = (password, confirmPassword) => {
        if (!confirmPassword) return 'Please confirm your password';
        if (password !== confirmPassword) return 'Passwords do not match';
        return '';
    };

    const checkPasswordStrength = (password) => {
        let score = 0;
        const feedback = [];

        if (password.length >= 8) {
            score++;
        } else {
            feedback.push('At least 8 characters');
        }

        if (/[A-Z]/.test(password)) {
            score++;
        } else {
            feedback.push('One uppercase letter');
        }

        if (/[a-z]/.test(password)) {
            score++;
        } else {
            feedback.push('One lowercase letter');
        }

        if (/[0-9]/.test(password)) {
            score++;
        } else {
            feedback.push('One number');
        }

        if (/[^A-Za-z0-9]/.test(password)) {
            score++;
        } else {
            feedback.push('One special character');
        }

        return { score, feedback };
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
        setPasswordStrength(checkPasswordStrength(formData.password));
    }, [formData.password, fieldTouched.password]);

    useEffect(() => {
        if (fieldTouched.confirmPassword) {
            setFormState(prev => ({
                ...prev,
                errors: { 
                    ...prev.errors, 
                    confirmPassword: validateConfirmPassword(formData.password, formData.confirmPassword) 
                }
            }));
        }
    }, [formData.password, formData.confirmPassword, fieldTouched.confirmPassword]);

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

    const handleRegister = async (e) => {
        e.preventDefault();
        
        // Validate all fields
        const emailError = validateEmail(formData.email);
        const passwordError = validatePassword(formData.password);
        const confirmPasswordError = validateConfirmPassword(formData.password, formData.confirmPassword);
        
        if (emailError || passwordError || confirmPasswordError) {
            setFormState(prev => ({
                ...prev,
                errors: { 
                    email: emailError, 
                    password: passwordError,
                    confirmPassword: confirmPasswordError 
                },
                message: 'Please correct the errors below',
                messageType: 'error'
            }));
            setFieldTouched({ email: true, password: true, confirmPassword: true });
            return;
        }

        setFormState(prev => ({ ...prev, isLoading: true, message: '', messageType: '' }));

        try {
            await authService.register(formData.email, formData.password);
            setFormState(prev => ({
                ...prev,
                message: 'Registration successful! You can now log in.',
                messageType: 'success',
                successful: true
            }));
            
            // Redirect to login after successful registration
            setTimeout(() => {
                navigate('/login');
            }, 2000);
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
                messageType: 'error',
                successful: false
            }));
        } finally {
            setFormState(prev => ({ ...prev, isLoading: false }));
        }
    };

    const togglePasswordVisibility = () => {
        setFormState(prev => ({ ...prev, showPassword: !prev.showPassword }));
    };

    const toggleConfirmPasswordVisibility = () => {
        setFormState(prev => ({ ...prev, showConfirmPassword: !prev.showConfirmPassword }));
    };

    const getStrengthColor = (score) => {
        if (score <= 2) return '#ef4444';
        if (score <= 3) return '#f59e0b';
        if (score <= 4) return '#10b981';
        return '#059669';
    };

    const getStrengthText = (score) => {
        if (score <= 2) return 'Weak';
        if (score <= 3) return 'Fair';
        if (score <= 4) return 'Good';
        return 'Strong';
    };

    return (
        <div className="register-screen">
            <div className="register-background">
                <div className="floating-particles">
                    <motion.div 
                        className="particle particle-1"
                        animate={{ 
                            y: [0, -30, 0],
                            rotate: [0, 360]
                        }}
                        transition={{ 
                            duration: 15,
                            repeat: Infinity,
                            ease: "linear"
                        }}
                    />
                    <motion.div 
                        className="particle particle-2"
                        animate={{ 
                            y: [0, 25, 0],
                            rotate: [0, -360]
                        }}
                        transition={{ 
                            duration: 20,
                            repeat: Infinity,
                            ease: "linear"
                        }}
                    />
                    <motion.div 
                        className="particle particle-3"
                        animate={{ 
                            y: [0, -20, 0],
                            rotate: [0, 180]
                        }}
                        transition={{ 
                            duration: 18,
                            repeat: Infinity,
                            ease: "linear"
                        }}
                    />
                    <motion.div 
                        className="particle particle-4"
                        animate={{ 
                            y: [0, 35, 0],
                            rotate: [0, -180]
                        }}
                        transition={{ 
                            duration: 22,
                            repeat: Infinity,
                            ease: "linear"
                        }}
                    />
                    <motion.div 
                        className="particle particle-5"
                        animate={{ 
                            y: [0, -15, 0],
                            rotate: [0, 270]
                        }}
                        transition={{ 
                            duration: 16,
                            repeat: Infinity,
                            ease: "linear"
                        }}
                    />
                    <motion.div 
                        className="particle particle-6"
                        animate={{ 
                            y: [0, 20, 0],
                            rotate: [0, -270]
                        }}
                        transition={{ 
                            duration: 25,
                            repeat: Infinity,
                            ease: "linear"
                        }}
                    />
                </div>
            </div>
            
            <motion.div 
                className="register-container"
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.6, ease: "easeOut" }}
            >
                <motion.div 
                    className="register-header"
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
                            animate={{ rotate: [0, 15, -15, 0] }}
                            transition={{ duration: 3, repeat: Infinity }}
                        >
                            <UserPlus className="plus-icon" size={16} />
                        </motion.div>
                        <motion.div
                            animate={{ rotate: [0, 10, -10, 0] }}
                            transition={{ duration: 2, repeat: Infinity }}
                        >
                            <Sparkles className="sparkle-icon" size={16} />
                        </motion.div>
                    </div>
                    <h1 className="register-title">Create Account</h1>
                    <p className="register-subtitle">Join our community and start your amazing journey</p>
                </motion.div>

                <motion.form 
                    onSubmit={handleRegister} 
                    className="register-form"
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
                            <Mail className="input-icon" size={20} />
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
                            <Lock className="input-icon" size={20} />
                            <input
                                id="password"
                                name="password"
                                type={formState.showPassword ? 'text' : 'password'}
                                autoComplete="new-password"
                                className="form-input"
                                value={formData.password}
                                onChange={(e) => handleInputChange('password', e.target.value)}
                                onBlur={() => handleInputBlur('password')}
                                placeholder="Create a strong password"
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

                        {/* Password Strength Indicator */}
                        {formData.password && (
                            <motion.div 
                                className="password-strength"
                                initial={{ opacity: 0, height: 0 }}
                                animate={{ opacity: 1, height: "auto" }}
                                transition={{ duration: 0.3 }}
                            >
                                <div className="strength-bar">
                                    <div 
                                        className="strength-fill"
                                        style={{ 
                                            width: `${(passwordStrength.score / 5) * 100}%`,
                                            backgroundColor: getStrengthColor(passwordStrength.score)
                                        }}
                                    />
                                </div>
                                <div className="strength-text" style={{ color: getStrengthColor(passwordStrength.score) }}>
                                    {getStrengthText(passwordStrength.score)}
                                </div>
                                {passwordStrength.feedback.length > 0 && (
                                    <ul className="strength-feedback">
                                        {passwordStrength.feedback.map((item, index) => (
                                            <li key={index}>{item}</li>
                                        ))}
                                    </ul>
                                )}
                            </motion.div>
                        )}

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
                        className="form-group"
                        initial={{ opacity: 0, x: -20 }}
                        animate={{ opacity: 1, x: 0 }}
                        transition={{ duration: 0.4, delay: 0.6 }}
                    >
                        <label htmlFor="confirmPassword" className="form-label">
                            Confirm Password
                        </label>
                        <div className={`input-wrapper ${formState.errors.confirmPassword ? 'error' : ''} ${formData.confirmPassword && !formState.errors.confirmPassword ? 'valid' : ''}`}>
                            <Lock className="input-icon" size={20} />
                            <input
                                id="confirmPassword"
                                name="confirmPassword"
                                type={formState.showConfirmPassword ? 'text' : 'password'}
                                autoComplete="new-password"
                                className="form-input"
                                value={formData.confirmPassword}
                                onChange={(e) => handleInputChange('confirmPassword', e.target.value)}
                                onBlur={() => handleInputBlur('confirmPassword')}
                                placeholder="Confirm your password"
                                disabled={formState.isLoading}
                                aria-invalid={!!formState.errors.confirmPassword}
                                aria-describedby={formState.errors.confirmPassword ? "confirm-password-error" : undefined}
                            />
                            <motion.button
                                type="button"
                                className="password-toggle"
                                onClick={toggleConfirmPasswordVisibility}
                                disabled={formState.isLoading}
                                whileHover={{ scale: 1.1 }}
                                whileTap={{ scale: 0.9 }}
                            >
                                {formState.showConfirmPassword ? <EyeOff size={20} /> : <Eye size={20} />}
                            </motion.button>
                        </div>
                        {formState.errors.confirmPassword && (
                            <motion.span 
                                className="field-error"
                                id="confirm-password-error"
                                initial={{ opacity: 0, height: 0 }}
                                animate={{ opacity: 1, height: "auto" }}
                                exit={{ opacity: 0, height: 0 }}
                            >
                                {formState.errors.confirmPassword}
                            </motion.span>
                        )}
                    </motion.div>

                    <motion.button 
                        type="submit" 
                        className={`register-button ${formState.isLoading ? 'loading' : ''}`}
                        disabled={formState.isLoading || formState.successful}
                        initial={{ opacity: 0, y: 10 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ duration: 0.4, delay: 0.7 }}
                        whileHover={{ scale: formState.isLoading ? 1 : 1.02 }}
                        whileTap={{ scale: formState.isLoading ? 1 : 0.98 }}
                    >
                        {formState.isLoading ? (
                            <LoadingSpinner size="sm" text="" color="white" />
                        ) : formState.successful ? (
                            <>
                                <CheckCircle size={20} />
                                <span>Account Created!</span>
                            </>
                        ) : (
                            <>
                                <span className="button-text">Create Account</span>
                                <UserPlus className="button-icon" size={20} />
                            </>
                        )}
                    </motion.button>
                </motion.form>

                <motion.div 
                    className="register-footer"
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    transition={{ duration: 0.5, delay: 0.8 }}
                >
                    <p className="login-prompt">
                        Already have an account? 
                        <Link to="/login" className="login-link">
                            Sign in here
                        </Link>
                    </p>
                </motion.div>
            </motion.div>
        </div>
    );
};

export default Register;