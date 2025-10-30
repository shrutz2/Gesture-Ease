"""
Process video files into landmark .npy samples compatible with dataset/landmarks format.

Usage (from backend/):
  python scripts/videos_to_landmarks.py --input-dir ../my_videos --output-dir ../dataset/landmarks --frames 40

Options:
  --input-dir PATH   directory containing video files (mp4/mov/avi/mkv)
  --output-dir PATH  base output directory for per-label npy files (default ../dataset/landmarks)
  --frames N         number of frames per sample (default 40)
  --label-from-filename  derive label from filename before first '_' or '-' or '.'
  --camera IDX       (not used) kept for parity with other scripts

Notes:
- This script imports `EnhancedLandmarkExtractor` from `app.py` to ensure exact same extraction logic.
- For each video, it samples `frames` frames uniformly across the video and saves a single .npy array of shape (frames, FEATURE_DIM) in `output-dir/<label>/`.
- Filenames are saved as `<label> (1).npy`, `<label> (2).npy` etc.
"""

import argparse
from pathlib import Path
import numpy as np
import cv2
import math
import sys

try:
    from app import EnhancedLandmarkExtractor, FEATURE_DIM
except Exception as e:
    raise SystemExit("Failed to import EnhancedLandmarkExtractor from app.py. Run this from the backend directory. Error: %s" % e)


VIDEO_EXTS = ['.mp4', '.mov', '.avi', '.mkv', '.MP4', '.MOV', '.AVI', '.MKV']


def list_videos(folder: Path):
    return [p for p in folder.iterdir() if p.is_file() and p.suffix in VIDEO_EXTS]


def next_index_for_label(folder: Path, label: str):
    existing = [p.name for p in folder.glob(f"{label}*.npy")]
    max_i = 0
    for name in existing:
        try:
            base = name.rsplit('.', 1)[0]
            if '(' in base and base.endswith(')'):
                i = int(base.split('(')[-1].rstrip(')'))
                if i > max_i:
                    max_i = i
        except Exception:
            continue
    return max_i + 1


def sample_frame_indices(total_frames: int, desired: int):
    if total_frames <= 0:
        return []
    if total_frames <= desired:
        # repeat last frame to pad
        indices = list(range(total_frames))
        while len(indices) < desired:
            indices.append(indices[-1])
        return indices[:desired]
    # uniform sampling
    return [int(round(i)) for i in np.linspace(0, total_frames - 1, desired)]


def process_video(video_path: Path, extractor: EnhancedLandmarkExtractor, frames_needed: int):
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        print(f"Failed to open video: {video_path}")
        return None

    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    if total <= 0:
        # Fallback: read all frames into list
        frames = []
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            frames.append(frame)
        total = len(frames)
        if total == 0:
            cap.release()
            return None
        indices = sample_frame_indices(total, frames_needed)
        sampled = []
        for idx in indices:
            frame = frames[idx]
            frame = cv2.resize(frame, (640, 480))
            landmark_vector, _, _ = extractor.extract_hand_landmarks(frame)
            if landmark_vector is None or landmark_vector.shape[0] != FEATURE_DIM:
                landmark_vector = np.zeros(FEATURE_DIM, dtype=np.float32)
            sampled.append(landmark_vector.astype(np.float32))
        cap.release()
        return np.stack(sampled, axis=0)

    indices = sample_frame_indices(total, frames_needed)
    sampled = []
    for idx in indices:
        cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
        ret, frame = cap.read()
        if not ret:
            # pad with zeros
            sampled.append(np.zeros(FEATURE_DIM, dtype=np.float32))
            continue
        frame = cv2.resize(frame, (640, 480))
        landmark_vector, _, _ = extractor.extract_hand_landmarks(frame)
        if landmark_vector is None or landmark_vector.shape[0] != FEATURE_DIM:
            landmark_vector = np.zeros(FEATURE_DIM, dtype=np.float32)
        sampled.append(landmark_vector.astype(np.float32))

    cap.release()
    return np.stack(sampled, axis=0)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--input-dir', required=True, help='Directory with video files')
    parser.add_argument('--output-dir', default='../dataset/landmarks', help='Base output dir')
    parser.add_argument('--frames', type=int, default=40, help='Frames per sample')
    parser.add_argument('--label-from-filename', action='store_true', help='Derive label from filename before separators')
    args = parser.parse_args()

    input_dir = Path(args.input_dir).resolve()
    out_base = Path(args.output_dir).resolve()

    if not input_dir.exists():
        raise SystemExit(f"Input directory does not exist: {input_dir}")

    extractor = EnhancedLandmarkExtractor()

    videos = list_videos(input_dir)
    if not videos:
        print("No video files found in", input_dir)
        return

    print(f"Found {len(videos)} videos. Processing...")

    for video in videos:
        name = video.stem
        if args.label_from_filename:
            # label is substring before first '_' or '-' or '.'
            for sep in ['_', '-', '.']:
                if sep in name:
                    name = name.split(sep)[0]
                    break
        label_dir = out_base / name
        label_dir.mkdir(parents=True, exist_ok=True)

        sample_idx = next_index_for_label(label_dir, name)
        print(f"Processing {video.name} -> label '{name}' (saving as {name} ({sample_idx}).npy)")

        arr = process_video(video, extractor, frames_needed=args.frames)
        if arr is None:
            print(f"Failed to process {video.name}")
            continue

        out_path = label_dir / f"{name} ({sample_idx}).npy"
        np.save(out_path, arr.astype(np.float32))
        print(f"Saved landmarks to {out_path}")


if __name__ == '__main__':
    main()
