import { useState } from 'react';
import { ArrowLeft, Mail, Lock, CheckCircle } from 'lucide-react';
import '../styles/Auth.css';
import fpService from '../services/forgotPassword';

const ForgotPassword = ({ onNavigate }) => {
  const [step, setStep] = useState(1);
  const [formData, setFormData] = useState({
    email: '',
    otp: '',
    newPassword: '',
    confirmPassword: '',
  });
  const [errors, setErrors] = useState({});
  const [isLoading, setIsLoading] = useState(false);
  const [message, setMessage] = useState('');
  const [messageType, setMessageType] = useState('');

  const validateEmail = () => {
    const newErrors = {};
    if (!formData.email) {
      newErrors.email = 'Email is required';
    } else if (!/\S+@\S+\.\S+/.test(formData.email)) {
      newErrors.email = 'Email is invalid';
    }
    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const validateOtp = () => {
    const newErrors = {};
    if (!formData.otp) {
      newErrors.otp = 'OTP is required';
    } else if (formData.otp.length !== 4) {
      newErrors.otp = 'OTP must be 4 digits';
    }
    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const validatePassword = () => {
    const newErrors = {};
    if (!formData.newPassword) {
      newErrors.newPassword = 'Password is required';
    } else if (!(/^(?=.*[A-Z])(?=.*\d)(?=.*[^A-Za-z0-9]).{8,}$/).test(formData.newPassword)) {
      newErrors.newPassword = 'Must be 8+ chars with uppercase, number, special character';
    }
    if (!formData.confirmPassword) {
      newErrors.confirmPassword = 'Please confirm your password';
    } else if (formData.newPassword !== formData.confirmPassword) {
      newErrors.confirmPassword = 'Passwords do not match';
    }
    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSendOtp = async (e) => {
    e.preventDefault();
    if (validateEmail()) {
      setIsLoading(true);
      setMessage(''); setMessageType('');
      try {
        const res = await fpService.sendOtp(formData.email);
        setMessage('OTP sent to your email');
        setMessageType('success');
        setStep(2);
      } catch (err) {
        const apiMsg = err.response?.data?.error?.message || err.response?.data?.detail;
        setMessage(apiMsg || 'Failed to send OTP. Please try again.');
        setMessageType('error');
      } finally {
        setIsLoading(false);
      }
    }
  };

  const handleVerifyOtp = async (e) => {
    e.preventDefault();
    if (validateOtp()) {
      setIsLoading(true);
      setMessage(''); setMessageType('');
      try {
        await fpService.verifyOtp(formData.email, formData.otp);
        setMessage('OTP verified');
        setMessageType('success');
        setStep(3);
      } catch (err) {
        const apiMsg = err.response?.data?.error?.message || err.response?.data?.detail;
        setMessage(apiMsg || 'Invalid or expired OTP.');
        setMessageType('error');
      } finally {
        setIsLoading(false);
      }
    }
  };

  const handleResetPassword = async (e) => {
    e.preventDefault();
    if (validatePassword()) {
      setIsLoading(true);
      setMessage(''); setMessageType('');
      try {
        const res = await fpService.updatePassword(formData.email, formData.newPassword);
        const action = res.data?.action;
        setMessage(action === 'created' ? 'Account created successfully!' : 'Password successfully updated!');
        setMessageType('success');
        setTimeout(() => onNavigate('login'), 1200);
      } catch (err) {
        const apiMsg = err.response?.data?.error?.message || err.response?.data?.detail;
        setMessage(apiMsg || 'Failed to update password.');
        setMessageType('error');
      } finally {
        setIsLoading(false);
      }
    }
  };

  const handleChange = (e) => {
    setFormData({
      ...formData,
      [e.target.name]: e.target.value,
    });
    if (errors[e.target.name]) {
      setErrors({
        ...errors,
        [e.target.name]: undefined,
      });
    }
  };

  return (
    <div className="auth-page">
      <div className="auth-container">
        <div className="auth-card">
          <div className="auth-header">
            <div className="auth-logo">M</div>
            <h2 className="auth-title">Reset Password</h2>
            <p className="auth-subtitle">
              {step === 1 && 'Step 1: Enter your email'}
              {step === 2 && 'Step 2: Verify OTP'}
              {step === 3 && 'Step 3: Create new password'}
            </p>
            <div className="progress-bar">
              <div
                className={`progress-fill ${step === 2 ? 'progress-half' : ''} ${
                  step === 3 ? 'progress-complete' : ''
                }`}
              ></div>
            </div>
          </div>

          {message && (
            <div className={`auth-message ${messageType}`}>{message}</div>
          )}
          {step === 1 && (
            <form className="auth-form" onSubmit={handleSendOtp}>
              <div className="form-group">
                <label htmlFor="email" className="form-label">
                  <Mail size={16} />
                  Email Address
                </label>
                <input
                  type="email"
                  id="email"
                  name="email"
                  className={`form-input ${errors.email ? 'input-error' : ''}`}
                  placeholder="Enter your registered email"
                  value={formData.email}
                  onChange={handleChange}
                />
                {errors.email && <span className="error-text">{errors.email}</span>}
              </div>

              <button type="submit" className="btn btn-primary btn-block" disabled={isLoading}>
                {isLoading ? 'Sending OTP...' : 'Send OTP'}
              </button>
            </form>
          )}

          {step === 2 && (
            <form className="auth-form" onSubmit={handleVerifyOtp}>
              <div className="info-message">We've sent a 4-digit OTP to <strong>{formData.email}</strong></div>

              <div className="form-group">
                <label htmlFor="otp" className="form-label">
                  Enter OTP
                </label>
                <input
                  type="text"
                  id="otp"
                  name="otp"
                  className={`form-input ${errors.otp ? 'input-error' : ''}`}
                  placeholder="Enter 4-digit OTP"
                  maxLength={4}
                  value={formData.otp}
                  onChange={handleChange}
                />
                {errors.otp && <span className="error-text">{errors.otp}</span>}
              </div>

              <div className="form-actions">
                <button
                  type="button"
                  className="btn btn-secondary"
                  onClick={() => setStep(1)}
                >
                  Back
                </button>
                <button type="submit" className="btn btn-primary" disabled={isLoading}>
                  {isLoading ? 'Verifying...' : 'Verify OTP'}
                </button>
              </div>
            </form>
          )}

          {step === 3 && (
            <form className="auth-form" onSubmit={handleResetPassword}>
              <div className="form-group">
                <label htmlFor="newPassword" className="form-label">
                  <Lock size={16} />
                  New Password
                </label>
                <input
                  type="password"
                  id="newPassword"
                  name="newPassword"
                  className={`form-input ${errors.newPassword ? 'input-error' : ''}`}
                  placeholder="Create a new password"
                  value={formData.newPassword}
                  onChange={handleChange}
                />
                {formData.newPassword && (
                  <div className={`password-criteria ${/^(?=.*[A-Z])(?=.*\d)(?=.*[^A-Za-z0-9]).{8,}$/.test(formData.newPassword) ? 'ok' : ''}`}>
                    Meets all criteria: 8+ characters, uppercase, number, and special character.
                  </div>
                )}
                {errors.newPassword && (
                  <span className="error-text">{errors.newPassword}</span>
                )}
              </div>

              <div className="form-group">
                <label htmlFor="confirmPassword" className="form-label">
                  Confirm Password
                </label>
                <input
                  type="password"
                  id="confirmPassword"
                  name="confirmPassword"
                  className={`form-input ${errors.confirmPassword ? 'input-error' : ''}`}
                  placeholder="Confirm your new password"
                  value={formData.confirmPassword}
                  onChange={handleChange}
                />
                {errors.confirmPassword && (
                  <span className="error-text">{errors.confirmPassword}</span>
                )}
              </div>

              <button type="submit" className="btn btn-primary btn-block" disabled={isLoading}>
                {isLoading ? 'Resetting Password...' : 'Reset Password'}
              </button>
            </form>
          )}

          <div className="auth-switch">
            <button
              className="link-button"
              onClick={() => onNavigate('login')}
              style={{ display: 'flex', alignItems: 'center', gap: '4px' }}
            >
              <ArrowLeft size={16} />
              Back to Login
            </button>
          </div>
        </div>

        <button className="back-button" onClick={() => onNavigate('landing')}>
          ← Back to Home
        </button>
      </div>
    </div>
  );
};

export default ForgotPassword;
