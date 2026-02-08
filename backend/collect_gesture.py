import cv2
import numpy as np
import mediapipe as mp
import os
import argparse
import time

# =========================
# CONFIG
# =========================
SEQUENCE_LENGTH = 30
FEATURES_PER_FRAME = 126  # 2 hands x 21 landmarks x (x,y,z)
DATASET_DIR = "dataset"

# =========================
# ARGUMENTS
# =========================
parser = argparse.ArgumentParser()
parser.add_argument("--word", required=True, help="Gesture word label")
parser.add_argument("--samples", type=int, default=20, help="Number of samples")
args = parser.parse_args()

WORD = args.word.lower()
TOTAL_SAMPLES = args.samples

# =========================
# SETUP DATASET FOLDER
# =========================
word_dir = os.path.join(DATASET_DIR, WORD)
os.makedirs(word_dir, exist_ok=True)

existing = len([f for f in os.listdir(word_dir) if f.endswith(".npy")])
sample_counter = existing

# =========================
# MEDIAPIPE
# =========================
mp_hands = mp.solutions.hands
mp_draw = mp.solutions.drawing_utils

hands = mp_hands.Hands(
    static_image_mode=False,
    max_num_hands=2,
    min_detection_confidence=0.6,
    min_tracking_confidence=0.6
)

# =========================
# CAMERA
# =========================
cap = cv2.VideoCapture(0)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

print(f"\n[MOVIE_CAMERA] Collecting gesture: '{WORD}'")
print("Controls:")
print("  ENTER  → start sample")
print("  ESC    → exit\n")

# =========================
# HELPERS
# =========================
def extract_landmarks(results):
    landmarks = np.zeros((2, 21, 3))  # 2 hands

    if results.multi_hand_landmarks:
        for i, hand in enumerate(results.multi_hand_landmarks):
            if i >= 2:
                break
            for j, lm in enumerate(hand.landmark):
                landmarks[i, j] = [lm.x, lm.y, lm.z]

    return landmarks.reshape(-1)  # (126,)

def draw_landmarks(frame, results):
    if results.multi_hand_landmarks:
        for hand in results.multi_hand_landmarks:
            mp_draw.draw_landmarks(
                frame,
                hand,
                mp_hands.HAND_CONNECTIONS,
                mp_draw.DrawingSpec(color=(0, 255, 0), thickness=2, circle_radius=3),
                mp_draw.DrawingSpec(color=(0, 255, 0), thickness=2)
            )

# =========================
# MAIN LOOP
# =========================
current_sample = 0

while current_sample < TOTAL_SAMPLES:
    frames = []
    recording = False

    while True:
        ret, frame = cap.read()
        if not ret:
            continue

        frame = cv2.flip(frame, 1)
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = hands.process(rgb)

        draw_landmarks(frame, results)

        cv2.putText(
            frame,
            f"Sample {current_sample+1}/{TOTAL_SAMPLES}",
            (10, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            1,
            (255, 255, 255),
            2
        )

        cv2.putText(
            frame,
            "Press ENTER to record | ESC to quit",
            (10, 460),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (200, 200, 200),
            1
        )

        cv2.imshow("Gesture Recorder", frame)
        key = cv2.waitKey(1)

        # ESC
        if key == 27:
            cap.release()
            cv2.destroyAllWindows()
            print("👋 Exit")
            exit()

        # ENTER → countdown + record
        if key == 13:
            # -------- COUNTDOWN --------
            for i in [3, 2, 1]:
                ret, frame = cap.read()
                frame = cv2.flip(frame, 1)
                cv2.putText(
                    frame,
                    f"Starting in {i}",
                    (180, 240),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    2,
                    (0, 255, 255),
                    4
                )
                cv2.imshow("Gesture Recorder", frame)
                cv2.waitKey(1000)

            ret, frame = cap.read()
            frame = cv2.flip(frame, 1)
            cv2.putText(
                frame,
                "GO!",
                (250, 240),
                cv2.FONT_HERSHEY_SIMPLEX,
                2,
                (0, 255, 0),
                4
            )
            cv2.imshow("Gesture Recorder", frame)
            cv2.waitKey(500)

            # -------- RECORDING --------
            while len(frames) < SEQUENCE_LENGTH:
                ret, frame = cap.read()
                frame = cv2.flip(frame, 1)
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                results = hands.process(rgb)

                draw_landmarks(frame, results)

                landmarks = extract_landmarks(results)
                frames.append(landmarks)

                cv2.putText(
                    frame,
                    f"Recording {len(frames)}/{SEQUENCE_LENGTH}",
                    (180, 30),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    1,
                    (0, 0, 255),
                    2
                )

                cv2.imshow("Gesture Recorder", frame)
                cv2.waitKey(1)

            break 

    # =========================
    # SAVE SAMPLE
    # =========================
    frames = np.array(frames)  # (30, 126)
    filename = f"{WORD}_{sample_counter:03d}.npy"
    np.save(os.path.join(word_dir, filename), frames)

    print(f"[CHECK] Saved: {filename}")

    sample_counter += 1
    current_sample += 1

print("\n[PARTY_POPPER] Data collection complete!")
cap.release()
cv2.destroyAllWindows()
