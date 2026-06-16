import { useCallback, useEffect, useRef, useState } from 'react'

import { env } from '@/config/env'
import { postChat } from '@/services/api'
import type { BookingState, ChatHistoryItem, ChatMessage, ViewMode } from '@/types/chat'

const STORAGE_KEY = 'agicent_chat_messages'
const SESSION_KEY = 'agicent_chat_session'
const LANGUAGE_KEY = 'agicent_chat_language'

function generateId(): string {
  return `${Date.now()}-${Math.random().toString(36).slice(2, 9)}`
}

function loadMessages(): ChatMessage[] {
  try {
    const stored = sessionStorage.getItem(STORAGE_KEY)
    return stored ? JSON.parse(stored) : []
  } catch {
    return []
  }
}

function saveMessages(messages: ChatMessage[]): void {
  try {
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify(messages))
  } catch {
    // ignore
  }
}

function loadUserLanguage(): string | null {
  try {
    return sessionStorage.getItem(LANGUAGE_KEY)
  } catch {
    return null
  }
}

function saveUserLanguage(language: string | null): void {
  try {
    if (language) {
      sessionStorage.setItem(LANGUAGE_KEY, language)
    } else {
      sessionStorage.removeItem(LANGUAGE_KEY)
    }
  } catch {
    // ignore
  }
}

function getOrCreateSessionId(): string {
  try {
    let id = sessionStorage.getItem(SESSION_KEY)
    if (!id) {
      id = generateId()
      sessionStorage.setItem(SESSION_KEY, id)
    }
    return id
  } catch {
    return generateId()
  }
}

function getActiveBooking(): BookingState | null {
  try {
    const raw = sessionStorage.getItem('agicent_active_booking')
    return raw ? (JSON.parse(raw) as BookingState) : null
  } catch {
    return null
  }
}

function computeConsultationIntent(latestUser: ChatMessage): 'request' | 'connect' | undefined {
  const text = latestUser.content.toLowerCase()

  const hasMvp = /(mvp|min(imum)? viable|prototype|poc|po\s*c)/i.test(text)
  const hasProduct = /(product|feature|scope|roadmap|requirements|build|develop|launch|kickoff)/i.test(text)
  const hasAi = /(ai|llm|rag|machine learning|ml|nlp|predictive|predict|agent|chatbot|model)/i.test(text)
  const hasTeamAug =
    /(staff augmentation|team augmentation|augmentation|hire|hiring|developers|developer team|dedicated team|fractional|on\s*demand|contract)/i.test(
      text,
    )
  const hasBudget = /(budget|cost|pricing|price|\$|estimate|range|rate)/i.test(text)
  const hasTimeline = /(timeline|timeframe|how soon|when|start|delivery)/i.test(text)
  const hasActiveProject = /(project|engagement|proposal|statement of work|sow)/i.test(text)

  const signals = [hasMvp, hasProduct, hasAi, hasTeamAug, hasBudget || hasTimeline || hasActiveProject].filter(Boolean)

  if (signals.length < 2) return undefined

  if (hasTeamAug || hasBudget || hasTimeline) return 'connect'
  return 'request'
}

function detectLanguageStyle(text: string, currentLanguage: string | null): string | null {
  const hindiRegex = /[\u0900-\u097F]/
  if (hindiRegex.test(text)) {
    return 'hi'
  }

  const hinglishTerms = [
    'mujhe', 'chahiye', 'banana', 'kaise', 'kya', 'kar sakte', 
    'hain', 'kiya', 'mera', 'aap', 'kaafi', 'zarurat', 'hogi', 'karo', 'karenge', 'liye'
  ]
  const lowerText = text.toLowerCase()
  for (const term of hinglishTerms) {
    if (lowerText.includes(term)) {
      return 'hi'
    }
  }

  const englishTerms = ['what', 'how', 'why', 'can you', 'please', 'explain', 'recommend', 'could you', 'is there', 'tell me']
  for (const term of englishTerms) {
    if (lowerText.includes(term)) {
      return 'en'
    }
  }

  return currentLanguage
}

