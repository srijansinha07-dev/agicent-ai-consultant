import sys
from unittest.mock import patch, MagicMock

# Append backend to path so we can import modules
import pathlib
sys.path.append(str(pathlib.Path(__file__).parent.absolute()))

from services.voice_transcription import transcribe_audio, normalize_hinglish

def test_transcribe_flow():
    print("=== TRACING TRANSCRIPTION FLOW ===")
    
    # Mock Faster-Whisper output
    # Real Devanagari output: "नमस्ते, मैं एक healthcare assistant बनाना चाहता हूँ"
    devanagari_transcript = "नमस्ते, मैं एक healthcare assistant बनाना चाहता हूँ"
    
    # Create mock segments
    mock_segment = MagicMock()
    mock_segment.text = devanagari_transcript
    
    # Create mock info
    mock_info = MagicMock()
    mock_info.language = "hi"
    mock_info.language_probability = 0.99
    
    # Create mock model
    mock_model = MagicMock()
    mock_model.transcribe.return_value = ([mock_segment], mock_info)
    
    print(f"1. Whisper Outputs: {devanagari_transcript}")
    print(f"2. Language detected by Whisper: {mock_info.language}")
    
    # Patch the _get_model function in voice_transcription
    with patch('services.voice_transcription._get_model', return_value=mock_model):
        try:
            print("3. Calling transcribe_audio()...")
            # Create a fake audio bytes object to pass validation
            fake_audio = b"fake_webm_data_12345"
            result = transcribe_audio(fake_audio, filename="test.webm", content_type="audio/webm")
            
            print(f"\n4. Final Result returned to API Router:")
            print(f"   text: {result.text}")
            print(f"   language: {result.language}")
            print(f"   confidence: {result.confidence}")
            
            # Check if it was normalized successfully
            expected = normalize_hinglish(devanagari_transcript)
            if result.text == expected:
                print("\n[SUCCESS] Normalization was correctly applied!")
            else:
                print(f"\n[ERROR] Normalization failed. Expected '{expected}', got '{result.text}'")
                
        except Exception as e:
            print(f"Error during execution: {e}")

if __name__ == "__main__":
    test_transcribe_flow()
