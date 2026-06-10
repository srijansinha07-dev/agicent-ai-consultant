import { useCallback, useEffect, useState } from 'react'

import { env } from '@/config/env'
import { postChat } from '@/services/api'
import type { ChatHistoryItem, ChatMessage, ViewMode } from '@/types/chat'

const STORAGE_KEY = 'agicent_chat_messages'
const SESSION_KEY = 'agicent_chat_session'

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

export interface UseChatReturn {
  viewMode: ViewMode
  messages: ChatMessage[]
  isLoading: boolean
  error: string | null
  sessionId: string
  setViewMode: (mode: ViewMode) => void
  sendMessage: (query: string) => Promise<void>
  clearMessages: () => void
  goHome: () => void
}

export function useChat(): UseChatReturn {
  const [viewMode, setViewMode] = useState<ViewMode>('closed')
  const [messages, setMessages] = useState<ChatMessage[]>(loadMessages)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [sessionId] = useState(getOrCreateSessionId)

  useEffect(() => {
    saveMessages(messages)
  }, [messages])

  const sendMessage = useCallback(
    async (query: string) => {
      if (!query.trim() || isLoading) return

      const userMessage: ChatMessage = {
        id: generateId(),
        role: 'user',
        content: query.trim(),
        timestamp: Date.now(),
      }

      setMessages((prev) => [...prev, userMessage])
      setIsLoading(true)
      setError(null)

      // Build history from current messages
      const history: ChatHistoryItem[] = messages.map((m) => ({
        role: m.role,
        content: m.content,
      }))

      try {
        const response = await postChat({
          doc_id: env.docId,
          query: query.trim(),
          history,
        }, env.userId, sessionId)

        const intent = computeConsultationIntent(userMessage)

        const assistantMessage: ChatMessage = {
          id: generateId(),
          role: 'assistant',
          content: response.answer,
          sources: response.sources,
          queryType: response.query_type,
          timestamp: Date.now(),
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
        // Remove the user message on failure so they can retry
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
  }, [])

  return {
    viewMode,
    messages,
    isLoading,
    error,
    sessionId,
    setViewMode,
    sendMessage,
    clearMessages,
    goHome: clearMessages,
  }
}
