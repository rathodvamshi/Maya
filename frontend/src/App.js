import React, { useState, useEffect, useCallback, Suspense } from 'react';
import { BrowserRouter as Router, Routes, Route, Link, Navigate, useLocation } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import Login from './components/Login';
import RegisterNew from './components/RegisterNew';
import AuthModal from './components/AuthModal';
import LandingPage from './components/LandingPage';
import Dashboard from './components/Dashboard';
import LoadingSpinner from './components/LoadingSpinner';
import authService from './services/auth';
import './styles/variables.css';
import './styles/App.css';

/* 
// Old Home component - replaced with LandingPage
const Home = ({ setAuthModal }) => {
    const [showScrollTop, setShowScrollTop] = useState(false);
    const mountRef = useRef(null);

    const handleScroll = useCallback(() => {
        setShowScrollTop(window.scrollY > 300);
    }, []);

    useEffect(() => {
        window.addEventListener('scroll', handleScroll);

        // Setup 3D background animation
        const scene = new THREE.Scene();
        const camera = new THREE.PerspectiveCamera(75, window.innerWidth / window.innerHeight, 0.1, 1000);
        camera.position.z = 15;

        const renderer = new THREE.WebGLRenderer({ alpha: true });
        renderer.setSize(window.innerWidth, window.innerHeight);
        const mount = mountRef.current;
        mount.appendChild(renderer.domElement);

        // Lights
        const directionalLight = new THREE.DirectionalLight(0x3b82f6, 1);
        directionalLight.position.set(5, 5, 5);
        scene.add(directionalLight);

        const ambientLight = new THREE.AmbientLight(0x404040, 0.5);
        scene.add(ambientLight);

        // Particle system for trails
        const particleGeometry = new THREE.BufferGeometry();
        const particleCount = 1000;
        const particlePositions = new Float32Array(particleCount * 3);
        const particleVelocities = new Float32Array(particleCount * 3);
        for (let i = 0; i < particleCount; i++) {
            particlePositions[i * 3] = (Math.random() - 0.5) * 20;
            particlePositions[i * 3 + 1] = (Math.random() - 0.5) * 20;
            particlePositions[i * 3 + 2] = (Math.random() - 0.5) * 20;
            particleVelocities[i * 3] = (Math.random() - 0.5) * 0.01;
            particleVelocities[i * 3 + 1] = (Math.random() - 0.5) * 0.01;
            particleVelocities[i * 3 + 2] = (Math.random() - 0.5) * 0.01;
        }
        particleGeometry.setAttribute('position', new THREE.BufferAttribute(particlePositions, 3));
        const particleMaterial = new THREE.PointsMaterial({
            color: 0x3b82f6,
            size: 0.05,
            transparent: true,
            opacity: 0.3,
        });
        const particles = new THREE.Points(particleGeometry, particleMaterial);
        scene.add(particles);

        // Symbols and tools
        const symbols = ['∑', 'π', '√', '∞', '∫', '≈', 'θ', '🧭', '📏', '🖩', '📐'];
        const meshes = [];
        const targetPositions = [];
        const initialPositions = [];
        const timeOffsets = symbols.map(() => Math.random() * 2 * Math.PI);

        // Simulate brain shape with a point cloud
        const brainRadius = 3;
        symbols.forEach((_, i) => {
            const theta = Math.random() * Math.PI * 2;
            const phi = Math.acos(2 * Math.random() - 1);
            const r = brainRadius * Math.cbrt(Math.random());
            const x = r * Math.sin(phi) * Math.cos(theta);
            const y = r * Math.sin(phi) * Math.sin(theta);
            const z = r * Math.cos(phi);
            targetPositions.push(new THREE.Vector3(x, y, z));
        });

        const fontLoader = new FontLoader();
        fontLoader.load('https://threejs.org/examples/fonts/helvetiker_regular.typeface.json', (font) => {
            symbols.forEach((sym, i) => {
                const textGeo = new TextGeometry(sym, {
                    font,
                    size: 0.3,
                    depth: 0.1,
                    curveSegments: 12,
                    bevelEnabled: true,
                    bevelThickness: 0.01,
                    bevelSize: 0.01,
                    bevelOffset: 0,
                    bevelSegments: 5,
                });

                const material = new THREE.MeshStandardMaterial({
                    color: 0x3b82f6,
                    metalness: 0.9,
                    roughness: 0.2,
                    emissive: 0x3b82f6,
                    emissiveIntensity: 0.8,
                });

                const mesh = new THREE.Mesh(textGeo, material);
                mesh.position.set((Math.random() - 0.5) * 20, (Math.random() - 0.5) * 20, (Math.random() - 0.5) * 20);
                initialPositions.push(mesh.position.clone());
                scene.add(mesh);
                meshes.push(mesh);
            });
        });

        // Animation loop
        const animate = (time) => {
            requestAnimationFrame(animate);

            const scrollFraction = Math.min(document.documentElement.scrollTop / (document.documentElement.scrollHeight - document.documentElement.clientHeight), 1);

            meshes.forEach((mesh, i) => {
                const target = targetPositions[i];
                const initial = initialPositions[i];
                mesh.position.lerpVectors(target, initial, scrollFraction);
                mesh.rotation.y = scrollFraction * Math.PI * 2 + Math.sin(time / 1000 + timeOffsets[i]) * 0.2;
                mesh.rotation.x = Math.sin(time / 1000 + timeOffsets[i]) * 0.1;
                mesh.material.emissiveIntensity = 0.8 + Math.sin(time / 500 + timeOffsets[i]) * 0.2 * (1 - scrollFraction);
            });

            // Update particles
            for (let i = 0; i < particleCount; i++) {
                particlePositions[i * 3] += particleVelocities[i * 3] * (1 - scrollFraction);
                particlePositions[i * 3 + 1] += particleVelocities[i * 3 + 1] * (1 - scrollFraction);
                particlePositions[i * 3 + 2] += particleVelocities[i * 3 + 2] * (1 - scrollFraction);
                if (Math.abs(particlePositions[i * 3]) > 10 || Math.abs(particlePositions[i * 3 + 1]) > 10 || Math.abs(particlePositions[i * 3 + 2]) > 10) {
                    particlePositions[i * 3] = (Math.random() - 0.5) * 20;
                    particlePositions[i * 3 + 1] = (Math.random() - 0.5) * 20;
                    particlePositions[i * 3 + 2] = (Math.random() - 0.5) * 20;
                }
            }
            particleGeometry.attributes.position.needsUpdate = true;

            renderer.render(scene, camera);
        };
        requestAnimationFrame(animate);

        // Handle resize
        const handleResize = () => {
            camera.aspect = window.innerWidth / window.innerHeight;
            camera.updateProjectionMatrix();
            renderer.setSize(window.innerWidth, window.innerHeight);
        };
        window.addEventListener('resize', handleResize);

        return () => {
            window.removeEventListener('scroll', handleScroll);
            window.removeEventListener('resize', handleResize);
            if (mount && renderer.domElement) {
                mount.removeChild(renderer.domElement);
            }
        };
    }, [handleScroll]);

    const scrollToTop = () => {
        window.scrollTo({ top: 0, behavior: 'smooth' });
    };

    return (
        <div className="home-container">
            <div ref={mountRef} className="bg-canvas"></div>

            <div className="hero-section">
                <h1 className="hero-title">Maya: Your Personal AI Assistant</h1>
                <p className="hero-subtitle">An intelligent, adaptive partner for managing tasks and memories with a human touch.</p>
                <div className="hero-cta">
                    <button 
                        onClick={() => setAuthModal({ isOpen: true, mode: 'signin' })} 
                        className="cta-button login-link"
                    >
                        Get Started
                    </button>
                    <button 
                        onClick={() => setAuthModal({ isOpen: true, mode: 'signup' })} 
                        className="cta-button register-link"
                    >
                        Sign Up
                    </button>
                </div>
            </div>

            <section className="about-section">
                <h2 className="section-title">About Maya</h2>
                <p className="section-text">
                    Maya is a cutting-edge personal AI assistant designed to understand you deeply. Powered by advanced AI technologies, Maya remembers your conversations, learns your preferences, and adapts to your unique style, making every interaction feel natural and personalized.
                </p>
                <div className="feature-cards">
                    <div className="feature-card">
                        <h3>Conversational Memory</h3>
                        <p>Recalls past interactions for seamless, natural conversations.</p>
                    </div>
                    <div className="feature-card">
                        <h3>Personalized Learning</h3>
                        <p>Adapts to your preferences, tone, and frequent tasks.</p>
                    </div>
                    <div className="feature-card">
                        <h3>Multi-Format Support</h3>
                        <p>Handles text, voice, and potentially images or videos.</p>
                    </div>
                </div>
            </section>

            <section className="goals-section">
                <h2 className="section-title">Our Goals</h2>
                <ul className="goals-list">
                    <li>Deliver highly contextual and personalized responses.</li>
                    <li>Support a wide range of tasks, from reminders to complex queries.</li>
                    <li>Continuously improve through learning from user interactions.</li>
                    <li>Provide a fast, efficient, and reliable experience.</li>
                </ul>
            </section>

            <section className="why-best-section">
                <h2 className="section-title">Why Maya is the Best</h2>
                <p className="section-text">
                    Maya stands out by combining a powerful language model (Google Gemini Pro) with a sophisticated memory system and knowledge graph. This allows Maya to understand relationships, learn over time, and deliver responses that feel uniquely tailored to you. Our real-time backend and intuitive interface ensure a seamless experience, whether you're managing tasks or having a casual chat.
                </p>
            </section>

            <section className="tech-stack-section">
                <h2 className="section-title">Tech Stack</h2>
                <div className="tech-stack-grid">
                    <div className="tech-item">Google Gemini Pro: Language Engine</div>
                    <div className="tech-item">Redis +PostgreSQL: Memory Storage</div>
                    <div className="tech-item">Neo4j/ArangoDB: Knowledge Graph</div>
                    <div className="tech-item">FastAPI + WebSocket: Real-Time Backend</div>
                    <div className="tech-item">React: Intuitive Frontend</div>
                    <div className="tech-item">Celery: Task Management</div>
                    <div className="tech-item">ELK Stack: Performance Monitoring</div>
                </div>
            </section>

            <footer className="footer">
                <p>Built with ❤️ by the Maya Team</p>
                <p>Empowering you with AI that grows with you.</p>
                <div className="footer-links">
                    <a href="https://x.ai" target="_blank" rel="noopener noreferrer">About xAI</a>
                    <a href="https://x.ai/api" target="_blank" rel="noopener noreferrer">API Access</a>
                    <a href="https://help.x.com/en/using-x/x-premium" target="_blank" rel="noopener noreferrer">Premium Plans</a>
                </div>
            </footer>

            {showScrollTop && (
                <button onClick={scrollToTop} className="back-to-top">
                    ↑
                </button>
            )}
        </div>
    );
};
*/ 

