// ULTIMATE FIX: RAW landmarks only, backend handles ALL normalization
// This matches EXACT training pipeline

import React, { useState, useEffect, useRef, createContext, useContext } from 'react';
import './App.css';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || 'http://localhost:5000';
const API = `${BACKEND_URL}/api`;

// Auth Context (unchanged)
const AuthContext = createContext();
const useAuth = () => useContext(AuthContext);

const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [token, setToken] = useState(null);
  const [loading, setLoading] = useState(false);

  const login = async (email, password) => {
    try {
      const response = await fetch(`${API}/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password })
      });
      const data = await response.json();
      if (response.ok) {
        setToken(data.token);
        setUser(data.user);
        return { success: true };
      }
      return { success: false, error: data.error };
    } catch (error) {
      return { success: false, error: 'Network error' };
    }
  };

  const register = async (username, email, password) => {
    try {
      const response = await fetch(`${API}/auth/register`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, email, password })
      });
      const data = await response.json();
      if (response.ok) {
        setToken(data.token);
        setUser(data.user);
        return { success: true };
      }
      return { success: false, error: data.error };
    } catch (error) {
      return { success: false, error: 'Network error' };
    }
  };

  const logout = () => {
    setToken(null);
    setUser(null);
  };

  const refreshUserStats = async () => { };

  return (
    <AuthContext.Provider value={{ user, token, loading, login, register, logout, refreshUserStats, isAuthenticated: !!user }}>
      {children}
    </AuthContext.Provider>
  );
};

// Auth Page (unchanged)
const AuthPage = ({ onSuccess }) => {
  const [isLogin, setIsLogin] = useState(true);
  const [formData, setFormData] = useState({ username: '', email: '', password: '' });
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const { login, register } = useAuth();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');

    try {
      let result;
      if (isLogin) {
        result = await login(formData.email, formData.password);
      } else {
        result = await register(formData.username, formData.email, formData.password);
      }

      if (result.success) {
        onSuccess();
      } else {
        setError(result.error);
      }
    } catch (error) {
      setError('Something went wrong. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const handleChange = (e) => {
    setFormData(prev => ({ ...prev, [e.target.name]: e.target.value }));
  };

  return (
    <div className="auth-page">
      <div className="auth-container">
        <div style={{ textAlign: 'center', marginBottom: '2rem' }}>
          <h1>{isLogin ? 'Welcome Back' : 'Join GestureB'}</h1>
          <p>{isLogin ? 'Sign in to continue' : 'Start learning today'}</p>
        </div>

        <form onSubmit={handleSubmit}>
          {!isLogin && (
            <div style={{ marginBottom: '1rem' }}>
              <input type="text" name="username" value={formData.username} onChange={handleChange}
                placeholder="Username" style={{ width: '100%', padding: '12px', border: '1px solid #ddd', borderRadius: '8px', fontSize: '16px' }}
                required minLength={3} />
            </div>
          )}

          <div style={{ marginBottom: '1rem' }}>
            <input type="email" name="email" value={formData.email} onChange={handleChange}
              placeholder="Email" style={{ width: '100%', padding: '12px', border: '1px solid #ddd', borderRadius: '8px', fontSize: '16px' }}
              required />
          </div>

          <div style={{ marginBottom: '1rem' }}>
            <input type="password" name="password" value={formData.password} onChange={handleChange}
              placeholder="Password" style={{ width: '100%', padding: '12px', border: '1px solid #ddd', borderRadius: '8px', fontSize: '16px' }}
              required minLength={6} />
          </div>

          {error && (
            <div style={{ color: '#dc3545', marginBottom: '1rem', padding: '8px', background: '#f8d7da', borderRadius: '4px' }}>
              {error}
            </div>
          )}

          <button type="submit" disabled={loading}
            style={{ width: '100%', padding: '12px', background: '#18119e', color: 'white', border: 'none', borderRadius: '8px', fontSize: '16px', fontWeight: '600', cursor: loading ? 'not-allowed' : 'pointer', opacity: loading ? 0.7 : 1 }}>
            {loading ? 'Processing...' : (isLogin ? 'Sign In' : 'Create Account')}
          </button>
        </form>

        <div style={{ textAlign: 'center', marginTop: '1rem' }}>
          <span>{isLogin ? "Don't have an account?" : "Already have an account?"}</span>
          <button type="button" onClick={() => setIsLogin(!isLogin)}
            style={{ background: 'none', border: 'none', color: '#18119e', cursor: 'pointer', textDecoration: 'underline', marginLeft: '8px' }}>
            {isLogin ? 'Sign Up' : 'Sign In'}
          </button>
        </div>
      </div>
    </div>
  );
};

// Landing & Search Pages (unchanged - keeping code short)
const LandingPage = ({ onGetStarted }) => {
  const [showContent, setShowContent] = useState(false);
  const { user, logout } = useAuth();

  useEffect(() => {
    const timer = setTimeout(() => setShowContent(true), 1000);
    return () => clearTimeout(timer);
  }, []);

  return (
    <div className="landing-page">
      {user && (
        <div style={{ position: 'fixed', top: '1rem', right: '1rem', background: 'white', padding: '1rem', borderRadius: '12px', boxShadow: '0 4px 12px rgba(0,0,0,0.1)', display: 'flex', alignItems: 'center', gap: '1rem', zIndex: 1000 }}>
          <div>
            <div style={{ fontWeight: '600' }}>{user.username}</div>
            <div style={{ fontSize: '0.875rem', color: '#666' }}>Level {user.stats?.level || 1} • {user.stats?.total_points || 0} pts</div>
          </div>
          <button onClick={logout} style={{ background: '#dc3545', color: 'white', border: 'none', padding: '8px 12px', borderRadius: '6px', cursor: 'pointer' }}>Logout</button>
        </div>
      )}

      <div className="content">
        <div className="logo">
          <div className="logo-icon"></div>
          <div className="logo-shadow"></div>
        </div>

        {showContent && (
          <>
            <div className="heading">GestureB</div>
            <div className="subheading">Learn Sign Language with AI</div>
            <div className="description">
              <div className="description-text">Master sign language through interactive lessons and real-time AI feedback.</div>
            </div>
            <div className="action-buttons">
              <button className="action-primary" onClick={onGetStarted}>{user ? 'Continue Learning' : 'Get Started'}</button>
            </div>
          </>
        )}
      </div>
    </div>
  );
};

const SearchPage = ({ onSearch, onProfile }) => {
  const [searchTerm, setSearchTerm] = useState('');
  const [isSearching, setIsSearching] = useState(false);
  const [results, setResults] = useState([]);
  const [allWords, setAllWords] = useState([]);
  const { user, logout } = useAuth();

  useEffect(() => {
    fetchAllWords();
  }, []);

  const fetchAllWords = async () => {
    try {
      const response = await fetch(`${API}/words`);
      const data = await response.json();
      
      if (data.success) {
        setAllWords(data.words || []);
        setResults(data.words || []);
      }
    } catch (error) {
      console.error('Error fetching words:', error);
    }
  };

  const handleSearch = async (e) => {
    e.preventDefault();
    if (!searchTerm.trim()) {
      setResults(allWords);
      return;
    }

    setIsSearching(true);
    try {
      const response = await fetch(`${API}/search?q=${encodeURIComponent(searchTerm)}`);
      const data = await response.json();
      if (data.success) {
        setResults(data.results || []);
      }
    } catch (error) {
      console.error('Search error:', error);
    } finally {
      setIsSearching(false);
    }
  };

  return (
    <div className="search-page">
      <div style={{ position: 'fixed', top: '1rem', right: '1rem', background: 'white', padding: '1rem', borderRadius: '12px', boxShadow: '0 4px 12px rgba(0,0,0,0.1)', display: 'flex', alignItems: 'center', gap: '1rem', zIndex: 1000 }}>
        <div>
          <div style={{ fontWeight: '600' }}>{user.username}</div>
          <div style={{ fontSize: '0.875rem', color: '#666' }}>Level {user.stats?.level || 1} • {user.stats?.total_points || 0} pts</div>
        </div>
        <button onClick={logout} style={{ background: '#dc3545', color: 'white', border: 'none', padding: '8px 12px', borderRadius: '6px', cursor: 'pointer' }}>Logout</button>
      </div>

      <div style={{ maxWidth: '1200px', margin: '0 auto', padding: '2rem' }}>
        <h1 style={{ textAlign: 'center', marginBottom: '2rem' }}>Search Signs</h1>

        <form onSubmit={handleSearch} style={{ marginBottom: '2rem' }}>
          <div style={{ display: 'flex', gap: '1rem', maxWidth: '600px', margin: '0 auto' }}>
            <input
              type="text"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              placeholder="Search for a sign..."
              style={{ flex: 1, padding: '12px', border: '1px solid #ddd', borderRadius: '8px', fontSize: '16px' }}
            />
            <button type="submit" disabled={isSearching}
              style={{ padding: '12px 24px', background: '#18119e', color: 'white', border: 'none', borderRadius: '8px', cursor: 'pointer' }}>
              {isSearching ? 'Searching...' : 'Search'}
            </button>
          </div>
        </form>

        <div className="results-grid" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: '1rem' }}>
          {results.map((word, idx) => (
            <div key={idx} className="word-card"
              onClick={() => onSearch(word)}
              style={{ background: 'white', padding: '1.5rem', borderRadius: '12px', boxShadow: '0 2px 8px rgba(0,0,0,0.1)', cursor: 'pointer', transition: 'transform 0.2s', textAlign: 'center' }}>
              <h3 style={{ margin: '0 0 0.5rem 0' }}>{word}</h3>
              <button style={{ padding: '8px 16px', background: '#18119e', color: 'white', border: 'none', borderRadius: '6px', cursor: 'pointer' }}>
                Practice
              </button>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

// ========================================
// PRACTICE PAGE - ULTIMATE FIX
// Send PURE RAW landmarks, backend does ALL normalization
// ========================================
const PracticePage = ({ word, onBack }) => {
  const { user, token, refreshUserStats } = useAuth();

  const videoRef = useRef(null);
  const landmarksCanvasRef = useRef(null);
  const streamRef = useRef(null);
  const mediaPipeRef = useRef(null);

  // REF-based recording
  const isRecordingRef = useRef(false);
  const landmarksBufferRef = useRef([]);

  const [cameraReady, setCameraReady] = useState(false);
  const [handsDetected, setHandsDetected] = useState(false);
  const [detectionConf, setDetectionConf] = useState(0);
  const [countdown, setCountdown] = useState(0);
  const [isRecordingUI, setIsRecordingUI] = useState(false);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [feedback, setFeedback] = useState(null);

  const COUNTDOWN_TIME = 3;

  useEffect(() => {
    startCamera();
    return cleanup;
  }, []);

  useEffect(() => {
    if (cameraReady) {
      initMediaPipe();
    }
  }, [cameraReady]);

  const startCamera = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { width: 640, height: 480, frameRate: 30 }
      });
      streamRef.current = stream;
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        videoRef.current.onloadedmetadata = () => setCameraReady(true);
      }
    } catch (e) {
      console.error('[ERROR] Camera error:', e);
      alert('Cannot access camera');
    }
  };

  const initMediaPipe = async () => {
    console.log('[BULLSEYE] Loading MediaPipe Hands ONLY');
    
    const handsScript = document.createElement('script');
    handsScript.src = 'https://cdn.jsdelivr.net/npm/@mediapipe/hands@0.4/hands.min.js';
    handsScript.async = true;

    const cameraScript = document.createElement('script');
    cameraScript.src = 'https://cdn.jsdelivr.net/npm/@mediapipe/camera_utils@0.3/camera_utils.min.js';
    cameraScript.async = true;

    document.body.appendChild(handsScript);
    document.body.appendChild(cameraScript);

    await Promise.all([
      new Promise(resolve => handsScript.onload = resolve),
      new Promise(resolve => cameraScript.onload = resolve)
    ]);
    
    console.log('[CHECK] MediaPipe Hands loaded');

    const hands = new window.Hands({
      locateFile: file => `https://cdn.jsdelivr.net/npm/@mediapipe/hands@0.4/${file}`
    });

    hands.setOptions({
      maxNumHands: 2,
      modelComplexity: 1,
      minDetectionConfidence: 0.7,
      minTrackingConfidence: 0.5
    });

    hands.onResults(onHandsResults);
    mediaPipeRef.current = hands;

    const camera = new window.Camera(videoRef.current, {
      onFrame: async () => {
        await hands.send({ image: videoRef.current });
      },
      width: 640,
      height: 480
    });
    camera.start();
    
    console.log('[CHECK] Camera started');
  };

  const onHandsResults = (results) => {
    if (!landmarksCanvasRef.current) return;

    const ctx = landmarksCanvasRef.current.getContext('2d');
    const width = 640;
    const height = 480;

    ctx.fillStyle = '#000000';
    ctx.fillRect(0, 0, width, height);

    if (!results.multiHandLandmarks || results.multiHandLandmarks.length === 0) {
      setHandsDetected(false);
      setDetectionConf(0);
      return;
    }

    setHandsDetected(true);
    setDetectionConf(results.multiHandedness[0].score);

    // [FIRE] CRITICAL: Extract PURE RAW landmarks (NO normalization)
    const rawLandmarks = extractPureRawLandmarks(results);
    
    // CRITICAL: Check REF
    if (isRecordingRef.current) {
      landmarksBufferRef.current.push(rawLandmarks);
      console.log('[RED] [FRAME]', landmarksBufferRef.current.length);
    }

    // Draw
    const HAND_CONNECTIONS = [
      [0, 1], [1, 2], [2, 3], [3, 4],
      [0, 5], [5, 6], [6, 7], [7, 8],
      [5, 9], [9, 10], [10, 11], [11, 12],
      [9, 13], [13, 14], [14, 15], [15, 16],
      [13, 17], [17, 18], [18, 19], [19, 20],
      [0, 17]
    ];

    results.multiHandLandmarks.forEach(handLandmarks => {
      const points = handLandmarks.map(lm => ({
        x: lm.x * width,
        y: lm.y * height
      }));

      ctx.strokeStyle = '#00FF00';
      ctx.lineWidth = 2;
      HAND_CONNECTIONS.forEach(([start, end]) => {
        ctx.beginPath();
        ctx.moveTo(points[start].x, points[start].y);
        ctx.lineTo(points[end].x, points[end].y);
        ctx.stroke();
      });

      ctx.fillStyle = '#00FF00';
      points.forEach(pt => {
        ctx.beginPath();
        ctx.arc(pt.x, pt.y, 4, 0, 2 * Math.PI);
        ctx.fill();
      });
    });
  };

  /* [FIRE] PURE RAW LANDMARKS - NO NORMALIZATION WHATSOEVER */
  const extractPureRawLandmarks = (results) => {
    const leftHandLandmarks = new Array(63).fill(0);
    const rightHandLandmarks = new Array(63).fill(0);

    if (!results.multiHandLandmarks || !results.multiHandedness || results.multiHandLandmarks.length === 0) {
      return [...leftHandLandmarks, ...rightHandLandmarks];
    }

    results.multiHandLandmarks.forEach((handLandmarks, idx) => {
      const handedness = results.multiHandedness[idx];
      if (!handedness || !handedness.classification || handedness.classification.length === 0) {
        return;
      }
      
      const handLabel = handedness.classification[0].label;
      const landmarks = [];
      
      // [FIRE] PURE RAW - Direct MediaPipe output (x, y, z)
      handLandmarks.forEach(lm => {
        landmarks.push(lm.x, lm.y, lm.z);
      });

      if (handLabel === 'Left') {
        leftHandLandmarks.splice(0, landmarks.length, ...landmarks);
      } else {
        rightHandLandmarks.splice(0, landmarks.length, ...landmarks);
      }
    });

    return [...leftHandLandmarks, ...rightHandLandmarks];
  };

  const cleanup = () => {
    if (streamRef.current) {
      streamRef.current.getTracks().forEach(t => t.stop());
    }
    if (mediaPipeRef.current) {
      mediaPipeRef.current.close();
    }
  };

  const startRecording = () => {
    if (!handsDetected) {
      alert('Please show your hands first');
      return;
    }

    setFeedback(null);
    setCountdown(COUNTDOWN_TIME);

    const countdownInterval = setInterval(() => {
      setCountdown(c => {
        if (c === 1) {
          clearInterval(countdownInterval);
          setTimeout(() => startActualRecording(), 100);
          return 0;
        }
        return c - 1;
      });
    }, 1000);
  };

  const startActualRecording = () => {
    console.log('[RED] [START] Recording...');
    
    landmarksBufferRef.current = [];
    isRecordingRef.current = true;
    setIsRecordingUI(true);

    // 5 seconds for 30+ frames
    setTimeout(() => {
      isRecordingRef.current = false;
      setIsRecordingUI(false);

      const landmarks = landmarksBufferRef.current;
      console.log('[CHECK] Landmarks captured:', landmarks.length);

      if (landmarks.length > 0) {
        console.log('[CHECK] Landmarks captured:', landmarks.length, 'frames x', landmarks[0].length, 'features');
      }

      analyzeGesture(landmarks);
    }, 5000);
  };

  const analyzeGesture = async (landmarks) => {
    // [FIRE] CRITICAL FIX 1: Validate word prop BEFORE sending
    if (!word || word === 'undefined') {
      console.error('[ERROR] ERROR: word prop is undefined!');
      setFeedback({
        is_correct: false,
        message: 'Error: No target word specified',
        confidence: 0
      });
      setIsAnalyzing(false);
      return;
    }

    if (!landmarks || landmarks.length < 3) {
      setFeedback({
        is_correct: false,
        message: 'Not enough frames. Keep hands visible.',
        confidence: 0
      });
      return;
    }

    setIsAnalyzing(true);

    try {
      console.log('[OUTBOX_TRAY] Sending to backend:');
      console.log('   Target word:', word);  // Should NOT be undefined!
      console.log('   Landmarks:', landmarks.length, 'frames');
      
      const response = await fetch(`${API}/predict_landmarks`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({
          target_word: word,  // This MUST be valid string
          landmarks: landmarks  // PURE RAW - backend will normalize
        })
      });

      if (!response.ok) {
        throw new Error(`Server error: ${response.status}`);
      }

      const result = await response.json();
      // Log full response with new verification logic
      console.log('[CHECK] Backend response received:');
      console.log('   Target word:', result.target_word);
      console.log('   Is correct:', result.is_correct);
      console.log('   Target confidence:', (result.target_confidence * 100).toFixed(1) + '%');
      console.log('   Points awarded:', result.points);
      console.log('   Message:', result.message);
      if (result.top_predictions && result.top_predictions.length > 0) {
        console.log('   Top predictions:');
        result.top_predictions.forEach(pred => {
          console.log(`      ${pred.rank}. ${pred.gesture}: ${(pred.confidence * 100).toFixed(1)}%`);
        });
      }
      console.log('   Debug - Target rank:', result.debug?.target_rank);
      
      setFeedback(result);

      if (result.is_correct && refreshUserStats) {
        refreshUserStats();
      }
    } catch (error) {
      console.error('[ERROR] Prediction error:', error);
      setFeedback({
        is_correct: false,
        message: 'Network error.',
        confidence: 0
      });
    } finally {
      setIsAnalyzing(false);
    }
  };

  const resetPractice = () => {
    setFeedback(null);
  };

  return (
    <div className="practice-page">
      <div className="practice-header">
        <div className="practice-title">
          <h1>Practice: {word}</h1>
          <div className="points-display">
            Level {user?.stats?.level || 1} • {user?.stats?.total_points || 0} points
          </div>
        </div>
      </div>

      <div className="practice-container">
        <div className="video-panel">
          <h2>Reference Video</h2>
          <video
            controls
            className="reference-video"
            src={`${BACKEND_URL}/videos/${word.toLowerCase()}.mp4`}
            onError={(e) => e.target.style.display = 'none'}
          />
        </div>

        <div className="camera-panel">
          <h2>Your Practice</h2>

          <div className="status-bar" style={{ display: 'flex', gap: '1rem', justifyContent: 'center', marginBottom: '1rem' }}>
            <span style={{
              padding: '8px 16px',
              borderRadius: '20px',
              fontSize: '14px',
              fontWeight: '600',
              background: handsDetected ? '#4caf50' : '#f44336',
              color: 'white'
            }}>
              {handsDetected ? '✓ Hands' : 'No Hands'}
            </span>
            <span style={{
              padding: '8px 16px',
              borderRadius: '20px',
              fontSize: '14px',
              fontWeight: '600',
              background: 'rgba(255,255,255,0.2)',
              color: 'white'
            }}>
              {Math.round(detectionConf * 100)}%
            </span>
          </div>

          <div className="camera-container" style={{ position: 'relative' }}>
            <video
              ref={videoRef}
              autoPlay
              muted
              playsInline
              style={{ display: 'none' }}
            />

            <canvas
              ref={landmarksCanvasRef}
              width={640}
              height={480}
              style={{
                width: '100%',
                maxWidth: '640px',
                borderRadius: '12px',
                background: '#000000',
                display: 'block',
                margin: '0 auto'
              }}
            />

            {countdown > 0 && (
              <div style={{
                position: 'absolute',
                top: 0,
                left: 0,
                right: 0,
                bottom: 0,
                background: 'rgba(0,0,0,0.8)',
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                justifyContent: 'center',
                borderRadius: '12px',
                zIndex: 10
              }}>
                <div style={{ fontSize: '120px', fontWeight: 'bold', color: '#4caf50' }}>
                  {countdown}
                </div>
                <p style={{ color: 'white', fontSize: '24px', marginTop: '20px' }}>
                  Get Ready
                </p>
              </div>
            )}

            <div className="camera-controls" style={{ marginTop: '1rem', textAlign: 'center' }}>
              {!isRecordingUI && !isAnalyzing && (
                <button
                  onClick={startRecording}
                  disabled={!cameraReady || !handsDetected}
                  style={{
                    padding: '15px 40px',
                    fontSize: '18px',
                    fontWeight: '600',
                    border: 'none',
                    borderRadius: '8px',
                    cursor: (cameraReady && handsDetected) ? 'pointer' : 'not-allowed',
                    background: (cameraReady && handsDetected) ? '#4caf50' : '#ccc',
                    color: 'white',
                    opacity: (cameraReady && handsDetected) ? 1 : 0.6
                  }}
                >
                  Start Recording
                </button>
              )}

              {isRecordingUI && (
                <div style={{ textAlign: 'center', color: 'white' }}>
                  <div style={{ fontSize: '24px', fontWeight: 'bold', color: '#f44336' }}>
                    [RED] Recording... ({landmarksBufferRef.current.length} frames)
                  </div>
                </div>
              )}

              {isAnalyzing && (
                <div style={{ textAlign: 'center', color: 'white' }}>
                  <div className="spinner" style={{
                    border: '4px solid rgba(255,255,255,0.3)',
                    borderTop: '4px solid white',
                    borderRadius: '50%',
                    width: '40px',
                    height: '40px',
                    animation: 'spin 1s linear infinite',
                    margin: '0 auto 10px auto'
                  }}></div>
                  <p>Analyzing...</p>
                </div>
              )}
            </div>

            {feedback && (
              <div style={{
                position: 'absolute',
                top: '50%',
                left: '50%',
                transform: 'translate(-50%, -50%)',
                background: 'white',
                padding: '30px',
                borderRadius: '16px',
                textAlign: 'center',
                boxShadow: '0 10px 40px rgba(0,0,0,0.3)',
                zIndex: 20,
                minWidth: '300px',
                border: feedback.is_correct ? '4px solid #4caf50' : '4px solid #f44336'
              }}>
                <h3 style={{
                  margin: '0 0 15px 0',
                  fontSize: '28px',
                  color: feedback.is_correct ? '#4caf50' : '#f44336'
                }}>
                  {feedback.is_correct ? '[CHECK] Correct' : '[ERROR] Try Again'}
                </h3>

                <p style={{ margin: '10px 0', color: '#333', fontSize: '16px' }}>
                  {feedback.message}
                </p>

                {feedback.is_correct && feedback.points && (
                  <p style={{
                    fontSize: '24px',
                    fontWeight: 'bold',
                    color: '#4caf50',
                    margin: '15px 0'
                  }}>
                    +{feedback.points} Points
                  </p>
                )}

                {feedback.predicted_word && !feedback.is_correct && (
                  <>
                    <p style={{ fontSize: '14px', color: '#666', marginTop: '10px' }}>
                      Detected: "{feedback.predicted_word}"
                    </p>
                    {feedback.top_predictions && feedback.top_predictions.length > 0 && (
                      <div style={{ fontSize: '12px', color: '#999', marginTop: '10px', paddingTop: '10px', borderTop: '1px solid #eee' }}>
                        <p style={{ margin: '5px 0', fontWeight: 'bold' }}>Top 5 predictions:</p>
                        {feedback.top_predictions.map(pred => (
                          <p key={pred.rank} style={{ margin: '2px 0' }}>
                            {pred.rank}. {pred.gesture}: {(pred.confidence * 100).toFixed(1)}%
                          </p>
                        ))}
                      </div>
                    )}
                  </>
                )}

                <button
                  onClick={resetPractice}
                  style={{
                    marginTop: '20px',
                    padding: '12px 30px',
                    background: '#18119e',
                    color: 'white',
                    border: 'none',
                    borderRadius: '8px',
                    fontSize: '16px',
                    fontWeight: '600',
                    cursor: 'pointer'
                  }}
                >
                  {feedback.is_correct ? 'Practice More' : 'Try Again'}
                </button>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

// User Profile
const UserProfile = ({ onBack }) => {
  const { user, logout } = useAuth();

  return (
    <div style={{ minHeight: '100vh', background: '#f8f9fa', padding: '2rem' }}>
      <div style={{ maxWidth: '800px', margin: '0 auto' }}>
        <div style={{ textAlign: 'center', marginTop: '2rem' }}>
          <h1>Profile</h1>
          <p>Username: {user?.username}</p>
          <p>Email: {user?.email}</p>
          <button onClick={logout} style={{
            background: '#dc3545',
            color: 'white',
            border: 'none',
            padding: '12px 24px',
            borderRadius: '6px',
            cursor: 'pointer',
            marginTop: '1rem'
          }}>
            Logout
          </button>
        </div>
      </div>
    </div>
  );
};

// Main App
function App() {
  const [currentPage, setCurrentPage] = useState('landing');
  const [currentWord, setCurrentWord] = useState('');

  return (
    <AuthProvider>
      <div className="App">
        <AuthWrapper
          currentPage={currentPage}
          currentWord={currentWord}
          setCurrentPage={setCurrentPage}
          setCurrentWord={setCurrentWord}
        />
      </div>
    </AuthProvider>
  );
}

// Auth Wrapper
const AuthWrapper = ({ currentPage, currentWord, setCurrentPage, setCurrentWord }) => {
  const { user, loading, isAuthenticated } = useAuth();

  const handleGetStarted = () => {
    if (isAuthenticated) {
      setCurrentPage('search');
    } else {
      setCurrentPage('auth');
    }
  };

  const handleAuthSuccess = () => setCurrentPage('search');
  const handleSearch = (word) => {
    setCurrentWord(word);
    setCurrentPage('practice');
  };
  const handleBackToSearch = () => {
    setCurrentPage('search');
    setCurrentWord('');
  };
  const handleProfile = () => setCurrentPage('profile');
  const handleBackFromProfile = () => setCurrentPage('search');

  if (loading) {
    return (
      <div style={{
        display: 'flex',
        justifyContent: 'center',
        alignItems: 'center',
        minHeight: '100vh',
        background: '#f8f9fa'
      }}>
        <div style={{ textAlign: 'center' }}>
          <h2>GestureB</h2>
          <p>Loading...</p>
        </div>
      </div>
    );
  }

  switch (currentPage) {
    case 'auth':
      return <AuthPage onSuccess={handleAuthSuccess} />;
    case 'search':
      return isAuthenticated ? <SearchPage onSearch={handleSearch} onProfile={handleProfile} /> : <LandingPage onGetStarted={handleGetStarted} />;
    case 'practice':
      return isAuthenticated ? <PracticePage word={currentWord} onBack={handleBackToSearch} /> : <LandingPage onGetStarted={handleGetStarted} />;
    case 'profile':
      return isAuthenticated ? <UserProfile onBack={handleBackFromProfile} /> : <LandingPage onGetStarted={handleGetStarted} />;
    case 'landing':
    default:
      return <LandingPage onGetStarted={handleGetStarted} />;
  }
};

export default App;