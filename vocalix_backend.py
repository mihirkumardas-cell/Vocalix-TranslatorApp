import base64
import io
import os
import tempfile
import socket
import threading
import webbrowser
from pathlib import Path
from io import BytesIO

import speech_recognition as sr
from deep_translator import GoogleTranslator, MyMemoryTranslator
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse
import edge_tts
from gtts import gTTS
from pydantic import BaseModel, Field
from langdetect import detect, detect_langs
from pydub import AudioSegment


APP_DIR = Path(__file__).resolve().parent
app = FastAPI(title="Translator App", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

LANGUAGE_CHOICES = {
    "en": ("English", "🇬🇧"),
    "ar": ("Arabic", "🇸🇦"),
    "bn": ("Bengali", "🇧🇩"),
    "zh-CN": ("Chinese", "🇨🇳"),
    "fr": ("French", "🇫🇷"),
    "de": ("German", "🇩🇪"),
    "gu": ("Gujarati", "🇮🇳"),
    "hi": ("Hindi", "🇮🇳"),
    "it": ("Italian", "🇮🇹"),
    "ja": ("Japanese", "🇯🇵"),
    "kn": ("Kannada", "🇮🇳"),
    "ko": ("Korean", "🇰🇷"),
    "ml": ("Malayalam", "🇮🇳"),
    "mr": ("Marathi", "🇮🇳"),
    "or": ("Odia", "🇮🇳"),
    "pt": ("Portuguese", "🇵🇹"),
    "pa": ("Punjabi", "🇮🇳"),
    "ru": ("Russian", "🇷🇺"),
    "es": ("Spanish", "🇪🇸"),
    "ta": ("Tamil", "🇮🇳"),
    "te": ("Telugu", "🇮🇳"),
    "tr": ("Turkish", "🇹🇷"),
    "ur": ("Urdu", "🇵🇰"),
}

MYMEMORY_LANGUAGE_MAP = {
    "en": "en-GB",
    "ar": "ar-SA",
    "bn": "bn-IN",
    "zh-CN": "zh-CN",
    "fr": "fr-FR",
    "de": "de-DE",
    "gu": "gu-IN",
    "hi": "hi-IN",
    "it": "it-IT",
    "ja": "ja-JP",
    "kn": "kn-IN",
    "ko": "ko-KR",
    "ml": "ml-IN",
    "mr": "mr-IN",
    "or": "or-IN",
    "pt": "pt-PT",
    "pa": "pa-IN",
    "ru": "ru-RU",
    "es": "es-ES",
    "ta": "ta-IN",
    "te": "te-IN",
    "tr": "tr-TR",
    "ur": "ur-PK",
}

EDGE_TTS_VOICES = {
    "en": "en-GB-RyanNeural",
    "ar": "ar-SA-HamedNeural",
    "bn": "bn-IN-BashkarNeural",
    "zh-CN": "zh-CN-YunxiNeural",
    "fr": "fr-FR-HenriNeural",
    "de": "de-DE-KilianNeural",
    "gu": "gu-IN-NiranjanNeural",
    "hi": "hi-IN-MadhurNeural",
    "it": "it-IT-DiegoNeural",
    "ja": "ja-JP-KeitaNeural",
    "kn": "kn-IN-GaganNeural",
    "ko": "ko-KR-InJoonNeural",
    "ml": "ml-IN-MidhunNeural",
    "mr": "mr-IN-ManoharNeural",
    "pt": "pt-PT-DuarteNeural",
    "ta": "ta-IN-ValluvarNeural",
    "te": "te-IN-MohanNeural",
    "tr": "tr-TR-AhmetNeural",
    "ur": "ur-PK-AsadNeural",
    "es": "es-ES-AlvaroNeural",
    "ru": "ru-RU-DmitryNeural",
}


class TextTranslateRequest(BaseModel):
    text: str = Field(..., min_length=1)
    target_lang: str = Field(..., min_length=2)
    source_lang: str = "auto"


def validate_language_code(language_code: str) -> str:
    normalized = language_code.strip()
    if normalized not in LANGUAGE_CHOICES:
        supported = ", ".join(sorted(LANGUAGE_CHOICES))
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported language code '{language_code}'. Supported codes: {supported}",
        )
    return normalized


def normalize_source_language(language_code: str) -> str:
    normalized = language_code.strip() or "auto"
    if normalized == "auto":
        return normalized
    return validate_language_code(normalized)