// Enhanced route animations
const pageVariants = {
    initial: {
        opacity: 0,
        x: -20,
        scale: 0.98
    },
    in: {
        opacity: 1,
        x: 0,
        scale: 1
    },
    out: {
        opacity: 0,
        x: 20,
        scale: 0.98
    }
};

const pageTransition = {
    type: "tween",
    ease: "anticipate",
    duration: 0.4
};

// Animated route wrapper
const AnimatedRoute = ({ children }) => {
    return (
        <motion.div
            initial="initial"
            animate="in"
            exit="out"
            variants={pageVariants}
            transition={pageTransition}
            style={{ width: "100%", height: "100%" }}
        >
            {children}
        </motion.div>
    );
};

// Enhanced private route wrapper with loading state
const PrivateRoute = ({ children }) => {
    const [isLoading, setIsLoading] = useState(true);
    const [isAuthenticated, setIsAuthenticated] = useState(false);

    useEffect(() => {
        const checkAuth = async () => {
            try {
                const user = authService.getCurrentUser();
                setIsAuthenticated(!!user);
            } catch (error) {
                setIsAuthenticated(false);
            } finally {
                setIsLoading(false);
            }
        };

        checkAuth();
    }, []);

    if (isLoading) {
        return (
            <div className="auth-loading">
                <LoadingSpinner />
            </div>
        );
    }

    return isAuthenticated ? children : <Navigate to="/login" replace />;
};

