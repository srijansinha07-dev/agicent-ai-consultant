import { useEffect, useMemo, useState } from 'react'

import type { UseChatReturn } from '@/hooks/useChat'

import { ChatInput } from './ChatInput'
import { MessageList } from './MessageList'
import { ConsultationModal } from './ConsultationModal'
import { PanelHeader } from './PanelHeader'
import { StarterPrompts } from './StarterPrompts'

interface ConsultantPanelProps {
  chat: UseChatReturn
}

const STARTER_PROMPTS = [
  'How would Agicent approach building an AI MVP?',
  'What team model fits a 3-month mobile app project?',
  'Which Agicent case studies are relevant for healthcare?',
  'How do we modernize a legacy product with AI?',
]

const WELCOME_MESSAGE =
  "Hi — I'm your Agicent AI Consultant. I'll help you think through MVPs, AI products, team models, and delivery strategy from Agicent's perspective. What are you working on?"

export function ConsultantPanel({ chat }: ConsultantPanelProps) {
  const isExpanded = chat.viewMode === 'expanded'
  const isEmpty = chat.messages.length === 0

  const [modalOpen, setModalOpen] = useState(false)
  const [modalVariant, setModalVariant] = useState<'request' | 'connect'>('request')
  const [modalDefaultDescription, setModalDefaultDescription] = useState<string | undefined>(undefined)

  const [ctaSubmitted, setCtaSubmitted] = useState(false)

  useEffect(() => {
    try {
      const stored = sessionStorage.getItem('agicent_consultation_offer_status')
      if (stored === 'submitted') setCtaSubmitted(true)
    } catch {
      // ignore
    }
  }, [])

  const lastAssistantMessage = useMemo(() => {
    if (chat.messages.length === 0) return null
    const last = chat.messages[chat.messages.length - 1]
    return last.role === 'assistant' ? last : null
  }, [chat.messages])

  const lastUserBeforeAssistant = useMemo(() => {
    if (!lastAssistantMessage) return null
    const lastAssistantIndex = chat.messages.findIndex((m) => m.id === lastAssistantMessage.id)
    if (lastAssistantIndex < 0) return null
    for (let i = lastAssistantIndex - 1; i >= 0; i -= 1) {
      if (chat.messages[i].role === 'user') return chat.messages[i]
    }
    return null
  }, [chat.messages, lastAssistantMessage])

  const showConsultationCta = useMemo(() => {
    if (chat.isLoading) return false
    if (modalOpen) return false
    if (!lastAssistantMessage) return false
    if (ctaSubmitted) return false
    return !!lastAssistantMessage.consultationIntent
  }, [chat.isLoading, modalOpen, lastAssistantMessage, ctaSubmitted])

  const shellStyle: React.CSSProperties = isExpanded
    ? {
        position: 'fixed',
        inset: 0,
        width: '100vw',
        height: '100vh',
        maxWidth: '100vw',
        maxHeight: '100vh',
        zIndex: 2147483000,
        borderRadius: 0,
        border: 'none',
        boxShadow: 'none',
        display: 'flex',
        flexDirection: 'column',
        background: 'var(--bg)',
        overflow: 'hidden',
      }
    : {
        position: 'fixed',
        bottom: '92px',
        right: '24px',
        zIndex: 2147483000,
        width: 'var(--widget-width)',
        height: 'var(--widget-height)',
        maxHeight: 'calc(100vh - 120px)',
        borderRadius: 'var(--radius)',
        display: 'flex',
        flexDirection: 'column',
        background: 'var(--bg)',
        border: '1px solid var(--border-strong)',
        boxShadow: 'var(--shadow-lg)',
        overflow: 'hidden',
        animation: 'expand-panel 0.22s ease-out',
      }

  return (
    <div
      className={isExpanded ? 'consultant-workspace consultant-workspace--expanded' : 'consultant-workspace'}
      style={shellStyle}
      role="dialog"
      aria-label="Agicent AI Consultant"
      data-view-mode={chat.viewMode}
    >
      <PanelHeader
        viewMode={chat.viewMode}
        showHome={!isEmpty}
        onHome={chat.goHome}
        onExpand={() =>
          chat.setViewMode(chat.viewMode === 'expanded' ? 'widget' : 'expanded')
        }
        onClose={() => chat.setViewMode('closed')}
      />

      <div
        className="consultant-workspace-body chat-scroll"
        style={{
          flex: 1,
          overflowY: 'auto',
          overflowX: 'hidden',
          background: isExpanded ? 'var(--bg)' : 'var(--bg-2)',
        }}
      >
        <div className="consultant-workspace-inner">
          {isEmpty ? (
            <StarterPrompts
              welcome={WELCOME_MESSAGE}
              prompts={STARTER_PROMPTS}
              onSelect={chat.sendMessage}
              isExpanded={isExpanded}
            />
          ) : (
            <MessageList
              messages={chat.messages}
              isLoading={chat.isLoading}
              error={chat.error}
            />
          )}

          {showConsultationCta ? (
            <div
              style={{
                margin: '10px 16px 0',
                padding: '12px 14px',
                borderRadius: 14,
                border: '1px solid var(--accent-border)',
                background: 'rgba(240, 90, 40, 0.06)',
              }}
            >
              <button
                type="button"
                onClick={() => {
                  if (!lastAssistantMessage?.consultationIntent) return
                  setModalVariant(lastAssistantMessage.consultationIntent)
                  setModalDefaultDescription(lastAssistantMessage?.consultationSummary)
                  setModalOpen(true)
                }}
                style={{
                  width: '100%',
                  border: 'none',
                  background: 'transparent',
                  color: 'var(--accent)',
                  fontWeight: 800,
                  fontSize: 14,
                  cursor: 'pointer',
                  textAlign: 'left',
                }}
              >
                {lastAssistantMessage?.consultationIntent === 'connect'
                  ? '[Connect with Agicent]'
                  : '[Request Consultation]'}
              </button>
            </div>
          ) : null}
        </div>
      </div>

      <div className={isExpanded ? 'consultant-workspace-footer' : undefined}>
        <ChatInput
          onSend={chat.sendMessage}
          disabled={chat.isLoading}
          isEmpty={isEmpty}
          isExpanded={isExpanded}
        />
      </div>

      <ConsultationModal
        open={modalOpen}
        variant={modalVariant}
        sessionId={chat.sessionId}
        history={chat.messages.map((m) => ({ role: m.role, content: m.content }))}
        defaultProjectDescription={modalDefaultDescription}
        onClose={() => setModalOpen(false)}
        onSuccess={(_payload) => {
          // Mark as submitted so we do not keep re-offering in this session.
          setCtaSubmitted(true)
          try {
            sessionStorage.setItem('agicent_consultation_offer_status', 'submitted')
          } catch {
            // ignore
          }
        }}
      />
    </div>
  )
}