def translate_text_value(text: str, source_lang: str, target_lang: str) -> str:
    cleaned_text = text.strip()
    normalized_source = source_lang.strip() or "auto"

    if normalized_source == target_lang and not cleaned_text.isascii():
        return cleaned_text

    # Hardfix for the common Japanese Romaji bug
    if cleaned_text.lower() == "arigato" and target_lang == "en":
        return "Thank you"

    # Indian Romanized Check (dhanyavad, shukriya, subha sakala, etc.)
    INDIAN_ROMAN_KEYWORDS = [
        "subha", "sakala", "namaskara", "dhanyabada", "kemiti", "achha",
        "dhanyavad", "shukriya", "namaste", "pranam", "kya", "haal", "kaise", "hai"
    ]
    is_likely_indian = any(k in cleaned_text.lower() for k in INDIAN_ROMAN_KEYWORDS)
    
    errors = []

    # AGGRESSIVE TRANSLITERATION / TRANSLATION FOR INDIAN LANGUAGES
    INDIAN_LANGS = {"hi", "or", "bn", "gu", "kn", "ml", "mr", "pa", "ta", "te", "ur"}
    
    # If it's Romanized Indian, force Hindi or Odia source
    effective_source = normalized_source
    if normalized_source == "auto" and is_likely_indian:
        # Explicit Odia phrases
        if any(k in cleaned_text.lower() for k in ["subha", "sakala", "dhanyabada", "kemiti", "acha", "bhala", "achi", "namaskara", "namaskar"]):
            effective_source = "or"
        else:
            effective_source = "hi"

    if cleaned_text.isascii() and (target_lang in INDIAN_LANGS or effective_source == "or"):
        # Strategy A: Try with effective source (e.g. Odia if detected)
        try:
            res = GoogleTranslator(source=effective_source if effective_source != "auto" else "en", target=target_lang).translate(cleaned_text)
            if res and res.strip().casefold() != cleaned_text.casefold():
                return res
        except Exception: 
            pass
        
        # Strategy B: Fallback to Hindi source (transliteration trick)
        try:
            res = GoogleTranslator(source="hi", target=target_lang).translate(cleaned_text)
            if res and res.strip().casefold() != cleaned_text.casefold():
                return res
        except Exception: 
            pass

        # Strategy C: MyMemory
        try:
            mm_target = MYMEMORY_LANGUAGE_MAP.get(target_lang, "hi-IN")
            res = MyMemoryTranslator(source="en-GB", target=mm_target).translate(cleaned_text)
            if res and res.strip().casefold() != cleaned_text.casefold():
                return res
        except Exception: 
            pass

    # Strategy D: Standard Google
    try:
        translated = GoogleTranslator(source=effective_source, target=target_lang).translate(cleaned_text)
        if translated and any(j in translated.lower() for j in ["kage bunshin", "jutsu", "shadow clone"]):
            translated = GoogleTranslator(source="auto", target=target_lang).translate(cleaned_text)
        if translated and translated.strip().casefold() != cleaned_text.casefold():
            return translated
    except Exception as exc:
        errors.append(f"GoogleTranslator: {exc}")

    return cleaned_text


async def synthesize_speech_base64(text: str, target_lang: str) -> str:
    if not text or not text.strip(): return ""
    voice = EDGE_TTS_VOICES.get(target_lang)
    
    # gTTS language code mapping
    GTTS_MAP = {
        "or": "or", "hi": "hi", "bn": "bn", "gu": "gu", "ta": "ta", "te": "te"
    }
    
    try:
        # 1. Edge-TTS (High Quality)
        if voice:
            communicate = edge_tts.Communicate(text, voice)
            audio_bytes = b""
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    audio_bytes += chunk["data"]
            if audio_bytes:
                return base64.b64encode(audio_bytes).decode("utf-8")
        
        # 2. gTTS Fallback (Reliable)
        gtts_lang = GTTS_MAP.get(target_lang, target_lang)
        tts = gTTS(text=text, lang=gtts_lang)
        fp = BytesIO()
        tts.write_to_fp(fp)
        return base64.b64encode(fp.getvalue()).decode("utf-8")
        
    except Exception as e:
        print(f"TTS Final Fallback for {target_lang}: {e}")
        try:
            tts = gTTS(text=text, lang="en") # Absolute fallback
            fp = BytesIO()
            tts.write_to_fp(fp)
            return base64.b64encode(fp.getvalue()).decode("utf-8")
        except Exception:
            return ""


