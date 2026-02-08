"""Data models and prediction logic"""

import numpy as np
from dataclasses import dataclass
from typing import List, Dict, Optional

@dataclass
class PredictionResult:
    """Prediction result structure"""
    is_correct: bool
    predicted_word: str
    confidence: float
    points: int
    message: str
    top_predictions: List[Dict]
    debug_info: Optional[Dict] = None

class GesturePredictor:
    """Handles gesture prediction logic"""
    
    def __init__(self, model, scaler, labels_map):
        self.model = model
        self.scaler = scaler
        self.labels_map = labels_map
        self.sequence_length = 30
        self.feature_dim = 126
    
    def predict(self, landmarks_sequence: np.ndarray, target_word: str) -> PredictionResult:
        """
        Predict gesture from landmarks sequence
        
        Args:
            landmarks_sequence: Array of shape (N, 126) with landmark vectors
            target_word: Expected word for comparison
            
        Returns:
            PredictionResult with prediction details
        """
        # Ensure correct sequence length
        if len(landmarks_sequence) > self.sequence_length:
            indices = np.linspace(0, len(landmarks_sequence)-1, self.sequence_length, dtype=int)
            landmarks_sequence = landmarks_sequence[indices]
        elif len(landmarks_sequence) < self.sequence_length:
            padding = np.repeat(landmarks_sequence[-1:], self.sequence_length - len(landmarks_sequence), axis=0)
            landmarks_sequence = np.vstack([landmarks_sequence, padding])
        
        # Normalize
        sequence_flat = landmarks_sequence.reshape(-1, self.feature_dim)
        sequence_normalized = self.scaler.transform(sequence_flat)
        sequence_processed = sequence_normalized.reshape(1, self.sequence_length, self.feature_dim)
        
        # Get predictions
        prediction_probs = self.model.predict(sequence_processed, verbose=0)[0]
        
        # Get top 5 predictions
        top_k_indices = np.argsort(prediction_probs)[::-1][:5]
        top_predictions = []
        for idx in top_k_indices:
            label = self.labels_map.get(idx, f"Unknown_{idx}")
            confidence = float(prediction_probs[idx])
            top_predictions.append({"word": label, "confidence": confidence})
        
        # Best prediction
        best_pred = top_predictions[0]
        predicted_word = best_pred["word"]
        confidence = best_pred["confidence"]
        
        # Check correctness
        is_correct = predicted_word.lower() == target_word.lower()
        
        # Calculate points
        points = self._calculate_points(is_correct, confidence)
        
        # Generate message
        message = self._generate_message(is_correct, predicted_word, target_word, confidence)
        
        return PredictionResult(
            is_correct=is_correct,
            predicted_word=predicted_word,
            confidence=confidence,
            points=points,
            message=message,
            top_predictions=top_predictions[:3],
            debug_info={
                "method": "direct_landmarks",
                "frames_used": self.sequence_length,
                "confidence_threshold": 0.25
            }
        )
    
    def _calculate_points(self, is_correct: bool, confidence: float) -> int:
        """Calculate points based on correctness and confidence"""
        if not is_correct:
            return 0
        
        if confidence > 0.5:
            return 15 + int(confidence * 10)
        elif confidence > 0.3:
            return 10
        else:
            return 5
    
    def _generate_message(self, is_correct: bool, predicted: str, target: str, confidence: float) -> str:
        """Generate user-friendly feedback message"""
        if is_correct:
            if confidence > 0.6:
                return f"Excellent! You signed '{predicted}' perfectly!"
            elif confidence > 0.4:
                return f"Good! You signed '{predicted}' correctly!"
            else:
                return f"Correct! '{predicted}' recognized!"
        else:
            return f"Try again! AI detected '{predicted}' but expected '{target}'"