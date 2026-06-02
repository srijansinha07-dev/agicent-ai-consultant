export type QueryType = 'page' | 'formula' | 'concept' | 'exact'

export type ConfidenceLevel = 'high' | 'medium' | 'low'

export type ViewMode = 'closed' | 'widget' | 'expanded'

export type MessageRole = 'user' | 'assistant'

/** Mirrors backend `history: list[dict]` on ChatRequest. */
export interface ChatHistoryItem {
  role: string
  content: string
  [key: string]: unknown
}

export interface ChatRequest {
  doc_id: string
  query: string
  history?: ChatHistoryItem[]
}

export interface Source {
  doc_id: string
  doc_name: string
  page: number
  text: string
  ocr_sourced: boolean
  confidence: ConfidenceLevel
  label?: string
  url?: string | null
}

export interface ChatResponse {
  answer: string
  query_type: QueryType
  sources: Source[]
}

export interface ChatMessage {
  id: string
  role: MessageRole
  content: string
  sources?: Source[]
  queryType?: QueryType
  timestamp: number
  /** Optional: consultation CTA intent for this assistant message. */
  consultationIntent?: 'request' | 'connect'
}
