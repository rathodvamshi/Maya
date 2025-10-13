import React, { useEffect, useRef, useState } from 'react';
import { motion } from 'framer-motion';

const OtpVerification = ({ email, onBack, onVerify, onResend, isVerifying, error, resendCooldown, resentJustNow }) => {
  const [code, setCode] = useState(['', '', '', '']);
  const inputs = useRef([]);

  useEffect(()=>{
    if(inputs.current[0]) inputs.current[0].focus();
  },[]);

  const handleChange = (idx, val) => {
    if(!/^[0-9]?$/.test(val)) return;
    const next = [...code];
    next[idx] = val;
    setCode(next);
    if(val && idx < 3) inputs.current[idx+1].focus();
  };

  const handleKeyDown = (idx, e) => {
    if(e.key === 'Backspace' && !code[idx] && idx>0) {
      inputs.current[idx-1].focus();
    }
  };

  const submit = (e) => {
    e.preventDefault();
    if(code.every(d=>d)) onVerify(code.join(''));
  };

  return (
    <motion.div initial={{opacity:0,y:20}} animate={{opacity:1,y:0}} className="otp-step">
      <h3 className="step-title">Verify Your Email</h3>
      <p className="step-subtitle">We sent a 4-digit code to <span className="highlight-email">{email}</span>. Enter it below.</p>
      <form onSubmit={submit} className="otp-form">
        <div className="otp-input-row">
          {code.map((d,i)=>(
            <input
              key={i}
              type="text"
              inputMode="numeric"
              maxLength={1}
              value={d}
              onChange={(e)=>handleChange(i,e.target.value)}
              onKeyDown={(e)=>handleKeyDown(i,e)}
              ref={el=>inputs.current[i]=el}
              className="otp-box"
              aria-label={`Digit ${i+1}`}
            />
          ))}
        </div>
        {error && <div className="form-error">{error}</div>}
        <div className="otp-actions">
          <button type="button" onClick={onBack} className="btn btn-secondary sm">Back</button>
          <button type="submit" disabled={isVerifying || !code.every(d=>d)} className="btn btn-primary sm">
            {isVerifying? 'Verifying...' : 'Verify OTP'}
          </button>
        </div>
        <div className="resend-row">
          {resentJustNow ? (
            <span className="form-success">OTP sent!</span>
          ) : resendCooldown>0 ? (
            <span className="cooldown">Resend in {resendCooldown}s</span>
          ) : (
            <button type="button" className="link-button" onClick={onResend}>Resend OTP</button>
          )}
        </div>
      </form>
    </motion.div>
  );
};

export default OtpVerification;
