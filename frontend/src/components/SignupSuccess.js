import React, { useEffect } from 'react';
import { motion } from 'framer-motion';

const SignupSuccess = ({ onRedirect }) => {
  useEffect(()=>{
    const t=setTimeout(()=> onRedirect && onRedirect(), 1800);
    return ()=>clearTimeout(t);
  },[onRedirect]);
  return (
    <motion.div className="signup-success" initial={{scale:0.6,opacity:0}} animate={{scale:1,opacity:1}}>
      <motion.div className="success-check" initial={{scale:0}} animate={{scale:1}} transition={{delay:0.2,type:'spring',stiffness:240}}>
        <svg width="70" height="70" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M20 6 9 17l-5-5"/></svg>
      </motion.div>
      <h3>Account Created!</h3>
      <p>Redirecting...</p>
    </motion.div>
  );
};

export default SignupSuccess;
