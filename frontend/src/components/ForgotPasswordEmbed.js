import React, { useState } from 'react';
import { Mail, Lock } from 'lucide-react';
import { sendOtp, verifyOtp, updatePassword } from '../services/forgotPassword';

const ForgotPasswordEmbed = ({ onBack }) => {
  const [step, setStep] = useState(1);
  const [form, setForm] = useState({ email: '', otp: '', pw: '', cpw: '' });
  const [errors, setErrors] = useState({});
  const [loading, setLoading] = useState(false);
  const [msg, setMsg] = useState('');
  const [msgType, setMsgType] = useState('');

  const onChange = (e) => {
    const { name, value } = e.target;
    setForm((s) => ({ ...s, [name]: value }));
    if (errors[name]) setErrors((er) => ({ ...er, [name]: undefined }));
  };

  const validEmail = (email) => /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
  const pwOK = /^(?=.*[A-Z])(?=.*\d)(?=.*[^A-Za-z0-9]).{8,}$/.test(form.pw || '');

  const doSend = async (e) => {
    e.preventDefault();
    const errs = {};
    if (!form.email) errs.email = 'Email is required';
    else if (!validEmail(form.email)) errs.email = 'Invalid email';
    setErrors(errs);
    if (Object.keys(errs).length) return;
    setLoading(true); setMsg(''); setMsgType('');
    try {
      await sendOtp(form.email);
      setMsg('OTP sent to your email'); setMsgType('success');
      setStep(2);
    } catch (err) {
      const apiMsg = err.response?.data?.error?.message || err.response?.data?.detail;
      setMsg(apiMsg || 'Failed to send OTP'); setMsgType('error');
    } finally { setLoading(false); }
  };

  const doVerify = async (e) => {
    e.preventDefault();
    const errs = {};
    if (!form.otp) errs.otp = 'OTP is required';
    else if (form.otp.length !== 4) errs.otp = 'OTP must be 4 digits';
    setErrors(errs);
    if (Object.keys(errs).length) return;
    setLoading(true); setMsg(''); setMsgType('');
    try {
      await verifyOtp(form.email, form.otp);
      setMsg('OTP verified'); setMsgType('success');
      setStep(3);
    } catch (err) {
      const apiMsg = err.response?.data?.error?.message || err.response?.data?.detail;
      setMsg(apiMsg || 'Invalid or expired OTP'); setMsgType('error');
    } finally { setLoading(false); }
  };

  const doUpdate = async (e) => {
    e.preventDefault();
    const errs = {};
    if (!form.pw) errs.pw = 'Password is required';
    else if (!pwOK) errs.pw = 'Must be 8+ chars with uppercase, number, special character';
    if (!form.cpw) errs.cpw = 'Confirm your password';
    else if (form.cpw !== form.pw) errs.cpw = 'Passwords do not match';
    setErrors(errs);
    if (Object.keys(errs).length) return;
    setLoading(true); setMsg(''); setMsgType('');
    try {
      const res = await updatePassword(form.email, form.pw);
      const action = res.data?.action;
      setMsg(action === 'created' ? 'Account created successfully!' : 'Password successfully updated!');
      setMsgType('success');
      setTimeout(() => onBack?.(), 1200);
    } catch (err) {
      const apiMsg = err.response?.data?.error?.message || err.response?.data?.detail;
      setMsg(apiMsg || 'Failed to update password'); setMsgType('error');
    } finally { setLoading(false); }
  };

  return (
    <div>
      {msg && <div className={`auth-message ${msgType === 'success' ? 'success' : msgType === 'error' ? 'error' : 'info'}`}>{msg}</div>}

      {step === 1 && (
        <form className="auth-form" onSubmit={doSend}>
          <div className="auth-input-group">
            <div className={`auth-input-wrapper ${errors.email ? 'error' : ''}`}>
              <Mail className="auth-input-icon" size={18} />
              <input
                type="email" name="email" value={form.email} onChange={onChange}
                placeholder="Enter your email" autoComplete="username" className="auth-input" />
            </div>
            {errors.email && <span className="error-text">{errors.email}</span>}
          </div>
          <button type="submit" className="auth-submit-btn" disabled={loading}>
            {loading ? <div className="auth-spinner"></div> : 'Send OTP'}
          </button>
          <div className="auth-form-meta">
            <button type="button" className="link-button forgot-link" onClick={onBack}>Back to Sign In</button>
          </div>
        </form>
      )}

      {step === 2 && (
        <form className="auth-form" onSubmit={doVerify}>
          <div className="auth-message info">We've sent a 4-digit OTP to <strong>{form.email}</strong></div>
          <div className="auth-input-group">
            <div className={`auth-input-wrapper ${errors.otp ? 'error' : ''}`}>
              <input
                type="text" name="otp" value={form.otp} onChange={onChange}
                placeholder="Enter 4-digit OTP" maxLength={4} className="auth-input" />
            </div>
            {errors.otp && <span className="error-text">{errors.otp}</span>}
          </div>
          <button type="submit" className="auth-submit-btn" disabled={loading}>
            {loading ? <div className="auth-spinner"></div> : 'Verify OTP'}
          </button>
          <div className="auth-form-meta">
            <button type="button" className="link-button forgot-link" onClick={() => setStep(1)}>Back</button>
          </div>
        </form>
      )}

      {step === 3 && (
        <form className="auth-form" onSubmit={doUpdate}>
          <div className="auth-input-group">
            <div className={`auth-input-wrapper ${errors.pw ? 'error' : ''}`}>
              <Lock className="auth-input-icon" size={18} />
              <input
                type="password" name="pw" value={form.pw} onChange={onChange}
                placeholder="New password" autoComplete="new-password" className="auth-input" />
            </div>
            {form.pw && (
              <div className={`password-criteria ${pwOK ? 'ok' : ''}`}>
                Meets all criteria: 8+ characters, uppercase, number, and special character.
              </div>
            )}
            {errors.pw && <span className="error-text">{errors.pw}</span>}
          </div>
          <div className="auth-input-group">
            <div className={`auth-input-wrapper ${errors.cpw ? 'error' : ''}`}>
              <Lock className="auth-input-icon" size={18} />
              <input
                type="password" name="cpw" value={form.cpw} onChange={onChange}
                placeholder="Confirm password" autoComplete="new-password" className="auth-input" />
            </div>
            {errors.cpw && <span className="error-text">{errors.cpw}</span>}
          </div>
          <button type="submit" className="auth-submit-btn" disabled={loading}>
            {loading ? <div className="auth-spinner"></div> : 'Update Password'}
          </button>
          <div className="auth-form-meta">
            <button type="button" className="link-button forgot-link" onClick={onBack}>Back to Sign In</button>
          </div>
        </form>
      )}
    </div>
  );
};

export default ForgotPasswordEmbed;
