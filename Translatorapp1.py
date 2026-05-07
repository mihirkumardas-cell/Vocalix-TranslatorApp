import speech_recognition as sr
from deep_translator import GoogleTranslator
from gtts import gTTS
from playsound import playsound
import os

def speak_text(text, lang='hi'):
    """Convert text to speech and play it"""
    tts = gTTS(text=text, lang=lang)
    filename = "temp.mp3"
    tts.save(filename)
    playsound(filename)
    os.remove(filename)

recognizer = sr.Recognizer()

# Ask target language
target_lang = input("Enter target language code (hi=Hindi, fr=French, es=Spanish): ")

print(f"✅ Translating into {target_lang.upper()}... Say 'stop' to exit.")

with sr.Microphone() as source:
    recognizer.adjust_for_ambient_noise(source)

    while True:
        print("🎤 Listening...")
        audio = recognizer.listen(source)

        try:
            text = recognizer.recognize_google(audio)
            print("🗣 You said:", text)

            if text.lower() == "stop":
                print("👋 Exiting translator.")
                speak_text("Exiting translator", lang=target_lang)
                break

            translated = GoogleTranslator(source='auto', target=target_lang).translate(text)
            print(f"🌍 Translated ({target_lang}):", translated)

            # Speak translation
            speak_text(translated, lang=target_lang)

        except Exception as e:
            print("⚠ Error:", str(e))