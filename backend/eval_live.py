import os
import sys
import pathlib
import logging

logging.basicConfig(level=logging.INFO, stream=sys.stdout)
sys.path.append(str(pathlib.Path(__file__).parent.absolute()))

from gtts import gTTS
from services.voice_transcription import transcribe_audio

# Each tuple: (Hindi Devanagari text to speak, target label)
test_cases = [
    ("मुझे एआई रिक्रूटमेंट प्लेटफार्म बनाना है", "AI recruitment platform"),
    ("रेज्यूम स्क्रीनिंग फीचर चाहिए", "Resume screening"),
    ("इंटरव्यू शेड्यूलिंग वर्कफ्लो", "Interview scheduling"),
    ("एक हेल्थकेयर असिस्टेंट बनाना है", "Healthcare assistant"),
    ("फास्ट ए पी आई या नोड जेएस", "FastAPI vs Node.js"),
    ("रिएक्ट डैशबोर्ड बनाना है", "React dashboard"),
]

def run():
    print("=== LIVE PIPELINE VALIDATION ===\n")
    model_loaded = False

    for i, (hindi_text, label) in enumerate(test_cases):
        print(f"[{i+1}] Target label: {label}")
        audio_path = f"_live_test_{i}.mp3"

        tts = gTTS(text=hindi_text, lang='hi')
        tts.save(audio_path)

        with open(audio_path, "rb") as f:
            audio_bytes = f.read()

        try:
            result = transcribe_audio(audio_bytes, filename=audio_path, content_type="audio/mp3")
            print(f"    FINAL_RETURN: {result.text}")
            print(f"    LANGUAGE: {result.language}")
        except Exception as e:
            print(f"    ERROR: {e}")

        print("-" * 60)
        if os.path.exists(audio_path):
            os.remove(audio_path)

if __name__ == "__main__":
    run()
