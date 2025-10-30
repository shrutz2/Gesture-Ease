#!/usr/bin/env python3
"""
FIXED Landmark Extraction for Sign Language Recognition
EXACTLY matches frontend extraction method
Extracts landmarks from videos in data/videos/ folder
"""

import cv2
import mediapipe as mp
import numpy as np
import pandas as pd
from pathlib import Path
import argparse
import logging
from tqdm import tqdm
import warnings
warnings.filterwarnings('ignore')

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

class LandmarkExtractor:
    """Landmark extractor matching EXACTLY the frontend method"""
    
    def __init__(self):
        self.mp_hands = mp.solutions.hands
        self.mp_pose = mp.solutions.pose
        self.mp_drawing = mp.solutions.drawing_utils
        
        # EXACT settings as frontend
        self.hands = self.mp_hands.Hands(
            static_image_mode=False,
            max_num_hands=2,
            min_detection_confidence=0.7,  # Match frontend exactly
            min_tracking_confidence=0.5,
            model_complexity=1
        )
        
        # Pose for shoulder detection
        self.pose = self.mp_pose.Pose(
            static_image_mode=False,
            model_complexity=1,
            enable_segmentation=False,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5
        )
        
    def extract_hand_landmarks(self, image):
        """
        Extract hand landmarks EXACTLY as frontend
        Returns: 126-dim vector [left_hand(63), right_hand(63)]
        """
        rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        
        # Detect hands and pose
        hands_results = self.hands.process(rgb_image)
        pose_results = self.pose.process(rgb_image)
        
        # Initialize arrays
        left_hand_landmarks = np.zeros(63)  # 21 * 3
        right_hand_landmarks = np.zeros(63)
        
        h, w = image.shape[:2]
        
        # Get shoulder center (same as frontend default)
        shoulder_x = w / 2
        shoulder_y = h / 3
        
        # If pose detected, use actual shoulders
        if pose_results.pose_landmarks:
            left_shoulder = pose_results.pose_landmarks.landmark[11]
            right_shoulder = pose_results.pose_landmarks.landmark[12]
            shoulder_x = (left_shoulder.x + right_shoulder.x) / 2 * w
            shoulder_y = (left_shoulder.y + right_shoulder.y) / 2 * h
        
        # Process hands
        if hands_results.multi_hand_landmarks and hands_results.multi_handedness:
            for hand_landmarks, handedness in zip(
                hands_results.multi_hand_landmarks, 
                hands_results.multi_handedness
            ):
                hand_label = handedness.classification[0].label
                
                # Extract landmarks
                landmarks = []
                for landmark in hand_landmarks.landmark:
                    # Pixel coordinates
                    x = landmark.x * w
                    y = landmark.y * h
                    z = landmark.z
                    
                    # Normalize EXACTLY like frontend
                    x_norm = (x - shoulder_x) / w
                    y_norm = (y - shoulder_y) / h
                    z_norm = z
                    
                    landmarks.extend([x_norm, y_norm, z_norm])
                
                # Assign to correct hand
                if hand_label == 'Left':
                    left_hand_landmarks = np.array(landmarks)
                else:
                    right_hand_landmarks = np.array(landmarks)
        
        # Combine: left + right = 126 features
        combined = np.concatenate([left_hand_landmarks, right_hand_landmarks])
        return combined, hands_results
    
    def draw_landmarks(self, image, hands_results):
        """Draw GREEN landmarks and connections on BLACK background"""
        # Create black canvas
        h, w = image.shape[:2]
        black_canvas = np.zeros((h, w, 3), dtype=np.uint8)
        
        if not hands_results.multi_hand_landmarks:
            return black_canvas
        
        # Hand connections (MediaPipe standard)
        HAND_CONNECTIONS = [
            (0,1),(1,2),(2,3),(3,4),  # Thumb
            (0,5),(5,6),(6,7),(7,8),  # Index
            (5,9),(9,10),(10,11),(11,12),  # Middle
            (9,13),(13,14),(14,15),(15,16),  # Ring
            (13,17),(17,18),(18,19),(19,20),  # Pinky
            (0,17)  # Palm
        ]
        
        for hand_landmarks in hands_results.multi_hand_landmarks:
            # Get points
            points = []
            for lm in hand_landmarks.landmark:
                x = int(lm.x * w)
                y = int(lm.y * h)
                points.append((x, y))
            
            # Draw GREEN lines
            for start_idx, end_idx in HAND_CONNECTIONS:
                start_pt = points[start_idx]
                end_pt = points[end_idx]
                cv2.line(black_canvas, start_pt, end_pt, (0, 255, 0), 2)
            
            # Draw GREEN dots
            for pt in points:
                cv2.circle(black_canvas, pt, 4, (0, 255, 0), -1)
        
        return black_canvas
    
    def process_video(self, video_path, max_frames=30):
        """
        Process video and extract landmark sequences
        Returns: list of 126-dim vectors (max_frames length)
        """
        cap = cv2.VideoCapture(str(video_path))
        
        if not cap.isOpened():
            logger.warning(f"Could not open: {video_path}")
            return []
        
        landmarks_sequence = []
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        
        # Sample frames uniformly
        if total_frames > max_frames:
            frame_indices = np.linspace(0, total_frames-1, max_frames, dtype=int)
        else:
            frame_indices = list(range(total_frames))
        
        current_frame = 0
        
        while cap.isOpened() and len(landmarks_sequence) < max_frames:
            ret, frame = cap.read()
            if not ret:
                break
            
            if current_frame in frame_indices:
                # Resize for consistency
                frame = cv2.resize(frame, (640, 480))
                
                # Extract landmarks
                landmarks, _ = self.extract_hand_landmarks(frame)
                landmarks_sequence.append(landmarks)
            
            current_frame += 1
        
        cap.release()
        
        # Pad if needed
        while len(landmarks_sequence) < max_frames:
            if landmarks_sequence:
                landmarks_sequence.append(landmarks_sequence[-1])
            else:
                landmarks_sequence.append(np.zeros(126))
        
        return landmarks_sequence[:max_frames]


