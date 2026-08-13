"""
Gesture Recognition Backend API
Flask-based REST API for real-time sign language recognition using BiLSTM model.
Handles landmark extraction, sequence normalization, and gesture prediction.
Database: MySQL with SQLAlchemy ORM
"""

import cv2
# MediaPipe is only used by the optional raw-frame endpoints; the main flow
# receives landmarks from the browser. Import it defensively so a missing or
# partially-installed mediapipe can't stop the whole server from booting.
try:
    import mediapipe as mp
    if not hasattr(mp, 'solutions'):
        mp = None
except Exception:
    mp = None
import numpy as np
import tensorflow as tf
from flask import Flask, request, jsonify, send_from_directory
import base64
import json
import pickle
import logging
import os
import traceback
from pathlib import Path
from datetime import datetime
from collections import deque
import warnings
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

warnings.filterwarnings('ignore')

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Import database
from database import db, User, UserProgress, GestureAttempt, LeaderboardEntry
from auth import generate_token, verify_token, token_required

# Model Configuration
SEQUENCE_LENGTH = 30  # Frames per gesture sequence
FEATURE_DIM = 126     # 21 landmarks Ã— 2 hands Ã— 3 coordinates
CONFIDENCE_THRESHOLD = 0.25  # Lowered - single attempt verification doesn't need 40%
MIN_HAND_CONFIDENCE = 0.5
SMOOTHING_WINDOW = 5
# Global model state
MODEL = None
SCALER = None
LABELS_MAP = {}
MODEL_LOADED = False

# Frame and prediction buffers for temporal smoothing
FRAME_BUFFER = deque(maxlen=SEQUENCE_LENGTH)
PREDICTION_BUFFER = deque(maxlen=5)
SOFTMAX_BUFFER = deque(maxlen=5)

app = Flask(__name__, static_folder=None)

# Database Configuration
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'mysql+pymysql://root:password@localhost:3306/gesture_ease')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    'pool_size': 10,
    'pool_recycle': 3600,
    'pool_pre_ping': True,
}

# Initialize database
db.init_app(app)

with app.app_context():
    try:
        db.create_all()
        logger.info("Database connected successfully")
    except Exception as e:
        logger.warning(f"Database connection warning: {e}")


# ---------------------------------------------------------------------------
# Security configuration
# ---------------------------------------------------------------------------

# CORS allowlist - only these origins may call the API (no more wildcard "*").
# Configure via ALLOWED_ORIGINS (comma-separated) in the environment.
ALLOWED_ORIGINS = [
    o.strip() for o in os.getenv('ALLOWED_ORIGINS', 'http://localhost:3000').split(',')
    if o.strip()
]


def _resolve_cors_origin():
    """Echo the request Origin only if it is allow-listed, else the first allowed origin."""
    origin = request.headers.get('Origin', '')
    if origin in ALLOWED_ORIGINS:
        return origin
    return ALLOWED_ORIGINS[0] if ALLOWED_ORIGINS else ''


# Rate limiting - protects auth endpoints from brute force and the API from abuse.
# Gracefully degrades to a no-op if flask-limiter isn't installed, so the app
# still runs (install it via requirements.txt to enable enforcement).
try:
    from flask_limiter import Limiter
    from flask_limiter.util import get_remote_address

    limiter = Limiter(
        key_func=get_remote_address,
        app=app,
        default_limits=["300 per hour"],
        storage_uri="memory://",
    )
    RATE_LIMITING_ENABLED = True
    logger.info("Rate limiting enabled (flask-limiter)")
except ImportError:
    RATE_LIMITING_ENABLED = False

    class _NoOpLimiter:
        """Fallback so @limiter.limit(...) is a harmless pass-through."""
        def limit(self, *args, **kwargs):
            def decorator(func):
                return func
            return decorator

    limiter = _NoOpLimiter()
    logger.warning("flask-limiter not installed - rate limiting is DISABLED. "
                   "Run: pip install flask-limiter")


def reset_prediction_buffer():
    """Reset softmax buffer when gesture session starts"""
    global SOFTMAX_BUFFER
    SOFTMAX_BUFFER.clear()
    logger.info("Prediction buffer reset for new session")


def smooth_softmax_predictions(new_softmax):
    """Temporal smoothing: maintain buffer of last 5 softmax outputs"""
    global SOFTMAX_BUFFER
    SOFTMAX_BUFFER.append(new_softmax)
    if len(SOFTMAX_BUFFER) > 0:
        averaged_softmax = np.mean(np.array(list(SOFTMAX_BUFFER)), axis=0)
        return averaged_softmax
    return new_softmax


def verify_gesture(landmarks_sequence, target_word, model, scaler, labels_map, 
                   confidence_threshold=CONFIDENCE_THRESHOLD, use_smoothing=True):
    """Verify if a landmark sequence matches the target gesture using target-only confidence scoring."""
    
    landmarks_flat = landmarks_sequence.reshape(-1, 126)
    landmarks_normalized = scaler.transform(landmarks_flat).reshape(1, 30, 126)
    
    raw_predictions = model.predict(landmarks_normalized, verbose=0)[0]
    
    if use_smoothing:
        predictions = smooth_softmax_predictions(raw_predictions)
    else:
        predictions = raw_predictions
    
    target_word_lower = target_word.lower().strip()
    target_idx = None
    
    for idx, word in labels_map.items():
        if word.lower().strip() == target_word_lower:
            target_idx = idx
            break
    
    if target_idx is None:
        return {
            "is_correct": False,
            "target_word": target_word,
            "target_confidence": 0.0,
            "message": f"Target '{target_word}' not in model labels",
            "buffer_size": len(SOFTMAX_BUFFER)
        }
    
    target_confidence = float(predictions[target_idx])
    is_correct = target_confidence >= confidence_threshold
    
    if is_correct:
        if target_confidence >= 0.6:
            points = 15
        elif target_confidence >= 0.4:
            points = 10
        elif target_confidence >= 0.25:
            points = 5
        else:
            points = 3
    else:
        points = 0
    
    if is_correct:
        if target_confidence >= 0.6:
            message = f"Perfect! You signed '{target_word}' very clearly!"
        elif target_confidence >= 0.4:
            message = f"Good! I recognized '{target_word}'!"
        else:
            message = f"Correct! You performed '{target_word}'!"
    else:
        message = f"Try again. '{target_word}' not clear enough."
    
    top_k_indices = np.argsort(predictions)[-5:][::-1]
    top_predictions = []
    for rank, idx in enumerate(top_k_indices, 1):
        gesture_name = labels_map.get(idx, f"Unknown_{idx}").lower().strip()
        confidence = float(predictions[idx])
        top_predictions.append({
            "rank": rank,
            "gesture": gesture_name,
            "confidence": confidence
        })
    
    return {
        "is_correct": is_correct,
        "target_word": target_word,
        "target_confidence": target_confidence,
        "message": message,
        "points": points,
        "top_predictions": top_predictions,
        "buffer_size": len(SOFTMAX_BUFFER),
        "smoothing_applied": use_smoothing
    }


@app.after_request
def add_cors_headers(response):
    """Add CORS headers to all responses (restricted to the allow-listed origins)"""
    response.headers['Access-Control-Allow-Origin'] = _resolve_cors_origin()
    response.headers['Vary'] = 'Origin'
    response.headers['Access-Control-Allow-Methods'] = 'GET,POST,PUT,DELETE,OPTIONS,HEAD'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type,Authorization'
    response.headers['Access-Control-Max-Age'] = '3600'
    return response


@app.before_request
def handle_preflight():
    """Handle CORS preflight requests (restricted to the allow-listed origins)"""
    if request.method == 'OPTIONS':
        response = jsonify()
        response.status_code = 204
        response.headers['Access-Control-Allow-Origin'] = _resolve_cors_origin()
        response.headers['Vary'] = 'Origin'
        response.headers['Access-Control-Allow-Methods'] = 'GET,POST,PUT,DELETE,OPTIONS,HEAD'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type,Authorization'
        return response

