import { useState, useEffect, useRef } from 'react';
import { Mail, Lock, Eye, EyeOff } from 'lucide-react';
import OtpVerification from './OtpVerification';
import ProfileDetailsStep from './ProfileDetailsStep';
import SignupSuccess from './SignupSuccess';
import { sendOtp, verifyOtp, completeRegistration, checkEmailAvailable } from '../services/signup';
import '../styles/RegisterNew.css';

const Register = ({ onNavigate, onRegister, embed = false }) => {
  // Steps: 1 credentials, 2 otp, 3 profile, 4 success
  const [step, setStep] = useState(1);
  const [formData, setFormData] = useState({
    email: '',
    password: '',
    confirmPassword: '',
    username: '',
    role: '',
  });
  const [errors, setErrors] = useState({});
    const [isLoading, setIsLoading] = useState(false);
    const [otpError, setOtpError] = useState('');
    const [verifyingOtp, setVerifyingOtp] = useState(false);
    const [otpSent, setOtpSent] = useState(false);
    const [otpSuccess, setOtpSuccess] = useState(false);
  const [resendCooldown, setResendCooldown] = useState(0);
  const [resentJustNow, setResentJustNow] = useState(false);
  const [tempPassword, setTempPassword] = useState('');
  const [finalizing, setFinalizing] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const [passwordStrength, setPasswordStrength] = useState({ score: 0, feedback: [] });
  const [emailAvailable, setEmailAvailable] = useState(true);
  const [checkingEmail, setCheckingEmail] = useState(false);
  const [emailChecked, setEmailChecked] = useState(false);
  const debounceRef = useRef();

  const validateStep1 = () => {
    const newErrors = {};

    if (!formData.email) {
      newErrors.email = 'Email is required';
    } else if (!/\S+@\S+\.\S+/.test(formData.email)) {
      newErrors.email = 'Email is invalid';
    }

    if (!formData.password) {
      newErrors.password = 'Password is required';
    } else if (formData.password.length < 8) {
      newErrors.password = 'Password must be at least 8 characters';
    }

    if (!formData.confirmPassword) {
      newErrors.confirmPassword = 'Please confirm your password';
    } else if (formData.password !== formData.confirmPassword) {
      newErrors.confirmPassword = 'Passwords do not match';
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  // step2 validation removed (OTP) handled separately
  // Send OTP handler
  const handleSendOtp = async () => {
    setIsLoading(true);
    setOtpError('');
    setOtpSent(false);
    setOtpSuccess(false);
    try {
      const res = await sendOtp(formData.email);
      if (res.data.success) {
        setOtpSent(true);
        setOtpSuccess(true);
        setStep(2);
      } else {
        setOtpError(res.data.message || 'Failed to send OTP');
      }
    } catch (err) {
      const msg = err.response?.data?.message || err.response?.data?.detail || 'Failed to send OTP';
      setOtpError(msg);
    }
    setIsLoading(false);
  };

  // Verify OTP handler
  // In your OTP step UI, show spinner if isLoading or verifyingOtp
  // Show checkmark if otpSuccess, error if otpError

  const checkPasswordStrength = (password) => {
    let score = 0;
    const feedback = [];

    if (password.length >= 8) score++; else feedback.push('At least 8 characters');
    if (/[A-Z]/.test(password)) score++; else feedback.push('One uppercase letter');
    if (/[a-z]/.test(password)) score++; else feedback.push('One lowercase letter');
    if (/[0-9]/.test(password)) score++; else feedback.push('One number');
    if (/[^A-Za-z0-9]/.test(password)) score++; else feedback.push('One special character');

    setPasswordStrength({ score, feedback });
  };

  useEffect(() => {
    checkPasswordStrength(formData.password);
  }, [formData.password]);

  // Live email availability check (debounced)
  // Use onInput for real-time validation, not deprecated onChange
  useEffect(() => {
    const email = formData.email.trim();
    setEmailChecked(false);
    if (!email || !/\S+@\S+\.\S+/.test(email)) {
      setEmailAvailable(true);
      setCheckingEmail(false);
      return;
    }
    setCheckingEmail(true);
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(async () => {
      try {
        const { data } = await checkEmailAvailable(email);
        setEmailAvailable(!!data?.available);
        setEmailChecked(true);
      } catch (e) {
        setEmailAvailable(true); // fail-open
        setEmailChecked(false);
      } finally {
        setCheckingEmail(false);
      }
    }, 600); // 600ms debounce for better UX
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, [formData.email]);

  const meetsAllCriteria = (() => {
    const pw = formData.password || '';
    const lengthOK = pw.length >= 8;
    const upperOK = /[A-Z]/.test(pw);
    const numberOK = /\d/.test(pw);
    const specialOK = /[^A-Za-z0-9]/.test(pw);
    return lengthOK && upperOK && numberOK && specialOK;
  })();

  const handleNext = async (e) => {
    e.preventDefault();
    if (!validateStep1()) return;
    if (!emailAvailable) {
      setErrors(prev => ({ ...prev, email: 'Email already registered' }));
      return;
    }
    setIsLoading(true);
    setOtpError('');
    try {
      await sendOtp(formData.email);
      setTempPassword(formData.password); // preserve before clearing if needed
      setStep(2);
      setResendCooldown(30);
    } catch (err) {
      const msg = err?.response?.data?.detail || err?.response?.data?.message || err?.message;
      setErrors({ email: (typeof msg === 'string' ? msg : 'Failed to send OTP') });
    } finally {
      setIsLoading(false);
    }
  };

  const handleVerifyOtp = async (code) => {
    setVerifyingOtp(true);
    setOtpError('');
    try {
      const { data } = await verifyOtp(formData.email, code);
      if (data.is_verified || data.verified === true) {
        setStep(3);
      } else {
        setOtpError((typeof data?.error === 'string' && data.error) || 'Invalid or expired OTP, please try again.');
      }
    } catch (err) {
      const msg = err?.response?.data?.detail || err?.response?.data?.message || err?.message;
      setOtpError(typeof msg === 'string' ? msg : 'Invalid OTP, please try again.');
    } finally {
      setVerifyingOtp(false);
    }
  };

  const handleResend = async () => {
    if(resendCooldown>0) return;
    try {
      await sendOtp(formData.email);
      setResendCooldown(30);
      setResentJustNow(true);
      setTimeout(()=> setResentJustNow(false), 1500);
    } catch(e){/* ignore */}
  };

  useEffect(()=>{
    if(step===2 && resendCooldown>0){
      const t=setTimeout(()=> setResendCooldown(c=>c-1),1000);
      return ()=>clearTimeout(t);
    }
  },[step,resendCooldown]);

  const handleProfileComplete = async ({username, role, hobbies}) => {
    setFinalizing(true);
    try {
      // Final defensive check to reduce 409s
      try {
        const { data: avail } = await checkEmailAvailable(formData.email);
        if (avail && avail.available === false) {
          setErrors({ submit: 'This email is already registered. Please sign in instead.' });
          setFinalizing(false);
          return;
        }
      } catch(_) { /* ignore and proceed */ }
      const payload = { email: formData.email, password: tempPassword, username, role, hobbies };
      const { data } = await completeRegistration(payload);
      // Auto login: store tokens in the same format as authService.login
      if (data?.access_token) {
        try {
          localStorage.setItem('user', JSON.stringify(data));
        } catch(e) { /* ignore storage errors */ }
      }
      setStep(4);
      onRegister && onRegister();
    } catch (err) {
      const code = err?.response?.status;
      const detail = err?.response?.data?.detail || err?.response?.data?.message || err?.message;
      if (code === 409) {
        setErrors({ submit: 'This email is already registered. Please sign in instead.' });
      } else {
        setErrors({ submit: (typeof detail === 'string' ? detail : 'Failed to complete registration') });
      }
    } finally {
      setFinalizing(false);
    }
  };

  const handleSkipProfile = () => handleProfileComplete({username:'', role:'', hobbies:[]});

  const handleChange = (e) => {
    setFormData({ ...formData, [e.target.name]: e.target.value });
    if (errors[e.target.name]) setErrors({ ...errors, [e.target.name]: '' });
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

  const roleOptions = [
    { value: 'web_dev', label: 'Web Developer 💻' },
    { value: 'ai_dev', label: 'AI Developer 🤖' },
    { value: 'employee', label: 'Employee 👔' },
    { value: 'designer', label: 'Designer 🎨' },
    { value: 'manager', label: 'Manager 🧭' },
    { value: 'researcher', label: 'Researcher 🔬' },
    { value: 'content_creator', label: 'Content Creator ✍️' }
  ];

  const cardContent = (
        <div className={`auth-card ${embed ? 'register-embed-card' : ''}`}>
           <div className="auth-modal-header">
            <div className="progress-bar">
              <div className="progress-fill" style={{width: `${(step/4)*100}%`}}></div>
            </div>
          </div>

          {step === 1 && (
            <form className="auth-form signup-minimal" onSubmit={handleNext}>
              <div className="form-group">
                <div className={`input-wrapper auth-input-wrapper ${errors.email ? 'error' : ''}`}>
                  <Mail className="auth-input-icon" size={20} />
                  <input
                    type="email"
                    name="email"
                    placeholder="Enter your email"
                    value={formData.email}
                    onInput={handleChange}
                    autoComplete="email"
                    className="auth-input"
                  />
                </div>
                <div style={{display:'flex',alignItems:'center',gap:6,minHeight:22}}>
                  {checkingEmail && !errors.email && formData.email && (
                    <span className="auth-subtitle" style={{fontSize:'12px'}}>
                      <span className="spinner" style={{display:'inline-block',width:16,height:16,border:'2px solid #ccc',borderTop:'2px solid #333',borderRadius:'50%',animation:'spin 1s linear infinite',marginRight:4}}></span>
                      Checking availability…
                    </span>
                  )}
                  {emailChecked && emailAvailable && !checkingEmail && !errors.email && formData.email && (
                    <span style={{color:'#059669',fontSize:16}} title="Email is available">✔️ Email is available</span>
                  )}
                  {emailChecked && !emailAvailable && !checkingEmail && !errors.email && formData.email && (
                    <span style={{color:'#ef4444',fontSize:16}} title="Email already registered">❌ Email already registered</span>
                  )}
                  {errors.email && <span className="error-text">{errors.email}</span>}
                </div>
              </div>

              <div className="form-group">
                <div className={`input-wrapper auth-input-wrapper ${errors.password ? 'error' : ''}`}>
                  <Lock className="auth-input-icon" size={20} />
                  <input
                    type={showPassword ? 'text' : 'password'}
                    name="password"
                    placeholder="Create a password"
                    value={formData.password}
                    onChange={handleChange}
                    autoComplete="new-password"
                    className="auth-input"
                  />
                  <button type="button" className="password-toggle auth-password-toggle" onClick={() => setShowPassword(!showPassword)}>
                    {showPassword ? <EyeOff size={20} /> : <Eye size={20} />}
                  </button>
                </div>
                {errors.password && <span className="error-text">{errors.password}</span>}
                {formData.password && (
                  <>
                    <div className={`password-criteria ${meetsAllCriteria ? 'ok' : ''}`}>
                      Meets all criteria: 8+ characters, uppercase, number, and special character.
                    </div>
                  </>
                )}
              </div>

              <div className="form-group">
                <div className={`input-wrapper auth-input-wrapper ${errors.confirmPassword ? 'error' : ''}`}>
                  <Lock className="auth-input-icon" size={20} />
                  <input
                    type={showConfirmPassword ? 'text' : 'password'}
                    name="confirmPassword"
                    placeholder="Confirm your password"
                    value={formData.confirmPassword}
                    onChange={handleChange}
                    autoComplete="new-password"
                    className="auth-input"
                  />
                  <button type="button" className="password-toggle auth-password-toggle" onClick={() => setShowConfirmPassword(!showConfirmPassword)}>
                    {showConfirmPassword ? <EyeOff size={20} /> : <Eye size={20} />}
                  </button>
                </div>
                {errors.confirmPassword && <span className="error-text">{errors.confirmPassword}</span>}
              </div>

              <div className="form-meta-row">
                <button
                  type="button"
                  className="link-button forgot-link"
                  onClick={() => onNavigate && onNavigate('forgot-password')}
                >
                  Forgot Password?
                </button>
              </div>

              <button type="submit" className="auth-submit-btn" disabled={isLoading}>
                {isLoading ? <div className="auth-spinner"></div> : 'Continue'}
              </button>

            </form>
          )}
          {step === 2 && (
            <OtpVerification
              email={formData.email}
              onBack={()=> setStep(1)}
              onVerify={handleVerifyOtp}
              onResend={handleResend}
              isVerifying={verifyingOtp}
              error={otpError}
              resendCooldown={resendCooldown}
              resentJustNow={resentJustNow}
            />
          )}
          {step === 3 && (
            <ProfileDetailsStep
              onComplete={handleProfileComplete}
              onSkip={handleSkipProfile}
              isSubmitting={finalizing}
            />
          )}
          {step === 4 && (
            <SignupSuccess onRedirect={()=> onNavigate && onNavigate('signin')} />
          )}

          {step !== 4 && (
            <div className="auth-switch">
              <span>Already have an account? </span>
              <button className="link-button" onClick={() => onNavigate && onNavigate('signin')}>Sign In</button>
            </div>
          )}
        </div>
  );

  if (embed) {
    return cardContent;
  }

  return (
    <div className="auth-page">
      <div className="auth-container">
        {cardContent}
        <button className="back-button" onClick={() => onNavigate && onNavigate('landing')}>← Back to Home</button>
      </div>
    </div>
  );
};

export default Register;
