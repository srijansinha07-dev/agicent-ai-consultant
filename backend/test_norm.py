import re
import time
from indic_transliteration import sanscript
from indic_transliteration.sanscript import transliterate

def _process_hindi_block(text: str) -> str:
    # 1. Transliterate to ITRANS
    t = transliterate(text, sanscript.DEVANAGARI, "itrans")
    
    # 2. Anusvara and Nasals
    t = t.replace('M', 'n').replace('.N', 'n').replace('.n', 'n')
    
    # 3. Trailing Schwa deletion (only lowercase 'a' at word ends)
    t = re.sub(r'a\b', '', t)
    
    # 4. Medial Schwa deletion & Specific Conversational Fixes
    t = re.sub(r'\bchAhatA\b', 'chAhtA', t)
    
    # 5. Vowels & Consonants mapped to conversational Hinglish
    t = re.sub(r'\bA', 'aa', t)
    t = t.replace('A', 'a')
    t = t.replace('uu', 'oo').replace('U', 'oo')
    t = t.replace('ii', 'ee').replace('I', 'ee')
    t = t.replace('chCh', 'chh').replace('Ch', 'chh')
    
    # kyaa -> kya
    t = re.sub(r'\bkyaa\b', 'kya', t, flags=re.IGNORECASE)
    
    # 6. Final cleanups
    t = t.lower()
    t = re.sub(r'\byah\b', 'yeh', t)
    t = re.sub(r'\bvah\b', 'woh', t)
    t = t.replace('|', '.')
    
    return t

def normalize_hinglish(text: str) -> str:
    def replacer(match):
        return _process_hindi_block(match.group(0))
        
    return re.sub(r'[\u0900-\u097F]+', replacer, text)

tests = [
    "मुझे एक AI recruitment platform बनाना है जो resumes screen करे aur candidates rank करे।",
    "क्या FastAPI use karna chahiye ya Node.js?",
    "मैं recruiters aur candidates dono ko support karna chahta hoon.",
    "इस project ka MVP kitne time mein ban sakta hai?",
    "मुझे healthcare assistant banana hai jo appointment booking aur patient records handle kare."
]

tech_terms = [
    "API", "FastAPI", "Node.js", "React", "PostgreSQL", 
    "AWS", "Docker", "LangChain", "OpenAI", "Gemini", 
    "ChromaDB", "Railway", "Vercel"
]

print("=== VALIDATION SET ===")
for text in tests:
    print(f"Original: {text}")
    start = time.perf_counter()
    res = normalize_hinglish(text)
    dur = (time.perf_counter() - start) * 1000
    print(f"Normal:   {res} ({dur:.3f} ms)\n")

print("=== PROTECTION REQUIREMENTS ===")
for term in tech_terms:
    res = normalize_hinglish(term)
    print(f"{term} -> {res} (Protected: {term == res})")