class EnhancedLandmarkExtractor:
    """Extract raw MediaPipe landmarks for hand gesture recognition."""
    
    def __init__(self):
        self.mp_hands = mp.solutions.hands
        self.mp_drawing = mp.solutions.drawing_utils
        
        self.hands = self.mp_hands.Hands(
            static_image_mode=False,
            max_num_hands=2,
            min_detection_confidence=MIN_HAND_CONFIDENCE,
            min_tracking_confidence=0.5,
            model_complexity=1
        )
        
    def extract_hand_landmarks(self, image):
        """Extract landmarks in EXACT training format: (2, 21, 3) → (126,)
        
        Training format:
        - No handedness logic
        - Detection order only (up to 2 hands)
        - Zero padding if < 2 hands
        - Output: (126,) = 2 hands × 21 landmarks × 3 coords
        """
        rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        hands_results = self.hands.process(rgb_image)
        
        landmarks = np.zeros((2, 21, 3), dtype=np.float32)
        hands_detected = 0
        
        if hands_results.multi_hand_landmarks:
            for i, hand_landmarks in enumerate(hands_results.multi_hand_landmarks):
                if i >= 2:
                    break
                hands_detected += 1
                for j, lm in enumerate(hand_landmarks.landmark):
                    landmarks[i, j] = [lm.x, lm.y, lm.z]
        
        return landmarks.reshape(-1), hands_detected, hands_results
    
    def draw_enhanced_landmarks(self, image, hands_results):
        """Draw enhanced landmarks on image"""
        if not hands_results.multi_hand_landmarks:
            return image
            
        annotated_image = image.copy()
        
        for hand_landmarks in hands_results.multi_hand_landmarks:
            self.mp_drawing.draw_landmarks(
                annotated_image, hand_landmarks, self.mp_hands.HAND_CONNECTIONS,
                self.mp_drawing.DrawingSpec(color=(0, 255, 0), thickness=2, circle_radius=3),
                self.mp_drawing.DrawingSpec(color=(0, 255, 0), thickness=2)
            )
        
        return annotated_image


def load_mlops_artifacts():
    """Load all MLOps artifacts with comprehensive error handling"""
    global MODEL, SCALER, LABELS_MAP, MODEL_LOADED
    
    try:
        models_dir = Path('models')
        artifacts_dir = Path('artifacts')
        
        # Load model - try multiple formats
        model_loaded = False
        for model_file in ['best_model.h5', 'model.h5', 'model.keras']:
            model_path = models_dir / model_file
            if model_path.exists():
                logger.info(f" Loading model from {model_path}...")
                try:
                    MODEL = tf.keras.models.load_model(str(model_path))
                    logger.info(" Model loaded successfully")
                    model_loaded = True
                    break
                except ValueError as e:
                    # Handle models saved with legacy layer configs (e.g. LSTM with
                    # unsupported kwargs like `time_major`). Try a compatibility
                    # loader that strips unknown args from LSTM config and retry.
                    msg = str(e)
                    logger.warning(f"Model load failed, trying compatibility fallback: {msg}")
                    if 'Unrecognized keyword arguments passed to LSTM' in msg or 'time_major' in msg:
                        from tensorflow.keras.layers import LSTM as _KerasLSTM

                        class CompatLSTM(_KerasLSTM):
                            @classmethod
                            def from_config(cls, config):
                                # remove legacy keys that newer Keras does not accept
                                config.pop('time_major', None)
                                config.pop('implementation', None)
                                return super().from_config(config)

                        try:
                            MODEL = tf.keras.models.load_model(
                                str(model_path),
                                custom_objects={'LSTM': CompatLSTM}
                            )
                            logger.info(" Model loaded successfully (compatibility mode)")
                            model_loaded = True
                            break
                        except Exception as e2:
                            logger.error(f"Compatibility load also failed: {e2}")
                    # re-raise if it's not the expected legacy LSTM issue
                    logger.error(" Model load failed and compatibility fallback did not succeed")
                    continue
                model_loaded = True
                break
        
        if not model_loaded:
            logger.error("Ã¢ÂÅ’ No model found")
            return False
        
        # Load scaler
        scaler_path = artifacts_dir / 'scaler.pkl'
        if scaler_path.exists():
            with open(scaler_path, 'rb') as f:
                SCALER = pickle.load(f)
            logger.info("âœ“ Scaler loaded")
        else:
            logger.error(" Scaler not found")
            return False
        
        # Load CLEAN labels - prioritize word_mappings.json for clean words
        labels_loaded = False
        
        # Try word_mappings.json first (has clean words)
        word_mappings_path = artifacts_dir / 'word_mappings.json'
        if word_mappings_path.exists():
            logger.info(f"â€¹ Loading clean words from {word_mappings_path}...")
            with open(word_mappings_path, 'r') as f:
                word_data = json.load(f)
            
            if 'class_names' in word_data:
                clean_words = word_data['class_names']
                LABELS_MAP = {i: word for i, word in enumerate(clean_words)}
                logger.info(f" Clean words loaded: {len(LABELS_MAP)} classes")
                labels_loaded = True
        
        # Fallback to other label files if needed
        if not labels_loaded:
            label_paths = [
                models_dir / 'labels.json',
                artifacts_dir / 'labels.json'
            ]
            
            for labels_path in label_paths:
                if labels_path.exists():
                    logger.info(f"Ã°Å¸â€œâ€¹ Loading labels from {labels_path}...")
                    with open(labels_path, 'r') as f:
                        labels_data = json.load(f)
                    
                    if 'id_to_label' in labels_data:
                        raw_labels = labels_data['id_to_label']
                        LABELS_MAP = {}
                        for i, label in raw_labels.items():
                            clean_label = label.split('_(')[0] if '_(' in label else label
                            LABELS_MAP[int(i)] = clean_label
                    elif 'classes' in labels_data:
                        if isinstance(labels_data['classes'], list):
                            raw_words = labels_data['classes']
                            LABELS_MAP = {}
                            for i, word in enumerate(raw_words):
                                clean_word = word.split('_(')[0] if '_(' in word else word
                                LABELS_MAP[i] = clean_word
                        else:
                            LABELS_MAP = {int(k): v.split('_(')[0] if '_(' in v else v 
                                        for k, v in labels_data['classes'].items()}
                    
                    logger.info(f"Ã¢Å“â€¦ Labels cleaned and loaded: {len(LABELS_MAP)} classes")
                    labels_loaded = True
                    break
        
        if not labels_loaded:
            logger.error("Ã¢ÂÅ’ No labels found")
            return False
        
        
        MODEL_LOADED = True
        logger.info(" All artifacts loaded successfully!")
        logger.info(f" Total unique words: {len(LABELS_MAP)}")
        logger.info(f" Sample words: {list(LABELS_MAP.values())[:10]}")
        
        return True
        
    except Exception as e:
        logger.error(f"Ã¢ÂÅ’ Failed to load artifacts: {e}")
        import traceback
        traceback.print_exc()
        MODEL_LOADED = False
        return False


# Initialize landmark extractor (only if MediaPipe is available; the browser
# does landmark extraction for the main flow, so this is optional).
landmark_extractor = EnhancedLandmarkExtractor() if mp is not None else None