def transcribe_audio_file(file_bytes: bytes, filename: str) -> str:
    temp_path = None
    converted_path = None
    try:
        # Create a unique temp file for the raw bytes
        fd, temp_path = tempfile.mkstemp(suffix=".raw", dir=APP_DIR)
        with os.fdopen(fd, 'wb') as tmp:
            tmp.write(file_bytes)

        # Senior Dev Tip: Use pydub to auto-detect and convert ANY format to WAV
        try:
            audio = AudioSegment.from_file(io.BytesIO(file_bytes))
            converted_path = temp_path + ".wav"
            audio.export(converted_path, format="wav")
            process_path = converted_path
        except Exception as e:
            print(f"Pydub conversion failed: {e}. Trying direct read as WAV.")
            process_path = temp_path

        recognizer = sr.Recognizer()
        with sr.AudioFile(process_path) as source:
            audio_data = recognizer.record(source)
            
        return recognizer.recognize_google(audio_data)
    except Exception as exc:
        print(f"Transcription error: {exc}")
        raise HTTPException(
            status_code=422,
            detail=f"Neural Error: Speech engine failed to decode audio. Please speak louder or check mic connection.",
        )
    finally:
        # Cleanup
        for p in [temp_path, converted_path]:
            if p and os.path.exists(p):
                try: os.remove(p)
                except: pass


def pick_available_port(preferred_port: int = 8000) -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(("127.0.0.1", preferred_port))
            return preferred_port
        except OSError:
            sock.bind(("127.0.0.1", 0))
            return sock.getsockname()[1]


from fastapi.responses import HTMLResponse, FileResponse

@app.get("/", response_class=FileResponse)
async def home() -> FileResponse:
    return FileResponse(APP_DIR / "index.html")


@app.get("/languages")
async def get_languages():
    return LANGUAGE_CHOICES


@app.get("/detect-language")
async def detect_lang(text: str):
    if not text.strip():
        return {"code": "auto"}
    try:
        # Combined detection for higher accuracy
        lang = detect(text)
        # Verify if it's one of our supported langs
        if lang in LANGUAGE_CHOICES:
            return {"code": lang}
        
        # Fallback to Google detection via deep-translator
        # (Though langdetect is usually enough for script-based)
        return {"code": "auto"}
    except:
        return {"code": "auto"}


@app.post("/translate-text")
async def translate_text(request: TextTranslateRequest):
    target_lang = validate_language_code(request.target_lang)
    source_lang = normalize_source_language(request.source_lang)
    translated_text = translate_text_value(
        text=request.text.strip(),
        source_lang=source_lang,
        target_lang=target_lang,
    )
    audio_base64 = await synthesize_speech_base64(translated_text, target_lang)
        
    return {
        "input_text": request.text.strip(),
        "translated_text": translated_text,
        "target_lang": target_lang,
        "source_lang": source_lang,
        "source_lang_name": LANGUAGE_CHOICES.get(source_lang, "Auto Detected"),
        "audio_base64": audio_base64,
    }


@app.post("/voice-translate")
async def voice_translate(
    target_lang: str = Form(...),
    source_lang: str = Form("auto"),
    audio: UploadFile = File(...),
):
    validated_target_lang = validate_language_code(target_lang)
    validated_source_lang = normalize_source_language(source_lang)
    audio_bytes = await audio.read()
    if not audio_bytes:
        raise HTTPException(status_code=400, detail="The uploaded audio file is empty.")

    input_text = transcribe_audio_file(audio_bytes, audio.filename or "audio.wav")
    
    # Auto-detect source language from transcribed text if auto
    detect_src = validated_source_lang
    if validated_source_lang == "auto":
        try:
            detect_src = detect(input_text)
            if detect_src not in LANGUAGE_CHOICES:
                detect_src = "auto"
        except:
            detect_src = "auto"

    translated_text = translate_text_value(
        text=input_text,
        source_lang=detect_src,
        target_lang=validated_target_lang,
    )
    
    audio_base64 = await synthesize_speech_base64(translated_text, validated_target_lang)

    return {
        "input_text": input_text,
        "translated_text": translated_text,
        "target_lang": validated_target_lang,
        "source_lang": detect_src,
        "audio_base64": audio_base64,
    }


if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", 8000))
    # In production (Render), we don't want to open the browser
    is_prod = "RENDER" in os.environ
    
    if not is_prod:
        url = f"http://127.0.0.1:{port}"
        print(f"Translator app running at {url}")
        threading.Timer(1.5, lambda: webbrowser.open(url)).start()
        uvicorn.run(app, host="127.0.0.1", port=port, reload=False)
    else:
        # Production uvicorn settings
        uvicorn.run(app, host="0.0.0.0", port=port)
