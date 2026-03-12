# CLEAN WORKFLOW - 5 FILES ONLY

## 📋 Essential Files

1. **extract_raw_landmarks.py** - Extract landmarks from videos
2. **verify_landmarks.py** - Verify landmarks are RAW
3. **train_model.py** - Train the model
4. **inference.py** - Test inference
5. **app.py** - Flask backend (already exists)

## 🚀 Quick Start

```bash
# Step 1: Extract landmarks
python backend/extract_raw_landmarks.py

# Step 2: Verify
python backend/verify_landmarks.py

# Step 3: Train
python backend/train_model.py

# Step 4: Test
python backend/inference.py --video test.mp4 --target "hello"

# Step 5: Run Flask
python backend/app.py
```

## ✅ Done!
