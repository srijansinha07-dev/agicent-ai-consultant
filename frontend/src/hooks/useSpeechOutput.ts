import { useCallback, useEffect, useRef, useState } from 'react'

export interface SpeechOutputService {
  speak: (text: string, language?: string) => void
  stop: () => void
  isSpeaking: () => boolean
}

function mapLanguageToSpeechCode(language?: string): string {
  if (!language) {
    return 'en-US'
  }

  const code = language.toLowerCase().trim()
  if (code === 'hi' || code.startsWith('hi')) {
    return 'hi-IN'
  }
  if (code === 'en' || code.startsWith('en')) {
    return 'en-US'
  }

  return language
}

const ABBREVIATION_MAP: [RegExp, string][] = [
  [/\bAPI\b/g, 'A P I'],
  [/\bAPIs\b/g, 'A P I s'],
  [/\bNLP\b/g, 'N L P'],
  [/\bML\b/g, 'M L'],
  [/\bLLM\b/g, 'L L M'],
  [/\bLLMs\b/g, 'L L M s'],
  [/\bRAG\b/g, 'R A G'],
  [/\bAWS\b/g, 'A W S'],
  [/\bGCP\b/g, 'G C P'],
  [/\bUI\b/g, 'U I'],
  [/\bUX\b/g, 'U X'],
  [/\bCI\/CD\b/g, 'C I C D'],
  [/\bMVP\b/g, 'M V P'],
  [/\bPOC\b/g, 'P O C'],
  [/\bSQL\b/g, 'S Q L'],
]

const NUMBER_WORDS = ['one','two','three','four','five','six','seven','eight','nine','ten']

export function sanitizeForSpeech(text: string): string {
  let t = text

  // 1. Strip code fences
  t = t.replace(/```[\s\S]*?```/g, ' ')
  t = t.replace(/`([^`]+)`/g, '$1')

  // 2. Replace URLs
  t = t.replace(/https?:\/\/\S+/g, 'A link was provided. ')

  // 3. Convert numbered lists: "1. Item" → "Step one. Item."
  t = t.replace(/^\s*(\d+)\.\s+(.+)$/gm, (_m, num, item) => {
    const word = NUMBER_WORDS[parseInt(num, 10) - 1] ?? num
    return `Step ${word}. ${item.trim()}.`
  })

  // 4. Convert bullet lists: "* Item" or "- Item" → "Item."
  t = t.replace(/^\s*[-*]\s+(.+)$/gm, (_m, item) => `${item.trim()}. `)

  // 5. Strip markdown formatting
  t = t.replace(/\*\*([^*]+)\*\*/g, '$1')   // bold
  t = t.replace(/\*([^*]+)\*/g, '$1')        // italic
  t = t.replace(/_{1,2}([^_]+)_{1,2}/g, '$1') // underscore
  t = t.replace(/#{1,3}\s*/g, '')            // headings
  t = t.replace(/---+/g, '. ')              // separators
  t = t.replace(/\[([^\]]+)\]\([^)]+\)/g, '$1') // [text](url)
  t = t.replace(/[>#]/g, '')

  // 6. Insert natural pause after headers (any ALL-CAPS line or ending in colon)
  t = t.replace(/([A-Z][A-Z\s]{4,}:?)\n/g, '$1. ')

  // 7. Expand abbreviations for pronunciation
  for (const [pattern, replacement] of ABBREVIATION_MAP) {
    t = t.replace(pattern, replacement)
  }

  // 8. Normalise whitespace
  t = t.replace(/\n{2,}/g, '. ')
  t = t.replace(/\n/g, ' ')
  t = t.replace(/\s{2,}/g, ' ')
  t = t.replace(/\.\s*\./g, '.')

  return t.trim()
}

/** @deprecated Use sanitizeForSpeech instead */
function stripMarkdownForSpeech(text: string): string {
  return sanitizeForSpeech(text)
}

function createBrowserSpeechService(): SpeechOutputService | null {
  if (typeof window === 'undefined' || !window.speechSynthesis) {
    return null
  }

  const synthesis = window.speechSynthesis
  let activeUtterance: SpeechSynthesisUtterance | null = null

  // Trigger voice loading immediately
  if (synthesis.onvoiceschanged !== undefined) {
    synthesis.onvoiceschanged = () => {
      synthesis.getVoices()
    }
  }
  synthesis.getVoices()

  return {
    speak(text: string, language?: string): boolean {
      const cleaned = stripMarkdownForSpeech(text)
      if (!cleaned) {
        return false
      }

      synthesis.cancel()

      const utterance = new SpeechSynthesisUtterance(cleaned)
      const targetLang = mapLanguageToSpeechCode(language)
      utterance.lang = targetLang
      utterance.rate = 1
      utterance.pitch = 1

      const voices = synthesis.getVoices()
      if (voices.length > 0) {
        let voice = voices.find((v) => v.lang === targetLang || v.lang.startsWith(targetLang.split('-')[0]))
        if (!voice) {
          voice = voices.find((v) => v.default) || voices[0]
        }
        if (voice) {
          utterance.voice = voice
        }
      }

      utterance.onend = () => {
        if (activeUtterance === utterance) {
          activeUtterance = null
        }
      }
      utterance.onerror = () => {
        if (activeUtterance === utterance) {
          activeUtterance = null
        }
      }

      activeUtterance = utterance
      synthesis.speak(utterance)
      return true
    },
    stop() {
      synthesis.cancel()
      activeUtterance = null
    },
    isSpeaking() {
      return synthesis.speaking
    },
  }
}

export interface UseSpeechOutputReturn {
  isSupported: boolean
  isSpeaking: boolean
  speak: (text: string, language?: string) => void
  stop: () => void
}

export function useSpeechOutput(): UseSpeechOutputReturn {
  const serviceRef = useRef<SpeechOutputService | null>(null)
  const [isSupported, setIsSupported] = useState(false)
  const [isSpeaking, setIsSpeaking] = useState(false)

  useEffect(() => {
    const service = createBrowserSpeechService()
    serviceRef.current = service
    setIsSupported(service !== null)

    return () => {
      service?.stop()
    }
  }, [])

  useEffect(() => {
    if (!isSupported) {
      return undefined
    }

    const intervalId = window.setInterval(() => {
      setIsSpeaking(serviceRef.current?.isSpeaking() ?? false)
    }, 200)

    return () => {
      window.clearInterval(intervalId)
    }
  }, [isSupported])

  const speak = useCallback((text: string, language?: string) => {
    const service = serviceRef.current
    if (!service) {
      return
    }
    service.speak(text, language)
    setIsSpeaking(true)
  }, [])

  const stop = useCallback(() => {
    serviceRef.current?.stop()
    setIsSpeaking(false)
  }, [])

  return {
    isSupported,
    isSpeaking,
    speak,
    stop,
  }
}