// Enhanced navigation component
const Navigation = ({ currentUser, onLogout, setAuthModal }) => {
    const location = useLocation();
    const isAuthPage = ['/login', '/register'].includes(location.pathname);

    if (isAuthPage) return null; // Hide navigation on auth pages

    return (
        <motion.nav 
            className="navbar"
            initial={{ y: -60, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            transition={{ duration: 0.3 }}
        >
            <Link to={currentUser ? "/dashboard" : "/"} className="nav-brand">
                <motion.span
                    className="brand-text gradient-text"
                    whileHover={{ scale: 1.05 }}
                    whileTap={{ scale: 0.95 }}
                >
                    Maya
                </motion.span>
            </Link>
            <div className="nav-links">
                {currentUser ? (
                    <motion.button 
                        onClick={onLogout} 
                        className="nav-button logout-btn"
                        whileHover={{ scale: 1.02 }}
                        whileTap={{ scale: 0.98 }}
                    >
                        Logout
                    </motion.button>
                ) : (
                    <div className="nav-auth-links">
                        <button 
                            onClick={() => setAuthModal({ isOpen: true, mode: 'signin' })}
                            className="nav-link nav-button"
                        >
                            <motion.span
                                whileHover={{ scale: 1.05 }}
                                whileTap={{ scale: 0.95 }}
                            >
                                Login
                            </motion.span>
                        </button>
                        <button 
                            onClick={() => setAuthModal({ isOpen: true, mode: 'signup' })}
                            className="nav-link register-btn nav-button"
                        >
                            <motion.span
                                whileHover={{ scale: 1.05 }}
                                whileTap={{ scale: 0.95 }}
                            >
                                Register
                            </motion.span>
                        </button>
                    </div>
                )}
            </div>
        </motion.nav>
    );
};

function App() {
    const [currentUser, setCurrentUser] = useState(undefined);
    const [isInitializing, setIsInitializing] = useState(true);
    const [authModal, setAuthModal] = useState({ isOpen: false, mode: 'signin' });

    useEffect(() => {
        const initializeAuth = async () => {
            try {
                const user = authService.getCurrentUser();
                setCurrentUser(user);
            } catch (error) {
                console.error('Auth initialization error:', error);
            } finally {
                setIsInitializing(false);
            }
        };

        initializeAuth();

        // Listen for auth state changes
        const handleStorageChange = (e) => {
            if (e.key === 'user' || e.key === 'access_token') {
                const user = authService.getCurrentUser();
                setCurrentUser(user);
            }
        };

        window.addEventListener('storage', handleStorageChange);
        return () => window.removeEventListener('storage', handleStorageChange);
    }, []);

    const handleLogout = useCallback(() => {
        authService.logout();
        setCurrentUser(null);
        window.location.href = "/";
    }, []);

    const handleAuthSuccess = useCallback((user) => {
        setCurrentUser(user);
        setAuthModal({ isOpen: false, mode: 'signin' });
    }, []);

    const closeAuthModal = useCallback(() => {
        setAuthModal({ isOpen: false, mode: 'signin' });
    }, []);

    if (isInitializing) {
        return (
            <div className="app-initializing">
                <LoadingSpinner />
            </div>
        );
    }

    return (
        <Router>
            <div className="app-container">
                <main className="app-content">
                    <Suspense fallback={<LoadingSpinner />}>
                        <AnimatePresence mode="wait">
                            <Routes>
                                <Route 
                                    path="/" 
                                    element={
                                        <AnimatedRoute>
                                            <LandingPage />
                                        </AnimatedRoute>
                                    } 
                                />
                                <Route 
                                    path="/login" 
                                    element={
                                        <AnimatedRoute>
                                            <Login onAuthSuccess={handleAuthSuccess} />
                                        </AnimatedRoute>
                                    } 
                                />
                                <Route 
                                    path="/register" 
                                    element={
                                        <AnimatedRoute>
                                            <RegisterNew onAuthSuccess={handleAuthSuccess} />
                                        </AnimatedRoute>
                                    } 
                                />
                                <Route 
                                    path="/dashboard" 
                                    element={
                                        <PrivateRoute>
                                            <AnimatedRoute>
                                                <Dashboard />
                                            </AnimatedRoute>
                                        </PrivateRoute>
                                    } 
                                />
                                <Route path="*" element={<Navigate to="/" replace />} />
                            </Routes>
                        </AnimatePresence>
                    </Suspense>
                </main>

                {/* Auth Modal */}
                <AuthModal
                    isOpen={authModal.isOpen}
                    onClose={closeAuthModal}
                    onAuthSuccess={handleAuthSuccess}
                    initialMode={authModal.mode}
                />
            </div>
        </Router>
    );
}

export default App;