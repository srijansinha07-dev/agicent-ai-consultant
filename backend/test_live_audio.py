import sys
import os
import pathlib
import logging

# Set up logging to stdout so we can see the [VOICE] tags
logging.basicConfig(level=logging.INFO, stream=sys.stdout)

# Append backend to path
sys.path.append(str(pathlib.Path(__file__).parent.absolute()))

from gtts import gTTS
from services.voice_transcription import transcribe_audio

def run_live_test():
    print("=== GENERATING REAL HINDI AUDIO ===")
    tts = gTTS(text="नमस्ते, मैं एक हेल्थकेयर असिस्टेंट बनाना चाहता हूँ", lang='hi')
    audio_path = "test_hindi.mp3"
    tts.save(audio_path)
    print(f"Audio saved to {audio_path}")
    
    print("\n=== RUNNING LIVE TRANSCRIPTION PATH ===")
    with open(audio_path, "rb") as f:
        audio_bytes = f.read()
    
    print("Calling transcribe_audio() on actual Faster-Whisper model...\n")
    try:
        # Note: This will download/load the Whisper model if not already loaded,
        # which might take a few seconds.
        result = transcribe_audio(audio_bytes, filename="test_hindi.mp3", content_type="audio/mp3")
        
        print("\n=== FINAL RETURNED OBJECT TO ROUTER ===")
        print(f"text: {result.text}")
        print(f"language: {result.language}")
        print(f"confidence: {result.confidence}")
    except Exception as e:
        print(f"Error during live transcription: {e}")
        
if __name__ == "__main__":
    run_live_test()
