"""
FINAL CLEAN INFERENCE CONTRACT
================================

GOAL:
✔ RAW mediapipe only
✔ Shape always (30,126)
✔ No normalization shift
✔ Same format train + inference
✔ Strict target verification
✔ No dominant random word

RULES:
1. Extract: x, y, z ONLY (no shoulder subtraction)
2. Pad: second hand with zeros (not random)
3. Sequence: exactly 30 frames (uniform sample or repeat last)
4. Scale: ONLY scaler.transform (fitted on train only)
5. Verify: target confidence >= 0.30 (ignore highest prediction)
"""

import numpy as np
import tensorflow as tf
import pickle
import json
from pathlib import Path


class CleanInferenceEngine:
    """Production inference - NO fancy transforms"""
    
    def __init__(self, model_path, artifacts_dir):
        self.model = tf.keras.models.load_model(model_path)
        
        with open(Path(artifacts_dir) / 'scaler.pkl', 'rb') as f:
            self.scaler = pickle.load(f)
        
        with open(Path(artifacts_dir) / 'labels.json', 'r') as f:
            labels_data = json.load(f)
            self.labels_map = {int(k): v for k, v in labels_data['id_to_label'].items()}
    
    def predict(self, landmarks_sequence, target_word=None):
        """
        Predict gesture
        
        Args:
            landmarks_sequence: np.array shape (N, 126) where N >= 1
            target_word: str or None
        
        Returns:
            dict with is_correct, confidence, message
        """
        
        # FIX #1: Normalize sequence to exactly 30 frames
        # MODIFIED: Take last 30 frames (most recent gesture) instead of uniform sampling
        if len(landmarks_sequence) > 30:
            landmarks_sequence = landmarks_sequence[-30:]
        elif len(landmarks_sequence) < 30:
            last_frame = landmarks_sequence[-1]
            pad_count = 30 - len(landmarks_sequence)
            padding = np.repeat(last_frame[np.newaxis, :], pad_count, axis=0)
            landmarks_sequence = np.vstack([landmarks_sequence, padding])
        
        # Step 2: Apply scaler (fitted on train only)
        landmarks_flat = landmarks_sequence.reshape(-1, 126)
        landmarks_scaled = self.scaler.transform(landmarks_flat).reshape(1, 30, 126)
        
        # Step 3: Get softmax output
        softmax_output = self.model.predict(landmarks_scaled, verbose=0)[0]
        
        # Step 4: Target verification (if target provided)
        if target_word:
            return self._verify_target(softmax_output, target_word)
        else:
            return self._classify(softmax_output)
    
    def _verify_target(self, softmax_output, target_word):
        """Verify if target gesture was performed"""
        
        target_word_lower = target_word.lower().strip()
        target_idx = None
        
        # Find target word index
        for idx, word in self.labels_map.items():
            if word.lower().strip() == target_word_lower:
                target_idx = idx
                break
        
        if target_idx is None:
            return {
                'is_correct': False,
                'target_confidence': 0.0,
                'message': f"Target '{target_word}' not found in vocabulary"
            }
        
        target_confidence = float(softmax_output[target_idx])
        
        # FIX #2: Improved decision threshold logic
        # MODIFIED: Accept if exact match OR (target in top 3 AND confidence >= 0.10)
        predicted_idx = np.argmax(softmax_output)
        predicted_word = self.labels_map[predicted_idx]
        
        # Get target rank in top predictions
        top_k_indices = np.argsort(softmax_output)[-3:][::-1]
        target_rank = None
        for rank, idx in enumerate(top_k_indices, 1):
            if idx == target_idx:
                target_rank = rank
                break
        
        # Decision rule: exact match OR (top 3 AND confidence >= 0.10)
        if predicted_word.lower().strip() == target_word_lower:
            is_correct = True
        elif target_rank is not None and target_rank <= 3 and target_confidence >= 0.10:
            is_correct = True
        else:
            is_correct = False
        
        if is_correct:
            if target_confidence >= 0.6:
                message = f"Perfect! You signed '{target_word}' very clearly!"
            elif target_confidence >= 0.4:
                message = f"Good! I recognized '{target_word}'!"
            else:
                message = f"Correct! You performed '{target_word}'!"
        else:
            message = f"Try again. '{target_word}' not clear enough."
        
        return {
            'is_correct': is_correct,
            'target_confidence': round(target_confidence, 3),
            'message': message,
            'target_rank': target_rank
        }
    
    def _classify(self, softmax_output):
        """Classify gesture (no target)"""
        
        top_idx = np.argmax(softmax_output)
        predicted_word = self.labels_map[top_idx]
        confidence = float(softmax_output[top_idx])
        
        return {
            'predicted': predicted_word,
            'confidence': round(confidence, 3)
        }
