#!/usr/bin/env python3
"""
Confidence Calibration Analysis
Analyzes model confidence on validation set to recommend optimal threshold
"""

import numpy as np
import tensorflow as tf
from sklearn.preprocessing import RobustScaler, LabelEncoder
from sklearn.model_selection import train_test_split
from pathlib import Path
import pickle
import json
import sys

def calibrate_threshold():
    """Analyze confidence distribution and recommend optimal threshold"""
    
    print("\n" + "="*70)
    print("CONFIDENCE CALIBRATION ANALYSIS")
    print("="*70 + "\n")
    
    # Load model
    model_path = Path('models/best_model.h5')
    if not model_path.exists():
        print(f"[ERROR] Model not found at {model_path}")
        return False
    
    try:
        model = tf.keras.models.load_model(str(model_path))
        print(f"[OK] Loaded model from {model_path}")
    except Exception as e:
        print(f"[ERROR] Failed to load model: {e}")
        return False
    
    # Load scaler
    scaler_path = Path('artifacts/scaler.pkl')
    if not scaler_path.exists():
        print(f"[ERROR] Scaler not found at {scaler_path}")
        return False
    
    try:
        with open(scaler_path, 'rb') as f:
            scaler = pickle.load(f)
        print(f"[OK] Loaded scaler from {scaler_path}")
    except Exception as e:
        print(f"[ERROR] Failed to load scaler: {e}")
        return False
    
    # Load label encoder
    encoder_path = Path('artifacts/label_encoder.pkl')
    if not encoder_path.exists():
        print(f"[ERROR] Label encoder not found at {encoder_path}")
        return False
    
    try:
        with open(encoder_path, 'rb') as f:
            label_encoder = pickle.load(f)
        print(f"[OK] Loaded label encoder from {encoder_path}")
    except Exception as e:
        print(f"[ERROR] Failed to load label encoder: {e}")
        return False
    
    # Load dataset
    print(f"\n[LOADING] Loading dataset...")
    dataset_path = Path('dataset')
    X_list, y_list = [], []
    
    for word_folder in sorted(dataset_path.iterdir()):
        if not word_folder.is_dir():
            continue
        word = word_folder.name
        for npy_file in word_folder.glob('*.npy'):
            data = np.load(npy_file)
            if data.shape == (30, 126):
                X_list.append(data)
                y_list.append(word)
    
    X = np.array(X_list, dtype=np.float32)
    y = np.array(y_list)
    print(f"[OK] Loaded {len(X)} samples, {len(np.unique(y))} classes")
    
    # Split data (same as train_model.py)
    X_temp, X_test, y_temp, y_test = train_test_split(X, y, test_size=0.2, stratify=y, random_state=42)
    X_train, X_val, y_train, y_val = train_test_split(X_temp, y_temp, test_size=0.25, stratify=y_temp, random_state=42)
    
    print(f"[OK] Split data: Train={len(X_train)}, Val={len(X_val)}, Test={len(X_test)}")
    
    # Normalize validation set
    X_val_normalized = scaler.transform(X_val.reshape(-1, 126)).reshape(X_val.shape)
    
    # Encode validation labels
    y_val_enc = label_encoder.transform(y_val)
    
    # Get predictions on validation set
    print(f"\n[PREDICTING] Running model on validation set ({len(X_val)} samples)...")
    predictions = model.predict(X_val_normalized, verbose=0)
    
    # Extract true class confidence
    correct_confidences = []
    wrong_confidences = []
    
    for i, (pred, true_label) in enumerate(zip(predictions, y_val_enc)):
        true_confidence = float(pred[true_label])
        predicted_label = np.argmax(pred)
        is_correct = (predicted_label == true_label)
        
        if is_correct:
            correct_confidences.append(true_confidence)
        else:
            wrong_confidences.append(true_confidence)
    
    print(f"[OK] Analyzed {len(predictions)} predictions")
    print(f"    Correct predictions: {len(correct_confidences)}")
    print(f"    Wrong predictions: {len(wrong_confidences)}")
    
    # Compute statistics
    print(f"\n[STATISTICS]")
    
    if correct_confidences:
        mean_correct = np.mean(correct_confidences)
        min_correct = np.min(correct_confidences)
        max_correct = np.max(correct_confidences)
        std_correct = np.std(correct_confidences)
        print(f"\n  Correct Predictions ({len(correct_confidences)} samples):")
        print(f"    Mean confidence:  {mean_correct:.4f}")
        print(f"    Min confidence:   {min_correct:.4f}")
        print(f"    Max confidence:   {max_correct:.4f}")
        print(f"    Std deviation:    {std_correct:.4f}")
    else:
        print(f"\n  [WARNING] No correct predictions found")
        return False
    
    if wrong_confidences:
        mean_wrong = np.mean(wrong_confidences)
        min_wrong = np.min(wrong_confidences)
        max_wrong = np.max(wrong_confidences)
        std_wrong = np.std(wrong_confidences)
        print(f"\n  Wrong Predictions ({len(wrong_confidences)} samples):")
        print(f"    Mean confidence:  {mean_wrong:.4f}")
        print(f"    Min confidence:   {min_wrong:.4f}")
        print(f"    Max confidence:   {max_wrong:.4f}")
        print(f"    Std deviation:    {std_wrong:.4f}")
    else:
        print(f"\n  [WARNING] No wrong predictions found")
    
    # Recommend threshold
    print(f"\n[THRESHOLD ANALYSIS]")
    print(f"  Current threshold: 0.30")
    print(f"  Min(correct):      {min_correct:.4f}")
    print(f"  Max(wrong):        {max_wrong:.4f}")
    
    if min_correct > max_wrong:
        optimal_threshold = (min_correct + max_wrong) / 2
        gap = min_correct - max_wrong
        print(f"\n  ✓ GOOD SEPARATION - Classes are well-separated")
        print(f"    Gap between min(correct) and max(wrong): {gap:.4f}")
        print(f"    Recommended threshold: {optimal_threshold:.4f}")
        print(f"    (Midpoint between {min_correct:.4f} and {max_wrong:.4f})")
    else:
        print(f"\n  ✗ POOR SEPARATION - Overlap detected")
        print(f"    Min(correct) {min_correct:.4f} ≤ Max(wrong) {max_wrong:.4f}")
        print(f"    Classes are not well-separated")
        optimal_threshold = (mean_correct + mean_wrong) / 2
        print(f"    Using mean-based threshold: {optimal_threshold:.4f}")
    
    # Validation accuracy at different thresholds
    print(f"\n[THRESHOLD PERFORMANCE]")
    thresholds = [0.20, 0.25, 0.30, 0.35, 0.40, 0.50, optimal_threshold]
    
    for threshold in sorted(set(thresholds)):
        correct_count = sum(1 for conf in correct_confidences if conf >= threshold)
        wrong_count = sum(1 for conf in wrong_confidences if conf < threshold)
        accuracy = (correct_count + wrong_count) / (len(correct_confidences) + len(wrong_confidences))
        print(f"  Threshold {threshold:.4f}: {accuracy:.4f} accuracy ({correct_count + wrong_count}/{len(correct_confidences) + len(wrong_confidences)} correct)")
    
    print(f"\n[RECOMMENDATION]")
    print(f"  Use threshold: {optimal_threshold:.4f}")
    print(f"  Current threshold (0.30) vs Optimal ({optimal_threshold:.4f})")
    if optimal_threshold > 0.30:
        print(f"  → Increase threshold by {optimal_threshold - 0.30:.4f} for better precision")
    elif optimal_threshold < 0.30:
        print(f"  → Decrease threshold by {0.30 - optimal_threshold:.4f} for better recall")
    else:
        print(f"  → Current threshold is already optimal")
    
    print("\n" + "="*70 + "\n")
    return True


if __name__ == '__main__':
    try:
        success = calibrate_threshold()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n[FATAL ERROR] {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
