#!/usr/bin/env python3
"""
Emergency Fix: Generate missing scaler.pkl from existing data
Run this when model exists but scaler is missing
"""

import numpy as np
import pickle
import json
from pathlib import Path
from sklearn.preprocessing import RobustScaler, StandardScaler
import pandas as pd
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

def generate_missing_scaler():
    """Generate scaler.pkl from existing landmark data"""
    
    print("="*60)
    print("🔧 GENERATING MISSING SCALER")
    print("="*60)
    
    # Create directories if they don't exist
    artifacts_dir = Path('artifacts')
    artifacts_dir.mkdir(exist_ok=True)
    
    # Check if scaler already exists
    scaler_path = artifacts_dir / 'scaler.pkl'
    if scaler_path.exists():
        print(f"✅ Scaler already exists at {scaler_path}")
        response = input("Overwrite? (y/n): ")
        if response.lower() != 'y':
            return
    
    # Load data manifest
    csv_path = Path('data/data.csv')
    if not csv_path.exists():
        print("❌ data/data.csv not found!")
        print("Creating scaler from scratch...")
        
        # Create a default scaler with expected ranges
        scaler = StandardScaler()
        
        # Generate dummy data with expected ranges for landmarks
        # 30 frames x 126 features (2 hands x 21 landmarks x 3 coords)
        dummy_data = np.random.randn(1000, 126) * 0.2 + 0.5  # Centered around 0.5
        dummy_data = np.clip(dummy_data, 0, 1)  # Landmark coords are typically 0-1
        
        scaler.fit(dummy_data)
        
        # Save scaler
        with open(scaler_path, 'wb') as f:
            pickle.dump(scaler, f)
        
        print(f"✅ Default scaler saved to {scaler_path}")
        
    else:
        print(f"✅ Found data manifest: {csv_path}")
        
        # Load all landmark files
        df = pd.read_csv(csv_path)
        all_landmarks = []
        
        print(f"Loading {len(df)} landmark files...")
        
        for _, row in df.iterrows():
            filepath = row['filepath']
            
            try:
                # Load landmark file
                data = np.load(filepath)
                
                # Handle different formats
                if 'landmarks' in data.files:
                    landmarks = data['landmarks']
                elif 'arr_0' in data.files:
                    landmarks = data['arr_0']
                else:
                    landmarks = data[data.files[0]]
                
                # Flatten sequences for scaler fitting
                if landmarks.ndim == 2:
                    all_landmarks.extend(landmarks)
                elif landmarks.ndim == 3:
                    for frame in landmarks:
                        all_landmarks.extend(frame)
                        
            except Exception as e:
                print(f"⚠️ Error loading {filepath}: {e}")
                continue
        
        if not all_landmarks:
            print("❌ No landmarks could be loaded!")
            print("Creating default scaler instead...")
            
            # Create default scaler
            scaler = StandardScaler()
            dummy_data = np.random.randn(1000, 126) * 0.2 + 0.5
            dummy_data = np.clip(dummy_data, 0, 1)
            scaler.fit(dummy_data)
        else:
            print(f"✅ Loaded {len(all_landmarks)} landmark frames")
            
            # Convert to numpy array
            X = np.array(all_landmarks)
            
            # Ensure correct shape
            if X.shape[1] != 126:
                print(f"⚠️ Warning: Expected 126 features, got {X.shape[1]}")
                if X.shape[1] > 126:
                    X = X[:, :126]
                else:
                    # Pad with zeros
                    padding = np.zeros((X.shape[0], 126 - X.shape[1]))
                    X = np.hstack([X, padding])
            
            # Create and fit scaler
            print("Fitting scaler...")
            scaler = RobustScaler()  # More robust to outliers
            scaler.fit(X)
            
            print(f"✅ Scaler fitted on {X.shape} data")
        
        # Save scaler
        with open(scaler_path, 'wb') as f:
            pickle.dump(scaler, f)
        
        print(f"✅ Scaler saved to {scaler_path}")
    
    # Generate label encoder if missing
    label_encoder_path = artifacts_dir / 'label_encoder.pkl'
    if not label_encoder_path.exists():
        print("\n🔧 Generating label encoder...")
        
        from sklearn.preprocessing import LabelEncoder
        
        # Get unique labels from CSV or create defaults
        if csv_path.exists():
            df = pd.read_csv(csv_path)
            unique_labels = df['label'].unique()
        else:
            # Default labels
            unique_labels = ['hello', 'today', 'thanks', 'please', 'yes', 
                           'no', 'good', 'bad', 'help', 'sorry']
        
        label_encoder = LabelEncoder()
        label_encoder.fit(unique_labels)
        
        with open(label_encoder_path, 'wb') as f:
            pickle.dump(label_encoder, f)
        
        print(f"✅ Label encoder saved with {len(unique_labels)} classes")
        
        # Also save as JSON for reference
        labels_json = {
            'classes': list(unique_labels),
            'num_classes': len(unique_labels)
        }
        
        with open(artifacts_dir / 'labels.json', 'w') as f:
            json.dump(labels_json, f, indent=2)
        
        print(f"✅ Labels saved to labels.json")
    
    # Generate class weights if missing
    weights_path = artifacts_dir / 'class_weights.json'
    if not weights_path.exists():
        print("\n🔧 Generating class weights...")
        
        # Equal weights for all classes
        if csv_path.exists():
            df = pd.read_csv(csv_path)
            class_counts = df['label'].value_counts()
            
            # Calculate balanced weights
            total_samples = len(df)
            n_classes = len(class_counts)
            
            class_weights = {}
            for label, count in class_counts.items():
                weight = total_samples / (n_classes * count)
                class_weights[label] = float(weight)
        else:
            # Default equal weights
            class_weights = {label: 1.0 for label in unique_labels}
        
        with open(weights_path, 'w') as f:
            json.dump(class_weights, f, indent=2)
        
        print(f"✅ Class weights saved")
    
    print("\n" + "="*60)
    print("✅ ALL ARTIFACTS GENERATED SUCCESSFULLY!")
    print("="*60)
    print("\n📁 Generated files:")
    print(f"  - {scaler_path}")
    print(f"  - {label_encoder_path}")
    print(f"  - {artifacts_dir / 'labels.json'}")
    print(f"  - {weights_path}")
    print("\n🚀 Now run: python app.py")
    

def check_existing_files():
    """Check what files exist"""
    print("\n📁 Checking existing files...")
    
    paths_to_check = [
        'models/model.keras',
        'models/model.h5',
        'models/best_model.h5',
        'artifacts/scaler.pkl',
        'artifacts/label_encoder.pkl',
        'artifacts/labels.json',
        'artifacts/class_weights.json',
        'data/data.csv'
    ]
    
    for path_str in paths_to_check:
        path = Path(path_str)
        if path.exists():
            size = path.stat().st_size / 1024  # KB
            print(f"  ✅ {path_str} ({size:.1f} KB)")
        else:
            print(f"  ❌ {path_str}")
    

if __name__ == "__main__":
    print("\n🔍 SCALER GENERATION TOOL")
    print("="*60)
    
    # Check existing files
    check_existing_files()
    
    print("\nOptions:")
    print("1. Generate missing scaler from data")
    print("2. Create default scaler (if no data available)")
    print("3. Exit")
    
    choice = input("\nEnter choice (1/2/3): ")
    
    if choice == '1' or choice == '2':
        generate_missing_scaler()
    else:
        print("Exiting...")