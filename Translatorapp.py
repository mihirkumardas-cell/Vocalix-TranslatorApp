from fastapi import FastAPI, File, UploadFile
from deep_translator import GoogleTranslator
import speech_recognition as sr
from gtts import gTTS
import io

app = FastAPI()

@app.post("/voice-translate/")
async def voice_translate(target_lang: str, audio: UploadFile = File(...)):
    # Save uploaded audio
    audio_bytes = await audio.read()
    with open("input.wav", "wb") as f:
        f.write(audio_bytes)

    # Speech to text
    recognizer = sr.Recognizer()
    with sr.AudioFile("input.wav") as source:
        audio_data = recognizer.record(source)
        text = recognizer.recognize_google(audio_data)

    # Translate text
    translated = GoogleTranslator(source='auto', target=target_lang).translate(text)

    # Text to speech
    tts = gTTS(translated, lang=target_lang)
    speech_io = io.BytesIO()
    tts.save("output.mp3")
    with open("output.mp3", "rb") as f:
        speech_io.write(f.read())
    speech_io.seek(0)
    return {
        "input_text": text,
        "translated_text": translated,
        "target_lang": target_lang,
        "audio": speech_io.getvalue()   # For frontend: send as audio file
    }