def extract_and_preprocess_frame(frame_base64):
    """Enhanced frame processing with quality control"""
    global FRAME_BUFFER
    
    try:
        frame_data = base64.b64decode(frame_base64)
        nparr = np.frombuffer(frame_data, np.uint8)
        frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        if frame is None:
            return None, None
        
        frame = cv2.resize(frame, (640, 480))
        
        landmark_vector, hands_detected, hands_results = landmark_extractor.extract_hand_landmarks(frame)
        
        display_frame = landmark_extractor.draw_enhanced_landmarks(frame, hands_results)
        
        cv2.putText(display_frame, f"Hands: {hands_detected}", (10, 30), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        cv2.putText(display_frame, f"Buffer: {len(FRAME_BUFFER)}/{SEQUENCE_LENGTH}", (10, 60), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        
        if hands_detected > 0:
            FRAME_BUFFER.append(landmark_vector)
        else:
            FRAME_BUFFER.append(np.zeros(FEATURE_DIM, dtype=np.float32))
        
        if len(FRAME_BUFFER) == SEQUENCE_LENGTH:
            sequence_array = np.array(list(FRAME_BUFFER), dtype=np.float32)
            sequence_flat = sequence_array.reshape(-1, FEATURE_DIM)
            sequence_normalized = SCALER.transform(sequence_flat)
            sequence_processed = sequence_normalized.reshape(1, SEQUENCE_LENGTH, FEATURE_DIM)
            
            return sequence_processed, display_frame
        
        return None, display_frame
        
    except Exception as e:
        logger.error(f"Error processing frame: {e}")
        return None, None


def smooth_predictions(new_prediction):
    """Smooth predictions using a buffer to reduce jitter"""
    global PREDICTION_BUFFER
    
    PREDICTION_BUFFER.append(new_prediction)
    
    if len(PREDICTION_BUFFER) < 3:
        return new_prediction
    
    label_counts = {}
    confidence_sums = {}
    
    for pred in PREDICTION_BUFFER:
        label = pred['label']
        confidence = pred['prob']
        
        if label in label_counts:
            label_counts[label] += 1
            confidence_sums[label] += confidence
        else:
            label_counts[label] = 1
            confidence_sums[label] = confidence
    
    best_label = max(label_counts.keys(), 
                    key=lambda x: (label_counts[x], confidence_sums[x] / label_counts[x]))
    
    return {
        'label': best_label,
        'prob': confidence_sums[best_label] / label_counts[best_label]
    }



@app.route('/api/predict', methods=['POST', 'OPTIONS'])
def predict_gesture():
    """Redirect to predict_landmarks endpoint for compatibility"""
    if request.method == 'OPTIONS':
        return '', 200
    
    # Redirect POST requests to the landmarks endpoint
    return predict_from_landmarks()


def normalize_landmark_sequence(landmarks_array, target_length=30):
    """Normalize a landmark sequence to exactly 30 frames by sampling or padding."""
    if len(landmarks_array) == 0:
        raise ValueError("Empty landmark sequence")
    
    current_length = len(landmarks_array)
    
    if current_length == target_length:
        return landmarks_array
    
    if current_length > target_length:
        indices = np.linspace(0, current_length - 1, target_length, dtype=int)
        return landmarks_array[indices]
    else:
        last_frame = landmarks_array[-1]
        pad_count = target_length - current_length
        padding = np.repeat(last_frame[np.newaxis, :], pad_count, axis=0)
        return np.vstack([landmarks_array, padding])






@app.route('/api/predict_landmarks', methods=['POST', 'OPTIONS'])
def predict_from_landmarks():
    """
    Verify if a user's gesture matches the target word.
    Query param: ?reset_buffer=true to start a new gesture session.
    """
    if request.method == 'OPTIONS':
        return '', 200
    
    if not MODEL_LOADED:
        return jsonify({
            "is_correct": False,
            "message": "Model not loaded",
            "target_confidence": 0
        }), 503

    try:
        data = request.json
        target_word = data.get('target_word', '').lower().strip()
        landmarks_sequence = data.get('landmarks', [])
        
        reset_buffer = request.args.get('reset_buffer', 'false').lower() == 'true'
        if reset_buffer:
            reset_prediction_buffer()
        
        # Validate target_word
        if not target_word or target_word == 'undefined' or target_word == 'none':
            logger.error(f"Invalid target_word received: '{target_word}'")
            return jsonify({
                "is_correct": False,
                "message": "Invalid target word",
                "target_confidence": 0
            }), 400
        
        logger.info(f"Verification request: target='{target_word}', frames={len(landmarks_sequence)}")
        
        if len(landmarks_sequence) < 3:
            return jsonify({
                "is_correct": False,
                "message": "Not enough frames",
                "target_confidence": 0
            }), 400
        
        # Convert and validate landmarks
        landmarks_array = np.array(landmarks_sequence, dtype=np.float32)
        
        if landmarks_array.shape[1] != 126:
            logger.error(f"Invalid features: {landmarks_array.shape[1]}")
            return jsonify({
                "is_correct": False,
                "message": "Invalid landmark format",
                "target_confidence": 0
            }), 400
        
        if len(landmarks_array) > 30:
            indices = np.linspace(0, len(landmarks_array)-1, 30, dtype=int)
            landmarks_array = landmarks_array[indices]
        elif len(landmarks_array) < 30:
            last_frame = landmarks_array[-1]
            pad_count = 30 - len(landmarks_array)
            padding = np.repeat(last_frame[np.newaxis, :], pad_count, axis=0)
            landmarks_array = np.vstack([landmarks_array, padding])
        
        logger.info(f"Sequence normalized: {landmarks_array.shape}")
        
        result = verify_gesture(
            landmarks_array,
            target_word,
            MODEL,
            SCALER,
            LABELS_MAP,
            confidence_threshold=CONFIDENCE_THRESHOLD,
            use_smoothing=False
        )
        
        logger.info(f"Verification result:")
        logger.info(f"   is_correct: {result['is_correct']}")
        logger.info(f"   target: '{target_word}'")
        logger.info(f"   target_confidence: {result['target_confidence']:.3f}")
        logger.info(f"   message: {result['message']}")
        logger.info(f"   points: {result['points']}")
        
        # Return CLEAN response format with buffer info
        return jsonify({
            "is_correct": result["is_correct"],
            "target_word": result["target_word"],
            "target_confidence": round(result["target_confidence"], 3),
            "message": result["message"],
            "points": result["points"],
            "top_predictions": result["top_predictions"],
            "debug": {
                "target_rank": next((p["rank"] for p in result["top_predictions"] if p["gesture"] == target_word.lower()), -1),
                "top1": result["top_predictions"][0] if result["top_predictions"] else None,
                "frames_received": len(landmarks_sequence),
                "threshold_used": CONFIDENCE_THRESHOLD
            },
            "buffer_info": {
                "size": result["buffer_size"],
                "max_size": 5,
                "smoothing_applied": result["smoothing_applied"]
            }
        }), 200
        
    except Exception as e:
        logger.error(f"Error: {e}")
        logger.error(traceback.format_exc())
        return jsonify({
            "is_correct": False,
            "message": f"Server error: {str(e)}",
            "target_confidence": 0
        }), 500


@app.route('/api/attempt', methods=['POST', 'OPTIONS'])
@token_required
def save_attempt():
    """Save gesture attempt to database with user tracking"""
    if request.method == 'OPTIONS':
        return '', 204

    try:
        data = request.json
        # Trust the authenticated user from the JWT, never a client-supplied id.
        # This prevents users from writing attempts on behalf of someone else (IDOR).
        user_id = request.user_id
        target_word = data.get('target_word', '').lower().strip()
        is_correct = data.get('is_correct', False)
        target_confidence = data.get('target_confidence', 0)
        points = data.get('points', 0)
        feedback = data.get('message', '')
        top_predictions = data.get('top_predictions', [])
        
        # Validate user
        if not user_id:
            return jsonify({'success': False, 'error': 'User ID required'}), 400
        
        user = User.query.get(user_id)
        if not user:
            return jsonify({'success': False, 'error': 'User not found'}), 404
        
        # Create gesture attempt record
        attempt = GestureAttempt(
            user_id=user_id,
            target_word=target_word,
            target_confidence=target_confidence,
            is_correct=is_correct,
            points=points,
            feedback=feedback,
            top_predictions=json.dumps([p for p in top_predictions[:5]])  # Store top 5
        )
        
        db.session.add(attempt)
        
        # Update or create word progress
        progress = UserProgress.query.filter_by(user_id=user_id, word=target_word).first()
        if progress:
            progress.attempts += 1
            if is_correct:
                progress.correct += 1
            progress.confidence = target_confidence
            progress.updated_at = datetime.utcnow()
        else:
            progress = UserProgress(
                user_id=user_id,
                word=target_word,
                attempts=1,
                correct=1 if is_correct else 0,
                confidence=target_confidence
            )
            db.session.add(progress)
        
        db.session.commit()
        
        # Refresh user to get updated attempts
        db.session.refresh(user)
        
        logger.info(f"Attempt saved for user {user.username}: {target_word} - {'Correct' if is_correct else 'Incorrect'}")
        logger.info(f"Total points after save: {sum([a.points for a in user.attempts])}")
        
        return jsonify({
            'success': True,
            'attempt_id': attempt.id,
            'points': points,
            'user_stats': user.get_stats()
        }), 201
        
    except Exception as e:
        logger.error(f"Error saving attempt: {e}")
        logger.error(traceback.format_exc())
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/user/<int:user_id>/progress', methods=['GET'])
@token_required
def get_user_progress(user_id):
    """Get user's word progress"""
    try:
        # Ownership check: a user may only read their own progress (prevents IDOR).
        if request.user_id != user_id:
            return jsonify({'success': False, 'error': 'Forbidden'}), 403

        user = User.query.get(user_id)
        if not user:
            return jsonify({'success': False, 'error': 'User not found'}), 404
        
        progress = UserProgress.query.filter_by(user_id=user_id).order_by(UserProgress.updated_at.desc()).all()
        
        return jsonify({
            'success': True,
            'username': user.username,
            'progress': [p.to_dict() for p in progress]
        })
        
    except Exception as e:
        logger.error(f"Error getting progress: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/user/<int:user_id>/attempts', methods=['GET'])
@token_required
def get_user_attempts(user_id):
    """Get user's recent gesture attempts"""
    try:
        # Ownership check: a user may only read their own attempts (prevents IDOR).
        if request.user_id != user_id:
            return jsonify({'success': False, 'error': 'Forbidden'}), 403

        limit = request.args.get('limit', 20, type=int)

        user = User.query.get(user_id)
        if not user:
            return jsonify({'success': False, 'error': 'User not found'}), 404
        
        attempts = GestureAttempt.query.filter_by(user_id=user_id)\
            .order_by(GestureAttempt.created_at.desc())\
            .limit(limit).all()
        
        return jsonify({
            'success': True,
            'username': user.username,
            'attempts': [a.to_dict() for a in attempts]
        })
        
    except Exception as e:
        logger.error(f"Error getting attempts: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500
def _check_prediction_match(predicted, target, confidence):
    """Enhanced matching with fuzzy logic for variations"""
    predicted_lower = predicted.lower().strip()
    target_lower = target.lower().strip()
    
    # Exact match
    if predicted_lower == target_lower:
        return True
    
    # High confidence partial match (for compound words)
    if confidence > 0.6:
        if target_lower in predicted_lower or predicted_lower in target_lower:
            return True
    
    return False


def _calculate_quality_points(is_correct, confidence, predicted, target):
    """Calculate points based on correctness and gesture quality"""
    if not is_correct:
        return 0
    
    # Base points on confidence
    if confidence > 0.7:
        return 20 + int((confidence - 0.7) * 20)  # 20-26 points
    elif confidence > 0.5:
        return 15 + int((confidence - 0.5) * 25)  # 15-20 points
    elif confidence > 0.3:
        return 10 + int((confidence - 0.3) * 25)  # 10-15 points
    else:
        return 5  # Minimum for correct but low confidence


def _generate_feedback_message(is_correct, predicted, target, confidence, top_predictions):
    """Generate contextual feedback based on prediction quality"""
    if is_correct:
        if confidence > 0.7:
            return f"Excellent! Perfect execution of '{predicted}'. Your gesture was clear and accurate."
        elif confidence > 0.5:
            return f"Good job! You correctly signed '{predicted}'. Keep practicing for even better accuracy."
        elif confidence > 0.3:
            return f"Correct! '{predicted}' was recognized. Try to make your gestures more pronounced for higher confidence."
        else:
            return f"'{predicted}' was detected but with low confidence. Focus on clearer hand positioning and movement."
    else:
        # Provide helpful feedback for incorrect predictions
        if confidence > 0.5:
            return f"The system detected '{predicted}' with high confidence, but you were practicing '{target}'. Review the correct gesture and try again."
        else:
            return f"Gesture unclear. The system detected '{predicted}' but expected '{target}'. Ensure your hands are fully visible and perform the complete gesture."


def _assess_gesture_quality(landmarks_array, confidence, is_correct):
    """Assess the quality of the performed gesture"""
    # Calculate movement magnitude
    if len(landmarks_array) > 1:
        movement = np.sum(np.abs(np.diff(landmarks_array, axis=0)))
        avg_movement = np.mean(movement)
    else:
        avg_movement = 0
    
    # Assess based on movement and confidence
    if is_correct and confidence > 0.6:
        quality = "excellent"
        feedback = "Your gesture execution was clear and accurate."
    elif is_correct and confidence > 0.4:
        quality = "good"
        feedback = "Good execution. Minor improvements in clarity could increase confidence."
    elif is_correct:
        quality = "acceptable"
        feedback = "Gesture recognized but could be clearer. Focus on complete hand movements."
    elif confidence > 0.4:
        quality = "unclear_target"
        feedback = "Gesture detected but doesn't match target. Review the correct sign."
    else:
        quality = "needs_improvement"
        feedback = "Gesture unclear. Ensure hands are fully visible and perform complete movements."
    
    return {
        "quality": quality,
        "feedback": feedback,
        "movement_detected": avg_movement > 0.1,
        "recommendations": _get_quality_recommendations(quality, avg_movement)
    }


def _get_quality_recommendations(quality, movement):
    """Get specific recommendations based on quality assessment"""
    recommendations = []
    
    if movement < 0.05:
        recommendations.append("Increase hand movement - gestures should be more dynamic")
    
    if quality in ["needs_improvement", "acceptable"]:
        recommendations.append("Ensure both hands are fully visible in frame")
        recommendations.append("Complete the full gesture motion before stopping")
        recommendations.append("Maintain consistent hand positioning relative to your body")
    
    if quality == "unclear_target":
        recommendations.append("Review the correct sign for this word")
        recommendations.append("Pay attention to hand shape and finger positions")
    
    return recommendations

@app.route('/api/predict/sign', methods=['POST'])
def predict_sign():
    """Enhanced prediction endpoint for single frame"""
    if not MODEL_LOADED:
        return jsonify({"error": "Model not loaded. Check server logs."}), 503

    data = request.json
    frame_base64 = data.get('frame_base64')

    if not frame_base64:
        return jsonify({"error": "Missing 'frame_base64' in request."}), 400

    sequence_processed, display_frame = extract_and_preprocess_frame(frame_base64)

    if display_frame is not None:
        _, buffer = cv2.imencode('.jpeg', display_frame)
        display_frame_base64 = base64.b64encode(buffer).decode('utf-8')
    else:
        display_frame_base64 = ""

    predictions_data = []
    
    if sequence_processed is not None and MODEL:
        try:
            prediction_probs = MODEL.predict(sequence_processed, verbose=0)[0]
            top_k_indices = np.argsort(prediction_probs)[::-1][:5]
            
            raw_predictions = []
            for i in top_k_indices:
                label = LABELS_MAP.get(i, f"Unknown_{i}")
                prob = float(prediction_probs[i])
                raw_predictions.append({"label": label, "prob": prob})
            
            best_prediction = raw_predictions[0]
            # FIXED: Reduced threshold for better recognition
            if best_prediction['prob'] >= 0.3:
                smoothed_prediction = smooth_predictions(best_prediction)
                predictions_data.append(smoothed_prediction)
                
                for pred in raw_predictions[1:]:
                    if pred['prob'] >= 0.15:  # Reduced threshold for alternative predictions
                        predictions_data.append(pred)
            else:
                predictions_data.append({"label": "Low confidence", "prob": best_prediction['prob']})
            
            logger.info(f"Predicted: {predictions_data[0]['label']} ({predictions_data[0]['prob']:.3f})")
            
        except Exception as e:
            logger.error(f"Prediction error: {e}")
            predictions_data.append({"label": "Prediction error", "prob": 0.0})
    else:
        predictions_data.append({
            "label": f"Collecting frames... ({len(FRAME_BUFFER)}/{SEQUENCE_LENGTH})", 
            "prob": 0.0
        })
    
    return jsonify({
        "predictions": predictions_data,
        "timestamp": datetime.now().isoformat(),
        "model_version": "enhanced_v1.0",
        "frame_with_overlay_base64": display_frame_base64,
        "buffer_status": {
            "current_size": len(FRAME_BUFFER),
            "required_size": SEQUENCE_LENGTH,
            "ready": len(FRAME_BUFFER) == SEQUENCE_LENGTH
        }
    })


@app.route('/api/search', methods=['GET', 'POST', 'OPTIONS'])
def search():
    """Search available sign language words."""
    
    # Handle OPTIONS preflight
    if request.method == 'OPTIONS':
        return jsonify({'status': 'OK'})
    
    # Ensure we have words available
    if not MODEL_LOADED or not LABELS_MAP:
        logger.warning(" Search called but no words available - using defaults")
        default_words = ["hello", "thank you", "yes", "no", "please", "sorry", "help", "good", "about", "accept"]
        
        return jsonify({
            "success": True,
            "words": default_words,
            "total_found": len(default_words),
            "total_classes": len(default_words),
            "search_term": "",
            "model_loaded": False,
            "approach": "Default Words",
            "features": f"{FEATURE_DIM}D",
            "sequence_length": SEQUENCE_LENGTH,
            "message": "Using default words - model not loaded"
        })
    
    # Get all available words
    all_words = list(LABELS_MAP.values())
    logger.info(f" Search endpoint called - {len(all_words)} words available")
    
    # Extract search term from request
    search_term = ""
    if request.method == 'POST':
        data = request.get_json() or {}
        search_term = data.get('query', '').lower().strip()
        logger.info(f"Ã°Å¸â€Â POST search query: '{search_term}'")
    elif request.method == 'GET':
        search_term = request.args.get('q', '').lower().strip()
        search_term = search_term or request.args.get('query', '').lower().strip()
        logger.info(f"Ã°Å¸â€Â GET search query: '{search_term}'")
    
    # If no search term, return all words (limited to first 100)
    if not search_term:
        sorted_words = sorted(all_words)[:100]
        
        result = {
            "success": True,
            "words": sorted_words,
            "total_found": len(all_words),
            "total_classes": len(all_words),
            "search_term": "",
            "model_loaded": MODEL_LOADED,
            "approach": "Landmark-based BiLSTM with Attention",
            "features": f"{FEATURE_DIM}D",
            "sequence_length": SEQUENCE_LENGTH,
            "accuracy": "82.6%",
            "top3_accuracy": "92.5%",
            "message": f"Showing first {len(sorted_words)} words"
        }
        
        logger.info(f"Ã¢Å“â€¦ No search term - returning {len(sorted_words)} words")
        return jsonify(result)
    
    # Perform search
    filtered_words = []
    search_lower = search_term.lower()
    
    # Case-insensitive search
    for word in all_words:
        if search_lower in word.lower():
            filtered_words.append(word)
    
    # Sort by relevance
    exact_matches = [w for w in filtered_words if w.lower() == search_lower]
    starts_with = [w for w in filtered_words if w.lower().startswith(search_lower) and w.lower() != search_lower]
    contains = [w for w in filtered_words if search_lower in w.lower() and not w.lower().startswith(search_lower)]
    
    final_words = exact_matches + starts_with + contains
    
    # Prepare response
    result = {
        "success": True,
        "words": final_words[:50],  # Limit to 50 results
        "total_found": len(final_words),
        "total_classes": len(all_words),
        "search_term": search_term,
        "model_loaded": MODEL_LOADED,
        "approach": "Landmark-based BiLSTM with Attention",
        "features": f"{FEATURE_DIM}D",
        "sequence_length": SEQUENCE_LENGTH,
        "accuracy": "82.6%",
        "top3_accuracy": "92.5%",
        "message": f"Found {len(final_words)} matches for '{search_term}'"
    }
    
    logger.info(f"Ã°Å¸Å½Â¯ Search '{search_term}' found {len(final_words)} matches")
    return jsonify(result)


@app.route('/api/words', methods=['GET'])
def get_words():
    """Get all available words - FRONTEND COMPATIBLE"""
    if LABELS_MAP and MODEL_LOADED:
        words = sorted(list(LABELS_MAP.values()))
        logger.info(f" /api/words - returning {len(words)} words")
        
        return jsonify({
            "success": True,
            "words": words,
            "total_classes": len(words),
            "approach": "Landmark-based BiLSTM with Attention",
            "features": f"{FEATURE_DIM}D",
            "sequence_length": SEQUENCE_LENGTH,
            "model_loaded": True,
            "accuracy": "82.6%",
            "top3_accuracy": "92.5%"
        })
    else:
        logger.warning("Ã°Å¸â€œÂ /api/words - model not loaded, returning defaults")
        default_words = ["hello", "thank you", "yes", "no", "please", "sorry", "help", "good", "about", "accept"]
        
        return jsonify({
            "success": True,
            "words": default_words,
            "total_classes": len(default_words),
            "approach": "Default Words",
            "features": f"{FEATURE_DIM}D",
            "sequence_length": SEQUENCE_LENGTH,
            "model_loaded": False,
            "error": "Model not loaded"
        })


@app.route('/api/status', methods=['GET', 'OPTIONS'])
def status():
    """Backend status check"""
    if request.method == 'OPTIONS':
        return '', 204
    word_count = len(LABELS_MAP) if LABELS_MAP else 0
    
    return jsonify({
        "success": True,
        "status": "online", 
        "model_loaded": MODEL_LOADED,
        "total_classes": word_count,
        "sequence_length": SEQUENCE_LENGTH,
        "feature_dimension": FEATURE_DIM,
        "buffer_size": len(FRAME_BUFFER),
        "approach": "Landmark-based BiLSTM with Attention" if MODEL_LOADED else "Model not loaded",
        "features": f"{FEATURE_DIM}D",
        "accuracy": "82.6%" if MODEL_LOADED else "N/A",
        "timestamp": datetime.now().isoformat(),
        "ready_for_predictions": MODEL_LOADED and SCALER is not None
    })


@app.route('/api/session/start', methods=['POST', 'OPTIONS'])
def start_gesture_session():
    """Start new gesture session - resets prediction buffer"""
    if request.method == 'OPTIONS':
        return '', 204
    
    reset_prediction_buffer()
    
    return jsonify({
        "success": True,
        "message": "New gesture session started",
        "buffer_reset": True,
        "buffer_size": len(SOFTMAX_BUFFER)
    }), 200


@app.route('/api/reset_buffer', methods=['POST'])
def reset_buffer():
    """Reset the frame buffer"""
    global FRAME_BUFFER, PREDICTION_BUFFER
    FRAME_BUFFER.clear()
    PREDICTION_BUFFER.clear()
    logger.info("Ã°Å¸â€â€ž Buffers reset")
    return jsonify({"success": True, "message": "Buffers reset successfully"})


@app.route('/api/model_info', methods=['GET'])
def model_info():
    """Get complete information about the loaded model"""
    if not MODEL_LOADED:
        return jsonify({
            "success": False,
            "error": "Model not loaded",
            "model_loaded": False,
            "num_classes": 0,
            "approach": "Model not loaded",
            "features": f"{FEATURE_DIM}D"
        }), 503
    
    return jsonify({
        "success": True,
        "model_loaded": MODEL_LOADED,
        "num_classes": len(LABELS_MAP),
        "classes": list(LABELS_MAP.values()),
        "sequence_length": SEQUENCE_LENGTH,
        "feature_dim": FEATURE_DIM,
        "confidence_threshold": CONFIDENCE_THRESHOLD,
        "buffer_size": len(FRAME_BUFFER),
        "approach": "Landmark-based BiLSTM with Attention",
        "features": f"{FEATURE_DIM}D",
        "accuracy": "82.6%",
        "top3_accuracy": "92.5%"
    })



@app.route('/videos/<filename>')
def serve_video(filename):
    """Serve video files for the frontend"""
    try:
        videos_dir = Path('videos')
        if not videos_dir.exists():
            # Try alternative paths
            alternative_paths = [
                Path('dataset/videos'),
                Path('backend/videos'),
                Path('data/videos')
            ]
            for alt_path in alternative_paths:
                if alt_path.exists():
                    videos_dir = alt_path
                    break
        
        if videos_dir.exists():
            return send_from_directory(str(videos_dir), filename)
        else:
            logger.warning(f"Videos directory not found for {filename}")
            return jsonify({"error": "Videos directory not found"}), 404
            
    except Exception as e:
        logger.error(f"Error serving video {filename}: {e}")
        return jsonify({"error": f"Video not found: {filename}"}), 404


# Authentication endpoints for frontend compatibility
@app.route('/api/auth/login', methods=['POST', 'OPTIONS'])
@limiter.limit("5 per minute", methods=['POST'])
def login():
    """Login with MySQL database"""
    if request.method == 'OPTIONS':
        return '', 204
    try:
        data = request.get_json()
        email = data.get('email', '').strip().lower()
        password = data.get('password', '')
        
        # Validation
        if not email or not password:
            return jsonify({
                "success": False,
                "error": "Email and password required"
            }), 400
        
        if '@' not in email:
            return jsonify({
                "success": False,
                "error": "Invalid email format"
            }), 400
        
        # Check if user exists
        user = User.query.filter_by(email=email).first()
        
        if not user or not user.check_password(password):
            return jsonify({
                "success": False,
                "error": "Invalid email or password"
            }), 401
        
        # Success - return user data with JWT token
        token = generate_token(user.id, user.username)
        logger.info(f"User logged in: {user.username}")
        return jsonify({
            "success": True,
            "token": token,
            "user": user.to_dict()
        }), 200
        
    except Exception as e:
        logger.error(f"Login error: {e}")
        return jsonify({
            "success": False,
            "error": "Login failed"
        }), 500

@app.route('/api/auth/register', methods=['POST', 'OPTIONS'])
@limiter.limit("3 per minute", methods=['POST'])
def register():
    """Register new user with MySQL database"""
    if request.method == 'OPTIONS':
        return '', 204
    try:
        data = request.get_json()
        email = data.get('email', '').strip().lower()
        password = data.get('password', '')
        username = data.get('username', '').strip()
        
        # Validation
        if not email or not password:
            return jsonify({
                "success": False,
                "error": "Email and password required"
            }), 400
        
        if not username:
            return jsonify({
                "success": False,
                "error": "Username required"
            }), 400
        
        if '@' not in email:
            return jsonify({
                "success": False,
                "error": "Invalid email format"
            }), 400
        
        if len(password) < 6:
            return jsonify({
                "success": False,
                "error": "Password must be at least 6 characters"
            }), 400
        
        # Check if user exists
        if User.query.filter_by(email=email).first():
            return jsonify({
                "success": False,
                "error": "Email already registered"
            }), 409
        
        if User.query.filter_by(username=username).first():
            return jsonify({
                "success": False,
                "error": "Username already taken"
            }), 409
        
        # Create new user
        user = User(email=email, username=username)
        user.set_password(password)
        
        db.session.add(user)
        db.session.commit()
        
        # Generate JWT token
        token = generate_token(user.id, user.username)
        logger.info(f"New user registered: {user.username}")
        
        return jsonify({
            "success": True,
            "token": token,
            "user": user.to_dict()
        }), 201

        
    except Exception as e:
        logger.error(f"Register error: {e}")
        return jsonify({
            "success": False,
            "error": "Registration failed"
        }), 500

@app.route('/api/auth/me', methods=['GET'])
def me():
    """Get current user profile with database"""
    try:
        # Get token from header
        auth_header = request.headers.get('Authorization', '')
        if not auth_header.startswith('Bearer '):
            # For now, return demo user if no token
            return jsonify({
                'success': True,
                'user': {
                    'user_id': 0,
                    'username': 'demo',
                    'email': 'demo@gesturease.com',
                    'stats': {
                        'level': 1,
                        'total_points': 0,
                        'current_streak': 0,
                        'longest_streak': 0,
                        'total_attempts': 0,
                        'correct_attempts': 0,
                        'words_practiced': [],
                        'accuracy': 0
                    }
                }
            })
        
        # Extract user ID from token
        token = auth_header.replace('Bearer ', '')
        try:
            user_id = int(token.split('-')[1])
        except:
            return jsonify({'success': False, 'error': 'Invalid token'}), 401
        
        # Get user from database
        user = User.query.get(user_id)
        if not user:
            return jsonify({'success': False, 'error': 'User not found'}), 404
        
        return jsonify({
            'success': True,
            'user': user.to_dict()
        })
        
    except Exception as e:
        logger.error(f"Error fetching user profile: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/leaderboard', methods=['GET'])
def leaderboard():
    """Get top users leaderboard"""
    try:
        # Get top 10 users by points
        top_users = db.session.query(User, db.func.sum(GestureAttempt.points).label('total_points'))\
            .outerjoin(GestureAttempt)\
            .group_by(User.id)\
            .order_by(db.desc('total_points'))\
            .limit(10).all()
        
        leaderboard_data = []
        for idx, (user, points) in enumerate(top_users, 1):
            stats = user.get_stats()
            leaderboard_data.append({
                'rank': idx,
                'username': user.username,
                'total_points': stats['total_points'],
                'accuracy': stats['accuracy'],
                'total_attempts': stats['total_attempts'],
                'level': stats['level']
            })
        
        return jsonify({
            'success': True,
            'leaderboard': leaderboard_data,
            'total_users': User.query.count()
        })
        
    except Exception as e:
        logger.error(f"Leaderboard error: {e}")
        return jsonify({'success': True, 'leaderboard': []})


@app.route('/api/debug_landmarks', methods=['POST'])
def debug_landmarks():
    """Debug endpoint to check landmark extraction quality"""
    if not MODEL_LOADED:
        return jsonify({"error": "Model not loaded"}), 503

    try:
        data = request.json
        frames = data.get('frames', [])
        
        if not frames:
            return jsonify({"error": "No frames provided"}), 400

        logger.info(f"DEBUGGING landmark extraction for {len(frames)} frames...")
        
        debug_info = {
            "total_frames": len(frames),
            "landmark_extraction_details": [],
            "coordinate_ranges": {
                "x_min": float('inf'), "x_max": float('-inf'),
                "y_min": float('inf'), "y_max": float('-inf'),
                "z_min": float('inf'), "z_max": float('-inf')
            },
            "hand_detection_stats": {
                "frames_with_hands": 0,
                "frames_without_hands": 0,
                "average_confidence": 0
            }
        }
        
        landmarks_sequence = []
        total_confidence = 0
        frames_with_hands = 0
        
        for i, frame_base64 in enumerate(frames[:5]):  # Debug first 5 frames only
            try:
                # Remove data URL prefix if present
                if 'data:image' in frame_base64:
                    frame_base64 = frame_base64.split(',')[1]
                
                frame_data = base64.b64decode(frame_base64)
                nparr = np.frombuffer(frame_data, np.uint8)
                frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                
                if frame is not None:
                    frame = cv2.resize(frame, (640, 480))
                    
                    # Extract landmarks with detailed debug info
                    rgb_image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    hands_results = landmark_extractor.hands.process(rgb_image)
                    pose_results = landmark_extractor.pose.process(rgb_image)
                    
                    frame_debug = {
                        "frame_index": i,
                        "hands_detected": 0,
                        "hand_confidences": [],
                        "raw_landmarks_sample": [],
                        "normalized_landmarks_sample": [],
                        "pose_detected": pose_results.pose_landmarks is not None
                    }
                    
                    # Check hand detection
                    if hands_results.multi_hand_landmarks and hands_results.multi_handedness:
                        for hand_landmarks, handedness in zip(hands_results.multi_hand_landmarks, hands_results.multi_handedness):
                            hand_confidence = handedness.classification[0].score
                            hand_label = handedness.classification[0].label
                            
                            frame_debug["hands_detected"] += 1
                            frame_debug["hand_confidences"].append({
                                "hand": hand_label,
                                "confidence": float(hand_confidence)
                            })
                            
                            total_confidence += hand_confidence
                            frames_with_hands += 1
                            
                            # Sample first 3 landmarks (raw)
                            raw_sample = []
                            for j, landmark in enumerate(hand_landmarks.landmark[:3]):
                                raw_coords = {
                                    "landmark_id": j,
                                    "x": float(landmark.x),
                                    "y": float(landmark.y), 
                                    "z": float(landmark.z)
                                }
                                raw_sample.append(raw_coords)
                                
                                # Update coordinate ranges
                                debug_info["coordinate_ranges"]["x_min"] = min(debug_info["coordinate_ranges"]["x_min"], landmark.x)
                                debug_info["coordinate_ranges"]["x_max"] = max(debug_info["coordinate_ranges"]["x_max"], landmark.x)
                                debug_info["coordinate_ranges"]["y_min"] = min(debug_info["coordinate_ranges"]["y_min"], landmark.y)
                                debug_info["coordinate_ranges"]["y_max"] = max(debug_info["coordinate_ranges"]["y_max"], landmark.y)
                                debug_info["coordinate_ranges"]["z_min"] = min(debug_info["coordinate_ranges"]["z_min"], landmark.z)
                                debug_info["coordinate_ranges"]["z_max"] = max(debug_info["coordinate_ranges"]["z_max"], landmark.z)
                            
                            frame_debug["raw_landmarks_sample"] = raw_sample
                    
                    # Extract full landmark vector using our method
                    landmark_vector, hands_detected, _ = landmark_extractor.extract_hand_landmarks(frame)
                    landmarks_sequence.append(landmark_vector)
                    
                    # Sample of normalized landmarks
                    if np.any(landmark_vector != 0):
                        normalized_sample = landmark_vector[:9].tolist()  # First 3 landmarks (9 coords)
                        frame_debug["normalized_landmarks_sample"] = normalized_sample
                    
                    debug_info["landmark_extraction_details"].append(frame_debug)
                    
            except Exception as e:
                logger.error(f"Error processing frame {i}: {e}")
                debug_info["landmark_extraction_details"].append({
                    "frame_index": i,
                    "error": str(e)
                })
        
        # Calculate stats
        if frames_with_hands > 0:
            debug_info["hand_detection_stats"]["average_confidence"] = total_confidence / frames_with_hands
            
        debug_info["hand_detection_stats"]["frames_with_hands"] = frames_with_hands
        debug_info["hand_detection_stats"]["frames_without_hands"] = len(frames) - frames_with_hands
        
        # Check if landmarks look reasonable
        landmarks_array = np.array(landmarks_sequence)
        debug_info["landmark_quality"] = {
            "all_zeros": int(np.sum(np.all(landmarks_array == 0, axis=1))),
            "non_zero_frames": int(np.sum(np.any(landmarks_array != 0, axis=1))),
            "landmark_vector_shape": landmarks_array.shape,
            "average_landmark_magnitude": float(np.mean(np.abs(landmarks_array[landmarks_array != 0]))),
            "landmark_std": float(np.std(landmarks_array[landmarks_array != 0]))
        }
        
        logger.info(f" DEBUG SUMMARY:")
        logger.info(f"   - Hands detected in {frames_with_hands}/{len(frames)} frames")
        logger.info(f"   - Average confidence: {debug_info['hand_detection_stats']['average_confidence']:.3f}")
        logger.info(f"   - Coordinate ranges: X[{debug_info['coordinate_ranges']['x_min']:.3f}, {debug_info['coordinate_ranges']['x_max']:.3f}]")
        logger.info(f"   - Non-zero landmarks: {debug_info['landmark_quality']['non_zero_frames']}/{len(frames)}")
        
        return jsonify({
            "success": True,
            "debug_info": debug_info,
            "recommendation": "Check if coordinate ranges and detection rates match training expectations"
        })
        
    except Exception as e:
        logger.error(f" Debug landmarks error: {e}")
        return jsonify({"error": f"Debug failed: {str(e)}"}), 500


@app.route('/api/test_model', methods=['GET'])
def test_model():
    """Test model with dummy data - detailed prediction statistics"""
    if not MODEL_LOADED or not MODEL or not SCALER:
        return jsonify({"error": "Model not ready"}), 503
    
    try:
        dummy_input = np.random.random((1, 30, 126)).astype(np.float32)
        predictions = MODEL.predict(dummy_input, verbose=0)[0]
        
        softmax_stats = {
            "max_softmax_value": float(np.max(predictions)),
            "min_softmax_value": float(np.min(predictions)),
            "mean_softmax_value": float(np.mean(predictions)),
            "std_softmax_value": float(np.std(predictions)),
            "sum_softmax_value": float(np.sum(predictions))
        }
        
        top_indices = np.argsort(predictions)[::-1][:10]
        top_predictions = []
        
        for rank, idx in enumerate(top_indices, 1):
            word = LABELS_MAP.get(idx, f"Unknown_{idx}")
            confidence = float(predictions[idx])
            top_predictions.append({
                "rank": rank,
                "index": int(idx),
                "word": word,
                "confidence": confidence
            })
        
        hello_info = {"exists_in_vocabulary": False, "index": -1, "softmax_confidence": 0.0, "rank_among_all_classes": -1}
        for idx, word in LABELS_MAP.items():
            if word.lower() == 'hello':
                hello_confidence = float(predictions[idx])
                hello_rank = int(np.where(np.argsort(predictions)[::-1] == idx)[0][0]) + 1
                hello_info = {
                    "exists_in_vocabulary": True,
                    "index": int(idx),
                    "softmax_confidence": hello_confidence,
                    "rank_among_all_classes": hello_rank
                }
                break
        
        return jsonify({
            "success": True,
            "model_architecture": {
                "input_shape": str(MODEL.input_shape),
                "output_shape": str(MODEL.output_shape),
                "total_classes": int(MODEL.output_shape[-1])
            },
            "softmax_statistics": softmax_stats,
            "top_10_predictions": top_predictions,
            "hello_analysis": hello_info,
            "dummy_input_shape": list(dummy_input.shape)
        })
        
    except Exception as e:
        return jsonify({"error": f"Test failed: {str(e)}"}), 500


@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        "success": True,
        "status": "healthy",
        "model_loaded": MODEL_LOADED,
        "timestamp": datetime.now().isoformat(),
        "total_classes": len(LABELS_MAP) if LABELS_MAP else 0
    })


# Debug endpoint for troubleshooting
@app.route('/api/debug', methods=['GET'])
def debug_endpoint():
    """Debug endpoint to check what's loaded"""
    
    # Check if 'hello' exists in our vocabulary
    hello_exists = False
    hello_index = -1
    
    if LABELS_MAP:
        for idx, word in LABELS_MAP.items():
            if word.lower() == 'hello':
                hello_exists = True
                hello_index = idx
                break
    
    return jsonify({
        "success": True,
        "model_loaded": MODEL_LOADED,
        "labels_map_size": len(LABELS_MAP) if LABELS_MAP else 0,
        "sample_labels": list(LABELS_MAP.values())[:20] if LABELS_MAP else [],
        "scaler_loaded": SCALER is not None,
        "model_object_loaded": MODEL is not None,
        "buffer_size": len(FRAME_BUFFER),
        "sequence_length": SEQUENCE_LENGTH,
        "feature_dim": FEATURE_DIM, 
        "confidence_threshold": CONFIDENCE_THRESHOLD,
        "min_hand_confidence": MIN_HAND_CONFIDENCE, 
        
        "hello_debug": {
            "exists_in_vocabulary": hello_exists,
            "hello_index": hello_index,
            "all_words_containing_hello": [word for word in LABELS_MAP.values() if 'hello' in word.lower()] if LABELS_MAP else []
        },
        
        # Model shape info
        "model_info": {
            "input_shape": str(MODEL.input_shape) if MODEL else None,
            "output_shape": str(MODEL.output_shape) if MODEL else None,
            "num_classes_from_model": MODEL.output_shape[-1] if MODEL else None
        },
        
        "artifacts_status": {
            "models_dir_exists": Path('models').exists(),
            "artifacts_dir_exists": Path('artifacts').exists(),
            "word_mappings_exists": Path('artifacts/word_mappings.json').exists(),
            "scaler_exists": Path('artifacts/scaler.pkl').exists(),
            "model_files": [f.name for f in Path('models').glob('*.h5')] + [f.name for f in Path('models').glob('*.keras')] if Path('models').exists() else []
        }
    })



@app.route('/api/save_landmarks', methods=['POST', 'OPTIONS'])
def save_landmarks():
    """
    Save recorded landmarks to dataset folder structure.
    
    Request:
    {
        "word": "hello",
        "landmarks": [[x1,y1,z1,...], [x2,y2,z2,...], ...]
    }
    
    Response:
    {
        "status": "saved",
        "word": "hello",
        "file": "hello_01.npy",
        "frames": 30,
        "shape": [30, 126]
    }
    """
    if request.method == 'OPTIONS':
        return '', 204
    
    try:
        data = request.json
        word = data.get('word', '').lower().strip()
        landmarks = data.get('landmarks', [])
        
        # Validate input
        if not word or word == 'undefined' or word == 'none':
            logger.error(f"Invalid word: '{word}'")
            return jsonify({
                "status": "error",
                "message": "Invalid word provided"
            }), 400
        
        if len(landmarks) < 10:
            logger.error(f"Too few frames: {len(landmarks)}")
            return jsonify({
                "status": "error",
                "message": f"Too few frames ({len(landmarks)} < 10)"
            }), 400
        
        if len(landmarks) > 200:
            logger.error(f"Too many frames: {len(landmarks)}")
            return jsonify({
                "status": "error",
                "message": f"Too many frames ({len(landmarks)} > 200)"
            }), 400
        
        # Convert to numpy array
        landmarks_array = np.array(landmarks, dtype=np.float32)
        
        # Validate shape
        if landmarks_array.ndim != 2 or landmarks_array.shape[1] != 126:
            logger.error(f"Invalid shape: {landmarks_array.shape}")
            return jsonify({
                "status": "error",
                "message": f"Invalid landmark shape: {landmarks_array.shape}"
            }), 400
        
        # Create dataset directory structure
        dataset_dir = Path('dataset') / word
        dataset_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"Dataset dir: {dataset_dir}")
        
        # Find next file number
        existing_files = list(dataset_dir.glob(f"{word}_*.npy"))
        next_num = len(existing_files) + 1
        
        # Save file
        filename = f"{word}_{next_num:02d}.npy"
        filepath = dataset_dir / filename
        
        np.save(filepath, landmarks_array)
        logger.info(f"Saved: {filepath}")
        
        # Verify save
        if not filepath.exists():
            logger.error(f"File not created: {filepath}")
            return jsonify({
                "status": "error",
                "message": "Failed to save file"
            }), 500
        
        # Verify loaded data
        loaded = np.load(filepath)
        logger.info(f"Verified: shape={loaded.shape}, dtype={loaded.dtype}")
        
        return jsonify({
            "status": "saved",
            "word": word,
            "file": filename,
            "frames": int(landmarks_array.shape[0]),
            "shape": list(landmarks_array.shape),
            "path": str(filepath),
            "message": f"[CHECK] Successfully saved {landmarks_array.shape[0]} frames"
        }), 200
        
    except Exception as e:
        logger.error(f"[ERROR] Error saving landmarks: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({
            "status": "error",
            "message": f"Server error: {str(e)}"
        }), 500


# ---------------------------------------------------------------------------
# Serve the built React frontend (DEPLOYMENT-ONLY - no app/API logic changes).
# In the Docker image the build is copied to <app>/static; locally it lives at
# ../frontend/build. Override with the FRONTEND_BUILD_DIR env var if needed.
#
# Route ordering / why the API is never shadowed:
#   Flask/Werkzeug matches the most specific rule first, so every registered
#   route (/api/..., /health, /videos/<filename>, etc.) is chosen before this
#   generic /<path:path> catch-all. As a belt-and-suspenders guard, any
#   unregistered /api/* path returns a JSON 404 here instead of index.html.
# ---------------------------------------------------------------------------
def _resolve_frontend_dir():
    env_dir = os.getenv('FRONTEND_BUILD_DIR')
    if env_dir:
        return env_dir
    here = os.path.dirname(os.path.abspath(__file__))
    for candidate in (os.path.join(here, 'static'),                      # Docker image
                      os.path.join(here, '..', 'frontend', 'build')):    # local dev
        if os.path.isdir(candidate):
            return candidate
    return os.path.join(here, 'static')


FRONTEND_BUILD_DIR = _resolve_frontend_dir()


@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve_frontend(path):
    """Serve the React production build. Static assets (JS/CSS/images) are
    returned as-is; any other path falls back to index.html."""
    if path.startswith('api/'):
        return jsonify({'success': False, 'error': 'Not found'}), 404

    file_path = os.path.join(FRONTEND_BUILD_DIR, path)
    if path and os.path.isfile(file_path):
        return send_from_directory(FRONTEND_BUILD_DIR, path)

    index_path = os.path.join(FRONTEND_BUILD_DIR, 'index.html')
    if os.path.isfile(index_path):
        return send_from_directory(FRONTEND_BUILD_DIR, 'index.html')

    return jsonify({'success': False, 'error': 'Frontend build not found'}), 404


# Load artifacts on import for better startup time
load_mlops_artifacts()

if __name__ == '__main__':
    print("Starting Gesture-Ease Backend Server...")
    print("="*70)
    
    word_count = len(LABELS_MAP) if LABELS_MAP else 0
    sample_words = list(LABELS_MAP.values())[:10] if LABELS_MAP else []
    
    print(f"Server ready with {word_count} sign classes")
    print(f"Sample words: {sample_words}")
    print(f"Model loaded: {MODEL_LOADED}")
    print(f"Scaler loaded: {SCALER is not None}")
    print("="*70)
    print("Available endpoints:")
    print("   Status: http://localhost:5000/api/status")
    print("   Search: http://localhost:5000/api/search")
    print("   Words: http://localhost:5000/api/words")
    print("   Predict: http://localhost:5000/api/predict")
    print("   Health: http://localhost:5000/health")
    print("="*70)
    
    # Use Gunicorn in production, Flask dev server locally
    if os.getenv('FLASK_ENV') == 'production':
        print("Production mode - use Gunicorn to start")
        print("   gunicorn -c gunicorn_config.py app:app")
    else:
        print("Development mode - starting Flask dev server")
        app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)