export interface UseChatReturn {
  viewMode: ViewMode
  messages: ChatMessage[]
  isLoading: boolean
  error: string | null
  sessionId: string
  userLanguage: string | null
  setViewMode: (mode: ViewMode) => void
  sendMessage: (query: string, languageOverride?: string, voiceNoteUrl?: string) => Promise<void>
  setUserLanguage: (language: string) => void
  clearMessages: () => void
  goHome: () => void
}

export function useChat(): UseChatReturn {
  const [viewMode, setViewMode] = useState<ViewMode>('closed')
  const [messages, setMessages] = useState<ChatMessage[]>(loadMessages)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [sessionId] = useState(getOrCreateSessionId)
  const [userLanguage, setUserLanguageState] = useState<string | null>(loadUserLanguage)
  const userLanguageRef = useRef<string | null>(loadUserLanguage())

  useEffect(() => {
    saveMessages(messages)
  }, [messages])

  const setUserLanguage = useCallback((language: string) => {
    userLanguageRef.current = language
    setUserLanguageState(language)
    saveUserLanguage(language)
  }, [])

  const sendMessage = useCallback(
    async (query: string, languageOverride?: string, voiceNoteUrl?: string) => {
      if (!query.trim() || isLoading) return

      let activeLanguage: string | null | undefined = languageOverride
      if (!activeLanguage) {
        const detectedLang = detectLanguageStyle(query, userLanguageRef.current)
        activeLanguage = detectedLang ?? userLanguageRef.current
      }

      if (activeLanguage && activeLanguage !== userLanguageRef.current) {
        setUserLanguage(activeLanguage)
      }

      const userMessage: ChatMessage = {
        id: generateId(),
        role: 'user',
        content: query.trim(),
        timestamp: Date.now(),
        language: activeLanguage ?? undefined,
        voiceNoteUrl: voiceNoteUrl ?? undefined,
      }

      setMessages((prev) => [...prev, userMessage])
      setIsLoading(true)
      setError(null)

      const history: ChatHistoryItem[] = messages.map((m) => ({
        role: m.role,
        content: m.content,
      }))

      try {
        const response = await postChat(
          {
            doc_id: env.docId,
            query: query.trim(),
            history,
            booking_state: getActiveBooking(),
            language: activeLanguage ?? undefined,
          },
          env.userId,
          sessionId,
        )

        const intent = computeConsultationIntent(userMessage)

        const assistantMessage: ChatMessage = {
          id: generateId(),
          role: 'assistant',
          content: response.answer,
          sources: response.sources,
          queryType: response.query_type,
          timestamp: Date.now(),
          language: activeLanguage ?? undefined,
          consultationIntent: response.consultationIntent ?? intent,
          consultationSummary: response.consultationSummary ?? undefined,
          availableSlots: response.availableSlots ?? undefined,
          budget: response.budget ?? undefined,
          timeline: response.timeline ?? undefined,
        }

        setMessages((prev) => [...prev, assistantMessage])
      } catch (err) {
        const message = err instanceof Error ? err.message : 'Something went wrong. Please try again.'
        setError(message)
        setMessages((prev) => prev.filter((m) => m.id !== userMessage.id))
      } finally {
        setIsLoading(false)
      }
    },
    [messages, isLoading, sessionId],
  )

  const clearMessages = useCallback(() => {
    setMessages([])
    setError(null)
    userLanguageRef.current = null
    setUserLanguageState(null)
    saveUserLanguage(null)
  }, [])

  return {
    viewMode,
    messages,
    isLoading,
    error,
    sessionId,
    userLanguage,
    setViewMode,
    sendMessage,
    setUserLanguage,
    clearMessages,
    goHome: clearMessages,
  }
}
