export type QueryType = 'page' | 'formula' | 'concept' | 'exact'

export type ConfidenceLevel = 'high' | 'medium' | 'low'

export type ViewMode = 'closed' | 'widget' | 'expanded'

export type MessageRole = 'user' | 'assistant'

/** A bookable calendar slot returned by the backend. */
export interface SlotOption {
  start: string   // ISO datetime
  end: string     // ISO datetime
  display: string // human-readable, e.g. "Tuesday, June 10 at 9:00 AM EDT"
}

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
  session_id?: string // used by consultant agent for stateful memory
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
  consultationIntent?: 'request' | 'connect' | null
  consultationSummary?: string | null
  availableSlots?: SlotOption[] | null
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
  /** Optional: pre-fill text for the consultation form. */
  consultationSummary?: string
  /** Optional: bookable calendar slots returned by the agent. */
  availableSlots?: SlotOption[]
}
