import os
import sys
import pathlib
import time
from gtts import gTTS

sys.path.append(str(pathlib.Path(__file__).parent.absolute()))

from services.voice_transcription import _get_model, normalize_hinglish

test_cases = [
    "AI recruitment platform",
    "Healthcare assistant",
    "FastAPI vs Node.js",
    "React dashboard",
    "PostgreSQL database",
    "Resume screening",
    "Candidate ranking",
    "Interview scheduling",
    "AWS deployment",
    "Customer support chatbot"
]

def generate_and_transcribe():
    print("=== ESTIMATING CURRENT BEHAVIOR ===\n")
    model = _get_model()
    
    for i, phrase in enumerate(test_cases):
        audio_path = f"test_phrase_{i}.mp3"
        # Generate Hindi TTS. Feeding English into a Hindi voice model creates Hinglish pronunciation.
        tts = gTTS(text=phrase, lang='hi')
        tts.save(audio_path)
        
        try:
            segments, info = model.transcribe(
                audio_path,
                beam_size=3,
                language=None,
                task="transcribe",
                vad_filter=True,
                vad_parameters=dict(min_silence_duration_ms=500),
                condition_on_previous_text=False,
                temperature=0.0,
            )
            parts = [s.text.strip() for s in segments if s.text.strip()]
            raw_text = " ".join(parts).strip()
            
            if any("\u0900" <= c <= "\u097f" for c in raw_text):
                norm_text = normalize_hinglish(raw_text)
            else:
                norm_text = raw_text
                
            print(f"[{i+1}] Target: {phrase}")
            print(f"    Raw Whisper Output: {raw_text}")
            print(f"    Normalized Output:  {norm_text}\n")
        except Exception as e:
            print(f"[{i+1}] Target: {phrase} -> ERROR: {e}\n")
            
        if os.path.exists(audio_path):
            os.remove(audio_path)

if __name__ == "__main__":
    generate_and_transcribe()
