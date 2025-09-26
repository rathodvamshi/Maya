import React from 'react';
import { motion } from 'framer-motion';
import '../styles/variables.css';
import '../styles/LoadingSpinnerNew.css';

const LoadingSpinner = ({ size = 'md', text = 'Loading...', color = 'primary' }) => {
    const sizeClasses = {
        sm: 'spinner-sm',
        md: 'spinner-md',
        lg: 'spinner-lg'
    };

    return (
        <motion.div 
            className={`loading-spinner ${sizeClasses[size]}`}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
        >
            <div className={`spinner ${color}`}>
                <motion.div
                    className="spinner-ring"
                    animate={{ rotate: 360 }}
                    transition={{ duration: 1, repeat: Infinity, ease: "linear" }}
                />
            </div>
            {text && <span className="spinner-text">{text}</span>}
        </motion.div>
    );
};

export default LoadingSpinner;
