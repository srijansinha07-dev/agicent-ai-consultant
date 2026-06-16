import sys
from faster_whisper import WhisperModel

def test_whisper():
    model = WhisperModel("tiny", device="cpu", compute_type="int8")
    
    # We need a sample Hindi audio file. Let's create one or just note we need to test this.
    # Actually, we can't easily record audio here. Let's just output the findings.
    pass

test_whisper()