def main():
    parser = argparse.ArgumentParser(description="Extract landmarks from sign language videos")
    parser.add_argument('--videos_dir', type=str, default='data/videos',
                       help='Directory containing video files')
    parser.add_argument('--output_dir', type=str, default='data/landmarks',
                       help='Output directory for landmark .npy files')
    parser.add_argument('--csv_out', type=str, default='data/data.csv',
                       help='Output CSV manifest')
    parser.add_argument('--max_frames', type=int, default=30,
                       help='Frames per video')
    parser.add_argument('--visualize', action='store_true',
                       help='Save visualization images (green landmarks on black)')
    
    args = parser.parse_args()
    
    videos_dir = Path(args.videos_dir)
    
    # Check videos directory
    if not videos_dir.exists():
        logger.error(f"Videos directory not found: {videos_dir}")
        logger.error("Expected structure: data/videos/*.mp4")
        return
    
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    viz_dir = None
    if args.visualize:
        viz_dir = output_dir / 'visualizations'
        viz_dir.mkdir(exist_ok=True)
    
    extractor = LandmarkExtractor()
    
    # Collect all video files
    video_files = []
    for video_file in videos_dir.glob('*.mp4'):
        # Extract word from filename
        # Format: word.mp4 or word_word(1).mp4
        word = video_file.stem.split('_')[0]
        video_files.append({
            'path': video_file,
            'word': word,
            'video_id': video_file.stem
        })
    
    logger.info(f"Found {len(video_files)} videos")
    
    # Process videos
    manifest_data = []
    
    for video_info in tqdm(video_files, desc="Processing videos"):
        video_path = video_info['path']
        word = video_info['word']
        video_id = video_info['video_id']
        
        # Extract landmarks
        landmarks_seq = extractor.process_video(video_path, args.max_frames)
        
        if landmarks_seq:
            # Save .npy file
            npy_file = output_dir / f"{word}_{video_id}.npy"
            np.save(npy_file, np.array(landmarks_seq))
            
            # Add to manifest
            manifest_data.append({
                'filepath': str(npy_file),
                'label': word,
                'video_id': video_id,
                'num_frames': len(landmarks_seq)
            })
            
            # Save visualization if requested
            if viz_dir:
                # Read video again for visualization
                cap = cv2.VideoCapture(str(video_path))
                ret, frame = cap.read()
                cap.release()
                
                if ret:
                    frame = cv2.resize(frame, (640, 480))
                    _, hands_results = extractor.extract_hand_landmarks(frame)
                    
                    # Draw landmarks on black canvas
                    viz_frame = extractor.draw_landmarks(frame, hands_results)
                    
                    viz_path = viz_dir / f"{word}_{video_id}_landmarks.jpg"
                    cv2.imwrite(str(viz_path), viz_frame)
    
    # Save manifest CSV
    df = pd.DataFrame(manifest_data)
    df.to_csv(args.csv_out, index=False)
    
    logger.info(f"✅ Processing complete!")
    logger.info(f"📊 Processed: {len(manifest_data)} videos")
    logger.info(f"📁 Landmarks: {output_dir}")
    logger.info(f"📋 Manifest: {args.csv_out}")
    
    # Show class distribution
    if not df.empty:
        class_counts = df['label'].value_counts()
        logger.info(f"📈 Top words:")
        for word, count in class_counts.head(10).items():
            logger.info(f"   {word}: {count} samples")


if __name__ == '__main__':
    main()