import sys
import difflib
import pathlib

sys.path.append(str(pathlib.Path(__file__).parent.absolute()))
from services.voice_transcription import correct_technical_vocabulary

test_cases = [
    ("AI recruitment platform", "AI pavard rikrootament pletphorm", ["AI", "recruitment", "platform"]),
    ("Healthcare assistant", "helth keyar asistent", ["Healthcare", "assistant"]),
    ("FastAPI vs Node.js", "faastapi vs node.js", ["FastAPI", "Node.js"]),
    ("React dashboard", "reeakt daishbord", ["React", "dashboard"]),
    ("PostgreSQL database", "postgreskyuel detabes", ["PostgreSQL", "database"]),
    ("Resume screening", "reejiyooms skreen", ["Resume", "screening"]),
    ("Candidate ranking", "kanidets rainking", ["Candidate", "ranking"]),
    ("Interview scheduling", "intarviyoo shedooling", ["Interview", "scheduling"]),
    ("AWS deployment", "aws deploiment", ["AWS", "deployment"]),
    ("Customer support chatbot", "kastamar sapot chaetbot", ["Customer", "support", "chatbot"])
]

def eval_corrections():
    print("=== AFTER IMPLEMENTATION EVALUATION ===\n")
    
    total_detected = 0
    total_corrected = 0
    
    for target, normalized, target_terms in test_cases:
        corrected = correct_technical_vocabulary(normalized)
        
        # Simple count of how many target terms exist in the corrected string
        # Case insensitive match
        corrected_lower = corrected.lower()
        terms_found = sum(1 for t in target_terms if t.lower() in corrected_lower)
        total_detected += len(target_terms)
        total_corrected += terms_found
        
        print(f"Target:     {target}")
        print(f"RAW WHISPER: [Simulated Devanagari Mapped Output]")
        print(f"NORMALIZED: {normalized}")
        print(f"CORRECTED:  {corrected}")
        print(f"Correction Rate: {terms_found}/{len(target_terms)} fixed")
        print("-" * 50)
        
    print(f"\nOVERALL CORRECTION RATE: {total_corrected}/{total_detected} ({(total_corrected/total_detected)*100:.1f}%)")

if __name__ == "__main__":
    eval_corrections()
