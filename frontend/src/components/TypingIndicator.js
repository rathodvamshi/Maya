// Modern ChatGPT-Style Typing Indicator
import React from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Bot } from 'lucide-react';
import '../styles/TypingIndicator.css';

const TypingIndicator = ({ isVisible = false }) => {
  return (
    <AnimatePresence>
      {isVisible && (
        <motion.div 
          className="typing-indicator-container"
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -10 }}
          transition={{ duration: 0.2, ease: "easeOut" }}
        >
          <div className="typing-indicator-avatar">
            <Bot size={18} />
          </div>
          <div className="typing-indicator">
            <div className="typing-dot"></div>
            <div className="typing-dot"></div>
            <div className="typing-dot"></div>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
};

export default TypingIndicator;