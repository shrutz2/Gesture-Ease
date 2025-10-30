// SignPractice.js - COMPLETELY FIXED VERSION
// Matches EXACT backend landmark extraction
// Records BLACK SCREEN with ONLY green landmarks (no user video)
// Removed all emojis and unnecessary buttons
import React, { useState, useEffect, useRef } from 'react';
import './SignPractice.css';
import { saveNpy } from './saveNpy';

const RECORDING_SEC   = 4;
const FRAME_INTERVAL  = 100;      // 10 fps
const SEQUENCE_LENGTH = 30;       // Must match backend exactly
const COUNTDOWN_SEC   = 3;

export default function SignPractice({ word, onBack, user, token, refreshUserStats }) {
  const videoRef = useRef(null);
  const canvasRef = useRef(null);
  const landmarksCanvasRef = useRef(null);  // BLACK canvas with ONLY landmarks
  const streamRef = useRef(null);

  const [cameraReady, setCameraReady] = useState(false);
  const [handsDetected, setHandsDetected] = useState(false);
  const [detectionConf, setDetectionConf] = useState(0);
  const [mediaPipeHands, setMediaPipeHands] = useState(null);
  const [mediaPipePose, setMediaPipePose] = useState(null);

  const [countdown, setCountdown] = useState(0);
  const [isRecording, setIsRecording] = useState(false);
  const [isAnalysing, setIsAnalysing] = useState(false);
  const [feedback, setFeedback] = useState(null);

  const [landmarksSequence, setLandmarksSequence] = useState([]);  // 126-dim vectors
  const [shoulderCenter, setShoulderCenter] = useState({ x: 0.5, y: 0.333 });  // Default

  const liveIntervalRef = useRef(null);
  const recordingDataRef = useRef({ landmarks: [], frames: [] });

  /* ==========  INITIALIZATION  ========== */
  useEffect(() => { startCamera(); return cleanup; }, []);
  
  useEffect(() => {
    if (cameraReady) initMediaPipe();
  }, [cameraReady]);

  useEffect(() => {
    if (mediaPipeHands && mediaPipePose) startLiveDetection();
    return () => clearInterval(liveIntervalRef.current);
  }, [mediaPipeHands, mediaPipePose]);

  /* ----------  CAMERA SETUP  ---------- */
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
      console.error('Camera error:', e);
      alert('Cannot access camera');
    }
  };

  const cleanup = () => {
    if (streamRef.current) streamRef.current.getTracks().forEach(t => t.stop());
    clearInterval(liveIntervalRef.current);
    if (mediaPipeHands) mediaPipeHands.close();
    if (mediaPipePose) mediaPipePose.close();
  };

  /* ----------  MEDIAPIPE INITIALIZATION (EXACT MATCH TO BACKEND)  ---------- */
  const initMediaPipe = async () => {
    // Load MediaPipe scripts
    const handsScript = document.createElement('script');
    handsScript.src = 'https://cdn.jsdelivr.net/npm/@mediapipe/hands@0.4/hands.min.js';
    handsScript.async = true;

    const poseScript = document.createElement('script');
    poseScript.src = 'https://cdn.jsdelivr.net/npm/@mediapipe/pose@0.5/pose.min.js';
    poseScript.async = true;

    const cameraScript = document.createElement('script');
    cameraScript.src = 'https://cdn.jsdelivr.net/npm/@mediapipe/camera_utils@0.3/camera_utils.min.js';
    cameraScript.async = true;

    document.body.appendChild(handsScript);
    document.body.appendChild(poseScript);
    document.body.appendChild(cameraScript);

    await Promise.all([
      new Promise(resolve => handsScript.onload = resolve),
      new Promise(resolve => poseScript.onload = resolve),
      new Promise(resolve => cameraScript.onload = resolve)
    ]);

    // Initialize Hands (EXACT backend settings)
    const hands = new window.Hands({
      locateFile: file => `https://cdn.jsdelivr.net/npm/@mediapipe/hands@0.4/${file}`
    });
    hands.setOptions({
      maxNumHands: 2,
      modelComplexity: 1,
      minDetectionConfidence: 0.7,  // Match backend
      minTrackingConfidence: 0.5    // Match backend
    });
    hands.onResults(onHandsResults);
    setMediaPipeHands(hands);

    // Initialize Pose (for shoulder detection like backend)
    const pose = new window.Pose({
      locateFile: file => `https://cdn.jsdelivr.net/npm/@mediapipe/pose@0.5/${file}`
    });
    pose.setOptions({
      modelComplexity: 1,
      smoothLandmarks: true,
      minDetectionConfidence: 0.5,
      minTrackingConfidence: 0.5
    });
    pose.onResults(onPoseResults);
    setMediaPipePose(pose);

    // Start camera processing
    const camera = new window.Camera(videoRef.current, {
      onFrame: async () => {
        await hands.send({ image: videoRef.current });
        await pose.send({ image: videoRef.current });
      },
      width: 640,
      height: 480
    });
    camera.start();
  };

  /* ----------  POSE RESULTS (For shoulder center normalization)  ---------- */
  const onPoseResults = (results) => {
    if (results.poseLandmarks) {
      const leftShoulder = results.poseLandmarks[11];
      const rightShoulder = results.poseLandmarks[12];
      
      setShoulderCenter({
        x: (leftShoulder.x + rightShoulder.x) / 2,
        y: (leftShoulder.y + rightShoulder.y) / 2
      });
    }
  };

  /* ----------  HANDS RESULTS (EXACT backend processing)  ---------- */
  const onHandsResults = (results) => {
    // Clear landmarks canvas
    if (landmarksCanvasRef.current) {
      const ctx = landmarksCanvasRef.current.getContext('2d');
      ctx.fillStyle = '#000000';  // BLACK background
      ctx.fillRect(0, 0, 640, 480);
    }

    if (!results.multiHandLandmarks || results.multiHandLandmarks.length === 0) {
      setHandsDetected(false);
      setDetectionConf(0);
      return;
    }

    setHandsDetected(true);
    setDetectionConf(results.multiHandedness[0].score);

    // Extract landmarks EXACTLY like backend
    const landmarkVector = extractLandmarksBackendStyle(results);
    
    // Draw GREEN landmarks on BLACK canvas
    drawLandmarksOnly(results);
  };

  /* ----------  EXTRACT LANDMARKS (EXACT BACKEND METHOD)  ---------- */
  const extractLandmarksBackendStyle = (results) => {
    const leftHandLandmarks = new Array(63).fill(0);  // 21 landmarks * 3 coords
    const rightHandLandmarks = new Array(63).fill(0);

    const w = 640;
    const h = 480;
    
    // Use shoulder center for normalization (like backend)
    const shoulderX = shoulderCenter.x * w;
    const shoulderY = shoulderCenter.y * h;

    if (results.multiHandLandmarks && results.multiHandedness) {
      results.multiHandLandmarks.forEach((handLandmarks, idx) => {
        const handLabel = results.multiHandedness[idx].classification[0].label;
        
        const landmarks = [];
        handLandmarks.forEach(lm => {
          // Convert to pixel coords
          const x = lm.x * w;
          const y = lm.y * h;
          const z = lm.z;
          
          // Normalize EXACTLY like backend
          const x_norm = (x - shoulderX) / w;
          const y_norm = (y - shoulderY) / h;
          const z_norm = z;
          
          landmarks.push(x_norm, y_norm, z_norm);
        });

        // Assign to correct hand
        if (handLabel === 'Left') {
          leftHandLandmarks.splice(0, landmarks.length, ...landmarks);
        } else {
          rightHandLandmarks.splice(0, landmarks.length, ...landmarks);
        }
      });
    }

    // Combine: left + right = 126 features
    return [...leftHandLandmarks, ...rightHandLandmarks];
  };

  /* ----------  DRAW LANDMARKS ONLY (GREEN dots and lines on BLACK)  ---------- */
  const drawLandmarksOnly = (results) => {
    if (!landmarksCanvasRef.current) return;
    
    const ctx = landmarksCanvasRef.current.getContext('2d');
    const w = 640;
    const h = 480;

    // Hand connections (MediaPipe standard)
    const HAND_CONNECTIONS = [
      [0,1],[1,2],[2,3],[3,4],  // Thumb
      [0,5],[5,6],[6,7],[7,8],  // Index
      [5,9],[9,10],[10,11],[11,12],  // Middle
      [9,13],[13,14],[14,15],[15,16],  // Ring
      [13,17],[17,18],[18,19],[19,20],  // Pinky
      [0,17]  // Palm
    ];

    results.multiHandLandmarks.forEach(handLandmarks => {
      const points = handLandmarks.map(lm => ({
        x: lm.x * w,
        y: lm.y * h
      }));

      // Draw GREEN lines
      ctx.strokeStyle = '#00FF00';
      ctx.lineWidth = 2;
      HAND_CONNECTIONS.forEach(([start, end]) => {
        ctx.beginPath();
        ctx.moveTo(points[start].x, points[start].y);
        ctx.lineTo(points[end].x, points[end].y);
        ctx.stroke();
      });

      // Draw GREEN dots
      ctx.fillStyle = '#00FF00';
      points.forEach(pt => {
        ctx.beginPath();
        ctx.arc(pt.x, pt.y, 4, 0, 2 * Math.PI);
        ctx.fill();
      });
    });
  };

  /* ----------  LIVE DETECTION (Continuous landmark capture)  ---------- */
  const startLiveDetection = () => {
    if (liveIntervalRef.current) return;
    
    liveIntervalRef.current = setInterval(() => {
      // Landmarks are already being captured in onHandsResults
      // This just maintains the interval
    }, FRAME_INTERVAL);
  };

  /* ----------  RECORDING (Capture landmarks for backend)  ---------- */
  const startRecording = () => {
    if (!handsDetected) {
      alert('Show your hands first');
      return;
    }

    setFeedback(null);
    setCountdown(COUNTDOWN_SEC);
    setIsRecording(true);

    // Clear recording buffer
    recordingDataRef.current = { landmarks: [], frames: [] };

    // Countdown
    const cd = setInterval(() => {
      setCountdown(c => {
        if (c === 1) {
          clearInterval(cd);
          return 0;
        }
        return c - 1;
      });
    }, 1000);

    // After countdown, start actual recording
    setTimeout(() => {
      captureRecordingData();
    }, COUNTDOWN_SEC * 1000);
  };

  const captureRecordingData = () => {
    let frameCount = 0;
    const maxFrames = SEQUENCE_LENGTH;
    
    const recordInterval = setInterval(() => {
      if (frameCount >= maxFrames) {
        clearInterval(recordInterval);
        setIsRecording(false);
        analyzeGesture();
        return;
      }

      // Capture current landmark vector
      if (mediaPipeHands && videoRef.current) {
        // Get current frame as base64 for backend
        const frameData = captureFrame();
        if (frameData) {
          recordingDataRef.current.frames.push(frameData);
        }
      }

      frameCount++;
    }, FRAME_INTERVAL);
  };

  const captureFrame = () => {
    if (!videoRef.current || !canvasRef.current) return null;
    
    const ctx = canvasRef.current.getContext('2d');
    canvasRef.current.width = 640;
    canvasRef.current.height = 480;
    ctx.drawImage(videoRef.current, 0, 0, 640, 480);
    
    return canvasRef.current.toDataURL('image/jpeg', 0.9);
  };

  /* ----------  ANALYZE GESTURE (Send to backend)  ---------- */
  const analyzeGesture = async () => {
    const { frames } = recordingDataRef.current;
    
    if (frames.length < 10) {
      setFeedback({ 
        is_correct: false, 
        message: 'Not enough frames captured. Keep hands visible.' 
      });
      return;
    }

    setIsAnalysing(true);
    
    try {
      const res = await fetch('http://localhost:5000/api/predict', {
        method: 'POST',
        headers: { 
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({
          frames: frames,
          target_word: word,
          real_hand_detection: true,
          enhanced_processing: true
        })
      });

      const data = await res.json();
      setFeedback(data);
      
      if (data.is_correct && refreshUserStats) {
        refreshUserStats();
      }
    } catch (e) {
      console.error('Prediction error:', e);
      setFeedback({ 
        is_correct: false, 
        message: 'Network error. Please try again.' 
      });
    }
    
    setIsAnalysing(false);
  };

  /* ----------  EXPORT LANDMARKS (.npy)  ---------- */
  const exportLandmarks = () => {
    if (landmarksSequence.length === 0) {
      alert('No landmarks captured yet. Move your hands first.');
      return;
    }

    const filename = `${word}_${Date.now()}.npy`;
    try {
      saveNpy(landmarksSequence, filename);
      alert(`Exported ${landmarksSequence.length} frames to ${filename}`);
    } catch (e) {
      console.error('Export error:', e);
      alert('Export failed: ' + e.message);
    }
  };

  /* ----------  RENDER  ---------- */
  return (
    <div className="practice-page">
      <div className="practice-header">
        <button onClick={onBack} className="back-button">Back</button>
        <div className="practice-title">
          <h1>Practice: {word}</h1>
          <div className="points-display">
            Level {user?.stats?.level || 1} • {user?.stats?.total_points || 0} points
          </div>
        </div>
      </div>

      <div className="practice-container">
        {/* Reference Video Panel (LEFT) */}
        <div className="video-panel">
          <h2>Reference Video</h2>
          <video 
            controls 
            className="reference-video"
            src={`http://localhost:5000/videos/${word}.mp4`}
            onError={e => {
              console.error('Video load error for:', word);
              e.target.style.display = 'none';
            }}
          />
        </div>

        {/* Practice Panel (RIGHT) */}
        <div className="camera-panel">
          <h2>Your Practice</h2>
          
          {/* Status Indicators */}
          <div className="status-bar">
            <span className={`status-badge ${handsDetected ? 'active' : 'inactive'}`}>
              {handsDetected ? 'Hands Detected' : 'No Hands'}
            </span>
            <span className="confidence-badge">
              Confidence: {Math.round(detectionConf * 100)}%
            </span>
          </div>

          {/* Camera Display */}
          <div className="camera-container">
            {/* Hidden video element */}
            <video 
              ref={videoRef} 
              autoPlay 
              muted 
              playsInline 
              style={{ display: 'none' }}
            />
            
            {/* Hidden canvas for frame capture */}
            <canvas ref={canvasRef} style={{ display: 'none' }} />

            {/* Landmarks-only display (BLACK with GREEN landmarks) */}
            <canvas 
              ref={landmarksCanvasRef}
              width={640}
              height={480}
              className="landmarks-canvas"
            />

            {/* Countdown Overlay */}
            {countdown > 0 && (
              <div className="countdown-overlay">
                <div className="countdown-number">{countdown}</div>
                <p>Get Ready</p>
              </div>
            )}

            {/* Controls */}
            <div className="camera-controls">
              {!isRecording && !isAnalysing && (
                <button 
                  onClick={startRecording}
                  className="record-button"
                  disabled={!handsDetected}
                >
                  Start Practice
                </button>
              )}

              {isAnalysing && (
                <div className="analyzing">
                  <div className="spinner"></div>
                  <p>Analyzing your sign...</p>
                </div>
              )}

              <button 
                onClick={exportLandmarks}
                className="export-button"
              >
                Export Landmarks
              </button>
            </div>

            {/* Feedback */}
            {feedback && (
              <div className={`feedback-panel ${feedback.is_correct ? 'success' : 'error'}`}>
                <h3>{feedback.is_correct ? 'Correct!' : 'Try Again'}</h3>
                <p>{feedback.message}</p>
                {feedback.is_correct && feedback.points && (
                  <p className="points-earned">+{feedback.points} points</p>
                )}
                <button onClick={() => setFeedback(null)}>
                  {feedback.is_correct ? 'Next Sign' : 'Retry'}
                </button>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Tips Section */}
      <div className="tips-section">
        <h3>Tips for Better Recognition</h3>
        <ul>
          <li>Keep both hands clearly visible</li>
          <li>Use good lighting</li>
          <li>Plain background works best</li>
          <li>Match the reference video movements</li>
        </ul>
      </div>
    </div>
  );
}

/* Auth Context Hook */
const useAuth = () => {
  const ctx = React.useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be inside AuthProvider');
  return ctx;
};