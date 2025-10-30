"""
Record webcam samples and extract landmarks, saving .npy files compatible with dataset/landmarks format.

Usage examples (from project root):
  cd backend
  C:/Users/LENOVO/AppData/Local/Programs/Python/Python311/python.exe scripts/record_landmarks.py --label hello --samples 5

Options:
  --label LABEL        word/class name to save samples under (required)
  --samples N          number of samples to record (default: 5)
  --frames F           frames per sample (default: 40)
  --output-dir PATH    base output dir (default: ../dataset/landmarks)
  --auto               auto-record samples with countdown (no keypress)
  --camera IDX         camera index for cv2.VideoCapture (default 0)

This script imports the `EnhancedLandmarkExtractor` from `backend/app.py` to ensure landmarks are extracted the same way the server does.
"""

import argparse
import os
import time
import numpy as np
import cv2
from pathlib import Path

# Import the landmark extractor implemented in app.py
# Run this script from backend/ (or ensure backend is on PYTHONPATH)
try:
    from app import EnhancedLandmarkExtractor, FEATURE_DIM
except Exception as e:
    raise SystemExit("Failed to import EnhancedLandmarkExtractor from app.py. Run this script from the backend directory. Error: %s" % e)


def next_index_for_label(folder: Path, label: str):
    existing = [p.name for p in folder.glob(f"{label}*.npy")]
    # Files follow pattern: label (1).npy etc. Find next integer
    max_i = 0
    for name in existing:
        # try to extract (N)
        try:
            base = name.rsplit('.', 1)[0]
            if '(' in base and base.endswith(')'):
                i = int(base.split('(')[-1].rstrip(')'))
                if i > max_i:
                    max_i = i
        except Exception:
            continue
    return max_i + 1


def ensure_dir(p: Path):
    p.mkdir(parents=True, exist_ok=True)


def record_sample(cap, extractor, frames_needed: int, show_window=True):
    frames = []
    count = 0
    while count < frames_needed:
        ret, frame = cap.read()
        if not ret:
            print("Failed to read frame from camera")
            break

        # Resize for consistent extraction (same as server)
        frame = cv2.resize(frame, (640, 480))
        landmark_vector, hands_detected, hands_results = extractor.extract_hand_landmarks(frame)

        # If extractor returns None or wrong shape, fallback to zeros
        if landmark_vector is None or landmark_vector.shape[0] != FEATURE_DIM:
            landmark_vector = np.zeros(FEATURE_DIM, dtype=np.float32)
        frames.append(landmark_vector.astype(np.float32))

        # Create display overlay with colored left/right hands and connections
        display = frame.copy()
        try:
            if hands_results and getattr(hands_results, 'multi_hand_landmarks', None):
                for hand_landmarks, handedness in zip(hands_results.multi_hand_landmarks, hands_results.multi_handedness):
                    label = handedness.classification[0].label if handedness and hasattr(handedness, 'classification') else 'Right'
                    color = (0,255,0) if label == 'Left' else (0,0,255)
                    # draw landmarks and connections with color
                    extractor.mp_drawing.draw_landmarks(
                        display, hand_landmarks, extractor.mp_hands.HAND_CONNECTIONS,
                        extractor.mp_drawing.DrawingSpec(color=color, thickness=2, circle_radius=4),
                        extractor.mp_drawing.DrawingSpec(color=color, thickness=2)
                    )

            cv2.putText(display, f"Recording: {count+1}/{frames_needed}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255,255,255), 2)

            # Zoom preview - crop around landmarks if available
            zoom = None
            if hands_results and getattr(hands_results, 'multi_hand_landmarks', None):
                xs, ys = [], []
                for hand_landmarks in hands_results.multi_hand_landmarks:
                    for lm in hand_landmarks.landmark:
                        h, w = display.shape[:2]
                        xs.append(int(lm.x * w)); ys.append(int(lm.y * h))
                if xs and ys:
                    x1, x2 = max(0, min(xs)-40), min(display.shape[1]-1, max(xs)+40)
                    y1, y2 = max(0, min(ys)-40), min(display.shape[0]-1, max(ys)+40)
                    zoom = cv2.resize(display[y1:y2, x1:x2], (320,320)) if (y2>y1 and x2>x1) else None

            if show_window:
                cv2.imshow('Recording - press q to abort', display)
                if zoom is not None:
                    cv2.imshow('Zoom (hands)', zoom)
                else:
                    # close zoom window if previously open
                    cv2.destroyWindow('Zoom (hands)')
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    print('User requested abort')
                    return None
        except Exception as e:
            # if any overlay error occurs, fallback to simple display
            cv2.putText(display, f"Recording: {count+1}/{frames_needed}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255,255,255), 2)
            if show_window:
                cv2.imshow('Recording - press q to abort', display)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    print('User requested abort')
                    return None

        count += 1

    cv2.destroyAllWindows()
    if len(frames) != frames_needed:
        return None
    return np.stack(frames, axis=0)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--label', required=True, help='Label/word for the samples')
    parser.add_argument('--samples', type=int, default=5, help='Number of samples to record')
    parser.add_argument('--frames', type=int, default=40, help='Frames per sample')
    parser.add_argument('--output-dir', default='../dataset/landmarks', help='Base output dir')
    parser.add_argument('--auto', action='store_true', help='Auto-record samples with countdown')
    parser.add_argument('--camera', type=int, default=0, help='Camera index for cv2')

    args = parser.parse_args()

    base_out = Path(args.output_dir).resolve()
    label_dir = base_out / args.label
    ensure_dir(label_dir)

    extractor = EnhancedLandmarkExtractor()

    cap = cv2.VideoCapture(args.camera)
    if not cap.isOpened():
        raise SystemExit(f"Cannot open camera index {args.camera}")

    print(f"Ready to record {args.samples} samples for label '{args.label}' into: {label_dir}")
    print("Press Ctrl+C to quit at any time.")

    try:
        for s in range(args.samples):
            start_index = next_index_for_label(label_dir, args.label)

            if args.auto:
                # countdown 3 seconds
                for i in range(3, 0, -1):
                    print(f"Recording sample {s+1}/{args.samples} in {i}...")
                    time.sleep(1)
            else:
                input(f"Press Enter to start recording sample {s+1}/{args.samples} (or Ctrl+C to cancel)")

            print(f"Recording sample {s+1}/{args.samples} - collect {args.frames} frames...")
            sample = record_sample(cap, extractor, frames_needed=args.frames, show_window=True)

            if sample is None:
                print("Sample aborted or failed — skipping")
                continue

            out_name = f"{args.label} ({start_index}).npy"
            out_path = label_dir / out_name
            np.save(out_path, sample.astype(np.float32))
            print(f"Saved sample to {out_path}")

    except KeyboardInterrupt:
        print('\nRecording interrupted by user')
    finally:
        cap.release()
        cv2.destroyAllWindows()


if __name__ == '__main__':
    main()
