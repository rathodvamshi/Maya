import React from 'react';

const MayaLogo = ({ size = 60, className = "" }) => {
    return (
        <svg 
            width={size} 
            height={size} 
            viewBox="0 0 200 200" 
            className={className}
            xmlns="http://www.w3.org/2000/svg"
        >
            <defs>
                <linearGradient id="mayaGradient" x1="0%" y1="0%" x2="100%" y2="100%">
                    <stop offset="0%" style={{stopColor:'#6366f1', stopOpacity:1}} />
                    <stop offset="30%" style={{stopColor:'#8b5cf6', stopOpacity:1}} />
                    <stop offset="60%" style={{stopColor:'#ff6b9d', stopOpacity:1}} />
                    <stop offset="100%" style={{stopColor:'#ffc3a0', stopOpacity:1}} />
                </linearGradient>
                <linearGradient id="brainGradient" x1="0%" y1="0%" x2="100%" y2="100%">
                    <stop offset="0%" style={{stopColor:'#ffffff', stopOpacity:0.95}} />
                    <stop offset="50%" style={{stopColor:'#f0f9ff', stopOpacity:0.9}} />
                    <stop offset="100%" style={{stopColor:'#ddd6fe', stopOpacity:0.8}} />
                </linearGradient>
                <linearGradient id="chatGradient" x1="0%" y1="0%" x2="100%" y2="100%">
                    <stop offset="0%" style={{stopColor:'#3b82f6', stopOpacity:0.8}} />
                    <stop offset="100%" style={{stopColor:'#1d4ed8', stopOpacity:0.9}} />
                </linearGradient>
                <filter id="glow" x="-50%" y="-50%" width="200%" height="200%">
                    <feGaussianBlur stdDeviation="3" result="coloredBlur"/>
                    <feMerge> 
                        <feMergeNode in="coloredBlur"/>
                        <feMergeNode in="SourceGraphic"/>
                    </feMerge>
                </filter>
                <filter id="innerGlow" x="-50%" y="-50%" width="200%" height="200%">
                    <feGaussianBlur stdDeviation="2" result="coloredBlur"/>
                    <feMerge> 
                        <feMergeNode in="coloredBlur"/>
                        <feMergeNode in="SourceGraphic"/>
                    </feMerge>
                </filter>
            </defs>
            
            {/* Main chat bubble container */}
            <g filter="url(#glow)">
                {/* Primary speech bubble */}
                <path 
                    d="M40 70 Q40 45 65 45 L135 45 Q160 45 160 70 L160 110 Q160 135 135 135 L85 135 L65 155 L75 135 L65 135 Q40 135 40 110 Z"
                    fill="url(#mayaGradient)"
                    stroke="rgba(255, 255, 255, 0.2)"
                    strokeWidth="1"
                />
                
                {/* Secondary smaller chat bubble */}
                <circle 
                    cx="170" 
                    cy="60" 
                    r="12" 
                    fill="url(#chatGradient)"
                    opacity="0.7"
                />
                <circle 
                    cx="185" 
                    cy="45" 
                    r="8" 
                    fill="url(#chatGradient)"
                    opacity="0.5"
                />
                <circle 
                    cx="195" 
                    cy="30" 
                    r="5" 
                    fill="url(#chatGradient)"
                    opacity="0.3"
                />
            </g>
            
            {/* Enhanced brain design */}
            <g transform="translate(70, 65)" filter="url(#innerGlow)">
                {/* Brain outline */}
                <path 
                    d="M30 25 Q35 10 45 15 Q50 5 60 15 Q65 20 60 30 Q55 35 50 30 Q45 40 35 35 Q25 30 30 25 Z"
                    fill="url(#brainGradient)"
                    stroke="rgba(255, 255, 255, 0.6)"
                    strokeWidth="1.5"
                />
                
                {/* Left hemisphere neural pathways */}
                <g stroke="rgba(139, 92, 246, 0.7)" strokeWidth="1.2" fill="none">
                    <path d="M32 20 Q35 15 38 20 Q35 25 32 20"/>
                    <path d="M30 28 Q33 23 36 28 Q33 33 30 28"/>
                    <path d="M38 32 Q41 27 44 32 Q41 37 38 32"/>
                </g>
                
                {/* Right hemisphere neural pathways */}
                <g stroke="rgba(99, 102, 241, 0.7)" strokeWidth="1.2" fill="none">
                    <path d="M52 20 Q55 15 58 20 Q55 25 52 20"/>
                    <path d="M50 28 Q53 23 56 28 Q53 33 50 28"/>
                    <path d="M46 32 Q49 27 52 32 Q49 37 46 32"/>
                </g>
                
                {/* Central connection */}
                <line x1="42" y1="25" x2="48" y2="25" stroke="rgba(255, 107, 157, 0.8)" strokeWidth="1.5"/>
                
                {/* Neural nodes */}
                <circle cx="35" cy="22" r="1.5" fill="rgba(139, 92, 246, 0.9)"/>
                <circle cx="45" cy="18" r="1.5" fill="rgba(99, 102, 241, 0.9)"/>
                <circle cx="40" cy="30" r="1.5" fill="rgba(255, 107, 157, 0.9)"/>
                <circle cx="50" cy="30" r="1.5" fill="rgba(255, 195, 160, 0.9)"/>
                <circle cx="55" cy="22" r="1.5" fill="rgba(139, 92, 246, 0.9)"/>
                
                {/* Synaptic connections */}
                <g stroke="rgba(255, 255, 255, 0.4)" strokeWidth="0.8" fill="none">
                    <path d="M35 22 L45 18"/>
                    <path d="M40 30 L50 30"/>
                    <path d="M45 18 L55 22"/>
                    <path d="M35 22 L40 30"/>
                    <path d="M50 30 L55 22"/>
                </g>
            </g>
            
            {/* Chat message dots inside bubble */}
            <g transform="translate(90, 90)">
                <circle cx="0" cy="0" r="3" fill="rgba(255, 255, 255, 0.9)"/>
                <circle cx="12" cy="0" r="3" fill="rgba(255, 255, 255, 0.7)"/>
                <circle cx="24" cy="0" r="3" fill="rgba(255, 255, 255, 0.5)"/>
            </g>
        </svg>
    );
};

export default MayaLogo;