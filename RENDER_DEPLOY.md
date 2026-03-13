# Render Deployment - Single Container

## 1 minute setup:

1. Go to **render.com** → Sign up with GitHub

2. Click **"New +"** → **"Web Service"**

3. Select repo: **shrutz2/Gesture-Ease**

4. Fill in:
   - **Name:** gesture-ease
   - **Branch:** main
   - **Runtime:** Docker
   - **Instance:** Free (or Starter $7/month)

5. Click **"Create Web Service"**

6. Wait 10-15 minutes for build

7. Done! Your app is live at: `https://gesture-ease.onrender.com`

---

## That's it!

- Frontend runs on port 80
- Backend runs on port 5000
- Nginx proxies /api/ to backend
- Everything in one container ✓

---

## If build fails:

Check logs in Render dashboard. Common issues:
- Model file too large → compress it
- RAM insufficient → upgrade to Starter

---

## Cost:
- Free: $0/month (sleeps after 15 mins)
- Starter: $7/month (always running)
