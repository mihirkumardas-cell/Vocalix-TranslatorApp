# Translator App

This project runs a FastAPI-based translator with:

- Text translation
- Voice file transcription
- Translated speech playback
- A simple browser UI at the root route

## Supported audio upload formats

Upload one of these for voice translation:

- `.wav`
- `.flac`
- `.aiff`
- `.aif`
- `.aifc`

## Install

```powershell
pip install -r requirements.txt
```

## Run

```powershell
python -m uvicorn Translatorapp:app --host 127.0.0.1 --port 8000 --reload
```

Or double-click `start_translator_app.bat`.

## Open in browser

```text
http://127.0.0.1:8000
```

## API endpoints

- `GET /`
- `GET /languages`
- `POST /translate-text`
- `POST /voice-translate`
