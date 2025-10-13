import React, { useState } from 'react';
import { motion } from 'framer-motion';

const presetHobbies = ['Reading','Gaming','Music','Travel','Cooking','Fitness','Open Source','UI Design','Writing'];
const roles = [
  'Web Developer 💻',
  'AI Developer 🤖',
  'Employee 👔',
  'Designer 🎨',
  'Manager 🧭',
  'Researcher 🔬',
  'Content Creator ✍️'
];

const ProfileDetailsStep = ({ onComplete, onSkip, isSubmitting }) => {
  const [username,setUsername]=useState('');
  const [role,setRole]=useState('');
  const [hobbies,setHobbies]=useState([]);
  const [subStep, setSubStep] = useState(1); // 1: name, 2: role, 3: hobbies

  const toggleHobby = (h) => {
    setHobbies(prev => prev.includes(h)? prev.filter(x=>x!==h): [...prev,h]);
  };

  const nextFromName = (e) => {
    e.preventDefault();
    if (username.trim().length === 0) return;
    setSubStep(2);
  };

  const nextFromRole = (e) => {
    e.preventDefault();
    if (!role) return;
    setSubStep(3);
  };

  const submit=(e)=>{
    e.preventDefault();
    onComplete({username, role, hobbies});
  };

  return (
    <motion.form onSubmit={submit} initial={{opacity:0,y:20}} animate={{opacity:1,y:0}} className="profile-step">
      <h3 className="step-title">Complete Your Profile</h3>
      <p className="step-subtitle">Optional details help Maya personalize responses.</p>

      {subStep === 1 && (
        <div className="form-group">
          <label>Username</label>
          <input value={username} onChange={e=>setUsername(e.target.value)} placeholder="Choose a username" />
          <div className="profile-actions">
            <button type="button" className="btn btn-secondary" onClick={onSkip}>Skip</button>
            <button type="button" className="btn btn-primary" onClick={nextFromName} disabled={!username.trim()}>Next</button>
          </div>
        </div>
      )}

      {subStep === 2 && (
        <div className="form-group">
          <label>Role</label>
          <select value={role} onChange={e=>setRole(e.target.value)}>
            <option value="">Select role</option>
            {roles.map(r=> <option key={r} value={r}>{r}</option>)}
          </select>
          <div className="profile-actions">
            <button type="button" className="btn btn-secondary" onClick={()=>setSubStep(1)}>Back</button>
            <button type="button" className="btn btn-primary" onClick={nextFromRole} disabled={!role}>Next</button>
          </div>
        </div>
      )}

      {subStep === 3 && (
        <>
          <div className="form-group">
            <label>Hobbies</label>
            <div className="hobby-grid">
              {presetHobbies.map(h => (
                <button type="button" key={h} className={`hobby-chip ${hobbies.includes(h)?'active':''}`} onClick={()=>toggleHobby(h)}>{h}</button>
              ))}
            </div>
          </div>
          <div className="profile-actions">
            <button type="button" className="btn btn-secondary" onClick={()=>setSubStep(2)}>Back</button>
            <button type="submit" className="btn btn-primary" disabled={isSubmitting}>{isSubmitting? 'Saving...' : 'Finish'}</button>
          </div>
        </>
      )}
    </motion.form>
  );
};

export default ProfileDetailsStep;
