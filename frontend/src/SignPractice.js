// SignPractice.js - ULTRA SIMPLE (Training-Style Auto Recording)
// [CHECK] NO countdown gates
// [CHECK] NO handsDetected conditions
// [CHECK] AUTO start when button clicked
// [CHECK] 30 frames = DONE (exactly like training)
import React, { useState, useEffect, useRef } from 'react';
import './SignPractice.css';
import { saveNpy } from './saveNpy';

const SEQUENCE_LENGTH = 30;

export default function SignPractice({ word, onBack, user, token, refreshUserStats }) {
  const videoRef = useRef(null);
  const landmarksCanvasRef = useRef(null);
  const streamRef = useRef(null);

  const [cameraReady, setCameraReady] = useState(false);
  const [mediaPipeHands, setMediaPipeHands] = useState(null);
  const [handsDetected, setHandsDetected] = useState(false);
  
  const [isRecording, setIsRecording] = useState(false);
  const [isAnalysing, setIsAnalysing] = useState(false);
  const [feedback, setFeedback] = useState(null);
  const [frameCount, setFrameCount] = useState(0);
  
  // [FIRE] NEW: Data collection mode
  const [dataCollectionMode, setDataCollectionMode] = useState(false);
  const [recordingsSaved, setRecordingsSaved] = useState(0);

  // CRITICAL: Buffer WITHOUT any gates
  const landmarksBufferRef = useRef([]);
  const isRecordingRef = useRef(false);
  const frameCountRef = useRef(0);

  /* ==========  INITIALIZATION  ========== */
  useEffect(() => { 
    startCamera(); 
    return cleanup; 
  }, []);
  
  useEffect(() => {
    if (cameraReady) initMediaPipe();
  }, [cameraReady]);

  /* ----------  CAMERA  ---------- */
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

  const cleanup = () => {
    if (streamRef.current) streamRef.current.getTracks().forEach(t => t.stop());
    if (mediaPipeHands) mediaPipeHands.close();
  };

  /* ----------  MEDIAPIPE HANDS ONLY  ---------- */
  const initMediaPipe = async () => {
    console.log('[BULLSEYE] Loading MediaPipe Hands...');

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
    setMediaPipeHands(hands);

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

  /* ----------  onHandsResults - NO GATES  ---------- */
  const onHandsResults = (results) => {
    // Draw (always)
    drawLandmarks(results);

    // Update UI (non-blocking)
    setHandsDetected(results.multiHandLandmarks?.length > 0);

    // [FIRE] CRITICAL: Record if flag is true (NO OTHER CONDITIONS)
    if (isRecordingRef.current) {
      // Extract 126D landmarks
      const frameLandmarks = new Array(126).fill(0);
      
      if (results.multiHandLandmarks && results.multiHandLandmarks.length > 0) {
        results.multiHandLandmarks.forEach((hand, handIndex) => {
          if (handIndex > 1) return;
          
          hand.forEach((lm, i) => {
            const base = handIndex * 63 + i * 3;
            frameLandmarks[base] = lm.x;
            frameLandmarks[base + 1] = lm.y;
            frameLandmarks[base + 2] = lm.z;
          });
        });
      }

      // ALWAYS PUSH (no gates, no conditions)
      landmarksBufferRef.current.push(frameLandmarks);
      frameCountRef.current = landmarksBufferRef.current.length;
      setFrameCount(frameCountRef.current);
      
      console.log('[RED] [FRAME]', frameCountRef.current, '/ 30');

      // Stop at 30
      if (frameCountRef.current >= SEQUENCE_LENGTH) {
        console.log('[CHECK] 30 frames reached - stopping');
        stopRecording();
      }
    }
  };

  /* ----------  DRAW  ---------- */
  const drawLandmarks = (results) => {
    if (!landmarksCanvasRef.current) return;

    const ctx = landmarksCanvasRef.current.getContext('2d');
    const canvas = landmarksCanvasRef.current;
    
    ctx.fillStyle = '#000000';
    ctx.fillRect(0, 0, 640, 480);

    if (results.multiHandLandmarks) {
      results.multiHandLandmarks.forEach((landmarks) => {
        ctx.strokeStyle = '#00FF00';
        ctx.lineWidth = 2;
        
        const connections = [
          [0,1],[1,2],[2,3],[3,4],
          [0,5],[5,6],[6,7],[7,8],
          [0,9],[9,10],[10,11],[11,12],
          [0,13],[13,14],[14,15],[15,16],
          [0,17],[17,18],[18,19],[19,20]
        ];

        connections.forEach(([start, end]) => {
          const s = landmarks[start];
          const e = landmarks[end];
          ctx.beginPath();
          ctx.moveTo(s.x * 640, s.y * 480);
          ctx.lineTo(e.x * 640, e.y * 480);
          ctx.stroke();
        });

        ctx.fillStyle = '#00FF00';
        landmarks.forEach((lm) => {
          ctx.beginPath();
          ctx.arc(lm.x * 640, lm.y * 480, 5, 0, 2 * Math.PI);
          ctx.fill();
        });
      });
    }
  };

  /* ----------  RECORDING - ULTRA SIMPLE  ---------- */
  const startRecording = () => {
    console.log('[RED] [START] Recording started immediately');
    
    // Clear buffer
    landmarksBufferRef.current = [];
    frameCountRef.current = 0;
    setFrameCount(0);
    
    // Set flag (THIS IS THE ONLY GATE)
    isRecordingRef.current = true;
    setIsRecording(true);
    setFeedback(null);
  };

  const stopRecording = () => {
    console.log('[STOP_SIGN] [STOP] Recording stopped');
    
    // Clear flag
    isRecordingRef.current = false;
    setIsRecording(false);

    const landmarks = landmarksBufferRef.current;
    
    console.log('[CHECK] Landmarks captured:', landmarks.length);
    
    if (landmarks.length > 0) {
      console.log('[CHECK] Frame shape:', landmarks[0].length);
      console.log('[CHECK] Non-zero:', landmarks[0].filter(v => v !== 0).length);
    }

    // Validate
    if (landmarks.length < 3) {
      setFeedback({ 
        is_correct: false, 
        message: 'Not enough frames captured. Try again.' 
      });
      return;
    }

    // [FIRE] NEW: Check mode
    if (dataCollectionMode) {
      saveLandmarks(landmarks);
    } else {
      analyzeGesture(landmarks);
    }
  };

  /* ----------  SEND TO BACKEND  ---------- */
  const analyzeGesture = async (landmarks) => {
    setIsAnalysing(true);

    try {
      console.log('[OUTBOX_TRAY] Sending:', landmarks.length, 'frames');

      const res = await fetch(`${process.env.REACT_APP_BACKEND_URL || 'http://localhost:5000'}/api/predict_landmarks`, {
        method: 'POST',
        headers: { 
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({
          target_word: word,
          landmarks: landmarks
        })
      });

      if (!res.ok) throw new Error(`HTTP ${res.status}`);

      const data = await res.json();
      console.log('[INBOX_TRAY] Full backend response:');
      console.log('   Target:', data.target_word);
      console.log('   Is correct:', data.is_correct);
      console.log('   Target confidence:', (data.target_confidence * 100).toFixed(1) + '%');
      console.log('   Points:', data.points);
      console.log('   Message:', data.message);
      if (data.top_predictions?.length > 0) {
        console.log('   Top predictions:');
        data.top_predictions.forEach(p => {
          console.log(`      ${p.rank}. ${p.gesture}: ${(p.confidence * 100).toFixed(1)}%`);
        });
      }
      
      setFeedback(data);
      
      // Save to database
      if (user?.user_id) {
        try {
          await fetch(`${process.env.REACT_APP_BACKEND_URL || 'http://localhost:5000'}/api/attempt`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              user_id: user.user_id,
              target_word: word,
              is_correct: data.is_correct,
              target_confidence: data.target_confidence,
              points: data.points,
              message: data.message,
              top_predictions: data.top_predictions
            })
          });
          console.log('[CHECK] Attempt saved to database');
        } catch (e) {
          console.error('⚠️ Failed to save attempt:', e);
        }
      }
      
      if (data.is_correct && refreshUserStats) {
        refreshUserStats();
      }
    } catch (e) {
      console.error('[ERROR] Error:', e);
      setFeedback({ 
        is_correct: false, 
        message: 'Network error. Try again.' 
      });
    }
    
    setIsAnalysing(false);
  };

  /* ----------  SAVE LANDMARKS (Data Collection)  ---------- */
  const saveLandmarks = async (landmarks) => {
    setIsAnalysing(true);

    try {
      console.log('[FLOPPY_DISK] Saving landmarks to dataset:', word, landmarks.length, 'frames');

      const res = await fetch(`${process.env.REACT_APP_BACKEND_URL || 'http://localhost:5000'}/api/save_landmarks`, {
        method: 'POST',
        headers: { 
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({
          word: word,
          landmarks: landmarks
        })
      });

      if (!res.ok) throw new Error(`HTTP ${res.status}`);

      const data = await res.json();
      console.log('[CHECK] Saved:', data);
      
      setFeedback({
        is_correct: true,
        message: `[CHECK] Saved! (${landmarks.length} frames)`,
        file: data.file
      });
      
      setRecordingsSaved(c => c + 1);
    } catch (e) {
      console.error('[ERROR] Save error:', e);
      setFeedback({ 
        is_correct: false, 
        message: 'Failed to save. Check backend.' 
      });
    }
    
    setIsAnalysing(false);
  };
  const exportLandmarks = () => {
    if (landmarksBufferRef.current.length === 0) {
      alert('No landmarks. Record first.');
      return;
    }

    const filename = `${word}_${Date.now()}.npy`;
    try {
      saveNpy(landmarksBufferRef.current, filename);
      alert(`Exported ${landmarksBufferRef.current.length} frames`);
    } catch (e) {
      alert('Export failed');
    }
  };

  /* ----------  RENDER  ---------- */
  return (
    <div className="practice-page">
      <div className="practice-header">
        <button onClick={onBack} className="back-button">← Back</button>
        <div className="practice-title">
          <h1>Practice: {word}</h1>
          <div className="points-display">
            Level {user?.stats?.level || 1} • {user?.stats?.total_points || 0} points
          </div>
        </div>
        {/* [FIRE] NEW: Mode toggle */}
        <div className="mode-toggle">
          <label>
            <input 
              type="checkbox" 
              checked={dataCollectionMode}
              onChange={(e) => setDataCollectionMode(e.target.checked)}
            />
            [BAR_CHART] Data Collection Mode ({recordingsSaved} saved)
          </label>
        </div>
      </div>

      <div className="practice-container">
        {/* Reference Video */}
        <div className="video-panel">
          <h2>Reference Video</h2>
          <video 
            controls 
            className="reference-video"
            src={`${process.env.REACT_APP_BACKEND_URL || 'http://localhost:5000'}/videos/${word}.mp4`}
            onError={e => e.target.style.display = 'none'}
          />
        </div>

        {/* Practice Panel */}
        <div className="camera-panel">
          <h2>Your Practice</h2>
          
          {/* Status */}
          <div className="status-bar">
            <span className={`status-badge ${handsDetected ? 'active' : 'inactive'}`}>
              {handsDetected ? '✓ Hands' : 'No Hands'}
            </span>
            {isRecording && (
              <span className="recording-badge">
                [RED] Recording: {frameCount} / 30
              </span>
            )}
          </div>

          {/* Camera */}
          <div className="camera-container">
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
              className="landmarks-canvas"
            />

            {/* Controls */}
            <div className="camera-controls">
              {!isRecording && !isAnalysing && (
                <button 
                  onClick={startRecording}
                  className="record-button"
                >
                  [RED] Start Recording (Auto 30 frames)
                  {dataCollectionMode && ' - SAVE MODE'}
                </button>
              )}

              {isAnalysing && (
                <div className="analyzing">
                  <div className="spinner"></div>
                  <p>{dataCollectionMode ? 'Saving...' : 'Analyzing...'}</p>
                </div>
              )}

              <button 
                onClick={exportLandmarks}
                className="export-button"
                disabled={landmarksBufferRef.current.length === 0}
              >
                Export .npy
              </button>
            </div>

            {/* Feedback */}
            {feedback && (
              <div className={`feedback-panel ${feedback.is_correct ? 'success' : 'error'}`}>
                <h3>{feedback.is_correct ? '[CHECK] Correct!' : '[ERROR] Try Again'}</h3>
                <p>{feedback.message}</p>
                {feedback.predicted_word && (
                  <>
                    <p>Detected: {feedback.predicted_word} ({Math.round(feedback.top_prediction_confidence * 100)}%)</p>
                    {feedback.top_predictions && feedback.top_predictions.length > 0 && (
                      <div style={{ fontSize: '12px', color: '#666', marginTop: '10px', paddingTop: '10px', borderTop: '1px solid #ddd' }}>
                        <p style={{ margin: '5px 0', fontWeight: 'bold' }}>Top 5:</p>
                        {feedback.top_predictions.map(pred => (
                          <p key={pred.rank} style={{ margin: '2px 0' }}>
                            {pred.rank}. {pred.gesture}: {Math.round(pred.confidence * 100)}%
                          </p>
                        ))}
                      </div>
                    )}
                  </>
                )}
                {feedback.is_correct && feedback.points && (
                  <p className="points-earned">+{feedback.points} points</p>
                )}
                <button onClick={() => setFeedback(null)}>
                  {feedback.is_correct ? 'Next' : 'Retry'}
                </button>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Tips */}
      <div className="tips-section">
        <h3>Tips</h3>
        <ul>
          <li>Click "Start Recording" - it will auto-capture 30 frames</li>
          <li>Keep hands visible during recording</li>
          <li>Good lighting helps</li>
          <li>Match reference video movements</li>
        </ul>
      </div>
    </div>
  );
}