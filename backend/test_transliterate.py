import time
from indic_transliteration import sanscript
from indic_transliteration.sanscript import transliterate

tests = [
    "मुझे AI recruitment platform बनाना hai",
    "नमस्ते, मैं एक healthcare assistant बनाना चाहता हूँ"
]

print("=== LATENCY & OUTPUT TEST ===")
for text in tests:
    start = time.perf_counter()
    result = transliterate(text, sanscript.DEVANAGARI, sanscript.ITRANS)
    duration = (time.perf_counter() - start) * 1000
    print(f"Original: {text}")
    print(f"ITRANS: {result}")
    
    # Try optitrans for better readable Hinglish if available
    result2 = transliterate(text, sanscript.DEVANAGARI, sanscript.OPTITRANS)
    print(f"OPTITRANS: {result2}")
    
    # Try hk
    result3 = transliterate(text, sanscript.DEVANAGARI, sanscript.HK)
    print(f"HK: {result3}")
    
    print(f"Time: {duration:.3f} ms\n")
