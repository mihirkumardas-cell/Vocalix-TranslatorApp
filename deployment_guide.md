# Deployment Guide for Vocalix AI Translator

This guide details how to deploy the Vocalix application to **Netlify** (Frontend) and **Render** (Backend).

## 1. Backend Deployment (Render)

1.  **Repository**: Push your code to a GitHub repository.
2.  **Create Web Service**: In Render, click "New" -> "Web Service".
3.  **Connect Repo**: Connect your Vocalix repository.
4.  **Settings**:
    *   **Runtime**: Python
    *   **Build Command**: `pip install -r requirements.txt` (Ensure you have `fastapi`, `uvicorn`, `gtts`, `edge-tts`, `deep-translator`, `langdetect`, `pydub` listed).
    *   **Start Command**: `uvicorn vocalix_backend:app --host 0.0.0.0 --port $PORT`
5.  **Environment Variables**:
    *   `PORT`: 10000 (standard for Render)
6.  **URL**: Note down your Render URL (e.g., `https://vocalix-backend.onrender.com`).

## 2. Frontend Deployment (Netlify)

1.  **Repository**: Use the same repository or a separate one.
2.  **Create Site**: In Netlify, click "New site from Git".
3.  **Connect Repo**: Select your repository.
4.  **Settings**:
    *   **Base directory**: `.` (if `index.html` is at root).
    *   **Build command**: (Leave empty as it's static HTML).
    *   **Publish directory**: `.`
5.  **Environment Variables**:
    *   `VITE_API_BASE`: Set this to your Render URL.
6.  **Configuration**: Ensure `index.html` uses the correct backend URL. The current code has a `getApiBase()` function that should be updated:

```javascript
function getApiBase() {
  if (window.location.hostname.includes("netlify.app")) {
    return "https://YOUR-RENDER-URL.onrender.com";
  }
  return "http://127.0.0.1:8000";
}
```

## 3. Important Notes
*   **CORS**: The backend is already configured to allow all origins.
*   **FFmpeg**: Render handles dependencies well, but for `pydub`, ensure you don't need manual FFmpeg installation (Render's Python environment usually includes it or handles `pip install` well).
